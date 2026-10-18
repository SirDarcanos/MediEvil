# MediEvil LiveMap

A standalone companion minimap for runners using their own DuckStation, BIOS, USA game and saves. On first launch it extracts all 25 textured maps from the runner's own supported disc image into local app-data storage. It reads live RAM without controlling or patching the game.

**This folder is the maintained project location.** No extracted game assets, emulator, BIOS, savestates, RAM dumps or controller-automation research belong in this repository or its downloads.

## Download for runners

[**Download the LiveMap preview**](https://github.com/SirDarcanos/MediEvil/releases/tag/livemap-v0.1.0-preview.1) — Windows x64, macOS Apple Silicon/ARM64 and Linux x64. Native downloads bundle Python; no separate Python installation or commands are needed.

Unzip the entire folder, then double-click **`MediEvilMinimap.exe`** on Windows or **`Open Minimap.command`** on Mac. On Linux, open `MediEvilMinimap`. The browser setup page guides you through importing your own game. Keep `_internal` beside the executable. See the [runner guide](RUNNERS.md) for DuckStation configuration and security/preview caveats.

This is an explicitly **preview** release: native builds/startup checks passed and Mac has a user smoke-test report; actual Windows/Linux DuckStation gameplay and lifecycle checks remain unverified. No game assets, BIOS or saves are distributed.

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

[Native CI run 39139164216](https://github.com/SirDarcanos/MediEvil/actions/runs/39139164216) produced bundled-Python Windows x64, Linux x64 and macOS ARM64 packages, with successful native tests and frozen-startup/resource checks. Python 3.10 and 3.14 source checks also passed. The initial `a8e54aa` Mac candidate (the subsequent fix changed archive metadata only, not runtime code) additionally imported the local USA disc, rendered its textures and reopened its cache without an image argument. The read-only DuckStation GDB backend has prior live gameplay evidence.

These are unsigned preview releases, not universally validated stable releases. Actual Windows/Linux DuckStation gameplay and lifecycle checks, signing/notarization decisions and maintainer approval remain before a general release-ready claim. CI startup checks do not prove live emulator compatibility.

Keep tests and build tooling in the repository, not in runner archives. The distribution builder uses an explicit allowlist and excludes all game assets, private data and research.

## License and attribution

The parent repository's existing GNU GPL v3 license is retained verbatim in [LICENSE.txt](LICENSE.txt). FrogLord format-source MIT notices and other provenance are retained in [THIRD_PARTY.md](THIRD_PARTY.md). Game assets remain their owners' property and are generated locally, never shipped here.
