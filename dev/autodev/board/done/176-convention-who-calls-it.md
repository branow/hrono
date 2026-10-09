---
id: 176
title: convention — a test that constructs the state proves the reader, not the writer
priority: medium
size: small
depends_on: [170, 171, 175]
spec_refs: []
---

## Context
Authored by the PO after #175, as the fourth instance of one shape.

`CONTRIBUTING.md` already carries the SEAM rule (a seam proves the wiring, not
the backend's contract) and its real-SIZE extension. This is the same family
seen from the other end, and it has now cost four tickets:

- **#094/#108** — 585 green tests over a corpus that could not build, because
  every affected path was covered only through its seam.
- **#163** — the orphan sweep could have run `range(1)` for its whole life: the
  collector's own tests called `attach_orphans(level=1)` directly, so they
  proved the FUNCTION and nothing proved its caller.
- **#175** — `jobs.scope.fan_out` was called from tests only. Its tests passed.
  No request could reach it, so #172 shipped an aggregation over a structure
  the product could not produce.
- **#172** — every test of the aggregation planted the parent with
  `store.create_fanout`, which is why the above went unnoticed for one more
  ticket.

## What to write down
A bullet in `CONTRIBUTING.md`, beside the seam rules, in their voice:

> A test that CONSTRUCTS the state it asserts on proves the reader and says
> nothing about the writer. At least one test per feature must arrive at that
> state the way production does — through the endpoint, the op, the CLI — or
> the thing that builds it can be dead and every test stays green (#094, #163,
> #172, #175).

## Acceptance criteria
- [x] `CONTRIBUTING.md` carries it, with the four citations.
- [x] It says what to DO (one test that arrives the production way), not only
      what is wrong.
- [x] `ruff format`, `ruff check --fix`, `pytest` clean.

## Review log
- 2026-09-26 po: authored from #175, as the fourth instance.

- 2026-09-26 dev: done, commit 271f50c. One bullet beside the seam rules, in
  their voice, with all four citations — and it leads with what to DO ("at
  least one test per feature must arrive at that state the way production
  does") rather than only naming the mistake, because a rule you can act on
  survives longer than one you can only fail.

  `CLAUDE.md`'s pointer updated to name it, so the summary stays accurate.
  Eleven citations in `CONTRIBUTING.md` now, none lost.

  It landed in a committed file, which #171 is what made possible five tickets
  ago. This is the first convention that could not have been written down
  usefully before that.

  Gate clean: 1207 passed. Nothing under `src/`.

- 2026-09-26 qa: PASS, to po-review. Verified the bullet against the four
  tickets it cites — each claim is in the ticket named, with the right ticket
  against it — and confirmed the eleven citations in `CONTRIBUTING.md` all
  survive, so nothing was lost moving it in.

  Checked it in a fresh clone the way I did for #171: the bullet arrives.

  The wording is right where it counts. "Proves the READER and says nothing
  about the WRITER" is the sentence that would have caught #175, and it is
  short enough that someone will remember it at the moment they are writing
  the convenient fixture.

- 2026-09-26 po: CLOSED. Four tickets paid for that sentence; it now costs the
  next person nothing.

  Worth noting what this depended on. #170 wrote the real-SIZE convention into
  a file nobody else could read, #171 moved the conventions somewhere committed,
  and #176 is the first rule that went straight into a place it will actually
  reach a reader. The three tickets are one arc, and the middle one is the one
  that was easy to skip.

  M11 continues with #173 (cancel) and #174 (SSE), both now standing on a
  fan-out that exists.
