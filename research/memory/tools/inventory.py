#!/usr/bin/env python3
"""Extract the inventory descriptor table from the identified USA executable.

Descriptor stride/count: initialization at 0x8005D92C.
Inventory stride/base: consumption at 0x8005E104.
Names are resolved through the executable's localization pointer table, not the README.
This proves the table mapping, not every item's acquisition/use in gameplay.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct

EXE_SHA1 = '265ce5dc508002a339ae535e49a5b1b4e683b732'


def extract(exe):
    if hashlib.sha1(exe).hexdigest() != EXE_SHA1:
        raise ValueError('Expected the identified USA MEDIEVIL.EXE')
    load, size = struct.unpack_from('<II', exe, 0x18)

    def offset(address, width):
        result = address-load+0x800
        if result < 0x800 or result+width > min(len(exe), size+0x800):
            raise ValueError('Descriptor pointer outside the executable')
        return result

    def u32(address):
        return struct.unpack_from('<I', exe, offset(address, 4))[0]

    items = []
    for index in range(43):
        descriptor = 0x800d9f48+index*20
        label_id = u32(descriptor+4) >> 16
        label_pointer = u32(0x800d98bc+label_id*4)
        start = offset(label_pointer, 1)
        end = exe.find(b'\0', start, start+128)
        if end < 0:
            raise ValueError('Unterminated inventory name')
        name = exe[start:end].decode('ascii')
        initial_and_maximum = u32(descriptor+8)
        items.append({'index': index, 'name': name,
                      'game_state_offset': f'0x{0x80+index*4:X}', 'type': 'ushort',
                      'pointer_root': '0x800EDB3C',
                      'observed_resolved_address': f'0x{0x800f8174+0x80+index*4:08X}',
                      'descriptor': f'0x{descriptor:08X}', 'label_id': label_id,
                      'label_pointer': f'0x{label_pointer:08X}',
                      'initial_quantity': initial_and_maximum & 0xffff,
                      'descriptor_upper_halfword': initial_and_maximum >> 16,
                      'flags': f'0x{u32(descriptor):08X}'})
    return {'exe_sha1': EXE_SHA1, 'verification': 'Code/table backed; see runtime evidence for tested pickups',
            'items': items}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('exe', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(json.dumps(extract(args.exe.read_bytes()), indent=2)+'\n')
