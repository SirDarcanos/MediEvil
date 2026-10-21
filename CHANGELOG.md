# Changelog

Notable changes are grouped by component. MediSplit and LiveMap are versioned
independently; release tags use `medisplit-v...` and `livemap-v...`. Unreleased
entries do not select a version or authorize a release. See the
[release policy](AGENTS.md#history-and-releases).

## Unreleased

### MediSplit

- Add a development Any%-only ASL with 17 fixed splits: 14 successful level
  exits, then Fazguls, Kardok and Zarok. Keep only Autostart, Autosplit and Autoend
  options, with no HoH delay or automatic reset; preserve both legacy scripts.
- Use a directly editable script and existing cached-base/direct-field RAM
  readers without emu-help, full-RAM snapshots or a generated-source workflow.
  Actual LiveSplit/emulator gameplay validation remains outstanding.
- Add a small MediEvil Recomp v0.2b RAM lookup for 64-bit ASL hosts with
  `MemoryPages()`, retaining the same Any% route and three settings. Recomp
  discovery and gameplay remain unverified.

### LiveMap

- Separate sampling, HTTP serving, movement tracking and fallback rendering;
  share texture decoding and response/security handling without changing the
  runner workflow, map format or controls.

### Reference and research

- Expand the USA typed-address reference and retain reusable memory-audit tools,
  probes, tests and curated evidence, including owner/lifetime guards and
  verification limits ([#2](https://github.com/SirDarcanos/MediEvil/pull/2),
  [#3](https://github.com/SirDarcanos/MediEvil/pull/3)).

### Project workflow

- Add the working agreement, GitHub Issues role/readiness mapping, auxiliary
  model permissions and independent component versioning policy.

## LiveMap 0.2.0 — 2026-10-20

Unsigned preview, tagged
[`livemap-v0.2.0`](https://github.com/SirDarcanos/MediEvil/releases/tag/livemap-v0.2.0).

- Add an arrow ahead of Dan that shows his observed movement direction and hides while stationary or without fresh live movement.
- Provide individually named Windows x64, macOS ARM64 and Linux x64 downloads with checksums. Native build/startup checks passed; actual Windows/Linux gameplay remains unverified.

## LiveMap 0.1.0-preview.1 — 2026-10-18

Initial published preview, tagged
[`livemap-v0.1.0-preview.1`](https://github.com/SirDarcanos/MediEvil/releases/tag/livemap-v0.1.0-preview.1).

- Provide a read-only MediEvil USA minimap, own-disc map extraction/cache, and
  native Windows x64, Linux x64 and macOS ARM64 downloads.
- Use DuckStation shared memory on Windows/Linux and local GDB reads on macOS.
- Package no emulator, BIOS, game assets, saves or RAM dumps.
- Native build/startup checks passed; macOS had local import/render/cache checks
  and a user smoke-test report. Actual Windows/Linux DuckStation gameplay and
  lifecycle remain unverified, as stated in the published preview notes.

No historical MediSplit release dates or new versions are inferred from the
legacy script headers.
