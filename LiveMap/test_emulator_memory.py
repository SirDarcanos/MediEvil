"""Real POSIX fixture mapping plus Windows ABI doubles; not a Windows live test."""
import ctypes
import mmap
import os
import sys
import unittest
import uuid
from unittest.mock import patch
import emulator_memory as memory
import ram
from test_minimap import fixture


class WindowsMappingExamples(unittest.TestCase):
    class API:
        def __init__(self, opened=41, mapped=True):
            self.data = ctypes.create_string_buffer(bytes(fixture()))
            self.calls = []
            self.opened, self.mapped = opened, mapped
        def OpenFileMappingW(self, *args):
            self.calls.append(('open', args)); return self.opened
        def MapViewOfFile(self, *args):
            self.calls.append(('map', args)); return ctypes.addressof(self.data) if self.mapped else 0
        def UnmapViewOfFile(self, *args): self.calls.append(('unmap', args)); return 1
        def CloseHandle(self, *args): self.calls.append(('close', args)); return 1

    def setUp(self):
        for replacement in (patch('emulator_memory.sys.platform', 'win32'),
                            patch('emulator_memory.win_error', side_effect=lambda msg: OSError(2, msg))):
            replacement.start()
            self.addCleanup(replacement.stop)

    def test_open_existing_only_with_read_rights_and_no_inheritance(self):
        api = self.API()
        with patch('emulator_memory.windows_api', return_value=api):
            reader = ram.DuckStationRAM(73)
            self.assertEqual(api.calls[:2], [('open', (4, False, 'duckstation_73')),
                                            ('map', (41, 4, 0, 0, ram.RAM_SIZE))])
            self.assertEqual(ram.decode_snapshot(reader.snapshot())['position'], [-32000, -200000, 32000])
            self.assertTrue(reader.view.readonly)
            with self.assertRaises(TypeError): reader.view[0] = 7
            reader.close(); reader.close()
        self.assertEqual([x[0] for x in api.calls], ['open', 'map', 'unmap', 'close'])

    def test_missing_mapping_is_not_created(self):
        api = self.API(opened=0)
        with patch('emulator_memory.windows_api', return_value=api):
            with self.assertRaises(OSError): memory.ReadOnlyMapping('duckstation_73')
        self.assertEqual(api.calls, [('open', (4, False, 'duckstation_73'))])

    def test_mapping_failure_closes_handle(self):
        api = self.API(mapped=False)
        with patch('emulator_memory.windows_api', return_value=api):
            with self.assertRaises(OSError): memory.ReadOnlyMapping('duckstation_73')
        self.assertEqual([x[0] for x in api.calls], ['open', 'map', 'close'])

    def test_windows_names_include_release_and_arm_builds(self):
        names = [(1, 'duckstation-qt-x64-ReleaseLTCG.exe'), (2, 'DuckStation-qt-arm64.exe'),
                 (3, 'python.exe'), (4, 'PCSX-Redux.exe')]
        with patch('emulator_memory.process_names', return_value=names):
            self.assertEqual(memory.emulator_pids('duckstation'), [1, 2])
            self.assertEqual(memory.emulator_pids('redux'), [4])


@unittest.skipIf(sys.platform == 'win32', 'POSIX fixture; native Windows smoke is separate')
class POSIXMappingExamples(unittest.TestCase):
    def test_real_read_only_mapping_larger_than_standard_ps1_ram(self):
        lib = ctypes.CDLL(None, use_errno=True)
        lib.shm_open.argtypes = [ctypes.c_char_p, ctypes.c_int] + ([] if sys.platform == 'darwin' else [ctypes.c_uint])
        lib.shm_open.restype = ctypes.c_int
        lib.shm_unlink.argtypes = [ctypes.c_char_p]
        name = f'/me-map-{os.getpid()}-{uuid.uuid4().hex[:6]}'
        fd = lib.shm_open(name.encode(), os.O_CREAT | os.O_EXCL | os.O_RDWR, ctypes.c_uint(0o600))
        self.assertGreaterEqual(fd, 0, os.strerror(ctypes.get_errno()))
        writable = None
        reader = None
        try:
            os.ftruncate(fd, ram.RAM_SIZE * 4)
            writable = mmap.mmap(fd, ram.RAM_SIZE * 4, prot=mmap.PROT_READ | mmap.PROT_WRITE)
            writable[:ram.RAM_SIZE] = fixture()
            reader = memory.ReadOnlyMapping(name)
            self.assertEqual(len(reader.view), ram.RAM_SIZE)
            self.assertEqual(ram.decode_snapshot(bytes(reader.view[:]))['status'], 'live')
            with self.assertRaises(TypeError): reader.view[0] = 5
            self.assertEqual(writable[:ram.RAM_SIZE], fixture())
        finally:
            if reader: reader.close()
            if writable: writable.close()
            os.close(fd)
            lib.shm_unlink(name.encode())


@unittest.skipUnless(sys.platform == 'win32', 'Requires native Windows; never counted as a Mac pass')
class NativeWindowsMappingExample(unittest.TestCase):
    def test_owned_fixture_can_be_opened_without_write_rights(self):
        # Creation/writes are confined to this uniquely named test fixture.
        api = memory.windows_api()
        create = api.CreateFileMappingW
        create.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32,
                           ctypes.c_uint32, ctypes.c_uint32, ctypes.c_wchar_p]
        create.restype = ctypes.c_void_p
        name = f'MediEvilMapReadTest_{os.getpid()}_{uuid.uuid4().hex}'
        handle = create(ctypes.c_void_p(-1), None, 4, 0, ram.RAM_SIZE, name)
        self.assertTrue(handle)
        address = None
        reader = None
        try:
            address = api.MapViewOfFile(handle, 2, 0, 0, ram.RAM_SIZE)
            self.assertTrue(address)
            ctypes.memmove(address, bytes(fixture()), ram.RAM_SIZE)
            reader = memory.ReadOnlyMapping(name)
            self.assertTrue(reader.view.readonly)
            self.assertEqual(ram.decode_snapshot(bytes(reader.view[:]))['position'],
                             [-32000, -200000, 32000])
        finally:
            if reader: reader.close()
            if address: api.UnmapViewOfFile(address)
            api.CloseHandle(handle)


if __name__ == '__main__': unittest.main(verbosity=2)
