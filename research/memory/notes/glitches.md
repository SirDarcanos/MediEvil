# Gameplay memory questions

Goal: actionable addresses, state relationships, reproducible in-game manipulations and their limits. Code analysis is a tool for answering these questions, not an effort to reconstruct the entire game. Target is the USA executable identified in the root README. Other project's scripts/data and emulator remain outside our writable scope.

## Evidence rules

- **Observed:** values/events captured in an identified private emulator run.
- **Code-backed:** a read/write or condition traced in the matching native executable/overlay; not automatically a demonstrated exploit.
- **Reported:** an inspected external account; useful for reproduction, not proof of the mechanism.
- **Hypothesis:** a proposed explanation with a specific experiment still needed.
- Laboratory state restoration, level requests and forced prerequisites are not in-game exploits. Record their writes and never use injected/derived values as natural-progression proof.
- An allowed-glitch claim needs a controller-only reproduction from a normal state and the applicable category's rules. No blanket claim that every trick is permitted in every category.

## Priority 1: Fazgul / soldier despawn

Questions:

1. Which army entities are never instantiated, frozen/inactive, or actually removed?
2. Which camera/visibility, inventory and cutscene conditions cause the difference?
3. Why can returning the camera to the gates recover soldiers or crash later phases?
4. Which effect is native game logic, and which variations depend on emulator timing?

### Inspected report

The firsthand TAS submission discussion at <https://tasvideos.org/Forum/Topics/23554>, Zarok's Lair section, describes a **console-friendly** soldier-despawn setup: inventory glitch into the cutscene, dismiss dialogue with Triangle, and close inventory after the camera returns to Dan. It reports initial center soldiers versus additional gate soldiers, off-camera freezing, and later reactivation/crash hazards. It also describes inventory buffering during the Kardok/Zarok transitions and positioning-dependent Zarok vulnerability.

This is a report to test, not an established memory mechanism. Search summaries suggesting all versions require old ePSXe conflict with the console-friendly report; the inaccessible Fandom page was not accepted as verified evidence. Do not assert an emulator-only cause from that summary.

### Existing code facts and hypotheses

- `int 0x800EEE70` distinguishes normal updates (0), tested pause (1) and observed inventory/book UI (2).
- Native loop `0x8002364C` still calls several actor/world update functions in submode 2, but omits the normal logical-counter increment and some normal-mode processing. Thus "inventory freezes everything" is false as a general code model.
- The normal branch also processes words at `0x800EEEFC` / `0x800EEEFE` and state at `0x800EEEF8`. Initial probe labels guessed these were cutscene fields. Owner tracing instead ties them to track requests and level audio/resource transitions (`0x8006D9BC`, `0x80031D70`); do not use the old log labels as established cutscene meanings.
- The actual native sequence interpreter `0x800648A8` uses the pointer at `0x800EDC18`: structure `+0x20` is a flags word, `+0x24` a descriptor pointer, and `+0x34` the incremented timeline counter. Its event opcode `0x12` writes the `0x800EE934` script-flag array; opcode `0x13` requests a textbox. It runs in both normal and inventory/book submode branches. Runtime branch effects and skip/visibility interactions still need controlled comparison.
- Inventory admission `0x80023CB0` requires `(GameFlags & 0x19F) == 0`, both player physics motion fields `+0x48` and `+0x50` zero, and actor `+0x50` bit `0x100000` clear. `0x80023AA0` calls this gate before queuing inventory definition `0x800DA358`. Our continuously moving timing sweep never opened inventory; changing its timing alone cannot establish the reported setup.
- UI coordinator `0x80063F9C` derives submode from live UI state (`0x800EDBE8` and a window stack); submode is not an independent switch to poke. `GameFlags` bits `0x02/0x04/0x08/0x10` distinguish coordinator branches. Other submode-2 UI windows are not automatically inventory.
- Actor loops `0x800410A4` / `0x80041314` skip an actor in submode 2 when actor byte `+0x34` has bit `0x10`. Therefore a running sequence VM and paused selected actors can coexist. Which soldiers/gate actors meet that condition in a successful glitch still needs runtime evidence.
- **Sequence-start cleanup:** `0x80064270` begins by calling `0x80062400(0x800DA358)`. The latter searches the four-entry request table at `0x800EF3A0`: for a matching active entry it resolves the live window and calls `0x8006226C(1)`; for a matching inactive/pending entry it replaces the request ID with `0x191`. Therefore merely opening/queuing ordinary inventory before a scene does not bypass its cleanup. The observed brief inventory overlap is not evidence of a sustained buffer glitch.
- **Buffered reopening, observed and code-backed:** request function `0x8005E37C` finds an existing matching request and, if its flags have bit `0x08`, sets bit `0x10` rather than allocating a duplicate request. Close function `0x8006226C(1)` does nothing if the window is already marked `+0x44 & 0x20`; the request's reopen bit can therefore survive scene-start cleanup of a window already closing. `0x80060E58` eventually frees the old window and clears request flag `0x01`. In [controlled traces](../evidence/inventory-cleanup-validation.json), open at Vsync 80, Triangle at 110, then Select at 114/116 yielded request flags `0x1D` through cleanup and a new live inventory at 139 while the sequence continued. Select at 118/120 did not. These timings are relative to the explicit laboratory scene-prerequisite write at 120, not a natural-route setup.
- The TAS account's general **Inventory Glitch** section specifically describes opening **and closing** inventory to obtain an action window; its **Inventory Buffering** section describes repeated opening/closing. Our one-opening probes test admission/cleanup, not that complete reported manipulation.
- **Hypothesis:** inventory/cutscene scheduling and visibility-dependent activation can diverge, leaving gate soldiers outside the normally completed sequence. Need matched actor-creation/update/removal traces, not just total counts or screenshots.

### User-supplied reproduction target

The supplied procedure uses **Select to open, then two quick Select presses to close/reopen**, with movement/jump/attack inputs during the closing/reopening action window. It reports inventory invulnerability; that protection has not yet been tested with a matched native damage event here. Our earlier Triangle-close tests established a UI queue interaction, not an exact reproduction of this Select sequence.

For soldier despawn, enter the central circular platform during that action window, leave inventory through Zarok's speech, and close it when the camera returns to Dan. Stay in the lower half while fighting the first half of the Fazguls. The supplied account says the remaining soldiers cheer if activated after the last active enemy dies, but reports a crash on console/emulators other than ePSXe 2.0.0 or older; its memory-management explanation is speculation, not established cause. On Redux our target is the **partial variant**: activate the other group before the last active enemy dies. No post-victory reactivation/crash claim has been tested here.

The user additionally reports that ePSXe HLE must be disabled to avoid some/all allied soldiers refusing to move or fight, and identifies 2.0.0 as the last crash-free version for completing the exploit. This compatibility claim is retained as **reported**, not independently executed. Our private Redux logs identify a loaded SCPH-1001 US BIOS; that is not a demonstration of equivalence to ePSXe's HLE-disabled configuration. Ordinary Redux army controls do exhibit soldier attacks/damage. Missing registration/list membership, intentional inventory-mode freezing, and populated actors failing to fight must be diagnosed separately.

Experiments: capture a normal final-arena entry, match it to inventory-open/close timing sweeps, log actor definitions/lifetimes, camera/script state and phase counters. Revisit gate visibility only in sacrificial private sessions because crashes are a reported outcome.

## Priority 2: final-combat randomness

Questions:

- What exact RNG state, transition and output does `0x800A43B8` implement?
- Which final-fight callers consume it: target selection, attacks, delays, movement, particles or audio?
- Are choices actually random, or deterministic reactions to distance, facing, visibility and timing?
- Can controller actions advance or avoid consuming the stream without disrupting the desired encounter?

**Code-backed and initially runtime-validated:** state is `uint 0x800F3994`; `0x800A43B8` advances it as `(state * 0x41C64E6D + 0x3039) mod 2^32`, returning `(state >> 16) & 0x7FFF`. A non-pausing callback before the native store at `0x800A43D8` captured 99 Crypt calls: every observed register/state transition matched the formula, with no discontinuities in that window (`../evidence/rng-crypt-validation.json`). This is not yet final-fight manipulation evidence.

The stream is not exclusively combat-related. Main-code call sites in `0x80023E38` choose distance-gated sound variants and repeat delays; `0x800534A4` uses it in primitive/effect setup, and `0x80067410` has random sound modulation paths. The Crypt trace actually reached the ambient/effect call sites. Their consumption of the same state is established; whether a particular final-arena action changes the desired NPC decision is a separate experiment.

Plan: use non-pausing execution callbacks in our own interpreter instance to log caller return address, actor context hints and pre/post state. Compare repeated identical saved-state/input trials and one-variable input changes. A seed correlation alone is not proof that a particular action manipulates the desired decision.

## Further memory-led questions

- Collision gaps, wall/corner passage, floor tests and trigger volumes.
- Signed coordinate/fixed-point wrap and why level looping sometimes kills Dan unless direction is held.
- Inventory buffering, hard-landing suppression and resurrection/helmet state interactions.
- Entity visibility/activation boundaries, spawn suppression and stale references across phases.
- Level-exit requests versus completion flags, cutscene dispatch and map/module loading.
- Item ownership/quantity/durability and imp theft/duplication state ownership.

These are investigation targets, not discoveries or certified skips. Promote each only with addresses, code support, setup/reproduction, counterexamples and observed outcomes.
