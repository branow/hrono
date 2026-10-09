---
id: 218
title: fix what the health page shows, from the health page
priority: medium
size: medium
depends_on: [216]
spec_refs: [REQUIREMENTS.md#7 (47-50), #8 (59)]
---

## Context
"Needs attention" is a list of counts that link elsewhere. The API can already place a parked section, the pipeline can already rewrite a stale brief; the panel offers neither where the problem is shown.

## Description
Each health item opens to its own list, with the action beside each row and for the whole list:

- waiting (parked) sections: where each would most nearly fit and its score; place it in a chosen topic (the existing move endpoint, which pins).
- stale or missing briefs: why it is stale (members, prompt or model changed); regenerate this one, or all.
- forced placements and misfits: the topic it sits in, the topic it is nearer to; move it.
- failed runs: link to the run page's retry (#213).
- hand edits: every pinned topic and section in the tree, who pinned it and when if known, with release.

Each item states whether automation will deal with it on the next sync or whether it is waiting for a person — the guide's "a few misfits are normal" belongs here, next to the number.

Regenerating one brief needs a way to run `brief` / `brief-upper` scoped to one topic; add the scope if the op lacks it.

## Findings from the UI review (2026-10-03)
Seen by driving the dashboard in headless Chromium against a copy of the local test database (tree `click`: 8 topics, 2 levels, 126 sections, 3 runs), as admin and reader, at 1440px and 800px, light and dark. Screenshots are in `.autodev/board/ui-review-2026-10-03/`. Severity: **A** wrong or broken, **B** confusing enough to cost time, **C** polish. The tree is small, so anything that only breaks at scale was not seen; forms were opened, not submitted.

- **B** Passing checks read as nonsense: "0 topics nothing points at", "0 sections placed without a score".
- **B** Items are links to somewhere else; nothing can be fixed here.
- **A** It did not notice that the root brief is not a brief (see 46).

## Acceptance criteria
- [ ] a parked section can be placed in a topic from the list, and the placement survives a sync
- [ ] one stale brief can be regenerated without touching any other topic — asserted on what was rewritten
- [ ] every pinned topic and section in the tree is listed with a release action
- [ ] each health item says automation-or-person
- [ ] writer and admin see actions; reader sees the lists only, and forged POSTs are refused
- [ ] driven in a real browser on a tree that has each condition

## Out of scope
New health checks beyond the brief gate of #217. Bulk structural surgery.

## Review log
- 2026-10-03 po: authored from the requirements review and the UI review of the same day, at the user's request.
