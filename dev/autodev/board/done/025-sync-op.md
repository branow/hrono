---
id: 025
title: `sync` op — git clone/pull to cache + version capture (T12)
priority: high
size: big
depends_on: [023, 024, 012, 004]
spec_refs: [build-order.md#T12, design-sketch-v1.md, implementation-notes.md#sources]
---

## Context
`sync` is the first real ingest op and the entry point of the pipeline: it pulls
a source's current bytes into a local cache and captures the exact version those
bytes came from, so everything downstream (filter, split, hash, identity) works
against a pinned snapshot. It registers into the op registry (#023) and runs
per-source via the scope resolver (#024). This ticket does `git` sources only;
discovery/confluence/notion readers are M8.

## Description
Register a `sync` op handler that, for a `git` source, clones the repo into a
local cache on first run and pulls updates on subsequent runs, then records the
synced version.

- **Source config**: read the source row from the `sources` registry (#012) and
  decrypt its `auth` secret via the cipher (#004), using the same token/ssh
  injection as the git validation (#013) — reuse that auth logic, do not
  duplicate it. Never log or persist the credential in clear.
- **Cache location**: a deterministic per-source path under the hrono data dir
  (recommend `./.hrono/cache/sources/<source-name>/`); document it. First run =
  `git clone` (shallow is fine — we only need current bytes); later runs =
  `git fetch` + reset/pull to the target ref. Bound with a timeout;
  `GIT_TERMINAL_PROMPT=0` and non-interactive auth as in #013.
- **Version capture**: after sync, capture the resolved commit SHA as the
  source's synced version and persist it (a `sources`-scoped sync-state row or a
  column — pick and document; the per-file `path + blob hash` identity lands with
  T15, this ticket captures the repo-level commit). Identity must be
  fetch-method-independent per design-sketch (SSH vs HTTPS of the same repo →
  same identity); note how the captured version supports that.
- **Job integration**: the op runs as a job leaf (one per source via #024).
  Success -> the leaf succeeds with the captured version; a clone/pull failure ->
  the leaf fails with a clear reason (no credential leak), leaving other sources'
  leaves unaffected (#023 guarantee).
- Idempotent: syncing an unchanged repo re-captures the same commit and does not
  corrupt the cache.

## Acceptance criteria
- [ ] `sync` over a reachable `git` source clones it into the per-source cache on
      first run and captures the resolved commit SHA as the synced version.
- [ ] A second `sync` of an unchanged repo pulls (no clone), re-captures the same
      commit, and leaves the cache consistent (idempotent).
- [ ] A `sync` after the remote advances fetches the new commits and updates the
      captured version to the new SHA.
- [ ] Auth (none/token/ssh) works via the reused #013 injection; the credential
      never appears in a log, the captured state, or an error reason.
- [ ] A failed sync (unreachable/bad auth) fails its leaf with a clear reason and
      does not affect other sources' leaves or leave a half-written cache that
      breaks the next run.
- [ ] Regression-grade tests use a local bare/file:// repo (offline,
      deterministic): first-clone captures a SHA, commit-then-resync updates it,
      unchanged resync is a no-op, and a bad source fails cleanly; a test fails if
      a credential leaks or the version is not captured.
- [ ] `ruff format`, `ruff check --fix`, `pytest` all clean; work committed.

## Out of scope
- Filtering which files are ingestable (#026 / T13).
- Splitting/chunking, per-file hashing, URIs, storage of sections/passages
  (T14/T15).
- Non-git source readers (bitbucket-workspace/github-user discovery T41;
  confluence/notion T42/T43).
- Change classification / incremental diff (M7 `sync` diff, T33) — this ticket
  only pulls bytes + captures version.

## Review log
- 2026-08-15 PO: authored as the first ingest op. git-only; reuses #013 auth
  injection; captures the repo commit as the version (per-file identity is T15).
  Sized `big` (clone/pull lifecycle + cache + version + job integration); split
  into clone-vs-pull commits if a clean seam exists.
- 2026-08-16 dev: picked up (deps 023, 024, 012, 004 in done/), in-progress.
- 2026-08-16 dev: implemented. Extracted #013's auth logic into a shared
  `registry/git_auth.py::git_auth(url, auth)` context manager (token URL rewrite
  / ssh 0600 keyfile + GIT_SSH_COMMAND, cleaned up on exit); refactored
  `validate_git` onto it (no duplication; its tests still pass). New
  `ingest/sync.py::sync(job, context)`: reads the source from the registry,
  decrypts its `auth` secret via the cipher (generic JobContext gained a
  `cipher` field, threaded from the Worker; app builds it from master_key +
  key_id), clones into `./.hrono/cache/sources/<name>` on first run or
  fetch+`reset --hard FETCH_HEAD` on resync, then captures `rev-parse HEAD` as
  the version in a new `source_state` table (migration 0006). GIT_TERMINAL_PROMPT
  =0, 120s timeout; a failed clone rmtrees the partial cache so the next run is
  clean; failure reasons are credential-free (never stderr). Version = commit SHA
  -> content-addressed, so SSH vs HTTPS of the same repo yield the same identity.
  Registered into the op registry (`OPS["sync"]=sync`; app imports ingest.sync).
  Worker `claim_next` already skips parents (#024) so per-source leaves run
  independently. Tests: `tests/ingest/test_sync.py` (offline, local file:// repos)
  — first clone captures the SHA + cache contents, idempotent unchanged resync,
  remote-advance updates the SHA, bad source -> SyncError + no half-written cache,
  token auth decrypted + never in state, and sync running as a registered job op
  via fan-out through the Worker. Gate clean (ruff format, ruff check --fix,
  pytest 250 passed). Verified live: registering a file:// git source returns 201
  (the shared git_auth drives #013 validation in the running server); the sync
  execution path is covered by the unit tests (no external enqueue endpoint yet).
  Scope: filtering #026, split/hash/URIs T14/T15, discovery/confluence M8,
  incremental diff M7. Committed f215dc7. Moved to verifying.
- 2026-08-16 qa: FAIL -> back to todo. One blocking security defect on AC4
  ("the credential never appears in a log, the captured state, or an error
  reason") and the description's explicit "Never log or persist the credential
  in clear".

  Finding (token-auth git credential persisted in cleartext in the cache):
  for a `token`-auth git source, `git_auth._with_token` rewrites the https URL
  to `https://x-access-token:<TOKEN>@host/...` and `sync._sync_repo` runs
  `git clone <effective> <cache>` (src/hrono/ingest/sync.py:64). Git persists the
  clone URL VERBATIM into `<cache>/.git/config` as `remote.origin.url`, so the
  decrypted token is written in cleartext to
  `.hrono/cache/sources/<name>/.git/config`. Worse, the re-sync path runs
  `git fetch origin` (sync.py:59), which reads that stored URL - so the design
  actively DEPENDS on the token being persisted in config. Verified empirically:
  `git remote add origin https://x-access-token:SUPERSECRETTOKEN@github.com/...`
  stores `remote.origin.url = https://x-access-token:SUPERSECRETTOKEN@github.com/
  ...` in `.git/config` (grep confirms the token in cleartext), and a plain
  `git clone` stores the passed URL verbatim. This defeats the encrypt-at-rest
  guarantee (#003/#004): any user/process/backup with filesystem read access to
  the hrono data dir obtains the git token in cleartext.

  Why the tests miss it: `test_token_auth_is_decrypted_and_never_leaks` uses a
  local `file://` repo, but `_with_token` only rewrites `https://` URLs, so the
  token is NEVER injected into the clone URL in that test and `.git/config` never
  receives it; the test then only asserts the token is absent from the
  `source_state` table - not from the cache. The suite is green while the real
  https-token path leaks. `none` and `ssh` are fine (none has no credential; ssh
  uses a 0600 key file that git_auth unlinks and never writes to config).

  Required change: do not leave the token in the persisted remote URL. After the
  clone, immediately `git -C <cache> remote set-url origin <token-free-url>` so
  `.git/config` holds only the clean URL, and re-inject auth per fetch WITHOUT
  writing it to disk - e.g. fetch the effective (token) URL explicitly
  (`git -C <cache> fetch <effective>` instead of `fetch origin`), or use
  `GIT_ASKPASS` / a transient `-c http.<url>.extraheader=Authorization: ...` /
  `-c credential.helper=`. Then add a regression test for the https-token path
  that asserts the token string appears NOWHERE under
  `.hrono/cache/sources/<name>/` (including `.git/config`) after a first sync AND
  a re-sync - a test that fails if the credential is persisted. (Use a local
  token-checking http remote, or at minimum assert the effective token URL is
  never written to `.git/config`.)

  Everything else verified and sound (do not re-litigate on return): the
  `git_auth` extraction (shared by #013 validation and sync, no duplication),
  the clone-first / fetch+reset-later lifecycle, commit-SHA version capture into
  the `source_state` upsert (idempotent, fetch-method-independent), cache cleanup
  on a failed clone (rmtree + re-raise), the none/ssh auth paths, timeout +
  GIT_TERMINAL_PROMPT=0, opaque credential-free failure reasons, JobContext
  gaining `cipher` and the worker/app wiring, and the sync op registered into
  the #023 registry running per-source via #024. The gate is clean (ruff
  format/check, pytest 250 passed) - the fix should keep it so and add the
  token-persistence test.
- 2026-08-16 qa: FAIL -> back to todo. https-token clone persisted the token in
  the cache's .git/config (git_auth injected the token into the clone URL; the
  test only checked source_state, not the cache).
- 2026-08-16 dev: fixed. Reworked `git_auth` to never rewrite the URL for token
  auth — it now yields (clean_url, env, config_args) and supplies the token via a
  transient inline credential helper (`-c credential.helper=` reset + an inline
  helper that reads the token from `HRONO_GIT_TOKEN` in the env). The URL stays
  clean, so nothing lands in `.git/config` or `FETCH_HEAD`; the secret lives only
  in the process env for the git call. Unified: both `validate_git` (ls-remote)
  and `sync` (clone/fetch) use this same triple — no duplication, and validation
  no longer puts the token in argv either. Runner signature gained `config_args`.
  Tests: new `tests/registry/test_git_auth.py` asserts the token stays out of the
  URL and config args and goes to env (github x-access-token / bitbucket
  x-token-auth); updated `test_git_validation.py` stubs; strengthened the sync
  token test to assert the token appears NOWHERE under the cache dir (incl.
  .git/config) after first sync AND resync. Gate clean (ruff format, ruff check
  --fix, pytest 254 passed). Proved directly: a real token-auth clone+resync
  leaves `.git/config` holding only the clean file:// URL, token absent from the
  whole cache, version still captured. Committed 4937f84. Back to verifying.
- 2026-08-16 dev: fixed. Reworked `git_auth` to yield `(clean_url, env,
  config_args)`: token auth no longer rewrites the URL - the URL stays clean and
  the token is supplied via a transient inline credential helper
  (`-c credential.helper=` to reset others, then `-c credential.helper=!f() {
  echo username=<user>; echo password=$HRONO_GIT_TOKEN; }; f`) with the token in
  the `HRONO_GIT_TOKEN` env var, so nothing token-bearing is ever written to
  `.git/config`. sync clones/fetches with the clean URL + config_args on every
  invocation (fetch no longer depends on a persisted token); git_validation
  updated to the same signature. Added `test_git_auth.py` (token stays out of
  url/config, goes to env) and reworked the sync test to rglob the whole cache
  (incl `.git/config`) for the token after clone AND re-sync. Committed 4937f84.
  Back to verifying.
- 2026-08-16 qa: PASS -> po-review. Re-verified the fix; the blocking
  token-persistence defect is resolved. Confirmed `git_auth`'s token path yields
  a CLEAN url with the token only in `HRONO_GIT_TOKEN` env (not the url, not the
  config args - the args carry the literal `$HRONO_GIT_TOKEN` reference expanded
  by git at helper-run time), and it resets other credential helpers first.
  Drove a real token-auth sync against a local repo (clone + re-sync): the
  commit SHA is captured and stable (idempotent), the token appears NOWHERE
  under `.hrono/cache/sources/repo/` including `.git/config`, and the stored
  `remote.origin.url` is clean. This also strengthens #013 - the token is no
  longer in the clone/ls-remote process cmdline or in config, only transiently
  in the process env. none/ssh paths unchanged and still green. The regression
  test now rglobs the entire cache for the token after both clone and fetch (it
  would fail if the credential were persisted), and `test_git_auth.py` locks the
  mechanism. Re-ran the gate: ruff format clean (95 files), ruff check passed,
  pytest 254 passed. All previously-verified dimensions still hold (git_auth
  extraction, clone/fetch lifecycle, SHA version capture, cache cleanup on
  failure, job wiring); the fix commit is a proper atomic Conventional Commit
  (`fix:`), no emojis.
- 2026-08-16 PO: PASS -> done. This ticket earned its qa bounce: the first cut
  persisted a token-auth git credential in cleartext in the cache's .git/config
  (git wrote the token-bearing clone URL to remote.origin.url), a real
  encrypt-at-rest bypass - caught, fixed, re-verified. Independently confirmed the
  fix: `git_auth` token path yields a CLEAN url with the token ONLY in the
  HRONO_GIT_TOKEN env (not the url, not the config_args - those carry an inline
  credential helper referencing $HRONO_GIT_TOKEN, expanded by git at run time),
  and after a REAL clone via git_auth, rglobbing the entire cache found ZERO
  files containing the token, with remote.origin.url clean. This also hardens
  #013 (token no longer in argv/config for ls-remote). Clone-first/fetch+reset
  lifecycle, commit-SHA version capture into source_state (idempotent,
  fetch-method-independent), cache cleanup on failed clone, none/ssh paths, and
  the op registered into #023 running per-source via #024 all verified across the
  cycle. Ran the gate: ruff format (95 clean), ruff check clean, pytest 254
  passed. Unblocks #026 (filter). Closed at 4937f84.
