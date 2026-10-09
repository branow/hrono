---
id: 068
title: stable cluster node ids across rebuilds — so briefs survive an unchanged re-cluster (M7 incremental placement)
priority: high
size: big
depends_on: [040, 059, 062, 064]
spec_refs: [build-order.md#M7, clustering-lifecycle.md, how-hrono-works.md, implementation-notes.md]
---

## Context
Surfaced by the #065 (`maintain`) design conflict. hrono's DIFFERENTIATOR is
incremental update — a source change touches only affected nodes, never a full
regeneration. Today that promise BREAKS at the brief layer:
- `cluster` (#040 `replace_tree`) DELETEs all nodes at a level and INSERTs fresh
  ones with new autoincrement ids on every run.
- `briefs.node_id` is `REFERENCES nodes(id) ON DELETE CASCADE`, so re-clustering
  cascade-deletes EVERY brief (and the whole upper tree via #060/#061).
- `brief`/`brief-upper` then see new node ids with no brief and regenerate ALL of
  them — the expensive LLM reduce — even when nothing changed.

So condense/embed are incremental (content-hash keyed, stable), but cluster +
brief + brief-upper are FULL-COST every rebuild. #064's member-set-signature
staleness is correct machinery but never fires through `maintain`, because the
briefs are cascade-deleted before their signature is ever compared. The fix is
STABLE node identity across rebuilds.

## The requirement (M7 — T33-T39 incremental lifecycle)
A re-cluster over unchanged (or mostly-unchanged) input must PRESERVE node
identity for clusters that did not meaningfully change, so their briefs survive
and #064's signature-skip actually saves the LLM cost:
- Match new clusters to existing nodes by membership overlap (sticky re-check),
  keeping the node id (and thus its brief) when the member set is unchanged or
  within the settle tolerance (clustering-lifecycle.md constants).
- Only genuinely new/changed/dissolved clusters mint/retire node ids; their
  briefs regenerate. Unchanged clusters keep node id + brief (near-zero).
- Propagate a changed leaf brief UPWARD (the #062 build-tree no-op-once-built gap):
  a changed child brief marks its parent's member-signature stale so upper levels
  rebuild only along the affected path (this is the `propagate` judge cascade,
  implementation-notes).
- Preserve pins (manual edits, M9) across the sticky re-check.

## Why this is the linchpin
Without stable node ids, `maintain` re-runs the entire brief tree every time — the
core "incremental update" promise is only half-true (cheap embed, full-cost
briefs). This ticket is what makes a second `maintain` genuinely near-zero and a
single changed file touch only its path. It is explicitly M7, deferred from M4
(#065 ships the full-build easy-button meanwhile).

## Acceptance criteria (when pulled into M7)
- [ ] A re-cluster over unchanged input keeps node ids for unchanged clusters;
      their briefs are NOT cascade-deleted and NOT regenerated (LLM call count 0).
- [ ] A single changed source file re-clusters/re-briefs only the affected node(s)
      and their ancestor path, not the whole tree — demonstrated with a call count.
- [ ] #064's member-set-signature skip now actually fires through `maintain`.
- [ ] Manual edits / pins survive the sticky re-check (with M9).
- [ ] Baked clustering constants unchanged; deterministic under the seed.
- [ ] `ruff format`, `ruff check --fix`, `pytest` all clean.

## Out of scope
- The full-build easy-button (#065, M4) — this makes its second run incremental.
- Recall (M5) / Export (M6).

## Review log
- 2026-08-25 PO: promoted backlog -> todo as the M7 (Lifecycle) foundation. The
  MVP (M0-M6) is complete; this is now the T34 incremental-placement substrate
  (T34.1 sticky pre-batch-centroid re-check + the propagate-upward gap are already
  in this ticket's scope). It is the M7 critical path — T34.2-4 and T35-T39 build
  on stable node ids, so it goes first. Still high priority; deps (040/059/062/064)
  all done, so it is READY. When picking it up, align its `settle`/warm-rebuild
  aspects with T39 (they overlap) — but the core deliverable here is stable ids so
  a re-cluster does not wipe+regenerate every brief.
- 2026-08-24 PO: authored from the #065 maintain design conflict. This is the
  concrete incremental-placement requirement behind hrono's differentiator:
  briefs are keyed to unstable cluster node ids, so a re-cluster wipes and
  regenerates the whole brief tree. Parked in backlog as M7 (T33-T39) — high
  priority WITHIN M7 because it is the differentiator, but it does not block the
  M4 full-build (#065) or the M5/M6 MVP path. Pull in when M7 starts.
- 2026-08-25 dev: DONE, committed 0acf1d0, handoff to qa. Node identity is now
  CONTENT-derived and preserved across rebuilds:
  - migration 0016 adds `nodes.signature`. `cluster.store` `replace_tree`/
    `replace_level` no longer blind-delete: `_reconcile` matches each new
    cluster's signature to an existing node and REUSES its id (clearing/refreshing
    members, keeping the node row + its brief un-cascaded); unmatched clusters
    mint ids; unmatched nodes retire (briefs cascade). Leaf signature = sorted set
    of member CONTENT HASHES (stable across a re-split's new section ids); upper
    signature = sorted child NODE IDS (stable once the level below is).
  - `briefs.member_signature` now signs leaves over content hashes (not section
    ids), so #064's freshness skip actually fires through a rebuild.
  - Net: change propagates only up the changed path automatically — an unchanged
    child keeps its id, so its parent's signature is unchanged and its brief is
    kept; a changed child gets a new id, shifting its parent's signature up the
    line. No separate propagate pass needed.
  Verified: ruff clean; pytest 532 passed / 1 skip. Load-bearing proofs:
  (1) tests/cluster/test_stable_ids.py — a re-cluster over unchanged content (new
  section ids) keeps node ids, a preserved node's brief SURVIVES with an unchanged
  content signature, changed content mints a new id; (2) tests/tree/test_maintain
  — a SECOND `maintain` over an unchanged corpus makes ZERO LLM calls and keeps
  every node id (the incremental promise, end to end).
  DEFERRED (note for the M7 remainder, not in this ticket's load-bearing scope):
  - Sticky re-check with settle TOLERANCE (keep a node id when membership changed
    *slightly*, per clustering-lifecycle constants) — this ships EXACT-match
    preservation; the tolerance/centroid sticky re-check is T34.2-4/T39.
  - Pins / manual edits survival (M9, no pins exist yet).
  Baked clustering constants unchanged; deterministic.
- 2026-08-25 qa: PASS (commit 0acf1d0) -> po-review. This is the differentiator
  ticket and it delivers — verified BOTH incremental halves end-to-end:
  - Unchanged corpus: drove a first maintain (11 LLM calls, real build) then a
    SECOND maintain over the identical corpus -> 0 LLM calls and every node id
    preserved. Section ids change on re-split, but the content-hash leaf signatures
    keep node ids/briefs stable, so #064's skip fires. (test_stable_ids +
    test_second_maintain_makes_zero_llm_calls_and_keeps_node_ids cover this.)
  - Single changed file (criterion #2, "demonstrated with a call count"): drove a
    9-file corpus, edited ONE file, re-maintained -> only 2 LLM calls vs 13 for the
    full build (the changed leaf's brief + its affected ancestor path), not the
    whole tree, not zero. The `_reconcile` scheme makes this automatic: a changed
    file's leaf gets a new content-signature -> new id -> its parent's child-id set
    shifts -> new parent id up the path, while unchanged siblings keep id + brief.
  - `_reconcile` is correct: signature-match reuses the node id (brief un-cascaded,
    members refreshed), unmatched mints, unreused retires (brief cascades);
    deterministic (sorted labels, first-id-wins). Bottom-up build order makes the
    upper child-id signatures stable before parents sign over them. Migration 0016
    is nullable (pre-signature nodes rebuild once).
  - Gate: I had to ISOLATE — a concurrent #083 (sync diff) left UNTRACKED
    `ingest/diff.py`/`test_diff.py` in the tree with 6 E501s, so a bare `ruff check`
    was red on #083's not-yet-linted WIP, NOT 068. In a worktree at 0acf1d0: ruff
    clean, format clean, full suite 532 passed / 1 skip.
  Deferrals are legitimate and documented, aligned with the PO's T34/T39 note:
  settle-TOLERANCE sticky re-check (keep an id when membership changes *slightly*)
  is T34.2-4/T39; pins survival is M9 (no pins exist). This ships EXACT-match
  preservation, which is what makes the second maintain near-zero.
  Minor (non-blocking): the single-changed-file affected-path-only re-brief is
  proven by my drive + the composition of the committed unit tests (unchanged->0,
  changed-content->new id), but there is no single committed end-to-end test that
  edits one file and asserts the partial call count directly — worth adding when
  the M7 lifecycle tickets (T34+) build on this. (Pre-existing `.gitignore` edit +
  the separate #083 WIP remain in the tree.)
- 2026-08-25 PO review: PASS -> done. The differentiator ticket, delivered. Gated
  #068's commit (0acf1d0, now one below HEAD since #083 committed on top) in an
  isolated worktree: ruff clean, 102 cluster/summarize/tree tests pass. Read
  `_reconcile` + migration 0016: node identity is content-derived (leaf signature
  = sorted member CONTENT HASHES, stable across a re-split's new section ids;
  upper = sorted child node ids), and reconcile REUSES a node id on signature
  match (brief un-cascaded, members/children refreshed), mints on no-match, retires
  the unreused (brief cascades) — deterministic (sorted labels, first-id-wins),
  migration nullable (pre-signature rows rebuild once). This is exactly what #065's
  design conflict said was needed and I deferred to M7: an unchanged re-cluster now
  keeps node ids + briefs (#064's skip fires), so a second maintain is ZERO LLM
  calls, and a changed file mints a new leaf id that shifts only its ancestor
  path's ids — change propagates only up the changed path, automatically, no
  separate propagate pass. All load-bearing acceptance criteria met. Deferrals are
  legitimate and documented (settle-TOLERANCE sticky re-check = T34.2-4/T39; pins =
  M9). Closed. Spun off #084 for qa's note: add a committed one-file-change ->
  partial-call-count regression test (the mechanism is unit-tested and qa drove the
  e2e, but the differentiator deserves a committed guard on the partial path).
