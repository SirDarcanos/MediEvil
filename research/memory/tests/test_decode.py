from pathlib import Path
import struct
import unittest

from tools import decode


class AddressTests(unittest.TestCase):
    def setUp(self):
        self.data = bytearray(decode.RAM_SIZE)
        struct.pack_into('<I', self.data, 0x100, 0x80001000)
        struct.pack_into('<I', self.data, 0x1530, 0x80100000)
        struct.pack_into('<i', self.data, 0x100024, -40000)

    def test_two_dereferences_use_virtual_addresses_and_byte_offsets(self):
        self.assertEqual(decode.read(self.data, 'int', 0x80000100, 0x530, 0x24), -40000)

    def test_health_does_not_fit_in_byte(self):
        struct.pack_into('<i', self.data, 0x1000, 300)
        self.assertEqual(decode.read(self.data, 'int', 0x80000100, 0), 300)
        self.assertEqual(decode.read(self.data, 'byte', 0x80000100, 0), 44)

    def test_inventory_sentinel_is_ffff_not_00ff(self):
        struct.pack_into('<H', self.data, 0x1080, 65535)
        self.assertEqual(decode.read(self.data, 'ushort', 0x80000100, 0x80), 65535)
        self.assertEqual(decode.read(self.data, 'short', 0x80000100, 0x80), -1)

    def test_reject_invalid_pointers_and_offsets(self):
        for pointer in (0, 0x1f800000, 0x80200000, 0x80001001, 0xa0001000):
            struct.pack_into('<I', self.data, 0x100, pointer)
            with self.assertRaises(ValueError):
                decode.read(self.data, 'int', 0x80000100, 0)
        with self.assertRaises(ValueError):
            decode.read(self.data, 'int', 0x80000100, -1)

    def test_mode_three_does_not_imply_actor_is_ready(self):
        for address, value in ((0x6993c, 0x27bdffe8), (0x69940, 0x240406f0),
                               (0x69958, 0xaf840568), (0xeee64, 3),
                               (0xedb3c, 0x80001000), (0x1530, 0)):
            struct.pack_into('<I', self.data, address, value)
        # A state allocation exists, but its actor registration field is still zero.
        with self.assertRaisesRegex(ValueError, 'main-RAM address'):
            decode.gameplay(self.data)

    def test_persistent_map_fields_do_not_need_an_actor(self):
        struct.pack_into('<I', self.data, 0xedb3c, 0x80001000)
        struct.pack_into('<I', self.data, 0x1530, 0)
        struct.pack_into('<H', self.data, 0x10c8, 65535)
        self.data[0x103a] = 1
        self.assertEqual(decode.read(self.data, 'ushort', 0x800edb3c, 0xc8), 65535)
        self.assertEqual(decode.read(self.data, 'byte', 0x800edb3c, 0x3a), 1)
        with self.assertRaises(ValueError):
            decode.read(self.data, 'int', 0x800edb3c, 0x530, 0x24)

    def test_reject_wrong_game_signature(self):
        with self.assertRaisesRegex(ValueError, 'signature'):
            decode.gameplay(self.data)


if __name__ == '__main__':
    unittest.main()
