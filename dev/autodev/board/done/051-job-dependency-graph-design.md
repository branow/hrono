---
id: 051
title: DESIGN — first-class job dependencies (DAG), execution order, retry, and tree-mutation semantics
priority: medium
size: big
depends_on: [022, 023, 024]
spec_refs: [build-order.md#T11, build-order.md#M7, clustering-lifecycle.md]
---

## Context
A design ticket (produce a decision, not code yet). The current jobs framework
hides pipeline dependencies inside ops (the `split` op runs sync->filter->split->
store internally) plus one-level parent/leaf fan-out. This folds together several
concerns raised in review that share one root question — WHAT IS THE JOB GRAPH
AND HOW DOES IT EXECUTE AND RE-RUN INCREMENTALLY:

- Dependencies: sync -> filter -> split -> store -> embed -> cluster -> brief is a
  real dependency chain currently implicit. First-class edges would let the
  worker order stages topologically and run independent branches in parallel
  (embed source A while splitting source B).
- N-level jobs (not just parent+leaf): the current framework is deliberately
  TWO levels. Stakeholder wants ANY big task to be a job that splits into smaller
  jobs down to atomic units — e.g. "rebuild the whole pipeline" -> a top job ->
  one job per op (sync/split/embed/cluster) -> per-cluster/per-node sub-jobs ->
  atomic leaves. Every level is independently trackable (feeds #052 progress) and
  parallelizable. Two levels cannot express this; a recursive/multi-level tree
  (or DAG) can. This is the general "everything is a job" engine.
- Incremental re-run (hrono's differentiator): a changed source should invalidate
  only its node -> its brief -> the parent brief. That is a dependency graph;
  without one, re-run is coarse.
- Job granularity / retry atom (deferred from the 25a89e5 review): a leaf is
  currently a WHOLE source (`{"type":"source"}`), which is not small; "atomic"
  today means failure-isolated + idempotent, NOT node-level. True incremental
  retry wants the atom at node/file/content-hash level.
- Tree mutation during a job: `scope` is captured at creation but resolved at
  execution; over a mutating tree, does a job operate on a snapshot or the live
  tree? Currently unanswered.

## Hard constraints to honor in the design
- Single-writer SQLite lock (#008): parallelism buys COMPUTE overlap (embed/
  cluster/LLM already run outside the lock) only — DB writes still serialize.
  Do not design for concurrent persistence. DB writes are NOT the bottleneck
  (they are short); the parallelism target is embedding-building and external
  API/LLM work.
- Parallelism model = many workers, LOCK-FREE compute, short SERIALIZED persist.
  The load-compute-persist shape (#035 embed, #040 cluster: load working set
  under lock -> RELEASE -> compute -> re-acquire -> persist) is the required
  discipline: a job must never hold the lock while doing slow work, or worker
  count buys nothing.
- Staleness at persist (consequence of releasing the lock): between "load under
  lock" and "persist under lock" the underlying data can change (another job, an
  edit). The persist step MUST reconcile staleness (re-check version/content_hash,
  skip or recompute if the input moved), not blindly write. This is the same
  read-then-write race as the tree-mutation question below.
- Keep it lean: dependencies + priorities is a mini workflow engine; let the
  incremental-invalidation requirement drive the shape, not generality. Do NOT
  reimplement Airflow/Temporal.
- Ops are idempotent (sync/split per-source txn) — the retry model must preserve
  that.

## Questions the design must answer
- Edge model: explicit `depends_on` edges vs derived from op-stage order? Cycle
  detection? One table or a `job_edges` table?
- Failure propagation: if job A fails, are downstream B/C canceled, held, or left
  pending? Is there partial-success (the existing derived `partial` parent
  status, T57)?
- Retry: reset failed->pending in place vs clone; at what granularity (leaf vs
  node/hash); how re-run interacts with idempotent ops.
- Parallel execution: worker pool size; how the single-writer lock bounds it;
  which stages are safe to overlap.
- Tree-mutation/consistency: snapshot vs live-tree; how scope resolution handles
  a tree that changed since job creation.
- Relationship to M7 (incremental lifecycle) — is this the substrate M7 builds
  on, and should it be designed WITH M7 rather than before it?

## Deliverable
A short decision doc (blueprint-style) capturing the chosen edge model, failure/
retry semantics, parallelism bound, and tree-mutation stance, plus the follow-up
implementation tickets it spawns. No production code in this ticket.

## Out of scope
- Implementing the scheduler (spawned as follow-up tickets from the decision).
- Job priorities (#050) — related but separate; fold in only if the DAG design
  subsumes it.

## Review log
- 2026-08-22 stakeholder + PO: raised while reviewing the worker (priorities +
  job relations/parallelism). Merged with the deferred 25a89e5 concern
  (granularity/retry/tree-mutation) since they share one root. Scoped as a design
  ticket to decide before M3 tree-ops and M7 land, not an immediate build.

## Decision (2026-09-27)

**No job DAG. The dependency graph lives in the DATA, and it already works.**

This ticket asked whether it should be designed WITH M7 rather than before it.
M7 shipped, so the question is answerable from what was built rather than from
what was imagined, and the answer changes the shape of the ticket.

### 1. The chain is a SEQUENCE, and it is already first-class — as an op

`tree/sync_chain.py` composes `update -> propagate -> brief -> brief-upper ->
monitor -> repair` in one function, in one order, with the order documented as
the op's reason to exist. `maintain` does the same for a cold build.

First-class EDGES would be a regression here, and #122 is the evidence: that
bug was a chain that skipped a stage — sections arrived unsummarised, `brief`
silently dropped them, and the briefs cited sources they had never read. A map
that looks right and is quietly wrong, with no error anywhere. A DAG lets an
operator wire that; a composing op cannot be sequenced incorrectly. The design
question "explicit `depends_on` vs derived from stage order" is answered by
neither: the order is CODE, in the one place that knows why it is the order.

### 2. N-level fan-out: not until something needs two

The framework has one level, parent + leaf. #175 is the warning: `fan_out` was
reachable from tests only, nothing in production created a parent, and #172
shipped an aggregation over a structure no request could produce. Building a
recursive tree before anything produces two levels is that mistake at a larger
size. The trigger to revisit: a real op that genuinely fans out twice —
per-source then per-file is the plausible one, and `sync` does not need it.

### 3. Incremental re-run does NOT need job edges — it is a data dependency

This was the ticket's strongest argument and it is the one M7 answered without
a graph. What makes a re-run incremental is not knowing which JOB ran before;
it is knowing whether a piece of CONTENT still matches what produced it:

- `briefs._is_fresh` compares the brief's member signature, prompt hash and
  model fingerprint (#064, #191). Anything that moved, re-briefs; nothing else
  does.
- `member_signature` signs over CONTENT HASHES, so a re-split that re-mints
  section ids does not invalidate a brief (#068).
- `propagate` climbs from a changed leaf and marks exactly the ancestors whose
  descriptions no longer hold (#087), recording each decision in `update_log`.
- `embed` embeds one content hash once (#144); `sync` per-source is idempotent.

That IS the invalidation graph, and it is finer than a job DAG could be: it is
keyed by content, not by run. A job DAG would be a SECOND representation of the
same dependency, and the two would eventually disagree — with the data right
and the graph confidently wrong.

It also answers the retry-atom question. The atom is already the content hash:
re-running any op skips what is fresh, so "retry at node level" and "run the op
again" are the same operation. Reset-in-place versus clone stops mattering.

### 4. Tree mutation during a job: load-compute-persist, reconciled by signature

`scope` is resolved at execution, and the discipline (#035, #040) is: load the
working set under the lock, RELEASE, compute, re-acquire, persist. The staleness
that window admits is reconciled by the same signatures as above — persist
re-checks what it computed against, rather than blindly writing. No snapshot
isolation, no job-level versioning. A job operates on the LIVE tree and its
writes are guarded by content, which is the only thing that survives a
concurrent hand-edit anyway (#154's pins are the other half: an operator's
decision outranks a recomputation).

### 5. Parallelism: measured, and not the constraint anyone assumed

The ticket's constraint section says DB writes serialize and the target is
compute overlap. #193 measured the actual contention: a write issued during a
1.2s read-heavy recall waited **7.7 ms**. WAL plus a connection pool, so the
lock is not the bottleneck and was not the one to design around.

The real serialization is one worker thread. A worker POOL is a small,
independent change (`Worker` already takes its dependencies by injection and
claims under the lock with no double-claim) and it needs no dependency graph to
be worth doing — it needs a workload with two independent runnable jobs, which
one-level fan-out already produces. That is the only implementation ticket this
design spawns, and it stays unauthored until someone has that workload.

### What this ticket spawns

Nothing to build. Two triggers to watch:

- an op that genuinely fans out twice -> revisit N-level.
- two independent runnable jobs and a measured wait -> a worker pool ticket.

The durable half — the graph lives in the data, and load-compute-persist
reconciles by signature — goes in `CONTRIBUTING.md`, because it is the rule
every future op has to follow whether or not anyone reads this ticket.
