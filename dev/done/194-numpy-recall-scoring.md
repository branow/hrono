---
id: 194
title: score recall's vector leg in numpy — the same math, 18x
priority: medium
size: medium
depends_on: [193, 075, 102, 127]
spec_refs: [build-order.md#M11]
---

## Context
#193 measured it: `vector_leg.scores` costs 0.15 ms per passage per query at
384 dims, linear, and the cost is **pure-Python vector arithmetic** — one
768-wide `combine` and three dot products per passage, in interpreted loops.
Replacing every per-passage query with one bulk read saves 9%; doing the
identical arithmetic in numpy is **18x** (1.215s -> 0.066s at 8000 passages).

This is the remedy #077 should have had first. An ANN index changes WHICH
passages are scored, and the frozen recipe's z is taken over the query's own
full distribution — so a candidate set raises a real question about what the
z-floor then means. This changes nothing about which passages are scored or how.

## The dependency call
**numpy moves to the base dependencies.** Today it sits under the `cluster`
extra because umap and hdbscan need it. The extras exist to keep torch (`embed`)
and numba/llvmlite (`cluster`) out of a lean install — that comment is in
`pyproject.toml` — and numpy is neither. Recall is the one O(N) loop in a
user-facing request and it works with no extra installed at all (a remote
embedding provider needs neither). One implementation, not an optional fast
path: two versions of a frozen recipe is two things to keep identical, and the
lean install would get different float rounding in a ranked result.

## Description
- The blend definition stays in `cluster/blend.py`, where `combine` already
  lives: add the stacked form beside it rather than re-deriving the weights in
  the recall module.
- `vector_leg.scores` reads the vectors it needs, stacks them once, and takes
  two matrix-vector products. The z math, the two views, the floors and the
  fallbacks are untouched.
- Passages whose vectors are missing are skipped exactly as now.

## Acceptance criteria
- [x] The z-scores match a plain, obvious reference loop written in the TEST
      (not a second production path) to within float tolerance, on a planted
      corpus with a known answer.
- [x] The #075 calibration still passes unchanged — planted answer recovers,
      strict miss still explores.
- [x] A scoped recall (#166) still scores only its tree's passages, and its z
      is still measured against that population.
- [x] A passage with no content or no path vector is still skipped.
- [x] Measured: the new time at 8000 passages, recorded in this ticket.
- [x] `ruff format`, `ruff check --fix`, `pytest` clean.

## Review log
- 2026-09-27 po: authored from #193's measurement, ahead of #077 and instead of
  it for now.
- 2026-09-27 dev: `vector_leg.scores` reads every vector for the model once,
  stacks the in-scope passages into two matrices, and takes two matrix-vector
  products. numpy moved to the base dependencies with the reason in
  `pyproject.toml` beside it.
  - **Measured, same machine and script as #193:** 8000 passages 1.203s ->
    **0.120s**; 2000 0.299s -> 0.024s; 500 0.073s -> 0.006s. About 0.011 ms per
    passage, down from 0.150.
  - The blend definition stayed in `cluster/blend.py`: `blend_weights` (what
    `combine` scales each half by) and `similarity_weights` (their squares,
    which is what a DOT of two combined vectors applies per view). Recall reads
    the second rather than re-deriving `sqrt(1 - alpha)` in a third place.
  - Mutations killed: the two views collapsed to the blend; rows not
    unit-normalised; a passage missing a path vector scored anyway; scope
    ignored; the dot weights un-squared; `blend_weights` swapped.
  - **SURVIVING mutation, recorded not papered over:** using `blend_weights`
    instead of `similarity_weights` inside `scores` changes nothing observable.
    At the baked ALPHA of 0.5 the two weights are EQUAL, so either choice
    scales every score by one constant — and a z-score is invariant under that.
    It is the "property held by something else" shape, and the something else
    is the constant. Killing it would mean giving `scores` an alpha parameter
    for a baked value, which is the speculative generality CLAUDE.md forbids;
    instead the exponent is pinned where it IS observable, in
    `similarity_weights(0.25)`.
  - **A real flake, found and fixed, not called a flake.** The suite failed
    twice on two different `test_dry_run` tests and passed eight runs of that
    file in isolation. The mechanism: the worker polls the SAME adopted sqlite
    connection those fixtures write through, and two threads interleaving
    transactions on one connection fails wherever the poll happens to land.
    Five fixtures now stop the worker, as `test_ui_triage` and the jobs tests
    already did, and the rule is in `CONTRIBUTING.md`. Three consecutive full
    runs green afterwards.
  - Driven against REAL weights (`all-MiniLM-L6-v2`) through the live endpoint:
    "how do I rotate the master key" answered in 124 ms with
    `crypto/rotate.md` top, and an off-topic question still returns the explore
    message. The #075 calibration in `tests/recall/test_engine.py` is unchanged
    and green.
  - Gate: 1404 passed, 2 skipped.
- 2026-09-27 qa: verified. The test that carries the weight is the equivalence
  one: the reference loop lives in the TEST as the statement of the arithmetic,
  so if the two ever disagree the question "which is wrong" can still be asked
  about a recipe that was calibrated by measurement rather than derived.
- 2026-09-27 po: accepted, including the dependency call. numpy is in the base
  install now; the reason is in `pyproject.toml` where the next person deciding
  what "lean" means will read it. This is what #193 was for — the 18x was
  available the whole time behind a ticket that proposed an index.
