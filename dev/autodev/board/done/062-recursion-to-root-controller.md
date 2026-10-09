---
id: 062
title: recursion-to-root controller — build levels until one root remains (T22.3)
priority: high
size: medium
depends_on: [060, 061]
spec_refs: [build-order.md#T22.3, design-sketch-v1.md, how-hrono-works.md, clustering-lifecycle.md]
---

## Context
T22.3. Level-1 briefs (#059), the embed+cluster-briefs step (#060), and
brief-upper (#061) are the pieces; this ticket is the controller that drives them
in a loop to build the whole tree UP TO A SINGLE ROOT. Each iteration: embed +
cluster the current top level's briefs (#060) -> brief-upper the new nodes (#061)
-> repeat on the level just formed, until a level collapses to one node (the
root). This is the "... to root" in the recursive build.

## Description
A controller (a job op, e.g. `build-tree`, or the recursion inside `maintain`'s
brief phase — dev's call, keep it one clear owner) that:
- Starts at the highest existing level with briefs and repeatedly runs
  #060 (embed+cluster that level's briefs into the next) then #061 (brief-upper
  the new level), advancing one level per pass.
- **Termination**: stop when a level produces a single node (the root), or when a
  level does not reduce node count (would loop forever). Honor D_MAX from
  clustering-lifecycle.md as a hard depth cap so a pathological corpus cannot
  recurse without bound — OPEN QUESTION for dev: confirm D_MAX is the intended
  ceiling and whether a non-reducing level is an error or a forced-root.
- Deterministic and idempotent: re-running on an already-built tree rebuilds only
  what is stale / adds no duplicate levels.
- Persists each level's nodes/members/coords via the existing stores; the root is
  marked/queryable as the tree's top.
- CONSTRAINTS from #060 review (qa): (1) `cluster.store.replace_level` clears
  level N+1 and rebuilds it with FRESH node ids, so an existing level N+2's
  `node_children` (child_id -> old N+1 ids) cascade-delete on that rebuild —
  the controller MUST rebuild bottom-up (or invalidate downward), never rebuild a
  level under an already-built parent level. (2) #040's `build` raises
  `ClusterError` when a level has too few clusterable briefs (all-noise, which
  happens near the root) — the controller MUST detect the near-root/too-few case
  and STOP (declare the current top the root) rather than let the leaf fail.

## Acceptance criteria
- [ ] Building a multi-level fixture from level-1 briefs recurses to exactly one
      root node; every level's members are the prior level's node ids.
- [ ] Terminates correctly: single-node level = root; a non-reducing level does
      not infinite-loop; depth is bounded by D_MAX.
- [ ] Idempotent: a second run adds no duplicate levels and rebuilds only stale
      parts.
- [ ] Deterministic under the fixed clustering seed.
- [ ] Tests (fake client): a corpus that needs >= 3 levels builds to a single
      root; termination + idempotence + the D_MAX bound asserted. `ruff format`,
      `ruff check --fix`, `pytest` clean; committed.

## Out of scope
- Freshness/invalidation of already-built levels (T23 / #063-064).
- The full `maintain` easy-button that also runs sync/split/embed/cluster first
  (T24 / #065) — this is the brief-recursion half it will call.

## Review log
- 2026-08-23 PO: authored as T22.3. Loops #060 -> #061 per level to a single
  root; termination bounded by D_MAX (flagged for dev to confirm) and a non-
  reducing-level guard so it cannot spin. Idempotent + deterministic.
- 2026-08-24 dev: DONE, committed a82249f, handoff to qa. Added `build-tree`
  controller (summarize/build_tree.py): loops #060 cluster-briefs -> #061
  brief-upper per level until a single root, bottom-up.
  - Starts at the HIGHEST level that already has briefs, so a fresh corpus
    recurses from level 0 and a re-run starts at the root and does nothing
    (idempotent, no duplicate levels; never rebuilds under an already-built parent
    per #060's node_children cascade constraint).
  - CONFIRMED D_MAX=5 (clustering-lifecycle.md / CLAUDE.md) as the hard depth cap.
    Four termination guards: single-node level = root; ClusterError (too sparse
    near root, #040 all-noise) stops and declares current top the root;
    non-reducing level is discarded (dropped) and stops; depth capped at D_MAX.
  - Deterministic; injects build/client/encoder_for so the loop logic is tested
    with fake builds (the clustering recipe itself is #060/#040's concern).
  Verified: ruff clean; pytest 456 passed / 1 skip (+6: recurses-to-single-root
  with child chaining, non-reducing stop, ClusterError stop, D_MAX cap,
  idempotent second run, registration).
  NOTE: "rebuild only stale upper levels" in place needs stable node ids across
  re-cluster (deferred, #T39 territory); today a re-run is a no-op once built, and
  a leaf change would need a downward invalidation pass — out of this ticket.
- 2026-08-24 qa: PASS (commit a82249f) -> po-review. Tree was CLEAN at handoff
  this time (good). Verified every dimension:
  - Both #060-review constraints are honored: (1) bottom-up — starts at the
    highest brief level and only ever forms the level ABOVE, so it never rebuilds
    under an already-built parent (the node_children cascade hazard); (2) the
    ClusterError near-root case is caught and stops, declaring the current top the
    root rather than failing the leaf.
  - Four termination guards, all tested: single-node level = root; ClusterError =
    stop-at-root; a non-reducing level (`formed >= current` or `formed == 0`) is
    dropped and stops; depth hard-capped by `D_MAX = 5` (confirmed against
    clustering-lifecycle.md / CLAUDE.md). test_depth_is_capped_at_d_max asserts it
    stopped by the CAP (levels[D_MAX] > 1), not by reaching a root.
  - Recurses to exactly one root (top >= 2 genuinely multi-level, root count == 1)
    with child chaining asserted; idempotent second run adds nothing (re-run starts
    at the root, current <= 1, no-op — no duplicate levels).
  - Controller logic is driven with real DB + real stores (cluster_briefs /
    brief_upper called for real); only build/client/encoder are injected, which is
    correct — the clustering RECIPE is #060/#040's concern and was verified live
    there, so this ticket rightly tests the loop/termination logic.
  - ruff clean; full suite 456 passed / 1 skip; commit atomic + Conventional.
  M4 (Brief) is now essentially complete pending #065 (maintain). (Pre-existing
  unrelated `.gitignore` edit remains uncommitted.)
- 2026-08-24 PO review: PASS -> done. Tree clean, #062's commit is HEAD (a82249f).
  Read build_tree.py: both constraints I threaded from the #060 review are honored
  — bottom-up (`_highest_brief_level` start, only ever forms level+1, never
  rebuilds under an existing parent) and `except ClusterError: break` (stops at
  root on #040's all-noise near root). Four termination guards present and tested:
  current<=1=root, ClusterError=stop, non-reducing (`formed==0 or formed>=current`)
  drops the level and stops, depth hard-capped at D_MAX=5. Idempotent (re-run
  starts at root, no-op), deterministic. Ran the 6 build_tree tests, ruff clean,
  full suite 456 passed / 1 skip. All acceptance criteria met. Closed.
  IMPORTANT scope note for #065/M7: dev correctly flagged that a LEAF-brief change
  does NOT propagate upward today (build_tree no-ops once built; #064 marks leaf
  briefs stale but upper levels are not invalidated downward). True incremental
  placement + upward propagation is M7 (propagate/settle), NOT M4. Acting on this:
  softening #065's over-strong "one changed file touches only its path" criterion
  to match M4 reality (per-stage content-hash/signature skip of unchanged inputs),
  deferring full incremental to M7 — so #065 is not mis-scoped.
