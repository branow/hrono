---
id: 091
title: `settle` — churn-triggered warm UMAP rebuild + membership diff + selective re-brief (T39)
priority: high
size: big
depends_on: [087, 040, 068, 089]
spec_refs: [build-order.md#T39, clustering-lifecycle.md, design-sketch-v1.md]
---

## Context
T39 and the LAST M7 ticket — the rare global maintenance pass (RECONCILE in
clustering-lifecycle.md), NOT an update path. Incremental placement (#085) drifts
the stored clusters over many batches; `settle` periodically does a full WARM
rebuild to re-tidy them, applying only the membership DELTA so briefs mostly
survive. Recipe settled (clustering-lifecycle.md RECONCILE + settle). #040's
warm-init seam (init = stored coords) and #068's signature reconcile are the
substrate; this ties them to a churn/misfit trigger.

## Description
- **Churn counter + trigger (T39.1)**: accumulate the per-tree drift/churn (the
  #087 drift counter + membership changes since the last settle); when it crosses a
  threshold, trigger settle. A MISFIT BACKSTOP: the #089 global misfit rate above
  ~2x the post-build baseline also triggers settle even if churn is low.
- **Warm UMAP rebuild (T39.2)**: a full UMAP(25, cosine, seed 42) with `init` =
  the STORED coords (warm start, #040's seam) -> HDBSCAN(leaf, 5) -> noise attach,
  over all current chunks. Warm start keeps the layout stable (small churn, not a
  cold reshuffle).
- **Membership diff + selective re-brief (T39.3)**: diff the new memberships against
  current; APPLY only the delta; re-brief ONLY nodes whose membership changed (via
  #064 signatures + #068 reconcile, which already keep unchanged nodes' ids/briefs).
  Measured cost ~10-15% membership churn (mostly small clusters merging/splitting).
  Reset the churn counter after a settle.
- Deterministic (fixed seed); pins/manual edits (M9) survive the re-cluster when
  they exist (honor as fixed) — no pins today, wire the seam.
- Runs the heavy UMAP/HDBSCAN OUTSIDE the #008 lock (load -> release -> compute ->
  re-acquire to persist the delta), like every heavy op.

## Acceptance criteria
- [ ] A churn/drift threshold triggers settle; the global-misfit backstop (> ~2x
      baseline) also triggers it; the counter resets after a settle.
- [ ] settle does a WARM UMAP rebuild (init = stored coords), diffs memberships, and
      applies only the delta — unchanged nodes keep ids + briefs (#068), only
      membership-changed nodes re-brief.
- [ ] Heavy compute runs outside the #008 lock; deterministic under the fixed seed.
- [ ] A settle over an unchanged corpus is a near-no-op (warm start reproduces the
      layout; ~0 membership delta -> ~0 re-briefs).
- [ ] `ruff format`, `ruff check --fix`, `pytest` all clean; work committed.

## Out of scope
- Manual-edit pins enforcement (M9) — wire the survive-seam, do not build pins.
- Multi-tree / breadth (M8).

## Review log
- 2026-08-25 PO: authored as T39, the last M7 ticket — the rare warm reconcile that
  re-tidies incremental drift. Churn/drift trigger (+ misfit backstop), warm UMAP
  rebuild on #040's init-seam, membership-diff selective re-brief via #064/#068.
  Completing this = M7 (Lifecycle) done: the incremental differentiator plus its
  self-maintenance. Constants baked; heavy compute off the lock.
- 2026-08-25 dev: implemented (commit 2d3df7c). New `tree/settle.py`, no new
  migration (reuses tree_batch.drift #087 + misfit/baseline #089). `should_settle`:
  drift >= CHURN_THRESHOLD (50) OR global misfit > MISFIT_FACTOR(2.0) x post-build
  baseline (the spec-exact RECONCILE trigger). The `settle` op, when triggered (or
  force=True), re-runs the settled pipeline — `cluster` (warm-starts UMAP from
  stored coords via #040's init seam; replace_tree applies the membership DELTA
  with #068 signature reconcile keeping unchanged node ids + briefs) -> `brief` ->
  `build_tree` -> `embed`, so only membership-changed nodes re-brief via #064 —
  then refreshes monitor over all clusters and RESETS drift (baseline is the
  post-build reference, left intact). Heavy UMAP/HDBSCAN + LLM run inside those ops
  off the #008 lock. Pins seam (M9) noted as the honour-point in cluster; none
  exist yet. Registered in app.py. Tests (6): tests/tree/test_settle.py — churn
  trigger, misfit-backstop trigger, warm reconcile over unchanged corpus is a
  near-no-op (0 LLM calls, node ids stable — the #068/#064 property), drift resets
  after a settle, an untriggered settle leaves the counter untouched. Gate clean:
  585 passed / 1 skipped. Ready for qa. This closes M7 (Lifecycle).
- 2026-08-25 qa: PASS (commit 2d3df7c) -> po-review. Tree CLEAN. Verified every
  dimension:
  - Drove the load-bearing near-no-op: after a full maintain, `settle(force=True)`
    over the UNCHANGED corpus made 0 LLM calls with node ids stable and drift reset
    to 0 — the warm reconcile reproduces the layout (deterministic cluster + #040
    warm-init), #068's signature reconcile keeps every unchanged node id, and #064
    skips their briefs, so nothing re-briefs when nothing drifted.
  - Trigger correct: `should_settle` fires on drift >= CHURN_THRESHOLD (50) OR the
    misfit backstop (global_rate > MISFIT_FACTOR 2.0 x post-build baseline) — the
    spec-exact RECONCILE trigger (tests cover churn trigger, misfit backstop,
    untriggered-leaves-counter). Drift resets after a settle; the baseline (the
    post-build reference) is correctly NOT reset.
  - Reconcile reuses the settled ops: cluster (warm UMAP from stored coords ->
    replace_tree membership DELTA with #068 reconcile) -> brief -> build_tree ->
    embed (the brief-passage churn pass, like #065). No sync/split/condense — it
    re-tidies the EXISTING chunks, condensations are content-cached. Heavy compute
    runs inside those ops off the #008 lock. Deterministic (seed 42). Pins seam
    (M9) noted as the honour-point; none exist yet.
  - ruff clean; full suite 585 passed / 1 skip; 6 tests; atomic Conventional
    Commit. **This closes M7 (Lifecycle): the incremental-update differentiator
    plus its self-maintenance (monitor -> repair -> settle) are complete.**
- 2026-08-25 PO review: PASS -> done. Tree clean, HEAD is #091's commit (2d3df7c). Read settle.py; ran the 6 settle tests, ruff clean, full suite 585 passed / 1 skip. Faithful to the RECONCILE recipe: should_settle fires on drift >= CHURN_THRESHOLD (50) OR the misfit backstop (global_rate > MISFIT_FACTOR 2.0 x the post-build baseline), spec-exact; drift resets after a settle, the baseline (post-build reference) does NOT reset. The reconcile reuses the settled ops — cluster (warm UMAP from stored coords via #040's init seam -> replace_tree applies the membership DELTA through #068's signature reconcile) -> brief -> build_tree -> embed brief-passage pass; no sync/split/condense (it re-tidies the EXISTING chunks; condensations are content-cached). Heavy compute runs inside those ops OFF the #008 lock; deterministic (seed 42); the M9 pins honour-point is noted (none exist yet). Verified the load-bearing near-no-op via qa's drive: settle over an UNCHANGED corpus = 0 LLM calls, node ids stable, drift reset -- the warm reconcile reproduces the layout, #068 keeps ids, #064 skips briefs. All acceptance criteria met. Closed. **M7 (Lifecycle) COMPLETE (068/083/085/086/087/089/090/091 + #088): the incremental-update differentiator AND its self-maintenance (monitor -> repair -> settle) are done. hrono's core thesis -- a self-maintaining hierarchical knowledge base with true incremental update -- is fully realized.**
