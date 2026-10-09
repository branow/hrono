---
id: 085
title: incremental `update` op — sticky re-check + nearest-centroid placement (T34)
priority: high
size: big
depends_on: [083, 068, 040, 086]
spec_refs: [build-order.md#T34, clustering-lifecycle.md, how-hrono-works.md]
---

## Context
T34, the true incremental UPDATE path and hrono's differentiator in its efficient
form. Today `maintain` full-rebuilds the cluster level each run (keeping stable
ids via #068). T34 replaces that for change batches: it NEVER re-runs UMAP/HDBSCAN
over existing content — it places only the changed chunks (from #083's diff) by
deterministic dot products against stored cluster centroids, so untouched chunks
cannot move and churn = changed content, exactly. Recipe is SETTLED
(clustering-lifecycle.md UPDATE section) — bake the constants, do not re-derive.

## Description
An `update` op that consumes #083's diff and applies the per-chunk placement rule
(all constants baked: TAU=0.70, min_cluster_size=5, MAX_CAP=30):
- **unchanged hash** -> nothing.
- **deleted** -> remove from its cluster; mark that cluster's brief dirty (#064).
  If the cluster drops below 2 members, DISSOLVE it: each remaining member re-enters
  the placement rule. (T34.4)
- **changed** (new hash for a tracked chunk) -> embed, then STICKY RE-CHECK FIRST:
  similarity to its own cluster's STORED PRE-BATCH centroid >= TAU -> stays (only its
  brief dirty); < TAU -> placement rule. Never re-place an edited chunk from scratch
  (the argmax between adjacent leaves is a hair-trigger — 64% churn for nothing).
  Pre-batch centroid ON PURPOSE (survives a batch editing a whole cluster's files).
  (T34.1)
- **new** (no previous cluster) -> embed, PLACEMENT RULE: best similarity vs cluster
  CENTROIDS (not nearest member): >= TAU join that cluster (mark dirty); < TAU -> the
  pending pool (#086 incubator). (T34.2)
- **moved/renamed** (same content hash, new path) -> MOVE in place: reuse the content
  embedding (content-addressed), recompute the path embedding, re-check the combined
  vector vs the chunk's current cluster centroid: >= TAU stays (metadata-only update);
  < TAU -> placement rule. Never treat a move as delete+add. (T34.3)
- Centroid = mean of a cluster's member combined vectors, renormalized. Every decision
  is a deterministic dot product. A joined/dirtied cluster's brief regenerates via the
  existing #064 signature -> #059/#061 skip/rebuild path.
- Lock discipline like the other ops (load under lock -> compute -> persist).

## Acceptance criteria
- [ ] `update` places only the diff's changed chunks; an UNTOUCHED chunk never moves
      (asserted: 0 moved of N untouched over a change batch).
- [ ] changed-chunk sticky re-check keeps a chunk in its cluster when own-centroid
      sim >= TAU; a chunk whose content left the topic (< TAU) re-places.
- [ ] new chunk joins the best centroid >= TAU or parks in the pending pool (#086).
- [ ] moved/renamed reuses the content vector (no re-embed) and stays unless the path
      shift drops it below TAU; deleted removes + dissolves-below-2.
- [ ] Every placement is deterministic; dirtied clusters' briefs regenerate, others
      are untouched; constants baked (TAU 0.70, min_cluster_size 5).
- [ ] `ruff format`, `ruff check --fix`, `pytest` all clean; work committed.

## Out of scope
- Pending-pool drain / force-assign / aging (T35 / #086 — this op only PARKS into it).
- propagate judge cascade (T36), monitor (T37), repair (T38), settle/reconcile (T39).
- The full warm-rebuild reconcile path (T39) — that stays the maintenance-only route.

## Review log
- 2026-08-25 PO: authored as T34 on the #083 diff + #068 stable-id substrate. The
  settled UPDATE recipe: sticky pre-batch-centroid re-check for edits, nearest-CENTROID
  placement for new, move-in-place, delete+dissolve; sub-TAU parks in the incubator
  (#086). Constants baked. The differentiator's efficient form (no full re-cluster).
- 2026-08-25 dev: implemented (commit 6f145af). Three layers plus the op:
  `cluster/placement.py` — `place(conn, tree, deltas, centroids, model, batch)`
  applies the per-chunk rule against a FROZEN pre-batch centroid snapshot: deleted
  (membership already cascaded) marks its node for a dissolve sweep; changed/moved
  run the sticky re-check vs their prior node's pre-batch centroid (>= TAU 0.70 stays,
  else placement); new runs the placement rule (best centroid >= TAU joins, else
  `incubator.park`). A final dissolve sweep deletes any node that dropped below two
  members and re-places its survivors. Every decision is a dot product; TAU baked.
  `ingest/reconcile.py` — bridges #083's FILE diff to section-level deltas, mutating
  only the changed files' sections (untouched files keep their section ids AND
  membership): matches new->old sections by CONTENT HASH first (an unchanged section
  in an edited file self-matches and stays put via sticky sim~1), then by ordinal;
  unmatched old -> deleted. Moved reuses the content body (content-addressed) so embed
  skips it. `tree/update.py` — the `update` op: per source sync -> diff -> snapshot
  pre-batch centroids + reconcile (one #008 lock) -> embed (own lock) -> place (re-lock);
  registered in server/app.py. Migration 0018 adds `tree_batch` (monotonic per-tree
  update-batch counter stamping incubator parks). Promoted split_op `_store_file` ->
  public `store_file` (returns stored (id, ordinal, hash)); added fts.clear_path and
  cluster/store helpers (section_node, member_count, node_member_rows, remove_member,
  delete_node). Tests (13): tests/cluster/test_placement.py (6 — join/park/sticky-stay/
  off-topic-replace/dissolve-below-2/move-stays, plus untouched-never-moves assertion),
  tests/ingest/test_reconcile.py (4 — new/changed-carries-prior-node/deleted/moved-
  reuses-hash), tests/tree/test_update.py (3 — registered, swaps-changed-leaves-
  untouched, no-change-noop). Gate clean: 558 passed / 1 skipped. Parking on sub-TAU
  requires an existing cluster set; with none, a chunk parks in the incubator as
  designed. Ready for qa.
- 2026-08-25 qa: PASS (commit 6f145af) -> po-review. Tree CLEAN at handoff.
  Verified the keystone efficient-incremental behavior end-to-end:
  - Drove full maintain (13 LLM calls) -> edit ONE of 9 files -> `update`
    (placement only, no re-cluster) -> `brief`: only 1 of 3 leaf briefs
    regenerated; the untouched leaves skipped via #064's content-signature. This is
    the differentiator in efficient form (churn = changed content), proven through
    the real op chain.
  - `update` places ONLY the diff's changed chunks: untouched FILES aren't in
    #083's diff so their sections + memberships are never touched
    (test_update asserts f1's section ids unchanged after editing f0); an unchanged
    section inside an EDITED file re-matches by content hash and re-joins its
    cluster via the sticky re-check (sim ~ 1), so it doesn't change clusters either.
  - placement.py is faithful to the settled recipe: sticky re-check vs the FROZEN
    PRE-BATCH centroid (>= TAU 0.70 stays, else re-place); new -> best CENTROID
    >= TAU joins else parks in the #086 incubator; moved reuses the content vector
    (content-addressed, embed skips it) and re-checks the new-path combined vector;
    deleted's membership cascaded in reconcile, then a dissolve sweep deletes any
    node under 2 members and re-places its survivors. Every decision is a dot
    product; TAU baked; new clusters form only via the incubator drain (not here).
  - Op wiring correct: diff + PRE-BATCH centroid snapshot + reconcile under one
    #008 lock (centroids are consistently pre-batch), embed under its own lock,
    placement re-acquires; `tree_batch` (migration 0018) stamps incubator parks for
    aging. reconcile mutates only changed files' sections and carries each chunk's
    prior node id for the sticky target.
  - ruff clean; full suite 558 passed / 1 skip; 13 tests (placement 6 / reconcile
    4 / update 3); atomic Conventional Commit (the `_store_file`->`store_file`
    promotion + fts.clear_path + cluster/store helpers are all in service of this
    op).
  Scope note for PO (NOT a defect): `update` is the PLACEMENT stage — it dirties
  the affected leaf signatures but does not itself run brief/build_tree, so after
  `update` alone the briefs are stale until a `brief` pass runs (which then
  regenerates only the dirtied leaves, as I verified). A one-command incremental
  path (an "incremental maintain" chaining update -> brief -> propagate) + the
  upper-level propagate cascade are T36/orchestration, explicitly out of this
  ticket's scope. The leaf placement + selective-regeneration mechanism is
  complete and correct.
- 2026-08-25 PO review: PASS -> done. Tree clean, HEAD is #085's commit (6f145af). Read placement.py/reconcile.py/update.py; ran the 13 placement/reconcile/update tests, ruff clean, full suite 558 passed / 1 skip. Faithful to the settled recipe: sticky re-check vs the FROZEN PRE-BATCH centroid (>= TAU 0.70 stays, else re-place), new -> best CENTROID >= TAU joins else parks in the #086 incubator, moved reuses the content-addressed vector + re-checks the new-path combined vector, deleted cascades in reconcile then a dissolve sweep deletes nodes under 2 members and re-places survivors; every decision a dot product, TAU baked, new clusters form only via the incubator drain. Op wiring correct: diff (#083) + pre-batch centroid snapshot + reconcile under one #008 lock (centroids consistently pre-batch), embed under its own lock, placement re-acquires; migration 0018 tree_batch stamps incubator parks for aging. Verified the keystone via qa's drive: edit 1 of 9 files -> update (placement only, no re-cluster) -> brief regenerates only 1 of 3 leaves, untouched sections never touched. All acceptance criteria met. Closed. Accepted qa's scope note (NOT a defect): update is the PLACEMENT stage — it dirties leaf signatures; the UPWARD propagation of a changed leaf brief (which #068's child-id signature cannot detect, since a sticky-placed leaf keeps its id) is T36 propagate, the next tranche. **T34 (incremental update) done; the leaf-level incremental placement loop (#083 diff -> #085 place -> #086 incubate -> #064 selective re-brief) is closed. Remaining for the FULL incremental promise: T36 propagate (upward cascade), then T37 monitor / T38 repair / T39 settle.**
