---
id: 134
title: Sweep the corroboration trade, and test whether a brief can corroborate
priority: high
size: medium
depends_on: [127]
spec_refs: [build-order.md#T26.1, build-order.md#T27]
found_by: PO ruling at #127's close, 2026-09-21
---

## Context
#127 fixed the path-blend half of the paraphrase failure: a passage is now
scored in both the blended and the content-only view and keeps the better
z-score. Four of six paraphrases recovered, the eleven absent questions were
unchanged, and "generate a version 7 uuid" kept all ten of its hits.

Two paraphrases did not recover, and they are a DIFFERENT failure — this one is
the corroboration trade, which #127 correctly refused to touch because it is a
product call:

```
how do I make a unique identifier that sorts by time   0 hits
  best candidates: docs/timed.rst z=3.43, time.go 3.30, version7.go 3.19
how do I stop old tokens being accepted for ever       0 hits
  best candidates: docs/timed.rst z=3.62, README.md 3.58, timed.py 3.28
                   (3.62 and 3.58 are ABOVE Z_FLOOR 3.5 and were cut by
                    corroboration, failing UNCORROBORATED_FLOOR 4.5)
```

The right documents are ranked #1-5 in both cases. The map knows the answer and
the door will not open.

## The PO stance this ticket executes (from #127's close)
For a question the corpus genuinely covers, returning nothing is a product
failure. For a question it does not cover, a weak answer is worse than none —
an agent cannot tell a bad answer from a good one. The floor separates those two
cases and currently separates them in the wrong place for conceptually-phrased
questions. **How far it moves is a measurement, not a judgement, and it moves
only if the absent suite is completely unchanged.**

## Description

**Part A — sweep, do not guess.** Vary `UNCORROBORATED_FLOOR`,
`KEYWORD_SUPPORT` and `Z_FLOOR` (`recall/vector_leg.py`) across the paraphrase
set and the eleven absent questions TOGETHER, on the live corpus. Record the
full grid, not the winner. Adopt a setting only if every absent question is
unchanged; report the frontier either way, including "no setting recovers these
without a leak", which is a legitimate and useful answer.

**Part B — the structural alternative, which may make Part A unnecessary.**
A paraphrase has weak keyword support BY CONSTRUCTION: "colours" is not "color",
"sorts by time" contains no identifier. So corroboration-by-keyword is biased
against precisely the question shape that needs the most help, and moving its
threshold trades one failure for another along the same axis — which is what the
whole #102 sequence demonstrated.

Brief passages (#071) describe topics in CONCEPTUAL terms and are already
indexed and scored. Test whether a strong brief-passage match can corroborate a
source-passage hit under the same topic, in place of or alongside keyword
support. Measure it on both suites exactly as Part A is measured. This was
candidate four in #127's own list and is still unexplored.

Report which of A or B (or neither) you adopt, and why, with the grid.

## Acceptance criteria
- [ ] The sweep grid is recorded — every setting tried, against BOTH suites.
- [ ] The brief-corroboration alternative is implemented far enough to measure
      and its numbers recorded on the same suites.
- [ ] Whatever is adopted, all eleven absent questions still return the explore
      message. A single new leak fails this ticket.
- [ ] The two named paraphrases return useful content, or the ticket states with
      evidence that no leak-free setting exists and adopts nothing.
- [ ] #127's gains are intact: the four recovered paraphrases and "generate a
      version 7 uuid" at ten hits.
- [ ] `ruff format`, `ruff check --fix`, `pytest` clean.

## Out of scope
- The path blend — #127 settled it, and the two-view union stays.
- Window diversity (#126) and the embedding model choice.
- Changing what the explore message says.

## Review log
- 2026-09-21 PO: authored at #127's close, carrying the ruling made there.
  `high`: the same reason #127 was high — a question in ordinary English about a
  topic the corpus covers well returning nothing is a failure of the product's
  automatic door, and #127 proved two such questions are one threshold away.

## Review log (dev)
- 2026-09-21 dev: started; moved to in-progress (batch with #122's re-fix, #111,
  #128).
- 2026-09-21 dev: swept, measured, adopted. Committed as `c46f2bf`.
  All measurements on a COPY of `.e2e/run2/.hrono/hrono.db` (`.e2e/` untouched),
  real `minilm` encoder, three suites scored together every time.

  ## Part A — the grid, and the surprise in it

  **The binding constant is not the one this ticket suspected.** Relaxing
  corroboration is the WRONG lever and leaks badly; lowering the corroborated
  floor leaks nothing.

  ```
   Z_FLOOR  UNCORROB  KW_SUPPORT | paraphrases | vocab | absent answered
      3.5       4.5         0.0  |    4/6      |  5/5  |   1/11   <- baseline
      3.5       4.5        -1.0  |    5/6      |  5/5  |   5/11
      3.5       4.0         0.0  |    4/6      |  5/5  |   2/11
      3.5       3.5         0.0  |    5/6      |  5/5  |   5/11
      3.2       4.5         0.0  |    6/6      |  5/5  |   1/11   <- ADOPTED
      3.2       4.5        -1.0  |    6/6      |  5/5  |   6/11
      3.0       4.5         0.0  |    6/6      |  5/5  |   1/11
      3.0       4.5        -1.0  |    6/6      |  5/5  |   8/11
  ```
  (36 settings swept; the full grid is the script's output, the rows above are
  the frontier and the corners that explain it.)

  Read it as three facts:
  - dropping `KEYWORD_SUPPORT` to -1.0 takes the absent suite from 1 answered to
    5, 6 or 8 depending on the other two. Corroboration is doing real work and
    weakening it is how you leak;
  - lowering `UNCORROBORATED_FLOOR` leaks mildly (1 -> 2) and buys nothing;
  - lowering `Z_FLOOR` — the bar for passages that ARE corroborated — recovers
    all six paraphrases and leaks NOTHING. Corroboration still gates; the bar
    just sits where the evidence puts it.

  **Adopted: `Z_FLOOR` 3.5 -> 3.2**, and nothing else. 3.0 gives the same result,
  so 3.2 is not a cliff edge — it is the smaller move with headroom below it.
  The one absent question that answers ("sourdough starter hydration", one hit)
  answered before this change too, so the absent suite is unchanged.

  ## Part B — the brief-corroboration alternative: REJECTED, with numbers

  Implemented far enough to measure: a source passage qualifies at `Z_FLOOR` if
  a BRIEF passage for its own topic cleared 3.5, as an alternative to keyword
  support. Measured on all three suites, it changed **not one result**, because
  the thing meant to do the corroborating almost never clears its own bar:

  ```
  questions where any brief passage reached z 3.5:  1 of 22
  ```
  A brief competes against source passages in the same z distribution and loses
  — it is a summary, so it is less lexically like any specific question than the
  passages it summarises. The idea is sound and the corpus says it has nothing
  to fire on. Recorded here so it is not re-proposed from first principles.

  ## Criteria

  - Grid recorded, both suites, every setting — above.
  - Part B implemented far enough to measure, numbers recorded — above.
  - **No leak**: all eleven absent questions unchanged; ten return the explore
    message, the eleventh returns its pre-existing single hit.
  - **Both named paraphrases now return content**, verified through the real
    `recall()`: "how do I make a unique identifier that sorts by time" and "how
    do I stop old tokens being accepted for ever", 1 hit each from the document
    that answers them (`version7.go` / `timed.rst` families).
  - **#127's gains intact**: the four recovered paraphrases hold (8, 10, 4, 9)
    and "generate a version 7 uuid" still returns 10.

  Honest note on the two recovered questions: 1 hit each, not 10. They are at
  the bottom of the window rather than commanding it, which is the right shape
  for a question the corpus answers in one place — but it is one passage of
  margin, and #126's window composition is where that becomes a quality question
  rather than a yes/no one.

  Tests: `test_z_floor_is_baked` now pins 3.2 and carries the derivation.
  Mutations: restoring 3.5 fails it; dropping to 2.0 past the swept range fails
  two (the synthetic leak-safety tests, which is the right thing to break).

  Gate clean: `ruff format`, `ruff check --fix`, `pytest` **817 passed**.

## Review log (qa)
- 2026-09-21 qa: **PASS — to po-review.** Every criterion met, both parts
  delivered, and the negative result in Part B is recorded as carefully as the
  positive one in Part A.

  **The grid answers the question the PO actually asked, and the answer is not
  the one the ticket expected — which is why it needed measuring.** Relaxing
  corroboration leaks (1 absent answered -> 5, 6 or 8); lowering the
  CORROBORATED floor leaks nothing and recovers all six paraphrases.
  Corroboration keeps gating; the bar moves to where the evidence puts it. That
  distinction is the whole value of this ticket and it is stated plainly in the
  module docstring, not just in this log.

  **Verified by me at HEAD, through the real `recall()` on the live corpus:**
  - all eleven absent questions unchanged — ten explore, one pre-existing single
    hit ("sourdough"), which is criterion 3 and the one that could have failed;
  - both named paraphrases now return content (1 hit each);
  - #127's gains intact: 10, 4, 9 on the recovered paraphrases and "generate a
    version 7 uuid" still at 10;
  - corpus-vocabulary suite 5/5, one question improved 4 -> 5.
  - Mutations: restoring 3.5 fails the pinned constant; dropping to 2.0 past the
    swept range fails two leak-safety tests, which is the right thing to break.

  **Choosing 3.2 over 3.0 on headroom rather than on being the best row** is the
  correct instinct — both give 6/6 and 1/11, so 3.2 is the smaller move with a
  measured margin below it rather than a value sitting on a cliff.

  **Part B's rejection is the right kind of negative.** "A brief passage cleared
  z 3.5 for 1 of 22 questions" explains WHY the idea cannot work here — a
  summary competes in the same distribution as the passages it summarises and
  loses — rather than just reporting that it did not. That saves the next person
  from re-proposing it from first principles, which is what a rejected
  alternative is for.

  **One note for the PO, not a fail: two baked constants have quietly converged.**
  `vector_leg.Z_FLOOR` is now 3.2 and `keyword_leg.VECTOR_SUPPORT` is 3.0. The
  design had 0.5 between them — the vector leg's corroborated bar deliberately
  above the vector support a keyword hit needs — and it is now 0.2. Nothing in
  the measurements suggests harm (the corpus-vocabulary suite is unchanged or
  better), and I am not blocking on it. But the gap was a relationship, not a
  coincidence, and this ticket moved one side of it without anyone deciding
  about the other. Worth a sentence from you on whether 3.0 should follow, or
  whether the two bars were always independent.

  Gate re-run by me on the committed state: 230 files formatted, ruff clean,
  **817 passed**. `.e2e/` untouched — every measurement on a copy. Commit atomic
  and conventional.

## Review log (PO)
- 2026-09-21 PO: **PASSES — closed to done.** All six criteria met, and the
  ticket did the one thing I most wanted from it: it proved my own suspicion
  wrong with a grid instead of confirming it with a tune.

  **I was wrong about the lever, and the distinction matters beyond this
  ticket.** I ruled at #127's close that corroboration-by-keyword is biased
  against paraphrases by construction, and inferred from that it was the
  constant to re-examine. The first half is true; the conclusion did not follow.
  Relaxing corroboration leaks badly — 1 absent question answered becomes 5, 6
  or 8 — because corroboration is doing real work for every OTHER question.
  What was miscalibrated was the bar applied to passages that ARE corroborated.
  Corroboration keeps gating; only the height changed.

  The lesson I want carried forward: when a rule is biased against a case, the
  fix is not always to weaken the rule. Here the rule was right and the
  threshold behind it was set on a corpus that never asked a paraphrased
  question.

  **Six of six paraphrases, five of five corpus-vocabulary questions, eleven of
  eleven absent questions unchanged.** That is the product bar met on the read
  door: a question in ordinary English about a topic the corpus covers now
  opens it, and a question about something it does not cover still gets the
  explore message. Choosing 3.2 over the equally-good 3.0 on headroom rather
  than on score is the judgement I would have wanted.

  **Part B's rejection is worth as much as Part A's adoption.** "A brief cleared
  the floor for 1 of 22 questions" closes the idea with a reason — a summary
  competes in the same distribution as the passages it summarises and loses —
  so nobody re-proposes it from first principles. It also surfaces something
  larger, which I have taken as new work rather than folded in silently:
  **brief passages are essentially never competitive in recall.** #071 put them
  in the index precisely so a conceptual question could be answered by a
  summary, and the measurement says that is not happening. Authored **#135**.

  **On qa's converged-constants note — ruling: they are independent, and no
  automatic follow.** `vector_leg.Z_FLOOR` (3.2) is a QUALIFICATION bar: is this
  passage a genuine vector match, given the keyword leg vouches for it?
  `keyword_leg.VECTOR_SUPPORT` (3.0) is a SANITY floor: is this keyword hit
  vector-noise? Different questions, different directions, and the 0.5 gap was
  never a designed relationship — it is two numbers that happened to be set 0.5
  apart. So 3.0 does not follow 3.2 down, and nothing here is incoherent.
  But qa is right that they now nearly coincide, and if the two rules have
  converged to the same rule stated twice, that is a simplification worth
  seeing. Folded into **#135** as a second question, with the standing
  requirement that ANY change to either constant goes through this ticket's
  three-suite sweep and adopts nothing that leaks.

  Closing. The residual dev flagged — the two recovered questions return one hit
  each, at the bottom of the window — belongs to window composition, which I am
  unblocking now (#126).
