---
id: E046
title: a canceled prompt preview says canceled; the topic picker scales
priority: medium
depends_on: [E043]
requirements: []
---

## Goal
The prompt preview (E043) misreports a canceled run as a failure and lists
every briefed topic in one select, which is unusable on a large tree.

## Tickets

### 461 a canceled preview says it was canceled
Change: a canceled preview job reads "The preview was canceled", not "The
preview failed" through `failures.explain`. Have `preview.panel` return a
typed shape so `_render` drops its `type: ignore[arg-type]`.
Done when:
- [ ] cancel a running preview: the page says canceled, no failure copy
- [ ] no `type: ignore` left in settings.py for the preview form
Look at: src/hrono/server/preview.py, server/ui/settings.py

### 462 the topic picker works on a large tree
Change: group the topic select by level (or a filterable list) so a user
finds one topic among hundreds.
Done when:
- [ ] on a tree with hundreds of briefed topics, a topic is found by level or by typing
Look at: src/hrono/server/preview.py, templates/config.html

## Out of scope
- previewing more than one topic at once

## Log
- 2026-10-04 po: created from backlog/E043-followups.md (qa round 1).
- 2026-10-04 po: E043 merged (f9af2bc); starting.
- 2026-10-04 dev: 461+462 committed together 26545ae; tests test_a_canceled_preview_says_canceled_not_failed and test_the_topic_picker_groups_topics_by_level_and_offers_a_filter; mutations canceled=False and a flat picker both failed them; tests/server 756 passed.
- 2026-10-04 qa: pass at 26545ae. Built 301 briefed topics on levels 0-2 and drove the picker in Chromium: three level optgroups, typing "(#250)" narrowed it to one topic, which could then be picked, and clearing the box brought all 301 back. Canceled a running preview through /ui/jobs/<id>/cancel: the page shows "The preview was canceled" in a warn callout and keeps the typed template. Re-ran dev's canceled=False mutation (it fails the test), plus mine: dropping the canceled branch from the template, a filter threshold of 100, and grouping by tree. All three were caught. Ruff is clean and test_ui_settings.py passes 65. Followups are in backlog/E046-followups.md.
- 2026-10-04 po: accept at 26545ae. Both Done-whens met by qa's drive (301 topics, cancel); README updated; picker edge cases in backlog/E046-followups.md.
- merged to main at f42ea92
