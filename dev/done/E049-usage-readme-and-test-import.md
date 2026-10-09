---
id: E049
title: polish — the Usage README line says what is windowed; one json import
priority: low
depends_on: [E047]
requirements: []
---

## Goal
The README tells a reader the whole agent-calls card covers 30 days, not only
the confidence share; a test helper stops re-importing json.

## Tickets

### 491 the README says the whole card covers the last 30 days
Change: README.md:105-106 (as left by E047) reads "over the last 30 days, a
count per day and the share it was not confident about"; rewrap to 80.
Done when:
- [ ] the line names the 30-day window for the count, the days and the share
- [ ] no line of that paragraph over 80 chars (other long README lines are out of scope)
Look at: README.md

### 492 the topic-filter test helper uses the module's json
Change: drop the local `import json as _json` in the helper and use `json`.
Done when:
- [ ] tests/server/test_ui_browser.py has no local json import; test passes
Look at: tests/server/test_ui_browser.py:496

## Out of scope
- splitting E047's commits — main history is not rewritten

## Log
- 2026-10-04 po: created from E047-followups (README line) and E048-followups (json import); waits on E047 merging, and E044 also edits test_ui_browser.py.
- 2026-10-04 po: E047 merged (ad37949); README:106 still runs past 80 chars. Held: E044 (in flight) edits README.md and test_ui_browser.py too.
- 2026-10-04 po: E044 merged (4fb4cfd); README:112-113 still runs past 80 and windows only the share. Started; T491 Done-when narrowed to its own paragraph.
- 2026-10-04 dev: T491 and T492 committed; README paragraph rewrapped to 80 and says the 30-day window covers count, days and share; test_ui_browser.py (27 passed) runs. Mutation: restoring the local import is trivially visible; no behaviour to guard.
- 2026-10-04 qa: pass at 56ab06c; word-diffed README (only the window sentence changed, paragraph lines all <=80), checked copy against usage.py/usage.html, ruff clean, test_ui_browser.py 27 passed; no mutation re-run (T492 has no behaviour, T491 is docs); followups in backlog/E049-followups.md.
- 2026-10-04 po: reject at 56ab06c; README:110-111 now puts "the latest" inside "over the last 30 days", but usage.py `_asked` shows the latest questions of any age (false docs, the one thing this epic fixes). Move "the latest" out of the window clause; folded backlog/E049-followups.md into this.
- dev round 2: bf43e04/580ed26 README moves the latest questions out of the 30-day window; paragraph wraps at 80 (awk length check).
- qa round 2 PASS at 580ed26: README usage paragraph now puts the latest questions outside the 30-day window (matches _asked/recall_log.latest, usage.py:63); word-diff vs main shows only that change plus rewrap; no new >80 lines (two pre-existing removed); ruff clean; test_ui_browser topic/filter tests 3 passed. Text-only round, no mutations applicable. No followups.
- 2026-10-04 po: accept at 580ed26; README now windows count, days and share to 30 days and leaves the latest questions unwindowed (matches usage.py:62-65); paragraph wraps at 80; test helper uses the module json.
- merged to main at 580ed26 (ff); full suite green on third run, earlier runs hit unrelated flakes (test_completeness ResourceWarning, test_trees, test_manual_split) that pass in isolation
