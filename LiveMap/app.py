#!/usr/bin/env python3
"""Local, read-only MediEvil map window. Python standard library only."""
from __future__ import annotations
import argparse
import json
from http.server import ThreadingHTTPServer
from pathlib import Path
import webbrowser

from feed import Feed
from local_http import ROOT, make_handler


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
    server = ThreadingHTTPServer(('127.0.0.1',args.port), make_handler(feed, maps))
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
