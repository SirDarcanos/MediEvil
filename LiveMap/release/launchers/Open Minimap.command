#!/bin/sh
HERE=$(CDPATH= cd -P "$(dirname "$0")" && pwd) || exit 1
cd "$HERE" || exit 1
if [ -x "$HERE/MediEvilMinimap" ]; then
  "$HERE/MediEvilMinimap" --gdb-port 2345 --open "$@"
else
  if ! command -v python3 >/dev/null 2>&1; then
    printf '%s\n' 'Python 3.10+ is required for this source package. Install it from python.org or use a standalone Mac build.'
    read -r answer
    exit 1
  fi
  python3 "$HERE/runner.py" --gdb-port 2345 --open "$@"
fi
status=$?
if [ "$status" -ne 0 ]; then printf '%s\n' 'Minimap stopped. Press Return to close.'; read -r answer; fi
exit "$status"
