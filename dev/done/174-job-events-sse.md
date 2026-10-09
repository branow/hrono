---
id: 174
title: watch a job's progress live, over SSE
priority: medium
size: medium
depends_on: [172]
spec_refs: [build-order.md#T57.3, implementation-notes.md]
---

## Context
`GET /jobs/<id>/events` — "live progress via SSE (text/event-stream); one-way,
so SSE not WebSocket". The spec chose the transport and said why; this
implements it.

It is also what M10's jobs view (T53) is built on, which is why it is worth
doing before the dashboard rather than inside it.

## Description
- `text/event-stream`, emitting the job's state as it changes: status
  transitions and #172's progress.
- One-way by design. Nothing the client sends matters, so the complexity of a
  socket buys nothing.
- Ends when the job reaches a terminal state, so a client that waits for the
  stream to close has waited for the job.
- `hrono jobs watch <id>` consumes it (spec line 351).

## Acceptance criteria
- [x] A client connected to a running job receives its transitions and its
      final state, then the stream ends.
- [x] A job already finished gets its final state and an immediate close, not
      a hang.
- [x] An unknown id is a 404 before any stream starts.
- [x] The stream does not hold the single writer or a database connection open
      for its lifetime (#092, #008).
- [x] `hrono jobs watch <id>` prints progress and exits when the job ends.
- [x] `ruff format`, `ruff check --fix`, `pytest` clean.

## Review log
- 2026-09-26 po: authored.

- 2026-09-26 dev: done, commit 2a200f7. `GET /jobs/<id>/events` emits
  `event: state` frames on every change and ends when the job does; the CLI
  consumes it as `hrono jobs watch <id>`.

  It POLLS and holds no connection between polls. A watcher that kept one open
  would hold the shared lock for as long as somebody left a terminal window
  open (#008, #092) — a way to wedge the server by being interested in it. The
  read goes through `run_in_threadpool`, so a slow read does not stall the
  event loop either.

  The client needed a `stream` method of its own: `_request` decodes a whole
  body, and a stream has no whole body until the job finishes. No read timeout
  on it — a watch is meant to sit there, and the 10s that suits registry CRUD
  would end it mid-job. That is #168's lesson applied one endpoint over rather
  than re-learned.

  **Driving it found something the tests would not have.** The stream ended at
  `failed 1/2` — a parent's status goes terminal the MOMENT one child fails,
  which is right for a GET (#172: the outcome is decided) and wrong for a
  watch, because the other stage was still writing and anyone acting on that
  close acts on a database still being changed. `is_terminal` now also waits
  for the children. Same final status, but "the stream ends when the job does"
  is true. Re-driven:

      before: running 0/2 -> failed 1/2   (stream closed, a stage still going)
      after:  running 0/2 -> failed 2/2

  Mutations, all killed: the stream never ending -> the suite HANGS, which is
  the defect stated precisely; emitting nothing -> 3 fail; no progress in the
  frames -> 2; an unknown id opening an empty stream -> 1; ending the watch
  while a stage runs -> 1.

  Gate clean: 1223 passed, 2 skipped.

- 2026-09-26 qa: PASS, to po-review. Gate at 2a200f7: ruff clean, 1223 passed.

  **Verified the AC nobody can verify by reading: the stream holds no lock.**
  With a watcher connected to a live server I issued a read and a WRITE
  alongside it:

      GET /jobs             200 in 0.0026s
      PUT /trees/watchtest  200 in 0.024s

  A watcher that held the shared connection would have blocked the write, and
  the write is the one that matters — the single writer is the resource. That
  is the criterion that would have been quietly untrue if the stream had taken
  a connection for its lifetime, and no unit test would have noticed.

  Re-ran dev's H1 (the stream never ending): the suite HANGS, which is the
  clearest possible statement of that defect and worth keeping as-is.

  **The find of this ticket is dev's, and it came from driving.** `failed 1/2`
  with a stage still writing is a correct status and a wrong moment to close a
  watch. Nothing in the acceptance criteria said so; "the stream ends when the
  job does" only looks ambiguous once you have watched it end early. The fix
  keeps the status identical and moves only the moment, which is the smallest
  thing that makes the sentence true.

  T57 is complete: a parent that reports, a cancel that stops what it can, and
  a watch that ends when the work does.

- 2026-09-26 po: CLOSED. **T57 is done**, and M10's jobs view (T53) now has the
  endpoint it was always going to need.

  The pattern across these three tickets is worth naming: each one's real
  finding came from DRIVING it, not from the tests. #172's aggregation was
  dormant (found by grep while implementing), #173's honest "1 stage is still
  running" came from watching a cancel land mid-run, and #174's early close
  came from watching a stream end. The suites were green throughout and each
  time they were green about the right thing and silent about the interesting
  one.

  That is the convention from #170 and #176 earning its place twice over in one
  milestone. I am not writing a third rule; the two we have say it.

  M11 has T58 (shared-resource dry-run) and T59 (rotate-key) left. Both are
  self-contained and neither needs the dashboard.
