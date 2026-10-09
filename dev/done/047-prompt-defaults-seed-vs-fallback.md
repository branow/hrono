---
id: 047
title: DECISION — seed defaults into the DB (A) vs read-time fallback (B)
priority: low
size: small
depends_on: [021]
spec_refs: [build-order.md#T10.2]
---

## Decision
KEEP design A (seed defaults into the DB on first run, `is_default` rows). This
is a record of a considered fork, not a change request. Do not reopen unless the
trigger below fires.

## The fork
Default prompt templates live in code (`descriptor.defaults`) and are available
at runtime. That raised: do we even need seeding? Two viable designs:

- A (current, #021): on first run, materialize defaults into the DB as
  `is_default=1` rows. Reads are uniform and listable — `GET /prompts` returns
  the four rows with no merge, prompts behave exactly like sources/connections/
  models. `delete` on an `is_default` row rewrites it from the code default
  (reset-to-default). Cost: the seeding routine + the `is_default` column.
- B: DB holds ONLY user overrides; a missing prompt falls back to
  `descriptor.defaults` at read time. Reset-to-default becomes trivially "delete
  the override row" and seeding disappears. Cost: every read path (`list`/`get`)
  must MERGE code-defaults with DB rows, and prompts become a special case vs
  the other collections.

## Why A was kept
Uniform, listable reads: one query returns the effective set and prompts are not
a special case in the engine. A is already built and tested (#021); the merge-on-
read logic B needs is not obviously cheaper than maintaining the seeding path.

## Trigger to revisit
If the seeding/`is_default` maintenance cost grows (e.g. many seeded collections,
frequent default churn) OR the reset semantics get awkward, re-evaluate B —
moving the complexity to a single read-time merge helper. Only then.

## Review log
- 2026-08-22 stakeholder + PO: discussed during review of the prompts/seeding
  commits. Recorded the A-vs-B fork; decided to keep A. No code change.
- 2026-08-22 PO triage: archived to done/ as a decision record. This is a closed
  ADR (keep design A), not pending work — only a "revisit if the trigger fires"
  clause. Kept for the trail; removed from the active backlog inbox. Reopen by
  authoring a fresh ticket only if the recorded trigger fires.
