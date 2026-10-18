import struct
import unittest
from objects import static_model, transform, Definitions, placed_objects, EXE_BASE


def model_fixture(kind=3):
    # MOF wire quads are cyclic, unlike GXSP terrain's strip order.
    # One four-corner static part, one normal, one primitive block.
    textured=kind==3
    size=164 if textured else 152
    b=bytearray(size)
    struct.pack_into('<4sIII',b,0,b'\x02FOM',size,0,1)
    struct.pack_into('<6H8I',b,16,0,1,4,1,1,0,104,120,0,0,0,0,0,0)
    for i,v in enumerate(((-50,0,50),(50,0,50),(50,0,-50),(-50,0,-50))):struct.pack_into('<3h',b,64+i*8,*v)
    struct.pack_into('<3h',b,96,0,-4096,0)
    struct.pack_into('<4I',b,104,64,96,0,0)
    struct.pack_into('<2H',b,120,kind,1)
    struct.pack_into('<5H',b,124,0,1,2,3,0)
    if textured:
        struct.pack_into('<H2BH2BH4B',b,134,42,0,0,0,255,0,0,255,255,0,255)
        b[148:152]=bytes([128,128,128,0])
        # The MOF can contain unused tail data; size still covers the full resource.
    else:b[136:140]=bytes([40,80,120,0])
    return b


class ObjectTests(unittest.TestCase):
    def test_ft4_vertex_uv_pairing_and_global_texture(self):
        m=static_model(model_fixture(),{42:{}})
        self.assertEqual(m['vertices'],[[-50,0,50],[50,0,50],[50,0,-50],[-50,0,-50]])
        self.assertEqual(m['face_uvs'],[[[0,0],[255,0],[255,255],[0,255]]])
        self.assertEqual(m['face_textures'],[42])
        self.assertEqual(m['vertex_colours'],[[128,128,128]]*4)

    def test_untextured_colour(self):
        m=static_model(model_fixture(1),{})
        self.assertEqual(m['face_textures'],[None])
        self.assertEqual(m['vertex_colours'],[[40,80,120]]*4)

    def test_malformed_and_unsupported_rejected(self):
        with self.assertRaises(ValueError):static_model(model_fixture(),{})
        for offset,fmt,value in [(0,'4s',b'\x02XAR'),(4,'I',10),(8,'I',0x20),(18,'H',2),(20,'H',65535),(122,'H',0),(124,'H',4)]:
            b=model_fixture();struct.pack_into('<'+fmt,b,offset,value)
            with self.subTest(offset=offset),self.assertRaises(ValueError):static_model(b,{42:{}})
        with self.assertRaises(ValueError):static_model(model_fixture()[:80],{42:{}})

    def test_raw_translation_and_quarter_turn(self):
        self.assertEqual(transform([100,20,0],[5,10,15],[0,64,0]),[5,30,-85])
        self.assertEqual(transform([100,20,0],[5,10,15],[0,0,0]),[105,30,15])
        self.assertEqual(transform([0,0,100],[0,0,0],[64,0,0]),[0,-100,0])

    def test_main_definition_selects_subtype_model(self):
        exe=bytearray(0xb7000);struct.pack_into('<II',exe,0xb6224,EXE_BASE+100,0xffffffff)
        struct.pack_into('<IH',exe,100,EXE_BASE+400,2);exe[400:405]=b'Gate\0'
        struct.pack_into('<I',exe,276,EXE_BASE+500);struct.pack_into('<8H',exe,500,41,0,0,0,42,0,0,0)
        d=Definitions(exe,'.');self.assertEqual(d.resolve(0,1,6),(42,'Gate'))
        with self.assertRaises(ValueError):d.resolve(0,2,6)

    def test_placement_metadata_retained_and_unresolved_reported(self):
        class D:
            def resolve(self,*args):return 42,'Gate'
        data=bytearray(80);struct.pack_into('<4sIHHI',data,0,b'PTME',80,1,0,16)
        struct.pack_into('<IHBB',data,16,99,0,0,0);data[33]=64
        struct.pack_into('<3h',data,36,100,200,300);struct.pack_into('<2I',data,56,7,9)
        out=placed_objects(data,D(),6,{42:model_fixture()},{42:{}})
        self.assertEqual(len(out['instances']),1)
        self.assertEqual(out['instances'][0]['rotation'],[0,64,0])
        self.assertEqual(out['instances'][0]['init_flags'],7)
        self.assertEqual(out['instances'][0]['destroy_flags'],9)
        self.assertEqual(placed_objects(data,D(),6,{},{} )['omitted'][0]['reason'],'Model absent from level WAD')

if __name__=='__main__':unittest.main()
