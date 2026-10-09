---
id: 140
title: The keyword leg's search half contributes zero hits; only its scores half is load-bearing
priority: medium
size: medium
depends_on: [134, 135]
spec_refs: [build-order.md#T26.2, build-order.md#T27]
found_by: dev while investigating #135 on 2026-09-22
---

## Context
Measured on the live corpus, per question, counting which leg admitted each
passage that reached the fused window:

```
question                                  vec-only  kw-only  both
how does the signer verify a signature          15        0     0
generate a version 7 uuid                       21        0     0
how is key rotation handled                     12        0     0
how do I set the color level in chalk           40        0     0
what does this project do overall                7        0     0
```

**`keyword_leg.search` qualified nothing, on any question.** Its bar is BM25
z >= 6.0 with vector support >= 3.0, and the first half is apparently never
reached on this corpus. Every hit hrono has ever returned came from the vector
leg.

**This does NOT mean the keyword leg is dead code.** Its OTHER half —
`keyword_leg.scores`, the z-map the vector leg reads for corroboration — is
load-bearing and proven so: #134 measured that dropping `KEYWORD_SUPPORT` to
-1.0 takes the eleven absent questions from 1 answered to 5, 6 or 8. The leg
earns its place as a CORROBORATOR and contributes nothing as a RETRIEVER.

## Why this matters
T27's recipe is a weighted 70/30 RRF fusion of two legs. If one leg never
contributes a passage, the 70/30 weighting has never done anything, the fusion
is a sort of one list, and a reader of `fusion.py` is being told about a
mechanism that does not run. That is the same class of problem as #123's
docstring promising a corrective that did not exist — code describing a system
it is not.

It also means `Z_FLOOR = 6.0` has never been exercised, so nobody knows whether
it is right.

## What to establish
1. Is 6.0 simply too high for this corpus, or is the BM25 z-distribution shaped
   so that it is unreachable in general? Measure the max keyword z per question
   and compare with the floor.
2. Would a reachable keyword leg IMPROVE anything? #134's sweep is the tool and
   the eleven absent questions are the counterweight: a keyword hit the vector
   leg missed is the case it exists for, and if lowering the floor produces none
   of those and only leaks, that is the answer.
3. If the retriever half genuinely earns nothing, say so in `fusion.py` and
   `keyword_leg.py` rather than leaving the 70/30 weighting to imply otherwise.
   Deleting it is NOT obviously right — corroboration needs the same scores —
   but describing it accurately is.

## Acceptance criteria
- [ ] The keyword z-distribution is measured against its floor, and whether 6.0
      is reachable is stated with numbers.
- [ ] Either the leg is made to contribute (through #134's sweep, with the
      absent suite unchanged), or the recipe's documentation is corrected to say
      that the keyword leg corroborates rather than retrieves.
- [ ] `ruff format`, `ruff check --fix`, `pytest` clean.

## Out of scope
- Removing the keyword leg or its FTS index — corroboration depends on both.
- The corroboration constants themselves (#134 settled those with a sweep).

## Review log
- 2026-09-22 dev: filed while investigating #135. Not folded into #135, which
  is about the SUMMARY layer; this is about the keyword leg and wants its own
  measurement.

## PO triage 2026-09-22 — promoted to `todo`, priority confirmed `medium`

Promoted straight after #135 closed, because it is the same question one layer
down and the measurement tooling is warm. Nothing is broken today — the
corroboration half is load-bearing and proven — so this stays `medium`. What
makes it worth doing now is that our own recipe documentation describes a
weighted fusion of two legs while one leg has never contributed a passage, and
that gap has a way of being discovered by whoever trusts the documentation.

## Review log (dev)
- 2026-09-22 dev: investigated and committed. All three criteria. **The answer
  is option 3: the leg corroborates, it does not retrieve, and the recipe's
  documentation now says so.** All measurements on a COPY of `.e2e/run2`.

  ## 1. Is 6.0 reachable? No — it is above the observed MAXIMUM

  ```
  question                                    matches  max kz  >=6.0
  how does the signer verify a signature           88    4.37      0
  what is the timestamp signer expiry logic        83    4.07      0
  generate a version 7 uuid                       100    3.82      0
  how do I style terminal output with colours      56    3.11      0
  how do I set the color level in chalk            88    2.96      0
  how is key rotation handled                      58    2.19      0
  what does this project do overall                19    1.91      0
  ```
  The best BM25 z any question produced is **4.37**, against a floor of 6.0. A
  floor 38% above the observed maximum is not a bar, it is a ceiling.

  ## 2. Would lowering it help? No — and this is the more interesting half

  Swept the floor down to 2.5, well into the noise, counting hits the keyword
  leg would add that the vector leg did NOT already have:

  ```
  floor | on-topic: new hits | absent: new hits
    6.0 |                  0 |                0
    5.0 |                  0 |                0
    4.0 |                  1 |                0
    3.0 |                  1 |                0
    2.5 |                  1 |                0
  ```
  **One hit across nine on-topic questions, for a 58% reduction in the floor.**

  The mechanism is the constant convergence qa spotted at #134, seen from the
  other side. `VECTOR_SUPPORT` is 3.0 and the vector leg's own floor is 3.2, so
  the keyword leg can only ever admit passages in a **0.2-wide band** — ones
  with enough vector support to be nearly qualified already. There is almost
  nothing in that band. So there are two independent reasons this leg retrieves
  nothing, and removing either would not fix it.

  (That is a better answer to qa's original observation than the one I gave at
  #134. The constants are not the same rule stated twice — their companions
  differ — but their proximity does squeeze the keyword leg's retrieval window
  to nearly zero width. Both things are true.)

  ## 3. What shipped

  No constant changed: nothing measured says a different floor retrieves
  anything worth having, and #134's rule is to adopt no change that does not pay
  for itself against both suites. What changed is the documentation, in the two
  places that currently mislead:

  - `keyword_leg.py` — states that `search` has never qualified a passage, both
    reasons with their numbers, and that `scores` IS load-bearing (#134 measured
    that weakening it leaks 1 absent answer to 5-8). The module earns its place
    entirely through corroboration.
  - `fusion.py` — states that the 70/30 weighting has in practice ranked ONE
    list, and why the mechanism stays anyway: it is the frozen recipe, and a
    different corpus or embedding model could make the other leg fire.

  Plus a test: fusion ranks cleanly from a single leg, in either direction. That
  is not an edge case here — it is every query we have measured — and it was
  untested. Mutations: intersecting the legs instead of unioning fails 16,
  flattening the single-leg scores fails 3.

  Gate clean: `ruff format`, `ruff check --fix`, `pytest` **916 passed**.
- 2026-09-22 qa: **PASS — to po-review.** All three criteria met, and the answer
  is the right one — documented rather than tuned.

  **Both halves of the finding are measured, not argued**, and the second is the
  one that settles it. The floor being unreachable (4.37 against 6.0) would
  invite the obvious fix; the sweep shows that fix buys ONE hit across nine
  questions at a 58% floor reduction. Establishing that before proposing
  anything is exactly what the ticket asked for, and it is why nothing was
  changed.

  **The mechanism dev found is the better answer to my #134 note.**
  `VECTOR_SUPPORT` 3.0 against the vector leg's own floor of 3.2 leaves a
  0.2-wide band for the keyword leg to retrieve in, and there is almost nothing
  in it. So the constants are independent by role AND their proximity squeezes
  the leg to nothing — both true, and the second explains the observation the
  first does not.

  **Verified:**
  - Gate: 297 files formatted, ruff clean, **916 passed**.
  - Mutations dev ran, re-run by me, plus two of mine: gutting `scores` — the
    load-bearing corroboration half — fails 5, and dropping `VECTOR_SUPPORT`
    from `search` fails 2. So the module's real job IS pinned, which matters
    given the docstring now says the other half does nothing.
  - The single-leg fusion test is the right addition: it is not an edge case
    here, it is every query measured, and it was untested.
  - Leaving the 70/30 mechanism in place while documenting that it has ranked
    one list is the correct call. Deleting it would bake this corpus's
    behaviour into the recipe; describing it accurately costs nothing and stops
    the next reader inferring a fusion that is not happening.

  No new work filed. The residual from #135 (two overview phrasings returning
  explore) remains #134's class and is still not this.

## Review log (PO)
- 2026-09-22 PO: **PASSES — closed to done.** All three criteria met.

  A ticket that measured twice and changed no behaviour, correctly. The floor
  being unreachable is the kind of finding that tempts an immediate fix; the
  sweep that shows the fix buys one hit for a 58% floor reduction is what makes
  "change nothing" the evidenced answer rather than the lazy one.

  **What I am closing this on is the documentation, and I want to say why that
  is a real deliverable.** `fusion.py` told every reader that hrono ranks a
  weighted fusion of two legs. It ranks one. That is the same shape as #123's
  docstring promising a corrective that did not exist and #120's "drift" that
  was a snapshot — code describing a system it is not, which this project has
  now hit three times and which costs somebody a day each time they believe it.

  The mechanism stays, and that is right: deleting the weighting would bake one
  corpus's behaviour into a frozen recipe, and a different embedding model could
  make the keyword leg fire tomorrow. Describe accurately, keep the mechanism.

  **This closes the recall investigation arc** — #127 (path blend), #134
  (corroboration sweep), #126 (window diversity), #135 (the summary layer), and
  now #140. Recall went from "a paraphrase returns one hit and one document" to
  every measured on-topic question returning a full, diversified window with
  summaries winning the overview questions, and the eleven absent questions
  never moving. Five tickets, one counterweight suite, no leaks.
