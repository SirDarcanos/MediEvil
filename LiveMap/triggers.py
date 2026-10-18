"""Static exit-volume extraction, grounded in the retail USA collision/exit path.

8004d42c -> 8004e270 -> 800344a0 -> 800348ac. See research/exits/ and
RESEARCH.md. Authored volumes, not live activation or exact integer hit tests.
"""
from itertools import product
import math
import struct
from appearance import region


def is_exit(flags):
    event = flags & 255
    return flags & 0xC000 == 0xC000 and bool(flags & 0x200) and (100 <= event <= 124 or 201 <= event <= 224)


def checked(data, chunk, pointer, size):
    start, end = chunk
    if pointer < start or pointer + size > end:
        raise ValueError('Exit data outside its map packet')
    return region(data, pointer, size)


def inverse_rotation(values):
    a,b,c,d,e,f,g,h,i = [x / 4096 for x in values]
    determinant = a*(e*i-f*h)-b*(d*i-f*g)+c*(d*h-e*g)
    if not .95 < determinant < 1.05:
        raise ValueError('Unsupported exit rotation matrix')
    return [[v/determinant for v in row] for row in
            ((e*i-f*h,c*h-b*i,b*f-c*e),(f*g-d*i,a*i-c*g,c*d-a*f),(d*h-e*g,b*g-a*h,a*e-b*d))]


def hull(points):
    points = sorted(set(tuple(p) for p in points))
    def cross(a,b,c): return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
    def half(values):
        result=[]
        for p in values:
            while len(result)>1 and cross(result[-2],result[-1],p)<=0: result.pop()
            result.append(p)
        return result
    return half(points)[:-1]+half(reversed(points))[:-1]


def area(poly):
    return abs(sum(a[0]*b[1]-a[1]*b[0] for a,b in zip(poly,poly[1:]+poly[:1])))/2


def clip_rect(poly, rect):
    """Clip the footprint to one authored collision-grid cell."""
    for axis, edge, sign in ((0,rect[0],1),(0,rect[1],-1),(1,rect[2],1),(1,rect[3],-1)):
        output=[]
        for a,b in zip(poly,poly[1:]+poly[:1]):
            ain=(a[axis]-edge)*sign>=0;bin=(b[axis]-edge)*sign>=0
            if ain: output.append(a)
            if ain!=bin:
                t=(edge-a[axis])/(b[axis]-a[axis])
                output.append([a[k]+t*(b[k]-a[k]) for k in (0,1)])
        poly=output
    return poly


def grid_cells(data, chunk, count, wanted):
    start,end=chunk
    checked(data,chunk,start,24)
    nx,nz,size,shift=struct.unpack_from('<BBHB',data,start+8)
    if not 8 < shift < 16 or nx != 65536 >> shift or nz != nx or size != 1 << shift:
        raise ValueError('Unsupported collision grid dimensions')
    ids,records=struct.unpack_from('<2I',data,start+16)
    checked(data,chunk,ids,nx*nz*2)
    result={i:[] for i in wanted};expected=0
    for position in range(nx*nz):
        index=struct.unpack_from('<h',data,ids+position*2)[0]
        if index==-1: continue
        if index!=expected: raise ValueError('Invalid collision grid record index')
        expected+=1;at=records+index*24
        checked(data,chunk,at,24)
        pointer=struct.unpack_from('<I',data,at)[0];n=data[at+12]
        if n: checked(data,chunk,pointer,n*2)
        for j in range(n):
            record=struct.unpack_from('<H',data,pointer+j*2)[0]
            if record>=count: raise ValueError('Invalid collision grid zone reference')
            if record in result:
                x=(position%nx)*size-32768;z=(position//nx)*size-32768
                rect=[x,x+size,z,z+size]
                if rect not in result[record]: result[record].append(rect)
    return result


def exit_triggers(data, collision_chunk, grid_chunk, scripted_events=None):
    if collision_chunk is None: return []
    scripted_events=scripted_events or {}
    start,end=collision_chunk
    checked(data,collision_chunk,start,16)
    count,_,pointer=struct.unpack_from('<HHI',data,start+8)
    checked(data,collision_chunk,pointer,count*44)
    candidates=[]
    for index in range(count):
        at=pointer+index*44
        flags,x,y,z,radius=struct.unpack_from('<4HI',data,at+32)
        proof=scripted_events.get(flags&255) if flags&0xC200==0xC200 else None
        if not is_exit(flags) and proof is None: continue
        if not x or not y or not z: raise ValueError('Degenerate exit volume')
        matrix=list(struct.unpack_from('<9h',data,at));inverse=inverse_rotation(matrix)
        centre=list(struct.unpack_from('<3i',data,at+20));half=[x,y,z]
        # Stored rotation maps (world - centre) into local collision space.
        corners=[[centre[r]+sum(inverse[r][c]*half[c]*signs[c] for c in range(3)) for r in range(3)]
                 for signs in product((-1,1),repeat=3)]
        if max(sum((p[k]-centre[k])**2 for k in range(3)) for p in corners)>radius+400+1e-6:
            raise ValueError('Exit sphere check clips its box; needs explicit support')
        candidates.append({'record':index,'event':flags&255,'flags':flags,'centre':centre,
                           'matrix':matrix,'half_size':half,'radius_squared':radius,
                           'height_range':[math.floor(min(p[1] for p in corners)),math.ceil(max(p[1] for p in corners))],
                           'footprint':hull([[p[0],p[2]] for p in corners])})
        if proof is not None:candidates[-1]['script_source']=dict(proof)
    if not candidates: return []
    if grid_chunk is None: raise ValueError('Exit volumes lack a collision grid')
    cells=grid_cells(data,grid_chunk,count,[v['record'] for v in candidates])
    exits=[]
    for volume in candidates:
        poly=volume.pop('footprint')
        pieces=[clip_rect(poly,rect) for rect in cells[volume['record']]]
        pieces=[p for p in pieces if area(p)>1e-6]
        # Unreferenced authored boxes are not reachable by the game's grid lookup.
        if not pieces: continue
        if sum(area(p) for p in pieces)>=area(poly)*(1-1e-6): pieces=[poly]
        volume['footprints']=[[[round(v,3) for v in p] for p in piece] for piece in pieces]
        volume['grid_cells']=cells[volume['record']]
        exits.append(volume)
    return exits
