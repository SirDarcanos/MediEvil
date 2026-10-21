# MediSplit — Any%

[`MediSplit.asl`](MediSplit.asl) is a directly editable Any%-only autosplitter for MediEvil USA. It has **17 fixed splits** and only three custom settings.

**Development build:** actual LiveSplit compilation, emulator compatibility and gameplay timing remain unverified. Runtime testing is left to the maintainer.

## Setup

1. Select `MediSplit.asl` in LiveSplit's **Scriptable Auto Splitter** component.
2. Configure your run with the 17 segments below. Names are your choice; the script does not inspect segment or category names.
3. Enable the component's start/split controls and the script options you want.
4. Load the script before starting an attempt and run one matching emulator/game instance.

There is no generator, companion source, custom DLL or emu-help requirement for this script. Edit the ASL directly.

## Three settings

All default on:

- **Autostart:** start on the game's accepted New Game request, not merely entering Dan's Crypt or loading a save.
- **Autosplit:** split the 14 level completions, Fazguls and Kardok.
- **Autoend:** split Zarok's native death as the final segment, independently of Autosplit.

There is **no automatic reset**. Reset LiveSplit manually between attempts. The script still tracks completed route events when an automatic action is disabled; split manually to keep the timer's segments aligned. Loading the script mid-run does not infer earlier completions.

## Fixed split order

1. Dan's Crypt
2. The Graveyard
3. Cemetery Hill
4. The Hilltop Mausoleum
5. Return to the Graveyard
6. The Enchanted Earth
7. Pools Of The Ancient Dead
8. The Lake
9. The Crystal Caves
10. The Gallows Gauntlet
11. The Haunted Ruins
12. The Ghost Ship
13. The Entrance Hall
14. The Time Device
15. Fazguls
16. Kardok
17. Zarok

Level splits occur immediately on the expected level's successful native exit. Deaths, quits, reloads and unrelated level/header changes do not count. There is no Hall of Heroes handling, Rune option, optional boss split or separate Zarok's Lair entry split.

The route advances in this order, once per event per attempt. Fazguls requires army victory; Kardok and Zarok require their distinct actors, phases and native death actions with previously observed positive HP. A zero HUD bar alone does not finish a boss.

## RAM readers

Target layout: MediEvil USA, SCUS-94227, executable SHA-1 `265ce5dc508002a339ae535e49a5b1b4e683b732`. Three short code anchors qualify the layout; the script does not calculate that full executable hash from RAM.

| Reader | RAM source |
| --- | --- |
| ePSXe, 32-bit | Built-in signature scan for the native RAM-base pointer, then cached base + field offsets |
| DuckStation | Read-only `duckstation_PID` shared-memory export |
| PCSX-Redux | Read-only `pcsx-redux-wram-PID` named mapping |
| MediEvil Recomp v0.2b | Signature lookup of the 4 MiB managed RAM array, then cached base + field offsets |

DuckStation requires **Export Shared Memory** enabled and an emulator restart (`Hacks/ExportSharedMemory` on builds providing it). No emulator/version or LiveSplit build is certified by this source change.

Recomp requires a **64-bit ASL host with `MemoryPages()`**; your rebuilt Mac port provides this API. Stock 32-bit Windows LiveSplit cannot use the Recomp reader. Launch Recomp's `medievil` executable, load the USA game and wait for the `Any% USA` diagnostic before New Game. On the Mac port, reload the changed file through **Auto Splitter → Load Trusted ASL** and approve the game process when prompted.

Recomp lookup scans readable private regions in overlapping 1 MiB windows, checks the known 4 MiB CoreCLR array layout and qualifies the USA code anchors. It caches the result, with a fresh lookup after manual timer reset or a rejected read. The array must fit within one readable region. Multiple matching buffers are rejected rather than guessed; restart Recomp if a game reset leaves stale copies. Automatic discovery and gameplay on Recomp remain unverified.

The readers access individual fields, not whole-RAM snapshots. Detected read/layout/owner failures discard pending observations without restarting the route or replaying completed splits. Ordinary polling can miss short events and is not atomic or proof against unseen same-address object reuse.

Diagnostics go to LiveSplit's debug output. Check the component switches, emulator export/configuration and read permissions if automation remains inactive. Unsupported or ambiguous RAM sources disable automatic actions; manual timer controls remain available.

## Legacy scripts

The original scripts remain separate and byte-identical, including their version headers and credits:

- [`MediSplit_Any%.asl`](MediSplit_Any%25.asl)
- [`MediSplit_100%.asl`](MediSplit_100%25.asl)

**Only these legacy scripts** use the bundled [`emu-help-v3`](emu-help-v3). Put it in LiveSplit's `Components` directory when choosing a legacy script. Their historical tested-on claim is ePSXe 2.0.0; it is not a compatibility claim for this Any% script.

## Resources and attribution

- [MediEvil Speedrun Discord](https://discord.gg/V5DZEq9Fbf)
- [MediEvil on Speedrun.com](https://www.speedrun.com/medievil)
- [LiveSplit auto-splitter documentation](https://github.com/LiveSplit/LiveSplit.AutoSplitters)
- [MediEvil speedrunning wiki](https://medievil.wiki/w/Speedrunning)
- [emu-help-v3 source](https://github.com/Jujstme/emu-help-v3) — legacy dependency; also credited for the ePSXe native descriptor signature used by the independent direct reader
- [Recomp v0.2b entry point](https://github.com/BlackLabelHQ/MediEvilRecomp/blob/v0.2b/Program.cs) and [its RAM implementation](https://github.com/BlackLabelHQ/RecompOne/blob/1272fb80b1638efdae8f281ff6c6e90f93866ae6/RecompOne.Runtime/Memory/PSMemory.cs) — RAM layout provenance

Original contributors:

- SirDarcanos — author
- Xeelze — original script that inspired the rewrite
- 7eraser7 — development and memory-address research
- BlackMenthol — testing and memory-address research
- NoobKillerRoof — extensive testing

The project license and bundled third-party notices remain in place.
