---
id: 158
title: reparent, merge and dissolve a topic by hand
priority: medium
size: medium
depends_on: [155]
spec_refs: [build-order.md#T47.1, build-order.md#T47.2, build-order.md#T47.4]
---

## Context
Three of the four surgery endpoints. Two of them already exist as PIPELINE
primitives — `levels.migrate_children` moves a child, `repair.dissolve` retires
a node and re-places its members — so the work is the operator-facing surface,
the pin, and the one genuinely new operation (merge).

## Design, decided
- `reparent` moves a node under a named parent and pins its PARENTING, or the
  next `repair` run would move it back by proximity.
- `merge` folds several nodes into one: the members of all of them land in the
  surviving node (the lowest id, so the result is deterministic), the others
  retire, and the survivor's membership is pinned. Its brief is NOT pinned —
  the merged topic genuinely needs a new summary, and the next `brief` run
  should write one.
- `dissolve` reuses `repair.dissolve`: the node retires and its members
  re-enter the placement rule. Nothing is pinned, because the operator asked
  for the members to be re-placed, not fixed.
- All three are admin-gated and refuse to cross trees.

## Acceptance criteria
- [x] `reparent` moves the node and pins its parenting; a `repair` run then
      leaves it where it was put.
- [x] `merge` moves every member into the survivor, retires the others, and
      leaves no orphaned brief or brief passage behind (#125).
- [x] `dissolve` retires the node and re-places its members.
- [x] Reparenting a node under itself or its own descendant is a 422; under
      a node this tree does not hold (another tree's included) it is a 404
      (PO ruling, 2026-09-24) — never a corrupted tree.
- [x] `merge` and `dissolve` refuse a node above level 0 (422, naming the
      level); `reparent` refuses a parent that is not exactly one level up.
      No operation here ever leaves a node without a parent (PO, 2026-09-24).
- [x] Admin-only; unknown ids 404.
- [x] `ruff format`, `ruff check --fix`, `pytest` clean.

## Out of scope
Manual split (#159), section move (#160).

## Review log
- 2026-09-23 po: authored.

- 2026-09-23 dev: all three in `edits.py` beside the M9 operations, each
  pinning exactly what the ticket decided and nothing more — reparent pins
  parenting, merge pins the survivor's membership but NOT its brief (a merged
  topic needs a new summary), dissolve pins nothing and releases any membership
  pins on the members it frees, because the operator asked for a re-placement.

  Two refusals worth naming: a node cannot become its own parent, and cannot be
  hung under its own descendant. A cycle there does not fail loudly — it
  detaches a whole subtree from the root and the export simply stops mentioning
  it, which an operator would discover weeks later.

  Mutations run, all killed: a reparent allowed to form a cycle -> 1 fail; the
  survivor depending on the caller's order -> 1; a merged-away node not retired
  -> 2 (its brief outliving it, #125); a merge not pinning -> 1; a reparent not
  pinning -> 1.

- 2026-09-24 qa: FAIL, back to todo. Gate is clean in isolation (worktree at
  6bd8239, concurrent #159 WIP kept out: `ruff format` no change, `ruff check`
  clean, 1096 passed / 1 skipped). Two of dev's stated mutations reproduce
  (cycle check removed -> 1 fail; survivor by caller order -> 1 fail), so the
  list is honest as far as it goes. Three defects it does not reach:

  **F1 — `dissolve` is a silent no-op on any real topic (blocking).**
  `repair.dissolve` (`src/hrono/cluster/repair.py:229`) is the BELOW-TWO
  retirement rule: `if store.member_count(conn, node_id) >= 2: return False`.
  `edits.dissolve` (`src/hrono/edits.py:174`) calls it unconditionally, ignores
  the bool, and reports success anyway. Observed on a 2-member node:
  `200 {"node_id": 2, "members_replaced": 2}` while the node is STILL PRESENT
  with both members still in it — and `edits.dissolve:182` has already released
  their MEMBERSHIP pins on the way past. min_cluster_size is 5, so every real
  topic takes this path: the operator is told a topic was dissolved, the topic
  is untouched, and their pins are gone. Fails AC "dissolve retires the node
  and re-places its members". The endpoint must either drive a retirement that
  works at any member count, or refuse loudly — never 200 over a no-op.

  **F2 — `merge` deletes another tree's membership (blocking).**
  `src/hrono/edits.py:145` — `DELETE FROM node_members WHERE section_id = ?`.
  The PK is `(node_id, section_id)`, so a section that is also a member in a
  SECOND tree loses that row too. Observed: other tree's member count 1 -> 0
  after a merge in `default`. Use `store.remove_member(conn, node_id,
  section_id)`, which scopes by node and refreshes the signature, instead of
  raw SQL.

  **F3 — the cross-tree test does not test cross-tree.**
  `test_a_node_from_another_tree_is_refused` passes `{"to": 99999}` — an id
  that exists in no tree. Nothing on this ticket exercises a real node of
  another tree. Driven with one: reparent returns **404**, while the AC says
  422. The 404 is defensible (`require_node`: "a node of ANOTHER tree is not
  found here"), so this is also a ticket question — flagged for PO below — but
  the test must use a real foreign node either way, and `merge` needs the same
  case, which nothing covers.

  **F4 — the dissolve test asserts half the state it built.**
  It checks the node is gone and nothing is pinned, never that the member found
  a new home. Mutation dev did not try: make `repair.dissolve` skip
  `placement.assign_or_park` entirely — 9/9 still green. Same shape as #125 and
  #128. Assert the freed section's new node id.

  **F5 — `members_replaced` overstates (minor).** It is the member count taken
  before the call, not what was re-placed or parked. Report what actually
  happened, once F1 makes that a real number.

  **F6 — no test drives the AC's own claim** that "a `repair` run then leaves
  it where it was put"; only the pin row is asserted. #157's harness makes this
  a thin addition.

  **For PO, not dev:** the AC says a node under a node in another tree is 422,
  the code says 404 by a documented rule. Settle which, so the fix is not a
  guess.

- 2026-09-24 po: ruling on qa's F3 question, so dev does not guess.
  **404 is correct; the acceptance criterion is what was wrong.** `require_node`
  states the rule — "a node of ANOTHER tree is not found here, however real it
  is" — and every M9 edit already follows it. A 422 for the cross-tree case
  would mean the API answers differently depending on the contents of a tree
  the caller did not ask about and may not be allowed to see, and the same id
  would return two different statuses for reasons invisible from the request.

  AC amended, and it is the only thing about F3 that changes: **422 is for a
  conflict between ids that both exist IN THIS TREE** — a node under itself, or
  under its own descendant — and **404 is for an id this tree does not hold**,
  cross-tree included. F3's other half stands unchanged: the test must drive a
  REAL node of another tree rather than an id that exists nowhere, and `merge`
  needs the same case, which nothing covers today.

  F1, F2, F4, F5 and F6 stand as qa wrote them. F1 is the one that decides this
  ticket: an operator told a topic was dissolved, whose topic is untouched and
  whose pins are gone, is the exact failure this milestone exists to prevent.

- 2026-09-24 dev: picked up again on qa F1-F6 and the PO ruling.

- 2026-09-24 dev: fixed, commit 77c8301. All six qa findings, under the PO's
  ruling on F3.

  **F1** was a layering mistake, not a missing check. `repair.dissolve` is the
  automatic repair's BELOW-TWO RULE wrapped around an operation, and this
  endpoint wanted the operation. Split into two: `repair.retire` retires a node
  and re-places every member, and `repair.dissolve` is that rule calling it.
  The automatic path is unchanged — same guard, same bool — and the operator's
  path no longer inherits a size question nobody asked it. Driven on a real
  server against a six-member topic: `200 {"joined": 6}`, node gone, all nine
  sections in the surviving node. Before the fix the same call answered
  `200 {"members_replaced": 6}` over a node it had not touched.

  **F5** fell out of F1 rather than being patched on: `retire` counts what
  `assign_or_park` actually did, so the body is `{"joined", "parked",
  "skipped"}` and a chunk that found nowhere above TAU is reported as PARKED
  instead of being counted as a placement (#133). A test asserts a real parked
  pair, not a zero.

  **F2** — `store.remove_member(conn, node_id, section_id)` instead of raw
  `DELETE ... WHERE section_id = ?`. It scopes by node and refreshes the
  signature, both of which the raw statement skipped.

  **F3** — both halves. The test now builds a REAL node in a second tree and
  drives reparent and merge at it, and asserts the PO's ruling: 404 for an id
  this tree does not hold, 422 kept for the cycle cases where both ids are
  this tree's.

  **F4** — the dissolve tests assert where each member LANDED, by node id, not
  merely that the node died.

  **F6** — `test_a_reparented_node_survives_the_pipeline` runs the real
  `migrate_children` after the reparent and asserts 0 moves, then unpins and
  re-runs and asserts 1. The fixture gained a fourth topic and brief vectors so
  the corpus genuinely WANTS the node back; without the second half this test
  would have passed over a corpus with nowhere better to go (#136).

  Also carried, because the AC "unknown ids 404" was not true on a real
  server: `dissolve` resolved the embedding model BEFORE confirming the node,
  so `hrono serve` with no model registered answered an unknown id with a 500.
  Same fix and same shape as #159's. Its own regression test builds a server
  with no model, which is the only way the test client can see it.

  Mutations, all killed:
  - dissolve routed back through the below-two rule -> 3 fail.
  - merge deleting membership by section alone -> 1 fail.
  - the node lookup ignoring the tree -> 1 fail.
  - retire never re-placing a member -> 3 fail.
  - every member reported as placed -> 1 fail.
  - reparent moving without pinning -> 2 fail (including the pipeline test,
    which is the one that proves the pin buys something).
  - dissolve resolving the model before confirming the node -> 1 fail.

  Gate clean on a clean tree: 1112 passed.

- 2026-09-24 qa: FAIL, back to todo. F1-F6 are all genuinely fixed — I re-ran
  the F2 mutation (merge deleting by section alone) and it fails as dev said,
  the gate is clean on a clean tree (1112 passed), and a real server drives
  the good paths correctly: reparent returns `{"pinned": true}`, a cycle is
  refused `422 "that parent is below this node"`, and dissolving a six-member
  topic really does retire it now.

  What none of us checked, either round: **these three operations assume the
  node is a LEAF, and nothing stops an operator using them on a topic higher
  up.** A node above level 0 carries its payload in `node_children`, not
  `node_members`, and every one of these operations handles only the latter.

  **G1 — `merge` orphans the loser's children (blocking).**
  `edits.merge` moves `node_members` and then `store.delete_node`s the loser,
  whose `node_children` rows cascade away with it. Observed on the two level-1
  parents in the surgery fixture: after the merge, `third` and `fourth` have no
  parent at all. `attach_orphans` collects orphans at **level 0 only** —
  `levels.py:133` and `build_tree.py:107` both hardcode it — so a leaf is
  re-parented on the next `sync` by proximity, silently, to somewhere the
  operator did not choose; a node at level 1 or above is orphaned with NO
  collector anywhere, which is unreachable from the root and absent from the
  export. That is the exact harm `reparent`'s own cycle guard exists to
  prevent, arriving through the door beside it.

  **G2 — `dissolve` does the same, and reports nothing (blocking).**
  `repair.retire` re-places `store.node_member_rows`. An upper topic has no
  member rows — its children are its content — so dissolving one deletes it,
  re-places nothing, and detaches the subtree. Observed: dissolving
  `other_parent` returned `200 {"joined": 0, "parked": 0, "skipped": 0}` while
  `third` and `fourth` lost their parent. The honest new counts from F5 make
  this visible in the body, which is the one good thing here: a response that
  says it moved nothing, after an operation the operator was told succeeded.

  **G3 — `reparent` enforces no level (blocking).**
  `POST /nodes/<leaf>/reparent {"to": <another leaf>}` -> **200**. A level-0
  node now hangs under a level-0 node, and it is PINNED there, so the pipeline
  will not undo it. `0012_node_children.sql` states the invariant that a parent
  is one level up; a single keystroke breaks it, permanently, by design of the
  pin.

  **G4 — `merge` enforces no level either (blocking).**
  Merging a leaf with a level-1 parent -> **200**. The survivor is the LEAF
  (lowest id wins, which is deterministic but says nothing about which node is
  the right KIND), the parent retires taking its children with it, and a
  level-0 node is left holding what used to be a branch.

  **What must change.** All four are the same missing rule: an operation that
  moves a node's contents must handle the contents that node actually has, and
  a relationship between two nodes must respect their levels. Two ways:

  - **Refuse.** Reject a node above level 0 for merge and dissolve, and require
    `parent.level == node.level + 1` for reparent. Smallest change, no new
    behavior, and it never corrupts the tree.
  - **Carry.** Move the loser's `node_children` to the survivor in a merge, and
    re-place a retired upper node's children through `attach_orphans`' rule in
    a dissolve.

  **For PO, and it decides which:** the ticket says "fold several topics into
  one", and an upper node IS a topic — so "refuse" narrows what was authored.
  I lean refuse HERE plus a follow-up ticket for upper-level surgery, because
  "carry" needs the re-placement rule one level up and a decision about what a
  dissolved upper topic's children should attach to, which is a design
  conversation and not a fix. Please rule before dev starts.

- 2026-09-24 po: ruling on G1-G4. **Refuse, and this ticket is leaf-only.**

  "Carry" is the better product answer and it is not a fix — it needs the rule
  for where a dissolved upper topic's children attach, which is
  `attach_orphans`' rule generalized above level 0, and #114 deliberately
  stopped that rule at level 0. Deciding it inside a ticket that is already on
  its third round would be the third guess in a row about something nobody has
  settled. Authored as #163.

  For THIS ticket, add the rule and nothing else:
  - `merge` and `dissolve` refuse a node above level 0 (422), with a message
    that says these operate on leaf topics and names the node's level, so the
    operator is not left guessing which of their ids was wrong.
  - `reparent` requires `parent.level == node.level + 1` (422). It stays usable
    at every level, because moving a child between parents one level up is
    exactly what it is for and it breaks nothing.

  A refusal that leaves the tree intact is worth more than an operation that
  half-works, and the export going quiet about a subtree is the kind of defect
  this board has twice found weeks late (#114, #125).

  AC amended below.

- 2026-09-24 dev: picked up on G1-G4 under the PO ruling (refuse).

- 2026-09-24 dev: G1-G4 fixed, commit 711a99e. The PO ruled refuse, and the
  four findings turned out to be one missing rule stated twice.

  `require_leaf` sits beside `require_node` and says why in the one place both
  callers read: a leaf topic's content is its sections, an upper topic's is its
  children, and `merge`/`dissolve` move only the first. `reparent` keeps
  working at every level and gains the invariant 0012_node_children.sql states
  — a parent is exactly one level up.

  Driven on a real server, all three refusals with the tree untouched after:

      merge [3, 4]      -> 422 "this operates on leaf topics, and node 3 is at
                           level 1: merging or dissolving a topic above the
                           leaves would detach every topic beneath it"
      dissolve 4        -> 422 (same rule, same message)
      reparent 2 -> 1   -> 422 "a parent sits exactly one level up: node 2 is
                           at level 0, so its parent must be at level 1, and
                           node 1 is at level 0"

  Every message names the ids and the levels, because the operator's next
  question is "which of mine was wrong" and a refusal that does not answer it
  costs them the same trip twice.

  Mutations. Five run, one SURVIVED and was made to kill:
  - the leaf refusal removed -> 3 fail.
  - the one-level-up rule removed -> 1 fail.
  - merge no longer checking -> 2 fail; dissolve no longer checking -> 1 fail.
  - `above != own + 1` weakened to `above < own + 1` — a parent MORE than one
    level up allowed: SURVIVED. The rule was only half-guarded; the fixture had
    nothing above level 1, so "exactly" was never tested against a grandparent.
    Added one at level 2 and the leaf-under-grandparent case; now kills.

  Gate clean: 1116 passed.

- 2026-09-24 qa: PASS, to po-review. Third round; G1-G4 are closed and the
  earlier F1-F6 still hold.

  Gate re-run on a clean tree at 711a99e: format no change, check clean, 1116
  passed. Drove all three refusals on a real `hrono serve` and read the tree
  afterwards — nodes and edges identical to before the three calls, and every
  message names both ids and both levels, which is what an operator needs to
  know which of their arguments was wrong.

  Re-ran the mutation dev reported as SURVIVED-then-fixed (`above != own + 1`
  weakened to `<`): it fails now, so the grandparent case is really guarded.

  Ran one they did not: move `require_leaf` out of the up-front validation loop
  and into the mutation loop. It SURVIVED, and benignly — the endpoint runs
  inside `db.write()`, so the refusal rolls back a partial merge either way. I
  checked that directly rather than assuming: a refused three-node merge leaves
  both survivors' members and every pin exactly as they were. Worth naming
  because the safety is the TRANSACTION, not the ordering — `edits.merge` is
  correct only when called inside one, which today is the only way it is
  called.

  Also verified a path with no test: a THREE-node merge. It works — all three
  sections land in the lowest id and both losers retire.

  **One gap, for the PO to weigh rather than a fourth round.** Every merge test
  uses exactly two nodes, so the AC's own plural ("retires the OTHERS") is
  unguarded; the loop over `rest` could regress to handling one and the suite
  would stay green. The behavior is correct today — I drove it — so this is
  missing regression cover, not a defect. It is one line in an existing test,
  and #163 rewrites this function to carry children anyway.

- 2026-09-24 po: CLOSED. Three rounds, and each one found something the round
  before could not have: the first that `dissolve` did nothing on any real
  topic, the second that all three operations assumed a leaf, the third that
  the "exactly one level up" rule was only guarded downward. None of those
  would have been found by reading the diff — the first came from driving a
  two-member node, the second from asking what these operations DO with a node
  whose content is children, the third from a mutation. That is the process
  working, not failing.

  On the merge-arity gap: not worth a fourth round. The behavior is verified
  working, the miss is regression cover for a function #163 rewrites anyway,
  and I would rather that test be written against the version that carries
  children than against this one. Added to #163's acceptance criteria.

  One thing I am keeping from this ticket beyond the code: two of the three
  rounds failed on the SAME shape — an operation written for the entity the
  author had in mind, applied by an operator to the entity they had in mind.
  #160 is the next one of these. Its ticket already says "refuse a node in
  another tree"; it should also say which nodes a section may be moved INTO.
