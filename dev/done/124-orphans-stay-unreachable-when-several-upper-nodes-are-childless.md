---
id: 124
title: build_tree reports success while the map is unreachable
priority: medium
size: small
depends_on: [114]
spec_refs: [build-order.md#T30]
found_by: qa while verifying 114 on 2026-09-15
---

## Context
#114 closed two states: a leaf born after the recursion (attached by brief
vector to its nearest parent) and a root whose children all cascaded away
(`_collect_under_single_parent` collects them, the move `_collect_root` makes).
The second declines when the level above holds more than one node:

```python
if len(parents) != 1:
    return ()
```

## Description
That leaves a third state unhandled, and `build_tree` reports success in it.
Driven on a copy of the re-run database: plant a SECOND childless level-1 node
beside the existing one, then run `build_tree`.

```
planted: level-1 nodes = [7, 11], edges = 0
after build_tree: edges = [(12, 7), (12, 11)]
STILL UNREACHABLE level-0 nodes: [1, 2, 4, 8, 9, 10]
```

`build_tree` recursed level 1 into a new level-2 root, then `attach_orphans`
took `_parent_level` = 1, found no centroid there (both nodes are childless),
handed off to `_collect_under_single_parent`, which saw two parents and
returned. Every leaf — the whole corpus — is written to the export and linked
from nothing.

Not reachable today: producing it needs a three-level tree, and the only shape a
real rebuild produces on the current two-level corpus is the single-parent case
#114 fixed (confirmed on the live database, where all six leaves attach). It
becomes reachable as soon as a corpus is large enough to recurse past one
intermediate level.

## Description of the fix
Decide what a childless upper level means and handle it once:
- if several candidate parents are childless, there is no centroid to place by,
  so either collect the orphans under the nearest node ONE LEVEL HIGHER (which
  does have children — the new root in the trace above), or
- re-derive the childless level rather than patching under it, since a level
  whose every node lost its children carries no information.
Whichever is chosen, `attach_orphans` should not return `()` silently when it
has orphans it could not place: that is the failure mode that made the original
#114 invisible. `assert_every_leaf_is_reachable` already exists and would catch
this shape — it just needs a test that drives it.

## Acceptance criteria
- [ ] A tree whose intermediate level is entirely childless still ends with
      every level-0 node reachable from the root.
- [ ] `assert_every_leaf_is_reachable` is asserted over that shape.
- [ ] `attach_orphans` cannot return empty while leaving a placeable orphan
      unattached (log, raise, or attach one level up — the ticket decides).
- [ ] `ruff format`, `ruff check --fix`, `pytest` clean.

## PO ruling (2026-09-15, at #114's close) — the EMPHASIS is wrong

Priority confirmed `medium` and it stays in `backlog` — it genuinely needs a
three-level tree to reach and the live corpus has two. But the ticket is aimed
at the lesser half of its own finding.

The multi-parent branch condition is a detail. **The half that matters is that
`build_tree` reports SUCCESS while the map is unreachable.** That is the
silent-failure shape that produced F16, F20 and F29 — the three worst findings
of the September run — and the standing rule set at #096's close is: **refuse
what cannot be rendered correctly; degrade what can — but never report success
for either.**

So the fix I want is NOT a better branch condition in
`_collect_under_single_parent`. It is an honest return: **`build_tree` must not
complete successfully while level-0 nodes are unparented.** Fixing the branch
makes that one route safe; fixing the report makes EVERY route visible,
including the ones nobody has thought of yet — and this ticket exists precisely
because somebody found a route nobody had thought of.

#114 already has the invariant as a test ("no level-0 node in a built tree is
without a parent"). This is that invariant, enforced where it matters.

The moment a corpus reaches three levels this stops being latent, so re-check it
whenever the corpus grows rather than treating `backlog` as permanent.

## Acceptance criteria (superseding)
- [ ] `build_tree` does not return successfully with unparented level-0 nodes —
      it surfaces them (a raise, or a result the caller must act on; the CLI and
      job record must show it, not swallow it).
- [ ] The multi-childless-parent case specifically is covered by a test that
      builds a three-level tree and asserts the leaves are reachable, or that
      the failure is LOUD.
- [ ] `ruff format`, `ruff check --fix`, `pytest` clean.

## Review log
- 2026-09-15 PO: priority `medium` and backlog confirmed (needs three levels to
  reach). Emphasis re-scoped from the branch condition to the silent success,
  which is the defect that actually matters and the one our worst findings all
  share.

## Added by PO (2026-09-21, at #123's close)

**A single-child upper node is invisible to #123's corrective, by arithmetic.**
A parent's centroid is the mean of its children's brief vectors, so a parent
holding exactly one child IS that child: `own` = 1.0, no `best_other` can exceed
it, and 1.0 is above TAU — so `upper_misfits` never flags it and
`migrate_children` never moves it. qa drove this while verifying #123 (a lonely
parent whose only child matched another parent's topic exactly: `moved=0`).

This ticket is the right home because the shape is the same one it already owns:
an upper node that is degenerate rather than wrong. #123 cannot CREATE one — its
migrate provably cannot empty a parent — so this is about the ones a rebuild or
a retirement leaves behind. Whatever rule this ticket lands for childless upper
nodes should say what it does with one-child ones too.

## PO triage 2026-09-21 — promoted to `todo`, priority confirmed `medium`

Pairs with #131: both are `build_tree` reporting success over a map that is not
whole. This one already carries the single-child blind spot #123 left (a parent
holding one child is its own centroid, so neither half of #123's rule can see
it), so whoever takes it decides the degenerate-upper-node rule once rather than
twice.

## Review log (dev)
- 2026-09-21 dev: implemented and committed. All three superseding criteria.

  **Both halves, because the standing rule asks for both.** #096's rule is
  "refuse what cannot be rendered correctly; degrade what can — but never report
  success for either", and this shape CAN be degraded, so it is:

  1. **Degrade** — `_collect_under_single_parent` now searches upward when the
     candidate level offers no single node: `_sole_ancestor` walks levels above
     and takes the nearest one holding exactly ONE node. A level whose every
     node lost its children carries no information; the node above it does. The
     "exactly one" condition is the point — a level holding several is a choice,
     and picking one arbitrarily buries the orphans under a topic nothing says
     they belong to.
  2. **Never report success** — `build_tree` ends with `_require_reachable`,
     raising `UnreachableTree` if any level-0 node has no parent edge. The
     worker records that as a failed job with the node ids, so the CLI and the
     job record both show it.

  **The one-topic tree is exempt, and finding that out was the guard working.**
  #112's sub-rung corpus builds ONE level-0 node which IS the root — it has no
  parent because there is nothing above it. The guard caught it on the first
  run, which is a good sign about the guard and a reminder that "unparented" and
  "unreachable" are not the same predicate.

  **Testing the guard directly is deliberate, and I checked it was necessary.**
  I tried four plantable shapes (a childless level above, two childless levels,
  three nodes at one level, nodes only at level 2) and the collect or the
  recursion repaired every one — which is exactly what should happen and exactly
  why a front-door test cannot reach the state. So `_require_reachable` is
  tested directly (the #119 pattern), and a separate test asserts the PIPELINE
  always calls it — because a guard nobody reaches is not a guard, and removing
  the call was a surviving mutation until that test existed.

  Mutations, all killed: the guard call removed, the guard firing on a one-topic
  tree, the ancestor search removed, and the ancestor search accepting a
  multi-node level.

  Also carried, per the PO's note: the single-child upper node is the same
  family, and `_sole_ancestor`'s "exactly one" rule is the answer to it — a
  level with one node is a candidate, a level with several is not.

  Gate clean: `ruff format`, `ruff check --fix`, `pytest` **906 passed**.

## Review log (qa)
- 2026-09-22 qa: **PASS — to po-review.** All three superseding criteria met.

  **Doing both halves is right, and matches the standing rule rather than the
  ticket's letter.** #096's rule is "refuse what cannot be rendered correctly;
  degrade what can — but never report success for either", and this shape CAN be
  degraded. Fixing only the report would have left a repairable tree failing.

  **Verified:**
  - Mutations dev ran, re-run by me, plus one of mine: making `_sole_ancestor`
    walk DOWN instead of up fails 2, so the direction is pinned and not an
    accident of the query.
  - The "exactly one node" condition is the load-bearing part and is tested
    directly: a level offering a CHOICE is skipped. Picking one of several
    arbitrarily would bury the orphans under a topic nothing says they belong
    to — reachable, and wrong in a way nobody would ever notice.
  - **Testing the guard directly is justified, and dev showed the work rather
    than asserting it.** Four plantable shapes were tried and the collect or the
    recursion repaired every one. That is the right evidence for "a front-door
    test cannot reach this", and it is the #119 pattern applied knowingly.
  - The separate test that the PIPELINE calls the guard is what makes the direct
    test worth having — removing the call was a surviving mutation until it
    existed, and a guard nobody reaches is not a guard.
  - The one-topic exemption (#112) is correct and is pinned in both directions.
    That the guard caught it on its first run is a good sign about the guard.

  Gate: 297 files formatted, ruff clean, 912 passed.

## Review log (PO)
- 2026-09-22 PO: **PASSES — closed to done.** All three superseding criteria.

  I re-scoped this ticket away from its own filing — from "fix the branch
  condition" to "never report success over an unreachable map" — and dev
  delivered both, which is right and is what #096's rule actually says. Fixing
  only the report would have left a repairable tree failing; fixing only the
  branch would have made ONE route safe and left the unknown ones silent. This
  ticket exists because somebody found a route nobody had thought of.

  **`_require_reachable` is the piece I most wanted.** F16, F20 and F29 — the
  three worst findings of the September run — are all the same shape: a stage
  completing over a result that cannot be rendered. `build_tree` can no longer
  be one of them, whatever future route produces an orphan.

  The "exactly one node" rule in the ancestor search is better than what the
  ticket asked for. A level offering a CHOICE is not a place to collect under:
  picking one arbitrarily buries topics beneath a parent nothing says they
  belong to, which is reachable and wrong in a way nobody would ever notice.
  That rule also answers the single-child note I folded in at #123's close.

  Testing the guard directly with the four failed plant attempts written down is
  the right evidence for "a front-door test cannot reach this" — and pairing it
  with a test that the pipeline CALLS the guard is what makes the pair sound.

  No new work spun off.
