---
id: 161
title: a DomainError reaches the client as internal-error, losing the code #145 gave it
priority: medium
size: small
depends_on: [145]
spec_refs: [implementation-notes.md]
---

## Context
Filed by dev while working #159, out of its scope.

#145 gave every domain failure its own kebab-case `code` — `embed-error`,
`cluster-error`, `sync-error` — so a boundary could tell "hrono failed, and
this is which failure" from "something threw". The HTTP boundary cannot: only
`AppError` is registered as a handled type (`src/hrono/server/errors.py:36`),
and `DomainError` is not one of its subclasses, so every domain failure falls
into `_handle_unexpected` and renders the generic `_INTERNAL` envelope.

Observed on a real server (`hrono serve`, no embedding model registered),
driving `POST /trees/default/nodes/<id>/split`:

    {"error":{"code":"internal-error","message":"internal error"}}   [500]

while the log line underneath it reads
`hrono.embed.runner.EmbedError: no embedding model available`. The operator is
told nothing; the one word that would have told them what to do —
`embed-error`, "no embedding model available" — reached the log and not them.

## Why it matters
Every endpoint that resolves an embedding model or drives a cluster op can
raise one of these: `split`, `dissolve`, `recall`, the ops behind `POST /jobs`.
A missing or misconfigured model is an OPERATOR error with a one-line fix, and
today it is indistinguishable from a crash — which is also what it looks like
in a bug report.

## Question for the PO
#145 decided deliberately that these "stay 500" and invented no new HTTP
statuses. That decision is about the STATUS; this ticket is about the CODE and
MESSAGE, which #145's own acceptance criteria ask to be preserved. Two ways:

- keep 500 but render the domain error's own `code` and message (smallest
  change: register `DomainError` on the boundary beside `AppError`), or
- rule that a missing model is a 409/422 CONFIGURATION error, which reopens
  what #145 settled.

The first is a faithful reading of #145. The second is a better answer for this
particular failure and a bigger conversation.

## Out of scope
Changing which failures are 5xx vs 4xx across the board — that is the PO's
call, and it wants its own ticket.

- 2026-09-25 dev: picked up.

## Acceptance criteria
- [x] A `DomainError` raised from a route renders its own `code` and message.
- [x] The status stays 500, per #145.
- [x] An `AppError` is unchanged; a FOREIGN exception still says nothing.
- [x] `ruff format`, `ruff check --fix`, `pytest` clean.

- 2026-09-25 dev: done, commit 85bc8c9. The fix is one registered handler, and
  the reason it is that small is that the conversion already existed:
  `errors.as_app_error` is what #109 settled for the JOB door. Reusing it means
  `hrono jobs get` and an HTTP call now describe one failure the same way,
  rather than the same `EmbedError` reading as `embed-error` in a job record
  and `internal-error` over HTTP. Writing a second conversion here would have
  been the defect in a new place.

  The PO's first option ("register `DomainError` beside `AppError`") was the
  right one and needed no new envelope, no new status, and no decision about
  4xx-vs-5xx — which is what kept the second option out of scope.

  Driven on a real server, the exact case from the ticket — `dissolve` on a
  database with no embedding model registered:

      before: {"code":"internal-error","message":"internal error"}          500
      after:  {"code":"embed-error","message":"no embedding model available",
               "details":{"type":"EmbedError"}}                             500

  On exposure, since this widens what a client is told: nothing new is exposed.
  `as_app_error` already sends exactly these strings to the same operators
  through `hrono jobs get`, and the rule it encodes is unchanged — hrono's own
  wording is written for a reader and kept, a FOREIGN library's is dropped and
  reaches the log instead. A test drives a `RuntimeError` mentioning sqlite and
  asserts the client sees none of it.

  One correction worth keeping rather than quietly fixing: I wrote a test
  asserting `TooFewPoints` answers as `cluster-error`, its family. It does not,
  and it should not — it declares `too-few-points` deliberately, because it is
  the one clustering failure that is not a failure and a caller may answer it
  by collecting (#094, #112). The test now asserts the real contract and says
  why, because the distinction is exactly what a client would otherwise have
  to guess at.

  Mutations, both killed: the handler unregistered (the original defect) -> 5
  fail; the handler dropping the code and answering `internal error` -> 4 fail.

  Gate clean: 1155 passed, 2 skipped.

- 2026-09-25 qa: PASS, to po-review. Gate re-run at 85bc8c9: ruff clean, 1155
  passed, 2 skipped. Re-ran dev's Y2 (the handler dropping the code) — 5 fail.

  I measured the thing the ticket is actually for, which is what an operator
  reads. Same command, same server with no embedding model registered, with and
  without the handler:

      with:    $ hrono recall default "anything at all"
               no embedding model available
      without: $ hrono recall default "anything at all"
               internal error

  One line versus the other is the entire ticket, and it reaches the CLI with no
  change to the client — the envelope already carried the message and the client
  already rendered it; there was simply never anything but "internal error" in
  it.

  **Security, checked rather than assumed.** This widens who reads a domain
  message, so I looked for anything that must not travel. Nothing does, and it
  is deliberate rather than lucky: `ingest/api.py` raises
  `SyncError(f"cannot reach the provider: {type(exc).__name__}")` with the
  comment "the type, never the text: a url with userinfo in it would otherwise
  reach a job record through the message (#109)". No `SyncError` interpolates a
  URL, token or credential anywhere in `ingest/`. The rule that protected the
  job door already protects this one, because it is the same conversion.

  Ran one dev did not: route EVERY exception through the new domain handler, to
  check the foreign-exception guard is doing its own work and not riding on
  handler ordering. The test fails, so it is. Worth one note for later — under
  that mutation the client is told "the job failed", which is `as_app_error`'s
  JOB-door wording arriving in an HTTP response. Unreachable today, since
  foreign exceptions go to the catch-all, but if a future change ever routes
  them here the phrasing is wrong for the door.

  The `TooFewPoints` correction in dev's log is the right call: the test asserts
  the contract that exists rather than the one either of us assumed, and says
  why the distinction matters.

- 2026-09-25 po: CLOSED, first round. One registered handler, and the operator
  whose server has no embedding model is now told so instead of "internal
  error".

  The right thing happened here and it is worth naming: dev did not write a
  conversion. `as_app_error` already existed for the job door, so the fix was to
  point the HTTP boundary at it — and the result is that one failure now reads
  identically through `hrono jobs get` and through a request, which nobody asked
  for and everybody wanted. A second conversion would have passed this ticket
  and drifted from the first within two milestones.

  qa's security check is the standard I want on anything that widens what a
  client is told: not "is there a rule" but "which line of code enforces it, and
  does it cover this". The answer was a comment written for #109 that still
  holds.

  #053's mapping layer — which statuses domain failures should eventually carry
  — remains unauthored and unneeded. This ticket was never about the status.
