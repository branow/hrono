---
id: 002
title: serve opens the DB and applies migrations at startup
priority: high
size: small
depends_on: [001]
spec_refs: [build-order.md#T1, build-order.md#T2, implementation-notes.md]
---

## Context
T1 built the migration runner (`discover` + `Migrator` in
`src/hrono/db/migrations.py`, tested) but **nothing invokes it** and the server
(`src/hrono/server/app.py`) opens no database at all. Before any secret, user,
or registry table can exist at runtime, `hrono serve` must own the SQLite file
(single writer, per the architecture) and bring the schema up to date on
startup. This is implied-but-unenumerated infrastructure that unblocks all of
M0's secrets/auth and M1's registries. Flagged gap: the runner exists but is
unwired — this ticket wires it.

## Description
1. **Resolve packaged migrations.** Add a helper that locates the packaged
   migrations directory `src/hrono/db/migrations/` at runtime — via
   `importlib.resources` (preferred) or `Path(__file__).parent / "migrations"` —
   so it works when hrono is installed as a package, not only from the repo
   root. It `discover`s the migrations and applies them to a given connection
   using the existing `Migrator`.
2. **Open + migrate.** Add an entry that opens the hrono database at the
   canonical path `./.hrono/hrono.db` (per CLAUDE.md) using
   `db.connection.connect`, applies pending migrations, and returns the ready
   connection. Default path only — do not add a config knob or flag.
3. **Wire into `serve`.** On `hrono serve` startup (FastAPI `lifespan` on the
   app built by `create_app`), open the DB and apply migrations **before** the
   server accepts requests; close the connection on shutdown. The server is the
   single writer.
4. **Testability.** Keep `create_app` a factory and allow injecting a DB path or
   connection for tests (dependency injection, no monkeypatching).

Conventions: single writer owns the file; DI over monkeypatch; minimum surface
(no new CLI flags in this ticket); early returns; typed params.

## Acceptance criteria
- [ ] Starting the server against a fresh path creates `.hrono/hrono.db` with
      `schema_migrations` populated for every packaged migration, and the `keys`
      table (from #001) present.
- [ ] Restarting against an existing, up-to-date DB applies nothing (idempotent)
      and starts cleanly.
- [ ] The migrations directory is resolved from the installed package, not a
      hard-coded absolute path (verify it resolves without relying on the
      current working directory being the repo root).
- [ ] `GET /health` still returns 200 after the startup wiring.
- [ ] A test drives startup with an injected temp DB path and asserts the
      packaged migrations were applied; a second test asserts a repeat startup
      is a no-op.
- [ ] `ruff format`, `ruff check --fix`, and `pytest` are all clean; committed.

## Out of scope
- Master-key handling / secrets (that is #003, #004).
- Auth, users, or any endpoint beyond the existing `/health` and `/version`.
- A `--db-path` flag or any other configurable DB location.

## Review log
- 2026-08-15 PO: authored and moved to todo. Spun out as a flagged gap — T1's
  runner and T2's server exist but nothing opens the DB or runs migrations at
  startup; #003 onward depend on this.
- 2026-08-15 dev: picked up (001 now in done/), moved to in-progress.
- 2026-08-15 dev: implemented. Added `packaged()` + `migrate(conn)` to
  `db/migrations.py` (packaged dir resolved via `Path(__file__).parent /
  "migrations"`, independent of cwd); new `db/database.py` with
  `DEFAULT_PATH = .hrono/hrono.db` and `open_database(path)` = connect + migrate;
  wired a FastAPI `lifespan` into `create_app` that opens+migrates before serving
  and closes on shutdown, with DI via `db_path` or a ready `connection` (injected
  connection used as-is and not closed). Tests: `tests/db/test_database.py`
  (packaged migrations applied, idempotent restart via empty `pending()`,
  resolves independent of cwd, default path) and `tests/server/test_startup.py`
  (startup creates .hrono/hrono.db with schema_migrations + keys table, repeat
  startup no-op, /health 200 after wiring, injected connection used and left
  open). Gate clean (ruff format, ruff check --fix, pytest 36 passed). Verified
  the real flow: ran `hrono serve` from a fresh temp dir, got /health 200 and
  /version 200, confirmed .hrono/hrono.db created with schema_migrations=[(1,
  keys)] and the keys table present, clean startup/shutdown. Committed f3bbae7.
  Moved to verifying for qa.
- 2026-08-15 qa: PASS -> po-review. Verified all dimensions. Drove the real
  flow: ran the actual `hrono serve` binary from a fresh temp cwd (not the repo
  root) on port 8137 — `.hrono/hrono.db` was created at the default path,
  `schema_migrations` held version 1 and the `keys` table (from #001) was
  present, `/health` returned 200 and `/version` returned the right body, with
  clean lifespan startup/shutdown in the log. Confirmed migration dir resolves
  from the module (`Path(__file__).parent / "migrations"`), independent of cwd
  (proven both by the temp-cwd drive and the monkeypatch.chdir test).
  Idempotency confirmed: repeat startup applies nothing (`pending() == ()`,
  row count unchanged). DI is clean — `create_app(db_path=...)` /
  `create_app(connection=...)`, injected connection used as-is and left open,
  no monkeypatching of the code under test. Verified `connect()` mkdirs the
  parent so the default `.hrono/` path works on a fresh checkout. Tests are
  regression-grade and cover every acceptance criterion (DB+migrations on
  startup, idempotent restart, cwd-independent resolution, /health, injected
  connection). Code review clean: early returns, typed params, docstrings
  only (no stray inline comments), no emojis, no speculative surface (no
  --db-path flag). Security: no secrets, no new endpoints or role surface in
  scope. Commit f3bbae7 is a proper atomic Conventional Commit (feat, one
  sentence, no body/attribution), no stray changes. Re-ran the gate myself:
  ruff format clean (23 files), ruff check passed, pytest 36 passed.
- 2026-08-15 PO: PASS -> done. Re-verified against the code, not just the logs:
  `open_database` = connect + `migrate`; `packaged()` resolves module-relative
  (`Path(__file__).parent/"migrations"`), cwd-independent; lifespan opens+
  migrates before serving and closes only an owned connection (injected one left
  open); factory `create_app(db_path=/connection=)`; no `--db-path` flag. Drove
  the real binary from a fresh temp cwd: `.hrono/hrono.db` created at the default
  path, `schema_migrations=[(1,'keys')]`, tables {keys, schema_migrations},
  /health 200, /version 0.1.0, clean startup/shutdown. Ran the gate myself: ruff
  format (23 clean), ruff check clean, pytest 36 passed. Regression-grade tests
  cover startup+migrations, idempotent restart, cwd-independent resolution,
  /health, injected-connection DI. This unblocks #003/#005/#007. No adjacent
  work spun off. Closed at f3bbae7.
