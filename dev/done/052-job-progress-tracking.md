---
id: 052
title: job progress tracking — derive parent % from leaf counts; per-leaf reporting only for long leaves
priority: low
size: medium
depends_on: [022, 023, 024]
spec_refs: [build-order.md#T11, build-order.md#T57]
---

## Context
Jobs expose only discrete status (pending/running/succeeded/failed/canceled); a
user cannot see "how far along." The parent/leaf fan-out already provides a
natural, near-free progress signal: progress = succeeded_leaves / total_leaves
for a parent, computed at read time from a COUNT on `parent_id` — the same
child-status counting the derived `partial` parent status (T57) already does. No
op instrumentation needed. This is the same lever as the granularity question in
#051: finer fan-out (per-file/node vs per-source) makes derived progress smoother
automatically.

## Description
- Phase 1 (cheap, do first): `GET /jobs/{id}` on a parent returns derived
  progress {done, total, fraction} from child leaf statuses. No schema change, no
  op coupling. CLI/dashboard poll it.
- Phase 2 (only if needed): per-leaf sub-progress for genuinely LONG single leaves
  (huge-file split, large embedding batch) via an optional `report(fraction)`
  callback the op may call + a `progress` column updated during the run (short
  writes under the #008 lock). Do NOT instrument every op — only long ones.

## Acceptance criteria
- [ ] A parent job read reports done/total/fraction derived from leaf statuses;
      correct as leaves complete; no new column for phase 1.
- [ ] Standalone (childless) jobs report 0/1 -> 1/1 sensibly.
- [ ] (Phase 2, if built) a long op can report sub-progress without the framework
      knowing op internals; absent a report, behavior is unchanged.
- [ ] `ruff format`, `ruff check --fix`, `pytest` all clean.

## Out of scope
- Instrumenting every op with progress reporting (only long leaves, phase 2).
- Time-remaining estimates.

## Review log
- 2026-08-22 stakeholder + PO: raised while reviewing the worker. Derive parent %
  from leaf counts (free, reuses T57 counting); tie smoothness to #051 fan-out
  granularity; per-leaf reporting deferred to long-leaf case only.
- 2026-09-27 po: CLOSED. Phase 1 shipped as #172 (T57.1): `jobs/aggregate.py`
  derives `{status, done, total}` for a parent from its children's statuses at
  read time, with no column and no op coupling, and #174 streams it over SSE.
  Two deliberate deviations from this ticket:
  - **No `fraction`.** `done` and `total` are the measurement; a ratio of two
    numbers already in the payload is a second representation of the same fact
    for a client to disagree with.
  - **A childless job reports NO progress, not `0/1 -> 1/1`.** #172 returns
    None for a leaf on purpose: a leaf answers for itself, and inventing
    progress for one would put a progress bar on every single-stage job in the
    system.
  Phase 2 (sub-progress inside one long leaf) is still not built and still not
  needed. The trigger to reopen is a single leaf long enough that a watcher
  sees nothing move — a full-corpus embed is the candidate; when someone runs
  one and says so, that is the evidence this ticket wanted.
