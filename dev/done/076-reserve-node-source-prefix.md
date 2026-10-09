---
id: 076
title: reserve the `node-` source-name prefix so briefs cannot collide with a user source
priority: low
size: small
depends_on: [013, 071]
spec_refs: [implementation-notes.md]
---

## Context
Spun off from #071 (brief passages) PO review (qa note). Brief passages are
stored under a synthetic `source` key `node-<id>` (`recall/brief_passages.py`),
which shares the same `sources.source` namespace as user-registered git sources.
A user source literally named `node-5` would collide with node 5's brief-passage
source key: `clear_source("node-5")` on a brief rebuild would also wipe that
user source's passages/FTS rows (and vice-versa) — silent cross-deletion.

Extremely unlikely (git sources aren't named `node-<int>`, and briefs are
internal), so it did NOT block #071. But the failure mode is silent data
corruption, and the fix is a tiny reserved-prefix rule.

## Description
Reserve the `node-` prefix for internal use in source-name validation (the git
source validator #013 / the sources descriptor validate hook):
- Reject a user attempt to register a source whose name starts with `node-`
  (clean ValidationFailed, consistent with the other registry validators).
- OR namespace brief-passage source keys so they cannot occupy the user source
  namespace at all (e.g. a distinct column / a prefix that is not a legal user
  source name). Pick the smaller, clearer change.
- Existing sources unaffected; the seeded/internal `node-<id>` keys still work.

## Acceptance criteria
- [ ] A user source named `node-<anything>` is rejected (or brief keys live in a
      namespace users cannot collide with).
- [ ] Brief-passage store/replace under `node-<id>` is unchanged and still scoped.
- [ ] A regression test proves a user source cannot clear a node's brief passages
      and vice-versa.
- [ ] `ruff format`, `ruff check --fix`, `pytest` all clean.

## Out of scope
- Any change to brief-passage addressing (`node://...`) — this is the internal
  `source` KEY namespace only.

## Review log
- 2026-08-25 PO: spun off from #071 PO review. Reserve the `node-` source-name
  prefix (or namespace brief keys) so a user source cannot collide with a node's
  brief-passage source key. Low priority (improbable, internal), but the failure
  mode is silent cross-deletion — cheap to close.
- 2026-09-21 PO: scope narrowed by #125, and the narrowing is now earned.
  #125's first attempt (`ef6ef60`) briefly ADDED a second collision direction —
  every node retirement silently deleted a colliding user source's FTS rows, at
  three sites, on every rebuild. `2129a2a` scopes both deletes by source type
  and `3f001ca` pins that with a mutation-checked test, so the retirement
  direction is closed by construction. What remains here is exactly what was
  filed: `ingest.store.clear_source` on a BRIEF REBUILD (`brief_passages.py:57`),
  which still matches on the source name alone. Still `low` — the re-brief path
  needs a user source literally named `node-<int>` to bite. Keeping it in
  backlog.

## Review log (dev)
- 2026-09-22 dev: implemented and committed. All four criteria.

  Took the SMALLER of the two fixes the ticket offered: reserve the prefix at
  the boundary. One `field_validator` and no migration, where re-namespacing the
  brief keys would touch the passage store, the FTS index and every stored row
  — for a collision that needs a user to name a repo `node-5`.

  **Case-insensitive, which is the half a prefix check usually gets wrong.**
  `store_brief` clears by the stored string, so refusing only the lower-case
  spelling would leave `NODE-5` free to be registered and then silently wiped.
  A mutation to `startswith` without the `.lower()` fails.

  **A PREFIX, not the word**: `nodejs-docs` and `my-node-5` are perfectly
  reasonable repos and are accepted. Mutating the check to `"node" in value`
  fails 5 tests, which is the guard against over-reserving a common English
  word in a namespace users choose freely.

  One test ties `RESERVED_PREFIX` to `brief_passages.SOURCE_TYPE`, so if #071's
  key shape ever changes this fails rather than leaving a reservation that
  guards nothing.

  As #125 recorded, the retirement direction was already closed by construction
  (its trigger matches `source_type` as well as name); this closes the
  re-brief direction, which is what remained.

  Gate clean: `ruff format`, `ruff check --fix`, `pytest` **953 passed**.

## Review log (qa)
- 2026-09-22 qa: **PASS — to po-review.** All four criteria met.

  **Case-insensitivity is the half that matters and it is pinned.** `store_brief`
  clears by the stored string, so a lower-case-only check would have left
  `NODE-5` registrable and then silently wiped — the bug, with a fix in front of
  it. The mutation to `startswith` without `.lower()` fails.

  Reserving a PREFIX rather than the word is equally load-bearing: `nodejs-docs`
  is an entirely ordinary repo, and mutating to `"node" in value` fails 5.

  Tying `RESERVED_PREFIX` to `brief_passages.SOURCE_TYPE` in a test is the
  detail I would have asked for — a reservation that silently stops matching the
  thing it reserves is worse than none.

## Review log (PO)
- 2026-09-22 PO: **PASSES — closed to done.** All four criteria met, and the
  last direction of a collision first noted in August is closed.

  Taking the smaller of the two fixes is right: one validator and no migration
  against re-namespacing the passage store, the FTS index and every stored row —
  for a collision that needs a user to name a repo `node-5`. Improbable, and the
  failure mode is silent cross-deletion in a namespace the user has no reason to
  know is shared, which is why it was never `low` for the right reasons.

  Case-insensitivity and prefix-not-word are both pinned, and tying the
  reservation to `brief_passages.SOURCE_TYPE` means it cannot silently stop
  guarding the thing it reserves.

  **This also closes the #125 arc.** That ticket shut the retirement direction
  by construction; this shuts the re-brief direction. The `node-` namespace is
  now hrono's, declared and enforced.
