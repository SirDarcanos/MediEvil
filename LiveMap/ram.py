"""Read-only emulator RAM readers and version-specific MediEvil decoder.

Named shared-memory transports never pause, control, or write to the game.
See RESEARCH.md for evidence supporting the MediEvil USA offsets.
"""
from __future__ import annotations
import struct
import subprocess
import sys
import time
from emulator_memory import ReadOnlyMapping, emulator_pids
import bizhawk

RAM_SIZE = 0x200000
GAME_STATE_PTR = 0xEDB3C
PLAYER_IN_STATE = 0x530
CURRENT_LEVEL = 0xEEE2C
MODE = 0xEEE64
FRAME = 0xEEE60
POSITION = 0x24
SIGNATURES = (
    (0x21CA4, bytes.fromhex('e8ffbd271000bfafbf66020c000000003367010c000000000df0023ccefa4234')),
    (0x485EC, bytes.fromhex('801f023ca400428ce0ffbd271800b0af2180a0001c00bfaf')),
    (0x99AD0, bytes.fromhex('0f801c3cd4d59c2721f0a00308cd020c04008420')),
)


def physical(pointer: int, length: int = 4) -> int:
    """Admit only aligned main-RAM pointers, never hardware or masked garbage."""
    if 0x80000000 <= pointer < 0x80200000:
        address = pointer - 0x80000000
    elif 0xA0000000 <= pointer < 0xA0200000:
        address = pointer - 0xA0000000
    else:
        raise ValueError('Pointer is not in PS1 main RAM')
    if address & 3 or not 0 <= address <= RAM_SIZE - length:
        raise ValueError('Unaligned or out-of-range pointer')
    return address


def u32(data, offset: int) -> int:
    return struct.unpack_from('<I', data, offset)[0]


def decode_snapshot(data: bytes) -> dict:
    if len(data) != RAM_SIZE:
        raise ValueError('Expected exactly 2 MiB of RAM')
    if any(data[address:address + len(pattern)] != pattern for address, pattern in SIGNATURES):
        return {'status':'waiting_game', 'message':'Waiting for MediEvil USA (SCUS-94227).'}
    mode, level, frame = u32(data, MODE), u32(data, CURRENT_LEVEL), u32(data, FRAME)
    base = {'mode':mode, 'level':level, 'frame':frame}
    if mode != 3:
        return {**base, 'status':'not_playing', 'message':'Menu, movie, or level transition.'}
    if not 0 <= level < 25:
        return {**base, 'status':'loading', 'message':'Waiting for a valid level.'}
    try:
        state_pointer = u32(data, GAME_STATE_PTR)
        state = physical(state_pointer, 0x6F0)
        player_pointer = u32(data, state + PLAYER_IN_STATE)
        player = physical(player_pointer, 0x98)
        xyz = list(struct.unpack_from('<3i', data, player + POSITION))
        # No playable-area/height bounds: falling and wrapping are the use case.
        physics_pointer = u32(data, player + 0x80)
        fixed_xyz = None
        try:
            physics = physical(physics_pointer, 0x3C)
            fixed_xyz = [v / 65536 for v in struct.unpack_from('<3i', data, physics + 0x30)]
        except ValueError:
            pass
    except (ValueError, struct.error):
        return {**base, 'status':'loading', 'message':'Waiting for Dan’s actor.'}
    return {**base, 'status':'live', 'message':'Read-only live position.', 'position':xyz,
            'physics_position':fixed_xyz, 'player_address':f'0x{player_pointer:08x}',
            'state_address':f'0x{state_pointer:08x}'}


def redux_pids() -> list[int]:
    return emulator_pids('redux')


def duckstation_pids() -> list[int]:
    return emulator_pids('duckstation')


def bizhawk_pids() -> list[int]:
    return emulator_pids('bizhawk') if sys.platform == 'win32' else []


class SharedRAM(ReadOnlyMapping):
    def __init__(self, pid: int, name: str | None = None):
        if pid <= 0:
            raise ValueError('Invalid PID')
        self.pid = pid
        super().__init__(name or f'pcsx-redux-wram-{pid}')

    def snapshot(self) -> bytes | None:
        """Retry around frame/level/actor handoff; never pause the emulated CPU."""
        if self.view is None:
            raise RuntimeError('Closed RAM connection')
        for _ in range(3):
            before = tuple(u32(self.view, a) for a in (FRAME, MODE, CURRENT_LEVEL, GAME_STATE_PTR))
            data = bytes(self.view[:])
            after = tuple(u32(self.view, a) for a in (FRAME, MODE, CURRENT_LEVEL, GAME_STATE_PTR))
            inside = tuple(u32(data, a) for a in (FRAME, MODE, CURRENT_LEVEL, GAME_STATE_PTR))
            if before == inside == after:
                # Actor positions are not an atomic transaction. Reject samples that
                # changed while copying, rather than presenting a mixed tuple.
                decoded = decode_snapshot(data)
                if decoded['status'] == 'live':
                    state = physical(u32(data, GAME_STATE_PTR), 0x6F0)
                    actor = u32(data, state + PLAYER_IN_STATE)
                    p = physical(actor, 0x98)
                    if u32(self.view, state + PLAYER_IN_STATE) != actor:
                        continue
                    if self.view[p + POSITION:p + POSITION + 12] != data[p + POSITION:p + POSITION + 12]:
                        continue
                return data
        return None


class DuckStationRAM(SharedRAM):
    def __init__(self, pid: int):
        if sys.platform == 'darwin':
            raise OSError('DuckStation shared RAM is available on Windows/Linux, not macOS.')
        super().__init__(pid, f'duckstation_{pid}')


class Tracker:
    """One reader; auto-discovery never attaches a debugger or controls gameplay."""
    def __init__(self, pid: int | None = None, emulator: str = 'auto', gdb_port: int | None = None):
        if emulator not in ('auto', 'redux', 'duckstation', 'bizhawk'):
            raise ValueError('Unknown emulator')
        if pid is not None and pid <= 0:
            raise ValueError('Invalid PID')
        if gdb_port is not None and (not 1 <= gdb_port <= 65535 or pid is not None or emulator not in ('auto', 'duckstation')):
            raise ValueError('GDB requires a local port, no PID, and auto/DuckStation selection')
        self.gdb_port = gdb_port
        self.next_connect = -10.0
        self.connect_message = 'Waiting to reconnect to exported RAM.'
        self.requested_pid = pid
        self.requested_emulator = emulator
        self.ram_emulator = None
        self.ram = None
        self.last_discovery = -10.0
        self.candidates = []
        self.bizhawk_multiple = False
        self.epoch = 0
        self.previous = None
        self.last_frame_change = time.monotonic()

    def close(self):
        if self.ram:
            self.ram.close()
            self.ram = None

    def sample(self) -> dict:
        now = time.monotonic()
        refreshing_stalled_mapping = False
        result = {'status':'disconnected', 'message':'Start DuckStation, PCSX-Redux or Windows BizHawk and load MediEvil USA (SCUS-94227).'}
        if self.requested_emulator == 'bizhawk' and sys.platform != 'win32':
            return {**result, 'status':'unavailable', 'message':'BizHawk integration currently requires Windows and the bundled Lua bridge.',
                    'epoch':self.epoch, 'sample_time':time.time()}
        if now - self.last_discovery >= 1:
            self.last_discovery = now
            try:
                self.candidates = []
                self.bizhawk_multiple = False
                if self.gdb_port is not None:
                    self.candidates = [(None, 'duckstation-gdb')]
                else:
                    for name, discover in (('redux', redux_pids), ('duckstation', duckstation_pids), ('bizhawk', bizhawk_pids)):
                        if self.requested_emulator in ('auto', name):
                            found = discover()
                            if name == 'bizhawk' and len(found) > 1 and (self.requested_pid is None or self.requested_pid in found):
                                self.bizhawk_multiple = True
                            self.candidates.extend((pid, name) for pid in found
                                                   if self.requested_pid is None or pid == self.requested_pid)
            except (OSError, subprocess.SubprocessError):
                self.candidates = []
                result = {'status':'unavailable', 'message':'Cannot enumerate emulator processes.'}
            if self.ram and (self.ram.pid, self.ram_emulator) not in self.candidates:
                self.close()
                self.epoch += 1
            elif self.ram and self.ram_emulator != 'bizhawk' and self.gdb_port is None and self.previous and now - self.last_frame_change > 1:
                # A reader's mapping can outlive a disabled/reallocated export.
                # Release it before reopening so an orphan Windows object is not
                # mistaken for a paused producer. Genuine pauses retain history.
                self.close()
                refreshing_stalled_mapping = True
        if self.bizhawk_multiple:
            if self.ram:
                self.close(); self.epoch += 1
            return {**result, 'status':'multiple', 'message':'Keep only one BizHawk instance and one copy of the LiveMap Lua script open; --pid cannot disambiguate its shared bridge.',
                    'epoch':self.epoch, 'sample_time':time.time()}
        if not self.ram:
            if len(self.candidates) > 1:
                return {**result, 'status':'multiple', 'message':'Multiple emulators; select one with --emulator and/or --pid.',
                        'pids':[pid for pid, _ in self.candidates],
                        'emulators':[{'pid':pid, 'emulator':name} for pid, name in self.candidates],
                        'epoch':self.epoch, 'sample_time':time.time()}
            if self.candidates and now >= self.next_connect:
                self.next_connect = now + 1
                try:
                    pid, name = self.candidates[0]
                    if name == 'duckstation-gdb':
                        from gdb_reader import GDBRAM
                        self.ram = GDBRAM(self.gdb_port)
                    elif name == 'bizhawk':
                        self.ram = bizhawk.BizHawkRAM(pid)
                    else:
                        self.ram = (DuckStationRAM if name == 'duckstation' else SharedRAM)(pid)
                    self.ram_emulator = name
                    if not refreshing_stalled_mapping:
                        self.epoch += 1
                        self.previous = None
                except (OSError, ValueError):
                    message = ('DuckStation: enable Show Debug Menu under Advanced, then Export Shared Memory under Debugging. Restart the game.'
                               if name == 'duckstation' else 'Redux RAM is not available yet.')
                    if name == 'bizhawk':
                        message = 'BizHawk: load web/bizhawk.lua in Tools > Lua Console; keep one EmuHawk instance open. Windows only.'
                    if name == 'duckstation' and sys.platform == 'darwin':
                        message = 'DuckStation on macOS needs the explicit GDB fallback; shared RAM is Windows/Linux only.'
                    if name == 'duckstation-gdb':
                        message = f'Enable DuckStation GDB on local port {self.gdb_port}. Attachment may pause it; resume manually.'
                    self.connect_message = message
                    if refreshing_stalled_mapping:
                        self.epoch += 1
                        self.previous = None
                    return {**result, 'status':'unavailable', 'message':message, 'pid':pid,
                            'emulator':name, 'epoch':self.epoch, 'sample_time':time.time()}
            elif self.candidates:
                pid, name = self.candidates[0]
                result = {**result, 'status':'unavailable', 'message':self.connect_message, 'pid':pid, 'emulator':name}
        if self.ram:
            try:
                snapshot = self.ram.snapshot()
                result = decode_snapshot(snapshot) if snapshot is not None else {'status':'updating','message':'Waiting for a consistent frame.'}
                result['pid'] = self.ram.pid
                result['emulator'] = self.ram_emulator
                current = (result.get('level'), result.get('player_address'), result.get('frame'))
                if self.previous and (current[:2] != self.previous[:2] or
                        (isinstance(current[2], int) and isinstance(self.previous[2], int) and current[2] < self.previous[2])):
                    self.epoch += 1
                if current[2] != (self.previous[2] if self.previous else None):
                    self.last_frame_change = now
                if result['status'] == 'live' and self.ram_emulator == 'bizhawk' and getattr(self.ram, 'is_paused', False):
                    result['status'] = 'paused'
                    result['message'] = 'BizHawk is paused; the read-only Lua bridge is still updating.'
                if result['status'] == 'live' and now - self.last_frame_change > 1:
                    result['status'] = 'paused'
                    result['message'] = 'Game frame is not advancing.'
                if self.gdb_port is not None:
                    result['message'] += ' GDB attachment may pause DuckStation once; resume manually. No control commands are sent.'
                self.previous = current
            except (OSError, ValueError, struct.error) as error:
                name, pid = self.ram_emulator, self.ram.pid
                self.close()
                self.epoch += 1
                self.next_connect = time.monotonic() + 1
                self.connect_message = (f'BizHawk Lua bridge: {error} Reload the bundled script in Tools > Lua Console.'
                                        if name == 'bizhawk' else 'RAM connection lost; reconnecting.')
                result = {'status':'unavailable','message':self.connect_message, 'emulator':name, 'pid':pid}
        return {**result, 'epoch':self.epoch, 'sample_time':time.time()}
