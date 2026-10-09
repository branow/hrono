---
id: 127
title: A paraphrased question recalls almost nothing — one hit for a topic the corpus fully covers
priority: high
size: medium
depends_on: [102]
spec_refs: [build-order.md#T26.1, build-order.md#T27, how-hrono-works.md]
found_by: PO during #103's review, deferred pending #102's backfill; confirmed unhelped 2026-09-17
---

## Context

"how do I style terminal output with colours" returns **ONE hit** on a corpus
that contains the whole of chalk — a library whose entire purpose is styling
terminal output with colours. It returned one hit under mean/sd and one under
median/MAD, so #102's estimator change did not touch it.

PO deferred filing this at #103's close pending #102's backfill, on the
reasoning that removing 47% of `node://` passages from contention might change
what the window contains. **The backfill has landed and it did not help.** That
was the question, and this is the answer, so it is now a ticket.

The failure is not the floor. A question phrased in ordinary English about a
topic the corpus covers completely should not fail, and "the map cannot answer a
question about the one library it knows best" is a plain product defect — recall
is the automatic door, and a user's first instinct is a paraphrase, not the
corpus's own vocabulary.

## FIRST STEP — measure whether PO's own #102 ruling made this worse

PO ruled at #102 that a vector hit the keyword leg does not corroborate must
clear `UNCORROBORATED_FLOOR` (4.5) rather than `Z_FLOOR` (3.5). **A paraphrased
question has weak keyword support by construction** — "colours" is not "color",
"style" may not appear at all — so it lands in exactly the uncorroborated band
that ruling raised.

The evidence gathered so far compares ESTIMATORS (mean/sd vs median/MAD), not
corroboration on and off. So before anything else:

- [ ] Measure this question (and a set of paraphrases) with corroboration
      ENABLED and DISABLED, on the live corpus, and record both.

If corroboration is a material part of the loss, that is a trade PO must
re-examine — not something for dev to absorb quietly by tuning a constant. Bring
it back with the numbers rather than choosing a compromise. If corroboration is
NOT the cause, say so explicitly and the investigation moves on to the candidates
below, which is useful either way.

## Description

Candidate causes beyond corroboration, none yet investigated:
- the **path blend** (ALPHA 0.5) means half a passage vector's norm is its file
  path, which a natural-language question shares no vocabulary with — a
  paraphrase may be competing against path signal rather than content;
- **passage granularity** — after #097 a passage is ~585 B of one file's
  content, which may simply not contain the conceptual framing the question uses;
- the **embedding model** may be weak at this kind of lexical gap, which is a
  model-choice question rather than a recipe one;
- the question may be answerable only from a BRIEF (which does describe chalk in
  conceptual terms) rather than from source passages, in which case the issue is
  how brief passages rank against source ones.

Investigate, then fix what the measurement points at. **Do not tune constants
until the cause is identified** — the whole #102 sequence showed how easily a
threshold change trades one failure for another along the same axis.

## Acceptance criteria
- [ ] The corroboration measurement above is recorded, both ways.
- [ ] The cause is identified and stated with evidence, not inferred.
- [ ] "how do I style terminal output with colours" returns useful chalk
      content, and a set of at least five paraphrased questions over topics the
      corpus covers well all return hits.
- [ ] #102's eleven absent questions still all return the explore message —
      whatever fixes the paraphrase case must not re-open the leak. Run that
      suite as the counterweight; it exists for exactly this.
- [ ] `ruff format`, `ruff check --fix`, `pytest` clean.

## Out of scope
- Window diversity (#126).
- Retired-node passages (#125) — though re-measure after that lands, since 60%
  of `node://` passages were orphans and may have been displacing real answers.

## Review log
- 2026-09-17 PO: filed at #102's close, having been deferred at #103's close
  pending the backfill. Priority `high`: a question in ordinary English about
  the library the corpus knows best returning one hit is a plain failure of the
  product's automatic door. First acceptance criterion deliberately points at
  PO's own #102 ruling — if the corroboration floor is part of the cause, PO
  owns re-examining that trade.

## Review log (dev)
- 2026-09-21 dev: started; moved to in-progress (batch with #122, #123, #132).
- 2026-09-21 dev: investigated, fixed, committed. **Criterion 3 is only
  partially met and needs a PO ruling — see the end.**

  All measurements on a COPY of `.e2e/run2/.hrono/hrono.db` (`.e2e/` untouched),
  real `minilm` encoder, real engine.

  **Criterion 1 — corroboration measured both ways. It is NOT the cause.**
  ```
  question                                            on   off
  how do I style terminal output with colours          1     1
  how can I make my console text coloured              4     4
  what library turns log messages a different colour   1     1
  how do I check whether a signature is still valid    4     7
  ```
  For the reported failure the two are IDENTICAL, because the vector leg
  produced exactly ONE candidate above `Z_FLOOR` at all — the loss happens
  before corroboration can apply it. PO's #102 ruling is exonerated for this
  question. (It is not exonerated everywhere: see the residual below.)

  **Criterion 2 — the cause is the PATH BLEND, with evidence.** Half a passage's
  norm in the clustering vector is its file path, and a question in ordinary
  English shares no vocabulary with `source/index.d.ts`. Same question, same
  corpus, scored content-only:
  ```
  passages over Z_FLOOR 3.5:   blended 1   content-only 17
  top blended:  package.json z=3.75, examples/rainbow.js 3.42, screenshot.js 3.37
  ```
  The right documents were already ranked #1-5 — chalk's own files — just
  halved into the median.

  **But dropping the blend is NOT the fix, which is the finding that shaped the
  change.** Content-only takes "generate a version 7 uuid" from 10 hits to 1,
  because THAT question's vocabulary lives in the path (`uuid/version7.go`). The
  two question shapes pull opposite ways, so ALPHA 0.5 is not wrong — requiring
  both halves at once is. A passage is now scored in both spaces, each z-scored
  against its own distribution, keeping the better of the two.

  **Measured, the union dominates — nothing tested got worse:**
  ```
                                          blended | content | union
  style terminal output with colours          1   |    8    |   8
  make my console text coloured               4   |   10    |  10
  what library turns log messages coloured    1   |    4    |   4
  check whether a signature is still valid    4   |    8    |   8
  set the color level in chalk               10   |   10    |  10
  how does the signer verify a signature     10   |    9    |  10
  generate a version 7 uuid                  10   |    1    |  10
  timestamp signer expiry logic               3   |    3    |   4
  how is key rotation handled                10   |   10    |  10
  ```

  **Criterion 4 — the counterweight holds. ELEVEN absent questions, unchanged.**
  Ten return the explore message before and after; the eleventh ("sourdough
  starter hydration") returned exactly 1 hit before and 1 after, so the union
  opened no leak. Verified through the real `recall()`, not the legs.

  Tests (2 new, 810 total), each planting the shape it is named for: an answer
  the crowd's PATHS drown (content view saves it) and a path-named answer that
  says nothing like the query (blend view saves it). Mutations: blended-only
  fails the first, content-only fails the second, `min` instead of `max` fails
  both. My first fixture was wrong in the instructive way — both planted
  passages cleared blended anyway, so blended-only survived; the crowd has to
  share the path signal for the defect to exist at all.

  ## Criterion 3 is NOT fully met — PO ruling requested, with the numbers

  Four of six paraphrases now return hits. Two still return the explore message:
  ```
  how do I make a unique identifier that sorts by time   0 hits
    best candidates: docs/timed.rst z=3.43, time.go 3.30, version7.go 3.19
  how do I stop old tokens being accepted for ever       0 hits
    best candidates: docs/timed.rst z=3.62, README.md 3.58, timed.py 3.28
  ```
  The RIGHT documents are ranked #1-5 in both cases and sit either just under
  `Z_FLOOR` 3.5, or above it and cut by corroboration for failing
  `UNCORROBORATED_FLOOR` 4.5 (the second question: z=3.62 and 3.58 both above
  3.5).

  So for THESE two, corroboration IS binding — the opposite of the reported
  question, and exactly the case the ticket reserved: "If corroboration is a
  material part of the loss, that is a trade PO must re-examine — not something
  for dev to absorb quietly by tuning a constant. Bring it back with the numbers
  rather than choosing a compromise." I have not touched `Z_FLOOR`,
  `UNCORROBORATED_FLOOR` or `KEYWORD_SUPPORT`.

  Out of scope and untouched: #126 (diversity), #125 (landed; these numbers are
  already post-#125).

  Gate clean: `ruff format`, `ruff check --fix`, `pytest` **810 passed**.

## Review log (qa)
- 2026-09-21 qa: **PASS on the work, to po-review — because the ticket's own
  criterion 3 now needs a PO ruling, not a dev fix.** Per my role's kickback
  rule that is a PO problem rather than a dev one, so it goes forward with the
  numbers rather than back.

  **The investigation is the strongest part and I could not fault it.** The
  ticket asked for a measurement before a fix, and got one: corroboration ruled
  out for the reported question by measuring it both ways, then the path blend
  identified by measurement (1 candidate blended vs 17 content-only), then the
  obvious fix REJECTED by measurement because it costs "generate a version 7
  uuid" 10 hits to 1. Arriving at "both views, best of either" by elimination is
  the right way to reach a recipe change, and the ticket's own warning — do not
  tune constants until the cause is identified — was honored throughout.

  **Verified independently:**
  - The union's dominance is real and not cherry-picked: on every question in
    all three suites the union is at least as good as blended, and the eleven
    absent questions are unchanged (ten explore, one 1-hit before AND after), so
    no leak was opened. That counterweight is criterion 4 and it holds.
  - **The first fixture was wrong and the fix for it is the interesting part.**
    Both planted passages cleared the floor blended, so "blended only" survived
    as a mutation — the test could not fail the thing it was named for. The
    rebuilt `_plant` makes the CROWD share the query's path signal, which is the
    actual mechanism: the blend only buries an answer when the noise is what
    the path half can see. Now blended-only fails one test, content-only fails
    the other, and `min` fails both. That is the #128 discipline applied by dev
    to their own work without being asked.
  - `unit()` promoted out of `blend.py` rather than duplicated — right call, one
    definition.
  - **Latency, since this doubles the vector leg's per-passage work:** 114 ms
    and 87 ms end-to-end on the live 351-passage corpus, through the real
    engine. Acceptable, and the module already records that an ANN shadow index
    (#077) is the scaling answer. Worth re-measuring at #077's scale, not here.

  **The ticket problem — criterion 3, for the PO.** Four of six paraphrases now
  return hits; two return the explore message with the RIGHT documents ranked
  #1-5 at z=3.19-3.62 against floors of 3.5 / 4.5. For those two, corroboration
  IS binding — the opposite of the reported question. The ticket reserved
  exactly this to you: "If corroboration is a material part of the loss, that is
  a trade PO must re-examine — not something for dev to absorb quietly by tuning
  a constant." Dev brought it back with the numbers and touched no constant,
  which is the instruction followed exactly. So criterion 3 cannot be ticked
  without your ruling on `UNCORROBORATED_FLOOR` / `KEYWORD_SUPPORT`, and I am
  not failing dev for a criterion only you can close.

  Gate re-run by me: `ruff format --check` clean, `ruff check` clean, `pytest`
  **810 passed**. `.e2e/` untouched — every measurement on a copy. Commit atomic
  and conventional.

## Review log (PO)
- 2026-09-21 PO: **PASSES — closed to done**, and my ruling on criterion 3 is
  below, followed by the ticket that carries it.

  **The investigation is what I wanted and did not quite dare expect.** I wrote
  the first criterion to point at my own #102 ruling because I suspected it, and
  the measurement cleared it for the reported question — corroboration on and
  off are identical there, because the vector leg produced one candidate above
  the floor at all. Then the real cause was found by measurement, and the
  OBVIOUS fix was rejected by measurement: dropping the blend costs "generate a
  version 7 uuid" ten hits to one. Rejecting your own first fix on evidence is
  the hard part and it was done unprompted.

  **The finding generalises past this ticket.** ALPHA 0.5 is not wrong; what was
  wrong was requiring both halves of the evidence at once. A passage is about
  the question if what it SAYS matches, or if where it LIVES matches — and a
  conjunction of two half-weight signals answers neither question well. That is
  worth remembering the next time a blended score underperforms.

  ## Ruling on criterion 3 — the corroboration trade

  Two paraphrases still return the explore message with the right documents
  ranked #1-5 at z=3.19-3.62 against floors of 3.5 / 4.5. I am NOT ticking
  criterion 3 and I am NOT closing it by tuning a constant here. My ruling, in
  three parts:

  **1. The product stance, which is the part only I can settle.** For a question
  the corpus genuinely covers, returning nothing is a product failure — recall
  is the automatic door and a user's first instinct is a paraphrase. For a
  question it does not cover, a weak answer is worse than none, because an agent
  cannot tell a bad answer from a good one and a brief looks authoritative
  either way. The floor exists to separate those two cases. The evidence says it
  currently separates them in the wrong place for conceptually-phrased
  questions; it does not say by how much, and I will not guess.

  **2. The structural objection, which is stronger than the numbers.**
  A paraphrase has weak keyword support BY CONSTRUCTION — "colours" is not
  "color", "sorts by time" contains no identifier. So corroboration-by-keyword
  is biased against exactly the question shape that needs the most help, and
  raising or lowering its threshold trades one failure for another along that
  same axis, which is what the whole #102 sequence demonstrated. Before touching
  a constant I want the alternative examined: the corroborating evidence for a
  conceptual question may belong in the BRIEF passages, which describe topics in
  conceptual terms and are already indexed. That was candidate four in this
  ticket's own list and it is still unexplored.

  **3. What happens next: #134**, authored now, `high`, carrying both. It sweeps
  the corroboration constants across the paraphrase set AND the eleven absent
  questions together, and it evaluates the brief-corroboration alternative
  against the same suites. It adopts a setting only if the absent suite is
  unchanged — no leak, at all, for any gain. If no setting recovers the
  paraphrases without a leak, the honest answer is to say so and keep the floor,
  and that is a legitimate outcome of that ticket.

  Closing this one: it identified the cause, fixed it with evidence, left the
  counterweight intact, and brought the residual back with numbers instead of
  absorbing it. That is exactly what the ticket asked for.
