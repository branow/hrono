---
id: E045
title: polish — source links say which hosts link; no repo-less gitlab link
priority: medium
depends_on: [E039]
requirements: []
---

## Goal
Apply every E039 followup: the README promises links only where they exist, a
link is never built without a repo, and the edit-history tests stop reaching
into a private helper.

## Tickets

### 451 README names the hosts that link (user-facing)
Change: README.md:112 says a section from a repo "on github.com, gitlab.com or
bitbucket.org" links to its file; a self-hosted instance shows the path alone.
Done when:
- [ ] the sentence matches `_BLOB` in src/hrono/ingest/blob_link.py
Look at: README.md:112

### 452 a one-segment gitlab.com instance never gives a repo-less link
Change: drop the `host != "gitlab.com"` exception (no gitlab discovery exists)
or return None for `gitlab.com/<owner>`; pin it with a test that fails on the
mutation `if "/" not in rest:`.
Done when:
- [ ] `gitlab.com/<owner>` + path yields no link or a link with a repo, tested
Look at: src/hrono/ingest/blob_link.py:33, tests/ingest/test_blob_link.py

### 453 edit-history tests do not import the private `_when`
Change: assert on the stored made_at formatted as the page shows it, or make
`_when` a public helper the page and tests share.
Done when:
- [ ] no test imports `_when`; the stamp assertions still fail on a wrong time
Look at: tests/server/test_ui_node_edits.py:27, src/hrono/server/ui/nodes.py

## Out of scope
- rewording c3e16fe / 31b5f83: merged on main, history is not rewritten

## Log
- 2026-10-04 po: created from E039-followups (user: apply all suggestions).
- 2026-10-04 dev: 451/452/453 committed on epic/E045; blob_link and edit tests pass; mutations (drop guard, stamp slice) fail tests.
- 2026-10-04 qa: pass at ddbef14; ruff clean, blob_link + ui_node_edits + ui_node tests pass (86); README line matches _BLOB; mutations re-run: guard→if False (5 fail), restored gitlab exception (2 fail), stamp [:16]→[:10] (1 fail), nodes._when clock[:5]→[:2] (1 fail); no followups.
- 2026-10-04 po: accept at ddbef14; README matches _BLOB, gitlab.com/<owner> links only with a repo (tested both ways), no test imports _when.
- merged to main at ddbef14 (ff-only, full suite green)
