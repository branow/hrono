---
id: 010
title: HTTP client wrapper (Bearer header, error mapping)
priority: medium
size: medium
depends_on: [009]
spec_refs: [build-order.md#T5.3, implementation-notes.md]
---

## Context
Every client subcommand is a thin HTTP call to `hrono serve`. Rather than each
command re-implementing base-URL resolution, auth headers, and error handling,
they share one wrapper. This ticket builds it: resolve the current context
(#009), attach the Bearer token, issue the request, and map transport/HTTP
failures to clear, actionable CLI errors with correct exit codes. It is the
foundation the registry/recall/tree/jobs commands (M1+) all build on. Authored
ahead alongside #009 to keep dev's queue stocked.

## Description
Add a small `httpx`-based client (recommend `src/hrono/client/http.py`) that the
CLI commands call. It:
- resolves the **current context** from #009's store (server_url + token); if
  there is no current context, fails with a clear "no active context — run
  `hrono context add ...`" message and a non-zero exit.
- issues requests against `server_url` with `Authorization: Bearer <token>` set
  on every call; JSON in/out; `snake_case` keys preserved.
- maps failures to typed client errors that the CLI boundary renders as a clean
  one-line message + non-zero exit (never a raw traceback, mirroring the
  master-key error pattern already in `cli.py`):
  - connection refused / DNS / timeout -> "cannot reach hrono server at
    <server_url>" .
  - `401` -> "unauthorized — check the token for this context".
  - `403` -> "forbidden — this token's role lacks permission".
  - `404` -> "not found".
  - other `4xx`/`5xx` -> surface the server's JSON `detail`/error message if
    present, else the status line.
- exposes a minimal typed surface (e.g. `get`/`post`/`put`/`delete` returning
  parsed JSON, or a single `request` helper) — only what a subcommand needs; no
  retry/backoff/streaming yet (SSE `watch` is a later ticket).

Prove it end to end against a **real running server** (or FastAPI `TestClient`):
point the client at a live `hrono serve`, call an unauthenticated route
(`/health` / `/version`) to confirm base-URL + round-trip, and assert the error
mapping by hitting a route that returns 401/404. Do **not** add a speculative
user-facing command that is not in the CLI spec just to exercise the wrapper —
test the wrapper directly.

Conventions: error map as data (status -> message builder), not an if/elif
ladder; typed params and returns; early returns; the token never appears in an
error message, log line, or exception string; DI the context/base-url for tests.

## Acceptance criteria
- [ ] With a current context set, the client issues requests to its server_url
      with an `Authorization: Bearer <token>` header on every request (verified
      by asserting the header the server receives).
- [ ] With no current context, a client call exits non-zero with a clear
      "no active context" message, not a traceback.
- [ ] A `GET /health` / `GET /version` round-trips and returns parsed JSON when
      pointed at a real running server.
- [ ] Error mapping is correct and traceback-free: connection failure ->
      "cannot reach" message; `401` -> unauthorized message; `403` -> forbidden
      message; `404` -> not-found message; other errors surface the server's
      message. Each maps to a non-zero exit at the CLI boundary.
- [ ] The bearer token never appears in any error message, log, or exception
      string.
- [ ] Regression-grade tests cover: header attachment, no-context error, a live
      round-trip (against TestClient or a spawned server), and the full
      status->message mapping (revert the mapping -> a test fails).
- [ ] `ruff format`, `ruff check --fix`, `pytest` all clean; work committed.

## Out of scope
- The per-collection subcommands (`sources`/`models`/`recall`/`tree`/`jobs`)
  that use this wrapper — those are their own tickets in M1+.
- SSE / job `watch` streaming, retries/backoff, pagination.
- Any server-side change.

## Review log
- 2026-08-15 PO: authored and moved to todo. T5.3 client wrapper; depends on
  #009 for the current context. Reuses the established "boundary maps typed
  errors to clean one-line CLI messages" pattern from the master-key work.
- 2026-08-16 dev: picked up (dep 009 in done/), moved to in-progress.
- 2026-08-16 dev: implemented. New `src/hrono/client/http.py`: a `Client`
  (server_url + token) with get/post/put/delete returning parsed JSON, attaching
  `Authorization: Bearer <token>` on every request; `from_context()` resolves the
  current context from #009's store and raises `NoContext` when none. Failures
  map to typed errors via a data-driven status table (`_STATUS_ERRORS`:
  401->Unauthorized, 403->Forbidden, 404->NotFound; else RequestFailed carrying
  the server's `detail`) and transport errors -> `Unreachable(server_url)`; a
  `message()` boundary helper renders each to a clean one-line, token-free string
  via `_MESSAGES` (mirrors cli._KEY_ERRORS). DI seam: the Client takes an
  optional `http: httpx.Client` (sync httpx can't drive ASGITransport, so tests
  inject a MockTransport-backed client for units and Starlette TestClient for the
  live round-trip). Tests: `tests/client/test_http.py` — header attachment,
  401/403/404 parametrised mapping, other-status surfaces server detail,
  connection-failure->Unreachable, no-context, token-never-in-message, and a live
  /health+/version round-trip. Gate clean (ruff format, ruff check --fix, pytest
  207 passed). Also drove the REAL spawned server: /health+/version round-trip,
  admin token authorized on /users, bad token -> clean Unauthorized (no leak),
  down server -> clean "Cannot reach". Scope: the per-collection subcommands that
  use this and SSE/watch are later tickets; CLI exit-code wiring lands with the
  first command that calls it (this ticket ships the wrapper + message mapping).
  Committed 9ef8ca6. Moved to verifying.
- 2026-08-16 qa: PASS -> po-review. Verified all dimensions (security lens on
  token handling). Drove the wrapper against a REAL spawned `hrono serve`: with
  no current context `from_context()` raises `NoContext` rendering "No active
  context. Add one with 'hrono context add ...'"; `GET /health` and `/version`
  round-trip parsed JSON; a protected `GET /users` with the admin token
  succeeds (proving the `Authorization: Bearer` header is attached and
  accepted). Error mapping is correct and traceback-free: a bad token -> 401
  Unauthorized ("check the token for this context"), a reader POST -> 403
  Forbidden, `GET /sources/ghost` -> 404 NotFound, a duplicate POST -> 409
  RequestFailed surfacing the server's `detail` ("user already exists: admin"),
  and pointing at a dead port -> Unreachable ("Cannot reach hrono server at
  http://127.0.0.1:1."). Confirmed the bearer token appears in NO rendered
  message and NO exception string (the token lives only in the request header).
  The status->error and error->message maps are data-driven (`_STATUS_ERRORS`,
  `_MESSAGES`), not if/elif; the httpx client and context are DI'd. Tests are
  regression-grade and offline (mock transport + FastAPI TestClient): exact
  Bearer-header assertion, parametrized 401/403/404 typed-error mapping (revert
  the map -> the test fails), 409-surfaces-detail, connection-failure ->
  Unreachable, no-context, token-never-in-message-or-str, and a live round-trip.
  Note on the "non-zero exit at the CLI boundary" AC: this ticket provides the
  typed errors + `message()` renderer; no subcommand wires it yet (out of scope
  - the ticket forbids a speculative command), so the exit happens in future
  subcommands via the established cli.py echo+Exit(1) pattern - correctly
  deferred. Code review clean: structured typed errors, early returns, typed,
  docstrings only, no emojis, no retry/SSE (out of scope). Commit 9ef8ca6 is a
  proper atomic Conventional Commit. Re-ran the gate: ruff format clean (77
  files), ruff check passed, pytest 207 passed.
- 2026-08-16 PO: PASS -> done. Drove the real Client against a spawned server:
  /health + /version round-trip parsed JSON; the Bearer header is attached and
  accepted (authorized GET /users returned the admin); a bad token -> clean
  Unauthorized with the token absent from the message; a dead port -> clean
  "Cannot reach hrono server at ...". status->error and error->message maps are
  data-driven (_STATUS_ERRORS/_MESSAGES), httpx client + context DI'd. Ran the
  gate: ruff format (78 clean), ruff check clean, pytest 212 passed. The
  non-zero-CLI-exit AC is correctly deferred (no subcommand wires it yet; ticket
  forbids a speculative command) - typed errors + message() renderer are ready.
  Completes the T5 CLI-client foundation (context store #009 + client #010).
  Note: the client parses today's {"detail":...} shape; #028 migrates it to the
  new {"error":{...}} envelope when #027 lands. Closed at 9ef8ca6.
