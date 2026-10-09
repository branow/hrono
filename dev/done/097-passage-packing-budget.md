---
id: 097
title: Passages pack to ~100 B instead of the 800 B budget; byte-chop cuts mid-token
priority: high
size: medium
depends_on: []
spec_refs: [build-order.md#T14.3, build-order.md#T14.4, how-hrono-works.md]
found_by: e2e manual QA 2026-09-03 — .e2e/FINDINGS.md F7, F8
---

## Context
Measured over 92 real sections from three public repos
(`.e2e/artifacts/ingest-coverage.md`):

```
passage bytes: n=1514 min=9 median=135 max=800 mean=183
histogram: <64: 7 | 64-200: 1151 | 200-400: 241 | 400-800: 112 | 800+: 3
```

76% of passages are under 200 B against an 800 B budget.

## Description
Root cause in `ingest/split/pack.py:_pack`:

```python
limit = budget if min_group is None else min_group      # 100, not 800
...
if child.end - start >= limit:
    flush(child.end)                                    # flush at 100 B
```

`_passages` calls `_pack(wrapper, PASSAGE_BYTES, MIN_GROUP)`, so the flush
threshold is `MIN_GROUP = 100` and the 800 B budget only bounds descending and
chopping. Every sibling group is cut as soon as it crosses 100 bytes.

The settled recipe disagrees: `docs/research/prototype/structure-split.ipynb:pack_node`
has **no min-group flush** — it flushes only when a group would bust the budget
— and its measured output is `57 paragraphs, sizes [122, 195, ..., 799, 800,
835]`, a median in the 600s. The prose in `how-hrono-works.md` ("a sibling group
is flushed once it reaches 100 bytes, so a decent structural unit stands alone")
was implemented as an unconditional flush.

Effect on one docstring in `src/itsdangerous/signer.py` — seven consecutive
passages of 100/284/137/115/132/144/111 B, one line each — and the recall hit it
produces is a truncated sentence rather than a ~200-token unit. The passage
table is also 4-6x larger than intended (1514 rows for 92 sections), inflating
both the vector index and FTS.

**F8, same area:** the smallest passage in the corpus is `b'tColor = '` (9 B), a
fragment of an identifier in `source/vendor/ansi-styles/index.d.ts`. `_chop`
slices raw byte offsets with no backoff to whitespace, and `_merge_tiny` did not
fold it because it was first in its group.

Work:
- Re-derive the intended min-group semantics against the prototype and either
  drop the unconditional flush or apply it only where it was meant to (e.g. a
  group of >= 2 structural siblings at a real boundary), then re-measure the
  distribution on a real repo.
- Back `_chop` off to the nearest whitespace/token boundary within a tolerance.
- Prototype also skipped whitespace-only spans (`if raw[s:e].strip()`);
  production does not — decide whether to match.

## Decision (2026-09-12, dev — technical call, no PO input needed)

Restore the prototype's behaviour: **remove the unconditional min-group flush**.
`_pack` should flush only when adding the next child would bust the budget,
which is what `docs/research/prototype/structure-split.ipynb:pack_node` does and what
produced the measured `[122, 195, ..., 799, 800, 835]` distribution.

If the "a decent structural unit stands alone" intent in `how-hrono-works.md` is
still wanted, it must be expressed as a condition that cannot cap a group at
100 B — e.g. flush at a *real* structural boundary (a named node, not a
`~blank-line` cascade node) rather than at a byte count. Implement the removal
first, re-measure on the QA corpus, and only add the boundary rule if the
distribution says it is needed.

`_chop` backs off to the nearest whitespace within a tolerance (say 10% of the
budget) before cutting, so no passage is a mid-token fragment.

## Acceptance criteria
- [ ] On a real repo corpus the passage median lands in the 400-800 B band and
      the <200 B share is a small minority; byte-identity invariants still hold.
- [ ] No passage is a mid-token fragment of an identifier.
- [ ] A size-distribution assertion over a fixture corpus guards the regression.
- [ ] `ruff format`, `ruff check --fix`, `pytest` clean.

## Review log
- 2026-09-15 dev: started; moved to in-progress.
- 2026-09-15 dev: implemented and committed as `9e01051`. Decision block
  followed in order: remove the flush first, measure, and only add a boundary
  rule if the distribution demands one. **It did not — no boundary rule was
  added.**

  **Four changes in `ingest/split/pack.py`:**
  1. **The unconditional min-group flush is gone.** `_pack` no longer takes
     `min_group`; a group is flushed by the BUDGET alone (a child that would
     bust it, a child too big to fit at all, or the end of the node), which is
     `structure-split.ipynb:pack_node`'s rule. Section packing is unchanged by
     this: at the section level `limit` was already the budget, and a group at
     exactly the budget flushes at the same place either way.
     `MIN_GROUP` is now dead and was deleted from `constants.py`.
  2. **`_chop` backs off to a token edge.** Each cut walks back to just after
     the last whitespace byte within `_CHOP_BACKOFF` (10%) of the target; with
     no whitespace in the window the target stands, so the budget is never
     exceeded and progress is guaranteed. This needs the file bytes, so
     `sections(root, budget, raw)` now takes them — threaded from `split` and
     from both production callers (`split_op`, `recall/brief_passages`), which
     already had `raw` in hand.
  3. **`_chop` splits EVENLY, not budget-then-remainder.** The target is
     recomputed from what is left over how many cuts remain, so 1805 B becomes
     602/602/601 instead of 800/800/205 — a remainder crumb is a passage no
     later pass can fold away (`_enforce_budget` runs after `_merge_tiny`).
  4. **A crumb merge may not push its neighbour over the budget.**
     `_merge_tiny` takes a `cap` (passage level only; section behaviour and its
     documented MIN_PARA overshoot are untouched). Without it a 15 B class
     header merged forward into an 800 B group, and the budget backstop then
     byte-CHOPPED that group — a structural run of 22 methods came back as
     `.raw[1/2]` parts with no structure paths. This surfaced as a real failure
     in `test_a_passage_over_several_siblings_carries_all_their_paths` once the
     packer started filling the budget, and it is the reason chop parts fall to
     ZERO on the real corpus.

  **Before/after on the real corpus** (`.e2e/run2/repos/{itsdangerous,chalk,
  uuid}`, read-only, ingest filter as the QA run configured it; 69 files, 75
  sections):

  | | n | min | median | mean | max | <200 B | >800 B |
  |---|---|---|---|---|---|---|---|
  | before | 786 | 19 | **152** | 212 | 800 | **68%** | 0 |
  | after  | 317 | 18 | **585** | 525 | 800 | **15%** | 0 |

  Histogram after: `0-64: 9 | 64-200: 38 | 200-400: 51 | 400-800: 214 | 800: 5`.
  The median lands in the 400-800 band the criterion asks for, and the passage
  table is 2.5x smaller (786 -> 317 rows for the same corpus), which is the
  vector-index and FTS saving the ticket predicted. Of the 47 remaining sub-200
  B passages, **11 are the only passage of their section** (a whole small file:
  `.gitattributes`, `.npmrc`, `go.mod`) and cannot be bigger; the other 36 are
  tails and headings inside multi-passage sections.

  **F8 reproduced and fixed on the same corpus:** before, one chop cut landed
  mid-identifier (`chalk source/index.js`, `...};\n\ncons` — inside `const`);
  after, mid-token chop cuts = **0**, and in fact chop parts = 0 because change
  4 stops structural groups degrading into raw chops at all.

  **Byte identity re-verified as part of every measurement**, not assumed: each
  of the 69 files was reassembled from its sections and each section from its
  passages — **0 mismatches**, before and after. No passage exceeds 800 B in
  either run.

  **Boundary rule: not needed.** The distribution with the flush simply removed
  already meets the criterion, so nothing was added; `how-hrono-works.md`'s "a
  sibling group is flushed once it reaches 100 bytes" prose is now wrong and
  should be corrected in the spec repo (outside this repo — flagged, not
  edited).

  Tests (5 new/rewritten, 697 total), each verified regression-grade by
  mutating the source and watching the matching test go red:
  - `test_passages_fill_the_budget_instead_of_stopping_at_a_crumb` — the
    distribution assertion the criterion asks for, over both fixture corpora:
    median >= half the budget, max <= budget, nothing under 200 B. Replaces
    `test_min_group_lets_a_real_unit_stand_alone`, whose intent this ticket
    retires. Restoring the flush fails it.
  - `test_a_dense_file_packs_into_few_passages_not_one_per_line`.
  - `test_a_chop_cuts_at_whitespace_not_mid_token` — a structureless tab-joined
    blob (the only shape that really reaches `_chop`; the delimiter cascade
    already splits on spaces and newlines, so the old version of this test
    passed vacuously). Its even target falls 61 B past a tab, so removing the
    backoff cuts mid-run and the test fails.
  - `test_a_chop_splits_evenly_rather_than_leaving_a_crumb` — 1805 B ->
    [602, 602, 601]; budget-then-remainder gives [800, 800, 205] and fails.
  - `test_a_crumb_never_costs_its_neighbour_its_structure` — the class-header
    shape; uncapping the merge fails it AND the identity test above.

  Not touched: #102, #100, #103, #105, #113, #114, #101. `.e2e/` read-only
  throughout (database mtime still 2026-09-03 20:54:49).
  Gate clean: `ruff format` (225 files unchanged), `ruff check --fix` (all
  checks passed), `pytest` **697 passed**. Handing off to verifying.
- 2026-09-15 qa: **PASS — to po-review.** No defects. Byte identity holds in
  both directions on the real corpus and under fuzz, the budget is a hard
  ceiling I could not break, and dev's distribution reproduces exactly.

  **1. Byte identity — 0 failures, and I checked more than concatenation.** On
  `.e2e/run2/repos` (read-only; both run databases' mtimes unchanged) under the
  three stored source filters, for all 69 files / 75 sections: file ==
  concat(sections) AND section == concat(passages), PLUS sections tile from 0 to
  `len(raw)` with no gap or overlap and passages tile their section exactly.
  **0 failures on `9e01051` and 0 on `733549c`** — the property is preserved,
  not merely still true by luck of the same inputs.

  **2. The budget is a hard ceiling.** The proof in `_chop` holds: `parts =
  ceil(L/budget)` so `target = ceil(L/parts) <= budget`; `_token_edge` only ever
  walks BACK from `cursor+target`; and `max(..., cursor+1)` guarantees progress.
  Driven adversarially — no whitespace at all, whitespace only before the
  window, whitespace exactly at the window edge, one whitespace at each target,
  `len == budget`, `budget+1`, `2*budget`, `2*budget+1`, dense multibyte UTF-8:
  every case tiles exactly with **0 over-budget, 0 zero-length**. Then 600
  fuzzed files across 10 extensions and 5 content styles through the full
  `split()`: **over-budget 0, identity 0, gap/overlap 0, empty 0**, largest
  passage exactly 800. The no-whitespace case degrades exactly as documented —
  the hard target stands (5000 B -> 7 even parts of 714/715), so the backoff can
  never push a part over.

  **3. The crumb cap is right, not a patch — I measured the counterfactual.**
  Removing `cap=PASSAGE_BYTES` from `_merge_tiny` on the real corpus:

  | | with the cap (shipped) | without |
  |---|---|---|
  | passages | 317 | 317 |
  | raw byte-chopped parts | **0** | **10** |
  | sub-`MIN_PARA` (64 B) passages | 9 | 5 |
  | over budget / identity fails | 0 / 0 | 0 / 0 |

  So it DOES reintroduce crumbs `_merge_tiny` exists to remove — 4 of them
  (18 B, 38 B, 40 B, 48 B), 1.3% of passages — and in exchange it stops 10
  structurally-grouped passages being shredded into raw parts. With the cap the
  entire corpus has ZERO raw chop parts: every passage is node-aligned. That is
  the right trade: a short passage is still a coherent unit with correct
  provenance, while a byte-chopped group loses the structure the splitter exists
  to produce. A crumb that cannot merge in either direction simply stays its own
  small passage — I confirmed all four such cases keep byte identity and
  coverage. The other 5 sub-64 B passages are whole tiny files (`.npmrc` 19 B,
  `.gitattributes` 19 B, `go.mod` 30 B, `.gitignore` 44 B, `docs/changes.rst`
  45 B) and are identical before and after: genuinely unavoidable.

  **4. Distribution re-measured independently — dev's numbers are exact.**

  ```
  [old 733549c] files=69 sections=75 passages=786 median=152 mean=212 max=800
                under200=532 (68%)  over800=0
  [new 9e01051] files=69 sections=75 passages=317 median=585 mean=525 max=800
                under200= 47 (15%)  over800=0
  ```

  Section count is unchanged at 75 — the claim that section packing is
  untouched holds on real data. On the 47 remaining sub-200 B passages: 10 are
  whole tiny files, 12 are the last passage of a section (the remainder after
  the final full one), 21 are >= `MIN_PARA` and structurally legitimate, and 4
  are the capped crumbs above. Nothing avoidable is left.

  One refinement to dev's mid-token figure, in dev's favour once scoped. My
  detector counts EVERY internal passage boundary whose two neighbouring bytes
  are both non-whitespace, which gives 48 -> 5, not 1 -> 0. Classifying them:
  **mid-token CHOP cuts go 1 -> 0** — exactly dev's number, and the one before
  is F8's shape verbatim (`ansi256];\n};\n\ncons | t usedModels` in
  `chalk/source/index.js`). The remaining 5 are STRUCTURAL node edges the
  grammar chose (a docstring opening after `"""`, a `.rgb(` chain boundary, a
  `,` after a JSON value) — not chop artifacts, not what F8 is about, and they
  fell 47 -> 5 as a side effect of packing more per passage.

  **5. Compatibility — no mixed state from a `maintain`, a mixed corpus only
  from update-only, and nothing breaks either way.** `split_op.py:53` does
  `store.clear_source(conn, name)` and then re-splits EVERY file, so the `split`
  op (and therefore `maintain`) re-packs a source wholesale: the run2 database's
  786 passages become 317 in one pass, with no per-file cache to leave old rows
  behind. `update` re-splits only changed files (`reconcile.py:163` deletes by
  path), so an update-only corpus does keep 152 B passages for untouched files
  until each one changes. That is acceptable: byte identity is per file, so
  reassembly and provenance are unaffected; nothing in `src/hrono/recall/` or
  `src/hrono/embed/` references `PASSAGE_BYTES` or any byte budget at all
  (recall's cap is a COUNT of hits, `engine.py:45`); and FTS5's `bm25`
  (`fts.py:49`) length-normalises by construction. The one real consequence is
  calibration, and it lands on the next ticket: **#102's median/MAD noise floor
  must be calibrated against a uniformly packed corpus, so run a full `maintain`
  before measuring it** — calibrating on a half-updated corpus would fit the
  floor to a bimodal score distribution. Flagging for the PO rather than
  re-opening #102.

  **6. The signature change is complete and cannot carry stale bytes.** `raw` is
  a required positional third argument, so no caller can omit it. All three call
  sites updated: `split()` itself, `split_op.py:75` and
  `brief_passages.py:66` — and in both external sites the `raw` passed is the
  same local variable the tree was built from two lines earlier
  (`raw = (cache / path).read_bytes()` then `structure(Path(path), raw)`; and
  `structure(grammar, raw)`), so the bytes and the tree cannot diverge.

  **Mutation-verified by me** in a worktree at `9e01051` (`PYTHONPATH` asserted
  inside it) — each of the four behaviours is pinned by the test named for it:
  the `MIN_GROUP` early flush restored -> `test_passages_fill_the_budget_
  instead_of_stopping_at_a_crumb` and `test_a_dense_file_packs_into_few_
  passages_not_one_per_line`; the token backoff dropped -> `test_a_chop_cuts_at_
  whitespace_not_mid_token`; the even split dropped -> `test_a_chop_splits_
  evenly_rather_than_leaving_a_crumb`; the crumb cap dropped -> `test_a_crumb_
  never_costs_its_neighbour_its_structure` (plus an identity test).

  Commit `9e01051` is a clean Conventional Commit, atomic, 5 files, no stray
  changes; `.gitignore` is still the pre-existing uncommitted line. `.e2e/` read
  only — `run/` mtime still 2026-09-03 20:54:49 and `run2/` unchanged.
  Worktrees removed, tree clean.

  Gate re-run by me on `9e01051`: `ruff format --check` 225 files unchanged,
  `ruff check` clean, `pytest` **697 passed** in 41.1s. All acceptance criteria
  hold.
- 2026-09-15 PO: **ACCEPTED -> done.** Commit 9e01051. Verified independently
  by re-measuring on the real repos, not by reading the reported numbers.

  **Gate re-run by me:** `ruff format --check .` 225 files already formatted;
  `ruff check .` all checks passed; `uv run pytest` **697 passed** in 41.1s.

  **I re-measured the distribution myself** over `.e2e/run2/repos` (read-only),
  running the same probe against `733549c` in a worktree and against `9e01051`,
  same filter config both sides so the two are directly comparable:

  | | before (733549c) | after (9e01051) |
  |---|---|---|
  | passages | 1113 | **474** (-57%) |
  | median | 156 | **592** (3.8x) |
  | mean | 223 | 524 |
  | under 200 B | 64% | **15%** |
  | over 800 B | 0 | 0 |
  | **sections** | **112** | **112** |
  | identity failures | 0 | 0 |

  My absolute counts differ from dev's and qa's because I used a generic filter
  config rather than the run's per-source excludes; the DISTRIBUTION matches
  theirs closely (median 592 vs 585, mean 524 vs 525, under-200B 15% both).
  **Sections unchanged at 112 on both sides** is the number that matters most:
  section packing really was untouched, so the clustering and brief layers see
  exactly the corpus they saw before. Byte identity re-verified by me on every
  section (112/112 reassemble from their passages), with **0 gaps, 0 overlaps,
  0 over-budget** — the load-bearing invariant survived a rewrite of the packer's
  flush rule, which is the risk this ticket carried.

  **Mid-token chopping: I found zero.** Across the whole corpus there are
  **0 raw chop parts at all** — every passage is node-aligned — so F8 cannot
  occur, not merely does not. The `_chop` rewrite is sound on its own terms too:
  `target = ceil(remaining/parts)` with `parts = ceil(remaining/budget)` is
  always <= budget, the backed-off cut only ever moves earlier, and
  `max(..., cursor + 1)` guarantees progress when a window holds no whitespace.
  Even parts rather than budget-then-remainder is the right instinct — it stops
  the packer manufacturing the very crumbs the next pass has to clean up.

  Removing the flush rather than adding a boundary rule is the better outcome
  and I am glad the fallback my Decision block allowed was not reached: the
  defect was an invented rule, and deleting it restores the settled recipe
  instead of layering a second rule on top of a wrong one.

  **Rulings:**
  1. **The spec prose was wrong, and I have corrected it myself — done, not
     delegated.** I verified the claim at its source rather than accepting it:
     `app/structure-split.ipynb:pack_node` flushes on
     `nxt_start - group_start > budget` and nothing else; there is no
     `MIN_GROUP`, no 100-byte rule, and the only small-span rule in the
     prototype is `merge_tiny`'s 64-byte `MIN_PARA`, which production keeps. So
     `how-hrono-works.md:41` described a rule the settled recipe it claims to
     describe never had — and #030 implemented the prose literally, which is
     exactly how the 152-byte median got built.
     Spec reconciliation is the PO's job (precedent: #036, where I reconciled
     `implementation-notes.md` after the profile rename), and leaving it is the
     live risk dev correctly flagged: the spec is the source of truth, so a
     future ticket reading that sentence would reinstate the flush and undo this
     work. I have rewritten the bullet to say the group is flushed by the budget
     and nothing else, added the whitespace-edge chop, and attached a dated
     correction note carrying the before/after measurements and an explicit
     "do not reinstate a group-size flush from this paragraph's old wording".
     The old text is quoted in the note so the trail is readable rather than
     erased.
  2. **CONFIRMED, and stronger than qa framed it — recorded on #102.**
     qa is right that `split_op.py:53` clears and re-splits per file, so
     `maintain` re-packs wholesale with no mixed state while an update-only
     workflow leaves untouched files at the old packing. But I checked what the
     re-run's database actually holds, and it is not half-updated — it is
     **entirely pre-097**: 786 stored corpus passages, **median 152, mean 212,
     68% under 200 B**, which is the "before" column exactly. run2 was driven
     before this commit landed.
     So the operative instruction for #102 is not "avoid a half-updated corpus",
     it is: **`.e2e/run2/.hrono/hrono.db` cannot be used to calibrate recall at
     all.** Calibrating a median/MAD floor against it would fit the floor to a
     packing that no longer exists — every passage in it is ~4x shorter than
     what the system now produces, and score distributions over 152-byte and
     592-byte passages are not comparable. A full `maintain` must be re-run
     after 097 before any #102 calibration, and if an update-only pass is used
     instead, the corpus is bimodal and the floor is fitted to an artefact.
     Recorded on #102, which is next in the queue.
  3. **Trade CONFIRMED, and I measured the counterfactual myself.** With the cap
     removed in a worktree: **14 raw chop parts appear** and sub-64 B crumbs
     drop from 12 to 6. So the cap spends 6 crumbs to prevent 14 structural
     passages being shredded — and it is not a close call, because the two
     outcomes are not comparable in kind. A crumb is a *complete but small*
     unit: it keeps its node alignment and its structure path, so recall can
     still cite what it is. A raw chop part is a *fragment of a unit*: no node,
     no path, and it destroys the very thing #031's structure path indexes and
     #102 will rank on. Trading intact-and-short for shredded-and-long would be
     the wrong direction for a retrieval system. The cost is also bounded — a
     crumb is under 64 B, about 16 tokens — while the corpus-wide payoff is
     absolute: **zero raw parts anywhere**, every passage node-aligned.

  All acceptance criteria hold. The e2e re-run's own finding for #097 (152 B
  median, predicted on the known-expected baseline) is now closed against a
  measured 592.
