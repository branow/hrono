---
id: E016
title: a claude-code text model can be registered, as the README says
priority: high
depends_on: []
requirements: []
---

## Goal
The README recommends a claude-code connection for trying hrono, and the next
step, `hrono models set` on a text model, fails every time. The first-run path
must work as written.

## Tickets

### 1 validating a claude-code text model goes through the CLI backend
Change: `_default_generate` dispatches on the connection's provider; a
claude-code connection generates through the headless backend (#107), not an
HTTP POST to a missing `endpoint`.
Done when:
- [ ] `PUT /models/<name>` (kind text, claude-code connection) succeeds against
  a real `claude` CLI, driven on a scratch server following the README
- [ ] a broken CLI still yields an actionable bad-request, not a URL error
- [ ] openai/anthropic validation unchanged (existing tests green)
Look at: src/hrono/registry/validation/model_validation.py `_default_generate`;
connection_validation.py `_validate_claude_code`; src/hrono/llm/

## Out of scope
- testing a connection before saving it (E013)

## Log
- 2026-10-03 po: created from backlog claude-code-text-model-cannot-be-registered (found by E004).
- 2026-10-03 po: starting — touches registry/validation/ and llm/, not E006's collections/; keep README edits to the claude-code steps.
- 2026-10-03 dev: ticket 1 056c5da — PUT /models via real claude CLI on scratch server: 201 (5s), bad model -> 400 'claude CLI failed the probe: 404'; mutations: drop claude-code branch (3 fail), drop cache_root anchor (1 fail), ledger role (1 fail); probe goes through client_for so it is ledgered.
- 2026-10-03 qa: round 1 FAIL at 056c5da — drove README path on scratch server with real claude (haiku 201 in 7s; bogus model 400 'the claude CLI failed the probe: ... 404'; ledger rows role=validate); re-ran mutations: cache_root anchor (killed), drop claude-code branch (killed), probe a different model than registered (SURVIVED). Findings: model-name test gap, CLI probe ignores validation timeout (300s > 120s client wait), README line 32 unwrapped.
- round 2 dev: fb02ecd fixes qa findings 1-4 (argv test, 60 s CLI probe bound with hung-CLI test, README rewrap, cache_root once); mutations: wrong model and unbounded timeout both killed.
- 2026-10-03 qa: round 2 FAIL at fb02ecd — round-1 findings 1-4 fixed; drove README path with real claude (haiku in 6.7 s, bogus model 400, ledger rows) and a hung fake claude on a real server (400 'timed out' at 60.5 s, nothing stored); re-ran wrong-model mutation (killed) and own _CLI_TIMEOUT=300 (SURVIVED). Finding: the hung-CLI test monkeypatches _CLI_TIMEOUT, so the bound is unpinned and DI is bypassed.
- dev round 3: cdf074b, probe limit is a cli_timeout parameter (hung test passes 0.5), test holds _CLI_TIMEOUT < WRITE_TIMEOUT; mutants 300 s constant and call-site both killed; full suite 1757 passed.
- 2026-10-03 qa: round 3 FAIL at cdf074b — round-2 finding fixed (cli_timeout DI, _CLI_TIMEOUT < WRITE_TIMEOUT); gate clean (663 passed, 2 skipped); real claude drive returned 400 on account 429 session limit, nothing stored; mutations: _CLI_TIMEOUT=300 (killed), call-site 300 (killed), validate_model default cli_timeout=300.0 (SURVIVED). Findings: unpinned default, Co-Authored-By trailers on fb02ecd and cdf074b.
- 2026-10-03 po: stuck after 3 qa rounds; left fixes are small: pin validate_model's default cli_timeout below WRITE_TIMEOUT, reword fb02ecd/cdf074b to subject only. Q user: grant a 4th round? (rec: yes.)
- 2026-10-03 po: user granted a 4th round ("yes"); restarting — pin validate_model default cli_timeout < WRITE_TIMEOUT, reword fb02ecd/cdf074b without trailers.
- dev round 4 (build round 1 of 3): started; pin validate_model default cli_timeout, reword trailers.
- dev round 4: 220284d pins validate_model default cli_timeout < WRITE_TIMEOUT (default=300.0 mutant killed); fb02ecd/cdf074b reworded to subject only (now 131c7b1/c3dadc6, no trailers); gate clean, claude-code tests 8 passed.
- 2026-10-03 qa: round 4 PASS at 220284d — round-3 findings fixed (validate_model default cli_timeout pinned < WRITE_TIMEOUT; 131c7b1/c3dadc6 subject only, no trailers on any epic commit); gate clean (ruff, 291 affected passed, 1 skipped); drove README path on scratch server with real claude: models set haiku wrote in 4.3 s, bogus model 400 'the claude CLI failed the probe: ... 404' and not stored, ledger rows role=validate for both; mutations: default cli_timeout=300.0 (killed), bounded_cli_client drops timeout (killed), call site passes _CLI_TIMEOUT instead of cli_timeout (killed).
- 2026-10-03 po: review ACCEPT at 220284d — README claude-code path driven by qa with real claude (201, bogus 400, ledgered); probe bounded 60 s < 120 s client wait and pinned; README set-validation copy updated; diff stays in validation/llm.
- merged to main at 7a3df4e
