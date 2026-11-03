---
id: E065
title: a review that fails from Review now shows on its topic, in either language
priority: medium
kinds: [ui, backend]
depends_on: [E063]
outcomes: [O4, O2]
journeys: [J6, J7]
waits_on: []
---

## Goal
A curator presses Review now (or runs `hrono tree review`) and the insights
model answers an error. The run fails on Runs, but the topic page says
nothing: the review ran outside a named stage, so the failed job names no
item and the topic never learns of it. O4 says a failed pass shows on its
topic; today that holds only for a sync. Also from E063's qa: the topic
says "the review found nothing to add" right under "the last review did not
finish", the uk page shows the model's English level word, the "low" chip
looks like plain text, and E063's rule hiding closed disclosures stops the
browser's find-in-page from finding text in them.

## Build on
- The sync path already runs review as a named stage (`_stage` in
  `src/hrono/tree/settle.py`); `_review_due` (settle.py:123) does the same.
  `_failed_run` (`server/ui/reviewed.py:172`) then matches unchanged.
- `hidden="until-found"` (Chromium, Safari 18) or scoping E063's
  `details:not([open]) > :not(summary)` rule (base.html:221) to the tree menu
  and Runs; rejected: removing it (brings back the overlap reports).
- Chip tones from E060's shape brief; translations through the existing
  `_()` catalogue.

## Design
- Failed last review: the callout only; "The review found nothing to add."
  shows only when the last review finished with no findings.
- Level chip text through `_()`: en high/medium/low, uk висока/середня/
  низька. `plain` (low) gets the faint wash other quiet chips use, so it
  reads as a chip, not mono text.

## Tickets

### 1 a review that fails during Review now shows on its topic
Change: run the due reviews in `_review_due` as a named stage so the failed
job names the topic; `POST /jobs {"op":"settle"}` on an unknown tree is
refused like `/trees/<name>/sync`; `insights_threshold` gets an upper bound
(a field error, not a saved 40-digit value).
Done when:
- [ ] on the flask copy, the insights model on a fake provider that answers
      500: Review now fails, and the reviewed topic shows the failed-review
      callout with a link to that run; `hrono tree review flask` the same
      (test through the topic page)
- [ ] that topic shows no "found nothing to add" under the callout
- [ ] `POST /jobs {"op":"settle","tree":"nope"}` answers 404, no job queued
- [ ] a raw form POST of a 40-digit threshold re-renders with a field error

### 2 the findings card reads right in uk, and find-in-page works
Done when:
- [ ] topic 17 on the flask copy in uk: chips read висока/середня/низька;
      the low chip has a visible wash, light and dark, 390 and 1280
- [ ] Ctrl-F for a word inside a closed disclosure (a topic's "Details")
      finds it in Chromium; ui-check at 390 still reports no overlap on the
      tree menu and Runs (evidence/E065/)

## Out of scope
- Home's 0.55 s rewrite plan and the long moving line (E064 followups).

## Tried

## Log
- 2026-11-03 po: created from backlog/E063-followups.md (qa round 1 and po review).
- 2026-11-03 dev: round 1. T1 commit on epic/E065 (settle review stage; real app: fake 500 provider, hrono tree review flask failed naming 'review of topic 17', topic page shows callout + run link, no 'found nothing'; POST /jobs settle nope 404; 40-digit threshold refused; mutations: unwrap stage, drop 'not failed', drop require_tree each fail a test). T2 (uk chips seen at 390 light/dark; find-in-page: window.find in Chromium, test bites when the global rule returns; ui-check evidence/E065).
- 2026-11-03 qa: round 1 pass at d347ea1. Drove on the flask copy with a fake provider: hrono tree review and Review now (double click queued one run) fail naming review of topic 17, topic page shows the callout + run link, no found-nothing; POST /jobs settle nope/''/../ 404; threshold 40 digits, 1e9, 100000001, 0, -5, 1.5 refused; uk chips висока/середня/низька at 390/1280 light/dark; find-in-page reaches a hash in the closed Details (not with the old rule). Re-ran unwrap-review-stage mutation (2 tests fail) and the threshold-bound mutation (fails). Fixed: end-to-end worker test (c2e8d0a), api.md 404 line (644f150), dashboard Review now door refuses an unknown tree (d347ea1). Full suite 2373 passed. ui-check: new overlap reports are undrawn closed-disclosure content (followups). Followups: backlog/E065-followups.md.
- 2026-11-03 po: accepted at d347ea1. The failed review shows on its topic from Review now and `hrono tree review`, uk chips read висока/середня/низька with a visible low wash (screenshots seen), find-in-page reaches closed Details. The JSON titles in qa's screenshots are the fake provider's canned answer on qa's own copy, not a product fault. Remaining items stay in backlog/E065-followups.md for acceptance 2.
