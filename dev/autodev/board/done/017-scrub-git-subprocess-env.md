---
id: 017
title: git validation subprocess runs with a scrubbed env (no master key)
priority: low
size: small
depends_on: [013]
spec_refs: [build-order.md#T7.2]
---

## Context
Spun off from #013 PO review (qa non-blocking find). `git_validation._run` builds
the child process env as `{**os.environ, "GIT_TERMINAL_PROMPT": "0"}`, so the
git subprocess inherits the entire server environment — including
`HRONO_MASTER_KEY` when the key is supplied via env. In practice nothing leaks
(git does not echo its env and its stderr is never surfaced to the client), so
this is low priority — but the master key is the crown-jewel secret that decrypts
every stored credential, and least-privilege says a subprocess that has no need
for it should not receive it. Cheap defense-in-depth.

## Description
Run the `git ls-remote` subprocess with a minimal, explicit environment instead
of inheriting the full server env. Pass only what git legitimately needs
(e.g. `PATH`, `HOME` for ssh/config resolution, and the intentional
`GIT_TERMINAL_PROMPT=0` / `GIT_SSH_COMMAND`), and deliberately exclude
`HRONO_MASTER_KEY` (and any other hrono secret env). Keep the DI `run` seam and
all current behavior (none/token/ssh, timeout, opaque reasons) unchanged — this
is purely tightening the child env.

## Acceptance criteria
- [ ] The git subprocess environment does NOT contain `HRONO_MASTER_KEY` (assert
      in a test that sets it and inspects the env passed to a stubbed runner /
      the constructed env).
- [ ] git still resolves and runs: none/token/ssh validation all behave exactly
      as before (reachable -> ok, unreachable -> "cannot reach", bad auth ->
      "authentication failed", timeout bounded); ssh still finds its key via
      `GIT_SSH_COMMAND`.
- [ ] No credential or master key appears in the child env, any reason, or logs.
- [ ] Regression test asserts the scrubbed env (master key absent) and that a
      normal validation path still succeeds.
- [ ] `ruff format`, `ruff check --fix`, `pytest` all clean; work committed.

## Out of scope
- Any change to the validation logic, auth methods, or reason messages.
- Scrubbing subprocess envs elsewhere (only the git validation path is in
  scope; if other subprocesses land later they get the same treatment then).

## Review log
- 2026-08-15 PO: authored from #013 review (qa env-hygiene note). Low/small;
  nothing leaks today, but the master key should not ride into subprocesses that
  do not need it.

## Review log (PO routing correction) — 2026-08-16
- PO: this ticket's implementation was committed but the ticket file was left in
  todo/ (the committed code matches the ticket exactly; the gate at HEAD passes).
  Routing it to verifying/ so qa verifies it properly - NOT closing it here (it
  must still pass qa + PO review). Recurring hygiene: commit AND route the ticket
  (todo->in-progress->verifying) together; do not leave a committed ticket
  stranded in todo.

## qa — 2026-08-16

PASS -> po-review. Verified; resolves the #013 env-hygiene note. `git_auth`
now yields a COMPLETE minimal child env via `_child_env`: `GIT_TERMINAL_PROMPT=0`
plus an explicit allowlist of non-secret vars git legitimately needs (PATH, HOME,
TLS cert vars, proxy vars) copied from os.environ when present, plus the auth
extra (HRONO_GIT_TOKEN / GIT_SSH_COMMAND); `HRONO_MASTER_KEY` and every other
server secret are excluded. Both git subprocess paths were tightened - `sync._run`
and `git_validation._run` now pass `env=env` instead of `{**os.environ, **env}`
(correctly covering #025 sync as well as #013 validation via the shared
`git_auth`). Drove it with `HRONO_MASTER_KEY=CROWN-JEWEL` set in the server env:
the git child env for none/token/ssh contains neither the var nor its value,
while PATH and GIT_TERMINAL_PROMPT are present; and a REAL none-auth sync against
a local repo still clones and captures a 40-char commit SHA with the scrubbed env
(functionality preserved). Tests are regression-grade
(`test_child_env_excludes_hrono_secrets` parametrized over none/token/ssh, and
`test_subprocess_env_excludes_the_master_key` through the validate_git path -
both assert the key absent and PATH/GIT_TERMINAL_PROMPT present). Code review
clean: explicit allowlist as data, DI `run` seam and all auth/timeout/opaque-
reason behavior unchanged, typed, docstrings only, no emojis. Commit 9e16d3d is a
proper atomic Conventional Commit (`fix:`).

Verified 017 IN ISOLATION: the working tree carried dev's in-progress #030-fix
WIP (`pack.py`/`test_pack.py`, mid-edit, which introduced 2 transient ruff-check
errors); I stashed it, re-ran the gate on 017's committed HEAD - ruff format
clean (114 files), ruff check "All checks passed", pytest 317 passed - then
restored the WIP. 017's own commit is clean and independently verified. Process
note (recurring, now a 3rd instance): the #030-fix WIP polluted this review; the
standing ask to keep the tree clean between tickets stands.
- 2026-08-16 PO: PASS -> done. Independently confirmed the least-privilege fix
  with HRONO_MASTER_KEY=CROWN_JEWEL_SECRET set in the env: `git_auth`'s
  `_child_env` builds the git child env from GIT_TERMINAL_PROMPT=0 + an explicit
  allowlist (PATH/HOME/TLS/proxy) + the auth extra - it does NOT copy the whole
  os.environ, so for none/token/ssh the master key (name AND value) is ABSENT
  from the child env while GIT_TERMINAL_PROMPT and PATH are present. Both git
  subprocess paths (sync._run + git_validation._run) pass env=env, not
  {**os.environ,**env}. Ran the gate: ruff format (114 clean), ruff check clean,
  pytest 318 passed. Resolves the #013 env-hygiene note; least-privilege for the
  crown-jewel secret. All hardening follow-ups (011/014/017) now done. Closed at
  9e16d3d.
