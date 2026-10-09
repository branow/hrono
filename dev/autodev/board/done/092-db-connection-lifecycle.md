---
id: 092
title: DB connection lifecycle — rollback on error, BEGIN IMMEDIATE, busy retry, real /health
priority: blocker
size: big
depends_on: []
spec_refs: [build-order.md#T1, build-order.md#T11, implementation-notes.md]
found_by: e2e manual QA 2026-09-03 — .e2e/FINDINGS.md F23, F13, F14
---

## Context
The server holds ONE `sqlite3.Connection` for its whole lifetime
(`db/database.py:Database`), guarded by an `RLock`, and every write rides
Python's implicit DEFERRED transaction (`with database.connect() as conn, conn:`).
In the e2e run this wedged the server permanently, twice.

## Description
Observed (FINDINGS F23): after an op raised, and again after a single row was
inserted by another process, the server entered a state where
- every write returned 500 with `sqlite3.OperationalError: database is locked`
- every read served a STALE snapshot (a committed row was invisible for 20+ min)
- the worker stopped claiming jobs entirely
- `/health` kept returning `{"status":"ok"}`
Only a restart cleared it. In WAL mode a connection with an open read
transaction pins its snapshot; the connection can then never write and never
sees other writers.

Also (F13): an 11-minute `maintain` (57 of 92 condensations, ~7 min of paid LLM
calls) died outright on a transient `database is locked`, with no retry.
Also (F14): the raw driver string is stored and served as the job's `error`,
bypassing the `{error:{code,message,details}}` envelope.

Work:
- `Database.connect` must `rollback()` the connection whenever the block raises,
  so a failed op cannot poison it.
- Use `BEGIN IMMEDIATE` for write transactions (explicit, not Python-implicit)
  and retry on SQLITE_BUSY with bounded backoff on top of `busy_timeout`.
- End read transactions promptly (commit/rollback after reads) so the snapshot
  cannot go stale.
- `/health` must probe the database (`SELECT 1`, plus report
  `connection.in_transaction`) instead of returning a constant; consider a
  `/health?deep=1` that also reports whether the worker thread is alive.
- Map driver errors onto `AppError` before they reach a job record or a client.
- Multi-process story — **DECIDED 2026-09-12 (PO)**: do BOTH.
  - Move off the single process-lifetime connection to per-request /
    per-op connections (a small pool), so nothing outside the server can
    poison the one connection everything shares. This is the primary fix.
  - ALSO take an exclusive lock on the database file at startup, so a second
    `hrono serve` against the same file is refused with a clear message
    instead of two workers racing the same queue.

## Acceptance criteria
- [ ] An op that raises mid-transaction leaves the shared connection usable:
      the next write succeeds and the next read sees the newest commit.
- [ ] A write blocked by another writer retries and succeeds rather than failing
      the job; a genuinely unavailable database surfaces a mapped AppError.
- [ ] An external process's commit is visible to the server's next read.
- [ ] `/health` fails (non-200 or an explicit degraded body) when the database
      is unusable or the worker is dead.
- [ ] Regression test: write from a second connection while a long transaction
      is in flight, assert no wedge and no stale read.
- [ ] A second `hrono serve` on the same database file is refused at startup
      with a clear message (not a silent second worker).
- [ ] `ruff format`, `ruff check --fix`, `pytest` clean.

## Out of scope
- Job resume/checkpointing (its own ticket if wanted).

## Review log
- 2026-09-14 dev: started. Reading F23/F13/F14 evidence and the db layer before
  touching code; implementing the 2026-09-12 PO decision (per-op connections
  plus a startup exclusive lock).
- 2026-09-14 dev: implemented (commit 08736e4). Four moving parts.
  (1) `db/connection.py` now opens connections under legacy transaction control
  with `isolation_level="IMMEDIATE"`: a read runs outside any transaction (so
  it can never pin a WAL snapshot — F23's stale reads) and every write BEGINs
  IMMEDIATE, taking the write lock up front instead of failing on upgrade
  (F13). (2) `db/database.py`: `Database` is now a connection lender over a
  `Connections` seam — `Pool` (per-op connections to a path, 4 kept idle,
  `Database.at`) and `Shared` (one adopted connection, `Database.adopt`, for
  tests/injection). Every borrow ends clean: commit on success, rollback on
  exception, and a connection whose rollback fails is dropped rather than
  pooled; nested borrows on one thread reuse the same connection so an op
  calling an op shares its transaction. New `write()` = explicit BEGIN
  IMMEDIATE with bounded backoff retries (4 attempts, 50/100/200 ms) on top of
  busy_timeout, commit at the end; the 17 `connect() as conn, conn:` sites plus
  the worker's enqueue/claim/finish, jobs fan-out, user writes and the registry
  CRUD writes moved onto it. A busy `sqlite3.OperationalError` escaping any
  block is mapped to a new `Unavailable` (503, `unavailable`) AppError, so a
  driver string no longer reaches a job record or a client (F14).
  (3) `db/lock.py`: `exclusive()` flocks `<db>.lock`; `hrono serve` holds it for
  its lifetime and a second serve exits 1 with "another hrono server is already
  using .hrono/hrono.db". `serve` now runs the server in owned-`db_path` mode
  (so production uses the pool) with bootstrap/seed on a short-lived connection.
  (4) `/health` probes the database (`SELECT 1` + `in_transaction`) and the
  worker thread, and answers 503 `{"status":"degraded",...}` if either is gone.
  Also had to keep migration atomicity: `executescript` commits pending work, so
  `Migrator.apply` wraps each migration in `_atomic()` (PEP 249 control,
  restored and closed afterwards) — the pre-existing rollback test still passes.
  Tests: 12 new. `tests/db/test_database.py` — failed block leaves the next
  caller clean, a foreign *subprocess* commit is visible to the next read, a
  write waits out another writer, an unavailable database raises a mapped
  `Unavailable` after backing off, a long write in flight neither wedges nor
  stales other connections, nested borrows share one transaction.
  `tests/db/test_lock.py` (4) — second holder refused with a clear message,
  release, independence, lockfile location. `tests/jobs/test_worker.py` — a job
  dying mid-transaction does not wedge the queue (next foreign-inserted job is
  claimed and runs). `tests/server/test_app.py` — health ok / degraded on dead
  worker / degraded on unusable db. `tests/server/test_cli.py` — a second serve
  is refused and never starts uvicorn.
  Verified for real, not just green: started `hrono serve --port 8099` in a
  scratch dir. `/health` -> 200 `{"status":"ok","database":{"ok":true,
  "in_transaction":false},"worker":"alive"}`. A second `hrono serve` on the same
  file -> "another hrono server is already using .hrono/hrono.db", exit 1. Two
  jobs inserted by an external process were seen and claimed within ~10 ms each
  (F23's invisible-row case) and both failed cleanly; after those failures a
  registry POST returned 201 and read back, and `/health` stayed ok. With an
  external process holding BEGIN IMMEDIATE for 2 s, `POST /users` waited 1.64 s
  and returned 201 instead of "database is locked" (F13). Gate: ruff format,
  ruff check --fix, pytest all clean — 601 passed.
  Noted, not fixed (out of scope): `hrono reset` does not remove the new
  `.hrono/hrono.db.lock` sidecar; harmless (flock is advisory on the fd) and it
  belongs with F32's "reset leaves the cache behind".
- 2026-09-14 qa: PASS -> po-review. Verified against commit `08736e4` (the only
  uncommitted change in the tree is a pre-existing `.e2e/` line in `.gitignore`,
  not dev's and not counted).
  **Gate, re-run:** `ruff format --check .` 217 files already formatted;
  `ruff check .` all checks passed; `pytest` 601 passed, 0 failed (29s).
  **Real flows driven** (own scratch env, `hrono serve --port 8399` on a fresh
  db, not the `.e2e/` workspace):
  - AC1 mid-transaction failure, decisive version: registered a real git source,
    ran `sync` + `split` (33 sections / 823 passages / 872 contents landed),
    then installed a foreign `BEFORE INSERT ON sections ... RAISE(ABORT)`
    trigger and re-ran `split`. The op failed *after* `store.clear_source` had
    deleted all 33 rows -> job `failed`, and `SELECT count(*) FROM sections`
    read back **33** from a separate process: the whole write rolled back, zero
    half-applied state. Immediately afterwards a foreign-inserted `noop` was
    claimed and succeeded, `POST /users` -> 201, `/health` -> 200 ok. This is
    exactly F23's trigger and it no longer wedges anything.
  - AC1/AC3 also confirmed the cheap way: three real ops (`monitor`, `cluster`,
    `repair`) enqueued by an *external* process were claimed within ~20 ms and
    all failed; the fourth (`noop`) still succeeded; `POST /users` 201 and read
    back. F23's invisible-row and stale-snapshot symptoms are gone.
  - AC2 (F13): a foreign process holding `BEGIN IMMEDIATE` for 3 s -> `POST
    /users` waited 2.13 s and returned **201**. Held for 30 s -> `503
    {"error":{"code":"unavailable","message":"database is busy, try again
    shortly"}}` after 21.2 s of backoff — a mapped AppError, no driver string
    (F14's observed case).
  - AC4: `/health` 200 `{"status":"ok","database":{"ok":true,
    "in_transaction":false},"worker":"alive"}`; after the worker died it
    returned **503 `{"status":"degraded",...,"worker":"dead"}`** while reads
    still answered 200 — precisely the blind spot F23 complained about, now
    visible. (The worker dying out of `_claim` is #093's `depends_on: [092]`
    scope — "guard `_finish` and `_claim`" — not a 092 defect.)
  - AC6: a second `hrono serve` on the same file exits 1 with "another hrono
    server is already using .hrono/hrono.db"; lockfile is `0600`; after a clean
    shutdown the next serve reacquires it and comes up ok.
  - Load/idle: 8 concurrent `POST /users` all 201 in 10-19 ms while `sync` +
    `split` ran in the worker; idle server at 0.0% CPU with a flat WAL, so the
    worker's per-poll `BEGIN IMMEDIATE` costs nothing.
  - Config-vs-work: `POST /sources` created no job row.
  **Migration atomicity (the flagged risk), proven independently:** built a
  `Migrator` on a real `db.connection.connect()` connection with a migration
  whose *runtime* (not parse-time) failure lands mid-script
  (`CREATE TABLE b; INSERT; duplicate INSERT; CREATE TABLE c`). Result: raised
  `IntegrityError`, tables = `['a','schema_migrations']` (b and c absent, also
  from a second process), `schema_migrations` = `[1]` only, `in_transaction`
  False, `autocommit` restored to LEGACY (-1) with `isolation_level` back to
  `IMMEDIATE`, the connection still writable, and a fixed v2 re-applied
  cleanly. `_atomic`'s ordering is right: `with _atomic(conn), conn:` exits
  `conn` (rollback) before `_atomic` restores control.
  **Nested borrows:** read every `write()` site. No op calls another op from
  inside a `write()` block — `maintain`, `build_tree`, `settle` and `update`
  all invoke sub-ops outside their write blocks, and every LLM call in
  `condense`/`brief`/`brief_upper`/`propagate` sits outside the write, so the
  write lock is never held across a network call. The nested path in
  `Database.connect` returns the thread-local connection without acquiring
  `Shared`'s RLock again, so self-deadlock is impossible; an inner failure
  propagates to the outer borrow which rolls the whole thing back
  (`test_nested_borrows_share_one_transaction` asserts count == 0).
  `registry/engine.py:61` and `auth/users.py:52` still catch
  `sqlite3.IntegrityError` around a `write()` — checked that `_mapped` returns
  non-busy errors unchanged so those catches keep working.
  **Tests:** 12 new, all regression-grade and tied to the findings —
  `tests/db/test_database.py` (failed block leaves a clean connection, a
  foreign *subprocess* commit is visible, a write waits out a rival, an
  unavailable db raises mapped `Unavailable` after >=0.3 s of backoff, a long
  write neither wedges nor stales, nested borrows share one transaction),
  `tests/db/test_lock.py` (4), `tests/jobs/test_worker.py` (a job dying
  mid-transaction does not wedge the queue and leaves no `probe` table),
  `tests/server/test_app.py` (health ok / degraded-worker / degraded-db),
  `tests/server/test_cli.py` (second serve refused, uvicorn never started).
  AC5's regression test is `test_a_long_write_does_not_wedge_or_stale_the_
  other_connections`. They fail if the feature breaks.
  **Code review:** matches the PO's 2026-09-12 decision exactly (per-op pooled
  connections as primary, plus a startup file lock). `Connections` Protocol
  with `Pool`/`Shared` is composition and a clean DI seam (`Database.at` /
  `Database.adopt`) rather than monkeypatching; every parameter typed; early
  returns; no god object; `fcntl.flock` over hand-rolled locking; no stray
  inline comments (only justified `# noqa` lines); no emojis; ruff-clean at 80
  cols. Consistent with the surrounding codebase.
  **Security:** lockfile opened `O_CREAT|O_RDWR, 0o600`; `Unavailable`'s
  message is generic and carries no driver text or path; `/health` stays
  unauthenticated by design and only exposes up/down plus an exception *type*
  name; no secrets touched; the master key path is unchanged and still never
  logged; role enforcement untouched (`/users` still `Admin`-gated).
  **Commit:** `fix: lend a connection per op and lock the database file so one
  failed op cannot wedge the server` — Conventional, lowercase, one sentence,
  no body, no attribution; atomic (the ~30 test-file edits are the mechanical
  `Database(conn)` -> `Database.at/adopt` constructor change the fix requires);
  no unrelated files.
  Out of scope, filed not blocked: backlog #109 — job records still store
  `str(exc)` verbatim for non-busy driver errors (my poison-trigger run stored
  `'poisoned mid-transaction'`), so F14's envelope goal is only half met; the
  `jobs.error` column has no `code`/`details`, which is a schema change.
- 2026-09-14 PO: **PASS -> done.** Verified independently of the Review log,
  against commit `08736e4` (working tree carries only the pre-existing `.e2e/`
  line in `.gitignore`, not dev's).
  **Gate, re-run myself:** `ruff format --check .` 217 files already formatted;
  `ruff check .` all checks passed; `pytest` 601 passed in 29.5s.
  **Diff read:** `db/connection.py` (legacy control, `isolation_level
  ="IMMEDIATE"` — reads outside any transaction, writes take the write lock up
  front), `db/database.py` (`Connections` Protocol with `Pool`/`Shared`,
  `Database.at`/`Database.adopt`, commit-or-rollback on every borrow, a
  connection whose rollback fails is dropped not pooled, `write()` = BEGIN
  IMMEDIATE with 4 bounded retries, busy errors mapped to `Unavailable`),
  `db/lock.py` (`fcntl.flock` on a `0600` sidecar, `Conflict` with a clear
  message), `server/app.py` (`/health` probes db + worker, 503 degraded),
  `cli.py` (serve holds the lock for its lifetime, bootstrap on a short-lived
  connection, owned-`db_path` mode so production uses the pool),
  `migrations.py` (`_atomic` keeps each migration atomic despite
  `executescript`). This is exactly the 2026-09-12 decision: per-op pooled
  connections as the primary fix PLUS a startup exclusive file lock. Nothing
  speculative added.
  **Drove a real server myself** (fresh scratch db, `hrono serve --port 8479`):
  - AC4/AC6 first: `/health` -> 200 `{"status":"ok","database":{"ok":true,
    "in_transaction":false},"worker":"alive"}`; a second `hrono serve` on the
    same file exits 1 with "another hrono server is already using
    .hrono/hrono.db".
  - AC3/AC1 (F23): a job row committed by a **separate process** was claimed
    0.1 s later and failed; immediately after that failure `POST /users` -> 201
    and `GET /users` -> 200, with `/health` still ok. The wedge is gone.
  - AC2 (F13): with a foreign process holding `BEGIN IMMEDIATE`, `POST /users`
    waited **2.65 s and returned 201**. Held past the retry budget it returned
    **503 `{"error":{"code":"unavailable","message":"database is busy, try
    again shortly"}}`** after 21.1 s — a mapped AppError, no driver string.
  - AC5: `test_a_long_write_does_not_wedge_or_stale_the_other_connections`
    exists and is the named regression.
  Every acceptance criterion is truthfully ticked. F23 and F13 are closed;
  F14's observed case (the stored `database is locked` string) is closed.
  **Ruling 1 — qa's backlog #109 (F14 residual): split ACCEPTED.** F14's
  observed failure was the busy string reaching the job record, and that is
  mapped now. The residual — `jobs/worker.py:_execute` storing `str(exc)` for
  any other driver error, and `jobs.error` having no `code`/`details` — needs a
  schema migration and a worker-boundary mapping, which is a different change
  from this ticket's connection lifecycle. 092 has no acceptance criterion it
  misses because of it. #109 stays in `backlog/` at `low` for the next triage
  tick; it is not a 092 defect and does not hold this ticket open.
  **Ruling 2 — worker death under prolonged contention: attribution to #093
  ACCEPTED.** I reproduced it independently: after a foreign writer held the
  lock past the ~21 s budget, `/health` returned **503 `{"status":"degraded",
  ...,"worker":"dead"}`** while reads still answered. That is `_claim`'s write
  raising and escaping `run()` — verbatim #093's scope ("Guard `_finish` and
  `_claim`; never let an exception leave `run()`"), and #093 is already in
  `todo/` as a `blocker` with `depends_on: [092]`, so it becomes pickable the
  moment this closes. 092's own promise here was *visibility* (AC4), and the
  degraded `/health` is exactly the blind spot F23 complained about, now lit up.
  Making 092 carry the fix as well would be stuffing scope into a ticket that
  did its job.
  No new tickets authored this tick; none needed beyond the two above.
