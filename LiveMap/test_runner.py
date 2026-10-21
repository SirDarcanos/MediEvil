import http.client
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from disc_import import EXE_SHA1, MAX_IMAGE
from runner import Runner, make_runner_handler, main


class FakeFeed:
    def __init__(self):
        self.stop=threading.Event()
        self.worker=threading.Thread(target=self.stop.wait,daemon=True)
    def current(self):return {'status':'connecting','message':'Fixture, no emulator attachment'}


def fake_maps(source, cache, progress):
    root=Path(cache)/'maps';root.mkdir()
    maps=[]
    for n in range(25):
        code=f'M{n:02}';(root/(code+'.json')).write_text('{}');maps.append({'code':code,'file':code+'.json'})
    (root/'manifest.json').write_text(json.dumps({'exe_sha1':EXE_SHA1,'maps':maps}))
    return root


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.feed=FakeFeed();self.runner=Runner(self.temp.name,self.feed)
        self.server=ThreadingHTTPServer(('127.0.0.1',0),make_runner_handler(self.runner));self.port=self.server.server_address[1]
        self.runner.listening=True
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join(2);self.feed.stop.set()
        if self.feed.worker.is_alive():self.feed.worker.join(2)
        self.temp.cleanup()
    def request(self,route,method='GET',body=None,headers=None):
        c=http.client.HTTPConnection('127.0.0.1',self.port,timeout=3)
        c.request(method,route,body,headers or {});r=c.getresponse();result=r.status,r.read();c.close();return result
    def post_headers(self):
        return {'Origin':f'http://127.0.0.1:{self.port}','X-Setup-Token':self.runner.token,'Content-Type':'application/octet-stream'}
    def test_empty_cache_shows_setup_without_opening_emulator(self):
        status,body=self.request('/');self.assertEqual(status,200);self.assertIn(b'Build your maps once',body)
        self.assertFalse(self.feed.worker.is_alive())
        status,body=self.request('/api/setup');self.assertEqual(json.loads(body)['token'],self.runner.token)
    def test_cross_origin_and_rebinding_reads_rejected(self):
        self.assertEqual(self.request('/api/setup',headers={'Origin':'https://evil.invalid'})[0],403)
        self.assertEqual(self.request('/api/state',headers={'Host':f'evil.invalid:{self.port}'})[0],403)
    def test_setup_and_map_keep_distinct_security_policies(self):
        for route, is_map in (('/api/setup', False), ('/setup.js', False),
                              ('/api/state', True), ('/terrain.js', True)):
            with self.subTest(route=route):
                connection = http.client.HTTPConnection('127.0.0.1', self.port, timeout=3)
                self.addCleanup(connection.close)
                connection.request('GET', route)
                response = connection.getresponse()
                body = response.read()
                self.assertEqual(response.status, 200)
                self.assertEqual(int(response.getheader('Content-Length')), len(body))
                self.assertEqual(response.getheader('Cache-Control'), 'no-store')
                self.assertEqual(response.getheader('X-Content-Type-Options'), 'nosniff')
                self.assertIsNone(response.getheader('Access-Control-Allow-Origin'))
                policy = response.getheader('Content-Security-Policy')
                self.assertIn("frame-ancestors 'none'", policy)
                self.assertEqual("img-src 'self' data:" in policy, is_map)
                self.assertEqual("object-src 'none'" in policy, not is_map)

    def test_import_requires_both_origin_and_token(self):
        headers=self.post_headers();del headers['Origin']
        self.assertEqual(self.request('/api/import','POST',b'data',headers)[0],403)
        headers=self.post_headers();headers['X-Setup-Token']='bad'
        self.assertEqual(self.request('/api/import','POST',b'data',headers)[0],403)
        headers=self.post_headers();headers['X-Setup-Token']='\u00e9'
        self.assertEqual(self.request('/api/import','POST',b'data',headers)[0],403)
    def test_failed_upload_import_cleans_temp_and_can_retry(self):
        status,body=self.request('/api/import','POST',b'not a disc',self.post_headers())
        self.assertEqual(status,400);self.assertIn('error',json.loads(body));self.assertFalse(self.runner.busy)
        self.assertEqual(list(Path(self.temp.name).iterdir()),[])
        self.assertFalse(self.feed.worker.is_alive())
    def test_large_upload_rejected_before_body(self):
        h=self.post_headers();h['Content-Length']=str(MAX_IMAGE+1)
        self.assertEqual(self.request('/api/import','POST',b'',h)[0],400)
    def test_success_switches_to_live_ui_and_reuses_cache(self):
        with patch('local_http.import_game',side_effect=fake_maps):
            status,body=self.request('/api/import','POST',b'fixture',self.post_headers())
        self.assertEqual(status,200);self.assertTrue(json.loads(body)['ready']);self.assertTrue(self.feed.worker.is_alive())
        self.assertIn(b'id="map"',self.request('/')[1]);self.assertEqual(self.request('/maps/M00.json')[1],b'{}')
        self.assertEqual(self.request('/api/import','POST',b'fixture',self.post_headers())[0],409)
        feed=FakeFeed();restored=Runner(self.temp.name,feed);self.assertTrue(restored.ready)
        self.assertFalse(feed.worker.is_alive(),'A failed port bind must not attach to an emulator')
    def test_native_double_click_opens_browser_source_stays_opt_in(self):
        cases=[(True,[],True),(True,['--no-open'],False),(False,[],False),(False,['--open'],True)]
        for frozen,flags,expected in cases:
            with self.subTest(frozen=frozen,flags=flags),tempfile.TemporaryDirectory()as tmp:
                feed=FakeFeed()
                with patch('runner.sys.frozen',frozen,create=True),patch('runner.Feed',return_value=feed),patch('runner.ThreadingHTTPServer')as server,patch('runner.webbrowser.open')as opened:
                    server.return_value.server_address=('127.0.0.1',54321)
                    server.return_value.serve_forever.side_effect=KeyboardInterrupt
                    main(['--data-dir',tmp,'--port','54321']+flags)
                    if expected:opened.assert_called_once_with('http://127.0.0.1:54321')
                    else:opened.assert_not_called()
                self.assertFalse(feed.worker.is_alive(),'Empty-cache launch must not attach to an emulator')

    def test_documented_preserve_then_reimport_recovers_damaged_cache(self):
        for damage in ('empty','malformed','missing-map'):
            with self.subTest(damage=damage),tempfile.TemporaryDirectory()as tmp:
                root=Path(tmp);cache=root/'app-data';cache.mkdir();sentinel=root/'own-save.sav';sentinel.write_bytes(b'protected fixture')
                if damage=='empty':(cache/'maps').mkdir()
                else:
                    fake_maps(None,cache,None)
                    if damage=='malformed':(cache/'maps/manifest.json').write_text('{')
                    else:(cache/'maps/M00.json').unlink()
                original={str(f.relative_to(cache/'maps')):f.read_bytes()for f in(cache/'maps').rglob('*')if f.is_file()}
                with self.assertRaises((ValueError,OSError)):Runner(cache,FakeFeed())
                (cache/'maps').rename(cache/'maps.backup')
                recovery=Runner(cache,FakeFeed());self.assertFalse(recovery.ready)
                fake_maps(None,cache,None);recovery.activate();self.assertTrue(recovery.ready)
                preserved={str(f.relative_to(cache/'maps.backup')):f.read_bytes()for f in(cache/'maps.backup').rglob('*')if f.is_file()}
                self.assertEqual(original,preserved);self.assertEqual(sentinel.read_bytes(),b'protected fixture')

    def test_missing_game_portrait_uses_original_neutral_svg(self):
        with tempfile.TemporaryDirectory()as tmp:
            root=Path(tmp);(root/'web').mkdir();(root/'web/marker.svg').write_text('<svg>neutral</svg>')
            with patch('local_http.ROOT',root):
                status,body=self.request('/dan.png')
            self.assertEqual(status,200);self.assertEqual(body,b'<svg>neutral</svg>')

    def test_map_symlink_keeps_route_content_type_and_path_confinement(self):
        maps_dir = fake_maps(None, self.temp.name, None)
        map_path = maps_dir / 'M00.json'
        backing = map_path.with_suffix('.payload')
        map_path.rename(backing)
        try:
            map_path.symlink_to(backing.name)
        except (OSError, NotImplementedError) as error:
            self.skipTest(f'Creating a local symlink is unavailable: {error}')
        self.runner.activate()  # This is a valid cache, including its internal symlink.
        connection = http.client.HTTPConnection('127.0.0.1', self.port, timeout=3)
        self.addCleanup(connection.close)
        connection.request('GET', '/maps/M00.json')
        response = connection.getresponse()
        self.assertEqual(response.status, 200)
        self.assertEqual(response.getheader('Content-Type'), 'application/json')
        self.assertEqual(response.read(), b'{}')

        # A changed link may not escape the map directory after activation.
        private = Path(self.temp.name) / 'private.txt'
        private.write_text('private fixture')
        map_path.unlink()
        map_path.symlink_to(private)
        self.assertEqual(self.request('/maps/M00.json')[0], 403)

    def test_map_path_does_not_expose_arbitrary_files(self):
        self.runner.maps['maps']=[{'code':'BAD','file':'../../private.txt'}]
        self.assertEqual(self.request('/maps/BAD.json')[0],403)

if __name__=='__main__':unittest.main()
