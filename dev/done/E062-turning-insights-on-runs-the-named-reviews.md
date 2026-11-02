---
id: E062
title: an admin who turns insights on runs the reviews the estimate names, root included
priority: high
kinds: [backend, ui]
depends_on: [E061]
outcomes: [O2, O1, O4]
journeys: [J7, J3]
waits_on: []
---

## Goal
An admin turns insights on for a built tree; the settings line says "Would
review 2 topics" (17 and the root 19 on flask). Today nothing they can press
runs those reviews: `settle` returns `settled:false` unless churn trips, and
a sync reviews other topics and never the root (acceptance 1, gap 1, O2
FAIL). Findings also keep no source version, so after a sync their evidence
links point at code the review never read (gap 2). The README does not
mention the step (gap 6). After this epic the admin presses one action, the
named topics and the root are reviewed, and every finding links the version
it was read at.

## Build on
- `tree/settle.py` `settle(force=...)` and `summarize/build_tree.py`, which
  already run a level's passes after its briefs; `summarize/insights.py`
  `passes_for`/`due` decide the passes (the dry run uses them). Add a path in
  `settle` for "not tripped, passes due": run the due passes bottom-up and
  re-brief only each reviewed topic's parent (as the sync chain's
  `_brief_upper_levels` does), never a full re-cluster. Rejected: forcing a
  full warm rebuild (re-clusters and re-briefs, costs calls for nothing).
- The Runs page's existing job queueing for the "Review now" action.
- The section's stored source version (the synced commit) and the existing
  section-link builder (`server/ui/reviewed.py` around line 99) for the
  evidence version.

## Design
Deltas to E060's shape brief (`done/E060-insights-in-the-dashboard.md`).
- Tree settings, insights on: the dry-run line gains when: "Would review 2
  topics, about $5.60 (estimate). Review now runs them; a sync reviews a
  topic whose brief it rewrites." A secondary button "Review now" next to
  the line, shown only when a pass is due and a model has the role; it
  queues `settle` and links to the run. Nothing due: "Every topic over the
  threshold is reviewed." No model: the existing "no model has the role".
- Topic page evidence: `path:lines` links to the file at the version the
  review read; an older finding with no version keeps today's link with a
  faint "version not recorded".

## Tickets

### 1 settle runs the due reviews when nothing else is due, and the settings say how
Change: settle, not tripped, runs the passes `passes_for` names and re-briefs
their parents only; the dry run and settings line name the action (Design);
"Review now" queues it. `docs/summarization.md` "Where it runs" and
`docs/api.md` say so.
Done when:
- [ ] on the flask copy (text models brief/judge/condense on the fake
      provider first, lessons; `insights` on the real claude-code opus),
      insights on at threshold 50 000: the dry run names topics T and the
      root; "Review now" (or `POST /jobs {"op":"settle"}`) runs exactly one
      pass on each of them and on no other topic, root last; no brief other
      than the reviewed topics and their parents is rewritten (counts in the
      Log); at most 10 real calls (D2)
- [ ] a second settle with nothing changed runs no pass and calls no model
- [ ] insights off, or no model with the role: settle untripped is still
      `settled:false` with no call (test)
- [ ] settings at 390 and 1440, light and dark: the line with the action and
      the button; the button absent when nothing is due (screenshots)

### 2 each finding's evidence keeps the source version it was read at
Change: the pass records, per evidence item, the version of the file the
lookups returned (the section's synced commit); the topic page links that
version.
Done when:
- [ ] after ticket 1's run on flask, every evidence item with a file of
      every new finding has a version equal to that source's synced commit
      (query in the Log)
- [ ] after a commit that changes that file is synced, the evidence link
      still opens the reviewed version, not the new one (test, and one link
      checked on the copy)
- [ ] findings stored before this epic render with today's link and
      "version not recorded" (test)

### 3 the README says what insights is, what it costs and what runs it
Change: README Configuration: the optional `insights` role with the others,
the per-tree `insights`/`insights_threshold`, about $2.50 a pass at API
prices, and that "Review now"/settle and syncs run the reviews.
Done when:
- [ ] a new reader following only the README sets the role, turns the step
      on and runs the reviews on the flask copy (commands quoted in the Log)

## Out of scope
- A root pass on every sync (D8 stands: a sync reviews the root only when
  its count reaches the threshold or its brief was rewritten).

## Tried

## Log
- 2026-11-02 po: created from acceptance 1 gaps 1, 2 and 6 (O2, O1, O4).
- 2026-11-02 dev: round 1 started, branch epic/E062.
- 2026-11-02 dev: T1 (feat settle) flask copy, fake text models, real opus insights: dry run named 17 and root 19; POST settle ran 2 passes (17 then 19), only briefs 17 and 19 rewritten, 1 fake brief-upper call + 4 opus calls; second settle after server restart: settled:false, no call. Mutations: untripped path removed, pending's model check removed -> tests fail. T2 evidence stamped (28 of 30 items versioned = synced commit; 2 cited condensed/ paths, now mapped, test; real model writes source/<src>/<path>); evidence link opens stamped version on copy (instance set to github.com/pallets/flask). Mutation: no stamping -> 2 tests fail. 8 real calls total. T3 README Insights section. Fast suite green (2164). Round 1 handed to qa.
- 2026-11-02 qa: round 1 PASS at cf1ef55. Drove the flask copy (text models + a review stub on a local fake provider): settle with insights off, and on with no insights model -> settled:false, 0 calls; Review now clicked in Chromium -> passes on 17 then 19 only, briefs 17 and 19 only rewritten; second settle 0 calls; double click -> second settle 0 calls; failing provider -> run failed naming 'review of topic 17'; hostile evidence (reviewer version dropped, ../ path unversioned, <script> escaped, lines 'abc' -> #L1); simulated newer sync keeps the reviewed blob link, unversioned finding says 'version not recorded'. README path with real claude-code opus (`hrono models set opus -f opus.json`, `hrono tree config set flask -f t2.json` insights on at 100000, Review now, `hrono jobs watch`): 1 pass on root 19, 5 findings, 13/13 evidence items versioned 85c5d93, links open blob/85c5d93; 3 real calls (validate + review + extend). Re-ran dev's mutation (untripped path removed -> settle test fails) and a stamping mutation (2 fail). Fixed cf1ef55: Review now posted to the page's tree, not the edited one; metered line lacked the period. Full suite green (1 known flake, passes alone and on main: backlog/flaky-test_a_topic_that_does_not_divide_is_refused_and_left_intact.md). Followups: backlog/E062-followups.md. Critique: evidence/E062/critique.md; ui-check: evidence/E062/ui-qa.
- 2026-11-02 po: accepted at cf1ef55. Review now runs 17 then the root 19 only, findings link the version read (85c5d93), the README path ran on real opus; settings at 1280 light and 390 dark checked. Followups 1-3 (a `hrono tree review` command, README cost, the Runs message) and 4 (two-source evidence key) folded into E063 ticket 3; the 390 chrome overlaps into E063 ticket 1; the manual-split flake into E064 ticket 3.
- Log: merged to main at ff8d488
