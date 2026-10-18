"""Two-screen-pixel width for identified, otherwise zero-width fences/gates."""
import json,math
from pathlib import Path
CATALOG=json.loads(Path(__file__).with_name('fence_materials.json').read_text())


def offsets(points):
    """Return unit screen-normal offsets, or None for any visible-width face."""
    a,b=max(((a,b) for a in points for b in points),key=lambda pair:(pair[0][0]-pair[1][0])**2+(pair[0][2]-pair[1][2])**2)
    if (a[0],a[2])>(b[0],b[2]):a,b=b,a
    dx,dz=b[0]-a[0],b[2]-a[2];length=math.hypot(dx,dz)
    if length<1e-6:return None
    if max(abs(dx*(p[2]-a[2])-dz*(p[0]-a[0]))/length for p in points)>1e-4:return None
    lo,hi=min(p[1] for p in points),max(p[1] for p in points)
    if hi-lo<1e-6:return None
    result=[]
    for p in points:
        # Paired top/bottom vertices get exactly +/-1 even on sloping ground.
        column=[q[1] for q in points if math.hypot(q[0]-p[0],q[2]-p[2])<1e-4]
        low,high=min(column),max(column)
        if high-low<1e-6:low,high=lo,hi
        side=2*(p[1]-low)/(high-low)-1
        result.append([round(-dz/length*side,9),round(dx/length*side,9)])
    return result


def terrain_fence_proxies(mesh, code):
    """Minimum-width readout for identified fence materials in every level.

    Tiny projected widths from integer vertex rounding count too. The browser
    uses this opaque native-colour strip only below two screen pixels; wider
    faces keep their normal texture. World mesh vertices are never rewritten.
    """
    materials=set(CATALOG['terrain_materials'].get(code,[]))
    result=[]
    for i,face in enumerate(mesh['faces']):
        if mesh['face_textures'][i] not in materials:continue
        points=[mesh['vertices'][j] for j in face]
        if max(p[1] for p in points)-min(p[1] for p in points)<1e-6:continue
        a,b=max(zip(points,points[1:]+points[:1]),key=lambda q:(q[0][0]-q[1][0])**2+(q[0][2]-q[1][2])**2)
        dx,dz=b[0]-a[0],b[2]-a[2];length=math.hypot(dx,dz)
        if length<1e-6:continue
        ux,uz=dx/length,dz/length;nx,nz=-uz,ux
        along=[(p[0]-a[0])*ux+(p[2]-a[2])*uz for p in points]
        across=[(p[0]-a[0])*nx+(p[2]-a[2])*nz for p in points]
        middle=(min(across)+max(across))/2;y=sum(p[1] for p in points)/len(points)
        ends=[[round(a[0]+ux*t+nx*middle,6),round(y,6),round(a[2]+uz*t+nz*middle,6)] for t in (min(along),max(along))]
        result.append({'face':i,'width':round(max(across)-min(across),9),'ends':ends})
    return result


def fence_faces(mesh, code, instances=()):
    materials=set(CATALOG['terrain_materials'].get(code,[]));eligible=set()
    for instance in instances:
        if str(instance['model']) in CATALOG['gate_models']:
            eligible.update(range(instance['first_face'],instance['first_face']+instance['face_count']))
    result={}
    for i,face in enumerate(mesh['faces']):
        if i not in eligible and mesh['face_textures'][i] not in materials:continue
        value=offsets([mesh['vertices'][v] for v in face])
        if value is not None:result[str(i)]=value
    return result
