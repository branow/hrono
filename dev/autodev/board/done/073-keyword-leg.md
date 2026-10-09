---
id: 073
title: recall keyword leg — BM25 z-scored, qualifies only at z >= 6.0 with vector support z >= 3.0 (T26.2)
priority: high
size: medium
depends_on: [070, 072]
spec_refs: [build-order.md#T26.2, how-hrono-works.md]
---

## Context
The second recall leg, over the FTS5 index (#070). BM25 alone is dangerous: its
background distribution is stopword matches, so meaningless text can score high —
so a keyword hit **NEVER qualifies alone**. The frozen recipe (how-hrono-works.md):
BM25 over path+body with query terms OR-ed, z-scored over the matched set, and a
passage qualifies only at **z >= 6.0 AND vector support z >= 3.0** (from #072's
vector z for the same passage).

## Description
- Query the FTS5 index (#070) with the question's terms OR-ed; rank matches by
  BM25; z-score over the MATCHED set (not the whole corpus).
- SANITIZE the query (from #070 review): `fts.search` passes the string straight
  to FTS5 `MATCH`, so a raw user question with FTS5 operators / unbalanced quotes
  raises OperationalError. Tokenize the question into bare terms and OR them (e.g.
  quote each term or strip FTS5 syntax) — build a valid MATCH expression; never
  pass the raw question. Empty/all-stopword query -> no matches, not a crash.
- A passage qualifies iff keyword z >= **6.0** AND its vector-leg z (#072) for the
  same passage is >= **3.0**. A high BM25 with no vector support does NOT qualify.
- Return qualified passages with their keyword z for #074's fusion rank.
- Baked constants (6.0, vector-support 3.0); frozen recipe, not config.

## Acceptance criteria
- [ ] The leg z-scores BM25 over the matched set and qualifies a passage only at
      keyword z >= 6.0 AND vector-support z >= 3.0.
- [ ] A stopword-heavy high-BM25 passage with no vector support is REJECTED
      (regression test proves keyword-alone never qualifies).
- [ ] A genuine keyword+semantic match qualifies.
- [ ] Constants baked, not config.
- [ ] `ruff format`, `ruff check --fix`, `pytest` all clean; work committed.

## Out of scope
- The vector leg (#072) and fusion (#074).
- Query expansion / synonyms / stemming beyond FTS5 defaults.

## Review log
- 2026-08-24 PO: authored as T26.2. Frozen recipe: BM25 z over matched set,
  qualify only at z>=6.0 WITH vector support z>=3.0 (keyword never alone). The
  load-bearing test is "stopword high-BM25 without vector support is rejected".
- 2026-08-25 dev: DONE, committed e1e4682, handoff to qa. `recall/keyword_leg.py`
  `search(conn, query, vector_z)`: tokenises the question into bare terms, quotes
  each as a phrase and ORs them (never passes the raw question to FTS5 MATCH —
  operators/quotes can't crash it; empty/all-punctuation -> no matches), runs
  #070's BM25 search, z-scores relevance (-bm25) over the MATCHED set, and
  qualifies a passage only at keyword z >= 6.0 AND vector-leg z >= 3.0 (baked). A
  high-BM25 stopword match with no vector support NEVER qualifies. Added
  `vector_leg.scores()` exposing the full per-passage vector z-map (support can be
  3.0-3.5, below the leg's own 3.5 qualify floor); `search` filters it.
  Verified: ruff clean; pytest 490 passed / 1 skip (+8: strong+support qualifies,
  strong+no-support rejected [load-bearing], only the supported of two strong
  matches qualifies, no-hits empty, match-expr OR/punctuation, messy-query
  sanitized without crashing, all-punctuation empty). Returns keyword z for #074.
- 2026-08-25 qa: PASS (commit e1e4682) -> po-review. Tree CLEAN at handoff.
  Verified every dimension:
  - The load-bearing "keyword never qualifies alone" is directly tested at the
    boundary: a strong-BM25 passage with vector support z=2.9 (just below 3.0) is
    rejected, and with NO vector hit at all is rejected; only the vector-supported
    of two strong matches qualifies. Qualification is z_keyword >= 6.0 AND
    vector_z.get(id, 0.0) >= 3.0.
  - FTS query sanitization (my #070 note) is fully addressed: `_match_expr`
    extracts bare alphanumeric terms, quotes each as a phrase, and ORs them, so
    FTS5 operators / unbalanced quotes / a query word like "or" cannot inject or
    crash; empty / all-punctuation -> None -> no matches. Tested with a messy
    query and an all-punctuation query (no crash, empty result).
  - Good refactor: `vector_leg.scores()` now exposes the FULL per-passage vector
    z-map (support 3.0 sits below the vector leg's own 3.5 qualify floor, and #074
    fuses on it); `vector_leg.search()` just filters it — vector-leg behavior
    unchanged (its tests still green in the 490).
  - BM25 z-scored over the MATCHED set (relevance = -bm25); std=0 -> (); constants
    baked (Z_FLOOR=6.0, VECTOR_SUPPORT=3.0), not config.
  - ruff clean; full suite 490 passed / 1 skip; atomic Conventional Commit.
  Note for PO (same frozen-recipe characteristic I flagged on #072, stricter
  here): z >= 6.0 over the matched set needs a matched set of ~37+ for any passage
  to reach the floor, so the keyword leg is deliberately very conservative — by
  design (never alone), covered by fusion/explore. (Pre-existing unrelated
  `.gitignore` edit remains uncommitted.)
- 2026-08-25 PO review: PASS -> done. Read keyword_leg.py at HEAD (e1e4682); gated
  in an isolated worktree (tree carried untracked #074 WIP): ruff clean, 20 recall
  tests pass. The load-bearing "keyword never alone" is correct and
  boundary-tested (strong BM25 with vector support z=2.9 rejected, z>=3.0
  qualifies). FTS5 sanitization fully addresses my #070 note — `_match_expr`
  extracts bare alphanumeric terms, quotes each as a phrase, ORs them; empty/
  all-punctuation -> None -> no matches, no crash. Correct subtlety: the vector
  SUPPORT threshold (3.0) sits BELOW the vector leg's own qualify floor (3.5), so
  a non-qualifying vector passage can still support a keyword hit — implemented via
  the new `vector_leg.scores()` full z-map, with `vector_leg.search()` filtering
  it (vector-leg behavior unchanged). Constants baked (6.0, 3.0). All acceptance
  criteria met. Closed. Refined #075's corpus-sizing note to cover BOTH legs'
  fireability (vector ~13+ passages, keyword ~37+ matched set).
