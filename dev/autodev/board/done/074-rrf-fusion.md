---
id: 074
title: RRF fusion — weighted 70/30 reciprocal rank, cap 10, empty -> explore (T27)
priority: high
size: medium
depends_on: [072, 073]
spec_refs: [build-order.md#T27, how-hrono-works.md]
---

## Context
Fuses the two legs into the final ranked hits. Frozen recipe (how-hrono-works.md):
union the qualified sets from the vector leg (#072) and keyword leg (#073), rank
by **weighted reciprocal rank fusion, 70/30 vector/keyword**
(score = sum of weight / (60 + rank)), cap at **10** passages. There is NO
gap-based cutoff — the z-floors alone decide membership. An empty union injects
nothing and returns one line: "no confident matches - explore the map."

## Description
- Union the qualified passages from both legs (a passage may qualify in one or
  both). Rank within each leg by that leg's score to get per-leg ranks.
- Fuse: `score(p) = 0.7/(60 + vector_rank(p)) + 0.3/(60 + keyword_rank(p))`,
  contributing a term only for the leg(s) where the passage qualified. k = 60,
  weights 70/30 baked.
- Sort by fused score desc, cap at **10** hits. No gap/threshold cutoff beyond
  the legs' z-floors.
- Empty union -> return zero hits + the explore message
  "no confident matches - explore the map." (exact copy per implementation-notes).
- Deterministic ordering (stable tie-break, e.g. by passage address) so results
  are reproducible.

## Acceptance criteria
- [ ] Qualified sets are unioned and ranked by weighted RRF (70/30, k=60), capped
      at 10; constants baked.
- [ ] A passage qualifying in both legs outranks an equal single-leg passage
      (weights compose); ordering is deterministic.
- [ ] An empty union returns no hits and the exact explore message.
- [ ] No gap-based cutoff exists — only the #072/#073 z-floors gate membership.
- [ ] `ruff format`, `ruff check --fix`, `pytest` all clean; work committed.

## Out of scope
- The legs themselves (#072/#073) and the endpoint/hit rendering (#075).

## Review log
- 2026-08-24 PO: authored as T27. Frozen recipe: weighted RRF 70/30, k=60, cap 10,
  no gap cutoff, empty -> the exact explore message. Deterministic tie-break.
- 2026-08-25 dev: DONE, committed 06b3e3e, handoff to qa. `recall/fusion.py`
  `fuse(vector_hits, keyword_hits) -> Fusion(hits, message)`: unions the two legs'
  qualified passages, ranks by weighted RRF score = 0.7/(60+vrank) +
  0.3/(60+krank) (a term per leg the passage qualified in), caps at 10, ties break
  by passage id (deterministic). No gap cutoff — the #072/#073 z-floors alone gate
  membership. Empty union -> hits=() + the exact "no confident matches - explore
  the map." All constants baked (K=60, 0.7/0.3, cap 10).
  Verified: ruff clean; pytest 496 passed / 1 skip (+6: both-leg outranks
  single-leg, deterministic tie-break, cap 10, empty->explore message, weights
  compose, constants baked).
- 2026-08-25 qa: PASS (commit 06b3e3e) -> po-review. Tree CLEAN at handoff.
  Pure fusion, correct on every dimension: weighted RRF score =
  0.7/(60+vrank) + 0.3/(60+krank) with a term per qualifying leg, union of both
  legs, sorted by (-score, pid) so a both-leg passage outranks an equal
  single-leg one and ties break deterministically by id, capped at 10, no gap
  cutoff (z-floors alone gate membership). Empty union -> () + the exact message
  "no confident matches - explore the map." Constants baked (K=60, 0.7/0.3,
  CAP=10). Tests cover all of it (both-leg-first, tie determinism, cap, exact
  explore string, weights compose). ruff clean; full suite 496 passed / 1 skip;
  atomic Conventional Commit. Only the recall endpoint (#075) remains in M5.
  (Pre-existing unrelated `.gitignore` edit remains uncommitted.)
- 2026-08-25 PO review: PASS -> done. Read fusion.py at HEAD (06b3e3e); gated in
  an isolated worktree (tree carried #075 WIP modifying fusion.py): ruff clean, 26
  recall tests pass. Pure function, exact to the frozen recipe: weighted RRF
  score = 0.7/(60+vrank) + 0.3/(60+krank), one term per qualifying leg, union of
  both legs, sorted (-score, pid) so a both-leg passage outranks an equal
  single-leg one with deterministic tie-break, capped at 10, NO gap cutoff (the
  #072/#073 z-floors alone gate membership), empty union -> the exact
  "no confident matches - explore the map." Constants baked (K=60, 0.7/0.3,
  CAP=10). All acceptance criteria met. Closed. Only #075 (endpoint + CLI +
  calibration) remains to complete M5.
