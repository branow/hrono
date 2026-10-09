---
id: 179
title: a job records the tokens it spent
priority: medium
size: medium
depends_on: [132, 133, 172]
spec_refs: [implementation-notes.md]
---

## Context
The spec's job shape has carried a `cost` field since M0 and nothing fills it:

    { "id": "job_42", "status": "partial",
      "progress": {...}, "cost": { "tokens": 480000, "usd": 1.12 } }

Three tickets have pointed at the gap. #172 named it out of scope, #178 is
PARKED on it — a dry-run that estimates cost needs a record of what things
actually cost — and the operator running a `maintain` over a large corpus has
no way to ask what it spent afterwards.

The data is half there: `briefs` records `input_tokens` and `output_tokens`
per brief (0011). Nothing aggregates it, and `condense` and `propagate` record
nothing at all.

## Description
- Every op that makes LLM calls reports the tokens it spent in the outcome it
  already returns (#132/#133): `{"tokens": {"input": N, "output": M}}`.
- The worker stores that on the job row, beside `result`.
- `GET /jobs/<id>` reports it, and a PARENT sums its children's (#172's
  derivation, one field over).
- `hrono jobs get` shows it.

## Out of scope, and why
`usd`. Converting tokens to money needs a price per model, which is config this
project does not have and which goes stale the moment a provider changes it.
Reporting a made-up number to someone deciding whether to spend money is worse
than reporting none. Tokens are a fact; dollars are a lookup, and the lookup is
its own ticket.

## Acceptance criteria
- [x] An op that calls an LLM reports its token usage; one that does not
      reports nothing rather than zero.
- [x] `GET /jobs/<id>` shows a leaf's tokens and a parent's SUM.
- [x] `hrono jobs get` shows them.
- [x] A job that spends nothing has no `cost` key at all.
- [x] `ruff format`, `ruff check --fix`, `pytest` clean.

## Review log
- 2026-09-26 po: authored — the third ticket to point at this gap is enough.

- 2026-09-26 dev: done. **No migration.** `result` is already defined as "a
  JSON object of COUNTS, never prose" (0027), and a token count is exactly
  that — so the tokens go in the outcome an op already returns, and
  `GET /jobs/<id>` derives `cost` at read time the way #172 derives status. No
  second place for it to go stale.

  Four ops now report what they spent, and the one that mattered most reported
  nothing at all: **`propagate`** discarded every `CompletionResult.usage` it
  received, while issuing BEST_OF (3) votes per changed leaf and RE-ASKING on
  a bad reply. The most expensive stage of a run was the one nobody could
  account for. Its two existing outcome tests now pin the numbers, and the
  abstention case is the sharper one — `{"input": 6, "output": 6}` for a topic
  that was never judged. An abstention is not free, and until now it looked it.

  `condense` returned NO outcome at all, so it gained one (`condensed`, plus
  tokens). That is #133's rule catching up with a stage it had missed.

  A parent's cost is its children's summed — same derivation as its status, and
  a stage that called no model contributes nothing rather than a zero. A run
  with no model calls has no `cost` key at all: `{"input": 0}` on a `cluster`
  job invites the reader to ask which model it used.

  `usd` is deliberately absent. It needs a price per model — config this
  project does not have, that goes stale when a provider changes it — and a
  made-up number shown to someone deciding whether to spend is worse than no
  number. Tokens are a fact; dollars are a lookup.

  Mutations, all killed: a model-free run reporting zero -> 1 fail; a parent
  reporting its largest child instead of the sum -> 2; the judge panel not
  counting its votes -> 2.

  Gate clean: 1239 passed, 2 skipped. **#178's cost half now has a source of
  truth**, which was the point.

- 2026-09-26 qa: PASS, to po-review, with three tests added.

  Gate: ruff clean, 1243 passed. Re-ran dev's J3 (the judge panel not counting
  its votes) — 2 fail.

  **The finding, and it is #176 catching this ticket two tickets after we wrote
  it down.** I mutated `brief` to stop appending its usage and **nothing
  failed.** Same for `brief_upper` and `condense`. Every test of the cost
  SURFACE — mine and dev's — plants the result JSON by hand, so they proved the
  reader and said nothing about three of the four writers. Only `propagate` was
  covered, because its outcome tests already existed and asserting the new key
  was forced on us.

  That is exactly the rule in `CONTRIBUTING.md`: *a test that constructs the
  state it asserts on proves the reader and says nothing about the writer.* It
  is a good sign that the convention caught something this fast and a poor one
  that it had to.

  Three tests added, each calling the OP: brief reports `{"input": 80,
  "output": 24}` for two nodes, brief_upper and condense report theirs, and a
  second brief run with nothing to do reports no `tokens` key at all. All three
  mutations now kill.

  The `usd` omission is right and I want to endorse it rather than let it read
  as unfinished. Tokens are a fact this system observes; dollars are a lookup
  against a price list that does not exist here and goes stale when a provider
  changes it. Showing someone an invented number while they decide whether to
  spend money is the worst available option.

- 2026-09-26 po: CLOSED. A job says what it spent, and #178's cost half has the
  source of truth it was parked on.

  Two things worth keeping.

  **`propagate` reported nothing.** It issues three votes per changed leaf and
  re-asks each on a bad reply, so it is the most expensive stage in a run, and
  it threw every usage away. The abstention case makes the point sharpest: six
  completions for a topic that was never judged, previously indistinguishable
  from free. An operator asking "why did that cost so much" had no way to find
  out.

  **No migration.** `result` was already defined as a JSON object of counts, so
  tokens belong in it and `cost` derives at read time like status and progress.
  Three derivations now, one pattern, nothing stored twice. That is the third
  time #172's shape has paid for itself.

  qa's finding is the one I will remember from this ticket: the convention we
  wrote in #176 caught its author two tickets later, in work done by the same
  process that wrote it. Rules about testing are worth nothing until they
  inconvenience the person who wrote them.
