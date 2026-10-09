---
id: 021
title: prompt default seeding on first run + prompt-hash + default-reset delete
priority: high
size: medium
depends_on: [020]
spec_refs: [build-order.md#T10.2, implementation-notes.md#prompts, summarization-experiments.md]
---

## Context
The pipeline needs prompts to exist out of the box, so hrono ships defaults that
are seeded on first run; a user can override a default or add named variants. Two
collection-specific behaviors distinguish `prompts` from the other registries:
defaults are seeded automatically, and DELETE of a default resets it to the
shipped text rather than removing it (so the pipeline never loses a required
slot). This ticket adds those behaviors on top of #020's CRUD, plus the
prompt-hash link used later to invalidate exactly what a prompt produced.
Spun off from the T10 prompts slice.

## Description
Three pieces:
1. **Default seeding.** Ship the default prompt set (one per pipeline role:
   condense, brief, brief-upper, judge) - use the chosen recipes from
   `summarization-experiments.md` as the default templates. On startup, seed any
   missing defaults into the `prompts` collection if absent (idempotent, like the
   bootstrap-admin pattern in #007: seed-if-missing, never overwrite a
   user-modified prompt). Mark seeded rows as defaults so DELETE can reset them.
2. **Default-reset delete.** DELETE of a default prompt restores the shipped
   default text instead of removing the row (the row and its slot survive);
   DELETE of a non-default (user-added) prompt removes it as normal. A user
   override of a default (PUT) replaces the text but keeps the name; a subsequent
   DELETE resets it to the shipped default.
3. **Prompt-hash link.** Store a hash of each prompt's `template` on its row, so a
   future edit can invalidate exactly the entities that prompt produced. Store
   and update the hash on write; the actual invalidation propagation is DEFERRED
   (it needs trees / the update mechanism, like the staleness work in T58) - this
   ticket only lays the hash so nothing has to be back-filled later.

If the base needs a seam to admit seeding / default-reset (e.g. a descriptor-level
"defaults" provider or a "protected/default" flag), keep it generic (a
capability the base offers, keyed by descriptor data), not a `prompts`-specific
branch in the engine. Flag the design choice in the review log.

## Acceptance criteria
- [ ] First serve against a DB with no prompts seeds exactly one default per
      role (condense/brief/brief-upper/judge); a second serve seeds nothing new
      and does not overwrite a user-modified prompt (idempotent).
- [ ] DELETE of a default prompt resets it to the shipped default text (row +
      slot survive), verified by a subsequent GET returning the default; DELETE
      of a user-added prompt removes it (GET -> 404).
- [ ] A PUT override of a default changes its template; a following DELETE
      restores the shipped default.
- [ ] Each prompt row stores a hash of its template, updated on write (assert the
      hash changes when the template changes).
- [ ] Any base seam added for seeding/default-reset is generic (descriptor-driven
      or a base capability), not a prompts-only engine branch.
- [ ] Regression-grade tests cover first-run seeding, idempotent re-seed,
      no-overwrite of a modified prompt, default-reset-on-delete, user-prompt
      removal, override-then-reset, and the template-hash update.
- [ ] `ruff format`, `ruff check --fix`, `pytest` all clean; work committed.

## Out of scope
- Invalidation/staleness propagation from a prompt edit (needs trees; deferred,
  companions T58) - only store the hash here.
- Slot/role matching against trees.
- Tuning the default prompt text beyond adopting the summarization-experiments
  recipe.

## Review log
- 2026-08-15 PO: authored as the T10.2 follow-on to #020. Flagged that seeding +
  default-reset are the first collection-specific CRUD semantics - any base seam
  must stay generic, not prompts-special. Prompt-hash stored now; invalidation
  propagation deferred with the tree/update work.
- 2026-08-16 dev: picked up (dep 020 in done/), moved to in-progress.
- 2026-08-16 dev: implemented, all three seams GENERIC (keyed by descriptor
  data, no prompts branch in the engine). (1) `Descriptor.defaults: tuple[dict]`
  — prompts ships one default per role (condense/brief/brief-upper/judge)
  adopting the summarization-experiments recipe; other collections default to
  `()`. `registry/seeding.py::seed_defaults(conn, cipher, descriptors)` inserts
  missing defaults marked `is_default=1` (seed-if-missing, like #007 bootstrap);
  wired in the CLI after bootstrap over `registry/collections.py::COLLECTIONS`
  (also now the single source app.py iterates to mount routers). (2) Migration
  `0004_registry_defaults.sql` adds `is_default INTEGER NOT NULL DEFAULT 0` and
  `content_hash TEXT` to the generic registry table; the engine's `delete_item`
  resets an `is_default` row to its descriptor default (via `store.replace`,
  keeping the flag) and returns `{"reset": name}`, else removes it — generic for
  any collection with defaults. (3) `content_hash` (SHA-256 of the stored config
  body) written on every insert/replace for later invalidation. Extracted the
  shared write helpers (encrypt/mask/content_hash) into `registry/write.py` so
  the engine and seeding hash+encrypt identically; `store` gained `is_default`/
  `content_hash` columns (back-compat defaults keep existing callers working).
  Tests: `test_prompt_defaults.py` — one-default-per-role seed, idempotent
  reseed that never overwrites a user-modified row, default-reset-on-delete,
  user-prompt removal (404), override-then-delete restores the default, and the
  template-hash changes on write. Gate clean (ruff format, ruff check --fix,
  pytest 190 passed). Verified on the real binary: first serve seeds the 4
  defaults, restart stays at 4 (no reseed/overwrite), PUT-override then DELETE
  resets condense with the row + is_default=1 + content_hash intact. Scope:
  invalidation propagation from a prompt edit is deferred to the tree/update work
  (T58) — only the hash is laid here. **M1 registries complete.** Committed
  3158cb1. Moved to verifying.
- 2026-08-16 qa: PASS -> po-review. Verified all dimensions (deep pass on the
  first collection-specific-semantics ticket; developer lens on the base
  refactor). The seams are genuinely GENERIC (AC5): a descriptor-level
  `defaults: tuple[dict, ...]` field, `is_default` + `content_hash` columns on
  the shared `registry` table (migration 0004, forward-only, applied via
  `executescript` so both ALTERs land), a `seed_defaults(conn, cipher,
  descriptors)` that iterates ALL descriptors, a central `COLLECTIONS` tuple
  (app/cli loop over it), and a delete path that branches on the generic
  `row["is_default"]` + `_default_config(descriptor, name)` reading descriptor
  data - there is NO `collection == "prompts"` branch in the engine. The
  encrypt/mask/hash helpers were DRY'd into a shared `write.py` used by both the
  engine and seeding. Drove the full lifecycle through the real CLI serve path:
  first serve seeds exactly one default per role (condense/brief/brief-upper/
  judge); DELETE of a default returns `{"reset": name}` and the row survives
  (GET returns the shipped default text); PUT override changes the template and
  flips `content_hash`; DELETE of the override restores the shipped default;
  a user-added prompt DELETE returns `{"deleted": name}` and GET -> 404; after
  modifying `condense` to a sentinel and RESTARTING, the count stays 4 and the
  user's text is preserved (seed-if-missing, never overwrites). Seeding runs at
  the same single-writer pre-serve spot as bootstrap-admin (idempotent on
  restart). Tests are regression-grade and offline (drive `seed_defaults`
  directly): one-default-per-role, idempotent-reseed-no-overwrite,
  delete-resets-default, delete-removes-user-prompt, override-then-reset, and
  template-hash-updates-on-write. Minor non-blocking note: `content_hash` is a
  SHA-256 of the full stored config body (not the `template` field alone) - it
  satisfies the AC for prompts (template change flips the hash, verified) and is
  a generic per-collection content hash; for secret-bearing collections it is
  noisy under Fernet's non-determinism, but that column is unused until the
  deferred invalidation work (T58), so no impact today. Code review clean:
  generic descriptor-driven seams, DRY write helpers, typed, docstrings only, no
  emojis; invalidation propagation correctly deferred. Commit 3158cb1 is a
  proper atomic Conventional Commit. Re-ran the gate: ruff format clean (68
  files), ruff check passed, pytest 190 passed. This completes the M1 registries
  (T6-T10).
- 2026-08-16 PO: PASS -> done. Confirmed the critical requirement myself: the
  seeding/default-reset seams are GENERIC - grep finds no collection-specific
  branch in engine/store/write/seeding; the reset path reads `descriptor.defaults`
  via `_default_config` and branches on the generic `row["is_default"]`, and
  `seed_defaults` iterates all descriptors (prompts ships defaults, others `()`).
  Drove the full lifecycle on the real binary: first serve seeds exactly one
  default per role (brief/brief-upper/condense/judge); DELETE of a default
  returns {"reset": name} and the row survives with the shipped default; PUT
  override then DELETE restores the default; a user-added prompt DELETE removes
  it (GET 404); and after editing a prompt and RESTARTING, the count stays 4 and
  the user's text is preserved (seed-if-missing never overwrites). Ran the gate:
  ruff format (68 clean), ruff check clean, pytest 190 passed. Completes M1
  (registries T6-T10). Note for T58 (deferred invalidation): `content_hash` is
  SHA-256 of the full stored config body, so it is stable for the secretless
  collections that actually drive invalidation (prompts/models) but noisy for
  secret-bearing rows under Fernet nondeterminism - fine today (unused until
  T58), revisit when wiring edit->invalidation. Closed at 3158cb1.
