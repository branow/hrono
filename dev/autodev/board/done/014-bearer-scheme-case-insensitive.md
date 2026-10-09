---
id: 014
title: Bearer auth scheme match is case-insensitive (RFC 7235)
priority: low
size: small
depends_on: [006]
spec_refs: [implementation-notes.md#auth]
---

## Context
Spun off from #006 PO review (qa non-blocking find). `_bearer_token` in
`src/hrono/server/auth.py` compares the auth scheme with `scheme != "Bearer"`,
which is case-sensitive, so `Authorization: bearer <token>` (lowercase) is
rejected with 401. Per RFC 7235 the auth-scheme token is case-insensitive, so a
spec-conformant client using `bearer`/`BEARER` should authenticate. Today our
own CLI (#010) and the future dashboard control their own header and send
`Bearer`, and the current behavior fails closed (safe), so this is low priority
— but the moment a third-party or non-first-party client hits the API it is a
real interop bug. Cheap to make correct.

## Description
Make the scheme comparison case-insensitive in `_bearer_token`: match the scheme
ignoring case (e.g. compare `scheme.lower() == "bearer"`), leaving the token
value itself untouched (tokens stay case-sensitive). No other behavior changes —
missing header, empty token, and unknown token must still yield the same opaque
401. Keep it a one-line-ish, well-tested change.

## Acceptance criteria
- [ ] `Authorization: bearer <valid-token>` and `Authorization: BEARER
      <valid-token>` authenticate exactly like `Bearer <valid-token>`.
- [ ] The token value remains case-sensitive (a token differing only in case
      does NOT authenticate).
- [ ] Missing header, empty token, and unknown token still return the same
      opaque 401 as before (no regression to the #006 matrix).
- [ ] A regression test covers the mixed-case scheme accept and the
      case-sensitive-token reject.
- [ ] `ruff format`, `ruff check --fix`, `pytest` all clean; work committed.

## Out of scope
- Any change to token generation/hashing or the 401/403 model.
- Supporting auth schemes other than Bearer.

## Review log
- 2026-08-15 PO: authored from #006 review (qa RFC-7235 nit). Low/small; fails
  closed today so not urgent, but correct scheme matching matters once
  non-first-party clients hit the API.

## Review log (PO routing correction) — 2026-08-16
- PO: this ticket's implementation was committed but the ticket file was left in
  todo/ (the committed code matches the ticket exactly; the gate at HEAD passes).
  Routing it to verifying/ so qa verifies it properly - NOT closing it here (it
  must still pass qa + PO review). Recurring hygiene: commit AND route the ticket
  (todo->in-progress->verifying) together; do not leave a committed ticket
  stranded in todo.

## qa — 2026-08-16

PASS -> po-review. Verified; closes the #006 RFC-7235 observation. The fix is the
minimal one-liner (`scheme != "Bearer"` -> `scheme.lower() != "bearer"` in
`_bearer_token`), token value untouched. Drove the real server: `Bearer`,
`bearer`, `BEARER`, and `BeArEr` all authenticate (200); the token stays
case-sensitive (swapcased token -> 401); and the opaque-401 matrix is unchanged
(no header / `Basic` / empty `bearer ` / unknown token all -> 401), so no
regression to the #006 auth behavior. Tests are regression-grade
(`test_bearer_scheme_is_case_insensitive` over bearer/BEARER/BeArEr,
`test_token_value_stays_case_sensitive` via swapcase). Tree was clean and the
commit isolated. Commit e7acee9 is a proper atomic Conventional Commit (`fix:`),
no emojis. Re-ran the gate: ruff format clean (114 files), ruff check passed,
pytest 317 passed.
- 2026-08-16 PO: PASS -> done. Minimal correct fix (`scheme.lower() != "bearer"`,
  token untouched). Drove the live server: `Bearer`/`bearer`/`BEARER`/`BeArEr` +
  token all authenticate (200); a case-swapped token -> 401 (token stays
  case-sensitive); no-header and `Basic` -> 401 (opaque-401 matrix unregressed).
  The empty-`bearer ` and unknown-token paths are correct by inspection
  (empty token -> `not token.strip()` -> None -> 401; unknown -> authenticate
  None -> 401) and covered by qa's TestClient regression tests; my live probe of
  `bearer ` tripped httpx's client-side "illegal header value" (never reached the
  server - a harness artifact, not the product). Gate at HEAD: ruff format/check
  clean, pytest 317 passed. Closes the #006 RFC-7235 observation. Closed at
  e7acee9.
