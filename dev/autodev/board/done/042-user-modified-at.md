---
id: 042
title: users.modified_at — stamp a last-modified timestamp on user mutation
priority: low
size: small
depends_on: [005, 033]
spec_refs: [build-order.md#T4.1]
---

## Context
`User` currently records only `created_at`. There is no field that tells you a
row was changed after creation, and there is now at least one code path that
mutates a user in place without leaving any trace: `hrono admin reset-token`
(#033) rotates a user's `token_hash` but records nothing. As more user-mutating
operations arrive (role change, token rotation over HTTP, manual edits in M9),
"when was this user last touched" becomes a real question with no answer today.

This ticket is deliberately deferred, NOT authored into todo: a `modified_at`
added now would equal `created_at` for every row's whole life, because no op
mutates a user except the token rotation in #033. That is a speculative dead
column, which CLAUDE.md forbids. Pull this into todo only when the FIRST user
mutation that should bump it lands (or retro-wire it onto #033's reset-token).

## Description
Add a `modified_at TEXT NOT NULL` column to `users` (ISO-8601 UTC), defaulting
to `created_at` at creation, and update it on every in-place user mutation.

- Migration: forward-only `NNNN_users_modified_at.sql`; backfill existing rows
  with `modified_at = created_at`.
- `User` gains a typed `modified_at: str` field (frozen model unchanged in
  shape otherwise).
- `create_user` sets `modified_at = created_at`.
- Every mutating op stamps `modified_at = now(UTC)`: at minimum the #033
  `admin reset-token` rotation; plus any role-change / token-rotation op that
  exists when this is pulled in.
- Do NOT expose the token or its hash — this only adds a timestamp.

## Acceptance criteria
- [x] `users` has a `modified_at` column; existing rows backfilled to
      `created_at` by the migration.
- [x] `create_user` returns a `User` whose `modified_at == created_at`.
- [x] `admin reset-token` (and any other in-place user mutation present at pull-in
      time) updates `modified_at` and leaves `created_at` unchanged.
- [x] `get_user` / `list_users` surface `modified_at`; token/hash still never
      exposed.
- [x] Regression-grade tests: create sets both equal; a mutation bumps
      `modified_at` strictly past `created_at` while `created_at` is untouched.
- [x] `ruff format`, `ruff check --fix`, `pytest` all clean; work committed.

## Out of scope
- Any new mutation op itself (role change, HTTP token rotation) — this only adds
  and maintains the timestamp on ops that already exist when pulled in.
- Audit history / full change log — a single last-modified stamp, not an event
  trail.

## Review log
- 2026-08-22 stakeholder: suggested during commit-by-commit review of #005.
  PO framing: agreed as a backlog item, NOT for now — no user-mutation path
  makes it non-speculative yet except #033's in-place token rotation. Pull into
  todo when the first mutating op that should bump it lands.
- 2026-09-27 po: PULLED IN. The trigger this ticket set is the weaker half of
  its own condition — `reset_token` (#033) is still the only in-place mutation
  — but the question it answers has become a real one: with the dashboard
  shipped and master-key rotation in (#177), an operator auditing credentials
  has no way to ask "when was this token last rotated". A token issued two
  years ago and never rotated looks exactly like one rotated this morning.
  That is not a speculative column; it is the one fact the users table is
  missing for the only audit anyone does with it.
- 2026-09-27 dev: `0035_users_modified_at.sql`, `User.modified_at`, stamped by
  `create_user` and moved by `reset_token`; `GET /users` carries it.
  - `reset_token` returns the user with the NEW stamp. It used to hand back the
    row it read before the UPDATE, which would have had `admin reset-token`
    report the moment before the rotation it had just done.
  - Mutations, all killed: the rotation not stamping; the old object returned;
    creation stamping something other than `created_at`.
  - Two existing tests changed meaning rather than shape: "the target's
    non-secret columns are untouched" is now "its identity is untouched and
    only the rotation stamp moves", which is the claim #042 makes.
  - UPGRADE DRIVE on a real old database, built in a `git worktree` at the
    previous commit: the column appears, the legacy row backfills to its own
    `created_at`, and a rotation then moves it while `created_at` holds.
  - Gate: 1397 passed, 2 skipped.
