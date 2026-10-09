---
id: 198
title: a real-corpus build failed once with "clustering produced no clusters"
priority: high
size: medium
depends_on: [040]
spec_refs: []
---

## Context
Found in #197's walkthrough, on hrono's own repository. `tree maintain` failed
with `cluster-error: clustering produced no clusters`; the NEXT identical
invocation succeeded and built 26 topics. Running the recipe directly over the
same 394 combined vectors gave 26 clusters and 76 attached noise points.

`build._attach_noise` raises when HDBSCAN labelled every point noise
(`len(core_idx) == 0`). So on that run it did, and on the next it did not.

## What is known
- 394 sections, 768-dim combined vectors, recipe `min_points=27,
  n_components=25, n_neighbors=15, min_cluster_size=5`.
- UMAP is seeded (`random_state` is set — the "n_jobs overridden" warning says
  so), which is what makes ONE differing run interesting rather than expected.
- The corpus is a live repository that was being committed to between runs, so
  the input may have differed by a few files.
- The first run of the three had failed earlier, at the brief stage, so the
  second ran against a corpus that had just been embedded.

## What to do
Reproduce before fixing. The corpus is cheap to rebuild (a local clone plus
MiniLM). If it reproduces, the question is whether a seeded UMAP is really
deterministic across processes here, or whether the input differed.

Whatever the cause, the MESSAGE needs work regardless: "clustering produced no
clusters" tells an operator nothing they can act on, and this is the one error
in the pipeline that can end a long expensive run.

## Review log
- 2026-09-28 po: authored from #197. Recorded rather than guessed at.
