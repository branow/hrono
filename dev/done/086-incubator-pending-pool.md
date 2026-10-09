---
id: 086
title: incubator — pending pool store, drain mini-pipeline, force-assign + `forced`, aging (T35)
priority: high
size: big
depends_on: [040, 068]
spec_refs: [build-order.md#T35, clustering-lifecycle.md]
---

## Context
T35, the pending pool the incremental `update` (#085 / T34) parks sub-TAU chunks
into — a chunk that fits no existing cluster waits here until enough siblings
arrive to form a real cluster, rather than being force-married to strangers. The
recipe is SETTLED (clustering-lifecycle.md UPDATE + the "scoped mini-pipeline"
mechanism). #085 depends on this for its `< TAU` case, so build it alongside/first.

## Description
- **Store + pending query (T35.1)**: a pending pool holding parked chunks (by
  content hash / section) queryable as "pending" (not yet in a cluster). Every
  chunk is in exactly one cluster OR explicitly pending (invariant 3).
- **Drain mini-pipeline (T35.2)**: when the pool reaches `min_cluster_size` (5),
  run the SCOPED MINI-PIPELINE over the pool ONLY — UMAP(25, cosine, seed 42) ->
  HDBSCAN(leaf, 5) -> nearest-member assignment, deterministic, touching nothing
  outside the pool. Emit only its DENSITY-CORE clusters as new clusters; stragglers
  are NOT married to each other (they stay pending).
- **Force-assign residual + `forced` flag (T35.3)**: residual pool noise after a
  drain is force-assigned to the MOST SIMILAR existing cluster IGNORING TAU (a chunk
  outside the tree is unfindable — worse than one alien summary member). Force-placed
  chunks carry a `forced` flag + their placement similarity, so the misfit monitor
  (T37) re-checks them preferentially and a mis-placed pioneer migrates once its real
  siblings arrive.
- **Aging (T35.4)**: a chunk pending for more than N batches while the pool stays
  below `min_cluster_size` is force-assigned the same way (flagged) — nothing waits
  forever.
- Reuse the #040 clustering primitives (the scoped mini-pipeline IS UMAP->HDBSCAN(leaf)
  over a subset); constants baked (min_cluster_size 5, seed 42).

## Acceptance criteria
- [ ] A pending store + "pending" query; every chunk is in one cluster or pending
      (invariant), never both, never neither.
- [ ] Pool at min_cluster_size drains via the scoped mini-pipeline; only density-core
      clusters emit; stragglers stay pending (not married to each other).
- [ ] Residual noise force-assigns to the nearest existing cluster ignoring TAU, with
      a `forced` flag + similarity recorded.
- [ ] Aging force-assigns an over-N-batches pending chunk (flagged); nothing waits
      forever.
- [ ] Mini-pipeline is deterministic + scoped (touches nothing outside the pool);
      constants baked.
- [ ] `ruff format`, `ruff check --fix`, `pytest` all clean; work committed.

## Out of scope
- The `update` placement rule that FEEDS the pool (#085 / T34).
- The misfit monitor that re-checks `forced` chunks (T37) and repair (T38).

## Review log
- 2026-08-25 PO: authored as T35, the pending pool for #085's sub-TAU placements.
  Store + pending query -> drain via the scoped mini-pipeline (density-core only) ->
  force-assign residual ignoring TAU with a `forced` flag -> aging. The `forced` flag
  is what lets a mis-placed pioneer self-correct once its siblings arrive (via T37).
  Constants baked. Build alongside #085 (they are coupled).
- 2026-08-25 dev: implemented (commit 3216101). Migration 0017 adds `pending`
  (PK tree+content_hash, FK contents) and `node_members.forced`. New
  `cluster/incubator.py`: park/pending/unpark/count store fns (invariant: parked by
  content hash, unparked the moment placed); `drain` runs the scoped mini-pipeline
  over the pool ONLY via an injectable core-labeler (default `build.core_labels` =
  UMAP-25/cosine/seed-42 -> HDBSCAN leaf, min_cluster_size 5, WITHOUT noise-attach
  so -1 residual stays -1), emits only density cores as new leaf nodes, force-assigns
  residual noise to the nearest PRE-DRAIN existing centroid ignoring TAU; `age`
  force-assigns over-max_age (baked 5) chunks only while the pool is sub-minimum.
  Added `store.add_leaf_node`/`add_member` (content-hash signature kept fresh so a
  later full rebuild #068 can match), `store.node_centroids` (renormalized mean of
  member combined vectors), `build.core_labels`. Tests: `tests/cluster/test_incubator.py`
  (5) with a deterministic content-aware labeler cover park/pending/unpark, below-min
  no-op, drain-emits-core + force-assign-residual (forced flag + similarity), aging,
  and young-not-aged. Gate clean: 545 passed / 1 skipped. Force-assign no-ops (chunk
  stays pending) when no existing cluster exists yet. Ready for qa.
- 2026-08-25 qa: PASS (commit 3216101) -> po-review. Tree CLEAN at handoff (the
  long-standing `.gitignore` edit was folded into this commit — harmless cleanup).
  Verified every dimension of this big ticket:
  - Drove the drain end-to-end (injected content-aware labeler): 5 pending chunks
    where 4 form a density core + 1 is residual -> the core emits as ONE new leaf
    node, the residual force-assigns to the pre-existing cluster with `forced=1`
    and its similarity recorded, the pool empties (0 pending), and every chunk
    ends in exactly one cluster (invariant held). Residual snapshots PRE-drain
    centroids, so it attaches to an existing cluster, not a just-formed core; if no
    existing cluster exists, `_force_assign` no-ops and the chunk stays pending.
  - CRITICAL consistency with #068 confirmed: `add_leaf_node`/`add_member` set the
    node signature via `node_content_signature` = `_signature(sorted member
    content-hashes)` — byte-identical to #068's `replace_tree` leaf signature (I
    checked `_signature(sorted(h)) == _signature(h for h in ...)`). So a later full
    rebuild MATCHES an incubator-created node and keeps its brief — the incubator
    and the full-rebuild path agree on identity.
  - Scoped mini-pipeline: `build.core_labels` is UMAP-25/cosine/seed-42 ->
    HDBSCAN(leaf, min_cluster_size 5) returning RAW labels (-1 stays -1, no noise-
    attach), over the pool ONLY — touches nothing outside it; deterministic.
    Constants baked (MIN_CLUSTER_SIZE 5, MAX_AGE 5, seed 42). Aging force-assigns
    over-max_age chunks only while the pool is sub-minimum (tested: aged vs young).
  - Migration 0017: `pending` (PK tree+content_hash, FK contents) + `node_members
    .forced`. `forced` members carry attached=1 + similarity for T37's re-check.
  - ruff clean; full suite 545 passed / 1 skip; 5 incubator tests; atomic
    Conventional Commit.
  Minor (non-blocking): `node_centroids` has no ORDER BY, so `_force_assign`'s
  `max`-by-dot tie-break is insertion-order on an exact float tie — negligible
  (distinct centroids won't tie exactly), but an `ORDER BY id` would make it
  strictly deterministic if ever wanted. With #085 (the `update` op that FEEDS the
  pool) next, T34/T35 close the incremental-placement loop.
- 2026-08-25 PO review: PASS -> done. Tree clean, HEAD is #086's commit (3216101; the long-standing uncommitted .gitignore edit was folded in — harmless cleanup, though ideally its own commit). Read incubator.py drain/_force_assign + migration 0017; ran the 5 incubator tests, ruff clean, full suite 545 passed / 1 skip. drain is correct: pool>=MIN_CLUSTER_SIZE gates it, the injectable core-labeler (default UMAP-25/cosine/seed-42 -> HDBSCAN leaf, min_cluster_size 5, RAW labels so -1 residual stays -1) runs over the pool ONLY, density cores (label>=0) emit as new leaf nodes and unpark, and residual (-1) force-assigns to centroids SNAPSHOTTED PRE-DRAIN (so residual attaches to a pre-existing cluster, never a just-formed core) ignoring TAU with forced=1 + similarity; age force-assigns over-MAX_AGE(5) chunks only while the pool is sub-minimum. CRITICAL consistency verified: add_leaf_node signs the node with the SAME content-hash signature as #068's replace_tree, so a later full rebuild matches an incubator-created node and keeps its brief. Constants baked (MIN_CLUSTER_SIZE 5, MAX_AGE 5, seed 42); invariant held (every chunk in one cluster or pending). All acceptance criteria met. Closed. Accepted qa's negligible node_centroids ORDER-BY tie-break note (distinct renormalized centroids won't exactly tie); noted for #085 which reuses node_centroids to add ORDER BY id if strict determinism on a float tie is ever wanted. **T35 (incubator) done; #085 (update op, T34) is now unblocked — closes the incremental-placement loop.**
