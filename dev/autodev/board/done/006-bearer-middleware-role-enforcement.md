---
id: 006
title: Bearer middleware + server-side role enforcement
priority: high
size: medium
depends_on: [005, 008]
spec_refs: [build-order.md#T4.2, implementation-notes.md#auth]
---

## Context
Roles are enforced server-side from day one — the API is the only trust
boundary; every later client (CLI, dashboard) relies on the server, never its
own UI, to forbid. This ticket turns the user/token layer from #005 into actual
request-time authentication and authorization: parse the Bearer token, resolve
the `User`, and gate each route by required role. It is the piece every future
authenticated endpoint (recall, config, ops, users) depends on. Spun off from
the T4 auth slice.

## Description
Add FastAPI auth wiring in `src/hrono/server/` that authenticates via
`Authorization: Bearer <token>` and enforces the role a route requires. Load
`engineering:security` before writing this.

- **Token extraction + authentication.** Read the `Authorization` header,
  require the `Bearer ` scheme, take the token, and resolve it with
  `auth.users.authenticate(conn, token)` from #005. Missing/malformed header or
  unknown token -> `401 Unauthorized`. Do not leak whether the header was
  absent vs the token invalid beyond the standard 401.
- **Role gate.** A dependency/factory (recommend
  `require_role(min_role)` in `src/hrono/server/auth.py`) that authenticates,
  then checks the user's role against the route's requirement using a role
  ordering `reader < writer < admin` (an admin may call a writer route). A
  valid token whose role is insufficient -> `403 Forbidden`. Encode the
  ordering as data (a rank map), not an if/elif ladder.
- **Wire it.** `/health` and `/version` stay unauthenticated (liveness). Add at
  least one protected route to prove the mechanism end to end — the natural
  choice is the users routes this slice needs anyway:
  `GET /users` (reader+ may list; expose only `name`/`role`/`created_at`, never
  token or hash), `POST /users` (admin only; returns the freshly created user
  and its raw token **once**), `DELETE /users/<name>` (admin only). If you
  prefer to keep the users routes in their own follow-up, wire `require_role`
  onto a single guarded probe route instead and note it — but the users routes
  are in-scope here and preferred, since #007 and the CLI both need them.
- Responses are JSON, `snake_case` keys, kebab-case role values. Errors return
  a clear JSON body and the correct status, never a stack trace.

Conventions: role ordering as a data-driven rank map; early returns; every
parameter typed; no secret (token/hash) ever in a response body or log line.

## Acceptance criteria
- [ ] A request with no `Authorization` header to a protected route -> 401;
      a malformed header (wrong scheme, empty token) -> 401; a well-formed
      Bearer with an unknown token -> 401.
- [ ] A valid token with sufficient role -> 200 and the intended response; a
      valid token with insufficient role (e.g. reader hitting an admin route)
      -> 403.
- [ ] Role ordering `reader < writer < admin` holds: admin satisfies a writer-
      or reader-required route; writer satisfies reader; reader does not satisfy
      writer/admin. The ordering is expressed as data, not branching.
- [ ] `/health` and `/version` remain reachable with no token.
- [ ] `POST /users` is admin-only and returns the raw token exactly once;
      `GET /users` never includes token or hash for any user;
      `DELETE /users/<name>` is admin-only.
- [ ] `POST /users` with a name that already exists returns a clean `409`
      Conflict with a JSON body (never a 500 or a traceback): `create_user`
      raises a raw `sqlite3.IntegrityError` on the PK, which the route must map.
      `POST /users` with a role outside reader/writer/admin returns `400`/`422`
      (from `InvalidRole`), not a 500. `DELETE /users/<name>` on an unknown name
      returns `404`.
- [ ] Regression-grade tests (FastAPI TestClient) cover 401 paths, 403 path,
      the role-ordering matrix, unauthenticated health/version, and that no
      response body or log contains a token/hash.
- [ ] `ruff format`, `ruff check --fix`, `pytest` all clean; work committed.

## Out of scope
- Bootstrapping the first admin token on an empty user table (#007).
- CLI client wiring / `hrono users` command (T5.3 + later).
- Rate limiting, token expiry, audit logging.

## Review log
- 2026-08-15 PO: authored and moved to todo. Depends on #005 for the token
  lookup; wires the users routes here since #007 and the CLI both need them.
- 2026-08-15 PO: added depends_on #008. This is the first ticket whose route
  handlers read `app.state.db` from FastAPI's sync threadpool, so the DB
  threading model (#008) must land first or these handlers will raise
  sqlite3.ProgrammingError.
- 2026-08-15 PO: added error-mapping criteria from #005 review. `create_user`
  raises a raw `sqlite3.IntegrityError` on a duplicate name and `InvalidRole`
  on a bad role; the routes must map these to 409 / 400-422 and unknown-name
  delete to 404, never a 500/traceback (product bar: actionable errors).
- 2026-08-15 dev: picked up (deps 005, 008 in done/), moved to in-progress.
- 2026-08-15 dev: implemented. `src/hrono/server/auth.py`: `require_role(min)`
  dependency factory — extracts `Authorization: Bearer <token>`, resolves it via
  `authenticate` through `app.state.db.connect()` (the #008 lock, so it is
  threadpool-safe), and gates on a data-driven rank map
  `{reader:0, writer:1, admin:2}` (no if/elif). Missing, malformed, and unknown
  credentials all raise one opaque 401 (no leak of which); insufficient role ->
  403. `src/hrono/server/users.py`: `GET /users` (reader+, returns only
  name/role/created_at), `POST /users` (admin, 201 + raw token once,
  `InvalidRole` -> 422, `sqlite3.IntegrityError` -> 409), `DELETE /users/{name}`
  (admin, 404 when absent); wired both routers in `create_app`; /health and
  /version stay open. Used `Annotated[User, Depends(require_role(...))]`
  module-level singletons (ruff B008-clean). Tests: `tests/server/test_users.py`
  (TestClient) cover 401 for missing/malformed/unknown, the full role matrix
  (reader/writer/admin x reader/writer/admin routes), open health/version,
  create-returns-token-once, list-never-leaks-token/hash, 409/422/404 mappings.
  Gate clean (ruff format, ruff check --fix, pytest 121 passed; switched to the
  non-deprecated HTTP_422_UNPROCESSABLE_CONTENT). Drove the real binary: booted
  serve, used the bootstrap admin token to list/create/delete, confirmed no-token
  ->401, bad-token ->401, reader POST ->403, dup ->409, bad role ->422, delete
  unknown ->404, and no token string in GET /users (also closes #007's deferred
  "admin authenticates against a protected route" AC). Committed 1395ebe. Moved
  to verifying for qa.
- 2026-08-15 qa: PASS -> po-review. Verified all dimensions (deep
  engineering:security pass, this being the sole authorization boundary). Drove
  the full boundary against a REAL running server: bootstrapped the admin, then
  confirmed unauthenticated /health and /version are 200; /users returns 401 for
  no header, a `Basic` scheme, an empty `Bearer `, and an unknown token (a
  single opaque 401 that never reveals missing-vs-invalid); admin and reader
  GET /users are 200; a reader POST and DELETE are 403; admin create returns 201
  with the raw token exactly once; duplicate name -> 409, invalid role -> 422,
  unknown delete -> 404, valid delete -> 200 (all clean JSON, no 500/traceback).
  GET /users bodies carry only name/role/created_at (no token/hash), and the
  minted reader token is absent from both stdout and stderr server logs. Role
  ordering is a data-driven rank map (`_ROLE_RANK`), not an if/elif ladder;
  admin satisfies reader+writer routes, writer satisfies reader but not admin,
  reader satisfies neither (proven via reader->admin 403 + the shared rank
  comparison). DB access in every handler and in `_authenticate` goes through
  the #008 `Database` lock, so this first DB-reading route runs from FastAPI's
  sync threadpool with no `sqlite3.ProgrammingError` (confirmed live). Roles are
  enforced in domain terms (`User.role`) at the boundary, never raw protocol.
  Tests are regression-grade (401 matrix, 403, role matrix, unauth
  health/version, token-never-in-body). Code review clean: structured
  HTTPException at the boundary, pydantic body validation, early returns, typed,
  docstrings only, no emojis. Commit 1395ebe is a proper atomic Conventional
  Commit. Two minor, non-blocking observations (all ACs met): the Bearer scheme
  match is case-sensitive (fail-closed; RFC 7235 scheme is technically
  case-insensitive, and the CLI client controls its own header), and
  reader->writer is not directly exercised because no writer-minimum route
  exists yet (the data-driven rank makes it equivalent to the tested
  reader->admin case). Re-ran the gate: ruff format clean (44 files), ruff check
  passed, pytest 121 passed.
- 2026-08-15 PO: PASS -> done. Drove the full boundary against a real running
  server (via httpx to avoid shell header-quoting): unauth health/version 200;
  opaque 401 for no-header / Basic scheme / empty Bearer / unknown token (never
  reveals which); admin GET /users 200; admin create 201 with the raw token
  exactly once; reader GET 200 but reader POST/DELETE 403; duplicate -> 409,
  invalid role -> 422, delete-unknown -> 404, delete -> 200; the reader token is
  absent from the GET /users body. Role ordering is a data-driven `_ROLE_RANK`
  map (no if/elif); DB access in every handler goes through the #008 Database
  lock (threadpool-safe, this being the first DB-reading route). Ran the gate:
  ruff format (44 clean), ruff check clean, pytest 121 passed. Product bar met:
  the server is the sole authorization boundary, errors are clean JSON with no
  traceback. Unblocks #012 (registry role gating) and closes #007's deferred
  "admin authenticates against a protected route" AC. Closed at 1395ebe. Spun
  off #014 for qa's RFC-7235 nit: the Bearer scheme match is case-sensitive.
