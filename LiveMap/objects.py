"""Authored static MOF props, not runtime entities or collision geometry.

FrogLord MR MOF/PTME/overlay format references: THIRD_PARTY.md. Only complete,
single-cel static models with supported primitives and level-local textures are
accepted. Unsupported/animated entities are reported rather than guessed.
"""
import math
from pathlib import Path
import struct
from appearance import region, item_label

EXE_BASE = 0x800214a4
# vertex count, environment-normal count, normal count, textured
TYPES = [(3,0,1,False),(4,0,1,False),(3,0,1,True),(4,0,1,True),
         (3,0,3,False),(4,0,4,False),(3,0,3,True),(4,0,4,True),
         (3,3,1,False),(4,4,1,False),(2,0,0,False),(3,0,0,False),
         (3,0,0,False),(4,0,0,False),(3,3,3,False),(4,4,4,False)]


def string_at(data, at):
    region(data, at, 1)
    end = data.find(b'\0', at, min(len(data), at+256))
    if end < 0: raise ValueError('Unterminated model/overlay name')
    return data[at:end].decode('ascii', errors='replace')


class Definitions:
    def __init__(self, exe, folder):
        self.exe, self.folder, self.cache = exe, Path(folder), {}

    def overlay(self, level):
        if level not in self.cache:
            index = struct.unpack_from('<I', self.exe, 0xb91d0+level*100+76)[0]
            region(self.exe, 0xac544+index*32, 32)
            path, pointer = struct.unpack_from('<II', self.exe, 0xac544+index*32)
            name = string_at(self.exe, path-EXE_BASE).replace('\\','/').split('/')[-1].split(';')[0]
            if not name or any(c not in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.-' for c in name) or not name.endswith('.BIN'):
                raise ValueError('Invalid overlay filename')
            region(self.exe, pointer-EXE_BASE, 4)
            base = struct.unpack_from('<I', self.exe, pointer-EXE_BASE)[0]
            self.cache[level] = ((self.folder/'OVERLAYS'/name).read_bytes(), base)
        return self.cache[level]

    def resolve(self, form, subtype, level):
        if not 0 <= form < 300: raise ValueError('Unknown entity form')
        pointer, levels = struct.unpack_from('<II', self.exe, 0xb6224+form*8)
        if not pointer: raise ValueError('Entity has no definition')
        if levels == 0xffffffff:
            data, base = self.exe, EXE_BASE
        else:
            if not levels & (1 << level): raise ValueError('Definition not enabled for this level')
            data, base = self.overlay(level)
        at = pointer-base;region(data, at, 180)
        name = string_at(data, struct.unpack_from('<I',data,at)[0]-base)
        count = struct.unpack_from('<H',data,at+4)[0]
        model = struct.unpack_from('<I',data,at+176)[0]
        if 0x80000000 <= model < 0x80200000:
            if subtype == 255 or subtype >= max(1,count): raise ValueError('Model subtype outside definition')
            offset = model-base+subtype*8;region(data,offset,8)
            model, model_set, model_index, padding = struct.unpack_from('<4H',data,offset)
            if model_set or model_index: raise ValueError('Animated model selection unsupported')
        if not 0 < model < 790: raise ValueError('No static model resource')
        return model, name


def static_model(data, images):
    region(data,0,16)
    if data[:4] != b'\x02FOM': raise ValueError('Not a complete static MOF')
    size, flags, parts = struct.unpack_from('<3I',data,4)
    if size != len(data) or not 0 < parts <= 256: raise ValueError('Invalid MOF header')
    if flags & 0x30: raise ValueError('Animated textures/flipbooks unsupported')
    region(data,16,parts*44+4)
    vertices, faces, uvs, tids, colours = [], [], [], [], []
    total_primitives = 0
    for part in range(parts):
        at=16+part*44
        _, cels, nv, nn, np, nh = struct.unpack_from('<6H',data,at)
        cp, pp = struct.unpack_from('<2I',data,at+12)
        total_primitives += np
        if cels!=1 or not nv or not np or total_primitives>50000: raise ValueError('Only bounded single-cel static parts supported')
        region(data,cp,16);vp,norm,bbox,_=struct.unpack_from('<4I',data,cp)
        region(data,vp,nv*8);region(data,norm,nn*8)
        points=[list(struct.unpack_from('<3h',data,vp+i*8)) for i in range(nv)]
        seen=0
        while seen<np:
            region(data,pp,4);kind,count=struct.unpack_from('<2H',data,pp);pp+=4
            if kind>=len(TYPES) or not count or count>np-seen: raise ValueError('Invalid MOF primitive block')
            vc,env,nc,textured=TYPES[kind]
            if vc<3: raise ValueError('Line primitives unsupported')
            # MOF wire indices/UVs already describe a cyclic perimeter. FrogLord
            # swaps the last pair for its strip-based mesh API; our renderer
            # takes cyclic quads, so unlike GXSP no swap belongs here.
            order=list(range(vc))
            for _ in range(count):
                region(data,pp,2*(vc+env+nc))
                indices=struct.unpack_from('<'+'H'*vc,data,pp);pp+=2*(vc+env+nc)
                if any(i>=nv for i in indices): raise ValueError('MOF vertex index outside part')
                uv=[[0,0] for _ in range(vc)];tid=None
                if textured:
                    region(data,pp,14 if vc==4 else 12)
                    if kind==3:  # FT4 uniquely stores image ID before its UVs.
                        tid=struct.unpack_from('<H',data,pp)[0];pp+=2
                        uv[0]=list(data[pp:pp+2]);uv[1]=list(data[pp+4:pp+6])
                        if struct.unpack_from('<H',data,pp+2)[0] or struct.unpack_from('<H',data,pp+6)[0]: raise ValueError('Pre-relocated MOF texture')
                        uv[2]=list(data[pp+8:pp+10]);uv[3]=list(data[pp+10:pp+12]);pp+=12
                    else:
                        uv[0]=list(data[pp:pp+2]);uv[1]=list(data[pp+4:pp+6])
                        if struct.unpack_from('<H',data,pp+2)[0] or struct.unpack_from('<H',data,pp+6)[0]: raise ValueError('Pre-relocated MOF texture')
                        uv[2]=list(data[pp+8:pp+10]);pp+=10
                        if vc==4: uv[3]=list(data[pp:pp+2]);pp+=2
                        tid=struct.unpack_from('<H',data,pp)[0];pp+=2
                    if tid not in images: raise ValueError('Model texture absent from level VLO')
                pp=(pp+3)&~3;region(data,pp,4);rgb=list(data[pp:pp+3]);pp+=4
                start=len(vertices)
                vertices.extend(points[indices[j]] for j in order)
                colours.extend([rgb.copy() for _ in order])
                faces.append(list(range(start,start+vc)));uvs.append([uv[j] for j in order]);tids.append(tid)
            seen+=count
    return {'vertices':vertices,'faces':faces,'face_uvs':uvs,'face_textures':tids,'vertex_colours':colours}


def transform(point, position, rotation):
    x,y,z=point
    for axis,angle in enumerate(rotation):
        c,s=math.cos(angle*math.tau/256),math.sin(angle*math.tau/256)
        if axis==0: y,z=c*y-s*z,s*y+c*z
        elif axis==1: x,z=c*x+s*z,-s*x+c*z
        else: x,y=c*x-s*y,s*x+c*y
    return [round(v+p,6) for v,p in zip((x,y,z),position)]


def placed_objects(data, definitions, level, resources, images):
    chunk=0
    while chunk<len(data):
        region(data,chunk,8);tag,size=struct.unpack_from('<4sI',data,chunk)
        if size<8: raise ValueError('Invalid map chunk')
        region(data,chunk,size)
        if tag==b'PTME': break
        chunk+=size
    if chunk==len(data): return {'models':{},'instances':[],'omitted':[]}
    region(data,chunk,16);count,_,pointer=struct.unpack_from('<HHI',data,chunk+8)
    if pointer<chunk+16 or pointer+count*64>chunk+size: raise ValueError('Invalid PTME entity array')
    models,instances,omitted={},[],[]
    failures={}
    for i in range(count):
        at=pointer+i*64;entity,form,subtype,_=struct.unpack_from('<IHBB',data,at)
        if item_label(form,subtype): continue  # Existing item markers retain their separate meaning.
        try:
            rid,name=definitions.resolve(form,subtype,level)
            if rid not in models:
                if rid in failures: raise ValueError(failures[rid])
                try:
                    if rid not in resources: raise ValueError('Model absent from level WAD')
                    models[rid]=static_model(resources[rid],images)
                except ValueError as error:
                    failures[rid]=str(error);raise
            position=list(struct.unpack_from('<3h',data,at+20));rotation=list(data[at+16:at+19])
            points=[transform(v,position,rotation) for v in models[rid]['vertices']]
            instances.append({'record':i,'id':entity,'form':form,'subtype':subtype,'model':rid,'name':name,
                              'position':position,'rotation':rotation,
                              'bounds':[[min(p[j] for p in points),max(p[j] for p in points)] for j in range(3)],
                              'init_flags':struct.unpack_from('<I',data,at+40)[0],
                              'destroy_flags':struct.unpack_from('<I',data,at+44)[0]})
        except ValueError as error:
            omitted.append({'record':i,'form':form,'subtype':subtype,'reason':str(error)})
    return {'models':models,'instances':instances,'omitted':omitted,
            'source':'Authored static models/poses only; visibility, movement, gates and collision are not live.'}


def flatten_objects(result, texture_means):
    """Bake only model transforms, never change the terrain mesh or its bounds."""
    mesh={key:[] for key in ('vertices','faces','vertex_colours','face_uvs','face_textures','face_colours')}
    for instance in result['instances']:
        model=result['models'][instance['model']]
        start=len(mesh['vertices']);instance['first_face']=len(mesh['faces']);instance['face_count']=len(model['faces'])
        mesh['vertices'].extend(transform(v,instance['position'],instance['rotation']) for v in model['vertices'])
        mesh['vertex_colours'].extend(model['vertex_colours'])
        mesh['faces'].extend([[start+i for i in face] for face in model['faces']])
        mesh['face_uvs'].extend(model['face_uvs']);mesh['face_textures'].extend(model['face_textures'])
        for face,tid in zip(model['faces'],model['face_textures']):
            rgb=[sum(model['vertex_colours'][i][c] for i in face)/len(face) for c in range(3)]
            if tid is not None:rgb=[min(255,rgb[c]*texture_means[tid][c]/128) for c in range(3)]
            mesh['face_colours'].append([round(c) for c in rgb])
    return mesh
