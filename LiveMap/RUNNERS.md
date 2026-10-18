# MediEvil live minimap — v1

A textured top-down map with Dan’s live position, raw XYZ coordinates, items, static props and authored exits. Follow, pan and zoom work outside the normal level bounds, including native coordinate wraps.

**Bring your own DuckStation, BIOS and MediEvil USA (SCUS-94227).** No game data or saves are supplied. The minimap never controls the game, patches RAM, changes DuckStation settings or writes save slots. There is no controller automation, telemetry reporting or external upload.

## Open the minimap

Unzip the **whole folder** somewhere you can run it. Do not launch files inside the ZIP.

- **Windows:** double-click `Open Minimap.cmd`.
- **macOS:** open `Open Minimap.command`.
- **Linux:** run `./open-minimap.sh`.

The **source ZIP requires Python 3.10 or newer**, from python.org or your package manager. It needs no Python packages. A standalone build includes Python; do not confuse the source ZIP with a standalone executable.

Keep the launcher window open while using the map. The browser opens at `http://127.0.0.1:8768`. Close the minimap with Ctrl-C in its launcher window. DuckStation stays open, although GDB disconnects can affect its pause state.

## Configure DuckStation

### Windows and Linux — preferred non-pausing connection

In DuckStation, enable **Settings → Advanced → Show Debug Menu**, then **Debugging → Export Shared Memory**. Restart DuckStation and load your game. Use the same OS user for the emulator and minimap; no administrator access is needed.

Older builds may need `[Hacks] ExportSharedMemory = true` in their existing settings file. Back it up before editing. Do not enable GDB for the normal Windows/Linux connection.

### macOS — explicit GDB fallback

Enable **Show Debug Menu**, then **Debugging → Enable GDB Server**, port **2345**. The Mac launcher uses that port. **DuckStation may pause when the map connects: resume it manually.** The map sends memory reads and acknowledgements only, never pause/resume, step, breakpoint or write commands. DuckStation can also change pause state on disconnect; check the game after closing the map. GDB may affect emulator debugging/achievement modes.

For a different configured port, run `python3 runner.py --gdb-port 3456 --open` (or use the standalone executable with those arguments).

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

- Start DuckStation and enter a level; menus/loading screens may have no Dan actor.
- Check the USA revision and connection setting above. Shared memory requires an emulator restart after enabling it.
- Windows/Linux sandboxed emulator installs may hide the export. Use a normal installation or an explicitly configured GDB fallback.
- If several supported emulators are open, close the extras or use `--emulator duckstation --pid NUMBER` (not with GDB).
- If port 8768 is occupied, add `--port 0` to choose an available local port, or open an already-running copy’s browser address.
- If the browser lost its connection, keep the launcher open and reload the page.

### Recover a damaged map cache

If startup reports a missing/invalid map manifest or map file, changing the port will not fix it. Close **only the minimap**, then open its app-data folder listed above. Rename **only its generated `maps` folder** to a new name such as `maps.backup-2026-10-18` (choose a name that does not already exist). Leave the backup, your game image, BIOS, DuckStation folders and save files alone.

Open the minimap again. With `maps` absent, first-time setup returns; select your own disc image to rebuild. The old generated maps stay preserved in the renamed folder. Do not try `--import-game` to overwrite a broken cache: v1 deliberately preserves an existing cache instead of replacing it.

## Current validation limits

This is a **runner preview**, not a claim that every OS/emulator version has been certified. Actual macOS DuckStation read-only tracking and a natural Crystal Caves full-loop/landing were demonstrated locally. Windows mapping calls have automated contract coverage, but **native Windows and Linux DuckStation end-to-end verification is still required**. A source ZIP is not proof of a tested standalone build. Do a smoke run on your exact emulator/build before relying on it in a timed run.

No emulator, BIOS, disc, extracted game assets, savestates, RAM dumps, research scripts or tests are included in the runner package. See `THIRD_PARTY.md` for format-source notices.
