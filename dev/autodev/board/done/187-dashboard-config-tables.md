---
id: 187
title: the dashboard's config tables, with secrets masked
priority: medium
size: small
depends_on: [180, 054]
spec_refs: [build-order.md#T55]
---

## Context
T55: "Config tables + dry-run modals". **The tables ship; the dry-run modals do
not**, because `?dry_run=true` does not exist — #178 is parked on a cost record
that only landed with #179. A modal over an endpoint that is not there is the
dead button #180 shipped and qa caught.

## Description
- `GET /ui/config` — every registry collection (sources, connections, models,
  prompts, trees) as a table: name, the fields that identify it, and whether it
  is a seeded default.
- **Secrets masked, through the registry's own `mask()`** and not a second
  redaction — one masking rule, already tested, already reading each
  collection's declared `secret_paths` (#142).
- Read-only. Editing config from the page is T55's other half and wants the
  dry-run beside it; a writer uses the CLI or the API until then.

## Acceptance criteria
- [x] Every collection is listed with its items.
- [x] A source's token is masked on the page — asserted against a REAL secret,
      not a placeholder. A connection's key too (qa).
- [x] A seeded default is marked as one.
- [x] An empty collection says so.
- [x] Reader-visible; nothing on the page writes.
- [x] `ruff format`, `ruff check --fix`, `pytest` clean.

## Review log
- 2026-09-27 po: authored, with the dry-run half explicitly deferred to #178.
- 2026-09-27 dev: `GET /ui/config` in `server/ui.py` + `templates/config.html`,
  a nav link in `base.html`. Every `COLLECTIONS` descriptor rendered through
  the registry's own `mask()` — no second redaction here, so a source type
  whose credential path moves is covered by declaring it (#142).
  - The template key had to be `rows`, not `items`: `collection.items` in
    Jinja resolves to `dict.items` and renders a bound method, not the list.
  - The fixture seeds through the production `seed_defaults` (#021) rather than
    planting `is_default=1` — a planted flag would have proved the template
    and said nothing about what `hrono serve` actually marks.
  - Mutations, all killed: (1) drop `mask()` -> the ciphertext assertion fails;
    (2) drop the `(default)` marker -> default test fails; (3) `Reader` ->
    `Writer` -> the reader test fails; (4) `COLLECTIONS[:1]` -> 3 fail.
  - Driven live against `hrono serve` on :8791 with a REAL Fernet-encrypted
    source token: page shows `"token": "***"`, neither the plaintext nor the
    stored ciphertext appears, the four seeded prompts are marked `(default)`,
    and connections/models/trees each say "no ... configured."
  - Gate: 1307 passed, 2 skipped.
- 2026-09-27 qa: verified, with one finding raised and fixed.
  - FINDING (fixed): masking every row with ONE descriptor — `COLLECTIONS[0]`
    instead of the loop variable — left all eight route tests green. It is the
    "property held by something else" shape: `sources` declares BOTH
    `auth.token` and `auth.key`, and every other collection's declared path is
    a subset of that, so the wrong descriptor still produces a correct page
    today. It stops being correct the first time a collection declares a path
    nobody else has, and the failure mode is a credential printed in a browser.
  - Fix: the assembly moved to `server/config_view.py` with `descriptors`
    passed in (injection, not monkeypatching), so the pairing is asserted
    directly in `tests/server/test_config_view.py` against two synthetic
    descriptors with disjoint secret paths. Mutations: wrong descriptor for
    every row -> fails; `COLLECTIONS[:2]` as the default -> fails.
  - Also added: a connection's key masked on the page, against a REAL encrypted
    secret — the route tests covered one collection's credential, not two.
  - Re-driven live on :8792 after the extraction: neither ciphertext on the
    page, two masks, the nav link present from `/ui`.
  - Gate: 1311 passed, 2 skipped.
- 2026-09-27 po: accepted. Every criterion met and the qa finding is the kind
  this ticket existed for — a masking bug that renders correctly is exactly how
  a credential reaches a browser unnoticed. T55's other half (editing config
  from the page, with the dry-run beside it) stays with #178.
