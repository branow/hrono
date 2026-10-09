---
id: 155
title: a pinned membership or parenting survives the re-cluster
priority: high
size: medium
depends_on: [154]
spec_refs: [build-order.md#T45.3, implementation-notes.md]
---

## Context
The second half of the pin contract, and the harder one: #154 stops a brief
being rewritten, this stops a MAP being reshuffled. The spec: "a pinned
membership/parenting survives `settle`'s re-cluster (honored as fixed, never
reshuffled)".

Three places move a member or a child today and each must learn the same rule:
`settle` (the warm reconcile), `repair.migrate` (misfit migration) and
`levels.migrate_children` (the upper-level twin). A pin that only `settle`
honours would be reverted by the next `repair` run instead — slower, and
harder to explain.

## Description
- `repair.migrate` skips a member whose membership is pinned, and counts it.
- `levels.migrate_children` skips a child whose parenting is pinned.
- `settle`'s membership diff keeps a pinned member where it is, and a pinned
  child under its parent, whatever the re-cluster produced.
- Each op reports how many it held, so an operator can see a pin doing work.

## Acceptance criteria
- [x] A pinned member stays in its node through a `repair` run that would have
      migrated it, and the run reports it held.
- [x] A pinned child stays under its parent through an upper-level migrate.
- [x] A pinned membership survives `settle` re-clustering the tree around it.
- [x] Unpinning releases it: the same run then moves it.
- [x] `ruff format`, `ruff check --fix`, `pytest` clean.

## Out of scope
Manual placement endpoints (#158, #160) — this is the pipeline half.

## Review log
- 2026-09-23 po: authored.

- 2026-09-23 dev: `repair.migrate` and `levels.migrate_children` skip a pinned
  target, which is the easy half. `settle` could not work that way: it
  re-clusters the whole leaf level, so every `node_members` row is rewritten
  and "do not move it" has nothing to apply to. It restores instead —
  immediately after the re-cluster and BEFORE `brief`, which reads membership
  to write summaries; a brief written over the wrong members is the same
  revert, one step removed.

  TWO THINGS THE TICKET DID NOT ANTICIPATE, both found by the test failing for
  a real reason:

  1. A membership pin has to say WHERE. Migration 0031 adds `anchor_id`,
     because by the time `settle` reads the pin there is no membership left to
     infer the topic from.
  2. The anchor node itself often does not survive. A node is identified by its
     members' content (#068), so the very hand-move a pin protects changes the
     node's signature and retires it. Anchoring on the id alone released the
     pin on exactly the operation it exists for. The anchor's OTHER members are
     captured before the rebuild, and afterwards the topic is whichever node
     inherited most of them — that node IS the topic the operator pointed at,
     under a new id, and the pin is re-anchored to it. A pin is released only
     when the topic is gone entirely.

  `settle` and `repair` now report what they held (`held`, `released`,
  `pinned`).

  Mutations run, all killed: repair ignoring the pin -> 4 fail; the upper level
  ignoring it -> 3; settle not restoring -> 4; a retired anchor releasing
  instead of following its company -> 3.

  Test note: the settle test first asserted the literal anchor id and failed
  against a successor node. That was the code being right and the test being
  too literal (#136) — it now asserts the chunk is still with the NEIGHBOURS
  the operator put it among, which is what a topic is.

- 2026-09-23 qa: PASSED, and this is the strongest piece of design work in the
  batch. Added a mutation dev did not state: `settle` forgetting the anchor's
  company before the rebuild (`anchored = {}`) -> 2 fail.

  The finding behind it deserves repeating, because it would have shipped as a
  silent revert otherwise: a node is identified by its members' content (#068),
  so the hand-move a pin protects is itself what retires the anchor node. Pins
  keyed on the node id alone would have released on precisely the operation
  they exist for — and released INVISIBLY, since the chunk simply stays where
  the machine put it. Following the anchor's company to its successor node is
  the correct reading of what an operator meant by "this topic".

  Verified that all three movers honour pins, not just settle: `repair.migrate`
  and `levels.migrate_children` each have a control test showing the unpinned
  case DOES move, so the pin is what makes the difference.

- 2026-09-23 po: CLOSED, and the anchor-follows-its-company rule is now a
  settled decision, not an implementation detail. State it plainly for whoever
  reads this next: a topic is its members, not its id. Every later feature that
  needs to point at a topic across a rebuild must resolve it the same way.

  Adjacent work noted, no ticket: nothing yet SHOWS an operator which of their
  pins were released by a settle. The count is in the job result (#132), which
  is enough today and will not be enough once a dashboard exists (M10).
