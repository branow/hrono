---
id: 005
title: users table + CRUD + token hashing
priority: high
size: medium
depends_on: [002]
spec_refs: [build-order.md#T4.1, implementation-notes.md#auth]
---

## Context
Roles must be enforced server-side from day one, and enforcement needs a place
to look up who a token belongs to and what role they hold. This ticket lays the
persistence and domain layer for auth: the `users` registry, the token
generator/hasher, and the pure CRUD operations over users. It unblocks the
Bearer middleware (#006) and the bootstrap-admin flow (#007). It deliberately
does NOT wire any HTTP route or middleware — this is storage + pure functions
only, so it can be tested without a running server. Spun off from the M0->M1
auth slice (T4) to keep dev's queue stocked past the T3 tail.

## Description
Tokens are verify-only, so we store a one-way hash of the token, never the
token itself (unlike provider secrets, which are reversibly encrypted). A token
is high-entropy random, so a fast one-way hash with constant-time comparison is
the correct and sufficient primitive — do NOT reach for bcrypt/argon2 (those
are for low-entropy passwords) and do NOT hand-roll crypto. Load
`engineering:security` before writing this.

Three changes:

1. **Migration** `src/hrono/db/migrations/0002_users.sql` (0002 is the next free
   number; 0001 is taken) creating table `users`:
   - `name TEXT PRIMARY KEY` — the user's unique handle.
   - `role TEXT NOT NULL` — one of `reader` | `writer` | `admin`
     (kebab-case values; enforce the set in code, and add a `CHECK` constraint).
   - `token_hash TEXT NOT NULL UNIQUE` — SHA-256 hex of the raw token bytes.
   - `created_at TEXT NOT NULL` — ISO-8601 UTC timestamp.

2. **Token primitives** in a new module (recommend
   `src/hrono/crypto/tokens.py`, alongside `keys.py`):
   - `generate_token() -> str` — a fresh high-entropy URL-safe token
     (`secrets.token_urlsafe(32)`).
   - `hash_token(token: str) -> str` — SHA-256 hex of the token's UTF-8 bytes
     (mirror `keys.fingerprint` in shape; deterministic, one-way).
   - `verify_token(token: str, token_hash: str) -> bool` — constant-time
     compare via `hmac.compare_digest`; never a plain `==`.

3. **User domain + CRUD** in a new module (recommend
   `src/hrono/auth/users.py`):
   - a frozen `User(name: str, role: str, created_at: str)` model
     (note: the token hash is a storage detail, not part of the returned model;
     never expose token or hash in any read).
   - a `Role` set/enum fixing the three valid roles.
   - pure functions taking a `sqlite3.Connection`:
     `create_user(conn, name, role) -> tuple[User, str]` (inserts the row with a
     freshly generated+hashed token, returns the `User` and the raw token
     **once**), `get_user(conn, name) -> User | None`,
     `list_users(conn) -> tuple[User, ...]`, `delete_user(conn, name) -> bool`,
     and `authenticate(conn, token) -> User | None` (hash the presented token,
     look up by `token_hash`, return the `User` or `None`). No HTTP here.

Conventions: forward-only `NNNN_description.sql`; frozen/immutable types; every
parameter typed; `snake_case` columns, kebab-case role values; stdlib
(`hashlib`, `hmac`, `secrets`) over hand-rolled; return tuples not lists.

## Acceptance criteria
- [ ] `0002_users.sql`, applied via the existing `Migrator`, creates `users`
      with columns `name` (PK), `role`, `token_hash` (UNIQUE), `created_at`,
      and a CHECK constraint limiting `role` to reader/writer/admin.
- [ ] `generate_token()` returns a distinct high-entropy string each call;
      `hash_token` is deterministic SHA-256 hex and never returns the input;
      `verify_token` returns True only for the matching token and uses a
      constant-time compare (`hmac.compare_digest`, verified by test/inspection).
- [ ] `create_user` returns the raw token exactly once and persists only its
      hash; the token/hash never appears in `User`, `get_user`, or `list_users`.
- [ ] `authenticate` returns the correct `User` for a valid token and `None`
      for an unknown or malformed token.
- [ ] `create_user` with a role outside the allowed set is rejected before any
      row is written.
- [ ] `User` is frozen with typed fields; `delete_user` returns whether a row
      was removed.
- [ ] Regression-grade unit tests cover the table shape + CHECK, token
      determinism/difference/constant-time verify, full CRUD, `authenticate`
      hit/miss, invalid-role rejection, and the token-never-leaks guarantee.
- [ ] `ruff format`, `ruff check --fix`, `pytest` all clean; work committed.

## Out of scope
- Any HTTP route (`GET/POST /users`, `DELETE /users/<name>`) — that plus the
  Bearer middleware is #006.
- Bootstrapping an admin token on an empty table at startup — that is #007.
- Password login, token expiry/rotation, or per-user rate limiting.

## Review log
- 2026-08-15 PO: authored and moved to todo. First ticket of the T4 auth slice;
  storage + pure functions only so it lands testable without server wiring.
- 2026-08-15 dev: picked up (dep 002 in done/), moved to in-progress.
- 2026-08-15 dev: implemented. Migration `0002_users.sql` (users: name PK, role
  NOT NULL with CHECK in reader/writer/admin, token_hash NOT NULL UNIQUE,
  created_at NOT NULL). `src/hrono/crypto/tokens.py`: `generate_token`
  (secrets.token_urlsafe(32)), `hash_token` (SHA-256 hex, mirrors
  keys.fingerprint), `verify_token` (hmac.compare_digest, never ==).
  `src/hrono/auth/users.py`: frozen `User(name, role, created_at)` (no token/hash
  field), `ROLES` frozenset, and pure sqlite CRUD `create_user` (validates role
  before writing, returns User + raw token once, persists only the hash),
  `get_user`, `list_users` (sorted tuple), `delete_user` (bool), `authenticate`
  (hash-and-lookup, None on miss/malformed). Tests: `tests/auth/test_users.py`
  (table shape + CHECK, token_hash UNIQUE, token-once/hash-only, no token leak in
  reads, CRUD, authenticate hit/miss, invalid-role rejection with no write,
  frozen model) and `tests/crypto/test_tokens.py` (distinct high-entropy,
  deterministic SHA-256 hex, never-returns-input, verify true-only-on-match,
  constant-time compare guarded by spying hmac.compare_digest). Gate clean (ruff
  format, ruff check --fix, pytest 68 passed). Verified against a real migrated
  DB: users table present, create returns a 43-char token stored only as its hash
  (raw absent), authenticate hit/miss, invalid role rejected with no row,
  delete True-then-False. Committed 7d48656. Moved to verifying for qa.
- 2026-08-15 qa: PASS -> po-review. Verified all dimensions. Drove the full
  flow against a real migrated DB: `users` has exactly {name PK, role,
  token_hash, created_at}; the `role` CHECK constraint is present and limited
  to reader/writer/admin (rejects `superuser` at the SQL layer);
  `token_hash` UNIQUE. `create_user` returns the raw token once (43-char
  urlsafe) and persists only its SHA-256 hash — confirmed at the byte level
  that the raw token never appears in the DB file, and it is absent from
  `User`, `get_user`, and the repr. `authenticate` returns the right user on a
  valid token and None on unknown/empty. Invalid role is rejected
  (`InvalidRole`) before any write (table stays empty). Edge: duplicate name
  raises `sqlite3.IntegrityError` on the PK and does not overwrite the existing
  row. `list_users` returns a name-sorted tuple; `delete_user` returns
  True-then-False. Security (engineering:security lens): one-way SHA-256 token
  hash with `hmac.compare_digest` constant-time verify — the correct primitive
  for high-entropy tokens, not a password KDF as the ticket directs; all SQL
  parameterized (no injection); roles enforced by CHECK + the `ROLES` frozenset;
  no secret in logs; `authenticate`'s indexed hash-equality lookup carries no
  usable timing channel (attacker cannot control the stored hash without
  breaking SHA-256). Tests are regression-grade and cover every criterion,
  including a spy asserting `hmac.compare_digest` is actually used. Code review
  clean: frozen/typed model, tuples not lists, early-return role check, stdlib
  only, docstrings only (no stray inline comments), no emojis, no HTTP surface
  (correctly out of scope). Commit 7d48656 is a proper atomic Conventional
  Commit (feat, one sentence, no body/attribution), no stray changes. Re-ran
  the gate myself: ruff format clean (31 files), ruff check passed, pytest 68
  passed.
- 2026-08-15 PO: PASS -> done. Re-verified against the code and a real migrated
  DB, not just the logs: `0002_users.sql` = {name PK, role NOT NULL CHECK in
  reader/writer/admin, token_hash NOT NULL UNIQUE, created_at NOT NULL};
  `verify_token` uses `hmac.compare_digest`; `create_user` validates role before
  any write and returns the raw token once. Drove it: 43-char token, raw token
  absent from the DB file at rest, `authenticate` returns the user on a valid
  token and None on unknown/empty, `User` has no token/hash field, invalid role
  rejected with no row written, `delete_user` True-then-False. Ran the gate
  myself: ruff format (31 clean), ruff check clean, pytest 68 passed. Product
  bar met: only one-way hashes persisted, correct primitive for high-entropy
  tokens. Closed at 7d48656. Spun off one adjacent refinement into #006:
  duplicate-name create currently raises a raw sqlite3.IntegrityError, which the
  POST /users route must map to a clean 409, not a 500/traceback.
