---
id: E030
title: setup's embed hint reads right, and a refused build stays on the page
priority: low
depends_on: [E026]
requirements: [7]
---

## Goal
Minor findings on E026's setup wizard: one install line everywhere, a hint that
does not break, a refusal a browser can read, one "default" constant.

## Tickets

### 1 the embed hint says one install line and names the remote option
Change: `INSTALL` in embed/runner.py matches the README (`uv pip install
"hrono[embed]"`), or the README matches it; code spans in the models-step
callout get `white-space: nowrap`; add one line pointing to Settings > models
for a remote embedding model.
Done when:
- [ ] README, runner hint and setup page name the same command
- [ ] at 1100px no callout code span wraps
- [ ] the callout names Settings > models as the alternative
Look at: src/hrono/embed/runner.py:33, server/templates/setup.html:78-81

### 2 a refused setup build re-renders the page
Change: `/ui/setup/build` for an unknown tree re-renders setup with the message,
not a raw JSON 404. `test_maintain_for_a_registered_tree_queues_a_job` also
asserts a `jobs` row with `tree='alpha'`.
Done when:
- [ ] a form post with `tree=nope` gets the setup page with the message, zero jobs
- [ ] the maintain test fails if no job row is written
Look at: src/hrono/server/ui/setup.py:238, tests/server/test_trees.py:92

### 3 one DEFAULT_TREE constant
Change: every "default" tree literal imports the one constant.
Done when:
- [ ] `grep -rn '"default"'` in tree/, summarize/, cluster/, registry/ finds only the definition
Look at: registry/collections/trees.py:32, tree/{update,maintain,settle,sync_chain}.py, summarize/brief_upper.py:46, cluster/*.py

## Out of scope
- installing the extra from the browser

## Log
- 2026-10-04 po: created from backlog/E026-followups.md (qa r1 + po review). Waits on E026 (same setup files).
- 2026-10-04 dev: round 1 started, worktree epic/E030
- 2026-10-04 dev r1: T1 7ba75e7 one `uv pip install "hrono[embed]"` line in runner/failures/ask/setup; browser test measures code span at 160px box; mutation nowrap->normal fails it.
- 2026-10-04 dev r1: T2 253f664 build refusal re-renders step-build; test asserts 200, message, zero jobs; maintain test asserts the jobs row. T3 1465ae7 grep for "default" in tree/summarize/cluster/registry finds only the definition. Suites for server/embed/registry/tree/summarize/cluster green (1490).
- 2026-10-04 qa r1: pass at 253f664. Drove `hrono serve` on a scratch db: models-step callout at 1100px shows `uv pip install "hrono[embed]"` on one line (1 client rect) and links Settings section=models; a browser form post of tree=nope to /ui/setup/build re-renders setup with "tree not registered: nope", 0 jobs. README/runner/failures/ask/setup name one command; grep for "default" finds only the definition. Mutations re-run: nowrap->normal fails the browser test (dev's); dropping the build-step refusal fails the refusal test; maintain enqueuing tree="x" fails the maintain test (mine). 850 affected tests pass, ruff clean. Followups: backlog/E030-followups.md.
- 2026-10-04 po: orphaned in po-review after qa pass (run stopped); restarted for review. Followups rejected (see board.md).
- 2026-10-04 qa r1 (rerun): fail at 253f664. Drove `hrono serve` on a scratch db: a browser post of tree=nope to /ui/setup/build returns 200 setup page with "tree not registered: nope", 0 jobs; models callout renders the Settings section=models link (fixture render). Mutations: nowrap->normal fails the browser test (dev's); dropping the is_known refusal and dropping the build-step refused() each fail the refusal test; deleting the "remote embedding model ... Settings" sentence from setup.html:81 survives all 48 setup+browser tests -> blocking: T1 Done-when 3 has no test. 833 affected tests pass, ruff clean. Followups: backlog/E030-followups.md.
- Round 2 dev: cd31189 pins the Settings > models callout in test_models_step_without_the_embed_backend_says_how_to_get_it; removing the sentence fails it.
- 2026-10-04 qa r2: pass at cd31189. Prior blocker fixed: the models-step test now asserts "remote embedding model instead" and the Settings section=models link. Mutations re-run: deleting the sentence (dev's) and unlinking only Settings (mine) each fail test_models_step_without_the_embed_backend_says_how_to_get_it; unmutated 48 setup+browser tests pass, ruff clean. Test-only diff, no regressions; round-1 drive stands. Followups: backlog/E030-followups.md.
- 2026-10-04 po: accept at cd31189. All Done-whens met per qa r1 drive + r2 test pin; README/runner/page name one command. Step-1 refusal placement is minor (hand-made post only) -> backlog/E030-followups.md.
- 2026-10-04 po: merged at 4ff97e8; moved po-review -> done (the merge left it in po-review).
