---
id: 141
title: the sources collection takes a source TYPE, not a git-shaped body
priority: high
size: medium
depends_on: [055]
spec_refs: [build-order.md#T40, build-order.md#M8, design-sketch-v1.md]
---

## Context
M8 (breadth) starts here. `registry/sources.py` models a source as exactly one
thing — `GitSource` with `type: Literal["git"]`, a `url`, a `GitAuth` and a
`GitFilter` — and `SOURCES` hard-wires `validate=validate_git`. A second source
type cannot be registered at all: not "registers badly", but is rejected by the
model. That is the first wall M8 hits, and the registry already shows the shape
that gets past it — `connections` is provider-discriminated and its validators
are a table.

This is the first of the three tickets #055 was split into. It does the MODEL
half only: after it, a non-git source can be REGISTERED and validated; syncing
it is #142 and reading its content is #143.

## Description
Make `sources` type-discriminated the way `connections` is provider-discriminated:

- Keep `GitSource` exactly as it is (fields, `node-` reservation, secrets) and
  make it one variant of a discriminated union keyed on `type`, with pydantic's
  discriminator so an unknown type fails validation with a message naming the
  types that exist.
- `SOURCES.model` becomes the union. `secret_paths` stays as it is — `auth.token`
  / `auth.key` are absent from a variant that has no auth, and the engine
  already skips a path it does not find (confirm this, and pin it with a test).
- `SOURCES.validate` becomes a dispatcher over a `_VALIDATORS[type]` table,
  `{"git": validate_git}`, mirroring `connections`. A type with no validator
  registers without a reach check rather than crashing.
- The union has ONE variant today. Do not invent a `confluence` or `notion`
  variant to prove the mechanism — a test variant registered into the table
  inside the test proves it without shipping a speculative model.

## Acceptance criteria
- [x] `sources` accepts a body by its `type` discriminator; git is one variant
      and behaves exactly as today (same fields, same `node-` rejection, same
      secret encryption at rest).
- [x] An unregistered `type` is rejected at the boundary with a message naming
      the known types — a clean 422, not a crash or a pydantic dump.
- [x] Validation dispatches from a per-type table; git still reach-checks, and a
      type with no validator registers without one.
- [x] A test registers a SECOND variant through the real registry engine (model
      + validator table entry only, no engine edit) and PUTs/GETs it — the
      property #055 asks for, demonstrated rather than asserted.
- [x] `ruff format`, `ruff check --fix`, `pytest` clean.

## Out of scope
- Syncing a non-git source (#142) and reading its content (#143).
- Shipping a real Confluence/Notion model (their own M8 tickets).
- Any change to git behaviour.

## Review log
- 2026-09-23 po: authored as the model third of #055, which is now split. M8 is
  the milestone that fires #055's own pull-in trigger ("before the second source
  type lands"), and M7 closed with #130.

- 2026-09-23 dev: `Source` is now a `RootModel` over a `type`-discriminated
  union (one variant, `GitSource`, unchanged), and `SOURCES.validate` is
  `validate_source`, a dispatcher over `source_validation.VALIDATORS`
  ({"git": validate_git}), in the same shape `connections` uses. A type with no
  entry registers without a reach check. `secret_paths` needed no change —
  `write._holder` already returns None for a path a variant lacks, and a test
  now pins that.

  Tests in `tests/registry/test_source_types.py`, with the second variant
  defined in the test rather than shipped. Mutations run, all killed:
  - `validate_source` never dispatching (validator = None) -> 2 tests fail.
  - an unmapped type raising instead of registering -> 1 fails.
  - the union replaced by `RootModel[dict]` (no discriminator) -> 3 fail.

  Note for qa: `validate_git` failing surfaces as 400, not 422 — that is
  existing behaviour of `ValidationFailed`, unchanged here, and the test says
  so rather than asserting the shape I expected.

- 2026-09-23 qa: PASSED. Every criterion met. Re-ran dev's first mutation (the
  validator table never dispatching -> 2 fail) and added one dev did not: every
  type receiving GIT's validator regardless of its own -> 3 fail. The dispatch
  is pinned in both directions.

  Driven live: `hrono serve` on 8133, `POST /sources` with a git body registers
  and reads back with its secrets masked; `POST /sources` with
  `type: "confluence"` is a 422 whose details name `git`. Code review: the
  union follows `connections` field for field, the validator module is one
  function over one table, and nothing speculative shipped — the second variant
  lives in the test, which is the right place for it until a real reader exists.

  One observation, not a defect: `validate_git` surfacing as 400 rather than
  422 is `ValidationFailed`'s existing behaviour, and the test records it
  instead of asserting what dev expected. Correct call.

- 2026-09-23 po: CLOSED. M8's first wall is down: a reader is now a model
  variant plus two table entries, demonstrated rather than asserted. Keeping
  the second variant in the test rather than shipping an unused `confluence`
  model is exactly the right restraint.
