import copy,unittest
from edge_on import offsets,fence_faces,terrain_fence_proxies

class EdgeOnTests(unittest.TestCase):
 def test_only_collinear_projection_gets_width_even_if_shoelace_cancels(self):
  self.assertIsNone(offsets([[0,-100,0],[100,-100,0],[0,0,100],[100,0,100]]))
  self.assertIsNone(offsets([[0,-100,0],[1,0,0],[1,0,100],[0,-100,100]]))
  self.assertIsNone(offsets([[0,0,0],[0,0,100],[0,0,200]]))
 def test_exact_two_pixel_span_on_rotated_and_sloping_fence(self):
  points=[[0,-100,0],[0,0,0],[100,50,100],[100,-50,100]];original=copy.deepcopy(points);out=offsets(points)
  self.assertAlmostEqual(sum((out[0][k]-out[1][k])**2 for k in range(2))**.5,2)
  self.assertAlmostEqual(sum((out[2][k]-out[3][k])**2 for k in range(2))**.5,2);self.assertEqual(points,original)
 def test_walls_and_unidentified_cutouts_stay_untouched(self):
  mesh={'vertices':[[0,-100,0],[0,0,0],[0,0,100],[0,-100,100]],'faces':[[0,1,2,3]]*3,'face_textures':[669,768,None]}
  self.assertEqual(set(fence_faces(mesh,'GY1')),{'0'})
  self.assertEqual(fence_faces(mesh,'AC'),{})
 def test_named_gate_not_other_prop(self):
  mesh={'vertices':[[65537,-100,0],[65537,0,0],[65537,0,100],[65537,-100,100]],'faces':[[0,1,2,3]],'face_textures':[None]}
  self.assertEqual(set(fence_faces(mesh,'CR',[{'model':293,'first_face':0,'face_count':1}])),{'0'})
  self.assertEqual(fence_faces(mesh,'CR',[{'model':162,'first_face':0,'face_count':1}]),{})
  self.assertEqual(mesh['vertices'][0][0],65537)
 def test_graveyard_proxy_covers_subpixel_width_without_touching_mesh(self):
  mesh={'vertices':[[0,-100,0],[1,0,0],[1,0,100],[0,-100,100]],'faces':[[0,1,2,3]],'face_textures':[669]};before=copy.deepcopy(mesh)
  result=terrain_fence_proxies(mesh,'GY1');self.assertEqual(len(result),1)
  self.assertGreater(result[0]['width'],0);self.assertLessEqual(result[0]['width'],1)
  self.assertEqual(mesh,before)
 def test_proxy_is_only_the_identified_graveyard_fence(self):
  mesh={'vertices':[[0,-100,0],[0,0,0],[0,0,100],[0,-100,100]],'faces':[[0,1,2,3]]*2,'face_textures':[669,768]}
  self.assertEqual([x['face'] for x in terrain_fence_proxies(mesh,'GY1')],[0])
  self.assertEqual(terrain_fence_proxies(mesh,'CR'),[])
  mesh['face_textures']=[1990,669]
  self.assertEqual([x['face'] for x in terrain_fence_proxies(mesh,'GS')],[0])
if __name__=='__main__':unittest.main()
