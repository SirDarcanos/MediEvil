import base64
import struct
import unittest
import zlib
from textures import vlo_images, texture_atlas, png_rgba
from extract_maps import parse_map
from test_appearance import vlo


class TextureTests(unittest.TestCase):
    def test_native_texel_order_and_alpha(self):
        image = vlo_images(vlo())[42]
        self.assertEqual(image['crop'], [0, 0, 4, 1])
        self.assertEqual(image['rgba'], bytes([255,0,0,255,0,255,0,255] * 2))
        data = vlo()
        data[56:58] = b'\x10\x10'
        self.assertEqual(vlo_images(data)[42]['rgba'][:4], b'\0\0\0\0')
        struct.pack_into('<H', data, 58, 0x8000)
        self.assertEqual(vlo_images(data)[42]['rgba'][:4], b'\0\0\0\xff')
        struct.pack_into('<H', data, 38, 1)
        self.assertEqual(vlo_images(data)[42]['rgba'][:4], b'\0\0\0\x80')

    def test_eight_bit_and_direct_pixels(self):
        data = vlo(1);data[42] = 2
        self.assertEqual(vlo_images(data)[42]['rgba'], bytes([255,0,0,255,0,255,0,255]))
        direct = bytearray(48)
        struct.pack_into('<4s4I', direct, 0, b'2GRV', 1, 20, 0, 44)
        struct.pack_into('<4HI4H4B', direct, 20, 0, 0, 2, 1, 44, 7, 2 << 7, 0, 0, 0, 0, 2, 1)
        struct.pack_into('<2H', direct, 44, 31, 31 << 10)
        self.assertEqual(vlo_images(direct)[7]['rgba'], bytes([255,0,0,255,0,0,255,255]))

    def test_content_rectangle_and_bad_data(self):
        data = vlo();data[40] = 1;data[42] = 2
        self.assertEqual(vlo_images(data)[42]['crop'], [1,0,2,1])
        data[40] = 250
        with self.assertRaises(ValueError): vlo_images(data)
        with self.assertRaises(ValueError): vlo_images(b'2GRV')
        data = vlo();struct.pack_into('<I', data, 28, 99999)
        with self.assertRaises(ValueError): vlo_images(data)

    def test_png_atlas_retains_texels_and_edge_gutter(self):
        atlas = texture_atlas(vlo_images(vlo()), [42])
        png = base64.b64decode(atlas['png'].split(',')[1]);self.assertEqual(png[:8], b'\x89PNG\r\n\x1a\n')
        at=8;compressed=b''
        while at < len(png):
            n=struct.unpack_from('>I',png,at)[0];tag=png[at+4:at+8];payload=png[at+8:at+8+n]
            self.assertEqual(zlib.crc32(tag+payload),struct.unpack_from('>I',png,at+8+n)[0])
            if tag==b'IDAT': compressed+=payload
            at+=n+12
        rows=zlib.decompress(compressed);stride=1+atlas['width']*4
        x,y,w,h=atlas['rects'][42]
        self.assertEqual((w,h),(4,1))
        pixel=lambda px,py: rows[py*stride+1+px*4:py*stride+1+px*4+4]
        self.assertEqual(pixel(x,y),bytes([255,0,0,255]))
        self.assertEqual(pixel(x+1,y),bytes([0,255,0,255]))
        self.assertEqual(pixel(x-2,y-2),pixel(x,y))
        self.assertEqual(pixel(x+w+1,y+2),pixel(x+w-1,y))
        with self.assertRaises(ValueError): texture_atlas({}, [42])
        with self.assertRaises(ValueError): png_rgba(1,1,b'')

    def test_polygon_uv_remap_and_shading_integration(self):
        data=bytearray(112)
        struct.pack_into('<4sI8sI',data,0,b'GROF',20,b'MEDIEVIL',len(data))
        struct.pack_into('<4sI',data,20,b'GXSP',92)
        struct.pack_into('<5H2B4I',data,28,0,0,0,1,4,0,0,56,80,0,0)
        struct.pack_into('<6H8B',data,56,0,1,2,3,7,3,0,0,255,0,0,255,255,255)
        for i in range(4): struct.pack_into('<3hH',data,80+i*8,i,0,i,0x8480)
        remap=struct.pack('<8H',0,0,0,0,0,0,0,42)
        g=parse_map(data,{42:[200,100,50]},remap)
        self.assertEqual(g['faces'],[[0,1,3,2]])
        self.assertEqual(g['face_uvs'],[[[0,0],[255,0],[255,255],[0,255]]])
        self.assertEqual(g['face_textures'],[42])
        self.assertEqual(g['vertex_colours'],[[128,128,128]]*4)
        self.assertEqual(g['face_colours'],[[200,100,50]])
        with self.assertRaises(ValueError): parse_map(data,{},remap)
        with self.assertRaises(ValueError): parse_map(data,{42:[1,2,3]},b'')


if __name__ == '__main__': unittest.main()
