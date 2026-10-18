import struct
import unittest
from triggers import exit_triggers, is_exit, inverse_rotation, clip_rect, area


def fixture(flags=0xC268, centre=(100,50,100), matrix=(4096,0,0,0,4096,0,0,0,4096)):
    data=bytearray(622)
    struct.pack_into('<4sIHHI',data,0,b'PLOC',60,1,0xFFFF,16)
    struct.pack_into('<9hH3i4HI',data,16,*matrix,0,*centre,flags,10,20,30,1400)
    struct.pack_into('<4sIBBHB3x2I',data,60,b'DIRG',562,16,16,4096,12,84,596)
    for i in range(256): struct.pack_into('<h',data,84+i*2,-1)
    struct.pack_into('<h',data,84+136*2,0)
    struct.pack_into('<I',data,596,620);data[608]=1
    struct.pack_into('<H',data,620,0)
    return data


class ExitTriggerTests(unittest.TestCase):
    def test_only_game_completion_event_ranges(self):
        for event in (100,101,104,124,201,224): self.assertTrue(is_exit(0xC200|event))
        for event in (0,7,93,94,96,97,98,99,125,200,225,255): self.assertFalse(is_exit(0xC200|event))
        for flags in (0x4268,0xC068,0x8268,0x0268): self.assertFalse(is_exit(flags))

    def test_box_record_and_height_are_not_a_door_marker(self):
        zones=exit_triggers(fixture(),(0,60),(60,622));self.assertEqual(len(zones),1)
        z=zones[0]
        self.assertEqual(z['event'],104);self.assertEqual(z['centre'],[100,50,100])
        self.assertEqual(z['half_size'],[10,20,30]);self.assertEqual(z['height_range'],[30,70])
        self.assertEqual(z['footprints'],[[[90,70],[110,70],[110,130],[90,130]]])
        self.assertNotIn('active',z)
        self.assertEqual(exit_triggers(fixture(flags=0xC207),(0,60),(60,622)),[])

    def test_scripted_events_require_explicit_proof_and_event_zone_flags(self):
        proof={13:{'kind':'scripted','callback':'test-only'}}
        self.assertFalse(is_exit(0xC20D))
        self.assertEqual(exit_triggers(fixture(flags=0xC20D),(0,60),(60,622)),[])
        zone=exit_triggers(fixture(flags=0xC20D),(0,60),(60,622),proof)[0]
        self.assertEqual(zone['event'],13);self.assertEqual(zone['script_source'],proof[13])
        self.assertEqual(zone['footprints'],[[[90,70],[110,70],[110,130],[90,130]]])
        self.assertNotIn('active',zone)
        for flags in (0x420D,0xC00D,0xC20C,0xC20E):
            self.assertEqual(exit_triggers(fixture(flags=flags),(0,60),(60,622),proof),[])

    def test_world_corners_invert_world_to_local_matrix(self):
        m=(3546,0,2048,0,4096,0,-2048,0,3546)
        z=exit_triggers(fixture(matrix=m),(0,60),(60,622))[0]
        for x,zpos in z['footprints'][0]:
            dx,dz=x-100,zpos-100
            self.assertAlmostEqual(abs((m[0]*dx+m[2]*dz)/4096),10,delta=.002)
            self.assertAlmostEqual(abs((m[6]*dx+m[8]*dz)/4096),30,delta=.002)
        self.assertTrue(any(abs(x-93.66)<.01 and abs(y-130.98)<.01 for x,y in z['footprints'][0]))

    def test_tilt_uses_all_eight_corners_for_projection(self):
        m=(0,4096,0,-4096,0,0,0,0,4096)
        z=exit_triggers(fixture(matrix=m),(0,60),(60,622))[0]
        self.assertEqual(z['height_range'],[40,60])
        self.assertEqual(sorted(set(p[0] for p in z['footprints'][0])),[80,120])

    def test_grid_clips_unreachable_parts_and_omits_unreferenced_boxes(self):
        z=exit_triggers(fixture(centre=(0,50,100)),(0,60),(60,622))[0]
        self.assertEqual(sorted(set(p[0] for p in z['footprints'][0])),[0,10])
        data=fixture();data[608]=0
        self.assertEqual(exit_triggers(data,(0,60),(60,622)),[])

    def test_malformed_packets_fail_closed(self):
        with self.assertRaises(ValueError): exit_triggers(fixture(),(0,59),(60,622))
        with self.assertRaises(ValueError): exit_triggers(fixture(),(0,60),None)
        data=fixture();struct.pack_into('<H',data,620,1)
        with self.assertRaises(ValueError): exit_triggers(data,(0,60),(60,622))
        data=fixture();struct.pack_into('<I',data,596,900)
        with self.assertRaises(ValueError): exit_triggers(data,(0,60),(60,622))
        data=fixture();data[72]=8
        with self.assertRaises(ValueError): exit_triggers(data,(0,60),(60,622))
        data=fixture();struct.pack_into('<I',data,56,0)
        with self.assertRaises(ValueError): exit_triggers(data,(0,60),(60,622))
        with self.assertRaises(ValueError): inverse_rotation([0]*9)

    def test_missing_collision_packet_is_explicitly_empty(self):
        self.assertEqual(exit_triggers(b'',None,None),[])

    def test_clipping_preserves_area_and_handles_disjoint_cell(self):
        poly=[[-2,-2],[2,-2],[2,2],[-2,2]]
        self.assertEqual(area(clip_rect(poly,[0,4,0,4])),4)
        self.assertEqual(clip_rect(poly,[5,8,5,8]),[])


if __name__ == '__main__': unittest.main()
