---
id: 214
title: the topic page — sections you can tell apart, facts before hashes
priority: medium
size: medium
depends_on: [212]
spec_refs: [REQUIREMENTS.md#4 (28)]
---

## Context
The topic page is where a curator spends their time and it has one false alarm, one unreadable list and an information order that puts hashes level with facts.

## Description
Root: a topic with no parent that is the tree's root is shown as the root, not as a warning. The unreachable warning stays for topics that really are orphaned.

Sections: each row shows the file path plus what distinguishes it — the heading or symbol it starts at, its line range, its size — and its fit. Sort by fit so misfits surface; filter by path. Eleven rows reading "CHANGES.md core" must become eleven different rows.

Facts first: who wrote the brief, when, with which model and what it cost up front; build, prompt and member hashes behind "details".

Breadcrumb from root to this topic, with names from #212.

Actions in the page head: rename, edit brief, add note, and a Structure menu for reparent / merge / split / dissolve, each still confirming with its consequences stated. Pinned state is visible at the top.

A tab or breadcrumb that reflects where the user is, instead of lighting "Map".

Use the width: the brief should not sit beside a long empty gutter.

## Findings from the UI review (2026-10-03)
Seen by driving the dashboard in headless Chromium against a copy of the `~/hrono-click` database (tree `click`: 8 topics, 2 levels, 126 sections, 3 runs), as admin and reader, at 1440px and 800px, light and dark. Screenshots are in `.autodev/board/ui-review-2026-10-03/`. Severity: **A** wrong or broken, **B** confusing enough to cost time, **C** polish. The tree is small, so anything that only breaks at scale was not seen; forms were opened, not submitted.

- **A** The root topic is flagged in warning yellow: "PARENT none — nothing points at this topic". A root has no parent by definition. Screenshot: `admin-topic-root-1440-dark.png`.
- **A** The sections list is eleven identical rows "CHANGES.md core" — no heading, line range or size to tell one from another. Screenshot: `admin-topic-leaf-1440-light.png`.
- **B** "Who wrote the brief" exposes hashes (build, prompt, members) with equal weight to the facts a person wants (model, when, cost).
- **B** "COST 2 in, 5,371 out" — input is wrong for `claude-code` (cache tokens are dropped), and tokens are not a cost.
- **B** Editing is behind "Edit by hand" at the bottom of the brief card; structure surgery is not discoverable from the page head.
- **C** The right column ends after two small cards and leaves a long empty gutter beside the brief.

## Acceptance criteria
- [ ] the root topic shows no warning; an orphaned topic still does
- [ ] sections of the same file are distinguishable by heading/symbol and line range
- [ ] the section list sorts by fit and filters by path
- [ ] hashes are not visible until asked for
- [ ] every edit action is reachable from the page head, and absent for a reader
- [ ] full breadcrumb on every topic page
- [ ] existing node-page and surgery tests pass; before/after screenshots in the Review log

## Out of scope
New edit operations. Brief version history.

## Review log
- 2026-10-03 po: authored from the requirements review and the UI review of the same day, at the user's request.
