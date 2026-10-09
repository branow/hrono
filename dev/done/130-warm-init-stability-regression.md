---
id: 130
title: No regression test measures what warm init is FOR — layout stability
priority: low
size: medium
depends_on: [101]
spec_refs: [build-order.md#T39.2]
found_by: qa while verifying #101 on 2026-09-21
---

## Context
#101 restored the warm path: after an update every member has a coordinate, so
`stored_coords` stops returning None and `settle` re-inits from the prior
layout. Its tests assert the mechanism — coverage, and that `init` arrives
non-None — which is what #101's acceptance criteria literally ask for. Nothing
asserts the PROPERTY the warm path exists to deliver: that unchanged content
keeps its place across a rebuild.

I measured it by hand against the real recipe while verifying #101, on a planted
60-vector corpus with 6 sections added and each inheriting its cluster's mean
coordinate (exactly what the backfill writes):

```
unchanged sections keeping their label, WARM init : 55 / 60
unchanged sections keeping their label, COLD init : 55 / 60
cluster count before/after: 4 -> 4
```

So the inherited coordinates are safe — real UMAP accepts duplicate init rows,
and stability is no worse than cold. But "no worse than cold" is also the
measurement that says the benefit is unproven, and neither number is pinned.

## Description
Add one regression test over the REAL recipe (not an injected build seam, per
#108) that plants a corpus, builds it, adds a few sections with inherited
coordinates, rebuilds warm, and asserts unchanged sections keep their topic
above some floor. Pick the floor from a measurement, not from taste, and record
the measurement in the test so a future reader knows what it is defending.

Note it is a slow test (~20 s of real UMAP per build); mark it accordingly if
the suite grows a slow lane.

## Acceptance criteria
- [ ] A test drives the real recipe and asserts a stability floor for unchanged
      sections across a warm rebuild.
- [ ] The floor's provenance (the measured number) is stated in the test.
- [ ] `ruff format`, `ruff check --fix`, `pytest` clean.

## Review log
- 2026-09-21 qa: filed while verifying #101. Not blocking it: #101's criterion
  names the check it wanted ("assert the init argument is not None") and dev
  made it; this is the deeper property behind that criterion, and it deserves
  its own card rather than a retrofit.
- 2026-09-23 dev: implemented as `tests/cluster/test_warm_stability.py`, over
  the real recipe and the real warm path (build -> add -> place -> backfill ->
  rebuild) through the `cluster` op. Floor 0.90 from a measured 1.000.

  The measurement the ticket asked for came back negative, and the test says so
  in its own docstring rather than implying a guard it does not have. Stability
  on this fixture is 1.000 under EVERY mutation of the warm path — misaligned
  coords, zeroed coords, coords times a thousand, no init at all — and under a
  broken recipe too (min_cluster_size 5 -> 20, n_components 25 -> 2). On a
  harder corpus (240 points, 8 groups, spread 0.3-0.5) warm and cold agree
  inside the noise and warm is not reliably better: 0.850 vs 0.863 on one seed,
  0.950 vs 0.950 on the next, and a scrambled init beat both on a third.

  Mutations that DO kill the test, each in the code it names:
  - `backfill_coords` returning 0 without writing -> fails (coverage).
  - `stored_coords` returning None despite full coverage -> fails (the warm
    path never fires).
  - a section dropped from the build's input -> fails (the map loses a member).

  For PO: this is the evidence to decide whether warm init earns its keep.
  Nothing here argues for removing it — it is spec'd (T39.2), it is free, and
  the inherited coordinates are demonstrably safe — but its benefit is now
  measured as indistinguishable from cold, not merely unproven.

- 2026-09-23 qa: verified. Re-ran two of dev's stated mutations (`stored_coords`
  returning None despite full coverage; `backfill_coords` returning 0 without
  writing) — both kill the test — and tried one dev did not: misaligning the
  members to their section ids inside `op.cluster`. It SURVIVES, and cannot do
  otherwise: the agreement metric compares two builds that are both mutated, so
  any fixed permutation applied to both is invisible to it. Worth knowing; not
  a defect in this ticket.

  The ticket's acceptance criteria are met (a floor over the real recipe, its
  provenance stated, gate clean) and the test drives the REAL backend through
  the warm path (#108), not an injected seam.

  Passing to PO with dev's negative result, because it is a product question,
  not a code one: the floor cannot distinguish warm init from cold or from a
  broken recipe, and on a harder corpus warm is not reliably better than cold.
  The test as written guards the warm path's MECHANISM (coverage, warm firing,
  no section lost) and says so; nobody should later read it as evidence that
  warm init pays for itself. The PO should decide whether T39.2's warm init
  stays on that basis.

- 2026-09-23 po: CLOSED, and the open question DECIDED: warm init stays.

  The measurement says its benefit is indistinguishable from cold on every
  corpus we can pin. That is an argument for not INVESTING further in it — not
  for removing it. It is spec'd (T39.2), it costs nothing at run time, the
  inherited coordinates are demonstrably safe, and a layout that drifts freely
  between rebuilds would make the stored graph coordinates meaningless to any
  later dashboard. Nobody should reopen this without a new measurement on a
  real corpus; the test's docstring now carries the evidence so the next reader
  starts where we finished.

  The test earns its place for what it does pin: the warm path's mechanism end
  to end (backfill covers every new section, `stored_coords` goes warm, no
  section is lost in the rebuild). No new ticket.
