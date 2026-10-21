# MediEvil LiveMap

LiveMap is a companion map for **MediEvil USA (SCUS-94227)**. It opens in your browser, follows Dan as you play, and shows the level's terrain, items and exits. A green arrow shows his movement direction.

## Download and start

[**Download LiveMap 0.3.0 — unsigned preview**](https://github.com/SirDarcanos/MediEvil/releases/tag/livemap-v0.3.0)

Choose **Windows x64**, **Mac Apple Silicon (ARM64)** or **Linux x64**. These downloads include Python, so you do not need to install it separately. Extract the whole ZIP and keep its files together.

- **Windows:** open `MediEvilMinimap.exe`.
- **Mac with DuckStation:** open `Open Minimap.command`.
- **Mac with PCSX-Redux:** open `MediEvilMinimap` directly.
- **Linux:** open `MediEvilMinimap` or `open-minimap.sh`.

You provide your own emulator, BIOS and game. On first launch, select your game's data-track BIN or supported ISO to create all 25 maps on your computer. Your game file and saves stay unchanged.

[**Player guide: setup, controls, upgrades and troubleshooting**](RUNNERS.md)

## Choose your emulator

| Emulator | Connection | Instructions |
| --- | --- | --- |
| DuckStation | Shared memory on Windows/Linux; local GDB connection on Mac | [Set up DuckStation](RUNNERS.md#duckstation-on-windows-or-linux) |
| PCSX-Redux | Automatic detection of its normal RAM export | [Set up PCSX-Redux](RUNNERS.md#pcsx-redux-on-windows-linux-or-macos) |
| BizHawk | Experimental Windows-only script, targeting 2.11.1 / Octoshock | [Set up BizHawk](RUNNERS.md#bizhawk-on-windows--experimental) |

**Preview limits:** these apps are unsigned and may trigger security warnings. Actual Windows/Linux DuckStation gameplay and BizHawk's Windows gameplay/script behavior remain unverified. Build/startup checks are not gameplay tests. Try your setup before a timed run, and keep your computer's security protections enabled.

Items and exits show positions stored in the level, not live collection or gate status. LiveMap reads the game without controlling it; no game assets, emulator, BIOS or saves are supplied.

## For developers

- [Run from source, code layout and bridge details](DEVELOPMENT.md)
- [Build packages and check release readiness](release/BUILD.md)

This folder is the maintained LiveMap project. Generated game data and private research outputs do not belong in the repository or its downloads.

## License and attribution

LiveMap retains the repository's [GNU GPL v3 license](LICENSE.txt). [Third-party notices](THIRD_PARTY.md) record format-source attribution. Game assets belong to their owners and are generated locally, not distributed here.
