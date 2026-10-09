---
id: 164
title: an operator cannot file a parked chunk into a topic
priority: medium
size: small
depends_on: [160, 086]
spec_refs: [build-order.md#T48]
---

## Context
Filed by qa while verifying #160.

`move_section` requires the section to be a member of a node in this tree, and
a PARKED chunk is a member of nothing — the incubator holds it precisely
because no topic scored TAU for it (#086). So:

    POST /trees/default/sections/5/move {"to_node": 1}
    404 "section not a member of tree default: 5"

That is the sibling of #160's use case and arguably the more common one. A
chunk in the WRONG topic is visible but survivable; a chunk in NO topic is
invisible to the tree, and the operator who knows where it belongs is the only
one who can fix it before the incubator's own rules do.

The refusal message makes it worse by being technically true and practically
misleading: the section IS in this corpus, it just has no node.

## What it needs
- Accept a section that is parked in this tree, and `incubator.unpark` it as
  part of the move — `assign_or_park` already treats "joined" and "unparked"
  as one act, and for the same reason: a chunk left clustered AND pending is
  the state that function exists to prevent.
- Keep the 404 for a section that is genuinely not this tree's at all.
- The message should distinguish the two cases; "not a member" reads as "does
  not exist" to the person holding the id.

## Acceptance criteria
- [x] A parked section moves into a chosen leaf topic and is no longer pending.
- [x] A section belonging to no tree here is still a 404, with a message that
      says which of the two it is.
- [x] `ruff format`, `ruff check --fix`, `pytest` clean.

## Review log
- 2026-09-24 qa: filed from #160 verification.

- 2026-09-24 dev: picked up.

- 2026-09-24 dev: done, commit a-parked-chunk (see git log). The move now
  accepts a chunk from the PENDING POOL and unparks it as part of the join —
  not as a second step, because `assign_or_park` already treats those as one
  act and for the reason its docstring gives: a chunk left clustered AND
  pending is the state it exists to prevent. `from_node` is null when the
  chunk came from the pool rather than another topic, which is the honest
  answer to "where was it".

  The 404 now names both places it looked: "tree default holds no section 999:
  it is in no topic here and not in the pending pool". The old message said
  "not a member", which reads as "does not exist" to someone holding the id.

  Driven live: `{"section_id": 2, "from_node": null, "to_node": 1, "pinned":
  true}`, the pending table empty afterwards, the pin anchored at the topic.

  Mutations, all killed: the parked case refused again -> 1 fail; the unpark
  removed, leaving the chunk clustered AND pending -> 1; the existence check
  removed -> 1; everything treated as parked -> 1.

- 2026-09-24 qa: FAIL, back to todo — for one missing test, not for the code.

  The implementation is right and I verified it on a real server: a homeless
  chunk files under a topic with `from_node: null`, the pending table is empty
  afterwards, the pin is anchored, and the 404 now names both places it looked.
  Gate clean at e288a0d, 1126 passed. Re-ran dev's S2 (unpark removed) and it
  fails, so the #086 invariant is genuinely guarded — `incubator.sweep`'s own
  docstring calls "in a cluster AND pending" the other half of it, which is the
  codebase agreeing with this choice.

  **The gap: nothing tests that the pending pool is read PER TREE.** I drove it
  — a chunk parked in tree `other`, moved in tree `default`, is a 404 and the
  other tree's pool is untouched — but no test asserts it. `_is_parked` reaches
  a shared table through a tree-scoped query, and if that scope were ever lost,
  one tree's operator could pull another tree's homeless chunk into their map.
  That is the same cross-tree class as this ticket family's F2, which was a
  real defect two rounds ago.

  It is one row in the table `test_a_section_move_refuses_what_this_tree_does_
  not_hold` already loops over:

      (parked_in_another_tree, ids["first"], 404)

  plus an assertion that the other tree's pool still holds it. Sending it back
  because a verified-but-unguarded behavior with nothing queued to rewrite it
  is how a guarantee quietly stops being one — and because at one line, the
  round trip costs less than the risk.

- 2026-09-24 dev: qa's finding fixed. One row in the refusal table plus two
  assertions that the other tree keeps its chunk.

  qa was right that it was worth the round trip, and the mutation says so:
  drop the tree from `incubator.parked_batch`'s query — the pool read globally
  — and **only this new row fails**. 171 other tests in `tests/server` and
  `tests/cluster` pass over a pool that no longer belongs to any tree. That is
  a shared table reached by one scoped query with, until now, one caller and
  no guard.

  One honest note on the run: the first execution of the file after the edit
  reported this same `test_merge_leaves_another_trees_membership_alone`
  failing, and it has not reproduced since — 5 repeat runs of the file with
  the cache disabled, plus two full-suite runs, all green, and the test passes
  alone. I could not make it fail again and I am not able to explain it, so I
  am recording it rather than calling it nothing. Each test builds its own
  database under `tmp_path`, so a shared-state explanation does not fit; a
  half-written file between the edit and the run does.

- 2026-09-24 qa: PASS, to po-review. The one finding is closed and closed
  properly — dev ran the mutation I asked for and it says more than I expected:
  drop the tree from `incubator.parked_batch`'s query and 171 tests across
  `tests/server` and `tests/cluster` stay green while ONE fails. A shared table
  whose only guarantee is a WHERE clause now has a test that notices when the
  clause goes.

  Gate re-run at fc2df4a: ruff clean, 1126 passed. Commit is `test:`, which
  matches this repo's history for a test-only change, and touches nothing else.

  On dev's reported one-off failure: I ran the file eight more times with the
  cache disabled and the full suite twice more — all green, 25/25 every time.
  I cannot reproduce it either. Dev's own explanation is the only one that fits
  the facts, since each test builds its database under `tmp_path` and cannot
  see another's: the file was read between the edit and the format. Recording
  the non-reproduction rather than the theory. If it returns, it returns with
  evidence.

  I want to note what dev did here rather than what they fixed. They were sent
  back for one line, they added the line, ran the mutation that justified the
  request, and then reported a failure they could have quietly let pass — one
  that no longer happens and that nobody would have asked about. That is the
  behavior this board's process is for.

- 2026-09-24 po: CLOSED. The milestone's promise was "an operator can fix what
  the machine got wrong", and until this ticket the one thing they could not
  fix was the chunk the machine declined to place at all — the only kind that
  is invisible rather than merely misfiled. M9 is now true as stated.

  The kickback was right and I want the reason on the record, because it will
  come up again: qa sent back a CORRECT implementation for a single missing
  test, and the mutation that followed showed 171 tests passing over a pending
  pool that belonged to no tree. "The behavior is verified, ship it" would have
  left a cross-tree guarantee resting on one unguarded WHERE clause — and F2 in
  #158 was exactly that defect, reached by exactly that reasoning.

  Board is clear: `todo`, `in-progress`, `verifying` and `po-review` all empty.
  Remaining work is #163 (upper-level surgery and who collects an orphan above
  level 0), #161 (a DomainError reaching the client as `internal-error`) and
  #165, plus the 25 items backlog triage left in place on 2026-09-21.
