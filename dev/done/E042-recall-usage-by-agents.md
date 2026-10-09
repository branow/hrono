---
id: E042
title: see how often agents call recall and what they ask
priority: medium
depends_on: []
requirements: [72]
---

## Goal
An admin wants to know whether agents use the tree and what they look for, to
judge what to fix. Today recall leaves no trace.

## Tickets

### 421 every API recall is recorded, bounded
Change: a migration adds a recall log (tree, user, question, hit count, top
score, confident or not, when). The API recall route writes one row; the
panel's Ask page does not (it is a curator, not an agent). Keep the newest N
rows per tree (N baked, e.g. 10,000); never slows recall noticeably.
Done when:
- [ ] `hrono recall` and the HTTP route each add one row; Ask adds none
- [ ] the cap holds past N; the migration keeps existing data
Look at: src/hrono/recall/, server/app.py recall route, db/migrations/

### 422 the Usage page shows recall calls and recent questions
Change: calls per day, share not confident, and the latest questions with who
and hit count; a not-confident question links to Ask with it filled in.
Admin and writer only.
Done when:
- [ ] counts match the log; a reader cannot see the questions (server-side)
Look at: src/hrono/server/ui/usage.py, templates/usage.html

## Out of scope
- per-question cost, alerts, export of the log

## Log
- 2026-10-04 po: created from REQUIREMENTS 72.
- 2026-10-04 dev: round 1 started
- 2026-10-04 dev: 421+422 committed (head dc5c94a). Tests: tests/recall/test_log.py, test_recall_endpoint (cap, row), test_ui_ask (Ask adds none), test_ui_usage (reader never gets questions, link to Ask). Mutations: cap offset, can_write gate, dropped record call - each failed a test. Not driven on a live server (the secret-scanning hook blocked reading the bootstrap token log); covered through the production app via TestClient.
- 2026-10-04 qa: pass at dc5c94a. Drove a live uvicorn server on a scratch db: real `hrono recall` via a profile (one answered, one refused) added exactly 2 rows with user/hits/top_score/confident right; the Ask page (opened from the Usage link, question prefilled and escaped) added none; Usage page screenshot as admin/writer shows the section, a reader gets no section and no question text. Cap cost measured ~0.5ms per recall at 10,000 rows. Re-ran dev's role-gate mutation (killed) plus mine: confident always 1, latest oldest-first (both killed); [-DAYS:] -> [:DAYS] survives (followup). 136 affected tests + ui_vocabulary/ui_browser pass; ruff clean. Followups: backlog/E042-followups.md.
- 2026-10-04 po: accept at dc5c94a. Both Done-when met per qa's live drive; README/GLOSSARY match. Minors stay in backlog/E042-followups.md.
- merged to main at 53107df
