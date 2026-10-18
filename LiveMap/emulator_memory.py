"""Read-only named mappings and process names. No scanning, debugger or write APIs.

DuckStation 00e299795 exports duckstation_<PID> on Windows/Linux when
Hacks/ExportSharedMemory is enabled; its first 2 MiB contain standard PS1 RAM.
macOS DuckStation uses unnamed Mach memory entries, not POSIX shared memory.
"""
from __future__ import annotations
import ctypes
import mmap
import os
from pathlib import Path
import subprocess
import sys

RAM_SIZE = 0x200000
FILE_MAP_READ = 0x0004
TH32CS_SNAPPROCESS = 0x00000002


class ProcessEntry(ctypes.Structure):
    _fields_ = [('dwSize', ctypes.c_uint32), ('cntUsage', ctypes.c_uint32),
                ('th32ProcessID', ctypes.c_uint32), ('th32DefaultHeapID', ctypes.c_void_p),
                ('th32ModuleID', ctypes.c_uint32), ('cntThreads', ctypes.c_uint32),
                ('th32ParentProcessID', ctypes.c_uint32), ('pcPriClassBase', ctypes.c_int32),
                ('dwFlags', ctypes.c_uint32), ('szExeFile', ctypes.c_uint16 * 260)]


def windows_api():
    api = ctypes.WinDLL('kernel32', use_last_error=True)
    signatures = {
        'OpenFileMappingW': ([ctypes.c_uint32, ctypes.c_int, ctypes.c_wchar_p], ctypes.c_void_p),
        'MapViewOfFile': ([ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_size_t], ctypes.c_void_p),
        'UnmapViewOfFile': ([ctypes.c_void_p], ctypes.c_int),
        'CloseHandle': ([ctypes.c_void_p], ctypes.c_int),
        'CreateToolhelp32Snapshot': ([ctypes.c_uint32, ctypes.c_uint32], ctypes.c_void_p),
        'Process32FirstW': ([ctypes.c_void_p, ctypes.POINTER(ProcessEntry)], ctypes.c_int),
        'Process32NextW': ([ctypes.c_void_p, ctypes.POINTER(ProcessEntry)], ctypes.c_int),
    }
    for name, (args, result) in signatures.items():
        function = getattr(api, name)
        function.argtypes, function.restype = args, result
    return api


def win_error(message):
    code = ctypes.get_last_error()
    return OSError(code, message)


def process_names() -> list[tuple[int, str]]:
    if sys.platform != 'win32':
        result = subprocess.run(['ps', '-axo', 'pid=,comm='], capture_output=True,
                                text=True, timeout=3, check=True)
        found = []
        for line in result.stdout.splitlines():
            parts = line.strip().split(None, 1)
            if len(parts) == 2 and parts[0].isdigit():
                found.append((int(parts[0]), Path(parts[1]).name))
        return found
    api = windows_api()
    handle = api.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if handle in (None, ctypes.c_void_p(-1).value):
        raise win_error('Cannot enumerate emulator processes')
    try:
        entry = ProcessEntry()
        entry.dwSize = ctypes.sizeof(entry)
        found = []
        more = api.Process32FirstW(handle, ctypes.byref(entry))
        while more:
            name = bytes(entry.szExeFile).decode('utf-16-le').split('\0', 1)[0]
            found.append((entry.th32ProcessID, name))
            more = api.Process32NextW(handle, ctypes.byref(entry))
        if ctypes.get_last_error() != 18:  # ERROR_NO_MORE_FILES
            raise win_error('Process enumeration interrupted')
        return found
    finally:
        api.CloseHandle(handle)


def emulator_pids(emulator: str) -> list[int]:
    result = []
    for pid, name in process_names():
        name = name.casefold()
        if emulator == 'redux':
            match = name in ('pcsx-redux', 'pcsx-redux.exe')
        elif emulator == 'duckstation':
            match = (name in ('duckstation', 'duckstation-qt') or
                     (name.startswith('duckstation') and name.endswith('.exe')))
        else:
            raise ValueError('Unknown emulator')
        if match:
            result.append(pid)
    return sorted(set(result))


class ReadOnlyMapping:
    def __init__(self, name: str):
        self.view = None
        self._api = None
        self._handle = None
        self._address = None
        if sys.platform == 'win32':
            self._api = windows_api()
            # Open EXISTING only. Python mmap(tagname=...) can create a mapping;
            # it is intentionally not used here.
            self._handle = self._api.OpenFileMappingW(FILE_MAP_READ, False, name)
            if not self._handle:
                raise win_error('Exported RAM mapping is not available')
            self._address = self._api.MapViewOfFile(self._handle, FILE_MAP_READ, 0, 0, RAM_SIZE)
            if not self._address:
                error = win_error('Cannot read exported RAM mapping')
                self.close()
                raise error
            array = (ctypes.c_ubyte * RAM_SIZE).from_address(self._address)
            self.view = memoryview(array).cast('B').toreadonly()
        else:
            lib = ctypes.CDLL(None, use_errno=True)
            # Darwin declares shm_open variadic; arm64 passes varargs differently.
            lib.shm_open.argtypes = [ctypes.c_char_p, ctypes.c_int] + ([] if sys.platform == 'darwin' else [ctypes.c_uint])
            lib.shm_open.restype = ctypes.c_int
            fd = lib.shm_open(name.encode('ascii'), os.O_RDONLY, ctypes.c_uint(0))
            if fd < 0:
                error = ctypes.get_errno()
                raise OSError(error, os.strerror(error), name)
            try:
                if os.fstat(fd).st_size < RAM_SIZE:
                    raise ValueError('Exported RAM mapping is smaller than 2 MiB')
                self.view = mmap.mmap(fd, RAM_SIZE, flags=mmap.MAP_SHARED, prot=mmap.PROT_READ)
            finally:
                os.close(fd)

    def close(self):
        if self.view is not None:
            if isinstance(self.view, memoryview):
                self.view.release()
            else:
                self.view.close()
            self.view = None
        if self._address:
            self._api.UnmapViewOfFile(self._address)
            self._address = None
        if self._handle:
            self._api.CloseHandle(self._handle)
            self._handle = None
