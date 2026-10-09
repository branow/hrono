---
id: 132
title: An op can decline to do its work and report success — no outcome reaches the operator
priority: high
size: medium
depends_on: [105, 087]
spec_refs: [implementation-notes.md, build-order.md#T36]
found_by: PO at #105's close, 2026-09-21
---

## Context
Spun off from #105 PO review. #105 made a judge panel that cannot parse its
replies ABSTAIN rather than fake a `none` — the right call, because a false
`none` silently suppresses a real cascade. The abstention is recorded "loudly"
in `update_log`, and that is the loudest thing the code can currently do:

```
$ grep -rn "update_log" src/hrono --include="*.py"
  cluster/incubator.py   writes
  summarize/propagate.py writes
  db/update_log.py       the writer itself
```

**Two writers, zero readers.** Op handlers return `None`, so a job row carries a
status and an error string and nothing else. The consequence, end to end: hrono
can decline to judge a topic whose content changed, correctly leave its
ancestors unmarked, finish the job as `succeeded`, and no operator — CLI, API or
future dashboard — has any way to learn that a stale brief is still being served
as current.

This is not #105's defect; #105 promised not to fabricate a verdict and it does
not. It is the gap #105 made visible, and it applies to every op that makes a
decision worth knowing about: propagate's abstentions and skips, the incubator's
parks and force-assignments, repair's migrations, monitor's rate.

## Description
Give an op an OUTCOME, and give the operator a way to see it.

The minimum honest version, in two parts:

1. **Ops return a result summary, and the job row carries it.** A small typed
   result per op (counts, not prose) persisted on the job — e.g. propagate
   returning `{judged, propagated, skipped, abstained}`. `jobs` already has the
   row; this is a column plus the handler signatures. Ops that have nothing to
   say return nothing and the column stays null.
2. **An abstention is a warning, not a row.** A job that completed but declined
   part of its work must be distinguishable from one that did everything. Decide
   whether that is a status value (`succeeded-with-warnings`), a field on the
   result, or a non-zero count the CLI renders — pick ONE and state why.

Explicitly NOT in scope: a reader for the whole `update_log` table, or the
dashboard. #106 owns the operator-facing surface and the M10 dashboard owns the
audit view; this ticket owns making the outcome EXIST so both have something to
read. Keep the surface minimal — counts, not an event stream.

## Open question — flag, do not guess
Does the result belong on the `jobs` row (simple, one place, but couples every
op's vocabulary to one column) or in a per-op result table keyed by job id
(cleaner, more machinery)? State which you chose and why. Do not invent a
generic event bus; this is counts on a completed job.

## Acceptance criteria
- [ ] `propagate` returns a result carrying at least `judged`, `propagated`,
      `skipped` and `abstained`, and it is persisted with the job.
- [ ] A run in which every panel abstained is distinguishable from a clean run
      by reading the job alone — no SQL against `update_log` required.
- [ ] The distinction is visible through whatever operator surface exists at the
      time (today: the job read path; if #106 has landed, its CLI).
- [ ] Ops with nothing to report are unchanged and persist nothing.
- [ ] A regression test drives a propagate run that abstains and asserts the
      operator-visible outcome, not the `update_log` row.
- [ ] `ruff format`, `ruff check --fix`, `pytest` clean.

## Out of scope
- Rendering `update_log` history anywhere (M10).
- Changing any op's DECISIONS. This ticket reports; #105 and #087 decide.
- Job error codes — that is backlog #109, and the two should not be merged: an
  error is a job that failed, this is a job that succeeded incompletely.

## Review log
- 2026-09-21 PO: authored at #105's close. Priority `high`: the product bar says
  trustworthy, and a system that can quietly decline work while reporting
  success is the exact opposite. It is also the cheapest possible moment to fix
  it — #105 and #110 both just added decisions worth reporting, and #106 will
  want something to render.

## Review log (dev)
- 2026-09-21 dev: started; moved to in-progress (batch with #122, #123, #127).
- 2026-09-21 dev: implemented and committed.

  **Open question 1 — the `jobs` row, not a per-op table.** Migration `0027`
  adds `jobs.result`, a JSON object of counts. The coupling the ticket worried
  about does not arise because the column is opaque to the schema: it stores an
  op's vocabulary, it does not encode it in columns. A per-op result table keyed
  by job id would be a second lifecycle, a second read path and a join, for data
  that is a flat map of small integers written once at the end of a job. The
  read path already exists and now carries it.

  **Open question 2 (mine, not the ticket's) — `incomplete` is a FIELD, not a
  status.** I considered a `succeeded-with-warnings` status and rejected it:
  status is a state machine the worker, the reclaimer, `/jobs?status=`, and
  every test branch on, and widening it would make every existing
  `status = 'succeeded'` check subtly wrong — including the reclaim logic #093
  depends on. A job that declined part of its work is still a job that
  succeeded; WHAT it did is data about the job. One field, `result.incomplete`,
  is the single thing a reader has to check.

  **The path, end to end.** `Handler` returns `Mapping[str, object] | None`; the
  worker keeps whatever the handler returned and hands it to `_finish`, which
  serializes it alongside the terminal status. An op that returns nothing
  persists nothing — a null column says "this op had nothing to report", which
  is true of most of them. `set_status` writes `result = COALESCE(?, result)`,
  so a later status flip that carries no outcome (a reclaim, a cancel) cannot
  erase what the run reported; that is tested, because #093 makes re-status a
  normal event.

  `Job.result` is the LAST field with a default, so none of the ~40 places that
  construct a `Job` had to change — the first shape I wrote made it required and
  broke 136 tests, which was the clearest possible argument for the default.

  **`propagate` is the first reporter**, and reports what #105 made possible to
  decline: `judged`, `propagated`, `skipped`, `abstained`, `incomplete`.
  `abstained` is the count that matters — those topics CHANGED and were not
  judged, so their ancestors were correctly left unmarked and a stale brief is
  still being served as current.

  Tests (7 new, 808 total): a clean run's counts and an all-abstained run's
  counts; the worker persisting an outcome and persisting nothing for a quiet
  op; a failed job carrying no outcome (an error is not an outcome); a reclaim
  not erasing one; and `GET /jobs/{id}` carrying `result` for a declined run and
  `null` for a quiet one — the criterion asks for the operator surface, so the
  test uses it. Mutations, all killed: the worker dropping the outcome,
  overwriting instead of COALESCE, counting abstentions as judged, pinning
  `incomplete` to False, and hiding the field from the API.

  Not touched: `update_log` rendering (M10), any op's decisions, job error codes
  (#109 — an error is a job that failed, this is one that succeeded
  incompletely, and they stay separate as the ticket required).

  Gate clean: `ruff format`, `ruff check --fix`, `pytest` **808 passed**.
- 2026-09-21 qa: **PASS — to po-review.** Every criterion met, both open
  questions answered with reasons rather than preferences, and the second
  question — the one dev raised themselves — was answered the way I would have
  insisted on.

  **Not widening `status` is the right call and worth keeping on the record.**
  `status` is branched on by the reclaimer (#093), the queue, `/jobs?status=`,
  and a lot of tests; a `succeeded-with-warnings` value would have made every
  `status = 'succeeded'` check subtly wrong, including the reclaim path. A job
  that declined part of its work IS a job that succeeded; what it did is data.

  **Verified independently:**
  - `result = COALESCE(?, result)` is the detail that makes this safe under
    #093, and it is tested: a reclaim or cancel flipping status cannot erase
    what a completed run reported. That is the kind of interaction a new column
    usually gets wrong.
  - A failed job stores no result — an error is not an outcome — and the
    `isinstance(outcome, Mapping)` guard means an op returning something else
    (`attach_orphans` returns a tuple) persists nothing rather than crashing the
    worker. I checked that path specifically.
  - `Job.result` last with a default is why ~40 construction sites did not
    change; the 136-test failure dev hit with the required version is the
    evidence that the default is load-bearing, not cosmetic.
  - The criterion says "the operator surface", and the test uses it:
    `GET /jobs/{id}` carries `result` for a declined run and `null` for a quiet
    one. Read-path only, reader role, no new write surface.
  - `propagate`'s counts are the right ones. `abstained` is the number that
    matters: those topics CHANGED and were not judged, so a stale brief is still
    being served as current, and `incomplete` is the single field a reader has
    to check.
  - Mutations re-run by me, all killed: worker dropping the outcome, overwriting
    instead of COALESCE, counting abstentions as judged, pinning `incomplete`
    False, hiding the field from the API.
  - Migration `0027` is additive and nullable; its comment states the reasoning
    (why not a status) rather than restating the SQL.

  **One note for the PO, not a fail.** `propagate` is the only reporter so far.
  The incubator also writes `update_log` in propagate's shape (parks,
  force-assigns), and #113/#123 now make decisions worth counting too. Nothing
  here blocks that — the mechanism takes any op — but "an op can decline work
  and still report success" is only closed for the op that motivated it.

  Gate re-run by me: 810 passed, ruff clean. Commit atomic and conventional.

## Review log (PO)
- 2026-09-21 PO: **PASSES — closed to done.** Every criterion met, and both open
  questions answered the way I would have ruled.

  The one I care most about is the one dev raised rather than the one I wrote:
  `incomplete` as a FIELD, not a new status. Status is a state machine several
  subsystems branch on, including #093's reclaim; widening it to carry a quality
  judgement would have made every existing `status = 'succeeded'` check quietly
  wrong, and the bug that produced would have been horrible to find. A job that
  declined part of its work is still a job that succeeded. What it did is data
  about the job.

  **This closes the gap #105 exposed and I would not have shipped M6 without.**
  Before it, hrono could decline to judge a topic whose content changed,
  correctly leave its ancestors unmarked, report `succeeded`, and leave a stale
  brief being served as current with no way for anyone to find out. "Trustworthy"
  is one of four things on the product bar, and a system that can quietly do
  less than it was asked while reporting success fails it outright.

  `result = COALESCE(?, result)` is the detail that makes it survive contact with
  #093, and I am glad it is tested rather than reasoned about — a reclaim
  erasing the outcome of the run that actually did the work would have been a
  subtle and permanent loss.

  **Passes, and the follow-up qa named is real — authored #133** (backlog,
  `medium`). `propagate` is the only reporter so far, but the incubator already
  writes `update_log` in propagate's shape, and #113/#123 now make decisions an
  operator would want counted: how many members were force-assigned, how many
  pioneers were freed. The mechanism takes any op; adopting it is per-op work
  and belongs on its own card, not stuffed into this one.
