---
id: 120
title: Pin the snapshot semantics of nodes.signature so this is not re-filed
priority: medium
size: small
depends_on: [064, 068]
spec_refs: [build-order.md#T30, build-order.md#T38]
found_by: qa while verifying 100 on 2026-09-15
---

## Context
`nodes.signature` is the content-hash signature of a node's members (#068), and
#064 decides whether a brief is stale by comparing a node's CURRENT signature
with the `member_signature` its brief was written under. So the stored value has
to equal `store.node_content_signature(conn, node_id)` at all times, or the
staleness check is answering about the wrong member set.

Recomputed every node's signature in the live re-run database
(`.e2e/run2/.hrono/hrono.db`, on a COPY, before any change of mine):

```
node 1 level 0: stored=60b816b97200b603 recomputed=60b816b97200b603  match
node 2 level 0: stored=9a51202597fdd8f0 recomputed=9a51202597fdd8f0  match
node 3 level 0: stored=c22f8f4d41701758 recomputed=aa71a64ddefc9041  MISMATCH
node 4 level 0: stored=1afd99d2138859be recomputed=a3688e9250abecbf  MISMATCH
node 5 level 0: stored=fd7783f6b8d30b46 recomputed=fd7783f6b8d30b46  match
node 6 level 0: stored=8b9219e232ddc86f recomputed=8b9219e232ddc86f  match
node 7 level 1: stored=e85534b300c4119e recomputed=e3b0c44298fc1c14  MISMATCH
```

Three of seven disagree. Found while checking #100's claim that a rename leaves
signatures untouched — which is TRUE: the renamed section's content hash is
unchanged, so the recomputed value is unchanged. What the rename exposed is that
`add_member` recomputes and rewrites the signature, so a node whose stored value
had drifted is silently CORRECTED by the next membership write, which looks like
a rename changing the signature when it is really the stale value being fixed.

## Description
Two distinct problems.

**1. Leaf signatures drift.** Nodes 3 and 4 hold a value that is not the
signature of their members. Every path that changes membership through
`store.add_member` / `add_leaf_node` recomputes it, but paths that change
membership some other way do not — a cascade delete when a section is dropped
(`reconcile._drop_path`, `store.clear_source`) removes `node_members` rows with
no recompute, which is almost certainly how these two drifted. Consequence: #064
compares against a value describing a member set that no longer exists, so a
brief can be judged fresh when its members changed, or stale when they did not.

**2. Upper-level signatures are structurally meaningless.**
`node_content_signature` reads `node_members`, which only leaf nodes have —
level >= 1 nodes hold `node_children`. So recomputing any upper node gives
`e3b0c44298fc1c14`, the SHA-256 of the empty string. Node 7's stored value came
from `replace_level`, so it is not the empty hash, but nothing can ever
recompute it consistently, and any future call to `node_content_signature` on an
upper node silently returns the empty-set hash. #064's staleness check therefore
cannot work above level 0 at all.

## Description of the fix
- Decide where the signature is authoritative and recompute it there, rather
  than at every writer: a small `refresh_signature(conn, node_id)` called after
  ANY membership change, including the cascade paths, or a derived read that
  computes it on demand and drops the stored column.
- Give upper levels a signature over their CHILD node ids (or their children's
  signatures), so the value means the same thing at every level, and make
  `node_content_signature` dispatch on the node's level rather than silently
  returning the empty hash.
- One-off: recompute every stored signature for existing databases, or accept
  that the first membership write per node corrects it (which is what happens
  today, at the cost of one spurious re-brief).

## Acceptance criteria
- [ ] For every node in a built tree, the stored signature equals a fresh
      recomputation — asserted as an invariant test after build, update and
      settle.
- [ ] Dropping a section (changed/deleted/moved path) leaves no node whose
      stored signature disagrees with its members.
- [ ] An upper-level node has a signature derived from its children, and
      `node_content_signature` never silently returns the empty-set hash.
- [ ] `ruff format`, `ruff check --fix`, `pytest` clean.

## PO investigation (2026-09-15, at #100's close) — scope CUT IN HALF

I verified both halves of this filing against a copy of `.e2e/run2/.hrono/hrono.db`.

### The leaf half is REAL, and here is the mechanism, demonstrated

Recomputing every node's signature against its members: leaf nodes **3 and 4
disagree** with their stored values. I then reproduced the cause in one
statement — took node 1 (whose signature agreed), deleted a member section, and
watched the `node_members` row cascade away while `nodes.signature` stayed
untouched. Agreement went True -> False. **Cascade deletes drift the signature**,
because the three refresh sites (`add_leaf_node`, `add_member`, `remove_member`)
are the only writers and a FK cascade goes around all three.

### The upper-level half is NOT a defect — remove it from scope

The filing says upper signatures are "structurally the empty-set hash". They are
not. Node 7 (level 1) stores **exactly the child-id signature**
`_signature(f"n{cid}" ...)` that `replace_level` writes at line 137, and it is
**not** the empty-set hash — I checked both explicitly.

The apparent disagreement is an artefact of the diagnostic: `node_content_signature`
is a LEAF function over `node_members`, and an upper node legitimately has no
members, so applying it there returns the empty-set hash and differs from the
correctly-stored value. Nothing ever stores that result.

It is not latent either. Every caller of the three members-based refreshers
targets a provably level-0 node:

| call site | why its node is level 0 |
|---|---|
| `store.add_leaf_node` | hardcodes `INSERT ... level 0` |
| `placement.py:134` (`_in_place`) | node from `membership()`, which filters `nodes.level = 0` |
| `placement.py:150` (`_sticky`) | node from `node_centroids`, which selects `WHERE level = 0` |
| `placement.py:206` (`assign_or_park`) | same `node_centroids` |
| `incubator.py:252` (`_force_assign`) | same `node_centroids` |
| `repair.py:130` (migrate) | target from the leaf centroid map |

**No production path can call the members-based refresh on a level >= 1 node.**
Do not build anything for it.

### A full rebuild does not heal this — it CONSUMES it

This is the part that sets the priority. `replace_tree` computes each label's
signature from the NEW members and hands it to `_reconcile`, which matches
labels to existing nodes **by stored signature**. A drifted node advertises a
member set that no longer exists, so at the next full build it will usually fail
to match — **minting a new node id and regenerating its brief** — and in the
unlucky case it matches the wrong label and hands that label the wrong brief.

So the fix must also say what happens to databases that have already drifted:
either a one-time reconciliation pass over stored signatures, or an explicit
statement that an existing database must be rebuilt from scratch. Pick one; do
not leave it implicit.

### Why `high`, not `medium`

The cost is not mainly LLM spend. A signature that no longer tracks its members
breaks **#064's brief-freshness invariant in both directions**: it can fire
invalidation when nothing changed (needless regeneration) and fail to fire when
something did — leaving a brief that describes members its node no longer has.
#064 and #068 are what make incremental update trustworthy, and that is the
product's differentiator. It is also not theoretical: **2 of 6 leaf nodes
drifted in a single normal run.**

## Acceptance criteria (superseding)
- [ ] A section deleted by any path (including the `_drop_path` FK cascade)
      leaves every affected node's stored signature equal to
      `node_content_signature` of its remaining members.
- [ ] A regression test drives the CASCADE path specifically — deleting a
      `sections` row, not calling `remove_member` — and fails if the refresh is
      removed.
- [ ] Existing drifted databases are addressed explicitly: either a one-time
      reconciliation, or documented as requiring a rebuild.
- [ ] Nothing is added for level >= 1 nodes (see above).
- [ ] `ruff format`, `ruff check --fix`, `pytest` clean.

## Review log
- 2026-09-15 PO: promoted backlog -> todo, `medium` -> **`high`**, title and
  scope corrected. The leaf half is confirmed with a demonstrated mechanism; the
  upper-level half is a category error and is removed from scope. Added the
  `replace_tree` finding, which is what moves the priority: a full rebuild
  consumes the drifted value as its matching key rather than healing it.
  Good catch by qa — chasing the anomaly instead of dismissing it is exactly
  right, and it is how the real defect surfaced.
- 2026-09-15 dev: **STOPPED — handing back, not implemented.** The superseding
  acceptance criteria contradict a settled design decision (#068's stable ids),
  and I measured that implementing them makes the live database WORSE. No code
  change is committed; the working tree is clean at `fd15c60`.

  **What the stored signature actually is.** It is a snapshot of the member set
  as of the last membership WRITE — not a live recomputation. That is precisely
  what makes #068 work: `split` deletes a source's sections and re-inserts them
  with NEW ids for identical content, so at the moment `replace_tree` runs, the
  node's members have *already* cascaded away. The rebuild recognises the node
  by the signature it kept THROUGH that teardown. `tests/cluster/test_stable_
  ids.py::_resplit` is exactly the "cascade delete" this ticket asks me to
  refresh after, and three tests there assert that ids and briefs survive it.

  **So I implemented the ticket and it broke them.** With the prescribed
  refresh (a sweep recomputing every level-0 signature, called where the
  cascade happens):
  `test_recluster_over_unchanged_content_keeps_node_ids`,
  `test_a_preserved_nodes_brief_survives_the_recluster` and
  `test_changed_content_mints_a_new_node_id` all fail — every node is re-minted
  and every brief regenerated, because after the delete the recomputed
  signature is the empty-set hash.

  **Measured on the real drifted database** (COPY of `.e2e/run2/.hrono/
  hrono.db`; `.e2e/` untouched, run2 mtime 2026-09-15 18:12:38 and the #122
  evidence copy 18:30:38 unchanged), running the REAL `cluster` op:

  | scenario | ids kept | retired | minted | briefs surviving |
  |---|---|---|---|---|
  | as-is (nodes 3 and 4 drifted) | 1, 2, 4, 7 | 3, 5, 6 | 8, 9, 10 | **4 of 7** |
  | #120 applied (stored := recomputed, then rebuild) | 1, 2, 7 | 3, 4, 5, 6 | 8, 9, 10, 11 | **3 of 7** |

  Node 4 is the case that decides it: its DRIFTED value `1afd99d2...` MATCHED a
  rebuilt label exactly, so it kept its id and its brief, and its members went
  6 -> 7 with the recomputed signature now equal to the stored one. The drift
  came from sections being deleted and re-ingested with identical content
  (#122), so the stale snapshot described precisely what the rebuild
  re-clustered. "Correcting" it to `a3688e92...` — the signature of its
  post-delete members — makes it match nothing, so it is retired and its brief
  is regenerated at LLM cost. The ticket's fix costs one extra node id and one
  extra paid brief on the exact database the planned maintain will run against.

  **A factual correction to the premise.** #064 is NOT affected by this. Brief
  freshness compares `briefs.member_signature(conn, node_id)` — computed ON
  DEMAND from current members, and already dispatching leaf vs upper — with the
  `member_signature` stored on the brief row. It never reads `nodes.signature`.
  `grep -rn "signature" src/` shows `nodes.signature` has exactly ONE reader:
  `store._reconcile`. So the "freshness invariant broken in both directions"
  argument does not hold; the only consumer is #068's id matching, and that
  consumer wants the snapshot.

  **What the residual defect is, if any.** A member section deleted FOR GOOD
  (its file removed, never re-ingested) leaves a snapshot naming content that no
  longer exists, so at the next rebuild that node fails to match and loses its
  id — one spurious re-brief. Fixing that requires distinguishing "deleted and
  coming back" from "deleted for good", which is only knowable AFTER the
  re-ingest, i.e. at `replace_tree` time — by which point the snapshot has
  already done its job and `replace_tree` writes the correct value anyway. I do
  not see a fix that keeps re-split id reuse; that is why I am not proposing
  one.

  **Options for the PO** (this needs a product/design call, not a dev call):
  1. **Close as not-a-defect**, and pin the semantics so it is not re-filed: a
     docstring on `nodes.signature` saying it is the member set at last WRITE
     and that a cascade delete deliberately leaves it, plus a test that asserts
     a cascade delete does NOT refresh it. Small, and I can do it in one tick.
  2. **Narrow to the deleted-for-good case** and accept one re-brief per such
     node as the documented cost.
  3. **Redesign #068's matching key** if stored == recomputed is genuinely
     wanted — e.g. match on the member content-hash SET rather than a digest,
     so a partial overlap can match. That is a redesign of stable ids, not a
     small fix, and it needs its own ticket.

  On the maintain the coordinator is gating: from this measurement the current
  database does NOT need a rebuild-from-scratch on account of signatures — it
  keeps 4 of 7 briefs as-is and would keep fewer if #120 were applied. The
  id churn it does show (3 of 6 leaves retired) comes from a full rebuild
  re-clustering a corpus that six incremental updates have moved on, which is
  inherent to rebuild-after-incremental, not to this ticket.

## PO RULING (2026-09-15) — dev's stop was CORRECT. This is not a defect.

**I was wrong, and the error was mine.** I set this ticket's priority and gated
the planned maintain on it, on the argument that a drifting signature breaks
#064's brief-freshness invariant in both directions. **That premise is false**,
and dev is right to have stopped rather than implement against it.

### The #064 claim, verified at source

There is exactly **ONE** SQL read of `nodes.signature` in all of `src/`:
`cluster/store.py:168`, inside `_reconcile`. Nothing else reads the column.

#064 freshness never touches it. `briefs.stale_or_missing` compares the stored
`briefs.member_signature` column against `briefs.member_signature(conn, node_id)`
— computed ON DEMAND from current `node_members`, and already leaf/upper aware
(it falls back to child node ids when a node has no section members). So the
sole consumer of `nodes.signature` is #068 id matching, **and id matching wants
the snapshot**.

### The snapshot is the mechanism, not an accident

`split` deletes a source's sections and re-inserts identical content under NEW
section ids, so by the time `replace_tree` runs the members have already
cascaded away. The rebuild recognises a node by the signature it **kept
through** that teardown. `tests/cluster/test_stable_ids.py::_resplit` is exactly
that cascade delete, and the three tests are not incidentally passing — a full
section teardown followed by preserved node ids has no other possible mechanism:

- `test_recluster_over_unchanged_content_keeps_node_ids` — the statement;
- `test_a_preserved_nodes_brief_survives_the_recluster` — the value of it;
- `test_changed_content_mints_a_new_node_id` — the discrimination.

A refresh-on-cascade sets the signature to the empty-set hash at delete time, so
`_reconcile` matches nothing. That is why dev's implementation broke all three.

### The A/B, re-run by me on copies of run2

| | kept | retired | minted | briefs surviving |
|---|---|---|---|---|
| as-is | 1, 2, 4 | 3, 5, 6 | 8, 9, 10 | **4 of 7** |
| #120 applied | 1, 2 | 3, 4, 5, 6 | 8, 9, 10, 11 | **3 of 7** |

Dev's numbers exactly. **Node 4 decides it**: its snapshot matched a rebuilt
label, keeping its id and its brief. Correcting the value made it match nothing
— one extra retired node and one extra paid brief. The prescribed fix is not
merely unnecessary, it is **actively worse on the real database**.

### What I got wrong, recorded so it is not repeated

I measured "stored != `node_content_signature`(current members)" and read it as
drift. The observation was right; the interpretation was not.
`node_content_signature` is **not the inverse** of the stored value — the stored
value is the member set as of the last WRITE, and recomputing it mid-teardown
legitimately disagrees. Nothing consumes the recomputation, so the disagreement
has no victim. That trap is exactly what this ticket now exists to close.

### Decision: OPTION 1 — close the defect, ship the pin

Not option 2: the deleted-for-good residual is real but has no implementable
content beyond documentation. If a section is gone for good the node's
membership genuinely changed, so a new id and a fresh brief is the HONEST
outcome, not a bug — and dev is right that "gone" cannot be told from "coming
back" until `replace_tree`, by which point the snapshot has served its purpose
and the correct value is written anyway.

Not option 3: redesigning #068's matching key would chase an aesthetic
(`stored == recomputed`) that no consumer wants, and would put a working
mechanism at risk to do it. If a real need ever appears it is its own ticket;
nothing today motivates one.

## Scope (superseding everything above)

Pin the semantics so this reading cannot be made silently again.

## Acceptance criteria (superseding)
- [ ] `nodes.signature` carries a docstring/comment at its writers stating it is
      the member set **as of the last write**, that a cascade delete
      deliberately does NOT refresh it, and that this retention is what lets a
      re-split reuse node ids (#068).
- [ ] It states explicitly that `node_content_signature(conn, node_id)` is a
      WRITE helper and is **not** expected to equal the stored value at an
      arbitrary moment — naming `_reconcile` as the only reader.
- [ ] A test asserts a cascade delete does NOT refresh `nodes.signature`, and
      fails if a refresh is added. This is the regression guard for the fix that
      must never be made.
- [ ] No behaviour change. If a test fails, the test is wrong.
- [ ] `ruff format`, `ruff check --fix`, `pytest` clean.

## Review log
- 2026-09-15 PO: dev's stop ACCEPTED as correct — this is a design call and dev
  escalated it properly rather than implementing a fix that broke three settled
  tests. Priority `high` -> `medium`, title and scope replaced: there is no
  defect, only an invariant that reads like one. PO verified the #064 claim at
  source (one reader, `_reconcile`), confirmed the three tests encode the
  snapshot mechanism, and re-ran the A/B on copies of run2 with dev's exact
  result. **The maintain is no longer gated on this** — see the board.

## Review log (dev, 2026-09-21)
- 2026-09-21 dev: picked up under the PO's superseding scope (option 1 — pin the
  semantics, no behaviour change). Committed.

  **The pin lives on `node_content_signature`**, which is where the trap is: it
  is the function a reader reaches for when asking "is the stored value right?",
  and answering that question with it is precisely the category error this
  ticket exists to prevent. Its docstring now says it is a WRITE helper, that
  `nodes.signature` is the member set as of the last WRITE, that a cascade
  delete deliberately does not refresh it, and that the retention is what lets a
  re-split reuse node ids (#068). It names `_reconcile` as the column's only
  reader and states that #064's freshness compares
  `briefs.member_signature` — computed on demand — and never touches this
  column at all.

  **The guard test is the ticket's real deliverable**, and I checked it guards
  rather than describes. `test_a_cascade_delete_does_not_refresh_the_signature`
  deletes a `sections` row directly (the FK cascade path, not `remove_member`),
  then asserts three things: the stored signature is unchanged, the membership
  row really did cascade away, and a fresh recomputation DISAGREES — the last
  one being the observation the PO originally misread as drift, now written down
  as expected rather than alarming.

  **Mutation — I added the fix that must never be made.** A migration with an
  `AFTER DELETE ON node_members` trigger refreshing `nodes.signature`:
  ```
  FAILED test_changed_content_mints_a_new_node_id
  FAILED test_a_cascade_delete_does_not_refresh_the_signature
  4 failed
  ```
  So the guard fires first and by name, and #068's three stable-id tests fall in
  behind it. Migration removed; `git status` shows only the pre-existing
  `.gitignore` change.

  No behaviour change: 825 passed, and the only source edit is a docstring.

  Not done, per the superseding criteria: nothing for level >= 1 nodes, no
  refresh anywhere, no reconciliation pass for existing databases.

  Gate clean: `ruff format`, `ruff check --fix`, `pytest` **825 passed**.
- 2026-09-21 qa: **PASS — to po-review.** All five superseding criteria met, and
  the ticket delivers what its final scope actually asked for: not a fix, a
  fence.

  **Verified:**
  - The pin is on `node_content_signature`, which is the right place — it is the
    function anyone reaches for when asking "is the stored value right?", and
    answering with it is the exact category error the PO made and then
    documented. Putting the warning on the writers instead would have missed the
    reader who needs it.
  - It states all four required things: snapshot as of the last WRITE, cascade
    delete deliberately not refreshing, the retention being what lets a re-split
    reuse node ids (#068), and `_reconcile` as the column's only reader with
    #064 explicitly not touching it.
  - I re-ran dev's mutation with a cruder trigger of my own (set the signature
    to empty on any `node_members` delete): four tests fail, the new guard among
    them. So the fence holds against more than the one shape dev tried.
  - The guard is not redundant even though #068's three tests also fire. It
    fails BY NAME — a future reader sees "a cascade delete does not refresh the
    signature" rather than three id-stability failures they then have to
    interpret, which is the whole point of a ticket whose deliverable is
    comprehension.
  - The third assertion is the one I would have asked for if it were missing:
    the recomputation DISAGREES, written down as expected rather than alarming.
    That is the observation that started this ticket, now inoculated.
  - No behaviour change: the only source edit is a docstring, 825 passed.

  Gate re-run by me: ruff clean. Commit atomic, `docs:` prefix appropriate.

## Review log (PO)
- 2026-09-21 PO: **PASSES — closed to done.** All five superseding criteria met.

  This ticket closes with no defect fixed, which is the right outcome and the
  one I got wrong twice before reaching it. I filed it as drift, raised it to
  `high`, and gated a planned maintain on it; dev stopped and measured, and the
  measurement said the "fix" would retire an extra node and pay for an extra
  brief on the real database. The invariant reads like a bug and is the
  mechanism.

  So what ships is a fence, and it is placed where I walked into the trap: on
  `node_content_signature`, the function I reached for to ask "is the stored
  value right?" — a question it cannot answer, because the stored value is a
  snapshot of the last WRITE and recomputing it mid-teardown legitimately
  disagrees. The docstring now says that, names `_reconcile` as the only reader,
  and states that #064 never touches the column.

  **The guard test is the part that makes this durable**, and qa's check of it
  is the right one: it fails BY NAME, so the next person who "fixes" the drift
  sees "a cascade delete does not refresh the signature" rather than three
  id-stability failures to interpret. qa also broke it with a cruder trigger of
  their own, so the fence holds against more than the one shape dev tried.

  The third assertion — that a fresh recomputation DISAGREES — is the whole
  ticket in one line: the observation I misread, written down as expected.

  No new work. The deleted-for-good residual stays as ruled: a section gone for
  good means the membership genuinely changed, and a new id with a fresh brief
  is the honest outcome.
