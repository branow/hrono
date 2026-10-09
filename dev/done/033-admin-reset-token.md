---
id: 033
title: `hrono admin reset-token <user>` — reissue a token locally, no data loss
priority: medium
size: medium
depends_on: [005]
spec_refs: [build-order.md#T4, implementation-notes.md#auth, admin-recovery-and-reset]
---

## Context
Promoted from the stakeholder backlog request `admin-recovery-and-reset`. The
bootstrap admin token is printed once and stored only as a SHA-256 hash; lose it
and the API is unrecoverable via HTTP (no user can authenticate to make another,
and bootstrap will not re-fire on a non-empty `users` table). This is the
**targeted** recovery path: a local CLI command that reissues a user's token
against the DB file directly, with no data loss. The nuclear full-reset is #034.
Load `engineering:security` (auth-bypass boundary) before starting.

## Description
Add `hrono admin reset-token <user>` to the Typer CLI. It:
- Opens the local hrono DB directly (`open_database`, migrations already applied)
  and, for the named existing user, generates a fresh token, stores only its new
  hash (reusing #005's `generate_token`/`hash_token`), and prints the raw token
  ONCE with the same one-time-display posture as bootstrap (#007) — name, role,
  "shown once", Bearer usage.
- **Requires NO existing Bearer token** — it is the recovery path *from* having
  none. Its trust boundary is local filesystem access to the DB (the same access
  that could already do sqlite surgery), so it bypasses API auth by design; state
  this in the help text.
- Does NOT require the master key: token hashes are independent of the encrypted
  secrets, so recovery works without it (do not force `--key-file`).
- Unknown user -> a clear `AppError` (rendered via the CLI helper) and non-zero
  exit; never a traceback. If the DB does not exist yet, say so clearly (there is
  nothing to reset; run `serve` first to bootstrap).
- Only touches the `users` table (the target user's `token_hash`); no other row
  changes.

Note: this reissues an EXISTING user's token. It does not create users
(that is the authed `POST /users`) and is not key rotation (`rotate-key`, T59).
Naming sits under `hrono admin` for discoverability; flag if the team prefers a
different namespace given it is a no-auth local op (unlike the authed
`admin rotate-key`).

## Acceptance criteria
- [ ] `hrono admin reset-token <existing-user>` prints a fresh raw token once
      (name/role/one-time/Bearer message) and updates only that user's
      `token_hash`; the OLD token no longer authenticates and the NEW one does.
- [ ] It requires no existing Bearer token and no master key; it operates on the
      local DB file.
- [ ] An unknown user -> clear error + non-zero exit, no traceback; a missing DB
      -> clear "nothing to reset / run serve first" message.
- [ ] No row other than the target user's token hash is modified; other users'
      tokens still authenticate.
- [ ] Help text documents that this is a local recovery command that bypasses API
      auth via filesystem access.
- [ ] Regression-grade tests: reissue rotates the hash (old token fails / new
      works via `authenticate`), unknown-user error, missing-DB message, and only
      the target row changes; token never persisted in plaintext, never logged.
- [ ] `ruff format`, `ruff check --fix`, `pytest` all clean; work committed.

## Out of scope
- Nuclear full reset / DB wipe (#034).
- Creating users, changing roles, or `rotate-key` (T59).
- Any HTTP endpoint (this is a local CLI recovery command by design).

## Review log
- 2026-08-16 PO: triaged from the stakeholder `admin-recovery-and-reset` request;
  split targeted (#033) vs nuclear (#034). Medium priority - real ops gap, not
  blocking M2/M3; should land by MVP (M6). Security boundary = local file access,
  no auth/key required, stated in help. Flagged the `hrono admin` namespace for
  confirmation.

## dev — 2026-08-16

Added `hrono admin reset-token <user>` as a new `admin` Typer sub-app
(`src/hrono/admin/`), plus `auth.users.reset_token(conn, name)` which reissues
an existing user's token: generates a fresh token (#005 helpers), UPDATEs only
that user's `token_hash`, returns the raw token once, and raises NotFound for an
unknown user.

Security posture (engineering:security): no Bearer token and no master key
required — token hashes are independent of the encrypted secrets, so recovery
works without the key. Trust boundary is filesystem access to the DB, stated in
the sub-app help text. Raw token generated securely, only its hash stored,
printed ONCE with the same posture as bootstrap (#007), never logged.

Guards: DEFAULT_PATH is checked for existence BEFORE open_database (which would
otherwise create an empty file), so a missing DB yields a clear
"nothing to reset / run serve first" message + exit 1. Unknown user -> AppError
rendered via cli_message + exit 1, no traceback. Only the target row's
token_hash changes.

Namespace: used `hrono admin` per the ticket's own recommendation (PO flagged it
for confirmation). It sits alongside the future authed `admin rotate-key`;
acceptable since discoverability wins and the no-auth nature is documented in
help. Flag on review if the team wants a distinct namespace for no-auth local
ops.

Verified on the real binary: seeded admin+reader, `reset-token admin` reissued
and the new token authenticates as admin/admin; the bootstrap flow earlier
confirmed the old token returns 200 before reset (so rotation invalidates it —
also covered by pytest against `authenticate`). Unknown user prints
"user not found: nobody" exit 1; missing DB prints the run-serve-first message.

Tests: rotation (old fails via authenticate / new works), only-target-row-
changes (other user still authenticates, non-secret columns unchanged),
unknown-user clean error, missing-DB message, new token never in the stored hash
nor the DB file bytes, and help documents the auth bypass. Gate clean: ruff
format/check, pytest 289 passed. Commit 895bcfb.

## qa — 2026-08-16

PASS -> po-review. Verified all dimensions (engineering:security lens on the
auth-bypass boundary). Tree was clean and 033 committed in isolation (895bcfb) -
the earlier #033 WIP is now properly committed. Drove the real binary: from an
empty cwd, `hrono admin reset-token admin` prints "No hrono database ... nothing
to reset. Run 'hrono serve' first" and exits 1 (the command checks
`DEFAULT_PATH.exists()` BEFORE `open_database`, so it never creates an empty DB).
After bootstrapping, `reset-token admin` runs with NO --key-file and NO Bearer
token, prints the new token ONCE (name/role/"shown ONCE"/"previous no longer
works"/Bearer). Restarting the server: the OLD admin token is now REJECTED (401),
the NEW token authenticates as admin/admin (200), and the reader's token is
UNAFFECTED (200) - rotation works and touches only the target user. Byte-level
security check: the raw token is NOT in the DB file (only its SHA-256 hash is
stored, and the stored hash == sha256(new token)); the admin role and the user
count are unchanged, so only `token_hash` mutated. Unknown user -> "user not
found: nobody" + exit 1 (via the #027/#028 AppError + cli_message, no traceback).
Help text documents the design: "bypass API authentication ... trust boundary is
filesystem access, so they need no token and no key" - a legitimate boundary
since filesystem access could already do the same sqlite surgery, and no master
key is needed because token hashes are independent of the encrypted secrets.
Tests are regression-grade (rotation via `authenticate`, only-target-row,
unknown-user, missing-DB, token-never-in-plaintext incl. a DB-bytes scan,
help-documents-bypass). Code review clean: reuses #005 `generate_token`/
`hash_token`, only-target UPDATE, typed, docstrings only, no emojis; scope
correct (reissues an existing user only - not create/rotate-key/HTTP). Commit
895bcfb is a proper atomic Conventional Commit (`feat:`). Re-ran the gate: ruff
format clean (109 files), ruff check passed, pytest 289 passed.
- 2026-08-16 PO: PASS -> done. Drove the real recovery flow (tree clean, 033
  committed in isolation at 895bcfb - the hygiene issue self-corrected). Missing
  DB -> clear "nothing to reset. Run 'hrono serve' first" + exit 1 (checks
  DEFAULT_PATH.exists() before open_database, never creates an empty file).
  `admin reset-token admin` with NO --key-file and NO Bearer token -> exit 0 and
  a clean one-time message (user/role/new token/"previous no longer works"/
  Bearer). After restart: the OLD admin token -> 401 (rotated out), the NEW ->
  200, and the reader's token -> 200 (only the target user's token_hash changed);
  the new token is absent from the DB/WAL plaintext (only its SHA-256 hash
  stored). Unknown user -> "user not found: nobody" + exit 1 via #027/#028
  AppError + cli_message, no traceback. Auth-bypass boundary is sound and
  documented in help (local file access, no key needed - token hashes are
  independent of encrypted secrets). Ran the gate: ruff format (109 clean), ruff
  check clean, pytest 289 passed. Targeted recovery half of the stakeholder
  request; #034 is the nuclear half. Closed at 895bcfb.
