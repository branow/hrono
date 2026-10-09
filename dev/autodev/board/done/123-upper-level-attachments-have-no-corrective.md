---
id: 123
title: An upper-level attachment below TAU is permanent and invisible
priority: high
size: medium
depends_on: [113, 114]
spec_refs: [build-order.md#T37, build-order.md#T38, clustering-lifecycle.md]
found_by: qa while verifying 114 on 2026-09-15
---

## READ FIRST — a sentence in the code you are about to edit is wrong

`cluster/levels.py`'s `attach_orphans` docstring ends: "So a poor attachment
stays **until a full rebuild re-derives the level**". That escape does not
exist. Nothing deletes an upper brief, so `_highest_brief_level` never drops
back, and `build_tree` starts there and stops — PO confirmed it empirically: a
full rebuild of the live corpus retired leaves 3, 5, 6 and minted 8, 9, 10 while
**root 7 survived untouched**. Level 1 was not re-derived.

The sentence two lines above it states the true bound correctly. **Delete or
correct the closing clause as part of this ticket** — it is the same class of
error #114 fixed (a docstring promising a corrective that does not exist), in
the same docstring, and you are the reader it was written for.

## Context

#114 attaches an orphaned level-0 node under its nearest level-1 parent, taking
the same trade #086 took at level 0: attach imperfectly rather than leave a
topic unreachable from `root.md`. That trade is right.

What is missing is the other half. At level 0 a poor placement is *meant* to be
corrected later — the misfit monitor re-checks it and repair migrates it. At
level >= 1 no such path exists, so a below-TAU attachment is **permanent and
invisible**.

Verified independently by PO at #114's review, all three legs:

| leg | finding |
|---|---|
| the flag | `node_children.attached` and `assignment_similarity` have **zero `SELECT`s** anywhere in `src/` — the only `node_children` reads are `child_id` and brief text |
| the monitor | `monitor.py` contains **no mention of `level`** at all; it measures level-0 misfits only |
| the reconcile | nothing re-clusters an existing upper level — `cluster_briefs` has one caller, inside `build_tree`'s loop, and `build_tree` starts at `_highest_brief_level` (the root, once level-1 briefs exist) and breaks immediately |

#114 corrects the false docstring that claimed otherwise. This ticket is the
corrective itself.

## Description

Give upper-level placements the same re-check level 0 gets. The harm is a topic
filed under a parent it does not belong to: it stays reachable (so this is less
severe than the unreachability #114 fixed) but it is reachable in the WRONG
place, and an agent walking the map from `root.md` is led down a branch whose
brief does not describe what it contains. The map is then confidently wrong,
which is worse per-encounter than being incomplete.

**This is deliberately NOT merged with #113, and the distinction matters.** They
are the same SHAPE — a placement flag with no reader — but different jobs:

- **#113 (level 0)** has a consumer path that already exists. `monitor._misfits`
  and `repair.migrate` are there; the flag needs reading and the misfit test
  needs to consider TAU. Small, scoped, with a measured case.
- **This ticket (level >= 1)** has no monitor at all. `monitor` would need a
  level concept, and `repair` an upper-level migrate.

Merging would turn a ready small ticket into a big design one and delay the
level-0 fix. So this DEPENDS on #113: whatever design #113 lands for reading
placement flags should be **extended upward**, not reinvented in parallel. Start
by reading #113's implementation, not by designing afresh.

## Acceptance criteria
- [ ] A level-1 parent holding a below-TAU attached child is observable —
      through the monitor's stored counts or an equivalent surfaced signal, not
      only as a column nothing reads.
- [ ] Once a better-fitting parent exists, the child moves and the flag is
      cleared; a test proves a deliberately mis-attached leaf leaves the parent
      it was attached to.
- [ ] The mechanism reuses #113's, or the ticket records why it could not.
- [ ] `ruff format`, `ruff check --fix`, `pytest` clean.

## Out of scope
- The attach-on-orphan behaviour itself (#114) — attaching imperfectly beats
  leaving a topic unreachable, and that trade is settled.
- Re-clustering upper levels wholesale. A re-check and a migrate are
  proportionate; rebuilding a level because one child is misplaced inverts the
  incremental promise, exactly as ruled on #114.

## Review log
- 2026-09-15 PO: filed at #114's review, where qa found the claimed corrective
  does not exist. Priority `medium`: the harm is a confidently-wrong branch
  rather than a missing one, and it needs #113's design first. Explicitly not
  merged with #113 — same shape, different size, and merging would delay the
  level-0 fix that is already scoped and measured.

## PO ruling (2026-09-15, at #114's close) — raised to `high`, and it is MEASURED

This was filed as a latent shape. It is not. The three attachments holding the
live map together were measured by qa and re-measured by PO:

```
7->8   sim 0.615      7->9   sim 0.594      7->10  sim 0.335      (TAU = 0.70)
```

**Every one is below TAU.** So the missing reader does not guard a hypothetical
case; it guards the only case that has ever occurred. Right now **half the real
map is held together by attachments the system itself scores as low-confidence,
with nothing able to review them.**

**The harm is also not softer than #113's, which is what I previously assumed.**
A parent's brief is written over its children, and its signature is over child
ids — so when a child set changes the parent re-briefs. A badly-attached child
therefore does not merely sit in an odd place in the tree: it **pollutes the
parent's brief content**, exactly as a forced member pollutes a leaf's. Same
harm, one level up, and equally permanent while nothing reads the flag.

`depends_on: [113, 114]` is unchanged, so dispatch will not let this jump #113
— which is right, because #113's design is the one this extends. The priority
now states its real weight instead of letting it drift in the backlog.

## Review log
- 2026-09-15 PO: `medium` -> `high`, backlog -> todo, at #114's close. The
  three live attachments are all below TAU, and the parent-re-brief path makes
  the harm equivalent to #113's rather than softer. Added the docstring
  correction at the top of this ticket, since its implementer is the reader the
  misleading sentence would mislead.

## Review log (dev)
- 2026-09-21 dev: started; moved to in-progress (batch with #122, #132, #127).
- 2026-09-21 dev: implemented and committed.

  **The false sentence is corrected first, as the ticket asked.** The
  `attach_orphans` docstring said a poor attachment "stays until a full rebuild
  re-derives the level". It does not: nothing deletes an upper brief, so
  `_highest_brief_level` never drops back and `build_tree` starts at the root
  and stops. The true bound was FOREVER, and the docstring now says so and then
  names the reader this ticket adds.

  **Extended #113's mechanism upward rather than reinventing it**, as the ticket
  required. The mapping is one-to-one:
  | level 0 (#113) | level >= 1 (this) |
  |---|---|
  | `store.forced_members` | `store.attached_children` |
  | combined-vector space | BRIEF space (`_parent_centroids`, already there) |
  | `monitor._misfits`: `best_other > own` OR forced-and-sub-TAU | `levels.upper_misfits`, same rule over child edges |
  | `repair._needs_migrate`: rate OR a forced member | `_repair_upper_levels`, rate OR an attached child |
  | `migrate` re-adds the member unforced | `store.move_child` re-adds the child unattached |
  Upper rows land in the SAME `misfit` table (it is keyed by node id, and a
  parent is a node), so one rate and one set of repairs cover the whole tree.

  **Why the attached half is load-bearing, measured in the fixture.** #114
  attaches to the NEAREST parent and `_parent_centroids` then absorbs the child
  into that parent's centroid, so `own` (0.45 in the planted case) beats every
  `best_other` (0.0). The existing rule is structurally blind to exactly the
  placements this exists to review — the same fact as #113's, one level up. The
  control test proves it: the identical child with the flag OFF is not counted.

  **Upper levels are measured in full, not sampled.** The bounded sample exists
  for thousands of sections; a level has a handful of parents, so sampling it
  would add the starvation risk (#129) for no saving.

  **`move_child` refreshes BOTH signatures** — the parent that lost a child and
  the one that gained it — because a parent's brief is written over its children
  and #064 reads the child-id signature. That is the harm this ticket is really
  about: a badly attached child does not just sit in the wrong place, it
  pollutes the parent's brief content. Tested directly.

  Tests (9 new, 801 total): sub-TAU attached child is a misfit; the same child
  unattached is NOT (the control); an attached child that actually fits is not;
  it moves once a better parent exists and the flag clears; with nowhere better
  it keeps both place and flag; both briefs re-stale on a move; plus criteria 1
  and 2 driven through the real `monitor` and `repair` OPS, not the helpers.
  Mutations, all killed: dropping the attached rule, dropping its TAU check,
  inverting the migrate comparison, keeping the flag on a move, and skipping the
  old parent's signature refresh.

  Not touched: #114's attach-on-orphan behaviour, and no wholesale re-clustering
  of upper levels — a re-check and a migrate, as the ticket scoped.

  Gate clean: `ruff format`, `ruff check --fix`, `pytest` **801 passed**.

## Review log (qa)
- 2026-09-21 qa: **PASS — to po-review.** All four criteria met, the false
  docstring is corrected, and the mechanism is #113's extended rather than a
  parallel invention — which the ticket required and which I checked line by
  line, not by reading the claim.

  **Verified independently:**
  - The one-to-one mapping holds: `attached_children` ↔ `forced_members`,
    `upper_misfits` ↔ `_misfits`, `_repair_upper_levels` ↔ `_needs_migrate`,
    `move_child` ↔ `migrate`'s `add_member(forced=False)`. Same rule, same
    either/or trigger, same flag-clearing-by-re-placement. A reader who knows
    #113 needs nothing new to read this.
  - The control test is again the one that makes it provable: the identical
    child with the flag OFF is not counted. Without it the count could have been
    geometry.
  - **`migrate_children` structurally cannot empty a parent, which I checked
    because #124 would have inherited it.** A parent's centroid is the mean of
    its children, so a single-child parent's centroid IS that child: `own` is
    1.0 and no `best_other` can exceed it. Driven — a lonely parent whose only
    child matches another parent's topic exactly: `moved=0`, the parent keeps
    its child. So this ticket cannot manufacture childless upper nodes.
  - **The corollary is a bounded blind spot, recorded not filed:** by the same
    arithmetic a single-child parent is invisible to BOTH halves of the rule
    (own = 1.0 is above TAU, and nothing can beat it), so an attachment that
    left a parent holding one child can never be reviewed. It is the same shape
    as a one-member cluster at level 0, it needs a second child to arise at all,
    and #124 already owns childless/degenerate upper nodes. Not worth its own
    card today; worth knowing if #124 is picked up.
  - Both signatures refreshed on a move is the right call and is tested
    directly. A parent's brief is written over its children, so the parent that
    LOST one is as stale as the one that gained one — missing that half would
    have left a brief describing a child that is no longer there, which is the
    same class of defect as #122's mis-citation.
  - Measuring upper levels in full rather than sampling them is right, and
    avoids inheriting #129's starvation at a level where the saving would be
    nothing.
  - Import direction checked: `monitor`/`repair` → `levels`, and `levels`
    imports neither, so the top-level imports are safe and the function-local
    imports were correctly promoted.
  - Mutations re-run by me, all killed: dropping the attached rule, dropping its
    TAU check, inverting the migrate comparison, keeping the flag on a move,
    skipping the old parent's signature refresh.

  Gate re-run by me: 810 passed, ruff clean. Commit atomic and conventional.

## Review log (PO)
- 2026-09-21 PO: **PASSES — closed to done.** All four criteria met.

  This closes the second half of a promise that shipped in a migration comment
  and then in a docstring. 0017 said a mis-placed pioneer migrates once its real
  siblings form; `attach_orphans` said a poor attachment lasts "until a full
  rebuild re-derives the level". Both were fiction, and the second was worse
  than the first because it named an escape that does not exist. It is
  corrected, and the correction is the first thing in the docstring rather than
  a footnote.

  **The measurement that made this `high` is now guarded.** All three
  attachments holding the live map together score 0.615, 0.594 and 0.335 against
  TAU 0.70 — every one below. Until this commit nothing could review any of
  them, and because a parent's brief is written over its children, each was
  quietly shaping the brief of the node above it. Half the real map was held
  together by placements the system itself scored as low-confidence, with no
  path to a second opinion. That is closed.

  I am glad the mechanism is #113's rather than a parallel one. Two
  implementations of "a placement flag with a reader" would have drifted, and
  the one-to-one mapping in the Review log means the next person reads one idea,
  not two.

  **qa's single-child blind spot: folded into #124, not a new card.** A parent
  holding one child has that child AS its centroid, so `own` is 1.0 and neither
  half of the rule can see it. It needs a second child to arise at all, it
  cannot be created by this ticket (`migrate_children` provably cannot empty a
  parent — qa drove that), and #124 already owns degenerate upper nodes. I have
  appended it there so whoever picks up #124 finds it rather than rediscovers
  it.

  No new work spun off beyond that note.
