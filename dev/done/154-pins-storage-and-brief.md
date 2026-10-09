---
id: 154
title: a hand-edit pins what it touched, and brief regen respects the pin
priority: high
size: medium
depends_on: [064]
spec_refs: [build-order.md#T45.1, build-order.md#T45.2, implementation-notes.md]
---

## Context
M9 opens here. The spec's rule is one sentence and the whole milestone depends
on it: "A hand-edit pins the entity, and the pipeline treats a pin as a hard
constraint ... Without this, a manual fix gets silently reverted on the next
update." Every endpoint T46-T48 adds is worthless until a pin actually stops
the pipeline, so the pin lands first, with the pipeline honouring it, and the
endpoints follow.

## Design, decided
- A pin is a ROW, not a boolean smeared across tables: `pins(kind, target_id,
  reason, pinned_at)` where `kind` is `brief`, `membership` or `parenting`.
  One table answers "is this pinned" for every surface, and a new pinnable
  thing is a new `kind` rather than a migration per table.
- Pinning is a CONSEQUENCE of editing, never a separate call the user must
  remember: the endpoints in #156-#160 write the pin in the same transaction as
  the edit. `unpin` is the only explicit pin operation.
- A pinned brief keeps its text AND its stored signature untouched, so nothing
  downstream sees it as stale and tries again on the next batch.

## Description
- Migration: the `pins` table plus its index.
- `pins.py`: `pin(conn, kind, target_id, reason)`, `unpin(conn, kind,
  target_id)`, `is_pinned(conn, kind, target_id)`, `pinned(conn, kind)`.
- `brief` (and `brief-upper`): a node whose brief is pinned is SKIPPED — not
  regenerated, not re-signed, not counted as produced. The op's outcome counts
  gain `skipped_pinned` so the operator can see it happened (#132/#133).
- A retired node's pins go with it (cascade), like its brief.

## Acceptance criteria
- [x] A pinned brief survives a `brief` run that would otherwise regenerate it:
      same text, same stored signature, and the run reports it as skipped.
- [x] An unpinned sibling in the same run IS regenerated — the skip is the
      pin's doing, not the run doing nothing.
- [x] `unpin` hands it back: the next run regenerates it.
- [x] Deleting a node removes its pins.
- [x] `ruff format`, `ruff check --fix`, `pytest` clean.

## Out of scope
- The endpoints that create pins (#156 onward) — this ticket's tests pin
  through the store.
- `settle` honouring membership/parenting pins (#155).

## Review log
- 2026-09-23 po: authored. M9's foundation; everything else in the milestone
  depends on the pin being a hard constraint first.

- 2026-09-23 dev: `pins` is one table keyed (kind, target_id) with two triggers
  so a retired node and a deleted section take their pins with them — a pin on
  an id the tree no longer holds would otherwise apply to whatever is created
  with that id next. `hrono/pins.py` imports nothing of hrono's, so every layer
  can ask without a cycle.

  The skip happens at SELECTION (`briefs.stale_or_missing`), not after the
  call: a pinned node then costs nothing, and no caller can forget to check.
  Both `brief` and `brief-upper` now return `{briefed, skipped_pinned}` — they
  returned nothing before, and "briefed 0" needs to distinguish "nothing to do"
  from "you froze it yourself" (#132/#133).

  Mutations run, all killed: selection ignoring the pin -> 3 fail; the retired
  node keeping its pins -> 1; any string accepted as a kind -> 1.

  One note on the tests, because it bit me: the first version made a node stale
  by writing `member_signature = 'stale'` directly, so "the pin did not
  re-sign it" compared 'stale' to 'stale' and proved nothing. The nodes now go
  stale the REAL way — each gains a member — and the stored signature is the
  original one throughout.

- 2026-09-23 qa: PASSED. Re-ran dev's selection mutation (3 fail) and added one
  they did not: an unknown kind accepted silently — still killed. The pin
  vocabulary is closed, which matters because a typo'd kind would create a row
  nothing ever reads and an operator would believe their edit was protected.

  The skip at SELECTION rather than after the call is the right design: a
  pinned node makes no LLM call at all, and that is pinned by its own test.

  On dev's own test note — the first version compared 'stale' to 'stale' — that
  is the fourth instance of this family on the board, and it was caught by dev
  rather than by me. The convention is working.

- 2026-09-23 po: CLOSED. M9 has its foundation and it is the right one: a pin
  is a row with a kind, so the next pinnable thing costs an entry rather than a
  migration, and it records WHY — a frozen topic with no explanation is a
  mystery someone eventually resolves by deleting it.
