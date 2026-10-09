---
id: 018
title: models registry (CRUD + kind discriminator) via the registry base
priority: high
size: medium
depends_on: [012]
spec_refs: [build-order.md#T9.1, implementation-notes.md#models]
---

## Context
`models` is the usage config for a text or embedding model; features reference
models by name into typed slots. With the registry base (#012) proven across
`sources` and `connections`, this is the third collection and should again be a
descriptor plus its pydantic model. It carries no secret of its own (the
provider credential lives on the referenced `connection`), so this is the
simplest registry yet — mostly the `kind` discriminator and the
connection reference. Validation (embedding load / text round-trip) is the
follow-on #019.

## Description
Add a `models` descriptor (recommend `src/hrono/registry/models.py`) and register
it via #012's `build_router`, like `sources`/`connections`:
- A pydantic v2 body with `kind` (`text` | `embedding`, kebab-case) discriminating
  the two, though both share the same shape per the spec (they differ only by
  output type): `name`, `kind`, `connection` (a connection name, or `null` =
  load & run in-process), `model` (the model id/path string), and a free-form
  `params` object (e.g. text: `temperature`/`max_tokens`; embedding:
  `dims`/`batch_size`). Keep `params` a permissive dict this ticket; slot/kind
  matching against trees is later.
- `secret_paths = ()` (models hold no secret; the credential is on the
  connection).
- `write_role = "writer"`.
- A validation hook seam wired but a no-op stub here (real load/round-trip
  validation is #019). Registering runs no model and loads nothing.

No engine or storage change — reuse the generic `registry` table; `kind` lives in
the config JSON. If the base needs any change to admit a secretless collection
(e.g. empty `secret_paths`), that change must be generic, not models-specific.

## Acceptance criteria
- [ ] `POST /models` registers both a `text` and an `embedding` model;
      `GET`/`GET <name>`/`PUT`/`DELETE` work via the base engine.
- [ ] `connection: null` (in-process) and `connection: "<name>"` (remote) both
      round-trip cleanly; `params` is preserved verbatim.
- [ ] `secret_paths=()` means no encryption/masking happens and the row stores a
      null key_id; a test asserts a model round-trips with no secret handling.
- [ ] Role gating and the error matrix come through the base unchanged: reader
      GET only (writer mutates; 401 unauth, 403 under-privileged), duplicate 409,
      invalid body (bad `kind`) 422, unknown name 404.
- [ ] Adding `models` required a descriptor + model only — no per-collection
      branch in the engine (state this in the review log; any base change is
      generic).
- [ ] Regression-grade tests cover text + embedding registration, connection
      null/named, params preservation, and the role/error matrix.
- [ ] `ruff format`, `ruff check --fix`, `pytest` all clean; work committed.

## Out of scope
- Embedding/text validation (#019 / T9.2+T9.3) — only the hook seam here.
- `kind`-vs-slot matching against trees (a later tree ticket).
- `prompts` collection (T10).

## Review log
- 2026-08-15 PO: authored on the #012 base. Third registry collection, secretless
  (`secret_paths=()`); a good check that the base handles a no-secret collection
  as cleanly as the secret-bearing ones.
- 2026-08-15 dev: picked up (dep 012 in done/), moved to in-progress.
- 2026-08-15 dev: implemented. New `registry/models.py`: a `Model` pydantic body
  (`name`, `kind: Literal["text","embedding"]`, `connection: str | None = None`,
  `model`, permissive `params: dict = {}`) and the `MODELS` descriptor with
  `secret_paths=()`, `write_role="writer"`, no-op validation hook (#019 fills it).
  Wired via `build_router(MODELS)` in create_app. NO engine or storage change:
  the base's empty-`secret_paths` path already no-ops (no encrypt/mask, null
  key_id) and `kind` lives in the config JSON — confirms the base admits a
  secretless collection with zero special-casing. Tests: `test_models.py` covers
  text + embedding registration (fetch echoes kind/connection/params), CRUD
  round-trip, `connection: null` and named both preserved, `params` preserved
  verbatim, secretless -> null key_id row, role matrix (401/403/reader GET),
  409 duplicate, 422 bad kind, 404 unknown. Gate clean (ruff format, ruff check
  --fix, pytest 167 passed). Third collection on the base; load/round-trip
  validation is #019. Committed a8dabdb. Moved to verifying.
- 2026-08-15 qa: PASS -> po-review. Verified all dimensions. AC5 (descriptor
  only, no engine change) proven at the diff level: `engine.py`, `store.py`, and
  `descriptor.py` are byte-for-byte unchanged since #012 - the base admits a
  secretless collection with zero generic change, because `secret_paths=()`
  naturally skips the encrypt/mask loops and leaves `key_id` null. Drove the
  real server: a `text` model (named connection, params) and an `embedding`
  model (`connection: null` in-process, nested params) both register 201 and
  round-trip via the base engine, with `params` preserved verbatim including a
  nested object/array (`{"nested":{"a":[1,2]}}`). Confirmed at the DB level that
  both secretless rows store `key_id = NULL` (no encryption/masking). Role/error
  matrix comes through the base unchanged: unauth GET 401, reader POST 403,
  writer mutates, duplicate 409, invalid `kind` ("vision") 422, unknown name
  404. `kind` is a plain `Literal["text","embedding"]` field (both kinds share
  one shape per the spec, so no discriminated union is needed - the minimal
  correct choice). Tests are regression-grade: parametrized text+embedding with
  a verbatim `params` comparison, `test_secretless_stores_null_key_id`, the full
  role/error matrix, and bad-kind 422, over both named and null connections.
  Code review clean: frozen descriptor, permissive `params` dict via
  `default_factory`, typed, docstrings only, no emojis; validation-hook seam a
  no-op stub for #019 as scoped. Commit a8dabdb is a proper atomic Conventional
  Commit. Re-ran the gate: ruff format clean (60 files), ruff check passed,
  pytest 167 passed.
- 2026-08-15 PO: PASS -> done. Confirmed the descriptor-only claim myself:
  `git diff 9a4af5b..HEAD` over engine.py/store.py/descriptor.py is EMPTY - the
  base admits a secretless collection with zero generic change (empty
  secret_paths naturally skips encrypt/mask, leaves key_id null). Drove the live
  server: text (named connection) and embedding (connection:null) models both
  register 201 and round-trip with params preserved verbatim including a nested
  object/array; bad kind 422, duplicate 409, unknown 404; and both rows store
  key_id NULL at the DB level. Ran the gate: ruff format (60 clean), ruff check
  clean, pytest 167 passed. Third collection on the base, clean. Unblocks #019
  (model validation). No adjacent work spun off. Closed at a8dabdb.
