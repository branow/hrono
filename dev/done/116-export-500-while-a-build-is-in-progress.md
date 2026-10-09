---
id: 116
title: Export 500s while a build is in progress — a busy tree reads as a server fault
priority: low
size: small
depends_on: [096]
spec_refs: [build-order.md#T31, implementation-notes.md]
found_by: qa while verifying 096 on 2026-09-14
---

## Context
#096 made `export/store.load` refuse a tree whose top level holds more than one
node: `Internal` (500) "tree is not built to a single root: N nodes at its top
level". That is right for the state F20 found — a build that died half-way
leaves a permanent forest, and rendering one silently drops briefs.

It is also reachable TRANSIENTLY, with nothing broken. `build_tree` commits each
level as it recurses and only `_collect_root` collapses the top, so a `GET
/trees/{name}/export` that lands between two levels sees several nodes at the
current top level and gets a 500.

## Description
Same state, two very different meanings:
- the build died -> a real defect, 500 is right;
- the build is running -> the tree is simply not ready yet, and 500 (plus the
  logged `_logger.error` with a traceback) reads as a server fault, pages an
  operator, and pollutes the error budget.

A caller cannot tell the two apart from the response. The obvious shape is to
distinguish them: if a maintain/build job for this tree is RUNNING, answer 409
(or 503 with `Retry-After`) and a message like "tree is being rebuilt; try
again" — the tree's own job state is already in the `jobs` table; otherwise keep
the 500. Anything that reads the tree mid-build has the same ambiguity, so the
check may belong next to the loader rather than in the route.

## Description of the fix
- Decide the code: 409 ("conflict — a build is in progress") vs 503 +
  `Retry-After`. 409 matches "the resource is in a state that forbids this"; 503
  matches "come back shortly". The API conventions in `implementation-notes.md`
  should settle it rather than taste.
- Look up the tree's running job once, in the same connection the loader
  already has.
- Keep the 500 for the no-running-build case, unchanged: a permanent forest must
  stay loud.

## Acceptance criteria
- [ ] A forest with no running build for that tree still fails with the #096
      500 and its `details`.
- [ ] A forest while a maintain/build job for that tree is running answers the
      chosen non-5xx code with a clear "build in progress" message.
- [ ] Test drives both, and asserts the 5xx case still logs at error level while
      the in-progress case does not.
- [ ] `ruff format`, `ruff check --fix`, `pytest` clean.

## Review log
- 2026-09-14 PO: confirmed at `low`/`small` and kept in backlog. The filing is
  accurate — one state, two meanings — and acceptance criterion 1 is the part
  that matters: the permanent-forest 500 must stay loud when this is made
  quieter for the transient case. I verified the loud half myself on the real
  corpus at #096's close (7 nodes at level 0 -> 500 with exact `details`, CLI
  exit 1, 0 files), and it is strictly better than the silent brief-dropping it
  replaced. This is ops noise and a false page, not a correctness bug.
  Note for the planned end-to-end re-run: an export issued while a build is in
  progress will 500 with an accurate message. That is this ticket, expected, and
  not a new finding — do not re-file it.

## Review log (dev)
- 2026-09-22 dev: implemented and committed. All four criteria.

  **409, not 503 + Retry-After.** The ticket asked the API conventions to settle
  it rather than taste, and they do: `implementation-notes.md` has no
  `Retry-After` anywhere and `Conflict` (409) already exists in `errors.py` for
  "the resource is in a state that forbids this", which is exactly the case — a
  half-built tree is a state of the resource, not a busy server. 503 would also
  imply the SERVER is degraded, and it is not; only this one tree is mid-flight.
  Using the envelope we have beats inventing a second retry convention.

  The check lives next to the loader, not in the route, because the ticket is
  right that anything reading the tree mid-build has the same ambiguity — the
  CLI export path gets it for free.

  **Only an IN-FLIGHT job for THIS tree excuses a forest**, and both halves are
  pinned: a `succeeded` job still gets the 500, and another tree's running build
  still gets the 500. Without those a permanent forest could hide behind any job
  row anywhere, which would quietly undo #096.

  The ops list is the ones that RESHAPE a tree (`maintain`, `sync-tree`,
  `build-tree`, `cluster`, `cluster-briefs`, `settle`) — an `embed` or `recall`
  job running says nothing about the tree's shape.

  Tests (5 new, 944 total): the four loader cases plus the endpoint answering
  409 with the app envelope. Mutations: never checking fails 2, always
  conflicting fails 5, accepting a finished job fails 1, accepting another
  tree's job fails 1.

  Gate clean: `ruff format`, `ruff check --fix`, `pytest` **944 passed**.
- 2026-09-22 qa: **FAIL — back to todo.** The 409/500 split is right and its
  four cases are pinned. One mutation of mine survives, on the clause that
  decides which jobs count.

  **Blocking — the op filter is unpinned.**
  ```
  mutation: drop `AND op IN ('maintain', 'sync-tree', ...)` from _building
  result:   953 passed
  ```
  An `embed` or `recall` job pending for that tree would then excuse a forest.
  Those ops say nothing about a tree's SHAPE, so a permanent forest — #096's
  actual defect, a build that died and silently drops briefs — would come back
  as a polite 409 "try again shortly" for as long as any unrelated job sat in
  the queue. That is the 500 this ticket was careful to preserve, lost through
  the side door.

  Fix: a test with a running `embed` job for the tree asserting the 500 still
  fires. The `_job` helper added here already takes an op.

  **What I verified as PASSING:**
  - Gate: 300 files formatted, ruff clean, **953 passed**.
  - Choosing 409 over 503 is argued from the conventions, not taste, and I
    agree with the reasoning: a half-built tree is a state of the RESOURCE, and
    503 would say the server is degraded when only this tree is mid-flight.
    Reusing the existing `Conflict` beats inventing a retry convention.
  - Putting the check at the loader rather than the route is right — the CLI
    export path gets it for free.
  - Mutations dev ran, re-run by me: never checking fails 2, always conflicting
    fails 5, a finished job excusing it fails 1, another tree's job excusing it
    fails 1. Those last two are the ones that keep #096 loud and they are solid.
- 2026-09-22 dev: **re-picked up after qa's FAIL**; fixed. Tests only.

  qa is right and the framing is the useful part: the op filter is not a detail
  of the query, it is the clause that keeps #096 loud. Without it, any queued
  `embed` or `recall` job for the tree turns a permanent forest into "try again
  shortly", indefinitely.

  `test_a_job_that_does_not_reshape_the_tree_excuses_nothing` runs a `embed`
  job and asserts the 500 still fires. qa's mutation now fails.

  Gate clean: **954 passed**. Handing back to verifying.
- 2026-09-22 qa: **PASS — to po-review.** My mutation now fails; all five loader
  cases and the endpoint are pinned. Everything in my previous PASS list stands.

## Review log (PO)
- 2026-09-22 PO: **PASSES — closed to done.** All four criteria met.

  A 500 with a logged traceback is a promise that something is broken. It was
  being made about a tree that was simply not finished yet — paging an operator
  and spending the error budget on a race with our own builder. Same state, two
  meanings, and the job row already knew which.

  Arguing 409 from the conventions rather than taste is what I asked for, and
  the answer is right: a half-built tree is a state of the RESOURCE, 503 would
  claim the server is degraded when only this tree is in flight, and reusing
  `Conflict` beats inventing a `Retry-After` convention this API does not have.

  qa's kickback was narrow and correct. The op filter is not query detail — it
  is the clause that keeps #096 loud, and without it any queued `embed` job
  would have turned a permanent forest into an indefinite "try again shortly".
