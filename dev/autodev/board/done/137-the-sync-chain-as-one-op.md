---
id: 137
title: `sync` — one op that brings a tree up to date, in the right order
priority: high
size: medium
depends_on: [085, 087, 089, 090, 122]
spec_refs: [build-order.md#T34, build-order.md#T36, implementation-notes.md]
found_by: split from #106 at the PO ruling on note D, 2026-09-21
---

## Context
Split 1 of 3 from #106, which was `big`. This one is the product decision made
real; #138 exposes it, #139 is the debug escape hatch.

**hrono's differentiator is incremental update, and today a user cannot run it.**
`update`, `propagate`, `monitor` and `repair` are implemented and tested, and
the only thing anyone can trigger is `maintain` — a full cold rebuild. So after
changing their code, a user's only supported option is the expensive thing hrono
exists to avoid.

Exposing the pieces separately is not the answer, and the reason is measured:
#122 was exactly the bug where the chain skipped a step, and the result was
briefs citing sources they had never read — a map that looks right and is
quietly wrong, with no error anywhere. Steps that must run in order should be
one thing that cannot be sequenced incorrectly.

## Description
Add a `sync` op that runs, in order, over one tree:

```
update  ->  brief (stale leaves)  ->  brief-upper (stale uppers)
        ->  propagate  ->  monitor  ->  repair
```

`update` already owns sync/diff/reconcile/embed/place/age/drain/condense as of
#122, so this op composes existing ops rather than reimplementing anything —
the same way `maintain` composes the cold-build ops today. Read `tree/maintain.py`
first; this is its incremental twin and should look like it.

**`settle` is NOT in the chain.** It is expensive and stays explicitly invoked
(PO note D.3): its churn trigger informs, it does not fire. If the trigger has
fired, say so in the result rather than acting on it.

**`maintain` keeps its job** — the cold build, for a tree that does not exist
yet. Do not fold the two together; a first build and an update are different
operations with different costs, and conflating them is how a user accidentally
pays for a rebuild.

**Report what it did** (#132's mechanism, already built): return counts per
stage, and set `incomplete` when a stage declined work. A user who runs one verb
over ten stages needs the result to say what happened, or the single verb
becomes a black box — which is the honest objection to this design and the thing
that answers it.

## Acceptance criteria
- [ ] `sync` is registered in `OPS` and runs the chain above in order over a
      tree that already exists.
- [ ] It composes the existing ops; no stage logic is reimplemented.
- [ ] `settle` is not run, and the result says whether its trigger has fired.
- [ ] The result carries per-stage counts and `incomplete`, persisted on the job
      (#132).
- [ ] A test drives the REAL chain over a built tree with a changed file and
      asserts the tree is up to date afterwards: the changed leaf re-briefed,
      its ancestors marked, and no member left uncondensed (#122's invariant).
- [ ] A stage that fails fails the job with which stage it was, and leaves the
      database consistent — no half-applied chain.
- [ ] `maintain` is unchanged and still does the cold build.
- [ ] `ruff format`, `ruff check --fix`, `pytest` clean.

## Out of scope
- The HTTP endpoint and CLI command (#138).
- The generic op trigger (#139).
- `settle` automation of any kind.

## Review log
- 2026-09-21 PO: split from #106 at note D's ruling. `high` — it is the
  differentiator, unreachable. Sized `medium` because it composes ops that all
  exist; if it starts growing stage logic of its own, that is the signal to stop
  and come back to me.

## Review log (dev)
- 2026-09-21 dev: started; moved to in-progress.
- 2026-09-21 dev: implemented and committed as `fdc577a`.

  ## The chain order in the ticket is WRONG, and a test caught it

  The ticket (and PO note D, and #106 before it) specifies:
  ```
  update -> brief -> brief-upper -> propagate -> monitor -> repair
  ```
  **With that order `propagate` is a no-op.** It judges a leaf's NEW content
  against its STORED brief — the old one — and marks the ancestors above it
  stale. Running `brief` first rewrites that brief with the CURRENT member
  signature, so `_changed_leaves` finds nothing, nothing is judged, and no
  ancestor is ever marked. The upper levels keep describing content that changed
  underneath them, silently and for ever.

  I found it because the failing-stage test used an exploding judge and the
  judge was never called. Shipped order:
  ```
  update -> propagate -> brief -> brief-upper -> monitor -> repair
  ```
  `propagate` marks ancestors stale, THEN `brief` regenerates the changed
  leaves and `brief-upper` the ancestors that propagate just marked. There is a
  test that fails if the two are swapped back, and the reasoning is in the
  module docstring rather than only here — this is the sharpest possible example
  of why the ticket's premise (the order is load-bearing, expose one verb) is
  right.

  ## The rest

  **Name.** The op is `sync-tree`, not `sync`: `sync` is already the per-source
  ingest op. Matches `build-tree`'s shape. The CLI verb #138 adds can still be
  `hrono tree sync`.

  **Composition only.** Six existing ops called in order, the same way
  `maintain` composes the cold-build ops — no stage logic reimplemented, and the
  seams (`encoder_for`, `client`, `core_labeler`) threaded through so the chain
  is drivable in tests exactly as `maintain` is.

  **`settle` is reported, never run.** `should_settle` is read at the end and
  returned as `settle_due`. A test forces drift to 9999, asserts the trigger
  fires, and asserts no node id changed — hrono saw the trigger and did nothing,
  which is PO note D.3 made testable.

  **The result (#132).** Per-run counts plus `settle_due` and `incomplete`.
  One verb over six stages is a black box unless it reports, which is the honest
  objection to this design; this is the answer to it.

  Tests (7 new, 855 total): registered under its own name; a changed file leaves
  the tree up to date with #122's no-uncondensed-member invariant holding; the
  result's shape; settle reported-not-run; a failing stage propagating out with
  earlier stages' work committed; `maintain` untouched; and the ordering test.
  Mutations: swapping brief and propagate fails 2, running settle inside the
  chain fails 1, dropping `update` fails 2.

  Gate clean: `ruff format`, `ruff check --fix`, `pytest` **855 passed**.
- 2026-09-21 qa: **FAIL — back to todo.** The ordering discovery is excellent
  and I have verified it at source. But the chain's whole value is that all six
  stages run, in order, and **three of them can be deleted with the suite
  staying green.**

  **Blocking — `brief-upper`, `monitor` and `repair` are unpinned.**
  ```
  mutation                                            result
  brief_upper(...) -> pass                            62 passed
  repair(...)      -> pass                            62 passed
  monitor(...)     -> pass                            62 passed
  "incomplete": bool(judged...) -> False              62 passed
  ```
  The most serious is `brief-upper`. `propagate` marks ancestors stale and that
  is ALL it does — "MARKS ONLY: it never regenerates a brief" is the first line
  of its own docstring. If `brief-upper` never runs, the chain leaves the tree
  in exactly the state the ordering fix was meant to prevent: ancestors known to
  be wrong, flagged as wrong, and still serving their old text. Deleting the
  stage that fixes them changes nothing any test can see.

  **The assertion that should have caught it is vacuous.**
  `test_a_changed_file_leaves_the_tree_up_to_date` asserts `stale >= 0`, which
  is true of every possible run, and `briefed >= leaves`, which held before the
  run too. The ticket's criterion asks for "the changed leaf re-briefed, its
  ancestors marked" and only the third clause (no member left uncondensed) is
  actually checked.

  Fix — assert the chain's effect, not its shape:
  - after the run, an ancestor of the changed leaf has a REGENERATED brief. The
    cleanest signal is that propagate marked it and `brief-upper` then cleared
    the mark: capture the ancestor's `member_signature`/`stale` before the run
    and assert the brief row changed and `stale` came back to 0. Deleting
    `brief_upper` must fail that.
  - `monitor` ran: the `misfit` table carries rows for this tree afterwards (it
    is empty on a tree that has only ever been `maintain`ed with no update).
  - `repair` ran: it already takes a `core_labeler` seam — pass a recording one
    and assert it was reached, or assert a repair-visible effect.
  - `incomplete` is carried from the judge: drive a run whose panel abstains
    (#105 made that reachable) and assert `incomplete is True`.

  **What I verified as PASSING (need not be redone):**
  - Gate: 237 files formatted, ruff clean, **855 passed**.
  - **The ordering finding is real and I confirmed it at source**, not from the
    log: `propagate._changed_leaves` skips a leaf when
    `signature == brief["member_signature"]` (`propagate.py:116`), and
    `brief` writes `member_signature=signature` (`brief.py:98`). Brief first
    therefore guarantees propagate selects nothing. The docstring records it
    where the next reader will meet it, and swapping the two fails two tests.
    This is a genuine defect in a chain the project has had written down since
    September, found by noticing that an exploding judge was never called —
    exactly the instinct #128 asks for.
  - `sync-tree` rather than `sync` is right (`sync` is the per-source ingest op)
    and the name matches `build-tree`.
  - Composition only: six existing ops, seams threaded, nothing reimplemented.
  - **`settle` reported-not-run is properly pinned**: drift forced to 9999, the
    trigger asserted True, node ids asserted unchanged. `settle_due` hardcoded
    False fails it. That is PO note D.3 made testable, and it is the one
    behavioural claim in this ticket I could not break.
  - A failing stage propagates out with earlier stages' work committed.
- 2026-09-21 dev: **re-picked up after qa's FAIL**; fixed. Tests only — the
  chain itself is unchanged, so everything qa passed stands.

  qa is right and the finding is embarrassing in a useful way: I wrote a ticket
  whose entire premise is "all six stages must run in order", then tested the
  ordering and left three stages deletable. `assert stale >= 0` is true of every
  run; `briefed >= leaves` held before the run too. Two vacuous assertions in
  the test that carries the criterion.

  **Each stage is now pinned by its EFFECT, which is what made the difference.**
  Asserting "the stage ran" needs a seam; asserting what the stage leaves behind
  needs nothing and cannot be satisfied another way:

  | stage | what now fails without it |
  |---|---|
  | `update` | the changed file is never ingested — 4 tests |
  | `propagate` | nothing is judged, ancestors unmarked — 4 tests |
  | `brief` | the changed leaf's own brief is not rewritten |
  | `brief-upper` | an ancestor's brief is not regenerated and the stale mark is never cleared |
  | `monitor` | the `misfit` table has no rows for the tree — 2 tests |
  | `repair` | a planted below-two-member cluster is still there afterwards |

  **The fake LLM was half the problem.** It returned the same sentence for every
  brief, so a regenerated brief was indistinguishable from an untouched one —
  "did this stage run?" was literally unanswerable from the database. Brief
  replies are now numbered, and that one change is what let `brief` and
  `brief-upper` be pinned at all. Worth remembering: a constant fake makes
  regeneration invisible.

  **`repair` needed a planted condition.** A healthy little tree gives it
  nothing to do, which is why deleting it was invisible rather than merely
  untested. The test now plants a cluster with one member — below the dissolve
  floor — and asserts it is gone after the run, so the stage is asserted by
  doing its job rather than by being reached.

  **`incomplete`** is pinned by a run whose judge declines every panel (#105
  made that reachable, #132 made it reportable): `abstained > 0` and
  `incomplete is True`.

  Gate clean: `ruff format`, `ruff check --fix`, `pytest` **858 passed**.
  Handing back to verifying.
- 2026-09-21 qa: **PASS — to po-review.** The three stages I failed this on are
  pinned, and re-run by me: dropping `brief-upper` fails 1, `monitor` fails 2,
  `repair` fails 1. I also re-tried the three that already failed (`update`,
  `propagate`, `brief`) and they still do. Every stage of the chain is now
  individually killable, which is the property this op exists to have.

  **Pinning by EFFECT rather than by reaching the stage is the right choice**
  and better than what I suggested. I offered a recording `core_labeler` seam
  for `repair`; planting a below-two-member cluster and asserting it is gone
  afterwards asserts the stage did its JOB, and cannot be satisfied by the stage
  merely being called. That distinction matters for a chain whose whole claim
  is that the stages do something in order.

  **The numbered fake is the detail I would have missed.** A constant fake LLM
  made a regenerated brief indistinguishable from an untouched one, so "did this
  stage run?" was unanswerable from the database regardless of how the assertion
  was written. Noticing that the FIXTURE, not the assertion, was the obstacle is
  the harder half of this fix.

  Everything in my previous PASS list stands, including the ordering discovery —
  which I had already confirmed at source (`propagate.py:116` vs `brief.py:98`)
  and remains the most valuable thing in this ticket.

  Gate re-run by me: **858 passed**, ruff clean, 237 files formatted. Commit is
  test-only and atomic.

## Review log (PO)
- 2026-09-21 PO: **PASSES — closed to done.** All eight criteria met.

  **The chain order in my own ruling was wrong, and this ticket caught it.**
  PO note D, #106 before it, and this ticket's own Description all specified
  `update -> brief -> ... -> propagate`. In that order `propagate` selects
  nothing: it judges a leaf's new content against its STORED brief, and briefing
  first overwrites that brief with the current signature. The upper levels would
  have gone on describing content that changed underneath them — silently, with
  no error, on every run of the one command a user is supposed to trust.

  I am recording that prominently because of what it says about the decision it
  sits inside. The argument for one verb was that the stages are order-coupled
  and the coupling is not obvious. **The project had the order written down
  wrongly for two weeks and nobody noticed** — including me, twice. That is the
  argument, demonstrated on itself. Eight separate commands would have shipped
  this bug to every operator and called it flexibility.

  It was found by noticing that a deliberately-exploding judge was never called.
  A test written for error handling caught a design defect because someone asked
  why it passed.

  **qa's kickback was correct and its resolution improved on its own
  suggestion.** Three of six stages were deletable with the suite green — on a
  ticket whose premise is that all six must run. Pinning each by its EFFECT
  rather than by reaching it is the stronger form, and finding that the constant
  fake LLM was the real obstacle (a regenerated brief was indistinguishable from
  an untouched one) is the part I would not have thought to look for.

  `settle` reported-never-run is pinned with drift forced past its threshold and
  node ids asserted unchanged. That is D.3 — hrono does not spend money unasked
  — made testable rather than promised.

  **PO note D's chain is now corrected in place** so the next reader inherits
  the right order rather than the one I wrote. #138 and #139 carry the rest of
  the surface.
