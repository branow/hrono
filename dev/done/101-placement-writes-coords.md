---
id: 101
title: Warm UMAP init can never fire — placement never writes section_coords
priority: medium
size: small
depends_on: []
spec_refs: [build-order.md#T39.2, build-order.md#T34]
found_by: e2e manual QA 2026-09-03 — .e2e/FINDINGS.md F28
---

## Context
`settle` is specified to rebuild with `init = stored coords` (T39.2), via
`cluster/store.py:stored_coords`, which returns `None` unless it has a
coordinate for EVERY section in the build.

## Description
`placement.place` stores membership but no coordinate, so one `update` is enough
to break coverage:

```
 members: 92   coords: 89
 members with no coord: 3
 their paths: ['src/itsdangerous/rotation.py',
               'src/itsdangerous/signer.py', 'src/itsdangerous/signer.py']
```

`stored_coords` then correctly returns `None` and `settle` cold-inits UMAP. Since
settle only runs *because* churn accumulated, and churn means sections were
placed without coords, the warm path can never fire in practice — losing the
layout stability that keeps unchanged content in place and node signatures
matching across rebuilds.

Work: have `placement.place` persist a coordinate for each placed section
(the centroid it joined, or a nearest-neighbour interpolation), or let
`stored_coords` return a partial init with missing rows filled from their
nearest placed neighbour.

## Decision (2026-09-12, dev — technical call, no PO input needed)

`placement.place` writes a `section_coords` row for every section it places,
using the reduced coordinate of the centroid it joined (a placed section has no
UMAP coordinate of its own; the centroid is the honest approximation and keeps
warm-init's alignment). A force-assigned or drained chunk gets the same
treatment. `stored_coords` stays strict — with this fix it will simply never see
a partial set after a normal update.

## Acceptance criteria
- [ ] After an `update`, `section_coords` covers every member.
- [ ] A settle after an update uses the warm init (assert the init argument is
      not None), and its membership delta stays small over an unchanged corpus.
- [ ] `ruff format`, `ruff check --fix`, `pytest` clean.

## Review log
- 2026-09-21 dev: started; moved to in-progress (batch with #105, #110, #113,
  #112).
- 2026-09-21 dev: implemented and committed.

  **One sweep after the batch, not a write per placement site — a deliberate
  deviation from the Decision block, stated here.** The Decision said
  `placement.place` writes the coordinate. Placement is not the only way a
  section gains membership during an update: `incubator.age` force-assigns and
  `incubator.drain` mints whole clusters, both AFTER `place` returns and under
  their own locks (`tree/update.py:125-127`). A write inside `place` would have
  left exactly those members uncovered, and `stored_coords` is all-or-nothing —
  one uncovered member and the warm path is gone again. So
  `store.backfill_coords(tree, model)` runs once at the end of `_update_source`,
  after the drain, and the acceptance criterion ("`section_coords` covers every
  member") is what it asserts directly.

  **What a placed section inherits.** The mean of its cluster's members that DO
  have a coordinate — the honest approximation, and the one that keeps it inside
  the layout it joined. A cluster where nobody has one (a drained pool is the
  real case) takes the reduced centroid of the nearest cluster that does, by
  combined-vector dot product: the same approximation one level out. With no
  coordinates anywhere there is no layout to preserve, so nothing is written and
  `stored_coords` correctly returns None — a first build still inits fresh.

  `stored_coords` stays strict, as the Decision requires.

  Tests (5 new, 787 total): after a real `update` over a built tree every
  level-0 member has a coordinate (and the SQL asserts it as a LEFT JOIN count,
  so it cannot pass by looking at the wrong rows); a `cluster` rebuild after
  that update receives a non-None `init`; plus three store-level tests for the
  inherit, the nearest-cluster fallback, and the no-layout case.
  Mutations: removing the backfill call fails 2, removing the fallback fails 1,
  taking the FURTHEST cluster instead of the nearest fails 1. A fourth mutation
  (dropping the `if not covered` fast path) proved it was a no-op against the
  `if not anchors` guard below it, so I removed the redundant guard rather than
  writing a test for two ways of saying the same thing.

  Gate clean: `ruff format`, `ruff check --fix`, `pytest` **787 passed**.
- 2026-09-21 qa: **PASS — to po-review.** Both criteria met, and the deviation
  from the Decision block is the right call, well argued, and load-bearing.

  **The deviation is correct, not a shortcut.** The Decision said `place` writes
  the coordinate. `incubator.age` and `incubator.drain` both add members AFTER
  `place` returns (`tree/update.py:125-127`), and `stored_coords` is
  all-or-nothing — one uncovered member and the warm path is gone again. A write
  inside `place` would have left exactly those uncovered and the ticket would
  have looked fixed while staying broken. The single post-batch sweep is what
  makes the criterion ("covers every member") true rather than nearly true.

  **Verified independently:**
  - The coverage assertion is a LEFT JOIN count over level-0 members, so it
    cannot pass by counting the wrong rows, and it is asserted BEFORE the update
    too — proving the full build starts covered and the update is what used to
    break it.
  - The fallback chain is right: own cluster's mean -> nearest cluster's mean ->
    nothing. The last case matters: a first build has no layout to preserve, so
    writing an invented coordinate would be worse than `stored_coords` returning
    None. Tested.
  - Dimension safety: `_mean` reads `len(coords[0])` and indexes the rest, which
    would break on mixed dims — but `replace_tree` deletes a tree's coords
    before writing new ones, so within a tree they are uniform. Checked rather
    than assumed.
  - **Real UMAP accepts the duplicated init rows the backfill produces.** This
    was my main concern: inherited coordinates are exact duplicates of a cluster
    mean, and a warm init that crashed or degraded would make this ticket worse
    than the bug. Measured against the real recipe on a planted 60-vector corpus
    with 6 added sections inheriting their cluster's mean:
    ```
    unchanged sections keeping their label, WARM : 55 / 60
    unchanged sections keeping their label, COLD : 55 / 60
    clusters before/after: 4 -> 4
    ```
    No crash, and stability no worse than cold. Filed **#130** for the
    stability regression test that would pin this properly — not blocking,
    because criterion 2 names the check it wanted ("assert the init argument is
    not None") and dev made exactly that.
  - Mutations re-run by me: removing the backfill call fails 2, removing the
    nearest-cluster fallback fails 1, taking the furthest instead of the nearest
    fails 1. Dev's removal of the redundant `if not covered` guard is right —
    it was provably a no-op against the `if not anchors` guard, and two ways of
    saying the same thing is worse than one.

  **One note, not blocking:** the sweep runs inside `_update_source`, so a run
  over three CHANGED sources sweeps three times. Each sweep is two bounded
  queries plus the writes it actually needs, and the later sweeps find nothing
  to write, so it is a small constant, not a scaling problem. Worth moving to
  `update` after the source loop if that function is ever touched again.

  Gate re-run by me: 789 passed, ruff clean. Commit atomic and conventional.

## Review log (PO)
- 2026-09-21 PO: **PASSES — closed to done.** Both criteria met.

  I accept the deviation from the Decision block and would have made the same
  call. `stored_coords` is all-or-nothing, so "write it where placement writes
  membership" was only correct if placement were the only writer — and it is
  not: the incubator's age and drain both add members after `place` returns.
  A fix that left those uncovered would have looked like a fix and changed
  nothing, which is the worst outcome available here. The criterion I wrote
  ("covers every member") is what the sweep asserts directly.

  The fallback chain is the part I want on the record: own cluster's mean, then
  the nearest cluster's mean, then **nothing**. The third case is a product
  decision as much as a technical one — a first build has no layout to preserve,
  and inventing a coordinate to make `stored_coords` non-empty would have made
  the warm path fire on a fiction. Declining to write is the honest answer.

  **The measurement matters more than the mechanism here**, so I am glad qa took
  it: real UMAP accepts the duplicated init rows this produces, and stability is
  no worse than cold (55/60 either way on a planted corpus). That is the
  difference between "warm init now fires" and "warm init now fires and is
  safe". It is not yet the difference between "safe" and "worth having" — the
  benefit is still unmeasured on real data. **#130** carries that and stays
  `low`: the next end-to-end run over a real corpus is the natural place to get
  the number, and if it shows no stability gain at all, the honest follow-up is
  to ask whether warm init earns its complexity, not to defend it.

  No new work spun off beyond #130.
