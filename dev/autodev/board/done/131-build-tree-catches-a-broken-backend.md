---
id: 131
title: build_tree reads a BROKEN clusterer as "the current top is the root"
priority: medium
size: small
depends_on: [112]
spec_refs: [build-order.md#T29]
found_by: qa while verifying #112's fix on 2026-09-21
---

## Context
`summarize/build_tree.py:70` catches `ClusterError` broadly:

```python
try:
    cluster_briefs(...)
except ClusterError:
    break  # too sparse to cluster near the root -> current top is root
```

This is the same defect qa found in `cluster/op.py` at #112, one level up.
`build_clusters` raises a plain `ClusterError` when the reduction fails, when
the clusterer fails, when it produces no clusters and when the backend is not
installed (`cluster/build.py:108,146,164,171,179`). Any of those, at any level,
is silently read as "this level is the root" — so a broken backend halfway up
produces a TRUNCATED tree that reports success, rather than a failed job.

The comment on that line says "too sparse", which is now expressible: #112
introduced `cluster.TooFewPoints(ClusterError)` for exactly the one refusal a
caller may answer by collecting.

## Description
Narrow the catch to `TooFewPoints`. Every other `ClusterError` should fail the
`build-tree` run, the way it did before the ladder existed. One-line change plus
its test.

## Why it was not folded into #112
#112 owns the LEAF decision and is closed on its own criteria; this is the
upper-level caller, with its own failure shape (a truncated tree rather than a
collapsed one) and its own test. Same class, different blast radius — and F16
is the evidence that a half-built tree is its own kind of wrong.

## Acceptance criteria
- [ ] `build_tree` catches only `TooFewPoints` when deciding "the current top is
      the root".
- [ ] A test proves a `ClusterError` from the backend at an upper level fails
      the run rather than truncating the tree.
- [ ] The existing "too sparse near the root" behaviour is unchanged (its tests
      still pass).
- [ ] `ruff format`, `ruff check --fix`, `pytest` clean.

## Review log
- 2026-09-21 qa: filed while verifying #112's fix. Not blocking #112 — it is
  pre-existing, predates the ladder, and #112 is what makes the fix expressible.

## PO triage 2026-09-21 — promoted to `todo`, priority confirmed `medium`

First off the list, and I said so when it was filed. It is the same defect #112
closed one level down, with a worse blast radius: `build_tree.py:70` catches
`ClusterError` broadly, so a reduction that FAILED, a clusterer that failed, or
a backend that is not installed is read as "the current top is the root" — a
TRUNCATED tree reported as success. #112 created `TooFewPoints` precisely so the
distinction is expressible, and this is a one-line narrowing plus its test.

A tree that stops early and says nothing is the same class of lie as #112's
collapsed one: an operator cannot act on a map they have no reason to distrust.

## Review log (dev)
- 2026-09-21 dev: implemented and committed as `7c7ed38`. Both criteria.

  One-line narrowing: `build_tree` catches `TooFewPoints` instead of
  `ClusterError`, so the ladder declining to reduce still means "the current top
  is the root" and every other backend failure now fails the run.

  **The test harness was hiding it, which is the part worth recording.**
  `raising_build` — the fake used by every "too sparse" test — raised a plain
  `ClusterError`, so the two cases were literally the same object in the tests.
  Splitting it into `raising_build` (`TooFewPoints`: the ladder declines) and
  `broken_build` (`ClusterError`: the backend breaks) is what let either be
  asserted. A fake that cannot tell two cases apart guarantees the code need not
  either.

  Tests: a broken clusterer raises out of `build_tree`, and the ladder declining
  still stops the climb with `_collect_root` parenting the survivors under one
  root (`{0: 12, 1: 1}`) — the behaviour that must NOT change. Mutations:
  restoring the broad catch fails 1, removing the catch fails 3.

  Gate clean: `ruff format`, `ruff check --fix`, `pytest` **886 passed**.
- 2026-09-21 qa: **PASS — to po-review.** Both criteria met.

  Verified: restoring the broad catch fails 1; removing the catch entirely fails
  3; and one of mine — letting `TooFewPoints` propagate instead of breaking —
  fails 3, so the stop is pinned in both directions.

  **Splitting the test fake into `raising_build` and `broken_build` is the fix
  behind the fix.** The two cases were literally the same exception object in
  the harness, so no test could have told them apart however the production code
  was written. A fake that cannot distinguish two cases guarantees the code need
  not either — worth remembering beyond this ticket.

  The kept behaviour is asserted concretely (`{0: 12, 1: 1}` — the climb stopped
  and `_collect_root` parented the survivors), not just "no exception".

## Review log (PO)
- 2026-09-21 PO: **PASSES — closed to done.** Both criteria met.

  This is #112's defect at the altitude where it does more damage: a truncated
  tree reported as success. #112 created `TooFewPoints` precisely so the two
  could be told apart, and the narrowing here is the second half of that work.

  **The finding worth carrying forward is about the test fake, not the code.**
  `raising_build` raised a plain `ClusterError`, so "the ladder declines" and
  "the backend broke" were the same object in every test — no test could have
  distinguished them however the production code was written. A fake that
  cannot tell two cases apart guarantees the code need not either. That is a
  sibling of the constant-fake lesson from #137 and #084, and three independent
  instances in one week is a pattern: **when a defect survives testing, check
  the fake before the assertion.**

  No new work spun off.
