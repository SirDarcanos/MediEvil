#!/bin/sh
HERE=$(CDPATH= cd -P "$(dirname "$0")" && pwd) || exit 1
cd "$HERE" || exit 1
if [ -x "$HERE/MediEvilMinimap" ]; then
  exec "$HERE/MediEvilMinimap" --open "$@"
fi
if ! command -v python3 >/dev/null 2>&1; then
  printf '%s\n' 'Python 3.10+ is required for this source package. Install Python or use a standalone Linux build.' >&2
  exit 1
fi
exec python3 "$HERE/runner.py" --open "$@"
