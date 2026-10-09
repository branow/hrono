---
id: 109
title: Job errors carry a code, not a raw driver string
priority: low
size: small
depends_on: [092, 027]
spec_refs: [implementation-notes.md]
found_by: qa verification of 092 on 2026-09-14 (residual half of .e2e/FINDINGS.md F14)
---

## Context
092 mapped *busy* driver errors onto the new `Unavailable` AppError, so the
"database is locked" string F14 observed no longer reaches a job record. Every
other driver error still does: `jobs/worker.py:_execute` stores `str(exc)` for
any exception, and `jobs.error` is a bare TEXT column with no `code` or
`details`.

Reproduced during 092's verification: a `BEFORE INSERT` trigger raising
`RAISE(ABORT, 'poisoned mid-transaction')` inside the `split` op stored exactly
`poisoned mid-transaction` as the job's `error` — the sqlite driver's wording,
with nothing for a client to branch on.

## Description
Every other surface routes through the `{error:{code,message,details}}`
envelope; job records do not. Closing this means deciding whether `jobs` grows
`error_code` / `error_details` columns (a migration) or whether the error is
stored as a JSON blob, then mapping unmapped `sqlite3.Error`s onto an AppError
at the worker boundary the way `Database.connect` already does for busy errors.

## Acceptance criteria
- [ ] A job that fails on a driver error records a kebab-case `code` alongside
      a client-safe message, not the driver's wording.
- [ ] `GET /jobs` serves the same shape as the HTTP error envelope.
- [ ] `ruff format`, `ruff check --fix`, `pytest` clean.

- 2026-09-23 dev: mapped the worker boundary through a new `errors.as_app_error`
  and grew `jobs` two columns (migration 0029) rather than a JSON blob, so the
  record matches `result` (#132) and the envelope field for field. `GET /jobs`
  and `GET /jobs/{id}` both serve `{code, message, details}` through one
  `_job()`; `hrono jobs get` renders `code: message`. Legacy rows (failed before
  0029) read back with their text and a fallback `internal-error` code.

  Mutations run, each killed: `as_app_error` returning `str(error)` for a
  foreign exception; dropping its `isinstance(error, AppError)` passthrough;
  `_error` serving the bare string; dropping `_error`'s None guard; the worker
  not persisting the code.

- 2026-09-23 qa: FOUND THREE, all fixed in the same commit rather than bounced,
  since each was a defect in this ticket's own change.

  1. `worker.py:_execute` recorded the mapped error and logged NOTHING, so the
     driver's wording was not moved out of the client's reach — it was deleted.
     The docstring claimed "the original wording reaches the log", and no log
     line existed. Now `_logger.exception("job %s (%s) failed", ...)`, pinned by
     a caplog test.
  2. An unknown op became "the job failed" — the op name came from the client's
     own request and is both safe and the only useful thing to say. Now
     `BadRequest(f"unknown op: {job.op}")`, so it records `bad-request` and the
     op name.
  3. Driven live (`hrono serve` on 8131, POST /jobs op=brief), the first build
     answered `{"code": "internal-error", "message": "the job failed",
     "details": {"type": "LLMError"}}` — hiding hrono's OWN message ("no text
     model available"), which is the actionable half of every operator-facing
     failure. `as_app_error` now keeps the message of an exception raised from
     `hrono.*` and hides only FOREIGN wording, which is what the ticket asked
     ("not the driver's wording"). Both halves of that rule are mutated and
     killed. Per-domain codes stay #053's job.

  Also caught: the repro fixture was failing on `nodes.created_at NOT NULL`
  before ever reaching the poison trigger, so every "the wording is absent"
  assertion passed for the wrong reason (#125 again). Fixed, and the caplog
  test now proves the trigger fires by finding its text in the log.

  Verified: acceptance criteria met; live server + CLI (`hrono jobs list/get`)
  drive the real flow; upgrade path checked by migrating a populated pre-0029
  database with a failed job on it; one dev mutation re-run (`_error` serving
  the bare string) plus five of my own; gate clean (`ruff format`, `ruff check`,
  968 passed). Commit is atomic, subject-only, and the stray `.gitignore` line
  was split into its own `chore:` commit.

- 2026-09-23 po: CLOSED. Both criteria met and the product bar holds where it
  matters most here — actionable errors. The version qa caught first ("the job
  failed" for every failure) would have been a net LOSS for the operator: the
  ticket exists so a client gets a field to branch on, not so a human loses the
  sentence that tells them a model is missing. The shipped rule — hrono's own
  wording kept, foreign wording logged and replaced by its type — is the right
  line, and the one the ticket actually asked for.

  Adjacent work: per-domain codes (`sync-error`, `llm-error`, ...) instead of
  one `internal-error` for everything. That is #053's scope, not a new ticket;
  noted there.
