"""Typed PS1-address reads for validating ASL pointer paths against captured RAM.

This is an offline verifier, not a LiveSplit runtime/integration test.
"""
import struct

RAM_SIZE = 0x200000
TYPES = {'byte': 'B', 'short': 'h', 'ushort': 'H', 'int': 'i', 'uint': 'I'}


def read(data, kind, address, *offsets):
    if len(data) != RAM_SIZE:
        raise ValueError('Expected exactly 2 MiB of main RAM')
    if kind not in TYPES:
        raise ValueError('Unknown scalar type')

    def physical(value, width):
        # The bundled PS1 helper accepts this KSEG0 main-RAM range.
        offset = value - 0x80000000
        if offset < 0 or offset > RAM_SIZE-width or offset % width:
            raise ValueError('Invalid or unaligned main-RAM address')
        return offset

    for offset in offsets:
        if not isinstance(offset, int) or offset < 0:
            raise ValueError('Expected a nonnegative byte offset')
        address = struct.unpack_from('<I', data, physical(address, 4))[0] + offset
    width = struct.calcsize(TYPES[kind])
    return struct.unpack_from('<'+TYPES[kind], data, physical(address, width))[0]


def gameplay(data):
    # Instruction checks establish this tested executable layout before data reads.
    for address, expected in ((0x8006993c, 0x27bdffe8), (0x80069940, 0x240406f0),
                              (0x80069958, 0xaf840568)):
        if read(data, 'uint', address) != expected:
            raise ValueError('Game signature mismatch')
    if read(data, 'int', 0x800eee64) != 3:
        raise ValueError('Not in gameplay/loading mode')
    state = read(data, 'uint', 0x800edb3c)
    actor = read(data, 'uint', 0x800edb3c, 0x530)
    # Validate actor even when health is all the caller wants: state exists in loading.
    position = [read(data, 'int', 0x800edb3c, 0x530, off) for off in (0x24, 0x28, 0x2c)]
    frame = read(data, 'uint', 0x800eee60)
    flags = read(data, 'uint', 0x800eee24)
    if frame == 0 or flags & 0x80:
        raise ValueError('Loading or transitioning')
    return {'state': state, 'actor': actor, 'position': position,
            'health': read(data, 'int', 0x800edb3c, 0),
            'level': read(data, 'int', 0x800eee2c),
            'overlay': read(data, 'uint', 0x80010000),
            'gameFrame': frame, 'submode': read(data, 'int', 0x800eee70)}
