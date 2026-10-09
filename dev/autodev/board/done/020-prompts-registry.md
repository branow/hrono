---
id: 020
title: prompts registry (CRUD + role typing) via the registry base
priority: high
size: medium
depends_on: [012]
spec_refs: [build-order.md#T10.1, implementation-notes.md#prompts]
---

## Context
`prompts` is the registry of prompt templates a tree references by name into
typed pipeline slots. It is the fourth and last M1 collection, again a descriptor
plus its pydantic model on the #012 base. It is secretless like `models`. This
ticket does CRUD + role typing; default seeding + the prompt-hash link for
invalidation is the follow-on #021 (which also handles the "delete a default
resets, does not remove" wrinkle).

## Description
Add a `prompts` descriptor (recommend `src/hrono/registry/prompts.py`) and
register it via #012's `build_router`, like the other collections:
- A pydantic v2 body: `name`, `role` (`condense` | `brief` | `brief-upper` |
  `judge`, kebab-case — fixes which pipeline slot the prompt can fill), and
  `template` (the prompt text with placeholders). Field keys `snake_case`.
- `secret_paths = ()` (no secret; null key_id).
- `write_role = "writer"`.
- A validation hook seam wired but a no-op stub here (there is no external
  validation for a prompt; #021 may use a hook for template sanity, otherwise it
  stays a stub).

Standard CRUD via the base only — GET list / GET one / POST / PUT / DELETE.
Default seeding and the default-reset-on-delete semantics are explicitly OUT of
this ticket (that is #021); here, DELETE removes a row like any other collection.
No engine or storage change — reuse the generic `registry` table; `role` lives in
the config JSON. Any base change to admit prompts must be generic.

## Acceptance criteria
- [ ] `POST /prompts` registers a prompt with a valid `role`; `GET`/`GET
      <name>`/`PUT`/`DELETE` work via the base engine.
- [ ] `role` outside `condense|brief|brief-upper|judge` is rejected 422; a valid
      prompt round-trips with `template` preserved verbatim.
- [ ] `secret_paths=()` -> null key_id row, no encryption/masking.
- [ ] Role gating + error matrix come through the base unchanged: reader GET
      only (writer mutates; 401 unauth, 403 under-privileged), duplicate 409,
      invalid body 422, unknown name 404.
- [ ] Adding `prompts` required a descriptor + model only — no per-collection
      engine branch (state this in the review log).
- [ ] Regression-grade tests cover registration for each valid role, bad-role
      422, template preservation, null key_id, and the role/error matrix.
- [ ] `ruff format`, `ruff check --fix`, `pytest` all clean; work committed.

## Out of scope
- Default seeding on first run + the "delete a default resets, not removes"
  behavior + prompt-hash link (#021 / T10.2).
- Slot/role matching against trees (later tree ticket).
- Any prompt-content/template validation beyond the role enum.

## Review log
- 2026-08-15 PO: authored on the #012 base. Fourth and final M1 collection.
  Kept default-seeding + default-reset semantics out of this ticket - they are
  the collection-specific part and belong in #021.
- 2026-08-15 dev: picked up (dep 012 in done/), moved to in-progress.
- 2026-08-15 dev: implemented. New `registry/prompts.py`: a `Prompt` pydantic
  body (`name`, `role: Literal["condense","brief","brief-upper","judge"]`,
  `template`) and the `PROMPTS` descriptor with `secret_paths=()`,
  `write_role="writer"`, and a no-op `_validate(config, context)` stub (the #019
  two-arg hook signature; #021 may fill it for template sanity). Wired via
  `build_router(PROMPTS)` in create_app. NO engine or storage change — `role`
  lives in the config JSON, secretless -> null key_id via the base's empty-
  secret_paths path. Fourth collection, zero special-casing: the #012 base is now
  proven across sources (secret), connections (secret + provider-union),
  models (secretless + connection ref), and prompts (secretless + role enum).
  Tests: `test_prompts.py` covers registration for each of the four roles (fetch
  echoes role/template), bad-role 422, CRUD round-trip with template preserved
  verbatim, null key_id row, and the role matrix (401/403/reader GET) + 409/404.
  Gate clean (ruff format, ruff check --fix, pytest 184 passed). Scope: default
  seeding + default-reset-on-delete + prompt-hash link are #021. Committed
  f42dcd2. Moved to verifying. **M1 registries CRUD is complete.**
- 2026-08-15 qa: PASS -> po-review. Verified all dimensions. AC5 holds:
  `engine.py`/`store.py`/`descriptor.py` are byte-for-byte unchanged since #019
  - `prompts` is a descriptor + pydantic model only, and its no-op `_validate`
  correctly uses the post-#019 `(config, context)` hook signature. Drove the
  real server: all four roles (condense, brief, brief-upper, judge) register
  201 and round-trip via the base engine with `template` preserved verbatim
  (placeholders and newlines intact); a bad `role` ("system"/"rewrite") -> 422;
  role/error matrix through the base unchanged (unauth GET 401, reader POST 403,
  writer mutates, duplicate 409, unknown name 404); PUT and DELETE behave like
  any collection (no default-reset semantics - correctly deferred to #021).
  Confirmed at the DB level that the secretless prompt rows store `key_id =
  NULL`. `role` is a plain `Literal[...]` field (fixes the pipeline slot),
  validated by pydantic. Tests are regression-grade: parametrized per-role
  registration with a verbatim template assertion, bad-role 422, PUT-replace
  round-trip, `test_secretless_stores_null_key_id`, and the full role/error
  matrix. Code review clean: frozen descriptor, typed, docstrings only, no
  emojis; the default-seeding/prompt-hash/default-reset wrinkle is correctly out
  of scope (#021). Commit f42dcd2 is a proper atomic Conventional Commit. Re-ran
  the gate: ruff format clean (64 files), ruff check passed, pytest 184 passed.
  This completes the four M1 registry collections (sources/connections/models/
  prompts).
- 2026-08-15 PO: PASS -> done. Confirmed engine/store/descriptor byte-for-byte
  unchanged since #019 (diff empty) - prompts is a descriptor + model only, with
  the no-op hook using the post-#019 (config, context) signature. Drove the live
  server: all four roles (condense/brief/brief-upper/judge) register 201 and
  round-trip with template preserved verbatim (placeholders + newlines); bad
  role 422, duplicate 409, unknown 404; all four secretless rows store key_id
  NULL. Ran the gate: ruff format (64 clean), ruff check clean, pytest 184
  passed. Completes the four M1 registry CRUD collections. Unblocks #021
  (default seeding + hash + reset-delete). No adjacent work spun off. Closed at
  f42dcd2.
