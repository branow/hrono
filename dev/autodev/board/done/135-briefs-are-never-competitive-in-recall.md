---
id: 135
title: Brief passages are almost never competitive in recall — the summary layer is not answering
priority: medium
size: medium
depends_on: [134, 071]
spec_refs: [build-order.md#T26.1, how-hrono-works.md]
found_by: PO at #134's close, 2026-09-21, from #134's Part B measurement
---

## Context
#134 tested whether a BRIEF passage could corroborate a source hit under the
same topic — briefs describe topics conceptually, so they looked like the
natural corroborator for a conceptually-phrased question. The rule changed not
one result on any suite, for a reason that is more interesting than the rule:

```
questions where any brief passage reached z 3.5:   1 of 22
```

A brief competes against source passages in the SAME z distribution and loses.
It is a summary, so it is less lexically like any specific question than the
passages it summarises.

**#071 put briefs in the recall index on the premise that a conceptual question
could be answered by a summary.** The measurement says that premise is not
being met: the summary layer is indexed, embedded, scored — and never wins. The
whole tree exists to produce those summaries.

## What to establish, before proposing a fix
1. Is it the distribution? A brief is one of ~7 node:// sources against ~340
   source passages, so it is scored against a population it is unlike. Would a
   separate z-distribution per `source_type` change the picture?
2. Is it the blend? A brief's path is `nodes/<id>/<slug>` — synthetic, and after
   #127 it is scored in both views, so this may already be answered.
3. Is it the passage granularity? A brief is split by the same structure-aware
   splitter, so a "summary" hit is really one ~585 B fragment of a summary, not
   the summary.
4. Is it correct? A defensible answer is that source passages ARE the better
   answer to most questions and the tree's job is traversal, not retrieval — in
   which case #071's premise should be rewritten rather than the recipe.

That fourth option is a real outcome, not a cop-out. Establish which before
changing anything.

## Also in scope — the two converged constants (PO, #134)
`vector_leg.Z_FLOOR` is 3.2 and `keyword_leg.VECTOR_SUPPORT` is 3.0. PO ruled at
#134's close that they are independent by role — a qualification bar and a
sanity floor, asked in opposite directions — so 3.0 does not follow 3.2 down.
But they now nearly coincide, and if the two rules have converged to the same
rule stated twice, that is a simplification worth seeing. Examine it here, since
this ticket is already inside the same scoring code.

**Standing requirement, from #134:** any change to either constant goes through
#134's three-suite sweep (paraphrase, corpus-vocabulary, eleven absent
questions) and adopts nothing that leaks.

## Acceptance criteria
- [ ] The cause is established with evidence and stated, including "this is
      correct and #071's premise should change" as a permitted answer.
- [ ] If a recipe change is adopted, it goes through #134's sweep and the
      absent suite is unchanged.
- [ ] The two-constant question is answered: converged by coincidence, or the
      same rule stated twice.
- [ ] `ruff format`, `ruff check --fix`, `pytest` clean.

## Out of scope
- Window composition (#126) and how briefs are RENDERED once returned.

## Review log
- 2026-09-21 PO: authored at #134's close. `medium`: recall works well now for
  both question shapes without briefs, so this is not a live failure — it is the
  discovery that a layer we built and pay for on every rebuild is contributing
  nothing to the read door, which is worth understanding before M10 renders it.

## PO triage 2026-09-22 — promoted to `todo`, priority raised `medium` -> `high`

Promoted now that the six-ticket batch is closed and the board is empty, and
raised because the question has grown while it waited.

#071 put brief passages in the recall index on the premise that a conceptual
question could be answered by a SUMMARY. Three separate measurements since then
say that premise is not being met: #134 found a brief cleared the vector floor
for 1 of 22 questions, #126's window measurements never show a `node://` hit in
a top-10, and the two paraphrases that #134 recovered are answered by source
passages alone. Meanwhile #137/#138 made the whole tree reachable with one
command, so the summary layer is now built and paid for on EVERY sync.

That is the shape of a question worth answering properly: a layer we generate
with LLM calls, store, embed, index and re-brief on every change, contributing
nothing measurable to the read door. Either the recipe is wrong or #071's
premise is, and "the tree's job is traversal, not retrieval" remains a permitted
and respectable answer — in which case the honest fix is to stop indexing
briefs, not to tune their scores.

Investigate before proposing. The four candidate causes in the Description are
the starting list, not a menu to pick from.

## Review log (dev)
- 2026-09-22 dev: investigated and committed as `7e89338`. **The premise is
  wrong: briefs ARE competitive, and they win exactly where they should.** All
  measurements on a COPY of `.e2e/run2/.hrono/hrono.db`, real `minilm` encoder,
  real engine; `.e2e/` untouched.

  ## The answer: option 4, but sharper than the ticket framed it

  Not "source passages are simply better" — **the question set was wrong.**

  ```
  question                                     best brief rank | brief max | source max
  what does this project do overall                          0 |     0.321 |      0.280
  what are the main components of this codebase              0 |     0.406 |      0.297
  how is key rotation handled                               15 |     0.197 |      0.490
  how does the signer verify a signature                    29 |     0.258 |      0.528
  generate a version 7 uuid                                 37 |     0.323 |      0.575
  how do I style terminal output with colours               96 |     0.116 |      0.338
  ```

  End to end through the real `recall()`:
  ```
  OVERVIEW questions                          hits | summaries | top
  what does this project do overall              7 |     2     | summary
  what are the main components of this codebase  2 |     2     | summary
  give me an overview of the architecture        5 |     5     | summary
  SPECIFIC questions
  how does the signer verify a signature        10 |     0     | source
  generate a version 7 uuid                     10 |     0     | source
  how do I style terminal output with colours    9 |     0     | source
  ```

  **A brief takes the TOP slot on every overview question that returns anything,
  and takes nothing on a specific one.** That is #071's premise being met, not
  missed: a question about one function is best answered by that function, and a
  question about the whole corpus is best answered by a summary of it.

  **#134's "1 of 22" was an artefact of its question set.** All twenty-two were
  specific — paraphrases of "how does X work" plus eleven absent questions.
  None asked what the corpus IS. The layer was doing its job; the measurement
  could not see it. My own note on #134 drew the wrong conclusion from a true
  observation, which is worth recording next to the observation.

  So: nothing to fix in the recipe, and #071's premise stays. The candidate
  causes 1-3 (distribution, blend, granularity) are moot — none of them is
  stopping anything. What was missing was a measurement with the right
  questions, and a test so the belief cannot drift again: `recall` puts a
  planted summary in the top slot, and it fails if `kind` stops distinguishing
  a summary. The finding is written into `brief_passages.py` where the next
  reader will meet it.

  ## The two converged constants: independent, and one is never reached

  `vector_leg.Z_FLOOR` 3.2 and `keyword_leg.VECTOR_SUPPORT` 3.0 are NOT the same
  rule stated twice. They gate on different companions: the vector leg wants
  vector z >= 3.2 with keyword z >= 0.0 (merely non-negative), the keyword leg
  wants BM25 z >= 6.0 with vector z >= 3.0. Different corners of the same
  two-dimensional space, deliberately. Converged by coincidence — the PO's
  ruling at #134 holds, and 3.0 does not follow 3.2 down.

  **And a finding I did not go looking for: the keyword leg's SEARCH half
  qualifies nothing at all.**
  ```
  question                                  vec-only  kw-only  both
  how does the signer verify a signature          15        0     0
  generate a version 7 uuid                       21        0     0
  how is key rotation handled                     12        0     0
  how do I set the color level in chalk           40        0     0
  what does this project do overall                7        0     0
  ```
  Every hit hrono has ever returned came from the vector leg. The keyword leg
  earns its place as a CORROBORATOR — #134 proved that half is load-bearing —
  and contributes nothing as a retriever, which means T27's 70/30 RRF weighting
  has never done anything. Filed as **#140** rather than folded in: this ticket
  is about the summary layer, and that is about the keyword leg.

  ## Residual, recorded not fixed
  Two of five overview phrasings still return the explore message ("what is this
  repository for", "how are the parts of this system organised"). Same class as
  #134's paraphrase work, one rung more conceptual. Not this ticket.

  Gate clean: `ruff format`, `ruff check --fix`, `pytest` **915 passed**.
- 2026-09-22 qa: **PASS — to po-review.** All four criteria met, including the
  one that permits "this is correct" as an answer — which is what it turned out
  to be, for a reason nobody had considered.

  **The finding overturns its own ticket, and the evidence is clean.** A brief
  takes the TOP slot on every overview question that returns anything and takes
  nothing on a specific one. I re-read the numbers rather than the conclusion:
  best-brief rank 0 with the brief outscoring every source passage (0.321 vs
  0.280, 0.406 vs 0.297) on the two overview questions, and rank 15-96 on the
  four specific ones. That is not a layer failing to compete; that is a layer
  competing and correctly losing where it should.

  **"The measurement could not see it" is the right diagnosis and the important
  one.** #134's 22 questions were paraphrases of "how does X work" plus eleven
  absent ones. None asked what the corpus IS. A negative result over a question
  set that excludes the case is not a negative result, and this ticket exists
  because that distinction was missed once already.

  **Verified:**
  - Gate: 297 files formatted, ruff clean, **915 passed**.
  - Mutations: labelling every hit `summary` fails 2, dropping the label fails
    1. So the test pins the property in both directions — a summary CAN win, and
    the window is not silently all-summaries.
  - The test needed keyword corroboration to pass, which is not a flaw: a brief
    goes through the same floor as any passage. Dev noticing that rather than
    lowering the floor to make the test green is the correct instinct.
  - The constants answer is right and checkable: the vector leg wants vector
    z >= 3.2 with keyword z >= 0.0; the keyword leg wants BM25 z >= 6.0 with
    vector z >= 3.0. Different companions, so not the same rule — the PO's
    ruling at #134 stands.
  - **#140 is a real find and correctly separated.** The keyword leg qualifying
    nothing on any question means T27's 70/30 fusion has never weighted
    anything, which a reader of `fusion.py` would not guess. Filing it rather
    than folding it in keeps this ticket's answer clean.

  The residual (two overview phrasings still returning explore) is recorded and
  correctly left — it is #134's class, one rung more conceptual.

## Review log (PO)
- 2026-09-22 PO: **PASSES — closed to done.** All four criteria met, and the
  answer is the one I explicitly permitted and least expected to be right.

  **I wrote the premise of this ticket and the premise was wrong.** At #134's
  close I recorded "brief passages are essentially never competitive in recall"
  and raised it to `high` on the strength of that. The observation was true —
  one brief cleared the floor in 22 questions — and the conclusion did not
  follow, because all 22 questions were specific. A measurement that excludes
  the case cannot speak to it. That is the second time this month I have drawn a
  wrong conclusion from a true measurement (the first was #120's signature
  "drift"), and both times what corrected it was somebody re-measuring with a
  different question rather than arguing.

  **The layer is doing its job.** An overview question puts a summary in the top
  slot; a specific question gets source passages and no summaries at all. That
  is exactly the division of labour #071 was built for, and it is now pinned by
  a test in both directions rather than believed.

  So: nothing changes in the recipe, #071's premise stands as written, and the
  finding is recorded in `brief_passages.py` where the next person to wonder
  will land — which matters, because the wrong belief was recorded on a board
  ticket by me and would have outlived the measurement that disproved it.

  **#140 is the more interesting thing this ticket found.** The keyword leg
  qualifies nothing, on any question, so T27's weighted 70/30 fusion has never
  weighted two lists — it has sorted one. Every hit hrono has ever returned came
  from the vector leg. That is a mechanism our own documentation describes and
  the system does not run, which is the #123 shape again. It stays `medium` in
  backlog: the corroboration half is load-bearing and proven, nothing is broken
  today, and it deserves the same kind of measured session this ticket got.

  The two-constant question is answered and closed: independent by role, and
  converged by coincidence.
