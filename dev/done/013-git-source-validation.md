---
id: 013
title: git source validation on write (reach + auth) via the validation hook
priority: high
size: medium
depends_on: [012]
spec_refs: [build-order.md#T7.2, implementation-notes.md#sources]
---

## Context
A registered source must be reachable and its credentials must work, so a dead
or misauthed source is rejected at write time rather than failing later during a
sync. #012 built the registry base with a validation-hook seam and a stub for
`git`; this ticket fills that hook for the `git` source type. It is the first
real use of the validation seam and the pattern later source types (T41-T43)
follow. Spun off from the M1/T6 slice.

## Description
Implement the `sources` git validation hook invoked on POST/PUT (from #012): given
a git source body (url + auth), verify the repo is reachable and the credentials
authenticate, without cloning the whole repo. Use a lightweight remote check
(recommend `git ls-remote` against the URL with the resolved auth, or the
equivalent library call) so it is fast and side-effect-free. Support the three
auth methods from the spec:
- `none` — public repo, no credentials.
- `token` — inject per the spec's token URL forms
  (`https://x-token-auth:<token>@bitbucket.org/...`,
  `https://x-access-token:<token>@github.com/...`) or the provider-appropriate
  header; never log the token or embed it in an error message.
- `ssh` — validate using the supplied key.

On success the write proceeds and the secret is stored encrypted (via #012/#004).
On failure, reject the write with a clear `400` naming what failed
(unreachable vs auth rejected) WITHOUT leaking the credential. Load
`engineering:security` for the credential handling and `engineering:developer`
for the hook wiring. Keep it minimal: reachability + auth only, no clone, no
content read.

## Acceptance criteria
- [ ] `POST`/`PUT /sources` with a reachable `git` repo and working auth (each of
      none/token/ssh) succeeds and stores the source (secret encrypted).
- [ ] An unreachable URL is rejected with a clear `400` ("cannot reach") and the
      source is NOT stored.
- [ ] A reachable repo with bad credentials is rejected with a clear `400`
      ("authentication failed") and the source is NOT stored.
- [ ] The token/ssh key never appears in any error message, log line, or stored
      row in clear form.
- [ ] Validation does not clone the repo or read its contents (reach + auth
      only), and is bounded by a sane timeout so a hanging remote fails cleanly.
- [ ] Regression-grade tests cover success per auth method and both failure
      modes (unreachable, bad auth), using a local/served git repo or a stubbed
      remote so the suite is deterministic and offline; a test fails if a
      credential leaks or a dead source is accepted.
- [ ] `ruff format`, `ruff check --fix`, `pytest` all clean; work committed.

## Out of scope
- Discovery source types (`bitbucket-workspace`/`github-user`) validation — T41.
- confluence/notion validation — T42/T43.
- Actually cloning or ingesting the source (M2).

## Review log
- 2026-08-15 PO: authored as the T7.2 follow-on to #012. Flagged that tests must
  stay deterministic/offline (local repo or stubbed remote) and that credentials
  must never surface in errors/logs.
- 2026-08-15 dev: picked up (dep 012 in done/), moved to in-progress.
- 2026-08-15 dev: implemented. New `registry/git_validation.py`:
  `validate_git(config, *, run=<real git>, timeout=10)` runs `git ls-remote`
  (no clone) with a bounded timeout and `GIT_TERMINAL_PROMPT=0`; token method
  injects x-access-token/x-token-auth per host, ssh writes the key to a 0600
  temp file and sets a BatchMode GIT_SSH_COMMAND (key file removed in finally);
  exit 0 -> ok, stderr matching auth markers -> ValidationFailed("authentication
  failed"), else -> ("cannot reach repository"). Reasons never include the url,
  stderr, or the credential. Wired as the `sources` descriptor's hook (replaced
  #012's stub). The `run` seam is DI so tests are offline. Tests:
  `test_git_validation.py` (none/token/ssh success with url/env asserted,
  unreachable, bad-auth, timeout->unreachable, and token-absent-from-reason via
  stubbed runner) and updated `test_sources.py` to exercise the REAL hook against
  a local `git init --bare` file:// repo (register/list/fetch/put/delete/secret
  all still pass through real validation) plus an unreachable-url case asserting
  400 and that nothing is stored. Note: filling the hook changed `sources` write
  behavior, so the #012 API tests were updated to a reachable local repo (in
  scope: my change required it). Gate clean (ruff format, ruff check --fix,
  pytest 143 passed). Scope: reach+auth only, no clone; discovery/confluence/
  notion validation are later tickets. Committed bd0c3d5. Moved to verifying.
- 2026-08-15 qa: PASS -> po-review. Verified all dimensions (deep security pass
  on the credential handling). Drove the real server against a real local bare
  repo over file:// (offline, deterministic): method=none and method=token both
  create 201 with the token masked to `***` and encrypted at rest; an
  unreachable repo is rejected with a clean `400 {"detail":"cannot reach
  repository"}`, the source is NOT stored (subsequent GET -> 404, only the
  reachable ones remain), and a token canary appears NOWHERE - not in the 400
  body, not in stdout/stderr server logs, and not in the DB file (encrypted).
  The hook runs before `store.insert`, so a rejected write persists nothing.
  Credential handling is sound: validation runs on the plaintext before
  encryption (it must, to test auth), reasons are opaque ("cannot reach" /
  "authentication failed") and never echo stderr/url/token, the ssh key is
  written to a 0600 temp file and unlinked in a `finally` (even on exception),
  timeout is bounded (10s -> code 124 -> "cannot reach"), and
  `GIT_TERMINAL_PROMPT=0` + ssh `BatchMode=yes` prevent hangs. Uses
  `git ls-remote` only - no clone, no content read. Tests are regression-grade
  and offline: `test_git_validation.py` stubs the runner (DI `run=`) to cover
  none/token/ssh injection, unreachable, bad-auth classification, timeout, and a
  token-never-in-reason assertion; `test_sources.py` exercises the CRUD/reject
  paths against a real local bare repo. Token-URL injection uses the
  spec-sanctioned x-access-token/x-token-auth forms. Minor non-blocking note:
  `_run` passes the full server env to the git child (so HRONO_MASTER_KEY, if
  env-supplied, is inherited) - git never echoes env and stderr is never
  surfaced, so nothing leaks; a minimal-env subprocess would be marginally
  tidier hygiene, not required. Code review clean: DI runner, markers-as-data,
  early returns, typed, docstrings only, no emojis. Commit bd0c3d5 is a proper
  atomic Conventional Commit. Re-ran the gate: ruff format clean (54 files),
  ruff check passed, pytest 143 passed.
- 2026-08-15 PO: PASS -> done. Drove the real validation offline against a local
  `git init --bare` file:// repo: reachable none-auth and token-auth both create
  201 (token masked to ***), an unreachable repo is rejected with a clean
  400 {"detail":"cannot reach repository"} and is NOT stored (GET -> 404), and a
  token canary appears NOWHERE - not in the 400 body, not in stdout/stderr logs,
  not in the DB/WAL plaintext. Uses `git ls-remote` only (no clone), bounded
  10s timeout, GIT_TERMINAL_PROMPT=0, ssh key to a 0600 temp file removed in
  finally, auth markers as data, opaque reasons. Tests are regression-grade and
  offline (DI runner stub + real local repo). Ran the gate: ruff format (54
  clean), ruff check clean, pytest 143 passed. Closed at bd0c3d5. Spun off #017
  for qa's non-blocking env-hygiene note: the git subprocess inherits the full
  server env, so an env-supplied HRONO_MASTER_KEY reaches the child - scrub it
  (least-privilege for the master key).
