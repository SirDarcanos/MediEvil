import hashlib
import struct
import unittest
from unittest.mock import patch
from scripted_exits import ROUTES,script_records,scripted_exit_events,START_SEQUENCE

BASE=0x80010000

def fixture():
    b=bytearray(256);at=16
    for op,branch,flags,args in [(2,0,0,[0]),(9,1,0x6012,[0,13]),(102,1,1,[0,START_SEQUENCE,BASE+128]),(1,0,0,[0])]:
        size=8+4*len(args);struct.pack_into('<HBBI'+'I'*len(args),b,at,op,branch,size,flags,*args);at+=size
    struct.pack_into('<I',b,172,BASE+200)
    return b


def proof(data):return (13,BASE+128,BASE+200,hashlib.sha256(data).hexdigest())

class ScriptedExitTests(unittest.TestCase):
    def test_exact_positive_zone_branch_retains_provenance_not_active_state(self):
        b=fixture()
        with patch.dict(ROUTES,{'TEST':proof(b)}):result=scripted_exit_events('TEST',b,BASE,BASE+16)
        self.assertEqual(set(result),{13});self.assertEqual(result[13]['kind'],'scripted')
        self.assertEqual(result[13]['sequence'],hex(BASE+128));self.assertNotIn('active',result[13])
        self.assertIn('not sampled',result[13]['activation'])

    def test_other_levels_are_not_inferred_from_script_commands(self):
        self.assertEqual(scripted_exit_events('OTHER',fixture(),BASE,BASE+16),{})

    def test_changed_overlay_is_rejected_even_outside_script(self):
        b=fixture();rule=proof(b);b[255]=1
        with patch.dict(ROUTES,{'TEST':rule}),self.assertRaisesRegex(ValueError,'overlay differs'):
            scripted_exit_events('TEST',b,BASE,BASE+16)

    def test_false_or_nested_conditions_and_other_callbacks_rejected(self):
        for offset,fmt,value in [(32,'I',0x6022),(30,'B',2),(40,'I',14),(60,'I',BASE+192),(172,'I',BASE+204)]:
            b=fixture();struct.pack_into('<'+fmt,b,offset,value)
            with self.subTest(offset=offset),patch.dict(ROUTES,{'TEST':proof(b)}),self.assertRaises(ValueError):
                scripted_exit_events('TEST',b,BASE,BASE+16)

    def test_bad_record_bounds_and_sizes_fail_closed(self):
        for b in [fixture()[:40],bytearray(16)]:
            with self.assertRaises(ValueError):script_records(b,BASE,BASE+16)
        b=fixture();b[19]=7
        with self.assertRaises(ValueError):script_records(b,BASE,BASE+16)
        self.assertEqual(script_records(b,BASE,0),[])

if __name__=='__main__':unittest.main()
