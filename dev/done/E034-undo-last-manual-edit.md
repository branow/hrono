---
id: E034
title: a curator can undo the last manual edit on a topic
priority: low
depends_on: [E033]
requirements: [61]
---

## Goal
A curator who renamed a topic, rewrote its brief or added a note by mistake
can undo it in one click, instead of re-typing what was there.

## Tickets

### 1 a manual edit records what it replaced
Change: rename, brief rewrite and note record the prior value (and who, when)
in the same transaction as the edit, in `edits.py`.
Done when:
- [ ] each of the three leaves one row holding the before-value
- [ ] a failed edit leaves no row
Look at: src/hrono/edits.py, src/hrono/server/edits.py

### 2 Undo on the topic page
Change: the topic page offers "Undo <edit>" for the topic's latest recorded
edit; it restores the before-value (a rewrite restores the E033 version) and
keeps the pin rules of edits.py. Confirm first, stating what will change (58).
Done when:
- [ ] driven: rename, undo -> old name back; rewrite, undo -> old brief back
- [ ] a reader gets 403; undo twice does not re-apply an older edit
Look at: src/hrono/server/ui/nodes.py, templates/node.html

### 3 the version list keeps only what it uses, and is pinned
Change: in `_version_line` drop the unused `who`; write the leading-gap test
as `if number or group[0][1] or group[0][3]:`; drop the no-op
`user-select: none` on `.diff-*::before` (base.html:373).
Done when:
- [ ] a page test shows a regeneration-replaced version and asserts
  "replaced by a regeneration"
- [ ] the version-list tests still pass unchanged otherwise
Look at: src/hrono/server/ui/nodes.py:425-450, templates/base.html,
tests/server/test_ui_node_edits.py

## Out of scope
- undo of structural edits (move, merge, split, dissolve)
- a multi-step undo history

## Log
- 2026-10-04 po: created from REQUIREMENTS.md 61 (optional). Structural undo left out: reversing a merge/split is a re-cluster, not an undo.
- 2026-10-04 po: + T3 from E035-followups (same file, nodes.py). README wrap and commit-split lines rejected as taste/process.
- 2026-10-04 dev: T3 bd41cde; tests in test_ui_node_edits.py; mutated the leading-gap test (`if number` fails it). `number or` is redundant by construction (a later group never starts at line 0), so that mutant survives as equivalent.
- 2026-10-04 dev: T1+T2 bc2ac90 (one commit, wiring of `who` and undo share nodes.py); driven through the real app via TestClient, full suite green. Mutations: no log clear, no latest-id check, note ref lost, rename not logged: each fails a test. Not driven in a browser or `hrono serve`.
- 2026-10-04 qa: pass at bc2ac90. Drove rename/undo (old name back, unticked refused, Undo gone after), rewrite/undo (old brief back, "stands"), note/undo (note gone) in Chromium against the live app; affected tests 801 passed; ruff clean. Re-ran dev's no-log-clear mutant (2 fail) and mine: no-earlier-brief filter dropped (fails); restored brief not re-pinned (survives, pin already held; followup). Followups: backlog/E034-followups.md.
- 2026-10-04 po: accept at bc2ac90. Done-whens met per qa's live drive; README states Undo. Release-leaves-edit_log and the rest are minor: backlog/E034-followups.md.
- merge: landed on main at bc2ac90 (ff)
