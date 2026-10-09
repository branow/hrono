---
id: 175
title: the job fan-out is unreachable — nothing in production ever creates a parent
priority: high
size: medium
depends_on: [172]
spec_refs: [implementation-notes.md, build-order.md#T57]
---

## Context
Found by dev while implementing #172 and confirmed by grep:
`jobs.scope.fan_out` — the function that creates a parent job and one leaf per
resolved item — **is called from tests only.** Nothing under `src/` calls it.

- `POST /jobs` calls `worker.enqueue`, which inserts ONE row.
- `POST /trees/<name>/maintain` and `/sync` enqueue one job each.
- `maintain` runs its stages as direct function calls with synthetic in-memory
  `Job` objects (`_stage(...)`), so a stage is never a row.

Its commit message says it "completed the jobs framework" (01f704d), and by
its own tests it works. No operator can reach it.

Driven to be sure: `POST /jobs {"op":"sync","scope":{"type":"all"}}` against a
server with two registered sources produced one job and
`GET /jobs/<id>/children` returned `[]`.

## Why this is high
#172 derives a parent's status and progress from its children, and every test
of it plants the parent with `store.create_fanout` directly — so the feature is
correct and DORMANT. It answers about a structure the product cannot produce.
That is #094/#108's shape at the framework level rather than inside one op.

It also means the spec's own job example is not reachable:

    { "id": "job_42", "op": "maintain", "status": "partial",
      "progress": { "done": 1180, "total": 1240 } }

## What it needs, and the design question in it
- `POST /jobs` with a scope that resolves to more than one item should fan out,
  and return the PARENT id. That changes what the caller gets back, which is
  why this is a ticket and not a patch.
- Decide whether `maintain`'s STAGES become job rows. The spec's `1180 of 1240`
  reads like per-unit progress rather than per-stage, so this wants a look at
  what `progress` is meant to count before anything is wired.
- Whichever way: a test that drives a REAL fan-out through the API and reads
  the parent back, not one that calls `fan_out` itself. The current tests are
  the reason nobody noticed.

## Review log
- 2026-09-26 dev: filed from #172, with the grep and the driven confirmation.

## Acceptance criteria
- [x] `POST /jobs` with a source-scoped op over all sources fans out and
      returns the PARENT id.
- [x] An explicit single source stays one job; an op that takes the whole tree
      never fans out.
- [x] A test drives a REAL fan-out through the API and reads the parent back.
- [x] `ruff format`, `ruff check --fix`, `pytest` clean.

- 2026-09-26 dev: done. The wiring is `fans_out(op, scope)` at the door, and
  the interesting part was deciding WHICH requests it covers.

  Not every op: `fan_out` resolves "all" to SOURCES, and only `sync` and
  `split` read `job.scope["name"]`. Fanning `monitor` or `embed` out per source
  would hand them, three times over, a scope they cannot read. `SOURCE_SCOPED`
  is a frozenset with a comment saying how to tell — data, like `OPS` itself,
  and a test asserts the set holds exactly the two ops that read a source name
  so the reason survives the next person.

  Nor every scope: an explicit single source stays one job. A parent with one
  child is a layer the operator clicks through to reach the thing they asked
  for.

  **`maintain`'s stages are deliberately NOT job rows here.** The spec's
  `1180 of 1240` looks like per-unit progress, and #052 in the backlog settles
  the mechanism as "derive parent % from leaf counts" — which is what #172
  does. Making each stage a row needs ordering between them, which is #051's
  DAG design. Out of scope and named rather than guessed.

  Driven end to end, which is the whole point of this ticket:

      POST /jobs {"op":"sync","scope":{"type":"all"}}   -> parent id
      GET  /jobs/<parent>   running  {"done":0,"total":2}
                            failed   {"done":2,"total":2}
      GET  /jobs/<parent>/children   alpha-src -> failed, beta-src -> failed
      $ hrono jobs get <parent>
        sync  failed
        progress: 2 of 2 stages done

  (The syncs fail because the fixture's git URLs are fake; the aggregation is
  what this proves.) #172 was correct and dormant three commits ago; it is now
  reachable from the door an operator uses.

  Mutations, all killed: the door not fanning out -> 2 fail; every op fanning
  out -> 3; an explicit single source fanning out -> 2.

  Gate clean: 1207 passed, 2 skipped.

- 2026-09-26 qa: PASS, to po-review. #172 is no longer dormant, and I checked
  that by the same route an operator has rather than by reading the diff.

  Gate at 2a8d086: ruff clean, 1207 passed. Re-ran dev's F2 (every op fanning
  out) — 3 fail.

  Checked the two doors dev did not mention. `POST /trees/<name>/maintain` and
  `/sync` enqueue `maintain` and `sync-tree`, neither of which is
  source-scoped, so neither fans out — correct, those are whole-tree ops, and
  worth stating because "the fan-out is wired" could be read as "everywhere".

  **One observation, not a defect.** `sync` over all sources on a server with
  NO sources registered produces a parent that is immediately `succeeded` with
  zero children and no progress. That is `create_fanout`'s documented behaviour
  and it predates this ticket — but #175 is what makes it reachable, since the
  same request used to run one job that died on `scope["name"]`. A crash became
  a silent success, which is the better of the two and still says nothing. I am
  not filing it: with no sources registered, "syncing all of them succeeded" is
  true, and the operator knows their own registry is empty. Recording it so the
  next person who meets a suspiciously instant success knows where it comes
  from.

  The decision I want to endorse is the SCOPE of the wiring. Dev could have
  fanned every op out and made the ticket look bigger; instead the set is two
  names with a test asserting WHY those two, and `maintain`'s stages are
  explicitly left to #051's design rather than invented here. A ticket about
  unreachable code is the easiest place in the world to build more of it.

- 2026-09-26 po: CLOSED. The job framework's parent/child structure is reachable
  from the door an operator uses, three commits after we shipped an aggregation
  over it that nothing could produce.

  **This is the fourth instance, so it becomes a convention.** #094's seams,
  #166 and #168's real size, #163's uncalled sweep, and now a framework
  function whose only callers were its own tests. The shape is always the same:
  *a test that constructs the state directly proves the reader and says nothing
  about the writer.* `fan_out` was tested faithfully and correctly by calling
  `fan_out`. Nobody asked who calls it.

  I am adding that to `CONTRIBUTING.md` now that it is committed and reaches
  people — #176 authored for the one-bullet change, so it goes through the
  board like anything else rather than being slipped in during a review.

  #173 (cancel) and #174 (SSE) are unblocked and next. They were authored
  before this was found and would both have been built on the same unreachable
  structure; holding them one ticket was the right call.
