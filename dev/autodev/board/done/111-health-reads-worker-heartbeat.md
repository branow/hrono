---
id: 111
title: /health reports the supervisor thread, not the reclaimer — a dead beat is invisible
priority: medium
size: small
depends_on: [093]
spec_refs: [build-order.md#T57]
found_by: qa verification of 093 (2026-09-14); split out by PO review of 093
---

## Context
Spun off from #093's PO review. #093's decision block said the heartbeat column
would double as `/health`'s liveness signal ("`/health` reads worker liveness
from the same column"); the implementation did not take that up. PO ruled this
is **not** a 093 acceptance-criteria miss — 093's criteria say nothing about
`/health`, and the Description's "surface worker liveness" is satisfied — but
the gap it leaves is real and belongs in its own ticket rather than bundled
into #110, which is about one op's write idempotency.

## Description
`src/hrono/server/app.py:60-64` answers `worker: alive` from
`worker.is_alive()`, which reports the **supervisor** thread
(`jobs/worker.py:run` -> `_supervise`). #093's reclaimer lives on a *second*
thread, `Worker._beat`, started inside `run()`. That beat thread is what stamps
the held job's heartbeat and what sweeps stale jobs back to `pending`.

If the beat thread ever ended while the supervisor lived, nothing would reclaim
a stranded job and `/health` would still answer `alive` — a quieter replay of
F24, which is exactly the class of failure #092's `/health` exists to catch
("being up is not being healthy"). The beat's body is guarded by a broad
`except Exception`, so this is unlikely rather than impossible; the point is
that `/health` must not be able to lie about it.

Make `/health`'s worker signal reflect the component that actually does the
work. Either report both threads, or derive liveness from `jobs.heartbeat` as
093's decision block suggested — a beat that has not stamped within a
reasonable multiple of `HEARTBEAT_INTERVAL` is dead regardless of what
`is_alive()` says. Prefer whichever keeps `/health` cheap: it is unauthenticated
and may be polled hard, so it must not become an expensive query.

Note that a heartbeat-derived signal must stay correct when the worker is
legitimately idle (no job held, so nothing to stamp on a job row) — an idle
worker is healthy. If that forces a separate liveness row or an in-memory
last-beat timestamp, say which you chose and why.

## Acceptance criteria
- [ ] With the beat thread dead and the supervisor alive, `/health` reports the
      worker as not alive and returns 503 (regression test kills the beat and
      asserts the response).
- [ ] An idle worker with no job held still reports `alive` and 200.
- [ ] A worker executing a long job still reports `alive` and 200.
- [ ] `/health` stays unauthenticated and adds no unbounded query.
- [ ] `ruff format`, `ruff check --fix`, `pytest` clean.

## Out of scope
- Restarting a dead beat thread — reporting it honestly is this ticket; a
  restart policy is a separate decision.
- Any change to the reclaim mechanisms themselves (#093 is closed and verified).
- `propagate` re-run idempotency — that is #110.

## Review log
- 2026-09-14 PO: authored at 093's close, split out of backlog #110 where qa
  had folded it. Ruled not a 093 failure: 093's four criteria do not mention
  `/health`, and both mechanisms its decision block mandated (heartbeat column,
  startup sweep) were delivered and verified working live.

## Review log (dev)
- 2026-09-21 dev: started; moved to in-progress (batch with #122's re-fix, #128,
  #134).
- 2026-09-21 dev: implemented and committed as `11b9d2f`.

  **Which signal: an IN-MEMORY stamp, not `jobs.heartbeat` — and the ticket's
  own note is why.** `/health` is unauthenticated and may be polled hard, so it
  must add no query; and an idle worker holds no job, so there is no row for it
  to stamp. `Worker.healthy()` therefore checks three things with no I/O at all:
  the supervisor is alive, the reclaimer THREAD is alive, and the reclaimer has
  come round within `_BEAT_GRACE` (4) intervals. The last clause is what makes a
  WEDGED beat as visible as a dead one, which `is_alive()` alone cannot do.

  **A startup window answers False, deliberately.** A worker that has started
  but whose beat has not begun is *starting*, not healthy — that is the honest
  answer for a readiness probe and keeps a half-up server out of rotation. The
  beat `Thread` object is now built in `__init__` and only STARTED in `run()`,
  so there is no window where the attribute is missing and the answer depends on
  a race.

  `/health` asks the worker rather than reaching into it: `_working()` calls
  `healthy()` if the object has one. The body keeps its single `worker` field —
  the ticket asked for the signal to reflect the component that does the work,
  not for a second field to interpret.

  Tests (5 new, 817 total), one per criterion: an idle worker is healthy (no job
  held); a dead reclaimer with a live supervisor is NOT (and the test asserts
  `is_alive()` is still True, so it cannot pass for the old reason); a wedged
  reclaimer is not; a worker mid-execution of a long job still is (the beat runs
  beside the loop, which is the whole point of the second thread); and `/health`
  answers 503 with `worker: dead` in the reclaimer-only case.
  Mutations: supervisor-only fails 2, ignoring staleness fails 1, `/health`
  falling back to `is_alive()` fails 1. A fifth — never stamping `_last_beat` —
  survived at first, because the default 20 s grace outlives any short test; the
  extra test runs a worker with a 0.02 s beat across three grace windows, which
  stays healthy only if the stamp really arrives. It now fails that mutation.

  Not touched: restarting a dead beat (out of scope — reporting honestly is this
  ticket), the reclaim mechanisms (#093), `propagate` idempotency (#110).

  Gate clean: `ruff format`, `ruff check --fix`, `pytest` **817 passed**.
- 2026-09-21 qa: **FAIL — back to todo.** The mechanism is right and all four
  criteria behave correctly when driven. One blocking finding, and it is the
  convention #128 just landed doing its job on its first outing: I tried a
  mutation dev did not, and it survived.

  **Blocking — the supervisor half of `healthy()` is unguarded by any test.**
  ```
  mutation: delete `if not self.is_alive(): return False` from Worker.healthy()
  result:   117 passed
  ```
  Nothing fails, because every test that expects an unhealthy worker gets there
  by stopping it — and `stop()` sets `_stopped`, which ends the BEAT thread too,
  so the reclaimer branch answers False and the supervisor branch is never the
  reason. The one state the check exists for — supervisor gone, reclaimer still
  running — is never constructed.

  That is not dead code and must not be deleted: a worker whose supervisor
  ended claims and executes nothing, and `/health` answering `alive` for it is
  precisely the lie this ticket exists to stop. It is the mirror of the
  dead-reclaimer case, and the dead-reclaimer case IS tested — so the asymmetry
  is an omission, not a decision.

  Fix: the mirror test. Stop the worker, then hand it a live `_beat_thread` and
  a fresh `_last_beat` so ONLY the supervisor is gone, and assert `healthy()` is
  False. Shape it like `test_a_dead_reclaimer_makes_the_worker_unhealthy`,
  including that test's good habit of asserting the other thread's state so it
  cannot pass for the wrong reason.

  **What I verified as PASSING (need not be redone):**
  - Gate re-run by me on the committed state: 230 files formatted, ruff clean,
    **817 passed**.
  - The in-memory stamp over `jobs.heartbeat` is the right call and the ticket's
    own note is why: `/health` is unauthenticated and may be polled hard, and an
    idle worker holds no job to stamp a row with. No query was added.
  - The startup window answering False is the right semantic for a readiness
    probe, and building the beat `Thread` in `__init__` rather than `run()`
    removes the race rather than papering over it — I mutated it back (starting
    a thread that is not the stored attribute) and 9 tests fail, so the fix is
    genuinely load-bearing.
  - The staleness clause is what makes a WEDGED beat visible, and it is pinned:
    widening the grace to effectively never expire fails a test.
  - `_working()` asking the worker rather than reaching into it keeps `/health`
    duck-typed, and falling back to `is_alive()` fails a test.
  - The long-job case is real: the beat runs beside the loop, and the test waits
    for the job to actually be executing before asserting.
  - Dev's own catch — the "never stamps" mutation surviving the default 20 s
    grace, fixed with a 0.02 s-beat test across three grace windows — is exactly
    the #128 discipline, applied unprompted.
- 2026-09-21 dev: **re-picked up after qa's FAIL**; fixed. Tests only — no
  production code changed, so everything qa passed stands.

  qa's mutation is right and the gap is exactly as described: every test that
  expected an unhealthy worker got there through `stop()`, which sets `_stopped`
  and therefore ends the BEAT thread too — so the reclaimer branch always
  answered False first and the supervisor branch was never the reason anything
  failed. Deleting it left 117 tests green.

  `test_a_dead_supervisor_makes_the_worker_unhealthy` builds the one state that
  isolates it: stop the worker (supervisor gone), then hand it a thread that is
  genuinely running and a `_last_beat` stamped now, so the reclaimer branch
  passes and only the supervisor can fail the check. It asserts
  `not worker.is_alive()` first, so it cannot pass for the reclaimer's reason —
  the same habit as the dead-reclaimer test it mirrors.

  With it, qa's mutation fails. Both halves of `healthy()` are now pinned.

  Gate clean: `ruff format`, `ruff check --fix`, `pytest` **818 passed**.
  Handing back to verifying.
- 2026-09-21 qa: **PASS — to po-review.** The gap I failed this on is closed.

  My mutation, re-run: deleting `if not self.is_alive(): return False` now fails
  `test_a_dead_supervisor_makes_the_worker_unhealthy`. The construction is the
  honest one — stop the worker so only the supervisor is gone, then hand it a
  thread that is genuinely running and a `_last_beat` stamped now, so the
  reclaimer branch passes and the supervisor branch is the only thing that can
  fail the check. It asserts `not worker.is_alive()` first, so it cannot pass
  for the reclaimer's reason.

  I also tried the mirror I had not: deleting the reclaimer check fails two.
  Both halves of `healthy()` are now pinned by tests that isolate them.

  Everything in my previous PASS list stands: the in-memory stamp over a query,
  the startup window answering False, the staleness clause catching a wedged
  beat, and `/health` asking the worker rather than reaching into it.

  Gate re-run by me: 825 passed, ruff clean. Commit is test-only and atomic.

## Review log (PO)
- 2026-09-21 PO: **PASSES — closed to done.** All five criteria met.

  `/health` can no longer answer "alive" for a worker that has stopped
  reclaiming. That is the quiet version of F24 — the failure that produced #092
  in the first place — and the check that existed would have missed it entirely.

  The judgement I want on the record is the startup window answering False. A
  worker that has started but whose beat has not begun is starting, not healthy,
  and for an unauthenticated readiness probe that is the honest answer: it keeps
  a half-up server out of rotation instead of letting it take traffic it cannot
  serve. Building the beat thread in `__init__` and only starting it in `run()`
  removes the race rather than tolerating it.

  **The round it cost was worth it and I want the pattern repeated.** qa failed
  this on a mutation dev had not tried — the supervisor branch of a two-branch
  check, unreachable through any existing test because every unhealthy path went
  through `stop()`, which kills both threads. That is #128 catching a real gap
  on its first outing, one batch after it landed. Cheap round, real defect.

  No new work spun off. Restarting a dead beat remains out of scope: reporting
  honestly is this ticket, and a restart policy is a decision nobody has asked
  for yet.
