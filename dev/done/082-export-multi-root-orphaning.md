---
id: 082
title: export orphans sibling top nodes when the stored tree has no single root
priority: high
size: medium
depends_on: [078, 079, 080, 062]
spec_refs: [how-hrono-works.md, build-order.md#T29, build-order.md#T31]
---

## Context
Spun off from #080 QA review. The export pipeline (`export/store.load` #080 ->
`collapse` #078 -> `render` #079) assumes the stored tree has ONE root:
`StoredTree.root` is a single node and `store.load` picks it as
`root = max(node_level, key=level)`. But #062 (recursion-to-root) can legitimately
terminate with MULTIPLE nodes at the top level — its "a level that fails to reduce
the node count is discarded and stops" guard leaves the current top level intact,
which may hold >1 node (a corpus that clusters down to a few stable topics that
won't merge further). For such a corpus there is NO single root.

## The defect (reproduced in the #080 review)
With two top-level nodes (10, 11), `load` picks 10 as root:
- `root.md` lists only node 10's children; node 11 and its whole subtree are
  UNREACHABLE from `root.md` — an agent walking the export never sees half the
  tree.
- Node 11's brief renders at a malformed path `"/brief.md"` (its `_directory` is
  empty because it has no parent and is not the root), and its children flatten to
  the top level instead of nesting under it.
So a multi-root corpus exports an incomplete + malformed tree, silently. The
common single-root case (most corpora, and any that #062 collapses to one node) is
fine — this only bites multi-top trees.

## PO DECISION (2026-08-25): option (b) — single-root build guarantee in #062.
The spec is explicit that the stored tree has ONE root whose brief abstracts the
top level (how-hrono-works.md: "The root brief uses the same prompt over the top
level"). So the fix belongs at the BUILD layer, not a cosmetic export patch:
#062's recursion controller must terminate with EXACTLY ONE root. Option (a)
(export-layer virtual root) is rejected — it leaves the stored tree multi-rooted
with no real orienting root brief (contradicting "the root brief orients") and
only papers over the symptom in export while recall / any other consumer still
sees no single root.

### What to build (fix in `summarize/build_tree.py`, the #062 controller)
- When the recursion would terminate with MORE THAN ONE node at the top level
  (the non-reducing-level case, or the D_MAX-cap case), add a final COLLECT step:
  create one root node parenting all current top-level nodes (via node_children)
  and run `brief-upper` (#061) over it, so the root brief abstracts across the top
  topics — exactly the spec's "root brief over the top level".
- This is a COLLECT, not a cluster (do not force meaningless clustering); it runs
  once at the end when clustering has genuinely stopped reducing.
- The root-collect may exceed D_MAX by one (the root is always allowed) — decide
  and document: D_MAX bounds the CLUSTERED levels; the final root sits on top.
- A corpus that already collapses to a single root is unchanged (no extra level).
- Downstream (`store.load` #080 / `collapse` #078 / `render` #079) then always
  sees one root — no export change needed beyond the regression test.

### Regression test (assert MVP export completeness)
- A stored tree that recursion leaves with multiple top nodes now gets ONE root;
  EVERY top topic is reachable from `root.md`; no node renders at a malformed
  `"/brief.md"` path; the root brief exists (brief-upper over the top level).

## Out of scope
- Anything else in the export pipeline (058-081 behavior is otherwise correct).

## Review log
- 2026-08-25 qa (during #080 review): found + reproduced the multi-root orphaning.
  #080 passes its own criteria (the gap is in the #078/#079 internals it wires,
  explicitly out of #080's scope), so filed here. HIGH priority because it affects
  MVP export COMPLETENESS — recommend resolving before / alongside the #081 MVP
  close so the MVP does not ship an export that silently drops topics on multi-root
  trees.
- 2026-08-25 PO triage: real MVP-completeness defect, DECISION = option (b)
  (single-root build guarantee in #062, see above) — rejected (a) because the spec
  puts a real root brief over the top level. Promoted backlog -> todo at HIGH
  priority. Fix site is `summarize/build_tree.py` (#062 controller) + `brief-upper`
  (#061) for the root brief; deps all done, so it is READY. Not blocking #081 (the
  CLI is independently correct), but the MVP is not truly complete until BOTH #081
  and #082 land — else a multi-root corpus exports a silently-incomplete map.
- 2026-08-25 dev: DONE, committed 12052a1, handoff to qa. Implemented PO option
  (b) — the single-root guarantee at the BUILD layer (summarize/build_tree.py).
  After the recursion loop, `_collect_root` checks the highest node level: if it
  has >1 node (the non-reducing-drop, ClusterError, or D_MAX-cap cases), it
  creates ONE root at top+1 parenting ALL top nodes via node_children (a COLLECT,
  not a cluster — no forced meaningless clustering) and runs brief-upper (#061)
  over it, so the root brief abstracts across the top topics per the spec. The
  root may sit one level above D_MAX (documented: D_MAX bounds the CLUSTERED
  levels; the root is always allowed on top). A corpus that already reaches one
  root is unchanged (no extra level); idempotent (a re-run starts at the root,
  count 1, no collect). No export change needed — store.load/collapse/render now
  always see one root.
  Verified: ruff clean; pytest 528 passed / 1 skip. Updated the 062 termination
  tests (non-reducing / ClusterError / D_MAX now collect a single root, every top
  node reachable as its children) + added the #082 export-completeness regression:
  a 12-stable-top corpus exports with root.md linking all 12 topics, no malformed
  "/brief.md" path. Downstream export (078-081) unaffected.
- 2026-08-25 qa: PASS (commit 12052a1) -> po-review. My original finding is
  resolved — verified end-to-end. Drove the exact orphaning scenario through the
  full build+export: 5 non-reducing top nodes -> `_collect_root` creates ONE root
  at top+1 (via `replace_level` with all-label-0, so one node parenting all 5 tops
  through node_children), briefs it with brief-upper, and `store.load` -> collapse
  -> render now yields a single root whose root.md links ALL 5 top topics — no
  orphaned subtree, no malformed `"/brief.md"` path. Confirmed the collect is a
  COLLECT not a cluster (labels don't force merges), is a no-op / idempotent for an
  already-single-root tree (top_count <= 1 -> return), and may sit one level above
  D_MAX (documented; D_MAX bounds the CLUSTERED levels). Regression tests updated
  (#062 termination now single-root) + the #082 completeness test added. ruff
  clean; full suite 528 passed / 1 skip; atomic `fix:` Conventional Commit. **The
  MVP export is now truly complete — multi-root corpora export a walkable, fully
  reachable map.** (Pre-existing `.gitignore` edit still uncommitted.)
- 2026-08-25 PO review: PASS -> done. My decided option (b) implemented exactly.
  Read `_collect_root`: after the recursion loop, if the highest level has >1 node
  it calls `replace_level(top+1, [(0, node_id, False, None) for each top node])` —
  all label 0, so ONE root node parents every top node via node_children (a
  COLLECT, not a cluster) — then brief-uppers it, so the root brief abstracts the
  top level per the spec's "root brief over the top level". `len(top_nodes) <= 1
  -> return` keeps it a no-op for already-single-root trees; the root may sit one
  level above D_MAX (documented; D_MAX bounds the clustered levels). Verified: 21
  build_tree+export tests pass, ruff clean, full suite 528 passed / 1 skip. All
  acceptance criteria met — a multi-top corpus now exports one root.md linking
  every top topic, no orphaned subtree, no malformed path. Closed. **MVP (M0-M6,
  T1-T32) is now FULLY complete and airtight — no known export-completeness gap.**
