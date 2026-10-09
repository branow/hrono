---
id: 160
title: move a section into a topic by hand, and keep it there
priority: medium
size: small
depends_on: [155]
spec_refs: [build-order.md#T48, implementation-notes.md]
---

## Context
`POST /trees/<name>/sections/<id>/move { "to_node": "..." }`. The last manual
edit, and the one an operator reaches for most: a chunk landed in the wrong
topic and they can see where it belongs. It pins, or the misfit monitor moves
it back within a batch.

## Description
- Move the section's membership to the named node in one transaction, recording
  it unforced with no attachment similarity (it was placed by a human, not by
  proximity, and pretending otherwise would corrupt the misfit rate).
- Pin the membership.
- Refuse a node in another tree, and a section that is not in this tree at all.

## Acceptance criteria
- [x] The section leaves its old node and joins the named one.
- [x] The move is pinned: a `repair` run does not migrate it back.
- [x] Its new membership carries no fabricated similarity.
- [x] The destination is a LEAF node. A section is a member of a level-0
      topic; moving one into an upper topic puts a section row under a node
      whose content is children, which is the defect #158 spent two rounds on
      (PO, 2026-09-24). Above level 0 is a 422 naming the level.
- [x] Refusals follow the ruling of 2026-09-24: an id this tree does not hold
      — another tree's node, an unknown node, a section that is not in this
      tree — is a **404**; a 422 is for a conflict between things that do both
      live here. Never a half-move.
- [x] Admin-only.
- [x] `ruff format`, `ruff check --fix`, `pytest` clean.

## Review log
- 2026-09-23 po: authored.

- 2026-09-24 po: amended before pickup. Two of #158's three rounds failed on
  the same shape — an operation written for the entity its author had in mind,
  reached by an operator holding a different one — and this ticket moves a
  section, which only a leaf can hold. Said up front so it is a criterion
  rather than a third discovery.

- 2026-09-24 dev: picked up.

- 2026-09-24 dev: done, commit 14f15b9. `edits.move_section` beside the other
  M9 operations, the same shape: the edit and the pin in one transaction.

  The PO's amendment cost one line — `require_leaf`, which #158 had already
  put beside `require_node` — and its message was rewritten to state the
  INVARIANT rather than the two operations that happened to need it first, so
  all three callers read correctly: "only a leaf topic holds sections, and
  node 3 is at level 1: an upper topic's content is the topics beneath it, not
  chunks".

  `_member_node` scopes the lookup to this tree, so a section that is real but
  belongs to another tree's map is a 404 here, per the ruling. Driven live:

      move section 2 -> node 1   200 {"from_node": 2, "pinned": true}
      move into node 3 (level 1) 422 (message above)
      move section 9999          404 "section not a member of tree default"

  and the row it wrote reads `assignment_similarity = NULL`, with the pin
  anchored at the new node.

  The interesting test is `test_a_moved_section_is_not_migrated_back`. My first
  version ran `migrate` twice — pinned, then unpinned — and the second run
  proved nothing, because the first had already emptied the node down to the
  pinned section itself, which then fitted perfectly and had nowhere better to
  go. The corpus had moved under the assertion. It now runs migrate ONCE over a
  node holding two sections where the pin is the only difference between them:
  gamma stays, alpha leaves. A run that moved neither would have been the
  vacuous version of this test, and that is exactly what the two-run version
  had become.

  Mutations, all killed: no pin -> 2 fail; an invented similarity -> 1; the
  leaf check removed -> 1; a section this tree does not hold accepted -> 1; the
  section never leaving its old node -> 1; and `migrate` no longer honouring a
  membership pin -> 1, which is the test's real subject.

  Gate clean: 1122 passed.

- 2026-09-24 qa: PASS, to po-review. Every criterion met, including the PO's
  leaf amendment. Gate re-run on a clean tree at 14f15b9: 1122 passed, ruff
  clean. Drove the endpoint on a real `hrono serve` and read the rows back —
  the move lands with `assignment_similarity = NULL`, the pin is written with
  the new node as its anchor, and both refusals return the right status with a
  message that names the level or the tree.

  Re-ran dev's Q6 (`migrate` no longer honouring a membership pin): it fails,
  so the test really is measuring the pin and not the absence of a better home
  — which matters here more than usual, because dev's first version of that
  test was vacuous for exactly that reason and they said so.

  Ran one they did not: skip `remove_member` when the section is already in the
  target node. SURVIVED, and benignly — `add_member` is `INSERT OR IGNORE`, so
  moving a section into the node it already occupies is the same no-op either
  way. Noting it because it is a surviving mutation, not because it is a gap.

  Two things found that do NOT block, both filed:

  **#164 — a parked chunk cannot be moved at all.** `_member_node` requires a
  membership, and the incubator's chunks have none, so an operator looking at a
  chunk that is in NO topic gets `404 "section not a member of tree default"`.
  That is the sibling of this ticket's use case and probably the more common
  one — a chunk in the wrong topic is at least visible. Not a defect against
  THIS ticket, whose criteria are about moving a member, and no corruption
  either way, so it is a ticket rather than a kickback.

  **#165 — a move can empty a topic, and the empty topic keeps its brief.**
  Confirmed: after moving its only section away, the node still has its brief
  and its `node://` passages, so recall can answer from the summary of a topic
  containing nothing. It self-heals — the below-two rule retires it on the next
  `repair` and #125's trigger takes the passages with it — so this is #125 with
  a clock on it, one `sync` wide. Filed `low`.

- 2026-09-24 po: CLOSED, first round — the only ticket in this milestone that
  passed on its first pass, and the reason is visible in the log: the
  amendment I made before pickup turned #158's third discovery into this
  ticket's first criterion. That is the cheapest a lesson has been on this
  board.

  T48 done, and with it the M9 manual-edit surface an operator was promised:
  rename, write a brief, annotate, pin, release, reparent, merge, dissolve,
  split, move. Every one of them pins what it touched and refuses what would
  corrupt the tree.

  **#164 promoted to `todo`, medium.** qa is right that a chunk in NO topic is
  the worse of the two cases — a chunk in the wrong topic is at least in the
  map, and a parked one is invisible to the tree until the incubator's own
  rules happen to place it. The milestone's promise is "an operator can fix
  what the machine got wrong", and today the one thing they cannot fix is the
  chunk the machine declined to place at all. It is small and it finishes the
  story.

  **#165 stays in backlog, low.** The pipeline already repairs it within one
  `sync`, and the fix wants a decision about how much a move is allowed to do,
  which is not worth a slot ahead of #164.
