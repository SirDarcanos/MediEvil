"""Loopback-only HTTP handlers for the map and first-run disc import."""
from __future__ import annotations

import hmac
from http.server import BaseHTTPRequestHandler
import json
from pathlib import Path
import struct
import tempfile
from urllib.parse import urlsplit

from disc_import import MAX_IMAGE, import_game

ROOT = Path(__file__).resolve().parent
CONTENT_TYPES = {
    '.html': 'text/html; charset=utf-8',
    '.js': 'text/javascript; charset=utf-8',
    '.css': 'text/css; charset=utf-8',
    '.png': 'image/png',
    '.svg': 'image/svg+xml',
    '.json': 'application/json',
}
MAP_FILES = {
    '/': 'index.html',
    '/app.js': 'app.js',
    '/terrain.js': 'terrain.js',
    '/raster.js': 'raster.js',
    '/movement.js': 'movement.js',
    '/style.css': 'style.css',
    '/dan.png': 'dan.png',
}
COMMON_CSP = "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; "
MAP_CSP = COMMON_CSP + "img-src 'self' data:; frame-ancestors 'none'"
SETUP_CSP = COMMON_CSP + "frame-ancestors 'none'; object-src 'none'; base-uri 'none'"


class LocalHandler(BaseHTTPRequestHandler):
    """Shared origin checks and responses; routes remain explicit allowlists."""

    def log_message(self, *args):
        pass

    @property
    def route(self):
        return urlsplit(self.path).path

    def local_request(self, token=None):
        port = self.server.server_address[1]
        hosts = {f'127.0.0.1:{port}', f'localhost:{port}'}
        origins = {f'http://{host}' for host in hosts}
        origin = self.headers.get('Origin')
        if self.headers.get('Host') not in hosts or (origin and origin not in origins):
            self.send_error(403)
            return False
        if token is not None and (origin not in origins or not hmac.compare_digest(
                self.headers.get('X-Setup-Token', '').encode('utf-8'), token.encode('ascii'))):
            self.send_error(403)
            return False
        return True

    def respond(self, payload, kind='application/json', status=200, *, csp=MAP_CSP):
        if isinstance(payload, dict):
            payload = json.dumps(payload).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', kind)
        self.send_header('Content-Length', str(len(payload)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Security-Policy', csp)
        self.end_headers()
        try:
            self.wfile.write(payload)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def serve_file(self, path, *, kind=None, csp=MAP_CSP):
        try:
            payload = path.read_bytes()
        except FileNotFoundError:
            self.send_error(404)
            return
        self.respond(payload, kind if kind is not None else CONTENT_TYPES[path.suffix], csp=csp)


def make_handler(feed, maps, maps_dir=None):
    maps_dir = Path(maps_dir) if maps_dir is not None else ROOT / 'data/maps'

    class MapHandler(LocalHandler):
        def do_GET(self):
            if self.local_request():
                self.serve_map()

        def serve_map(self):
            route = self.route
            if route == '/api/state':
                self.respond(feed.current())
            elif route == '/api/maps':
                self.respond(maps)
            elif route in MAP_FILES:
                path = ROOT / 'web' / MAP_FILES[route]
                if route == '/dan.png' and not path.exists():
                    path = ROOT / 'web/marker.svg'
                self.serve_file(path)
            else:
                # Maps are activated after first-run import, so derive routes
                # from the current manifest rather than caching an empty index.
                candidates = {f'/maps/{m["code"]}.json': m['file'] for m in maps['maps']}
                if route not in candidates:
                    self.send_error(404)
                    return
                path = (maps_dir / candidates[route]).resolve()
                if not path.is_relative_to(maps_dir.resolve()):
                    self.send_error(403)
                    return
                self.serve_file(path, kind='application/json')

    return MapHandler


def make_runner_handler(runner):
    class RunnerHandler(make_handler(runner.feed, runner.maps, runner.maps_dir)):
        def setup_response(self, payload, status=200):
            self.respond(payload, status=status, csp=SETUP_CSP)

        def do_GET(self):
            if not self.local_request():
                return
            route = self.route
            if route == '/api/setup':
                self.setup_response(runner.state())
            elif route in ('/setup.js', '/setup.css') or (route == '/' and not runner.ready):
                filename = 'setup.html' if route == '/' else route[1:]
                self.serve_file(ROOT / 'web' / filename, csp=SETUP_CSP)
            else:
                self.serve_map()

        def do_POST(self):
            if not self.local_request(token=runner.token):
                return
            if self.route != '/api/import':
                self.send_error(404)
                return
            try:
                length = int(self.headers.get('Content-Length', ''))
                if not 0 < length <= MAX_IMAGE or self.headers.get('Transfer-Encoding'):
                    raise ValueError
                if self.headers.get('Content-Type') != 'application/octet-stream':
                    raise ValueError
            except ValueError:
                self.setup_response({'error': 'Select one data-track BIN or ISO, up to 1 GiB.'}, status=400)
                return
            with runner.lock:
                if runner.busy or runner.ready:
                    self.setup_response({'error': 'An import is already active or maps are already installed.'}, status=409)
                    return
                runner.busy = True
                runner.error = None
            try:
                runner.data_dir.mkdir(parents=True, exist_ok=True)
                self.connection.settimeout(30)
                runner.progress('Receiving your disc image locally…')
                # Uploads stay on loopback; temporary disc bytes never enter
                # the app directory or survive a completed/failed import.
                with tempfile.TemporaryDirectory(prefix='.upload-', dir=runner.data_dir) as temp:
                    image = Path(temp) / 'data-track.bin'
                    with image.open('xb') as output:
                        remaining = length
                        while remaining:
                            block = self.rfile.read(min(1024 * 1024, remaining))
                            if not block:
                                raise ValueError('Disc upload was interrupted. Select the file again.')
                            output.write(block)
                            remaining -= len(block)
                    import_game(image, runner.data_dir, runner.progress)
                runner.activate()
                self.setup_response({'ready': True})
            except (ValueError, OSError, UnicodeError, KeyError, RuntimeError, struct.error) as error:
                runner.error = str(error)
                runner.progress('Import did not complete. No existing maps or disc files were changed.')
                self.setup_response({'error': runner.error}, status=400)
            finally:
                runner.busy = False

    return RunnerHandler
