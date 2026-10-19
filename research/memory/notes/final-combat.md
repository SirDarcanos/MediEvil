# Final-combat memory findings

USA `ZL.BIN` SHA-1 `37bbf2910f86cb3629d9dac3576017a9aac63433`, game index 23, loaded header 25. These findings concern gameplay memory. Native code supplies the interpretation; controller-only reproductions and instrumented traces determine which manipulations work in a run.

**Status:** code-backed findings below, not yet a reproduced Fazgul despawn or certified RNG route. Laboratory level requests/relocations are setup, never claimed level skips. A final-level entrance state is not the army arena.

## State and actor tables

Let `L = *(uint*)0x800EE978`. Interpret these offsets only in the final level with a live, correctly initialized level-data allocation.

| Field | Type/address | Native evidence / limits |
|---|---|---|
| Phase sequence index | `uint L+0x00` | Initialized to zero at `0x800119B4`; state controller `0x80011AA0` advances it when a phase-specific script flag is set. Not a clock. |
| Army outcome | `int L+0x04` | In phase 2, controller writes 0 when no friendly soldiers are counted, or 1 when friendlies remain and no enemies are counted. Do not treat it as a valid result outside that phase/path. |
| Post-army actor index | `ushort L+0x08` | Phase 4 cleanup walks up to eight friendly actor slots. |
| Later-phase countdown | `short L+0x0A` | Set to 5 at particular transitions; phases 5/7 decrement it and check raw state `0x800EEEF8` (audio-role candidate, not a verified cutscene-state field). Not the army outcome field. |
| Sound handles | `int L+0x0C`, `int L+0x10` | Initialized to -1; used for sound lifetime/voice gating. These are not generic victory flags. |
| Friendly registration rows | `0x8001C950`, 8 rows × 12 bytes | Soldier constructor binds a private pointer to one row and writes the runtime actor pointer at row `+8`. Row identity/index fields precede it. |
| Enemy registration rows | `0x8001C9B0`, 8 rows × 12 bytes | Same actor-slot convention. Identity fields include paired 16-bit values; do not flatten them into a guessed logical entity ID. |
| Current actor HP | `short actor+0x5A` | Used by skeleton code; Dan is a special case whose actual health is in game state, not his definition-derived actor HP. |
| Actor private state | `uint actor+0x90` | Skeleton controller data, including the row pointer at `+0`, a short timing field at `+4`, and additional target/movement references. Not a stable absolute allocation. |

The phase-to-script-flag lookup at `0x8001C92C` contains indices `11,10,13,14,15,18,17,18,19` into the byte flag region beginning `0x800EE934`. A set flag can advance the phase and launch a sequence. **This does not establish that writing such a flag is an in-game exploit or a valid natural reproduction.**

Native entry points: level initializer `0x800119B4`, sound cleanup `0x80011A68`, phase controller `0x80011AA0`; skeleton constructor `0x80016894`, action initializer `0x80016B88`, update `0x80016F14`.

### Typed read paths

USA-only examples for **friendly slot 0**; other rows have 12-byte stride. Guard gameplay mode, level 23/header 25, current owner and non-null slot first. A registration slot is not automatically counted/live.

```csharp
vars.armyPhase = vars.Helper.Make<uint>(0x800EE978, 0x00);
vars.armyOutcome = vars.Helper.Make<int>(0x800EE978, 0x04); // Meaningful in phase 2.
vars.friendly0Actor = vars.Helper.Make<uint>(0x8001C958);
vars.friendly0HP = vars.Helper.Make<short>(0x8001C958, 0x5A);
vars.friendly0Action = vars.Helper.Make<byte>(0x8001C958, 0x5C);
vars.friendly0Delay = vars.Helper.Make<short>(0x8001C958, 0x90, 0x04);
vars.friendly0Animation = vars.Helper.Make<byte>(0x8001C958, 0x74, 0x20);
```

Enemy slot-0 actor pointer is at `0x8001C9B8`. Negative HP/death action can occur before removal. These typed paths are based on native scalar reads/stores; Windows LiveSplit execution remains untested.

## What RNG directly affects

Shared state is `uint 0x800F3994`; native routine `0x800A43B8` implements the formula documented in the root README.

### Friendly initial HP

In `0x80016894`, subtype 0 selects the friendly path and subtracts `rand() & 0xFF` from the actor's initialized HP. The matching skeleton definition starts at 500, so this produces **245–500 initial HP**. The enemy subtype does not execute this subtraction in that constructor.

[Runtime constructor bindings](../evidence/army-rng-consumers.json) now match all eight draws at return address `0x800169A8` to the same actors' first registered HP samples. Every pre-subtraction HP was 500; slot-order initial HP was **298, 298, 379, 497, 278, 321, 307, 419** (sum 2797). Both identical-input repetitions matched all 1,794 RNG calls and actor contexts with no recurrence discontinuities. These values belong to this state/input sequence, not fixed soldier stats.

Implication: a stream shift before a friendly spawn can change its endurance before any attack decision is made. Spawn/update order determines which soldier receives which draw; other shared-stream callers intervene.

### Attack selection and delay

In `0x80016B88`, entering actor action 5:

1. One draw selects animation value `0x17` or `0x18` using `rand() & 1`.
2. A second draw sets the short private timing field to `rand() % 60` (0–59).

[Native-store readback](../evidence/army-decision-validation.json) verified **39/39** action-5 decisions: byte `[actor+0x74]+0x20` exactly matched the first draw's animation selection and short `[actor+0x90]+4` matched the second draw modulo 60. The stores are at `0x80016E54` and `0x80016E8C`; the non-pausing readback checkpoint is `0x80016EF8`. The RNG trace remained byte-identical to the prior observation-only run. Observed choices were 18 animation-`0x17` and 21 animation-`0x18`, with delays 1–58 (the code permits 0–59).

The animation IDs are code values, not yet a verified mapping to named attack styles or hit probabilities. Do not assume the two animations alone explain the fight result.

### Damage versus block

Collision callback `0x80016AAC` checks the event/source form. For the other-form-3 branch it draws RNG at return `0x80016B18`: even output invokes generic hit handler `0x80047210`; odd output enters action 18 instead. The generic handler's event-type-1 branch directly calls damage routine `0x800458E8`, confirming this is a damage path rather than only an animation/effect handler. This is **not** a universal player/projectile hit probability.

[Immediate native readback](../evidence/army-hit-validation.json) verified **106** such decisions at `0x80016B78`: all 48 odd-output cases preserved HP and entered action 18; all 58 even-output cases reduced HP. In this setup allied defenders lost 50 per accepted hit and enemy defenders 20. Seven accepted hits killed allies and entered action 11. The RNG trace remained byte-identical to its control. Damage amounts and the finite hit/block distribution are observations for this context, not universal stats or independent probability estimates.

The accepted-hit branch draws again at `0x80016B34`; if that output's low three bits are zero, it draws a third time at `0x80016B48` and passes `(output & 3)+0x9E` to an actor effect/sound helper. Thus a hit and a block consume different numbers of RNG calls, feeding back into later decisions. Effect identity remains separately qualified.

### Low-health voice consumption

In `0x80016F14`, a friendly with HP below 100 and no active level voice handle calls the shared RNG. The voice handle is `int L+0x10` (distinct from `L+0x0C`). A low-three-bit zero result plus action 5 permits a voice request. The RNG call occurs before the action-5 test, so an injured friendly can consume a draw even when that last condition does not produce a voice.

[A 900-Vsync native fight trace](../evidence/army-low-health-rng.json) observed **539** such calls among 1,368 total draws, all subtype 0 and HP below 100. The handle-`-1` predicate is code-backed at `L+0x10`; the original trace field mislabeled `L+0x0C` as that handle and is explicitly corrected in the evidence artifact, not counted as a direct handle read. Only 39 had action 5; the others were actions 17 (220), 11 (124), 6 (91) and 18 (65). Seventy draws outside action 5 even had low-three-bits zero, yet did not satisfy that final action predicate. HP at the callback ranged from -47 to 99: signed HP/death action must not be confused with freed-memory reads. These were checked actor contexts in the native update path. The same trace validated another 120 action-5 animation/delay readbacks.

Implication: damage and the lifetime of dying actors change RNG consumption as well as survival, even without a new attack or audible voice. The stream is coupled to ambient/audio/effect consumers elsewhere, so a simple fixed draw count per attack is not sufficient.

### Non-soldier level callback

[Caller ownership](../evidence/level-rng-consumer.json) identifies `0x800283D0` as a separate level callback, registered by `0x800241F4` under enable-mask bit `0x80`. It updates six groups of three coordinate/phase elements through the pool pointer at `0x800EE094`. Site `0x800284AC` draws `rand()%3` during particular phases; `0x80028670` draws on phase transitions. These accounted for **810 + 117 = 927** of the 1,794 calls in the constructor/early-combat trace, all in submode 0 in that observation. Its code explicitly skips update work in pause submode 1, not inventory/book submode 2. Exact visual identity and configuration effects remain unverified; do not label those calls soldier attacks or infer ownership from the stale scratch-actor hint.

## Outcome counting and the despawn question

In phase 2, `0x80011AA0` traverses the runtime list headed through `0x800EE888`, with sentinel `0x800EE884`. It examines each node's record reference at node `+0x0C`, requires form/type 3 at record `+4`, and splits friendly/enemy counts using subtype at record `+6`.

- No counted friendlies: outcome 0.
- Friendlies and enemies both present: keep waiting.
- Friendlies present, no counted enemies: outcome 1 and script flag `0x800EE941` is set.

**Established:** this is a particular runtime-list count, not a count of every authored soldier record in the map.

**Hypothesis to test:** inventory/cutscene interruption leaves gate soldiers uninstantiated, or outside this counted list, allowing the counted enemies to reach zero early. Need creation/removal/list-membership traces. Merely seeing fewer soldiers or an early victory does not distinguish those cases.

The constructor writes an actor pointer into a fixed row; one action initializer clears its row pointer. Later phases use registration rows for cleanup. This supplies concrete references to inspect for the reported later gate-camera crash, but no use-after-free cause is claimed without a trace.

## Authored versus runtime soldiers

The decoded map resource 752 inside level WAD 751 has eight authored enemy skeleton records, all subtype 1 and initial flags 8: four at each gate around X ±1040, Z -3400. Their initial flag's full meaning still needs the creation path. These positions/records do not prove when or where the live soldiers are instantiated or moved by the cutscene.

## Controlled runtime results

A stable [laboratory detachment/relocation](physics.md) did not itself start the encounter. The first walking route stopped outside radius 500 and left phase 0, script flag 11 unset and both counted teams empty. A later controller-only closer approach reached `(-41, 32, 363)` and naturally set flag 11/phase 1 at probe Vsync 223. Thus the earlier failure was a route stopping short of the native trigger, not proof of a missing entrance-script dependency or soldier despawn. A separately labeled test writes only byte `0x800EE93F` to 1 at probe Vsync 120. Native code then instantiated eight counted enemies (by Vsync 1103) and eight friendlies (2417); phase 2 began at 2542 and the cinematic gameplay flag cleared at 2662. These are `army-intro-normal-2` observations, not normal-route entry.

[Entry comparisons](../evidence/army-entry-validation.json) show that the moving inventory attempt and six adjacent timing offsets never entered inventory. They are invalid interruption tests, not a reproduced or disproved glitch. A matched stationary-window pair did open inventory at Vsync 123 with sequence counter 1, and remained open at 124 with counter 2. It closed at 125. Suppressing **all Triangle inputs** still produced that closure, correcting the earlier early-dismissal hypothesis. All eight enemies subsequently appeared in those ordinary-opening tests. A later [buffered-reopen comparison](../evidence/inventory-cleanup-validation.json) did sustain a newly opened inventory through sequence counter 89: open at Vsync 80, Triangle at 110, Select at 114 or 116. The old window closes, its reopen request survives scene cleanup, and a new window opens at 139. Select at 118/120 did not reproduce that reopening. The [full-introduction pair](../evidence/army-buffer-comparison.json) then established a consequence at the tested south-side position: no-reopen control reached 8 friendlies/8 enemies; buffered entry reached 0 friendlies/4 enemies and immediately selected the native **loss** outcome. This is not the successful reported skip. In the final sampled registration rows, only enemy slots 1, 3, 4 and 6 were populated, with no friendly slots populated. Actor non-allocation versus inactive ownership still needs lifecycle tracing. Testing now follows the user-supplied Select close/reopen procedure at the native central trigger; the earlier buffering traces used Triangle for closing and an injected intro flag.

[Final-army RNG evidence](../evidence/rng-army-comparison.json) records five 600-Vsync trials from the identical phase-2 state. Idle consumed 1,008 draws, movement 934, inventory 580 and attacks 2,702; all recurrence steps validated without discontinuities. Idle repetition matched every `(Vsync, caller RA, before, after)` tuple and soldier-HP endpoint. Idle ended with four positive-HP registered friendlies (sum 460), movement five/467, inventory seven/891, attacks seven/491. All eight enemies remained. These are slot observations, not victory-list counts or final outcomes. Inventory pauses simulation; movement changes distances/visibility/targets; attacks may directly damage actors. HP differences do **not** yet isolate RNG causality.

Action-5 draw return addresses `0x80016E20` and `0x80016E58` each occurred 100 times in idle, 97 movement, 62 inventory and 98 attacks. Injured-friendly consumer return `0x800170F8` also appeared. Thus the observed stream includes final-level soldier decisions, not just ambient effects.

### Population and release timing

[Native-trigger Select traces](../evidence/native-inventory-buffer.json) reproduce buffered entry without an introduction-flag write: both controls enter near `(-44, 33, 368)` at Vsync 127; only the reopen input sustains the later UI state. They still inherit laboratory level/relocation setup, not a complete natural-route playthrough.

[Release comparisons](../evidence/army-release-comparison.json) continue the identical buffered state. Releasing inventory at sequence counter **520** caused the enemy count to jump 4→8 when normal updates resumed; all eight allies later activated, and the battle ended with no allies and loss outcome 0. Releasing at **1078** allowed eight allies to activate while only four enemies were counted. At the 6000-Vsync observation limit, five allies and one enemy remained. A [strictly idle continuation](../evidence/army-idle-victory.json) removed the last enemy at continuation Vsync 136, set native army outcome 1 at 138 and reached phase 3 at 140, with five allies and Dan's 300 HP intact. All logged effective pad masks were zero: no healing, attacks or movement. This certifies only a hands-off **army-controller success flag** in this setup. The probe stopped at phase 3, before the missing four enemies were reactivated or the following cutscene completed. The user clarified that failing to reactivate them in the cheering-to-cutscene window itself commonly crashes; this early stop therefore does **not** establish crash-free fight/glitch completion or a Redux compatibility workaround. Holding the UI through phase 2 instead suppressed all allies and selected immediate loss.

These establish population/update dependencies, not isolated RNG advantages. Initial HP, draw ordering and other consumers may also change. Missing actors must not be called deleted without lifetime/ownership evidence. Research priority is understanding these fight/RNG dependencies, not completing a particular exploit or provoking the reported crash.

### Post-victory reactivation and the Redux fault

Corrected upper-half movement brought all four missing enemy slots **0, 2, 5, 7** into the counted list at continuation Vsyncs 264–268, after army success. By slot sample 451, all four had 500 HP and action **19**, the same action observed on victorious positive-HP allies. The aftermath and allied cleanup progressed to phase 5. This earlier stopping point alone did not establish successful glitch completion.

A [continuation through the next transition](../evidence/post-reactivation-fault.json) then stopped after 91 sampled Vsyncs. Redux logged **`Unaligned address 0x95FF9313 in LW from 0x800A2980`** and **`First chance exception: LoadAddressError from 0x800A2980`**. The outer task timed out after no further frames. Thus this tested Redux configuration did **not** provide a crash-free workaround. The register/heap cause is not yet diagnosed; do not promote the reported memory-management explanation to fact. Starting states inherit laboratory setup, and no other emulator/configuration has been compared here.

## Next deciding experiments

1. Map animation values `0x17/0x18` to contact timing and damage events; distinguish action entry from a completed attack or collision.
2. Trace target selection, facing/distance/collision and per-actor update order. Those can change contact opportunities without changing the hit/block formula.
3. Bind remaining consumers to their owners and phase/state predicates; preserve repeat controls when adding observation callbacks.
4. Quantify healing, injury/death-state lifetime and activation timing as coupled changes to health and subsequent RNG draws, not RNG-only controls.
5. Keep emulator/BIOS/audio-setting claims separate from observed native behavior. No exploit-completion or deliberate post-victory crash experiment is required for this fight/RNG model.
