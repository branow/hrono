---
id: E015
title: every talk-back is caught (condensations and briefs), a stubborn one is not re-paid on every sync, and the update stage says what it spent
priority: high
depends_on: [E001]
requirements: [96]
---

## Goal
E001 closed the scale crash and left three holes in the same gate: a short
talk-back passes it, a section the model always refuses costs two calls on
every sync forever, and the update stage hides that spend.

## Tickets

### 1 a short talk-back is caught
Change: run the asks/addresses/talks checks before the `MIN_CHARS` floor (or
have `talks_back` call them directly).
Done when:
- [ ] "Could you paste the file for me?" is flagged, listed by
  `GET /trees/{n}/unusable-condensations`, and re-condensed
- [ ] a short plain condensation is still usable
Look at: src/hrono/summarize/shape.py `unusable` / `talks_back`

### 2 a refused re-condense is not retried on a no-op sync
Change: record the refusal (body hash + model); an unchanged sync skips a
section already refused for the same body and model; it stays listed.
Done when:
- [ ] second unchanged sync after a refusal makes 0 condense calls
- [ ] a changed body or model retries it
Look at: src/hrono/tree/update.py `_talked_back`; summarize/condense.py `keep`

### 3 the update stage reports its condense step
Change: fold condense's outcome (condensed, refused, tokens) into `_outcome`.
Done when:
- [ ] an unchanged sync that re-condensed shows the counts on its run page
Look at: src/hrono/tree/update.py `update` / `_outcome`

### 4 a brief that echoes the prompt is never stored
Change: first check the 26 identical level-0 briefs on ~/hrono-demo against
the #217 brief gate; close whatever lets an echo through (retry once, never
store it) and list stored briefs that fail the gate.
Done when:
- [ ] the ~/hrono-demo echo brief is rejected by the gate, by a test on its text
- [ ] stored failing briefs are listed and regenerated on the next maintain
Look at: src/hrono/summarize/brief.py, brief_upper.py, shape.py

## Out of scope
- the condensation prompt itself

## Log
- 2026-10-03 po: created from backlog short-talk-back, persistent-talk-back, update-stage-hides (E001 follow-ups).
- 2026-10-03 po: added T4 from backlog identical-prompt-echo-briefs (E003 follow-up).
- 2026-10-03 dev: round 1 started on epic/E015.
- 2026-10-03 po: restarted — orphaned by a stopped run; resumes on its branch and worktree.
- 2026-10-03 dev: T4 committed 65b35d1; gate echoes() vs prompt template (57% echo vs <=15% real); 700 tests pass in summarize/server/tree; mutations of ECHO_SHARE/ECHO_WORDS bite via real-brief fixtures.
- 2026-10-03 qa: round 1 FAIL at 65b35d1 — echo gate flags plausible short real briefs (glue words like this/with/when/then count), ECHO_WORDS 3..10 and ECHO_SHARE 0.2 mutations survive, /unusable-briefs docstring stale; T1-T3 pass (drove /unusable-* on a ~/hrono-demo copy; pending-request, redo-held, spent mutations bite). See qa findings.
- round 2 0518beb: echo gate drops function words, ECHO_WORDS 8, boundary + short-brief tests, _outcome changed-sync test, trees.py docstring; mutations on ECHO_WORDS 7/9, ECHO_SHARE 0.2/0.4, stoplist, **spent each fail a test.
- 2026-10-03 qa: round 2 PASS at 0518beb — all four round-1 findings fixed; gate clean, 711 tests pass in tests/summarize, tests/tree, tests/server; drove /unusable-briefs (28 echoes) and /unusable-condensations (13 talk-backs) on a ~/hrono-demo copy; re-ran ECHO_WORDS 9, ECHO_SHARE 0.31, drop **spent on a changed sync (each fails a test); residual domain-vocabulary false-positive risk filed to backlog/echo-gate-domain-vocabulary.md.
- 2026-10-03 po: review ACCEPT at 0518beb — T1-T4 Done-when met by qa's drives (/unusable-* on a ~/hrono-demo copy, run page shows condense counts); stubborn-echo re-pay risk tracked in backlog/echo-gate-domain-vocabulary.md.
- merged to main at 3ece8be
