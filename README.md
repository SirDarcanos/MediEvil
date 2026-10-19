# MediEvil — USA memory address reference

Game-memory addresses and data layouts for **MediEvil, USA retail SCUS-94227**.
Executable: `MEDIEVIL.EXE`, SHA-1 `265ce5dc508002a339ae535e49a5b1b4e683b732`.
Other game revisions have not been verified against this reference.

- [Address notation and pointer roots](#address-notation-and-pointer-roots)
- [Global game state](#global-game-state)
- [Title and New Game state](#title-and-new-game-state)
- [Player state and health](#player-state-and-health)
- [Inventory and level progress](#inventory-and-level-progress)
- [Position, physics and attachments](#position-physics-and-attachments)
- [UI and scripted sequences](#ui-and-scripted-sequences)
- [Boss health and final encounters](#boss-health-and-final-encounters)
- [Shared RNG](#shared-rng)
- [Native tables and routines](#native-tables-and-routines)
- [Level IDs](#level-ids)
- [Corrections to older address lists](#corrections-to-older-address-lists)
- [Evidence and limits](#evidence-and-limits)

## Address notation and pointer roots

Addresses are **PS1 virtual addresses**, not emulator process offsets. Main RAM
occupies `0x80000000`–`0x801FFFFF`; a raw main-RAM file offset is the address minus
`0x80000000`. Multi-byte values are little-endian.

`uint8`/`uint16`/`uint32` mean unsigned 1/2/4-byte values; `int16`/`int32` are
signed 2/4-byte values. Pointers occupy four bytes. Addresses and offsets are
hexadecimal; mode, phase, action and index values are decimal unless prefixed
with `0x`. Brackets mean reading the value at an address: `[G + 0x530]` reads a
pointer from the game-state allocation.

| Symbol | Type | Pointer read | Owner / lifetime |
| --- | --- | --- | --- |
| `G` | `uint32` | `[0x800EDB3C]` | Game-state allocation, size `0x6F0`. Persists through the observed level-to-map transition. **Can remain non-null after free on return to title.** |
| `A` | `uint32` | `[G + 0x530]` | Registered player actor. Can be null during loading and on the map while `G` remains live. |
| `P` | `uint32` | `[A + 0x80]` | Player physics allocation; valid only with its owning actor. |
| `T` | `uint32` | `[0x800EDC1C]` | Title-control allocation. Interpreted in main mode 2, overlay header 24. |
| `F` | `uint32` | `[0x800EDB74]` | Generic screen-transition allocation. Its destructor clears this root after freeing it. |
| `S` | `uint32` | `[0x800EDC18]` | Active scripted-sequence allocation; nullable between sequences. |
| `L` | `uint32` | `[0x800EE978]` | Level-local data. **Its layout changes with the loaded level.** |
| `B` | `uint32` | `[0x80021508]` | Shared Kardok/Zarok actor root in `ZL.BIN`, header 25 only. Not a global boss pointer for other levels. |
| `D` | `uint32` | `[B + 0x08]` | Definition of that boss actor; identifies its class through `D + 0x88`. |

An aligned pointer inside RAM is not proof that its allocation is still owned.
The fatal-to-title capture shows `G` retaining its old address while its freed
bytes are reused. A live actor is needed for actor/physics reads, but persistent
inventory on the map does not require an actor.

**Evidence labels:** **Observed** means captured during native execution, with
any laboratory setup stated. **Code-backed** means established from native code
or static tables, without necessarily exercising every use. Unresolved meanings
are identified in their rows. Detailed experiments are indexed in
[the memory research directory](research/memory/README.md).

## Global game state

| Address | Type | Field | Meaning / verification |
| --- | --- | --- | --- |
| `0x80010000` | `uint32` | Loaded overlay header | Observed on boot, title, gameplay and map transitions. Separate from the game-level index. Can retain an old header during loading or change before the new screen is ready. |
| `0x800EEE2C` | `int32` | Current game-level index | Index into the 25-entry level table. Can retain the previous level on the map. |
| `0x800EEE30` | `int32` | Requested / next level index | Used by native level dispatch; also exercised in explicitly labelled laboratory level requests. |
| `0x800EEE64` | `int32` | Main mode | Observed: 2 menu, 3 gameplay/loading, 4 map/initialization, 5 movie dispatch, 9 title sequence. Mode 3 alone does not establish live player data. |
| `0x800EEE70` | `int32` | Gameplay submode | 0 normal, 1 tested pause/hard UI, 2 inventory/book/other UI. Native code also handles 3. Submode 2 alone does not identify inventory. |
| `0x800EEE60` | `uint32` | Logical update counter | Held during tested pause and parts of loading. Not a Vsync count or elapsed time. |
| `0x800EDDAC` | `uint32` | Vblank counter | Video-timing counter used in the captures; distinct from logical updates. |
| `0x800EEE24` | `uint32` | Game flags | Bit `0x80`: transition pending. UI coordination also uses `0x02`, `0x04`, `0x08`, `0x10`. Other bits need their own interpretation. |
| `0x800EEE6C` | `int32` | Gameplay result / dispatch request | Observed 5 on natural Crypt exit, 6 in a fatal flow; 4 used for labelled native level-dispatch setup. Result values are not screen-ready flags. |
| `0x800EEF00` | `uint16` | Music track word | Includes sentinel `0xFFFF`. Tracks 16 and 21 were observed in final encounters. This is not a universal boss-death or sequence-position field. |
| `0x800EEEF8` | `int32` | Audio/resource transition state | Code-backed audio/level-transition role. Final-level code waits for value 8 in particular phases. Former “cutscene state” labels were guesses. |
| `0x800EEEFC` | 16-bit word | Track request | Code-backed audio request word; not a cutscene frame counter. |
| `0x800EEEFE` | 16-bit word | Queued track | Code-backed audio queue word; not a cutscene frame counter. |

Natural Crypt completion exposed separate moments: result 5, entry into main
mode 4, then header 26. Header 26 establishes map-module presence, not map UI
readiness. See [the exit capture](research/memory/evidence/crypt-exit-events.json).

## Title and New Game state

These fields belong to the live title allocation in main mode 2/header 24.
Their bytes are not title state after that owner or overlay has gone away.

| Address | Type | Field | Meaning / verification |
| --- | --- | --- | --- |
| `T + 0x00` | `int32` | Title flow | State 1 updates active UI; state 2 returns New Game to the main dispatcher. States 0, 1 and 2 were observed. |
| `T + 0x180` | `uint32` | Update callback | `0x800142A8` is the checked main-menu updater. Other title screens use different callbacks. |
| `T + 0x184` | `uint32` | Finish callback | `0x80014630` observed with that main-menu updater. |
| `T + 0x188` | `int32` | UI countdown | Observed -1 while the tested menu was active and 0 during its completion flow. Not the New Game button itself. |
| `T + 0x190` | `int32` | Menu selection | 0 New Game; 1 Load Game in the native branch. Selection 0 observed. This replaces the old widget-state interpretation of `0x80019134`. |
| `F + 0x00` | `uint32` | Transition flags | Constructor stores requested flags OR `0x01`; New Game initially produced `0x09`. The title updater tests completion bit `0x02`. |
| `F + 0x04` | `uint32` | Transition kind | New Game acceptance queues kind 1 from the checked main-menu branch. Idle/attract produced kind 2 in the control. |
| `F + 0x08` | `uint32` | Transition argument | New Game's checked call passes 1. Meaning is specific to the transition kind. |
| `F + 0x14` | `uint32` | Transition completion/result field | Constructor clears it; the title updater waits for value 1 before setting title flow 2. |

The main-menu updater accepts selection 0 by calling `0x8004E7B0(1, 1, 8)`.
In the recorded trial, a Cross input at Vsync 1 was followed by the transition
packet at 3 and title flow 2 at 124. These are acceptance and later completion,
not interchangeable button timestamps. The packet is generic: its values only
identify this event together with title/menu ownership.

Evidence: [New Game request fields and controls](research/memory/evidence/newgame-request-events.json).

## Player state and health

| Address | Type | Field | Meaning / verification |
| --- | --- | --- | --- |
| `G + 0x00` | `int32` | Current health | Native initial value 300; damage, refill `28 → 300` and fatal `64 → 0` observed. Authoritative player health. |
| `G + 0x04` | `int32` | Reserve energy | Bottle energy in health units. Native pickup added 300; automatic refill consumed `300 → 0`. |
| `G + 0x08` | `int32` | Reserve capacity | Owned bottle capacity in health units. One pickup changed `0 → 300`; consuming reserve did not remove capacity. |
| `G + 0x0C` | `int32` | Equipped weapon enum | Observed 18 initially, 0 Small Sword, 3 Throwing Daggers. **Not an inventory index:** daggers are inventory index 5. |
| `G + 0x530` | `uint32` | Player actor pointer | Native registration/unregistration observed. Different levels allocated Dan at different addresses. |
| `G + 0x6A0` | `int16` | Death/revival substate | Native `0 → 1` observed after fatal HP zero. The old “game-over flame” name does not establish animation timing or every reset path. |
| `0x800F1648` | `int32` | HUD health mirror | Callback copy of `G + 0x00`; observed stale/zero with real health 300. Not authoritative health. |

Derived bottle values: owned bottles = integer `reserveCapacity / 300`; full
bottles = integer `reserveEnergy / 300`; remaining partial-bottle energy =
`reserveEnergy % 300`. The old high-byte reads truncate these integers.
Multiple-bottle/partial-reserve transitions have not all been exercised.

Dan's generic actor HP at `A + 0x5A` is **not** his live health. His definition at
`0x800D50B0` includes an initial 400, while live player health is stored in `G`.

Evidence: [native health events](research/memory/evidence/health-events.json),
[fatal return and freed-memory reuse](research/memory/evidence/fatal-lifecycle-events.json).

## Inventory and level progress

Inventory has **43 records, four bytes apart**, starting at `G + 0x80`.
For index `i`, the primary value is `uint16 [G + 0x80 + i × 4]`; the adjacent
`uint16` at `+2` is a separate field, not the upper half of one 32-bit quantity.

`0xFFFF` means unavailable in the initialized/pickup cases. Zero is item-specific:
a Small Sword primary value of 0 means owned, whereas gold 0 is an empty total.
Weapon ownership, ammunition, durability and key-item values are not one common
boolean scheme. The complete layout and names are code-backed; only the noted
pickup/use transitions have been observed.

| Index | Item | Primary address (`uint16`) | Details |
| --- | --- | --- | --- |
| 0 | Small Sword | `G + 0x80` | Observed pickup: `0xFFFF → 0` (owned). |
| 1 | Broad Sword | `G + 0x84` | — |
| 2 | Magic Sword | `G + 0x88` | Corrected primary address; not the Club's secondary halfword. |
| 3 | Club | `G + 0x8C` | — |
| 4 | Hammer | `G + 0x90` | — |
| 5 | Throwing Daggers | `G + 0x94` | Observed pickup to 100, then native ammunition use 100→92. |
| 6 | Axe | `G + 0x98` | — |
| 7 | Chicken Drumstick | `G + 0x9C` | — |
| 8 | Crossbow | `G + 0xA0` | — |
| 9 | Longbow | `G + 0xA4` | — |
| 10 | Flaming Longbow | `G + 0xA8` | — |
| 11 | Magic Longbow | `G + 0xAC` | — |
| 12 | Spear | `G + 0xB0` | — |
| 13 | Lightning | `G + 0xB4` | — |
| 14 | Good Lightning | `G + 0xB8` | — |
| 15 | Chaos Rune | `G + 0xBC` | — |
| 16 | Earth Rune | `G + 0xC0` | — |
| 17 | Moon Rune | `G + 0xC4` | — |
| 18 | Star Rune | `G + 0xC8` | Observed pickup `0xFFFF → 1`; gate consumption `1 → 0xFFFF`. |
| 19 | Time Rune | `G + 0xCC` | — |
| 20 | Sheet Music | `G + 0xD0` | — |
| 21 | Skull Key | `G + 0xD4` | — |
| 22 | Lake Key | `G + 0xD8` | — |
| 23 | Harvester Part | `G + 0xDC` | — |
| 24 | Amber | `G + 0xE0` | — |
| 25 | Soul Helmet | `G + 0xE4` | — |
| 26 | Shadow Artefact | `G + 0xE8` | — |
| 27 | Shadow Talisman | `G + 0xEC` | — |
| 28 | Witch Talisman | `G + 0xF0` | — |
| 29 | Crucifix | `G + 0xF4` | — |
| 30 | Crucifix Cast | `G + 0xF8` | — |
| 31 | Safe Key | `G + 0xFC` | — |
| 32 | Landlord's Bust | `G + 0x100` | — |
| 33 | Arm | `G + 0x104` | Native initialized primary is 1. |
| 34 | Copper Shield | `G + 0x108` | — |
| 35 | Silver Shield | `G + 0x10C` | — |
| 36 | King Peregrin's Crown | `G + 0x110` | — |
| 37 | Chalice Of Souls | `G + 0x114` | HUD fill scaled to `0x1000`, not collected-chalice total. |
| 38 | Gold Pieces | `G + 0x118` | Gold quantity. |
| 39 | Dragon Gem | `G + 0x11C` | — |
| 40 | Gold Shield | `G + 0x120` | — |
| 41 | Dragon Armour | `G + 0x124` | — |
| 42 | Life Bottle | `G + 0x128` | Inventory entry; bottle capacity/energy are separate fields. |

The Life Bottle inventory entry is not the authoritative bottle count; capacity
and reserve are the fields at `G + 0x08` and `G + 0x04`.

### Level progress and chalices

| Address | Type | Meaning / verification |
| --- | --- | --- |
| `G + 0x34 + levelIndex` | `uint8` | One progress byte per level, 25 bytes through `G + 0x4C`. Bit `0x01`: completion; first Crypt completion observed at `G + 0x3A`. Replays need not change a set bit. |
| Same progress byte, bit `0x02` | Bit | Chalice collected for that level, set by the native collection path. The ending dispatcher counts this bit across all 25 bytes. Collection/count transitions remain code-backed rather than runtime-verified. |
| `G + 0x114` | `uint16` | Current Chalice of Souls HUD fill, scaled to `0x1000`. Not the number of collected chalices. |
| `G + 0x118` | `uint16` | Gold primary value in the inventory table. |

Evidence: [all 43 descriptors](research/memory/evidence/inventory-table.json),
[natural pickups](research/memory/evidence/pickup-events.json),
[dagger ammunition use](research/memory/evidence/dagger-use-events.json).
The Rune Smuggle workflow remains separately unverified; the Star Rune's
primary address and pickup/consumption values are established.

## Position, physics and attachments

Actor coordinates use signed world units. Physics positions use signed 16.16
fixed point: the integer represents world units multiplied by 65536. Negative Y
was observed during jumps; it is not an unsigned height.

| Address | Type | Field / meaning |
| --- | --- | --- |
| `A + 0x24 / 0x28 / 0x2C` | `int32` × 3 | Actor X/Y/Z. Walking and jump/landing changes observed. |
| `A + 0x50` | `uint32` | Actor flags. `0x08000000`: final-level train scripting; `0x10000000`: platform/attachment following. These are different relationships. |
| `A + 0x80` | `uint32` | Physics pointer `P`. |
| `A + 0x88` | `uint32` | Attachment-data pointer, when an attachment is present. |
| `P + 0x30 / 0x34 / 0x38` | `int32` × 3 | Current fixed-point X/Y/Z. Correspondence with actor coordinates observed. |
| `P + 0x20 / 0x24 / 0x28` | `int32` × 3 | Another fixed-point position vector, copied by the native setter. Its exact role in every physics branch is unresolved. |
| `P + 0x78 / 0x7A / 0x7C` | `int16` × 3 | Short XYZ copies written by one setter path. Not established as universal respawn coordinates. |
| `P + 0x48 / 0x4C / 0x50` | `int32` × 3 | Motion fields cleared by the setter's reset path; exact component roles/units remain under investigation. |
| `P + 0xBC / 0xC0 / 0xC4` | `int32` × 3 | Additional motion fields cleared by that reset path. |
| `P + 0xB8` | `int16` | Also cleared by the reset path; full semantics unresolved. |
| `G + 0x68C` | `int16` | Y copy written for the registered player under a definition condition; not a universal ground-height guarantee. |
| `G + 0x670` | `uint32` | Combined movement flags. Walking bit `0x100` observed; the complete bitfield is not mapped. |
| `G + 0x6B0` | `int32` | Idle input-update counter; increments at rest, including camera-only intervals. |
| `G + 0x6B8` | `int32` | Separate running counter in native code; running transitions not runtime-verified. |
| `G + 0x6BC` | `int32` | Walking input-update counter; observed increments while walking and reset at rest. |
| `G + 0x6DA / 0x6DC / 0x6DE` | `int16` × 3 | Coordinates written by final-level train scripting; not general actor position. |

For attachment data `Q = uint32 [A + 0x88]`:

| Address | Type | Meaning |
| --- | --- | --- |
| `Q + 0x00` | `uint32` | Parent object pointer. |
| `Q + 0x04` | `int16` | Parent matrix/part selector. |
| `Q + 0x08 / 0x0A / 0x0C` | `int16` × 3 | Local offset vector. |
| `Q + 0x10 / 0x12 / 0x14` | `int16` × 3 | Last-position vector consumed/updated by attachment routines. |
| Parent `+ 0x34`, bit `0x10` | Bit in `uint8` | Participates in a submode-2 condition that skips particular parent-matrix work. This is code-backed, not a proven collision exploit. |

Native position setter `0x800485EC` updates multiple copies. Platform-follow
routine `0x800468EC` can overwrite a changed world position from the attachment;
`0x80046A9C` can reassert following. A changed coordinate or cleared flag alone
does not establish a lasting teleport or detachment.

Details and evidence: [physics and attachment reference](research/memory/notes/physics.md).

## UI and scripted sequences

| Address | Type | Meaning / verification |
| --- | --- | --- |
| `0x800EDBD8` | `int32` | Live UI stack count used by coordinator `0x80063F9C`. |
| `0x800EF390 + i × 4` | `uint32` | Window pointer in that stack. |
| `0x800EDBE8` | `int32` | Blocking-UI count/state tested by the coordinator. Zero selects normal submode; this address is not itself a window pointer. |
| Window `+ 0x44` | `uint16` | Window flags. Coordinator excludes windows with `0x60` set from its active-window search; `0x20` participates in closing behavior. |
| `0x800DA358` | Static definition | Inventory class identity used by native UI classification and cleanup. Submode 2 by itself also covers other UI. |
| `0x800EF3A0 + i × 0x0C` | 12-byte record | Four UI request slots. `uint32 +0`: class/request ID; `uint16 +4`: flags; `int16 +0x0A`: delay. |
| Request flags `0x08 / 0x10` | Bits in `uint16` | Closing/completed and reopen-latch behavior in the checked inventory request path. A pending request differs from a live window. |
| `S + 0x20` | `uint32` | Sequence flags. |
| `S + 0x24` | `uint32` | Sequence descriptor pointer. |
| `S + 0x34` | `uint32` | Interpreter timeline/counter. Not interchangeable with Vsync, logical game updates or audio state. |

The coordinator derives submode from UI ownership and class. In its classified
branches, game-flag `0x04` identifies inventory, `0x08` another UI class,
`0x02` other non-hard UI and `0x10` hard UI. Scene-start cleanup can close an
inventory window or cancel a pending request; a reopen latch can survive the
old window's cleanup in the observed buffering tests.

Evidence: [UI cleanup ownership](research/memory/evidence/inventory-cleanup-validation.json),
[native inventory-buffer observations](research/memory/evidence/native-inventory-buffer.json).

## Boss health and final encounters

### HUD bar versus actor health

| Address | Type | Field |
| --- | --- | --- |
| `0x800F170C` | `int32` | Boss HUD active flag. |
| `0x800F1710` | `int32` | Boss HUD health input copied from the actor. |
| `0x800F1714` | `int32` | Renderer cache of clamped input. **Not authoritative boss HP.** |
| `0x800F171C` | `int32` | HUD maximum. |

Pumpkin captures had actor/input HP 1100 with an active HUD and cache 0 for 400
samples. Kardok also showed cache 0 while actor/input HP remained 1500. In the
Zarok last-hit capture, actor death preceded the HUD input/cache change by two
Vsyncs. A zero cache can therefore mean an unpopulated, stale or clamped display
value rather than a newly defeated boss.

### Kardok and Zarok actor data — header 25 only

These fields use `B` and `D` from the pointer-root table. Their owner is final
level index 23, overlay `ZL.BIN`/header 25, in gameplay mode 3.

| Address | Type | Field / meaning |
| --- | --- | --- |
| `0x80021508` | `uint32` | Shared current boss actor pointer. Both constructors assign it. |
| `B + 0x08` | `uint32` | Actor definition pointer `D`. |
| `B + 0x0C` | `uint32` | Actor-record pointer; its first `uint32` is the registered record ID. This differs from a script object ID. |
| `B + 0x5A` | `int16` | Live boss HP. Signed: a native Zarok killing blow produced -8. |
| `B + 0x5C` | `uint8` | Actor action/state. Meaning belongs to the actor's class. |
| `B + 0x90` | `uint32` | Actor-private allocation. |
| `D + 0x88` | `uint32` | Constructor address used to distinguish Kardok from Zarok. |

| Encounter | Level phase | Definition | Constructor | Registered actor ID | Observed native death |
| --- | --- | --- | --- | --- | --- |
| Kardok | 6 | `0x8001CDD4` | `0x80011F24` | `0xB3C4` | HP `6 → 0`, action 11, HUD active `1 → 0`. |
| Zarok | 8 | `0x8001D05C` | `0x80018784` | `0xB45D` | HP `6 → -8`, action 25. HUD active remained 1. |

Both bosses registered with HP 1500. Kardok also took 113 native 6-HP damage
events, reaching 822 without boss HP writes. The death-boundary tests then used
**explicit 6-HP laboratory setup** and player-health/ammo assistance. Native
attacks, rather than action/phase writes, caused the recorded deaths. They are
not unassisted full-fight results. Zarok's clean repeat passed; two executions
ended in byte-identical full RAM.

Phase 8 starts **before** the shared pointer changes from Kardok to Zarok.
A phase alone or a nonpositive read from an unowned pointer does not identify a
Zarok death. The verified actor class and death action distinguish the captured
boundary from pre-spawn zero; no legacy 65-HP threshold is inherent to these
fields.

Zarok callback `0x80019CE0` accepts ordinary event-type-1 damage when private
state `int32 [[B + 0x90] + 0]` is nonzero or action is 17. The shield can reject
hits during the other states. This damage gate is separate from health and the
death action.

Evidence: [Kardok arrival](research/memory/evidence/kardok-arrival-events.json),
[native damage](research/memory/evidence/kardok-damage-events.json),
[Kardok death and actor handoff](research/memory/evidence/final-boss-events.json),
[Zarok death and HUD lag](research/memory/evidence/zarok-death-events.json).

### Final-level controller and soldiers

`L` has this layout in **Zarok's Lair only**:

| Address | Type | Meaning |
| --- | --- | --- |
| `L + 0x00` | `uint32` | Phase index: 0 entrance, 1 introduction, 2 army battle, 3 result, 4 ally cleanup, 5 transition, 6 Kardok sequence, 7 transition, 8 Zarok sequence. Introduction/death animations can be included in an encounter phase. |
| `L + 0x04` | `int32` | Army outcome in phase 2: 0 loss when no friendlies are counted; 1 victory when friendlies remain and no enemies are counted. A stored 1 outside this phase is not a fresh result. |
| `L + 0x08` | `uint16` | Friendly-slot cleanup index in phase 4. |
| `L + 0x0A` | `int16` | Later-phase countdown, set to 5 at particular transitions; not a clock or outcome. |
| `L + 0x0C` | `int32` | Sound handle, initialized to -1. |
| `L + 0x10` | `int32` | Separate sound/low-health voice handle, initialized to -1. Earlier trace labels incorrectly used `+0x0C` for this voice gate. |
| `0x800EE934 + flagIndex` | `uint8` | Script-flag region. Phase lookup at `0x8001C92C` contains indices `11, 10, 13, 14, 15, 18, 17, 18, 19`. |
| `0x800EE941` | `uint8` | Army result-ready flag; both victory and loss paths can set it. Outcome is at `L + 0x04`. |
| `0x800EE945` | `uint8` | Flag 17, observed after Kardok's death animation and before phase 7. Later than the killing blow. |
| `0x800EE946` | `uint8` | Flag 18, reused by particular transition phases. |
| `0x800EE947` | `uint8` | Flag 19, checked by the final phase before exit result 5. Not established as the immediate killing-blow timestamp. |
| `0x8001C950 + slot × 0x0C` | 12-byte row | Eight friendly registration rows; actor pointer at row `+8`. Slot-0 actor pointer is `0x8001C958`. |
| `0x8001C9B0 + slot × 0x0C` | 12-byte row | Eight enemy registration rows; actor pointer at row `+8`. Slot-0 actor pointer is `0x8001C9B8`. |
| `0x800EE888` | `uint32` | Runtime actor-list head used by the army controller; sentinel `0x800EE884`. Next link at node `+4`, record pointer at node `+0x0C`. |

For soldiers, signed HP is at actor `+0x5A`, action at `+0x5C`, private pointer
at `+0x90`, short delay at private `+4`, and animation byte at
`[actor + 0x74] + 0x20`. The controller counts record type 3 (`int16 record+4`),
with friendly subtype 0 versus enemy subtype (`uint8 record+6`). Authored rows,
registered pointers, positive-HP actors and counted actors are different sets.

Native army outcome 1 was observed with five surviving allies in a labelled
laboratory-derived state. That outcome establishes army-controller victory,
not successful completion of the reported despawn glitch or its later handoff.
Detailed actor/RNG findings: [final-combat reference](research/memory/notes/final-combat.md).

### Pumpkin-specific level data

In The Pumpkin Serpent (level index 10/header 20), the same `L` root instead has
`int32 L+0x0C` phase and `int32 L+0x10` wake/gate data; gate value 9 was observed
before a labelled wake setup. These offsets are not the final-army layout.
Pumpkin definition `0x8001AD48`, constructor `0x80013D70`, initializer
`0x80013EE4`, updater `0x8001416C` and actor HP at `+0x5A` are code-backed;
actor/input/max HP 1100 was observed. Action 11 disables its bar in native code,
but Pumpkin damage/defeat was not reproduced in this audit.

## Shared RNG

| Address | Type | Meaning |
| --- | --- | --- |
| `0x800F3994` | `uint32` | Shared RNG state. |
| `0x800A43B8` | Routine | Updates the state and returns a 15-bit output. |
| `0x800EE094` | `uint32` | Pool pointer used by separate coordinate/phase callback `0x800283D0`; exact visual identity unresolved. Its draws are not soldier-attack draws. |

Native recurrence: `next = (state × 0x41C64E6D + 0x3039) mod 2^32`;
output: `(next >> 16) & 0x7FFF`.

The stream is shared by AI, sound/effects and level callbacks. Verified final-army
consumers include friendly initial HP `500 - (output & 0xFF)` (245–500), attack
animation/delay selection, hit/block decisions and low-health voice checks.
Input-dependent consumption and fixed-state repeatability do not establish a
practical full-game manipulation. Further RNG-route work is benched.

Evidence: [RNG validation](research/memory/evidence/rng-crypt-validation.json),
[consumer details](research/memory/notes/final-combat.md#what-rng-directly-affects).

## Native tables and routines

These are code/static-data addresses, not live health or inventory allocations.
Overlay-local entries only have their stated meaning while that overlay is loaded.

| Address | Kind | Meaning |
| --- | --- | --- |
| `0x800D9F48 + i × 0x14` | Static table | 43 inventory descriptors. |
| `0x800D98BC` | Static table | Inventory localization-string pointer table. |
| `0x800DA674 + levelIndex × 0x64` | Static table | 25 level records, 100 bytes each; `uint32 +0x4C` is overlay-descriptor index. |
| `0x800DA4E4` | Static table | Level-name label pointers. |
| `0x800CD9E8 + descriptorIndex × 0x20` | Static table | Overlay descriptors; descriptor index is not a loaded header ID. |
| `0x800EDE30` | `uint32` | Runtime overlay-descriptor pointer used by native code. |
| `0x8005D92C` | Routine | Inventory initialization. |
| `0x8005DE00` | Routine | Inventory value resolver. |
| `0x8005E104` | Routine | Inventory consumption. |
| `0x8006B034` | Routine | Equipped-weapon enum setter. |
| `0x80069BC0 / 0x80069C10` | Routines | Player registration / unregistration. |
| `0x800485EC` | Routine | Actor/physics position setter. |
| `0x800468EC / 0x80046A9C` | Routines | Platform-follow update / attachment update. |
| `0x800762B0` | Routine | Player health HUD copy/update. |
| `0x80077398` | Routine | Bar renderer; clamps input and updates its cached value. |
| `0x80063F9C` | Routine | UI coordination and submode selection. |
| `0x80064270 / 0x800648A8` | Routines | Scripted-sequence start / interpreter. |
| `0x8005E37C / 0x80062400` | Routines | UI request/reopen path / class cleanup. |
| `0x8004E7B0 / 0x8004E9F0 / 0x8004EC8C` | Routines | Transition request / allocation initialization / free-and-clear. |
| `0x8001203C / 0x800142A8` | `TL.BIN` routines | Title flow dispatcher / main-menu updater. |
| `0x800119B4 / 0x80011AA0` | `ZL.BIN` routines | Final-level initialization / phase controller. |
| `0x80016894 / 0x80016B88 / 0x80016F14` | `ZL.BIN` routines | Skeleton constructor / action initializer / update. |
| `0x80016AAC` | `ZL.BIN` routine | Skeleton collision hit/block callback. |
| `0x80047210 / 0x800458E8` | Routines | Generic hit/event handler / native damage handler. |

## Level IDs

Three namespaces coexist: **game-level index**, **loaded header ID** and
**overlay-descriptor index**. Crystal Caves, for example, uses index 8, header 4
and descriptor 2. Values below come from native executable/overlay metadata,
not gameplay visits to every level.

| Game index | Level | Header ID | Overlay | Descriptor index |
| --- | --- | --- | --- | --- |
| 0 | Title metadata | 24 | `TL.BIN` | 21 |
| 1 | The Graveyard | 12 | `GY1.BIN` | 10 |
| 2 | Return to the Graveyard | 13 | `GY2.BIN` | 11 |
| 3 | Cemetery Hill | 5 | `CH.BIN` | 3 |
| 4 | The Hilltop Mausoleum | 7 | `DC.BIN` | 5 |
| 5 | Scarecrow Fields | 21 | `SF.BIN` | 18 |
| 6 | Dan's Crypt | 6 | `CR.BIN` | 4 |
| 7 | The Ant Caves | 2 | `AC.BIN` | 0 |
| 8 | The Crystal Caves | 4 | `CC.BIN` | 2 |
| 9 | Pumpkin Gorge | 19 | `PG.BIN` | 16 |
| 10 | The Pumpkin Serpent | 20 | `PS.BIN` | 17 |
| 11 | The Sleeping Village | 22 | `SV.BIN` | 19 |
| 12 | Pools Of The Ancient Dead | 18 | `PD.BIN` | 15 |
| 13 | The Asylum Grounds | 3 | `AG.BIN` | 1 |
| 14 | Inside The Asylum | 16 | `IA.BIN` | 13 |
| 15 | The Enchanted Earth | 8 | `EE.BIN` | 6 |
| 16 | The Gallows Gauntlet | 10 | `GG.BIN` | 8 |
| 17 | The Haunted Ruins | 15 | `HR.BIN` | 12 |
| 18 | Hall of Heroes | 14 | `HH.BIN` | 23 |
| 19 | The Ghost Ship | 11 | `GS.BIN` | 9 |
| 20 | The Entrance Hall | 9 | `EH.BIN` | 7 |
| 21 | The Time Device | 23 | `TD.BIN` | 20 |
| 22 | The Lake | 17 | `LA.BIN` | 14 |
| 23 | Zarok's Lair | 25 | `ZL.BIN` | 22 |
| 24 | *Programmers's Playground | 12 | `GY1.BIN` | 10 |

Main-menu interpretation uses mode 2/header 24. The world-map module uses
header 26/main mode 4 and has no separate game-level index in this table; the
previous level index can persist. Header 27 was observed during startup and
therefore does not by itself mean run completion. Programmer's Playground
shares Graveyard's header 12, so header ID alone cannot distinguish them.

Source: [complete level records and overlay hashes](research/memory/evidence/level-table.json).

## Corrections to older address lists

Older emulator host offsets are not PS1 addresses. Resolved heap addresses below
are examples from `G = 0x800F8174`, not permanent replacements for pointer paths.

| Old read / label | Correction |
| --- | --- |
| `0x800F6E83`, “newGamePressed” | Sound-library bookkeeping written by `_SsVmVSetUp` at `0x800BC99C`. Not a New Game flag. Title selection/transition fields are listed above. |
| `0x80019134`, “newGameHighlighted” | Overlay-local widget-state lead, not the main menu's actual selection. The native selection is `int32 T+0x190`. |
| `0x800F1648`, byte “currentLife” | A stale-capable **32-bit HUD mirror**. Player health is `int32 G+0x00`; a byte also truncates 300 to 44. |
| `0x800F8179 / 0x800F817D`, bottle counts | Bytes inside reserve/capacity integers. Full fields are `int32 G+0x04 / G+0x08`, in 300-unit bottle amounts. |
| `0x800F8814`, byte “isGameOverFlame” | Resolved `G+0x6A0`, a signed 16-bit death/revival substate. Fixed allocation and flame-timing assumptions were unverified. |
| `0x800F1714`, “bossHealth” | A 32-bit clamped HUD cache. Final bosses' real HP is signed `int16 B+0x5A`; it can be negative at death. |
| `0x800F170C`, byte “isBoss” | A 32-bit HUD-active flag, not a universal actor-life flag. Zarok's remained 1 after the captured killing blow. |
| `0x800EEF00`, byte music track | A 16-bit word with `0xFFFF` sentinel; not an event timeline. |
| `0x800F8202`, Magic Sword quantity | Second halfword of the Club record. Magic Sword primary is `G+0x88` (`0x800F81FC` in the example allocation). |
| `FF 00`, unavailable inventory | Initialized unavailable primary is `FF FF` (`uint16 65535`); other values have item-specific meanings. |
| `0x801AF6C0`, “cameraView” | Stable owner/type/meaning not established. No general camera-state claim is made here. |
| `2A8B23`, old movement pointer | Not a PS1 virtual address. Fixed per-level actor coordinates were not established as permanent allocations. |
| `L+0x0C`, final-army low-health voice handle | The checked voice gate is `L+0x10`; `L+0x0C` is a distinct sound handle. |
| `0x800EEEF8 / 0x800EEEFC / 0x800EEEFE`, cutscene state/frame labels | Audio/resource transition and request/queue fields. Sequence counter is at `S+0x34` with its own owner. |

## Evidence and limits

The address research combines native code/static tables with finite, isolated
PCSX-Redux captures. Initial validation covered 127 full 2 MiB captures; later
pickups, lifecycle, UI, army and boss tests add event-specific evidence. Shared
starting states and laboratory setup are stated in the linked records; they
are not independent full-game playthroughs.

Kardok/Zarok death boundaries are observed with labelled last-hit setup. Pumpkin
defeat, every inventory item's use, all-level/replay transitions and the Rune
Smuggle workflow are not all runtime-verified. Windows emulator integration is
also untested. A raw zero, plausible pointer or successful process exit does not
establish the meaning of a game event.

- [Memory research and evidence index](research/memory/README.md)
- [Current trigger-verification status](research/memory/notes/asl-readiness.md)
- [Movement/attachment details](research/memory/notes/physics.md)
- [Final-combat actor and RNG details](research/memory/notes/final-combat.md)
- [Glitch questions and observation limits](research/memory/notes/glitches.md)
