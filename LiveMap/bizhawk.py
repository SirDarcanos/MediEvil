"""Read-only Windows BizHawk Lua bridge. Never reads or writes process memory.

The bundled Lua script exports a small, seqlocked sparse PS1 RAM snapshot using
BizHawk's own named-MMF API. The normal USA decoder remains authoritative.
"""
from __future__ import annotations
import struct
import sys
import time
from emulator_memory import ReadOnlyMapping, RAM_SIZE, emulator_pids

MAPPING_NAME = 'MediEvilLiveMap-BizHawk-v1'
PACKET_SIZE = 512
HEADER = struct.Struct('<4s7I')


def decode_packet(packet: bytes, now: float) -> tuple[bytes, bool, int]:
    if len(packet) != PACKET_SIZE:
        raise ValueError('Invalid BizHawk bridge packet size')
    magic, version, sequence, timestamp, status, count, reserved1, reserved2 = HEADER.unpack_from(packet)
    if magic != b'MLBH' or version != 1 or reserved1 or reserved2:
        raise ValueError('Unsupported BizHawk bridge protocol')
    if sequence & 1:
        raise ValueError('BizHawk export is being updated')
    if status not in (1, 2):
        raise OSError('Load a PS1 game and run the LiveMap Lua bridge in BizHawk.')
    if not -1 <= now - timestamp <= 2.5:
        raise OSError('BizHawk Lua bridge is stale; keep its script running.')
    if not 1 <= count <= 16:
        raise ValueError('Invalid BizHawk segment count')
    ram = bytearray(RAM_SIZE)
    offset = HEADER.size
    ranges = []
    for _ in range(count):
        if offset + 8 > len(packet):
            raise ValueError('Truncated BizHawk segment header')
        address, length = struct.unpack_from('<II', packet, offset)
        offset += 8
        if not length or address + length > RAM_SIZE or offset + length > len(packet):
            raise ValueError('Out-of-range BizHawk RAM segment')
        if any(address < end and address + length > start for start, end in ranges):
            raise ValueError('Overlapping BizHawk RAM segments')
        ranges.append((address, address + length))
        ram[address:address + length] = packet[offset:offset + length]
        offset += length
    if any(packet[offset:]):
        raise ValueError('Invalid BizHawk packet padding')
    return bytes(ram), status == 2, sequence


class BizHawkRAM:
    def __init__(self, pid: int):
        if sys.platform != 'win32':
            raise OSError('The BizHawk Lua bridge currently supports Windows only.')
        self.pid = pid
        self.mapping = ReadOnlyMapping(MAPPING_NAME, size=PACKET_SIZE)
        self.is_paused = False
        self._sequence = None
        self._updated_at = time.monotonic()
        self._seen_advance = False

    def _check_producer(self):
        # The bridge is shared, unlike Redux/DuckStation's per-PID mappings.
        # Do not rely on the tracker's slower discovery cache to bind a writer.
        if emulator_pids('bizhawk') != [self.pid]:
            raise OSError('Keep exactly one EmuHawk instance open for the LiveMap bridge.')

    def snapshot(self) -> bytes | None:
        self._check_producer()
        for _ in range(3):
            before = bytes(self.mapping.view[:HEADER.size])
            if struct.unpack_from('<I', before, 8)[0] & 1:
                continue
            packet = bytes(self.mapping.view[:PACKET_SIZE])
            after = bytes(self.mapping.view[:HEADER.size])
            if before != after or packet[:HEADER.size] != before:
                continue
            self._check_producer()
            ram, paused, sequence = decode_packet(packet, time.time())
            now = time.monotonic()
            if self._sequence is None:
                self._sequence = sequence
                self._updated_at = now
                return None  # Do not admit an orphan mapping just because it exists.
            if sequence != self._sequence:
                self._sequence = sequence
                self._updated_at = now
                self._seen_advance = True
            if now - self._updated_at > 1.5:
                raise OSError('BizHawk Lua bridge stopped updating; restart its script.')
            if not self._seen_advance:
                return None
            self.is_paused = paused
            return ram
        return None

    def close(self):
        self.mapping.close()
