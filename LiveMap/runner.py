#!/usr/bin/env python3
"""Runner entry point: private first-run disc import, then read-only live map."""
from __future__ import annotations
import argparse
import hmac
from http.server import ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import struct
import sys
import tempfile
import threading
from urllib.parse import urlsplit
import webbrowser
if sys.version_info < (3, 10):
    raise SystemExit('This source package needs Python 3.10 or newer. Install it from python.org or use a standalone build.')
from app import Feed, ROOT, make_handler
from disc_import import MAX_IMAGE, import_game, load_manifest


def user_data_dir():
    if sys.platform == 'win32':
        return Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData/Local')) / 'MediEvilMinimap'
    if sys.platform == 'darwin':
        return Path.home() / 'Library/Application Support/MediEvilMinimap'
    return Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local/share')) / 'medievil-minimap'


class Runner:
    def __init__(self, data_dir, feed):
        self.data_dir = Path(data_dir)
        self.maps_dir = self.data_dir / 'maps'
        self.feed = feed
        self.maps = {'maps': []}
        self.lock = threading.Lock()
        self.token = secrets.token_urlsafe(32)
        self.ready = False
        self.listening = False
        self.busy = False
        self.message = 'Choose your USA game data track to build your maps once.'
        self.error = None
        if self.maps_dir.exists():
            self.activate()

    def activate(self):
        maps = load_manifest(self.maps_dir)
        self.maps.update(maps)
        self.ready = True
        self.message = 'Maps ready. Connecting to DuckStation…'
        if self.listening:
            self.start_feed()

    def start_feed(self):
        if not self.feed.worker.is_alive():
            self.feed.worker.start()

    def progress(self, message):
        self.message = message

    def state(self):
        return {'ready': self.ready, 'busy': self.busy, 'message': self.message,
                'error': self.error, 'token': self.token}


def make_runner_handler(runner, port):
    Base = make_handler(runner.feed, runner.maps, port, maps_dir=runner.maps_dir)
    class Handler(Base):
        def local_request(self, mutation=False):
            hosts = {f'127.0.0.1:{port}', f'localhost:{port}'}
            origin = self.headers.get('Origin')
            if self.headers.get('Host') not in hosts or (origin and origin not in {f'http://{h}' for h in hosts}):
                self.send_error(403); return False
            if mutation and (origin not in {f'http://{h}' for h in hosts}
                    or not hmac.compare_digest(self.headers.get('X-Setup-Token', '').encode('utf-8'), runner.token.encode('ascii'))):
                self.send_error(403); return False
            return True

        def respond(self, payload, kind='application/json', status=200):
            if isinstance(payload, dict):
                payload = json.dumps(payload).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', kind)
            self.send_header('Content-Length', str(len(payload)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'; object-src 'none'; base-uri 'none'")
            self.end_headers()
            try:self.wfile.write(payload)
            except (BrokenPipeError, ConnectionResetError):pass

        def do_GET(self):
            if not self.local_request():return
            route = urlsplit(self.path).path
            if route == '/api/setup':
                self.respond(runner.state()); return
            if route in ('/setup.js', '/setup.css') or (route == '/' and not runner.ready):
                filename = 'setup.html' if route == '/' else route[1:]
                kind = 'text/html; charset=utf-8' if filename.endswith('html') else 'text/javascript; charset=utf-8' if filename.endswith('js') else 'text/css; charset=utf-8'
                self.respond((ROOT / 'web' / filename).read_bytes(), kind); return
            super().do_GET()

        def do_POST(self):
            if not self.local_request(mutation=True):return
            if urlsplit(self.path).path != '/api/import':
                self.send_error(404); return
            try:
                length = int(self.headers.get('Content-Length', ''))
                if not 0 < length <= MAX_IMAGE or self.headers.get('Transfer-Encoding'):
                    raise ValueError
                if self.headers.get('Content-Type') != 'application/octet-stream':
                    raise ValueError
            except ValueError:
                self.respond({'error':'Select one data-track BIN or ISO, up to 1 GiB.'}, status=400); return
            with runner.lock:
                if runner.busy or runner.ready:
                    self.respond({'error':'An import is already active or maps are already installed.'}, status=409); return
                runner.busy = True
                runner.error = None
            try:
                runner.data_dir.mkdir(parents=True, exist_ok=True)
                self.connection.settimeout(30)
                runner.progress('Receiving your disc image locally…')
                # The browser uploads only to loopback, never to an external service.
                with tempfile.TemporaryDirectory(prefix='.upload-', dir=runner.data_dir) as temp:
                    image = Path(temp) / 'data-track.bin'
                    with image.open('xb') as output:
                        remaining = length
                        while remaining:
                            block = self.rfile.read(min(1024 * 1024, remaining))
                            if not block:raise ValueError('Disc upload was interrupted. Select the file again.')
                            output.write(block);remaining -= len(block)
                    import_game(image, runner.data_dir, runner.progress)
                runner.activate()
                self.respond({'ready':True})
            except (ValueError, OSError, UnicodeError, KeyError, RuntimeError, struct.error) as error:
                runner.error = str(error)
                runner.progress('Import did not complete. No existing maps or disc files were changed.')
                self.respond({'error':runner.error}, status=400)
            finally:
                runner.busy = False
    return Handler


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, default=user_data_dir(), help='Writable local cache, independent of the app folder')
    parser.add_argument('--import-game', type=Path, help='Optional local BIN, ISO or CUE path; no upload needed')
    parser.add_argument('--emulator', choices=('duckstation','auto','redux'), default='duckstation')
    parser.add_argument('--pid',type=int)
    parser.add_argument('--gdb-port',type=int, help='Explicit read-only GDB fallback; attachment may pause DuckStation')
    parser.add_argument('--port',type=int,default=8768,help='Loopback map port; use 0 for an available port')
    browser = parser.add_mutually_exclusive_group()
    browser.add_argument('--open',dest='open',action='store_true',help='Open the map in your browser')
    browser.add_argument('--no-open',dest='open',action='store_false',help='Do not open a browser (automation/headless checks)')
    parser.set_defaults(open=bool(getattr(sys,'frozen',False)))
    args = parser.parse_args(argv)
    if args.port != 0 and not 1024 <= args.port <= 65535:parser.error('Map port must be 1024–65535, or 0.')
    if args.pid is not None and args.pid <= 0:parser.error('PID must be positive.')
    if args.gdb_port is not None and (not 1 <= args.gdb_port <= 65535 or args.gdb_port == args.port or args.pid is not None or args.emulator == 'redux'):
        parser.error('GDB needs a separate port1–65535, no PID, and DuckStation selected.')
    if args.gdb_port:
        print('GDB reads only. DuckStation itself may pause on attachment; resume manually. Disconnect may change its pause state.', flush=True)
    if args.import_game:
        try:import_game(args.import_game, args.data_dir, lambda text:print(text,flush=True))
        except (ValueError,OSError) as error:parser.error(str(error))
    feed = Feed(args.pid, emulator=args.emulator, gdb_port=args.gdb_port)
    try:
        runner = Runner(args.data_dir, feed)
        # Bind first so the exact selected port is used for Host/Origin checks.
        server = ThreadingHTTPServer(('127.0.0.1',args.port), make_runner_handler(runner,args.port))
        port = server.server_address[1]
        if port == args.gdb_port:raise ValueError('Map and GDB ports must differ.')
        server.RequestHandlerClass = make_runner_handler(runner,port)
        runner.listening = True
        if runner.ready:runner.start_feed()
    except (OSError,ValueError) as error:
        feed.stop.set()
        if feed.worker.is_alive():feed.worker.join(timeout=5)
        parser.error(f'Cannot start minimap: {error}. If the map port is occupied, use --port 0.')
    url = f'http://127.0.0.1:{port}'
    print(f'MediEvil minimap: {url}\nLocal cache: {args.data_dir}\nRead-only tracking. No telemetry reporting. Ctrl-C to stop.',flush=True)
    if args.open:webbrowser.open(url)
    try:server.serve_forever(poll_interval=.2)
    except KeyboardInterrupt:pass
    finally:
        server.server_close();feed.stop.set()
        if feed.worker.is_alive():feed.worker.join(timeout=5)

if __name__=='__main__':main()
