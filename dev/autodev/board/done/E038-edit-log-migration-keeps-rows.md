---
id: E038
title: polish — the edit_log rebuild is pinned to keep its rows
priority: low
depends_on: [E037]
requirements: []
---

## Goal
Migration 0042 rebuilds `edit_log`; nothing tests that it keeps the rows a
user already has. A data-losing edit to it would pass the suite today.

## Tickets

### 1 0042 keeps existing edit_log rows
Change: add a migration test: apply up to 0041, insert an edit_log row,
apply 0042, assert the row survives unchanged and the next inserted id is
above it (sqlite_sequence seeded).
Done when:
- [ ] the test passes on main
- [ ] it fails if 0042 drops the copy step, and if it skips seeding the
  sequence (both mutations run and noted in the Log)
Look at: db/migrations/0042_edit_log_autoincrement.sql,
tests/db/test_migrations.py, src/hrono/db/migrations.py

## Out of scope
- reflowing README.md:118-120 (taste)

## Log
- 2026-10-04 po: created from E037-followups.md (qa r1, migration line).
- 2026-10-04 dev r1: ticket 1 ec714c2; tests/db/test_migrations.py (rebuild keeps rows, ids stay above). Mutations, all fail the test: drop copy step; drop AUTOINCREMENT; copy without ids.
- 2026-10-04 qa r1: pass at ec714c2; ruff clean, tests/db 40 passed; re-ran drop-copy and drop-AUTOINCREMENT (both fail), own: copy without the before column (fails); clearing sqlite_sequence after the copy still passes, an equivalent mutant since SQLite takes max(seq, max id). No followups.
- 2026-10-04 po: accept ec714c2; Done-when met (seed mutant equivalent, id reuse pinned by drop-AUTOINCREMENT). Not filed (polish): test asserts migrate()==(42,), will need widening when 0043 lands.
- merged to main at ec714c2 by dev (full suite 2350 passed)
