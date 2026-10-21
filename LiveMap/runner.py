#!/usr/bin/env python3
"""Runner entry point: private first-run disc import, then read-only live map."""
from __future__ import annotations

import argparse
from http.server import ThreadingHTTPServer
import os
from pathlib import Path
import secrets
import sys
import threading
import webbrowser

if sys.version_info < (3, 10):
    raise SystemExit('This source package needs Python 3.10 or newer. Install it from python.org or use a standalone build.')

from disc_import import import_game, load_manifest
from feed import Feed
from local_http import make_runner_handler


def user_data_dir():
    if sys.platform == 'win32':
        return Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData/Local')) / 'MediEvilMinimap'
    if sys.platform == 'darwin':
        return Path.home() / 'Library/Application Support/MediEvilMinimap'
    return Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local/share')) / 'medievil-minimap'


class Runner:
    """Setup state; sampling starts only once maps and the HTTP listener are ready."""

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


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, default=user_data_dir(),
                        help='Writable local cache, independent of the app folder')
    parser.add_argument('--import-game', type=Path, help='Optional local BIN, ISO or CUE path; no upload needed')
    parser.add_argument('--emulator', choices=('duckstation', 'auto', 'redux'), default='duckstation')
    parser.add_argument('--pid', type=int)
    parser.add_argument('--gdb-port', type=int, help='Explicit read-only GDB fallback; attachment may pause DuckStation')
    parser.add_argument('--port', type=int, default=8768, help='Loopback map port; use 0 for an available port')
    browser = parser.add_mutually_exclusive_group()
    browser.add_argument('--open', dest='open', action='store_true', help='Open the map in your browser')
    browser.add_argument('--no-open', dest='open', action='store_false', help='Do not open a browser (automation/headless checks)')
    parser.set_defaults(open=bool(getattr(sys, 'frozen', False)))
    args = parser.parse_args(argv)
    if args.port != 0 and not 1024 <= args.port <= 65535:
        parser.error('Map port must be 1024–65535, or 0.')
    if args.pid is not None and args.pid <= 0:
        parser.error('PID must be positive.')
    if args.gdb_port is not None and (not 1 <= args.gdb_port <= 65535 or args.gdb_port == args.port
                                     or args.pid is not None or args.emulator == 'redux'):
        parser.error('GDB needs a separate port1–65535, no PID, and DuckStation selected.')
    if args.gdb_port:
        print('GDB reads only. DuckStation itself may pause on attachment; resume manually. Disconnect may change its pause state.', flush=True)
    if args.import_game:
        try:
            import_game(args.import_game, args.data_dir, lambda text: print(text, flush=True))
        except (ValueError, OSError) as error:
            parser.error(str(error))
    feed = Feed(args.pid, emulator=args.emulator, gdb_port=args.gdb_port)
    try:
        runner = Runner(args.data_dir, feed)
        # Handlers use the listener's actual port, including an OS-selected port.
        server = ThreadingHTTPServer(('127.0.0.1', args.port), make_runner_handler(runner))
        port = server.server_address[1]
        if port == args.gdb_port:
            raise ValueError('Map and GDB ports must differ.')
        runner.listening = True
        if runner.ready:
            runner.start_feed()
    except (OSError, ValueError) as error:
        feed.stop.set()
        if feed.worker.is_alive():
            feed.worker.join(timeout=5)
        parser.error(f'Cannot start minimap: {error}. If the map port is occupied, use --port 0.')
    url = f'http://127.0.0.1:{port}'
    print(f'MediEvil minimap: {url}\nLocal cache: {args.data_dir}\nRead-only tracking. No telemetry reporting. Ctrl-C to stop.', flush=True)
    if args.open:
        webbrowser.open(url)
    try:
        server.serve_forever(poll_interval=0.2)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        feed.stop.set()
        if feed.worker.is_alive():
            feed.worker.join(timeout=5)


if __name__ == '__main__':
    main()
