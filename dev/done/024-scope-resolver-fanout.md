---
id: 024
title: jobs framework — scope resolver + fan-out into atomic leaves (T11.3)
priority: high
size: medium
depends_on: [023, 012]
spec_refs: [build-order.md#T11.3, implementation-notes.md#jobs]
---

## Context
An op is `(op, scope)` and "fans out into one atomic job per item, failures leave
the rest pending" — but #023's worker runs a single job per enqueue. This ticket
adds the missing half: resolving a scope selector into a concrete item set and
fanning a parent job out into one atomic leaf job per item. It completes the jobs
framework (T11) so real ops (sync T12, split T14) can target "all sources" or a
named source and run per-item. Scope defaults to "everything that needs it".

## Description
Add a scope resolver (recommend `src/hrono/jobs/scope.py`) that turns a scope
selector into the set of items an op will run over, and wire fan-out into the
enqueue/worker path from #023.

- **Selectors** (data-driven; kebab-case `type`): `{"type":"all"}`,
  `{"type":"source","name":"<n>"}`. These are the M2-relevant scopes. Add the
  seam for `section`/`node`/`level` (they resolve against tree entities that do
  not exist until M3) but they may raise a clear "not yet supported" for now —
  do not fake them. `all` = every item the op needs; empty/omitted scope = `all`.
- **Resolution** reads the relevant registry/entities: for ingest ops, `all`
  resolves to every registered `sources` row and `source` to the one named
  source (404-style clear error if the name is unknown). Keep resolution a
  data-driven map from selector type to a resolver function, not an if/elif
  ladder.
- **Fan-out**: enqueuing a `(op, scope)` creates a parent job (status derived
  later in T57) and one atomic leaf job per resolved item, each leaf carrying the
  concrete single-item scope (e.g. `{"type":"source","name":"..."}`). The #023
  worker then runs each leaf independently; a failed leaf leaves siblings pending
  (already guaranteed by #023). Empty resolution (no items) completes the parent
  with no leaves rather than erroring.
- Everything goes through the #008 `Database` lock; leaf creation is atomic.

## Acceptance criteria
- [ ] `{"type":"all"}` resolves to every registered source; `{"type":"source",
      "name":"x"}` resolves to just `x`; an unknown source name is a clear error,
      not a crash; empty/omitted scope behaves as `all`.
- [ ] Enqueuing a parent `(op, scope)` creates one atomic leaf job per resolved
      item, each with a concrete single-item scope; the worker (#023) runs each
      leaf, and a failing leaf does not stop its siblings.
- [ ] A scope resolving to zero items completes without creating leaves and
      without erroring.
- [ ] `section`/`node`/`level` selectors have a wired seam but clearly report
      "not yet supported" (they land with tree entities in M3) — they are not
      silently ignored or faked.
- [ ] The selector->resolver dispatch is data-driven (a map), not a branch
      ladder.
- [ ] Regression-grade tests cover all/source resolution, unknown-source error,
      empty resolution, fan-out into N leaves with per-item scope, and the
      failing-leaf-does-not-block-siblings guarantee.
- [ ] `ruff format`, `ruff check --fix`, `pytest` all clean; work committed.

## Out of scope
- section/node/level resolution (needs tree entities, M3+).
- The ops themselves (`sync` is #025) — use the #023 trivial op / a test op to
  exercise fan-out.
- Parent status aggregation (T57, M11) — only create the parent + leaves here.

## Review log
- 2026-08-15 PO: authored to finish the T11 jobs framework. Resolves all/source
  now, seams section/node/level for M3. Fan-out creates atomic leaves so the
  #023 failure-isolation guarantee applies per item.
- 2026-08-16 dev: picked up (deps 023, 012 in done/), moved to in-progress.
- 2026-08-16 dev: implemented. `jobs/scope.py`: a data-driven `_RESOLVERS`
  map (`all`->every registered source, `source`->the named one or `NotFound`,
  section/node/level->`BadRequest` "not yet supported"); `resolve(db, scope)`
  (omitted/empty scope -> all) and `fan_out(db, op, scope)` creating a parent +
  one leaf per resolved item, each leaf carrying its concrete
  `{"type":"source","name":...}` scope. Raises the #027 `AppError` subclasses
  (NotFound/BadRequest) — first M2 code on the new error layer. Added
  `store.create_fanout` (parent + leaves in one transaction) and made
  `claim_next` skip parents via `NOT EXISTS (children)` so the worker only runs
  leaves/standalone jobs — a small generic change to #023's claim (its own tests
  still pass). Empty fan-out records the parent `succeeded` with no leaves.
  Everything under the #008 Database lock. Tests: `tests/jobs/test_scope.py` —
  all/source/omitted resolution, unknown-source NotFound, section/node/level
  BadRequest, fan-out into N per-item leaves, worker runs leaves while the parent
  stays pending (skipped), empty->succeeded-no-leaves, and failing-leaf-doesn't-
  block-siblings through fan-out. Gate clean (ruff format, ruff check --fix,
  pytest 244 passed). Drove it against a real DB: resolve all/source/unknown/
  node, fan-out ran all 3 sources per-item (3 leaves succeeded), parent left
  pending. Scope: section/node/level need tree entities (M3); real ops are #025+;
  parent status aggregation is T57. **T11 jobs framework complete.** Committed
  01f704d. Moved to verifying.
- 2026-08-16 qa: PASS -> po-review. Verified all dimensions. Drove the full path
  with a real Database + real Worker: `resolve` handles `{"type":"all"}` (every
  registered source), omitted/None scope (defaults to all), `{"type":"source",
  "name":x}` (just x), an unknown source -> `NotFound "unknown source: ghost"`,
  and `section`/`node`/`level` -> `BadRequest "scope type not yet supported"`
  (seamed, not faked). Dispatch is a data-driven `_RESOLVERS` map, and the
  resolver correctly raises the new #027 `AppError` subclasses (as the board
  directs new M2 code to). Fan-out over "all" created a parent + one atomic leaf
  per source, each leaf carrying its concrete single-item `{"type":"source",
  "name":...}` scope; the worker ran all leaves to `succeeded` while the PARENT
  stayed `pending` and was NEVER claimed - the critical correctness point,
  achieved by `claim_next`'s new `NOT EXISTS (children)` filter so a job with
  children is skipped (leaves and standalone jobs still run; #023's exactly-once
  + standalone tests remain green in the gate). Empty resolution (no sources)
  records the parent `succeeded` with zero leaves and no error. A failing leaf
  fails in isolation without blocking siblings (inherited from #023, retested
  here). Integrity: `create_fanout` inserts the parent + all leaves in ONE
  transaction, and since both the fan-out write and the worker claim go through
  the same #008 `Database` lock, the worker never observes a half-built fan-out
  (no chance of claiming a childless-looking parent mid-insert). Tests are
  regression-grade and use real Database/Worker threads, covering every AC.
  Code review clean: data-driven resolver map, atomic fan-out, typed, docstrings
  only, no emojis; tree-scope resolution and parent aggregation (T57) correctly
  out of scope. Commit 01f704d is a proper atomic Conventional Commit. Re-ran
  the gate: ruff format clean (89 files), ruff check passed, pytest 244 passed.
  This completes the T11 jobs framework.
- 2026-08-16 PO: PASS -> done. Drove the full path on a real Database + Workers.
  Resolution: `all`/omitted -> every source, `source` -> the named one, unknown
  source -> NotFound "unknown source: ghost", section/node/level -> BadRequest
  "scope type not yet supported" (seamed for M3, not faked) - via a data-driven
  _RESOLVERS map raising the new #027 AppError subclasses (first M2 code on the
  error layer). Fan-out over `all` created a parent + one atomic leaf per source;
  3 workers ran all 3 leaves to succeeded while the PARENT stayed `pending` and
  was NEVER claimed (the critical point - claim_next's NOT EXISTS children
  filter), a STANDALONE job still ran to succeeded, and the op ran exactly 4x
  (3 leaves + 1 standalone, never the parent). create_fanout is one transaction
  under the #008 lock, so no half-built fan-out is observable. Ran the gate: ruff
  format (89 clean), ruff check clean, pytest 244 passed. Completes the T11 jobs
  framework. Unblocks #025 (sync op). No adjacent work spun off. Closed 01f704d.
