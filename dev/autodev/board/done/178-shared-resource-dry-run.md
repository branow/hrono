---
id: 178
title: dry-run a shared-resource edit and report its blast radius per tree
priority: medium
size: big
depends_on: [054, 064]
spec_refs: [build-order.md#T58, implementation-notes.md]
---

## Context
T58. `sources`, `connections`, `models` and `prompts` are referenced by name
from many trees, so editing one has cross-tree blast radius. The spec's rule:
"Resources are mutable — edit in place, no version-and-repoint. `?dry_run=true`
is the safety."

    PUT|PATCH /trees/<name>?dry_run=true

    { "stale": { "sections": 0, "nodes": 47, "levels": [1,2,3] },
      "ops": ["cluster", "brief"],
      "estimated_cost": { "brief_calls": 47, "tokens": 210000, "usd": 0.6 } }

## Why it is `big` and parked
Two parts, and the second has no data behind it yet.

**Impact** is computable today: #064's signatures already decide what a change
makes stale, and #054 made a tree's sources explicit, so "which trees does this
resource touch" is now answerable. This half is real work but known work.

**Cost** is not. Nothing records tokens per job — I noted it as out of scope in
#172 and it is still true — so `tokens` and `usd` would be invented numbers
presented to an operator deciding whether to spend money. That is worse than
omitting them.

So this wants splitting: the impact half is a ticket, and the cost half needs a
per-job token/cost record first (its own ticket, and one the spec's `cost`
field on a job already implies).

## Review log
- 2026-09-26 po: authored and PARKED. The impact half is ready when someone
  wants it; the cost half needs a source of truth that does not exist.
- 2026-09-27 po: CLOSED as superseded. Split exactly as this ticket proposed:
  #190 shipped the impact half and #192 the cost half, once #179 gave the
  latter a source of truth. Building #190 also turned up #191, a silent
  wrong-answer this preview could not have described honestly.
