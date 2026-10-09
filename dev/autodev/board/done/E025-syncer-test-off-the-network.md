---
id: E025
title: the missing-syncer test never reaches a real provider
priority: medium
depends_on: []
requirements: []
---

## Goal
`test_a_type_with_no_syncer_fails_by_name` registers a `notion` source; Notion
now has a syncer, so the test calls api.notion.com and fails offline. It no
longer tests what its name says.

## Tickets

### 1 a type with no syncer, for real
Change: register a source type that has no syncer (a fake type registered in
the test, or one genuinely without), assert the error names it.
Done when:
- [ ] the test passes with the network off (no socket opened)
- [ ] removing the "no syncer" error path makes it fail (mutation-checked)
Look at: tests/ingest/test_syncer_dispatch.py, src/hrono/ingest/sync.py

## Out of scope
- other network-reaching tests (file a backlog line if found)

## Log
- 2026-10-03 po: created from backlog syncer-dispatch-test-reaches-the-network (E013 sandbox).
- 2026-10-03 dev: ticket 1 39dfd27; passes with socket.connect disabled; mutation: no-syncer raise removed -> test fails, restored.
- 2026-10-03 qa: pass 39dfd27; ran test_syncer_dispatch.py (4 pass) and the no-syncer test with socket connect/create_connection blocked (pass; main's notion version fails the same way); mutations: no-syncer raise -> bare return (dev's), message without type name, SYNCERS[...] KeyError path -> all fail the test.
- 2026-10-03 po: accept 39dfd27; both Done-when met by qa's offline run and three mutations; test-only, no user docs affected.
- merged to main at 39dfd27
