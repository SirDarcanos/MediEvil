"""Synthetic tests are not proof of the game's live coordinate layout."""
import http.client
import json
from pathlib import Path
import struct
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

import app
import extract_maps as maps
import ram


def fixture(position=(-32000, -200000, 32000), mode=3, level=6, frame=60):
    data = bytearray(ram.RAM_SIZE)
    for address, pattern in ram.SIGNATURES:
        data[address:address + len(pattern)] = pattern
    for address, value in ((ram.MODE, mode), (ram.CURRENT_LEVEL, level), (ram.FRAME, frame),
                           (ram.GAME_STATE_PTR, 0x80100000), (0x100530, 0x80110000),
                           (0x110080, 0x80120000)):
        struct.pack_into('<I', data, address, value)
    struct.pack_into('<3i', data, 0x110024, *position)
    struct.pack_into('<3i', data, 0x120030, 123 << 16, -456 << 16, 789 << 16)
    return data


class DecoderTests(unittest.TestCase):
    def test_signed_world_coordinates_are_not_clamped(self):
        sample = ram.decode_snapshot(fixture())
        self.assertEqual(sample['status'], 'live')
        self.assertEqual(sample['position'], [-32000, -200000, 32000])
        self.assertEqual(sample['physics_position'], [123, -456, 789])
        self.assertEqual(sample['level'], 6)

    def test_full_signed_32_bit_position(self):
        self.assertEqual(ram.decode_snapshot(fixture((-2147483648, 0, 2147483647)))['position'],
                         [-2147483648, 0, 2147483647])

    def test_revision_and_size(self):
        self.assertEqual(ram.decode_snapshot(bytes(ram.RAM_SIZE))['status'], 'waiting_game')
        with self.assertRaises(ValueError):
            ram.decode_snapshot(b'bad')

    def test_non_gameplay_and_bad_level_hide_player(self):
        for mode, level, expected in ((2, 6, 'not_playing'), (3, 25, 'loading')):
            value = ram.decode_snapshot(fixture(mode=mode, level=level))
            self.assertEqual(value['status'], expected)
            self.assertNotIn('position', value)

    def test_bad_actor_pointers_hide_player(self):
        for pointer in (0, 0x801FFFFC, 0x80110001, 0x1F801000, 0x00110000):
            data = fixture()
            struct.pack_into('<I', data, 0x100530, pointer)
            self.assertEqual(ram.decode_snapshot(data)['status'], 'loading')

    def test_uncached_alias(self):
        self.assertEqual(ram.physical(0xA0000120), 0x120)
        for pointer in (0x80200000, 0x80000001, 0xBFC00000):
            with self.assertRaises(ValueError):
                ram.physical(pointer)

    def test_bad_optional_physics_does_not_hide_actor(self):
        data = fixture()
        struct.pack_into('<I', data, 0x110080, 0)
        decoded = ram.decode_snapshot(data)
        self.assertEqual(decoded['status'], 'live')
        self.assertIsNone(decoded['physics_position'])

    def test_consistent_snapshot_and_write_protection(self):
        # Exercise the consistency routine with a read-only bytes view; actual
        # shm_open/O_RDONLY/PROT_READ is separately tested against Redux.
        shared = object.__new__(ram.SharedRAM)
        shared.view = bytes(fixture())
        self.assertEqual(shared.snapshot(), shared.view)
        with self.assertRaises(TypeError):
            shared.view[0] = 1


class FakeRAM:
    data = fixture()
    def __init__(self, pid): self.pid = pid
    def snapshot(self): return bytes(self.data)
    def close(self): pass


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        # Keep Redux examples independent of actual DuckStation instances.
        replacement = patch('ram.duckstation_pids', return_value=[])
        replacement.start()
        self.addCleanup(replacement.stop)

    @patch('ram.SharedRAM', FakeRAM)
    @patch('ram.redux_pids', return_value=[42])
    def test_pause_resume_rewind_disconnect_reconnect(self, discover):
        FakeRAM.data = fixture(frame=60)
        tracker = ram.Tracker()
        with patch('ram.time.monotonic', return_value=10):
            first = tracker.sample()
            self.assertEqual(first['status'], 'live')
        with patch('ram.time.monotonic', return_value=12):
            self.assertEqual(tracker.sample()['status'], 'paused')
        FakeRAM.data = fixture(frame=61)
        with patch('ram.time.monotonic', return_value=13):
            self.assertEqual(tracker.sample()['status'], 'live')
        FakeRAM.data = fixture(frame=1)
        with patch('ram.time.monotonic', return_value=14):
            self.assertGreater(tracker.sample()['epoch'], first['epoch'])
        discover.return_value = []
        with patch('ram.time.monotonic', return_value=16):
            self.assertEqual(tracker.sample()['status'], 'disconnected')
        discover.return_value = [43]
        with patch('ram.time.monotonic', return_value=18):
            self.assertEqual(tracker.sample()['pid'], 43)
        tracker.close()

    @patch('ram.redux_pids', return_value=[42, 43])
    def test_multiple_processes_need_selection(self, _):
        self.assertEqual(ram.Tracker().sample()['status'], 'multiple')

    def test_feed_stale_sample_hides_position(self):
        feed = app.Feed()
        feed.state = {'source':'live', 'sample_time':time.time() - 10, 'position':[1,2,3]}
        self.assertNotIn('position', feed.current())
        self.assertEqual(feed.current()['status'], 'error')

    def test_bad_snapshot_is_explicit_error(self):
        with tempfile.TemporaryDirectory() as d:
            feed = app.Feed(snapshot=Path(d) / 'missing')
            feed.run()
            self.assertEqual(feed.current()['status'], 'error')
            self.assertEqual(feed.current()['source'], 'snapshot')


class ArchiveTests(unittest.TestCase):
    def test_pp20_literal_fixture(self):
        # Bits are consumed from backwards bytes, low bit first.
        bits = [0, 1, 0]  # literal flag + count 3
        for value in b'CBA':
            bits += [int(v) for v in f'{value:08b}']
        bits += [0] * ((-len(bits)) % 8)
        encoded = bytes(sum(bits[i+j] << j for j in range(8)) for i in range(0, len(bits), 8))[::-1]
        self.assertEqual(maps.unpack_pp20(b'PP20\x09\x0a\x0c\x0d' + encoded + b'\0\0\3\0', 3), b'ABC')

    def test_reject_pp20_and_archive_truncation(self):
        for bad in (b'PP20', b'PP20\xff\x00\x00\x00' + b'\0\0\x01\0', b'PP20\x09\x0a\x0c\x0d\0\0\x01\0'):
            with self.assertRaises(ValueError): maps.unpack_pp20(bad)
        with self.assertRaises(ValueError): list(maps.wad_entries(b''))
        with self.assertRaises(ValueError): list(maps.wad_entries(struct.pack('<4I', 1, 0, 99, 0)))

    def test_wad_entry_and_terminator(self):
        data = struct.pack('<4I', 7, 2, 3, 1) + b'abc\0' + struct.pack('<4I', 0xFFFFFFFF, 0, 0, 0)
        self.assertEqual(list(maps.wad_entries(data)), [(7, 2, b'abc')])

    def test_geometry_indices_and_bounds(self):
        data = bytearray(104)
        struct.pack_into('<4sI8sI', data, 0, b'GROF', 20, b'MEDIEVIL', len(data))
        struct.pack_into('<4sI', data, 20, b'GXSP', 84)
        struct.pack_into('<5H2B4I', data, 28, 1, 0, 0, 0, 3, 0, 0, 56, 80, 0, 0)
        struct.pack_into('<6H', data, 56, 0, 1, 2, 0, 0, 0)
        for i, vertex in enumerate(((-1, 0, -2), (2, 0, 3), (0, -5, 0))):
            struct.pack_into('<3h', data, 80 + i*8, *vertex)
        decoded = maps.parse_map(data)
        self.assertEqual(decoded['faces'], [[0,1,2]])
        self.assertEqual(decoded['bounds'], [[-1,2],[-5,0],[-2,3]])
        struct.pack_into('<H', data, 56, 3)
        with self.assertRaises(ValueError): maps.parse_map(data)


class HTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.feed = app.Feed()
        cls.server = app.ThreadingHTTPServer(('127.0.0.1', 0), app.make_handler(cls.feed, {'maps':[]}, 0))
        cls.port = cls.server.server_address[1]
        cls.server.RequestHandlerClass = app.make_handler(cls.feed, {'maps':[]}, cls.port)
        cls.worker = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.worker.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.server.server_close(); cls.worker.join()

    def request(self, path='/', headers=None):
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=2)
        conn.request('GET', path, headers=headers or {})
        response = conn.getresponse()
        result = response.status, dict(response.getheaders()), response.read()
        conn.close()
        return result

    def test_local_state_and_no_cors(self):
        status, headers, body = self.request('/api/state')
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)['status'], 'connecting')
        self.assertNotIn('Access-Control-Allow-Origin', headers)
        self.assertIn("frame-ancestors 'none'", headers['Content-Security-Policy'])

    def test_cross_origin_and_rebinding_denied(self):
        self.assertEqual(self.request(headers={'Host':'evil.example'})[0], 403)
        self.assertEqual(self.request(headers={'Origin':'https://evil.example'})[0], 403)

    def test_local_neutral_marker(self):
        status, headers, body = self.request('/dan.png')
        self.assertEqual(status, 200)
        self.assertEqual(headers['Content-Type'], 'image/svg+xml')
        self.assertEqual(body, (app.ROOT / 'web/marker.svg').read_bytes())
        self.assertTrue(body.startswith(b'<svg'))
        self.assertEqual(self.request('/dan.png', {'Origin':'https://evil.example'})[0], 403)

    def test_file_allowlist(self):
        for path in ('/../ram.py', '/research/boot_probe.lua', '/maps/../../EXE/MEDIEVIL.EXE'):
            self.assertEqual(self.request(path)[0], 404)
        self.assertEqual(self.request('/app.js')[0], 200)
        self.assertEqual(self.request('/terrain.js')[0], 200)


if __name__ == '__main__':
    unittest.main(verbosity=2)
