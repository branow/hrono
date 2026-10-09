---
id: E003
title: a real build does not fail at random, and a slow write says it landed
priority: high
depends_on: []
requirements: []
---

## Goal
Two defects from the #197 walkthrough on hrono's own repo: one maintain failed
with "clustering produced no clusters" and the identical next one succeeded;
`hrono models set` on a local model reports a timeout for a write that landed.

## Tickets

### 1 reproduce, then fix, "clustering produced no clusters"
Change: reproduce first (394 sections, 768-dim, recipe in archive/198). If
HDBSCAN can label everything noise on a valid corpus, fall back (e.g. one
cluster / retry with a smaller min_cluster_size) instead of raising.
Done when:
- [ ] the cause is stated in the Log with the reproducing input, or the
  non-reproduction is recorded with what was tried
- [ ] an all-noise labelling no longer fails the run; tested on real vectors
Look at: src/hrono/cluster/build.py `_attach_noise`; archive/198

### 2 registry writes get a budget that fits validation
Change: a longer client timeout for writes that validate against a provider or
load weights; on timeout, tell the user how to check (`hrono models list`).
Done when:
- [ ] `hrono models set` on a first-load local model reports success
- [ ] a timed-out write names the command that checks whether it landed
Look at: src/hrono/client/http.py, src/hrono/cli.py; archive/199

## Out of scope
- clustering recipe changes beyond the all-noise case

## Log
- 2026-10-03 po: created from #198, #199.
- 2026-10-03 dev: started round 1 on epic/E003.
- 2026-10-03 dev: T1 5ec3273. Cause reproduced: the #197 db (the local demo database) shows the failed maintain died in cluster-briefs at level 0, over 26 IDENTICAL brief texts (one degenerate prompt-echo brief); 26 copies of that stored vector through the real recipe gave "no clusters", [0,1], "no clusters" across three processes — seeded UMAP over tied points is not reproducible, and the rerun's 2 upper nodes match. Fix: all-noise is one topic (density members, coords kept), not a raise.
- T1 verify: real-backend tests on structureless 384-dim vectors (build_clusters, and cluster-briefs via its op); mutations: restore the raise -> 3 tests red; attached=True -> stub test red. Full gate green (1687 passed).
- 2026-10-03 dev: T2 6bf910c. Drove it: fresh `hrono serve` on a scratch db, `hrono models set local-embed` (MiniLM, first load) took 13.93s and printed "Wrote models/local-embed." (10s budget would have timed out); `models list` shows it. Timeout path tested through the real Client + MockTransport + the CLI boundary: "within 120s ... check with 'hrono models get emb'".
- T2 mutations: budget dropped from set -> 2 red; injected client ignores per-request timeout -> 1 red; check not forwarded -> 2 red; message ignores check -> 2 red. Gate green (1693 passed, 3 skipped). Note: tied-vector nondeterminism (T1) is documented, not tested — no input reproduces it deterministically.
- 2026-10-03 qa: round 1 FAIL at 6bf910c. Gate green (1693 passed); drove models set (14.9s, Wrote) and a 120s timeout against a hanging server (names 'hrono models get local-embed'); tied 768-dim vectors x4 processes give 1 or 2 topics, never a failure; mutations re-run: restored raise -> 3 red, sims=1.0 -> 1 red, check=list -> 2 red. Finding: a leaf-level all-noise build now reports collected:false, indistinguishable from a real one-topic clustering (#133) — see qa findings.
- 2026-10-03 dev: round 2 538111a. ClusterResult.collapsed (all-noise labelling) -> cluster op reports collected:true; new real-backend op test over 30 stored structureless vectors (precondition: core_labels of the op's own combined vectors is all -1). cluster-briefs returns no counts, so nothing to report there; build_tree already treats a one-node level as the root.
- round 2 mutations: op ignores collapsed -> 1 red; collapsed always False -> 3 red; all->any -> 1 red; dead len() guard and dead collected=False init removed. Gate green (1695 passed, 3 skipped).
- 2026-10-03 qa: round 2 PASS at 538111a. Round 1 finding fixed: an all-noise leaf build now reports collected:true (ClusterResult.collapsed -> op). Gate: ruff format/check clean; pytest 1694 passed, 4 skipped (the extra skip is the embed extra missing from the venv I used, not the change). New op test passed in 4 separate processes. Mutations re-run: op ignores collapsed -> 1 red (dev's); mine, collapsed computed after noise attachment -> 3 red. T2 has not changed since its round 1 pass.
- 2026-10-03 po: ACCEPT at 538111a. Both Done-whens met by qa's drives (all-noise -> one topic, reported collected; models set 14.9s Wrote; timeout names the get command); README says it. The prompt-echo briefs behind #198 -> backlog/identical-prompt-echo-briefs.md.
- 2026-10-03 dev: merged to main (rebased onto f3e4853, gate green 1698 passed); main head 6fba790.
