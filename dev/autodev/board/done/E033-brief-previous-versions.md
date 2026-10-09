---
id: E033
title: a topic's brief keeps its previous versions, and the page shows what changed
priority: low
depends_on: []
requirements: [60]
---

## Goal
A curator can see what a brief said before the last regenerations or hand
rewrites, and what changed, so a bad rewrite is noticed and can be copied back.

## Tickets

### 1 every overwrite keeps the old brief
Change: a migration adds `brief_versions`; `briefs.upsert` (regen and manual
rewrite alike) copies the replaced text with when, model or user, and why
(regen / rewrite). Keep the last 5 per topic, a baked constant.
Done when:
- [ ] a regen and a rewrite each leave the prior text as a version row
- [ ] a 7th overwrite leaves exactly 5 rows, newest kept
- [ ] a first write (no prior brief) adds no row
Look at: src/hrono/summarize/briefs.py:441, src/hrono/db/migrations/

### 2 the topic page lists them with a diff
Change: the topic page gets a collapsed "Previous versions" block: each
version's when/who/why and a line diff against the current brief.
Done when:
- [ ] driven: rewrite a brief by hand, the page shows the old text and the diff
- [ ] a topic with no versions shows no block
Look at: src/hrono/server/ui/nodes.py, templates/node.html

## Out of scope
- restoring a version (that is E034's undo)
- versions of anything but briefs

## Log
- 2026-10-04 po: created from REQUIREMENTS.md 60 (optional; nothing else left to author).
- 2026-10-04 dev: round 1 started in worktree
- 2026-10-04 dev: T1 9c42a21 tests/summarize/test_brief_versions.py; mutations (drop newest-first order, KEEP 6, drop copy, rewrite reason) each fail a test.
- 2026-10-04 dev: T2 af52fd4 test_a_rewritten_brief_shows_the_old_text_and_what_changed drives POST brief then the page; mutation (empty diff) fails. Docs: README topic page paragraph.
- 2026-10-04 qa: pass at af52fd4. Drove hrono serve on a scratch db in Chromium (light, dark, 375px): node with two regens shows 1 kept with a correct diff; hand rewrite through the Edit form gives 2 kept, "rewritten by hand"; a node with one write shows no block; no sideways scroll. Re-ran KEEP_VERSIONS=6 (fails newest-five test); own mutations: swapped why labels and always-render block each fail the page test. 1151 passed on summarize/server/db/tree/export. Followups: backlog/E033-followups.md.
- 2026-10-04 po: accept at af52fd4. Done-whens met per qa; README matches. Minor: "written by by hand" when the replaced version was itself hand-written, prefixed diff lines; see backlog/E033-followups.md.
- merged to main at bd36a48 (rebased, full suite 2322 passed)
