---
id: 072
title: recall vector leg — path-blended similarity, z-scored, z >= 3.5 floor (T26.1)
priority: high
size: medium
depends_on: [069]
spec_refs: [build-order.md#T26.1, how-hrono-works.md]
---

## Context
The first recall retrieval leg. Ranks passages (source + brief, #069/#071) by the
same path-blended similarity used for clustering, converts to z-scores against
the query's OWN full score distribution, and qualifies a passage at **z >= 3.5**.
The recipe is FROZEN (how-hrono-works.md) — bake the constants, do not expose
them.

## Description
- Embed the query (content) and score every passage by the path-blended
  similarity `(1-a)*sim(q, content) + a*sim(q, path)`, a = 0.5 (#039) — reuse the
  blend identity; the query has content only (no path term of its own, so blend
  the query content against each passage's content and path components per the
  recipe).
- Convert raw scores to z-scores over the QUERY's full passage score distribution
  (mean/std of all scored passages for this query), not a global constant.
- Qualify a passage iff its vector z >= **3.5** (baked). Return the qualified
  passages with their z (for #073's vector-support check and #074's fusion rank).
- Deterministic for a fixed query + index.

## Acceptance criteria
- [ ] The leg scores passages by the a=0.5 path-blended similarity and z-scores
      them over the query's own distribution.
- [ ] Only passages with z >= 3.5 qualify; the z is returned for downstream use.
- [ ] Constants (a=0.5, z-floor 3.5) are baked, not config.
- [ ] A planted near-duplicate of the query qualifies; unrelated passages do not
      (regression-grade test on a synthetic index).
- [ ] `ruff format`, `ruff check --fix`, `pytest` all clean; work committed.

## Out of scope
- The keyword leg (#073), fusion (#074), endpoint (#075).
- ANN indexing / speed — correctness first; a vec0 shadow index is a later perf
  concern (noted on #035).

## Review log
- 2026-08-24 PO: authored as T26.1. Frozen recipe: a=0.5 path-blend, z-score over
  the query's own distribution, qualify at z>=3.5. Returns z for #073/#074.
- 2026-08-25 dev: DONE, committed 813206d, handoff to qa. `recall/vector_leg.py`
  `search(conn, query_vec, model_name)`: scores every embedded passage (source +
  brief) by the a=0.5 path-blended similarity as `dot(combine(q,q),
  combined_vector(passage))` (query content in both blend slots recovers
  (1-a)*sim(q,content)+a*sim(q,path) from one dot, reusing #039), z-scores over
  the QUERY's own full distribution, and returns (passage_id, z) for z >= 3.5,
  best first. Constants baked (ALPHA via blend, Z_FLOOR=3.5). Query embedding is
  the endpoint's job (#075) — the leg is pure scoring, deterministic + testable.
  Verified: ruff clean; pytest 482 passed / 1 skip (+3: a planted near-duplicate
  clears z>=3.5 while 20 orthogonal passages do not; empty index -> no hits; floor
  baked). Returns z for #073's vector-support check and #074's fusion.
- 2026-08-25 qa: PASS (commit 813206d) -> po-review. Tree CLEAN at handoff.
  Verified every dimension:
  - The load-bearing blend identity is EXACT (checked numerically to 1e-9):
    `dot(combine(q,q), combined_vector(passage)) == 0.5*sim(q,content) +
    0.5*sim(q,path)`, so the leg score is precisely the a=0.5 path-blended
    similarity, reusing #039 rather than re-deriving it. Elegant.
  - z-scored over the QUERY's own full passage distribution (population mean/std),
    qualify at z >= 3.5, z returned best-first for #073/#074. std=0 and empty-index
    edges return () cleanly. Constants baked (Z_FLOOR=3.5, ALPHA via combine).
  - Regression test plants a near-duplicate that clears z>=3.5 while ~20
    orthogonal passages do not; empty-index and floor-baked tested.
  - ruff clean; full suite 482 passed / 1 skip; atomic Conventional Commit.
  Characteristic to note for PO (NOT a defect — it's the frozen recipe): z-scoring
  over the query's own distribution caps the max achievable z at ~sqrt(N-1), so a
  corpus smaller than ~13 passages can never produce a vector-leg hit regardless
  of match quality. This is by design (precision-favoring) and is covered at the
  fusion layer by the keyword leg (#073) + empty->explore fallback (#074); worth
  keeping in mind when calibrating recall on tiny corpora (#075).
  (Pre-existing unrelated `.gitignore` edit remains uncommitted.)
- 2026-08-25 PO review: PASS -> done. Read vector_leg.py at the commit and gated
  it in an isolated worktree (tree carried #073 WIP modifying vector_leg.py +
  untracked keyword_leg.py): ruff clean, 12 recall tests pass. The blend identity
  is exact and elegant — score = `dot(combine(q,q), combined_vector(passage))`
  equals `(1-a)*sim(q,content)+a*sim(q,path)`, reusing #039 rather than
  re-deriving; z-scored over the QUERY's own population distribution; qualify at
  z>=3.5; std=0 and empty-index return () cleanly; constants baked (Z_FLOOR=3.5,
  ALPHA via combine). All acceptance criteria met. Closed. Threaded qa's
  characteristic into #075: z-over-own-distribution caps max z at ~sqrt(N-1), so
  the calibration corpus must have >= ~13 passages or the vector leg can never
  fire (by design) — size the calibration for that, and exercise keyword-only +
  empty->explore on tiny inputs.
