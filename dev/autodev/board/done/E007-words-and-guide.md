---
id: E007
title: one vocabulary, and a Guide that tells the truth
priority: medium
depends_on: [E005]
requirements: [94]
---

## Goal
Labels were written a page at a time ("3 chunks nearer", "7 hold sections")
and the Guide contradicts shipped behaviour in places. One pass over the words,
enforced by tests so it does not drift back. Detail: archive/216, archive/211.

## Tickets

### 1 every rendered string in one voice
Change: sentence case, glossary words only, no internal names, health checks
that read right at zero and non-zero.
Done when:
- [ ] a test over every UI route fails on a word GLOSSARY.md lists as not used
- [ ] old -> new string list in evidence/E007/strings.md for the user's veto
- [ ] a still-running sync reads "running n/m" on home and Runs, never
  "partial" (keep PARTIAL internal; jobs/aggregate.py)
Look at: server/templates/, server/ui/, GLOSSARY.md

### 2 the Guide audited and completed
Change: check every factual claim against code (#191 repoint claim is a known
miss); fix the roles table; add short recall, export, roles, pins, cost
sections; numbers come from constants.
Done when:
- [ ] each claim and its backing code listed in evidence/E007/guide-audit.md
- [ ] no number on the page duplicates a constant as a literal
- [ ] roles table does not wrap at 1440 or 800px
Look at: templates/guide.html, server/ui/guide.py

## Out of scope
- new pages

## Log
- 2026-10-03 po: created from #216, #211. Depends on E005 (shared templates).
- 2026-10-03 po: folded backlog running-job-says-partial into T1.
- 2026-10-03 po: starting (1 free slot; touches only UI copy, no overlap with E018-E020).
- 2026-10-03 dev: T2 53989ad, T1 089d622; tests/server + tests/jobs 667 passed, screenshots and audit in evidence/E007.
- 2026-10-03 qa: round 1 FAIL at 089d622. Drove home/Runs/run/Health/Guide at 1440+800 on a live server with a partial sync (reads running 1/3, filter works, tables do not wrap). Mutations: jobs.html status_word, also-filter (view+SQL), counted singular all killed; the partial->running JS mapping in overview/jobs/run survives every test. Findings: Health detail lines wrong at zero; live-update mapping untested; 'node' on the source edit form, which the vocabulary scan never visits.
- round 2 fix 7c62d13: triage detail hidden at zero (tested), one window.statusWord shared by the three live badges (browser test on home, Runs, run page; identity mutation killed), source name help reworded and vocabulary scan extended to edit/delete/section/json views.
- 2026-10-03 qa: round 2 FAIL at 7c62d13. Round-1 findings 1-3 fixed (tests/server+registry+jobs 955 passed; base.html statusWord identity, jobs.html identity, triage detail-at-zero and the old node- help all killed). New: a refused source name renders "Value error, source names starting with 'node-' are reserved..." (banned word + pydantic prefix, unscanned) while the reworded help no longer names the prefix.
- round 3 dev daeaa01: refusal and name help show `node-` in <code> via idents filter, Value error prefix stripped, refused save scanned; mutated removeprefix and idents, both fail tests.
- qa round 3 at de1cba7: fail. The `idents` filter sets everything after the first backtick in <code>, not just the identifier, so the refusal and the name help render mostly as code and the vocabulary scan skips that text; the tests pass with or without the fix. See qa findings.
- 2026-10-03 po: stuck after 3 rounds (`idents` wraps every part after index 0, not odd ones; tests do not bite). needs-user: grant one dev round for that fix + exact-markup tests only? (rec: yes; it is small and E008/E010/E013/E009 wait on it)
- 2026-10-03 po: user ruled yes — one dev round for the `idents` fix (wrap odd backtick parts only) + exact-markup tests that fail without it; nothing else. Restarting.
- round 4 dev 7c405d7: idents wraps odd backtick parts only (index % 2); exact-markup unit + refusal-sentence tests; mutation 'if index' killed by both.
- 2026-10-03 qa: round 4 PASS at 7c405d7. Round-3 finding fixed: idents wraps odd backtick parts only. Drove a real server on :18917 in Chromium at 1440: a refused node-x shows only `node-` as <code> in both the refusal and the name help; the rest is plain text. Affected tests (vocabulary, ui_config/settings/frame/browser/guide, registry) 429 passed; ruff clean. Mutations: dev's 'if index' (2 fail), 'not index % 2' (6 fail), unpaired-check removed (1 fail), escape dropped (2 fail), all killed.
- 2026-10-03 po: review ACCEPT at 7c405d7. Both tickets' Done-when met per qa rounds 1-4; strings.md and guide-audit.md (incl. #191) in evidence; README still true.
- merged to main at 3cf756b
