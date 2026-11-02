---
id: E060
title: a curator sees in the dashboard what insights will cost, what it changed in a topic, and what it found
priority: high
kinds: [ui]
depends_on: [E057, E058]
outcomes: [O4]
journeys: [J6, J7, J10]
waits_on: []
---

## Goal
A curator or admin who turned insights on needs to see, without the CLI,
what the step will cost, which topics it extended, what the strong model
changed against the cheaper brief and on what evidence, and what it spent.
Moves O4 (E054 536).

## Build on
- The Settings trees form already renders `Tree` fields (E057 adds them);
  the estimate comes from E057's dry run, shown the way the Set up page's
  estimate step shows calls and cost (`templates/setup.html`).
- The topic page's Previous versions block (`templates/node.html`, E033,
  E035) already diffs a version against the current brief: reuse it, do not
  build a second diff.
- Usage groups by role from the ledger (`server/usage.py`); the `insights`
  role should appear by itself; check the subscription estimate marking.
- Components from DESIGN.md: card, chip (`accent`, `warn`, `plain`), tip
  mark, `<details>` twisty, callout, empty state, tables. Locale: every new
  string in `server/locales` (Ukrainian too).

## Design
Shape brief (impeccable shape, incumbent system; no human round, so the
assumptions are marked).
- Job: Operate. Curator on a reviewed topic must answer "what did the
  strong model add, and can I trust it?" in one screen; admin on Settings
  must answer "what will turning this on cost?" before saving.
- Settings, trees form: "Insights" checkbox and "Review threshold
  (characters)" field with tip marks; below them a quiet line from the dry
  run: "Would review 3 topics, about $8.50 (estimate)" or, off, "Off: no
  reviews, no cost". Subscription: cost marked estimate as on Usage.
  Unsaved change re-estimates on the dry run (no new endpoint).
- Topic page, reviewed: under the "who wrote its brief" line, an `accent`
  chip "extended by insights" + model (mono) + date; a link "What changed"
  jumps to Previous versions with the cheaper brief's version opened and
  diffed. Then a card "Findings (9)": each finding a row: statement (body),
  confidence chip (high `ok`, medium `warn`, low `plain`), placement
  (faint: "stated in X" / "not stated" / "corrected"), evidence as mono
  `path:lines` links (to the file at the synced commit when the source has
  a web host, as section links do). "Checked and dropped (5)" folded in a
  twisty at the card's end.
- States: off (no chip, no card); on, no pass yet (no chip; card absent);
  reviewed with 0 findings (chip; card body "The review found nothing to
  add."); 15 long findings (rows wrap, paths break on `/`, no sideways
  scroll at 390); pinned (callout `warn`: "Pinned: findings kept, not
  applied to the brief" above the list); failed pass (callout `danger` with
  the run link, brief unchanged).
- Usage: `insights` appears as a role row like the others; no special card.
- Anti-goals: no "Insights" tab or page; no repeat of the tree's name; no
  word outside GLOSSARY.md (add "insights" and "finding" there in E057/E060).

## Tickets

### 1 tree settings show the step and its estimate
Done when:
- [ ] on the flask copy, Settings > trees shows Insights and the threshold
      with tips; toggling on shows the topics count and estimated cost from
      the dry run, off shows no cost; saved values round-trip
- [ ] the Insights tip says "about $2.50 a pass at API prices" (a
      subscription is not billed per token, `trees.py:63`); a threshold of
      `true` is refused like any non-integer (`trees.py:68`)
- [ ] 390 and 1440 wide, light and dark, keyboard only: screenshots in
      `evidence/E060/`

### 2 a reviewed topic shows the extension and its findings
Done when:
- [ ] on the flask copy after an E058 pass, the reviewed topic shows the
      chip with model and date, "What changed" opens the diff against the
      cheaper brief, and the findings card with evidence links and the
      dropped list folded; a pinned topic shows the callout; a topic with
      0 findings shows the empty line
- [ ] a seeded topic with 15 long findings: no horizontal scroll at 390
- [ ] a reader sees all of it and no write control
- [ ] an extended topic's page dates the brief by the extension (today
      "Built" shows the node's creation, 2026-10-10 on flask node 17)
- [ ] a topic passed six times with no rewrite between, after an earlier
      rewrite and pass: "What changed" still diffs against the cheaper
      brief (test; `summarize/briefs.py` `_keep_replaced` keeps the first
      pass version ever, not the oldest since the last non-pass one;
      E059 qa)

### 3 Usage counts the insights role
Done when:
- [ ] Usage on the flask copy after the passes lists `insights` with its
      calls and spend (subscription marked estimate); screenshots at 390
      and 1440, light and dark
- [ ] a sync's and a build's `insights` result carries the passes' tokens,
      added up like reviews (`summarize/build_tree.py:125` `total_insights`
      drops them; E059 qa)
- [ ] docs/dashboard.md describes the three surfaces

## Out of scope
- Re-running a pass from the page (proposal if wanted).

## Tried

## Log
- 2026-11-02 po: created from E054 536 (O4) with the shape brief.
- 2026-11-02 po: folded E057 qa followups (tip copy, bool threshold).
- 2026-11-02 po: folded E058 qa followup: the topic's date is the extension's.
- 2026-11-02 po: folded E059 qa followup: the insights result's token count (ticket 3).
- 2026-11-02 po: folded E059 qa followup: the cheaper brief kept after many passes (ticket 2).
- 2026-11-02 dev: round 1 started.
- 2026-11-02 dev: round 1 built (a4c6df9, a434ebc). Real app: flask copy seeded with 5 passes, ui-check at 1280/390 light+dark, Space on the Insights checkbox re-estimates. Mutations: tokens sum, kept-version rule, subscription flag, bool threshold, extended-vs-rewritten, failed-run since, cheaper flag, estimate JS body encoding. Evidence dev/evidence/E060.
- 2026-11-02 qa r1: pass at 03ba737. Drove the flask copy (dev's 5 seeded passes) as admin and reader at 390 and 1440: topics 19/1 extended (chip, What changed opens the cheaper brief, survives reload and back), 17 pinned, 18 nothing to add, 2 failed run links its run (200); Settings estimate re-estimated by keyboard on flask and streamlink, matches PUT ?dry_run=true (5 topics, $14.10 at 20000), double-click save round-trips, blank threshold saves 500000; true/0/1.5 refused; reader gets 403 on the dry run and the form preview; Usage lists insights with est. Re-ran dev's kept-version mutation (2 tests fail). Fixed: failed-review callout matched another tree's or a longer name's run (298ca55), the no-model estimate ran into the count (89e6643), reader-session test (03ba737). ui-check and critique in evidence/E060/qa and critique.md. Full suite 2325 passed. Followups: dev/backlog/E060-followups.md.
- 2026-11-02 po: accepted at 03ba737. Screenshots of node 19 (1280 light, 390 dark) show the chip, What changed, findings and the folded dropped list; Settings estimate fixed by 89e6643. Followups (provider-error callout, threshold placeholder, tip wording) folded into E061.
