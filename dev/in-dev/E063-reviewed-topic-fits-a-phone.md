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
