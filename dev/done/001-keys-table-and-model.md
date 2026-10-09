---
id: 001
title: keys table + key_id/fingerprint model
priority: high
size: small
depends_on: []
spec_refs: [build-order.md#T3.1, implementation-notes.md#secrets-at-rest]
---

## Context
hrono encrypts provider/source secrets at rest with a master key. Every
secret-bearing row records *which* key encrypted it, so a wrong or rotated key
yields a clear per-record error instead of a silent failure. This ticket lays
the first piece of "secrets at rest": the `keys` registry (fingerprints only,
never the key itself) plus the in-code key model and the fingerprint function.
It unblocks master-key startup load (#003) and the Fernet cipher (#004). It is
deliberately small — one migration plus one pure module — and is the
recommended first ticket of this cycle.

## Description
Two changes, no server wiring:

1. **Migration.** Add a forward-only migration file
   `src/hrono/db/migrations/0001_keys.sql` (the existing runner discovers
   `NNNN_description.sql` files; `0001` is free — no `.sql` exists yet) creating
   table `keys`:
   - `key_id INTEGER PRIMARY KEY` — the identity a secret row references; the
     active key is the latest one.
   - `key_hash TEXT NOT NULL UNIQUE` — the master key's fingerprint (SHA-256 hex
     of the raw key bytes). This is a fingerprint, never the key.
   - `created_at TEXT NOT NULL` — ISO-8601 UTC timestamp.

2. **Model + fingerprint.** Add a domain model and a pure fingerprint function
   in a new module. Recommend `src/hrono/crypto/keys.py` — do **not** name the
   package `secrets`, it shadows the stdlib `secrets` module.
   - a frozen dataclass `KeyRecord(key_id: int, fingerprint: str, created_at: str)`.
   - `fingerprint(key: bytes) -> str` returning the SHA-256 hex digest of the key
     bytes: deterministic and non-reversible.

No encryption, no key loading from file/env, no DB reconciliation — those are
#003 and #004. No raw key or secret plaintext ever touches this table or model.

Conventions: forward-only migration named `NNNN_description.sql`; frozen/
immutable types; every parameter typed; `snake_case` columns; standard libs
(`hashlib`) over hand-rolled.

## Acceptance criteria
- [ ] `0001_keys.sql`, applied via the existing `Migrator`, creates a `keys`
      table with columns `key_id`, `key_hash`, `created_at` and a UNIQUE
      constraint on `key_hash`.
- [ ] `fingerprint(key)` returns a stable SHA-256 hex string: same input yields
      the same output, different inputs yield different outputs, and the raw key
      is not recoverable from it.
- [ ] `KeyRecord` is immutable (frozen) with typed fields `key_id: int`,
      `fingerprint: str`, `created_at: str`.
- [ ] The new module is not named `secrets` (no stdlib shadow).
- [ ] Unit tests cover the migration creating the table shape and the
      fingerprint function's determinism and difference; a test fails if the
      table shape or fingerprint behavior regresses.
- [ ] `ruff format`, `ruff check --fix`, and `pytest` are all clean; work is
      committed.

## Out of scope
- Loading the master key from `--key-file`/`HRONO_MASTER_KEY` (that is #003).
- Encrypt/decrypt of secrets (that is #004).
- Inserting or verifying key rows at startup (that is #003).
- Key rotation / `rotate-key` (that is T59, far later).

## Review log
- 2026-08-15 PO: authored and moved to todo. Recommended first ticket of the
  cycle — small, self-contained (migration + pure model), no external services.
- 2026-08-15 dev: picked up, moved to in-progress.
- 2026-08-15 dev: implemented `0001_keys.sql` (keys table: key_id PK,
  key_hash TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL) and
  `src/hrono/crypto/keys.py` (frozen `KeyRecord`, pure `fingerprint()` via
  hashlib SHA-256 hex). Package named `crypto`, not `secrets`, to avoid the
  stdlib shadow. Tests: `tests/db/test_keys_migration.py` asserts the table
  shape and UNIQUE(key_hash) via the real Migrator+discover on the real
  migration file; `tests/crypto/test_keys.py` covers fingerprint determinism,
  difference, hex shape, non-reversibility, and KeyRecord immutability. Gate
  clean (ruff format, ruff check --fix, pytest 28 passed). Also drove the real
  flow manually: applied the migration to a fresh DB, confirmed the schema, and
  round-tripped a fingerprint row into a KeyRecord. Committed 6c610b4. Moved to
  verifying for qa.
- 2026-08-15 qa: PASS -> po-review. Verified all dimensions. Acceptance:
  drove the real flow with the actual Migrator+discover on a fresh DB — 0001
  applies as version 1, `keys` has exactly {key_id PK, key_hash TEXT NOT NULL,
  created_at TEXT NOT NULL}, UNIQUE(key_hash) confirmed via
  sqlite_autoindex + IntegrityError on duplicate, and re-apply is a no-op
  (forward-only tracking). `fingerprint()` confirmed deterministic, distinct
  per input, 64-char SHA-256 hex, non-reversible; round-tripped a real
  fingerprint row into `KeyRecord`. `KeyRecord` frozen and typed; module is
  `crypto`, not `secrets` (no stdlib shadow). Tests are regression-grade
  (assert exact column shape/PK/notnull, UNIQUE, fingerprint determinism/
  difference/hex/non-reveal, frozen). Code review clean: frozen/typed,
  stdlib `hashlib`, docstrings only (no stray inline comments), no emojis.
  Security: only fingerprints persisted, one-way, no key material in code or
  table; no role/input surface in scope. Commit 6c610b4 is a proper atomic
  Conventional Commit (feat, one sentence, no body/attribution), no stray
  changes. Re-ran the gate myself: ruff format clean (20 files), ruff check
  passed, pytest 28 passed.
- 2026-08-15 PO: PASS -> done. Independently re-verified every acceptance
  criterion against the code, not just the logs: `0001_keys.sql` creates
  `keys(key_id PK, key_hash TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL)`;
  `fingerprint()` is pure hashlib SHA-256 hex (deterministic, one-way);
  `KeyRecord` is frozen + typed; package is `crypto`, not `secrets`. Ran the
  gate myself: ruff format (20 files clean), ruff check (clean), pytest 28
  passed. Regression-grade tests present for both table shape and fingerprint
  behavior. Committed atomically (6c610b4). Product bar met: only fingerprints
  persisted, no key material anywhere. No adjacent work spun off. Closed.
