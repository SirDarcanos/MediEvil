# MediEvil LiveMap 0.4.0 — player guide

LiveMap opens a map in your browser and shows where Dan is while you play. It can follow him, show his movement direction, and display the level's items and exits.

**This is an unsigned preview.** Try it before using it in a timed run. Experimental BizHawk support has been user-tested successfully on Windows 11 with the latest BizHawk release.

## 1. What you need

- Your own **MediEvil USA game, SCUS-94227**, and the BIOS needed by your emulator.
- **DuckStation**, **PCSX-Redux**, or **BizHawk on Windows**. BizHawk's bridge targets version **2.11.1**, using its PlayStation core, **Octoshock**.
- A current web browser and at least **2 GiB of free space** for first-time setup.
- For making the maps: the game's **data-track BIN** (often called `Track 1.bin`) or an uncompressed, 2048-byte-sector **ISO**. CHD, other compressed images and other game revisions are not supported.

An emulator runs the game; LiveMap only reads its position. LiveMap does not include an emulator, BIOS, game, saves or maps. It creates the maps from your own game file.

## 2. Download and open LiveMap

Open the [LiveMap 0.4.0 download page](https://github.com/SirDarcanos/MediEvil/releases/tag/livemap-v0.4.0). Under **Assets**, choose the ZIP for your computer:

| Your computer | Download name | File to open after extracting |
| --- | --- | --- |
| Windows, x64 | `MediEvil-LiveMap-0.4.0-windows-x64.zip` | `MediEvilMinimap.exe` |
| Mac with Apple Silicon (M-series), using DuckStation | `MediEvil-LiveMap-0.4.0-macos-arm64.zip` | `Open Minimap.command` |
| Mac with Apple Silicon (M-series), using PCSX-Redux | Same Mac ZIP | `MediEvilMinimap` |
| Linux, x64 | `MediEvil-LiveMap-0.4.0-linux-x64.zip` | `MediEvilMinimap` or `open-minimap.sh` |

Intel Macs and other computer types do not have a ready-to-run download in this release. **Python is included** in the three platform ZIPs. GitHub's **Source code** downloads are for developers and need a separate Python installation.

1. Extract the **whole ZIP** into a new folder. Do not open the app from inside the ZIP.
2. Keep all its files together, including the `_internal` folder.
3. Open the file listed in the table. A browser page and a console or Terminal window may appear.
4. Keep the console or Terminal window open while using LiveMap.

The app uses a page on your own computer, normally `http://127.0.0.1:8768`. If the browser does not open, copy the address shown in the console into your browser.

### If your computer shows a security warning

These downloads are **unsigned**: Windows or macOS may not recognize their publisher. Download only from this repository's release page. Do not disable your computer's security protections to run them. If opening is blocked, report the exact warning and your operating system in the [issue tracker](https://github.com/SirDarcanos/MediEvil/issues).

## 3. Connect your emulator

Keep only the emulator you want to track open. Follow the section for that emulator; you do not need to configure all three.

### DuckStation on Windows or Linux

1. In DuckStation, open **Settings → Advanced** and enable **Show Debug Menu**.
2. Enable **Debugging → Export Shared Memory**. This lets LiveMap read the game's position.
3. Restart DuckStation, then load your game.
4. Open LiveMap using the Windows or Linux file listed above.

Run both apps under the same computer user account. Administrator access is not needed. Leave DuckStation's GDB server off for this connection.

### DuckStation on macOS

1. In DuckStation, enable **Settings → Advanced → Show Debug Menu**.
2. Enable **Debugging → Enable GDB Server**, using port **2345**. This is the connection LiveMap uses on Mac.
3. Load your game, then open **`Open Minimap.command`** from the extracted LiveMap folder.
4. **If DuckStation pauses when LiveMap connects, resume the game yourself.**

The Mac launcher is configured for DuckStation on port 2345. DuckStation may also change its pause state when LiveMap closes, so check the game afterward. This debugging connection may affect emulator debugging or achievement modes. LiveMap itself never sends pause, resume or memory-write commands.

### PCSX-Redux on Windows, Linux or macOS

1. Open PCSX-Redux and load your USA game.
2. Close other supported emulators so LiveMap can choose PCSX-Redux.
3. Open **`MediEvilMinimap.exe`** on Windows or **`MediEvilMinimap`** on Linux/Mac. On Linux, `open-minimap.sh` also works.

PCSX-Redux's normal shared-memory connection is detected automatically. It does not need the BizHawk script or DuckStation's GDB setting. Use a normal build that provides its standard RAM export.

**On Mac, do not use `Open Minimap.command` for PCSX-Redux:** that launcher selects DuckStation's debugging connection. Open `MediEvilMinimap` directly instead.

### BizHawk on Windows — experimental

This connection targets **BizHawk 2.11.1 with Octoshock**. The maintainer confirms it works on **Windows 11** with the latest BizHawk release. This is a user-reported gameplay test, not a report covering every script-lifecycle or performance scenario. Try your own setup before a timed run.

1. Open **one copy of EmuHawk**, BizHawk's main program, and load your USA game.
2. Open **Tools → Lua Console** in BizHawk. Lua is the scripting feature used to share Dan's position with LiveMap.
3. In the Lua Console, open **`bizhawk.lua`** from the **`web`** folder inside your extracted LiveMap folder. You can also save it using the **BizHawk Lua bridge** link on LiveMap's page.
4. Keep **one copy of the script running**. If you stop it, load/run it again to reconnect.
5. Open the **Windows** LiveMap app, `MediEvilMinimap.exe`.

Both apps must run under the same user in the **same Windows session**. If BizHawk is inside a Windows virtual machine, run Windows LiveMap inside that machine too. The Mac app cannot connect to BizHawk running inside Windows.

Only one EmuHawk instance can use this bridge at a time. Close extra instances rather than trying to select one. The script reads game memory and shares a small copy with LiveMap; it does not change the game, press buttons or advance frames. A stopped or stale connection hides Dan's marker.

BizHawk connections on macOS and Linux are not implemented. LiveMap does not install BizHawk, Lua, Windows or virtual-machine software for you.

## 4. First-time setup: create your maps

1. On LiveMap's setup page, choose your game's **data-track BIN** or supported **ISO**.
2. For a BIN/CUE game, choose the BIN containing game data, usually **Track 1**. Do not select the CUE file or an audio track in the browser.
3. Click **Extract my maps** and wait for it to finish. LiveMap checks the game revision and creates all **25 maps**, including their textures.
4. Enter a level in your emulator, or load your own save. The map can then show Dan.

Your game file goes only to LiveMap on **this computer**. It is not uploaded to an external website. LiveMap does not change your game file, BIOS, memory cards or saves. No special save or controller type is needed.

Next time, open LiveMap and your emulator. You do not need to select the game file again.

## 5. Use the map

- **Follow Dan** gently moves the map to catch up with Dan in either window; his marker stays at the reported position. Level changes, large jumps and reconnects recenter immediately. Drag the map to look elsewhere and turn off following. If your system requests reduced motion, following recenters without animation.
- **Pop out map** opens a resizable window with only the map, without toolbars, legends or coordinates. It starts with your current level selection, terrain, overlays and Follow Dan setting; later changes in either window stay separate. Mouse-wheel zoom, dragging and **F** to fit still work. Keep LiveMap running in its console; either browser window can be closed independently. If the window does not open, allow pop-ups for the local LiveMap site and try again.
- Use your mouse wheel or **+ / −** to zoom. Zooming in follow mode stays with Dan; after dragging, zoom is anchored at your mouse pointer. **Fit level** shows the whole level.
- The **green arrow** shows the direction Dan is moving, not where he is facing. It disappears when he stops, pauses or loses a fresh connection.
- Choose textured terrain, simple colours or height shading using the map's controls.
- Items, props and exits show positions stored in the level. **Items can remain shown after you collect them.** Hidden or conditional items may also appear; enemies and dropped items are not tracked.
- Exit areas do not tell you whether a gate or script is currently ready.
- The coordinate numbers are the game's X, Y and Z values. Tracking can continue outside the visible level; use **Follow Dan** to find the marker again.

After a reset, save-state load or level change, let LiveMap reconnect and check the level label. If it loses the connection, it hides Dan rather than showing an old position as live.

### Close LiveMap

On Windows, close LiveMap's console window. On Mac/Linux, press **Ctrl+C** in its console or Terminal window. Closing only the browser tab leaves LiveMap running. Your emulator stays open; with DuckStation's GDB connection, check whether the game has paused.

## 6. Upgrade or fix a problem

### Upgrade from an earlier preview

Close LiveMap, extract the new ZIP into a **new folder**, and open the new copy. Keep the old folder until you have checked the new version. Your saved maps live separately from the app, so existing maps normally load without another import. Use the **new bundled script** for BizHawk.

### The map cannot find Dan

- Check that the game is **MediEvil USA, SCUS-94227**, and enter a level. Menus and loading screens may have no position to show.
- Check the instructions for your emulator above. DuckStation needs a restart after enabling shared memory; BizHawk needs its script running.
- Close other supported emulators. For BizHawk, keep one EmuHawk instance and one script.
- Keep the LiveMap console open, then reload the browser page.
- If you use a sandboxed emulator package on Windows/Linux, it may hide the shared-memory connection. Try a normal installation under the same user account.

### LiveMap says its address is already in use

An older copy may still be running. Close that copy, or use the browser address it printed. Advanced users can start LiveMap with `--port 0` to choose a free local port; see the command examples below.

### Find your saved maps

LiveMap stores generated maps in its own app-data folder:

| System | Folder | How to open it |
| --- | --- | --- |
| Windows | `%LOCALAPPDATA%\MediEvilMinimap` | Paste this path into File Explorer's address bar. |
| macOS | `~/Library/Application Support/MediEvilMinimap` | In Finder, choose **Go → Go to Folder** and paste the path. |
| Linux | `$XDG_DATA_HOME/medievil-minimap`, or `~/.local/share/medievil-minimap` when that variable is not set | Open the location in your file manager. |

These files contain data from your game. Keep them private; do not redistribute them. Temporary import copies are removed after a normal success or failure. Force-quitting during import can leave temporary files in this app-data folder.

### Rebuild damaged maps without losing the old copy

If LiveMap reports a missing or invalid map file:

1. Close **only LiveMap**.
2. Open its app-data folder using the table above.
3. Rename **only the `maps` folder** to a new, unused name, such as `maps.backup-1`. Keep that backup.
4. Reopen LiveMap. First-time setup returns; select your own game file again.

Leave your emulator, game, BIOS and save folders alone. Changing the connection port will not repair maps. LiveMap deliberately does not overwrite an existing map cache, so `--import-game` is not a shortcut for this repair.

### Optional: commands and source downloads

Most players can use the platform ZIPs without typing commands. The source edition needs **Python 3.10 or newer** and no extra Python packages.

Open a terminal in the extracted app folder. With a standalone download, use `.\MediEvilMinimap.exe` on Windows or `./MediEvilMinimap` on Mac/Linux in place of `python3 runner.py` below. With Windows source, use `py -3 runner.py`.

```sh
# Choose an emulator explicitly:
python3 runner.py --emulator duckstation --open
python3 runner.py --emulator redux --open
python3 runner.py --emulator bizhawk --open

# DuckStation on Mac, or an explicitly configured GDB connection:
python3 runner.py --gdb-port 2345 --open

# Choose a free browser address:
python3 runner.py --port 0 --open

# Import a CUE file directly instead of selecting a BIN in the browser:
python3 runner.py --import-game "/path/to/game.cue" --open
```

For DuckStation on Mac, include `--gdb-port 2345` when combining options, or use your configured GDB port instead. Do not combine `--gdb-port` with Redux or BizHawk. `--pid NUMBER` can select a DuckStation/Redux process, but cannot select among multiple BizHawk instances and cannot be combined with GDB.

CUE references must stay inside the CUE's folder; nonstandard pregaps are unsupported. Older DuckStation builds may need `[Hacks] ExportSharedMemory = true` in their existing settings file; back it up before editing. Prefer the menu setting when available.

## 7. What this preview does and does not verify

Build and startup checks can show that the app opens and includes its files. They do **not** prove that every emulator version works during gameplay. See the [0.4.0 release notes](https://github.com/SirDarcanos/MediEvil/releases/tag/livemap-v0.4.0) for the checks performed on these downloads.

Actual Windows/Linux DuckStation gameplay and lifecycle testing remains outstanding. The maintainer reports successful BizHawk gameplay on Windows 11 with the latest BizHawk release. Individual Lua-script lifecycle scenarios and performance checks have not been reported. Earlier Mac DuckStation gameplay observations are historical, not a fresh test of 0.4.0.

The map-only window and smoother following were checked with a real, isolated macOS PCSX-Redux instance, a copied Crypt save-state and scripted controller-only walking. These checks used live read-only tracking and the browser's textured renderer; they do not establish other emulator/OS combinations, full save-state/level-transition lifecycle coverage or performance on other hardware.

LiveMap does not send controller input, patch game memory, change emulator settings or write saves. It has no telemetry reporting or external game-file upload. The downloads contain no emulator, BIOS, disc, extracted game assets, saves or RAM dumps. License and attribution notices are in the included `LICENSE.txt` and `THIRD_PARTY.md` files.
