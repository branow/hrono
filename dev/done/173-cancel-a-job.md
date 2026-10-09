---
id: 173
title: cancel a job, and have its children stop too
priority: medium
size: medium
depends_on: [172]
spec_refs: [build-order.md#T57.2, implementation-notes.md]
---

## Context
`POST /jobs/<id>/cancel` — "request cancel (cascades to pending/running
children)". The `canceled` status has been in the schema since 0005 and
nothing can reach it.

A maintain over a large corpus is the operation an operator most wants to
stop: it is long, it costs LLM calls, and today the only way out is killing
the server, which strands whatever was running (#093's reclaim exists because
that happens).

## Design, to decide while implementing
- COOPERATIVE: the worker checks for a cancel request between units and stops
  cleanly. Killing a thread mid-transaction is how a database ends up
  half-written, and #092 exists because that matters here.
- A PENDING child is canceled outright; a RUNNING one is asked and stops at its
  next check; a FINISHED one keeps its outcome — cancel is not an undo.
- Cancelling a child does not cancel its parent; cancelling a parent cascades
  down.
- What a partly-cancelled parent reports is #172's derivation, not a new rule.

## Acceptance criteria
- [x] Cancelling a parent stops its pending children and asks its running one.
- [x] A job that has already finished is not re-written by a cancel.
- [x] A canceled run leaves the database consistent — no half-applied stage.
- [x] The CLI can cancel (`hrono jobs cancel <id>`), and says what it did.
- [x] Admin-gated; unknown id 404.
- [x] `ruff format`, `ruff check --fix`, `pytest` clean.

## Review log
- 2026-09-26 po: authored.

- 2026-09-26 dev: done. Cooperative, and **the unit it cooperates at is a
  JOB** — that is the design decision the ticket left open and it follows from
  #092: the only way to stop a handler mid-flight is to kill the thread it is
  on, and a transaction interrupted halfway is how this database gets
  corrupted. No op polls a cancel flag, and adding one to every op signature
  buys a granularity nobody asked for.

  So a pending job is stopped outright and a running one is left to finish —
  and the response SAYS so rather than implying otherwise:

      {"job_id": "...", "stopped": 2, "running": 1, "finished": 0}
      $ hrono jobs cancel <id>
        Stopped 2 pending jobs.
        1 stage is already running and will finish.

  An operator who cancels a fan-out over forty sources and is told "39
  stopped, 1 still finishing" knows exactly where they are. "Canceled" over a
  stage still writing would be the lie.

  The update is ONE statement guarded by `status = 'pending'`, so a child the
  worker claimed between the read and the write is not overwritten — it counts
  as running, which is what it is. The mutation that guards against
  (cancelling RUNNING rows instead) fails four tests.

  **Nothing writes `canceled` to the parent's row.** #172 derives the parent
  from its children, so a parent whose children are all canceled reads as
  canceled with no second source of truth to keep in step. A test asserts both
  halves: the derived answer says canceled, the stored row still says pending.

  Driven live against a real fan-out: cancel landed while one child was
  running, `{"stopped":1,"running":1}`, and the parent settled at `failed 2/2`
  — one canceled, one that had already failed, and failure outranks cancel
  because "it broke" is what a person needs to hear first (#172's rule, doing
  its job here).

  Every test reaches the cancel AND the fan-out through the API, per #176 — the
  convention that landed two tickets ago, applied to the first ticket after it.

  Mutations, all killed: cancelling running rows instead of pending -> 4 fail;
  a parent cancelling only itself -> 4; a running stage reported as stopped ->
  2; an unknown job cancelled rather than refused -> 1.

  Gate clean: 1215 passed, 2 skipped.

- 2026-09-26 qa: PASS, to po-review, with one test added rather than a round
  trip.

  Gate at 1597d85 + the test commit: ruff clean, 1216 passed. Re-ran dev's G1
  (cancelling RUNNING rows instead of pending) — 4 fail. Drove it live: cancel
  landed mid-run, `{"stopped":1,"running":1}`, and the parent settled honestly.

  Checked the question the ticket's design raises and dev did not state: **does
  the worker stop picking up the rest?** It does, and by construction rather
  than by a new check — `claim_next` only takes `pending`, so a cancelled child
  is simply not claimable. After a cancel, `claim_next` returns None with three
  canceled children. Nothing new had to be taught to the worker, which is the
  best kind of answer.

  **The test I added.** Dev's scoping mutation (cancel every pending job rather
  than the target's children) killed tests — but only because the PARENT row is
  also pending, so the count came out 4 instead of 3. A fixture with one parent
  cannot tell "cancelled the target's children" from "cancelled everything
  pending": they look identical when nothing else is in the queue. That is the
  symmetric-fixture shape from `CONTRIBUTING.md`, met one ticket after writing
  it down. `test_cancelling_one_run_leaves_another_alone` creates two fan-outs
  and cancels one; the mutation now fails it for the right reason.

  The honesty of the response is what makes this ticket good. "Stopped 2
  pending jobs. 1 stage is already running and will finish." tells an operator
  where they are, which a bare "canceled" would not.

- 2026-09-26 po: CLOSED. `canceled` has been in the schema since migration 0005
  and nothing could reach it; it is reachable now, and it tells the truth about
  what it could not stop.

  The design decision I want kept is the one that WASN'T taken: no cancel flag
  threaded through every op signature. That would have bought interruption
  mid-op at the cost of touching seventeen handlers and inviting exactly the
  half-written transaction #092 exists to prevent. Cooperating at job
  granularity is less powerful and completely honest, and the response says
  which it is. An operator can act on "1 stage is still finishing"; they cannot
  act on a "canceled" that is not quite true.

  qa's added test is the third time this month a mutation has been killed for
  the wrong reason — the count matched by accident of the parent row. Worth
  noting that the convention we wrote in #176 and the symmetric-fixture note in
  #170 are both now being APPLIED rather than just cited, within a ticket or
  two of being written.

  T57 has one part left: #174, SSE. Then T58 and T59 close M11.
