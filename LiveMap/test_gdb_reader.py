"""Explicit GDB fallback acceptance: it must never send game-control commands."""
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch
import struct
import ram
from gdb_reader import MemoryClient, GDBRAM, ProtocolError
from test_minimap import fixture


class GDBCLIExamples(unittest.TestCase):
    def test_read_only_fallback_is_an_explicit_cli_choice(self):
        run = subprocess.run([sys.executable, str(Path(__file__).with_name('app.py')), '--help'],
                             capture_output=True, text=True, timeout=5)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertIn('--gdb-port', run.stdout)
        self.assertIn('pause', run.stdout.casefold())


def packet(payload):
    return b'$' + payload + f'#{sum(payload) % 256:02x}'.encode()


class ScriptedSocket:
    def __init__(self, chunks): self.chunks = list(chunks); self.sent = []
    def sendall(self, data): self.sent.append(data)
    def recv(self, size): return self.chunks.pop(0) if self.chunks else b''
    def settimeout(self, value): pass
    def close(self): pass


class GDBWireExamples(unittest.TestCase):
    def client(self, chunks):
        client = object.__new__(MemoryClient)
        client.socket = ScriptedSocket(chunks)
        client.buffer = bytearray()
        client.timeout = .5
        return client

    def test_fragmented_ack_stop_and_memory_reply(self):
        response = b'+' + packet(b'S02') + packet(b'1234abcd')
        client = self.client([bytes([x]) for x in response])
        self.assertEqual(client.read_many([(0xF1234, 4)]), [bytes.fromhex('1234abcd')])
        self.assertEqual(client.socket.sent, [packet(b'm800f1234,4'), b'+', b'+'])

    def test_hex_length_and_coalesced_multiple_replies(self):
        client = self.client([b'+' + packet(b'00' * 16) + b'+' + packet(b'01' * 4)])
        self.assertEqual(client.read_many([(0, 16), (0x24, 4)]), [bytes(16), bytes([1]) * 4])
        self.assertEqual(client.socket.sent[0], packet(b'm80000000,10') + packet(b'm80000024,4'))

    def test_corrupt_short_error_and_disconnect_replies_are_rejected(self):
        for response in [b'+$1234#00', b'$AAAA# 4', packet(b'12'), packet(b'E01'), b'', packet(b'zzzz')]:
            with self.subTest(response=response):
                client = self.client([response])
                with self.assertRaises(OSError): client.read_many([(0, 2)])

    def test_hardware_and_out_of_bounds_requests_send_nothing(self):
        client = self.client([])
        for span in [(0x1F801000, 4), (-1, 4), (ram.RAM_SIZE - 1, 4), (0, 8193), (0, 0)]:
            with self.assertRaises(ValueError): client.read_many([span])
        self.assertEqual(client.socket.sent, [])


class FixtureMemory:
    def __init__(self, data=None):
        self.data = fixture() if data is None else data
        self.calls = []
        self.mutate = None
    def close(self): pass
    def read_many(self, spans):
        self.calls.append(spans)
        blocks = [bytes(self.data[a:a+n]) for a, n in spans]
        if self.mutate and len(spans) > 8: self.mutate(spans, blocks)
        return blocks


class GDBSnapshotExamples(unittest.TestCase):
    def reader(self, memory):
        with patch('gdb_reader.MemoryClient', return_value=memory): return GDBRAM(19000)

    def test_sparse_reads_decode_actual_raw_tuple_without_bulk_ram_transfer(self):
        memory = FixtureMemory()
        reader = self.reader(memory)
        value = ram.decode_snapshot(reader.snapshot())
        self.assertEqual(value['position'], [-32000, -200000, 32000])
        self.assertEqual(value['physics_position'], [123, -456, 789])
        self.assertLess(sum(n for group in memory.calls for _, n in group), 2048)
        self.assertEqual(ram.decode_snapshot(reader.snapshot())['status'], 'live')

    def test_frame_and_actor_races_are_hidden(self):
        for mutation in ['frame', 'actor']:
            memory = FixtureMemory()
            def mutate(spans, blocks):
                if mutation == 'frame':
                    index = [i for i, (a, n) in enumerate(spans) if a == ram.CURRENT_LEVEL][-1]
                    changed = bytearray(blocks[index])
                    struct.pack_into('<I', changed, ram.FRAME - ram.CURRENT_LEVEL, 61)
                    blocks[index] = changed
                else:
                    blocks[-2] = struct.pack('<3i', 3, 4, 5)
            memory.mutate = mutate
            self.assertIsNone(self.reader(memory).snapshot())

    def test_wrong_game_and_menu_do_not_follow_actor_pointers(self):
        for data, status in [(bytes(ram.RAM_SIZE), 'waiting_game'), (fixture(mode=2), 'not_playing')]:
            memory = FixtureMemory(data)
            self.assertEqual(ram.decode_snapshot(self.reader(memory).snapshot())['status'], status)
            self.assertEqual(len(memory.calls), 1)

    def test_dangling_player_pointer_then_new_level_recovers(self):
        memory = FixtureMemory()
        reader = self.reader(memory)
        self.assertEqual(ram.decode_snapshot(reader.snapshot())['status'], 'live')
        struct.pack_into('<I', memory.data, 0x100530, 0)
        self.assertIsNone(reader.snapshot())
        memory.data = fixture(level=8)
        self.assertEqual(ram.decode_snapshot(reader.snapshot())['level'], 8)


if __name__ == '__main__':
    unittest.main(verbosity=2)
