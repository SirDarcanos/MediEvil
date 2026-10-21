# MediEvil LiveMap

A standalone companion minimap for runners using their own DuckStation or PCSX-Redux, BIOS, USA game and saves. Experimental Windows BizHawk support uses the bundled read-only Lua bridge. On first launch it extracts all 25 textured maps from the runner's own supported disc image into local app-data storage. It reads live RAM without controlling or patching the game.

**This folder is the maintained project location.** No extracted game assets, emulator, BIOS, savestates, RAM dumps or controller-automation research belong in this repository or its downloads.

## Download for runners

[**Download LiveMap 0.2.0 (unsigned preview)**](https://github.com/SirDarcanos/MediEvil/releases/tag/livemap-v0.2.0) — choose the individually named Windows x64, macOS Apple Silicon/ARM64 or Linux x64 ZIP. Native downloads bundle Python; no separate Python installation or commands are needed.

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

## BizHawk on Windows (experimental)

This unreleased source change is **not included in the published 0.2.0 binaries**. Target: BizHawk 2.11.1, PS1/Octoshock, MediEvil USA. Native BizHawk/NLua and Windows gameplay verification are still pending; local synthetic checks are not a substitute.

1. Run BizHawk and LiveMap in the **same Windows session/VM**, under the same user. Keep **one EmuHawk instance and one bridge script** open.
2. Load your game in BizHawk. Open **Tools → Lua Console**, then load `web/bizhawk.lua` from the app folder, or use the **BizHawk Lua bridge** download link in LiveMap.
3. Keep the script running. LiveMap now auto-detects supported emulators; `--emulator bizhawk` selects BizHawk explicitly. Multiple BizHawk instances are deliberately refused even with `--pid` because the exporter uses a shared named bridge.

The bridge reads a few PS1 RAM ranges and writes only a small host mapping. It never patches game RAM, sends controller input, advances frames, or pauses/resumes the game. It keeps a heartbeat while paused; stale/stopped exports hide the marker. No HTTP bridge, process-memory scanning, extra Python package, or BizHawk installation is performed by LiveMap. macOS/Linux BizHawk support is not implemented; their existing Redux/DuckStation routes remain available.

### Bridge contract and Windows test gate

The API reference is BizHawk **2.11.1**, commit `bdddf4a58aa1a022afb11dc73294a81a5aa7bbd5`: [named mapping writes](https://github.com/TASEmulators/BizHawk/blob/bdddf4a58aa1a022afb11dc73294a81a5aa7bbd5/src/BizHawk.Client.Common/Api/MemoryMappedFiles.cs), [Lua communication](https://github.com/TASEmulators/BizHawk/blob/bdddf4a58aa1a022afb11dc73294a81a5aa7bbd5/src/BizHawk.Client.Common/lua/CommonLibs/CommLuaLibrary.cs), [PS1 MainRAM domain](https://github.com/TASEmulators/BizHawk/blob/bdddf4a58aa1a022afb11dc73294a81a5aa7bbd5/src/BizHawk.Emulation.Cores/Consoles/Sony/PSX/Octoshock.IDebuggable.cs), and [cooperative scheduling while paused](https://github.com/TASEmulators/BizHawk/blob/bdddf4a58aa1a022afb11dc73294a81a5aa7bbd5/src/BizHawk.Client.Common/lua/CommonLibs/EmulationLuaLibrary.cs). No upstream implementation code is bundled.

The `MediEvilLiveMap-BizHawk-v1` mapping is 512 bytes: a 32-byte `<4s7I` little-endian header (`MLBH`, version, sequence, Unix seconds, running/paused/inactive status, segment count, two reserved zeros), followed by address/length-prefixed RAM bytes and zero padding. The exporter marks the mapping busy before copying, then publishes an even sequence; Python checks the header around its copy and reconstructs a sparse 2 MiB buffer for the existing USA decoder. It requires a producer advance and checks wall-clock plus monotonic freshness. RAM patches and emulator-control APIs are not part of this protocol.

Before accepting native support in the Windows VM, check real movement/arrow direction and signed XYZ; pause/resume with a live exporter heartbeat; stop/restart the Lua script; save-state and cross-level loads; emulator restart; wrong game/revision; and refusal of multiple EmuHawk instances. Confirm the app and emulator run in the same Windows guest. Synthetic mappings and Lua API mocks do not establish these outcomes.

## Movement arrow

A green arrow ahead of Dan shows his observed horizontal movement, not the direction he is facing. It uses screen-space sizing while zooming, becomes a compact chevron near the viewport edge without moving Dan’s marker, and disappears when he stops, pauses, disconnects, or the movement sample becomes stale. Recorded snapshots show no movement arrow. Level/session changes and large position jumps reset its history.

## Build and check

```sh
python3 -m unittest discover -s . -p 'test_*.py'
node --test web/test_*.cjs
for script in web/*.js; do node --check "$script"; done
python3 release/build.py --output dist
```

The default build is a **Python-required source preview**, not a bundled-interpreter executable. [Build instructions](release/BUILD.md) cover native standalone builds and outstanding release gates. The [repository build workflow](../.github/workflows/livemap-build.yml) tests source compatibility and builds Windows, Linux and macOS packages with bundled Python. It takes effect only once these files are committed and pushed. It uploads build artifacts, not public releases; native DuckStation verification remains a separate gate.

## Code layout

- `runner.py`: runner startup, cache/setup state and CLI; `app.py`: direct map/snapshot CLI.
- `feed.py`: background sampling and stale-state handling. `ram.py`, `emulator_memory.py` and `gdb_reader.py` own decoding and emulator transports.
- `local_http.py`: map/setup routes, loopback origin checks, upload protection and response policies.
- `disc_import.py` and `extract_maps.py`: disc import and extraction orchestration. `binary.py` supplies shared bounds checks; `vlo.py` decodes texture records for both `appearance.py` colour means and `textures.py` atlases. The remaining format modules handle props, exits and thin-face visibility.
- `web/app.js`: map loading, controls and overlays. `movement.js` owns movement history/expiry; `terrain.js` renders WebGL textures; `raster.js` handles Canvas fallbacks and shared shading. `setup.js` drives disc import.
- `test_*.py` and `web/test_*.cjs`: synthetic regression checks. `release/build.py` explicitly lists runtime files; add new runtime modules there as well as to the HTTP/page script lists when applicable.

These checks do not replace own-disc extraction, browser/GPU or native emulator verification.

## Release status

[Native CI run 39377444367](https://github.com/SirDarcanos/MediEvil/actions/runs/39377444367), at runtime commit `4f2c7d70c5befa68b27b9a1c19a1f18533f43a2d`, produced the 0.2.0 bundled-Python Windows x64, Linux x64 and macOS ARM64 packages, with successful native tests and frozen-startup/resource checks. Python 3.10 and 3.14 source checks also passed. Downloaded archive checksums, required notices and packaged frontend code were verified. Release asset names are clearer; ZIP contents remain the exact CI artifacts. The release tag also includes documentation-only release updates, with runtime/build inputs unchanged.

Earlier Mac preview evidence includes own-disc import, textured rendering, cached restart and read-only DuckStation GDB gameplay; those observations are not a fresh 0.2.0 native-gameplay certification.

These are unsigned preview releases, not universally validated stable releases. Actual Windows/Linux DuckStation gameplay and lifecycle checks, signing/notarization decisions and maintainer approval remain before a general release-ready claim. CI startup checks do not prove live emulator compatibility.

Keep tests and build tooling in the repository, not in runner archives. The distribution builder uses an explicit allowlist and excludes all game assets, private data and research.

## License and attribution

The parent repository's existing GNU GPL v3 license is retained verbatim in [LICENSE.txt](LICENSE.txt). FrogLord format-source MIT notices and other provenance are retained in [THIRD_PARTY.md](THIRD_PARTY.md). Game assets remain their owners' property and are generated locally, never shipped here.
