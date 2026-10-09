---
id: 095
title: Wire the incubator — nothing calls drain or age, so parked chunks are stranded for ever
priority: blocker
size: medium
depends_on: [094]
spec_refs: [build-order.md#T35.2, build-order.md#T35.3, build-order.md#T35.4]
found_by: e2e manual QA 2026-09-03 — .e2e/FINDINGS.md F29
---

## Context
```
$ grep -rn "incubator" src/ | grep -v incubator.py
src/hrono/cluster/placement.py:29:from hrono.cluster import incubator, store
src/hrono/cluster/placement.py:172:    incubator.park(conn, tree, content_hash, path, batch)
```
`park` is the only production caller. `drain` (T35.2/35.3) and `age` (T35.4)
exist and are unit-tested but are invoked by nothing.

## Description
Observed after the e2e M7 scenarios: two chunks parked and permanently
invisible to the tree.

```
pending: [('docs/unrelated-cooking-notes.md', batch 1),
          ('source/util-helpers.js',          batch 4)]
tree_batch: batch 8
```

A parked chunk is in no node, so it appears in no brief, no upper level and no
export — it is silently missing from the knowledge base (recall can still hit
its raw passages, so the corpus and the map disagree). One of the two was a
working member of node 2 until a rename ejected it (see 100).

Work:
- Call `drain` at the end of `update` (after placement) and/or from `settle`.
- Call `age` on every update run so an aged chunk is force-assigned.
- Decide and document where in the chain each belongs, and record drain/age
  outcomes in `update_log` so the dashboard can show them.
- Expose the pool: a count in the tree/export view, or a `pending` API, so
  stranded chunks are visible.

## Decision (2026-09-12, dev — technical call, no PO input needed)

Wire it into `update`, at the end of `_update_source`'s placement phase, in this
order: `age(...)` first (force-assign anything past `MAX_AGE`), then
`drain(...)` (emit density cores, force-assign the residual). Call `drain` again
from `settle`, since a reconcile is the natural moment to re-home strays.
Record every drain/age outcome in `update_log` with the same shape `propagate`
uses, so the pool's history is auditable.
`drain`'s own gate must match what the clusterer can actually handle (094).

## Acceptance criteria
- [x] After an `update` that parks chunks, a subsequent update/settle drains the
      pool into real clusters (or force-assigns aged chunks) with no manual step.
- [x] Invariant test: every section is in exactly one node OR pending, and no
      section stays pending beyond `MAX_AGE` batches.
- [x] `ruff format`, `ruff check --fix`, `pytest` clean.

## Review log
- 2026-09-14 dev: started; moved to in-progress.
- 2026-09-14 dev: implemented and committed as `8c7ab01`.
  Wiring, per the Decision block: `_update_source` now calls
  `incubator.age(...)` then `incubator.drain(...)` inside the same write lock
  that persists placement, and `settle` drains at the end of its warm
  reconcile. Two supporting changes were needed to make the invariant real:
  (1) `age`'s gate is now the DRAINABLE pool size (`_ready`, i.e. pending
  chunks that actually have a combined vector) instead of the raw row count —
  otherwise a pool of >= MIN_POINTS unembeddable rows blocked ageing for ever
  while never draining, the exact stranding this ticket forbids; #094's
  invariant (a 5-11 chunk pool still ages out) is preserved.
  (2) new `incubator.sweep(conn, tree)`, called by the `cluster` op right after
  `replace_tree`: a full rebuild homes every embedded section, so the pool rows
  it obsoletes must be retired or the chunk is "clustered AND pending" — which
  is precisely the state the real e2e database is in.
  Audit: drain/age outcomes are written to `update_log` via a new single writer
  `hrono/db/update_log.py` (`drain/core`, `drain/forced`, `age/forced`);
  `propagate` now uses the same writer, so the shape cannot drift.
  Pool exposure: `GET /trees/{name}/pending` (reader role) and
  `hrono tree pending <name>`.
  Tests (13 new, 639 total): `tests/cluster/invariant.py::assert_pool_invariant`
  is the invariant — every corpus section in exactly one level-0 node XOR
  pending, and nothing pending for more than `MAX_AGE` batches — asserted after
  every batch of the update-flow tests and after settle;
  `test_update_parks_an_alien_chunk_then_ages_it_in` drives the real `update`
  op over a git repo for six batches and proves the parked chunk is
  force-assigned rather than stranded; `test_update_drains_a_full_pool_in_the_
  same_batch`; `test_the_real_mini_pipeline_drains_a_planted_pool` runs drain
  with NO `core_labeler` seam (real UMAP -> HDBSCAN, two planted groups -> two
  new leaf nodes), the real-backend test #108's rule asks for;
  `test_age_empties_a_pool_the_clusterer_can_never_reduce` pins the new gate;
  sweep, update_log, route and CLI tests. Each wiring call was verified
  regression-grade by removing it and watching the matching test fail.
  Real-corpus verification (on COPIES in scratch; `.e2e/` untouched): the
  original database's two pool rows are both "in a node AND pending" — the
  `cluster`/settle sweep retires both, invariant clean. Reproducing F29's
  reported state (memberships deleted, so genuinely in no node) and running two
  update batches at batch 9 and 10: `docs/unrelated-cooking-notes.md` ->
  node 8 (forced, sim 0.281) and `source/util-helpers.js` -> node 2 (forced,
  sim 0.464 — back into the very node the rename ejected it from), pool empty,
  two `age/forced` rows in `update_log`.
  Gate clean: `ruff format` (221 files unchanged), `ruff check --fix` (all
  checks passed), `pytest` 639 passed. Handing off to verifying.
- 2026-09-14 qa: **FAIL — back to todo.** The wiring itself is right and
  regression-grade; the defect is that the pool is keyed by CONTENT HASH while
  membership is keyed by SECTION, so the invariant this ticket delivers is
  false for a production-reachable corpus, and the new `sweep` can strand a
  chunk worse than F29.

  What I verified as PASSING (so it need not be redone):
  - Gate re-run by me on `8c7ab01`: `ruff format --check` 221 files unchanged,
    `ruff check` clean, `pytest` **639 passed** in 33.9s.
  - Wiring is where the Decision block says and is regression-grade. I removed
    each call and watched the matching test fail:
    `update.py:91` (`age`) -> `test_update_parks_an_alien_chunk_then_ages_it_in`
    fails; `update.py:92` (`drain`) ->
    `test_update_drains_a_full_pool_in_the_same_batch` fails;
    `cluster/op.py:60` (`sweep`) ->
    `test_settle_retires_a_pool_row_its_rebuild_has_re_homed` fails;
    `settle.py:74` (`drain`) ->
    `test_settle_drains_chunks_its_own_embed_pass_made_placeable` fails.
  - `assert_pool_invariant` is real, not theatre. I drove all four violation
    classes against it and each raises with the right message: in no node, in 2
    nodes, clustered AND pending, pending past `MAX_AGE`.
  - Real-corpus claims reproduced INDEPENDENTLY on my own copy of
    `.e2e/run/.hrono/hrono.db` (`.e2e/` untouched, read-only): both pool rows
    are indeed already "in a node AND pending" (94/94 corpus sections homed, 0
    multi-homed); `sweep` retires exactly 2 and leaves no homeless section;
    replaying F29's genuinely-stranded state (memberships deleted) and running
    `age` at batches 9 and 10 gives `docs/unrelated-cooking-notes.md` -> node 8
    (forced, sim 0.2805) and `source/util-helpers.js` -> node 2 (forced, sim
    0.4641), pool empty, two `age/forced` rows in `update_log`. Dev's numbers
    are exact.
  - Pool exposure driven for real, not just unit-tested: `hrono serve` on a
    copy of the e2e database, `GET /trees/default/pending` -> 401 unauth, 401
    on a bad token, and the two real rows with a valid token; unknown tree is a
    clean `{"count":0,"pending":[]}`; `hrono tree pending default` through a
    profile printed both paths and the count.
  - `propagate`'s move onto `db/update_log.py:record` changed nothing: argument
    order and `created_at` are identical to the removed `_log`/`_now`, and
    `tests/summarize/test_propagate.py:203,224` still pin verdict/action/
    climbed_to/drift. #110 is neither addressed nor swallowed.
  - #108's rule is honoured: `test_the_real_mini_pipeline_drains_a_planted_pool`
    runs drain with no `core_labeler`, real UMAP -> HDBSCAN, two planted groups
    -> two leaf nodes.
  - Commit is a clean Conventional Commit, atomic, no stray files. The one
    uncommitted `.gitignore` line is pre-existing and not dev's.

  **Blocking defect — the pool is hash-keyed, membership is section-keyed.**
  `pending`'s primary key is `(tree, content_hash)` (`0017_incubator.sql`), but
  a node member is a `sections.id`. Two sections with identical content at
  different paths share one hash and get DIFFERENT combined vectors (the path
  blend, ALPHA 0.5), so one can clear TAU while its twin parks. Driven through
  the REAL `update` op over a git repo, no hand-built DB state: two files with
  the same body, `g9.txt` and `alien/g9.txt`, one update batch, and
  `assert_pool_invariant` raises `g9.txt is clustered AND pending`. Acceptance
  criterion 2 therefore does not hold.

  Three concrete consequences, worst first:
  1. `incubator.py:157-171` — `sweep` deletes the pool row when ANY section
     with that hash is homed. In the twin case where one twin is homed and the
     other is not, the parked twin ends up in NO node and in NO pool: invisible
     to the tree AND invisible to the new `pending` endpoint, strictly worse
     than F29. I reproduced that end state directly: `sweep` returns 1 and the
     twin section is left with zero memberships and no pending row. Minimum
     fix: only retire a hash whose sections are ALL homed (`NOT EXISTS` an
     unhomed section for that hash), so the pool row survives while any twin is
     still homeless.
  2. `incubator.py:185-207` + `_section_ids` at `209` — `_force_assign`
     attaches EVERY section sharing the hash to the chosen node, so forcing a
     parked twin drags its already-homed twin into a SECOND level-0 node. Driven
     with the real primitives: `assert_pool_invariant` raises `is in 2 nodes`.
     Force-assign (and drain's core emission) must skip a section that already
     has a level-0 membership in this tree.
  3. `placement.assign_or_park` parks by hash without checking whether another
     section of that hash is already homed, which is what creates the "both"
     state every batch. Guarding there (or unparking on join) closes it at the
     source.

  Other findings to fix in the same pass (not separately ticketed, they are all
  in code this commit wrote):
  4. `incubator.py:195` — `_force_assign` returns None when `centroids` is
     empty, so on a tree with no level-0 node `age` can never rescue anything:
     I ran 38 consecutive batches and the chunk was still pending, with the
     invariant's `MAX_AGE` bound violated the whole way. This overlaps #112 but
     must at least be stated as a known bound in the docstring rather than
     reading as "nothing waits forever".
  5. `tests/cluster/test_incubator.py:271-275` — `test_age_empties_a_pool_the_
     clusterer_can_never_reduce` ASSERTS that rows with no usable vector stay
     pending after ageing at batch 10 (parked at batch 1, so 9 > MAX_AGE 5).
     That is a state acceptance criterion 2 forbids, pinned as correct. It is
     not reachable through `placement.assign_or_park` today (a vectorless chunk
     is skipped, never parked), but it becomes reachable the moment the default
     embedding model changes. Either bound it explicitly or assert the
     invariant alongside it.
  6. `settle.py:62-74` — the closing `drain` runs AFTER `brief` and
     `build_tree`, so a drain that emits a new leaf node ends settle with a node
     that has no brief and no parent, and settle then resets drift so nothing
     re-triggers. Drain before the brief pass (or right after `cluster`).
  7. `update.py:92` and `settle.py:74` — `drain` runs the real UMAP -> HDBSCAN
     INSIDE the `database.write()` lock, contradicting the lock discipline both
     module docstrings state ("heavy compute runs outside the lock"). Bounded by
     pool size rather than corpus size, but it is the stated convention.
  8. Nit: `tree/commands.py:77` prints "1 pending chunks".

  On the forced-assignment question specifically: the `forced` flag IS written
  (`node_members.forced = 1`, confirmed on the real corpus for both rescued
  chunks), but it is COSMETIC — `grep -rn "forced" src/` shows writes only, no
  reader. `monitor._misfits` decides misfit as `best_other > own`, and a
  force-assigned chunk sits at its NEAREST centroid by construction, so it is
  never a misfit and `repair.migrate` never moves it. The 0.281 cooking-notes
  chunk will sit in node 8 and pollute its brief indefinitely. That is #086/#089
  scope, not this ticket's acceptance criteria, so I filed it as backlog #113
  rather than blocking on it.
- 2026-09-14 dev: **re-picked up after qa's FAIL**; fixed on top of `8c7ab01`,
  committed as `8668c5f`. Nothing qa passed was reverted.

  **Blocking defect — chose to RE-KEY the pool, not patch the callers.**
  New migration `0022_pending_by_section.sql`: `pending` is now
  `(tree, section_id)` with `REFERENCES sections(id) ON DELETE CASCADE`, and
  `path`/`content_hash` are read from `sections` instead of copied. Reasoning,
  as asked: the minimum patch qa sketched (a `NOT EXISTS` guard in `sweep`, a
  homed-section skip in `_force_assign`) makes the two symptoms go away but
  leaves the pool structurally unable to say what it is for — the primary key
  is `(tree, content_hash)` and the row carries ONE `path`, so a second `park`
  of the same hash overwrites the first twin's path and the table cannot
  represent two parked twins at all. Every guard would have been a workaround
  for a key that is coarser than the membership it complements; the pool is the
  complement of `node_members`, and `node_members` is per section. Keyed by
  section, `sweep` and `_force_assign` need no special cases (each acts on one
  section), the FK cascade retires the row of a deleted section for free, and
  the invariant is expressible per chunk. Cost is one forward-only migration
  over a table nothing outside the incubator reads. Carried rows are mapped
  `(content_hash, path) -> sections.id`, and rows whose section is already
  homed are dropped — on the real e2e database that retires exactly the two
  "clustered AND pending" rows on migrate, no further action needed.
  Follow-on guards in the same spirit: `assign_or_park` now UNPARKS on join
  (closes the "both" state at the source, qa's point 3), and `park` is
  `ON CONFLICT DO NOTHING` so a re-park keeps the ORIGINAL wait instead of
  resetting the age clock.

  The other four:
  1. `settle` reordered to cluster -> embed -> drain -> brief -> build_tree ->
     embed (the closing embed still vectorises the node:// brief passages, as
     `maintain` does). A leaf node the drain emits is now briefed in the same
     settle. NOTE: it is still not PARENTED — `build_tree` starts at the
     highest BRIEFED level, sees one root and stops, so nothing re-parents a
     leaf born after the recursion. That is `build_tree`'s incremental gap, not
     the ordering's, and it is identical on the `update` path; filed as backlog
     **#114** rather than swallowed. The test asserts the half this fix owns.
  2. Lock discipline: `drain` now takes a `Database`, not a connection — reads
     the pool under the read door, runs UMAP -> HDBSCAN off the lock,
     re-acquires to persist (the shape `cluster`/`embed` use). `update` calls it
     after its placement transaction closes; `settle` calls it between ops.
     `age` (dot products only) stays inside placement's transaction.
  3. `tree pending` pluralises: "1 pending chunk" / "2 pending chunks".
  4. The `_force_assign`-returns-None question: made the wording honest rather
     than pretending it cannot happen. `_force_assign`'s docstring now states
     the bound explicitly (no vector, or no level-0 node to fall back on = not
     placeable by any means the incubator has), the module docstring's "never
     pending beyond MAX_AGE" is qualified with "once it is PLACEABLE", and
     `assert_pool_invariant` takes the embedding model and applies the TIME
     bound only to placeable rows — the XOR half still applies to every section
     unconditionally. `test_age_empties_a_pool_the_clusterer_can_never_reduce`
     now asserts the invariant alongside its stranded rows, so the two can no
     longer contradict each other. #112's empty-tree case is untouched.

  Tests (6 new, 645 total), each verified regression-grade against `8c7ab01` in
  a throwaway worktree:
  - `test_update_parks_only_the_twin_that_fits_nowhere` — qa's exact
    reproduction through the REAL `update` op over a git repo: `g9.txt` and
    `alien/g9.txt` with the same body, one batch. On `8c7ab01` it raises
    `AssertionError: g9.txt is clustered AND pending`; on `8668c5f` it passes,
    and seven further batches age the parked twin in while its homed twin never
    moves (`_forced_node("g9.txt") is None`).
  - `test_sweep_keeps_the_row_of_a_twin_the_rebuild_did_not_home` — old code
    `sweep` returns 1 and strands the twin in no node and no pool; new returns 0.
  - `test_ageing_forces_only_the_parked_twin` — the parked twin's nearest
    centroid is a node its homed twin is NOT in, so old code writes
    `[(2, 2), (2, 3)]` (qa's "is in 2 nodes"); new writes `[(2, 3)]`.
  - `test_drain_labels_the_pool_off_the_write_lock` — a `core_labeler` that
    takes `database.write()` from another thread; fails if the labeller is moved
    back inside the lock (verified by moving it).
  - `test_a_leaf_node_the_settle_drain_emits_is_briefed` — with the old order
    the emitted nodes 5, 6 have no brief (`{5, 6} <= {1, 2, 3, 4}` fails).
  - `test_pending_pluralises_a_bigger_pool`.

  Real-corpus verification, on COPIES in scratch (`.e2e/` untouched, read-only):
  migrating the original database applies `0022` and retires both pool rows;
  94/94 corpus sections homed, 0 homeless, 0 multi-homed, pool empty. Replaying
  F29's genuinely-stranded state (memberships deleted, sections 192 and 196
  parked at batches 1 and 4) and ageing at batches 9 and 10 reproduces the
  earlier numbers exactly: `docs/unrelated-cooking-notes.md` -> node 8 (forced,
  sim 0.2805), `source/util-helpers.js` -> node 2 (forced, sim 0.4641), pool
  empty, two `age/forced` rows, `assert_pool_invariant` clean. Real HTTP surface
  driven too: `hrono serve` on a copy, `GET /trees/default/pending` -> 401
  unauth, 401 on a bad token, both rows (now carrying `section_id`) with the
  admin token, `{"count":0,"pending":[]}` for an unknown tree; `hrono tree
  pending default` through a profile printed both paths then, with one row
  removed, "1 pending chunk in tree 'default'."

  Untouched as instructed: #113 (the `forced` flag has no reader), #100, #101,
  #110, #112, and the pre-existing uncommitted `.gitignore` line.
  Gate clean: `ruff format` (221 files unchanged), `ruff check --fix` (all
  checks passed), `pytest` **645 passed**. Handing back to verifying.
- 2026-09-14 qa: **FAIL — back to todo.** One blocking finding, and it is a
  single false sentence, not a structural problem: everything the last
  rejection asked for is genuinely fixed and I proved each fix myself.

  **What I verified as PASSING on `8668c5f` (need not be redone):**
  - Gate re-run by me: `ruff format --check` 221 files unchanged, `ruff check`
    clean, `pytest` **645 passed** in 38.7s.
  - **Migration `0022` against the real database.** On COPIES of
    `.e2e/run/.hrono/hrono.db` (`.e2e/` never touched; it is at version 20, so
    0021+0022 both apply). Pre-migration the two pool rows map to sections 192
    and 196 and BOTH are already homed, and 0 corpus sections are homeless — so
    the `NOT EXISTS` clause drops exactly those two and loses nothing. Post:
    pool empty, 94/94 corpus sections homed, 0 homeless, 0 multi-homed,
    `PRAGMA foreign_key_check` empty, `integrity_check` ok, re-running
    `migrate` applies nothing. Edge cases driven on further copies: a pool row
    whose `(content_hash, path)` maps to NO section is dropped (correct — the
    old `_force_assign` could not have homed it either, `_section_ids` returned
    `[]`); a genuinely-homeless parked section carries across with its `batch`
    intact and the invariant holds; an empty pool migrates cleanly. The
    `(content_hash, path) -> sections.id` join can fan out to several sections,
    which is conservative-correct: only sections that are still homeless can
    survive the `NOT EXISTS`, and parking each of them is what the new
    invariant requires.
  - **The re-key closes the defect, driven through the real `update` op.** My
    own scenario, not dev's test: the SAME body at THREE paths (`t9.txt`,
    `alien/t9.txt`, `alien/deep/t9.txt`) — one content hash, three sections, a
    shape the old table structurally could not hold. Batch 1: `t9.txt` homes,
    the other two park INDEPENDENTLY, invariant clean; invariant clean at every
    one of batches 2-8; by batch 7 the pool is empty and each of the three is
    in exactly ONE node. Also drove two cases dev did not: deleting a parked
    twin from the repo retires its pool row through the FK cascade (pool -> []),
    and renaming a parked twin cascades the old row and parks the new section.
  - **Regression-grade, checked by mutating `8668c5f` in a worktree (with
    `PYTHONPATH` asserted inside it) and watching the matching test go red:**
    `sweep` back to a hash-keyed delete -> `test_sweep_keeps_the_row_of_a_twin_
    the_rebuild_did_not_home` fails; `_force_assign` fanned back out over every
    section sharing the hash -> `test_ageing_forces_only_the_parked_twin`
    fails; settle's drain moved back after `build_tree` ->
    `test_a_leaf_node_the_settle_drain_emits_is_briefed` fails; the labeller
    moved back inside `database.write()` ->
    `test_drain_labels_the_pool_off_the_write_lock` fails.
  - **Real-corpus numbers reproduced exactly, independently.** Replaying F29
    (memberships for 192/196 deleted, parked at batches 1 and 4) and ageing at
    batches 9 and 10: `docs/unrelated-cooking-notes.md` -> node 8 (forced, sim
    0.2805), `source/util-helpers.js` -> node 2 (forced, sim 0.4641), pool
    empty, two `age/forced` rows in `update_log`. The invariant correctly
    RAISES on the stranded state (`pending 7 batches`) and clears after ageing,
    so the narrowed time bound still has teeth.
  - **Real HTTP + CLI surface driven**, not just unit-tested: `hrono serve` on
    a copy of the e2e database -> `GET /trees/default/pending` 401 unauth, 401
    on a bad token, 200 with both rows now carrying `section_id`,
    `{"count":0,"pending":[]}` for an unknown tree; through a profile,
    `hrono tree pending default` printed both paths + "2 pending chunks", then
    "1 pending chunk" at one row and "0 pending chunks" at zero. Pluralisation
    fixed.
  - **`park`'s `ON CONFLICT DO NOTHING` cannot keep a stale row.** A content
    change goes through `reconcile`, which does `DELETE FROM sections WHERE
    source = ? AND path = ?` (`ingest/reconcile.py:163`) and re-inserts with a
    NEW id, so the old pool row leaves by FK cascade and the conflict cannot
    fire across a content change. The conflict can only fire for the identical
    section id, whose original wait is the honest one; and a join unparks, so
    the clock resets whenever the chunk is actually homed. Age semantics right.
  - **The narrowed time bound is honest engineering, not a moved goalpost.**
    The XOR half still applies to every corpus section unconditionally; only
    the time bound is conditioned, on a precondition that is a fact about the
    world (`_force_assign` has nothing to force it to). What stops an
    unplaceable row accumulating silently is that it is still in the pool, and
    the pool is now exposed — `GET /trees/{name}/pending` and `hrono tree
    pending` list it with its batch, so it is visible rather than silent. Both
    unplaceable causes are also bounded and ticketed: "no vector" is
    unreachable through `assign_or_park` today (`placement.py:169` returns
    "skipped" before parking), and the empty-tree case is #112.
  - Commit `8668c5f` is a clean Conventional Commit, atomic, no stray files;
    #113/#100/#101/#110/#112 untouched; the uncommitted `.gitignore` line is
    still pre-existing and not dev's.

  **Blocking defect — `src/hrono/tree/settle.py:28-29` states something the
  code does not do.** The module docstring says the drain's new position means
  "a leaf node the drain emits is briefed and parented in this same settle
  rather than left dangling until the next trigger". The parenting half is
  false, and dev's own review-log entry above and backlog #114 say so. I drove
  a forced `settle` whose drain emitted leaves 5 and 6:

  ```
  levels       [(0, 5), (1, 1)]
  node_children [(4, 1), (4, 2), (4, 3)]
  emitted briefed  True
  emitted parented []
  ```

  `export/store.py:46` picks the highest-level node as the root and descends
  `node_children`, so nodes 5 and 6 — and the chunks in them — are still
  absent from `hrono tree export`, which is one of the three harms this
  ticket's Description names. Shipping a docstring that asserts the gap is
  closed is how #114 gets lost, and it is the one claim a reader of `settle.py`
  will take on trust. Fix: say what is true — the drain runs before `brief` so
  the emitted leaf is BRIEFED in the same settle; it is not parented, because
  `build_tree` starts at the highest briefed level and never revisits level 0
  (#114). One sentence; that is the whole blocking list.

  **On #114's split itself: I accept the deferral.** A chunk that drains into a
  new leaf goes from "in no node at all" to "in a briefed level-0 node" —
  strictly better, and the ticket's acceptance criteria are pool-scoped and
  both hold. Re-parenting a leaf born after the recursion is `build_tree`'s
  decision (attach-to-nearest vs re-cluster level 1), correctly a separate
  ticket. One fact to fold into #114's Context while you are there, because it
  changes its priority argument: on the **`update`** path the emitted leaf gets
  no brief either (update never briefs) AND leaves the pending pool, so those
  chunks are momentarily LESS visible operationally than they were while
  parked — no brief, no export, no `pending` row. That is an argument for #114
  being medium-high, not medium.

  **Non-blocking observations (do not redo work for these):**
  - The drain's read-compute-write window can double-home a section if the pool
    changes in between — I drove it with a `core_labeler` that homes a pending
    section mid-run and got `homes: [1, 2]`. Not reachable: `db/lock.py` gives
    one process the file and `jobs/worker.py` runs one job at a time, and
    `cluster/op.py:40-61` already has the identical window, so the mitigation
    belongs to the shape and not to this call site. Filed as backlog **#115**.
  - Two new guards have no test and are currently unreachable through any
    production caller: `placement.py:173` (unpark on join — both callers of
    `assign_or_park` only ever pass already-homed or never-parked sections, and
    removing the line leaves all 645 tests green) and `park`'s `ON CONFLICT DO
    NOTHING`. They are defensive, they are what I asked for, and they are
    correct; just be aware they are unpinned.
  - Nit: the commit subject is 91 characters. The surrounding history sits at
    72-80.
- 2026-09-14 dev: **re-picked up after qa's second FAIL**; fixed as `18bb2b2`
  on top of `8668c5f`. Nothing qa passed was reverted; `8c7ab01` and `8668c5f`
  stand untouched.

  **Blocking defect — the docstring now says what the code does.**
  `tree/settle.py:26-34`: the drain's position is fixed by what it needs and
  what it produces — AFTER the embed pass, and BEFORE `brief`, so an emitted
  leaf is BRIEFED in this same settle. The "and parented" half is gone,
  replaced by the truth and its cause: it is NOT parented, because `build_tree`
  starts at the highest briefed level and never revisits level 0, so a leaf
  born after the recursion hangs under no parent and stays out of `export`
  (backlog #114). No behaviour change.

  **It warranted a test, and the test is the point.** A docstring cannot be
  asserted, but the behaviour it claims can — and that is exactly how this
  drifted. `test_a_leaf_node_the_settle_drain_emits_is_briefed` is renamed
  `..._is_briefed_not_parented` and now asserts both halves: `emitted <=
  _briefed`, and `emitted.isdisjoint(_parented)` with a preceding
  `assert parented` so the disjointness cannot pass vacuously. Verified it has
  teeth by simulating #114's fix (parenting every parentless level-0 node under
  the root after `build_tree`) — the test goes red, so whoever lands #114 is
  forced back to this docstring. That is the tripwire qa's finding asks for.

  **The two non-blocking notes — both ADDRESSED, not left.** They were
  defensive guards with no test, and an untested guard is the same class of
  problem as an untested docstring claim: it dies silently in a refactor.
  Pinned at the seam, since no production caller reaches them:
  - `tests/cluster/test_placement.py::test_a_parked_chunk_that_joins_is_unparked`
    calls `placement.assign_or_park` directly on a parked section that clears
    TAU. Deleting `placement.py:173` makes it fail (verified).
  - `tests/cluster/test_incubator.py::test_a_re_park_keeps_the_original_wait`
    parks the same section at batch 1 then batch 7 and asserts the stored batch
    is still 1. Turning `ON CONFLICT DO NOTHING` into `DO UPDATE SET batch`
    makes it fail (verified); a plain INSERT would raise.
  The commit-subject nit is CONSCIOUSLY LEFT for `8668c5f` — rewriting a commit
  qa verified by hash would invalidate that verification for no gain. This
  commit's subject is 69 chars, inside the 72-80 the history runs at.

  **#114 updated as asked** (`backlog/114-...md`): its Description now carries
  the `update`-path fact — `tree/update.py` runs placement, age and drain with
  NO `brief` pass, so a leaf `update`'s drain emits has no brief either AND its
  chunks have left the pending pool, making them momentarily LESS visible than
  while parked (a table in the ticket contrasts the two states: the parked
  chunk is at least listed by `GET /trees/{name}/pending`, the drained one is
  in no brief, no export and no pending listing until the next `brief`/settle
  pass). My view on priority: qa is right, that is a silent-missing window
  rather than a visible-waiting one, which is the failure mode #095 exists to
  close — raised `medium` -> `high` in the ticket and in `board.md`, PO owns
  the final call.

  Untouched as instructed: #113, #115, #100, #101, #110, #112, the rest of
  #114, and the pre-existing uncommitted `.gitignore` line (not in the commit).
  Gate clean: `ruff format` (221 files unchanged), `ruff check --fix` (all
  checks passed), `pytest` **647 passed** (645 + 2 new guard tests; the settle
  test was strengthened, not added). Handing back to verifying.
- 2026-09-14 qa: **PASS — to po-review.** `18bb2b2` fixes the one blocking
  finding and nothing else regressed. The only source change since `8668c5f` is
  `src/hrono/tree/settle.py`'s docstring (8 insertions, 5 deletions); the two
  commits I verified across the previous passes are untouched by hash, so
  everything I already confirmed still stands and I did not re-litigate it.

  **The docstring is now true.** It says the drain sits after the embed pass and
  BEFORE `brief`, so an emitted leaf is briefed in this settle, and then states
  the gap outright: "It is NOT parented: `build_tree` starts at the highest
  briefed level and never revisits level 0, so a leaf born after the recursion
  hangs under no parent and stays out of `export` (backlog #114)." Every clause
  matches what I measured last tick on this exact scenario — emitted {5, 6},
  `node_children` [(4,1),(4,2),(4,3)], briefed True, parented [], and
  `export/store.py:46` roots at the top node and descends `node_children` so
  they are unreachable. No overclaim left.

  **The test has teeth, and I confirmed dev's claim by driving it.** In a
  worktree at `18bb2b2` (`PYTHONPATH` asserted inside it) I simulated #114's
  attach-only fix — after `build_tree`, parent every parentless level-0 node
  under the tree's top node — and
  `test_a_leaf_node_the_settle_drain_emits_is_briefed_not_parented` fails on
  the right line:

  ```
  >       assert emitted.isdisjoint(parented)
  E       assert False
  E        + where False = {1, 2, 3, 5, 6}.isdisjoint... where {5, 6}.isdisjoint
  ```

  So landing #114 does force a return to this docstring, which is the whole
  argument for the test. The disjointness is also non-vacuous: the preceding
  `assert parented` holds on the unmutated run ({1, 2, 3} hang under the root),
  so it is not passing against an empty set.

  **Both previously-unpinned guards now fail when removed**, checked the same
  way: deleting `placement.py:173` (`incubator.unpark` on join) ->
  `tests/cluster/test_placement.py::test_a_parked_chunk_that_joins_is_unparked`
  fails `assert 1 == 0`; turning `park`'s `ON CONFLICT DO NOTHING` into
  `DO UPDATE SET batch = excluded.batch` ->
  `tests/cluster/test_incubator.py::test_a_re_park_keeps_the_original_wait`
  fails `assert 7 == 1`. Both tests are honest about pinning behaviour no
  production caller reaches today, which is the right way to keep a defensive
  guard from rotting.

  **#114** carries the fact I asked for (an update-drained leaf has no brief AND
  has left the pending pool, so it is briefly less visible than while parked)
  and dev raised it medium -> high. I agree with the raise; the final call is
  the PO's.

  Commit `18bb2b2` is a clean Conventional Commit ("fix: settle's docstring
  claimed a drained leaf is parented; it is not", 68 chars, lowercase, no body,
  no attribution), atomic, 4 files, no stray changes. The `.gitignore` line is
  still the pre-existing uncommitted one.

  Gate re-run by me on `18bb2b2`: `ruff format --check` 221 files unchanged,
  `ruff check` clean, `pytest` **647 passed** in 37.1s. Worktree removed; tree
  clean. Acceptance criteria 1-3 all hold. Handing to the PO.

  For the PO, the two things this ticket knowingly leaves open, both ticketed
  and neither in its acceptance criteria: **#114** (a drain-emitted leaf is
  briefed but unparented, so its chunks are still outside `export` — I accept
  the deferral because the chunk still moves from "in no node at all" to "in a
  briefed node", strictly better) and **#115** (drain persists a pool snapshot
  read before it took the lock — unreachable under the one-server/one-worker
  invariant, and `cluster/op.py` has the identical window).
- 2026-09-14 PO: **ACCEPTED -> done.** Three commits (8c7ab01 wiring + 8668c5f
  re-key + 18bb2b2 docstring) close F29. Verified independently.

  **Gate re-run by me:** `ruff format --check .` 221 files already formatted;
  `ruff check .` all checks passed; `uv run pytest` **647 passed** in 37s. Tree
  clean apart from the pre-existing `.gitignore` `.e2e/` line.

  **The headline, driven on the real database, not in fixtures.** On a copy of
  `.e2e/run/.hrono/hrono.db` (original untouched; mtime unchanged):
  - Migration applies cleanly, schema 20 -> 22, `pending` re-keyed to
    `(tree, section_id)`.
  - Both of F29's hash-keyed rows are retired, correctly: all 94 corpus
    sections are level-0 members, so both rows were the stale "clustered AND
    pending" half of the invariant. The pool empties and
    `assert_pool_invariant` PASSES over the real corpus.
  - I then built the DISCRIMINATING case the real data could not give me,
    because a migration that drops everything proves nothing: I un-homed
    `docs/unrelated-cooking-notes.md` (deleted its `node_members` row) at
    schema 20 so its pool row was genuinely live, then migrated. The row IS
    carried across (section 192, batch 1) while the already-homed twin is
    dropped. The `WHERE NOT EXISTS` clause discriminates exactly as documented.
  - The invariant then failed on the TIME bound — "pending 7 batches" at
    `tree_batch` 8, `MAX_AGE` 5 — which is F29 itself, and is the state this
    ticket exists to end. Driving `incubator.age(conn, 'default', 'minilm', 8)`
    force-assigned it: **1 chunk rescued, pool 0, section 192 now a member of
    node 8 with `forced=1` and similarity 0.2805**, one `update_log` row
    `(node 8, verdict 'age', action 'forced')` in propagate's shape, and
    `assert_pool_invariant` PASSES. The chunk that was stranded for ever is
    home, and its rescue is auditable.

  **The re-key was the right call, not a patch.** qa's first rejection found a
  genuine data-model error, and the fix is at the model rather than the callers:
  the pool is the complement of `node_members`, membership is per section, so a
  hash-keyed pool was strictly coarser than the thing it complements. Under the
  ALPHA-0.5 path blend two identical bodies at different paths get different
  vectors, so one can clear TAU while its twin parks — and one shared row cannot
  represent both. Re-keying by section makes the invariant expressible per chunk
  and lets `sweep` retire per section, and a deleted section now takes its pool
  row with it via `ON DELETE CASCADE`. `assign_or_park` also unparks on a join,
  closing the "clustered AND pending" half at the source. I am satisfied this is
  the model the spec implies, not a convenience.

  Acceptance criteria: AC1 met (update ages then drains at the end of placement;
  settle drains after the warm reconcile, before `brief`; `cluster` sweeps —
  no manual step anywhere). AC2 met and, more than met, made reusable:
  `tests/cluster/invariant.py` is a shared assertion any lifecycle test can
  make, asserting both halves per section plus the `MAX_AGE` time bound, with
  the unplaceable-chunk precondition stated honestly rather than hidden. AC3
  met.

  **Product surface.** `GET /trees/{name}/pending` is reader-gated, snake_case,
  returns a plain `count` + list (an unbuilt tree is zero, not a 404 — right
  call), and `hrono tree pending <name>` prints path + batch per chunk and a
  pluralised total. The pool is now visible instead of silently absent, which
  was the half of this ticket that was about trust rather than mechanism.
  `db/update_log.py` correctly lifts propagate's private `_log` into one shared
  writer rather than copying it — the dashboard reads one table with one shape.

  **Three commits for one ticket is right here**, not scope creep: two of them
  are qa bounces answered. The third (18bb2b2) is a docstring that *claimed*
  more than the code did — dev fixed the docstring rather than quietly leaving
  the lie, and pinned it with a test that goes red when #114 lands. Correcting a
  comment that overstates behaviour is exactly the discipline I want.

  **Rulings on the three questions qa left me:**
  1. **#114 — priority `high` CONFIRMED, and deferral out of #095 was right.**
     Confirmed on the reasoning dev and qa both give: the chunk moves from
     permanently stranded to homed-and-bounded, which is the promise #095 made,
     and the unparented-leaf problem lives in `build_tree`'s incremental gap —
     a different component needing its own design decision. #095 met its own
     criteria; stuffing this in would have been the anti-pattern. But I weight
     the `update`-path table heavily: a chunk there is in no brief, no export,
     AND no longer in the pending listing, so it is *visibly* waiting no more.
     That is a real, if bounded, trade and it must not sit. I have made the
     design call (attach-only, see the ticket) and promoted it to `todo/` at
     `high` — it should be taken early in the high band, because an unparented
     leaf is a chunk missing from the exported map, and the map is the product.
  2. **#115 — deferral CONFIRMED at `low`, and yes, ONE ticket for the shape.**
     qa is right that it is unreachable: `db/lock.py` gives one process the
     file and the worker runs one job at a time. It is latent, and #095 did not
     create the shape — `cluster/op.py` has the identical read/compute/write
     window and predates it. Hardening an unreachable path now is speculative
     surface. I have broadened its scope to cover BOTH call sites (the fix
     belongs to the shape, as the ticket itself argues) and tagged it for M11
     hardening; it stays in `backlog/`. It becomes real the day we run more than
     one writer, and whoever proposes that owns this ticket as a precondition.
  3. **#113 — RAISED medium -> `high`, and promoted to `todo/`.** I saw the
     0.281 cooking-notes placement myself in the run above, so this is measured,
     not argued. Three reasons it outranks its filed priority. (a) It is an
     unimplemented promise already written into shipped migration
     `0017_incubator.sql`, not new scope. (b) **#095 industrialised the thing
     that produces forced members without wiring the corrective half** — age
     and drain now force-assign on every update, so the rate of sub-TAU
     marriages goes UP as a direct consequence of this ticket. That coupling is
     what moves it. (c) A forced member permanently degrades a brief, and briefs
     are what the entire tree is made of; there is no other mechanism that can
     ever correct a bad placement.
     **On the interaction with #104** (my earlier call: ignore junk at ingest):
     it does NOT subsume this, and I want that recorded so neither ticket is
     closed on the other's account. Ingest filtering is globs, size caps and a
     null-byte sniff — it cannot recognise that a cooking note is off-topic for
     a source-code repo, which is precisely the observed case. #104 reduces the
     junk that arrives; #113 is the only thing that corrects junk once placed.
     Defence in depth, both needed.
