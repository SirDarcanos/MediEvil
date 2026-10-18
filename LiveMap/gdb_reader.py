"""Explicit loopback GDB memory-only fallback. Never interrupts/resumes/steps.

DuckStation itself pauses on attachment. The player must resume manually.
Named shared memory is preferable on Windows/Linux. No third-party packages.
"""
from __future__ import annotations
import socket
import time
from ram import (RAM_SIZE, SIGNATURES, GAME_STATE_PTR, PLAYER_IN_STATE, CURRENT_LEVEL,
                 MODE, POSITION, physical, u32)

GLOBAL_SIZE = MODE - CURRENT_LEVEL + 4


class ProtocolError(OSError):
    pass


class MemoryClient:
    def __init__(self, port: int, timeout: float = 1.0):
        if not 1 <= port <= 65535:
            raise ValueError('Invalid GDB port')
        self.timeout = timeout
        self.socket = socket.create_connection(('127.0.0.1', port), timeout=timeout)
        self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.buffer = bytearray()

    def close(self):
        if self.socket is not None:
            self.socket.close()
            self.socket = None

    def _more(self, deadline):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError('GDB memory read timed out')
        self.socket.settimeout(remaining)
        block = self.socket.recv(8192)
        if not block:
            raise ConnectionError('GDB server disconnected')
        self.buffer.extend(block)
        if len(self.buffer) > 65536:
            raise ProtocolError('Oversized GDB reply')

    def _packet(self, deadline):
        while True:
            if not self.buffer:
                self._more(deadline)
            while self.buffer and self.buffer[0] == ord('+'):
                del self.buffer[0]
            if not self.buffer:
                continue
            if self.buffer[0] != ord('$'):
                raise ProtocolError('Unexpected GDB framing or negative acknowledgement')
            end = self.buffer.find(b'#')
            if end < 0:
                if len(self.buffer) > 16385:
                    raise ProtocolError('Oversized GDB packet')
                self._more(deadline)
                continue
            if end > 16385:
                raise ProtocolError('Oversized GDB packet')
            if len(self.buffer) < end + 3:
                self._more(deadline)
                continue
            payload = bytes(self.buffer[1:end])
            checksum = bytes(self.buffer[end + 1:end + 3])
            del self.buffer[:end + 3]
            try:
                valid = (len(checksum) == 2 and all(c in b'0123456789abcdefABCDEF' for c in checksum)
                         and int(checksum, 16) == sum(payload) % 256)
            except ValueError:
                valid = False
            if not valid:
                self.socket.sendall(b'-')
                raise ProtocolError('GDB checksum mismatch')
            self.socket.sendall(b'+')
            return payload

    def read_many(self, spans: list[tuple[int, int]]) -> list[bytes]:
        if not spans or len(spans) > 32:
            raise ValueError('Invalid memory-read batch')
        packets = []
        for address, size in spans:
            if not 0 <= address < RAM_SIZE or not 0 < size <= 8192 or address + size > RAM_SIZE:
                raise ValueError('Only bounded PS1 main-RAM reads are permitted')
            payload = f'm{0x80000000 + address:x},{size:x}'.encode('ascii')
            packets.append(b'$' + payload + f'#{sum(payload) % 256:02x}'.encode('ascii'))
        self.socket.sendall(b''.join(packets))
        deadline = time.monotonic() + self.timeout
        result = []
        stops = 0
        for _, size in spans:
            reply = self._packet(deadline)
            while reply.startswith((b'S', b'T')):
                stops += 1
                if stops > 8:
                    raise ProtocolError('Too many unsolicited GDB stop packets')
                reply = self._packet(deadline)
            if reply.startswith(b'E') and len(reply) == 3:
                raise ProtocolError('GDB server rejected a RAM read')
            if len(reply) != size * 2 or any(c not in b'0123456789abcdefABCDEF' for c in reply):
                raise ProtocolError('Incomplete or non-hex GDB memory reply')
            result.append(bytes.fromhex(reply.decode('ascii')))
        return result


class GDBRAM:
    pid = None  # An explicitly selected port is not proof of a host PID.

    def __init__(self, port):
        self.client = MemoryClient(port)
        self.state = self.actor = self.physics = None

    def close(self):
        self.client.close()

    @staticmethod
    def image(spans, blocks):
        data = bytearray(RAM_SIZE)
        for (address, size), block in zip(spans, blocks):
            assert len(block) == size
            data[address:address + size] = block
        return data

    def _prime(self):
        spans = [(a, len(p)) for a, p in SIGNATURES] + [(CURRENT_LEVEL, GLOBAL_SIZE), (GAME_STATE_PTR, 4)]
        data = self.image(spans, self.client.read_many(spans))
        if (any(data[a:a + len(p)] != p for a, p in SIGNATURES) or
                u32(data, MODE) != 3 or not 0 <= u32(data, CURRENT_LEVEL) < 25):
            return data
        try:
            state = physical(u32(data, GAME_STATE_PTR), 0x6F0)
            pointer = self.client.read_many([(state + PLAYER_IN_STATE, 4)])[0]
            data[state + PLAYER_IN_STATE:state + PLAYER_IN_STATE + 4] = pointer
            actor = physical(u32(pointer, 0), 0x98)
            body = self.client.read_many([(actor, 0x98)])[0]
            self.state, self.actor = state, actor
            try:
                self.physics = physical(u32(body, 0x80), 0x3C)
            except ValueError:
                self.physics = None
            return None
        except ValueError:
            return data

    def snapshot(self):
        if self.state is None:
            initial = self._prime()
            if initial is not None:
                return bytes(initial)
        s, a, p = self.state, self.actor, self.physics
        spans = [(CURRENT_LEVEL, GLOBAL_SIZE), (GAME_STATE_PTR, 4), (s + PLAYER_IN_STATE, 4)]
        spans += [(address, len(pattern)) for address, pattern in SIGNATURES]
        spans += [(a, 0x98)]
        if p is not None:
            spans.append((p, 0x3C))
        base_count = len(spans)
        # Pipeline these checks in one socket write; never pause for consistency.
        spans += [(CURRENT_LEVEL, GLOBAL_SIZE), (GAME_STATE_PTR, 4),
                  (s + PLAYER_IN_STATE, 4), (a + POSITION, 12), (a + 0x80, 4)]
        blocks = self.client.read_many(spans)
        after = blocks[base_count:]
        body = blocks[6]
        try:
            stable = (blocks[0] == after[0] and blocks[1] == after[1] and blocks[2] == after[2]
                      and physical(u32(blocks[1], 0), 0x6F0) == s
                      and physical(u32(blocks[2], 0), 0x98) == a
                      and body[POSITION:POSITION + 12] == after[3]
                      and body[0x80:0x84] == after[4])
        except ValueError:
            stable = False
        if not stable:
            self.state = self.actor = self.physics = None
            return None
        try:
            next_physics = physical(u32(body, 0x80), 0x3C)
        except ValueError:
            next_physics = None
        if next_physics != p:
            self.physics = next_physics
            return None
        return bytes(self.image(spans[:base_count], blocks[:base_count]))
