---
id: E044
title: the map and the main actions work from the keyboard
priority: low
depends_on: []
requirements: [80]
---

## Goal
A user without a mouse can reach and operate the map and every page's main
action.

## Tickets

### 441 the map is keyboard-operable
Change: topics on the map are focusable in a sensible order, Enter opens one,
focus is visible; a skip link to a plain list of topics.
Done when:
- [ ] tab reaches every topic node; Enter opens it; focus ring visible both themes
Look at: templates/graph.html, server/graph.py

### 442 shell and main actions reachable by keyboard
Change: a "skip to content" link; `/` focuses Search; tree switcher and theme
button operable by keyboard; every primary button reachable in tab order.
Done when:
- [ ] driven by keyboard only: switch tree, search, start a sync, open a topic
Look at: templates/base.html, _parts.html

## Out of scope
- full WCAG audit; screen-reader copy beyond labels

## Log
- 2026-10-04 po: created from REQUIREMENTS 80.
- 2026-10-04 po: starting; E041 merged and no in-flight branch touches base.html/graph.html/_parts.html.
- 2026-10-04 dev: round 1 started.
- 2026-10-04 dev: 441+442 7ee0bf0 (one commit, shared templates); Chromium tests in tests/server/test_ui_browser.py (skip link, /, switcher+theme, tab reaches all topics + ring both themes + Enter keeps focus, outline skip, sync button); mutations: ring stroke, keep(), / key, Escape fold each fail a test; tests/server -k ui 552 pass.
- 2026-10-04 qa: pass 7ee0bf0; drove in Chromium: skip links (content + map outline), Tab to topics with the ring in light/dark (screenshots), Enter opens the panel with focus kept in it, / then Enter to find, switch between two seeded trees by Tab/Enter/Escape, Tab to Start a sync on a fresh tree; re-ran dev's Escape-fold, ring-stroke and keep() mutations plus my own (main tabindex, map skip link) and each failed a test; tests/server -k ui 552 pass; followups in backlog/E044-followups.md.
- 2026-10-04 po: reject 7ee0bf0; README:91 false (focus goes to the panel, not "kept where it was"), and per the user's "apply all suggestions" the qa followups (tab-reach test, full keyboard paths, header scroll, ring gap) are folded in here; backlog/E044-followups.md removed.
- dev round 2 f0e54c1: README says focus moves into the panel (test asserts it); Tab test checks topic hrefs subset; sync, switcher (second tree) and slash tests drive Tab/Enter to the end; body is one window tall so no document scroll; ring is a separate circle with a --bg gap. Mutated: old height layout and accent-coloured gap each fail the test. Evidence: evidence/E044/focus-ring-r2.png
- 2026-10-04 qa: pass f0e54c1 (round 2); all five PO findings fixed: README says focus moves into the panel and Chromium confirms it lands on the panel's close button; Tab-reach checks topic hrefs as a subset; sync/switcher/slash tests drive Tab+Enter to the end; drove the map at 1280x720, 800x600, 390x800 light+dark with scrollY 0 and the header in view throughout, ring with a page-coloured gap visible in both themes (screenshots); re-ran dev's old-height-layout mutation plus my own (ring circle removed, ring stroke none) and each failed the test; ruff clean; test_ui_browser 25 pass, tests/server -k 'ui or graph or shell' 552 pass; followups in backlog/E044-followups.md.
- 2026-10-04 po: reject f0e54c1; per the user's "apply all suggestions" qa's round-2 followup is folded in: the ring-gap assertion (tests/server/test_ui_browser.py ~612) must check the gap is the page colour (disc stroke == body background), not only != ring; backlog/E044-followups.md removed.
- 2026-10-04 qa: pass eefb2b2 (round 3); PO finding fixed: test_tab_reaches_every_topic_enter_opens_it_and_focus_is_drawn asserts disc stroke == computed body background in light and dark (tests/server/test_ui_browser.py:621); one-line test-only commit; re-ran dev's mutation (gap --accent) plus my own (gap --surface, the unfocused stroke, and --line), each fails at that assertion; ruff clean; tests/server/test_ui*.py 541 pass; no followups.
- 2026-10-04 po: accept eefb2b2; both Done-whens met by qa's keyboard-only drive, README matches the behaviour, every folded followup fixed, no followups left.
- merged to main at 4fb4cfd (rebased, one mechanical test-file conflict, full suite green)
