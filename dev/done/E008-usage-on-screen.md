---
id: E008
title: the panel shows what was spent — home, run page, a Usage page
priority: medium
depends_on: [E002, E005]
requirements: [19, 88, 89, 90, 92]
---

## Goal
The ledger (#201) and its roll-up (#202) exist; the panel shows almost none of
it. Put spend where people look, honestly marking subscription estimates.
Detail: archive/203, archive/220.

## Tickets

### 1 spend on home and on the run page
Done when:
- [ ] home shows total and last-run spend for the tree, linking to Usage
- [ ] a run page shows tokens, cost, model time, split by stage
- [ ] pre-ledger jobs show unknown, not free
Look at: server/ui/overview.py, ui/jobs.py, src/hrono/usage

### 2 a Usage page for every role
Change: spend over time; per configured model (upstream, provider, calls,
tokens, hours, cost); costliest runs with who started them; per user. Plain
SVG/bars, no new JS dependency.
Done when:
- [ ] a claude-code-only install never shows its estimate as money spent
- [ ] reader can open it; no horizontal scroll at 1440/800 (E005's test)

### 3 remote embedding calls record their tokens
Change: openai `/v1/embeddings` returns `usage.prompt_tokens`; record as
input_tokens; local stays NULL.
Done when:
- [ ] `GET /usage` prices a remote embedding run whose model has a price
Look at: src/hrono/llm/openai.py, embed/encoders.py, llm/ledger.py

### 4 home's recent runs page in SQL and show the derived status
Change: `_recent` uses `jobs.store.page_roots` (E002) instead of
`list_jobs` + Python filter, and prints the rolled-up status.
Done when:
- [ ] a finished fan-out run reads its derived status on Home, not "pending"
- [ ] Home reads only the rows it shows (measured)
Look at: src/hrono/server/ui/overview.py `_recent`

### 5 the run page's stage count matches its rows
Change: the "Stages N" header counts every stage listed, or reads "3 of 4
done" on a failed run (evidence/E002/failed-first-build.png reads 3 over 4).
Done when:
- [ ] a run failed at condense shows a header that agrees with its rows
Look at: src/hrono/server/templates/run.html stages header

## Out of scope
- budgets or alerts

## Log
- 2026-10-03 po: created from #203, #220.
- 2026-10-03 po: folded backlog home-recent-runs as ticket 4.
- 2026-10-03 po: folded backlog run-stages-count-header (E002 follow-up) as ticket 5.
- 2026-10-03 po: starting (E007 merged 3cf756b); rebase onto E011's TABS entry if it merges first.
- 2026-10-03 dev: round 1 started, worktree .claude/worktrees/E008
- 2026-10-03 dev: ticket 3 committed 0cc8606; real-HTTP stub test through encoder_for_model + roll-up; mutation (drop tally.add) fails it
- 2026-10-03 dev: tickets 1,2,4,5 committed 223ad08 (one commit, the pages share templates); driven in chromium 1440/800 no scroll, evidence/E008; mutations: before-ledger compare, billed flag, stage grouping, derived status, home limit all fail a test
- 2026-10-03 qa: round 1 FAIL at 223ad08 — drove usage/home/run/runs as reader+admin at 1440/800 in chromium (no scroll); re-ran derived-status, header +1, drop tally mutations (caught); own list_jobs-revert and day-order mutations survive; findings in qa verdict: pre-ledger tokens hidden on run page, home-bound test measures statements not rows, over-time untested, 4 tickets in one commit, usage.key API change, stale rollup docstring, live.py fixture bypasses ledger.record
- 2026-10-03 dev: round 2 fix 469ec5c for qa findings 1,2,3,5,6,7 (tests added, mutations: legacy tokens branch, day window, usage key, list_jobs revert all fail a test); finding 4 (split 223ad08) not done: it rewrites a commit qa has seen, which dev.md forbids
- 2026-10-03 qa: round 2 FAIL at 469ec5c — findings 1,3,5,6,7 hold (re-ran day-order, run-header/home tokens-only, usage-key, list_jobs-revert mutations: all caught; drove old run/usage/home/runs in chromium 1440/800, no scroll); open: home-bound test passes with page_roots(limit=10**9)[:5] reading all 400 rows, and 223ad08 still holds tickets 1,2,4,5 (needs orchestrator ruling on the split)
- dev r3: 2772125 fix finding 1 (test asserts roots-query LIMIT == RECENT_RUNS; mutations limit=10**9 and list_jobs revert both fail). Finding 2 not done: dev.md forbids rewriting 223ad08; orchestrator must rule (split or waive dim 8).
- 2026-10-03 qa: round 3 FAIL at 2772125 — finding 1 fixed (limit=10**9 and list_jobs-revert mutations fail; my raw unbounded roots query fails too); 831 server/usage/llm/embed/jobs tests pass, ruff clean; open: dim 8, 223ad08 holds tickets 1,2,4,5 and no orchestrator ruling (split or waive) is recorded
- 2026-10-03 po: stuck after 3 rounds; only open finding is dim 8 (223ad08 holds T1,2,4,5), a qa.md/dev.md conflict. needs-user: let the history stand and merge (rec: yes, as E011/E019; rebase keeps both Find and Usage in test_ui_frame.py TABS)?
- 2026-10-03 po: user answered "yes": history stands (dim 8 waived, as E009/E011/E019); restarting for gate and review.
- 2026-10-03 qa: round 4 PASS at 2772125 — dim 8 waived by user ("yes"); ruff clean, full suite 2152 passed; drove usage/home/run as admin+reader in chromium 1440/800 (200, no scroll); mutations re-run: drop tally.add (dev), billed=bool(billing), day window [:DAYS] (own) all caught; note: merge with main conflicts in tests/server/test_ui_frame.py TABS (keep Find and Usage)
- 2026-10-03 po: review ACCEPT at 2772125 — all 5 tickets met per qa round 4 and evidence/E008 (home, run, Usage at 1440/800); estimate never shown as spend, pre-ledger reads not recorded; README and Guide updated. Merge: keep Find and Usage in test_ui_frame.py TABS.
- merged to main, head cf801a6
