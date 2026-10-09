---
id: 003
title: master-key startup load (file/env, refuse-without, fingerprint)
priority: high
size: medium
depends_on: [001, 002]
spec_refs: [build-order.md#T3.2, implementation-notes.md#secrets-at-rest]
---

## Context
The server needs the master key to encrypt and decrypt secrets, and must fail
fast and clearly if the key is missing or wrong — a silent failure here means
corrupt or unreadable secrets. This ticket loads the key at `hrono serve`
startup and reconciles its fingerprint against the `keys` table (from #001,
opened and migrated by #002) so a wrong key is rejected before any request is
served. It provides the loaded key to the app for the cipher (#004).

## Description
1. **Load the key.** At startup, read the master key from `--key-file <path>`
   (preferred) or the `HRONO_MASTER_KEY` env var. `--key-file` wins when both are
   set. Add the `--key-file` option to `hrono serve` (spec CLI:
   `hrono serve --key-file <path> [--port 8080]`).
2. **Refuse without / on bad key.** Exit non-zero with a clear, actionable
   message if neither source is provided, the file is missing/unreadable, or the
   key is malformed (not a valid Fernet key). The server must not start.
3. **Reconcile fingerprint** using `fingerprint` and `KeyRecord` from #001,
   against the `keys` table:
   - keys table empty → insert a row for this key's fingerprint as the active
     key (the raw key is never stored).
   - a key row exists → the provided key's fingerprint must equal the active
     key's `key_hash`; on mismatch, refuse to start with a clear "wrong master
     key" error and mutate nothing. (Never auto-add a second key here — rotation
     is T59.)
4. **Expose to the app.** Make the loaded key and active `key_id` available to
   the application (app state or an injected dependency) for the cipher in #004.
   Never log the key; never store it in the DB.

Conventions: secrets never logged; fail-closed; DI over monkeypatch; clear
actionable errors; minimum surface (only the one `--key-file` option).

## Flagged assumption
The spec mandates Fernet (`cryptography`). A Fernet key is a urlsafe-base64
32-byte string; this ticket assumes the master key is supplied in that format
and validates it as such. If the team prefers accepting a passphrase and
deriving a Fernet key (KDF), raise it before implementing — do not silently
choose.

## Acceptance criteria
- [ ] `hrono serve` with neither `--key-file` nor `HRONO_MASTER_KEY` exits
      non-zero with a message naming both ways to supply the key.
- [ ] `--key-file` takes precedence over `HRONO_MASTER_KEY` when both are set.
- [ ] A malformed/invalid key is rejected at startup with a clear error and the
      server does not start.
- [ ] First start with an empty `keys` table records the key's fingerprint (a
      row appears; the raw key does not appear in the DB).
- [ ] Restart with the same key starts cleanly; restart with a *different* key
      is refused with a "wrong master key" error and no data is mutated.
- [ ] The active key and `key_id` are retrievable by the app for later
      encryption; the key never appears in logs or the database.
- [ ] Tests cover: missing key, precedence, invalid key, first-run insert,
      matching restart, mismatching restart.
- [ ] `ruff format`, `ruff check --fix`, and `pytest` are all clean; committed.

## Out of scope
- The encrypt/decrypt helper itself (that is #004).
- Key rotation / `POST /admin/rotate-key` (that is T59).
- Users / auth tokens (that is T4).

## Review log
- 2026-08-15 PO: authored and moved to todo. Flagged the Fernet-key-format
  assumption for dev to confirm before implementing.
- 2026-08-15 dev: picked up (001+002 in done/; both 003 and 005 were ready,
  took 003 by lowest-id tie-break). Resolving the flagged assumption in favour
  of the ticket's stated default: master key is a Fernet key (url-safe base64
  32-byte), validated as such. This is not a silent choice — Fernet is mandated
  by the spec (CLAUDE.md stack + implementation-notes#secrets-at-rest) and is
  the ticket's own default; passphrase+KDF would be a new, unspec'd decision.
  Added the `cryptography` runtime dependency (44.0.3), which the stack already
  lists. Moved to in-progress.
- 2026-08-15 dev: implemented. New `src/hrono/crypto/masterkey.py`:
  `load_key(key_file, env_value)` (file wins over env, strips whitespace,
  validates via `Fernet`, raises typed `KeyNotProvided`/`KeyFileUnreadable`/
  `InvalidKey`), and `reconcile(conn, key)` (empty keys table -> insert this
  key's fingerprint as key_id 1; existing -> must match `key_hash` or raise
  `WrongMasterKey`, mutating nothing; raw key never stored). Added `--key-file`
  to `hrono serve`; the CLI loads the key, maps errors to a clear non-zero exit
  (boundary owns the messages, exceptions carry attributes), then runs uvicorn
  with an app instance. `create_app` gained `master_key`; its lifespan
  reconciles before serving and holds the key + key_id in app.state (never
  logged, never persisted). Tests: `tests/crypto/test_masterkey.py` (file/env
  precedence, missing/empty/unreadable/invalid, first-run insert, raw-key
  absence, matching restart reuse, mismatch refuses + mutates nothing);
  `tests/server/test_cli.py` (refuse-without-key message names both sources,
  invalid rejected, boots with a valid key, host/port defaults); startup tests
  for key exposure and wrong-key refusal. Gate clean (ruff format, ruff check
  --fix, pytest 52 passed). Verified the real binary end-to-end: no key -> exit
  1 with the two-source message; first start writes one keys row (fingerprint
  only, raw key absent); matching restart clean; wrong key -> WrongMasterKey,
  server unreachable, keys table unchanged. Resolved the flagged assumption in
  favour of Fernet key format (spec-mandated). Filed backlog
  `sqlite-connection-thread-affinity` for the DB threading model (out of scope).
- 2026-08-15 qa: FAIL -> back to todo. One blocking defect on acceptance
  criterion 5 / description point 3 ("refused with a *clear* 'wrong master
  key' error").

  Finding (wrong-key refusal is an uncaught traceback, not a clear message):
  the missing-key and invalid-key paths exit with a clean one-line actionable
  message via the `except MasterKeyError -> typer.echo(_key_error_message(exc),
  err=True) -> raise typer.Exit(1)` handler at `src/hrono/cli.py:56-60`, and
  `_key_error_message` (`cli.py:65-67`) already falls back to `str(exc)` for
  `WrongMasterKey` ("wrong master key: does not match the active key"). But
  that handler only wraps `load_key` (`cli.py:57`). `reconcile` is called later,
  inside the FastAPI lifespan at `src/hrono/server/app.py:63`, which runs after
  `uvicorn.run` has started — so `WrongMasterKey` never reaches the CLI handler.
  Verified by driving the real binary: seeding a key then starting `hrono serve
  --key-file <other.key>` prints a full Python traceback ending in
  `hrono.crypto.masterkey.WrongMasterKey: wrong master key...` followed by
  uvicorn's `ERROR: Application startup failed. Exiting.` (exit code 3). The
  server correctly does not serve and mutates nothing (keys row count stays 1),
  so the fail-closed and no-mutation halves of the criterion hold — but a stack
  trace on the single most common operator mistake (pointing serve at the wrong
  key) is not the "clear" error the ticket requires, and it is inconsistent with
  the two sibling error paths that are clean.

  Required change: the wrong-key refusal must present the same clean, actionable
  one-line message and non-zero exit as the missing/invalid-key paths, not a
  traceback. The natural fix is to run `reconcile` where its `MasterKeyError`
  can flow through the existing `_key_error_message` handler — e.g. in the CLI
  before `uvicorn.run`, opening the DB via `open_database(db_path)`, reconciling
  there, then `create_app(connection=conn, master_key=key)` (the factory already
  accepts an injected `connection`). Add a test that asserts the wrong-key
  startup exits non-zero with the clear "wrong master key" message and NO
  traceback (the current `test_startup_refuses_a_wrong_master_key` only asserts
  `WrongMasterKey` is raised at the lifespan layer, so it does not catch this).

  Everything else verified and passing (not re-litigate on return): load
  precedence (--key-file over env), missing/empty/unreadable/invalid rejection,
  first-run fingerprint insert with raw key absent from the DB file, matching
  restart clean, no raw key in any serve log, key+key_id exposed in app.state,
  fingerprint-only persistence, commit shape (feat, one line, no body/attr),
  and the gate (ruff format/check clean, pytest 52 passed).
  Committed 85332a6. Moved to verifying for qa.
- 2026-08-15 dev: fix for the qa finding. Moved the key reconciliation out of the
  FastAPI lifespan and into the CLI preflight: `serve` now calls
  `load_key` -> `open_database(DEFAULT_PATH)` -> `reconcile(conn, key)` inside the
  same `try/except MasterKeyError` that already maps to a clean one-line message
  + `typer.Exit(1)`, so `WrongMasterKey` flows through `_key_error_message`
  exactly like the missing/invalid paths. The reconciled connection + key +
  key_id are injected into `create_app(connection=..., master_key=..., key_id=...)`
  and closed after `uvicorn.run`. `create_app` now reconciles only when it owns
  the connection (the db_path/test path); an injected connection is trusted as
  already reconciled and takes its `key_id` from the caller — this also avoids a
  redundant second reconcile. Added
  `test_serve_refuses_a_wrong_key_with_a_clear_message_not_a_traceback` (seeds a
  key, then starts with a different one, asserts non-zero exit, "wrong master
  key" in output, and NO "Traceback"); added `monkeypatch.chdir(tmp_path)` to the
  two valid-key CLI tests so the now-real `open_database(DEFAULT_PATH)` writes
  under tmp, not the repo. Gate clean (ruff format, ruff check --fix, pytest 69
  passed). Verified on the real binary: seeded a key (health ok), then
  `serve --key-file <other>` printed exactly `wrong master key: does not match
  the active key` and exited 1 with no traceback. Committed 42064c2. Moved to
  verifying for qa.
- 2026-08-15 dev: fixed. Moved reconcile into the CLI before `uvicorn.run`,
  inside the existing `except MasterKeyError` handler, so a wrong key prints the
  clear one-line message and exits 1 like the missing/invalid paths; threaded
  `key_id` into `create_app` so the lifespan no longer double-reconciles an
  injected connection. Added regression test asserting wrong-key exits non-zero
  with "wrong master key" and no Traceback. Committed 42064c2. Back to verifying.
- 2026-08-15 qa: PASS -> po-review. Re-verified the fix by driving the real
  binary: after seeding a key, `hrono serve --key-file <other>` now prints
  "wrong master key: does not match the active key" and exits 1 with no
  traceback, and the keys table is unchanged (1 row). Confirmed reconcile is
  caught by the CLI handler (`cli.py`), `key_id` is passed to `create_app` and
  the lifespan only reconciles when it owns the connection, and the CLI-owned
  connection is closed in a `finally`. Missing/invalid-key paths still
  short-circuit before the DB is opened. Regression covered by the new
  `test_serve_refuses_a_wrong_key_with_a_clear_message_not_a_traceback`. Gate
  re-run clean: ruff format (31 files), ruff check passed, pytest 69 passed. All
  previously-verified dimensions still hold; no other changes in the fix commit.
- 2026-08-15 PO: PASS -> done. The qa-flagged defect is genuinely fixed:
  `reconcile` now runs in the CLI preflight inside the existing
  `except MasterKeyError` handler (`cli.py`), so a wrong key flows through the
  data-driven `_KEY_ERRORS` map (str(exc) fallback) exactly like the missing/
  invalid paths; the injected connection stops the lifespan double-reconciling.
  Drove the real binary from a fresh temp cwd: no key -> clean one-line message,
  exit 1, zero traceback; first start with a valid key -> /health ok, one
  fingerprint row (raw key absent); wrong key -> "wrong master key: does not
  match the active key", exit 1, ZERO traceback lines, keys table unchanged
  (fail-closed + no mutation both hold). Ran the gate myself: ruff format (31
  clean), ruff check clean, pytest 69 passed. Regression locked by
  `test_serve_refuses_a_wrong_key_with_a_clear_message_not_a_traceback`.
  Unblocks #004 (Fernet cipher). No adjacent work spun off. Closed at 42064c2.
