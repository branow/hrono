---
id: 121
title: The shape check rejects a brief that quotes a question from the source
priority: medium
size: small
depends_on: [103]
spec_refs: [build-order.md#T21]
found_by: qa while verifying 103 on 2026-09-15
---

## Context
`summarize/shape.py:unusable` rejects `asks-the-caller` when ANY sentence in the
reply ends in "?" and contains "you"/"your":

```python
if any(s.endswith("?") and _YOU.search(s) for s in sentences):
    return "asks-the-caller"
```

The rule's stated intent is "a summary describes material; it does not
interrogate the person who asked for it". As written it cannot tell
interrogating the caller from QUOTING or REPORTING a question that is in the
material.

## Description
Zero false positives on the real corpus: I ran the check over all 14 stored
briefs in both e2e databases and only F21's genuine non-answer was rejected. The
exposure is in material the current three-repo corpus does not contain — FAQs,
troubleshooting pages and second-person how-to docs, i.e. exactly what the
Confluence/Notion source types on the roadmap are made of. Four legitimate
briefs I constructed are rejected:

```
"The module's docstring opens with \"How do you sign a cookie?\" and then
 answers it: Signer.sign appends a timestamp and an HMAC."          -> rejected
"A FAQ covering deployment. Questions answered include: ... Can you run this
 behind a proxy? What happens when a token expires?"                -> rejected
"...The final entry asks: why does your token expire early?"        -> rejected
"...Have you ever needed a signed cookie? it asks, before introducing
 URLSafeTimedSerializer and its max_age parameter."                 -> rejected
```

Cost per false positive is exactly what #103 set out to avoid: one paid retry
(same prompt, so the same reply is likely) and then a row in the triage queue
the flag exists to serve. The brief is still STORED, so no topic is lost — the
harm is spend plus triage noise, not data loss, which is why this did not block
#103.

A second, narrower case: `addresses-the-caller` is documented as safe for a
brief that "quotes such a phrase mid-text", but the check runs over the whole
FIRST SENTENCE, so a quote inside a long opening sentence is rejected —
`"The contributing guide tells reviewers to reply 'let me know if you need more
detail' when requesting changes, and documents the two-approval rule."` is
flagged. A quote in the second sentence is safe, as documented.

## Description of the fix
Keep the rule conservative; make it discriminate. Options, cheapest first:
- require the question to be the LAST sentence. F21's question is last
  ("...not a request for me to act on something. Are you sharing this as a
  reference pattern?"), while a quoted or reported question is normally
  followed by the summary continuing. This clears three of the four cases above
  and keeps the true positive.
- ignore a question that sits inside quotation marks or after a reporting verb
  ("asks", "the docstring opens with").
- for the meta-opener, match only at the START of the first sentence rather than
  anywhere within it.
Whichever is chosen, keep `test_usable_briefs_are_left_alone` and add the four
texts above to it, so the discrimination is pinned rather than argued.

## Acceptance criteria
- [ ] A brief that quotes or reports a question from the source is not rejected;
      the four texts above are pinned as usable.
- [ ] F21's actual stored text is still rejected (fixture, not a lookalike).
- [ ] A brief quoting an assistant phrase inside its first sentence is not
      rejected, matching what the module docstring already promises.
- [ ] `ruff format`, `ruff check --fix`, `pytest` clean.

## PO ruling (2026-09-15, at #103's close)

**Priority confirmed at `medium`.** Zero false positives across all 14 real
stored briefs (PO re-measured: run1 rejects 1 of 7 — F21 itself — and run2
rejects 0 of 7), so the class is not currently biting. But a corpus holding an
FAQ, a troubleshooting guide, or a docstring that quotes a question at the
reader is entirely ordinary, and the cost lands twice: a paid retry AND a
polluted triage queue, which is the queue the flag exists to serve. Not `low`.
Not `high` either — one narrow class, bounded, and the guard is otherwise
measured clean.

**Specify the discriminator now — recorded below while the reasoning is fresh.**
A heuristic is cheap to write down today and expensive to rediscover in a month.

### Starting proposal (qa's, NOT a settled decision)

A brief that INTERROGATES the caller tends to end on its question — F21's
question is the last sentence. A brief that QUOTES a question from the material
usually carries on afterwards, because the quote is evidence for a point the
brief then makes. So: only treat a `you`-bearing question as
`asks-the-caller` when it falls in the final sentence (or final N characters) of
the reply.

This is a heuristic nobody has yet tested against a corpus, so it is a starting
point, not a decision. It must be validated, not assumed.

## Acceptance criteria
- [ ] The discriminator still rejects F21 verbatim (run1's node 1 brief — the
      motivating case, available in `.e2e/run/.hrono/hrono.db`).
- [ ] It no longer rejects any of the four false positives qa constructed; those
      four are committed as test cases.
- [ ] It rejects nothing across all 14 real stored briefs in the two e2e
      databases beyond what `unusable` rejects today.
- [ ] **If the heuristic cannot satisfy all three, this ticket closes with that
      finding recorded and NO change shipped.** A guard that trades a narrow
      false-positive class for a false-NEGATIVE one is worse than the
      conservative guard it replaces — #103's whole design premise is that being
      wrong is expensive, so do not ship a worse trade to close a ticket.
- [ ] `ruff format`, `ruff check --fix`, `pytest` clean.

## Review log
- 2026-09-15 PO: confirmed `medium`; recorded qa's discriminator as the starting
  proposal with an explicit validation bar and an explicit licence to close
  without shipping if the bar is not met.

## PO triage 2026-09-21 — promoted to `todo`, priority confirmed `medium`

A brief REJECTED for quoting a question out of its own source is a false
positive in the guard that protects brief quality, and a rejected brief is a
topic with no summary. Small, bounded, and it degrades the read door every time
it fires.

## Review log (dev)
- 2026-09-21 dev: implemented and committed. All four criteria.

  **The discriminator: LAST sentence AND no reporting cue.** I took qa's
  starting proposal and it clears three of the four cases as the ticket
  predicted; the fourth ("The final entry asks: why does your token expire
  early?") IS last, so it needs the second half — a reporting cue in the
  sentence ("asks", "opens with", "questions answered include", a quote mark).
  A brief that quotes a question carries on afterwards; one that reports a
  question says so; one that interrogates does neither.

  `addresses-the-caller` is now anchored to the START of the first sentence
  (leading punctuation skipped), which is what the module docstring always
  claimed while the code scanned the whole sentence.

  **Two things the real corpus caught that reasoning did not:**

  1. **An apostrophe is not a quote.** My first quote cue included `'`, and
     F21's own text contains "you'd like me to condense" — so the true positive
     started passing. The class is now `" “ ‘` only, with the reason in a
     comment, because this will look like an oversight to the next reader.
  2. **A footer hid the question.** F21's STORED text ends with a `References:`
     block (briefs carried one before #102 moved it out), and the sentence
     splitter cuts a URI at every dot — so the fragments look like prose and the
     question stops being last. I dropped the non-prose tail by LINE rather than
     by sentence, which is the only level at which a URI list is recognisable.
     Without it the `run` corpus rejected 0 of 7 where the PO had measured 1.

  **Re-measured on both real corpora, matching the PO's numbers exactly:**
  ```
  .e2e/run  : 7 briefs, rejected [(1, 'asks-the-caller')]   <- F21, the true positive
  .e2e/run2 : 7 briefs, rejected []
  ```

  Tests: F21's ACTUAL stored text (fixture, not a lookalike) still rejected;
  the four quoted/reported questions from the ticket pinned as usable; an
  assistant phrase quoted mid-sentence usable; a genuine meta-opener still
  rejected; F21 WITH its footer still rejected; a brief ending in bullets
  usable. Mutations: any-sentence fails 21, ignoring the reporting cue fails 1,
  scanning the whole first sentence fails 1, not dropping the tail fails 1.

  Not done, per Out of scope: no change to the retry-once behaviour or the flag.

  Gate clean: `ruff format`, `ruff check --fix`, `pytest` **897 passed**.
- 2026-09-21 qa: **FAIL — back to todo.** The discriminator is right and the
  real-corpus numbers match the PO's exactly. One mutation I tried survives, on
  the helper this ticket added.

  **Blocking — `_prose`'s tail drop is pinned for what it REMOVES, never for
  what it must KEEP.**
  ```
  mutation: while lines and len(lines) > 1: lines.pop()   (drop every line but
            the first, instead of only the non-prose tail)
  result:   193 passed
  ```
  Every test whose brief is interrogating happens to be a single line, so a
  tail drop that eats real prose is invisible. The consequence is the dangerous
  direction for a quality guard: a multi-paragraph brief that ENDS by
  interrogating the caller would have its closing question thrown away and read
  as usable. F21's own reply is two sentences on one line; had the model put a
  blank line before its question — which is ordinary formatting — this check
  would now miss it.

  It also leaves `_TAIL` free to grow. If anyone later adds a pattern that
  happens to match ordinary prose, nothing fails.

  Fix: one test with a MULTI-LINE brief whose last line is prose ending in an
  interrogating question, asserting `asks-the-caller`. It fails under the
  mutation above and pins the helper in the direction that matters.

  **What I verified as PASSING (need not be redone):**
  - Gate: 297 files formatted, ruff clean, **898 passed**.
  - The two-part discriminator is right, and I confirmed both halves are
    load-bearing: dropping the `you` test fails 2, dropping the question-mark
    test fails 1.
  - **The two real-corpus catches are the best work in this ticket.** The
    apostrophe one is the kind of bug that ships: `'` in a quote class makes
    "you'd" read as a quotation, and it silently disabled the TRUE positive.
    Catching it by re-measuring against the stored briefs rather than trusting
    the unit tests is exactly right, and the reason is now a comment where the
    next reader will need it.
  - The footer one likewise: dropping the tail by LINE rather than by sentence
    is the only level at which a URI list is recognisable, since the sentence
    splitter cuts a URI at every dot. Without it `run` rejected 0 of 7 where
    the PO measured 1 — a silent loss of the only true positive we have.
  - Re-measured by me on both corpora: `run` rejects exactly F21, `run2` rejects
    nothing. Matches the PO's recorded numbers.
  - F21's ACTUAL stored text is the fixture, as the criterion required, and it
    is tested both bare and with its footer.
- 2026-09-21 dev: **re-picked up after qa's FAIL**; fixed. Tests only.

  qa is right: `_prose` was pinned for what it REMOVES and never for what it
  must KEEP, and every interrogating brief in the suite happened to be a single
  line, so a tail drop that ate prose was invisible. Their example is the one
  that makes it concrete — F21's own reply is two sentences on one line, and a
  blank line before the question is ordinary formatting.

  Two tests, one per direction: a multi-line brief whose last line is prose
  ending in an interrogating question is rejected, and a multi-line brief whose
  last line is ordinary prose is usable. qa's mutation (`len(lines) > 1` in
  place of the `_TAIL` match) now fails, so `_TAIL` can no longer be broadened
  into prose without something failing.

  Gate clean: `ruff format`, `ruff check --fix`, `pytest` **900 passed**.
- 2026-09-21 qa: **PASS — to po-review.** My mutation now fails, and the fix is
  pinned in both directions: a multi-line brief ending in an interrogation is
  rejected, one ending in prose is usable. `_TAIL` can no longer be broadened
  into prose without something failing, which was the real exposure.

  Everything in my previous PASS list stands — in particular the two
  real-corpus catches (the apostrophe reading as a quote mark, and the footer
  hiding the question), which are the best work in this ticket and would not
  have been found from the unit tests alone.

## Review log (PO)
- 2026-09-21 PO: **PASSES — closed to done.** All four criteria met, and my
  starting proposal needed the second half dev added.

  I proposed "only the last sentence counts" and recorded it as a starting
  point, not a decision. It clears three of the four cases; the fourth ("the
  final entry asks: why does your token expire early?") IS last, and needed the
  reporting cue. The combined rule — last sentence AND no reporting cue — states
  the actual distinction: a brief that quotes a question carries on, one that
  reports a question says so, one that interrogates does neither.

  **Both bugs in this ticket were found by re-measuring against the real stored
  briefs, and neither was visible from the unit tests.** An apostrophe inside a
  quote class made "you'd" read as a quotation and silently disabled the only
  true positive we have. A references footer hid the closing question, because
  the sentence splitter cuts a URI at every dot. Either would have shipped a
  guard that looks correct and no longer guards. The habit of re-running against
  the corpus after a heuristic change is what caught them, and it is worth more
  than the heuristic.

  qa's kickback was right and narrow: the tail drop was pinned for what it
  removes, never for what it keeps, and F21's own reply would have slipped
  through had the model put a blank line before its question.

  This matters ahead of M8. The exposure is FAQs, troubleshooting pages and
  second-person how-to docs — which is most of what a Confluence or Notion
  corpus is made of, and those source types are the next milestone.
