---
id: E002
title: a failed run never claims it did nothing
priority: high
depends_on: []
requirements: [39, 40, 44, 76]
---

## Goal
#213 landed (bfb9f75) with qa's kickback open: a failed run whose finished
stages reported no counts shows "Nothing to change … no model calls" after
making 4 model calls. Fix it and close the two notes qa left.

## Tickets

### 1 failed or canceled runs skip the "quiet" state
Change: guard `outcome.quiet` in run.html by status; a failed run says what
finished before the failure (the timeline) or nothing.
Done when:
- [x] a failed run whose stages returned null shows no "Nothing to change" text
- [x] mutation: removing the status guard fails the test
Look at: src/hrono/server/templates/run.html, server/outcome.py

### 2 a first build reports per-stage counts
Change: sync, split and embed return what they did (files read, sections cut,
sections embedded) instead of `result: null`.
Done when:
- [x] a first maintain's timeline shows non-zero counts for sync/split/embed
- [x] an unchanged re-run still reads "nothing to do" for them
Look at: src/hrono/tree/maintain.py, sync_chain.py, jobs/stages.py

### 3 the runs list pages in SQL
Change: page root jobs with LIMIT/OFFSET instead of rendering all then slicing.
Done when:
- [x] a tree with 5,000 runs renders page 1 reading 25 rows (measured)
Look at: src/hrono/server/ui/jobs.py `jobs_view`

## Out of scope
- money on the runs list (E008)

## Log
- 2026-10-03 po: created from #213's open kickback and qa notes.
- 2026-10-03 dev: started in .claude/worktrees/E002 on epic/E002.
- 2026-10-03 dev: T1 84062f4 — run.html guards the quiet state by status (failed/canceled read 'It stopped before it finished'), also fixed the JS reload list spelling 'cancelled' -> 'canceled'. Tests: real-worker condense failure page + parametrized failed/canceled/succeeded. Mutations KILLED: guard removed (3 fail), canceled dropped from guard (1 fail).
- 2026-10-03 dev: T2 887e33d — sync returns {fetched: 0|1} (version new vs pinned), split {files_changed, sections_cut, files_gone} (per-path section-hash tuples before vs after), embed {embedded: n}; sentences in outcome.COUNTED. Tests through the real worker: first build counts + page text, unchanged re-run all zero + timeline 'nothing to do', edit+delete re-run 1/1/1. Mutations KILLED: fetched always 1; every path counted changed; files_gone 0; embedded 0. Full gate: 1 unrelated flake (test_ui_graph SAME_NAME, backlog filed), passes alone.
- 2026-10-03 dev: T3 f124f02 — jobs.store.page_roots/count_roots/root_ops page and filter root runs in SQL; the status filter uses the derived status (_ROLLED, rollup's rule in SQL) and tests/jobs/test_page_roots.py holds it to rollup over every child-status combination up to 3. Measured at 5,000 runs (test_the_runs_list_reads_one_page_of_a_long_history): 81 statements / 0.018s for page 1 (25 rows), was 15,004 statements / 0.167s. Mutations KILLED: limit -1; failed/canceled order swapped; partial never; ORDER BY ascending; parent_id filter dropped; filter on stored status (that one survived at first through stale .pyc of equal size, cleared and re-run: killed).
- 2026-10-03 dev: driven: hrono serve on a scratch DB with a local OpenAI-compatible stand-in (canned summaries, hashed 64-dim vectors) over a 16-file git repo, in Chromium as admin. First maintain (model switched off) failed 'at condense, on section m10.md' with the timeline '1 new version fetched / 16 new or changed files read, 16 sections cut / 32 pieces of text embedded' and 'It stopped before it finished', no 'Nothing to change'. Unchanged re-runs: sync/split/embed/condense 'nothing to do'. Status filter failed -> 4 rows. (cluster then failed on the structureless vectors — backlog no-clusters-on-sixteen-random-vectors, for E003.) Screenshots evidence/E002/{runs-list,failed-first-build,failed-unchanged}.png.
- 2026-10-03 dev: handoff, epic/E002 head f124f02 (84062f4, 887e33d, f124f02). Gate in worktree: ruff format/check clean, pytest 1695 passed / 4 skipped (PYTHONDONTWRITEBYTECODE=1).
- 2026-10-03 qa: round 1 PASS at f124f02. Gate in own worktree: ruff format/check clean, pytest 1695 passed / 4 skipped. Drove hrono serve on a scratch DB with a local openai-compatible stand-in (chat switched off) over a 12-file git repo, Chromium as admin: first maintain failed at condense with '1 new version fetched / 12 new or changed files read, 12 sections cut / 24 pieces of text embedded' and 'It stopped before it finished'; unchanged re-run read 'nothing to do' for sync/split/embed; edit m1 + delete m2 re-run read 1 fetched / 1 changed, 1 cut, 1 gone / 1 embedded; runs list and status/op filters correct; no 'Nothing to change' on any failed run. Mutations re-run, all killed: run.html status guard removed (dev's, 3 fail); sync fetched = previous is None (mine); split changed = path absent before (mine).
- 2026-10-03 po: ACCEPT f124f02. All Done-when met per qa's drive and evidence/E002; failed run reads 'It stopped before it finished' with real stage counts; runs list pages in SQL (81 stmts at 5,000). Backlog: run-stages-count-header.
- merge: rebased on main, gate green (1707 passed), ff-merged; main head 16fb12c
