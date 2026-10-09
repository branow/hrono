---
id: 016
title: anthropic connection validation on write (list-models)
priority: high
size: medium
depends_on: [015]
spec_refs: [build-order.md#T8.2, implementation-notes.md#connections]
---

## Context
A registered connection must actually work, so a dead or misauthed provider
credential is rejected at write time rather than failing later during a real
model call. #015 wired the `connections` collection with a no-op validation
hook; this ticket fills that hook for `provider: anthropic` (T8.2). Validation
must cost no inference — it hits the provider's list-models endpoint, where a
200 proves the key authenticates. Other providers' validation ships with them
(openai/openai-compatible/claude-code under T44); this ticket does anthropic
only. Spun off from the T8 connections slice.

## Description
Implement the `connections` validation hook for `anthropic`: on POST/PUT, before
the row is stored, make a no-inference-cost request to the provider's
list-models endpoint (`GET /v1/models`) with the supplied `api-key` (honoring an
`endpoint` override when present). A 200 means valid — the write proceeds and the
key is stored encrypted (via #015/#012/#004). A 401/403 means the key is
rejected; any connection failure means unreachable. Reject the write with a
clear error naming which (auth rejected vs unreachable) WITHOUT leaking the key.
Use the `anthropic` SDK (per the stack) or a direct `httpx` GET — whichever is
simpler; bound it with a sane timeout so a hanging endpoint fails cleanly.
Load `engineering:security` for the credential handling.

The hook dispatches by `provider`: only `anthropic` is validated here; other
providers keep the #015 no-op stub until their tickets. Keep the dispatch
data-driven (a per-provider validator map), not an if/elif ladder, so T44 adds a
map entry, not a branch.

## Acceptance criteria
- [ ] `POST`/`PUT /connections` with `provider: anthropic` and a working key
      (list-models returns 200) succeeds and stores the connection (key
      encrypted).
- [ ] A key that list-models rejects (401/403) is rejected with a clear `400`
      ("authentication failed") and the connection is NOT stored.
- [ ] An unreachable endpoint is rejected with a clear `400` ("cannot reach")
      and the connection is NOT stored; validation is bounded by a timeout.
- [ ] The api-key never appears in any error message, log line, or stored row in
      clear form.
- [ ] Non-anthropic providers are unaffected (still the #015 stub); the
      per-provider validator dispatch is data-driven.
- [ ] Regression-grade tests cover success, auth-rejected, and unreachable using
      a stubbed/mocked endpoint so the suite is deterministic and offline (no
      real network, no real key); a test fails if the key leaks or a dead
      connection is accepted.
- [ ] `ruff format`, `ruff check --fix`, `pytest` all clean; work committed.

## Out of scope
- openai / openai-compatible / claude-code validation (T44).
- Any inference or model call beyond list-models.
- Caching or re-validating existing connections on read.

## Review log
- 2026-08-15 PO: authored as the T8.2 follow-on to #015. Flagged deterministic/
  offline tests (mock the endpoint), data-driven per-provider dispatch, and
  no-key-in-errors.
- 2026-08-15 dev: picked up (dep 015 in done/), moved to in-progress. Added
  `httpx` as a runtime dep. Confirmed the endpoint via the claude-api reference:
  `GET /v1/models`, headers `x-api-key` + `anthropic-version: 2023-06-01`; 200 =
  valid, 401/403 = auth rejected.
- 2026-08-15 dev: implemented. New `registry/connection_validation.py`:
  `validate_connection(config, *, run=<httpx>, timeout=10)` dispatches through a
  data-driven `_VALIDATORS = {"anthropic": ...}` map (T44 adds a map entry, no
  branch); `_validate_anthropic` GETs `<endpoint or api.anthropic.com>/v1/models`
  with the key in the `x-api-key` header — 200 -> ok, 401/403 ->
  ValidationFailed("authentication failed"), anything else (incl. connect error
  -> 0) -> ("cannot reach provider"). Reasons never contain the key/url/response.
  The `run` seam is DI so tests are offline. Wired as the `connections`
  descriptor's hook (replaced #015's stub); other providers hit the no-op default
  (map miss). Tests: `test_connection_validation.py` (unit via stubbed runner:
  200/401/403/unreachable, endpoint-override url, key-absent-from-reason,
  non-anthropic-not-validated; plus API-level 401->400-not-stored and
  200->201). Filling the hook made `connections` writes really validate, so
  #015's `test_connections.py` gained an autouse fixture stubbing
  `connection_validation._get -> 200` to stay offline (openai/local/claude-code
  were already no-op). Gate clean (ruff format, ruff check --fix, pytest 161
  passed). Scope: anthropic only; openai/openai-compatible/claude-code validation
  is T44. Committed 5f4e0c5. Moved to verifying.
- 2026-08-15 qa: PASS -> po-review. Verified all dimensions (security pass +
  claude-api reference check on the endpoint shape). Confirmed against the
  Anthropic API reference that validation hits `GET /v1/models` with the
  `x-api-key` and `anthropic-version: 2023-06-01` headers - the correct
  no-inference-cost endpoint (a 200 proves the key authenticates). Drove the
  real hook through the live server: an `anthropic` connection whose `endpoint`
  points at an unreachable host exercises the real httpx `_get`, is rejected
  with a clean `400 {"detail":"cannot reach provider"}`, is NOT stored
  (subsequent GET -> 404), and the api-key canary appears in neither the 400
  body nor the server logs. Credential handling is sound: validation runs on the
  plaintext before #015's encryption, reasons are opaque ("authentication
  failed" / "cannot reach provider") and never echo the key, the key travels
  only in the `x-api-key` header (not embedded in a URL, so no process-table
  exposure), and the timeout is bounded (httpx.HTTPError -> 0 -> "cannot
  reach"). Dispatch is data-driven via the `_VALIDATORS` provider map (not an
  if/elif ladder), so T44 adds a map entry; non-anthropic providers keep the
  #015 no-op stub (proven by test_non_anthropic_provider_is_not_validated).
  Tests are regression-grade and offline/deterministic: the unit tests stub the
  `run` DI param for valid(200)/auth-reject(401,403)/unreachable(0)/endpoint-
  override/key-never-in-reason, and the integration tests monkeypatch
  `connection_validation._get` for write-rejected-not-stored (400 + row count 0)
  and write-accepted (201); #015's CRUD tests were kept offline by stubbing
  `_get` to 200. Dependency `httpx>=0.27,<0.29` correctly promoted to a runtime
  dep (the validator makes real HTTP calls); the pre-existing dev-group httpx
  entry is now redundant but harmless (out of scope). Code review clean: DI
  runner, typed, early returns, docstrings only, no emojis. Commit 5f4e0c5 is a
  proper atomic Conventional Commit. Re-ran the gate: ruff format clean (58
  files), ruff check passed, pytest 161 passed.
- 2026-08-15 PO: PASS -> done. Confirmed the endpoint shape in the code (GET
  <endpoint or api.anthropic.com>/v1/models with x-api-key + anthropic-version
  header - the correct no-inference validation) and drove the offline rejection
  live: an anthropic connection pointed at an unreachable endpoint is rejected
  400 {"detail":"cannot reach provider"} and NOT stored (GET -> 404); a
  non-anthropic provider (claude-code) is not validated (201, no-op stub); the
  api-key canary appears in neither the 400 body nor the server logs. Dispatch
  is a data-driven _VALIDATORS map (T44 adds an entry, no branch), key travels
  in the x-api-key header (not the URL), reasons are opaque, timeout bounded,
  tests offline via the DI runner. Ran the gate: ruff format (58 clean), ruff
  check clean, pytest 161 passed. Completes the T8 connections slice. Non-issue:
  the now-redundant dev-group httpx entry is harmless; drop it opportunistically
  when #010 touches httpx. No ticket. Closed at 5f4e0c5.
