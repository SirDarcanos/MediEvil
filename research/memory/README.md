# USA memory audit

This audit targets `MEDIEVIL.EXE` SHA-1 `265ce5dc508002a339ae535e49a5b1b4e683b732` (SCUS-94227). See the [address reference](../../README.md) for address definitions and verification limits.

For the current autosplitter-focused findings and remaining checks, start with
[ASL verification status](notes/asl-readiness.md). RNG research is benched.

## Layout

| Directory | Contents | Git policy |
| --- | --- | --- |
| [`tools/`](tools/) | Reusable Python capture, decoding, extraction and analysis tools. | Keep source. |
| [`probes/`](probes/) | Bounded Lua scenarios, including explicitly labelled laboratory setups. | Keep source; a probe may require a particular owned starting state. |
| [`ghidra/`](ghidra/) | Static-analysis and export scripts for disposable Ghidra projects. | Keep Java source, not compiled classes or project databases. |
| [`tests/`](tests/) | Tool, evidence-predicate, layout and isolation regression tests. | Keep tests and fixtures. |
| [`evidence/`](evidence/) | Curated JSON findings, extracted tables, hashes and verification limits. | Keep relevant evidence, including informative negative results. |
| [`notes/`](notes/) | Interpretation, methodology and open research questions. | Keep notes; distinguish current findings from historical trials. |

Local `inputs/`, `runs/`, `outputs/` and `scratch/` directories are ignored, as
are caches, raw RAM/pixels, memory cards, save states, emulator app copies and
Ghidra databases. These directories are optional; `/tmp` remains the preferred
location for private runs. Curated JSON, Lua, Java, Python, Markdown and authored
diagrams are not blanket-ignored. No useful source or evidence was discarded
as part of the reorganization.

Evidence retains its original run paths and hashes as provenance. Moving a
summary does not make a historical `/tmp` path a required checkout location,
or mean that the latest probe source matches every earlier frozen-probe hash.
See [evidence handling](evidence/README.md).

## Reusable tools

Python tools use only the standard library. Commands below run from the
repository root; they also accept absolute script paths from another directory.

| Tool | Purpose |
| --- | --- |
| [`tools/run.py`](tools/run.py) | Finite isolated Redux launcher; resolves its default probe from `probes/`, not the working directory. |
| [`tools/decode.py`](tools/decode.py) | Typed PS1 reads, pointer paths and gameplay-ownership checks. Importable module, not an emulator client. |
| [`tools/inventory.py`](tools/inventory.py) | Extract all 43 inventory descriptors from the matching executable. |
| [`tools/levels.py`](tools/levels.py) | Extract level/index/header mappings from the executable and its overlay files. |
| [`tools/analyze.py`](tools/analyze.py) | Compare complete RAM captures and summarize declared successful runs. |
| [`tools/analyze_rng.py`](tools/analyze_rng.py) | Validate native RNG recurrence/caller traces without inferring fight outcomes. |
| [`tools/asl_signals.py`](tools/asl_signals.py) | Reference predicates for captured boss records; not a LiveSplit implementation. |

## Probe catalogue

The launcher selects a file in `probes/` with `--probe`; setup flags are launcher options,
not commands to execute a Lua file directly. None attaches to an existing
emulator. Matching game revision and starting-state prerequisites still apply.

| Probe | Reusable purpose / setup |
| --- | --- |
| `probes/probe.lua` | Default boot, movement and basic action capture. |
| `probes/title.lua` | Bounded title/menu/input observation. |
| `probes/ui-audit.lua` | Bounded scheduled UI inputs, live-window observations and equipment checks. |
| `probes/pickup.lua` | Crypt pickup routes with item-acquisition checks. |
| `probes/use-daggers.lua` | Native attack/ammunition-use check from an equipped-dagger state. |
| `probes/complete-crypt.lua` | First-visit Crypt completion/map transition and optional longer map observation. |
| `probes/lifecycle.lua` | Fatal-state continuation and title-return lifetime observation. |
| `probes/boss.lua` | Native level dispatch after explicit `--level-setup`. |
| `probes/pumpkin.lua` | Pumpkin observation/combat; optional labelled `--wake-setup`. |
| `probes/arena-seed.lua` | Explicit `--relocation-setup`; optional non-pausing position trace. |
| `probes/army.lua` | Army registration, UI buffering, native outcomes and optional RNG tracing; optional labelled `--intro-setup`. |
| `probes/rng.lua` | Bounded shared-RNG input/consumer observation. |
| `probes/boss-prep.lua` | Assisted pre-boss setup; requires `--ally-heal-setup`. |
| `probes/boss-combat.lua` | Native attacks with required `--combat-supply-setup`; optional explicit `--boss-last-hit-setup`. |

## Evidence

- `evidence/newgame-request-events.json`: guarded New Game acceptance packet at Vsync3 versus later title-flow completion at124; idle/attract and navigation controls do not match. The packet itself is generic, not a global New Game flag.
- `evidence/kardok-arrival-events.json` / `evidence/kardok-damage-events.json`: assisted encounter preparation, then 113 native 6-HP damage events without boss HP writes.
- `evidence/final-boss-events.json`: explicit 6-HP last-hit setup; native Kardok HP0/action11/HUD-active0, followed by phase/owner handoff to Zarok. This run did not finish Zarok.
- `evidence/zarok-death-events.json`: native sword HP6→−8/action25 in an inherited last-hit setup, with player-health/ammo assistance but no boss HP writes in this run. The clean repeat passed; both executions ended in identical full RAM. HUD cache reached0 two Vsyncs after actor death; HUD-active remained1.
- `tools/asl_signals.py` / `tests/test_asl_signals.py`: reference guard checks against captured boss records and negative fixtures, not a Windows LiveSplit implementation or integration test.
- `evidence/isolation-verification.json`: private renamed executable, matching binary hash, canonical-discovery exclusion and disabled TCP services.
- `evidence/health-events.json`: native player damage, bottle-energy transfer, fatal HP zero and later death-substate entry in a controller-only continuation. `evidence/fatal-lifecycle-events.json` continues the fatal state through automatic title return and demonstrates stale freed game-state memory; manual reset/load behavior remains untested.
- `evidence/pumpkin-setup-events.json`: explicitly injected level-dispatch setup and native allocation handoff; not a boss kill.
- `evidence/pumpkin-hud-events.json` / `evidence/pumpkin-hud-limits.json`: active input/actor/max binding at 1100 after labeled wake setup, plus 400 samples where the active bar's cache was zero despite input/actor HP 1100. Attempts did not damage/defeat the boss; do not present successful process exit as victory.
- `evidence/pumpkin-code-fields.json`: clean constructor/state-callback tracing for Pumpkin's HP/HUD and level-local phase fields. Candidates are not promoted to working death triggers without native transitions.
- `evidence/verified-runs.json`: two Crypt movement runs and a fresh boot; hashes for 127 complete 2 MiB captures, phase observations and per-4-KiB change counts.
- `evidence/pickup-events.json`: repeated Star Rune/Small Sword acquisitions, then bottle reserve/capacity gains and dagger acquisition. The first routes hit their frame limits before every item; the focused third route reached both acquisition goals. A successful process exit alone does not imply a successful whole route.
- `evidence/crypt-exit-events.json`: natural rune consumption, result 5, the first completion-bit change and map-module entry. The actor pointer cleared while game-state data persisted. The final image still showed loading, so map UI-ready timing was not established.
- `evidence/dagger-use-events.json`: eight native attack uses reduced ammunition 100 to 92, with one-unit decrements under both attack buttons and weapon enum 3 unchanged. Full depletion remains untested.
- `evidence/movement-fields.json`: captured weapon enum, combined movement flags and input-update counters; running transitions remain untested.
- `evidence/title-fields.json`: typed reads of the actual title-control pointer/flow state, backed by the title updater's dispatcher result. `evidence/title-input-events.json` records the tested Cross-to-flow-2 delay; alternate-menu-choice negative controls remain invalid.
- `evidence/level-table.json`: 25 static level records and their native display names, resolved through overlay descriptors to real `.BIN` header IDs. A descriptor index is not a loaded header ID; Programmer's Playground shares Graveyard's overlay header.
- `evidence/inventory-table.json`: 43 descriptors and names extracted from the matching executable. This establishes table layout, not gameplay verification of every item. The primary value has item-specific semantics; the Chalice entry is a HUD-updated fill fraction rather than an ownership count.
- `evidence/rng-crypt-validation.json` / `evidence/rng-input-comparison.json`: native unsigned recurrence validation and controlled Crypt input trials.
- `evidence/army-rng-consumers.json`: two identical 1,794-call traces, with all eight allied constructor draws bound to their observed initial HP.
- `evidence/army-hit-validation.json`: 106 native skeleton-collision decisions; odd outputs preserve HP/action 18, even outputs apply the observed 50/20 damage. Readback instrumentation preserved the original trace.
- `evidence/army-low-health-rng.json`: 539 low-health-check draws, including non-attacking/death states, plus 120 additional animation/delay readbacks.
- `evidence/level-rng-consumer.json`: separate six-group level callback consuming the shared stream; exact visual identity remains unverified.
- `evidence/army-decision-validation.json`: 39 exact attack-animation/delay readbacks; instrumentation left the RNG trace unchanged.
- `evidence/army-release-comparison.json`: release timing changes active combat populations (8v8 versus 8v4), with observed limits/outcomes rather than a claimed RNG-only cause.
- `evidence/native-inventory-buffer.json` / `evidence/army-buffer-comparison.json`: native-trigger Select buffering and separate laboratory intro controls; inherited setup remains explicit.
- `evidence/rng-army-comparison.json`: identical final-army seed, deterministic idle repeat, input-dependent RNG/caller and registered-HP endpoints, with pause/damage/visibility confounds retained.
- `evidence/inventory-cleanup-validation.json`: 17 complete pulse/buffer controls, including a queued reopen surviving scene cleanup and a new live inventory while the sequence advances; interrupted disk-full attempts excluded.
- `evidence/army-entry-validation.json`: missing-prerequisite control, matched native introductions, rejected moving UI attempts and brief stationary inventory entry; no sustained-inventory/despawn proof.
- `notes/final-combat.md`, `notes/glitches.md`, `notes/physics.md`: phase/actor/outcome relationships, inventory admission, sequence/actor-freeze interactions and failed setup controls; no certified Fazgul despawn or collision skip.
- `tools/decode.py`: offline typed PS1 reads and pointer-path checks. It is not a Windows LiveSplit test.

The original README, [supplied entity-definition spreadsheet](https://docs.google.com/spreadsheets/d/10V-bdQL4m7OJEFcUVu8-bVkRNP2D3pYeaZ3d_HElqAo/edit?gid=1573868363) and prior local research were leads. Meanings were checked against the executable's reads/writes and the recorded runtime observations. The public decompilation at commit `6afe6fe35d5ddf0ce1bebdb2e72f8215b5b5b407` names the same executable SHA-1, but most gameplay functions there are assembly placeholders.

The native allocator at `0x8006993C` allocates `0x6F0` bytes and stores its result through `gp + 0x568` (`0x800EDB3C`). The entry initializes `gp` to `0x800ED5D4`. Player registration at `0x80069BC0` stores the actor at game-state `+0x530`; the coordinate setter at `0x800485EC` writes signed 32-bit actor XYZ and their physics fixed-point counterparts.

Useful native code locations:

| Function / instruction | Observation |
|---|---|
|`0x8001203C` in `TL.BIN`|Reads title control through `0x800EDC1C`; flow state 2 returns the New Game dispatcher result. This is not proof of physical button-acceptance timing.|
|`0x800A8FEC`|Loads a 32-byte overlay descriptor selected by index; runtime descriptor-table pointer `0x800EDE30` matched `0x800CD9E8`.|
|`0x8006996C`|Stores initial health 300 at game-state `+0x00` with `sw`.|
|`0x80045C8C` in `0x800458E8`|Stores health after damage subtraction.|
|`0x80046138`|Sets health to zero and enters native death handling.|
|`0x800762B0`|Copies health into the HUD mirror and derives bottle display from 32-bit reserve energy/capacity.|
|`0x80093B70`, case 1|Bottle pickup adds 300 to both reserve energy (`+0x04`) and capacity (`+0x08`).|
|`0x8005D92C` / `0x8005E104`|Inventory initialization and consumption: 43 records, four-byte stride, 16-bit primary value.|
|`0x8005DE00`|Resolves descriptor `+6` through localization pointers at `0x800D98BC`, independently establishing each inventory name.|
|`0x80077398`|Generic HUD-bar renderer: 32-bit input at `+4`, clamped last-input cache at `+8`, maximum at `+0x10`. Explains the old boss-health cache rather than proving a universal boss-entity field.|
|`0x8006B034`|Sets equipped weapon enum at `+0x0C`; this enum differs from inventory indices.|
|`0x8006B104` / `0x80069C30`|Input-state/counter updates and combined flags at `+0x670`.|
|`0x8002364C`|Gameplay/submode loop; increments the logical frame counter only in the normal update branch.|
|`0x8004D42C` / `0x80059E58`|Native exit collision writes result 5; the dispatcher processes completion/progress and routes to the map or other next state. One first-visit Crypt-to-map-module path was exercised; this does not establish every replay/exit path.|
|`0x80069C10`|Unregisters the player actor by clearing game-state `+0x530`; persistent inventory/progress can still be valid afterward.|
|`0x800BC99C` in `_SsVmVSetUp`|Writes `0x800F6E83` from sound-program metadata. Key-on/pitch routines use it for tone indexing; it is not a New Game flag.|

## Reproduce captures

The launcher is specific to the tested local macOS application layout. Python tools require only the standard library. Supply your own game, BIOS and suitable Redux state; none are included here.

```sh
GAME="$HOME/PSX/MediEvil (USA)"
BIOS="$HOME/.epsxe/bios/scph1001.bin"

python3 research/memory/tools/run.py --game "$GAME" --bios "$BIOS" \
  --scenario movement --seed /path/to/crypt.state.gz \
  --output /tmp/medievil-movement-A

python3 research/memory/tools/run.py --game "$GAME" --bios "$BIOS" \
  --scenario boot --output /tmp/medievil-boot-A

python3 research/memory/tools/analyze.py /tmp/medievil-movement-A /tmp/medievil-boot-A \
  --output /tmp/medievil-analysis.json

python3 research/memory/tools/inventory.py "$GAME/EXE/MEDIEVIL.EXE" \
  --output /tmp/medievil-inventory.json

python3 research/memory/tools/levels.py "$GAME/EXE/MEDIEVIL.EXE" \
  --output /tmp/medievil-levels.json

python3 -m unittest discover -s research/memory/tests -t research/memory -p 'test_*.py' -v
```

Use a new empty output directory for each run. The launcher creates an isolated HOME, disposable memory cards and a CLI-only child. Current versions also copy the application into that run directory and rename only the copied executable to `ReduxAudit`, verifying identical binary bytes. This keeps the child out of tools that auto-discover the canonical `PCSX-Redux` process name. The source application is never renamed or patched. Web and GDB services are disabled: these probes use no TCP port. Ordinary probes also disable the interpreter debugger; `--trace-rng` and `--trace-position` enable only its private non-pausing execution/write callbacks, not network services. A running smoke test confirmed the private process path and no TCP listeners; its gameplay checks also passed.

The launcher does not attach to, stop, save or control an existing emulator. Normal probes read RAM and use controller inputs after the recorded state restoration/cold boot. Older records call this “no emulated RAM writes,” meaning no direct probe pokes, not no native game writes or initial state restoration. The probe is frozen before launch; `run.json` records setup, process isolation, seed provenance and probe/binary hashes.

`probes/boss.lua` is a separately labeled, controlled-setup experiment and **requires `--level-setup`**. From our Crypt state it writes only the next-level request (`0x800EEE30`), movie override (`0x800ED6CC`) and reload result (`0x800EEE6C = 4`). These injected request changes are not natural-event verification. It does not inject health, inventory, actor coordinates or boss-HUD values; subsequent native changes must be assessed separately. The target defaults to game index 10 / header 20 and can be specified with `BOSS_LEVEL` / `BOSS_HEADER`. A successful exploration run alone does not prove a boss kill or every HUD field's meaning.

`probes/pumpkin.lua` resumes that owned state with controller-driven dialogue dismissal, sword selection and combat. Its default mode makes no RAM pokes. Optional `--wake-setup` explicitly clears the level-local wake prerequisite at `[0x800EE978] + 0x10` once; the injected counter and resulting wake phase are not natural-progression evidence. HP, HUD, inventory and coordinates remain unmodified by the probe. Such runs have their own setup declaration in `run.json`; do not merge them into a controller-only/natural-progression claim.

`probes/use-daggers.lua` requires our acquired/equipped-dagger state and fails its own objective check if attacks do not consume ammunition. Use it with `--scenario actions`, not the movement-position criterion. `probes/complete-crypt.lua` is a finite first-exit experiment; its objective is a natural map transition plus the native completion flag, not waypoint arrival.

`probes/pickup.lua` is an experimental finite controller route, not a general game-playing tool. Waypoint arrival alone is not evidence of item acquisition; inspect the primary field's transition. The focused bottle/dagger route requires its acquisition conditions before advancing.

## RNG and final-level experiments

From a suitable owned gameplay state:

```sh
RNG_ACTION=idle python3 research/memory/tools/run.py --game "$GAME" --bios "$BIOS" \
  --scenario ui --seed /path/to/fight.state --probe research/memory/probes/rng.lua \
  --trace-rng --output /tmp/medievil-rng-idle
```

`RNG_ACTION` also accepts `move`, `inventory` and `attack`; each `probes/rng.lua` probe lasts 600 Vsyncs. `probes/army.lua --trace-rng` additionally records constructor/combat context and native action-5 result-store readbacks, without altering guest state. `ARMY_RELEASE_SEQUENCE` schedules a two-Vsync Select release when a live inventory reaches that sequence-counter threshold; it is not a wall-clock timing value. `tools/analyze_rng.py` checks every native recurrence step and groups caller return addresses. Compare identical seeds and repeats before interpreting input effects; inventory can change simulation progression, not just RNG.

`probes/arena-seed.lua` requires `--relocation-setup`; use `--trace-position` for its bounded position-writer observation. It clears explicitly recorded player flags and synchronizes actor/physics vectors. This is injected laboratory detachment, not an allowed skip. `probes/army.lua` normally only observes and uses inputs. Its optional `--intro-setup` writes byte `0x800EE93F` once to supply an omitted introduction prerequisite; no army counts, soldier HP or RNG values are injected. These state families inherit earlier laboratory setup even when a continuation itself makes no pokes.

Army controls: `ARMY_INPUT=normal|inventory`, `ARMY_MENU_AT` (default 120), `ARMY_LIMIT` (default 3600 Vsyncs), `ARMY_STATIONARY_WINDOW=1` to stop movement during Vsyncs 60–131, and `ARMY_SKIP_MODE=periodic|none|voice`. `ARMY_MENU_HOLD` sets the initial pulse duration; `ARMY_BUFFER_CLOSE_AT` and `ARMY_BUFFER_REOPEN_AT` add two-Vsync Triangle/Select pulses (default 0 disables them). New probes save these controls in `probe-options.json` and `buffer-options.json`. Input variants must demonstrate actual inventory (submode 2 and game-flags bit 4), not merely a Select press. Our stationary setup opened it briefly at 123–124, then it closed even with Triangle entirely suppressed. A later buffered sequence (open at 80, close at 110, reopen request at 114/116) did sustain a new inventory during the running sequence; see `evidence/inventory-cleanup-validation.json`. Soldier consequences, Fazgul despawn and route-valid entry remain unverified. Frozen probes and logs retain the tested versions; later acceptance checks are stricter than early runs' exit codes.

## Reproduce code inspection safely

Use Ghidra with the PS1 loader/language and a compatible JDK. Work on a **copy**, never the other project's original `.gpr`/`.rep` files:

```sh
WORK=$(mktemp -d)
cp "$GAME/Decomp.gpr" "$WORK/Decomp.gpr"
cp -R "$GAME/Decomp.rep" "$WORK/Decomp.rep"

"$GHIDRA_INSTALL_DIR/support/analyzeHeadless" "$WORK" Decomp \
  -process '*' -recursive -readOnly \
  -scriptPath "$PWD/research/memory/ghidra" -preScript PrepareAudit.java \
  -postScript AuditMemory.java "$GAME/EXE/MEDIEVIL.EXE" "$WORK/output"
```

`ghidra/PrepareAudit.java` establishes GP/entry context and selected callback entries in the disposable analysis program. `ghidra/AuditMemory.java` exports assembly, decompiler output, references and the mapped-byte comparison with the supplied executable. Decompiler types and generated names are interpretation aids; inspect the scalar loads/stores before assigning a type or meaning. This work does not establish exact GTE/physics arithmetic.

## Open checks

Kardok and Zarok native death boundaries were observed with explicitly labelled last-hit setup; Pumpkin defeat remains unverified. Other open areas include all-level allocation handoffs, every inventory use, cold-menu controls, Rune Smuggle/reset semantics, collision skips and Windows LiveSplit execution. RNG manipulation work is benched. Native player damage/refill/death and one automatic fatal-to-title lifecycle were exercised. Initial values and code-backed layouts are not substitutes for those transitions; see [current verification status](notes/asl-readiness.md) rather than treating every earlier experiment as the latest result.

Raw RAM, screenshots, ROMs, BIOS, memory cards, save states and Ghidra databases stay outside version control, preferably outside the checkout. They may contain copyrighted game data or another project's state. For gameplay-overlay analysis, `ghidra/LoadOverlayAudit.java` enforces a disposable project directory under `/tmp/medievil-ghidra-memory-audit`; create a fresh project copy under that root before using it. It should run with `-noanalysis` plus checked constructor/vtable entry addresses. Do not globally analyze main-program calls into fixed addresses belonging to other overlays: that produced overlapping functions and a stack-analyzer error in the initial Pumpkin export. The clean Pumpkin export used only `0x80013D70`, `0x80013EE4` and `0x8001416C`, with no such errors.

The original local Ghidra project's protected-file hashes were checked unchanged after isolated inspection. `ghidra/LoadTitleAudit.java` additionally loads `TL.BIN` only into the disposable analysis copy; its code and globals must not be interpreted as gameplay-state fields outside the title context.
