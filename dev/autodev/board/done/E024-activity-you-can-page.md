---
id: E024
title: the activity log can be filtered and paged past the newest 100
priority: medium
depends_on: [E010]
requirements: [76]
---

## Goal
A curator on a busy tree sees only the newest 100 decisions; "100 of 41,000"
with no way to reach the rest. Runs and sections already filter and page.

## Tickets

### 1 filter and page the activity log in SQL
Change: `update_log.recent` takes offset + verdict/action filter (and topic
id); the page gets a filter bar and pager like the sections list on the topic
page (E010). The climb figure draws the rows shown.
Done when:
- [ ] on a tree with > 100 decisions every one is reachable by paging
- [ ] filtering by verdict (e.g. abstained) shows only those, count matches
- [ ] filter and page survive in the URL; reader sees the same page
- [ ] paging and filter run in SQL (LIMIT/OFFSET, WHERE), not in Python
Look at: src/hrono/db/update_log.py, server/ui/views.py, templates/activity.html

## Out of scope
- sorting other than newest-first
- the map, the runs list

## Log
- 2026-10-03 po: created from REQUIREMENTS 76 (activity part left open after E010).
- 2026-10-03 dev: round 1 started, worktree epic/E024
- 2026-10-03 dev: ticket 1 9f2d0d8; verified by 8 TestClient tests via the real record writer plus browser/vocab suites; mutations: offset to 0, filter WHERE dropped, count ignoring filter, all caught.
- 2026-10-03 qa: round 1 FAIL at 9f2d0d8; drove a live server in Playwright (230 decisions; paged 1-3, filtered by verdict and topic, no-match, clamp, 390px); re-ran offset->0 (caught) and topic-dropped-from-pager (SURVIVED); findings: empty table under 'No decisions match', pager unpadded outside card-body, topic missing from the pager-link test, duplicate import, double COUNT.
- round 2 e4fd37a: fixed 5 qa findings (empty-result table, pager card-body, topic pager test, dup import, count split); mutation 'topic dropped from pager' now caught; 54 tests pass
- 2026-10-03 qa: round 2 PASS at e4fd37a; all 5 round-1 findings fixed; ruff clean, 750 affected tests pass; drove live uvicorn in Playwright (230 decisions: no-match shows no table, topic=7 Older link keeps topic and page 2 is topic 7 only, pager inside card-body, 390px no sideways scroll); mutations re-run: topic dropped from pager (caught), count ignoring topic (caught), table rendered under no-match (caught).
- 2026-10-03 po: review ACCEPT at e4fd37a; all 4 Done-when met by qa's live drive (230 decisions paged, verdict/topic filters, URL state, SQL LIMIT/OFFSET/WHERE); README already names the activity log.
- merged to main at 15c01d1
