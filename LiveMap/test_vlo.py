"""Shared VLO parsing and the consumers' intentionally different policies."""
from collections import Counter
import struct
import unittest

from appearance import vlo_colours
from test_appearance import vlo
from textures import vlo_images
from vlo import read_vlo


class VloTests(unittest.TestCase):
    def test_histogram_matches_ordered_texels_at_each_depth(self):
        for depth in (0, 1, 2):
            data = vlo(depth)
            if depth == 2:
                struct.pack_into('<H', data, 56, 0x8000)
            with self.subTest(depth=depth):
                image, = read_vlo(data)
                self.assertEqual(image.pixel_counts(), Counter(image.pixels()))
                self.assertEqual(len(list(image.pixels())), image.width * image.height)

    def test_colour_means_do_not_require_a_valid_crop(self):
        data = vlo()
        data[40] = 250
        self.assertEqual(vlo_colours(data)[42], [128, 128, 0])
        with self.assertRaisesRegex(ValueError, 'content rectangle'):
            vlo_images(data)

    def test_fog_clut_row_is_independent(self):
        data = vlo()
        data.extend(bytes(32))
        struct.pack_into('<H', data, 50, 2)  # Two palette rows.
        struct.pack_into('<H', data, 36, 2 << 6)  # Select the second row.
        struct.pack_into('<2H', data, 92, 31 << 10, 31 << 10)
        self.assertEqual(vlo_colours(data)[42], [0, 0, 255])
        self.assertEqual(vlo_images(data)[42]['rgba'], bytes([0, 0, 255, 255] * 4))

    def test_all_transparent_texels_have_zero_mean_and_alpha(self):
        data = vlo()
        data[56:58] = bytes(2)
        self.assertEqual(vlo_colours(data)[42], [0, 0, 0])
        self.assertEqual(vlo_images(data)[42]['rgba'], bytes(16))

    def test_common_malformed_records_rejected_by_both_consumers(self):
        cases = []
        for offset, fmt, value in ((0, '<4s', b'BAD!'), (8, '<I', 99999),
                                   (16, '<I', 99999), (24, '<H', 0),
                                   (26, '<H', 0), (28, '<I', 99999),
                                   (34, '<H', 3 << 7), (36, '<H', 0),
                                   (48, '<H', 17), (50, '<H', 0),
                                   (52, '<I', 99999)):
            data = vlo()
            struct.pack_into(fmt, data, offset, value)
            cases.append(data)
        cases.append(vlo()[:-1])
        for index, data in enumerate(cases):
            for consumer in (vlo_colours, vlo_images):
                with self.subTest(case=index, consumer=consumer.__name__):
                    with self.assertRaises(ValueError):
                        consumer(data)

    def test_duplicate_texture_ids_rejected_by_both_consumers(self):
        data = bytearray(72)
        struct.pack_into('<4s4I', data, 0, b'2GRV', 2, 20, 0, 68)
        for offset in (20, 44):
            struct.pack_into('<4HI4H4B', data, offset,
                             0, 0, 2, 1, 68, 7, 2 << 7, 0, 0, 0, 0, 2, 1)
        for consumer in (vlo_colours, vlo_images):
            with self.subTest(consumer=consumer.__name__):
                with self.assertRaisesRegex(ValueError, 'Duplicate texture ID'):
                    consumer(data)


if __name__ == '__main__':
    unittest.main()
