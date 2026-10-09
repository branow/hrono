---
id: 008
title: DB threading model — sync route handlers can safely use the connection
priority: high
size: medium
depends_on: [002]
spec_refs: [design-sketch-v1.md, implementation-notes.md]
---

## Context
Spun off from a dev suggestion filed during #003 (backlog:
`sqlite-connection-thread-affinity`). The server opens one `sqlite3.Connection`
in the FastAPI lifespan (event-loop thread) with the default
`check_same_thread=True`. FastAPI runs **sync** path handlers in a threadpool,
so the first sync endpoint that touches `app.state.db` will raise
`sqlite3.ProgrammingError: SQLite objects created in a thread can only be used
in that same thread`. It is latent today only because no route reads the DB —
but **#006 is the first that does** (`GET/POST /users`, `DELETE /users/<name>`
call `authenticate`/`list_users`/`create_user` on the shared connection from
threadpool handlers). This must be settled before #006 lands, hence `high` and a
blocker on 006. Settling the single-writer threading model once, here, is far
cheaper than deciding it ad hoc inside the first endpoint ticket.

## Description
Give the server a defined, correct threading model for its single SQLite
connection so any route handler (sync or async) can use it without cross-thread
errors or data races, while preserving the architecture's single-writer
guarantee. Load `engineering:developer` before writing this.

**Recommended direction (default — pick this unless you can justify better):**
open the connection with `check_same_thread=False` and serialize *all* access
to it behind one lock, exposed through a small owner object (recommend a
`Database` wrapper in `src/hrono/db/`) that holds the connection + a
`threading.Lock` (or `RLock`) and offers the minimal access methods handlers
need; every read and write goes through the lock. This is correct under WAL for
a single shared connection (a lone `sqlite3.Connection` is not safe for
concurrent cross-thread use even for reads), it is the minimum surface, and it
keeps "one server, one writer" literally true. Wire `app.state.db` to this owner
instead of a bare connection; the lifespan still opens it before serving and
closes it (only when owned) on shutdown; DI for tests still works
(`create_app(db_path=/connection=)`).

If, with `engineering:developer`, you judge a marshal-to-owning-thread or a
dedicated DB-worker-task design clearly better, you may take it — but a full
worker/queue is likely speculative now and out of scope; prefer the smallest
correct thing. Whatever you choose, the acceptance criteria below are
behavioral, not implementation-specific.

Update the existing startup/DI (#002) and the `test_startup` wiring that had to
run the lifespan in-thread as a workaround; that workaround should no longer be
necessary once the model is correct.

## Acceptance criteria
- [ ] A **sync** FastAPI route handler that reads and writes `app.state.db`
      succeeds when driven through `TestClient` (i.e. from a worker thread) with
      no `sqlite3.ProgrammingError` — proven by a regression test that adds/uses
      a temporary DB-touching probe route (or an actual endpoint) driven via
      TestClient.
- [ ] Concurrent requests that both touch the DB do not corrupt data or raise
      threading errors; access is serialized (or otherwise made safe) so a
      write is never interleaved with another operation on the same connection.
- [ ] The single-writer guarantee is preserved: exactly one connection owns the
      file for the server's lifetime; startup still opens+migrates before
      serving and closes it (only when owned) on shutdown.
- [ ] DI for tests still works: `create_app(db_path=...)` and
      `create_app(connection=...)` behave as before; the injected connection is
      used as-is and left open for its owner.
- [ ] The `test_startup` in-thread workaround for the injected-connection test
      is removed or shown unnecessary, and the suite still passes.
- [ ] Regression-grade tests fail if the threading model regresses (revert the
      fix -> the sync-handler-through-TestClient test raises).
- [ ] `ruff format`, `ruff check --fix`, `pytest` all clean; work committed.

## Out of scope
- A full background job/worker queue system (that is the jobs milestone; only
  build the minimum threading model endpoints need now).
- Multi-connection read replicas or a connection pool.
- Any specific endpoint's business logic (users routes are #006).

## Review log
- 2026-08-15 PO: triaged from the backlog and promoted to todo as #008.
  Reassessed priority medium -> high and depth: this blocks #006 (the first
  DB-reading route), so #006 now depends on it. Recommended the minimal
  check_same_thread=False + single-lock owner; left room for a better design if
  engineering:developer justifies it. Behavioral acceptance criteria so the
  implementation stays the dev's call.
- 2026-08-15 dev: picked up (dep 002 in done/), moved to in-progress. Took the
  PO's recommended minimal design — it is the smallest correct thing; a
  worker/queue would be speculative now.
- 2026-08-15 dev: implemented. `connection.connect` now opens with
  `check_same_thread=False`; added a `Database` owner in `db/database.py` holding
  the connection + an `RLock`, exposing `connect()` (a context manager yielding
  the connection with the lock held) and `close()`. The lifespan now wraps the
  connection (owned or injected) in `Database`, sets `app.state.db` to it,
  reconciles the owned path through `database.connect()`, and closes the Database
  only when owned; DI (`db_path`/`connection`) is unchanged and the injected
  connection is still left open for its owner. Route handlers use
  `with app.state.db.connect() as conn: ...`. Tests: added a sync probe route
  driven through `TestClient` (worker thread) that creates/writes/reads the DB
  with no ProgrammingError; a `Database` concurrency test (8 threads x 50 inserts
  = 400 rows, no errors) proving serialization; and removed the previous
  injected-connection `asyncio.run` in-thread workaround (now a plain
  `TestClient` block, per AC). Gate clean (ruff format, ruff check --fix, pytest
  77 passed). Regression-proven: temporarily reverting `check_same_thread=False`
  makes BOTH the sync-probe and the concurrency test fail with the exact
  `sqlite3.ProgrammingError: SQLite objects created in a thread can only be used
  in that same thread`, then restored. Smoke-tested the real binary: serve
  starts, /health and /version 200, clean shutdown. Committed e9a9f2d. Moved to
  verifying for qa.
- 2026-08-15 qa: PASS -> po-review. Verified all dimensions with a deeper pass
  on the concurrency surface (engineering:developer lens). Design matches the
  recommended direction: a `Database` owner holds the single connection + an
  `RLock`, `connect()` serializes every access, and `check_same_thread=False`
  is safe only because of that lock (documented). Independently confirmed the
  regression tests are genuinely regression-grade: reverting
  `check_same_thread=False` in place makes BOTH
  `test_sync_handler_uses_db_through_testclient` and
  `test_database_serializes_concurrent_cross_thread_access` fail with the exact
  `sqlite3.ProgrammingError: SQLite objects created in a thread can only be used
  in that same thread`, and restoring makes them pass (AC6 satisfied). AC2:
  8 threads x 50 inserts through the owner produced 400 rows with zero errors,
  proving serialization (no lost writes, no threading errors). AC1: a sync
  probe route driven via TestClient (threadpool) reads+writes the DB with no
  ProgrammingError. AC3: single connection still opened+migrated before serving
  and closed only when owned (lifespan wraps it, reconcile runs under the lock);
  the CLI's pre-serve reconcile/bootstrap are single-threaded so no cross-thread
  access occurs there, and the CLI still owns the single close. AC4/AC5: DI
  intact and the old `asyncio.run`/`lifespan_context` in-thread workaround is
  replaced by a normal `TestClient` drive. Confirmed nothing consumes
  `app.state.db` as a bare connection, so the owner swap breaks no existing
  path. Code review clean: concept-named owner, minimal surface, typed,
  docstrings only, no emojis, no speculative worker/queue. Commit e9a9f2d is a
  proper atomic Conventional Commit; working tree left clean after my
  revert-and-restore. Re-ran the gate: ruff format clean (33 files), ruff check
  passed, pytest 77 passed.
- 2026-08-15 PO: PASS -> done. The `Database` owner (single connection + RLock,
  `connect()` yields under the lock) matches the recommended minimal design;
  `check_same_thread=False` is safe only because of that lock, documented.
  Independently ran the gate (ruff format 35 clean, ruff check clean, pytest 88
  passed), the two named regression tests
  (test_sync_handler_uses_db_through_testclient +
  test_database_serializes_concurrent_cross_thread_access) both pass, and hit
  the owner from 12 threads x 50 inserts myself -> 600 rows, zero errors, proving
  serialization. qa already reproduced the definitive proof (revert
  check_same_thread=False -> both tests fail with the exact
  sqlite3.ProgrammingError -> restore -> pass). DI intact, single writer
  preserved, the old asyncio in-thread workaround removed. Unblocks #006 (first
  DB-reading routes). No adjacent work spun off. Closed at e9a9f2d.
