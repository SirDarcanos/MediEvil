"""Read-only PS1 VLO texels and padded PNG atlases (standard library only).

MediEvil/FrogLord format references are documented in THIRD_PARTY.md.
No resynthesis/upscaling: the atlas retains native texels, with edge gutters.
"""
import base64
import struct
import zlib
from appearance import region, psx_colour


def vlo_images(data):
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
        for row in range(height):
            palettes[(x, y + row)] = struct.unpack_from(f'<{width}H', data, pointer + row * width * 2)
    result = {}
    for i in range(count):
        at = images + i * 24
        x, y, words, height, pointer, tid, page, clut, flags = struct.unpack_from('<4HI4H', data, at)
        depth = (page >> 7) & 3
        if depth == 3 or not words or not height:
            raise ValueError('Invalid VLO image dimensions/depth')
        raw = region(data, pointer, words * height * 2)
        multiple = (4, 2, 1)[depth]
        width = words * multiple
        if depth == 2:
            pixels = [v[0] for v in struct.iter_unpack('<H', raw)]
        else:
            palette = palettes.get(((clut & 63) << 4, clut >> 6))
            if palette is None or len(palette) < (16 if depth == 0 else 256):
                raise ValueError('VLO image palette missing or wrong size')
            pixels = ([palette[n] for byte in raw for n in (byte & 15, byte >> 4)]
                      if depth == 0 else [palette[n] for n in raw])
        lookup = {p: bytes(psx_colour(p) + [0 if p == 0 else 128 if flags & 1 and p & 0x8000 else 255]) for p in set(pixels)}
        rgba = b''.join(lookup[p] for p in pixels)
        u, v, inner_w, inner_h = struct.unpack_from('<4B', data, at + 20)
        # Stored UV origin includes VRAM page offset and the image's padding.
        left, top = u - (x % 64) * multiple, v - y % 256
        crop_w = (inner_w or 256) - bool(flags & 4)
        crop_h = (inner_h or 256) - bool(flags & 8)
        if not (0 <= left < width and 0 <= top < height and
                0 < crop_w <= width - left and 0 < crop_h <= height - top):
            raise ValueError(f'Texture {tid}: invalid content rectangle')
        if tid in result:
            raise ValueError('Duplicate texture ID')
        result[tid] = {'width': width, 'height': height, 'rgba': rgba,
                       'crop': [left, top, crop_w, crop_h]}
    return result


def png_rgba(width, height, rgba):
    if len(rgba) != width * height * 4:
        raise ValueError('PNG dimensions do not match pixels')
    def chunk(tag, payload):
        return struct.pack('>I', len(payload)) + tag + payload + struct.pack('>I', zlib.crc32(tag + payload))
    rows = b''.join(b'\0' + rgba[y * width * 4:(y + 1) * width * 4] for y in range(height))
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>2I5B', width, height, 8, 6, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(rows, 9)) + chunk(b'IEND', b''))


def texture_atlas(images, used):
    """Shelf-pack only referenced textures, with two-texel duplicated borders."""
    width, x, y, row_height = 1024, 0, 0, 0
    placements = {}
    for tid in sorted(set(used)):
        if tid not in images:
            raise ValueError(f'Atlas texture {tid} missing')
        _, _, w, h = images[tid]['crop']
        if w + 4 > width:
            raise ValueError('Texture too wide for atlas')
        if x + w + 4 > width:
            x, y, row_height = 0, y + row_height, 0
        placements[tid] = [x + 2, y + 2, w, h]
        x += w + 4
        row_height = max(row_height, h + 4)
    height = 1
    while height < y + row_height:
        height *= 2
    if height > 2048:
        raise ValueError('Texture atlas exceeds size limit')
    rgba = bytearray(width * height * 4)
    for tid, (ax, ay, w, h) in placements.items():
        image = images[tid]
        left, top, _, _ = image['crop']
        for dy in range(-2, h + 2):
            sy = top + min(h - 1, max(0, dy))
            for dx in range(-2, w + 2):
                sx = left + min(w - 1, max(0, dx))
                src = (sy * image['width'] + sx) * 4
                dst = ((ay + dy) * width + ax + dx) * 4
                rgba[dst:dst + 4] = image['rgba'][src:src + 4]
    return {'width': width, 'height': height, 'rects': placements,
            'png': 'data:image/png;base64,' + base64.b64encode(png_rgba(width, height, rgba)).decode('ascii')}
