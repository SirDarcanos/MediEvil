"""Bounded, read-only ISO9660 import from a runner's own USA disc image.

Reads 2048-byte ISO, MODE1/2352 or MODE2/2352 data tracks. Never edits the
image; only the required EXE/archive/overlays are staged, then removed.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import tempfile
from extract_maps import EXE_SHA1, extract

MAX_IMAGE = 1024 * 1024 * 1024
MAX_FILE = 128 * 1024 * 1024
MAX_DIRECTORY = 2 * 1024 * 1024
CACHE_SCHEMA = 1


def image_path(path: Path) -> Path:
    path = Path(path)
    if path.suffix.lower() != '.cue':
        return path
    if path.stat().st_size > 65536:
        raise ValueError('CUE file is too large.')
    current = None
    for line in path.read_text(encoding='utf-8-sig').splitlines():
        match = re.fullmatch(r'\s*FILE\s+"([^"]+)"\s+BINARY\s*', line, re.I)
        if match:
            current = match[1].replace('\\', '/')
        if re.fullmatch(r'\s*TRACK\s+\d+\s+MODE[12]/(?:2048|2352)\s*', line, re.I):
            if not current:
                raise ValueError('CUE data track has no BINARY file.')
            relative = Path(current)
            if relative.is_absolute() or '..' in relative.parts or ':' in current:
                raise ValueError('Select the data-track BIN directly; CUE paths must stay inside its folder.')
            target = (path.parent / relative).resolve()
            if not target.is_relative_to(path.parent.resolve()):
                raise ValueError('CUE track escapes its folder.')
            return target
    raise ValueError('No supported data track found in CUE. Select Track 1 BIN or ISO; CHD is not supported in v1.')


class Disc:
    def __init__(self, path):
        self.path = image_path(Path(path))
        size = self.path.stat().st_size
        if not 16 * 2048 < size <= MAX_IMAGE:
            raise ValueError('Select a data-track BIN or ISO up to 1 GiB, not an audio track or CUE upload.')
        self.file = self.path.open('rb')
        self.size = size
        try:
            for stride, offset in ((2048, 0), (2352, 24), (2352, 16)):
                self.stride, self.offset = stride, offset
                self.file.seek(16 * stride + offset)
                pvd = self.file.read(2048)
                if len(pvd) == 2048 and pvd[:7] == b'\x01CD001\x01':
                    if struct.unpack_from('<H', pvd, 128)[0] != 2048:
                        continue
                    self.root = self.record(pvd[156:190])
                    break
            else:
                raise ValueError('Not a supported ISO9660 data track. Select the USA game Track 1 BIN or ISO (not CHD/audio).')
        except BaseException:
            self.file.close()
            raise

    def close(self):
        self.file.close()

    @staticmethod
    def record(data):
        if len(data) < 34 or data[0] > len(data) or data[32] > data[0] - 33:
            raise ValueError('Malformed ISO directory record.')
        name = data[33:33 + data[32]]
        if name in (b'\0', b'\1'):
            name = ''
        else:
            name = name.decode('ascii').split(';', 1)[0].upper()
            if not re.fullmatch(r'[A-Z0-9_.-]{1,64}', name) or name in ('.', '..'):
                raise ValueError('Unsafe ISO filename.')
        if data[25] & 0x80:
            raise ValueError('Multi-extent ISO files are not supported.')
        return {'name': name, 'sector': int.from_bytes(data[2:6], 'little'),
                'size': int.from_bytes(data[10:14], 'little'), 'directory': bool(data[25] & 2)}

    def chunks(self, entry):
        size = entry['size']
        if size < 0 or size > MAX_FILE:
            raise ValueError('Disc file exceeds import limits.')
        for index in range((size + 2047) // 2048):
            position = (entry['sector'] + index) * self.stride + self.offset
            length = min(2048, size - index * 2048)
            if position + length > self.size:
                raise ValueError('Disc file points beyond the image.')
            self.file.seek(position)
            block = self.file.read(length)
            if len(block) != length:
                raise ValueError('Truncated disc image.')
            yield block

    def directory(self, entry):
        if not entry['directory'] or entry['size'] > MAX_DIRECTORY:
            raise ValueError('Invalid ISO directory.')
        data = b''.join(self.chunks(entry))
        result = {}
        offset = 0
        while offset < len(data):
            length = data[offset]
            if not length:
                offset = (offset // 2048 + 1) * 2048
                continue
            if length > 2048 - offset % 2048 or offset + length > len(data):
                raise ValueError('ISO record crosses its directory sector.')
            item = self.record(data[offset:offset + length])
            offset += length
            if item['name']:
                if item['name'] in result or len(result) >= 256:
                    raise ValueError('Duplicate or excessive ISO directory entries.')
                result[item['name']] = item
        return result

    def copy(self, entry, target):
        if entry['directory']:
            raise ValueError('Expected a regular disc file.')
        with Path(target).open('xb') as output:
            for block in self.chunks(entry):
                output.write(block)


def load_manifest(folder):
    folder = Path(folder)
    manifest = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
    if manifest.get('exe_sha1') != EXE_SHA1 or len(manifest.get('maps', [])) != 25:
        raise ValueError('Map cache is incomplete or from an unsupported game revision.')
    seen = set()
    for item in manifest['maps']:
        code, filename = item.get('code', ''), item.get('file', '')
        if (not re.fullmatch(r'[A-Z0-9]{1,8}', code) or code in seen
                or filename != code + '.json' or not (folder / filename).is_file()
                or not (folder / filename).resolve().is_relative_to(folder.resolve())):
            raise ValueError('Map cache contains an invalid or missing map.')
        seen.add(code)
    return manifest


def import_game(source, cache, progress=lambda message: None):
    """Publish a complete cache atomically; preserve any existing cache on failure."""
    cache = Path(cache)
    cache.mkdir(parents=True, exist_ok=True)
    destination = cache / 'maps'
    if destination.exists():
        load_manifest(destination)
        return destination
    disc = Disc(source)
    try:
        progress('Reading your disc…')
        root = disc.directory(disc.root)
        # The retail disc stores these at its root. Some rebuilt images use
        # an EXE subdirectory; neither case depends on our local checkout layout.
        entries = disc.directory(root['EXE']) if 'EXE' in root and root['EXE']['directory'] else root
        if not {'MEDIEVIL.EXE', 'MEDRES.MWD', 'OVERLAYS'} <= entries.keys():
            raise ValueError('Required MediEvil files are missing from this disc.')
        with tempfile.TemporaryDirectory(prefix='.import-', dir=cache) as scratch:
            work = Path(scratch)
            exe = work / 'MEDIEVIL.EXE'
            if entries['MEDIEVIL.EXE']['size'] > 2 * 1024 * 1024:
                raise ValueError('Unexpected game executable size.')
            disc.copy(entries['MEDIEVIL.EXE'], exe)
            if hashlib.sha1(exe.read_bytes()).hexdigest() != EXE_SHA1:
                raise ValueError('Unsupported game revision. V1 requires MediEvil USA SCUS-94227.')
            progress('Copying map resources for local extraction…')
            disc.copy(entries['MEDRES.MWD'], work / 'MEDRES.MWD')
            overlays = disc.directory(entries['OVERLAYS'])
            (work / 'OVERLAYS').mkdir()
            total = 0
            for name, entry in overlays.items():
                if entry['directory'] or entry['size'] > 4 * 1024 * 1024:
                    raise ValueError('Unexpected overlay resource.')
                total += entry['size']
                if total > 32 * 1024 * 1024:
                    raise ValueError('Overlay resources exceed import limits.')
                disc.copy(entry, work / 'OVERLAYS' / name)
            progress('Building all 25 textured maps. This can take a minute…')
            maps = work / 'maps'
            extract(exe, work / 'MEDRES.MWD', maps)
            load_manifest(maps)
            (maps / 'import-info.json').write_text(json.dumps({'schema': CACHE_SCHEMA,
                'game': 'MediEvil USA SCUS-94227', 'source': 'Locally extracted from your own disc',
                'exe_sha1': EXE_SHA1}, indent=2) + '\n', encoding='utf-8')
            if destination.exists():
                raise ValueError('Another import created a cache; restart the minimap.')
            os.rename(maps, destination)
    finally:
        disc.close()
    progress('Ready')
    return destination
