"""Read-only map extraction for the SHA-1-identified US retail MediEvil disc.

Format references: FrogLord's ntsc-u-master.cfg, MWIResourceEntry, WADFile,
MediEvilMapGraphicsPacket, MediEvilMapPolygon and SVector. See THIRD_PARTY.md.
No FrogLord installation, Java, or third-party Python modules are needed.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import struct
from binary import region
from appearance import vertex_colour, vlo_colours, item_spawns
from textures import vlo_images, texture_atlas
from triggers import exit_triggers
from scripted_exits import ROUTES, scripted_exit_events
from objects import Definitions, placed_objects, flatten_objects
from edge_on import fence_faces, terrain_fence_proxies

EXE_SHA1 = '265ce5dc508002a339ae535e49a5b1b4e683b732'
LEVELS = [
    ('TL', 'Title'), ('GY1', 'The Graveyard'), ('GY2', 'Return to the Graveyard'),
    ('CH', 'Cemetery Hill'), ('DC', 'The Hilltop Mausoleum'), ('SF', 'Scarecrow Fields'),
    ('CR', "Dan’s Crypt"), ('AC', 'The Ant Caves'), ('CC', 'The Crystal Caves'),
    ('PG', 'Pumpkin Gorge'), ('PS', 'The Pumpkin Serpent'), ('SV', 'The Sleeping Village'),
    ('PD', 'Pools of the Ancient Dead'), ('AG', 'The Asylum Grounds'), ('IA', 'Inside the Asylum'),
    ('EE', 'The Enchanted Earth'), ('GG', 'The Gallows Gauntlet'),
    ('HR', 'The Haunted Ruins'), ('HH', 'Hall of Heroes'), ('GS', 'The Ghost Ship'),
    ('EH', 'The Entrance Hall'), ('TD', 'The Time Device'), ('LA', 'The Lake'),
    ('ZL', 'Zarok’s Lair'), ('PP', "Programmer’s Playground"),
]
# Names above are presentation only; resource IDs and overlay IDs come from the EXE.


def unpack_pp20(data: bytes, expected: int | None = None) -> bytes:
    """Decode the backwards PowerPacker bitstream, with bounded output/references."""
    if data[:4] != b'PP20':
        if expected is not None and len(data) != expected:
            raise ValueError('Uncompressed resource size mismatch')
        return data
    if len(data) < 12:
        raise ValueError('Truncated PP20 header')
    size = int.from_bytes(data[-4:-1], 'big')
    if not 0 < size <= 16 * 1024 * 1024 or (expected is not None and size != expected):
        raise ValueError('Invalid PP20 output size')
    widths = data[4:8]
    if any(not 1 <= w <= 16 for w in widths) or data[-1] > 31:
        raise ValueError('Invalid PP20 parameters')
    # Backwards bytes, low bit first within each byte.
    byte, bit = len(data) - 5, 0
    def bits(n: int) -> int:
        nonlocal byte, bit
        value = 0
        for _ in range(n):
            if byte < 8:
                raise ValueError('Truncated PP20 stream')
            value = (value << 1) | ((data[byte] >> bit) & 1)
            bit += 1
            if bit == 8:
                byte -= 1
                bit = 0
        return value
    bits(data[-1])
    out = bytearray(size)
    pos = size
    while pos:
        if bits(1) == 0:
            count = 1
            while True:
                extra = bits(2)
                count += extra
                if extra != 3:
                    break
            if count > pos:
                raise ValueError('PP20 literal exceeds output')
            for _ in range(count):
                pos -= 1
                out[pos] = bits(8)
        if not pos:
            break
        kind = bits(2)
        width = (7 if bits(1) == 0 else widths[kind]) if kind == 3 else widths[kind]
        distance = bits(width) + 1
        count = kind + 2
        if kind == 3:
            while True:
                extra = bits(3)
                count += extra
                if extra != 7:
                    break
        if count > pos:
            raise ValueError('PP20 match exceeds output')
        for _ in range(count):
            pos -= 1
            source = pos + distance
            if source >= size:
                raise ValueError('PP20 match outside decoded data')
            out[pos] = out[source]
    return bytes(out)


def wad_entries(data: bytes):
    pos = 0
    while pos + 16 <= len(data):
        rid, kind, size, count = struct.unpack_from('<4I', data, pos)
        pos += 16
        if rid == 0xffffffff:
            return
        if size > len(data) - pos:
            raise ValueError('WAD entry extends beyond archive')
        yield rid, kind, unpack_pp20(data[pos:pos + size])
        pos = (pos + size + 3) & ~3
    raise ValueError('WAD has no terminator')


def parse_map(data: bytes, textures: dict | None = None, remap: bytes | None = None, scripted_events: dict | None = None) -> dict:
    if data[:4] != b'GROF' or data[8:16] != b'MEDIEVIL':
        raise ValueError('Not a MediEvil map')
    declared_size = struct.unpack_from('<I', data, 16)[0]
    if declared_size != len(data):
        raise ValueError('Map size mismatch')
    pos = 0
    graphics = None
    collision_chunk = grid_chunk = None
    items = []
    while pos < len(data):
        if pos + 8 > len(data):
            raise ValueError('Truncated map chunk')
        tag, size = struct.unpack_from('<4sI', data, pos)
        if size < 8 or pos + size > len(data):
            raise ValueError(f'Invalid map chunk {tag!r} at {pos:x}')
        if tag == b'GXSP':
            graphics = pos
        if tag == b'PTME':
            items = item_spawns(data, pos, pos + size)
        if tag == b'PLOC': collision_chunk = (pos, pos + size)
        if tag == b'DIRG': grid_chunk = (pos, pos + size)
        pos += size
    if graphics is None:
        raise ValueError('No graphics chunk')
    base = graphics + 8
    g3, g4, gt3, gt4, vertex_count, grid, reserved = struct.unpack_from('<5H2B', data, base)
    polygon_ptr, vertex_ptr, grid_offsets, grid_lengths = struct.unpack_from('<4I', data, base + 12)
    poly_count = g3 + g4 + gt3 + gt4
    if not vertex_count or not poly_count or polygon_ptr + poly_count * 20 > len(data) or vertex_ptr + vertex_count * 8 > len(data):
        raise ValueError('Map geometry outside resource')
    vertices = [list(struct.unpack_from('<3h', data, vertex_ptr + i * 8)) for i in range(vertex_count)]
    colours = [vertex_colour(struct.unpack_from('<H', data, vertex_ptr + i * 8 + 6)[0]) for i in range(vertex_count)]
    faces, face_colours, face_textures, face_uvs = [], [], [], []
    for i in range(poly_count):
        a, b, c, d, texture, flags = struct.unpack_from('<6H', data, polygon_ptr + i * 20)
        order = [0, 1, 3, 2] if flags & 1 else [0, 1, 2]
        face = [[a, b, c, d][j] for j in order]
        raw_uvs = list(struct.iter_unpack('<2B', data[polygon_ptr + i * 20 + 12:polygon_ptr + i * 20 + 20]))
        face_uvs.append([list(raw_uvs[j]) for j in order])
        global_id = None
        if any(v >= vertex_count for v in face):
            raise ValueError('Invalid polygon vertex index')
        faces.append(face)
        shade = [sum(colours[v][c] for v in face) / len(face) for c in range(3)]
        if flags & 2 and textures is not None:
            if remap is None:
                raise ValueError('Texture remap missing')
            region(remap, texture * 2, 2)
            global_id = struct.unpack_from('<H', remap, texture * 2)[0]
            if global_id not in textures:
                raise ValueError(f'Texture {texture}/{global_id} missing from level VLO')
            shade = [min(255, shade[c] * textures[global_id][c] / 128) for c in range(3)]
        face_colours.append([round(c) for c in shade])
        face_textures.append(global_id)
    bounds = [[min(v[i] for v in vertices), max(v[i] for v in vertices)] for i in range(3)]
    exits = exit_triggers(data, collision_chunk, grid_chunk, scripted_events)
    return {'vertices': vertices, 'faces': faces, 'bounds': bounds,
            'exits': exits, 'exit_source': 'Authored PLOC volumes routed to level completion; static, not live activation',
            'face_colours': face_colours, 'items': items, 'appearance_version': 2,
            'vertex_colours': colours, 'face_textures': face_textures, 'face_uvs': face_uvs,
            'colour_source': 'VLO texture means modulated by original vertex colours' if textures is not None else 'vertex colours only',
            'item_source': 'Static PTME spawns; availability is not tracked',
            'source_sha256': hashlib.sha256(data).hexdigest()}


def extract(exe_path: Path, archive_path: Path, destination: Path) -> dict:
    exe = exe_path.read_bytes()
    if hashlib.sha1(exe).hexdigest() != EXE_SHA1:
        raise ValueError('Unsupported executable revision; expected retail USA SCUS-94227')
    destination.mkdir(parents=True, exist_ok=True)
    definitions = Definitions(exe, exe_path.parent)
    manifest = {'game': 'MediEvil (USA)', 'exe_sha1': EXE_SHA1, 'coordinate_units': 'raw PS1 world units', 'maps': []}
    with archive_path.open('rb') as archive:
        for index, (code, name) in enumerate(LEVELS):
            table = struct.unpack_from('<25I', exe, 0xb91d0 + index * 100)
            rid, overlay = table[0], table[19]
            if rid >= 790:
                raise ValueError('Invalid WAD resource ID')
            _, flags, kind, sector, _, _, packed, unpacked = struct.unpack_from('<8I', exe, 0xad064 + rid * 32)
            if not flags & 4 or packed > 16 * 1024 * 1024:
                raise ValueError('Invalid level WAD index')
            archive.seek(sector * 2048)
            blob = archive.read(packed)
            if len(blob) != packed:
                raise ValueError('Archive truncated')
            wad = unpack_pp20(blob, unpacked & 0xffffff)
            resources = {r:b for r,k,b in wad_entries(wad)}
            found = [(r,b) for r,b in resources.items() if b.startswith(b'GROF')]
            if len(found) != 1:
                raise ValueError(f'{code}: expected one map, found {len(found)}')
            map_rid, map_data = found[0]
            vlo_rid = table[1]
            if not 0 <= vlo_rid < 790:
                raise ValueError('Invalid VLO resource ID')
            vlo_entry = struct.unpack_from('<8I', exe, 0xad064 + vlo_rid * 32)
            if vlo_entry[6] > 16 * 1024 * 1024:
                raise ValueError('VLO resource too large')
            archive.seek(vlo_entry[3] * 2048)
            vlo_packed = archive.read(vlo_entry[6])
            if len(vlo_packed) != vlo_entry[6]:
                raise ValueError('VLO resource truncated')
            vlo = unpack_pp20(vlo_packed, vlo_entry[7] & 0xffffff)
            remap_offset = table[3] - (0x80021ca4 - 0x800)
            region(exe, remap_offset, 2)
            means, images = vlo_colours(vlo), vlo_images(vlo)
            script_proofs = {}
            if code in ROUTES:
                overlay_data, overlay_base = definitions.overlay(index)
                script_proofs = scripted_exit_events(code, overlay_data, overlay_base, table[2])
            geometry = parse_map(map_data, means, exe[remap_offset:], script_proofs)
            objects = placed_objects(map_data, definitions, index, resources, images)
            geometry['object_mesh'] = flatten_objects(objects, means)
            geometry['objects'] = objects['instances']
            geometry['scene_bounds'] = [[min([geometry['bounds'][j][0]]+[o['bounds'][j][0] for o in objects['instances']]),
                                         max([geometry['bounds'][j][1]]+[o['bounds'][j][1] for o in objects['instances']])] for j in range(3)]
            geometry['object_omissions'] = objects['omitted']
            geometry['object_source'] = objects.get('source', 'Authored static poses; not live visibility or collision.')
            geometry['edge_on_faces'] = fence_faces(geometry, code)
            proxies = terrain_fence_proxies(geometry, code)
            if proxies:
                geometry['fence_proxies'] = proxies
                for proxy in proxies: geometry['edge_on_faces'].pop(str(proxy['face']), None)
            geometry['object_mesh']['edge_on_faces'] = fence_faces(geometry['object_mesh'], code, geometry['objects'])
            geometry['scene_version'] = 3
            used = geometry['face_textures'] + geometry['object_mesh']['face_textures']
            geometry['texture_atlas'] = texture_atlas(images, [t for t in used if t is not None])
            geometry['texture_source_sha256'] = hashlib.sha256(vlo).hexdigest()
            info = {'table_index': index, 'code': code, 'name': name, 'overlay_id': overlay,
                    'wad_resource': rid, 'map_resource': map_rid, 'file': f'{code}.json',
                    'vertex_count': len(geometry['vertices']), 'face_count': len(geometry['faces']),
                    'item_count': len(geometry['items']), 'exit_count': len(geometry['exits']),
                    'object_count': len(geometry['objects']), 'object_omitted_count': len(geometry['object_omissions']),
                    'bounds': geometry['bounds']}
            geometry.update(info)
            (destination / info['file']).write_text(json.dumps(geometry, separators=(',', ':')))
            manifest['maps'].append(info)
            print(f'{code}: {len(geometry["vertices"])} terrain vertices, {len(geometry["faces"])} terrain polygons, {len(geometry["objects"])} static props, {len(geometry["object_mesh"]["faces"])} prop polygons')
    (destination / 'manifest.json').write_text(json.dumps(manifest, indent=2))
    return manifest

if __name__ == '__main__':
    root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exe', type=Path, default=root / 'EXE/MEDIEVIL.EXE')
    parser.add_argument('--archive', type=Path, default=root / 'EXE/MEDRES.MWD')
    parser.add_argument('--output', type=Path, default=root / 'minimap/data/maps')
    args = parser.parse_args()
    extract(args.exe, args.archive, args.output)
