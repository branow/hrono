---
id: 007
title: bootstrap admin token on empty user table
priority: high
size: small
depends_on: [005, 002]
spec_refs: [build-order.md#T4.3, implementation-notes.md#auth]
---

## Context
A fresh install has no users, so nobody can authenticate to create the first
one — a chicken-and-egg lock. The spec resolves it: the first `serve` against an
empty `users` table mints an admin token and prints it once. This is the only
moment a token is ever emitted to stdout, and it must be unmissable and
one-time. Spun off from the T4 auth slice; pairs with #005 (user creation) and
#002 (startup owns the DB).

## Description
At server startup (the same startup path that opens the DB and applies
migrations from #002), after migrations are applied, check whether the `users`
table is empty. If and only if it is empty, create one admin user via
`auth.users.create_user(conn, name, "admin")` from #005 and print the raw token
once to stdout with clear, actionable framing (what it is, that it grants admin,
that it will not be shown again, and how to use it as a Bearer token). If any
user already exists, do nothing and print nothing about tokens.

- The check-and-mint must be idempotent across restarts: it fires exactly once
  over the lifetime of a database (empty -> mint; never again while any user
  exists). Restarting a server that already has users must not mint a second
  admin nor reprint anything.
- The printed token is the raw token, never the hash; it appears exactly once,
  on stdout, and is never persisted in plaintext or written to a log file.
- Choose a sensible fixed name for the bootstrap admin (e.g. `admin`) and state
  it in the printed message so the operator knows the user handle.

Conventions: server-side only; every parameter typed; no secret written to logs
or the DB in plaintext; the message must be genuinely user-friendly (this is the
operator's first contact with the product).

## Acceptance criteria
- [ ] First `serve` (or first startup path) against an empty `users` table
      creates exactly one `admin` user and prints its raw token once to stdout
      with a clear message naming the user, the role, the one-time nature, and
      Bearer usage.
- [ ] Startup against a non-empty `users` table mints no user and prints no
      token.
- [ ] Restarting after bootstrap does not create a second admin nor reprint the
      token (idempotent over the DB lifetime).
- [ ] The token is emitted only to stdout, exactly once; neither the raw token
      nor a reversible form is written to the DB or any log.
- [ ] The minted admin can immediately authenticate against a protected route
      once #006 lands (verify via the authenticate path / an integration test).
- [ ] Regression-grade tests cover: empty-table mint prints a token and creates
      one admin; non-empty-table startup is silent; restart idempotency; token
      never persisted in plaintext.
- [ ] `ruff format`, `ruff check --fix`, `pytest` all clean; work committed.

## Out of scope
- The Bearer middleware / role enforcement itself (#006).
- Rotating or regenerating the admin token (`rotate-key` is T59, far later).
- Any interactive prompt or key-file handling (that is the master key, #003).

## Review log
- 2026-08-15 PO: authored and moved to todo. Small, but the operator's first
  contact with the product — the printed message is part of acceptance, not an
  afterthought.
- 2026-08-15 dev: picked up (deps 005, 002 in done/), moved to in-progress.
- 2026-08-15 dev: implemented. New `src/hrono/auth/bootstrap.py`:
  `bootstrap_admin(conn) -> str | None` — returns None if any user exists
  (idempotent), else creates one `admin` user via `create_user(conn, "admin",
  "admin")` and returns the raw token once; only the hash is persisted. Wired
  into the CLI startup path (post-reconcile, pre-uvicorn, on the connection the
  CLI owns): when a token is minted it prints a clear one-time block naming the
  user (`admin`), role, the shown-once nature, and Bearer usage
  (`_bootstrap_message`). Bootstrap lives in the CLI because after #003 the CLI
  is the startup orchestrator (it opens+reconciles the DB and injects the
  connection); the lifespan only opens for the db_path/test path. Tests:
  `tests/auth/test_bootstrap.py` (mints one admin + token, token authenticates
  the admin, silent when a user exists, idempotent across calls, raw token never
  persisted) and a CLI integration test in `tests/server/test_cli.py` (first
  serve prints the token once and it authenticates against the DB; second serve
  reprints nothing and mints no second admin). Gate clean (ruff format, ruff
  check --fix, pytest 75 passed). Verified on the real binary: first serve
  printed the admin/token/one-time/Bearer block; DB holds the admin with the raw
  token absent and its SHA-256 hash matching the printed token; restart printed
  no bootstrap block and user count stayed 1. Note: AC "minted admin can
  authenticate against a protected route once #006 lands" is verified here via
  the `authenticate` path (function + CLI test); the route-level check belongs to
  #006. Committed 118f0d8. Moved to verifying for qa.
- 2026-08-15 qa: PASS -> po-review. Verified all dimensions. Drove the real
  binary twice against a fresh DB: first `hrono serve` on an empty users table
  printed the bootstrap block to STDOUT naming user `admin`, role `admin`, the
  raw token, "shown ONCE", and Bearer usage; the token authenticates as the
  admin (admin count 1). Confirmed the guarantees at the byte level: the token
  is NOT written to stderr and is absent from the DB file (only its hash is
  persisted via #005's create_user). Second `serve` against the now-non-empty
  table was completely silent about token/Bearer/admin and minted nothing
  (idempotent, admin count still 1). Bootstrap correctly sits in the CLI
  startup path after reconcile and before uvicorn accepts requests, and the
  emptiness check runs under the single-writer model (no concurrency window).
  AC5 (route auth) verified via the `authenticate` path as the ticket allows,
  since #006 owns the route. Tests are regression-grade (mint+token+one admin,
  token authenticates, silent-when-user-exists, idempotent-across-calls,
  raw-token-never-persisted, plus the CLI first/second-serve integration).
  Code review clean: pure typed function, early return, docstrings only, no
  emojis, message is a plain data string. Security: token emitted once to
  stdout only, never logged, never persisted in plaintext. Commit 118f0d8 is a
  proper atomic Conventional Commit (feat, one sentence, no body/attribution).
  Re-ran the gate: ruff format clean (33 files), ruff check passed, pytest 75
  passed.
- 2026-08-15 PO: PASS -> done. Drove the real binary myself. First serve on an
  empty users table printed a genuinely clear one-time block to stdout (user:
  admin, role: admin, token, "shown ONCE... stored only as a hash", exact Bearer
  header). Confirmed the security guarantees cleanly: token present on stdout,
  absent from stderr, and absent from the DB file at rest (only the hash
  persisted); the token authenticates as User(name='admin', role='admin').
  Second serve against the now-non-empty table printed no bootstrap block and
  minted nothing (admin count stayed 1) - idempotent over the DB lifetime.
  Bootstrap is a pure idempotent function sitting in the CLI startup path after
  reconcile, before uvicorn. AC5 (route auth) verified via the authenticate
  path as the ticket allows; #006 owns the route-level check. Ran the gate: ruff
  format (33 clean), ruff check clean, pytest 75 passed. Message quality meets
  the operator-first bar. No adjacent work spun off. Closed at 118f0d8.
