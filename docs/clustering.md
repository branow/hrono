# Clustering lifecycle

How the stored topics are built, updated, monitored, repaired and settled. The
stored tree is not the agent-facing export: the export collapses it to a few
wide levels (see [architecture.md](architecture.md#explore)). The evidence for
every rule is in [`research/prototype/research.ipynb`](research/prototype/research.ipynb)
(steps 9–23) and [`edit-stability.ipynb`](research/prototype/edit-stability.ipynb).

Code: `src/hrono/cluster/` (build, placement, incubator, monitor, repair,
levels), `src/hrono/tree/` (the `update`, `sync-tree`, `settle` and `maintain`
ops).

## Constants

All baked in code, not config.

| Name | Value | Where | Why |
|---|---|---|---|
| `TEXT_WEIGHT`, `FOLDER_WEIGHT` | 0.6, 0.4 | `cluster/blend.py` | Section vector = `[√0.6·text ; √0.4·folders]`, so a dot product is `0.6·text_sim + 0.4·folder_sim`. Text is the embedding of the section's condensation (its raw content until condensed). Folders: every leading prefix of `source/folders/file`, the one at depth d weighing 1/d, hashed into `FOLDER_DIMS` (2048); two paths score the weight of their shared prefixes over the geometric mean of their totals. Chosen in `evaluations/2026-10-cluster-formula/`. Briefs have no path and cluster on content only. |
| `ALPHA` | 0.5 | `cluster/blend.py` | Recall's blend of content with the embedded path string, `[√(1−α)·content ; √α·path]`. Not used for clustering. |
| Recipe ladder | ≥ 27 points: UMAP 25 dims, 15 neighbours, `min_cluster_size` 5. ≥ 12 points: 10 dims, 10 neighbours, `min_cluster_size` 3. | `cluster/recipe.py` | One pipeline at every level, scaled to the point count. UMAP's spectral init needs N ≥ dims + 2 (UMAP-25 fails at 26 points). Below 12 points a level cannot be reduced and is one topic. |
| UMAP | cosine, seed 42, warm `init` from stored coords | `cluster/build.py` | Build and settle only; never during an update. |
| HDBSCAN | `leaf`, euclidean | `cluster/build.py` | Leaf selection gives the many small topics a summarization tree wants. |
| `TAU` | 0.70 | `cluster/placement.py` | Similarity a section needs to join an existing topic. Set for the old content-and-path-string space; to recalibrate on the new clustering vector. |
| `MAX_CAP` | 30 members | `cluster/repair.py` | The edge of one faithful brief (~500 tokens × 30 ≈ 15k input tokens). Small corpora's organic leaves sit below it (5–28, median ~10); on bcreg (8,459 sections) 62 of 432 cold-built leaves held 31–65. A cold build splits them before any brief (`cluster/op.py`); 52 of the 62 split, the rest have no two density cores and stay whole. |
| `MISFIT_THRESHOLD` | 0.25 | `cluster/repair.py` | Per-topic misfit share that triggers a migrate. |
| `SAMPLE_SIZE` | 32 topics | `cluster/monitor.py` | Bounded re-check per batch beyond the dirty topics. |
| `CHURN_THRESHOLD` | 50 drift points | `tree/settle.py` | When a settle is due. |
| `MISFIT_FACTOR` | 2.0 | `tree/settle.py` | Global misfit above 2× the post-build baseline also makes a settle due. |

The constants were measured on ~500 sections. The mechanisms do not depend on
scale, but the numbers should be re-measured on a larger corpus. Leaf sizes
track topic granularity, not corpus size, so a larger corpus should mean more
topics, not bigger ones.

**The scoped mini-pipeline** is the one reusable mechanism: UMAP → HDBSCAN
(leaf) → attach, run over a given set of sections only, deterministic for a
fixed set and touching nothing outside it. It drains the incubator and splits
oversized topics. It reproduced a cold rebuild's topics for an added repo at
ARI 0.81.

## Build

`cluster` (`cluster/op.py`): combined vectors → UMAP (warm from stored coords
when they exist and have the right width) → HDBSCAN leaf → every noise section
attaches to its nearest density-core member by dot product in the original
combined space, which is deterministic and independent of the reducer. Members
keep an attachment similarity; core members do not. The result has no noise:
every section is in exactly one topic. A level that HDBSCAN labels entirely
noise is one topic, flagged `collapsed`.

Noise is the corpus's most distinctive sections, not garbage. Lowering
`min_cluster_size` made noise worse (3 → 22% vs 17%; 2 → micro-pairs), so
noise is attached rather than shrunk. Attachment also stabilizes rebuilds:
warm rebuild agreement rises from ARI 0.55–0.59 (cores only) to 0.81–0.82.

Upper levels (`cluster-briefs`, `cluster/levels.py`) run the same build over
the level's brief vectors, until one root remains (`summarize/build_tree.py`).

## Update

`update` (`tree/update.py`) never runs UMAP or HDBSCAN over existing content,
so untouched sections cannot move and churn equals changed content. The file
diff (`ingest/diff.py`) classifies by content hash; placement
(`cluster/placement.py`) is a dot product against the **pre-batch** centroids:

- **Unchanged hash**: nothing.
- **Deleted**: membership goes; a topic below 2 members dissolves and each
  survivor is re-placed.
- **Changed**: sticky re-check against its own topic's pre-batch centroid.
  ≥ `TAU` stays, and only that brief goes stale. < `TAU` goes to the placement
  rule. A changed section is never re-placed from scratch: the argmax between
  adjacent leaf topics is a hair trigger, and nearest-member re-placement moved
  64% of edited sections (and 13% of unchanged ones) to a neighbour. With the
  sticky rule, 100% of edited sections stayed on real edit batches up to a
  178-file refactor (weakest own-similarity 0.889). The pre-batch centroid also
  survives a batch that edits every file of one topic.
- **Moved** (same bytes, new path): kept in place with its topic, similarity
  and `forced` flag. Re-scoring it would eject working members, because the
  path is half the vector. A move to a new extension splits differently and
  arrives as *changed*.
- **New**: best similarity against topic centroids (95% leave-one-out
  self-consistency vs 87% for nearest member, and O(topics)). ≥ `TAU` joins;
  < `TAU` parks in the incubator.

Pinned members (`src/hrono/pins.py`) are never moved by placement or repair.

## Incubator

`cluster/incubator.py`. The pool is temporary storage inside one run, as in
the research (`research.ipynb` steps 21–23): a section placed below `TAU` is
parked while the run places the rest, and at the end of the run the pool is
emptied:

- **Drain**, when the pool has `MIN_POINTS` (12) sections: the scoped
  mini-pipeline over the pool. Only density-core clusters become new topics;
  stragglers are never married to each other.
- **Home** everything left, drain noise or a pool too small to cluster, to the
  nearest existing topic, ignoring `TAU`. `TAU` is the "clearly needs no
  new topic" bar, not an admission gate: a section outside the tree is
  unfindable, which is worse than one alien member in a brief. Forced members
  carry a `forced` flag so the monitor re-checks them and a pioneer migrates
  once its real siblings form a topic.

`settle` and a full `cluster` also home the pool.

## Monitor

`cluster/monitor.py`. Vectors are unit length; a centroid is the renormalized
mean of its members. A section is a **misfit** iff its similarity to another
topic's centroid exceeds its similarity to its own. A forced member is a misfit
while its own similarity is below `TAU`, because nearest-centroid attachment
makes `own` the maximum by construction. Upper levels ask the same question in
brief space over child edges.

Per-topic counts persist, so a batch re-checks only dirty topics plus a
sample. The first run records the baseline; a fresh build's rate is nonzero
by nature (0.031 measured, since clusters are not spheres), so every threshold
is relative to it.

## Repair

`cluster/repair.py`, one topic at a time; only that topic's brief regenerates.

- **Split**: over `MAX_CAP` → scoped mini-pipeline over its members into
  density-core children; residual noise attaches to the nearest child. The
  cold `cluster` op applies the same split to every leaf it built, until
  none is over the cap or none splits further.
- **Migrate**: misfit share over `MISFIT_THRESHOLD`, or any forced member →
  each misfit moves to the topic that fits it and is recorded unforced. Upper
  levels migrate children in brief space.
- **Dissolve**: below 2 members → survivors re-enter placement.

## Settle

`tree/settle.py`. Incremental life degrades structure that no single-topic
repair fixes, so a tree is periodically settled: a warm rebuild (UMAP `init` =
stored coords), then only the membership diff is applied and only changed
topics are re-briefed. A settle over an unchanged corpus is a near no-op.

It is due when accumulated drift reaches `CHURN_THRESHOLD`, or global misfit
exceeds `MISFIT_FACTOR` × baseline. Drift is bumped by the relevance judge
(minor +1, major +2; see [summarization.md](summarization.md#propagation)) and
resets after a settle. Drift, not the misfit rate, is the primary trigger
because migrations keep the rate looking healthy while structure decays. A warm
rebuild itself reshuffles ~10–15% of memberships (mostly small topics merging
or splitting, not files scattering).

`sync-tree` reports when a settle is due but never runs one: settling costs
LLM calls, and hrono does not spend money unasked.

## Invariants

1. An update never moves a section whose content did not change.
2. Every placement outside build and settle is deterministic given the stored
   state.
3. Every section is in exactly one topic or in the incubator, never both.
4. Every membership change marks the affected brief stale; briefs regenerate
   from staleness only, never wholesale.
5. Embeddings and condensations are content-addressed; nothing is computed
   twice for the same bytes.
6. A changed section leaves its topic only if its content no longer fits it.
7. A pinned entity is never moved or rewritten by the pipeline.
