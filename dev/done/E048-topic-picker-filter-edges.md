---
id: E048
title: polish — the topic filter never leaves an empty level or a hidden pick
priority: medium
depends_on: [E046]
requirements: []
---

## Goal
E046's "Find a topic" filter can leave an empty level heading and keep showing a
topic it hid. Close both, and pin the filter with a browser test.

## Tickets

### 481 the filter hides empty levels and never keeps a hidden pick
Change: hide an optgroup once none of its options is visible; when the selected
option is hidden, reset the select to "pick a topic".
Done when:
- [ ] filtering to one level leaves no empty level headings
- [ ] filtering away the selected topic resets the select
Look at: src/hrono/server/templates/config.html:94-100

### 482 the filter has a browser test
Change: a test in the playwright harness types into the filter and checks
narrowing, empty-level hiding, the reset, and clearing restores every topic.
Done when:
- [ ] the test fails if either 481 rule or the filter itself is removed
Look at: tests/server/test_ui_browser.py, tests/server/test_ui_settings.py:1351

## Out of scope
- picker redesign

## Log
- 2026-10-04 po: created from backlog/E046-followups.md (user: apply all suggestions); waits for E046 to merge (config.html).
- 2026-10-04 po: E046 merged (f42ea92); starting. E044 may also add to test_ui_browser.py — append, do not reorder.
- 2026-10-04 dev: 481 bc7921f, 482 8104792; test_the_topic_filter_hides_empty_levels_and_resets_a_hidden_pick drives real Chromium; mutated each of group-hiding, reset, option-hiding, each failed it; no docs mention the filter.
- 2026-10-04 qa: pass at 8104792; ruff clean, test_ui_browser+test_ui_settings 85 passed (new test 1.4s); drove the filter in Chromium (all 14, 'leaf topic 1' -> Level 0 only, 'OVERVIEW' -> Level 1 only, no match -> no headings, a picked Level-1 topic reset to pick a topic) and read the screenshots; re-ran dev's group-hiding and reset mutations and my own case-sensitive match, each failed the new test; followups: backlog/E048-followups.md.
- 2026-10-04 po: accept at 8104792; both rules met as qa drove them, test pins each; json re-import left in backlog/E048-followups.md.
- merged to main at 8104792 (ff-only; full suite 2411 passed)
