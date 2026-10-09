---
id: 094
title: Clustering must handle small inputs — UMAP needs N >= 27 and raises TypeError below it
priority: blocker
size: medium
depends_on: []
spec_refs: [build-order.md#T18.1, build-order.md#T22.3, clustering-lifecycle.md]
found_by: e2e manual QA 2026-09-03 — .e2e/FINDINGS.md F15, F16, F17, F18
---

## Context
`UMAP_DIMS = 25` means spectral init requests `k = 26` eigenvectors, which
requires `N > 26`. Measured against the real `_default_reduce`
(`.e2e/artifacts/umap-threshold.md`):

| N | outcome |
| --- | --- |
| 5, 7, 10, 15, 20, 25, 26 | `TypeError: Cannot use scipy.linalg.eigh for sparse A with k >= N` |
| 27, 28, 30, 40 | ok |

It raises `TypeError`, not `ClusterError`, so every caller's guard misses it.

## Description
Three consequences observed on a real 3-repo corpus:
- **`build-tree` crashes instead of declaring a root (F16).** With 7 leaf nodes,
  `maintain` failed with the scipy TypeError after 92 condensations. The
  `except ClusterError: break` guard in `summarize/build_tree.py` — written for
  exactly this "too sparse near the root" case — never fires, `_collect_root` is
  never reached, and the tree stays one level deep. `settle(force=True)` fails
  the same way.
- **A corpus under 27 sections cannot be clustered at all (F15).**
- **`incubator.drain` gates at `MIN_CLUSTER_SIZE = 5` then calls the 27-input
  recipe (F17)** — every drain of a 5..26-chunk pool raises.

No test catches any of it (F18): `test_build_tree`, `test_levels` and
`drain` all inject seams, and the one real-recipe harness
(`tests/cluster/harness.py:planted_groups`) defaults to 76 vectors.

Work:
- Guard `_default_reduce` on `len(vectors) <= UMAP_DIMS + 1`: either reduce
  `n_components`, or pass `init="random"` (skips the spectral solve), or raise
  `ClusterError` — pick one and document why.
- Make sure `build_tree`, `cluster`, `cluster_briefs` and `incubator.drain` all
  behave sanely at small N (root declared, clean error, or successful reduce).
- Align `incubator.drain`'s gate with whatever the clusterer actually needs.

## Decision (2026-09-12, revised after PO review)

The first read of this was wrong. It is not "guard a crash" — the implementation
**ignores a rule the spec already states**. `how-hrono-works.md:109`:

> Upper levels reuse the same machinery on smaller inputs. The briefs of a level
> are embedded ... and clustered with the same UMAP -> HDBSCAN -> attachment
> pipeline, **with dimensions and `min_cluster_size` scaled to the point count**
> (e.g. UMAP-10, `min_cluster_size=3` at tens of topics).

`cluster/build.py` applies the baked leaf constants (`UMAP_DIMS = 25`,
`MIN_CLUSTER_SIZE = 5`) at EVERY level, so an upper level of 7-50 topics is
reduced with parameters meant for thousands of sections. The scipy `TypeError`
is the symptom; unscaled parameters are the defect.

Fix:
- Scale the recipe to the point count, per the spec. `n_components` and
  `min_cluster_size` (and `n_neighbors`, which has the same `< N` constraint)
  become functions of N, baked as a small table — e.g. UMAP-25/mcs-5 at
  thousands, UMAP-10/mcs-3 at tens. Derive the exact steps from the spec and
  the prototype; keep them as data, not literals in the call.
- Below whatever N the smallest rung can serve, raise `ClusterError` — the
  honest "this level cannot be reduced further" signal that `build_tree`'s
  `except ClusterError: break` is already written for.
- Never let a driver exception (scipy/numba/sklearn) escape the backend.

With that, the 7-topic case resolves itself with no new policy: `build_tree`
tries to reduce 7 briefs, cannot, breaks, and `_collect_root` parents all 7
under a single root and briefs it — which is what the stored tree is supposed to
look like. A root is not special; it is just the one node left at the top.

## Acceptance criteria
- [ ] `build_clusters` and `core_labels` at N = 4, 10, 26, 27 either succeed or
      raise `ClusterError` — never a driver exception.
- [ ] Clustering parameters scale with the point count per
      `how-hrono-works.md:109`; the scaling steps live in one data table.
- [ ] `build-tree` over a level too small to reduce declares the current top as
      root and completes; `maintain` succeeds end to end on a corpus with a
      single-digit node count.
- [ ] A drain of a 5-chunk pool does not raise.
- [ ] `ruff format`, `ruff check --fix`, `pytest` clean.

## Review log
- 2026-09-14 dev: started. Implementing the 2026-09-12 revised decision —
  scale the recipe to the point count per `how-hrono-works.md:109` instead of
  guarding a crash; reading the spec, the prototype mini-pipeline clamp, and
  the three call sites (`cluster`, `cluster-briefs`, `incubator.drain`) first.
- 2026-09-14 dev: implemented (commit 2f8c6be). Per the revised decision this
  is a scaling fix, not a crash guard.
  **The ladder, as data.** New `src/hrono/cluster/recipe.py` holds `LADDER`, a
  tuple of frozen `Recipe(min_points, n_components, n_neighbors,
  min_cluster_size)` rungs, and `recipe_for(points)` returns the largest rung
  the point count can serve, raising `ClusterError` below the smallest:
  `(27, 25, 15, 5)` — the settled leaf recipe (`clustering-lifecycle.md`,
  `how-hrono-works.md`), whose floor is the measured one
  (`.e2e/artifacts/umap-threshold.md`: UMAP-25 fails at N=26, works at N=27,
  i.e. `n_components + 2`, because spectral init asks for `n_components + 1`
  eigenvectors of an N-point graph) — and `(12, 10, 10, 3)` — the spec's own
  smaller recipe, `how-hrono-works.md:109` "UMAP-10, `min_cluster_size=3` at
  tens of topics", floored the same way (10 + 2). `n_neighbors` is carried
  because it has the same `< N` constraint; the prototype's mini-pipeline
  clamps it the same way (`research.ipynb` step 22:
  `n_neighbors=min(15, max(2, n_pool - 1))`). Below 12 there is no rung: that
  is the honest "this level cannot be reduced further".
  **Why the rungs are floored at validity rather than at "tens".** The spec
  gives two recipes and one example, not a boundary. Anchoring each rung at
  the count it can actually serve keeps the settled recipe running wherever it
  is valid (no change to any corpus of 27+ points — the leaf path, the
  known-group recovery tests and the real 104-section e2e corpus all behave
  exactly as before, `n_neighbors=15` being UMAP's own default) and applies
  the smaller recipe only where the settled one physically cannot run. Moving
  the boundary up to ~100 instead would have swapped the recipe under every
  medium corpus: measured on the canonical fixtures, UMAP-10/mcs-3 at N=60 and
  N=76 fragments planted groups (ARI 0.86/0.87, 7-8 clusters for 5 planted)
  where the settled recipe scores 1.000. That is a behaviour change the ticket
  did not ask for.
  **Call sites.** `build.py` no longer exports `UMAP_DIMS`/`MIN_CLUSTER_SIZE`;
  `_default_reduce` and `_default_cluster` each derive the recipe from their
  own point count, so `cluster`, `cluster-briefs` and `incubator.drain` are all
  scaled without plumbing. Both now translate any driver failure
  (scipy/numba/sklearn) into `ClusterError`, so nothing but `ClusterError`
  leaves the backend. `incubator` drains and ages against `recipe.MIN_POINTS`
  instead of its own `MIN_CLUSTER_SIZE = 5` — a pool the mini-pipeline cannot
  reduce is not a drainable pool, and aging still empties a 5..11-chunk pool so
  nothing waits forever.
  **Tests.** New `tests/cluster/test_recipe.py` (rung selection, the
  below-the-ladder `ClusterError`, and the invariant that every rung is
  runnable at its own floor: `min_points >= n_components + 2`,
  `n_neighbors < min_points`). `tests/cluster/test_build.py` gains real-recipe
  (no seam) parametrised tests: N = 1/4/10/11 raise `ClusterError` from both
  `build_clusters` and `core_labels`; N = 12/26/27/40 cluster for real with
  full coverage and recipe-width coords. `tests/summarize/test_build_tree.py`
  gains a REAL-backend test over 7 leaf briefs asserting levels `{0: 7, 1: 1}`
  and a single root. `tests/cluster/test_incubator.py` gains a 5-chunk pool
  that does not raise and leaves the pool intact. Two existing tests adjusted:
  the drain test now parks `MIN_POINTS - 1` cores, and `test_levels`'s
  partition assertion compares as a set (it used `sorted()` over frozensets,
  which is a partial order — the label order flipped under the new rung while
  the partition stayed exactly the two planted groups).
  **Verified on the real corpus, not just in tests.** Copied
  `.e2e/run/.hrono/hrono.db` (the 3-repo run that died: 7 leaf nodes, 7 briefs,
  104 sections, model `minilm`) to scratch and ran `build_tree` in-process over
  it with the real clusterer and a stub completion client. Result: `levels
  [(0, 7), (1, 1)]`, root node 11 with all 7 children, 8 briefs, and the M6
  export renders `root.md` plus every topic directory — the deliverable that
  was unusable before. The original database was not touched.
  **Gate:** `ruff format` 219 files unchanged, `ruff check --fix` all checks
  passed, `pytest` 622 passed.
  **Filed, not fixed:** #112 (backlog) — below the smallest rung a LEAF corpus
  (< 12 sections) now builds no level 0 at all. Strictly better than the old
  27-section floor, still a floor; what a tiny corpus should produce is a
  product call.
- 2026-09-14 qa: REJECTED back to todo. The scaling design is right and most of
  it verified clean, but the commit introduces a new, non-self-healing failure
  in the warm-init path it did not account for.

  **Defect (blocking) — warm init and the recipe disagree on width across a
  rung change.** `src/hrono/cluster/build.py:129-141` (`_default_reduce`) passes
  `init` to UMAP unconditionally while deriving `n_components` from the point
  count, and `src/hrono/cluster/op.py:41` feeds it `store.stored_coords`
  (`src/hrono/cluster/store.py:45`), which returns whatever width the PREVIOUS
  build wrote. Before this commit every level was 25-d, so the widths always
  matched; with two rungs they can differ. Driven, not read:
  - direct: `build_clusters(20 vectors, init=<20x25>)` ->
    `ClusterError("the reduction failed on these vectors")`, cause
    `ValueError: init ndarray must match n_components value`. Same in reverse
    (`N=40`, init width 10).
  - end to end through the real `cluster` op on a scratch DB: 40 embedded
    sections -> build #1 OK (`section_coords.dims = 25`, 3 nodes). Delete 20
    sections (the `ingest/reconcile.py:163` `_drop_path` flow; coords cascade,
    20 rows of width 25 remain) -> build #2 raises
    `ClusterError: the reduction failed on these vectors`; build #3 raises
    identically. The tree is permanently unclusterable: `replace_tree` is never
    reached, so the stale-width coords are never cleared and every later run
    fails the same way.
  Reachability is the headline flow, not a corner: `tree/maintain.py:60` runs
  `cluster` on EVERY maintain, and `tree/settle.py:57` does the same warm
  rebuild — which `clustering-lifecycle.md:14,97` specifies as `init` = stored
  coordinates. So any corpus that shrinks across N=27 (a deleted directory, a
  filter tightened) wedges both `maintain` and `settle` for good, with the
  generic message above and the real cause only in the chained traceback.
  Fix is small and belongs in this ticket: ignore the stored init when its width
  != `recipe.n_components` (drop it in `_default_reduce`, or have
  `stored_coords` return None on a width mismatch), and cover it with a test
  that rebuilds across the rung boundary in both directions.

  **What passed.** Gate re-run by me: `ruff format .` 219 files unchanged,
  `ruff check .` all checks passed, `pytest` 622 passed in 43s.
  - AC1 verified (N=4/10/26/27 give `ClusterError`, never a driver exception).
  - AC2 verified: the ladder is one data table (`cluster/recipe.py:41`), matches
    `how-hrono-works.md:109` (UMAP-10/mcs-3 at tens), and nothing imports
    `UMAP_DIMS`/`MIN_CLUSTER_SIZE` any more.
  - AC3 verified independently on a COPY of `.e2e/run/.hrono/hrono.db` (the
    original untouched): `build_tree` with the real clusterer yields
    `levels [(0, 7), (1, 1)]`, root node 11 with all 7 children, 8 briefs, and
    `collapse` + `render` produce 102 files including `root.md` and every topic
    directory. The M6 deliverable that F16 killed now renders.
  - AC4 verified (5-chunk pool: `drain` returns False, pool intact).
  - No regression for normal corpora, measured not assumed: `_default_reduce`
    output is `allclose` to the pre-change call (no `n_neighbors`, UMAP's own
    default is 15) at N=76 and N=60; ARI stays 1.000 on the canonical fixture.
    dev's boundary justification also holds — forcing UMAP-10/mcs-3 there gives
    ARI 0.776 with 8 clusters for 5 planted groups (N=76) and 0.904 (N=60).
  - Incubator gate change is sound: `drain` needs >= 12, `age` runs only below
    12, so a 5-11 pool is still force-assigned after `MAX_AGE`; no gap, and no
    conflict with 095 (nothing calls `drain`/`age` yet). It does deviate from
    `clustering-lifecycle.md:63`'s literal "reaches min_cluster_size", which the
    ticket's third work item explicitly sanctions.
  - Commit is atomic and Conventional (the `.gitignore` `.e2e/` line is
    pre-existing and not in it); `recipe.py` stays free of numpy/umap so the
    incubator remains importable without the cluster extra.

  **Notes for the PO, not blockers.** #112 is a correct out-of-scope filing: it
  is a strict improvement (floor moved 27 -> 12) and what a sub-12 corpus should
  produce is a product call, not a defect of this change. #108's acceptance
  criteria are now almost entirely satisfied by this commit's tests — worth
  re-scoping it to the seam/real-backend convention rule it also carries.
- 2026-09-14 dev: re-started after qa's rejection. Fixing only the blocking
  warm-init width defect on top of 2f8c6be; the scaling ladder itself stands.
- 2026-09-14 dev: defect fixed (commit 8019ad0), on top of 2f8c6be — the
  ladder itself is untouched.
  **The fix.** `_default_reduce` now passes the warm `init` to UMAP only when
  it has the width this build's recipe reduces to (`_fits`,
  `cluster/build.py:149`); a stale-width init is dropped and the build runs
  cold. Both of qa's repros are gone: `build_clusters(20, init=<20x25>)` and
  `build_clusters(40, init=<40x10>)` now return, with coords at the rung's
  width (25 -> 10 / 10 -> 25).
  **Why this over clearing the coords.** It is already self-healing without a
  second write: the build that dropped the init ends in
  `store.replace_tree`, which deletes every `section_coords` row for the tree
  and rewrites one per section at the NEW width — so build #2 runs cold and
  build #3 warm-starts normally (observed: coords 25 -> 10 -> 10, identical
  3-node tree on both). Clearing the stale rows eagerly would add a write
  before the heavy phase for no behaviour the build does not already give,
  and would have to happen inside the read lock in `cluster/op.py`. Putting
  the guard in `_default_reduce` rather than `store.stored_coords` also keeps
  it where the recipe is actually known: `stored_coords` would have to
  re-derive `recipe_for(len(section_ids))`, and any other caller of
  `build_clusters(init=...)` (settle's warm rebuild path) would still be
  unprotected. Width is the only dimension that legitimately drifts — a row
  count mismatch stays a caller bug and still surfaces as `ClusterError`.
  **Tests (all three fail without the guard, checked by reverting it).**
  `tests/cluster/test_build.py`: `test_real_recipe_drops_a_warm_init_from_
  another_rung`, parametrised both directions across the 27-point boundary
  ((25-wide init, N=20) and (10-wide init, N=40)) — real backend, asserts the
  coords come out at the rung's width AND are `allclose` to the same build
  given no init, i.e. the init was dropped, not coerced. Its counterweight
  `test_real_recipe_honours_a_warm_init_of_its_own_width` asserts a matching
  init still moves the layout, so the guard cannot degenerate into "never warm
  start". `tests/cluster/test_op.py`:
  `test_rebuild_across_a_rung_keeps_clustering` drives the REAL builder
  through the `cluster` op — 40 embedded sections over two sources, build #1
  (coords 25), `istore.clear_source` drops 20 (coords cascade, 20 rows of
  width 25 survive), build #2 must succeed with coords 10 and all 20 sections
  placed, build #3 proves the warm path is healthy again.
  **Verified on the real corpus, not just in tests.** Copied
  `.e2e/run/.hrono/hrono.db` (94 clusterable sections over 3 repos) to scratch
  and ran qa's flow through `cluster_op.cluster` with the real builder:
  build #1 -> coords [(25, 94)], 7 nodes; `clear_source` of `itsdangerous` and
  `chalk` -> 23 sections with 23 stale 25-wide coords; build #2 -> coords
  [(10, 23)], 3 nodes, 23 members; build #3 -> unchanged. With the guard
  reverted the same script dies at build #2 with `ClusterError` / `ValueError:
  init ndarray must match n_components value`, exactly as qa reported. The
  original `.e2e/` database was not modified.
  **Gate:** `ruff format .` 219 files unchanged, `ruff check .` all checks
  passed, `pytest` 626 passed (622 + the 4 new). The pre-existing `.gitignore`
  `.e2e/` line is untouched and not in the commit.
- 2026-09-14 qa: PASSED -> po-review. Re-verification of the warm-init fix
  (8019ad0) on top of the scaling ladder (2f8c6be). The ladder itself was
  re-confirmed, not re-litigated; the defect I raised is genuinely fixed.

  **1. The defect is fixed, and the self-heal is real (driven, not read).**
  I rebuilt my original breaking flow from scratch — 40 planted sections over
  two sources on a fresh DB, dropped 20 by the reconcile `_drop_path` flow
  (`DELETE FROM sections WHERE source = 'repo-b'`, coords cascade), and ran the
  real `cluster_op.cluster` with `build_clusters` four times. To prove the
  warm/cold claim rather than infer it, I wrapped `build._umap` with a spy that
  records the kwargs actually handed to `umap.UMAP`:
  - build #1 -> coords 25 (40 sections), 3 nodes, `init` absent (first build).
  - delete 20 -> 20 sections, 20 stale 25-wide coord rows.
  - build #2 -> **succeeds**, coords 10, 2 nodes, 20 members; spy shows
    `n_components=10`, `init` NOT passed (the stale init was dropped).
  - build #3 -> spy shows `init` PASSED, shape `(20, 10)`. build #4 likewise.
  So it is not silently cold for ever: the very next build warm-starts. Under
  2f8c6be this flow raised `ClusterError` at build #2 and every build after.
  Reproduced again on a COPY of the real `.e2e/run/.hrono/hrono.db`
  (original untouched): build #1 coords `[(25, 94)]` 7 nodes with `init`
  `(94, 25)` honoured from the original run's stored coords; `clear_source`
  of `itsdangerous` + `chalk` -> 23 sections with 23 stale 25-wide rows;
  build #2 coords `[(10, 23)]` 3 nodes 23 members, init dropped; build #3
  coords `[(10, 23)]`, init `(23, 10)` passed. dev's claim holds exactly.

  **2. Warm init is still load-bearing; the guard cannot degenerate.** The
  counterweight test `test_real_recipe_honours_a_warm_init_of_its_own_width`
  (`tests/cluster/test_build.py:174`) is real, not decorative: I forced
  `_fits` to `return False` (the "never warm-start" degeneration) and that test
  is the one that fails (`tests/cluster/test_build.py:183`), while the three
  drop-tests keep passing. `tests/cluster/test_op.py:132`
  `test_warm_init_uses_stored_coords_on_rebuild` still passes, and the real-DB
  run above shows a same-width init genuinely reaching UMAP. The
  `clustering-lifecycle.md:14,97` reconcile contract is intact.

  **3. Placement in `_default_reduce` is right.** Audited every producer of a
  non-None `init`: `cluster/op.py:41` (`store.stored_coords`) is the ONLY one.
  `cluster/levels.py:73` passes `init=None`; `build.py:128` (`core_labels`)
  passes `None`; `tree/settle.py:57` does not build directly — it delegates to
  the `cluster` op, so it inherits the guard. Guarding `store.stored_coords`
  instead would have left any future direct `build_clusters(init=...)` caller
  unprotected and forced the store to re-derive `recipe_for`, so
  `_default_reduce` — where the recipe is known — is the correct seam. Custom
  `reduce=` injections bypass it, which is the intended test seam, not a hole.

  **4. Row-count mismatch stays a loud caller bug.** Driven at N=40 (25-dim
  rung) with the real backend: init `(20, 25)` -> `ClusterError("the reduction
  failed on these vectors") <- IndexError: boolean index did not match indexed
  array ... size of axis is 20 but size ... is 40`; init `(60, 25)` -> the same
  `ClusterError` with the mirrored `IndexError`. Never a silent wrong result,
  never a driver exception escaping. `_fits`'s `ndim == 2` arm also holds: a
  1-D `(40,)` and a 3-D `(40,5,5)` init are dropped and the build returns
  correctly at width 25 rather than exploding. In practice `stored_coords`
  cannot produce a row mismatch at all (it returns None unless every section
  has a coord, and emits exactly `len(section_ids)` rows).

  **5. Regression — none, and the new tests have teeth.** Reverting the guard
  to `if init is not None:` in an isolated worktree (asserted
  `hrono.__file__` inside the worktree via `PYTHONPATH=<wt>/src`) fails
  exactly the three new tests and nothing else:
  `test_real_recipe_drops_a_warm_init_from_another_rung[25-20]`, `[10-40]`, and
  `tests/cluster/test_op.py::test_rebuild_across_a_rung_keeps_clustering`.
  The original review's end-to-end result is unchanged: on a fresh copy of the
  real e2e DB (7 leaf nodes, 104 sections), `build_tree` with the real
  clusterer and a stub completion client yields `levels [(0, 7), (1, 1)]`,
  root node 11 with all 7 children, 8 briefs, and `collapse(…, 3)` + `render`
  produce **102 files including `root.md`** — identical to what I measured on
  2f8c6be. AC1-AC5 all still hold.

  **Code, commit, security.** `_fits` (`src/hrono/cluster/build.py:149`) is a
  three-line pure predicate, fully typed, no mutation; the module docstring
  explains the drop so no inline comment is needed. Test comments follow the
  file's existing `# #NNN:` convention. No emojis. Nothing security-relevant
  is touched (local vectors only, no secret, no endpoint, no role surface).
  Commit `8019ad0` is Conventional, lowercase, one sentence, no body, no
  attribution; atomic at 3 files (+145/-3) with no stray changes — the
  `.gitignore` `.e2e/` line is pre-existing and not in it.

  **Gate re-run by me, not taken on trust:** `uv run ruff format .` -> 219
  files left unchanged; `uv run ruff check .` -> all checks passed;
  `uv run pytest` -> **626 passed** in 31.6s.

  **Note for the PO, not a blocker and not filed.** Pre-existing, unchanged by
  this commit: `build_clusters` converts `init` with `np.asarray(init,
  dtype=np.float32)` BEFORE `_fits` sees it, so a ragged/non-numeric init
  would raise `ValueError` from numpy rather than `ClusterError`. No caller can
  produce one (`stored_coords` is always rectangular), so it is a latent
  caller-bug path only.
- 2026-09-14 PO: **ACCEPTED -> done.** Both commits (2f8c6be ladder + 8019ad0
  warm-init width guard) close the ticket against the 2026-09-12 revised
  decision. Verified independently, not taken from the log.

  **The decision was honoured, not just the symptom.** The defect was framed as
  "unscaled parameters at every level", and the fix is exactly that: the ladder
  is data (`cluster/recipe.py:41`, two frozen rungs), derived from the spec's
  own two recipes (`how-hrono-works.md:109` — UMAP-25/mcs-5 at thousands,
  UMAP-10/mcs-3 at tens), each floored where it is physically valid
  (`n_components + 2`, the measured UMAP-25 26/27 boundary). `build.py` no
  longer names `UMAP_DIMS`/`MIN_CLUSTER_SIZE` anywhere (grep-clean in src and
  tests) and both backends derive the recipe from their own point count, so
  `cluster`, `cluster-briefs` and `incubator.drain` scale with no plumbing.
  `recipe.py` imports only `dataclasses` + `ClusterError`, so the incubator
  stays importable without the cluster extra. Below the smallest rung the
  honest `ClusterError` is raised — the signal `build_tree`'s
  `except ClusterError: break` was already written for, so the 7-topic case
  resolves with no new policy, as the decision predicted.

  I accept dev's boundary reasoning (rungs floored at validity rather than at
  "tens"): it keeps the settled recipe running wherever it is valid, and qa
  measured the alternative (UMAP-10/mcs-3 forced at N=60/76 drops ARI to
  0.904/0.776 against 1.000). Changing the recipe under every medium corpus is
  not what this ticket asked for.

  **Headline deliverable driven by me, end to end.** Copied
  `.e2e/run/.hrono/hrono.db` (the real 3-repo run that died in scipy: 7 leaf
  nodes, 7 briefs, 104 sections) to scratch; the original was not touched. Ran
  `build_tree` in-process with the REAL clusterer and a stub completion client,
  then `export.store.load` -> `collapse(..., 3)` -> `render`:
  - levels `[(0, 7), (1, 1)]` — was `[(0, 7)]` and a TypeError.
  - root node 11 at level 1 with all 7 children; exactly one top-level node.
  - 8 briefs.
  - export renders **102 files including `root.md`**, plus a directory per
    topic. F16's unusable export now renders. This is the M6 deliverable
    restored, observed rather than inferred.

  **Gate re-run by me:** `uv run ruff format --check .` 219 files already
  formatted; `uv run ruff check .` all checks passed; `uv run pytest` **626
  passed** in 32.6s. Working tree carries only the pre-existing, deliberate
  `.gitignore` `.e2e/` line (not dev's, not in either commit); both commits are
  atomic and Conventional.

  Acceptance criteria: AC1 met (`test_real_recipe_refuses_a_level_it_cannot_
  reduce` at N=1/4/10/11 and `test_real_recipe_clusters_every_size_it_accepts`
  at N=12/26/27/40, both `build_clusters` AND `core_labels`, real backend).
  AC2 met (one data table, matches the spec). AC3 met (verified above on the
  real corpus). AC4 met. AC5 met.

  **The qa bounce was correct and correctly answered.** The warm-init width
  defect was a genuine blocker — a corpus shrinking across N=27 wedged
  `maintain` AND `settle` permanently — and it was reachable from the headline
  flow, not a corner. The fix (`_fits`, `build.py:149`) is three pure lines at
  the seam where the recipe is actually known, it self-heals on the next build
  because `replace_tree` rewrites coords at the new width, and qa proved warm
  vs cold by spying on the kwargs UMAP receives rather than reasoning about it.
  The counterweight test means the guard cannot degenerate into "never warm
  start". This is the pipeline working as designed.

  **Rulings on the three questions qa left me:**
  1. **#108 — RE-SCOPED, not closed.** qa is right that 094's tests satisfy its
     testable acceptance criteria: AC1 (real `build_clusters`/`core_labels` at
     N=4/10/26/27) and AC2 (real-backend `build-tree` declaring a root over a
     tiny level, `tests/summarize/test_build_tree.py:274`) are both delivered
     here. I am NOT closing it, because the part that actually prevents the
     next 094 is the convention rule in its own Decision block, and that is
     unwritten. #108 is re-scoped to exactly that rule and nothing else.
  2. **#112 — CONFIRMED as an out-of-scope filing, and I am making its product
     call.** It is not a defect of this ticket: the floor moved 27 -> 12, a
     strict improvement, and what a sub-12 corpus should produce is a product
     decision that did not exist before this change forced it. Priority stays
     medium. I have added the decision (collect, do not fail) and promoted it
     to `todo/` so it is Ready rather than sitting on a question.
  3. **The `np.asarray(init)`-before-`_fits` note — correctly ignored, no card.**
     It is pre-existing, unchanged by this commit, and unreachable: the only
     producer of a non-None `init` is `store.stored_coords`, which is always
     rectangular and numeric. Hardening an unreachable path is speculative
     surface, which CLAUDE.md tells us not to add. Recorded here so it is not
     re-raised each review; if a second `init` producer ever lands, the ticket
     that adds it owns this.

  **One adjacent thing I found myself, folded into #102 rather than duplicated.**
  The rendered `root.md` carries the upper brief's mechanical footer
  `Children:\n- node 1\n- node 2...` (raw node ids, `summarize/brief_upper.py:101`)
  immediately above render's own proper `## Children` titled links — so an
  agent reading the MVP's top file sees the child list twice, once as opaque
  ids. This is the upper-level twin of F30's leaf URI footer, which #102
  already owns for `summarize/brief.py`. Pre-existing, not caused here; noted on
  #102 so both footers are fixed in one pass instead of spawning a duplicate.
