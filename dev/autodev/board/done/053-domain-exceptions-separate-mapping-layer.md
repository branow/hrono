---
id: 053
title: DESIGN — pure domain exceptions + a separate transport-mapping layer (Spring @ControllerAdvice style)
priority: medium
size: big
depends_on: [027, 048]
spec_refs: [implementation-notes.md, build-order.md#M11]
---

## Context
A design ticket (decide, then spawn implementation tickets). The current #027
AppError layer centralizes `AppError -> HTTP response`, but only did HALF the job:
the `domain -> AppError` mapping is still SCATTERED inside routes and the registry
engine (`except InvalidRole: raise Invalid(...)`, `except IntegrityError: raise
Conflict(...)`). Stores already raise PURE domain errors (InvalidRole,
DuplicateContext, MalformedConfig, KeyMismatch), which each route then hand-maps
to an HTTP-flavored AppError. That per-route re-raising is "mapping inside the
controller" — the thing we want to remove.

Target (Spring `@ControllerAdvice` model): domain exceptions know NOTHING about
transport; one dedicated advice/mapping layer maps a domain exception to a status
code. Domain code raises domain errors and never builds a response or picks a
status. This unifies with #048: the HTTP mapping and the CLI error boundary are
two RENDERERS of the same pure domain errors (HTTP -> status codes, CLI ->
message + exit code), with a transport-agnostic domain layer beneath both.

## Questions the design must answer
- Domain exception taxonomy: what pure domain errors exist (rename/keep
  InvalidRole/DuplicateContext/MalformedConfig/KeyMismatch/...); do they lose the
  HTTP metadata that AppError subclasses currently bake in?
- Mapping mechanism (pick one, keep it ONE layer, not in routes):
  - per-type FastAPI handlers: `add_exception_handler(DuplicateUser, ...)` (most
    Spring-like, one rule per handler), OR
  - a small data table `{DuplicateUser: (409,"conflict"), ...}` walked by one
    generic handler.
- Fallthrough: a domain error with no mapping -> generic 500 (as today);
  guaranteed by a test so nothing leaks.
- Do routes/engine STOP catching-and-re-raising (the goal), leaving only the
  mapping layer? Confirm the engine's IntegrityError->Conflict moves out of the
  route into the mapping layer or the store.
- Unify with #048: one domain-error set, two renderers (HTTP advice + CLI
  `cli_message`). Does AppError stay as an internal detail, get replaced, or
  become the mapping-layer's output type only?
- Migration path: incremental (introduce the mapping layer, move re-raises out
  collection by collection) vs one cut.

## Tradeoff to record
This REINTRODUCES a mapping table — the thing #027's docstring claimed to
eliminate. That virtue was partly false: #027 avoided the table only by pushing
HTTP vocabulary into the domain error and the real mapping into the routes. A
table in a dedicated transport layer is the correct home for transport policy;
the domain must not know it is 409.

## Deliverable
A short decision doc: the domain exception taxonomy, the chosen mapping
mechanism, how routes/engine stop mapping, and how HTTP + CLI share one domain
error set. Plus the implementation tickets it spawns. Supersedes/absorbs #048's
CLI half into one error architecture.

## Out of scope
- Implementing the refactor (spawned as follow-up tickets from the decision).

## Review log
- 2026-08-22 stakeholder + PO: raised while reviewing #027. Agreed: domain
  exceptions should be transport-agnostic with a separate Spring-style mapping
  layer; #027 centralized AppError->response but left domain->AppError scattered
  in routes. Linked to #048 (CLI half) as the unified error-architecture decision.

- 2026-09-23 po: #109 made this concrete. Every job failure now records a code,
  but every unmapped one records the SAME code (`internal-error`), because
  `errors.as_app_error` has no table to consult: a `SyncError`, an `LLMError`
  and a `KeyError` are indistinguishable to a client. The mapping layer this
  ticket proposes is what turns them into `sync-error`, `llm-error` and a
  genuine internal error, and `as_app_error` is now the single boundary that
  would consult it — one function, one table, no handler changes. Whatever this
  ticket decides must cover the job record, not only the HTTP path.

- 2026-09-23 po: CLOSED as substantially stale, with its live half promoted as
  #145. The ticket was written against "domain -> AppError mapping scattered
  inside routes and the registry engine". That is no longer the code: #027
  centralized AppError -> HTTP, #048 centralized the CLI boundary, #109 added
  the job boundary, and `grep "except"` across `server/` and the engine now
  finds exactly two catch-and-re-raise sites, both INSIDE the registry engine
  (IntegrityError -> Conflict, ValidationError -> Invalid) — which is one
  layer, and the layer the ticket wanted them moved to.

  The pure-domain-exception taxonomy it proposed also did not survive contact:
  `InvalidRole` / `DuplicateContext` / `MalformedConfig` no longer exist as
  separate types; those paths raise AppError subclasses directly, and a
  `@ControllerAdvice`-style indirection over them would add a layer to remove
  nothing.

  What IS real is the gap #109 exposed and this ticket predicted: op-level
  domain errors have no codes, so every job failure reports `internal-error`.
  That is #145, small, and it needs no design phase.
