# MediEvil live minimap — v1

A textured top-down map with Dan’s live position, raw XYZ coordinates, items, static props and authored exits. Follow, pan and zoom work outside the normal level bounds, including native coordinate wraps.

**Bring your own supported emulator, BIOS and MediEvil USA (SCUS-94227).** DuckStation and PCSX-Redux routes are retained; Windows BizHawk support is experimental. No game data or saves are supplied. The minimap never controls the game, patches RAM, changes DuckStation settings or writes save slots. There is no controller automation, telemetry reporting or external upload.

## Download and open — no commands to type

Get a native package from the [LiveMap preview release](https://github.com/SirDarcanos/MediEvil/releases/tag/livemap-v0.2.0). Choose **Windows x64**, **macOS Apple Silicon/ARM64**, or **Linux x64**. These packages include Python; you do **not** install Python or any Python packages. Intel Macs and other architectures are not supplied in this preview.

1. Download the ZIP for your OS, not GitHub's automatic **Source code** download.
2. Unzip the **whole folder**. Do not run files inside the ZIP, or move the executable away from its `_internal` folder.
3. Start the minimap:
   - **Windows:** double-click **`MediEvilMinimap.exe`**. `Open Minimap.cmd` is an alternative.
   - **macOS:** double-click **`Open Minimap.command`**. A Terminal window appears automatically; you do not type commands.
   - **Linux:** open **`MediEvilMinimap`**, or use `open-minimap.sh`.
4. Your browser opens the map/setup page. Keep any launcher/console window open while using it.

The default address is `http://127.0.0.1:8768`. On Windows, close the minimap's console window to quit. On Mac/Linux, Ctrl-C in its launcher window stops it. Closing only the browser tab does not stop the local map process. DuckStation stays open, although GDB disconnects can affect its pause state.

**Unsigned preview:** your OS may show a publisher/security warning. Do not disable OS security protections; report the exact warning if the download is blocked.

### Source edition (optional)

The separately named **source ZIP requires Python 3.10+**, from python.org or your package manager. It needs no Python packages. Its OS launchers are `Open Minimap.cmd`, `Open Minimap.command` and `open-minimap.sh`. Most runners should use a native download above instead.

## Configure DuckStation

### Windows and Linux — preferred non-pausing connection

In DuckStation, enable **Settings → Advanced → Show Debug Menu**, then **Debugging → Export Shared Memory**. Restart DuckStation and load your game. Use the same OS user for the emulator and minimap; no administrator access is needed.

Older builds may need `[Hacks] ExportSharedMemory = true` in their existing settings file. Back it up before editing. Do not enable GDB for the normal Windows/Linux connection.

### macOS — explicit GDB fallback

Enable **Show Debug Menu**, then **Debugging → Enable GDB Server**, port **2345**. The Mac launcher uses that port. **DuckStation may pause when the map connects: resume it manually.** The map sends memory reads and acknowledgements only, never pause/resume, step, breakpoint or write commands. DuckStation can also change pause state on disconnect; check the game after closing the map. GDB may affect emulator debugging/achievement modes.

For a different configured port, run `python3 runner.py --gdb-port 3456 --open` (or use the standalone executable with those arguments).

## Configure Windows BizHawk (experimental)

This new source-tree integration targets **BizHawk 2.11.1 / PS1 Octoshock**. It is not included in the previously published 0.2.0 downloads. **Native BizHawk/NLua and Windows gameplay verification are pending.**

1. Run Windows LiveMap **inside the same Windows session or UTM guest as BizHawk**, under the same OS user. The Mac app cannot open a Windows VM's named mappings.
2. Keep one EmuHawk instance open and load your own USA game.
3. In **Tools → Lua Console**, open `web/bizhawk.lua` from the LiveMap folder. Alternatively download it using LiveMap's **BizHawk Lua bridge** link. Keep only one copy of this script running.
4. Open LiveMap normally. The runner now defaults to auto-detection. For explicit source selection use `python3 runner.py --emulator bizhawk --open`; existing `--emulator duckstation` and `--emulator redux` selections still work.

The Lua script reads only small ranges of the `MainRAM` domain. It publishes a 512-byte host mapping using BizHawk's native communication API; it never writes game RAM, presses buttons, advances frames or pauses/resumes emulation. LiveMap opens that existing mapping read-only. Paused scripts keep a heartbeat; stopped, stale or malformed exports hide Dan rather than retaining a false live position. You must observe a producer update before a newly opened bridge is admitted.

Because this bridge is shared, multiple EmuHawk processes are refused even when `--pid` is supplied. Close the extras instead. If the script is stopped, reload it in the Lua Console. On unsupported cores/domains it exports an inactive status. No BizHawk, BIOS, Windows, UTM or Lua dependency is installed automatically. Other BizHawk platforms are not implemented.

### PCSX-Redux

Use a normal PCSX-Redux build with its standard named RAM export. Auto-detection or `--emulator redux` selects it without a Lua script or debugger. When several supported emulators are open, close the others or select a backend explicitly. The Mac DuckStation launcher still requests its existing GDB fallback; use the Redux source invocation/executable without `--gdb-port` for Redux.

## First launch: make your maps

1. In the setup page, select your game’s **data-track BIN** (usually `Track 1.bin`) or a 2048-byte **ISO**.
2. Click **Extract my maps**. The file goes only to the local `127.0.0.1` server. The app checks the USA executable revision, extracts geometry and original textures, and caches all 25 maps.
3. Once extraction finishes, the map opens. Enter a level or load **your own** save; Dan appears automatically. No special savestate or controller type is required.

For BIN/CUE games, choose the data BIN—not the CUE text file or audio BIN. To import a CUE directly without browser upload, run `python3 runner.py --import-game "/path/to/game.cue" --open`. CUE paths must stay inside its folder. CHD, compressed images, nonstandard pregaps and other game revisions are not supported in v1; use a supported data track instead. Keep at least 2 GiB free for temporary import work and generated maps. Temporary source files are removed when an import completes or fails normally; a forcibly killed process may leave temporary files in its cache.

Next time, just open the minimap. You do not select the image again.

Generated game assets stay on your machine:

- Windows: `%LOCALAPPDATA%\MediEvilMinimap`
- macOS: `~/Library/Application Support/MediEvilMinimap`
- Linux: `$XDG_DATA_HOME/medievil-minimap` or `~/.local/share/medievil-minimap`

Do not redistribute your generated cache. Nothing is written beside your disc, BIOS, memory cards or saves.

## During a run

Choose **Follow Dan** to keep the marker centered. Use the wheel or +/− to zoom, drag to pan, and **Fit level** to see the whole map. Textured terrain is the default; simple colours and height shading are alternatives. A neutral circle marks Dan; no copyrighted portrait is bundled.

Items and props show **authored static placements**, not collected-item or enemy tracking. Exit areas do not tell you whether a gate/script is ready. Map coordinates remain raw rather than being clamped to the level.

If the connection disappears, the marker is hidden rather than presented as live. Pause/reset/state-load/restart behavior depends on the emulator; let the map reconnect, then check the level label.

## If it does not connect

- Start your selected emulator and enter a level; menus/loading screens may have no Dan actor. For BizHawk, keep the bundled Lua bridge running.
- Check the USA revision and connection setting above. Shared memory requires an emulator restart after enabling it.
- Windows/Linux sandboxed emulator installs may hide the export. Use a normal installation or an explicitly configured GDB fallback.
- If several supported emulators are open, close the extras or use `--emulator duckstation --pid NUMBER` (not with GDB).
- If port 8768 is occupied, add `--port 0` to choose an available local port, or open an already-running copy’s browser address.
- If the browser lost its connection, keep the launcher open and reload the page.

### Recover a damaged map cache

If startup reports a missing/invalid map manifest or map file, changing the port will not fix it. Close **only the minimap**, then open its app-data folder listed above. Rename **only its generated `maps` folder** to a new name such as `maps.backup-2026-10-18` (choose a name that does not already exist). Leave the backup, your game image, BIOS, DuckStation folders and save files alone.

Open the minimap again. With `maps` absent, first-time setup returns; select your own disc image to rebuild. The old generated maps stay preserved in the renamed folder. Do not try `--import-game` to overwrite a broken cache: v1 deliberately preserves an existing cache instead of replacing it.

## Current validation limits

These are **unsigned runner-preview candidates**, not a claim that every OS/emulator version has been certified. Bundled-Python Windows x64, Linux x64 and macOS ARM64 builds passed native tests and frozen startup/resource checks in [CI run 39139164216](https://github.com/SirDarcanos/MediEvil/actions/runs/39139164216). The initial Mac candidate (same runtime code as the archive-permission repair) also completed local disc extraction, textured rendering and cached restart. Actual macOS DuckStation read-only tracking and a natural Crystal Caves full-loop/landing were demonstrated separately. **Actual Windows/Linux DuckStation gameplay and lifecycle verification is still required.** A source ZIP still requires Python; choose the matching native package to avoid that requirement. Do a smoke run on your exact emulator/build before relying on it in a timed run.

No emulator, BIOS, disc, extracted game assets, savestates, RAM dumps, research scripts or tests are included in the runner package. See `THIRD_PARTY.md` for format-source notices.
