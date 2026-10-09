---
id: E026
title: setup never dead-ends, and never builds a tree nobody registered
priority: medium
depends_on: [E013]
requirements: [7]
---

## Goal
The first-run wizard (E013) must finish on a default install and must not spend
money on a typo'd tree name.

## Tickets

### 1 a maintain for an unregistered tree is refused
Change: `POST /trees/{name}/maintain` and `POST /ui/setup/build` return 404
(actionable message naming the tree) when the tree is not in the registry; no
job is queued.
Done when:
- [ ] `tree=nope` on either route: 404, zero jobs, zero topics/briefs written
- [ ] a registered tree still builds (existing tests stay green)
Look at: src/hrono/server/trees.py, the E013 setup route

### 2 the models step says how to get the embed backend
Change: when the in-process embedding backend is missing, the models step says
so before offering the form, with the install line (`hrono[embed]` /
`uv sync --extra embed`); the API refusal carries the same hint.
Done when:
- [ ] without the extra, the setup page shows the hint, not a dead form
- [ ] the API error text names the install command
Look at: src/hrono/embed/runner.py, registry/validation/model_validation.py

### 3 sync_source's docstring stops claiming the setup path
Change: since c325ad9 setup calls `fetch_source`; move the "setup path fetches
a source" sentence from `sync_source` to `fetch_source`.
Done when:
- [ ] each docstring names only its real callers
Look at: src/hrono/ingest/sync.py

## Out of scope
- installing the extra from the browser

## Log
- 2026-10-03 po: created from backlog maintain-builds-an-unregistered-tree, setup-dead-ends-without-the-embed-extra (qa E013 r1). Waits on E013 (same setup module).
- 2026-10-03 po: E013 merged (4495ae9), depends_on met. Folded backlog sync-source-docstring-names-the-setup-path as T3.
- 2026-10-04 dev: round 1 started, worktree .claude/worktrees/E026
- 2026-10-04 po: orphaned by a stopped run (worktree clean, no commits); restarted on its branch.
- 2026-10-04 dev: T1 9768d6e tests test_trees/test_ui_setup (404, zero jobs/nodes); mutation is_known always-true fails both. T2 bf27932 setup page + runner/validation hint tests; mutation embed_missing=False fails page test. T3 a479836 docstrings. Handed off.
- 2026-10-04 qa: pass at a479836. Drove: POST /trees/nope/maintain 404 (0 jobs, 0 nodes), alpha and default 200; /ui/setup/build tree=nope 404; models step in Chromium with no sentence_transformers shows the install callout and no form (screenshot checked). Mutations: is_known->True and dropping require_tree in start_build fail the 404 tests; dropping the install line from NOT_INSTALLED fails the runner and validation tests. Ruff clean, 446 affected tests pass. Followups: backlog/E026-followups.md.
- 2026-10-04 po: accept at a479836. All Done-when met per qa's drive; README/GLOSSARY match. Minor: install line wording, remote-embed pointer -> backlog/E026-followups.md.
- 2026-10-04 po: orphaned again by a stopped run (accepted at a479836, rebased to 11a6780, not merged); restarted to merge.
- 2026-10-04 qa: pass at 11a6780 (range-diff identical to a479836). Ruff clean, 191 affected tests pass. Mutations: is_known->True fails both 404 tests; dropping the default clause fails 4 setup/tree tests. Live drive cut short: the secret-scanning hook blocked reading the scratch server's bootstrap token; relies on the a479836 drive of identical patches. Followups unchanged: backlog/E026-followups.md.
- 2026-10-04 po: accept at 11a6780 (range-diff identical to accepted a479836; qa re-gated). Minor findings already in E030.
- merged to main at 4b6b4a7 (dev, merge mode)
