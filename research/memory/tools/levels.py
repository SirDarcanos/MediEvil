#!/usr/bin/env python3
"""Resolve game-level indices, overlay descriptor indices and loaded header IDs.

These are three different namespaces. The per-level record's +0x4C value is an
index into overlay descriptors, not the ID found at PS1 address 0x80010000.
This extracts static metadata; it does not test every level transition.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct

EXE_SHA1 = '265ce5dc508002a339ae535e49a5b1b4e683b732'


def extract(exe_path):
    exe = exe_path.read_bytes()
    if hashlib.sha1(exe).hexdigest() != EXE_SHA1:
        raise ValueError('Expected identified USA executable')
    load, size = struct.unpack_from('<II', exe, 0x18)

    def offset(address, width):
        value = address-load+0x800
        if value < 0x800 or value+width > min(len(exe), size+0x800):
            raise ValueError('Pointer outside executable')
        return value

    def word(address):
        return struct.unpack_from('<I', exe, offset(address, 4))[0]

    result = []
    for index in range(25):
        record = 0x800da674+index*100
        descriptor_index = word(record+0x4c)
        descriptor = 0x800cd9e8+descriptor_index*32
        start = offset(word(descriptor), 1)
        end = exe.find(b'\0', start, start+256)
        if end < 0:
            raise ValueError('Unterminated overlay path')
        name = exe[start:end].decode('ascii').replace('\\', '/').split('/')[-1].split(';')[0]
        if not re.fullmatch(r'[A-Z0-9_]+\.BIN', name):
            raise ValueError('Invalid overlay filename')
        data = (exe_path.parent/'OVERLAYS'/name).read_bytes()
        label_pointer = word(0x800da4e4+index*4)
        label_start = offset(label_pointer, 1)
        label_end = exe.find(b'\0', label_start, label_start+256)
        if label_end < 0:
            raise ValueError('Unterminated level label')
        label = exe[label_start:label_end].decode('ascii')
        result.append({'level_index': index, 'name': label,
                       'label_pointer': f'0x{label_pointer:08X}', 'level_record': f'0x{record:08X}',
                       'wad_resource': word(record), 'overlay_descriptor_index': descriptor_index,
                       'overlay_descriptor': f'0x{descriptor:08X}', 'overlay_file': name,
                       'overlay_sha1': hashlib.sha1(data).hexdigest(),
                       'overlay_load_address': f'0x{word(word(descriptor+4)):08X}',
                       'loaded_header_id': struct.unpack_from('<I', data)[0]})
    return {'exe_sha1': EXE_SHA1, 'scope': 'Static metadata, not all-level runtime verification',
            'level_index_address': '0x800EEE2C', 'loaded_header_id_address': '0x80010000',
            'levels': result}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('exe', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(json.dumps(extract(args.exe), indent=2)+'\n')
