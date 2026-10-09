---
id: 159
title: split a topic by hand, through the scoped mini-pipeline
priority: low
size: small
depends_on: [158]
spec_refs: [build-order.md#T47.3]
---

## Context
`POST /trees/<name>/nodes/<id>/split` — "manual split (scoped mini-pipeline)".
`repair.split` already is that pipeline: it re-clusters a node's own members
into density cores and attaches the residual noise. The endpoint is the same
operation asked for by a human instead of by the size rule.

## Design, decided
- Reuses `repair.split` unchanged, including its refusal to split a cluster
  that yields fewer than two cores — a "split" that produces one child is not a
  split, and saying so is better than silently doing nothing.
- The children are NOT pinned: the operator asked for a division, and the
  pipeline's placement of individual members is still wanted.
- Synchronous, like the other adjustments: it touches one node's members and a
  human is waiting.

## Acceptance criteria
- [x] Splitting a node replaces it with two or more children holding all its
      members.
- [x] A node that cannot be split into two cores is refused with a message
      saying so, and is left intact.
- [x] Admin-only; unknown node 404.
- [x] `ruff format`, `ruff check --fix`, `pytest` clean.

## Out of scope
Choosing the split by hand (picking which members go where) — that is member
moves, one at a time, through #160.

## Review log
- 2026-09-23 po: authored.

- 2026-09-24 dev: done, commit 0fd6cd1. `repair.split` gained one keyword,
  `over`, defaulting to MAX_CAP so the automatic repair is byte-for-byte the
  operation it was; the manual path passes 0 and lets the recipe's own floor
  decide. Without it a sixteen-member topic — the case an operator actually
  asks about — returned `()` and would have been reported as "does not
  divide", which is a lie about the reason. The refusal the ticket named is
  untouched: fewer than two density cores is not a split, whoever asked.
  Children are not pinned.

  Two refusals, two messages, because they send an operator to different
  places: BELOW the recipe's floor there is nothing to divide by (#094), and
  saying "does not divide" there would send them hunting for a boundary that
  the clusterer never got to look for.

  Driving the REAL server found what the test client could not: the endpoint
  resolved the embedding model BEFORE it confirmed the node, so `hrono serve`
  on a database with no embedding model answered an unknown node id with a 500
  `internal-error` instead of 404. The order is now node first, model second,
  in one write connection instead of two. Re-driven after the fix:
  `404 {"code":"not-found","message":"node not found in tree default: 4242"}`.

  Mutations, all killed — two of them only after the test they exposed was
  rewritten, which is the point of running them:
  - one core still counts as a split (`len(positive) < 2` -> `< 1`): SURVIVED.
    The fixture's fourteen identical vectors produce ZERO cores, so the
    boundary was never probed — the refusal at the heart of this ticket was
    unguarded. Added `test_split_refuses_a_cluster_that_yields_one_core`
    through the `core_labeler` seam, which is the only way to construct
    exactly one core; now kills.
  - split drops its noise members (`cores.get(-1, [])` -> `[]`): SURVIVED,
    because the two clean groups of eight produced no noise at all, so "holds
    all its members" was asserted over a case that could not lose any. Added
    strays between the groups (4 of 18 members now label -1); now kills.
  - the human obeys MAX_CAP (`over=0` -> `over=30`): 3 fail.
  - the node existence check removed: 1 fail.
  - the floor reported as "does not divide": 2 fail.
  - the model resolved before the node is confirmed: 1 fail.

  The real UMAP -> HDBSCAN recipe runs unseeded through every server test here
  (no `core_labeler` injected), so the seam test above is the complement to a
  real backend, not a substitute (#108).

  Filed out of scope: #161 — a `DomainError` reaches the client as
  `internal-error`, losing the code #145 gave it. That is what made the 500
  above unreadable, and it is not this ticket's to fix.

- 2026-09-24 qa: PASS, to po-review. Verified at commit 0fd6cd1 on a clean
  tree (no foreign WIP: #158 is back in todo and uncommitted). Gate re-run:
  `ruff format` no change, `ruff check` clean, 1107 passed.

  Drove the real server myself (`hrono serve` on a fresh db, port 8138): the
  unknown-node case that dev's own real-flow pass caught now answers
  `404 not-found` with the tree named in the message, and an unauthenticated
  POST is 401 before any work is done. The route rejects GET with 405, so it
  is registered exactly once and only for POST.

  Checked one thing dev's mutations did not: the `over` DEFAULT is what keeps
  the AUTOMATIC repair on its budget, and nothing about the manual path may
  loosen it. Mutation `over: int = MAX_CAP` -> `over: int = 0` fails
  `test_split_leaves_a_within_cap_cluster_alone` — the budget is guarded, and
  it is guarded by a test that predates this ticket, which is the right place
  for it.

  Verified the pin question this ticket raises and does not mention: a manual
  split RETIRES the node, and a member of it may carry a MEMBERSHIP pin whose
  `anchor_id` names that now-dead node. The `pins_follow_node` trigger clears
  only `brief` and `parenting`, so the row survives — but #155's
  `_restore_pinned` is built for exactly this, following the anchor's surviving
  COMPANY to the node that inherited it. No stranded pin, no FK dangle.

  **For PO, an observation, not a defect.** In the specific case where a split
  destroys an anchor, the company query finds nothing — every other member
  moved into the children too — so `_restore_pinned` reads "the topic is gone
  entirely" and RELEASES the pin. The topic is not gone; it was divided. The
  operator's earlier pin is dropped silently by their own later split. #155's
  rule is defensible and this may be the wanted behavior (they did ask for a
  re-division), but nothing tells them it happened. Worth a ruling before an
  operator discovers it.

  Security: admin-gated at the router, enforced server-side; a writer gets 403
  in test and an anonymous caller 401 on the live server. No secrets on any
  path, input is a path integer. Commit is conventional, atomic, and carries
  no stray changes.

- 2026-09-24 po: CLOSED. Every criterion met and verified twice on the real
  server, not just in the suite. The ticket said "reuses `repair.split`
  unchanged" and it did not — it added one keyword — and that deviation is
  RIGHT: my "unchanged" meant the refusal and the pipeline, and dev kept both
  while noticing that the size gate is the automatic repair's budget and
  nothing an operator should inherit. A sixteen-member topic reported as "does
  not divide" would have been a lie about the reason, which is the failure
  mode this product cannot afford in a hand-edit surface. The default keeps the
  automatic path identical, and a mutation proves it.

  Two mutations that SURVIVED and were then made to kill are the most valuable
  thing in this ticket's log: the refusal at its centre was unguarded, and
  "holds all its members" was asserted over a fixture that had no noise to
  lose. That is #128's discipline finding real gaps rather than confirming
  green.

  Adjacent work authored, not stuffed in here: #162 for the pin QA surfaced.
