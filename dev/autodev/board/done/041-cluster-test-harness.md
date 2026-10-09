---
id: 041
title: Known-group + coverage test harness for clustering (T19)
priority: high
size: medium
depends_on: [040]
spec_refs: [build-order.md#T19, clustering-lifecycle.md, how-hrono-works.md]
---

## Context
Clustering quality is the whole point of the tree, but "did HDBSCAN cluster
sensibly?" is not something a normal unit test asserts. This ticket builds a
reusable harness that plants KNOWN groups in synthetic data, runs the real
cluster pipeline (#035 embed -> #039 blend -> #040 UMAP/HDBSCAN/attach), and
asserts the planted groups are recovered and every point is covered - a
regression guard on the clustering recipe and its baked constants so a future
tweak that quietly wrecks cluster quality fails a test. Depends on #040 (the
cluster op it exercises).

## Description
Add a clustering test harness (recommend `tests/cluster/` helpers +
`test_known_groups.py`) that is deterministic and offline:
- **Planted-group fixtures**: generate synthetic combined vectors with K known
  clusters (well-separated blobs, plus some near-boundary / noise points), under
  a FIXED seed so runs are reproducible. Optionally also drive from a small
  fixture repo whose files have an obvious grouping (e.g. by directory) so the
  path-blend (#039) contribution is exercised, not just random blobs.
- **Recovery metric**: run the real #040 cluster build and score the recovered
  clustering against the planted labels with a standard agreement measure
  (e.g. adjusted Rand index / homogeneity), asserting it clears a threshold that
  a correct recipe comfortably passes but a broken one (e.g. wrong metric,
  min_cluster_size, or missing UMAP) fails. Pick and document the threshold.
- **Coverage assertion**: every input section is assigned to exactly one
  bottom-level topic (noise attached per #040), i.e. no orphan/unassigned points.
- **Determinism**: the same fixture + seed yields the same clustering across
  runs (guards the fixed-seed requirement).
- **Regression teeth**: the harness must FAIL if a core constant is wrong -
  demonstrate by showing (in the ticket/tests) that perturbing the recipe (e.g.
  dropping UMAP or changing the HDBSCAN metric) drops recovery below threshold.

Keep it offline: use a fake/fixed embedder (no weights) and synthetic vectors so
CI needs no model download; use umap-learn/hdbscan as #040 does. This is a TEST
harness - it adds tests + fixtures + helpers, not product surface.

## Acceptance criteria
- [ ] A planted-K-group synthetic fixture (fixed seed) run through the real #040
      cluster build recovers the planted groups above a documented agreement
      threshold (e.g. ARI >= X); the threshold passes for the correct recipe.
- [ ] Coverage: every section is assigned to exactly one bottom-level topic (no
      unassigned points), noise attached.
- [ ] Determinism: the same fixture + seed produces the identical clustering on
      repeat runs.
- [ ] Regression teeth: the harness demonstrably FAILS when the recipe is
      perturbed (a shown example - wrong metric / no UMAP / wrong
      min_cluster_size drops recovery below threshold).
- [ ] Offline/deterministic: no model weights downloaded, no network; uses a
      fake embedder + synthetic vectors.
- [ ] `ruff format`, `ruff check --fix`, `pytest` all clean; work committed.

## Out of scope
- Upper-level recursion / briefs (M4) and export (M6).
- Incremental placement quality (M7 has its own edit-stability tests).
- Benchmarking real-repo cluster quality at scale (this is a correctness/
  regression harness on planted groups, not a benchmark).

## Review log
- 2026-08-17 PO: authored as T19, the clustering regression harness on the #040
  build. Planted-group fixtures + a recovery threshold + full-coverage +
  determinism, with a shown perturbation proving the harness has teeth. Offline
  (fake embedder), so CI needs no weights. Closes M3's validation.
- 2026-08-23 dev: DONE, committed 878c1fb, handoff to qa. Test-only (no product
  surface). Added `tests/cluster/harness.py` + `tests/cluster/test_known_groups.py`:
  - `planted_groups()` — canonical fixed-seed fixture: 5 blobs x 14 unit vectors,
    dim 80, spread 0.18, +6 genuine-noise points (label -1). Empirically tuned so
    the CORRECT recipe recovers at ARI 1.0 while perturbations fall far below the
    documented `RECOVERY_THRESHOLD = 0.80` (chose the regime by sweeping spread/
    dim; clean blobs don't exercise UMAP, over-hard blobs break the correct recipe
    too — 0.18/dim-80 gives the widest gap with margin against library drift).
  - `adjusted_rand_index` implemented in-harness (verified == sklearn to 1e-9 on
    the fixture and on random labelings, incl. negative ARI) so the harness does
    NOT couple to a transitive scikit-learn install.
  - Tests: recovery >= threshold (and > 0.95); full coverage (every point label
    >= 0, attachment-similarity-iff-attached bookkeeping consistent); determinism
    (identical labels + coords on repeat); ARI endpoints; reduced coords = 25-d.
  - Regression TEETH (both shown to drop recovery below threshold on the same
    fixture): dropping UMAP (identity reduce) -> ARI 0.427; wrong
    min_cluster_size=60 (> any group) -> all-noise -> `build_recovery` scores a
    ClusterError collapse as 0.0. `build_recovery` maps a collapse to 0.0 so a
    raise and a low ARI both read as "below threshold".
  - Offline/deterministic: synthetic vectors + fixed seed, no weights, no network;
    uses umap-learn/hdbscan as #040 does (dev-group installed).
  Verified: ruff format/check clean; full suite 395 passed / 1 skip (+7 new);
  known-groups run twice identical; cross-checked ARI vs sklearn. **M3 validation
  closed.**
- 2026-08-23 qa: PASS -> po-review. Verified every dimension:
  - Recovery: ran the real #040 build over the canonical planted fixture -> ARI
    1.0, comfortably above the documented `RECOVERY_THRESHOLD = 0.80`.
  - Coverage: every point assigned to exactly one topic (labels all >= 0), and
    the attach bookkeeping is consistent (similarity iff attached).
  - Determinism: identical labels + coords on repeat; `test_known_groups.py`
    green across 3 separate runs (7 passed each).
  - Teeth genuinely bite: re-ran both perturbations on the same fixture — no-UMAP
    (identity reduce) -> ARI 0.4275; wrong min_cluster_size=60 -> all-noise ->
    0.0; both far below 0.80 while the correct recipe is 1.0.
  - Offline: synthetic vectors + fixed seed, no embedder/weights/network at all
    (stricter than "fake embedder").
  - In-harness `adjusted_rand_index` is decoupled from scikit-learn and I
    independently confirmed it == `sklearn.metrics.adjusted_rand_score` to 1e-9
    on 5 random labelings and on the fixture — a good call to avoid a transitive
    dep.
  - Test-only (no product surface); ruff format/check clean; full suite 395
    passed / 1 skip (no segfault — #040's worker-join fix holds); commit 878c1fb
    is an atomic `test:` Conventional Commit.
  Observation for PO (non-blocking, NOT a defect): the harness plants combined
  vectors directly and drives only #040's `build_clusters`, so the #039 path-
  blend contribution is not exercised end-to-end here. The acceptance criteria
  only require the #040 build and driving embed->blend was explicitly optional,
  and #039 already has its own blend-identity tests, so this passes as-is; the
  queued #054 (sections->tree mapping) will naturally exercise more of the
  pipeline if an end-to-end harness is later wanted. (The pre-existing unrelated
  `.gitignore` edit remains uncommitted, out of this ticket's commit.)
- 2026-08-23 dev: board hygiene — a concurrent PO re-authored 041 into `todo/`
  (14:20, "re-authored after the active board was cleared") while I already had
  it in `in-progress/`, leaving a stale duplicate with no dev logs. Removed the
  todo/ copy; this verifying/ file (with the full handoff) is authoritative. Same
  id 041, one ticket.
- 2026-08-23 PO review: PASS -> done. Independently re-verified rather than
  trusting the logs. Read harness.py: standard contingency-table ARI, teeth
  injected cleanly through build_clusters' reduce/cluster seams. Ran
  test_known_groups.py 3x (7 passed each, deterministic); ruff clean; full suite
  395 passed / 1 skip. Drove the checks myself on the canonical fixture: correct
  recipe ARI 1.0 (>= 0.80 threshold); no-UMAP teeth -> 0.4275; wrong
  min_cluster_size=60 -> collapse -> 0.0 — both far below threshold, so the
  harness demonstrably fails on a perturbed recipe. Confirmed the in-harness ARI
  == sklearn to 1.7e-17 over 5 random labelings, so decoupling from scikit-learn
  is sound. All 6 acceptance criteria truly met. Accepted qa's non-blocking note:
  the harness drives #040's build_clusters directly and does not exercise #039
  blend end-to-end, but the ticket made the repo-fixture path explicitly OPTIONAL
  and #039 has its own blend-identity tests — passes as-is, no spinoff (queued
  #054 will exercise more of the pipeline if an e2e harness is later wanted).
  Closed. **M3 (Cluster) COMPLETE** (035/038/039/040/041); next milestone is M4
  (Brief, T20+).
