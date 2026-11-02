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

### 3 Usage counts the insights role
Done when:
- [ ] Usage on the flask copy after the passes lists `insights` with its
      calls and spend (subscription marked estimate); screenshots at 390
      and 1440, light and dark
- [ ] docs/dashboard.md describes the three surfaces

## Out of scope
- Re-running a pass from the page (proposal if wanted).

## Tried

## Log
- 2026-11-02 po: created from E054 536 (O4) with the shape brief.
