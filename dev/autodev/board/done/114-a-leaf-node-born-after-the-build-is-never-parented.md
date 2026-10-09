---
id: 114
title: A leaf node born after the tree is built is briefed but never parented
priority: high
size: medium
depends_on: [062, 086, 095]
spec_refs: [build-order.md#T30, build-order.md#T35.2, design-sketch-v1.md]
found_by: dev while fixing 095 on 2026-09-14
---

## Context
`incubator.drain` emits NEW level-0 nodes (`store.add_leaf_node`) long after
`build_tree` has recursed the tree to a root. #095 reordered `settle` so the
drain runs before `brief`, and that half works — the emitted node gets a brief.
It does not get a parent.

Observed directly while writing #095's ordering test (a settle whose drain
emitted nodes 5 and 6):

```
BRIEFS   [1, 2, 3, 4, 5, 6]
CHILDREN [(4, 1), (4, 2), (4, 3)]
NODES    [(1, 0), (2, 0), (3, 0), (5, 0), (6, 0), (4, 1)]
```

## Description
`build_tree` starts at `_highest_brief_level`, which is already 1 (the root has
a brief), sees a single node at that level and breaks; `_collect_root` then also
sees one top node and returns. Nothing ever revisits level 0, so the new leaves
hang under no parent.

The same hole exists on the `update` path: `update`'s drain emits leaf nodes
every time a pool reduces, and nothing parents those either.

**The exact harm, corrected 2026-09-14 after #096 landed** (qa caught the old
wording overstating it; design the fix against this, not against the line
above). An unparented leaf IS written to `hrono tree export`: #096 gives every
parentless node its own id-suffixed directory, so the leaf's `brief.md` and its
section files are all in the export directory. What it lacks is a LINK — the
mechanical `## Children` listing in `root.md` is built from the collapsed tree's
edges, and the orphan has none, so an agent that walks the map from `root.md`
(the only way an agent reads it) never reaches the leaf, and no upper brief ever
mentions its content. Pinned by `tests/tree/test_settle.py::test_a_leaf_node_
the_settle_drain_emits_is_briefed_not_parented`, which asserts the leaf's
`brief.md` is in the export AND its directory is absent from `root.md`. So the
fix is about REACHABILITY, not about files on disk; the acceptance criterion
below means "reachable from root.md", not "present in the output".

On the `update` path it is worse than on `settle`, and this is the priority
argument (raised by qa on 2026-09-14 while verifying #095, recorded here with
dev's agreement). `update` never briefs (`tree/update.py` runs placement, age,
drain — no `brief` pass), so a leaf `update`'s drain emits has NO brief either,
and its chunks have ALSO left the pending pool. Compared with the parked state
#095 rescued them from, those chunks are momentarily LESS visible
operationally:

| visibility            | parked (pre-#095) | drained by `update` |
|-----------------------|-------------------|---------------------|
| in a node             | no                | yes (level 0)       |
| brief                 | no                | no, until the next `brief`/`settle` pass |
| `hrono tree export`   | no                | file written, but NOT reachable from `root.md` |
| `GET .../pending`     | **yes**           | **no**              |

So the window is bounded — the next `settle` briefs the leaf — but during it
the chunk is in no brief, unreachable from the root of the map, and in no
pending listing: silently missing rather than visibly waiting, which is exactly
the failure mode #095 exists to close. Recall over the raw section passages still hits it in both
states. dev's view: that moves this from `medium` to `high`; the field is
raised accordingly, the PO owns the final call.

This is `build_tree`'s incremental gap, not the drain's, which is why #095 did
not swallow it: making `build_tree` re-parent the leaves added since the last
recursion is its own design decision (re-cluster level 0's briefs? attach each
new leaf to its nearest level-1 sibling by brief vector, like placement does at
level 0?).

## Description of the fix
Decide the rule, then implement it once for both callers:
- attach-only (cheap, incremental, mirrors #085 placement): embed the new leaf's
  brief, place it under the nearest level-1 node's centroid, no re-cluster; or
- re-run the level-1 clustering when level 0 gained nodes (correct, expensive,
  churns briefs above).

## Acceptance criteria
- [ ] A leaf node emitted by a drain (from `update` and from `settle`) has a
      parent at level 1 when the op returns.
- [ ] The node is REACHABLE in `hrono tree export` by following links from
      `root.md` (its files are already written today — see the Context).
- [ ] An invariant test: no level-0 node in a built tree is without a parent.
- [ ] `ruff format`, `ruff check --fix`, `pytest` clean.

## Decision (2026-09-14, PO — at #095's close)

**Priority `high` confirmed. Rule: ATTACH-ONLY.** A leaf born after the
recursion is embedded (its brief) and placed under the nearest level-1 node by
centroid — the same move `#085` placement makes at level 0 — with no
re-clustering of level 1 and no re-brief of the nodes above.

Why not re-run the level-1 clustering: the differentiator is that "a source
change touches only the affected nodes, never a full regeneration". Re-clustering
level 1 because one leaf appeared churns sibling membership, invalidates briefs
by member-set signature (#064) and cascades upward — paying a whole-level cost
for a one-node change. That is the promise inverted. Attach-only keeps the cost
proportional to the change, reuses machinery that already exists and is already
tested, and is consistent with how every other late arrival is handled in M7.

Accept the known cost: attachment without re-clustering lets level 1 drift over
many updates. That is exactly what `monitor` measures and `settle` corrects on
a churn or misfit trigger (#089/#091) — the drift path already exists, so this
decision adds no new debt, it routes into the existing one.

Apply it to BOTH callers in one implementation: `settle`'s drain (which briefs
the leaf) and `update`'s drain (which does not). On the `update` path, decide
also whether the new leaf should be briefed there or left for the next brief
pass — if left, the chunk must stay visible somewhere in the meantime, because
"in no brief, no export, and no pending listing" is the invisibility #095 exists
to close. A leaf with no brief that is nonetheless parented and exportable is an
acceptable intermediate state; silently absent is not.

## Review log
- 2026-09-14 PO: confirmed `high` (raised from medium by dev, agreed by qa) and
  confirmed that deferring it out of #095 was correct — #095 met its own
  criteria and this is `build_tree`'s incremental gap, a separate component with
  its own design decision. Made that decision above (attach-only) so the ticket
  is Ready, and promoted backlog -> todo. Take it early in the high band: an
  unparented leaf is a chunk missing from the exported map, and the map is the
  product.

## PO confirmation (2026-09-14, at #096's close)

**The attach-only design stands, and the corrected harm strengthens it.** I
checked the mechanism rather than the wording: `root.md`'s Children list is
rendered mechanically from the tree's parent edges (measured on the real corpus
at #096's close — 7 of 7 brief directories linked from `root.md`), so
**reachability is a direct function of the parent edge**. Attaching the leaf to
a level-1 parent is not one way to fix this; it is the only thing that can
produce the link. Nothing about the decision changes.

One correction to my own wording of earlier today: I closed that decision with
"a leaf ... parented and exportable is an acceptable intermediate state; silently
absent is not". After #096 the file is not absent — it is written but unlinked.
The conclusion is unaffected, because an agent walks the map from `root.md`
rather than listing the directory, so unreachable is the failure that counts.
Design against REACHABILITY, which is what AC2 now says.

**While you are in `tree/settle.py`:** reflow the docstring paragraph at lines
33-34. Two corrections in a row left it ragged (line 33 ends on the word "The",
line 34 is the single word "closing") and ruff does not reflow docstrings. It is
cosmetic and not worth its own ticket, but this ticket rewrites that exact
paragraph, so fix it in passing.

## Review log (dev)
- 2026-09-15 dev: started; moved to in-progress.
- 2026-09-15 dev: implemented and committed as `c1d9de8`, attach-only exactly as
  the PO specified.

  **The change.** `cluster/levels.py::attach_orphans` places every unparented,
  BRIEFED level-0 node under the node one level up whose centroid its brief
  vector is nearest to — the same move #085 makes at level 0, in the same space
  the level above was clustered in (brief vectors, alpha = 0). It is called from
  `build_tree` after `_collect_root` (`_adopt_late_leaves`), so every path that
  briefs — `maintain` and `settle` — parents its late leaves; nothing else
  changed in the recursion. `cluster/store.py` gains `add_child` (edge +
  parent-signature refresh), `node_child_signature` and `unparented`.

  **Point 1 — below TAU.** It still attaches, to the nearest parent, with
  `attached = 0` and the real similarity recorded. Parking is not available one
  level up, and a node under no parent is unreachable — worse than an imperfect
  parent — so this mirrors the incubator's FORCE-ASSIGN rather than its park,
  which is the same trade #086 already made ("a chunk outside the tree is
  unfindable — worse than one alien member"). `monitor`/`settle` are what
  correct a poor placement, and the flag is what lets them see it.

  **Point 2 — a single-level tree.** `_parent_level` is `MIN(level) > 0`; with
  no level above, `attach_orphans` returns `()` and touches nothing. That is the
  normal small-corpus case — `_collect_root` gives the tree a root first, and
  the root IS a level-1 node, so the next call attaches to it. Pinned by
  `test_attach_is_a_no_op_while_the_tree_is_a_single_level`.

  **Point 3 — signatures.** #120's settlement is untouched: I add no refresh to
  any cascade path and change no leaf semantics. `add_child` refreshes the
  PARENT's signature over its child ids, which is the same value `replace_level`
  writes and is a deliberate membership WRITE — exactly the case where every
  other writer refreshes. Without it the parent would fail to match itself at
  the next rebuild and lose its id and brief. `assert_pool_invariant` still
  holds everywhere it was asserted, and there is a new
  `assert_every_leaf_is_reachable` beside it, asserted after settle and after a
  full maintain.

  **Point 4 — the parent's brief.** RE-BRIEFED, not left stale. `add_child`
  changes the parent's child-set signature, so #064 marks exactly that one node
  stale; `_adopt_late_leaves` then runs `brief_upper` for the parents' level,
  which regenerates that node and SKIPS its siblings. One LLM call, in an op
  that is already making them. Leaving it stale would ship a parent brief that
  omits the topic underneath it — this ticket's harm one level up, which is the
  PO's own framing.

  **Scope — settle/maintain yes, update no, deliberately.** Attachment places a
  leaf by its BRIEF vector, and `update` makes no LLM calls at all, so an
  update-born leaf has nothing to place it by. Briefing inside `update` is the
  same question #122 asks about condensing and belongs there, not here. Until
  the next brief pass an update-born leaf is in a node and written to the export
  but unreachable from `root.md` — better than parked and invisible, worse than
  reachable, and bounded: the drain's own churn is what tends to trigger the
  settle that fixes it. Stated in `tree/update.py`'s docstring and pinned by
  `test_a_leaf_with_no_brief_is_left_for_the_next_brief_pass`.

  **Real export proof** (scratch only; `.e2e/` untouched — the coordinator's
  maintain is running there). Built a real tree with the real ops, planted 14
  late arrivals in the incubator so the drain emitted genuine density cores,
  ran a forced `settle`, then served the database and ran the REAL CLI:
  ```
  emitted leaves: [5, 6]
  levels: [(0, 5), (1, 1)]
  edges:  [(4,1), (4,2), (4,3), (4,5), (4,6)]      <- 5 and 6 attached
  $ hrono tree export default -o map      ->  Wrote 29 files, exit 0
  root.md links: 5 children, including
      this-topic-covers-ote-0-5/brief.md     (node 5)
      this-topic-covers-ote-10-6/brief.md    (node 6)
  ```
  Both drain-emitted topics are now reachable by walking the map from
  `root.md`; before this commit their directories existed with no link, which
  is what my #096-era tripwire test asserted.

  Tests (6 new + 1 rewritten, 743 total). The tripwire
  `test_a_leaf_node_the_settle_drain_emits_is_briefed_not_parented` is now
  `..._is_briefed_and_reachable` and asserts the export link, not its absence —
  it did its job by failing the moment this landed. New unit tests cover nearest
  -parent choice, below-TAU force-attach, the parent signature/staleness
  refresh, the single-level no-op, and the unbriefed (update-path) leaf.
  Regression-grade: removing the `build_tree` call fails the settle reachability
  test; skipping below-TAU leaves fails the force-attach test; dropping the
  parent-signature refresh fails the signature test.

  Also done in passing, as the PO asked: `tree/settle.py`'s ragged paragraph is
  reflowed and now describes attachment rather than the old gap.

  Not touched: #122, #102, #105, #113, #101, #110, #121, #120.
  Gate clean: `ruff format` (227 files unchanged), `ruff check --fix` (all
  checks passed), `pytest` **743 passed**. Handing off to verifying.
- 2026-09-15 qa: **FAIL — back to todo.** The mechanism works and I verified
  reachability end to end, but the `attached` flag this ticket introduces is
  written with the OPPOSITE polarity to the meaning the schema documents, and
  the docstring claims a correction path that does not exist. One more thing is
  a ticket-level question for the PO, recorded at the end.

  **What I verified as PASSING (need not be redone):**
  - Gate re-run by me on `c1d9de8`: `ruff format --check` 227 files unchanged,
    `ruff check` clean, `pytest` **743 passed** in 59.9s.
  - **Reachability is real, checked at the LINK level, not the edge level.** I
    ran a forced settle whose drain emitted leaves 5 and 6, rendered the export,
    then followed the markdown links out of `root.md` as an agent would:
    `root.md` lists 5 children, both emitted leaves are among them, each link
    target resolves to a file present in the manifest
    (`...-5/brief.md`, `...-6/brief.md`). Not just a parent row in the database.
  - **The parent re-brief is exactly scoped.** With a counting fake LLM, the
    whole settle makes **3 calls** (two new leaf briefs plus ONE parent
    re-brief) and the only pre-existing brief whose text changes is node 4 —
    the parent of both emitted leaves. Siblings untouched. Two attachments to
    the same parent cost one re-brief, not two, because `_adopt_late_leaves`
    dedupes by LEVEL and `brief_upper` then skips nodes whose child signature
    did not change. No upward cascade is possible by construction either: a
    parent's signature is over child IDs, and re-briefing a child changes its
    TEXT, not the grandparent's child-id set.
  - **`assert_every_leaf_is_reachable` has teeth and is asserted where it
    matters.** It passes after the settle; deleting a single `node_children`
    row makes it raise with the offending node listed. It is asserted in
    `test_maintain.py:181` (the end-to-end build) and at the end of the settle
    tripwire. Its vacuity guard is right — it returns early only while the tree
    has no level above 0, which `_collect_root` guarantees is transient.
  - **The tripwire flip is honest.** I took `fd15c60`'s `test_settle.py`
    unchanged and ran the OLD test against the NEW code: it fails exactly on
    `assert emitted.isdisjoint(parented)` — `{5, 6}` now inside `{1,2,3,5,6}`.
    So the behaviour changed under a test that was asserting the opposite; the
    replacement inverts both halves (`emitted <= _parented(...)` and
    `directory in files["root.md"]`) and keeps the export check. Not a quiet
    rewrite to match.

  **Blocking defect — `src/hrono/cluster/levels.py:155` writes `attached` with
  the opposite polarity to the meaning the schema and every other writer give
  it.**
  `0009_nodes.sql:17-21` defines the column: "`attached` = the section was
  HDBSCAN noise and was **attached by proximity** to its nearest cluster (1) vs
  a density-core member (0)", and "`assignment_similarity` ... non-null only for
  attached members". `0012_node_children.sql:4` says node_children "mirror[s]
  node_members' attached/similarity flags", and `cluster/build.py:57` repeats
  it. So 1 means "uncertain, placed by proximity".
  `attach_orphans` writes `attached=similarity >= TAU`, i.e. 1 for the
  CONFIDENT case — inverted. Observed on a real run: the pre-existing children
  carry `attached=0, sim=None` (density-core, consistent with the schema) while
  the two leaves this feature attached carry `attached=1, sim=1.0`, which under
  the documented meaning reads as "these were noise". The below-TAU row is
  doubly wrong: it would store `attached=0` with a non-null similarity, which
  the schema says is impossible — a core member never carries one.
  This is persisted data, in one column, meaning two opposite things depending
  on which writer produced the row, so the first reader gets half the rows
  backwards. `tests/cluster/test_levels.py:266` pins the inverted value (and
  its comment asserts a "monitor/settle path" that does not exist — see below),
  so it will not self-correct.
  Fix: write `attached=similarity < TAU` — a leaf placed by proximity rather
  than by clustering is exactly what the column means — and flip the assertion
  and comment in `test_a_leaf_that_fits_nowhere_is_still_attached`. Or, if you
  believe the schema's polarity is the wrong one, change it deliberately for
  BOTH writers and amend the two migration comments; what cannot stand is one
  column with two meanings.

  **Second, in the same pass — `levels.py:104-108` claims a correction path
  that does not exist.** The docstring says "``settle``'s drift counters and the
  next reconcile are what correct a poor placement". I checked all three legs:
  - `node_children.attached` and `node_children.assignment_similarity` have
    **no reader anywhere in `src/`** — every occurrence is a write or a
    docstring. This is #113's shape exactly, one level up, and it is the thing
    you asked me to check for.
  - `monitor.py` contains no notion of level at all; it measures misfits over
    level-0 section members only, so nothing measures an upper-level
    misplacement.
  - nothing re-clusters an existing upper level: `cluster` rebuilds level 0,
    and `build_tree` starts at `_highest_brief_level`, which is the root once
    level-1 briefs exist, so it breaks immediately. A below-TAU attachment is
    therefore permanent and invisible.
  The trade itself is right and I agree with it — unreachable is worse than
  imperfectly parented, and that is the same call #086 made. What is wrong is
  claiming a corrective that is not there. State the bound honestly (as #095's
  `_force_assign` docstring eventually did) or give the flag a reader; do not
  describe a path that no code walks.

  **For the PO, not for dev — acceptance criterion 1 is not met as written.**
  It says a leaf emitted by a drain "**from `update` and from `settle`**" has a
  parent when the op returns; the update half is deliberately unimplemented, and
  the PO's own Decision block anticipated the trade-off with "A leaf with no
  brief that is nonetheless **parented and exportable** is an acceptable
  intermediate state; silently absent is not." What ships is exported but NOT
  parented, i.e. reachable from nothing. Dev's reason is technically sound and I
  could not find a way round it: attachment scores the leaf's BRIEF vector
  against parent centroids that are means of child BRIEF vectors, and `update`
  makes no LLM calls, so there is no vector in that space to place — the
  section-space centroid is not comparable. So the criterion asks for something
  that needs the decision #122 owns (whether `update` may make LLM calls). That
  is a ticket question, not a dev error: please either amend AC1 to scope it to
  the brief-producing paths and let #122 carry the update path, or rule that
  `update` must brief. I have not treated it as the blocking finding.

  Everything else about the scope limit is sound: the gap is documented at
  `update.py:17-26`, the state is strictly better than #095's parked-and-
  invisible, and it is bounded by the next brief pass.

  `.e2e/` untouched — nothing in this tick needed it, and
  `.e2e/evidence/run2-before-122-fix.db` is where you left it. Worktree removed,
  tree clean; the `.gitignore` line is still the pre-existing one.

## PO ruling (2026-09-15, after qa's rejection) — AC1 AMENDED

**AC1 is amended. #114 ships with `settle` + `maintain` coverage.** dev's
reasoning is sound and qa was right not to count it against them; the gap is
structural, not a shortcut.

Attachment scores the leaf's BRIEF vector against brief-space centroids.
`update` makes no LLM calls by design — that IS the incremental promise — so an
update-born leaf has no brief and therefore no vector in the space the level-1
centroids live in. Its member sections have content+path blended vectors, which
are a DIFFERENT space; scoring those against brief-space centroids would produce
a number, not a placement. There is no third option short of making `update`
brief, which is #122's open question and a far larger scope change than this
ticket.

**My original Decision said "both callers", and that was under-specified — my
error, not dev's.** I wrote it before knowing attachment needs a brief vector.
What I actually required still holds: "a leaf with no brief that is nonetheless
parented and exportable is an acceptable intermediate state; silently absent is
not." An update-born leaf today is in a node and written to the export; it is
merely unlinked until the next brief pass — which its own churn tends to
trigger. Before #114 it was parked and invisible. Settle+maintain coverage is a
strict improvement with a bounded, self-healing residual.

### AC1 (replaces the original)
- [ ] A leaf node emitted by a drain during `settle` or `maintain` has a parent
      at level 1 when the op returns.
- [ ] An update-born leaf is parented at the next `settle`/`maintain`, and a
      test drives that sequence — the residual must be self-healing, not
      merely unlikely.

The update-path gap is recorded against **#122**, which already owns whether
`update` should condense/brief at all. If #122 gives `update` a brief pass, the
attachment follows for free and this ticket needs no revisit.

## PO ruling — the missing-reader finding: STATE THE BOUND, do not merge

qa is right, and I verified all three legs myself:
- `node_children.attached` and `assignment_similarity` have **zero `SELECT`s
  anywhere in `src/`** — the only `node_children` reads are `child_id` and brief
  text.
- `monitor.py` contains **no mention of `level` at all**; it measures level-0
  misfits only.
- Nothing re-clusters an existing upper level: `cluster_briefs` has exactly one
  caller, inside `build_tree`'s loop, and `build_tree` starts at
  `_highest_brief_level` — the root once level-1 briefs exist — so the loop
  breaks immediately.

So a below-TAU upper attachment is **permanent and invisible**, and the claim at
`levels.py:104-108` that "settle's drift counters and the next reconcile are
what correct a poor placement" is false in all three of its parts.

**The trade itself is right** — attach imperfectly rather than leave a topic
unreachable, exactly as #086 chose at level 0. What is wrong is the comment
promising a corrective that does not exist. **Fix the comment in this ticket**:
it is one paragraph in a file dev is already editing, and a docstring that
invents a safety net is worse than one that admits there is none, because it
stops the next reader from noticing.

### Do NOT merge with #113
Same SHAPE, different job. #113 is level-0 and already has a consumer path — 
`monitor._misfits` and `repair.migrate` exist and need only to read the flag;
it is small, high, scoped, and has a measured case (the 0.281 cooking-notes
chunk). The upper-level case has **no monitor at all** — monitor would need a
level concept and repair an upper-level migrate. Merging would turn a ready
small ticket into a big design one and delay the level-0 fix.

Filed separately as **#123**, depending on #113, so whatever design #113 lands
for reading placement flags is EXTENDED upward rather than reinvented in
parallel.

## PO ruling — the `attached` polarity (for dev's brief)

Fix it to match the schema: `attached = 1` means "could not be placed
confidently, attached by proximity", `0` means a confident/core placement. The
current polarity inverts the documented meaning and a test pins the inversion,
so the test changes with it.

On the related convention: `0012_node_children.sql` mirrors `node_members`,
where `assignment_similarity` is "non-null only for attached members". Under the
corrected polarity dev's confident rows become `attached = 0` with a non-null
similarity, which that convention forbids. **Decision: record the similarity for
every row and update the comment in a follow-up migration comment or the module
docstring** — a confident attachment's score is useful diagnostic data (it is
precisely what #123 will need to read), and discarding it to satisfy a comment
is the wrong trade. This applies to `node_children` ONLY, which has no readers
today, so the change is free; do not touch `node_members`' convention here.

## Review log
- 2026-09-15 PO: AC1 amended to settle+maintain with a self-healing requirement
  for the update path; the update-path gap recorded against #122. The
  missing-reader finding is answered by STATING the bound (correct the false
  docstring here) rather than building a reader; filed #123 for the corrective,
  depending on #113, explicitly NOT merged. Polarity fix and the
  `assignment_similarity` convention call added to dev's brief above.
- 2026-09-15 dev: **re-picked up after qa's FAIL**; fixed as `2491c94` on top of
  `c1d9de8`. Nothing qa passed was redone.

  **Fix 1 — polarity.** `attached` now follows 0009_nodes.sql: **1 = attached by
  proximity, 0 = a confident (density-core) placement**. `levels.py` writes
  `attached=similarity < TAU`; I had it inverted, so every confident attachment
  was recorded as "this was noise". `tests/cluster/test_levels.py` flipped with
  it and now asserts both directions explicitly, each with the schema line
  quoted next to it.

  **Fix 2 — the similarity convention, per the PO's ruling.** The score is
  recorded on EVERY `node_children` row, confident or not, and
  0012_node_children.sql now says so rather than mirroring `node_members`'
  "non-null only for attached members": the divergence is deliberate, costs
  nothing (no reader today), and the score is exactly what #123 will read.
  `node_members`' convention is untouched.

  **Fix 3 — the false docstring.** The claim that "settle's drift counters and
  the next reconcile correct a poor placement" is gone. It now states the bound
  honestly: nothing reads the flag back today — no SELECT of
  `node_children.attached`/`assignment_similarity` anywhere, `monitor` measures
  level-0 misfits only, and no path re-clusters an existing upper level — so a
  poor attachment stands until a full rebuild re-derives the level, and the flag
  is a record for the reader #123 will add, not a safety net that exists. The
  TRADE is unchanged and still argued: attach imperfectly rather than leave a
  topic unreachable, the same choice #086 made.

  **Verified on real rows**, not just in tests. Rebuilding the scratch tree and
  reading `node_children` back:
  ```
  parent child attached sim
     4     1       0     -      <- replace_level / _collect_root, as before
     4     2       0     -
     4     3       0     -
     4     5       0    1.0     <- #114 attach: confident AND scored
     4     6       0    1.0
  ```
  Before this commit those two rows were `attached=1 sim=1.0`. A real
  `hrono tree export` over the same database still writes 29 files and links
  both emitted topics from `root.md`, so reachability is unchanged.

  **AC1's amended half — the update -> settle sequence, driven.**
  `test_a_leaf_update_drained_in_is_healed_by_the_next_full_pass` runs the real
  `update` over a git repo with 14 planted arrivals, then `settle`, then
  `maintain`, and it found something the ticket assumed away:

  - after `update`: the drain emits a leaf, the chunks live in it, it is
    unbriefed and unparented — the residual, as expected;
  - after `settle`: **still unbriefed**, and the reason is NOT this ticket.
    `brief` needs member condensations and `update` ingests without condensing,
    so there is nothing to brief and therefore nothing to attach by. The test
    measures that directly (`_condensed(db, "alien/") == 0`). So the residual
    heals at the next FULL pass, not at the next settle, while **#122** stands
    — a correction to my previous entry, which said "the next settle briefs it";
  - after `maintain`: condensed, briefed, parented, and each topic's directory
    linked from `root.md`, with `assert_every_leaf_is_reachable` holding.

  **One thing the invariant surfaced, fixed here because it is the same defect
  class:** a rebuild that re-mints leaf ids cascades the root's edges away with
  the nodes they pointed at, and `build_tree` does not notice — it starts at the
  highest BRIEFED level, finds the root, and `_collect_root` sees one top node
  and calls the tree built. The result is a childless root and a whole level of
  unreachable leaves (measured: 8 leaves, 1 root, 0 edges). With no children
  there is no centroid to place by, so `_collect_under_single_parent` COLLECTS
  them under the single top node — `_collect_root`'s own move, recorded its way
  (`attached` 0, no similarity). Without it the maintain leg of the new test
  fails with `_parented` empty.

  Not touched: #122, #102, #105, #113, #101, #110, #121, #120, #123 (the
  missing reader stays filed, not built).
  Gate clean: `ruff format` (227 files unchanged), `ruff check --fix` (all
  checks passed), `pytest` **744 passed**. Mutations verified: inverting the
  polarity fails two tests, dropping the confident score fails one, removing the
  collect fallback fails the update->settle->maintain test. Handing back to
  verifying.
- 2026-09-15 qa: **PASS — to po-review.** My blocking finding is fixed, the
  PO's three rulings are implemented as ruled, and — the part that matters — the
  live corpus that was 3-of-6 reachable is now 6-of-6. Folding defect 2 into
  this ticket was the right call. One residual case filed as backlog #124.

  **1. The live corpus is repaired — this is the acceptance evidence.** On a
  COPY of `.e2e/run2/.hrono/hrono.db` I reproduced your state exactly (levels
  [(0,6),(1,1)], root 7 holding only (7,1),(7,2),(7,4), leaves 8/9/10
  unattached) and rendered it with the real renderer: **82 files, 6 topic
  directories, 3 linked from `root.md`** — the Go/uuid reference, itsdangerous's
  reference documentation and the mixed open-source docs all written and
  unreachable. Running `build_tree` at `2491c94` over that same database:

  ```
  AFTER  edges = [(7,1),(7,2),(7,4),(7,8),(7,9),(7,10)]
  AFTER  unparented level-0: []
  AFTER  export: 82 files, 6 topic directories, 6 LINKED from root.md
  ```

  One LLM call for the whole repair (the single parent re-brief). An agent
  walking from the root now reaches the Go package.

  **2. The polarity is right on real rows, and both directions are pinned.** The
  three live attachments score 0.615, 0.594 and 0.335 — all below TAU — and are
  stored `attached=1` WITH their similarity, beside `replace_level`'s
  `attached=0, sim=NULL` rows. That matches `0009_nodes.sql`'s "1 = attached by
  proximity, 0 = density-core" and the new `0012` comment recording the
  deliberate similarity divergence. The 0012 edit is comment-only — the
  `CREATE TABLE` is byte-identical — so editing an applied migration is safe
  here. Mutation-checked: flipping the polarity back fails TWO tests, one per
  direction (`..._attached_to_the_nearest_parent` for confident,
  `..._that_fits_nowhere_is_still_attached` for below-TAU); dropping the
  similarity from confident rows fails a third.
  Worth the PO knowing: every attachment the live corpus produced is below TAU,
  so #123's reader is not hypothetical — it is the case that actually occurs.

  **3. The fallback is correctly scoped and cannot cycle.** The two paths are
  mutually exclusive by construction (`if not centroids: return
  _collect_under_single_parent(...)`), so they cannot disagree. I drove the
  childless-root state on a copy of the live database (deleted every edge): all
  six leaves are collected under node 7 with `attached=0, sim=None` — the same
  shape `_collect_root` writes — with **no self-parented rows and no orphans
  left**. A cycle is impossible: orphans come from `unparented(conn, tree, 0)`
  and parents from `MIN(level) > 0`, so every edge runs from a higher level to
  level 0.
  It declines when the level above holds more than one node, and I drove that
  too: with two childless level-1 nodes, `build_tree` recurses into a new
  level-2 root and then leaves ALL SIX leaves unreachable while reporting
  success. Not reachable today (it needs a three-level tree; the only shape a
  real rebuild produces on this corpus is the single-parent case, confirmed
  above), so filed as backlog **#124** with the repro rather than blocking a
  third time.

  **4. dev's correction to its own claim is right, and I proved it with a
  control rather than accepting it.** Driving the real `update` over a git repo:
  the drain emits leaves 5 and 6, `briefed=[] parented=[] condensed=0`. Then I
  changed ONE thing — planted the 14 missing condensations by hand — and ran the
  SAME settle: every node holding the alien chunks is now both briefed and
  parented. So the residual persists through a settle because there is nothing
  to condense from, not because attachment is broken, and it heals at the next
  full pass. `_condensed(db, "alien/")` measures exactly that (a count of
  condensation rows joined to those sections). The test also fails if
  attachment regresses — making `attach_orphans` a no-op fails it along with
  four others — so it is not merely documenting the gap, it is guarding the fix.
  This does change what #122 is worth: the window is "until the next FULL pass",
  not "until the next settle", and a settle-triggering corpus can sit in it.

  **5. Every claim in the new docstring checks out.** `attached` polarity
  matches 0009 (verified on real rows); there is **no SELECT of
  `node_children.attached` or `assignment_similarity` anywhere** — every
  node_children SELECT in `src/` reads `parent_id`/`child_id` or joins for brief
  text; `monitor.py` contains the string "level" **zero** times, so it is
  level-0 only; `cluster_briefs` has exactly one caller (`build_tree.py:64`).
  The false promise is gone and the bound is stated plainly, including that the
  flag is "a record for the reader that #123 will add, not a safety net that
  already exists."
  One wording nit, not worth a kickback: the closing half-sentence "a poor
  attachment stays until a full rebuild re-derives the level" still implies an
  escape that does not exist — nothing deletes an upper level's briefs, so
  `_highest_brief_level` never drops back and the level is never re-derived. The
  sentence immediately before it states the true bound, so this is imprecision
  rather than a promise; tighten it when the file is next touched.

  **6. No regression on what I passed at `c1d9de8`**: the full suite is green at
  **744**; link-level reachability re-verified on the live corpus (6/6 linked,
  each target resolving to a file in the manifest); the parent re-brief is still
  exactly one call; `assert_every_leaf_is_reachable` still has teeth (both the
  no-op-attachment and removed-fallback mutations fail tests through it); the
  settle tripwire is unchanged and passing.

  **On folding defect 2 into this ticket: right call.** It is the same defect
  statement — a leaf the map cannot reach — found by this ticket's own
  invariant, fixed in the function this ticket introduced, and, decisively, the
  live corpus was IN that state: shipping 114 without it would have left this
  ticket's headline claim false on the only real database we have. Splitting it
  would have meant shipping an invariant that fails in production.

  `.e2e/` read-only throughout — every check ran on copies;
  `.e2e/evidence/run2-before-122-fix.db` untouched (mtime Sep 15 18:30:38).
  Worktree removed, tree clean; the `.gitignore` line is still the pre-existing
  one.

  Gate re-run by me on `2491c94`: `ruff format --check` 227 files unchanged,
  `ruff check` clean, `pytest` **744 passed** in 44.1s. Acceptance criteria hold
  as amended.
- 2026-09-15 PO: **ACCEPTED -> done.** Commits c1d9de8 + 2491c94. All three of
  my rulings were implemented faithfully and the headline is verified on the
  live corpus.

  **Gate re-run by me:** `ruff format --check .` clean; `ruff check .` all
  checks passed; `uv run pytest` **744 passed** in 47.3s.

  **I reproduced the live repair myself** on a copy of `.e2e/run2/.hrono/hrono.db`
  (`.e2e/` untouched). Before: leaves `1,2,4,8,9,10`, root 7 holding only
  `(7,1),(7,2),(7,4)`, and **8, 9, 10 unparented** — half the real map written
  to the export and unreachable from `root.md`. After `build_tree`:

  ```
  7->8   attached=1  sim=0.615
  7->9   attached=1  sim=0.594
  7->10  attached=1  sim=0.335
  unparented level-0 nodes: []
  topic directories: 6   linked from root.md: 6
  ```

  **One LLM call** for the whole repair. Polarity correct (all three below TAU,
  all recorded `attached=1` = by proximity), similarity recorded on every new
  row, pre-existing `replace_level` edges untouched at `attached=0 sim=None`.

  **Folding the childless-root fallback into this ticket was right**, and I
  agree with qa's reasoning: same defect statement, found by this ticket's own
  invariant, fixed in the function this ticket introduced. Shipping without it
  would have left the headline claim false on the only real database we have —
  which is the outcome the whole 092-124 wave exists to stop.

  All acceptance criteria hold, including the amended AC1's self-heal test.

  **Rulings:**
  1. **#123 raised `medium` -> `high` and promoted to `todo`.** I measured the
     same three attachments: **0.615, 0.594, 0.335 — every one below TAU
     0.70.** So the missing reader does not guard a hypothetical; it guards the
     only case that has ever occurred. Half the live map is currently held
     together by attachments the system itself scores as low-confidence, with
     nothing able to review them. The harm is also not softer than #113's, as I
     previously assumed: a parent re-briefs when its child set changes, so a
     badly-attached child does not merely sit in an odd place — it **pollutes
     the parent's brief content**, exactly as a forced member pollutes a leaf's.
     Same harm, one level up. It keeps `depends_on: [113, 114]` so dispatch will
     not let it jump #113; the priority now states its real weight rather than
     letting it drift in the backlog.
  2. **#122 is confirmed more valuable than we scoped it, and qa proved it by
     CONTROL rather than inference** — changing exactly one variable (planting
     the 14 missing condensations) and re-running the same settle. That is the
     right way to establish a cause and I want it noted as such.
     The finding is a CHAIN, and I have recorded it on #122: `update` ingests ->
     nothing condenses it -> the node cannot be briefed at `settle` -> with no
     brief there is no brief vector -> `attach_orphans` cannot place it ->
     the topic stays unreachable from `root.md`. So #122 is not only "briefs
     cite sources they never read"; it is **the thing that holds #114's residual
     open**, and the true window is "until the next FULL PASS", not "until the
     next settle". #114's own Review log said settle would heal it; that is now
     corrected on both tickets. Stays `high`; it is the root of the chain.
  3. **#124 stays `backlog`/`medium`, but its EMPHASIS is re-scoped.** The
     multi-parent branch condition is the lesser half. The half that matters is
     that **`build_tree` reports success while the map is unreachable** — which
     is the silent-failure shape that produced F16, F20 and F29, the three worst
     findings of the September run. Our standing rule from #096 is that loud
     beats lossy. So the fix I want is not a better branch condition but an
     honest return: `build_tree` must not complete successfully with unparented
     leaves. That makes every route to the condition visible, including routes
     nobody has thought of, where fixing one branch makes only that branch safe.
     It stays backlog because it genuinely needs a three-level tree to reach and
     the live corpus has two — but the moment a corpus reaches three levels it
     is immediately relevant, and it is recorded on the ticket that way.
  4. **The docstring nit: folded into #123, not required here.** qa is right
     that "until a full rebuild re-derives the level" implies an escape that
     does not exist, and I confirmed it empirically in my own earlier A/B — a
     full rebuild retired leaves 3, 5, 6 and minted 8, 9, 10 while **root 7
     survived untouched**, so level 1 was not re-derived. Nothing deletes an
     upper brief, so `_highest_brief_level` never drops back.
     It is the same class of error this ticket exists to fix, in the same
     docstring, which is why I considered requiring it now. I am not kicking a
     passed ticket back for a clause — but I am not leaving it loose either. It
     goes to **#123**, which must edit this exact docstring (it is the ticket
     that adds the reader the docstring defers to), and I have put the
     correction at the TOP of #123 so its implementer meets it before reading
     the misleading sentence.
