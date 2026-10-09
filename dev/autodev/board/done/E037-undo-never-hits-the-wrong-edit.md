---
id: E037
title: a stale Undo never undoes a different edit
priority: medium
depends_on: [E036]
requirements: [61]
---

## Goal
`edit_log` ids are reused once the log empties, so a stale tab's "Undo
rename" can undo a later brief rewrite. Close that, and the E036 test gap.

## Tickets

### 1 an edit_log id is never reused
Change: rebuild `edit_log` with AUTOINCREMENT in a new migration (keep rows),
or have `undo` check kind + made_at as well as id.
Done when:
- [ ] rename -> undo -> rewrite brief -> post the stale undo for the rename:
  refused with an actionable message, the brief untouched; a test pins it
Look at: src/hrono/edits.py `undo`/`_record`, db/migrations/0040_edit_log.sql

### 2 the unknown-record undo test can fail
Change: seed a fresh brief (long text, real signature), keep a different
signature, assert `stale_or_missing` lists the node after undo.
Done when:
- [ ] the mutation "restore with the current signature" (edits.py:151) fails
  `test_an_undone_rewrite_of_an_unknown_record_is_rebriefed`
Look at: tests/server/test_ui_node_edits.py:549

### 3 `_write_brief` is type-checked; README true for old rows
Change: pass `briefs.upsert` its fields explicitly, drop the
`type: ignore` at edits.py:157; README:118 "goes back to the model and prompt
that wrote it, when hrono kept them".
Done when:
- [ ] no `type: ignore` in edits.py; type check clean
Look at: src/hrono/edits.py:157, README.md:118

## Out of scope
- undoing structural changes

## Log
- 2026-10-04 po: created from backlog/edit-log-id-reuse.md and E036-followups.md.
- 2026-10-04 dev: round 1 started.
- 2026-10-04 dev: tickets 1-3 in bb8daf4; tests/server/test_ui_node_edits.py (40 pass); mutations: drop AUTOINCREMENT fails test_a_stale_undo_never_undoes_a_later_edit, stale restore signature fails the unknown-record test. No type checker installed; type: ignore removed.
- 2026-10-04 qa: pass at bb8daf4; ran ruff and 489 affected tests (db, summarize, cluster, server UI edits); basedpyright on edits.py has 0 errors and no type: ignore; drove the undo routes over HTTP through the app and ran 0042 on a scratch db (rows kept, sqlite_sequence seeded, cascade intact); re-ran both dev mutations (both fail), plus mine: undo without the id check (2 fail) and dropping model_fingerprint on restore (1 fails); followups in backlog/E037-followups.md.
- 2026-10-04 po: accept at bb8daf4; all three Done-when met per qa; README edit true; qa's minors stay in backlog/E037-followups.md.
- merged to main at bb8daf4
