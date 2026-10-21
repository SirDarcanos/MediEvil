"""Bounds checks shared by the read-only disc resource decoders."""


def region(data, offset, size):
    if offset < 0 or size < 0 or offset > len(data) - size:
        raise ValueError('Appearance data extends beyond resource')
    return memoryview(data)[offset:offset + size]
