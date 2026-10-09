---
id: 077
title: vec0/ANN shadow index for recall — bound recall latency + single-writer contention at scale
priority: medium
size: big
depends_on: [069, 072, 075]
spec_refs: [build-order.md#M11, design-sketch-v1.md, how-hrono-works.md]
---

## Context
Consolidates the #035 "vec0/ANN shadow index" deferral with the concrete
consequence found in #075 (recall endpoint) review: the recall engine
(`recall/engine.py` + `vector_leg.py`) SCANS EVERY passage and computes each
combined vector INSIDE the DB connection on every query. So a recall holds the
#008 connection for an O(N-passages) scan — recall latency grows linearly with
corpus size, and the scan serializes against the single writer (a long recall can
delay a concurrent write, and vice versa). Fine for MVP corpora and the
correctness-first frozen recipe (M5 shipped this way deliberately), but it does
not scale.

## Description (when pulled in)
Add an approximate-nearest-neighbour index over passage vectors so the vector leg
retrieves candidates without a full scan:
- A vec0 (sqlite-vec) shadow index over the combined passage vectors (or content
  + path components), kept in sync as passages are embedded (#069) / re-split.
- The vector leg queries the ANN index for top candidates, then applies the exact
  a=0.5 blended score + z-floor on that candidate set — the FROZEN recipe's z math
  is preserved (z over the query's distribution may need a defined candidate-set
  approximation; decide and document so recall results stay stable/deterministic
  enough).
- Do the heavy candidate math OFF the #008 lock where possible (load under lock ->
  release -> score), like the embed/cluster ops, so recall does not hold the
  writer lock for the scan.
- Keep the exact-scan path as a correctness reference / small-corpus fallback.

## Open questions
- How z-scoring-over-the-query's-own-distribution (both legs) interacts with an
  ANN candidate set rather than the full corpus — does the z-floor semantics
  change? (This is the subtle correctness risk; the calibration test #075 must
  still pass.)
- vec0 multi-vector-per-row limitations (the #035 note on why vectors are a blob
  table) — does the shadow index store combined vectors precomputed?

## Acceptance criteria (when pulled in)
- [ ] The vector leg retrieves candidates via the ANN index, not a full passage
      scan; recall latency is sublinear in corpus size on a large planted corpus.
- [ ] Recall does not hold the #008 writer lock for an O(N) scan.
- [ ] The #075 calibration still passes (planted-answer recovers, strict-miss ->
      explore) — the ANN path does not change the frozen recipe's outcomes on the
      test corpus.
- [ ] `ruff format`, `ruff check --fix`, `pytest` all clean.

## Out of scope
- Changing the frozen recall recipe's constants or z-floors.
- Distributed / external vector DBs — stay in-process (sqlite-vec).

## Review log
- 2026-08-25 PO: authored from #075 review (qa O(N)-scan note) + the #035 vec0
  deferral. MVP recall scans every passage under the DB connection; this bounds
  latency + writer contention at scale via a vec0/ANN shadow index. Parked
  (medium): MVP corpora are fine; pull in when recall latency is measured as a
  problem or M11 hardening. The subtle risk is preserving the z-floor semantics
  over an ANN candidate set — the #075 calibration is the guard.
- 2026-09-27 po: RE-RULED on #193's numbers, and still parked — but for a
  different and much narrower reason.
  - **Premise two is dead.** "The scan serializes against the single writer" is
    no longer true: a write issued during a 1.2s recall waited 7.7 ms.
    `Database.connect` lends from a pool and the database is in WAL. Drop the
    contention half of this ticket entirely.
  - **Premise three is real and now has a number**: 0.15 ms per passage per
    query at 384 dims, linear. 20k passages is ~3s; a 1024-dim model is ~2.7x
    that.
  - **But the cost is pure-Python arithmetic, not the scan**, so the first
    remedy is not an index: #194 does the identical math in numpy for 18x, with
    no candidate set and nothing to re-derive about the z-floor — which is the
    subtle risk this ticket has always carried.
  - New trigger: a corpus where recall is still too slow AFTER #194. At 18x,
    that is roughly 500k passages in one tree's scope. Pull this in when
    somebody has one and says so — and then the z-over-a-candidate-set question
    gets the design attention it deserves, instead of being paid for by a
    corpus that never needed it.
