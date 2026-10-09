---
id: 070
title: FTS5 full-text index over passage path + body for the keyword leg (T25.2)
priority: high
size: medium
depends_on: [032]
spec_refs: [build-order.md#T25.2, how-hrono-works.md]
---

## Context
Recall's keyword leg ranks passages by BM25 over an FTS5 full-text index of
passage **path + body** (how-hrono-works.md). This ticket builds and maintains
that index; the leg query + z-floor is #073. sqlite-vec is already in the stack;
FTS5 ships with SQLite.

## Description
- Create an FTS5 virtual table over passages indexing `path + body` (the path
  contributes the terms bodies don't say — a translation file's language, a
  license's nature). BM25 is FTS5's default ranking.
- Populate it from the passage store and keep it in sync when passages are
  (re)written by `split` (#032) — a changed/removed passage updates/removes its
  FTS row. Keep it a forward-only migration.
- Structure paths (`sp:`) are deliberately NOT indexed (how-hrono-works.md: the
  names they contain already appear in bodies; the rest is noise) — index the
  address path + body only.
- Deterministic; no external service.

## Acceptance criteria
- [ ] An FTS5 index over passage path + body exists and returns BM25-ranked
      matches for OR-ed query terms.
- [ ] The index stays consistent with the passage store across split re-runs
      (add / change / remove); a removed passage leaves no orphan FTS row.
- [ ] `sp:` structure paths are not indexed; address path + body are.
- [ ] `ruff format`, `ruff check --fix`, `pytest` all clean; work committed.

## Out of scope
- The keyword leg query, z-score, and z>=6.0 / vector-support>=3.0 floor (#073).
- Vector index (#069) and fusion (#074).

## Review log
- 2026-08-24 PO: authored as T25.2. FTS5 over passage path+body (BM25), kept in
  sync by split; sp: paths excluded per the recipe. Feeds the keyword leg (#073).
- 2026-08-25 dev: DONE, committed e675135, handoff to qa. Added migration 0015
  `passages_fts` (FTS5 virtual table over path + body; passage_id + source
  UNINDEXED) + `hrono/recall/fts.py` (clear_source / index_passage / search with
  bm25). Wired into split_op: clears the source's FTS rows then re-indexes each
  passage (path + decoded body) in the same txn, so the index is rebuilt on every
  re-split and never drifts. `insert_passage` now returns its id (for the FTS
  row). sp: structure paths are NOT indexed — only address path + body (schema).
  Verified: ruff clean; pytest 475 passed / 1 skip (+5: one FTS row per passage,
  OR-ed terms return BM25-ranked hits best-first, path-only terms match (path
  indexed), re-split is consistent with no duplicate rows, and change+remove via
  re-sync leaves no orphans — removed body term gone, new term present). search()
  feeds #073's keyword leg.
- 2026-08-25 qa: PASS (commit e675135) -> po-review. Tree CLEAN at handoff.
  Verified every dimension:
  - Sync is atomic and correct: split clears the source's FTS rows and re-indexes
    each passage (path + decoded body) in the SAME `with conn:` transaction as the
    passage store, so the index is rebuilt per re-split and cannot drift.
    `insert_passage` now returns its id for the FTS row (minimal change).
  - Consistency across add/change/remove proven over a REAL mutated repo: the test
    removes one file, changes another, re-syncs + re-splits, and asserts the
    removed body term is gone, the new term present, and FTS row count == passage
    count (no orphans). Plus one row per passage, OR-ed body terms BM25-ranked
    best-first, and path-only terms match (path indexed).
  - Migration 0015 indexes path + body only; passage_id/source are UNINDEXED
    bookkeeping; `sp:` structure paths are deliberately NOT indexed, per the recipe.
  - Security: `search` uses a parameterized `MATCH ?` (no SQL injection); BM25 is
    FTS5's default, ordered best (lowest) first.
  - ruff clean; full suite 475 passed / 1 skip; atomic Conventional Commit.
  Note for #073 (non-blocking): `search(match)` passes the query straight to FTS5
  MATCH, so #073's keyword leg must tokenize/sanitize the user query into a valid
  FTS5 expression (a raw query with FTS5 operators or unbalanced quotes would raise
  an OperationalError) — that is #073's scope, not a defect here. (Pre-existing
  unrelated `.gitignore` edit remains uncommitted.)
- 2026-08-25 PO review: PASS -> done. Read fts.py + migration 0015: FTS5 over
  path + body (passage_id/source UNINDEXED bookkeeping), `sp:` paths excluded per
  the recipe, kept in sync by split (clear_source then re-index each passage in
  the SAME txn -> no drift/orphans), parameterized `MATCH ?` (no injection), BM25
  best-first. Gated #070's commit (e675135) in an ISOLATED worktree because the
  live tree carried uncommitted #071 WIP (brief_passages.py with 5 ruff E501s +
  edits to cluster/store.py, summarize/brief.py, summarize/store.py) — in the
  worktree ruff is clean and the full suite is 475 passed / 1 skip. #070's own
  commit is clean; the ruff failure was entirely #071's WIP, not this ticket. All
  acceptance criteria met (BM25 over path+body, add/change/remove consistency via
  split, sp: excluded). Closed. Threaded qa's note into #073 (the keyword leg must
  tokenize/sanitize the user question into a valid FTS5 expression before MATCH).
  PROCESS: #071 WIP polluting this review is the recurring hygiene issue again;
  the in-flight #071 also has a ruff E501 in brief_passages.py:3 that must be fixed
  before it hands off. Flagged, not a #070 defect.
