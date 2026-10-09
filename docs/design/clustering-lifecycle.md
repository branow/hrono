# hrono — clustering lifecycle (stored layer)

Rules for how the **stored** level-1 clusters in the DB are built, updated, monitored, and repaired.
This is NOT the agent-facing tree: the level ratios / min-floor / max-cap in `design-sketch-v1.md`
describe the *rendered view* an agent traverses; the stored clusters below are its raw material.
Evidence for every rule: `prototype/research.ipynb` steps 9–23; conclusions summarized in `context.md`.

## Parameters (settled empirically)

| name | value | meaning |
|---|---|---|
| embedding model | `embedding.toml` (`Qwen3-Embedding-0.6B`, 1024 dims) | one config string; vectors from different models never mix |
| PATH_ALPHA | 0.5 | chunk vector = `[√(1-α)·content_emb ; √α·path_emb]` → dot product = blended similarity |
| UMAP | 25 dims, cosine, seed 42, warm-start (`init` = previous coords) | build/reconcile only — never runs during updates |
| HDBSCAN | `leaf`, `min_cluster_size=5`, euclidean | build/reconcile + mini-pipeline only |
| TAU | 0.70 | similarity threshold for joining an existing cluster |
| MAX_CAP | 30 (split into children of 5-20) | derived from the summarization budget, not clustering: ~500 tokens/chunk → 30 chunks ≈ 15k summary-input tokens, the edge of one faithful summary; also sits above the organic leaf-size range (5-28, median ~10) so it only catches pathological growth. Re-tune when summary-quality evals exist. |
| misfit thresholds | global reconcile: ~2× post-build baseline (≈0.06 here); per-cluster repair: >~25% of members | baseline is nonzero by nature (0.031 fresh here) — HDBSCAN's non-spherical clusters have edge members leaning to neighbor centroids — so thresholds are relative to the measured post-build baseline, never absolute |

**The one reusable mechanism — "scoped mini-pipeline":** run UMAP→HDBSCAN(leaf)→
nearest-member-assignment on a given set of chunks *only*, deterministic for a fixed set
(fixed seed), touching nothing outside the set. Used for: novel pools, oversized splits,
stale-cluster repairs. (Validated: reproduced a cold rebuild's clusters for an added repo
at ARI 0.81 — step 22.)

## Operations

### 1. BUILD (once per corpus; rare)
Embed all chunks (per unique hash) → UMAP(25, warm if previous coords exist) →
HDBSCAN(leaf, 5) → assign every noise chunk to the cluster of its most-similar member
(similarity computed in original combined space, not UMAP space). Persist: memberships,
`assigned` flag (density member vs proximity attachment), UMAP coordinates (for future warm starts).
Result: 0% noise — every chunk has exactly one cluster.

### 2. UPDATE (per change batch — the normal operation)
Never re-runs UMAP/HDBSCAN over existing content. Per chunk:
- **unchanged hash** → nothing.
- **deleted** → remove from its cluster; mark that cluster's summary dirty.
  If the cluster drops below 2 members, dissolve it: remaining member goes through the
  placement rule below.
- **changed (new hash for a chunk of an already-tracked file)** → embed → **sticky re-check
  first**: similarity to its own cluster's *stored pre-batch centroid* `≥ TAU` → stays; only
  its own summary dirty. `< TAU` (the content genuinely left the topic) → placement rule
  below. Never re-place an edited chunk from scratch: the placement argmax between adjacent
  leaf clusters is a hair-trigger — nearest-member re-placement hops 64% of edited chunks
  (and 13% of *unchanged* chunks in a leave-one-out control) into an adjacent cluster,
  doubling summary churn for nothing. Pre-batch centroid on purpose: "new version vs the
  cluster as it was" is the drift question, and it survives the edge where one batch edits
  a whole cluster's files (post-removal that cluster has no members to average). Validated
  on real webphone edit batches incl. a 178-file refactor: 100% stay, weakest own-sim 0.889,
  0/216 pending, dirty summaries per batch cut 8→4 / 11→9 / 27→23
  (`prototype/edit-stability.ipynb`).
- **new (no previous cluster)** → embed → **placement rule**: best similarity against
  cluster *centroids* (not nearest member: 95% vs 87% leave-one-out self-consistency on
  unchanged content, and O(#clusters) instead of O(#chunks) at scale):
  - `≥ TAU` → join that cluster; mark it dirty.
  - `< TAU` → into the **pending pool** (parked, queryable as "pending", not yet in a cluster).
- **moved/renamed file (same hash, new path)** → MOVE, in place: content embedding reused
  (content-addressed), path embedding recomputed, combined vector re-checked against the
  chunk's current cluster's stored centroid — still `≥ TAU` → stays, metadata-only update;
  `< TAU` (moved to a semantically different area — a real reorganization signal, path is
  α=0.5 of the vector) → re-place via the placement rule. Never treat a move as delete+add.
- **pending pool reaches `min_cluster_size`** → scoped mini-pipeline over the pool; only its
  *density-core* clusters are emitted as new clusters (stragglers are never married to each
  other). Residual pool noise is then **force-assigned to the most similar existing cluster,
  ignoring TAU** — TAU is the "clearly needs no new cluster" bar, not an admission gate; a
  chunk outside the tree is unfindable, which is worse than one alien member in a summary.
  Force-placed chunks carry a `forced` flag + their placement similarity; the misfit monitor
  re-checks flagged chunks preferentially, so a *pioneer* (first chunk of a new topic, placed
  wrong) migrates automatically once its real siblings arrive and form their cluster.
- **pool aging**: a chunk pending for more than N batches while the pool stays below
  `min_cluster_size` is force-assigned the same way (flagged) — nothing waits forever.

Guarantees: untouched chunks cannot move (nothing recomputes them); an edited chunk keeps
its cluster unless its content no longer fits the cluster it was in; every placement is
deterministic (dot products / fixed seeds); churn = changed content, exactly.
(Validated: 0 moved of 419 untouched; added repo formed own clusters, 90/91 refused
absorption — step 21; edited chunks 100% stay, 0/216 pending — edit-stability.ipynb.)

### 3. MONITOR (after every update batch)
**Misfit rate**, exactly: all chunk vectors are unit-length; each cluster's centroid = mean of
member vectors, re-normalized. For chunk c in cluster K: `own = c·centroid_K`,
`best_other = max_J≠K (c·centroid_J)`; c is a misfit iff `best_other > own`. Rate = misfits/total,
tracked globally and per cluster. Deterministic, plain dot products. Reference points measured:
0.031 fresh build (16/510), 0.035 after incremental growth. At 1M-chunk scale, compute
incrementally: re-check only members of dirty clusters plus a random sample per batch.

### 4. LOCAL REPAIRS (triggered by monitor / caps; touch one cluster only)
- **split**: cluster size > MAX_CAP → scoped mini-pipeline over its members → 2+ clusters;
  only their summaries rebuild.
- **repair**: one cluster's misfit above threshold → same scoped mini-pipeline over its
  members; alternatively migrate individual high-misfit chunks to their better cluster
  (both dirty their summaries).
- **dissolve**: cluster below 2 members → members re-enter the update rule.

### 5. RECONCILE (rare, only when the global monitor says so)
Global misfit above threshold → full warm rebuild (UMAP `init` = stored coordinates) →
**diff against current memberships** → apply, re-summarizing only nodes whose membership
changed. Measured cost: ~10–15% membership churn, mostly whole small clusters merging/
splitting with neighbors, not files scattering (steps 16, 19, 20). This is maintenance,
not an update path.

## Invariants
1. An update never moves a chunk whose content didn't change.
2. Every placement decision outside BUILD/RECONCILE is deterministic given the stored state.
3. Every chunk is in exactly one cluster, or explicitly in the pending pool.
4. Every membership change marks the affected cluster's summary dirty — summaries are
   regenerated from dirty flags only, never wholesale.
5. Embeddings are content-addressed (`hash`, `model`); nothing is ever embedded twice.
6. An edited chunk leaves its cluster only if its content no longer fits it (sticky
   re-check failed) — never because a neighboring cluster is marginally closer.

## Known open points
- Constants (MAX_CAP 30, TAU 0.70, misfit thresholds) were measured on 510 chunks; mechanisms
  are scale-independent but the numbers should be re-measured on a mid-size corpus (~50k chunks)
  before trusting them at 1M. Leaf cluster sizes track topic granularity, not corpus size, so
  scale should mean more clusters, not bigger ones — homogeneous blobs (e.g. hundreds of
  near-identical generated files) are the exception and are handled by the MAX_CAP split.
- Modified-chunk stability: TESTED, rule ADOPTED (2026-07-27, `prototype/edit-stability.ipynb` —
  webphone HEAD vs HEAD~3/10/15 replayed against the stored tree). Edits never fall below TAU
  (0/216 pending); the old nearest-member join rule was the churn source (64% adjacent-cluster
  hops on edited chunks, 13% misplacement even on unchanged chunks); the sticky re-check +
  nearest-centroid placement now in the UPDATE rule above keeps 100% of edited chunks in place
  (weakest own-sim 0.889). Residual caveat: TAU=0.70 was calibrated on nearest-member
  similarities (step 21's fmm refusal); centroid similarities run lower, so refusal gets
  strictly safer (fails into the pending pool, which the mini-pipeline drains) — but re-measure
  TAU against centroids alongside the other constants at the ~50k corpus.
