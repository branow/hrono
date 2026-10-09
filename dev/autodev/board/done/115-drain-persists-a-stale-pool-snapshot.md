---
id: 115
title: drain persists a pool snapshot it read before releasing the lock
priority: low
size: small
depends_on: [086, 095]
found_by: qa while verifying 095 on 2026-09-14
---

## Context
`incubator.drain` (`src/hrono/cluster/incubator.py:102-141`) follows the shape
`cluster` uses — read under the read door, reduce off the lock, re-acquire to
persist:

```python
with database.connect() as conn:
    ready = _ready(conn, tree, model_name)
...
labels = labeler(...)          # real UMAP -> HDBSCAN, no lock held
with database.write() as conn:
    ...                        # writes memberships for every row in `ready`
```

The write block trusts the snapshot: `store.add_leaf_node` /
`_force_assign` insert a membership for each section in `ready` without
re-checking that it is still pending.

Driven directly (a `core_labeler` that homes one of the pending sections
mid-run): the section ends up in TWO level-0 nodes, `[1, 2]` — the "is in 2
nodes" half of the #086 invariant.

## Description
Not reachable today: `db/lock.py` gives one server process the database file
and `jobs/worker.py` runs one job at a time, so nothing else writes
`node_members` or `pending` while a drain computes. Before #095's lock fix the
whole drain ran in one transaction, so the window is new — but the same window
already exists in `cluster/op.py:40-61`, which reads every section vector
outside the lock and persists `replace_tree` from that snapshot. This is the
codebase's settled read/compute/write shape, and the mitigation belongs to the
shape, not to one call site.

## Description of the fix
Make the persist step verify its snapshot rather than assume it, in both
places — e.g. drop from `ready` any section that gained a level-0 membership or
lost its pending row since the read, inside the write transaction. Cheap: one
`SELECT` over the pool at the top of the write block.

## Acceptance criteria
- [ ] A drain whose pool is mutated between the read and the persist never
      writes a second level-0 membership for a section, and never re-homes a
      section that has been unparked.
- [ ] Regression test drives the mutation through the `core_labeler` seam.
- [ ] `ruff format`, `ruff check --fix`, `pytest` clean.

## Decision (2026-09-14, PO — at #095's close)

**Deferral CONFIRMED. Priority `low` confirmed. Stays in `backlog/`, tagged for
M11 hardening. Scope BROADENED to one ticket covering both call sites.**

qa is right that it is unreachable today: `db/lock.py` gives one process the
database file and `jobs/worker.py` runs one job at a time, so nothing else
writes `node_members` or `pending` while a drain computes. Hardening an
unreachable path now is speculative surface, which is not how we spend.

It is also not #095's debt. `cluster/op.py` has the identical read/compute/write
window and predates this ticket; read-under-the-lock, reduce-off-the-lock,
re-acquire-to-persist is the codebase's settled shape for every heavy op
(#035/#040). #095 moving `drain` out of one long transaction was a lock-
discipline FIX, and it inherited the shape's window rather than inventing it.

So the mitigation belongs to the shape, as the ticket already argues. One
ticket, both call sites — `incubator.drain` and `cluster.op.cluster` — with the
persist step validating its snapshot inside the write transaction rather than
trusting it. Two tickets would guarantee the halves drift and leave the codebase
with one call site hardened and one not, which is worse than neither.

**The trigger to promote this is concurrency, not time.** It becomes reachable
the day anything runs a second writer — a second worker thread, a second server
process, an external writer. Whoever proposes that owns this ticket as a
precondition of the change, and should promote it then.

## Acceptance criteria (superseding the above)
- [ ] `incubator.drain`'s write block drops from its snapshot any section that
      gained a level-0 membership or lost its pending row since the read.
- [ ] `cluster.op.cluster`'s persist applies the equivalent validation to its
      own snapshot.
- [ ] Regression tests drive the mutation through the `core_labeler` seam
      (drain) and the `build=` seam (cluster), asserting no section ever lands
      in two level-0 nodes.
- [ ] `ruff format`, `ruff check --fix`, `pytest` clean.

## Review log
- 2026-09-14 PO: confirmed low and confirmed the deferral out of #095 —
  unreachable under the one-server/one-worker invariant, and the window is the
  settled shape's, not this commit's. Broadened to both call sites so the shape
  is fixed once. Stays in backlog; promote it when a second writer is proposed.

## Review log (dev)
- 2026-09-22 dev: implemented and committed. All three criteria.

  `_still_pending` re-reads the pool inside the write block and both persist
  paths — the density cores and the force-assign residuals — skip anything that
  is no longer parked. A core group whose every member found a home mints no
  node at all.

  **A re-check, not a lock**, which is the right trade for an unreachable path:
  it costs one query, changes nothing about the shape every heavy op uses (read
  under the door, reduce off the lock, re-acquire to persist), and makes the
  persist depend on the state it is persisting into rather than on a promise
  about who else is running.

  **`INSERT OR IGNORE` nearly hid the force-assign half.** My first test homed
  the stolen residual into the SAME node the force-assign would pick, and
  `_insert_member` silently absorbed the duplicate — so the mutation survived
  with the defect present. Homing it into a different node makes the second
  membership real. Worth remembering whenever a test asserts "not written
  twice" against that table.

  The forced flag matters too and is asserted: a re-force-assign would flag a
  section `forced` that had found its own home, and #113 would later "free" a
  pioneer that never was.

  Tests (3 new, 960 total), all driving the race through the `core_labeler`
  seam. Mutations: trusting the snapshot fails 2, the core path skipping the
  re-check fails 2, the forced path skipping it fails 1.

  Gate clean: `ruff format`, `ruff check --fix`, `pytest` **960 passed**.

## Review log (qa)
- 2026-09-22 qa: **PASS — to po-review.** All three criteria met, both call
  paths pinned, and the race driven through the seam as the ticket required.

  **The `INSERT OR IGNORE` catch is the most useful thing in this ticket.** A
  test asserting "not written twice" against `node_members` can be satisfied by
  the table silently absorbing the duplicate, and dev's first version was —
  the mutation survived with the defect present. Homing the stolen residual into
  a DIFFERENT node is what makes the second membership observable. That trap
  applies to any future test of that table.

  A re-check rather than a lock is the right trade for a path that is
  unreachable today: one query, no change to the shape every heavy op uses, and
  the persist now depends on the state it is persisting into rather than on a
  promise about who else is running. Mutations: trusting the snapshot fails 2,
  each path skipping the re-check fails 2 and 1, and one of mine — querying the
  wrong tree — fails 6.

## Review log (PO)
- 2026-09-22 PO: **PASSES — closed to done.** All three criteria met.

  I deferred this in September as unreachable and speculative to harden, and
  that was right at the time. What changed is the price: with the seam already
  there and the test harness warm, it is one query and three tests, and it
  removes a promise ("nothing else writes while we compute") from the set of
  things the invariant depends on. Promises about concurrency are the ones that
  quietly stop being true.

  **The `INSERT OR IGNORE` observation is worth more than this ticket.** A
  "not written twice" assertion against `node_members` can be satisfied by the
  table absorbing the duplicate rather than by the code preventing it — and
  dev's first test was exactly that, with the defect present and the suite
  green. That is a trap anyone testing membership will walk into.
