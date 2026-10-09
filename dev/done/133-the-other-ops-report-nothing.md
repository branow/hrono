---
id: 133
title: Only propagate reports an outcome; the ops that force placements report nothing
priority: medium
size: medium
depends_on: [132]
spec_refs: [build-order.md#T35, build-order.md#T37, build-order.md#T38]
found_by: qa at #132's verification, promoted by PO at its close
---

## Context
Spun off from #132, which built the mechanism — `jobs.result`, a JSON object of
counts persisted when a job finishes and rendered on the job read path — and
wired exactly one op to it, `propagate`, because that is the op whose abstention
(#105) motivated the ticket.

The ops that place things report nothing, and they are the ones whose decisions
an operator most needs to see:

- `update` / the incubator: how many chunks were parked, aged, drained, and
  **force-assigned ignoring TAU** (#086 T35.3). A force-assign is the system
  deciding that an alien member is better than an unreachable one — a real
  judgement call, made silently.
- `repair`: how many clusters split, dissolved or migrated, and since #113 how
  many forced pioneers were freed.
- `monitor`: the global rate it measured and how it moved against the baseline.
- `cluster`: whether it COLLECTED rather than clustered (#112) — a one-topic
  tree is a legitimate answer for a small corpus and a surprising one for a
  large one, and today they look identical from outside.

## Description
Give each of those ops a result in #132's shape: counts, never prose, and
`incomplete` only where the op genuinely declined work it was asked to do. Reuse
`jobs.result` exactly as it stands — this ticket adds no mechanism.

Keep it minimal per op. The test of whether a count belongs is whether an
operator would act differently on seeing it; "3 chunks force-assigned this run"
passes that test, "47 dot products computed" does not.

## Acceptance criteria
- [ ] `update`, `repair`, `monitor` and `cluster` each return a result of counts,
      persisted with the job.
- [ ] A force-assign and a collected (rather than clustered) build are each
      visible from the job alone.
- [ ] Ops that genuinely have nothing to report still persist nothing.
- [ ] A regression test per op asserts the counts it reports.
- [ ] `ruff format`, `ruff check --fix`, `pytest` clean.

## Out of scope
- Any change to #132's mechanism or to the `jobs.result` shape.
- Rendering history (M10) or an `update_log` reader.
- Changing any op's decisions.

## Review log
- 2026-09-21 PO: authored at #132's close from qa's note. `medium`, not `high`:
  #132 closed the case that could silently serve a stale brief, which was the
  urgent one. This is the same idea applied where it is useful rather than where
  it is dangerous, and each op can adopt it as it is next touched.

## PO triage 2026-09-21 — promoted to `todo`, priority confirmed `medium`

Promoted now because #138 just shipped `hrono jobs get`, which RENDERS a job's
result — so an op that reports nothing is now visibly a gap rather than a
theoretical one. The ops that force placements (the incubator's force-assigns,
repair's migrations, #112's collect-instead-of-cluster) are exactly what an
operator wants counted after running one verb over six stages.

## Review log (dev)
- 2026-09-21 dev: implemented and committed as `e90e6ea`. All five criteria.

  Four ops now return counts through #132's mechanism, and the `sync` chain
  aggregates them so one verb still answers "what happened?" in one place:

  | op | what it now says |
  |---|---|
  | `update` | `changed`, `batch`, **`forced`**, `parked` |
  | `monitor` | `measured`, `rate`, `baseline`, **`above_baseline`** |
  | `repair` | `dissolved`, `split`, `migrated`, **`freed`**, `reparented` |
  | `cluster` | `sections`, `topics`, `attached`, **`collected`** |

  The bolded ones are the judgements the ticket is about. A **force-assign** is
  the system deciding an alien member is better than an unreachable one (#086
  T35.3) — a real call, made silently until now. **`freed`** is a pioneer #113
  released. **`collected`** is #112's one-topic build, which from outside is
  indistinguishable from a normal small-corpus tree — legitimate for eight
  sections, alarming for eight hundred.

  `monitor` reports the MOVE (`above_baseline`) rather than only the rate,
  because a fresh tree's misfit rate is nonzero by nature and the bare number
  is not actionable.

  Test of "would an operator act differently on seeing it": `47 dot products`
  fails, `3 chunks force-assigned this run` passes. Nothing of the first kind
  is reported.

  Tests (7 new, 912 total) across four files, plus the chain's shape test
  extended. Mutations, all killed: `collected` pinned False, a dissolve not
  counted, the forced query looking for the wrong flag, `changed` always False,
  and the chain dropping its stages' counts.

  Not touched: #132's mechanism, `update_log` rendering (M10), and no op's
  decisions.

  Gate clean: `ruff format`, `ruff check --fix`, `pytest` **912 passed**.
- 2026-09-22 qa: **FAIL — back to todo.** The counts are all computed and the
  shape is asserted; two of them are never checked for a VALUE, so the
  arithmetic behind them is free.

  **Blocking — `freed` and `reparented` are shape-only.**
  ```
  mutation                                     result
  done["freed"] += moved   (was min(moved, forced))   311 passed
  done["reparented"] = 0   (dropping the count)       311 passed
  ```
  `freed` is the headline number of this ticket — a pioneer #113 released is
  exactly the decision the PO promoted this card for — and as it stands it could
  report every migration as a freed pioneer without a test noticing. That is
  worse than not reporting it: an operator reading "freed: 7" would believe
  seven alien members were revisited when the true number might be zero.
  `reparented` has the same hole one level up.

  `test_repair_reports_what_it_did` asserts `set(outcome)` and `dissolved == 1`,
  so the other three ride along on the shape check.

  Fix: extend that test, or add one beside it, that plants a forced member with
  a better home (the fixture in `test_repair.py` already does this for #113) and
  asserts `freed == 1` while `migrated` is larger — the two must be able to
  disagree, which is the whole point of `min(moved, forced)`. Same for
  `reparented` with a mis-attached child.

  **What I verified as PASSING (need not be redone):**
  - Gate: ruff clean, **912 passed**.
  - Mutations dev ran, re-run by me, plus one of mine: `above_baseline` pinned
    True fails 1.
  - **Reporting the MOVE rather than the bare rate is the right call.** A fresh
    tree's misfit rate is nonzero by nature, so "rate: 0.14" is not actionable
    and "above_baseline: true" is.
  - `collected` is the one I would have asked for if it were missing: #112's
    one-topic build is legitimate for eight sections and alarming for eight
    hundred, and from outside they are identical.
  - The chain aggregating its stages keeps one verb answerable in one place;
    dropping the stage counts fails 2.
  - Nothing of the "47 dot products" kind is reported. The counts are all things
    an operator would act on.
- 2026-09-22 dev: **re-picked up after qa's FAIL**; fixed. Tests only.

  qa is right, and the framing is the useful part: a count whose VALUE is never
  asserted is worse than no count. An operator reading "freed: 7" would believe
  seven alien members were revisited; with `freed += moved` the true number
  could be zero and nothing would fail.

  `test_freed_counts_pioneers_not_migrations` plants a cluster holding ONE
  forced pioneer and TWO ordinary misfits that also migrate, so `migrated` and
  `freed` must disagree — 3 and 1. That is the whole point of `min(moved,
  forced)` and it could not be checked while every migration in the fixture was
  a forced one.

  `test_repair_reports_the_children_it_reparented` does the same one level up,
  reusing #123's mis-attached fixture: `reparented == 1`.

  Mutations, now all killed: `freed += moved` fails 1, `reparented = 0` fails 1,
  `freed` never incremented fails 1.

  Gate clean: `ruff format`, `ruff check --fix`, `pytest` **914 passed**.
  Handing back to verifying.
- 2026-09-22 qa: **PASS — to po-review.** Both findings closed, re-run by me:
  `freed += moved` fails 1, `reparented = 0` fails 1.

  The fixture is the right shape — one forced pioneer beside two ordinary
  misfits, so `migrated` (3) and `freed` (1) are forced to disagree. A count
  that cannot disagree with its neighbour is not being tested, it is being
  spelled.

  Everything in my previous PASS list stands: reporting the MOVE rather than the
  bare misfit rate, `collected` distinguishing #112's one-topic build from a
  real one, and the chain keeping one verb answerable in one place.

  Gate re-run by me: **914 passed**, ruff clean.

## Review log (PO)
- 2026-09-22 PO: **PASSES — closed to done.** All five criteria met.

  #132 made an outcome possible; this makes the ops that force placements use
  it. The four counts I care about are all there: a **force-assign** (the system
  deciding an alien member beats an unreachable one), a **freed pioneer**, a
  **collected** rather than clustered build, and the misfit rate's **move**
  against its baseline rather than the bare number.

  Reporting the move is the judgement worth keeping. A fresh tree's misfit rate
  is nonzero by nature, so "0.14" tells an operator nothing and "above baseline"
  tells them whether to look.

  **qa's kickback is the sharpest observation of this batch: a count whose value
  is never asserted is worse than no count.** "freed: 7" would have an operator
  believe seven alien members were revisited when the true number could be zero
  — a report that is confidently wrong, which is the failure mode this whole
  month of work has been about. The fixture that fixes it forces `migrated` and
  `freed` to disagree, which is the only way to test a count that is defined as
  a subset of another.

  **This closes the backlog triage batch — all six promoted tickets are done.**
  Board: 118 closed, nothing in flight.
