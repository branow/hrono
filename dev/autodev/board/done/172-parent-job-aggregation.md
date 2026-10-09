---
id: 172
title: a parent job reports nothing about the children it is waiting on
priority: medium
size: medium
depends_on: [133, 139]
spec_refs: [build-order.md#T57.1, implementation-notes.md]
---

## Context
M11 opens. `hrono tree maintain` fans out into a parent job and a child per
stage, and `GET /jobs/<id>` answers about the PARENT row alone — its own
status, its own nothing-in-particular — while the work is in the children.

The spec settled the shape already:

    { "id": "job_42", "status": "partial",
      "progress": { "done": 1180, "total": 1240 }, ... }

and `jobs/model.py` says so in its own docstring: "the parent-only `partial`
status is derived at read time (T57), never stored, so it is absent from
`JobStatus`". The type has been waiting for this ticket since M0.

## Description
- A parent's status is DERIVED from its children: `partial` when some have
  succeeded and others have not yet, and the obvious readings otherwise —
  running while any child runs, failed if any failed, canceled if canceled,
  succeeded only when all children did.
- `progress` is `{done, total}` over the children, so a caller can render a bar
  without fetching them.
- `GET /jobs/<id>/children` lists them (spec line 281).
- Derived at READ time, never stored: a stored aggregate is a second source of
  truth that drifts the moment a child changes and nobody re-aggregates.

## Acceptance criteria
- [x] A parent with mixed children reports `partial`, and `progress` counts
      them.
- [x] A parent whose children all succeeded reports `succeeded`; one failed
      child makes it `failed`.
- [x] A LEAF job's answer is unchanged — no `partial`, no invented progress.
- [x] `GET /jobs/<id>/children` returns the children, newest state.
- [x] `hrono jobs get` shows the derived status and the progress.
- [x] `ruff format`, `ruff check --fix`, `pytest` clean.

## Out of scope
Cancel (#173) and SSE (#174). Cost aggregation — the spec shows a `cost` field
and nothing records per-job tokens yet; that is its own ticket when it exists.

## Review log
- 2026-09-26 po: authored, opening M11.

- 2026-09-26 dev: done. `jobs/aggregate.py` is a pure function over the
  children's statuses — no database, so the rules are a table rather than a
  fixture each, and it cannot drift from what is stored because nothing is
  stored. `GET /jobs/<id>` derives at read time, `GET /jobs/<id>/children`
  lists them, and `hrono jobs get` prints "progress: 1 of 3 stages done".

  The ORDER of the rules is the design. A failed child fails the parent even
  while others run — the run cannot now succeed, and "running" would have an
  operator wait for an outcome already decided. Canceled outranks running and
  ranks below failed, because "it broke" is what a person needs to hear first.
  A leaf gets None rather than a zero rollup: `0 of 0` would put a progress bar
  on every single-stage job in the system.

  One test earns its place beyond the ACs:
  `test_the_parents_own_stored_row_is_not_what_is_reported` — `create_fanout`
  leaves the parent `pending` and nothing ever updates it, so a parent
  reporting its own row would say `pending` over a finished run forever. That
  is the stale second source of truth, asserted rather than described.

  A fixture note: my first version planted `pending` children in a live server
  and they came back `failed` — the WORKER had claimed and run them. The
  harness now stops the worker before planting. A test about the read surface
  should not be racing the thing that writes it.

  Mutations, all killed: a failed child no longer failing the parent -> 1;
  succeeding once ANY child has -> 4; a leaf getting a rollup -> 2; the route
  reporting the stale stored row -> 1.

  **#175 filed, high, and it is the important thing I found.** `fan_out` — the
  only function that creates a parent and its leaves — is called from TESTS
  ONLY. Nothing in `src/` calls it. Driven: `POST /jobs` with
  `{"type":"all"}` over two registered sources produced one job and no
  children. So this ticket is correct and DORMANT: it answers about a structure
  no operator can produce. I did not widen the ticket to wire it, because what
  `POST /jobs` returns and whether `maintain`'s stages become rows are design
  decisions, not a patch.

  Gate clean: 1197 passed, 2 skipped.

- 2026-09-26 qa: PASS, to po-review — with the dormancy recorded as this
  ticket's headline, not a footnote.

  Gate at 7621f84: ruff clean, 1197 passed. Re-ran two of dev's mutations and
  added two of my own: cancel no longer outranking running -> 2 fail; progress
  counting only SUCCESSES rather than everything finished -> 2 fail. The table
  is the right shape for this — ten rows, each a rule, and a mutation lands on
  the row it breaks.

  **The finding is #175 and dev found it in their own work.** The aggregation
  is correct and cannot be reached: `fan_out` is called from tests only, so no
  operator can produce a parent job, and every test here plants one with
  `store.create_fanout` directly. I confirmed the grep independently and the
  driven result — `POST /jobs {"type":"all"}` over two sources, one job, no
  children.

  I am passing rather than failing, and the reason is worth stating. The
  ticket's acceptance criteria are all about what a parent REPORTS, and every
  one is met and guarded. Wiring the producer changes what `POST /jobs` returns
  and whether `maintain`'s stages become rows — a design decision, and dev was
  right to file it rather than widen. But this feature ships DORMANT, and a
  ticket closed with "done" against dormant code is how #094 happened, so the
  word belongs in the PO's record as much as the code does.

  The fixture note is the one I would have written: planting `pending` children
  in a live server races the worker that runs them. That is now stopped
  explicitly and said why.

- 2026-09-26 po: CLOSED, and **#175 promoted to `todo` at high — it goes
  next.**

  T57.1 is done as authored: a parent's status and progress are derived, never
  stored, and the rules read as a table. `partial` has been promised in
  `jobs/model.py` since M0 and now exists.

  But qa is right to make the dormancy the headline. This is the third time
  this month the same shape has surfaced — #094's seams, #166 and #168's real
  size, and now a whole framework function whose only callers are its own
  tests. The tests were not wrong; they tested `fan_out` faithfully. Nobody
  asked who calls it.

  That is a question worth adding to the conventions once I have seen it a
  fourth time, and I suspect I will: **a test that constructs the state
  directly proves the reader and says nothing about the writer.** #163's
  surviving mutation was this. #172's whole feature is this.

  I am NOT authoring #173 (cancel) or #174 (SSE) next. Both operate on jobs a
  fan-out produces, and building two more features on an unreachable structure
  would compound exactly what #175 is about. #175 first, then they mean
  something.
