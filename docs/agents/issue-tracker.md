# GitHub tracker policy

Approved by the maintainer on 2026-10-19; governed by [AGENTS.md](../../AGENTS.md).
Repository: `SirDarcanos/MediEvil`.

## Authoritative records and publication

GitHub Issues is the authoritative home for product specifications and their
implementation work. Use descriptive titles without mandatory prefixes. Search
open and closed records before creating one; update the same authoritative item
when scope still matches. A new Markdown spec home, duplicate issue, migration,
backlog, board or relationship graph is not a setup requirement.

An explicitly selected spec/ticket workflow publishes its scoped result here,
unless the user requests a draft, local artifact or review only. Faithful wording
of agreed commitments does not need another full-text approval. Consequential
new product decisions, missing scope and effects outside the selected publication
remain gated. Publishing a spec does not start implementation or create tickets.

A spec records the agreed goal, boundaries, behavior, stable acceptance IDs,
evidence limits and open decisions. Preserve IDs when wording evolves; do not
silently replace the contract or mark unverified acceptance complete. A bounded
implementation item points to its authoritative spec and applicable acceptance
IDs, describes its next action and exposes unresolved prerequisites.

## Role, readiness and impact

- `spec` identifies a product/acceptance contract.
- `implementation-step` identifies bounded implementation, design or validation
  work under a spec. Do not apply both roles to the same item.
- `ready-for-agent` means the **next action** is agent-suitable with sufficient
  scope and inputs. It can be analysis or coordination, not necessarily coding.
- `ready-for-human` means the next action requires a human decision/capability.
  Use the one matching the next responsible actor, not both.
- `needs-triage` marks unresolved scope/routing/relevance; `needs-info` marks a
  consequential missing decision or evidence. They are not completion states.
- Readiness is separate from role, native dependencies and integration status.
  A ready-labelled child with an unsatisfied blocker is not eligible to start.
  Parent readiness never means all children are ready or accepted. Assess each
  item independently; do not mass-promote children by their parent's label.
- Use `medisplit` and/or `livemap` for affected components. Reference-only work
  does not need an invented component label.
- `patch`, `minor`, `major` are shared SemVer impact labels, not component-scoped
  aliases. Classify actual delivered impact before release; if anticipating it
  on a spec, identify it as provisional. Mixed-component items record each
  component's impact explicitly. Labels neither change versions nor publish
  releases; see the [release policy](../../AGENTS.md#history-and-releases).
- GitHub open/closed state records lifecycle, not acceptance proof. Close work
  only within selected completion authority and with its scope/evidence met;
  a label or merged PR alone is not sufficient. Do not add closing keywords to
  PRs when issue closure was not selected.

## Native structure and relationship authority

Use GitHub-native sub-issues for spec ownership and native blocking dependencies
for execution prerequisites. Body links/checklists may explain relationships,
but are not substitutes for missing native structure. Avoid ordering by issue
number, title, list position or labels.

Before tracker mutations, discover the maintained native GitHub tracker route
from the available procedure catalog, read its entry/references, and verify the
current native API/capabilities. Read complete paginated records, labels,
parent/children and blocker/dependent edges. Resolve canonical repository/item
identity and the API's required database IDs; an issue number is not a database
ID. Missing native capability blocks the dependent mutation rather than silently
falling back to prose or inventing a graph operation.

A selected ticket-decomposition scope can cover its new children and derivable
internal links. Identify the exact parent/child and blocker/dependent sets before
writing. Authority for one issue, a label or a body edit does not grant arbitrary
existing/cross-scope edge changes, parent moves, migrations or removals. These
need their own exact scope and authority. Preserve unrelated and historical
relationships; do not delete/reparent to make a plan appear clean.

Immediately before a write, reconcile live state and the authorized set. After
it, read back role/readiness, canonical parent/children and both dependency
views as applicable. Return actual complete/partial/blocked state and uncertain
operations; do not retry an uncertain creation by creating a duplicate. Stop
before implementation or PR/release work that was not selected.

## Approved label vocabulary

Retain these exact names, colors and descriptions. No label deletion,
consolidation, assignment migration or backlog creation was selected for setup.
Additional vocabulary or semantic changes require agreement.

| Label | Color | Description |
| --- | --- | --- |
| `bug` | `d73a4a` | Something isn't working |
| `documentation` | `0075ca` | Improvements or additions to documentation |
| `duplicate` | `cfd3d7` | This issue or pull request already exists |
| `enhancement` | `a2eeef` | New feature or request |
| `good-first-issue` | `7057ff` | Good for newcomers |
| `help-wanted` | `008672` | Extra attention is needed |
| `invalid` | `e4e669` | This doesn't seem right |
| `question` | `d876e3` | Question or discussion without an implementation commitment |
| `wontfix` | `ffffff` | This will not be worked on |
| `spec` | `5319e7` | Product specification and acceptance criteria |
| `implementation-step` | `1d76db` | Bounded implementation, design or validation work under a spec |
| `needs-triage` | `d4c5f9` | Needs scope, routing or relevance triage |
| `needs-info` | `fbca04` | Missing a consequential decision or evidence |
| `ready-for-agent` | `0e8a16` | Next action is ready for agent work; dependencies still apply |
| `ready-for-human` | `d876e3` | Next action requires a human decision or capability |
| `medisplit` | `0052cc` | MediSplit autosplitter work |
| `livemap` | `006b75` | LiveMap companion application work |
| `patch` | `0e8a16` | Backward-compatible bug fix |
| `minor` | `1d76db` | Backward-compatible functionality |
| `major` | `b60205` | Incompatible public behavior or interface change |

The setup renames `good first issue` → `good-first-issue` and `help wanted` →
`help-wanted`, retaining their original colors/descriptions; it clarifies the
`question` description. The other six original labels remain unchanged.
