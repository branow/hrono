---
id: 055
title: generalize ingest (sync/filter/split) to source-type dispatch, like the registry engine
priority: medium
size: big
depends_on: [025, 026, 032]
spec_refs: [build-order.md#M8, design-sketch-v1.md, how-hrono-works.md]
---

## Context
The registry got a genuinely extensible descriptor+engine (add a collection with
zero engine change). The INGEST path did not: `sync` (#025), `filter` (#026), and
`split` (#032) are hardcoded to git with NO source-type dispatch seam anywhere.
`sync` directly runs `git clone`/`fetch`, and even the sources pydantic model is
git-only (`GitSource`, `type: Literal["git"]`). There is no `if source_type` and
no registry of syncers — the code assumes every source IS a git repo. The spec
intends many source types (git first, then Confluence, Notion, provider-discovery),
so this is a first-vertical-slice shortcut, not the final shape, and it must be
generalized before the second source type lands (M8 breadth).

## Concept that generalizes (mechanism differs, shape is universal)
Every source type needs: fetch current content into a local cache + pin a
VERSION. Git = clone/pull + commit SHA. Confluence/Notion = API pull + page-
version/etag/timestamp. `clone`/`pull` is just git's transport, not the abstraction.

## Description
Apply the same data-driven dispatch the rest of the codebase uses (OPS,
_RESOLVERS, _VALIDATORS):
- A source-type discriminated model for `sources` (git | confluence | notion | ...)
  the way `connections` is provider-discriminated — not a single `GitSource`.
- A per-source-type SYNCER seam (e.g. `SYNCERS[type]`): `sync` resolves the
  source's `type` and delegates; the git syncer keeps today's clone/pull + SHA.
  Each new type is one entry, no `sync` engine change.
- Do the same for `filter` and `split` where they assume a git working tree /
  file bytes: define the per-type seam (a non-git source may not be a filesystem
  tree at all).
- Keep `source_state` (version pin) generic — version is opaque text, already fine.

## Acceptance criteria
- [ ] `sources` model is source-type discriminated; git is one variant.
- [ ] `sync` dispatches by source type through a syncer registry; the git syncer
      behaves exactly as today (clone/pull, SHA version); an unknown type is a
      clean domain error, not a crash.
- [ ] `filter`/`split` have a per-type seam (git implementation unchanged);
      adding a source type does not edit their engines.
- [ ] Adding a second source type requires a model variant + registry entries
      only, no ingest-engine branch (mirrors the registry-collection property).
- [ ] `ruff format`, `ruff check --fix`, `pytest` all clean.

## Out of scope
- Actually implementing Confluence/Notion syncers — this is the DISPATCH seam so
  they become drop-in (their own tickets).
- Changing git behavior.

## Review log
- 2026-08-23 stakeholder + PO: raised while reviewing the #025 sync op. The
  ingest path hardcodes git with no source-type seam, unlike the extensible
  registry engine. Generalize to source-type dispatch before M8 breadth adds a
  second source type.
- 2026-08-23 PO triage: vetted, well-formed, DoR essentially met — but PARKED in
  backlog, NOT promoted to todo. Its own trigger is "before M8 breadth adds a
  second source type"; we are finishing M3, and the settled order (M3 -> M4 -> M5
  -> M6 export = MVP -> ... -> M8) means nothing on the MVP critical path needs
  multi-source dispatch yet. Promoting a `big` refactor now would preempt M4-M6.
  Pull into todo when M8 starts (or the first non-git source type is scheduled),
  at high priority since the second type is blocked on it.

- 2026-09-23 po: SPLIT and closed. Its own pull-in trigger fired — M7 closed
  with #130 and M8 breadth is next — and it is `big`, which the board splits on
  principle. It becomes #141 (the discriminated model), #142 (the syncer
  dispatch) and #143 (the filter/split seam), each one commit's worth of work
  and each independently verifiable. The acceptance criteria above are
  distributed across the three; nothing was dropped.
