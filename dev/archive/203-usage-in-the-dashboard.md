---
id: 203
title: the dashboard shows what was spent — home, run page, a Usage page
priority: medium
size: medium
depends_on: [202]
spec_refs: [REQUIREMENTS.md#11 (88-92), #3 (19)]
---

## Context
Today the only cost on screen is "2 in, 5,371 out" on a topic page, and the runs table has a TOKENS column that is always a dash.

## Description
Home: one figure for total spend and tokens on this tree, and the last run's, linking to the Usage page.

Run page and runs table: tokens, cost and model time for the run, split by stage.

A new Usage page (all roles): spend over time; a table per configured model with its upstream model, provider, calls, tokens, hours of model time and cost; the most expensive runs with who started them; spend per user. Subscription-billed figures are visibly marked as estimates and kept out of the metered total, as #202 reports them.

Server-rendered like the rest; charts are plain SVG or bars, no new JS dependency.

## Findings from the UI review (2026-10-03)
Seen by driving the dashboard in headless Chromium against a copy of the local test database (tree `click`: 8 topics, 2 levels, 126 sections, 3 runs), as admin and reader, at 1440px and 800px, light and dark. Screenshots are in `.autodev/board/ui-review-2026-10-03/`. Severity: **A** wrong or broken, **B** confusing enough to cost time, **C** polish. The tree is small, so anything that only breaks at scale was not seen; forms were opened, not submitted.

- **B** "COST 2 in, 5,371 out" — input is wrong for `claude-code` (cache tokens are dropped), and tokens are not a cost.
- **A** A 6m30s successful `maintain` shows "It reported nothing" and "No result recorded": no stages, no counts, no tokens. The most expensive action in the product leaves no trace. Screenshot: `s-run-ok.png`.
- **B** Each row repeats the op's full description, so the table is mostly the same two sentences; PROGRESS and TOKENS columns are empty.

## Acceptance criteria
- [ ] home shows total and last-run spend, and neither is blank on a tree with history
- [ ] a run's page shows its totals and a per-stage breakdown
- [ ] the Usage page answers: which model costs most, which run cost most, who started it, how many hours each model ran
- [ ] an install running only on `claude-code` never shows its estimate as money spent
- [ ] jobs from before the ledger show as unknown, not as free
- [ ] a reader can open the page; driven in a real browser at 1440px and 800px with no horizontal scroll

## Out of scope
Editing prices in the UI. Export of usage data.

## Review log
- 2026-10-03 po: authored from the requirements review and the UI review of the same day, at the user's request.
