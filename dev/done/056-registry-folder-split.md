---
id: 056
title: split the registry package — engine/base vs collections vs validation
priority: low
size: small
depends_on: [055]
spec_refs: []
---

## Context
`src/hrono/registry/` has grown to ~15 flat files mixing three distinct
concerns: the generic engine, the per-collection data definitions, and the
validators. It is at the edge of file sprawl and the conceptual boundary is real.

## Description
One level of subfolders (no deep nesting), mapping to how the code thinks:
- base/engine: `descriptor`, `engine`, `store`, `write`, `seeding`, `collections`
- collections/: `sources`, `connections`, `models`, `prompts`
- validation: `git_validation`, `connection_validation`, `model_validation`,
  `git_auth` — co-located with their collection, or a `validation/` folder.
Behavior-preserving move + import fixups only.

## Timing
Do this TOGETHER WITH #055 (source-type dispatch), not before: the `git_*` files
are entangled with the ingest/validation generalization and may move to a
per-source-type home anyway. Reorganizing now would churn imports twice.

## Acceptance criteria
- [x] Registry files grouped into one level of intent-named subfolders; no file
      logic changed.
- [x] Imports updated; public behavior identical.
- [x] `ruff format`, `ruff check --fix`, `pytest` all clean.

## Out of scope
- Any logic change; deep multi-level nesting.

## Review log
- 2026-08-23 stakeholder + PO: registry folder is getting crowded. Agreed to a
  one-level split (engine/collections/validation), TIMED WITH #055 to avoid
  churning imports twice. Low-pri hygiene.
- 2026-08-23 PO triage: parked in backlog, NOT promoted. depends_on #055, which
  is itself parked until M8; its own Timing section says do this together with
  #055 to avoid churning imports twice. Pull into todo only when #055 is pulled.
- 2026-09-27 po: PULLED IN. Its one timing condition has fired — #055 shipped
  (split into #141-#143), so the `git_*` files have settled where they are
  going to sit and reorganizing now churns imports once rather than twice.
  The folder has also grown since: `trees.py` (#054) and `impact.py` (#190)
  landed after this ticket was written.
- 2026-09-27 dev: one level of subfolders, and the cheap shape rather than the
  obvious one.
  - `collections.py` became `collections/__init__.py`, so
    `from hrono.registry.collections import COLLECTIONS` — six call sites — did
    not move at all, and the five collection modules sit beside the tuple that
    registers them. Absolute imports mean the stdlib `collections` is still the
    stdlib inside those files; checked from outside the package.
  - `validation/` takes the five reach-out validators. That is the boundary
    worth a folder: everything else in `registry/` touches a row, these call a
    git remote, a provider endpoint or a model load, so they are the slow ones
    and the ones with seams.
  - The engine core stayed FLAT — `store`, `descriptor`, `write`, `engine`,
    `seeding`, `impact`, `commands`. Those carry 100+ of the package's ~130
    import sites, and moving them would have been a hundred-line mechanical
    diff for no gain. 27 files touched instead.
  - Verified the wheel still ships the moved modules (`uv build`, then read the
    archive): a package rename that builds locally and ships nothing is the
    failure mode worth checking once.
  - Gate: 1404 passed, 2 skipped.
- 2026-09-27 qa: verified. Pure moves plus import rewrites; no test changed
  meaning, and the two that changed at all were combined-import lines.
