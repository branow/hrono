---
id: 177
title: rotate the master key, re-encrypting every secret under the new one
priority: medium
size: medium
depends_on: [003, 004, 015]
spec_refs: [build-order.md#T59, implementation-notes.md]
---

## Context
The last piece of M11's security surface. Every provider secret is encrypted
under one master key and tagged with its `key_id`; there is no way to change
that key without hand-editing the database.

    POST /admin/rotate-key { "old_key": "...", "new_key": "..." }

The old key is PROOF OF POSSESSION: verified against the `keys` fingerprint
before anything runs, 403 on mismatch. Without it, anyone who reaches the admin
endpoint can re-encrypt the corpus under a key they chose.

## The spec deviation, decided here
implementation-notes says this "returns a job id". **It will not, and the
reason is the job table.** A job's `scope` is persisted, so routing the
rotation through the queue writes both master keys into the database in
plaintext — the one thing this subsystem exists to prevent. The spec's reason
for a job is that rotation "touches every secret"; the secret-bearing rows are
registry config (sources, connections), which is tens of rows, not millions.

So: synchronous, inside ONE transaction, returning the new `key_id` and how
many rows moved. If the row count ever justifies a job, the job must carry a
HANDLE to keys held in memory, never the keys — and that is a different ticket.

## Description
- Verify `old_key` against the active `keys` row by fingerprint. Mismatch is a
  403 and nothing is touched.
- Validate `new_key` is a usable key before writing anything.
- In one transaction: insert the new key's fingerprint, then for every
  secret-bearing registry row decrypt under the old key and re-encrypt under
  the new, bumping its `key_id`.
- ALL OR NOTHING. A half-rotated database cannot be read by either key: the
  server holds one cipher, and a row tagged with the other key_id raises
  `KeyMismatch`. A failure mid-way must leave every row on the old key.
- The response says what to do next — the key file still holds the old key, and
  the next restart will refuse to start until it is updated.

## Acceptance criteria
- [x] A correct old key rotates every secret; each row's `key_id` is the new
      one and its plaintext is unchanged.
- [x] A wrong old key is a 403 and nothing in the database changes.
- [x] An unusable new key is refused before anything is written.
- [x] A failure part-way leaves every row on the OLD key (driven, not argued).
- [x] Admin-only.
- [x] The response tells the operator to update the key file.
- [x] No key, old or new, reaches the database, a log line, or an error
      message.
- [x] `ruff format`, `ruff check --fix`, `pytest` clean.

## Review log
- 2026-09-26 po: authored, with the job-vs-synchronous deviation decided.

- 2026-09-26 dev: done. Driven on a real server over a real secret:

      POST /admin/rotate-key (wrong old key)  403 "the old key does not match
                                                   this database's key"
      POST /admin/rotate-key (correct)        200 {"key_id": 2, "rotated": 1}
      the row                                 now on key_id 2
      the secret under the NEW key            ghp_a_real_looking_secret
      the secret under the OLD key            InvalidCiphertext
      restarting with the old key file        "wrong master key: does not
                                               match the active key"

  That last line is the protection working rather than a surprise, which is
  why the response tells the operator to update the key file before they meet
  it.

  Two mutations SURVIVED and both taught me something:

  - **skipping a row with no key_id.** My fixture gave every source a secret,
    so the guard was unexercised — and the state is ordinary, not exotic: a
    PUBLIC repo has `auth: null`, no secret, no key_id, and rotating it would
    decrypt under `int(None)`. Added a source with no auth; now kills.
  - **removing `rotate`'s own transaction.** It survived because the ROUTE's
    `database.write()` already rolls a failure back, so every test through the
    API was measuring the route's transaction and not this function's. That is
    the "property held by something else entirely" shape from CONTRIBUTING.md,
    met a week after writing it down. `rotate` is also callable directly and
    its own `with conn` is what protects that caller, so the new test calls it
    directly with a corrupt row; now kills.

  The other two killed as stated: no proof of possession -> 1 fail; an
  unusable new key not caught early -> 1.

  On the spec deviation the PO decided: no key reaches the jobs table, a log,
  or an error message, and a test greps the response body and every stored
  source row for both keys to prove it. The 403 says only that the key does not
  match — no fingerprint, nothing to work from.

  Gate clean: 1234 passed, 2 skipped.

- 2026-09-26 qa: PASS, to po-review, with one message fixed on the way through.

  Gate: ruff clean, 1235 passed. Re-ran dev's I1 (no proof of possession) and
  I4 (rotate's own transaction) — both fail. Drove the whole thing on a real
  server over a real secret and confirmed each step, including the one that
  matters most: `InvalidCiphertext` when the OLD key is pointed at a rotated
  row, and `wrong master key` when the server is restarted on the old key file.

  Security dimension, checked deliberately since this is the subsystem that
  exists for it:

  - neither key reaches the database, a log, or an error. A test greps the
    response body AND every stored source row for both keys.
  - the 403 says only that the key does not match — no fingerprint, nothing to
    work backwards from.
  - `keys` accumulates fingerprints, never key material, and `reconcile` takes
    the newest — so the old row is an audit trail rather than a second way in.
  - the fingerprint comparison is not constant-time. Not a finding: the
    attacker supplies a KEY, and exploiting the timing would mean inverting the
    hash to find one whose fingerprint prefix-matches. Recording that I looked.

  **The finding, and dev fixed it in place.** After a rotation the running
  server holds the OLD cipher while every row is on the new key, so it can
  decrypt NOTHING — a sync, any provider call, fails with `KeyMismatch`. The
  message said "this server is still running on the old one and will refuse to
  start with it", which describes the NEXT start and not the current state, and
  masked reads keep answering 200 — so an operator could carry on for some time
  before anything told them. It now says RESTART, and names what is broken
  until they do. Two tests: one on the message, one proving the blindness is
  real and that a masked read still answers, which is the trap.

  That gap was invisible to the tests and to the code; it only appears if you
  ask "what can this server do now?" — which is the question the acceptance
  criteria did not contain.

- 2026-09-26 po: CLOSED. T59 done, and the master key can be changed without
  hand-editing SQLite for the first time.

  **The deviation I decided in this ticket was right and I want the reasoning
  preserved, because the spec still says otherwise.** implementation-notes has
  this returning a job id. A job's `scope` is persisted; the inputs are two
  master keys; queueing it would write both into the database in plaintext, in
  the one subsystem whose entire purpose is that they are not. The spec's
  reason for a job — "touches every secret" — is about volume, and the
  secret-bearing rows are registry config. Synchronous is correct here and the
  ticket says why, so the next person meets an argument rather than a
  contradiction.

  If anyone ever does need the job form, the constraint is: the job carries a
  HANDLE to keys held in memory, never the keys.

  The finding qa made is the kind I most want caught. Every acceptance
  criterion was met and the operator could still have been stranded — because
  nobody asked "what can this server DO now?" between the rotation and the
  restart. Masked reads answering 200 is what makes that trap quiet.

  **M11's authored work is complete**: T57 (#172-#175), T59 (#177). T58 is
  authored and parked as #178 — its impact half is ready, its cost half needs a
  per-job token record that does not exist. That, and M10, are what remain.
