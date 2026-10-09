---
id: 189
title: structure surgery from the page — reparent, merge, dissolve, split, move
priority: medium
size: medium
depends_on: [188, 158, 159, 160, 163]
spec_refs: [build-order.md#T56]
---

## Context
The migrate half of T56 (#188 was the edit half). These are the operations that
move structure: unlike a rename, none of them is one node and none of them is
undone by typing the old value back. `merge` deletes nodes. `dissolve` retires
one and re-places its contents. `split` retires it and replaces it with
children. A `move` empties the topic a chunk came from.

Every one exists with tests and hard-won rules behind it: the survivor of a
merge is the lowest id so the result does not depend on the order an operator
typed (#158); dissolving the only topic at its level is REFUSED because it
would detach its children from the root (#163); a move pins, or the monitor
migrates it back within a batch and the operator watches their correction
undone (#155). None of that is re-decided here.

## Description
- On the topic page, for an admin: reparent (choose a parent), merge with
  another topic, dissolve, split. On each chunk: move it to another topic.
- **Candidates are offered, not typed.** A parent is a `<select>` of the
  topics one level up; a merge partner is a `<select>` of the topics at the
  same level. An operator typing a node id is an operator guessing, and
  `reparent` answering "a parent sits exactly one level up" is a worse way to
  learn the rule than not being offered the wrong option.
- **A destructive form needs a confirm checkbox**, refused server-side when
  absent. No JS, so no `confirm()`; a checkbox in the form is the same promise
  and it survives with scripting off.
- The DOMAIN's refusals are shown as they are. `Invalid` from `reparent`,
  `merge` or `dissolve` becomes the page's error line, not a 500 and not a
  reworded version that could drift from the rule that raised it.
- `dissolve` and `split` need an embedding model; with none, say so rather
  than 500 — and confirm the node BEFORE resolving it, which is the bug the
  API's own routes carry a comment about.
- After a merge or split the topic the operator was on may not exist any more.
  Land them somewhere real: the survivor for a merge, the tree map otherwise.

## Acceptance criteria
- [x] Reparent from the page moves the topic and pins the parenting.
- [x] The parent `<select>` offers exactly the topics one level up, and the
      merge `<select>` exactly the other topics at the same level.
- [x] Merge folds the topics and lands the operator on the SURVIVOR.
- [x] Dissolve re-places the members; dissolving the only topic at its level
      is refused with the domain's own message.
- [x] Split divides a topic and lands the operator somewhere that exists.
- [x] A chunk moves to another topic from the member list, pinned.
- [x] A destructive POST without the confirm field changes nothing.
- [x] A reader and a writer see no controls; a writer's POST is refused.
- [x] With no embedding model, dissolve/split say so and change nothing.
- [x] `ruff format`, `ruff check --fix`, `pytest` clean.

## Review log
- 2026-09-27 po: authored, as the migrate half of T56.
- 2026-09-27 dev: five POST routes (reparent, merge, dissolve, split, section
  move) behind `Admin`, plus `<select>` candidates and a confirm checkbox.
  - Candidates come from `_candidates`: parents one level up, merge partners at
    the same level, never the topic itself. The rule `edits.reparent` enforces
    is the rule the form offers, so nobody learns it from a refusal.
  - The confirm is checked SERVER-side, not hidden in the markup, so a
    hand-made POST is refused too. No JS, so no `confirm()`.
  - The domain's refusals are passed through verbatim — "a parent sits exactly
    one level up", "the only topic at its level", "too few members to divide" —
    rather than a reworded version that could drift from the rule.
  - Where the operator lands is computed: the merge SURVIVOR (which may not be
    the topic they were on), a split's first child (the one they were on has
    retired), the graph after a dissolve.
  - Mutations, all killed: confirm never required; merge landing back on the
    node; candidates offering every node; parents at the same level; the
    domain refusal replaced by a generic message; the emptied-topic note
    dropped; `Admin` -> `Writer` on the section move (this one SURVIVED at
    first — see qa).
  - Driven live on :8795: forms offered, reparent + move land with their pins,
    an unticked dissolve is refused, a ticked one retires the topic.
  - Gate: 1357 passed, 2 skipped.
- 2026-09-27 qa: verified, with one finding raised and fixed.
  - FINDING (fixed): the writer test covered ONE route (reparent), so
    `Admin` -> `Writer` on the section move survived — the route that pins a
    membership, and the one an operator would use most. Replaced with a table
    over every surgery route asserting 403 and no change. A door left ajar is
    the one nobody listed.
  - Two test expectations were mine, not the code's: reparenting an upper node
    under its own descendant is refused as a CYCLE before the level rule is
    reached, and a dissolved topic's members are re-placed OR parked — the
    placement rule's verdict is not what dissolving promises. Both are now
    asserted as the domain actually behaves, and the level rule gets its own
    case (a leaf under a leaf).
- 2026-09-27 po: accepted. T56 is complete, and with it M10 — every dashboard
  ticket from T49 to T56 is done. The surviving mutation is the one worth
  keeping in mind: a per-route permission needs a per-route test, and a single
  example of one stands for nothing.
