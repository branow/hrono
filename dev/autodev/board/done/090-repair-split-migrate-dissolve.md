---
id: 090
title: `repair` — local cluster repairs: split / migrate / dissolve (T38)
priority: high
size: medium
depends_on: [089, 086, 085]
spec_refs: [build-order.md#T38, clustering-lifecycle.md]
---

## Context
T38, the LOCAL repairs the monitor (#089) triggers — each touches ONE cluster only
and rebuilds only that cluster's brief. Recipe is SETTLED (clustering-lifecycle.md
LOCAL REPAIRS), all via the reusable SCOPED MINI-PIPELINE (#086's drain primitive:
UMAP -> HDBSCAN(leaf) -> nearest-member over a given set only, deterministic).

## Description
Three repairs, each scoped to one cluster, each dirtying only its brief:
- **split (T38)**: a cluster whose size > MAX_CAP (30) -> scoped mini-pipeline over
  its members -> 2+ child clusters (5-20 each); only their briefs rebuild. MAX_CAP
  is baked (the summarization budget, not clustering).
- **migrate**: a cluster whose per-cluster misfit is above threshold (> ~25% of
  members, relative to baseline #089) -> either re-run the scoped mini-pipeline over
  its members, OR migrate individual high-misfit chunks to their better cluster
  (best_other); both dirty the affected briefs. `forced` chunks (#086) are the
  preferential migrate candidates.
- **dissolve**: a cluster below 2 members -> its members re-enter the placement rule
  (#085); the empty node retires (its brief cascades, #068 identity rules).
- New/split clusters keep the #068 content-hash signature so a later rebuild matches
  them. Constants baked (MAX_CAP 30, min_cluster_size 5, seed 42).

## Acceptance criteria
- [ ] split: a > MAX_CAP cluster splits via the scoped mini-pipeline into 2+
      clusters of 5-20; only their briefs rebuild; new nodes carry #068 signatures.
- [ ] migrate: an above-threshold-misfit cluster is repaired (re-cluster its members
      or migrate the high-misfit/forced chunks to their best_other), dirtying the
      affected briefs only.
- [ ] dissolve: a below-2 cluster's members re-enter placement (#085); the node
      retires.
- [ ] Each repair touches ONE cluster's members; untouched clusters are unchanged;
      deterministic; constants baked.
- [ ] `ruff format`, `ruff check --fix`, `pytest` all clean; work committed.

## Out of scope
- The global warm rebuild / reconcile (#T39 settle) — repairs are LOCAL.
- The misfit measurement itself (#089) — repair consumes it.

## Review log
- 2026-08-25 PO: authored as T38, the local one-cluster repairs on #089's misfit
  signal, all via #086's scoped mini-pipeline. split (>MAX_CAP), migrate (per-
  cluster misfit / forced chunks), dissolve (<2 -> re-place). New nodes keep #068
  signatures; constants baked.
- 2026-08-25 dev: implemented (commit 45fd963). New `cluster/repair.py`, no new
  migration (uses existing tables). `split`: an over-MAX_CAP(30) cluster runs the
  scoped mini-pipeline (build.core_labels, injectable) over ONLY its members ->
  density cores become new leaf nodes (each with a #068 content-hash signature via
  add_leaf_node), residual noise attaches to the nearest core centroid, the
  oversized node retires (brief cascades); a <2-core result leaves the cluster
  intact. `migrate`: moves each misfit member (best_other > own on frozen centroids)
  to its best cluster via remove_member/add_member — decisions snapshot-frozen then
  applied, so on-topic members stay put and only affected briefs dirty. `dissolve`:
  a below-2 cluster retires and each survivor re-enters the placement rule through
  the new shared `placement.assign_or_park` (extracted from #085 so the rule isn't
  duplicated) — joins nearest >= TAU else parks in the incubator. The `repair` op
  picks per cluster from size + stored misfit rate (#089); registered in app.py.
  Constants baked (MAX_CAP 30, MISFIT_THRESHOLD 0.25; min_cluster_size lives in
  build.core_labels). Tests (6): tests/cluster/test_repair.py — split into 2 children
  of 5-20 with signatures + oversized node retired, within-cap no-op, migrate moves
  exactly the misfits (on-topic stay), dissolve retires + re-places, dissolve parks
  a homeless survivor. Gate clean: 579 passed / 1 skipped. Ready for qa.
- 2026-08-25 qa: PASS (commit 45fd963) -> po-review. Tree CLEAN. Verified every
  dimension:
  - Drove split end-to-end: an oversized 36-member cluster ran the scoped
    mini-pipeline (injected labeler) into 2 density-core children of 18 each
    (within 5-20), each a new leaf node carrying a #068 content-hash signature, and
    the oversized node RETIRED (its brief cascades). A <2-core result leaves the
    cluster intact (tested).
  - migrate is correct by construction + tested: it computes all misfit moves
    (best_other > own) against a FROZEN centroid snapshot, THEN applies them
    (remove_member/add_member), so on-topic members stay and only the source +
    target briefs dirty; forced/misfit chunks shed to the cluster that fits them.
  - dissolve: a below-2 cluster retires and each survivor re-enters the placement
    rule through the new SHARED `placement.assign_or_park` (a clean DRY extraction
    from #085 — the incremental rule and repair now share one join-or-park
    primitive; #085's placement tests stay green, behaviour preserved).
  - repair op picks ONE repair per cluster from size (>MAX_CAP 30 split, <2
    dissolve) + stored misfit rate (>0.25 migrate); each touches only its
    cluster('s targets); new/split nodes keep #068 signatures so a later full
    rebuild matches. Constants baked (MAX_CAP 30, MISFIT_THRESHOLD 0.25;
    min_cluster_size in core_labels). Deterministic.
  - ruff clean; full suite 579 passed / 1 skip; 6 repair tests + placement green;
    atomic Conventional Commit. Only #091 (settle) remains in M7.
- 2026-08-25 PO review: PASS -> done. Gated #090's commit (45fd963) in an isolated worktree (tree carried #091 settle WIP): ruff clean, 12 repair+placement tests pass, full suite 579 passed / 1 skip. Read repair.py: the repair op picks ONE local repair per cluster from size + stored misfit — split (>MAX_CAP 30: scoped mini-pipeline #086 -> density-core children 5-20, each a new leaf node with a #068 content-hash signature, the oversized node retires; <2 cores leaves it intact), migrate (>MISFIT_THRESHOLD 0.25: compute all best_other>own moves against a FROZEN centroid snapshot THEN apply, so on-topic members stay and only source+target briefs dirty), dissolve (<2: retire, each survivor re-enters placement via the new SHARED placement.assign_or_park — a clean DRY extraction so #085 incremental and #090 repair share one join-or-park primitive, #085 tests stay green). Each repair touches only its cluster's targets; new nodes keep #068 signatures so a later rebuild matches; constants baked (MAX_CAP 30, MISFIT_THRESHOLD 0.25, min_cluster_size 5); deterministic. All acceptance criteria met. Closed. **Only #091 (settle) remains in M7.**
