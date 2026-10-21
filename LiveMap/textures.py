"""Read-only PS1 VLO texels and padded PNG atlases (standard library only).

MediEvil/FrogLord format references are documented in THIRD_PARTY.md.
No resynthesis/upscaling: the atlas retains native texels, with edge gutters.
"""
import base64
import struct
import zlib
from vlo import psx_colour, read_vlo


def vlo_images(data):
    result = {}
    for image in read_vlo(data):
        pixels = list(image.pixels())
        lookup = {p: bytes(psx_colour(p) + [0 if p == 0 else 128 if image.flags & 1 and p & 0x8000 else 255])
                  for p in set(pixels)}
        rgba = b''.join(lookup[p] for p in pixels)
        left, top, crop_w, crop_h = image.crop
        if not (0 <= left < image.width and 0 <= top < image.height and
                0 < crop_w <= image.width - left and 0 < crop_h <= image.height - top):
            raise ValueError(f'Texture {image.texture_id}: invalid content rectangle')
        result[image.texture_id] = {'width': image.width, 'height': image.height, 'rgba': rgba,
                                    'crop': list(image.crop)}
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
