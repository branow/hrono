---
id: 163
title: surgery on an upper-level topic, and who collects an orphan above level 0
priority: medium
size: medium
depends_on: [158, 114]
spec_refs: [design-sketch-v1.md, build-order.md#T47]
---

## Context
Spun off from #158's second qa review, which ruled that merge and dissolve
refuse a node above level 0 rather than guess at the rule. This ticket is that
rule.

An upper topic carries its content in `node_children`, not `node_members`, so
the operations #158 ships handle none of it. Merging two upper topics deletes
the loser and its `node_children` rows cascade away; dissolving one re-places
nothing, because it has no member rows to re-place. Both detach a subtree.

## The gap underneath it
`attach_orphans` — the one thing that re-parents a node with no parent — reads
`store.unparented(conn, tree, 0)`. Both call sites hardcode level 0
(`cluster/levels.py:133`, `summarize/build_tree.py:107`). It was written for
#114, where the orphan was always a leaf the incubator emitted after the tree
was built, and that was the whole truth at the time.

It is not any more. A node above level 0 can lose its parent — through a merge
or dissolve one level up, and through any future path that retires an upper
node — and NOTHING collects it. It is unreachable from the root and absent
from the export, with no bound on how long: exactly the "FOREVER" that
`attach_orphans`' own docstring describes for the case it was written to fix.

This is worth confirming as a defect independent of manual edits: find whether
any pipeline path already retires an upper node with children. `_drop_level`
and `repair.split` are the candidates.

## What this ticket decides
1. **Does orphan collection generalize above level 0?** The attach rule (unit
   brief vector against each candidate parent's centroid, attach below TAU
   rather than park, because a node with no parent is unreachable) is written
   level-agnostically in prose already. If it generalizes, `attach_orphans`
   takes a level and `build_tree` sweeps every level, and #158's operations
   become safe at any level almost for free.
2. **What a dissolved upper topic's children attach to.** Its siblings' parents
   by proximity is the obvious answer and matches #085 one level up. Worth
   stating rather than inheriting.
3. **Whether merge should carry `node_children`** to the survivor — almost
   certainly yes, and it is the same move `merge` already makes for members.

## A constraint on the loop you will be editing (#162 qa)
`repair.split` folds NOISE members into the core groups BEFORE it builds the
children, which is the only reason a pinned noise member's pin follows it into
the child that adopts it. One loop, not two. Moving the reattachment after the
child creation would break that silently, and no test names the ordering.

## Acceptance criteria
- [x] Merging two upper topics leaves every child of both under the survivor.
- [x] Dissolving an upper topic leaves none of its children unparented.
- [x] A node orphaned at any level is collected by the next `sync`, not only a
      leaf.
- [x] A regression test drives the whole thing at level 1 and asserts the
      export reaches every node from the root (#114's harm, one level up).
- [x] A merge of MORE than two nodes is covered by a test: #158 verified the
      behavior by hand but every test there merges exactly two, so the loop
      over the losers is unguarded (#158 po review).
- [x] `ruff format`, `ruff check --fix`, `pytest` clean.

## Out of scope
The refusals #158 ships. They stay until this lands and are the correct
behavior in the meantime.

## Review log
- 2026-09-24 po: authored from #158's second qa review.

- 2026-09-25 dev: done, commit 94eec73. The ticket asked me to confirm whether
  the orphan gap is reachable without a hand edit. **It is, and the guard that
  should have caught it was blind in the same place.**

  The mechanism, from the code: `cluster_briefs` groups only the nodes that
  HAVE briefs (`briefs.level_briefs`), then filters again to those whose brief
  has a VECTOR. A node missing either is simply absent from `replace_level`'s
  members, so no parent edge is ever written for it. At level 0 `attach_orphans`
  came back for it; above level 0 nothing did. A brief can be missing for an
  ordinary reason — #121 is a live backlog item about briefs REJECTED by the
  quality guard.

  Then the part I did not expect: `_require_reachable` reads
  `unparented(tree, 0)`. An upper orphan hides from that BY CONSTRUCTION — its
  own children are parented, to it — so the leaf-level check sees a tidy map.
  Driven: a level-1 node holding a level-0 child, with no parent of its own,
  and the guard reported a healthy tree. That guard's whole purpose is "the
  routes nobody has thought of yet", and this was one of them.

  So the fix is three things, and the first two are the ticket's real content:

  1. `attach_orphans` takes a `level` (0 by default), and `_adopt_late_leaves`
     sweeps every level bottom-up, so a subtree that came loose is whole again
     before its own parent is looked at.
  2. `_require_reachable` checks every level below the top.
  3. The surgery #158 refused now works: `merge` carries the losers' CHILDREN
     to the survivor and pins their parenting (the upper twin of the membership
     pin a leaf merge sets), and `dissolve` re-places an upper topic's children
     through `levels.replace_children` — the #114 attach rule against the
     remaining siblings' centroids.

  `replace_children` moves a child to a SIBLING of the retired node, never to
  its grandparent: a parent sits exactly one level up, and promoting a child
  two levels would break by pipeline the invariant #158 now refuses by hand.

  One refusal survives, and it is a new one: dissolving the only topic at its
  level. There is no sibling to receive its children, so the operation's own
  definition cannot be met — doing it anyway is the detachment this ticket
  exists to close. `require_leaf` stays for that message's sake but now has one
  caller, `move_section`; `merge`'s refusal became `require_one_level`, which
  is the part of #158's G4 that outlives it: a merge folds topics of ONE level,
  because the survivor is the lowest id and that says nothing about KIND.

  Driven on a real server:

      merge [5, 6]   -> 200; node 6 retired, all four leaves under node 5,
                       all four parenting pins anchored at 5
      dissolve 5     -> 422 "node 5 is the only topic at its level, so its
                       children have nowhere to go", tree untouched

  Mutations. Seven run, ONE survived and was made to kill:
  - the guard back to level 0 only -> 1 fail.
  - `attach_orphans` ignoring its level -> 1 fail.
  - merge not carrying children -> 1; merge not refusing mixed levels -> 1.
  - dissolve not re-placing children -> 1; dissolve allowing the last topic at
    its level -> 1.
  - **the sweep back to `range(1)` — leaves only: SURVIVED.** My collector test
    calls `attach_orphans(level=1)` directly, which proves the FUNCTION and
    says nothing about whether anything calls it that way. That is #108's shape
    with the halves swapped, and the sweep could have run `range(1)` for its
    whole life with every unit test green. Added
    `test_the_build_sweeps_every_level_for_orphans`, which drives
    `_adopt_late_leaves` over a planted upper orphan; now kills.

  Honoured the constraint qa left in this ticket's context: `repair.split` folds
  noise into the core groups BEFORE building children, and I did not touch that
  loop.

  Gate clean: 1160 passed, 2 skipped.

- 2026-09-25 qa: FAIL, back to todo. The work is right — I could not break it —
  but one acceptance criterion is ticked and not met, and it is the one that
  names the harm.

  Everything else verified. Gate at 94eec73: ruff clean, 1160 passed. Re-ran the
  mutation dev reported as survived-then-fixed (the sweep back to `range(1)`)
  and it fails, so the wiring really is guarded now. Drove both surgeries on a
  real server: an upper merge carries all four leaves to the survivor and pins
  their parenting, and dissolving the last topic at its level is refused with
  the tree untouched.

  **The AC: "asserts the EXPORT reaches every node from the root (#114's harm,
  one level up)."** The tests assert `store.unparented(...)` and
  `_require_reachable`. Those are the edge table and the guard over it — not
  the export, which is a different module (`export/store.load` ->
  `collapse`) and is the thing #114 was actually about.

  I wrote it as a probe, and it is worth having as a test because it shows the
  harm in the product's own terms rather than in the schema's:

      BEFORE the sweep, export reaches: [1, 3, 5, 6]
        the orphaned upper node: NOT reachable
        its two leaves:          NOT reachable
      AFTER the sweep,  export reaches: [1, 2, 3, 4, 5, 6, 7]
        all of them reachable

  Three nodes invisible in the map while every edge in the database was
  perfectly well-formed underneath them. That is the sentence this ticket
  exists for, and no test says it.

  Add one that walks `collapse(...)` from its root and asserts every node is
  reached, before and after. `tests/tree/test_settle.py` has the pattern
  (`_export` / `assert_every_leaf_is_reachable`) — and note that helper is
  every LEAF, so it would have passed over this too.

  Nothing else. The `require_leaf`/`require_one_level` split is the right
  reading of what outlives #158, and `replace_children` moving a child to a
  SIBLING rather than the grandparent is the detail I would have got wrong.

- 2026-09-25 dev: qa's finding fixed, plus a defect of mine that it flushed out.

  **The export assertion.** qa is right that `unparented` and
  `_require_reachable` are the edge table and the guard over it, not the thing
  #114 was about. `_export_reaches` now walks `collapse(...)` from its root and
  the test asserts both halves, which states the harm in the product's terms:

      before the sweep, the export renders [1, 3, 5, 6]
      after,                               [1, 2, 3, 4, 5, 6, 7]

  Three nodes invisible in the map while every edge underneath them was
  well-formed. qa's note that `test_settle`'s existing helper walks every LEAF
  is the reason this needed its own: an upper orphan passes that, because its
  leaves ARE parented — to it.

  **And a race I introduced in #168.** While re-running the suite I hit a
  single failure in `tests/server/test_trees.py` that would not reproduce —
  the second one-off of the session. Rather than call it a flake twice I went
  looking, and there is a real mechanism: #168's warm-up read the DATABASE
  inside its daemon thread. An adopted connection is lent to one thread at a
  time by `Shared`'s RLock, but every test that writes through `with conn:`
  holds the RAW connection and never goes through that lock — so a background
  reader could be executing on the same sqlite3 connection at the same moment,
  in ~100 server tests at once.

  The config read moved to the startup thread; only the weights load in the
  background, which is all that was ever slow. Three full suite runs since, all
  1160 green.

  I cannot prove that race caused either failure — neither reproduces, and the
  FIRST one predates #168 entirely, so at most this explains the second. What I
  can say is that the mechanism was real, it was mine, and it is gone.

  Mutation on the restructure: drop the `_logger.debug` on the startup-thread
  branch -> the quiet-failure test fails, so the line is still guarded where it
  now lives.

- 2026-09-25 qa: PASS, to po-review. The export assertion is in and it has
  teeth: I mutated `attach_orphans` to find its parent and then not write the
  edge, and the test fails — so the walk measures what the export renders, not
  merely that the test ran.

  Gate at 485d449: ruff clean, 1160 passed, 2 skipped, and I re-ran the whole
  suite after dev's own three — still green.

  **On the race dev found: I want it on the record that they went looking.** I
  had nothing to do with it. They hit a single non-reproducing failure, and
  instead of writing "flake" for the second time in a session they traced it to
  a mechanism they had introduced themselves one ticket earlier — a daemon
  thread reading an adopted sqlite connection that a hundred tests hold raw,
  outside the lock that was supposed to serialise it. The fix is smaller than
  the original code, because the database read never needed to be off the
  request path; only the weights did.

  Their honesty about it is the right call too: the first one-off predates
  #168, so this explains at most one of the two. A real mechanism removed, and
  no claim beyond that.

  Everything else from my last entry stands. The surgery works on a real
  server, the refusal for the last topic at its level is the right shape, and
  `replace_children` moving a child to a sibling rather than its grandparent is
  the detail that keeps the pipeline honouring the invariant #158 enforces by
  hand.

- 2026-09-25 po: CLOSED. #158 refused upper-level surgery rather than guess the
  rule, and this is the rule — plus the defect that was underneath it the whole
  time.

  The finding that matters is not the surgery. It is that **an upper orphan was
  reachable without any hand edit, and the guard against it was blind in
  exactly the same place as the collector.** `cluster_briefs` groups only nodes
  that have briefs, and a brief can be missing for an ordinary reason — #121,
  sitting in this backlog, is about briefs REJECTED by the quality guard. So
  the path was: a rejected brief one level up, a node silently absent from its
  parent's grouping, a whole subtree gone from the export, and
  `_require_reachable` reporting a healthy tree because it only ever looked at
  the leaves. Three nodes invisible with every edge in the database
  well-formed.

  That reframes #121 from a quality annoyance to a trigger, and I am raising it
  to **high** and promoting it: a false-positive rejection is now known to cost
  a subtree until the next build sweeps it up.

  Two things about how this ticket ran, both worth keeping:

  The sweep's mutation survived because the collector was tested by calling it
  directly. Proving a function is not proving that anything calls it — #108's
  shape with the halves swapped, and the third time this month a test proved
  the wrong half.

  And dev traced a second non-reproducing failure to a race they had introduced
  one ticket earlier, rather than logging "flake" twice. A daemon thread reading
  an adopted connection that tests hold raw, outside the lock meant to serialise
  it. I would rather have that habit than a green suite.

  M9's surgery is complete at every level, and the tree can no longer lose a
  branch quietly.

- 2026-09-25 po: correction to my own entry above. **#121 is already DONE** —
  it closed earlier this month — so it is neither a live trigger nor something
  to promote. I read it off this ticket's context, which cited it as a backlog
  item, and did not check the board before writing.

  The point survives the error, but it needs a different example. A node is
  absent from its parent's grouping when it has NO brief at all, and the
  reachable way to get there now is a brief that failed to GENERATE — an LLM
  error or a refusal mid-run — rather than one rejected by the shape check. A
  brief that is merely flagged or judged unfaithful still exists and is still
  grouped, so those are not it.

  That is a narrower trigger than I claimed and the harm is the same size: one
  briefless node one level up, and its whole subtree leaves the export until
  something sweeps it. Which is exactly why the sweep and the widened guard are
  the substance of this ticket, and why I am not authoring a ticket against a
  trigger that is already closed.
