---
id: 211
title: the Guide tells the truth and covers what people ask
priority: medium
size: medium
depends_on: []
spec_refs: [GLOSSARY.md]
---

## Context
The user reports the guide is wrong in places. The review found a broken table and at least one claim that contradicts shipped behaviour, and the page says nothing about recall, export, roles or cost.

## Description
Audit every factual sentence on `/ui/guide` against the code and the baked constants, and fix or remove what does not hold. Known suspects: "Change one in Settings and every brief it wrote goes stale" against #191 (repointing a model at another upstream model invalidates nothing); the "cached by content hash" caption placed under *section* rather than *condensation*. Record each claim checked and its verdict in the Review log — the audit is the deliverable, not only the edits.

Fix "Who writes what": one row per role with role, what it does, configured model, upstream model, in columns that do not wrap into each other.

Add what is missing, briefly: what recall does and why it sometimes refuses; what export produces; what each role can do; what a pin means in practice; where cost comes from.

Set body text to a measure that fits the card, and make diagram captions readable.

Where a number can come from a constant, it comes from the constant, so the guide cannot go stale again.

## Findings from the UI review (2026-10-03)
Seen by driving the dashboard in headless Chromium against a copy of the `~/hrono-click` database (tree `click`: 8 topics, 2 levels, 126 sections, 3 runs), as admin and reader, at 1440px and 800px, light and dark. Screenshots are in `.autodev/board/ui-review-2026-10-03/`. Severity: **A** wrong or broken, **B** confusing enough to cost time, **C** polish. The tree is small, so anything that only breaks at scale was not seen; forms were opened, not submitted.

- **A** "Who writes what" is broken: the upstream model name wraps onto its own line under the role, the configured name floats far right. Screenshot: `admin-guide-1440-light.png`.
- **A** Claims to verify against the code, at least: "Change one in Settings and every brief it wrote goes stale" (#191 says repointing a model invalidates nothing); the "cached by content hash" caption sits under *section* in the pipeline diagram and belongs to *condensation*.
- **B** No word on recall strictness, export, roles, pins in practice, or cost — the things a new user asks first.
- **B** Body text is set to a narrow measure inside full-width cards, so every paragraph wraps after half the card and leaves the rest blank.
- **C** Diagram captions are too small and too pale to read.

## Acceptance criteria
- [ ] every factual claim on the page is listed in the Review log with the code that backs it
- [ ] no number on the page is a literal that duplicates a constant
- [ ] the roles table renders without wrapping at 1440px and 800px
- [ ] recall, export, roles, pins and cost each have a short section
- [ ] GLOSSARY.md and the guide's word list agree, and a test fails when they diverge

## Out of scope
A tutorial or onboarding flow (#219).

## Review log
- 2026-10-03 po: authored from the requirements review and the UI review of the same day, at the user's request.
