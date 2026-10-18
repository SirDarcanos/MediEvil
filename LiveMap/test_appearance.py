import struct
import unittest
from appearance import vertex_colour, vlo_colours, item_spawns, item_label


def vlo(depth=0):
    palette_size = 16 if depth == 0 else 256
    data = bytearray(58 + palette_size * 2)
    struct.pack_into('<4s4I', data, 0, b'2GRV', 1, 20, 1, 44)
    struct.pack_into('<4HI4H4B', data, 20, 0, 0, 1, 1, 56, 42, depth << 7, 64, 0, 0, 0, 4, 1)
    struct.pack_into('<4HI', data, 44, 0, 1, palette_size, 1, 58)
    struct.pack_into('<2H', data, 60, 31, 31 << 5)
    data[56:58] = b'\x21\x21' if depth == 0 else b'\x01\x02'
    return data


class AppearanceTests(unittest.TestCase):
    def test_vertex_colour_is_not_bgr555(self):
        self.assertEqual(vertex_colour(0x8480), [128, 128, 128])
        self.assertEqual(vertex_colour(0xF8F8 | 0x703), [248, 248, 248])
        self.assertEqual(vertex_colour(0), [0, 0, 0])

    def test_palette_texture_means_use_texel_frequencies(self):
        for depth in (0, 1):
            self.assertEqual(vlo_colours(vlo(depth))[42], [128, 128, 0])
        data = vlo()
        data[56:58] = b'\x11\x21'
        self.assertEqual(vlo_colours(data)[42], [191, 64, 0])
        # Haunted Ruins uses a 4-bit texture with the first 16 entries of a 256-colour CLUT.
        data = vlo(1)
        struct.pack_into('<H', data, 34, 0)
        self.assertEqual(vlo_colours(data)[42], [128, 128, 0])

    def test_transparent_padding_excluded_opaque_black_retained(self):
        data = vlo()
        data[56:58] = b'\x10\x10'
        self.assertEqual(vlo_colours(data)[42], [255, 0, 0])
        struct.pack_into('<H', data, 58, 0x8000)
        self.assertEqual(vlo_colours(data)[42], [128, 0, 0])

    def test_direct_colour_texture(self):
        data = bytearray(48)
        struct.pack_into('<4s4I', data, 0, b'2GRV', 1, 20, 0, 44)
        struct.pack_into('<4HI4H4B', data, 20, 0, 0, 2, 1, 44, 7, 2 << 7, 0, 0, 0, 0, 2, 1)
        struct.pack_into('<2H', data, 44, 31, 31 << 10)
        self.assertEqual(vlo_colours(data)[7], [128, 0, 128])

    def test_malformed_texture_data_rejected(self):
        with self.assertRaises(ValueError): vlo_colours(b'2GRV')
        data = vlo()
        struct.pack_into('<I', data, 28, 999999)
        with self.assertRaises(ValueError): vlo_colours(data)
        data = vlo()
        struct.pack_into('<H', data, 36, 0)
        with self.assertRaises(ValueError): vlo_colours(data)

    def test_static_spawn_position_and_category(self):
        data = bytearray(80)
        struct.pack_into('<4sIHHI', data, 0, b'PTME', 80, 1, 0xFFFF, 16)
        struct.pack_into('<IHBB', data, 16, 1234, 49, 7, 0)
        struct.pack_into('<3h', data, 36, -100, -200, 300)
        item = item_spawns(data, 0, 80)[0]
        self.assertEqual(item['name'], 'Coin bag')
        self.assertEqual(item['category'], 'gold')
        self.assertEqual(item['position'], [-100, -200, 300])
        self.assertNotIn('available', item)
        self.assertNotIn('collected', item)
        data[22] = 255
        self.assertEqual(item_spawns(data, 0, 80), [])
        with self.assertRaises(ValueError): item_spawns(data, 0, 79)

    def test_unknown_entities_and_variants_are_not_guessed(self):
        self.assertIsNone(item_label(26, 1))
        self.assertIsNone(item_label(49, 255))
        self.assertIsNone(item_label(5, 17))
        self.assertEqual(item_label(17, 3), ('rune', 'Star rune'))
        self.assertEqual(item_label(49, 3), ('chalice', 'Chalice'))
        self.assertEqual(item_label(49, 1), ('health', 'Life bottle'))


if __name__ == '__main__': unittest.main()
