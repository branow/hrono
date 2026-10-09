---
id: 022
title: jobs framework — job record schema + status model (T11.1)
priority: high
size: medium
depends_on: [002]
spec_refs: [build-order.md#T11.1, implementation-notes.md#jobs]
---

## Context
Opens M2 (Ingest). Every slow operation in hrono runs async: "config is data you
PUT, work is a job you POST", and the server owns a background worker. Before any
op (sync, split, embed, cluster) can run, there must be a job record to track it.
This ticket lays the persistence and domain model for jobs; the worker loop that
executes them is #023, and the first real op (`sync`) is T12. Pure storage +
model, so it lands testable without a running worker.

## Description
Add a forward-only migration and a jobs domain model.

1. **Migration** `NNNN_jobs.sql` (next free number after `0003_registry.sql`)
   creating a `jobs` table. Columns from the spec's job record:
   - `id TEXT PRIMARY KEY` — job id (e.g. `job_<n>`/uuid; pick and document).
   - `parent_id TEXT` — nullable; the parent job for fan-out aggregation (parents
     are added later, but the column lands now so nothing back-fills).
   - `tree TEXT` — nullable target tree name (null for pre-tree ingest ops).
   - `op TEXT NOT NULL` — the operation name (e.g. `sync`, `split`).
   - `scope TEXT NOT NULL` — JSON scope selector (e.g. `{"type":"all"}`,
     `{"type":"source","name":"..."}`); stored as text.
   - `status TEXT NOT NULL` — one of the leaf statuses below (CHECK-constrained).
   - `error TEXT` — nullable failure reason for a failed job.
   - `created_at TEXT NOT NULL`, `updated_at TEXT NOT NULL` — ISO-8601 UTC.
   Index `status` (the worker polls pending) and `parent_id` (child lookup).

2. **Domain model** (recommend `src/hrono/jobs/model.py`):
   - a `JobStatus` set/enum of the leaf statuses: `pending` | `running` |
     `succeeded` | `failed` | `canceled` (kebab-case values; the parent-only
     `partial` status is derived later in T57, not stored — do not add it here).
   - a frozen `Job` dataclass mirroring a row (typed fields).
   - pure helpers to serialize/deserialize the `scope` JSON and to read a row
     into a `Job`.

No worker, no op execution, no endpoints — those are #023 and the ops. Conventions:
forward-only `NNNN_description.sql`; frozen/immutable model; typed params;
`snake_case` columns, kebab-case status values; CHECK constraint on `status`;
standard libs.

## Acceptance criteria
- [ ] The migration, applied via the existing `Migrator`, creates `jobs` with the
      columns above, a CHECK limiting `status` to the five leaf statuses, and
      indexes on `status` and `parent_id`.
- [ ] `Job` is frozen and typed; `JobStatus` fixes exactly the five leaf statuses
      (no `partial`).
- [ ] A row round-trips to a `Job` and back, including a JSON `scope` that
      deserializes to the original selector.
- [ ] Inserting a status outside the allowed set is rejected at the SQL layer.
- [ ] Regression-grade tests cover the table shape + CHECK + indexes, the status
      set, and the row<->Job<->scope round-trip.
- [ ] `ruff format`, `ruff check --fix`, `pytest` all clean; work committed.

## Out of scope
- The worker loop / atomic leaf runner / op dispatch (#023 / T11.2+T11.4).
- Scope resolution into an item set (T11.3).
- Parent aggregation, cooperative cancel, SSE events (T57, M11) — only the
  `parent_id` column and `canceled` status land now.
- Any jobs HTTP endpoint (lands with the worker/ops).

## Review log
- 2026-08-15 PO: authored to open M2. Pure schema + model so it lands testable
  without the worker; deliberately excludes the parent-`partial`/cancel/SSE
  polish (T57) while laying the `parent_id` column and `canceled` status now.
- 2026-08-16 dev: picked up (dep 002 in done/), moved to in-progress.
- 2026-08-16 dev: implemented. Migration `0005_jobs.sql` (0004 was taken by
  #021) creates `jobs(id PK, parent_id, tree, op NOT NULL, scope NOT NULL,
  status NOT NULL CHECK IN the five leaf statuses, error, created_at, updated_at)`
  plus indexes `jobs_status` and `jobs_parent_id`. `src/hrono/jobs/model.py`:
  `JobStatus` StrEnum fixing exactly pending/running/succeeded/failed/canceled
  (no `partial`), a frozen typed `Job` dataclass mirroring a row, and pure
  `serialize_scope`/`deserialize_scope` (JSON) + `to_job(row)`. Job id format is
  documented as `job_<n>` in the scope selectors; id generation lands with the
  worker (#023). Tests: `tests/jobs/test_migration.py` (table shape, both
  indexes, CHECK rejects a non-leaf status, valid row round-trips) and
  `test_model.py` (status set is exactly the five, no partial; Job frozen; scope
  round-trip; row->Job with scope parsed to a dict). Gate clean (ruff format,
  ruff check --fix, pytest 198 passed). Verified against the real migrated DB:
  jobs table + both indexes present, five statuses (no partial), row round-trips
  to a Job with a dict scope, CHECK rejects 'partial'. Pure storage + model — no
  worker/ops/endpoints (those are #023 and the ops). Opens M2. Committed 25a89e5.
  Moved to verifying.
- 2026-08-16 qa: PASS -> po-review. Verified all dimensions. Drove the real
  migration: `0005_jobs.sql` (next forward-only number) creates `jobs` with all
  spec columns (id PK; parent_id/tree/error nullable; op/scope/status/
  created_at/updated_at NOT NULL), a CHECK limiting `status` to exactly the five
  leaf statuses, and indexes `jobs_status` + `jobs_parent_id`; an out-of-set
  status ("partial") is rejected at the SQL layer (CHECK constraint failed).
  `JobStatus` is a `StrEnum` fixing exactly pending/running/succeeded/failed/
  canceled (no `partial`, correctly deferred to T57); `Job` is a frozen typed
  dataclass; a row round-trips through `to_job` with the JSON `scope`
  deserializing back to the original selector, including a nested object/array.
  Tests are regression-grade: table shape, both indexes, CHECK rejection,
  status-set-exactly-five, frozen, scope round-trip, and row->Job. Code review
  clean: frozen model, typed, `StrEnum` values are the kebab-case statuses,
  pure (de)serialize helpers, docstrings only, no emojis, no worker/op/endpoint
  surface (correctly out of scope). Commit 25a89e5 is a proper atomic
  Conventional Commit. Re-ran the gate: ruff format clean (73 files), ruff check
  passed, pytest 198 passed. Opens M2 (Ingest).
- 2026-08-16 PO: PASS -> done. Migrated a fresh DB and exercised it myself: jobs
  table has all spec columns (id PK; parent_id/tree/error nullable; op/scope/
  status/created_at/updated_at NOT NULL), indexes jobs_status + jobs_parent_id
  present, CHECK rejects a non-leaf status ('partial'), and a row round-trips
  through to_job with the JSON scope deserializing back to the original dict
  selector. JobStatus is exactly the five leaf statuses (no partial, correctly
  deferred to T57); Job frozen + typed. Ran the gate: ruff format (73 clean),
  ruff check clean, pytest 198 passed. Pure storage + model, opens M2. Unblocks
  #023 (worker + dispatch). No adjacent work spun off. Closed at 25a89e5.
