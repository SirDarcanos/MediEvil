# USA ASL verification status

This is a watch/trigger audit, not a replacement ASL or a claim of complete coverage.
Original ASLs remain unchanged. Windows LiveSplit/ePSXe integration is untested.
RNG manipulation research is benched. Work does not include `LiveMap/`.

Addresses below are PS1 virtual addresses. Pointer offsets are byte offsets.
`G = *(uint*)0x800EDB3C`, `T = *(uint*)0x800EDC1C`,
`F = *(uint*)0x800EDB74`, `L = *(uint*)0x800EE978`,
`B = *(uint*)0x80021508`.

## Core watches

| Purpose | Typed read | Evidence and limits |
| --- | --- | --- |
| Loaded overlay header | `uint 0x80010000` | Observed transitions. Header 26 alone does not establish map UI readiness. |
| Current level index | `int 0x800EEE2C` | Distinct from overlay header; use `../evidence/level-table.json` for correspondence. |
| Main mode | `int 0x800EEE64` | Menu 2, gameplay/loading 3, map 4, movie 5, title flow 9. Not an allocation-liveness test by itself. |
| Native result | `int 0x800EEE6C` | Crypt exit 5 and fatal result 6 observed. Other exits/replays need controls. |
| Transition flags | `uint 0x800EEE24` | Bit `0x80` is transition pending; do not equate it with every form of loading. |
| Player actor | `uint [G]+0x530` | Native registration/unregistration observed. Reject non-gameplay ownership and transitions. |
| Death substate | `short [G]+0x6A0` | Native fatal transition 0→1 observed. Rune-smuggle reset exception remains unverified. |
| Star Rune primary quantity | `ushort [G]+0xC8` | Natural pickup 1 and consumption `0xFFFF` observed. Not an absolute heap address. |
| Music track | `ushort 0x800EEF00` | `0xFFFF` sentinel. Track changes are not established universal defeat/start signals. |

**Do not treat a non-null `G` as proof of ownership.** Fatal-to-title cleanup frees
it without clearing the root; the heap bytes are subsequently reused.

## New Game acceptance

The checked title updater at `0x800142A8` reads the actual selection at
`int [T]+0x190`: 0 is New Game, 1 is Load Game. Accepting selection 0 calls
`0x8004E7B0(1,1,8)`. The constructor at `0x8004E9F0` stores:

- `uint [F]+0`: flags = 9 initially (`8 | 1`).
- `uint [F]+4`: transition kind = 1.
- `uint [F]+8`: transition argument = 1.

This is a **generic transition packet**, not a dedicated New Game flag. Guard
main mode 2, header 24, live title main-menu ownership, `int [T]+0 == 1`,
selection 0, and the packet's kind/argument/active flag. Require a fresh guarded
acceptance edge. Do not read title fields after the title overlay is replaced.

`../evidence/newgame-request-events.json` records a Cross request at probe Vsync 1, the
accepted packet at 3, and title flow 2 only at 124. Idle/attract and navigation
controls did not match the guarded packet. Cold-menu-entry negatives remain
useful for checking the complete trigger. Load Game was proposed only as an
additional auto-start negative control, not a split or a delivery requirement;
the save/load detour was stopped after scope clarification.
`0x800F6E83` is sound bookkeeping, not an authoritative New Game button flag.

## Final encounters

| Watch | Status |
| --- | --- |
| `uint [L]+0` phase; `int [L]+4` army outcome | Native phase-2 outcome 1 verified in victory capture. Outcome is meaningful in phase 2; do not use a persistent 1 without phase/edge guards. |
| `uint 0x80021508` current boss actor | Code-backed shared root: constructors `0x80011F24` and `0x80018784` both assign it. A pointer replacement is not a kill. |
| `short [B]+0x5A` HP; `byte [B]+0x5C` action | Kardok observed in phase 6, entity `0xB3C4`, definition `0x8001CDD4`. Native attacks caused 113 decrements of 6: HP 1500→822, with no boss HP writes. See `../evidence/kardok-damage-events.json`. Kardok's native killing blow after explicit 6-HP setup produced HP0/action11/HUD active0; see `../evidence/final-boss-events.json`. Zarok's sword killing blow produced HP6→−8/action25, with HUD active still1; see `../evidence/zarok-death-events.json`. |
| `uint [B]+8` definition; `uint [definition]+0x88` constructor | ZL binary ties definition `0x8001CDD4` to constructor `0x80011F24`, and `0x8001D05C` to `0x80018784`. Use owner/class guards, not pointer plausibility alone. |
| HUD: `int 0x800F170C`, input `int 0x800F1710`, cache `int 0x800F1714`, max `int 0x800F171C` | Kardok arrival showed active 1 and input/max 1500, but cache reached 0 with actor HP still 1500. Pumpkin also showed actor/input 1100 with cache 0: cache is not authoritative HP. |

The first assisted Kardok preparation reached the encounter but timed out
because its stop predicate incorrectly expected script object `0xB348` as the
combat actor ID. This was a probe bug, not a game crash or a completed capture.
The corrected capture passed at Vsync 8305, with 120 matching arrival samples;
see `../evidence/kardok-arrival-events.json`. The final RAM also confirms definition
constructor `0x80011F24`. Kardok's later last-hit check verified the native death edge at Vsync 309,
script flag17 at 669, phase7 at 671 and phase8 at 810. Zarok registered at 3396
(entity `0xB45D`, definition `0x8001D05C`, constructor `0x80018784`, pre-setup
HP1500). **Phase8 begins before the shared root changes owner**: reject the
old Kardok actor during handoff.

Zarok's clean last-hit repeat passed: native sword damage at Vsync62 changed
signed actor HP6→−8 and entered action25. The renderer's HUD input/cache still
read6 at that sample; at64 input became−8 and cache clamped0. HUD active remained1.
Two executions ended in byte-identical full RAM, although the first run's
postprocessor failed on a missing `y` log field; the corrected repeat passed.
Both inherit the earlier explicit 6-HP setup and use player-health/ammo
assistance, with no boss HP/action/phase writes in the killing-blow run.
They verify a native last-hit boundary, not an unassisted full fight.
Graphics corruption is unresolved; it is not evidence of a game-specific
rendering fault.

Confirmed typed watch paths for the final encounters:

```csharp
vars.Helper.Make<short>(0x80021508, 0x5A);       // Signed actor HP; can be negative
vars.Helper.Make<byte>(0x80021508, 0x5C);        // Actor action: Kardok11, Zarok25 at sampled death
vars.Helper.Make<uint>(0x80021508, 0x08, 0x88);  // Definition constructor / encounter identity
vars.Helper.Make<uint>(0x800EE978, 0x00);        // Level-local phase; only within final-level ownership
```

Guard USA program identity, gameplay mode3, level index23, header25, valid
owned pointers and the encounter class/phase. Kardok uses phase6/constructor
`0x80011F24`; Zarok uses phase8/constructor `0x80018784`. A nonpositive HP read
alone is insufficient without ownership and native death-state checks.

`../probes/boss-prep.lua --ally-heal-setup` restores living friendly HP to 500 during
phase 2 only. It does not verify an unassisted army victory. `../probes/boss-combat.lua
--combat-supply-setup` restores living player HP and owned dagger ammunition;
by default it never writes boss HP. The separate explicit
`--boss-last-hit-setup` option lowers guarded boss HP to 6 once per boss, never
zero, then requires a native controller attack to produce death. It does not
write boss actions, phases, RNG, actor positions or ownership. All assistance
has per-write logs outside Git and must remain labelled. A last-hit test is not
an unassisted/full-fight claim.

## Final-split arming requirement

The user clarified the legacy guard's intent: zero before the boss spawns must
not count as defeat. Preserve that intent explicitly. The written
`Current == 0 && Old < 65` condition also accepts `Old == 0`; it does not alone
prove the boss was seen alive. The user clarified that the old threshold and
mechanism need not be retained if better watches make them unnecessary. The
requirement is to distinguish a real Zarok defeat from pre-spawn zeros and
unrelated owners. A verified actor class/phase plus a native death transition
satisfies the observed positive boundary without a legacy 65-HP threshold.
Zarok's sampled native death is action25 with signed HP≤0 on its own actor in
phase8. A complete ASL replacement still needs polling/negative/integration
checks; the death address and boundary now have native capture evidence.

DuckStation was optional. Its two private bootstrap attempts did not establish
a usable GDB capture (first: sandbox syntax error; second: no private listener
before timeout). Neither counts as independent gameplay verification. Further
DuckStation setup is deferred; Redux remains the working RAM-capture backend.

## Verification

The address-audit check passed 26 Python tests, including nine reference boss-signal tests covering
captured deaths, live/pre-spawn states, wrong encounter/context/version,
HUD-zero false positives and signed overkill. Python compilation, evidence JSON,
local Markdown links and the scoped diff-whitespace check also passed. These
are research-tool/reference checks, not Windows ASL execution or native tests
of every negative situation.

## Still required for complete ASL coverage

- Cold-title/menu-entry negative controls for early auto-start (no save/load work).
- Native/polling negative controls beyond the reference predicate fixtures.
- Rune-smuggle workflow/reset exception (route clarification pending); pause/quit/cancel/manual-reset controls.
- Other level exits/replays and transitions across allocations.
- Windows LiveSplit/ePSXe 2.0.0 execution and polling/timing checks.

A process exiting normally, a visible boss bar, or a plausible heap pointer does
not establish any of those objectives.
