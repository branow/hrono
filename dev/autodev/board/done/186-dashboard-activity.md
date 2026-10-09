---
id: 186
title: the dashboard's activity view — what the tree decided, and why
priority: medium
size: small
depends_on: [180, 182]
spec_refs: [build-order.md#T54]
---

## Context
T54: "Activity / `update_log` view". `update_log` (0019) records, per changed
topic, the judge's VERDICT and the ACTION taken — whether a change climbed, how
far, or was skipped. It is written on every propagate run and read by nobody.

That table is the only record of the system's own JUDGEMENT. A brief being
stale is a fact; a brief being judged "not materially changed, do not climb" is
a decision, and an operator who disagrees with the map needs to see the
decision rather than infer it.

## Description
- `GET /ui/trees/{tree}/activity` — newest first: when, which topic, the
  verdict, the action, and how far it climbed.
- The topic links to its page (#182).
- An ABSTENTION is marked. #105/#132 made abstaining a first-class outcome
  precisely because a topic that changed and was not judged leaves a stale
  brief in service — that row is the most important one on the page.
- Bounded: the newest N, with the count of what is not shown. A log view that
  renders forty thousand rows is a log view nobody opens twice.

## Acceptance criteria
- [x] Rows are newest first, with topic, verdict, action and climb.
- [x] An abstention is visibly distinct from a decision.
- [x] Each topic links to its page.
- [x] The view is bounded and says how many older rows exist.
- [x] Rows are per TREE.
- [x] An empty log says so.
- [x] `ruff format`, `ruff check --fix`, `pytest` clean.

## Review log
- 2026-09-27 po: authored.

- 2026-09-27 dev: done. `update_log` has been written since M7 (#087, and
  #095's incubator) and read by nobody; this reads it.

  **The abstention nearly shipped invisible.** I first keyed it off the
  VERDICT — the obvious column — and `propagate._record` writes the verdict as
  `"unparseable"` and the ACTION as `"abstained"`. So the marking would have
  matched nothing, on the row the page most exists to show: a topic that
  CHANGED, was not judged, and is still serving a stale brief. Found by reading
  the writer rather than the schema. The test now records through the real
  `record()` with production's own values, and the mutation that reads the
  verdict fails it.

  Bounded at 100 with the total beside it: "showing 100 of 100" and "showing
  100 of 41,000" are different situations and a page that prints only the first
  number cannot tell them apart.

  Mutations, all killed: the abstention read from the verdict -> 1 fail;
  oldest first -> 1; rows from every tree -> 1; the total reported as what is
  shown -> 1.

  Gate clean: 1300 passed, 2 skipped.

- 2026-09-27 qa: PASS, to po-review. Gate: 1300 passed, ruff clean. Re-ran P1
  (the abstention read from the verdict) — fails.

  Dev's find is the ticket. "Read the writer, not the schema" is the same
  lesson as #176 pointed the other way: the schema says there is a `verdict`
  column and an `action` column, and only the code that WRITES them says which
  carries the meaning. A test that planted `verdict="abstained"` would have
  passed forever over a page that marked nothing.

  Six views. The dashboard now shows the map, a topic, what needs attention,
  what ran, and what was decided.

- 2026-09-27 po: CLOSED. `update_log` was an audit trail with no reader for two
  milestones; it has one.

  The abstention row is why this view was worth doing. #105 made abstaining
  possible, #132 made it visible in a job's result, and neither made it
  findable afterwards — "which topics are serving a stale brief because the
  panel could not read its own answer" had no way to be asked. Now it is a row
  in orange.

  T55 (config tables) and T56 (surgery in-UI) remain, plus #184 (non-tree
  edges). T55's dry-run half depends on #178, which is parked — it ships
  without the modals and says so.
