"""Reference predicates for captured USA boss rows, not a LiveSplit implementation.

These exercise observed class/phase/death guards. They do not establish atomic
polling, allocation lifetime, emulator integration or arbitrary-game coverage.
"""
EXE_SHA1 = '265ce5dc508002a339ae535e49a5b1b4e683b732'
ENCOUNTERS = {
    'kardok': (6, 0x80011F24, 0x8001CDD4, 0xB3C4, 11),
    'zarok': (8, 0x80018784, 0x8001D05C, 0xB45D, 25),
}


def boss_death_candidate(row, encounter, *, exe_sha1):
    phase, constructor, definition, entity, action = ENCOUNTERS[encounter]
    if exe_sha1 != EXE_SHA1:
        return False
    expected = {'mode': 3, 'level': 23, 'overlay': 25, 'phaseIndex': phase,
                'bossConstructor': constructor, 'bossDefinition': definition,
                'bossEntity': entity, 'bossAction': action}
    if any(type(row.get(k)) is not int or row[k] != value for k, value in expected.items()):
        return False
    pointer, hp = row.get('bossPointer'), row.get('bossHP')
    return (type(pointer) is int and 0x80001000 <= pointer < 0x801FFF00 and pointer % 4 == 0
            and type(hp) is int and -32768 <= hp <= 0)
