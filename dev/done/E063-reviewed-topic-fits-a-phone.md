---
id: E063
title: a reviewed topic and the tree form hold on a phone and on bad input
priority: medium
kinds: [ui, backend]
depends_on: [E062]
outcomes: [O4]
journeys: [J6, J7]
waits_on: []
---

## Goal
A curator opening a reviewed topic on a 390-wide phone sees the findings run
off the screen: the page is 677 px wide because the model's confidence prose
sits in a chip that does not wrap (acceptance 1, gap 3; quality bar missed).
A failed review shows "Findings 0", read as "nothing found". The tree form
answers 500 to a non-numeric threshold. After this epic the topic page and
the form hold at 390, in both themes and both languages.

## Build on
- E060's shape brief: confidence chip high `ok`, medium `warn`, low `plain`.
  The level word becomes the chip; the rest of the model's sentence is faint
  body text that wraps. A confidence with no level word is plain text, no
  chip.
- The form's existing field-error path (`-3` re-renders with an error):
  `src/hrono/server/forms.py:402` `_number`.
- `backlog/E061-followups.md` items 2-4 and 6.

## Design
Deltas to E060's shape brief: confidence "high; the code path in make_config
is unconditional" renders as chip "high" + faint "the code path in
make_config is unconditional" on the line below the statement, wrapping.
Failed last review: the card heading has no count. Threshold placeholder per
locale (en "500,000", uk "500 000").

## Tickets

### 1 findings wrap at 390 and a failed review shows no count
Done when:
- [ ] on the flask copy after E062's passes, topics 17 and 18 (or the ones
      reviewed) at 390 wide, light and dark, en and uk: page width 390, no
      sideways scroll (ui-check report and screenshots in `evidence/E063/`)
- [ ] a 15-finding topic with long confidence prose and long paths holds at
      390 (seeded test fixture through the real page)
- [ ] a topic whose last review failed: the card heading has no "0"
- [ ] ui-check at 390, light and dark, on settings, a topic and Runs:
      no overlap in the page chrome (nav, the "admin" chip); every nav
      item reachable (today "Settings" is cut at the right edge)

### 2 the tree form refuses bad thresholds with a field error
Done when:
- [ ] a raw POST of `f.insights_threshold=abc` or `500,000` re-renders the
      form with a field error, no 500, tree unchanged (test)
- [ ] the JSON schema example for `insights_threshold` is an int; the
      placeholder is per locale (en "500,000", uk "500 000")

### 3 a CLI admin runs the reviews with one command, and the copy names them
Change: `hrono tree review <tree>` queues `settle` and watches it like
`hrono tree sync` does; README names it instead of `POST /jobs`, which
docs/api.md calls "for debugging only"; README cost "about $2.80 a topic (a
review and the extend call)", matching the dry run; Runs after Review now
says the reviews started, not "Started settle."; evidence versions keyed by
bare repo path only when one source of the tree holds that path
(`summarize/review.py:251`). From `backlog/E062-followups.md`.
Done when:
- [ ] on the flask copy with insights due (review model on the fake
      provider), `hrono tree review flask` runs the due passes and prints
      their result; with nothing due it says so and calls no model
- [ ] Runs after Review now names the reviews, en and uk
- [ ] a tree of two sources both holding `README.md`: an evidence item on
      it gets no version, or the version of the source it names (test)

## Out of scope
- The unscoped other-model condensation embed (E061 followups; needs a run
  stopped between condense and embed and a model change).

## Tried

## Log
- 2026-11-02 po: created from acceptance 1 gap 3 and E061 followups.
- 2026-11-02 po: ticket 3 and the chrome line added from E062 review (backlog/E062-followups.md).
- 2026-11-03 dev: round 1 started, branch epic/E063.
- 2026-11-03 dev: ticket 2 a1292b2: raw POST abc / 500,000 re-renders with "valid integer" field error, tree unchanged; placeholder en 500,000 / uk 500 000, schema example an int. Verified on the real tree form; mutation: _number raising again fails both tests.
- 2026-11-03 dev: ticket 1 5b135ff: confidence parsed to level chip + wrapping prose; failed review heading has no count; tabs wrap to two rows at <=720 so Settings is reachable; closed disclosure content no longer reported as overlapping (tree menu, Runs). Real flask copy, topic 17 seeded with 15 long findings, 18 with a failed run: page width 390, light/dark, en/uk, ui-check in evidence/E063/ui and ui-uk (remaining reports are the clipped long-brief "Read the whole brief" and clipped brief vs callout at 1280, pre-existing). Mutations: nowrap tabs, count shown when failed, old comma parse each fail a test.
- 2026-11-03 dev: ticket 3 35031ff: hrono tree review (settle via POST /jobs, watched, result printed), run on flask copy with a local fake openai-compatible model: "Reviewed 2 topics, extended 0: 0 findings."; second run "Nothing is due for review; no model was called." with 0 model calls. Runs says "Started the reviews." (en/uk), bare-path evidence version only when one source holds it, README $2.80 and CLI. Mutations: always-keep bare key, drop then=review, drop result print each fail a test.
- 2026-11-03 dev: fast suite 2176 passed (44 s). Handed to qa.
- 2026-11-03 qa: round 1 pass at eb7e939. Drove on a copy of the flask tree with a local fake model: hrono tree review ran 2 due reviews (6 findings, hostile <script> statement escaped), then reported nothing due with 0 calls. A model 500 failed the run with exit 1, and Review now in uk at 390 (double click) queued one job and the Runs notice showed. Raw form POSTs of abc/500,000/inf/nan/-5/1.5/5000 digits each gave a field error, never a 500. The findings card came back after a restart. ui-check en and uk on topics 17/18/19, Runs and settings: the remaining overlaps are inline-wrap and clipped-brief false positives. Re-ran dev's mutation (bare-path key always kept): it fails. qa fixed 34bb7ec (tree review now says insights off, unknown tree, no insights model and a drifted re-cluster; a failed watch prints the error; README) and eb7e939 (uk 'Перегляди запущено.'). Full suite 2363 passed. Followups: backlog/E063-followups.md; critique evidence/E063/critique.md.
- 2026-11-03 po: accepted at eb7e939. Screens at 390 (en light, uk dark): findings wrap, failed card has no count, tabs reach Parameters. The failed review not shown after Review now, the "found nothing to add" line under a failed callout, the uk chip word and find-in-page in closed disclosures go to E065.
- Log: merged to main at e62dcea
