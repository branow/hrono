---
id: E047
title: polish — the agent-questions card says "last 30 days" and sits in the page
priority: medium
depends_on: [E042]
requirements: []
---

## Goal
E042's Usage card reads its 30-day sums as totals and touches the card above.
Fix what a reader sees, then the two code shortcuts qa found.

## Tickets

### 471 the card sits inside the page stack
Change: move the "Agent questions" section inside the page's `.stack` div;
drop the undefined `mt-4`.
Done when:
- [ ] the card has the same gap as the other Usage cards (checked in a browser)
Look at: src/hrono/server/templates/usage.html:116

### 472 the chips say they cover the last 30 days
Change: label "N calls" and "X% not confident" as the last 30 days.
Done when:
- [ ] the chips name the 30-day window
- [ ] a test with more than 30 days of rows proves only the newest 30 count
  (mutating `[-DAYS:]` to `[:DAYS]` fails it)
Look at: src/hrono/server/ui/usage.py:61, templates/usage.html

### 473 typed per-day rows; one Ask link builder
Change: `recall_log.per_day` returns typed rows (TypedDict or dataclass) so the
sums need no `type: ignore`; the question link uses the Ask page's builder
(make `ask._link` public; touch nothing else in ask.py, E040 is in flight).
Done when:
- [ ] no `type: ignore` left in usage.py; the type checker is clean
- [ ] one function builds the Ask link; both pages use it
Look at: src/hrono/recall/log.py:48, server/ui/usage.py:60-73, server/ui/ask.py:153

## Out of scope
- new Usage features

## Log
- 2026-10-04 po: created from backlog/E042-followups.md (user: apply all suggestions).
- 2026-10-04 po: starting; E042 merged (53107df), no in-flight branch touches usage.py/usage.html/recall/log.py.
- 2026-10-04 dev: 471-473 in one commit 5b8e83a; test_the_agent_chips_count_only_the_newest_window_and_say_so + test_the_agent_card_sits_in_the_page_stack; mutated [-DAYS:] to [:DAYS] and it failed; tests/server and tests/recall green; no browser drive (HTML structure asserted); no type checker installed in env.
- 2026-10-04 qa: FAIL round 1 at be032ce. Drove /ui/usage in Chromium with 35 days of recall_log rows, with and without spend: with spend every card is 16px apart (471 ok); with nothing spent the 'Nothing has been spent yet' card ends at y=322 and the Agent questions card starts at y=322, zero gap (471 not met). 30-day window and chips correct. Mutations re-run: [-DAYS:]->[:DAYS] fails 2, drop 'Last N days' label fails 1, ask_link q->upper fails 1, Day.unsure<-calls fails 2. mypy and basedpyright: 0 errors on usage.py/log.py/ask.py. Followups: backlog/E047-followups.md.
- qa round 2: pass at acb2c81. Drove /ui/usage in Chromium: nothing-spent card 183-322 then Agent questions at 338 (16px), spent state all five cards 16px apart. Re-ran dev's mutation (empty card back outside .stack) and my own (stack opened only in the spent branch): both fail test_the_agent_card_sits_in_the_page_stack. Ruff clean, test_ui_usage 18 passed. Followups: backlog/E047-followups.md (one minor added).
- 2026-10-04 po: accept at acb2c81. 471-473 met per qa's browser drive (16px gaps both states), window mutation, mypy/basedpyright clean. README window wording + line length to backlog/E047-followups.md.
- merged to main at ad37949
