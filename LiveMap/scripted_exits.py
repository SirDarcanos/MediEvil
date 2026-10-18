"""Narrow USA-script proofs for additional exits; not a generic script emulator.

Only listed routes are eligible. Runtime activation/visibility is not sampled.
Evidence and scalar completion traces are retained in research/exit-gaps/.
"""
import hashlib
import struct
from appearance import region

# Event, sequence data, per-frame callback; scalar addresses for this USA build.
ROUTES={
    'GS':(13,0x800157d0,0x80014dc8,'3faf15cdec05c25d8b44bbd433873f2d64ccd15defbf8423c373bd1c602b9136'),
    'AC':(12,0x8001b840,0x80018fc4,'a1e117d35737c41a5937ded33c5f627a9a77e22e7d20e9e8abd95a4af1c11c5a'),
}
START_SEQUENCE=0x80064174


def script_records(data, base, pointer):
    if not pointer:return []
    at=pointer-base;records=[]
    for _ in range(10000):
        region(data,at,8);op,branch,size,flags=struct.unpack_from('<HBBI',data,at)
        if size<8 or size%4:raise ValueError('Invalid event-script record size')
        region(data,at,size)
        args=list(struct.unpack_from('<'+'I'*((size-8)//4),data,at+8))
        records.append({'address':base+at,'op':op,'branch':branch,'flags':flags,'args':args})
        at+=size
        if op==1:return records
    raise ValueError('Event script has no bounded terminator')


def scripted_exit_events(code, data, base, pointer):
    if code not in ROUTES:return {}
    event,sequence,callback,expected_digest=ROUTES[code]
    digest=hashlib.sha256(data).hexdigest()
    if digest!=expected_digest:raise ValueError(f'{code}: overlay differs from the traced USA build')
    records=script_records(data,base,pointer);matches=[]
    for i in range(1,len(records)-2):
        previous,condition,command,following=records[i-1:i+3]
        if (previous['op']==2 and previous['branch']==0
            and condition['op']==9 and condition['branch']==1 and condition['flags']==0x6012 and condition['args']==[0,event]
            and command['op']==102 and command['branch']==1 and command['flags']==1 and command['args']==[0,START_SEQUENCE,sequence]
            and following['op'] in (1,2,3) and following['branch']==0):
            matches.append((condition,command))
    if len(matches)!=1:raise ValueError(f'{code}: scripted exit branch no longer matches its proof')
    region(data,sequence-base,52)
    actual=struct.unpack_from('<I',data,sequence-base+44)[0]
    if actual!=callback:raise ValueError(f'{code}: scripted exit callback changed')
    condition,command=matches[0]
    return {event:{'kind':'scripted','activation':'Script-controlled route; activation and visibility are not sampled.',
                   'script_condition':hex(condition['address']),'script_command':hex(command['address']),
                   'sequence':hex(sequence),'callback':hex(callback),'overlay_sha256':digest}}
