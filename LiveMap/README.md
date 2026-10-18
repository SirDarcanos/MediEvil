# MediEvil LiveMap

A standalone companion minimap for runners using their own DuckStation, BIOS, USA game and saves. On first launch it extracts all 25 textured maps from the runner's own supported disc image into local app-data storage. It reads live RAM without controlling or patching the game.

**This folder is the maintained project location.** No extracted game assets, emulator, BIOS, savestates, RAM dumps or controller-automation research belong in this repository or its downloads.

## Run from source

Requires Python 3.10+ and a current browser. No Python packages are needed.

From this folder:

```sh
python3 runner.py --open
```

On macOS, use the explicit GDB fallback:

```sh
python3 runner.py --gdb-port 2345 --open
```

Follow the first-run page to select your own data-track BIN/ISO. Windows/Linux use DuckStation's read-only shared-memory export; macOS requires the configured local GDB server and may pause on attachment. See [the runner guide](RUNNERS.md) for configuration, supported game revision, controls, cache location and recovery. No special savestate or analogue controller is required.

## Build and check

```sh
python3 -m unittest discover -s . -p 'test_*.py'
python3 release/build.py --output dist
```

The default build is a **Python-required source preview**, not a bundled-interpreter executable. [Build instructions](release/BUILD.md) cover native standalone builds and outstanding release gates. The [repository build workflow](../.github/workflows/livemap-build.yml) tests source compatibility and builds Windows, Linux and macOS packages with bundled Python. It takes effect only once these files are committed and pushed. It uploads build artifacts, not public releases; native DuckStation verification remains a separate gate.

## Release status

Local disc import, browser setup/cache/rendering and source-package launch have been exercised on macOS. The read-only DuckStation GDB backend also has prior live gameplay evidence. Python-free release builds and native Windows/Linux DuckStation launch-to-live lifecycle checks still need completion before a general release-ready claim. CI builds alone will not prove live emulator compatibility.

Keep tests and build tooling in the repository, not in runner archives. The distribution builder uses an explicit allowlist and excludes all game assets, private data and research.

## License and attribution

The parent repository's existing GNU GPL v3 license is retained verbatim in [LICENSE.txt](LICENSE.txt). FrogLord format-source MIT notices and other provenance are retained in [THIRD_PARTY.md](THIRD_PARTY.md). Game assets remain their owners' property and are generated locally, never shipped here.
