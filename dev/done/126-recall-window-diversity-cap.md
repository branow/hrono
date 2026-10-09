---
id: 126
title: Recall returns up to 10 of 10 hits from a single document — the window needs a diversity rule
priority: high
size: small
depends_on: [102]
spec_refs: [build-order.md#T27, how-hrono-works.md]
found_by: e2e QA 2026-09-03 (F31); final evidence from #102's verification 2026-09-17
---

## UNBLOCKED 2026-09-21 — the decision is at the bottom of this ticket

Was: #102's AC2, held here because it needed a product call rather than dev
work. PO has now ruled (see **PO ruling** below, which supersedes the open
questions in Description and rewrites the acceptance criteria). The standing
recommendation of "a hard cap of ~2" was NOT adopted — read the ruling before
implementing.

## Context

`recall/fusion.py`'s weighted RRF caps the result count at 10 but has no notion
of where the hits come from, so one document can fill the whole window.

**Final measurement, on the live 438-passage corpus AFTER #102's footer removal
and backfill:**

| question | hits | distinct documents |
|---|---|---|
| "generate a version 7 uuid" | 10 | **1** |
| "how are UUIDs parsed from a string" | 10 | **1** |
| "how is key rotation handled" | 10 | 3 |
| "how does the signer verify a signature" | 10 | 2 |

**Removing the URI lists CONCENTRATED the window rather than diversifying it.**
That is the opposite of what one might reasonably have assumed — the reference
lists had been occupying slots that now go to more passages from the same
document — and it is why the decision should be taken on these numbers rather
than the 8-of-10 figure recorded earlier in #102.

## Description

Insert a diversity rule into the result window. dev has already left the slot in
`fusion.fuse()`, between the ranked sort and the CAP, so the change is small
once the rule is chosen.

The open questions, for the product owner:
- the per-document cap (the standing recommendation is ~2);
- whether brief (`node://`) and source passages are capped together or
  separately, or left free;
- what happens when the cap cannot be filled from distinct documents — pad from
  the best remaining, or return fewer hits.

The third is the one most likely to be forgotten and most likely to bite: a
small corpus may simply not HAVE ten documents worth returning, and padding
silently re-creates the concentration the cap exists to remove.

## Acceptance criteria
- [ ] (to be written once the cap is decided — the criteria depend on the rule)
- [ ] A `limit=10` result set draws from at least N distinct documents wherever
      the corpus allows it, and the behaviour when it cannot is explicit and
      tested.
- [ ] The four measured questions above are re-run and recorded after the
      change, so the effect is measured rather than assumed.
- [ ] `ruff format`, `ruff check --fix`, `pytest` clean.

## Review log
- 2026-09-17 PO: split out of #102 at its close. #102's AC1/AC3/AC4 were met and
  verified; AC2 was unimplemented BY DESIGN pending this decision, so holding
  finished work in `po-review/` against an external timeline would have
  misrepresented the board and helped nobody. Recorded as MOVED, not met.
  Priority `high` (it is a live quality defect on every query measured), size
  `small` (the seam exists), blocked until the product owner answers.


## PO ruling (2026-09-21) — supersedes the open questions above

Made after #127 and #134 changed the evidence. Both moved the window, so the
numbers in the Description are no longer the current state, and the shape of the
problem changed with them.

### The evidence now (live corpus, at HEAD, through the real `recall()`)

```
how do I set the color level in chalk            10 hits /  2 documents
how does the signer verify a signature           10 hits /  2 documents
generate a version 7 uuid                        10 hits /  1 document
how is key rotation handled                      10 hits /  4 documents
how can I make my console text coloured          10 hits /  5 documents
how do I check whether a signature is still valid 9 hits /  4 documents
how do I style terminal output with colours       8 hits /  5 documents
what library turns log messages a different colour 4 hits / 2 documents
how do I make a unique identifier that sorts by time  1 hit / 1 document
how do I stop old tokens being accepted for ever      1 hit / 1 document
```

Two things are now visible that were not when this was filed. Concentration
tracks the QUESTION, not a bug: the paraphrased questions already spread across
four or five documents, and the one-document cases are questions the corpus
genuinely answers in one place. And the window is no longer always full — two
questions return a single hit, so a rule that assumes ten slots to ration is
solving last month's problem.

### 1. Diversity — a RESERVE, not a cap

**Not a hard per-document cap.** A hard cap cannot tell "this document IS the
answer" from "this document is hogging the window", and `generate a version 7
uuid` at 10-of-1 is the first kind: the answer lives in one file, and truncating
it to two hits to make room for four worse ones from elsewhere makes the answer
worse to serve a metric.

**The rule:** fill the window by score, but no single document may take more
than **four of ten** *while another document still has a qualifying hit
unplaced*. When nothing else qualifies, the leader keeps the window. Scale the
four with `limit` (40%), so a smaller `limit` behaves the same way.

This says what I actually want: a document may dominate only when it has
earned it by being the only thing that answered.

### 2. Brief vs source — capped TOGETHER, no reserved slot, and here is why

They compete in one window on score. I considered reserving a slot for a
qualifying brief, since a topic summary is the most orienting thing an agent can
receive — and rejected it on #134's measurement: a brief passage cleared the
vector floor for **1 of 22** questions, so the reserve would almost never fire,
and a rule that never fires is surface without benefit. Why briefs never compete
is a real question and it is **#135**, not this ticket. If #135 changes that,
revisit this clause — it is the one I am least confident in, and I would rather
say so than pretend otherwise.

### 3. When the cap cannot be filled from distinct documents — return FEWER

Do not pad. This is the question the ticket correctly predicted would be
forgotten and would bite: padding from the best remaining silently re-creates
the concentration the rule exists to remove, and it does it invisibly, which is
worse than doing it openly. A short window is honest; a window padded back to
ten is a window that lies about its own diversity. The two one-hit questions
above are the live case, and one honest hit is the right answer for them.

### 4. The off-topic gate — already ruled, restated so it is not reopened here

A weak-but-nonzero answer for a question the corpus does not cover is worse
than the explore message: an agent cannot tell a bad answer from a good one, and
a brief reads as authoritative either way. That was ruled at #127's close and
#134 held it. The eleven absent questions are the guard, and this ticket must
not move them.

## Acceptance criteria (superseding the placeholder above)
- [ ] A document takes at most 40% of the window (4 of 10) while any other
      document has a qualifying hit unplaced; when none does, it may take more.
- [ ] Brief and source passages are capped together, on score, with no reserved
      slot.
- [ ] A window that cannot be filled from distinct documents returns FEWER hits
      and never pads.
- [ ] `generate a version 7 uuid` is re-measured and recorded; if it drops below
      10 hits, the ruling in section 1 was misapplied — the leader keeps the
      window when nothing else qualifies.
- [ ] The eleven absent questions still return the explore message (#134's
      suite, which is the counterweight for any recall change).
- [ ] All ten questions in the table above are re-run and recorded after the
      change, so the effect is measured rather than assumed.
- [ ] A regression test drives a window where one document dominates AND others
      qualify, and one where nothing else qualifies, asserting both outcomes.
- [ ] `ruff format`, `ruff check --fix`, `pytest` clean.

## Review log
- 2026-09-21 PO: unblocked. Ruled against the standing recommendation (a hard
  cap of 2) because #127 and #134 changed the evidence under it: concentration
  now tracks the question rather than a defect, and the window is no longer
  always full. Priority stays `high` — it is still a live quality defect on the
  three questions that return 10-of-1 or 10-of-2 — and size stays `small`, since
  the seam in `fusion.fuse()` is still there.

## Review log (dev)
- 2026-09-21 dev: started; moved to in-progress (batch with #111's re-fix, #108,
  #120).
- 2026-09-21 dev: implemented and committed as `a4b9024`, to the PO ruling.
  **One wording tension in the ruling is flagged at the end — not blocking, but
  it should be tightened before someone reads §3 on its own.**

  **The reserve, in `fusion.fuse()`'s existing slot.** One pass places hits in
  score order, giving each document up to `MAX_DOCUMENT_SHARE` (40% = 4 of 10);
  a hit past its document's share is DEFERRED, not dropped. The deferred pool
  then fills whatever the first pass left empty. So a document exceeds its share
  only on slots nobody else wanted, which is the ruling stated as an algorithm:
  every candidate gets its turn, and the leader keeps the remainder.

  `engine.recall` supplies the document map — the passage URI without its
  `#chunk-n` fragment, so the unit is the FILE, which is what a reader means by
  "the same place". `fuse` without a map is pure score order, so the fusion
  tests and any other caller are unchanged.

  **Measured on the live corpus, before -> after** (the ruling's own table
  re-run at HEAD; `.e2e/` untouched, copy only):
  ```
  question                                     hits/docs before -> after
  generate a version 7 uuid                        10 / 1  ->  10 / 5
  how do I set the color level in chalk            10 / 2  ->  10 / 4
  how does the signer verify a signature           10 / 2  ->  10 / 4
  how is key rotation handled                      10 / 4  ->  10 / 4
  how can I make my console text coloured          10 / 5  ->  10 / 5
  how do I style terminal output with colours       8 / 5  ->   9 / 5
  how do I check whether a signature is still valid 9 / 4  ->   9 / 4
  the two one-hit paraphrases                       1 / 1  ->   1 / 1
  ```
  **Every question kept its hit count; three of them went from 1-2 documents to
  4-5.** `generate a version 7 uuid` is the interesting one: the ruling
  protected it in case it was a genuine one-document answer, and the measurement
  says it never was — five documents qualified and were being crowded out. The
  protection cost nothing and the concentration was real.

  **The counterweight holds**: all eleven absent questions unchanged, ten
  explore plus the pre-existing single "sourdough" hit.

  Tests (6 new, 824 total): the reserve holding a leader while others qualify;
  the leader keeping the window when nothing else does; a short union coming
  back short; score order preserved within the window; no map meaning no
  diversity; and an END-TO-END `recall()` where the hog answers twelve times and
  scores higher every time, so in pure score order the quiet document never
  appears. Mutations, all killed: no reserve, dropping deferred hits (a hard
  cap), a share of 1, the engine not passing documents, and taking the document
  to be the passage rather than the file.

  My first two end-to-end fixtures could not fail — ten qualifying hits fit in a
  ten-slot window however you order them, so the reserve was never exercised.
  The third makes the hog outrank the quiet document on every hit, which is the
  only shape where the rule can matter.

  ## Flagged for PO: §1 and §3 of the ruling can be read as contradicting

  §1 says the leader keeps the window when nothing else qualifies; §3 says a
  window that cannot be filled from distinct documents returns FEWER and never
  pads. Read strictly, the first backfills to ten from one document and the
  second forbids it.

  I implemented §1, because it carries the explicit acceptance criterion ("if
  `generate a version 7 uuid` drops below 10 hits, the ruling in section 1 was
  misapplied"), and I read §3's "never pads" as forbidding the addition of
  anything that did not QUALIFY — which is what the code does: the backfill
  draws only from passages that already cleared a leg's floor, and a union
  shorter than ten still returns short. Under that reading the two agree.

  It would be worth one sentence in the ruling saying so, because the next
  reader may not reconcile them the same way.

## Review log (qa)
- 2026-09-21 qa: **PASS — to po-review**, and the ruling's §1/§3 tension goes
  with it for the PO to tighten. Under my role's kickback rule a ticket-wording
  problem is a PO problem, not a dev one, and dev resolved it correctly in the
  meantime.

  **The measurement is the strongest part and it is better than the ruling
  hoped.** `generate a version 7 uuid` went 10 hits / 1 document -> 10 hits / 5
  documents. The PO protected that question in case it was a genuine
  one-document answer; the data says it never was — five documents qualified and
  were being crowded out by score order. Every question kept its hit count and
  three went from 1-2 documents to 4-5. All eleven absent questions unchanged.

  **On the §1/§3 reading**: I agree with dev's resolution and would have made
  the same one. "Never pads" forbids adding what did not QUALIFY; the backfill
  draws only from passages that already cleared a leg's floor, and a union
  shorter than ten still returns short (tested). Under that reading the two
  sections agree, and §1's explicit acceptance criterion decides it in any case.
  It is worth one clarifying sentence from the PO so the next reader does not
  have to reconstruct the reconciliation.

  **Verified independently:**
  - Mutations dev ran, re-run by me, plus two they did not: backfilling the
    deferred pool in arrival order instead of score order fails 2, and counting
    the share globally rather than per document fails 3. (A third I tried —
    `placed[:CAP]` where `len(placed) == CAP` — is a no-op, not a mutation.)
  - The end-to-end test is the one that matters and dev rebuilt it twice to make
    it bite. Ten qualifying hits fit a ten-slot window however you order them,
    so the first two fixtures could not fail; the third makes the hog outrank
    the quiet document on every hit, which is the only shape where the rule can
    matter. Both engine mutations (not passing documents, and treating the
    passage as the document) now fail it.
  - Sizing the fixture's noise from `sqrt(N/n - 1)` rather than by trial is the
    right instinct and is written into the test, so the next person who changes
    a floor knows why 150 is there.
  - `fuse` without a document map is unchanged pure score order, so the fusion
    unit tests and any other caller are untouched — the seam is additive.
  - The document being the URI minus its `#chunk-n` fragment is the right unit:
    it is what a reader means by "the same place", and it is pinned by a
    mutation.

  Gate re-run by me on the committed state: 230 files formatted, ruff clean,
  **825 passed**. `.e2e/` untouched — measurements on a copy. Commit atomic and
  conventional.

## Review log (PO)
- 2026-09-21 PO: **PASSES — closed to done.** Every criterion met, including the
  one I wrote as a tripwire for my own ruling.

  **The tripwire fired the other way, and that is the finding.** I wrote "if
  `generate a version 7 uuid` drops below 10 hits, the ruling in section 1 was
  misapplied", protecting it in case it was a genuine one-document answer. It
  went 10 hits / 1 document -> 10 hits / **5 documents**. It was never a
  one-document answer: five documents qualified and score order alone was
  crowding four of them out. The protection cost nothing and the concentration
  I was hedging against was real on every question I had measured.

  That is why the reserve was the right shape over the recommended hard cap of
  two. A cap would have truncated all four of these questions to make room it
  did not need; the reserve let the window stay full AND diversify. Three
  questions went from 1-2 documents to 4-5 with no hit count lost anywhere, and
  the eleven absent questions did not move.

  **Clarifying §1 and §3, since dev and qa both had to reconcile them and
  reached the same reading independently:** "never pads" forbids adding anything
  that did not QUALIFY. It does not forbid a document taking slots no other
  document wanted — every hit in the window cleared a leg's floor, and a union
  shorter than ten still returns short. The two sections agree; my wording made
  that harder to see than it needed to be, and they were right to flag it rather
  than pick silently. Recorded here so the next reader does not re-derive it.

  **Rebuilding the end-to-end fixture twice is the work I most want to praise.**
  Ten qualifying hits fit a ten-slot window however you order them, so the first
  two versions could not fail. Noticing that — rather than shipping a green test
  — is exactly what #128 asks for, and sizing the third fixture's noise from
  `sqrt(N/n - 1)` instead of by trial means the next person who moves a floor
  will understand why the number is what it is.

  No new work spun off. The two one-hit paraphrases stay one hit: that is the
  corpus answering in one place, not a window problem, and #135 owns the
  question of why the summary layer never competes for those slots.
