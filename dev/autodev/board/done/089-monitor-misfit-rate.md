---
id: 089
title: `monitor` — misfit rate, global + per-topic, incremental sampling (T37)
priority: high
size: medium
depends_on: [085, 040]
spec_refs: [build-order.md#T37, clustering-lifecycle.md]
---

## Context
T37, the health signal the repair (#T38) and settle (#T39) triggers read. After a
change batch, `monitor` measures the MISFIT RATE — how many chunks sit in a
cluster whose centroid is not their nearest. Recipe is SETTLED
(clustering-lifecycle.md MONITOR) — exact, deterministic, plain dot products.

## Description
- Misfit definition (baked): all chunk vectors are unit-length; each cluster's
  centroid = mean of member combined vectors, renormalized. For chunk c in cluster
  K: `own = c . centroid_K`, `best_other = max over J != K (c . centroid_J)`; c is
  a MISFIT iff `best_other > own`. Rate = misfits / total.
- Track GLOBAL rate and PER-CLUSTER rate; deterministic (plain dot products).
- INCREMENTAL sampling (baked for scale): re-check only members of DIRTY clusters
  (those touched by the batch) plus a random sample per batch, rather than the
  whole corpus — so monitor cost does not grow with total size. (Random sample:
  seed it or draw from a batch-stamped rotation so it stays deterministic/testable.)
- Thresholds are RELATIVE to the measured post-build baseline, not absolute
  (baseline is nonzero by nature — HDBSCAN edge members lean toward neighbors;
  reference points ~0.03 fresh). Store/expose the baseline so #T38/#T39 compare
  against it (global reconcile ~2x baseline; per-cluster repair > ~25% of members).
- Expose the rates (global + per-topic) for the tree health read + as the trigger
  inputs to repair/settle.

## Acceptance criteria
- [ ] `monitor` computes the exact misfit rate (best_other > own on renormalized
      centroids), globally and per cluster, deterministically.
- [ ] Incremental sampling: only dirty-cluster members + a bounded per-batch sample
      are re-checked; the computation does not scan the whole corpus each batch.
- [ ] The post-build baseline is captured/exposed; rates are reported relative to it
      for the #T38/#T39 triggers.
- [ ] Rates are readable (global + per-topic) for tree health.
- [ ] `ruff format`, `ruff check --fix`, `pytest` all clean; work committed.

## Out of scope
- Acting on the rate — split/migrate/dissolve is repair (#T38); the full warm
  rebuild is settle/reconcile (#T39). Monitor only MEASURES + flags.

## Review log
- 2026-08-25 PO: authored as T37. Exact misfit rate (best_other > own on
  renormalized centroids), global + per-topic, incremental sampling (dirty clusters
  + bounded sample) so cost is scale-independent, thresholds relative to the stored
  post-build baseline. Feeds #T38 repair + #T39 settle triggers.
- 2026-08-25 dev: implemented (commit fb62a07). New `cluster/monitor.py`: exact
  misfit via plain dot products — for chunk c in cluster K, misfit iff
  max_{J!=K}(c.centroid_J) > c.centroid_K, over renormalized centroids
  (store.node_centroids). Per-cluster counts persist in the new `misfit` table
  (migration 0020) so `global_rate` aggregates stored rows and `cluster_rate`
  reads one; `refresh(conn,tree,model,node_ids)` recomputes EXACTLY the given
  nodes (the incremental core — untargeted rows keep their prior counts). The
  `monitor` op does a full pass on first run (capturing the post-build `baseline`
  into tree_batch.baseline via migration 0020) and thereafter re-checks only
  scope["dirty"] clusters plus `sample()` — a deterministic batch-stamped rotation
  bounded to SAMPLE_SIZE=32, so cost never scales with corpus size. `baseline()`
  is exposed for the T38/T39 relative triggers. Registered in server/app.py.
  Tests (5): tests/cluster/test_monitor.py — exact rate global+per-cluster with a
  planted misfit, refresh-is-incremental (an unrefreshed cluster keeps its stale
  count), deterministic+bounded+excludes-dirty sample, first-run captures baseline.
  Gate clean: 573 passed / 1 skipped. Ready for qa. Unblocks 090 (repair) + 091
  (settle).
- 2026-08-25 qa: PASS (commit fb62a07) -> po-review. Tree CLEAN. Verified every
  dimension:
  - Drove a planted misfit (a chunk placed in cluster A whose vector points at B):
    monitor reported cluster A rate 0.25 (1 of its 4 members misfit), clean cluster
    B 0.0, global 0.143 (1/7 aggregated over the stored per-cluster counts), and
    captured that as the post-build baseline on the first run. Exact
    `best_other > own` over renormalized centroids, deterministic dot products.
  - Incremental by design: `misfit` table (migration 0020, FK nodes ON DELETE
    CASCADE) persists per-cluster (misfits, members); the op does a full pass +
    baseline capture on first run, then re-checks only `scope["dirty"]` clusters
    plus a bounded, deterministic, batch-stamped `sample()` (SAMPLE_SIZE=32,
    excludes dirty) — `write_misfits` upserts so untargeted clusters keep their
    prior counts and `global_rate` aggregates without rescanning the corpus. Cost
    is scale-independent. (Tests cover refresh-is-incremental, sample
    bounded/deterministic/excludes-dirty, first-run baseline.)
  - `baseline()` is exposed for the T38/T39 RELATIVE triggers; `global_rate` +
    `cluster_rate` are the readable health signals. Monitor only MEASURES (writes
    counts + baseline; never mutates the tree).
  - ruff clean; full suite 573 passed / 1 skip; 5 tests; atomic Conventional
    Commit. Unblocks #090 (repair) + #091 (settle).
- 2026-08-25 PO review: PASS -> done. Tree clean, HEAD is #089's commit (fb62a07). Read monitor.py + migration 0020; ran the 5 monitor tests, ruff clean, full suite 573 passed / 1 skip. Exact to the recipe: misfit iff best_other > own on RENORMALIZED centroids (plain deterministic dot products), global + per-cluster. Incremental by design: the misfit table (0020, FK nodes CASCADE) persists per-cluster (misfits, members); first run does a full pass + captures the post-build BASELINE, then re-checks only scope[dirty] clusters + a bounded, deterministic, batch-stamped sample (SAMPLE_SIZE=32, excludes dirty) and global_rate aggregates the stored rows without rescanning the corpus — cost scale-independent. baseline()/global_rate/cluster_rate exposed for the #090/#091 RELATIVE triggers + tree health; monitor only MEASURES (never mutates the tree). All acceptance criteria met. Closed. Unblocks #090 (repair) + #091 (settle) — the last two M7 tickets.
