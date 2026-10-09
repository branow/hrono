---
id: 028
title: Migrate existing ad-hoc error handling onto the central layer
priority: high
size: medium
depends_on: [027]
spec_refs: [implementation-notes.md]
---

## Context
#027 builds the central `AppError` + one-handler layer. This ticket retires the
scattered ad-hoc handling so the whole codebase raises domain errors and maps
once, and switches responses to the `{"error": {code, message, details}}`
envelope consistently. Doing the sweep now — while the surface is still the
registries, auth, master-key, and the nascent jobs framework — keeps it cheap
and gives M2's remaining endpoints a consistent base.

## Description
Migrate every current error-to-response translation onto #027's `AppError`
hierarchy and the single handler; delete the now-redundant per-site handling:
- **Registry engine** (`registry/engine.py`): the inline `HTTPException`
  404/409/422/400 (unknown name, duplicate, invalid body, validation-hook
  rejection) become the matching `AppError` subclasses raised from the engine /
  store / write helpers.
- **Users routes** (`server/users.py`): `InvalidRole` -> `Invalid` (422),
  `sqlite3.IntegrityError` -> `Conflict` (409), unknown-name delete -> `NotFound`
  (404) — raised, not caught-and-mapped in the route.
- **Auth** (`server/auth.py`): the opaque 401 and the 403 become `Unauthorized`
  / `Forbidden` `AppError`s (keep the single-opaque-401 behavior and the
  `WWW-Authenticate` header).
- **Validation hooks** (git/connection/model `ValidationFailed`): map to the
  right `AppError` (400) centrally instead of each route translating.
- **Master-key / CLI** (`cli.py`): fold `MasterKeyError` and `_KEY_ERRORS` into
  `AppError` subclasses; the CLI boundary renders an `AppError` to its one-line
  message + non-zero exit via #027's helper. Delete `_KEY_ERRORS`.
- **Context commands** (`context/store.py` + `context/commands.py`): fold
  `MalformedConfig`, `DuplicateContext`, `UnknownContext` (the `_guard` path,
  from #009/#011) into `AppError` subclasses rendered by the same CLI helper, so
  the context commands map once like everything else. Keep the exact messages/
  exit behavior.
- **HTTP client** (`client/http.py`, #010): update the client's error parsing to
  read the new `{"error": {code, message}}` envelope (surface `error.message`,
  optionally branch on `error.code`) instead of `detail`.
- Update all affected tests to assert the new envelope/codes.

After this, no module should translate an exception to an HTTP response or a CLI
message on its own — they raise, the layer maps. Keep the master-key
fail-closed/no-mutation and the auth opaque-401 behaviors exactly as they were;
this is a shape/plumbing change, not a behavior change.

## Acceptance criteria
- [ ] The registry CRUD, users routes, auth, and validation hooks return the
      `{"error": {code, message, details}}` envelope with the same status codes
      as before (404/409/422/400/401/403); no route contains inline
      exception-to-response mapping.
- [ ] The master-key errors (missing/invalid/wrong key) still exit non-zero with
      a clear one-line CLI message and no traceback, now via `AppError` +
      #027's CLI helper; `_KEY_ERRORS` is deleted.
- [ ] The #010 HTTP client reads the new envelope and still maps
      connection/401/403/404/other to clean CLI messages; no `detail`-shaped
      parsing remains.
- [ ] Behavior is unchanged where it mattered: auth still returns a single opaque
      401 (+ `WWW-Authenticate`), wrong master key still fails closed with no
      mutation, secrets still never appear in any error body/log.
- [ ] All previously-passing error-path tests are updated to the new envelope and
      pass; a grep shows no remaining ad-hoc `HTTPException`/`_KEY_ERRORS` mapping
      outside the #027 layer (allow documented exceptions).
- [ ] `ruff format`, `ruff check --fix`, `pytest` all clean; work committed.

## Out of scope
- Adding new error types or endpoints (only migrating existing ones).
- The job-entity `error` field.
- Any behavior change beyond the response/message shape.

## Review log
- 2026-08-16 PO: authored as the migration half of the stakeholder error-handling
  request (foundation is #027). Includes updating the #010 client's error parsing
  to the new envelope. Flagged that master-key fail-closed + auth opaque-401
  behaviors must be preserved exactly — this is plumbing, not behavior.

## dev — 2026-08-16

Swept every error-to-response / error-to-CLI translation onto #027's AppError
layer + the `{"error":{code,message,details}}` envelope. No behavior change,
verified against the real binary.

Changes:
- errors.py: AppError gains an optional `headers`; `Unauthorized` bakes
  `WWW-Authenticate: Bearer`. server/errors.py passes `error.headers` on the
  response so the opaque 401 keeps its header.
- registry/engine.py: inline HTTPException 404/409/400/422 -> NotFound /
  Conflict / BadRequest / Invalid (pydantic errors under `details.errors`).
  `_run_hook` no longer catches; ValidationFailed now subclasses BadRequest so
  it maps centrally.
- registry/descriptor.py: `ValidationFailed(BadRequest)`.
- auth/users.py: `InvalidRole(Invalid)` with baked message; `create_user` maps
  sqlite IntegrityError -> Conflict. server/users.py route no longer catches or
  maps; unknown-delete raises NotFound.
- server/auth.py: opaque 401 -> Unauthorized, 403 -> Forbidden (no more
  HTTPException). server/jobs.py: 404 -> NotFound.
- crypto/masterkey.py: MasterKeyError -> AppError(BadRequest) subtree with the
  exact former CLI messages baked in. cli.py: deleted `_KEY_ERRORS` /
  `_key_error_message`; renders via `cli_message`.
- context/store.py: DuplicateContext/UnknownContext/MalformedConfig -> Conflict/
  NotFound/BadRequest with the exact former CLI text. context/commands.py:
  replaced `_guard` + per-command try/except with one `_run` boundary catching
  AppError.
- client/http.py: `_detail` reads `error.message` (was `detail`).

Preserved exactly (spot-checked on the running binary): auth single opaque 401 +
`WWW-Authenticate: Bearer`; wrong master key fails closed with a clean one-line
message and no traceback; secrets never in any body/log. CLI messages verified
identical for missing/invalid/unreadable key and unknown/malformed context.

Tests: strengthened the 401 test to assert the header + envelope, added a
layer-level WWW-Authenticate test, updated client/engine/users error-shape
assertions to the new envelope. Grep confirms no HTTPException / _KEY_ERRORS /
`detail=` left in src. Gate clean: ruff format/check, pytest 265 passed.
Commit 8ad3388.

## qa — 2026-08-16

PASS -> po-review. Verified the whole sweep is a behavior-preserving plumbing
change. AC5 audit: `grep -rn "HTTPException|_KEY_ERRORS|detail="` over src/hrono
returns nothing - no ad-hoc mapping remains. Drove the real server: every
migrated path returns the `{"error":{code,message,details}}` envelope with the
SAME status as before - unauth GET /users -> 401 (code `unauthorized`) WITH the
`www-authenticate: Bearer` header preserved; an unknown token gives the IDENTICAL
opaque 401 (missing vs invalid indistinguishable); reader POST -> 403
`forbidden`; GET /sources/ghost and /jobs/ghost -> 404 `not-found`; duplicate
POST -> 409 `conflict`; bad role -> 422 `validation-error`; a validation-hook
rejection (unreachable connection endpoint) -> 400 `bad-request` `"cannot reach
provider"` (ValidationFailed now subclasses BadRequest and maps centrally - the
engine no longer catches). The WWW-Authenticate header rides on `AppError.headers`
(baked on `Unauthorized`) and the handler passes it through. CLI preserved
exactly via `AppError` + `cli_message`: master-key missing/invalid/wrong-key
print the byte-identical one-line messages and exit 1 with no traceback, and the
wrong key still fails closed with NO mutation (keys row count stayed 1); context
malformed/duplicate/unknown print the identical messages and exit 1. The #010
client now reads `error.message` from the new envelope (surfaced the 409 message
correctly) - no `detail`-shaped parsing remains. Security preserved: no secret in
any body/log, opaque 401 intact, 500 catch-all still hides the traceback. Code
review clean: metadata-on-type (headers), no route-level mapping,
`ValidationFailed(BadRequest)` maps centrally, `_KEY_ERRORS` deleted, no emojis.
Tests updated to the new envelope + a layer-level WWW-Authenticate test. Commit
8ad3388 is a proper atomic Conventional Commit (`refactor:`). Re-ran the gate:
ruff format clean (97 files), ruff check passed, pytest 265 passed.
- 2026-08-16 PO: PASS -> done. Independently confirmed the sweep is
  behavior-preserving. AC5 grep over src/hrono returns NOTHING for
  HTTPException/_KEY_ERRORS/detail= - no ad-hoc mapping remains. Drove the live
  server: unauth GET /users -> 401 {"error":{"code":"unauthorized",...}} WITH the
  `www-authenticate: Bearer` header; a bad token gives the IDENTICAL opaque 401
  (missing vs invalid indistinguishable); reader POST -> 403 `forbidden`;
  404/409/422 all render the envelope with the right codes (not-found / conflict /
  validation-error). Master-key wrong-key still FAILS CLOSED: exit 1, clean
  "wrong master key: does not match the active key", zero traceback, keys row
  count unchanged (no mutation). The #010 client reads `error.message` from the
  new envelope. WWW-Authenticate rides on `AppError.headers`, ValidationFailed
  subclasses BadRequest (maps centrally), _KEY_ERRORS deleted. Ran the gate: ruff
  format (97 clean), ruff check clean, pytest 265 passed. Completes the
  stakeholder error-handling request (#027 foundation + #028 migration). Folded
  in #011's context-command errors as scoped. Closed at 8ad3388.
