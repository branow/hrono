---
id: 215
title: the shell and the home page — no overflow, no overlap, a home that answers "is it up to date"
priority: high
size: big
depends_on: []
spec_refs: [REQUIREMENTS.md#3 (17, 18, 20), #12 (74-79)]
---

## Context
Defects on every page: 4px of horizontal overflow at 1440px, hint bubbles that cover what they explain, a top bar that breaks at 800px. And a home page that shows four numbers and leaves two thirds of the window blank.

## Description
Shell. Remove the horizontal overflow at every width from 800px up, on every page. Hint bubbles open clear of their anchor and stay inside the viewport. The top bar collapses deliberately at narrow widths. Navigation becomes the agreed set — Home, Map, Ask, Runs, Health, Usage, Export, Settings, Guide — showing only the entries whose pages exist when this ticket lands; current-page marking is correct on every route, including topic pages.

Empty states. Every one says what the state means and offers the next action as a button or link, not a CLI command.

Feedback. Every action returns to the page it was taken from with a plain statement of what happened.

Home. Answer, in order: is the tree up to date (per source: last read, the commit it is at, whether the source has moved since), is anything running now (live progress, not only on the runs page), does anything need attention, what did the last run do. Drop the card that holds only "Open the map"; put a small live preview of the tree's shape or a direct link in the head instead. "Sync now" stays the primary action and reports the run it started.

Add a regression test that loads every UI route at 1440px and 800px in a real browser and fails on horizontal overflow — the defect is otherwise guaranteed to return.

## Findings from the UI review (2026-10-03)
Seen by driving the dashboard in headless Chromium against a copy of the `~/hrono-click` database (tree `click`: 8 topics, 2 levels, 126 sections, 3 runs), as admin and reader, at 1440px and 800px, light and dark. Screenshots are in `.autodev/board/ui-review-2026-10-03/`. Severity: **A** wrong or broken, **B** confusing enough to cost time, **C** polish. The tree is small, so anything that only breaks at scale was not seen; forms were opened, not submitted.

- **A** Every page is 4px wider than the window at 1440px, so a horizontal scrollbar is always there; the home page is 22px too wide at 800px. Screenshot: `admin-overview-1440-light.png`, `admin-overview-800-light.png`.
- **A** A hint bubble opens on top of the thing it explains: the "topics" hint covers the figure 8. Screenshot: `s-overview-tip.png`.
- **B** At 800px the top bar wraps into two rows with the user block orphaned on its own line.
- **B** The tab for a topic page lights up "Map", though the page is not the map. No tab exists for what the page is.
- **B** Empty states are one centred sentence with no next step: "Nothing decided about click yet", "It reported nothing", "No result recorded".
- **C** Half of each page at 1440px is empty while content sits in a 1130px column; on the home page the lower two thirds are blank.
- **B** The "Map" card is a full-width card holding one button.
- **B** Nothing about sources (which, when last read), a running job, or spend. The page answers "how big" and not "is it up to date".
- **C** "Needs attention" shows one row in a box inside a card.

## Acceptance criteria
- [ ] no page has horizontal overflow at 800, 1100 or 1440px — asserted by a browser test over every UI route
- [ ] no hint bubble overlaps its anchor's content or leaves the viewport
- [ ] home shows per-source freshness, including a source that is behind
- [ ] a running job is visible on home and updates live
- [ ] every empty state has a next action
- [ ] the current page is marked correctly on every route
- [ ] screenshots of every page, before and after, both themes, in the Review log

## Out of scope
Mobile layouts below 800px. A new visual identity — fix what is there.

## Review log
- 2026-10-03 po: authored from the requirements review and the UI review of the same day, at the user's request.
