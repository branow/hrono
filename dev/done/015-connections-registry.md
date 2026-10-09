---
id: 015
title: connections registry (CRUD + secret encryption) via the registry base
priority: high
size: medium
depends_on: [012]
spec_refs: [build-order.md#T8.1, implementation-notes.md#connections]
---

## Context
`connections` are provider credentials (one per provider account) that models
reach LLM/embedding APIs through. With the registry base (#012) proven, adding a
collection is a descriptor plus its pydantic model — no engine change. This
ticket instantiates `connections` (T8.1: CRUD + secret encryption), reusing the
base's generic CRUD, role gating, secret encryption-at-rest, and masking. It is
the second collection, and it proves the base generalizes beyond `sources`.
Provider reachability validation (anthropic list-models) is the follow-on #016.

## Description
Add a `connections` descriptor (recommend `src/hrono/registry/connections.py`)
and register it via #012's `build_router`, exactly like `sources`:
- A pydantic v2 body discriminated on `provider`, covering the v1 providers from
  the spec:
  - `anthropic` — `auth {method: "api-key", key}`, optional `endpoint` override.
  - `openai` — identical shape to anthropic.
  - `openai-compatible` — local servers (ollama/vllm/lm-studio); `endpoint` set,
    `auth` usually `{method: "none"}` (allow an optional key).
  - `claude-code` — `auth {method: "none"}`; no key (rides the server's logged-in
    CLI session).
  Field keys `snake_case`, provider/method values `kebab-case`.
- `secret_paths = (("auth", "key"),)` so the api-key is encrypted at rest via
  #004 and masked to `***` on every GET/POST — the base already does this; a
  `none`-auth connection stores no secret (null key_id), same as `sources` with
  `auth.method=none`.
- `write_role = "writer"`.
- A validation hook seam wired but a no-op stub in THIS ticket (real anthropic
  list-models validation is #016; other providers' validation is T44). Registering
  does not perform any inference.

No new engine or storage code — the generic `registry` table (#012) holds these
rows too; `provider` lives inside the config JSON. If anything in the base needs
a small change to admit `connections`, that is a signal the base leaked a
collection assumption — fix it in the base, do not special-case connections in
the engine.

## Acceptance criteria
- [ ] `POST /connections` registers each provider shape (anthropic, openai,
      openai-compatible, claude-code); `GET`/`GET <name>`/`PUT`/`DELETE` work via
      the base engine.
- [ ] An `api-key` secret is encrypted at rest (via #004, tagged key_id) and
      masked to `***` in every response; a test asserts the plaintext key is
      absent from both the API response and the stored row.
- [ ] A `claude-code`/`none`-auth connection stores no secret (null key_id) and
      round-trips cleanly.
- [ ] Role gating and the error matrix come through from the base unchanged:
      reader GET only (writer to mutate; 401 unauth, 403 under-privileged),
      duplicate 409, invalid/unknown-provider body 422, unknown name 404.
- [ ] Adding `connections` required a descriptor + model only — no per-collection
      branch added to the engine (state this in the review log; a base change, if
      any, is generic).
- [ ] Regression-grade tests cover each provider shape, secret encryption +
      masking, none-auth no-secret, and the role/error matrix.
- [ ] `ruff format`, `ruff check --fix`, `pytest` all clean; work committed.

## Out of scope
- Provider reachability validation (anthropic list-models is #016; other
  providers are T44) — only the hook seam here.
- `models`/`prompts` collections (T9/T10).
- Actually calling any provider / running inference.

## Review log
- 2026-08-15 PO: authored on the #012 base. Second registry collection; should
  be a descriptor + provider-union model, proving the base generalizes. Flagged
  that any base change to admit it must stay generic, not connection-specific.
- 2026-08-15 dev: picked up (dep 012 in done/), moved to in-progress.
- 2026-08-15 dev: implemented. New `registry/connections.py`: per-provider
  pydantic models (anthropic/openai with `ApiKeyAuth`, openai-compatible with
  required endpoint + optional-key auth, claude-code with none auth) combined
  into a `RootModel` discriminated union on `provider`; `CONNECTIONS` descriptor
  with `secret_paths=(("auth","key"),)`, `write_role="writer"`, no-op validation
  hook (real anthropic list-models is #016). Wired via `build_router(CONNECTIONS)`
  in create_app. NO engine or storage change: using a `RootModel` kept
  `descriptor.model` a BaseModel subclass so the base's `model_validate` /
  `model_dump` path works untouched; the generic `registry` table holds these
  rows with `provider` inside the config JSON. Tests: `test_connections.py`
  covers all four provider shapes (201 + fetch), CRUD round-trip, api-key
  encrypted-at-rest + masked with plaintext absent from response AND stored row
  (key_id tagged), claude-code/none -> null key_id, role matrix (401/403/reader
  GET), and 409/422(unknown provider)/422(missing key)/404. Gate clean (ruff
  format, ruff check --fix, pytest 153 passed). Confirms the #012 base
  generalizes to a second collection with a descriptor + model only. Scope:
  provider reachability validation is #016 (hook seam only here). Committed
  cdf81d0. Moved to verifying.
- 2026-08-15 qa: PASS -> po-review. Verified all dimensions. The headline AC5
  (new collection = a descriptor, not an engine change) is proven at the diff
  level: the commit touches only a new `connections.py` (a
  provider-discriminated `RootModel` + `Descriptor`) and a 2-line
  `app.include_router(build_router(CONNECTIONS))` wiring; `engine.py`,
  `store.py`, and `descriptor.py` are byte-for-byte unchanged since #012. Drove
  the real server: all four provider shapes (anthropic, openai,
  openai-compatible, claude-code) register 201 and round-trip via the base
  engine (the `RootModel` discriminated union dumps to a clean config the engine
  consumes). An `api-key` is encrypted at rest (stored ciphertext, key_id=1
  tagged) and masked to `***` in POST and GET responses; byte-level check
  confirms the plaintext key is absent from the stored row, the whole DB file,
  and the server logs. `claude-code` and `openai-compatible` none-auth
  connections store a null key_id (no secret). Role/error matrix comes through
  the base unchanged: unauth GET 401, reader POST/DELETE 403, writer mutates,
  duplicate 409, unknown provider (cohere/gemini) 422, missing api-key 422,
  unknown name 404 (all re-confirmed live with valid JSON). Tests are
  regression-grade: per-shape registration, encryption+masking asserted on both
  the response and the stored row, none-auth null key_id, and the full
  role/error matrix. Code review clean: provider Literals as kebab-case, frozen
  descriptor, typed, docstrings only, no emojis, validation-hook seam a no-op
  stub for #016 as scoped. Commit cdf81d0 is a proper atomic Conventional
  Commit. Re-ran the gate: ruff format clean (56 files), ruff check passed,
  pytest 153 passed.
- 2026-08-15 PO: PASS -> done. Confirmed the headline requirement myself at the
  diff level: `git diff 9a4af5b..HEAD` over engine.py/store.py/descriptor.py is
  EMPTY - the base generalized to a second collection with only a new
  connections.py (provider-discriminated RootModel + Descriptor) + a 2-line
  router wiring. Drove the live server: all four provider shapes (anthropic,
  openai, openai-compatible, claude-code) register 201; api-key masked to *** in
  POST and GET with the plaintext absent from the DB/WAL at rest (encrypted,
  key_id tagged); none-auth (claude-code/openai-compatible) store no secret;
  unknown provider 422, missing key 422, duplicate 409, unknown name 404. Ran
  the gate: ruff format (56 clean), ruff check clean, pytest 153 passed. Proves
  the #012 registry base is a real framework. Unblocks #016 (anthropic
  validation). No adjacent work spun off. Closed at cdf81d0.
