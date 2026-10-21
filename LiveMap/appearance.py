"""Disc-derived terrain colours and conservative static item-spawn labels.

FrogLord VLO/CLUT, MediEvil vertex and PTME formats; see THIRD_PARTY.md.
These markers do not represent runtime availability or scripted/dropped items.
"""
import struct
from binary import region
from vlo import psx_colour, read_vlo


def vertex_colour(packed):
    # MediEvil packs B bits around R/G; this is NOT ordinary BGR555.
    return [packed & 0xF8, (packed >> 8) & 0xF8,
            ((packed & 0x700) >> 3) | ((packed & 3) << 3)]


def vlo_colours(data):
    """Pixel-weighted opaque texture means, indexed by global texture ID.

    Uses actual 4/8-bit palette indices or direct 16-bit texels. Fully transparent
    zero pixels are excluded; 0x8000 is opaque black. No full texture rendering.
    """
    result = {}
    for image in read_vlo(data):
        pixels = image.pixel_counts()
        pixels.pop(0, None)
        total = sum(pixels.values())
        result[image.texture_id] = (
            [round(sum(psx_colour(p)[c] * n for p, n in pixels.items()) / total) for c in range(3)]
            if total else [0, 0, 0])
    return result


# Confirmed common form/subtype model assignments from this revision's entity
# table at EXE 0xb6224. Model IDs resolve using the ORDER of FrogLord's 790-file
# list; its inline resource-number comments contain errors and are not used.
WEAPONS = {
    0:'Small sword', 1:'Broad sword', 2:'Magic sword', 3:'Throwing daggers',
    4:'Axe', 5:'Club', 6:'Crossbow', 7:'Chicken drumstick', 8:'Arm',
    9:'Lightning', 10:'Longbow', 11:'Spear', 12:'Hammer',
    13:'Bow (variant 13)', 14:'Bow (variant 14)', 15:'Lightning (variant 15)',
    16:'Dragon potion', 20:'Copper shield', 21:'Silver shield', 22:'Gold shield',
}
PICKUPS = {
    0:('health','Energy vial'), 1:('health','Life bottle'), 2:('quest','Crown'),
    3:('chalice','Chalice'), 4:('chalice','Chalice'), 5:('chalice','Chalice'),
    6:('quest','Helmet'), 7:('gold','Coin bag'), 8:('health','Energy vial'),
    9:('gold','Money chest'), 10:('quest','Sheet music'), 11:('quest','Skull key'),
    12:('gold','Gold piece'), 13:('quest','Skull key'), 14:('quest','Harvester part'),
    15:('quest','Amber'), 16:('quest','Shadow artefact'), 17:('quest','Shadow talisman'),
    18:('quest','Witch talisman'), 19:('quest','Crucifix'), 20:('quest','Crucifix cast'),
    21:('quest','Safe key'), 22:('quest','Bust'), 23:('quest','Dragon gem'),
}
RUNES = ('Chaos rune', 'Earth rune', 'Moon rune', 'Star rune', 'Time rune')


def item_label(form, subtype):
    if form == 49:
        return PICKUPS.get(subtype)
    if form == 17 and subtype < len(RUNES):
        return 'rune', RUNES[subtype]
    if form == 5 and subtype in WEAPONS:
        return 'equipment', WEAPONS[subtype]
    if form == 6 and subtype < 4:
        return 'equipment', ('Copper shield', 'Copper shield', 'Silver shield', 'Gold shield')[subtype]
    if form == 4 and subtype < 4:
        return 'chest', 'Chest (contents not inferred)'
    return None


def item_spawns(data, chunk, chunk_end):
    region(data, chunk, 16)
    count, _, pointer = struct.unpack_from('<HHI', data, chunk + 8)
    if pointer < chunk + 16 or pointer + count * 64 > chunk_end:
        raise ValueError('Entity records outside PTME chunk')
    region(data, pointer, count * 64)
    items = []
    for index in range(count):
        at = pointer + index * 64
        entity_id, form, subtype, generic = struct.unpack_from('<IHBB', data, at)
        label = item_label(form, subtype)
        if label is None:
            continue
        category, name = label
        items.append({'id':entity_id, 'record':index, 'form':form, 'subtype':subtype,
                      'category':category, 'name':name,
                      'position':list(struct.unpack_from('<3h', data, at + 20)),
                      'init_flags':struct.unpack_from('<I', data, at + 40)[0],
                      'destroy_flags':struct.unpack_from('<I', data, at + 44)[0]})
    return items
