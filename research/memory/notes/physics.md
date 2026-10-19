# Movement and attachment memory

USA executable/addresses identified in the root README. These are native-code findings plus explicitly identified runtime observations; they are not automatically allowed glitches.

Let `G = *(uint*)0x800EDB3C`, `A = *(uint*)(G+0x530)`, `P = *(uint*)(A+0x80)`.

## Position is not one vector

Native setter `0x800485EC` writes:

| Owner/offset | Meaning evidenced by the setter |
|---|---|
| `int A+0x24/+0x28/+0x2C` | Actor XYZ, signed world units. Walking/jumping verified. |
| `int P+0x30/+0x34/+0x38` | Current XYZ, signed 16.16 fixed point. Read correspondence verified. |
| `int P+0x20/+0x24/+0x28` | Setter copies the current fixed-point position into this other position vector. Its precise use in every physics branch still needs tracing. |
| `short P+0x78/+0x7A/+0x7C` | Additional short XYZ updated when setter argument 4 is 1. Do not call it a general respawn checkpoint without tracing consumers. |
| `int P+0x48/+0x4C/+0x50`, `P+0xBC/+0xC0/+0xC4` | Motion fields cleared by that argument-1 path. Exact per-component roles/units need consumer analysis. |
| `short P+0xB8` | Also cleared by the reset path. |
| `short G+0x68C` | Setter copies Y here for the registered player under a specific definition condition. Not yet a general ground-height guarantee. |

Laboratory relocation attempts which changed only some copies produced large movement/falls or were overwritten. This is not evidence of an in-game teleport: the writes were injected and the intended arena position did not persist. A short coordinate's range and the 16.16 range suggest useful wrap questions, but do not establish the level-looping mechanism by themselves.

Typed LiveSplit read paths (USA/context guards still required):

```csharp
vars.playerActorFlags = vars.Helper.Make<uint>(0x800EDB3C, 0x530, 0x50);
vars.playerAttachment = vars.Helper.Make<uint>(0x800EDB3C, 0x530, 0x88);
vars.playerMotion48 = vars.Helper.Make<int>(0x800EDB3C, 0x530, 0x80, 0x48);
vars.playerMotion50 = vars.Helper.Make<int>(0x800EDB3C, 0x530, 0x80, 0x50);
vars.sequencePointer = vars.Helper.Make<uint>(0x800EDC18);
vars.sequenceFlags = vars.Helper.Make<uint>(0x800EDC18, 0x20);
vars.sequenceFrame = vars.Helper.Make<uint>(0x800EDC18, 0x34);
```

The sequence owner can be null between sequences; do not treat a failed/null-owner read as timeline frame zero. These paths are code-backed scalar layouts, not a Windows LiveSplit execution test.

## Platform following versus train scripting

These are different bits in `uint A+0x50`:

- **`0x08000000`:** the final-level train entry action sets it, and its normal exit action clears it. The train also writes short coordinates at `G+0x6DA/+0x6DC/+0x6DE`.
- **`0x10000000`:** generic platform/attachment follow logic uses it. This, not the train-specific bit alone, caused the observed overwrite during the position-writer trace.

Native `0x800468EC` checks the platform-follow bit and an attachment pointer at **`A+0x88`**. It transforms a stored local offset through the parent object's matrix, then calls `0x800485EC` to restore the child's world position. The trace observed the position store at `0x8004860C` with caller return address **`0x800469D8`**, inside that routine.

The attachment structure contains a parent pointer at `+0`, a short matrix/part selector at `+4`, a local short vector at `+8/+0xA/+0xC`, and a last-position short vector at `+0x10/+0x12/+0x14`, as consumed/updated by this routine and `0x80046A9C`.

`0x80046A9C` updates the attachment from physics support information. It can set the follow bit again. Clearing a bit once therefore is not necessarily sufficient to detach a character; which state owns the relationship matters.

### Inventory interaction worth testing

Both routines conditionally skip parent-matrix work when the parent actor's byte `+0x34` has bit `0x10` and `gameSubmode == 2`. This is a **code-backed interaction**, not yet a reproduced movement exploit. It gives a concrete experiment: compare child/parent matrices, local offsets, physics support and world position across inventory-open/close timing on a moving support object.

Do not promote forced detachment or coordinate injection to a route skip. A useful glitch claim needs a controller-only trigger, a repeatable resulting displacement/collision change, and negative controls from equivalent states.
