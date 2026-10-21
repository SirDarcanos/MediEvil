#!/usr/bin/env python3
"""Local, read-only MediEvil map window. Python standard library only."""
from __future__ import annotations
import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import threading
import time
from urllib.parse import urlsplit
import webbrowser
from ram import Tracker, decode_snapshot

ROOT = Path(__file__).resolve().parent


class Feed:
    def __init__(self, pid=None, snapshot=None, emulator='auto', gdb_port=None):
        self.tracker = Tracker(pid, emulator=emulator, gdb_port=gdb_port)
        self.stop = threading.Event()
        self.state = {'status':'connecting', 'message':'Connecting to local emulator…'}
        self.snapshot = snapshot
        self.worker = threading.Thread(target=self.run, daemon=True)

    def current(self):
        state = self.state
        if state.get('source') == 'live' and time.time() - state.get('sample_time', time.time()) > 1.5:
            return {'status':'error', 'source':'live', 'message':'RAM samples are stale; position hidden.'}
        return state

    def run(self):
        try:
            if self.snapshot:
                try:
                    data = self.snapshot.read_bytes()
                    self.state = {**decode_snapshot(data), 'source':'snapshot', 'message':'Recorded RAM snapshot — not live.', 'epoch':0}
                except (OSError, ValueError) as error:
                    self.state = {'status':'error', 'source':'snapshot', 'message':f'Cannot read snapshot: {error}'}
                return
            while not self.stop.is_set():
                try:
                    self.state = {**self.tracker.sample(), 'source':'live'}
                except Exception as error:
                    self.state = {'status':'error','message':f'RAM reader: {error}', 'source':'live'}
                self.stop.wait(1 / 30)
        finally:
            self.tracker.close()


def make_handler(feed, maps, port, maps_dir=None):
    maps_dir = Path(maps_dir) if maps_dir is not None else ROOT / 'data/maps'
    files = {'/':'index.html', '/app.js':'app.js', '/terrain.js':'terrain.js', '/style.css':'style.css', '/dan.png':'dan.png', '/bizhawk.lua':'bizhawk.lua'}
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            # Local origins only; do not expose game data through DNS rebinding.
            allowed_hosts = {f'127.0.0.1:{port}', f'localhost:{port}'}
            if self.headers.get('Host') not in allowed_hosts:
                self.send_error(403); return
            origin = self.headers.get('Origin')
            if origin and origin not in {f'http://{h}' for h in allowed_hosts}:
                self.send_error(403); return
            route = urlsplit(self.path).path
            if route == '/api/state':
                payload = json.dumps(feed.current()).encode()
                kind = 'application/json'
            elif route == '/api/maps':
                payload = json.dumps(maps).encode()
                kind = 'application/json'
            elif route in files:
                file = ROOT / 'web' / files[route]
                if route == '/dan.png' and not file.exists():
                    file = ROOT / 'web/marker.svg'
                try:
                    payload = file.read_bytes()
                except FileNotFoundError:
                    self.send_error(404); return
                kind = {'.html':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8','.css':'text/css; charset=utf-8','.png':'image/png','.svg':'image/svg+xml','.lua':'text/plain; charset=utf-8'}[file.suffix]
            else:
                candidates = {f'/maps/{m["code"]}.json':m['file'] for m in maps['maps']}
                if route not in candidates:
                    self.send_error(404); return
                file = (maps_dir / candidates[route]).resolve()
                if not file.is_relative_to(maps_dir.resolve()):
                    self.send_error(403); return
                try:
                    payload = file.read_bytes()
                except FileNotFoundError:
                    self.send_error(404); return
                kind = 'application/json'
            self.send_response(200)
            self.send_header('Content-Type', kind)
            self.send_header('Content-Length', str(len(payload)))
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'")
            self.end_headers()
            try:
                self.wfile.write(payload)
            except (BrokenPipeError, ConnectionResetError):
                pass
    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8768)
    parser.add_argument('--pid', type=int, help='Select an emulator process when more than one is running')
    parser.add_argument('--emulator', choices=('auto', 'duckstation', 'redux', 'bizhawk'), default='auto',
                        help='Auto-detect supported emulators, or restrict discovery to one kind')
    parser.add_argument('--gdb-port', type=int,
                        help='Explicit loopback GDB fallback. Attachment may pause DuckStation; resume manually. No control commands are sent.')
    parser.add_argument('--open', action='store_true', help='Open the local map in your default browser')
    parser.add_argument('--snapshot', type=Path, help='Inspect an explicitly labeled recorded RAM snapshot (not live)')
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error('port must be 1024–65535')
    if args.pid is not None and args.pid <= 0:
        parser.error('pid must be positive')
    if args.gdb_port is not None:
        if not 1 <= args.gdb_port <= 65535 or args.gdb_port == args.port:
            parser.error('GDB port must be 1–65535 and different from the map port')
        if args.pid is not None or args.snapshot or args.emulator not in ('auto', 'duckstation'):
            parser.error('--gdb-port requires auto/DuckStation and cannot be combined with --pid or --snapshot')
        print('GDB fallback: DuckStation may pause when attached. Resume it manually. The map sends memory reads only.', flush=True)
    manifest = ROOT / 'data/maps/manifest.json'
    if not manifest.exists():
        parser.error('Map data missing. Run python3 extract_maps.py first.')
    maps = json.loads(manifest.read_text())
    feed = Feed(args.pid, args.snapshot, emulator=args.emulator, gdb_port=args.gdb_port)
    server = ThreadingHTTPServer(('127.0.0.1',args.port), make_handler(feed,maps,args.port))
    feed.worker.start()
    url = f'http://127.0.0.1:{args.port}'
    print(f'MediEvil map: {url}\nRead-only RAM. Ctrl-C to stop.', flush=True)
    if args.open:
        webbrowser.open(url)
    try:
        server.serve_forever(poll_interval=0.2)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        feed.stop.set()
        feed.worker.join(timeout=5)

if __name__ == '__main__':
    main()
