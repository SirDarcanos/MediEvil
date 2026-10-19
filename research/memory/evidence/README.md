# Curated memory-research evidence

These JSON files contain extracted tables, scalar observations, source/run
hashes and verification limits. They are retained in Git. Raw game RAM, disc or
BIOS data, screenshots, save states and complete emulator runs are not included.

A file's presence does not mean its entire experiment succeeded. Read its scope,
setup and conclusion; failed objectives and negative controls can still explain
why an address or interpretation was rejected. Current address meanings are in
[the repository reference](../../../README.md); current trigger coverage is in
[the status notes](../notes/asl-readiness.md).

## Index

- **Tables and capture integrity:** [inventory-table.json](inventory-table.json),
  [level-table.json](level-table.json), [verified-runs.json](verified-runs.json),
  [isolation-verification.json](isolation-verification.json),
  [movement-fields.json](movement-fields.json).
- **Player, inventory and lifecycle:** [health-events.json](health-events.json),
  [fatal-lifecycle-events.json](fatal-lifecycle-events.json),
  [pickup-events.json](pickup-events.json), [dagger-use-events.json](dagger-use-events.json),
  [crypt-exit-events.json](crypt-exit-events.json).
- **Title/menu:** [newgame-request-events.json](newgame-request-events.json),
  [title-fields.json](title-fields.json), [title-input-events.json](title-input-events.json).
- **Pumpkin setup and HUD limits:** [pumpkin-setup-events.json](pumpkin-setup-events.json),
  [pumpkin-code-fields.json](pumpkin-code-fields.json),
  [pumpkin-hud-events.json](pumpkin-hud-events.json),
  [pumpkin-hud-limits.json](pumpkin-hud-limits.json).
- **UI and army population/outcomes:** [army-entry-validation.json](army-entry-validation.json),
  [inventory-cleanup-validation.json](inventory-cleanup-validation.json),
  [native-inventory-buffer.json](native-inventory-buffer.json),
  [army-buffer-comparison.json](army-buffer-comparison.json),
  [army-release-comparison.json](army-release-comparison.json),
  [army-idle-victory.json](army-idle-victory.json).
- **Final bosses:** [kardok-arrival-events.json](kardok-arrival-events.json),
  [kardok-damage-events.json](kardok-damage-events.json),
  [final-boss-events.json](final-boss-events.json),
  [zarok-death-events.json](zarok-death-events.json).
- **RNG observations/consumers:** [rng-crypt-validation.json](rng-crypt-validation.json),
  [rng-input-comparison.json](rng-input-comparison.json),
  [rng-army-comparison.json](rng-army-comparison.json),
  [army-rng-consumers.json](army-rng-consumers.json),
  [army-decision-validation.json](army-decision-validation.json),
  [army-hit-validation.json](army-hit-validation.json),
  [army-low-health-rng.json](army-low-health-rng.json),
  [level-rng-consumer.json](level-rng-consumer.json).
- **Fight experiments and transition fault:** [fight-action-comparison.json](fight-action-comparison.json),
  [fight-action-outcomes.json](fight-action-outcomes.json),
  [fight-repeatability.json](fight-repeatability.json),
  [jump-timing-search.json](jump-timing-search.json),
  [post-reactivation-fault.json](post-reactivation-fault.json).

## Provenance and reproduction

Historical filenames, absolute run paths, probe hashes and earlier field labels
are preserved as recorded. They are not checkout-path dependencies. JSON-to-JSON
basename references remain in this directory. Corrections qualify an old label
without rewriting the old sample/hash into a different observation.

The latest reusable probe is not necessarily byte-identical to an earlier
frozen probe. Reproduction requires the matching game revision, declared setup,
starting-state ancestry and relevant emulator configuration; hashes alone do
not supply the private inputs. Laboratory assistance must remain labelled.

New local runs belong outside the checkout or in the ignored `runs/` or
`outputs/` directories. Promote only a reviewed summary here, with its source
identity, objective, observed result and limitations. Do not copy raw game data
into this directory.
