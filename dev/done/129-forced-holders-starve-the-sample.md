---
id: 129
title: The forced-member sample preference starves past SAMPLE_SIZE holders
priority: low
size: small
depends_on: [113]
spec_refs: [build-order.md#T37]
found_by: qa while verifying #113 on 2026-09-21
---

## Context
#113 gave `monitor.sample` a `prefer` list so clusters holding a force-assigned
member jump the bounded per-batch round-robin. The preferred half is taken in
sorted node-id order and is NOT rotated by the batch seed, so once more than
`SAMPLE_SIZE` (32) clusters hold a forced member, the same 32 lowest ids are
re-checked on every batch for ever and the rest are never re-measured:

```
49 forced holders, k=32
seed 1 == seed 2 == seed 99   -> True        (the batch clock stops rotating)
never sampled: 33, 34, 35, 36, 37, 38, 39, 40, ...
```

## Description
Rotate the preferred slice by the batch seed the same way the remainder is
rotated, so every forced holder is re-measured within a bounded number of
batches. One expression in `monitor.sample`; the determinism property the
existing tests assert must survive (same seed -> same pick).

## Why this is not urgent
Repair does not depend on the sample: `repair._needs_migrate` iterates EVERY
cluster from `store.node_centroids` and reads `forced_members` directly, so a
starved holder is still visited and its pioneer still migrates. What starves is
the misfit COUNT refresh, which feeds the rate-based path and the settle
trigger — and a newly forced member's cluster is dirty in the batch that forced
it, so it is always measured at least once. This is a staleness bound, not a
correctness hole, and it only bites above 32 forced holders.

## Acceptance criteria
- [ ] With more forced holders than `SAMPLE_SIZE`, successive batch seeds cover
      every holder within a bounded number of batches (a test asserts the union
      over N consecutive seeds).
- [ ] The existing determinism and boundedness properties still hold.
- [ ] `ruff format`, `ruff check --fix`, `pytest` clean.

## Review log
- 2026-09-21 qa: filed while verifying #113; not blocking it, since #113's own
  acceptance criteria hold without this and repair reaches every holder anyway.

## Review log (dev)
- 2026-09-22 dev: implemented and committed. All three criteria.

  The preferred slice now rotates with the batch clock, exactly as the remainder
  always did — one `_rotate` helper used for both, so the two halves cannot
  drift apart again.

  **The bound is derived, not tuned.** The window advances one holder per batch,
  so covering a pool of P with a window of k takes P - k + 1 batches: 49 holders
  and SAMPLE_SIZE 32 gives 18. The test asserts coverage at exactly that, AND
  that one batch short leaves someone out — so it pins the bound rather than
  merely observing that coverage eventually happens.

  Below the cap nothing rotates and every holder is checked every batch, which
  is #113's shipped behaviour and is separately pinned.

  Mutations: sorted order (the starvation) fails 1, ignoring the clock fails 1.
  Determinism and boundedness hold.

  Gate clean: `ruff format`, `ruff check --fix`, `pytest` **957 passed**.

## Review log (qa)
- 2026-09-22 qa: **PASS — to po-review.** All three criteria met.

  **The bound is derived, and the test pins it from both sides** — coverage at
  P - k + 1 batches, and NOT at one fewer. A test that only asserted "eventually
  covered" would pass a rotation that crawled, and this one would fail it. One
  `_rotate` for both halves means they cannot drift apart again, which is how
  the bug existed.

  Mutations: sorted order fails 1, ignoring the clock fails 1, and one of mine —
  a window one short — fails 4.

## Review log (PO)
- 2026-09-22 PO: **PASSES — closed to done.** A starvation that only appears
  past 32 forced holders is exactly the kind of bug a growing corpus finds after
  it matters, and the fix costs one helper shared by both halves.
