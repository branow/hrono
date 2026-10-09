---
id: 112
title: A corpus under the smallest clustering rung builds no leaf level at all
priority: medium
size: small
depends_on: [094]
spec_refs: [how-hrono-works.md, clustering-lifecycle.md]
found_by: dev while implementing 094 on 2026-09-14
---

## Context
094 scaled the clustering recipe to the point count: the settled leaf recipe
(UMAP-25, `min_cluster_size` 5) serves N >= 27, the spec's smaller recipe
(UMAP-10, `min_cluster_size` 3) serves N >= 12, and below 12 `recipe_for` raises
`ClusterError` — "this level cannot be reduced further".

That is the right answer near the ROOT (`build-tree` reads it as "the current
top is the root" and `_collect_root` parents the survivors). It is a worse
answer at the LEAF: a corpus of, say, 8 sections raises `ClusterError` out of
the `cluster` op, so the tree has no level 0, no briefs, and nothing to export.
The old floor was 27 sections (F15), so this is a strict improvement, not a
regression — but the floor is still there.

## Description
Decide what a corpus too small to cluster should produce. The cheap, honest
options: one leaf topic holding every section (the same "collect" move
`_collect_root` already makes at the top), or a clean "corpus too small to
build a tree" job error that the CLI explains. Inventing a third UMAP rung
below 10 dims is NOT one of them — the spec names two recipes and the scaling
ladder should stay data derived from it.

## Acceptance criteria
- [ ] `hrono maintain` over a corpus of a handful of sections either builds a
      usable one-topic tree or fails with an explicit, actionable message.
- [ ] `ruff format`, `ruff check --fix`, `pytest` clean.

## Decision (2026-09-14, PO — after closing #094)

**Collect, do not fail.** A corpus too small to cluster builds ONE leaf topic
holding every section, briefs it, and exports normally — the same "collect"
move `_collect_root` (`summarize/build_tree.py:71`) already makes at the top of
the tree when clustering stops reducing.

Why, against the "explicit error" alternative: a small repo is a completely
legitimate corpus, and the product bar is that the real flow works end to end.
Telling a user with an 8-section repo that hrono cannot build a tree for them is
a dead end, not an answer — and it is inconsistent with what we already do one
level up, where "too few points to reduce" means "then this IS the node", not
"then fail". A tree of one topic is a correct, usable, walkable map of a small
corpus; recall and export both work over it unchanged. One rule, applied at both
ends of the tree.

Not in scope: a third UMAP rung below 10 dims (the ticket already rules this
out, correctly — the ladder stays data derived from the spec's two recipes), and
any change to the ladder's floors.

## Acceptance criteria (superseding the above)
- [ ] A corpus below `recipe.MIN_POINTS` clustered by the `cluster` op produces
      one level-0 node containing every section, rather than raising out of the
      op.
- [ ] That tree briefs and exports normally: `maintain` over a handful of
      sections yields a single root with content, and `hrono tree export`
      renders `root.md`.
- [ ] `recipe_for` still raises `ClusterError` below the smallest rung — the
      collect is the CALLER's decision, not a new rung. `build_tree` must keep
      reading that `ClusterError` as "the current top is the root" (#094).
- [ ] A regression test drives the real backend over a sub-12-section corpus
      end to end and asserts one topic, one root, and a rendered `root.md`.
- [ ] `ruff format`, `ruff check --fix`, `pytest` clean.

## Review log
- 2026-09-14 PO: confirmed as a correct out-of-scope filing from #094, not a
  defect of it — the floor moved 27 -> 12, a strict improvement, and this
  ticket exists because that change forced a product question that had not been
  asked before. Priority confirmed **medium** (real gap, but every corpus the
  project has actually run is far above the floor; it sits behind the blockers).
  Made the product call above so the ticket is executable without coming back to
  me, and promoted backlog -> todo.
- 2026-09-21 dev: started; moved to in-progress (batch with #105, #110, #113,
  #101).
- 2026-09-21 dev: implemented and committed as `88aa928`.

  **Collect, exactly as the PO ruled, and at the CALLER.** `cluster/op.py`
  catches the `ClusterError` the ladder raises and builds `_one_topic`: one
  level-0 node holding every section, nothing attached, no similarities. The
  ladder itself is untouched — `recipe_for` still raises below `MIN_POINTS`, so
  `build_tree` keeps reading that same error as "the current top is the root"
  (#094), which criterion 3 requires and a test now pins.

  **No coordinates are written for a collected build**, because no reduction
  ran. `stored_coords` then returns None and the next build inits fresh, which
  is correct: there is no layout to preserve. (This is also why #101's backfill
  writes nothing on such a tree — the two tickets agree on the same rule.)

  **Driven over the REAL backend**, as criterion 4 asks: a 3-file repo through
  the whole `maintain` pipeline with no `build=` injection, so the real recipe
  raises and the collect is what catches it. Asserted end to end: `nodes` is
  exactly `{level 0: 1}`, the root brief has content, every leaf is reachable,
  and `render(collapse(...))` produces a non-empty `root.md`. Section count is
  asserted BELOW `MIN_POINTS` in the same test, so the test cannot quietly stop
  exercising the path it was written for.

  Tests (2 new, 789 total). Mutations: removing the collect fails 1 (the corpus
  cannot build at all — the defect), one-node-per-section fails 1, and marking
  every member `attached` fails 1 once I added the assertion for it — that flag
  is a claim about HOW a member arrived and #114/#124 read it, so leaving it
  unpinned would have been the one-sided assertion again.

  Gate clean: `ruff format`, `ruff check --fix`, `pytest` **789 passed**.
- 2026-09-21 qa: **FAIL — back to todo.** The collect itself is right and the
  end-to-end evidence is real, but it is reached through `except ClusterError`,
  and that is not the error the ticket is about. `build_clusters` raises the
  SAME exception for at least five other reasons, so a corpus of any size whose
  clustering genuinely FAILED is now silently rebuilt as one topic and the job
  reports success.

  **Blocking — `src/hrono/cluster/op.py:52-55` catches every `ClusterError`,
  not "too few points".** The raise sites in `src/hrono/cluster/build.py`:
  | line | message |
  |---|---|
  | 108 | `clustering produced no clusters` |
  | 146 | `the reduction failed on these vectors` |
  | 164 | `the clusterer failed on these vectors` |
  | 171, 179 | `clustering backend is not installed` |
  Only `recipe.py:53` (`too few vectors to cluster`) is this ticket's case.
  Driven, on a 400-section corpus with a builder that raises build.py:146's
  error verbatim:
  ```
  nodes by level: [(0, 1)]        <- one topic
  members in that node: 400       <- the entire corpus
  ```
  The job then reports success. That is F16's failure mode turned inside out:
  before #094 a broken reduction failed loudly; after this commit it produces a
  confident, wrong, single-topic map of a corpus that has 400 sections in it,
  which the user has no way to tell from a correct small-corpus tree. A silently
  degraded tree is worse than a failed job — it is the read door lying again.

  Fix: decide on the POINT COUNT, which is what the ticket is about, and let
  every other `ClusterError` fail the job as it did before:
  ```python
  if len(vectors) < MIN_POINTS:
      result = _one_topic(len(vectors))
  else:
      result = builder(vectors, init=init)
  ```
  `cluster/recipe.py` imports nothing heavy (just `ClusterError` and
  `dataclasses`), so `op.py` can read `MIN_POINTS` without pulling the numeric
  stack in — the property its module docstring is careful about.
  Then add the test that would have caught it: a corpus ABOVE `MIN_POINTS` whose
  builder raises `ClusterError` must still raise out of the op.

  **What I verified as PASSING (need not be redone):**
  - The end-to-end test is genuine: no `build=` injection, the real recipe
    raises, and the assertions (`{0: 1}`, root brief with content, every leaf
    reachable, non-empty `root.md` through the real `collapse`/`render`) all
    hold. Asserting the section count is below `MIN_POINTS` inside the test is
    the right guard against it quietly ceasing to exercise the path.
  - `recipe_for` still raises below its floor, and `build_tree` still reads that
    as "the current top is the root" — criterion 3 holds, and is now pinned.
  - The `attached`/`assignment_similarity` assertion is the right call: nothing
    was attached by proximity because nothing clustered, and #114/#124 read that
    flag.
  - Writing no coordinates for a collected build is correct and consistent with
    #101's rule.
- 2026-09-21 dev: **re-picked up after qa's FAIL**; fixed as `0f4aedb` on top of
  `88aa928`. Nothing qa passed was redone.

  **qa is right, and the finding was worse than a bug in this ticket.** Catching
  `ClusterError` turned five distinct backend FAILURES into a confident,
  wrong, single-topic map of a corpus of any size, with the job reporting
  success. I reproduced it before fixing: 400 sections, a builder raising
  build.py:146's message verbatim, result `nodes by level [(0, 1)]`, 400 members
  in that one node.

  **The fix is a type, not a count.** My first attempt was qa's suggestion —
  gate on `len(vectors) < MIN_POINTS` — and it broke five existing tests, which
  is the right answer for the wrong reason: the ladder's floor is a property of
  the REAL recipe's spectral init, and a test seam injecting a small fake build
  can legitimately cluster 6 vectors. Gating on the count in the op would have
  made the seam meaningless and changed behaviour for any alternative builder.

  So the refusal got its own type: `cluster.TooFewPoints(ClusterError)`, raised
  by `recipe_for` and caught by nothing else. The op catches only that; every
  other `ClusterError` propagates and fails the job as before. `build_tree`'s
  `except ClusterError` still catches it by inheritance, so criterion 3 is
  unaffected — verified by its existing tests.

  This is the honest shape of the distinction: the ladder's refusal is the one
  clustering failure that is not a failure, and a caller may answer it by
  collecting. Saying that in the type means neither caller can catch a broken
  backend by mistake, which a comment could not guarantee.

  **The regression test qa asked for**:
  `test_a_broken_backend_fails_the_job_it_does_not_collect` — a corpus above the
  floor with a builder raising a plain `ClusterError` must raise out of
  `maintain` and leave `nodes` empty (nothing invented on the way out).
  Mutations: widening the catch back to `ClusterError` fails it; removing the
  collect fails the small-corpus test.

  Re-ran qa's own reproduction against the fix: `raises as it must: the
  reduction failed on these vectors`, `nodes: 0`.

  Gate clean: `ruff format`, `ruff check --fix`, `pytest` **790 passed**.
  Handing back to verifying.
- 2026-09-21 qa: **PASS — to po-review.** The finding is closed, and closed
  better than I suggested.

  **The type is the right answer; my count gate was not.** I proposed
  `len(vectors) < MIN_POINTS`; dev tried it, it broke five existing tests, and
  the reason is sound — the ladder's floor is a property of the REAL recipe's
  spectral init, and a test seam injecting a small fake build can legitimately
  cluster 6 vectors. Gating on the count in the op would have made the seam
  meaningless. `TooFewPoints(ClusterError)` expresses the actual distinction:
  the one clustering refusal a caller may answer by collecting.

  **Verified independently:**
  - My own reproduction, re-run against the fix: 400 sections, a builder raising
    build.py:146's message verbatim -> `raises as it must: the reduction failed
    on these vectors`, `nodes: 0`. Nothing invented on the way out.
  - **The raise site is outside the wrapping try, which is what makes this
    work.** `recipe_for` is called at `build.py:134` and `:157`, both BEFORE the
    `try` that converts any exception into a plain
    `ClusterError("the reduction failed...")`. Had it been inside, the new type
    would have been re-wrapped and the fix would have been cosmetic. Checked
    rather than assumed.
  - `TooFewPoints` is caught in exactly two places: `op.py:62` (this ticket) and
    `build_tree.py:70` by inheritance, which is criterion 3 — confirmed live
    that `except ClusterError` still catches it.
  - Every other raise site in `build.py` (79, 108, 127, 146, 164, 171, 179) is
    still a plain `ClusterError` and still fails the job.
  - Mutations: widening the catch back to `ClusterError` fails the new test;
    removing the collect fails the small-corpus test.

  **Filed, not blocking: #131.** `build_tree.py:70` has the SAME broad catch one
  level up, so a broken backend at an upper level is read as "the current top is
  the root" and produces a truncated tree that reports success. Pre-existing, and
  now trivially fixable because this ticket created the type that expresses it.

  Gate re-run by me on the committed state: `ruff format --check` 230 files
  already formatted, `ruff check` clean, `pytest` **790 passed**. Both commits
  atomic and conventional.

## Review log (PO)
- 2026-09-21 PO: **PASSES — closed to done.** All five criteria met, including
  the ones I added when I made the product call.

  The call was "collect, do not fail", and that is what shipped: a small repo is
  a legitimate corpus and a one-topic tree is a correct, walkable map of it.
  Briefed, exported, every leaf reachable, driven over the REAL recipe with no
  build seam — that is the product bar ("it actually works end to end") met the
  way I meant it.

  **What I most want recorded is the round it took.** The first implementation
  reached the collect through `except ClusterError`, and qa proved on a
  400-section corpus that a genuinely broken reduction was then silently rebuilt
  as one topic with the job reporting success. That is the same defect my own
  ruling was trying to avoid, arriving from the other direction: I said failing
  a small corpus is a dead end, and the fix turned a real failure into a
  confident wrong answer. **A degraded tree that reports success is worse than
  a failed job**, always — an operator can act on a failure and cannot act on a
  map they have no reason to distrust. If those two ever pull against each
  other again, this is the precedent.

  The resolution is better than either of the first two attempts, and I want the
  reasoning kept: `TooFewPoints` is a distinct type because the ladder's refusal
  is the one clustering failure that is not a failure. A count check in the op
  would have said the same thing in the wrong place — it would have overridden
  an injected builder that can legitimately cluster six vectors, which is how it
  announced itself by breaking five tests. Encoding the distinction in the type
  means no future caller can catch a broken backend by mistake, and a comment
  could never have promised that.

  qa's **#131** — `build_tree` has the identical broad catch one level up, so a
  broken backend mid-tree truncates the tree and reports success — is the same
  defect at a different altitude and is now cheap because this ticket created the
  type. I have raised it to `medium` in backlog and it is the first thing I will
  promote from that list.
