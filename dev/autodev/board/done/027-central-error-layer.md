---
id: 027
title: Central exception-handling layer (raise domain errors, map once)
priority: high
size: medium
depends_on: [006]
spec_refs: [implementation-notes.md, build-order.md]
---

## Context
Promoted from a stakeholder backlog request. Error handling is ad hoc today: the
registry engine raises `HTTPException` at each call site, `users.py` maps
`InvalidRole`/`IntegrityError` inline, and `cli.py` keeps a `_KEY_ERRORS` dict
for master-key errors. This does not generalize — jobs, ingest ops, and every
future endpoint will each need consistent, non-leaking error responses. The fix
is Spring `@ControllerAdvice`-style: code everywhere just *raises* a domain
error that carries its own mapping metadata, and ONE handler layer turns any such
error into a well-formed response and logs it. This ticket builds that layer; the
sweep that migrates existing raise-sites onto it is #028. Load
`engineering:developer` (architecture) + `engineering:release` (logging rules).

Decision (spec is silent on error-body shape, so settled here): the HTTP error
envelope is `{"error": {"code": "<kebab-case>", "message": "<client-safe>",
"details": {...} | null}}` — snake_case keys, kebab-case `code` values, per the
project conventions. This replaces FastAPI's default `{"detail": ...}`; #028
updates existing call sites/tests/clients to it (a deliberate, cheap change while
the surface is still small and the only client is our own CLI).

## Description
Add `src/hrono/server/errors.py` (or `src/hrono/errors.py` if it must be shared
with the CLI boundary):
- **`AppError` base** carrying its own mapping metadata: `status_code: int`,
  `code: str` (stable kebab-case), `message: str` (client-safe), and optional
  `details: dict | None`. The mapping lives ON the type, so adding an error needs
  no handler change.
- **Domain subclasses** with baked metadata: `NotFound` (404), `Invalid`/
  `ValidationError` (422), `BadRequest` (400), `Unauthorized` (401),
  `Forbidden` (403), `Conflict` (409). Each sets its `status_code` + a default
  `code`; message/details are per-instance. Keep them small; this is the
  vocabulary the rest of the code raises.
- **One FastAPI handler** registered in `create_app` via
  `app.add_exception_handler(AppError, ...)` that renders ANY `AppError` into the
  envelope above from the exception's own metadata (no if/elif, no error dict).
- **Catch-all** `Exception` handler -> generic `500` with a fixed
  `internal-error` code and a safe message; the internal detail/traceback is
  NEVER in the response, only logged.
- **Structured logging in the handler** per the release skill: 4xx logged at
  warning, 5xx at error with the stack trace; never log secrets/tokens.
- **CLI reuse**: `AppError`'s `message`/`code` must also drive the CLI boundary
  (startup/exit) so #028 can retire `_KEY_ERRORS` — expose a small helper that
  renders an `AppError` to a one-line CLI message + exit code, or document how
  the CLI consumes it. (The CLI mapping itself is migrated in #028.)

This ticket only builds the layer and registers the handlers; it may add one or
two demonstrator errors/routes to prove it end to end, but it does NOT yet
rewrite the existing registry/auth/cli raise-sites (that is #028).

## Acceptance criteria
- [ ] Raising any `AppError` subclass inside a request yields the mapped status
      and the `{"error": {code, message, details}}` envelope (snake_case keys,
      kebab-case `code`) WITHOUT the endpoint catching it — proven by a demo
      route per subclass via TestClient.
- [ ] Adding a new error type requires only defining the subclass with its
      metadata — no change to the handler (demonstrate with a synthetic
      subclass).
- [ ] An uncaught non-`AppError` exception returns a generic 500 with a fixed
      code and safe message; the response contains NO internal detail/traceback,
      and the traceback IS logged.
- [ ] 4xx are logged at warning, 5xx at error with stack; no secret/token
      appears in any error response or log line.
- [ ] The layer lives in its own module; the mapping is metadata-on-type, not an
      if/elif ladder or a hand-kept error dictionary.
- [ ] `AppError` metadata is consumable by the CLI boundary (helper/adapter
      exists) so #028 can migrate `_KEY_ERRORS` onto it.
- [ ] Regression-grade tests cover each subclass's status+envelope, the
      add-a-subclass-without-touching-the-handler property, the 500 catch-all
      no-leak + logged-traceback, and the CLI render helper.
- [ ] `ruff format`, `ruff check --fix`, `pytest` all clean; work committed.

## Out of scope
- Migrating existing raise-sites (registry engine, users routes, auth, cli
  `_KEY_ERRORS`, validation hooks) and updating their tests/clients to the new
  envelope — that is #028.
- Changing the job-entity `error` field (that is job state, not the HTTP
  envelope).
- Per-endpoint custom error pages / i18n.

## Review log
- 2026-08-16 PO: triaged from the stakeholder backlog request
  `centralized-exception-handling` and split foundation (#027) vs migration
  (#028). Settled the error envelope `{"error":{code,message,details}}` since the
  spec is silent and it fits the snake_case/kebab-case conventions. High
  priority: land the layer before M2's new endpoints proliferate more ad-hoc
  handling. New M2 endpoint code (jobs/ingest) should raise `AppError` once this
  lands; #028 sweeps anything that predates it.
- 2026-08-16 dev: picked up (dep 006 in done/), moved to in-progress.
- 2026-08-16 dev: implemented. `src/hrono/errors.py` (no fastapi, so the CLI can
  import it): `AppError` base with metadata-on-type (`status_code`, `code`) +
  per-instance `message`/`details`; subclasses BadRequest(400)/Unauthorized(401)/
  Forbidden(403)/NotFound(404)/Conflict(409)/Invalid(422); `envelope(error)`
  builds `{"error":{code,message,details}}`; `cli_message(error)` renders the
  client-safe line for the CLI boundary (so #028 can retire `_KEY_ERRORS`).
  `src/hrono/server/errors.py::install(app)` registers two handlers on
  create_app: an `AppError` handler that renders any subclass from its own
  metadata (no if/elif) — 4xx logged at warning, 5xx at error with exc_info — and
  an `Exception` catch-all returning a fixed `internal-error` 500 whose body
  carries NO internal detail (traceback only logged). Wired via
  `install_errors(app)` in create_app. Did NOT migrate existing raise-sites
  (registry/users/auth/cli) — that is #028; demo routes live only in the test.
  Tests: `tests/server/test_errors.py` — per-subclass status+envelope
  (parametrised), details carried through, add-a-subclass (Teapot 418) with no
  handler change, uncaught ValueError -> safe 500 with the internal detail absent
  from the body but exc_info logged, 4xx->warning logging, cli_message, and
  create_app-installs-the-layer (NotFound->404 envelope on the real factory).
  Gate clean (ruff format, ruff check --fix, pytest 233 passed). Smoke-tested the
  real serve: /health ok, clean shutdown with the handlers registered. Committed
  003e7f5. Moved to verifying.
- 2026-08-16 qa: PASS -> po-review. Verified all dimensions (developer +
  security + release-logging lenses). The layer is metadata-on-type: `AppError`
  bakes `status_code`/`code` on the subclass, `envelope(error)` renders
  `{"error":{code,message,details}}` from that metadata, and one
  `_handle_app_error` maps ANY subclass with no if/elif; independently proved
  the add-a-subclass property by defining a brand-new `Gone(410)` at drive time
  and getting the correct 410 envelope with zero handler/registry change (and
  the test's `Teapot(418)` does the same through the real ASGI app). `errors.py`
  is fastapi-free so the CLI can import it; `cli_message` renders the client-safe
  line for #028 to retire `_KEY_ERRORS`. Security: the catch-all `_handle_
  unexpected` returns a fixed `internal-error` 500 body carrying NO internal
  detail - the test raises `ValueError("secret-internal-detail")` and asserts
  that string is absent from the response while `exc_info` is logged; verified
  the safe-500 path requires `raise_server_exceptions=False` (which the test
  correctly uses). Logging per the release skill: 4xx at warning, 5xx at error
  with `exc_info` (stack). Confirmed `install_errors(app)` is wired in
  `create_app` (app.py:91) and `test_create_app_installs_the_layer` proves a
  NotFound route on the real factory yields a 404 envelope; the `Exception`
  catch-all does not disturb FastAPI's existing HTTPException/{"detail"} or
  RequestValidationError handling (all pre-existing 401/403/409/422 tests still
  green), so no regression - existing raise-sites are correctly left for #028.
  Tests are regression-grade: parametrized per-subclass status+envelope,
  details-carried-through, add-a-subclass-no-handler-change, safe-500-no-leak +
  logged-traceback, 4xx->warning, cli_message, create_app-installs. Code review
  clean: metadata-on-type (no error dict/if-ladder), separate module, typed,
  docstrings only, no emojis. Commit 003e7f5 is a proper atomic Conventional
  Commit; scope correct (builds the layer + demo routes in tests only, migration
  is #028). Re-ran the gate: ruff format clean (87 files), ruff check passed,
  pytest 233 passed (12 in test_errors.py).
- 2026-08-16 PO: PASS -> done. Drove the layer via TestClient on a throwaway
  app: NotFound -> 404 with the {"error":{code,message,details}} envelope
  (details carried through), Conflict -> 409, and a NOVEL subclass defined in the
  test (Teapot, 418) rendered correctly WITHOUT touching the handler - proving
  metadata-on-type (add an error = a subclass, no handler/dict change). An
  uncaught RuntimeError carrying "SECRET_INTERNAL_DETAIL" -> generic 500 with a
  fixed internal-error body and the secret ABSENT from the response (leaks: False)
  while the traceback is only logged (exc_info to the logger, 5xx at error /
  4xx at warning). `envelope()` renders from the exception's own metadata, no
  if/elif; `cli_message()` is ready for #028's CLI migration. Ran the gate: ruff
  format (87 clean), ruff check clean, pytest 233 passed. The foundation is
  solid; new M2 endpoint code can raise AppError now. Unblocks #028 (migration).
  Closed at 003e7f5.
