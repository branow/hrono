---
id: 040
title: `cluster` build — UMAP reduce + HDBSCAN leaf + noise attach + persist (T18)
priority: high
size: big
depends_on: [039, 023]
spec_refs: [build-order.md#T18, how-hrono-works.md, clustering-lifecycle.md, design-sketch-v1.md]
---

## Context
This turns embedded sections into the bottom level of the topic tree: cluster the
combined vectors (#039) into groups, attach the noise points, and persist the
membership + coordinates + flags that the brief step (M4) and the tree build on.
It is the `cluster` op (empty tree = full build; incremental placement is M7).
The clustering recipe and constants are SETTLED in `clustering-lifecycle.md` and
`how-hrono-works.md` - bake them, do not re-derive. Load `engineering:developer`.

## Description
Register a `cluster` job op (into #023's registry) that does a full build over a
tree's sections' combined vectors (#039):

1. **UMAP reduce (T18.1)**: reduce the combined vectors to **25 dimensions**,
   `metric="cosine"`, a **fixed seed** (deterministic), via `umap-learn`. Expose
   a warm-init hook (init = stored coords) for later incremental settle (#T39) -
   wire the seam even if the full build inits fresh. The nonlinear reduction
   creates the density contrast HDBSCAN needs.
2. **HDBSCAN leaf (T18.2)**: cluster the reduced vectors with
   `min_cluster_size=5`, `metric="euclidean"`,
   `cluster_selection_method="leaf"` (leaf selection -> many small clusters, the
   shape a summarization tree needs), via `hdbscan`.
3. **Noise attachment (T18.3)**: HDBSCAN leaves some points as noise (-1);
   attach each noise point to its nearest cluster **in the original combined
   space** (not the reduced space), so every section lands in a topic. Document
   the nearest-cluster rule (e.g. nearest centroid / nearest member by combined-
   space cosine).
4. **Persist (T18.4)**: store the resulting bottom-level topics (nodes) with
   their **members** (which sections), the section **coords** (the reduced 25-d
   position, for warm-init + the dashboard graph), and **flags** (e.g. was-noise/
   attached, forced). Reuse the #008 Database lock; a forward-only migration for
   the nodes/members/coords tables as needed.

Baked constants (from clustering-lifecycle.md; NOT config): UMAP 25-dim,
min_cluster_size 5, leaf selection, fixed seed, alpha 0.5 (via #039). Runs as a
job over a tree scope; heavy compute runs OUTSIDE the DB lock (load vectors under
lock -> release -> UMAP/HDBSCAN -> re-acquire to persist), like #035.

## Acceptance criteria
- [ ] `cluster` over a tree's embedded sections reduces the combined vectors to
      25 dims (UMAP, cosine, fixed seed) and produces bottom-level clusters via
      HDBSCAN (min_cluster_size=5, euclidean, leaf); the run is deterministic for
      the same input + seed.
- [ ] Every section ends up a member of exactly one bottom-level topic: HDBSCAN
      noise points are attached to their nearest cluster in the ORIGINAL combined
      space, and flagged as attached.
- [ ] Members, per-section reduced coords, and flags are persisted; a warm-init
      hook (init = stored coords) exists for later incremental settle (#T39).
- [ ] The op is registered and runs as a job over a tree scope; heavy compute
      runs outside the #008 Database lock; a failing run fails its leaf cleanly.
- [ ] Baked constants (UMAP-25 / min_cluster_size 5 / leaf / seed / alpha 0.5)
      are NOT config knobs.
- [ ] Regression-grade tests use a KNOWN-GROUP fixture (synthetic vectors with
      planted clusters) asserting the planted groups are recovered and every
      point is assigned (noise attached); deterministic under the fixed seed.
      (The broader known-group + coverage harness is #T19.)
- [ ] `ruff format`, `ruff check --fix`, `pytest` all clean; work committed.

## Out of scope
- Upper-level recursion (embed briefs -> cluster next level) - that is the brief
  step + recursion (M4).
- Incremental placement / sticky re-check / incubator / settle (M7, T33-T39) -
  this is the empty-tree FULL build only.
- Brief generation (M4) and export (M6).
- The full known-group + coverage TEST HARNESS (#T19 / a separate ticket).

## Review log
- 2026-08-16 PO: authored as T18 on the #039 combined vectors. Recipe + constants
  are SETTLED in clustering-lifecycle.md / how-hrono-works.md - bake them. Full
  build only (incremental is M7). Sized `big` (UMAP + HDBSCAN + noise attach +
  persist + migration); T18.1-4 can split into commits. Flagged the warm-init
  seam for #T39 and heavy-compute-outside-the-lock.
- 2026-08-22 dev: started. Confirmed the settled recipe (UMAP-25 cosine seed 42
  -> HDBSCAN leaf min_cluster_size 5 -> attach in original combined space) and
  verified it recovers planted clusters deterministically before coding.
- 2026-08-22 dev: DONE, committed 77249c3, handoff to qa. Implemented as the
  `cluster` op over a tree (`job.tree`, default "default"):
  - `cluster/build.py` — pure pipeline, all constants baked (UMAP_DIMS=25,
    cosine, seed 42; HDBSCAN min_cluster_size=5, euclidean, leaf). `init` seam
    wired for warm-start (#T39); `reduce`/`cluster` seams for offline tests.
    Noise (-1) attaches to nearest density-core member by dot in the ORIGINAL
    combined space; `attached` flag + `assignment_similarity` per member; all-
    noise / empty-input fail cleanly with ClusterError.
  - `cluster/store.py` — `section_combined_vectors` blends stored components
    (#039); `stored_coords` for warm-init (None unless every section has one);
    `replace_tree` clears + rebuilds a tree level (nodes/members/coords). Kept
    numpy-free so it imports without the extra.
  - `cluster/op.py` — loads combined vectors + warm-init coords UNDER the #008
    lock, runs the heavy build OUTSIDE it, re-acquires to persist (like #035);
    `build` imported lazily so `import`/registration works without the extra and
    a missing extra fails cleanly. Registered into OPS + app.py startup.
  - migration 0009_nodes.sql: nodes / node_members (attached + similarity) /
    section_coords (25-d blob).
  - Shared the embedding-model resolver into `embed/model.py` (embed + cluster
    read/write under the same model — prevents drift).
  - BLOCKING FIX (in scope, no combined vectors without it): wired
    `register_path_bodies` into the split op so section paths are stored as
    content bodies and the existing embed op vectorises them. Idempotent; split
    content-count tests still pass.
  - deps: umap-learn/hdbscan/numpy as an opt-in `[cluster]` extra (mirrors #038
    `embed`), plus in the dev group so the gate runs the REAL recipe.
  Verified: gate clean (ruff format/check, pytest 388 passed / 1 pre-existing
  skip). Known-group test recovers 5 planted groups, full coverage, deterministic
  labels+coords under the seed; attach rule tested in combined space; warm-init
  seam asserted (first build init None, rebuild inits from stored coords); op
  runs as a job with failure isolation. Drove the REAL op end-to-end (48
  sections, 4 planted topics) -> 4 nodes, every section in exactly one node, all
  coords 25-d.
  Flagged for PO: (1) "tree" is a job-level name today (no trees table / no
  section->tree mapping yet) — the op clusters ALL embedded sections into
  `job.tree`; revisit if multi-tree lands. (2) `forced` flag deferred (an M7
  incremental concept; not produced by a full build).
- 2026-08-22 qa: FAIL -> back to todo. The gate is NOT clean: `uv run pytest`
  intermittently crashes the interpreter with a SIGSEGV (reproduced ~1 run in 6;
  dev's single green run was luck). Root cause is a use-after-free the ticket's
  own tests introduce, not a flaky library:
  - `tests/cluster/test_op.py` line 213-216 (`test_failing_run_fails_its_leaf_
    cleanly`) and line 183-187 (`test_runs_as_a_job_and_persists`) call
    `worker.stop()` but never `worker.join()`. `Worker.stop()`
    (`src/hrono/jobs/worker.py:67`) only sets the stop Event; the daemon thread
    can still be inside `_claim` -> `store.claim_next` (`jobs/store.py:73`)
    running a SQLite query when the test then calls `database.close()`
    (`test_op.py:216`) / reads the DB. Closing the connection out from under the
    live query in the worker thread frees the sqlite3 handle mid-use -> segfault.
    Fault handler confirms: main thread at `database.py:53 close` <- `test_op.py:
    216`, worker thread at `store.py:73 claim_next` <- `worker.py:72 _claim`.
  - Fix: after `worker.stop()`, add `worker.join(timeout=5)` before closing or
    reading the DB in BOTH tests, matching the established pattern used by every
    other worker test (`tests/jobs/test_scope.py:51`, `tests/jobs/test_worker.py:
    44`, `tests/embed/test_op.py:157`, `tests/ingest/test_split_op.py:222`,
    `tests/ingest/test_sync.py:200`). Then re-run `uv run pytest` several times
    (say 10x) to confirm the segfault is gone before handing back.
  Everything else verified and passing: ruff format/check clean; build/store/op
  code is correct and idiomatic (constants baked not config; noise attaches to
  nearest density-core member by dot in the ORIGINAL combined space; empty/all-
  noise fail cleanly with ClusterError; heavy compute runs outside the #008 lock,
  load-under-lock -> release -> compute -> re-acquire-to-persist like #035; warm-
  init seam wired and asserted; migration 0009 nodes/node_members/section_coords
  with proper cascades). The path-body wiring into split_op is consistent
  (`sections.path` == the string registered by `register_path_bodies`, so the
  content-hash lookup matches). Only the two flaky tests block; fix them and the
  ticket passes. (Minor, non-blocking: the working tree carries a pre-existing
  unrelated `.gitignore` edit — not part of commit 77249c3; leave or land it
  separately, keep it out of this ticket's commit.)
- 2026-08-22 dev: FIXED, committed 5389ea3, handoff to qa. Applied qa's fix
  exactly: added `worker.join(timeout=5)` after `worker.stop()` in the `finally`
  of both `test_runs_as_a_job_and_persists` and `test_failing_run_fails_its_leaf_
  cleanly`, so the daemon thread's in-flight `claim_next` completes before the
  test reads / closes the DB — matching every other worker test's teardown. No
  production code changed (the race was test-only). Verified: ruff format/check
  clean; ran `pytest tests/cluster/test_op.py` 10x (7 passed each, no SIGSEGV)
  and the FULL suite 3x (388 passed / 1 skip each, no crash). Left the unrelated
  `.gitignore` edit out of the commit; tree clean but for that pre-existing file.
- 2026-08-22 qa: PASS -> po-review. Re-verified the fix and re-ran the whole
  checklist:
  - Fix commit 5389ea3 is exactly the prescribed change: `worker.join(timeout=5)`
    added after `worker.stop()` in the `finally` of BOTH cluster worker tests, no
    production code touched (the race was test-only). Conventional Commit.
  - Gate now clean and STABLE: I ran `pytest tests/cluster/test_op.py` 15x (0
    segfaults, was ~1-in-6 before) and the full `uv run pytest` twice (388 passed
    / 1 skip, no crash). `ruff format --check` + `ruff check` clean.
  - Drove the REAL op end-to-end (not fake_build): a planted 4-topic / 40-section
    corpus through `cluster_op.cluster` with the real UMAP-25 + HDBSCAN-leaf +
    combined-space attach pipeline -> 4 nodes, all 40 sections members of exactly
    one node (0 duplicate assignments), every coord 25-d, attach flag correct.
  - All other dimensions re-confirmed from the first pass: constants baked (not
    config); noise attaches to nearest density-core member by dot in the ORIGINAL
    combined space; empty/all-noise fail cleanly with ClusterError; heavy compute
    runs outside the #008 lock (load-under-lock -> release -> compute -> re-acquire
    to persist); warm-init seam wired + asserted; migration 0009 cascades correct;
    path-body wiring into split_op consistent.
  Note for PO: the ticket now spans two commits (77249c3 feature + 5389ea3 test
  fix) with 045's commit interleaved in history — expected after a qa bounce, not
  a defect. The pre-existing unrelated `.gitignore` edit remains uncommitted in
  the working tree (out of both commits); leave or land it separately.
- 2026-08-22 PO review: PASS -> done. Independently re-verified the keystone
  rather than trusting the logs. Read build.py/op.py/store.py/migration 0009:
  constants are module-level baked literals (UMAP_DIMS=25, cosine, seed 42;
  MIN_CLUSTER_SIZE=5, euclidean, leaf) with no config path; noise attaches by dot
  in the ORIGINAL combined space (`vectors[noise] @ vectors[core].T`, argmax);
  lock discipline correct (load in first connect() block -> block closes ->
  `builder(...)` runs outside any lock -> second connect() re-acquires to
  persist, like #035); migration cascades sound. Empirical: ran the previously-
  flaky `tests/cluster/test_op.py` 15x -> 0 segfaults (was ~1-in-6); ruff clean;
  full suite 388 passed / 1 skip. Drove the REAL UMAP-25+HDBSCAN-leaf+combined-
  attach pipeline on a planted 4-topic/40-section corpus: labels AND coords
  identical across two runs (deterministic), 4 topics recovered as exactly 4
  labels with each planted group mapping 1:1, every section assigned (label>=0),
  all coords 25-d. All 7 acceptance criteria truly met.
  Accepted dev's two scope flags: (1) `forced` flag is an M7 concept, correctly
  out of scope; (2) `tree` is a job-level string with no sections->tree mapping,
  so the op clusters ALL embedded sections into one tree today — a real
  limitation but out of this ticket's scope (multi-tree/M8, upper recursion/M4).
  Did NOT stuff it into 040 (which met its own criteria); spun off #054 to
  capture it for when multi-source/multi-tree lands. Closed. M3 build path (T18)
  complete; #041 (T19 harness) is now unblocked.
