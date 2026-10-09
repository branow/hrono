---
id: 050
title: job priorities — order the pending queue beyond FIFO (YAGNI-gated)
priority: low
size: small
depends_on: [022, 023]
spec_refs: [build-order.md#T11]
---

## Context
The worker claims the oldest runnable pending leaf (FIFO by created_at), one leaf
at a time. There is no way to make an interactive, user-triggered job jump ahead
of a long background job (e.g. a `recall`-driven re-embed vs a full re-cluster).
A `priority` would allow granular queue management. This is DEFERRED, not for
now: there is a single serial worker and no described queue contention, so
priority would reorder a queue that is not backed up.

## Trigger to pull into todo
When real queue contention exists — multiple workers (#depends on parallel
execution) OR interactive jobs competing with long background jobs for the single
worker.

## Description (when pulled in)
- Add `priority INTEGER NOT NULL DEFAULT 0` to `jobs`; higher runs first.
- `claim_next` orders by `priority DESC, created_at ASC` (FIFO within a priority).
- Leaves inherit the parent's priority at fan-out.
- Priority reorders PENDING jobs only; it does not preempt a running job.

## Acceptance criteria
- [ ] Pending jobs are claimed by (priority desc, created_at asc); same-priority
      keeps FIFO.
- [ ] Existing default behavior unchanged when no priority is set (all 0).
- [ ] Leaves carry the parent priority.
- [ ] `ruff format`, `ruff check --fix`, `pytest` all clean.

## Out of scope
- Preempting/pausing a running job.
- Fair-share/aging scheduling — plain integer priority only.

## Review log
- 2026-08-22 stakeholder + PO: raised while reviewing the worker. Cheap and
  non-breaking, but YAGNI with one serial worker and no contention. Deferred with
  a pull-in trigger. Related to #051 (dependency graph / parallel execution).
- 2026-09-27 po: re-checked, still YAGNI. The queue is one worker claiming the
  oldest runnable leaf, and nobody has measured a wait: #193 found a write
  during a 1.2s read waiting 7.7 ms, and the only interactive job — recall —
  is not a job at all, it answers synchronously. #051's decision names the
  thing that would have to come FIRST anyway: a worker pool, which needs two
  independent runnable jobs and a measured wait. Priorities are a way to order
  a queue that nobody is standing in.
