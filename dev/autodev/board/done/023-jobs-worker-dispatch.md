---
id: 023
title: jobs framework — worker loop + atomic leaf runner + op dispatch (T11.2+T11.4)
priority: high
size: big
depends_on: [022, 008]
spec_refs: [build-order.md#T11.2, build-order.md#T11.4, implementation-notes.md#jobs]
---

## Context
With the job record (#022) in place, the server needs a background worker that
actually executes jobs, and a registry that maps an op name to the code that runs
it. This is the engine of "work is a job you POST": enqueue a job, the worker
claims it, dispatches to the registered op, and records the outcome atomically.
Every M2+ op (sync T12, split T14, later embed/cluster/brief) plugs into this via
the op registry. Combines T11.2 (runner + loop) and T11.4 (op registry +
dispatch) because a runner is only testable against something to dispatch to.

## Description
1. **Op registry (T11.4)** — a data-driven map from op name to a handler
   callable (recommend `src/hrono/jobs/ops.py`), not an if/elif ladder. A handler
   is a typed callable that performs one job's work given the job + a context
   (the `Database`, and later the cipher/registries it needs). New ops (T12+)
   register an entry; the worker never branches on op name. Ship one trivial
   built-in op (e.g. `noop`, or an internal echo) so the loop is driveable and
   testable before real ops exist.
2. **Atomic leaf runner + worker loop (T11.2)** — a background task started in
   the server lifespan that polls for `pending` jobs, claims one (flip to
   `running` under the #008 `Database` single-writer lock so no double-claim),
   dispatches to the registered handler, and on return marks it `succeeded`;
   on exception marks it `failed` with the error reason (never a traceback to a
   client; never the whole batch — a failed leaf leaves other pending jobs
   untouched, per "failures leave the rest pending"). The runner executes one
   atomic unit of work per job. Bound the poll loop sanely; shut the worker down
   cleanly on server shutdown.
3. **Enqueue + observe** — an internal `enqueue(op, scope, ...)` that inserts a
   `pending` job and returns its id (ops/endpoints call this), plus minimal read
   endpoints `GET /jobs` (list; filters op/status) and `GET /jobs/<id>` (one job)
   gated `reader+` via #006. Status/JSON `snake_case`, status values kebab-case.

Keep the worker single-connection-safe: all DB access via the `Database` lock
(#008); the worker runs in the server process (single writer). No parallel op
execution needed yet (one leaf at a time is fine); note the choice.

## Acceptance criteria
- [ ] An enqueued job (via the internal `enqueue`) is picked up by the worker,
      dispatched to its registered op, and ends `succeeded`; a job whose op raises
      ends `failed` with a stored error reason and does NOT stop other pending
      jobs from running.
- [ ] The op registry is a data-driven name->handler map; a new op is a
      registration, not a branch in the worker (demonstrate with the trivial op +
      a second test op).
- [ ] Job claiming is race-safe under the single-writer `Database` lock: a job is
      claimed (pending->running) exactly once; a test that enqueues many jobs
      runs each exactly once with no double-execution.
- [ ] The worker starts with the server and shuts down cleanly on shutdown (no
      hang, no work lost mid-flight beyond the in-flight leaf).
- [ ] `GET /jobs` and `GET /jobs/<id>` return job status as JSON (reader+),
      reflect pending->running->succeeded/failed transitions, and 401/403 gate
      correctly; `GET /jobs/<unknown>` -> 404.
- [ ] Regression-grade tests drive enqueue->run->succeeded, enqueue->raise->
      failed-without-killing-siblings, the exactly-once claim under concurrency,
      registry dispatch, and the read endpoints' role/matrix. A test fails if a
      failed job blocks the queue or a job runs twice.
- [ ] `ruff format`, `ruff check --fix`, `pytest` all clean; work committed.

## Out of scope
- Scope resolution into an item set / fan-out into one leaf per item (T11.3,
  #024) — this ticket runs a single job per enqueue; the real fan-out lands with
  the scope resolver.
- Real ops (`sync` T12, `split` T14) — only a trivial built-in op to prove the
  loop.
- Parent aggregation, cooperative cancel, SSE events (T57, M11).

## Review log
- 2026-08-15 PO: authored as the M2 jobs engine. Combined T11.2 runner/loop with
  T11.4 op registry/dispatch since a runner needs a dispatch target to be
  driveable. Sized `big`; if dev finds a clean seam, landing the op registry and
  the worker loop as two commits is welcome. Fan-out/scope is #024; cancel/SSE
  are T57.
- 2026-08-16 dev: picked up (deps 022, 008 in done/), moved to in-progress.
- 2026-08-16 dev: implemented. `jobs/ops.py`: data-driven `OPS: dict[str,
  Handler]` (name -> `Callable[[Job, JobContext], None]`) with a built-in `noop`;
  `JobContext(database)` (grows with the cipher/registries later). `jobs/store.py`:
  enqueue-insert, `claim_next` (select oldest pending + flip to running, run under
  the caller's #008 Database lock so the select+update is atomic — no
  double-claim), `set_status`, `get`, `list_jobs` (op/status filters).
  `jobs/worker.py`: `enqueue(database, op, scope, ...) -> job_<uuid>` and a
  `Worker(threading.Thread)` — a daemon thread (keeps sync SQLite off the event
  loop) that polls, claims one leaf, dispatches to the registered op, marks
  succeeded, and on any exception marks failed with the reason (a failed leaf
  never stops the rest; unknown op -> failed). `server/jobs.py`: reader-gated
  `GET /jobs` (op/status filters) and `GET /jobs/{id}` (404 if absent). Worker is
  DI (`ops` param) so tests inject handlers; started in the lifespan after key
  setup and stopped+joined on shutdown. One leaf at a time (no parallel op exec
  yet — noted). Tests: `test_worker.py` (enqueue->succeeded, failing-leaf->failed
  without killing a sibling, unknown-op->failed, and exactly-once across 3
  concurrent workers proving the claim is race-safe) and `test_endpoints.py`
  (401 unauth, reader list, status filter, fetch-one with parsed scope, 404).
  Gate clean (ruff format, ruff check --fix, pytest 221 passed). Verified live:
  /jobs 401 unauth -> [] authed -> /jobs/ghost 404, worker starts with serve and
  shuts down cleanly. Scope: scope-resolution/fan-out is #024, real ops (sync
  T12) later, cancel/SSE are T57. Committed 4ff177f. Moved to verifying.
- 2026-08-16 qa: PASS -> po-review. Verified all dimensions (deep pass on the
  concurrency-critical worker; developer + security lenses). Drove the real
  server end to end: seeded a pending `noop` job, started `hrono serve`, and the
  lifespan-started background worker claimed and ran it to `succeeded` (visible
  via GET /jobs) - proving the real worker loop executes a job to completion in
  the running server. Endpoints gate correctly: unauth GET /jobs -> 401, reader
  GET /jobs -> 200, `?status=succeeded` filters, GET /jobs/ghost -> 404 (reader+
  via #006; 403 is unreachable since reader is the floor role). Clean shutdown
  verified live: SIGTERM -> the server exited cleanly with no hang and uvicorn
  logged "Application shutdown complete", confirming the lifespan `worker.stop()`
  + bounded `join(timeout=5)` (daemon thread). The op registry is a data-driven
  `OPS` name->handler map (noop built-in; tests register boom/count) - the worker
  never branches on op name. Claim safety: `claim_next` runs its select +
  conditional `UPDATE ... WHERE status='pending'` + re-read inside a single
  `database.connect()` acquisition of the #008 RLock, so it is atomic against
  other workers; independently STRESSED the exactly-once test (3 concurrent
  workers over 30 jobs, asserting each ran exactly once) 5/5 times with no
  flakiness. A failing leaf is recorded `failed` with its reason and does NOT
  stop siblings (test_a_failing_leaf_fails_without_killing_siblings: boom ->
  failed with "kaboom", noop -> succeeded); an unknown op -> failed. All DB
  access is under the single-writer lock; one leaf at a time in production (a
  single Worker), with multi-worker safety proven as a bonus. Tests are
  regression-grade and use REAL threads + REAL SQLite (not mocked). Code review
  clean: frozen JobContext, typed Handler, early returns, broad-except
  documented (a leaf failure is recorded, never a client traceback), docstrings
  only, no emojis. Minor non-blocking nit: the `status` query param in
  `server/jobs.py:list_jobs` shadows the imported fastapi `status` module, but
  that function never uses `status.HTTP_*`, so there is no bug. Commit 4ff177f
  is a proper atomic Conventional Commit. Re-ran the gate: ruff format clean (87
  files), ruff check passed, pytest 233 passed. Scope: fan-out/scope resolver
  (#024), real ops, and cancel/SSE (T57) correctly excluded.
- 2026-08-16 PO: PASS -> done. Independently stressed the concurrency-critical
  guarantees on the real worker/store (real threads + real SQLite): 4 concurrent
  Workers over 40 `count` jobs -> each ran EXACTLY once (40 distinct, none >1),
  proving the claim_next select+conditional-UPDATE under the #008 lock is
  race-safe; a `boom` job -> failed with its reason "kaboom" while all 40
  siblings succeeded (a failed leaf never blocks the queue); unknown/failed ops
  isolated. Op registry is a data-driven name->handler map (injected count/boom
  via DI, no op-name branch in the worker). qa verified the reader-gated
  GET /jobs (401/list/status-filter/404) and live server worker execution +
  clean SIGTERM shutdown (lifespan stop()+join). Ran the gate: ruff format (87
  clean), ruff check clean, pytest 233 passed. Unblocks #024 (scope resolver +
  fan-out). Minor tidy for later: the `status` query param in server/jobs.py
  shadows the fastapi `status` module (harmless, unused there) - drop
  opportunistically when #028 touches it. Closed at 4ff177f.
