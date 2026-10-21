"""PS1 VLO metadata, palettes and texels shared by colour and atlas extraction.

FrogLord format provenance is retained in THIRD_PARTY.md. Content-rectangle
validation belongs to the atlas consumer; colour means use the entire image.
"""
from collections import Counter
from dataclasses import dataclass
import struct

from binary import region


def psx_colour(pixel):
    return [((pixel >> shift) & 31) * 255 // 31 for shift in (0, 5, 10)]


@dataclass(frozen=True)
class VloImage:
    texture_id: int
    width: int
    height: int
    depth: int
    flags: int
    crop: tuple[int, int, int, int]
    raw: memoryview
    palette: tuple[int, ...] | None

    def pixels(self):
        """Native 16-bit colour words in row order (low nibble first)."""
        if self.depth == 2:
            for pixel, in struct.iter_unpack('<H', self.raw):
                yield pixel
        elif self.depth == 0:
            for byte in self.raw:
                yield self.palette[byte & 15]
                yield self.palette[byte >> 4]
        else:
            for index in self.raw:
                yield self.palette[index]

    def pixel_counts(self):
        """Count palette indices before expanding, keeping mean extraction cheap."""
        if self.depth == 2:
            return Counter(self.pixels())
        indices = Counter(self.raw)
        if self.depth == 0:
            nibbles = Counter()
            for byte, frequency in indices.items():
                nibbles[byte & 15] += frequency
                nibbles[byte >> 4] += frequency
            indices = nibbles
        pixels = Counter()
        for index, frequency in indices.items():
            pixels[self.palette[index]] += frequency
        return pixels


def read_vlo(data):
    """Yield validated image records without imposing a rendering policy."""
    region(data, 0, 20)
    if data[:4] != b'2GRV':
        raise ValueError('Expected PS1 VLO')
    count, images, clut_count, cluts = struct.unpack_from('<4I', data, 4)
    region(data, images, count * 24)
    region(data, cluts, clut_count * 12)
    palettes = {}
    for i in range(clut_count):
        x, y, width, height, pointer = struct.unpack_from('<4HI', data, cluts + i * 12)
        if width not in (16, 256) or not height:
            raise ValueError('Invalid VLO palette dimensions')
        region(data, pointer, width * height * 2)
        # A CLUT ID addresses a row; fog rows remain independent palettes.
        for row in range(height):
            palettes[(x, y + row)] = struct.unpack_from(f'<{width}H', data, pointer + row * width * 2)

    seen = set()
    for i in range(count):
        at = images + i * 24
        x, y, words, height, pointer, texture_id, page, clut, flags = struct.unpack_from('<4HI4H', data, at)
        depth = (page >> 7) & 3
        if depth == 3 or not words or not height:
            raise ValueError('Invalid VLO image dimensions/depth')
        raw = region(data, pointer, words * height * 2)
        palette = None
        if depth != 2:
            palette = palettes.get(((clut & 63) << 4, clut >> 6))
            if palette is None or len(palette) < (16 if depth == 0 else 256):
                raise ValueError('VLO image palette missing or wrong size')
        if texture_id in seen:
            raise ValueError('Duplicate texture ID')
        seen.add(texture_id)
        multiple = (4, 2, 1)[depth]
        u, v, inner_w, inner_h = struct.unpack_from('<4B', data, at + 20)
        crop = (u - (x % 64) * multiple, v - y % 256,
                (inner_w or 256) - bool(flags & 4), (inner_h or 256) - bool(flags & 8))
        yield VloImage(texture_id, words * multiple, height, depth, flags, crop, raw, palette)
