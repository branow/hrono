---
id: 012
title: Registry CRUD base, instantiated as `sources` (M1/T6 + T7.1)
priority: high
size: big
depends_on: [004, 006]
spec_refs: [build-order.md#T6, build-order.md#T7.1, implementation-notes.md#REST-API, design-sketch-v1.md]
---

## Context
M1 opens the registries. The four config collections (`sources`, `connections`,
`models`, `prompts`) share one uniform CRUD shape, so the spec builds a generic
**registry base** (T6) that each collection instantiates (T7-T10). This ticket
builds that base and proves it end to end by wiring the first collection,
`sources` (T7.1: config model + CRUD). It is the foundation every M1 registry
and the dashboard config views build on. Load `engineering:developer` (framework
shape) and `engineering:security` (secret handling) before starting.

Note on scope boundary: T6's line also mentions "shared-resource staleness
propagation". The spec realizes the tree-keyed dry-run/impact preview as **T58 in
M11** (it needs trees, which do not exist until M2+). So this ticket deliberately
excludes staleness/dry-run; it delivers CRUD + role gating + validation hook +
secret masking only.

## Description
Build a reusable registry mechanism, driven by a per-collection **descriptor**
(data), walked by one generic **engine** — not an if/elif ladder per collection:
- A descriptor declares: collection name (`sources`), the pydantic v2 body model,
  the set of secret field paths (for masking + encryption), the required write
  role, and an optional validation hook (callable run on write).
- The engine provides the uniform verb set as REST routes:
  `GET /<collection>` (list), `GET /<collection>/<name>` (fetch),
  `POST /<collection>` (create), `PUT /<collection>/<name>` (replace),
  `DELETE /<collection>/<name>`. `set` is POST-or-PUT per the CLI spec.
- **Role gating** via #006's `require_role`: reader may GET; writer may
  POST/PUT/DELETE. Enforced server-side.
- **Secret masking**: secret-declared fields are encrypted at rest via #004's
  `Cipher` (tagged with the active key_id) on write, and are **masked** (never
  returned in clear, e.g. `"***"`) on any GET. The plaintext secret leaves the
  server only never — it is write-only from the client's view.
- **Validation hook**: on POST/PUT, if the descriptor has a validation hook, run
  it and reject the write with a clear error if it fails (so no invalid/dead
  config is stored). For `sources` in THIS ticket the hook may be a no-op/stub;
  real git reach+auth validation is #013 (T7.2). Wire the hook seam now.
- **Error mapping** (clean JSON, correct status, no traceback): unknown name on
  GET/PUT/DELETE -> 404; duplicate name on POST -> 409; body failing model
  validation -> 422; validation-hook failure -> 400 with the reason.
- **Storage**: a forward-only migration for the sources rows (name PK, type,
  encrypted config/secret columns + key_id, created_at/updated_at as needed);
  reuse the `Database` owner (#008) for all access. Field keys `snake_case`,
  enum/type values `kebab-case`.

Instantiate `sources` (T7.1): the `git` single-repo body from
implementation-notes (name, type, url, auth{method}, optional filter). Registering
does NOT pull anything (pure declarative config). Only the `git` type here; other
source types are later tickets.

## Acceptance criteria
- [ ] The base is a data-driven descriptor + one engine; adding a second
      collection later requires a descriptor, not new branching in the engine
      (demonstrate the seam even though only `sources` is wired).
- [ ] `POST /sources` registers a git source (declarative; nothing is pulled);
      `GET /sources` lists; `GET /sources/<name>` fetches; `PUT` replaces;
      `DELETE` removes.
- [ ] Role gating holds: reader can GET but not POST/PUT/DELETE (403); writer
      can mutate; unauthenticated -> 401.
- [ ] A source `auth` secret (token/ssh key) is stored encrypted at rest (via
      #004, tagged key_id) and is masked in every GET response (never returned
      in clear); a test asserts the plaintext secret is absent from both the API
      response and the stored row in clear form.
- [ ] Error mapping is clean and traceback-free: unknown name -> 404, duplicate
      -> 409, invalid body -> 422, validation-hook rejection -> 400.
- [ ] The validation-hook seam exists and is invoked on write (a stub/no-op for
      git here is fine; #013 fills it).
- [ ] Regression-grade tests (TestClient) cover CRUD, role matrix, secret
      encryption+masking, and the full error-status matrix; a test fails if a
      secret leaks or a status regresses.
- [ ] `ruff format`, `ruff check --fix`, `pytest` all clean; work committed.

## Out of scope
- Git reach+auth validation (#013 / T7.2) — only the hook seam here.
- `connections`/`models`/`prompts` collections (T8-T10) — but the base must make
  adding them a descriptor, not an engine change.
- Staleness propagation / tree-keyed `?dry_run=true` impact + cost (T58, M11;
  needs trees).
- The `hrono sources` CLI subcommands (a later CLI ticket over #010's client).

## Review log
- 2026-08-15 PO: authored. This is `big` and cohesive (a framework only proves
  out with one real consumer, so T6+T7.1 ship together). If dev finds a clean
  seam to land the generic engine and the `sources` instance as two commits,
  splitting is welcome. Deferred the staleness/dry-run half to T58 per the spec.
  Depends on #006 (role gating) and #004 (secret cipher).
- 2026-08-15 dev: picked up (deps 004, 006 in done/), moved to in-progress.
- 2026-08-15 dev: implemented. New `registry` package: `descriptor.py` (frozen
  `Descriptor{collection, model, secret_paths, write_role, validate}` +
  `ValidationFailed`); `store.py` (generic CRUD over one `registry` table keyed
  by (collection, name), via the #008 `Database`); `engine.py`
  (`build_router(descriptor)` producing GET list/GET one/POST/PUT/DELETE, gated
  by #006 `require_role` via `dependencies=[...]`, encrypting secret_paths with
  #004 `Cipher` on write and masking them to "***" on every response, mapping
  errors 404/409/422/400); `sources.py` (git `GitSource` pydantic model + the
  `sources` Descriptor, secret_paths auth.token/auth.key, no-op validation hook
  seam for #013). Migration `0003_registry.sql` (generic table, key_id FK to
  keys). Design choice: ONE generic `registry` table (type lives inside the
  config JSON), so a new collection is a descriptor + `build_router`, no schema
  or engine change — demonstrated by `test_engine.py` wiring a synthetic
  `widgets` collection with a failing hook (proves the seam + 400 mapping).
  Storage stores the config JSON with secret fields replaced by ciphertext and
  the encrypting key_id on the row (NULL when no secret, e.g. auth.method=none).
  PUT is replace-existing-only (404 if absent) and 400s on path/body name
  mismatch. Tests: `tests/registry/test_sources.py` (CRUD, role matrix,
  unauth 401, secret encrypted-at-rest + masked in GET/POST with plaintext
  absent from both response and stored row, key_id tagged, 409/422/404/400
  matrix) and `test_engine.py` (descriptor seam + hook->400). Gate clean (ruff
  format, ruff check --fix, pytest 136 passed). Drove the live server: writer
  registers a git source (201), GET masks the token (plaintext absent), admin
  satisfies writer on PUT, 401/409/422/404 all correct. Scope: staleness/dry-run
  deferred to T58 per the ticket; git reach+auth hook is the #013 stub.
  Committed 9a4af5b. Moved to verifying for qa.
- 2026-08-15 qa: PASS -> po-review. Verified all dimensions (deep pass;
  developer + security lenses on a big M1-foundation ticket). Architecture is a
  genuinely data-driven `Descriptor` + one `build_router` engine with a generic
  `store` over a `(collection, name)` table; no per-collection branching. The
  seam is proven by `test_engine.py`, which wires a throwaway `Widget`
  descriptor through the same engine with zero engine changes (AC1). Drove the
  real server end to end: unauth POST /sources -> 401, reader POST -> 403,
  writer creates -> 201, reader GET -> 200, reader DELETE -> 403, writer DELETE
  -> 200. Secret handling verified at the byte level: a git `auth.token` is
  encrypted at rest (stored as Fernet ciphertext, `key_id=1` tagged) with the
  plaintext ABSENT from both the stored row and the entire DB file, and masked
  to `***` in the POST response and every GET (plaintext is write-only). Error
  matrix clean and traceback-free: duplicate -> 409, invalid body (bad `type`)
  -> 422, unknown name on GET/PUT/DELETE -> 404, validation-hook rejection ->
  400 (proven via the widgets `_reject_negative` hook), PUT path/body name
  mismatch -> 400. The validation-hook seam is wired and invoked on write; the
  git `_validate` is the intended #013 stub. `auth.method=none` stores a null
  key_id (nothing encrypted). Secret absent from server logs. Migration 0003 is
  the next forward-only number and reuses the #008 `Database` lock for all
  access; encryption happens outside the lock, the single INSERT/UPDATE inside
  it (atomic, PK-based duplicate detection). Tests are regression-grade and
  fail if a secret leaks or a status regresses. Code review clean: frozen
  descriptor, boundary pydantic validation, deepcopy to avoid mutating input,
  early returns, typed, docstrings only, no emojis, staleness/dry-run correctly
  deferred to T58. Commit 9a4af5b is a proper atomic Conventional Commit. Re-ran
  the gate: ruff format clean (52 files), ruff check passed, pytest 136 passed.
- 2026-08-15 PO: PASS -> done. Drove the live server myself on the two things
  this base must nail. Secret-at-rest: registered a git source with an
  auth.token, confirmed it is masked to "***" in both the POST response and
  every GET, and that the plaintext is ABSENT from the DB file AND the WAL at
  rest (write-only from the client's view, encrypted via #004 tagged key_id).
  Role/error matrix: unauth POST 401, reader POST 403, writer/admin POST 201,
  reader GET 200, duplicate 409, invalid body 422, GET/DELETE unknown 404,
  DELETE 200 - all clean JSON, no traceback. Architecture is a genuinely
  data-driven Descriptor + one build_router engine over a single
  (collection, name) table; adding a collection is a descriptor, not an engine
  change (seam proven by test_engine's synthetic widgets). Ran the gate: ruff
  format (52 clean), ruff check clean, pytest 136 passed. Staleness/dry-run
  correctly deferred to T58; git reach+auth hook is the #013 stub. This is the
  M1 foundation - connections/models/prompts (T8-T10) are now each just a
  descriptor. No adjacent work spun off. Closed at 9a4af5b.
