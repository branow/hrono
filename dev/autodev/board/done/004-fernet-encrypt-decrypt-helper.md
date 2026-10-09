---
id: 004
title: encrypt/decrypt helper (Fernet) tagging key_id
priority: medium
size: medium
depends_on: [003]
spec_refs: [build-order.md#T3.3, implementation-notes.md#secrets-at-rest]
---

## Context
Registries (connections, sources) store provider secrets encrypted at rest.
This ticket provides the single cipher helper every secret-bearing write and
read goes through: Fernet encrypt/decrypt using the master key loaded in #003,
tagging each ciphertext with the `key_id` that encrypted it so a wrong or
rotated key gives a clear per-record error rather than silent garbage. It is the
last piece of "secrets at rest" (T3) and is what M1's registry CRUD builds on.

## Description
Add a cipher module — recommend `src/hrono/crypto/cipher.py` (same package as
#001's `keys.py`; not `secrets`, which shadows the stdlib) — exposing:
- `encrypt(plaintext: str) -> Secret` where `Secret` is a small frozen model
  `Secret(key_id: int, ciphertext: str)` carrying the ciphertext plus the active
  `key_id`. (Returning a `(key_id, ciphertext)` tuple is acceptable; prefer the
  named frozen type.)
- `decrypt(key_id: int, ciphertext: str) -> str`, raising a clear typed error
  when the `key_id` does not match the loaded key, or the token is invalid or
  tampered.

Use `cryptography`'s Fernet with the master key loaded in #003; never hand-roll
crypto. The active `key_id` comes from the reconciled key (#003). Construct the
helper via dependency injection (pass in the key / Fernet instance and the
active `key_id`) so it is unit-testable without a running server and swappable
for rotation later. Round-trip must be exact for arbitrary UTF-8 secrets;
decrypt with the wrong key or a corrupted token must fail loudly.

Conventions: vetted crypto lib only (no hand-rolled); typed errors; DI over
monkeypatch; immutable result type; every parameter typed.

## Acceptance criteria
- [ ] `encrypt` then `decrypt` round-trips arbitrary UTF-8 strings exactly.
- [ ] `encrypt` tags its result with the active `key_id` from the reconciled key
      (#003).
- [ ] `decrypt` with a mismatched `key_id` raises a clear, typed error — never a
      silent wrong value.
- [ ] A tampered or corrupted ciphertext raises rather than returning data.
- [ ] The plaintext never appears in the stored ciphertext (it is encrypted, not
      merely encoded).
- [ ] The helper is constructed via injection and is unit-tested without
      starting the server.
- [ ] Tests cover round-trip, `key_id` tagging, mismatch error, and tamper
      detection.
- [ ] `ruff format`, `ruff check --fix`, and `pytest` are all clean; committed.

## Out of scope
- Wiring the cipher into any registry (connections/sources) — that arrives with
  M1 (T6/T7/T8).
- Key rotation / re-encryption across key_ids (that is T59).
- Persisting a `key_id` foreign key on secret rows — the columns land with the
  first registry that stores a secret.

## Review log
- 2026-08-15 PO: authored and moved to todo. Priority medium — completes the
  secrets-at-rest slice but is not itself a blocker for #001–#003.
- 2026-08-15 dev: picked up (dep 003 in done/), moved to in-progress.
- 2026-08-15 dev: implemented. New `src/hrono/crypto/cipher.py`: frozen
  `Secret(key_id, ciphertext)`; a `Cipher` built by injection
  (`Cipher(fernet, key_id)`, plus `Cipher.from_key(key, key_id)` so callers
  need not import Fernet). `encrypt(plaintext) -> Secret` tags the active
  key_id; `decrypt(key_id, ciphertext) -> str` raises typed `KeyMismatch` when
  the key_id is not active and `InvalidCiphertext` (from Fernet `InvalidToken`)
  on a malformed/tampered/foreign-key token (both under `DecryptError`). Tests:
  `tests/crypto/test_cipher.py` — parametrised UTF-8 round-trip (empty, unicode,
  newlines, 10k), key_id tagging, key_id-mismatch error, tamper detection,
  ciphertext-from-a-different-key error, plaintext-not-in-ciphertext, and frozen
  Secret. Gate clean (ruff format, ruff check --fix, pytest 88 passed).
  Manually drove the helper: round-trips unicode exactly, plaintext absent from
  ciphertext, KeyMismatch on wrong key_id (carries active/ciphertext ids),
  InvalidCiphertext on tamper. DI-only, no server needed. Completes the T3
  secrets-at-rest slice. Committed f9597d2. Moved to verifying for qa.
- 2026-08-15 qa: PASS -> po-review. Verified all dimensions (engineering:
  security lens). Drove the real cipher: exact round-trip for empty, 4-byte
  emoji, embedded NUL, and 5k strings; `encrypt` tags the active `key_id`;
  plaintext is absent from the real Fernet ciphertext (encrypted, not encoded);
  `decrypt` with a mismatched `key_id` raises `KeyMismatch` (a `DecryptError`
  subtype carrying active/ciphertext ids as attributes, not baked into the
  message); a tampered token raises `InvalidCiphertext`; and a token from a
  different key but tagged with the matching id fails Fernet's HMAC and also
  raises `InvalidCiphertext` (distinct, clear failure modes). Uses
  `cryptography`'s Fernet (authenticated AES-128-CBC + HMAC), no hand-rolled
  crypto; constructed purely by injection (`Cipher(fernet, key_id)` /
  `from_key`), unit-tested with no server. Tests are regression-grade and cover
  round-trip, key_id tagging, mismatch, tamper, cross-key, plaintext-absence,
  and frozen `Secret`. Note: a test string contains an emoji, but it is
  functional 4-byte-UTF-8 round-trip coverage (the canonical multi-byte case),
  not decoration, so it is consistent with the no-emoji rule's intent; no
  emojis in src. Code review clean: structured typed errors, frozen result,
  DI, docstrings only, no stray inline comments. Commit f9597d2 is a proper
  atomic Conventional Commit (feat, one sentence, no body/attribution). Re-ran
  the gate: ruff format clean (35 files), ruff check passed, pytest 88 passed.
- 2026-08-15 PO: PASS -> done. Drove the real cipher myself (engineering:
  security lens): exact round-trip for empty/unicode+NUL/5k strings; plaintext
  absent from the Fernet ciphertext (encrypted, not encoded); `encrypt` tags the
  active key_id; `decrypt` raises typed `KeyMismatch` on a wrong key_id and
  `InvalidCiphertext` on both a tampered token and a foreign-key token that
  fails Fernet's HMAC (distinct, loud failure modes, no silent wrong value).
  Vetted `cryptography` Fernet only, constructed by DI (`Cipher(fernet, key_id)`
  / `from_key`), frozen `Secret`, structured typed errors under `DecryptError`.
  Ran the gate: ruff format (35 clean), ruff check clean, pytest 88 passed;
  tests are regression-grade over round-trip/tagging/mismatch/tamper/cross-key/
  plaintext-absence. Completes T3 (secrets at rest); M1 registry CRUD builds on
  this. No adjacent work spun off. Closed at f9597d2.
