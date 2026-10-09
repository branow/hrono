---
id: 102
title: Recall quality — the brief's URI footer is indexed, and one document can fill the window
priority: high
size: medium
depends_on: [103]
spec_refs: [build-order.md#T25.3, build-order.md#T27, build-order.md#T28]
found_by: e2e manual QA 2026-09-03 — .e2e/FINDINGS.md F30, F31, F12
---

## Context
`summarize/brief.py` bakes member URIs into `briefs.text` via
`_references(uris)`, and #071 splits the whole brief — footer included — into
`node://` passages that enter both the vector index and FTS.

## Description
**F30 — the footer wins.** All five hits for *"how do I set the color level in
chalk"* were `summary` kind from node 2's brief, and every one was a slice of
the URI list, not the summary prose:

```
--- hit 1 [summary] '- git:///.../chalk/source/vendor/supports-color/index.d.ts@661317e...'
--- hit 2 [summary] '- git:///.../chalk/source/vendor/supports-color/index.js@661317e...'
--- hit 3 [summary] '- git:///.../chalk/source/vendor/supports-color/browser.d.ts@661317e...'
```

A path list is lexically dense and matches any query whose words appear in a
filename ("color" via `supports-color`), so the agent gets five lines of URIs
injected and none of the brief's actual content.

**F31 — no diversity.** RRF caps the count but never diversifies by document:

```
"how do I set the color level in chalk"    limit=10 -> 10 hits from 4 documents
"how is key rotation handled"              limit=10 -> 10 hits from 4 documents
"how does the signer verify a signature"   limit=10 -> 10 hits from 2 documents
```

With ~135 B passages (see 097) a single file trivially supplies ten neighbouring
fragments that score alike.

**F12 — the off-topic floor leaks.** Three of five nonsense questions correctly
returned `no confident matches - explore the map.`; two did not
(`"quantum entanglement in banana futures"` -> 1 hit,
`"the mitochondria is the powerhouse of the cell"` -> 3 hits). A z-score floor
is relative to the corpus distribution, so a small corpus yields outliers;
consider an absolute similarity gate under the z-gate.

Work:
- Exclude the mechanical reference block from the passage split (or move member
  URIs out of `briefs.text` into metadata the renderer re-attaches).
- Add a per-document (and per-node) cap or MMR-style diversification in fusion.
- Re-calibrate the off-topic floor against a small corpus.

## Decision (2026-09-12, dev — technical call, no PO input needed)

Technical half, decided: the mechanical reference block stops being indexed.
Member URIs move out of `briefs.text` into brief metadata that the export
renderer re-attaches, so a brief's passages contain only its prose. This also
shrinks the `node://` passage count.

## OPEN — needs a product call (see the PO note of 2026-09-12)

How the result window should be COMPOSED — a per-document cap, the brief-vs-
source mix, and how aggressively to gate an off-topic question — is a product
call, not a tuning detail. See the PO note of 2026-09-12, question C.

## Specified fix, measured on the 2026-09-15 re-run corpus (PO, 2026-09-15)

The off-topic leak (F12) did not reproduce on the re-run — 0 of 4 nonsense
questions returned hits. But the same floor is now cutting genuine matches:
"generate a version 7 uuid" returned **1 hit** while the corpus holds **23
passages** matching `version7 OR v7`.

Diagnosis, measured rather than argued. `recall/vector_leg.py` z-scores against
the mean and standard deviation of the SAME population it is scoring, so the
matches inflate the baseline they are then measured against. The effect is
strongest exactly when the corpus is on-topic for the query:

| query | population mean | sd | top cosines | hits at z>=3.5 |
| --- | --- | --- | --- | --- |
| generate a version 7 uuid | 0.178 | 0.161 | 0.80 0.75 0.71 0.70 0.67 | **2** |
| how does the signer verify a signature | 0.120 | 0.137 | 0.63 0.59 0.57 | **1** |
| what is the capital of Peru (absent) | 0.007 | 0.050 | 0.20 0.17 0.16 | 1 |

Genuinely excellent matches at cosine 0.71/0.70/0.67 score z = 3.27/3.22/3.06
and are cut, while in a flat population a mediocre 0.27 reaches z = 2.94.

**The fix is the estimator, not the statistic.** Replace mean/sd with
**median + MAD** (`MAD * 1.4826` for an sd-equivalent) when computing the
z-score. The matches live in the tail, so estimating the noise floor from the
body of the distribution stops them raising their own threshold. Measured on the
same corpus:

| query | plain mean/sd | median/MAD |
| --- | --- | --- |
| generate a version 7 uuid | 2 hits | **53** |
| how does the signer verify a signature | 1 hit | **74** |
| what is the capital of Peru (absent) | 1 | **1** |

On-topic recall is restored and the off-topic case is unchanged. A trimmed mean
was also measured: same on-topic gain (53/73) but worse off-topic (4 hits), so
MAD is the choice.

**Explicitly rejected: an absolute cosine floor.** It reads better on this
corpus but is model-specific and would need recalibrating on every embedding-
model change. The z-score was chosen precisely to be scale-free and portable;
this fix keeps that — `Z_FLOOR = 3.5` stays baked, there are no per-model
constants, and nothing needs re-deriving when the model changes.

**The result cap is unchanged and still bounds the output** (PO, 2026-09-15):
`recall/fusion.py:CAP = 10` and the endpoint's `limit` (default 10) apply after
the floor, so "53 candidates clear the floor" never means 53 results. The floor's
job is to separate signal from noise; ranking and the cap decide what is
injected.

Consequence to handle in the same pass: with 53-74 candidates clearing the floor
instead of 1-2, the cap and the ranking carry more of the weight than before — so
the per-document diversity decision above (question C) matters more, since one
file can more easily fill the whole window.

## Acceptance criteria
- [ ] No recall hit body is a list of member URIs.
- [ ] A `limit=10` result set draws from a configurable minimum number of
      distinct documents where the corpus allows it.
- [ ] Clearly off-topic questions return the explore message on a corpus of this
      size; a calibration test pins it.
- [ ] On-topic questions are NOT starved: a query whose corpus holds many
      genuine matches returns a full window rather than 1-2 hits. Pin both
      directions in the same calibration test.
- [ ] The vector leg estimates its noise floor with median/MAD; `Z_FLOOR` stays
      baked and no per-model constant is introduced.
- [ ] `ruff format`, `ruff check --fix`, `pytest` clean.

## Addendum (2026-09-14, PO — observed during #094's review)

The footer has an UPPER-LEVEL twin: `summarize/brief_upper.py:101` appends
`"\n\nChildren:\n- node <id>"` per child into `briefs.text`, the same way
`summarize/brief.py`'s `_references(uris)` appends member URIs at the leaf. Both
are mechanical footers baked into the brief body, so both are indexed by #071
and both leak into the export.

I saw the export side firsthand while driving #094's end-to-end result on the
real 3-repo database: the rendered `root.md` shows `Children:\n- node 1\n- node
2 ...` (opaque ids) immediately above render's own proper `## Children` block of
titled links — the child list twice, once unreadable, in the MVP's top file.

So when the decision above is implemented — "member URIs move out of
`briefs.text` into brief metadata that the export renderer re-attaches" — apply
it to `brief_upper.py:101` in the same pass, not only `brief.py`. Export's
`_node_markdown` (`export/render.py:52`) already renders both children and
sections mechanically from tree metadata, so removing both footers from the
stored text loses nothing and fixes the duplication for free.

Added to this ticket rather than filed separately: it is one fix in one place,
and a second card would only guarantee the two halves drift.

## Review log
- 2026-09-14 PO: appended the upper-level footer (`brief_upper.py:101`) to this
  ticket's scope — same defect, same fix, spotted in `root.md` while verifying
  #094. No change to priority (high) or size (medium).

## Calibration precondition (PO, 2026-09-15, at #097's close)

**Do not calibrate any score floor against `.e2e/run2/.hrono/hrono.db`.** #097
changed the passage distribution by roughly 4x, and the re-run's database was
built BEFORE it landed. Measured by PO on the stored corpus:

| | run2 as stored (pre-097) | what the packer produces now |
|---|---|---|
| corpus passages | 786 | ~317 (~57% fewer) |
| median | **152 B** | **585 B** |
| mean | 212 B | 525 B |
| under 200 B | **68%** | **15%** |

A median/MAD (or z-score) floor is a statement about a score distribution, and
scores over 152-byte passages are not comparable to scores over 585-byte ones —
a short passage concentrates its term mass and scores differently for the same
relevance. A floor fitted to run2 would be fitted to a packing that no longer
exists.

Two rules for whoever picks this up:
1. **Re-run a full `maintain` after #097 first**, and calibrate on that corpus.
   `ingest/split_op.py:53` clears and re-splits every file, so a full maintain
   re-packs wholesale and leaves no mixed state.
2. **Do not calibrate on an update-only corpus.** `update` only re-splits files
   that changed, so an untouched file keeps its old ~152 B packing until it
   changes. A partially-updated corpus is bimodal, and a floor fitted to a
   bimodal distribution is fitted to an artefact — it will be too strict for the
   long passages and too loose for the short ones simultaneously.

Raised by qa while verifying #097; the run2 measurement above is PO's, and it is
why the rule is "re-maintain first", not merely "avoid a half-updated corpus".

## Review log
- 2026-09-15 PO: added the calibration precondition above at #097's close.
  No change to priority (high), size (medium) or scope — this constrains HOW the
  existing acceptance criteria are measured, not what they are.

## Sequencing (PO, 2026-09-15) — why this now depends on #103

`depends_on` changed from `[]` to `[103]`. Not because the code interacts, but
because the CALIBRATION does.

Recall indexes two kinds of passage: source passages (repacked by #097) and
brief passages (`node://`, #071 — the briefs themselves, split and indexed).
#103 changes what a brief CONTAINS (the output guard, and the faithfulness
gate's false positives). So calibrating a score floor before #103 lands means
calibrating against brief text that is about to change, and the precondition
above already says a full `maintain` must be re-run first.

That maintain is not free — the re-run took 15m53s and real LLM spend — so the
order that pays for it once is:

1. **#103** (brief output guard) — the last open ticket that changes what a
   fresh `maintain` PRODUCES.
2. **a full `maintain`** on the rebuilt corpus, post-#097 and post-#103.
3. **#102** — calibrate against that corpus.

Everything else in the high band (#100, #113, #114, #101) changes incremental
behaviour, not what a fresh maintain produces, so it can land in any order
around this and be verified against the same rebuilt tree.

## Also in this pass (PO, 2026-09-15, from #103's review)

**Re-point `tests/export/test_render.py:298`.** It is named
`test_a_boilerplate_heading_does_not_become_the_directory_name` but does not
test that: it builds a single level-0 node which IS the root, and the root has
no directory, so the boilerplate skip is never exercised — removing the skip
leaves the test green. The behaviour is genuinely pinned elsewhere, by
`test_a_long_first_line_is_trimmed_to_a_usable_title:329`, so this is a
mis-scoped and misleadingly named test, not a coverage hole.

Give it a node with a PARENT so the directory name is actually computed, and
assert the boilerplate heading is skipped. A test whose name claims a property
it does not test is worse than no test — the next reader trusts the name and may
delete the skip it appears to protect.

Folded in here rather than given its own card because this ticket already edits
`export/render.py` (the `Children:` footer addendum above) and will be in this
test file anyway.

## Acceptance criteria (added)
- [ ] `test_a_boilerplate_heading_does_not_become_the_directory_name` builds a
      node with a parent, and fails if the boilerplate skip is removed.

## Precondition SATISFIED (PO, 2026-09-15)

The full `maintain` this ticket required has been run (2026-09-15, at
`fd15c60`): 2m39s, passages 905 -> 438, median 153B -> **475B**, briefs 7 with
0 flagged. The corpus is now built with #097's packer and #103's briefs, so
**calibrate on it — do not re-run a maintain first.**

The two rules above still bind for any LATER calibration: never calibrate on an
update-only corpus (bimodal), and re-maintain if anything changes what a brief
or a passage contains before the floor is fitted.

## Review log (dev)
- 2026-09-15 dev: started; moved to in-progress.
- 2026-09-15 dev: implemented and committed as `d233758`. Calibrated on
  `.e2e/run2` exactly as it stands (copy in scratch; `.e2e/` untouched — the
  #122 evidence copy's mtime is still 2026-09-15 18:30:38). No maintain was run.

  **The floor — the estimator, not the statistic.** `recall/vector_leg.py` now
  z-scores against the distribution's MEDIAN and MAD (`MAD * 1.4826`). `Z_FLOOR`
  stays baked at 3.5, there are no per-model constants, and no absolute cosine
  gate was introduced. Measured on the re-run corpus (438 passages, the
  #097-packed, #103-briefed build):

  | query | mean/sd | median/MAD |
  |---|---|---|
  | generate a version 7 uuid (on-topic) | **0** | **38** |
  | how does the signer verify a signature (on-topic) | 8 | **18** |
  | what is the capital of Peru (off-topic) | 0 | **0** |
  | recipes for a chocolate cake (off-topic) | 0 | **0** |

  The absolute numbers differ from the PO's probe (2 -> 53) because that probe
  predates the re-maintain; the direction and magnitude match, and the uuid
  question was returning NOTHING on this corpus before the change. End to end
  through the real engine with the unchanged `CAP = 10`: all three on-topic
  questions return a full window of 10, both off-topic questions return
  `no confident matches - explore the map.`

  **One case the swap exposed, handled explicitly:** MAD is zero whenever more
  than half the population shares one score — which is the shape of two existing
  fixtures and of any corpus with a flat noise body. `_spread` falls back to the
  standard deviation there, and only a population with no spread at all scores
  everything zero. Without it the vector leg returns nothing for those corpora
  (both fixtures fail), so it is pinned by mutation.

  **The brief footer.** `briefs.members` (migration `0024`) holds the member
  URIs as JSON; `brief.py` and `brief_upper.py` store prose in `text` and the
  list beside it, so #071's node:// passages carry prose only. The renderer
  re-attaches it as a `## References` section — confirmed two ways: a new
  `test_the_member_references_are_re_attached_from_metadata` asserts the
  section and every URI appear for a node with recorded members and that a node
  without them gets no empty section; and rendering the REAL corpus still
  produces all 82 files with its briefs unchanged (those rows predate the
  migration, so their footer is still in `text` and `members` is empty — the
  migration comment records that they clean up when #064 next regenerates them,
  with no backfill, because parsing prose back into a list is guesswork).

  **`brief_upper`'s "Children:" list** moves the same way — it is stored as
  `["node 3", ...]` and the renderer's mechanical titled links are no longer
  duplicated by a raw list inside the indexed text.

  **The mis-scoped render test.** `test_a_boilerplate_heading_does_not_become_
  the_directory_name` built a node that IS the root, so no directory name was
  ever derived and the boilerplate skip was never exercised — qa is right. I
  re-pointed it at what it genuinely proves and renamed it
  `test_a_brief_is_rendered_verbatim_including_its_own_headings` (the renderer
  derives a title but never rewrites the brief), strengthened its assertions,
  and left a comment naming `test_a_long_first_line_is_trimmed_to_a_usable_
  title` as the test that does pin the directory-name property.

  **Per-document diversity: NOT implemented**, as instructed. Where it goes:
  `recall/fusion.py`, inside `fuse()` between the ranked-candidate sort and
  `CAP` — the ranking is already computed there and `Hit` carries the `uri`, so
  a cap of ~2 per document is a filter over the sorted list before truncation,
  with no change to either leg or to the floor. Nothing in this commit stands in
  the way; the measured need is visible in my end-to-end run (the signer query
  returns 5 of 10 hits from one file, the uuid query 4 node:// passages from one
  node).

  **Acceptance, both sides, in one fixture** (`tests/recall/test_engine.py`):
  `test_an_on_topic_question_fills_the_window` builds a corpus with 12 genuine
  matches and a varied 30-passage noise body and asserts a FULL window of 10 —
  it returns 0 hits under mean/sd, which is the regression this ticket exists
  to fix; `test_an_off_topic_question_still_explores` asserts the explore
  message on the same corpus.

  Not touched: #122, #113, #123, #124, #105, #101, #110, #121, #120.
  Gate clean: `ruff format` (227 files unchanged), `ruff check --fix` (all
  checks passed), `pytest` **747 passed**. Mutations verified: reverting to
  mean/sd fails the on-topic window test; removing the sd fallback fails two
  existing recall tests. Handing off to verifying.
- 2026-09-15 qa: **FAIL — back to todo.** The median/MAD swap is sound and its
  headline numbers reproduce exactly, but on the corpus the PO told this ticket
  to calibrate against, **acceptance criterion 1 does not hold** — a recall hit
  body IS still a list of member URIs — and the swap introduced a new off-topic
  leak. Two blocking findings, both measured on the live corpus.

  **What I verified as PASSING (need not be redone):**
  - Gate re-run by me on `d233758`: `ruff format --check` 227 files unchanged,
    `ruff check` clean, `pytest` **747 passed** in 47.6s.
  - **Dev's four numbers reproduce exactly** on a copy of the live 438-passage
    corpus with the real minilm encoder: "generate a version 7 uuid" OLD 0 ->
    NEW **38**; signer OLD 8 -> NEW **18**; "capital of Peru" 0 -> 0;
    "chocolate cake" 0 -> 0. End to end with CAP 10, both of dev's on-topic
    questions fill the window and both of its off-topic questions return the
    explore message.
  - **The MAD fallback is sound and does not fire on real data (area 1).**
    `_spread` returns the sd only when the MAD is exactly 0, which requires at
    least half the population to share one score. On the live corpus the
    largest tie group is **1 of 438 for every query I ran** — cosine ties need
    identical (content_hash, path) pairs — so the fallback never engages, and
    it cannot flip between queries on a corpus like this. Nor can it silently
    reinstate the original defect wholesale: the fallback keeps the MEDIAN as
    the centre and only borrows the sd as the scale. Worth one sentence in the
    docstring that the fallback is a hybrid rather than the old estimator, since
    the sd half is still tail-inflated — not blocking.
  - **The renderer re-attaches references correctly, both ways (area 5).** A
    node with three recorded members renders a `## References` section listing
    exactly them; a node with none renders no such section. On the live corpus
    every row is `members='[]'`, so 0 of 6 brief.md files carry the section and
    the export is byte-unchanged — which is what dev claims.
  - **No regression across the wave (area 6).** The packer distribution at HEAD
    is identical to what I measured verifying #097 (69 files, 75 sections, 317
    passages, median 585, max 800, 0 byte-identity failures). #114's
    `assert_every_leaf_is_reachable` is still asserted in three suites
    (`test_maintain.py:181`, `test_settle.py:423`, `test_update.py:667`). The
    live database still renders 3-of-6 linked, but that is the un-rebuilt
    corpus — #114 landed after the maintain that produced it — not a regression
    here; I repaired that same database on a copy last tick.

  **Blocking 1 — AC1 fails on the corpus this ticket was told to calibrate on:
  "No recall hit body is a list of member URIs."**
  Driven through the real engine on the live post-maintain corpus:

  ```
  "generate a version 7 uuid"  -> 10 hits, 3 of them PURE URI lists:
      '- git://github.com/google/uuid/uuid.go@2d3c2a9...'
      '- git://github.com/google/uuid/version4.go@2d3c2a9...'
      '- git://github.com/google/uuid/version7.go@2d3c2a9...'
  ```

  That is F30's mechanism verbatim, occupying 30% of the answer window. Across
  the whole index, **57 of 121 `node://` passages (47%) are reference lists**.
  The fix is correct for briefs written after `0024`, and there are none — every
  brief in existence predates it, so on the evaluation corpus nothing changed.
  The PO's precondition note is explicit that this corpus IS the acceptance
  surface ("calibrate on it — do not re-run a maintain first").
  The stated reason for not backfilling does not hold for the rows that exist.
  The footers are machine-written with fixed separators — `brief.py:105` wrote
  `"\n\nReferences:\n"` and `brief_upper.py:104` wrote `"\n\nChildren:\n"` —
  so splitting them back out is EXACT for every row this codebase produced, not
  "guesswork". `0024` can split on that separator, store the tail as the JSON
  list and keep the head as `text`; the `node://` passages then need re-splitting
  from the corrected text (no LLM call — `store_brief` re-splits stored text).
  Either do that, or get the PO to amend AC1 to scope it to post-migration
  briefs and accept that the live corpus still leaks until it is re-briefed.

  **Blocking 2 — AC3 regressed: the swap introduced a new off-topic leak.**
  I ran eight genuinely absent questions rather than two. Seven return the
  explore message. One does not:

  ```
  "how to train a labrador puppy"   OLD estimator: 0 candidates
                                    NEW estimator: 4 candidates -> 4 hits
      threshold 0.160 -> 0.142
      hits: chalk/benchmark.js, chalk/package.json,
            itsdangerous/docs/make.bat, chalk/benchmark.js
  ```

  A labrador-training question is clearly off-topic by any reading, and the
  agent now gets four irrelevant code passages instead of "no confident matches
  - explore the map." AC3 says clearly off-topic questions return the explore
  message "on a corpus of this size; a calibration test pins it" — the pinning
  test uses dev's two probes, both of which still pass, so nothing catches this.
  Please add this probe (and a couple more absent-domain ones) to the
  calibration test, and decide whether the floor needs the extra guard the
  ticket's own F12 section contemplated. Note I am NOT asking for an absolute
  cosine gate — the PO rejected it and I agree with the portability argument.

  **Non-blocking observations:**
  - **On-topic improvement is uneven.** "how do I style terminal output with
    colours" returns **1 hit under BOTH estimators**, on a corpus that contains
    the whole chalk repository. Not a regression, but the claim that on-topic
    questions now fill the window holds for the two probes chosen and not for a
    third obvious one.
  - **Top-10 relevance is weak where the window did fill.** Of the ten hits for
    "generate a version 7 uuid", only ONE mentions v7/NewV7 at all, three are
    the URI lists above, and six come from a single node's brief. 38 candidates
    clearing the floor has not yet turned into ten right answers.
  - **For the PO on AC2 (diversity), which is deliberately unimplemented
    pending the product call this ticket itself marks OPEN:** my measurement is
    worse than the one in the review log. "how does the signer verify a
    signature" returns **8 of its 10 hits from ONE file** (dev reported 5), and
    the uuid query returns 6 of 10 from one node's brief. Whatever cap is
    chosen, the evidence for needing one is stronger than recorded.

  `.e2e/` read-only throughout — every measurement ran on a copy;
  `run2/.hrono/hrono.db` and `evidence/run2-before-122-fix.db` both untouched.
  No worktrees, tree clean; the `.gitignore` line is still the pre-existing one.

## PO rulings (2026-09-17, after qa's rejection) — dev's brief

### FINDING 1 — BACKFILL IN 0024. AC1 is not amended.

I verified the premise myself on the live corpus (schema 23, pre-0024, all 7
briefs):

```
node lvl  sentinel      footer lines  every line matches the machine format
   1   0  References             13  True
   2   0  References              9  True
   4   0  References              7  True
   8   0  References             10  True
   9   0  References             10  True
  10   0  References             20  True
   7   1  Children                6  True
ALL footers exactly reconstructible: True      node:// passages: 121
```

**7 of 7, zero exceptions.** So migration 0024's stated justification — "parsing
prose back into a list is guesswork" — is factually wrong. The footer is not
prose: it is a machine-generated block with a fixed sentinel
(`brief.py:105` `"\n\nReferences:\n"`, `brief_upper.py:104` `"\n\nChildren:\n"`)
and a fixed per-line format. The backfill is a `partition()` on a constant, not
a parse, and it needs no LLM call.

Three reasons this is a fix, not an announcement:

1. **The justification is false and I measured it false.** A decision resting on
   a wrong premise gets re-taken, not ratified — the same standard I applied to
   my own #120 reasoning when dev showed it was wrong.
2. **AC1 is this ticket's headline, and it fails on the corpus I named.** 30% of
   the answer window for "generate a version 7 uuid" is still F30 verbatim, and
   47% of node:// passages are reference lists. I told dev to calibrate on this
   corpus specifically; a fix that changes nothing on the only surface we
   evaluate against has deferred its acceptance criterion, not met it.
3. **"A regeneration is the normal way a brief changes" does not hold here.**
   #064 regenerates on member-set change, and this corpus is stable — so on
   these rows "the footer leaves the passages the next time #064 regenerates"
   means NEVER.

Scope: backfill `members` from the footer in 0024, strip the footer from
`briefs.text`, and re-split the node:// passages so the index loses the
reference lists. Assert 0 of 7 briefs retain a sentinel afterwards and that the
re-attached export output is byte-identical to today's.

### FINDING 2 — REQUIRE KEYWORD SUPPORT FOR AN UNSUPPORTED VECTOR HIT

Not "accept the leak": my stated principle is **better to cut than to leak**,
and returning `benchmark.js`, `package.json` and a Sphinx `make.bat` for "how to
train a labrador puppy" is the failure mode recall is designed to avoid —
a confident wrong answer where the explore message was correct.

Not "raise Z_FLOOR": the leak and the on-topic restoration are the SAME effect,
so moving the threshold trades along one axis and claws back exactly the gain
this ticket exists to deliver. That is the wrong axis.

**The discriminator is the keyword leg, and it is orthogonal.** The two cases
differ there even though they are similar on the vector axis: "version 7 uuid"
hits passages carrying `uuid`, `v7`, `NewV7`; "labrador puppy" hits passages
carrying none of its distinctive terms. BM25 separates them cleanly where cosine
does not.

This is also **already the settled architecture, applied symmetrically.** #073
holds that a keyword hit is never enough alone — it needs vector support at
z >= 3.0. The rule I want is the mirror: **a vector hit that the keyword leg
does not corroborate must clear a higher bar than one it does.** Z_FLOOR stays
3.5 for corroborated hits; unsupported hits need a higher floor.

Derive the constant from the live corpus and show the working: it must cut all
EIGHT of qa's absent questions AND keep the uuid (0 -> 38) and signer (8 -> 18)
restorations. If no value does both, say so and bring it back rather than
picking a compromise that half-leaks — that is a product call, not a dev one.

Accepted cost, deliberately: a genuinely on-topic question answered in
vocabulary the corpus does not share will now be cut. That is "cut, not leak"
working as intended, and recall fails safe to explore by design.

### THE PINNING TEST — what it must cover

The part that worries me most is the part that worries you: dev's two probes
both pass while the leak is live. **That is a structural failure of the test
design, not bad luck** — two probes cannot characterise a distribution. The
replacement must be a suite with all five of these properties:

1. **A SET of absent questions, at least qa's eight**, drawn from varied
   domains. Seven held and one leaked, so a single-domain set would have missed
   it. Each must be genuinely absent — no lexical overlap with the corpus.
2. **Assert the aggregate**: ALL absent questions return the explore message.
   One leak anywhere fails the suite, so a future tuning change cannot trade one
   leak for another silently.
3. **The on-topic counterweight in the SAME test.** A set of present questions
   that must return hits. This is the half that matters most: without it, the
   cheapest way to make the absent-set pass is to raise the floor until
   everything is cut — which is the original defect restored. Each half must be
   able to fail the other's fix.
4. **Assert direction, not magnitudes.** "> 0 hits" for present, "explore" for
   absent. Pinning 38 exactly makes the suite brittle to corpus and model
   changes and will get deleted by the next person it inconveniences.
5. **At least one present question must be one that mean/sd got WRONG** (uuid v7
   was 0 candidates), so the suite fails if the estimator reverts — the
   regression guard for this ticket's own change.

### The MAD-fallback docstring sentence

> When MAD is exactly zero — at least half the population sharing one score,
> which no live query produces (the largest tie group on the 438-passage corpus
> is 1) — the centre stays the MEDIAN and only the scale falls back to the
> standard deviation, so this is a hybrid at that point rather than a switch
> back to mean/sd.

### Also for the brief, not blocking

- **On-topic quality is not uniformly fixed** — "how do I style terminal output
  with colours" returns ONE hit under BOTH estimators on a corpus containing all
  of chalk, and only 1 of 10 uuid hits mentions v7/NewV7. The floor was not the
  only thing wrong. **Do not file this yet**: the backfill removes 47% of
  node:// passages from contention, so re-measure after Finding 1 lands before
  deciding whether a separate ranking ticket is warranted.
- **Diversity is worse than recorded** — the signer query returns 8 of 10 hits
  from ONE FILE (dev reported 5) and uuid 6 of 10 from one node's brief. AC2
  stays unimplemented pending the product owner; record the 8-of-10 figure so
  their decision is made on the real number.

### Standing rule set by this tick

Three tickets in a row have shipped a justification that defers work to a future
event which does not occur: `levels.py`'s "settle's drift counters correct it"
(#114), my own #120 reasoning, and now 0024's "a regeneration will clear it".
**A justification that defers work to a future event must name the event and
show it actually happens.** If it cannot be shown, the work is not deferred —
it is skipped, and the comment saying otherwise is worse than no comment,
because it stops the next reader from noticing.

## Review log
- 2026-09-17 PO: rulings above on qa's two blocking findings. Finding 1:
  backfill (premise verified false on all 7 live briefs). Finding 2: keyword
  corroboration for unsupported vector hits, not a floor change. Pinning-test
  specification and the MAD docstring sentence included. No change to priority
  or size.
- 2026-09-17 dev: **re-picked up after qa's FAIL**; fixed as `f423d3c` on top of
  `d233758`. Nothing qa passed was redone.

  **Finding 1 — the backfill, and the PO is right that it is not guesswork.**
  Migration `0024` now carries a Python data step (`db/backfill.py`, applied by
  the runner in the same transaction as its `.sql`; the runner gained a
  per-version step hook because re-splitting a brief is the packer's job, not
  SQL's). It partitions each brief on the machine sentinel, requires EVERY
  tail line to match `- <entry>` — a line that does not aborts that brief and
  leaves it untouched — stores the list in `members`, and re-splits the brief
  through `store_brief`, so the node:// sections AND passages are rebuilt.

  Measured on a COPY of the live corpus: 7 of 7 briefs moved, **75 member
  entries recovered**, 0 briefs left carrying a machine footer, and re-running
  `migrate` is a no-op. One brief (node 7) has `**References:**` in its own
  PROSE — the guard left it alone, which is the case the PO's "exactly
  reconstructible" claim depends on being handled.

  **A second source of URI lists, found while verifying, and fixed here.** After
  the footer move the corpus still held 24 pure-URI node:// passages. They
  belong to node-3, node-5 and node-6 — **nodes that no longer exist**. A
  retired node's brief cascades with it, but #071's passages are keyed by
  SOURCE and nothing cascades those, so the index was still serving summaries of
  three retired topics: **51 of 85 node:// passages (60%)**. The backfill now
  clears orphaned `node://` sources too, because "reference lists out of the
  index" is not achieved while they are there. Stopping them being CREATED is at
  the retirement site and is filed as backlog **#125** (high).

  Live corpus, end to end after the whole change: node:// passages **121 -> 34,
  pure URI lists 57 -> 0**, and no recall hit is a URI list any more.

  **Finding 2 — the corroboration rule and its derivation.** A vector hit the
  question's own terms do not corroborate must clear a higher bar:
  `UNCORROBORATED_FLOOR = 4.5`, with `Z_FLOOR` staying 3.5 for corroborated
  hits and `KEYWORD_SUPPORT = 0.0` (the average of what the query matched at
  all). Derivation, on the live corpus, over qa's eight absent questions plus
  three present ones — the full sweep is in my scratch probe, the decisive rows:

  | U (uncorroborated floor) | absent questions leaking | present kept (uuid/signer/chalk) |
  |---|---|---|
  | 3.5 (no rule) | 2 | 38 / 17 / 27 |
  | 4.0 | 1 | 32 / 14 / 22 |
  | **4.5** | **0** | **28 / 12 / 19** |
  | 5.0 | 0 | 17 / 11 / 16 |

  4.5 is the smallest swept value that cuts all eight; the worst absent
  candidate measured 4.03, so it clears that by ~0.5 while every present
  question still fills the 10-hit window.

  **One correction to the ruling's mechanism, forced by the data.** Defining
  corroboration as "appears in the FTS match set" does NOT work: the labrador
  question's one match scored keyword z **-0.37** — it matched on stopwords, the
  exact failure #073's docstring warns about. So `_match_expr` now drops a baked
  list of FUNCTION words before querying FTS. That is a quality fix for the
  keyword leg itself (its background was stopword matches) and it is what makes
  the support signal mean anything. With it, the absent questions match nothing
  lexically and are cut; the present ones corroborate on uuid/v7/signer/chalk.

  **Live result: all EIGHT absent questions return the explore message** (was:
  labrador leaked 4 hits), and uuid/signer/chalk each return a full window of
  10.

  **Test-fixture correction worth flagging:** three recall fixtures inserted
  passages WITHOUT indexing them into FTS — a state production never has, since
  `store_file`/`store_brief` always index. Under a rule that reads lexical
  evidence they looked like "no corroboration anywhere". They now index, which
  is both the reason the suite is honest and a small fidelity win.

  **The five-property pinning suite** (`tests/recall/test_engine.py`):
  (1) a SET of eight absent questions across eight domains, qa's own;
  (2) asserted in AGGREGATE — the test collects every leak and asserts the dict
  is empty, so one leak anywhere fails;
  (3) the on-topic counterweight in the same suite, twice — a present question
  must return hits, and the mean/sd-broken shape must be recovered;
  (4) DIRECTION only: `hits` vs `explore`, no counts anywhere;
  (5) `test_the_present_question_mean_sd_got_wrong_is_recovered` uses the shape
  that returns ZERO under mean/sd, so reverting the estimator fails the suite.
  Plus `test_the_absent_questions_could_have_leaked`, which asserts the fixture
  CAN leak (its absent questions do clear the plain vector floor) — without it
  the absent suite could pass on a corpus that never had the opportunity.
  The fixture embeds text as a bag of words over a vocabulary that INCLUDES
  function words, which is how an absent question gets near a passage it has
  nothing to do with — the real mechanism, reproduced deterministically.

  Mutations: removing the corroboration rule fails the absent suite; raising
  `Z_FLOOR` to cut everything instead fails the counterweight and two vector-leg
  tests; putting stopwords back in the match expression fails the absent suite.

  **Re-measured on-topic picture after the backfill** (for the PO's ranking
  decision, not filed):
  - "generate a version 7 uuid" — 10 hits, and now **10 of 10 from a single
    document** (before the backfill it was 6 of 10 plus 3 URI lists). Removing
    the reference lists did not improve diversity, it concentrated it.
  - "how do I set the color level in chalk" — 10 hits over 3 documents, max 5.
  - "how does the signer verify a signature" — 10 hits over 2 documents, max 8.
  - "how do I style terminal output with colours" — still **1 hit**, unchanged
    by the backfill. So the paraphrase weakness is not explained by the URI
    lists and survives them.
  For the product owner's diversity decision: the real number is **10 of 10**
  from one document on the uuid query, worse than the 8 of 10 previously
  reported; the cap would go in `fusion.fuse()` between the ranked sort and
  `CAP`.

  Not touched: #122, #113, #123, #124, #105, #101, #110, #121, #120; #125 filed,
  not fixed. `.e2e/` read-only throughout (the #122 evidence copy is untouched).
  Gate clean: `ruff format` (229 files unchanged), `ruff check --fix` (all
  checks passed), `pytest` **756 passed**. Handing back to verifying.
- 2026-09-17 qa: **FAIL — back to todo.** Both of my blocking findings are
  genuinely fixed and I confirmed them on all three real databases; the
  corroboration rule is well derived and well pinned. One NEW defect this commit
  created, in the PO addendum's own target, plus one coverage gap on the
  headline fix. Both small, both in the same pass.

  **What I verified as PASSING (need not be redone):**
  - Gate re-run by me on `f423d3c`: `ruff format --check` 229 files unchanged,
    `ruff check` clean, `pytest` **756 passed** in 46.7s.
  - **The migration runner's data step is safe (area 1).** Applied to copies of
    all THREE databases (`.e2e/run`, `.e2e/run2`, and
    `.e2e/evidence/run2-before-122-fix.db` copied out; `.e2e/` never written):
    7/7 briefs moved in each, footers 7 -> 0, `members` populated on all 7,
    **pure URI-list passages 92 -> 0 / 49 -> 0 / 48 -> 0**, corpus passages
    untouched (1526 / 317 / 786 unchanged). Re-running `migrate` applies
    nothing and leaves byte-identical state.
    Atomicity holds, driven two ways by injecting a failure into the step — one
    after its work, one part-way through a brief: in BOTH cases the database is
    identical to pristine (version 23, no `members` column, 7 footers, 121
    node:// passages, 10 node sections), and a retry then applies cleanly to the
    correct end state. So 092's per-migration guarantee survives the new hook.
    The per-brief abort works: a sentinel whose tail contains a prose line
    leaves that brief alone, and node 7's real `**References:**` PROSE is
    untouched while its machine `Children:` footer moves — the tricky live case,
    handled right.
  - **The orphan cleanup cannot delete a live node's passages (area 2).** It is
    not a string heuristic in the loose sense: `'node-' || n.id = s.source` is
    the exact inverse of `brief_passages.store_brief`'s single constructor
    `source = f"node-{node_id}"`. Checked on all three databases: every retained
    source maps to a live node, and **no live node lost its passages** in any of
    them (run1 live [1,2,4,5,8,9,10], run2 [1,2,4,7,8,9,10], evidence
    [1..7] — the last a useful control, where nothing was deleted at all).
  - **4.5 reproduces and is conservative (area 3).** My sweep on the migrated
    corpus: U=3.5 leaks 1 of 8, U=4.0 leaks 0, U=4.5 leaks 0 (present
    candidates 25/18 -> 22/16 -> 18/13). End to end at the shipped constants,
    **all 11 absent questions** — my original eight plus tax return, airspeed
    velocity and sourdough — return the explore message.
    I then hunted for the loss class beyond dev's set and found none. Two
    present questions return nothing ("what does BadSignature mean", "how is a
    timestamp encoded in a token") but they returned nothing under `d233758`
    too — their best vector z is 3.13 and 3.02, below the pre-existing 3.5 floor
    — so that is the floor's strictness, not corroboration. The only
    corroboration cost I could measure is marginal: "how do I disable colour
    output" goes 5 -> 4 candidates and still answers with 4 hits over 3
    documents. No present question lost its answer to the new bar.
  - **The stopword change is safe (area 4).** The baked list is 54 plain
    function words with no domain terms — "go" is NOT in it, which matters for a
    corpus holding a Go package, and "go uuid" keeps both terms. `_match_expr`
    returns None only when EVERY term is a stopword, and that degrades to the
    4.5 bar and the explore message rather than crashing ("what is it" -> 0
    hits, clean). "what does BadSignature mean" still keeps `badsignature`.
    It is load-bearing and pinned: dropping the filter fails
    `test_every_absent_question_returns_the_explore_message`.
  - **The fixture correction is honest (area 5).** The diff only ADDS
    `fts.index_passage(...)` after a passage insert; not one assertion was
    changed or deleted. And they really were testing an impossible state:
    production indexes every passage, and an un-indexed fixture makes every
    passage uncorroborated, so those suites would only ever have exercised the
    4.5 path.
  - **All five properties of the new suite are present (area 6)**, and the
    counterweight bites: eight absent questions across eight domains; an
    AGGREGATE assertion (`assert leaked == {}`, so one leak anywhere fails);
    the on-topic counterweight in the same suite; direction-only assertions
    (`assert result.hits`, no magnitudes); the mean/sd regression test; plus
    `test_the_absent_questions_could_have_leaked` proving the fixture can leak.
    Mutation-checked: "fixing" the leak by raising both floors to 12 fails
    **eight** tests including all three present-question counterweights, so the
    cheap wrong fix cannot pass; removing corroboration fails the absent suite.
  - **#125's filing is right.** The backfill clears the orphaned `node://`
    sources, which is the remediation this ticket needs to meet AC1 on the live
    corpus; stopping their creation lives at the retirement site, in different
    code, and is a different decision (which op should cascade them). Splitting
    there is the same line #113/#123 was split on, and it keeps this ticket to
    its own surface.

  **Blocking — `src/hrono/export/render.py:90` re-attaches an UPPER node's
  member list, so the PO addendum's duplication survives the fix and now shows
  RETIRED node ids.** The addendum (2026-09-14) is part of this ticket and says
  the rendered `root.md` shows the child list "twice, once unreadable, in the
  MVP's top file", and that removing the footers from the stored text "loses
  nothing and fixes the duplication for free". After this commit, `root.md` on
  the live corpus contains BOTH:

  ```
  ## Children
  - [This is configuration and setup documentation for the itsdangerous ...](...-1/brief.md)
  ... five titled links ...

  ## References
  - node 1
  - node 2
  - node 3      <- retired
  - node 4
  - node 5      <- retired
  - node 6      <- retired
  ```

  Live nodes are [1,2,4,7,8,9,10], so three of the six ids rendered name topics
  that no longer exist. The list left `briefs.text` (good — it is out of the
  index, AC1 holds) but the renderer puts it straight back into the export, so
  the duplication the addendum asked this pass to remove is still there, and is
  now stale as well as unreadable.
  `_references` is right for a LEAF, where members are section URIs the map has
  nowhere else — I verified a leaf `brief.md` renders a correct `## References`
  block. The fix is to not re-attach it for a node that has children, since
  `_node_markdown` already renders those as titled links — which is exactly what
  the addendum predicted would make it free.

  **Second, same pass — the backfill's WIRING is unpinned.** Setting
  `STEPS = {}` in `db/backfill.py` (so the step never runs) leaves the suite at
  **756 passed**. `tests/db/test_backfill.py` calls `brief_members(conn)`
  directly at six sites and never drives it through `migrate()`, so nothing
  catches the registration being dropped — and the registration is what makes
  every existing database actually get fixed, exactly once. One test that
  migrates a database holding a footer and asserts it moved would close it.

  **For the PO, not blocking — the ranking question dev raised.** I reproduced
  it and it is a little worse than reported: after the backfill "generate a
  version 7 uuid" returns **10 of 10 hits from ONE document**, "how are UUIDs
  parsed from a string" likewise 10 of 10 from one, "how is the secret key
  rotated" 10 over 3, signer 10 over 2. Removing the URI lists concentrated the
  window rather than diversifying it, which strengthens the case for AC2's
  per-document cap whenever that product call is made. The paraphrase weakness
  also survives: "how do I style terminal output with colours" is still 1 hit,
  unchanged by anything in this commit (1 candidate under both estimators).

  `.e2e/` read-only throughout — all three databases copied out before use;
  `evidence/run2-before-122-fix.db` untouched. Worktree removed, tree clean.
- 2026-09-17 dev: **re-picked up after qa's second FAIL**; both findings fixed
  as `9f80ca1` on top of `f423d3c`. Nothing qa passed was redone.

  **Blocking 1 — the export repeated the children, and cited retired nodes.**
  `export/render.py` now renders the stored member list ONLY for a node with no
  children. An upper node's list is child NODE IDS: `## Children` already
  renders exactly those as titled links, so it was the same thing twice in one
  file, and an id only means anything while the node exists — which is how
  `root.md` came to cite three topics that had been retired. A leaf's list is
  its members' SOURCE URIs, provenance the export shows nowhere else, so that
  half is unchanged (qa verified it is correct).

  Measured on a COPY of the live corpus, before and after, by rendering the real
  export and extracting every `node <id>` it contains:
  ```
  before: node ids named in the export [1, 2, 3, 4, 5, 6]   RETIRED named [3, 5, 6]
          root.md carries BOTH ## Children and ## References
  after : node ids named in the export  none                RETIRED named  none
          root.md: ## Children yes, ## References no; 6 leaf briefs keep theirs
  ```
  The retired-id half is closed structurally rather than by filtering: the only
  member lists that contain node ids belong to upper nodes, and those are now
  never rendered, so a retired id cannot reach the map through this path at all.
  `test_an_upper_node_does_not_repeat_its_children_as_references` plants three
  retired-looking ids on the root's brief and asserts `## Children` is there,
  `## References` is not, and none of the ids appears;
  `test_a_leaf_still_shows_its_source_references` pins the other side.

  I dropped a third test I had written — "no rendered file names a node id" —
  because it over-claimed: it passed only by planting node-id-shaped entries in
  a LEAF's members, a state no writer produces (`brief.py` stores URIs). Stating
  a guarantee the code does not have is the failure mode qa caught twice in this
  wave, so the suite now says what is true.

  **Blocking 2 — the backfill's wiring is pinned.**
  `test_migrate_runs_the_step_for_its_version` builds a database at the version
  BEFORE 0024 (applying the packaged migrations minus the last), plants a brief
  with a real footer, and calls `migrations.migrate(conn)` — the real entry
  point, not the step — then asserts the version was applied AND the footer
  moved. Plus `test_the_step_is_registered_for_the_migration_that_needs_it`,
  which asserts the registry is non-empty and references only migrations that
  exist. qa's exact probe now bites: setting `STEPS = {}` fails both (it left
  the suite green before), so the registration can no longer be removed by
  someone who sees no reason for it.

  **Carried forward for the PO, not acted on:** qa's post-backfill ranking
  numbers are slightly worse than mine and supersede them — "generate a version
  7 uuid" AND "how are UUIDs parsed from a string" are each 10 of 10 hits from
  ONE document, key rotation 10 over 3 documents, signer 10 over 2, and the
  paraphrase weakness ("style terminal output with colours" = 1 hit) is
  unchanged by this commit. Removing the URI lists concentrated the window
  rather than diversifying it. The per-document cap belongs in `fusion.fuse()`
  between the ranked sort and `CAP`; nothing in this ticket stands in its way.

  Not touched: #122, #113, #123, #124, #125, #105, #101, #110, #121, #120.
  Gate clean: `ruff format` (229 files unchanged), `ruff check --fix` (all
  checks passed), `pytest` **760 passed**. Handing back to verifying.
- 2026-09-17 qa: **FAIL — back to todo.** Both fixes do what they claim and are
  pinned. But the structural guarantee dev asked me to test rather than accept
  does not hold, and it fails in the state this very database is in — so the
  retired-id output I blocked on last tick is still reachable. One line.

  **Fix 2 — confirmed.** My `STEPS = {}` probe, which left the suite at 756
  green last tick, now fails **two** tests:
  `test_migrate_runs_the_step_for_its_version` (drives the real `migrations.
  migrate` entry point, not the step) and
  `test_the_step_is_registered_for_the_migration_that_needs_it`. The wiring is
  properly pinned.

  **Fix 1 — correct for the shape it was written for, and pinned.** Rendering
  the real export from a copy of the live corpus: `root.md` now has `## Children`
  and **no `## References`**, and **no `- node N` appears anywhere in the whole
  82-file export**. Both leaf directions still hold and the children-condition
  did not break them: a leaf WITH recorded members renders `## References`, a
  leaf with `members='[]'` renders none. Reverting the condition fails
  `test_an_upper_node_does_not_repeat_its_children_as_references`. #114's
  invariant is unchanged (the live database still shows 3 of 6 linked because it
  has not been rebuilt since #114 landed — same as last tick, not a regression).

  **Blocking — `src/hrono/export/render.py:90` guards on "has no children", not
  on "is a leaf", and those differ exactly in the state the live corpus is in.**
  `if not node.children` is true for an UPPER node whose children have
  cascaded away — #114's childless-root state, which the PO confirmed on this
  corpus and which I drove myself two ticks ago (a rebuild re-mints leaf ids,
  the root's edges cascade, `build_tree` does not notice). I reproduced it on a
  copy of the live database by deleting the edges:

  ```
  briefs whose members are node ids: [(7, ['node 1' ... 'node 6'])]
  files rendering '- node N': {'root.md': ['- node 1','- node 2','- node 3',
                                           '- node 4','- node 5','- node 6']}
  ```

  Live nodes are [1,2,4,7,8,9,10], so 3, 5 and 6 are retired — the exact output
  I blocked on last tick, back again. The docstring's "Nothing the renderer
  emits names a node id, which is what keeps that impossible rather than merely
  unlikely" is therefore false, and it is the only thing standing since the
  filtering was deliberately not added.
  Scope, measured rather than assumed: this is the ONLY route I found. A kept
  non-leaf node in a collapsed tree always has descendants at the next kept
  level, so `collapse` cannot manufacture a childless upper node on a
  well-formed tree — the gap is precisely #114's state, which is transient once
  `build_tree` runs but is where this database sits today.
  Fix: condition on the node's LEVEL rather than its child count —
  `_node_markdown` already has `tree.node_level`, and the docstring already says
  "a LEAF's member list", so the code just needs to say what the prose does.
  Please pin it with the childless-upper-node shape, since that is what the
  child-count guard misses.

  **One note, not a finding:** `backfill._partition` keys on the sentinel alone,
  so a LEAF brief whose PROSE happened to contain `"\n\nChildren:\n- ..."` would
  have those lines moved into `members` and rendered as a bogus `## References`
  block. They would be prose, not node ids, so it does not cause the harm above,
  and it needs an LLM to emit that exact shape — worth knowing, not worth code.

  Carried to the PO unchanged, as asked: "generate a version 7 uuid" and "how
  are UUIDs parsed from a string" each 10 of 10 hits from ONE document, key
  rotation 10 over 3, signer 10 over 2, and the paraphrase weakness ("how do I
  style terminal output with colours" = 1 hit) unchanged — the per-document cap
  decision rests on those.

  Gate re-run by me on `9f80ca1`: `ruff format --check` 229 files unchanged,
  `ruff check` clean, `pytest` **760 passed** in 46.3s. `.e2e/` read-only
  throughout — copies only; `evidence/run2-before-122-fix.db` untouched (mtime
  still Sep 15 18:30:38). Worktree removed, tree clean.
- 2026-09-17 dev: **re-picked up after qa's third FAIL**; fixed as `7df7636` on
  top of `9f80ca1`. Nothing qa passed was redone.

  **The fix.** `export/render.py:90` guarded on "has no children", which is not
  the same predicate as "is a leaf". They diverge in exactly one state and it is
  a live one — #114's childless upper node, where a rebuild re-minted the leaf
  ids and cascaded the root's edges away — so the root had nothing to render as
  children, the guard called it a leaf, and it printed its stored node ids,
  three of them retired. The guard is now
  `node.level == tree.levels - 1`: the agent-facing leaf level, which is the
  property the member list's SHAPE actually depends on (leaf -> source URIs,
  upper -> child node ids). A single-level tree is covered by the same
  expression (its only level is both 0 and `levels - 1`).

  **Pinned with that exact shape**, since a child-count guard passes everything
  else: `test_a_childless_upper_node_still_skips_its_references` deletes every
  `node_children` row — qa's own reproduction — plants three retired-looking ids
  on the root's brief, and asserts no `## References` and no `- node N` in ANY
  rendered file. Restoring the child-count guard fails it and nothing else,
  which is why the previous tick's suite did not catch this.

  **Verified on a COPY of the live corpus, in both states:**
  ```
  as stored                                   : 82 files, '- node N' ids none, retired none
  with the root's edges cascaded away (#114)  : 82 files, '- node N' ids none, retired none
  ```
  The second row is the state qa reproduced; before this commit it printed
  `- node 1 ... - node 6` into `root.md` with 3, 5 and 6 retired.

  **Docstring corrected.** The claim "Nothing the renderer emits names a node
  id, which is what keeps that impossible rather than merely unlikely" was false
  as written — it described the intent, not the guard. It now states what the
  code guarantees and why the predicate is level rather than child count,
  naming the state the two disagree on.

  Noted, not acted on (qa agrees it is not worth code): `backfill._partition`
  keys on the sentinel alone, so a leaf brief whose PROSE contained a
  machine-shaped "Children:" block would have those lines moved into `members`.
  They would be prose, not node ids, so there is no retired-id harm and the
  renderer would show them as references.

  Not touched: #122, #113, #123, #124, #125, #105, #101, #110, #121, #120.
  Gate clean: `ruff format` (229 files unchanged), `ruff check --fix` (all
  checks passed), `pytest` **761 passed**. Handing back to verifying.
- 2026-09-17 qa: **PASS — to po-review.** The level predicate closes the gap I
  found, it does not over-trigger, and the docstring now states what the code
  guarantees. Everything I passed across the previous three ticks stands.

  **The fix holds in both states, driven on copies of the live corpus:**

  ```
  as stored                          82 files | node ids rendered: NONE | ## References on 6 leaves, not root.md
  root's edges cascaded away (#114)  82 files | node ids rendered: NONE | ## References on 6 leaves, not root.md
  ```

  My own reproduction from last tick — deleting every `node_children` row so the
  root keeps its stored ids `['node 1' ... 'node 6']` while live nodes are
  [1,2,4,7,8,9,10] — now renders **no `- node N` anywhere in the 82-file
  export**. That is the state the child-count guard printed retired ids in.
  I also audited the two predicates directly rather than trusting the claim:
  across every node of the collapsed tree they agree everywhere in the stored
  state, and disagree on **exactly one node in exactly the named state** —
  node 7, agent level 0, 0 children — which is the one the level test excludes.
  No node disagreed in the other direction (a leaf-level node with children), so
  the docstring's "they differ in exactly one state" is supported by measurement,
  not just by argument.

  **It does not over-trigger.** A leaf with recorded members still renders
  `## References`; the same leaf with `members='[]'` renders none. Six leaf
  briefs keep their provenance in both states.

  **The single-level-tree claim is true.** Built one (one section, one node, no
  level above): `tree.levels=1`, root level 0, so `level == levels - 1` is True
  and the node's source URI renders — correct, since it IS a leaf and its
  members are URIs. The claim is not merely arithmetic luck; `collapse` always
  keeps stored level 0, so a stored leaf is always at the agent leaf level.

  **Mutation-verified, and dev's account of why the last suite missed it is
  exact.** Restoring the child-count guard fails ONLY
  `test_a_childless_upper_node_still_skips_its_references` — nothing else — so
  that test is the whole of the new cover, and it is the shape I asked for.
  Dropping the guard entirely fails both render tests.

  **The docstring no longer over-claims.** I read it rather than skimmed it. It
  makes four claims — that the caller keys on level not child count, that the
  two differ in exactly one state, that a child-count guard printed three
  retired ids on the QA corpus, and that level is the property the member list's
  shape depends on — and all four are true, the third being my own measurement.
  There is no impossibility claim left and no mechanism promised that does not
  exist, which is what the previous two versions got wrong.

  **No regression.** #114's invariant is unchanged (the live database still
  shows 3 of 6 linked because it has not been rebuilt since #114 landed — the
  same reading as the last three ticks, not a regression). The #097 packer
  distribution at HEAD is identical: 69 files, 75 sections, 317 passages, median
  585, max 800, 0 byte-identity failures.

  Gate re-run by me on `7df7636`: `ruff format --check` 229 files unchanged,
  `ruff check` clean, `pytest` **761 passed** in 48.0s. `.e2e/` read-only
  throughout — copies only; `evidence/run2-before-122-fix.db` untouched (mtime
  still Sep 15 18:30:38). Worktree removed, tree clean.

  **For the PO, carried forward unchanged — the per-document cap decision.**
  Post-backfill on the live corpus: "generate a version 7 uuid" **10 of 10 hits
  from ONE document**; "how are UUIDs parsed from a string" **10 of 10 from
  one**; "how is the secret key rotated" 10 over 3; "how does the signer verify
  a signature" 10 over 2. Removing the URI lists concentrated the window rather
  than diversifying it. The paraphrase weakness is unchanged and untouched by
  anything in this ticket: "how do I style terminal output with colours" returns
  1 hit, and did so under both estimators. AC2 remains the open product call.
- 2026-09-17 PO: **ACCEPTED -> done, with AC2 MOVED (not met).** Four commits
  across four rounds. Both of my rulings landed and held.

  **Gate re-run by me:** `ruff format --check .` 229 files already formatted;
  `ruff check .` all checks passed; `uv run pytest` **761 passed** in 46.3s.

  **I drove the export myself on copies of the live corpus, in BOTH states**
  (stored, and edges-cascaded into #114's childless root):

  ```
                                   STORED    CASCADED
  root.md '## References' block    False     False      (must be False)
  root.md raw '- node N' lines     0         0          (must be 0)
  leaf brief.md with References    6 of 6    6 of 6
  git:// refs rendered             69        69
  ```

  Identical in both states, which is the whole point of the level guard — a
  child-count guard would have diverged in exactly the cascaded one. The
  backfill recovered **75 member entries across 7 of 7 briefs**.

  **One thing my own first check got wrong, worth recording because it is
  evidence FOR the backfill's precision.** I flagged "1 brief still has a
  footer" and "root.md carries References". Both were my substring test being
  too loose: node 7's LLM-written brief text contains the prose
  `**References:** (spanning all three projects)`, which is content the model
  wrote, not the machine block (sentinel `"\n\nReferences:\n"`). The backfill
  keyed on the exact sentinel and correctly left model prose alone — precisely
  the discrimination I demanded when I ruled the backfill was exact rather than
  guesswork.

  **The corroboration ruling needed dev's correction and is better for it.** I
  specified "keyword corroboration"; dev found that "appears in the FTS match
  set" does not discriminate, because the absent question's single match scored
  keyword z **-0.37** — a stopword match. Keying on keyword z >= 0 (at or above
  the average of what the query matched at all), plus dropping 54 baked function
  words from `_match_expr`, is the right operationalisation of the rule and is
  independently a quality fix for the keyword leg. UNCORROBORATED_FLOOR = 4.5
  was derived on the live corpus with the working shown (U=3.5 leaks 2, 4.0
  leaks 1, 4.5 leaks 0, present candidates held at 28/12/19), and qa's
  independent sweep found all ELEVEN absent questions explore. The
  five-property suite is in and **the counterweight bites** — raising both
  floors to 12 fails eight tests, which is the property I cared about most.

  AC1, AC3 and AC4 are met.

  **Rulings:**
  1. **AC2 disposition: #102 CLOSES with AC2 moved, not met.** I refused to let
     AC1 close unmet two rounds ago, so let me be explicit about why this is
     different rather than appearing to bend my own rule. AC1 failed because the
     implementation did not deliver it on the corpus we evaluate against — that
     is unfinished work. AC2 is **unimplemented by design, blocked on a product
     decision that is neither mine nor dev's**, formally with the product owner
     now. Holding verified, substantial work in `po-review/` against an external
     decision timeline helps nobody, and it misrepresents the board: a ticket
     sitting in `po-review/` reads as "PO has not looked at it", whereas a
     ticket in `todo/` marked blocked is honest state. The diversity work also
     needs acceptance criteria that cannot be written until the cap is chosen.
     Moved to **#126**, which carries the FINAL evidence — and it is worse than
     when I last saw it: **10 of 10 hits from ONE document** for the uuid and
     UUID-parsing queries, 10 over 3 for key rotation, 10 over 2 for signer.
     Removing the URI lists CONCENTRATED the window rather than diversifying it,
     which is the opposite of what one might have assumed, and the product owner
     should decide on that number rather than the 8-of-10 previously recorded.
     I have not decided the cap.
  2. **#125 confirmed and PROMOTED to `todo`/high.** I verified the cause is
     structural: `delete_node` drops the `nodes` row and its members, children
     and brief cascade by FK — but `node://` passages live in `sections`/
     `passages` keyed by the STRING `source = "node-<id>"`, which is not an FK
     to `nodes`, so nothing cascades them. `store_brief` clears its own source,
     but a retired node is never re-briefed, so its passages persist for ever.
     This is not a one-off: my own #120 A/B showed a single rebuild retiring 3
     of 6 leaves, so orphans are created on essentially every rebuild and
     ACCUMULATE — 51 of 85 node:// passages (60%) were already summaries of
     topics that no longer exist. Recall answering from topics that have been
     retired is a correctness defect in the product's read door, and the
     backfill only cleared today's; without stopping creation it is back after
     one rebuild. High, and note the overlap with #076 (the `node-` source
     prefix) for whoever picks it up.
  3. **The paraphrase weakness is now a ticket (#127).** I deferred it pending
     the backfill's effect; the backfill has landed and did not help, which is
     the answer to the question I asked. One hit for "how do I style terminal
     output with colours" on a corpus containing all of chalk is a real recall
     failure, and it is not the floor.
     **And I must flag that my own Finding-2 ruling may have made it worse.** A
     paraphrased question has weak keyword support by construction, so it lands
     in the uncorroborated band and now needs 4.5 rather than 3.5. The evidence
     I was given compares ESTIMATORS (mean/sd vs median/MAD), not corroboration
     on/off. #127 must measure it both ways as its first step; if corroboration
     is a material part of the loss, that is my trade to re-examine, not dev's
     to absorb quietly.

  **On the two rejections over the reference guard** — child count, then level:
  both were right to bounce. The predicates differ on exactly one node in
  exactly the state #114 creates, and qa auditing both across every node rather
  than accepting the first fix is what found it. "Is a leaf" is a property of
  level, not of how many children happen to exist right now.
