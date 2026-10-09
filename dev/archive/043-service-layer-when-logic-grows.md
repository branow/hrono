---
id: 043
title: introduce a named service tier — only when business logic grows
priority: low
size: medium
depends_on: []
spec_refs: []
---

## Context
Raised during commit-by-commit review: should we formalize a service layer
between the HTTP routes and the storage modules? Decision: NOT NOW. Today the
logic is thin and the layering already mostly exists — routes are thin, the CLI
is a thin HTTP client of the server (#010), and the job ops are the orchestration
seam. A blanket service tier now would be anemic pass-through (route -> service ->
store with no logic in the middle), which the project rules forbid ("nothing
speculative", "no file sprawl"). Guarded invariants like `role in ROLES` in
`auth/users.py` are fine where they are (belt-and-suspenders with the SQL CHECK),
and authorization policy already lives in the Bearer middleware (#006), not the
DB layer.

## Trigger to pull into todo
Revisit when an operation appears that either:
- has MORE THAN ONE caller of the same business rule, or
- ORCHESTRATES multiple stores / side-effects (validate + persist + audit +
  invalidate ...).

First real candidate: the ingest/cluster/brief job ops (sync->filter->split->
store is already service-shaped) and the M7 incremental invalidation across
trees. Formalize the service tier there FIRST and surgically — never as a
codebase-wide ceremony refactor.

## Out of scope
- Any refactor of existing single-caller CRUD (users, registries) into services.
- Renaming `authenticate()` (a lookup, not policy) — cosmetic only.

## Review log
- 2026-08-22 stakeholder + PO: discussed, agreed to defer. Layering instinct is
  right; logic is too thin to make a service tier non-speculative yet. Captured
  as a marker with an explicit pull-in trigger.
- 2026-09-27 po: re-checked, still NOT NOW, and the check is cheap enough to
  record. The routes are still thin: the dashboard's biggest module
  (`server/ui/nodes.py`, 350 lines) is routes plus render helpers, and every
  decision it makes is `edits`, `notes` or `pins` — domain modules that already
  exist and are tested on their own. The registry engine, the job ops and
  `registry/impact.py` are the same shape. The trigger stands: a named service
  tier when a route starts holding business rules of its own, not before.
