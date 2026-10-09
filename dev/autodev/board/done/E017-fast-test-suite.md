---
id: E017
title: a test suite that runs in under a minute
priority: highest
depends_on: []
requirements: []
---

## Goal
The full suite takes 146s on main (1707 passed, 2026-10-03). Every dev and qa
round pays for it. Bring it under 60s, and lower if it's cheap, without losing
any test that catches a real regression. Requested by the user: start this
before any other todo epic.

## Tickets

### 1 run in parallel with pytest-xdist
Change: add `pytest-xdist` to the dev deps. Make the suite pass under
`-n auto`: no shared ports, files or global state between workers. CI and
CONTRIBUTING use `-n auto`.
Done when:
- [ ] `uv run pytest -q -n auto` is green three runs in a row
- [ ] CI workflow and CONTRIBUTING's gate line use it
Look at: pyproject.toml, .github/workflows/, tests/conftest.py, CONTRIBUTING.md

### 2 kill the fixed costs
Change: about 30 tests in tests/ingest and tests/llm spend 0.50s each in
teardown, because a stub `HTTPServer.shutdown()` waits out serve_forever's
0.5s poll. Fix it once in a shared fixture (e.g. `serve_forever(poll_interval=0.01)`).
Also check the slow setups in
tests/summarize/test_unusable_condensations.py (0.6-1.2s each) and use a
module-scoped fixture where state is read-only.
Done when:
- [ ] no teardown over 0.05s in `--durations=50`
- [ ] one stub-server helper replaces the copies
Look at: tests/llm/test_openai_*.py, tests/ingest/test_{confluence,notion,bitbucket,github}*.py

### 3 cut or shrink the slow and redundant tests
Change: profile with `--durations=60`. For each test over 0.5s, either make it
faster (a smaller input still proves it; sleeps become events or injected
clocks) or delete it if another test already covers it. Known: test_build.py
`test_recovers_planted_groups_with_full_coverage` at 9.3s, tests/tree/test_update.py
at about 1s each, tests/jobs/test_worker.py and test_events.py at 0.5-2s from
real sleeps. Collapse near-duplicate tests into one parametrized test. Keep
exactly one real-backend test per seam (#108).
Done when:
- [ ] `uv run pytest -q -n auto` finishes under 60s wall clock on this machine;
  before and after timings in evidence/E017/
- [ ] every deleted test is listed in the Log with what still covers it
- [ ] no test over 2s except the real-backend seam tests

## Out of scope
- changing production code to make tests faster, unless it is a real seam
  (an injected clock or poll interval)

## Log
- 2026-10-03 user via main session: created. Durations profile:
  evidence/E017/durations-before.txt
- 2026-10-03 po: starting now per user request, alongside restarted E004/E006/E015; it touches tests/ broadly, so expect test-file conflicts at merge — rebase onto main before qa.
- 2026-10-03 dev: round 1 started, worktree .claude/worktrees/E017
- 2026-10-03 dev r1: T1 2df654d xdist + tests/conftest.py (1 thread per worker via env; umap modules in two xdist groups, warm-up paid twice not 8x). Green 3x in a row at -n auto; gate.yml and CONTRIBUTING use -n auto. Mutated: dropping tryfirst on the hook put the group back across all workers (visible in -v gw ids).
- 2026-10-03 dev r1: T2 e969112 tests/stub_server.serving (poll 10ms) replaces 6 copies; teardowns now <0.1s under load. 7667d0b dead-supervisor test uses an Event, not sleep(2). No test deleted. test_unusable_condensations setup left as is (needs per-test db state).
- 2026-10-03 dev r1: T3 partial: 146s -> 48-66s wall, varying with machine load 21-36 from parallel epics (quiet-machine number not obtainable). Remaining >2s tests are the first-UMAP-per-worker JIT (real-backend) and test_update ageing (4s loaded, genuinely N runs). One unexplained failure of test_manual_split.py:161 in one full run, not reproduced in 8 further runs.
- 2026-10-03 qa r1: FAIL at 7667d0b. T1/T2 hold (full suite green -n auto; teardowns 0.01s; re-ran tryfirst mutation and poll=0.5 mutation, both bite). T3 not done: suite 58.5s (load 4.5 at start) / 96s (load ~22) — no margin; the ticket's named slow tests (test_build planted 32s on its worker, test_worker sleep(0.6), test_events, test_update) untouched; no near-duplicate collapse. See qa findings.
- 2026-10-03 dev r2: merged main (b4332a8, tests/eval) into the branch rather than rebase, so qa-seen hashes stay. Full suite green under -n auto. T3 1016de7: suite 39.9s and 41.3s at load 19-24 (qa saw 96s at load 22 before); 43.7s/46.6s earlier at load 11. Evidence: evidence/E017/durations-r2-run{1,2}.txt. Per-test module-built tree (tests/world.py) replaced ~45 x 0.25-0.5s setups in test_update and test_settle; heartbeat sleep 0.6->0.3 (stale_after scaled with it), events poll patched to 0.05, db rival hold 0.3->0.1.
- 2026-10-03 dev r2: mutations: restore() made a no-op fails test_update; worker heartbeat touch removed fails the shrunk heartbeat test. No test deleted, none collapsed: nothing remaining over 0.5s was a duplicate, only essential-time tests.
- 2026-10-03 dev r2: tests over 2s: the two first-UMAP tests (test_build planted 20-27s, test_settle drain 18-26s) are pure numba import+JIT (~9s alone, measured: the test body is milliseconds; a smaller input cannot shrink it), the real-backend seam, paid once on each of the two umap workers. test_ageing_measures_runs_not_changed_sources 2.1s loaded runs MAX_AGE real updates; test_pending_finds_every_section_of_a_corpus_past_the_variable_limit 1.4-2.1s inserts 32,800 rows past SQLite's variable limit. Both are the point of the test.
- 2026-10-03 dev r2: manual_split flake not reproduced in 34 runs (16 serial -n auto of server+cluster, 18 concurrent under load>20); filed backlog/test-manual-split-dense-topic-flake.md. `pytest -p no:xdist` failing on the --dist addopt is known and left.
- 2026-10-03 qa r2: PASS at 1016de7. Earlier findings resolved: full suite -n auto 40.4s/38.5s at load 15-24 (1792 passed), and 37.5s merged with current main 026d8ea (1904 passed, merges clean); first run on a fresh venv was 87s (numba JIT cache cold, one-time). Re-ran dev's mutations (restore() no-op: 18 tree tests fail; heartbeat touch removed: test fails) and my own (events stream emitting without the change filter: test_the_stream_follows_a_job_to_its_end fails). Heartbeat + db rival tests 80/80 green under 8 concurrent loops. Over 2s: the two first-UMAP tests (17-29s, numba warm-up), and test_ageing / test_update_parks_an_alien_chunk_then_ages_it_in at 2.1-2.2s loaded (0.9-1.7s isolated), which are MAX_AGE+1 real update runs against the baked constant, so accepted as essential. manual_split flake filed in backlog.
- 2026-10-03 po: ACCEPT at 1016de7. All Done-when met by qa r2 (40s/38s loaded, 37.5s merged with main; teardowns 0.01s; one stub helper; CI + CONTRIBUTING on -n auto; no test deleted). Over-2s ageing tests (2.1s loaded, MAX_AGE real runs) accepted as essential.
- merged to main at df5bece (rebased, full suite 1904 passed)
