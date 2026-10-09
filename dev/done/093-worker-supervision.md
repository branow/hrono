---
id: 093
title: Worker supervision — guard the status write, restart the thread, reclaim stranded jobs
priority: blocker
size: medium
depends_on: [092]
spec_refs: [build-order.md#T11.2, build-order.md#T57]
found_by: e2e manual QA 2026-09-03 — .e2e/FINDINGS.md F24
---

## Context
`jobs/worker.py:_execute` wraps the handler in `try/except` but calls
`self._finish(...)` — which WRITES — outside any guard. If that write raises,
the exception escapes `_execute`, escapes `run()`, and the daemon thread ends.

## Description
Observed (FINDINGS F24): `propagate` was claimed at 17:33:16 and stayed
`running` for ever. A `noop` enqueued afterwards was never claimed:

```
20:44:19 [('propagate', 'running'), ('noop', 'pending')]
20:44:34 [('propagate', 'running'), ('noop', 'pending')]
```

No log line was produced (`grep "Exception in thread"` on the server log finds
nothing), and the API kept answering reads, so nothing signalled that job
processing had stopped. The e2e run had to abandon the queue and drive ops
in-process to continue.

Work:
- Guard `_finish` and `_claim`; never let an exception leave `run()`.
- Log any unhandled worker exception (stderr + a structured line).
- Restart the loop after a failure (bounded backoff), or run it under a
  supervisor that does.
- Reclaim jobs left `running` with no live worker: a startup sweep
  (`running` -> `pending`) and/or a heartbeat column with a staleness timeout.
- Surface worker liveness (see 092's `/health`).

## Decision (2026-09-12, dev — technical call, no PO input needed)

Reclaim via **both**, because they cover different failures:
- a **heartbeat** column the worker touches on claim and on each poll, with a
  staleness timeout, so a job stranded by a dead worker is reclaimed while the
  server is still up (and `/health` reads worker liveness from the same column);
- a **startup sweep** flipping `running` -> `pending` for jobs with no live
  worker, which costs almost nothing and covers a hard crash.

Re-running a reclaimed job is acceptable: every expensive stage is content-hash
cached (`embed`, `condense`), which is exactly how the two failed `maintain`
runs recovered during the QA run — the second re-ran 2 condensations, not 92.
Ops must stay idempotent for this to hold; call that out in the ticket tests.

## Acceptance criteria
- [ ] A raising `set_status` does not kill the worker; the loop keeps claiming.
- [ ] An unhandled worker exception is logged, not silent.
- [ ] A job left `running` by a dead worker is reclaimed (test restarts a worker
      and asserts the job runs or is marked failed, never stranded).
- [ ] `ruff format`, `ruff check --fix`, `pytest` clean.

## Review log
- 2026-09-14 dev: started. Reproduced F24 first on a scratch database: with a
  foreign writer holding `BEGIN IMMEDIATE` past the ~21 s retry budget, the
  `_finish` write raised `Unavailable`, escaped `run()`, and the worker thread
  died after 23.1 s — the claimed job stayed `running` for ever and a `noop`
  enqueued afterwards stayed `pending`. Implementing the 2026-09-12 decision
  (supervisor + heartbeat + startup sweep).
- 2026-09-14 dev: implemented. Three moving parts.
  (1) `jobs/worker.py` — `run()` now starts a beat thread and enters
  `_supervise()`, a loop whose body is one claim-and-run `_cycle()`; a cycle
  that raises (the `_claim` or `_finish` write losing the database) is logged
  at ERROR with its traceback on `hrono.worker` and the loop restarts under
  bounded backoff (0.5 s doubling, capped at 5 s, reset by a clean cycle).
  Nothing can leave `run()` any more, and `_execute` clears the held job in a
  `finally` so a failed `_finish` releases it.
  (2) Heartbeat — migration `0021_job_heartbeat.sql` adds `jobs.heartbeat`;
  `store.claim_next` stamps it on claim, the beat thread re-stamps it every
  `HEARTBEAT_INTERVAL` (5 s) *while the op executes* (so a long job is never
  mistaken for a leftover), and the same beat runs `store.reclaim`, flipping
  any `running` job whose heartbeat is older than `STALE_AFTER` (60 s) back to
  `pending` with a WARNING line.
  (3) Startup sweep — `worker.reclaim_stranded(database)` requeues *every*
  `running` job and `create_app`'s lifespan calls it before the worker starts,
  covering a hard crash whose heartbeat never went stale.
  Tests (6, each verified to fail without its part of the fix): a refusing
  connection pool makes the status write raise —
  `test_a_failing_status_write_does_not_kill_the_worker` (the queue keeps
  moving, the thread lives) and `test_a_failing_status_write_is_logged`
  (an ERROR record with `exc_info`, the line F24 could not find);
  `test_a_job_stranded_by_a_dead_worker_is_reclaimed_and_rerun` seeds the row a
  dead worker leaves and asserts a later worker runs it — and asserts it runs
  **once more**, the idempotency the decision block requires (re-running is
  only safe because every expensive stage is content-hash cached);
  `test_a_running_job_is_not_reclaimed_while_its_worker_beats` is the
  false-positive guard; `test_the_startup_sweep_requeues_every_running_job` and
  `tests/server/test_startup.py::test_startup_requeues_and_runs_a_job_left_running`
  cover the sweep and its wiring.
  Verified, not just green. Before the change I reproduced F24 on a scratch
  database: worker dead 23.1 s into a foreign `BEGIN IMMEDIATE`, jobs
  `[('slow','running'), ('noop','pending')]`. After, the same script: worker
  alive, `noop` succeeded, and with production constants the stranded `slow`
  job was logged `requeued stranded job: job_ac9d…` and re-ran to `succeeded`
  32 s later. Then the real surface — `hrono serve` on a scratch db, port 8137:
  a foreign writer held the lock 25 s, `/health` stayed `200 {"status":"ok",
  …,"worker":"alive"}` throughout, the server log carried `worker cycle failed,
  restarting (1 in a row)` with its traceback (previously nothing), and a job
  enqueued after the contention ran to `succeeded`.
  Gate: `ruff format` 217 files unchanged, `ruff check --fix` all checks
  passed, `pytest` 607 passed in 31.0 s.
- 2026-09-14 dev: committed `f8e5800` ("fix: supervise the worker loop so a
  failed status write cannot silently end job processing") and moved to
  `verifying/`. The working tree keeps only the pre-existing `.e2e/` line in
  `.gitignore`, which is not mine and not in the commit.
- 2026-09-14 qa: verified — PASS, moved to `po-review/`.
  **Acceptance criteria** — all four confirmed independently, not taken on
  trust. **Decision block** — both mandated mechanisms are present: the
  heartbeat column (`0021_job_heartbeat.sql`, stamped by `store.claim_next`,
  re-stamped by `Worker._beat` every 5 s, swept at `STALE_AFTER` 60 s) *and*
  the startup sweep (`worker.reclaim_stranded`, `server/app.py:129`, before
  `worker.start()`).
  **Real flows driven.** (1) Migration on the *existing* database: copied
  `.e2e/run/.hrono/hrono.db` (at 0020, 16 jobs, 7 nodes) to scratch, opened it
  — migrated to 21, `jobs` gained `heartbeat`, `integrity_check` ok,
  `foreign_key_check` empty, row counts unchanged. (2) Startup sweep on that
  upgraded real database: seeded a `running` job with a *fresh* heartbeat, ran
  `hrono serve --port 8231`; the log carried `requeued job left running by a
  dead worker: job_stranded_qa` and the job re-ran to `succeeded` — the exact
  F24 shape, now self-healing. (3) Live heartbeat reclaim with **production**
  constants against the running server: seeded a `running` job with a 120 s-old
  heartbeat; within one beat the log carried `requeued stranded job:
  job_stale_qa` and it re-ran to `succeeded`. (4) `/health` stayed
  `200 {"status":"ok",...,"worker":"alive"}` throughout.
  **Risk 1 — false reclaim of a long op (the one that could double-issue paid
  LLM calls): PASS, proven empirically.** Production constants (beat 5 s, stale
  60 s), a 100 s op, and a foreign writer holding `BEGIN IMMEDIATE` for 77 s
  across the whole staleness window. Observed: the heartbeat froze at
  16:20:25 while the clock reached 16:21:45 (80 s stale), three
  `heartbeat failed: database is busy` WARNINGs, and **no reclaim** — the op
  ran exactly once and finished `succeeded`. The design is structurally safe
  here for two reasons worth recording: the beat thread is the *only* reclaimer,
  so a blocked beat cannot reclaim either; and `_sweep` (worker.py:152-157)
  commits `touch(held)` *before* computing the cutoff and running `reclaim`, so
  the held job is always freshly stamped in the same call that sweeps.
  `Pool.acquire` opens a new connection when idle is empty, so the beat can
  never be starved of a connection by an op holding one.
  **Risk 4 — startup-sweep blast radius: PASS.** `reclaim_stranded` requeues
  *every* `running` row with no cutoff, but 092's `db/lock.py:exclusive` is
  entered in `cli.py:115` *before* `create_app` is built, so a second server
  cannot reach the sweep. Confirmed live: a second `hrono serve` on the same
  file exited with `another hrono server is already using .hrono/hrono.db` and
  the first server's job was untouched.
  **Risk 5 — the beat as a second writer: PASS.** It takes one short
  `BEGIN IMMEDIATE` every 5 s on its own thread-local connection, `jobs` is
  indexed on `status` (0005), and when it loses the lock it logs a WARNING and
  retries. In the contention run above the op's own writes and completion were
  unaffected.
  **Tests are regression-grade — verified by mutation in a throwaway worktree
  at f8e5800.** Removing the `try/except` from `_supervise` fails
  `test_a_failing_status_write_does_not_kill_the_worker` and
  `test_a_failing_status_write_is_logged` (and reproduces F24's unhandled
  thread exception); disabling `store.touch` in `_sweep` fails
  `test_a_running_job_is_not_reclaimed_while_its_worker_beats`; neutering
  `store.reclaim` fails `test_a_job_stranded_by_a_dead_worker_is_reclaimed_and_rerun`,
  `test_the_startup_sweep_requeues_every_running_job` and
  `test_startup_requeues_and_runs_a_job_left_running`. All six earn their place.
  **Code review.** Composed, not nested: `run` -> `_supervise` -> `_cycle` ->
  `_execute`, each small and fully typed; `heartbeat_interval`/`stale_after`
  are injected seams rather than monkeypatching; `store.reclaim`'s f-string
  interpolates only literals and binds its one parameter; `_COLUMNS` is
  deliberately unchanged so `heartbeat` stays internal (minimum surface). No
  stray comments beyond `noqa` justifications, matching 092's style.
  **Security.** Nothing new logged but job ids; the ERROR traceback comes from
  the sqlite driver and carries no secret; no new input surface, no new
  dependency, roles untouched.
  **Commit.** `f8e5800` is a Conventional Commit, lowercase, one sentence, no
  body, no attribution line, and atomic — seven files, all part of this one
  change. The `.gitignore` `.e2e/` line is the QA run's, outside the commit.
  **Gate, re-run by me:** `ruff format` 217 files unchanged, `ruff check` all
  checks passed, `pytest` **607 passed** in 32.9 s.
  **Risk 2 — idempotency of a re-run: one real gap, but it is NOT this
  ticket's.** The machinery is correct; the *ops* are where the decision's
  assumption is thin. `brief` skips nodes that already have a fresh brief and
  `condense` is content-hash cached, so both re-run for free; `monitor` does
  all its work in one transaction and recomputes. **`propagate` is not
  idempotent** — and it is the op F24 actually stranded.
  `summarize/propagate.py:75-88` selects leaves purely by
  `member_signature != brief.member_signature`, and `_record`
  (`propagate.py:124-132`) never clears that condition, so a reclaimed re-run
  re-selects the same leaves, re-issues `BEST_OF` = 3 paid judge calls each,
  writes a duplicate `update_log` row, and `_bump_drift`
  (`propagate.py:163-167`) is additive (`drift = drift + ?`) — so drift
  double-counts toward `settle.py:38` `CHURN_THRESHOLD = 50` and can trigger an
  unnecessary warm reconcile. That is pre-existing debt in #087 that this
  ticket's reclaim now exposes rather than a defect in what dev built, so per
  the role rules it does not block: filed as backlog `110`.
  Also noted for the PO, not blocking: the decision block's parenthetical
  ("`/health` reads worker liveness from the same column") was not taken up —
  `server/app.py:60-64` reads `worker.is_alive()` on the supervisor thread
  only, so if the beat thread ever died the reclaimer would be gone while
  `/health` still answered `alive`. Folded into backlog `110`.
- 2026-09-14 PO: **PASS — closed to `done/`.** All four acceptance criteria are
  truthfully ticked and both mechanisms the 2026-09-12 Decision block mandated
  are present. Verified independently rather than from the Review log.
  **Gate, re-run by me:** `ruff format --check` 217 files already formatted,
  `ruff check` all checks passed, `pytest` **607 passed** in 32.1 s. Working
  tree carries only the pre-existing `.gitignore` `.e2e/` line, outside the
  commit. Diff of `f8e5800` read in full: 7 files, one coherent change.
  **Real flows driven by me**, on a fresh scratch profile (`hrono serve`, its
  own `.hrono/hrono.db`, migrated to 21, `jobs.heartbeat` present):
  (1) *Live heartbeat reclaim at production constants* — seeded a `running`
  job with a 120 s-old heartbeat against the live server; within one beat the
  log carried `requeued stranded job: job_po_stale` and it re-ran to
  `succeeded` 4 s later. This is F24's exact shape, now self-healing, and the
  log line F24 said did not exist.
  (2) *Startup sweep* — stopped the server, seeded a `running` job with a
  **fresh** heartbeat (the hard-crash shape the staleness timeout alone cannot
  catch), restarted: `requeued job left running by a dead worker: job_po_crash`
  and `succeeded`. The two mechanisms genuinely cover different failures, as
  the Decision block argued.
  (3) *Startup-sweep blast radius* — a second `hrono serve` on the same file
  exited with `another hrono server is already using .hrono/hrono.db`, so the
  cutoff-free sweep cannot reach a peer's running jobs.
  (4) `/health` answered `200 {"status":"ok",...,"worker":"alive"}` throughout.
  **Judgement call (c) — qa's mutation testing: verified, it stands.** I
  re-ran all three mutants at `f8e5800` in a throwaway worktree and reproduced
  qa's result exactly: removing `_supervise`'s `try/except` fails
  `test_a_failing_status_write_does_not_kill_the_worker` and
  `test_a_failing_status_write_is_logged` (and raises
  `PytestUnhandledThreadExceptionWarning` — F24's silent-thread-death
  signature); dropping `store.touch` from `_sweep` fails
  `test_a_running_job_is_not_reclaimed_while_its_worker_beats`; a no-op
  `store.reclaim` fails the other three. Six tests, six earned places.
  *Methodology note for future reviews:* the venv's editable install pins
  `hrono` to `/Users/orest/repos/hrono/src`, so mutating a worktree's `src/`
  and running the repo venv's pytest silently tests the UNMUTATED main source
  and every mutant appears to survive. My first pass hit this. Run worktree
  mutations with `PYTHONPATH=<worktree>/src` and assert
  `hrono.jobs.worker.__file__` points into the worktree before trusting a
  "survived" result.
  **Judgement call (a) — does 093's premise depend on idempotency that does
  not exist? Ruling: the premise holds well enough; 093 closes, and 110 is
  promoted to `todo/` at `high`.** qa's reading of `propagate` is correct and I
  confirmed it: `_changed_leaves` selects on a signature mismatch `_record`
  never clears, and `_bump_drift` is additive. And qa is right that this is the
  sharp case — 093 makes reclaim-and-re-run a normal event, and the failed-
  `_finish` path it recovers is precisely the one where `propagate`'s writes
  are ALREADY committed (they all land in one transaction at the end), so the
  re-run duplicates rather than completes. So the Decision block's "every
  expensive stage is content-hash cached" is not true of `propagate`. It still
  does not block, for four reasons I checked rather than assumed:
  1. The counterfactual is far worse. Without 093 a stranded `propagate` stops
     the whole queue for ever, silently, and needs an operator — that is the
     blocker we are closing. With 093 the worst case is a duplicated batch of
     judge calls. Trading silent total job-processing death for a bounded cost
     leak is the right trade, not a regression.
  2. Reclaim is rare by construction and proven not trigger-happy: the beat is
     the only reclaimer and `_sweep` stamps the held job in the same call that
     computes the cutoff, so a live long op cannot be reclaimed — qa proved
     this empirically at production constants (100 s op, 77 s of lock
     contention, no reclaim) and I re-read the code path to confirm the
     ordering is structural, not lucky.
  3. The blast radius is cost and audit fidelity, not integrity. I traced both
     consequences: `update_log` currently has **no readers** (`grep` finds only
     the writer and the migration), so the duplicate row is future dashboard
     debt; and drift double-counting can only pull a warm `settle` forward,
     which `tree/settle.py` documents as "a near-no-op" over an unchanged
     corpus and which resets the counter afterwards. No corruption, no wrong
     answers, no broken incremental-update promise.
  4. It is pre-existing #087 debt. 093 exposed it; it did not cause it, and
     none of 093's own criteria touch op idempotency. Per the role rules that
     is a new ticket, not a kick-back.
  110's `priority: high` and `depends_on: [087, 093]` are both correct and I
  am keeping them; I have rewritten it to Definition of Ready (acceptance
  criteria, out of scope, and the open design question about whether recording
  the judged signature collides with #064's re-brief invalidation) and moved it
  to `todo/`.
  **Judgement call (b) — the unaddressed `/health` parenthetical. Ruling: not
  a 093 acceptance-criteria miss, but qa filed it in the wrong place; split out
  as #111.** The four acceptance criteria say nothing about `/health`, and the
  Description's actual requirement — "surface worker liveness" — is met:
  `/health` reports the worker and answers 503 when it is gone. The Decision
  block's parenthetical names a preferred *source* for that signal, not a
  mechanism the ticket must ship, and the mechanisms it did mandate (heartbeat
  column, startup sweep) are both present. So: not a fail. But the underlying
  gap is real — the reclaimer lives on the beat thread, `worker.is_alive()`
  reports the supervisor thread, and a dead beat would be a quieter replay of
  F24. Folding that into 110 was wrong bundling: 110 is about one op's write
  idempotency and would leave an observability gap hostage to an unrelated
  fix. Authored **#111** (medium, small) for it and removed the "Also in scope"
  section from 110.
