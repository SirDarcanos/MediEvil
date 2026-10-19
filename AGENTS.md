# Project working agreement

Approved by the maintainer on 2026-10-19. Read this agreement before project
work. It governs the repository, not personal tool installations or other
projects. The maintainer owns product intent, consequential trade-offs and
permission changes; agents own routine engineering within the requested scope.

## Project and authoritative homes

- `Auto-Splitters/`: MediSplit and its bundled dependency. Keep old splitters
  separately when introducing their unified replacement; preserve their bytes
  and attribution. Assess an emu-help update for compatibility rather than
  blindly replacing the bundle.
- `LiveMap/`: the companion minimap and its own run/build documentation.
- `research/memory/`: reusable research tools, probes, Ghidra scripts, tests,
  curated evidence and notes; use its [index](research/memory/README.md).
- The root [README](README.md) is an address reference, not an ASL-development
  tutorial. Keep types, ownership, meanings and verification limits accurate.
- Before creating/updating specs, tickets, labels or native relationships, read
  [tracker policy](docs/agents/issue-tracker.md).
- Before auxiliary model assessments, service operations or assessment-policy
  changes, read [model-use policy](docs/agents/model-use.md). That permission is
  separate from ordinary agent delegation and independent review.
- The [changelog](CHANGELOG.md) records notable component changes. Release and
  versioning policy is below; no glossary or ADR collection is required merely
  to begin work.

## Scope, safety and collaboration

- Within a selected task, inspection, planning, implementation, safe local
  checks, bounded specialist delegation and lead-owned repairs are allowed.
  Ask about missing intent and consequential scope/risk/cost, not routine test
  seams or worker allocation. The user selects workflow stages.
- Preserve unrelated tracked, staged and untracked work, modes, symlinks,
  history and other worktrees. Inspect state before Git operations. Work only
  in assigned areas; another agent's files or running processes are not yours
  to change, stop or repurpose.
- Keep reusable source and relevant evidence eligible for Git. Ignore caches,
  private run outputs and game-data artifacts instead of discarding useful
  tools or hiding source with broad ignore rules.
- Do not commit game/BIOS/disc binaries, raw RAM, saves, cards, extracted assets,
  emulator copies, credentials or private personal information. Experiments
  use private copies, owned inputs/processes and isolated output directories.
  Original emulator installations, saves and Ghidra projects remain untouched
  unless an explicit task grants a particular change.
- Destructive actions, new sensitive disclosure, spending, global installs,
  credential provisioning/changes, deployment and release publication need
  explicit approval. A requested dependency update permits assessing that
  dependency; it is not permission for unrelated installations or upgrades.

## Git and stage boundaries

- Fetch/pull safely and branch from updated `origin/main`; use short-lived
  branches and PRs into `main`. Use a new branch after the old PR is merged.
  Do not introduce a persistent integration branch without approval.
- No direct pushes to `main`, force pushes, history rewrites or protection
  bypasses. The approved main rules require PRs, zero mandatory human approvals,
  no bypass actors, and blocked force pushes/deletion. No additional mandatory
  status checks were selected; required project verification still applies.
- Commit/push, PR publication and merge are separate selected effects. Do not
  infer them from an implementation request. An explicit compound request can
  select several stages. Do not delete branches without selected authority.
- Ordinary delivery returns its implemented/verified/partial/blocked outcome
  before offering PR work. PR work reuses current evidence; it does not restart
  the engineering task merely to prepare a report.
- Configured spec/ticket commands select their scoped tracker publication;
  draft/local/review-only requests override it. No second full-text approval
  is needed for faithful wording of already-agreed commitments. New product
  commitments and consequential effects still require approval.

## Verification, review and continuation

- Select checks for actual failure risks and existing coverage, without test
  quotas or a blanket test-first rule. Changed inputs invalidate affected
  evidence; preserve valid prior and historical observations.
- Report code-backed layouts, observed native events, laboratory setup and
  unverified behavior separately. A normal process exit, zero field or
  plausible pointer is not proof of the intended gameplay outcome.
- Failed/unavailable material checks and unresolved material findings block
  acceptance of the dependent behavior. Distinguish local/static checks from
  native emulator, Windows and end-to-end verification.
- Delivery includes separate independent Standards and Spec review contexts
  against the same pinned scope and evidence. Reviewers are read-only,
  independent of authors and one another, and do not repair their findings or
  recursively delegate. The lead owns integration and acceptance decisions.
  Missing review capability leaves delivery implemented-but-unaccepted.
- The lead chooses useful concurrency within assigned scope and resources,
  with finite worker assignments. Permit at most two automatic repair cycles
  per acceptance checkpoint; retain finding lineage and spent cycles across
  workers, method changes, handoffs and resume. Further repair or changed scope
  returns to the maintainer.
- Same-session evidence may remain in conversation. Do not require tickets,
  handoff files, draft PRs or committed validation reports merely because a
  session may end. Persist artifacts when selected. Preserve active ownership,
  uncertain operations and used/reserved allowances across interruptions.
- Discover needed companion procedures from the available runtime/catalog,
  read complete entries and relevant references, and check capability/source
  identity. Resolve relative references from their containing document.
  Missing/incompatible helpers block only their dependent route; do not install
  replacements, invent permissions or silently use an older incompatible flow.
- Maintain authorized meanings and documentation with the change. Reading
  existing definitions needs no domain workflow; actual terminology/model
  changes use the compatible domain procedure. ADR creation/supersession needs
  explicit agreement and preserves rationale/history.

Relevant checks, from the repository root:

```sh
python3 -m unittest discover -s research/memory/tests -t research/memory -v
python3 -m unittest discover -s LiveMap -p 'test_*.py'
node --check LiveMap/web/app.js
node --check LiveMap/web/terrain.js
node --check LiveMap/web/setup.js
```

Run only the relevant scope. Inspect `LiveMap/release/BUILD.md` before packaging;
new build-tool installation, signing and release effects are not implicit in a
code change. Existing CI is in `.github/workflows/livemap-build.yml` and is
path-filtered to LiveMap; absence of a CI run is not a research-tool test pass.

## History and releases

- MediSplit and LiveMap are independently versioned using Semantic Versioning.
  Future tags use `medisplit-v...` and `livemap-v...`. Address/reference research
  does not acquire a separate release version automatically.
- MediSplit's version is recorded in the applicable script header; preserve
  legacy headers when archiving old files. LiveMap's existing published version
  is identified by its release tag/notes; do not invent a package-version file
  or rewrite released tags as part of setup.
- Maintain root `CHANGELOG.md` by hand for notable user-relevant changes, grouped
  by component with an unreleased section. Documentation-only formatting may
  need no entry; explain that disposition when reporting.
- Shared `patch`/`minor`/`major` labels classify delivered impact; `medisplit` and
  `livemap` identify affected components. They never bump versions or authorize
  releases. Record different per-component impacts explicitly in mixed work.
- A breaking public change is major, compatible functionality minor, and a
  compatible fix patch. Pre-1.0/prerelease compatibility decisions and the exact
  next version remain maintainer release decisions, not inferred exceptions.
- Publishing a tag, release, package or deployment always requires explicit
  approval. Current LiveMap CI builds artifacts, not automatic public releases.
  Preserve `LICENSE.txt` and third-party notices.
