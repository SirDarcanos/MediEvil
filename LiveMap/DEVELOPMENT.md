# LiveMap development reference

For download and emulator setup instructions, use the [player guide](RUNNERS.md). This page covers running the code, its layout and the experimental BizHawk protocol.

## Run from source

Use Python 3.10 or newer and a current browser. The runtime uses Python's standard library; no extra Python packages are needed.

From the repository's `LiveMap/` directory:

```sh
python3 runner.py --open
```

The runner auto-detects supported emulators. To select one, add `--emulator duckstation`, `--emulator redux` or `--emulator bizhawk`. BizHawk is Windows-only and requires the bundled script running in the same session.

For DuckStation on macOS, explicitly select the read-only GDB connection:

```sh
python3 runner.py --gdb-port 2345 --open
```

Use the port configured in DuckStation. Attachment may pause the emulator; resume it manually. Disconnect may also affect its pause state. Redux and BizHawk do not use this GDB option.

On Windows source installations, use `py -3` in place of `python3`. The [player guide's optional commands](RUNNERS.md#optional-commands-and-source-downloads) cover direct CUE import, ports and process selection.

## Local checks

Run from `LiveMap/`:

```sh
python3 -m unittest discover -s . -p 'test_*.py'
node --test web/test_*.cjs
for script in web/*.js; do node --check "$script"; done
```

Tests use synthetic fixtures unless explicitly identified otherwise. They do not establish real emulator gameplay, GPU rendering or own-disc extraction. The CI workflow also builds native packages and checks startup; see [packaging](release/BUILD.md).

## Code layout

- `runner.py`: runner startup, cache/setup state and CLI; `app.py`: direct map/snapshot CLI.
- `feed.py`: background sampling and stale-state handling. `ram.py`, `emulator_memory.py`, `gdb_reader.py` and `bizhawk.py` own decoding and emulator transports.
- `local_http.py`: map/setup routes, loopback origin checks, upload protection and response policies.
- `disc_import.py` and `extract_maps.py`: disc import and extraction orchestration. `binary.py` supplies shared bounds checks; `vlo.py` decodes texture records for both `appearance.py` colour means and `textures.py` atlases. The remaining format modules handle props, exits and thin-face visibility.
- `web/app.js`: map loading, controls and overlays. `movement.js` owns movement history/expiry; `terrain.js` renders WebGL textures; `raster.js` handles Canvas fallbacks and shared shading. `setup.js` drives disc import.
- `test_*.py` and `web/test_*.cjs`: synthetic regression checks. `release/build.py` explicitly lists runtime files; add new runtime modules there as well as to the HTTP/page script lists when applicable.

These checks do not replace own-disc extraction, browser/GPU or native emulator verification.


## Experimental BizHawk bridge

The target is BizHawk 2.11.1 with PS1/Octoshock on Windows. The Lua script reads explicit `MainRAM` ranges and writes only a host mapping, never game RAM or controller input. Python opens the existing mapping read-only. No process-memory scan, HTTP bridge or extra runtime package is involved.

The mapping name is shared, so one EmuHawk instance and one script must be used. `--pid` cannot disambiguate several BizHawk instances. The reader checks producer identity around reads, requires observed producer advancement and rejects stale or torn exports.

The API reference is BizHawk **2.11.1**, commit `bdddf4a58aa1a022afb11dc73294a81a5aa7bbd5`: [named mapping writes](https://github.com/TASEmulators/BizHawk/blob/bdddf4a58aa1a022afb11dc73294a81a5aa7bbd5/src/BizHawk.Client.Common/Api/MemoryMappedFiles.cs), [Lua communication](https://github.com/TASEmulators/BizHawk/blob/bdddf4a58aa1a022afb11dc73294a81a5aa7bbd5/src/BizHawk.Client.Common/lua/CommonLibs/CommLuaLibrary.cs), [PS1 MainRAM domain](https://github.com/TASEmulators/BizHawk/blob/bdddf4a58aa1a022afb11dc73294a81a5aa7bbd5/src/BizHawk.Emulation.Cores/Consoles/Sony/PSX/Octoshock.IDebuggable.cs), and [cooperative scheduling while paused](https://github.com/TASEmulators/BizHawk/blob/bdddf4a58aa1a022afb11dc73294a81a5aa7bbd5/src/BizHawk.Client.Common/lua/CommonLibs/EmulationLuaLibrary.cs). No upstream implementation code is bundled.

The `MediEvilLiveMap-BizHawk-v1` mapping is 512 bytes: a 32-byte `<4s7I` little-endian header (`MLBH`, version, sequence, Unix seconds, running/paused/inactive status, segment count, two reserved zeros), followed by address/length-prefixed RAM bytes and zero padding. The exporter marks the mapping busy before copying, then publishes an even sequence; Python checks the header around its copy and reconstructs a sparse 2 MiB buffer for the existing USA decoder. It requires a producer advance and checks wall-clock plus monotonic freshness. RAM patches and emulator-control APIs are not part of this protocol.

Before accepting native support in the Windows VM, check real movement/arrow direction and signed XYZ; pause/resume with a live exporter heartbeat; stop/restart the Lua script; save-state and cross-level loads; emulator restart; wrong game/revision; and refusal of multiple EmuHawk instances. Confirm the app and emulator run in the same Windows guest. Synthetic mappings and Lua API mocks do not establish these outcomes.


## Movement display

The arrow represents observed horizontal movement, not facing. Its screen-space size stays consistent while zooming. Near the viewport edge it becomes a compact chevron without moving Dan's marker. It hides when stationary, paused, disconnected or stale, and is absent for recorded snapshots. Level/session changes and large jumps reset movement history.

## Verification history and release boundaries

Earlier Mac previews had own-disc import, textured rendering, cached restart and read-only DuckStation GDB gameplay observations. Those are historical observations, not fresh 0.3.0 gameplay certification.

Actual Windows/Linux DuckStation gameplay and lifecycle checks remain outstanding. Native BizHawk/NLua gameplay, script lifecycle, Windows mappings and performance remain unverified. Existing PCSX-Redux transport code is not evidence of a fresh cross-platform gameplay test. Keep these limits visible when publishing previews.

The release tag identifies the version; do not invent a separate package-version source. Public releases need maintainer approval. Keep the matching full repository source/build scripts available under the repository license, retain third-party notices and distribute no game data.
