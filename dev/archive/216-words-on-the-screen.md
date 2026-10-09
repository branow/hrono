---
id: 216
title: one vocabulary — every label, hint and message read as a person would say it
priority: medium
size: medium
depends_on: []
spec_refs: [GLOSSARY.md]
---

## Context
The glossary bans "chunk" and the map says "3 chunks nearer". The home page says "7 hold sections". Passing health checks read "0 topics nothing points at". Op descriptions shout "the NORMAL one". The words were written a page at a time.

## Description
Go through every user-visible string in the templates and the view code — labels, hints, legends, chips, empty states, confirmations, error and notice messages, op descriptions — and bring them to one voice: sentence case, whole phrases, glossary words only, no internal names (`node`, `chunk`, `cluster`, config keys) where a glossary word exists, no emphasis by capitals.

Specific repairs from the review: the home stats ("7 hold sections" -> a label that says what is counted); health checks phrased so that zero reads naturally and non-zero reads as a task; overlay labels; the map legend; op descriptions; "looking at it"; "What it ships as"; "Exactly what it returned".

Add a test that fails when a banned glossary word appears in rendered output of any UI route, so the vocabulary is enforced rather than remembered.

List the strings changed, old and new, in the Review log, so the user can veto wording.

## Findings from the UI review (2026-10-03)
Seen by driving the dashboard in headless Chromium against a copy of the local test database (tree `click`: 8 topics, 2 levels, 126 sections, 3 runs), as admin and reader, at 1440px and 800px, light and dark. Screenshots are in `.autodev/board/ui-review-2026-10-03/`. Severity: **A** wrong or broken, **B** confusing enough to cost time, **C** polish. The tree is small, so anything that only breaks at scale was not seen; forms were opened, not submitted.

- **B** "7 hold sections" reads as a sentence fragment; nobody can tell what is counted.
- **B** The overlay label says "3 chunks nearer" — "chunk" is a word the glossary bans.
- **B** The op descriptions shout ("the NORMAL one", "the FIRST one").
- **B** Passing checks read as nonsense: "0 topics nothing points at", "0 sections placed without a score".

## Acceptance criteria
- [ ] no rendered UI page contains a word the glossary lists as not used — enforced by a test over every route
- [ ] health checks read correctly at zero and at non-zero
- [ ] no label is a sentence fragment or an internal identifier
- [ ] the old -> new string list is in the Review log
- [ ] the guide and tooltips use the same word for the same thing

## Out of scope
Translation. Renaming API fields or CLI output.

## Review log
- 2026-10-03 po: authored from the requirements review and the UI review of the same day, at the user's request.
