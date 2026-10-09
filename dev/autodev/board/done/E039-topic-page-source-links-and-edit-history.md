---
id: E039
title: the topic page links each section to its file and lists who edited it
priority: medium
depends_on: []
requirements: [29, 62]
---

## Goal
A curator on a topic page can open a section's file in the source repo, and
see every manual edit on the topic with who made it and when — today only the
latest edit's author shows, inside the Undo box.

## Tickets

### 391 a section links to its file in the source repository
Change: a section from a git source (git, github, bitbucket discovery) links to
its file at the synced commit on the host (GitHub/GitLab/Bitbucket blob URL,
line anchor when the section has lines). Unknown host or local path: show the
path as text, no link. Never put credentials from the url in the href.
Done when:
- [ ] github and bitbucket sections link to the exact commit + file (+ lines)
- [ ] an url with `user:token@` yields a link without them
- [ ] a non-git or unknown-host section shows the path, no dead link
Look at: src/hrono/server/ui/nodes.py, templates/node.html, ingest/git_reader.py

### 392 the topic page lists its manual edits with who and when
Change: `edit_log` keeps every edit. New migration adds nullable `closed`
('undone' | 'released'); `_record` stops pruning; `undo` and `release` set
`closed` on the newest row instead of deleting. `latest_edit` offers the
newest row only, and only when `closed` is NULL (plus the no-before rule).
A short "Edits" list on the topic page: kind, who, when, "undone" tag, newest
first (cap ~10, "and N older"). Readers see it; Undo stays writer-only.
Done when:
- [ ] three edits by two users show in order with each author and time
- [ ] a topic with no edits shows nothing (no empty heading)
- [ ] undo, then a second undo finds nothing; release leaves no Undo; rows stay
- [ ] existing undo/release/id-reuse tests still pass
Look at: src/hrono/server/ui/nodes.py (undo block), templates/node.html

## Out of scope
- editing or undoing anything but the newest edit
- links for Confluence/Notion pages (already their own url)

## Log
- 2026-10-04 po: created from REQUIREMENTS 29, 62.
- 2026-10-04 dev: round 1 started.
- 2026-10-04 dev: 391 done in 9c7a182 (tests/ingest/test_blob_link.py, tests/server/test_ui_node.py; mutation: drop the source_type guard, confluence test fails). 392 blocked: edit_log keeps ONE row per topic by design (edits._record prunes older rows, 0040 comment: one step deep), so a list of 3 edits has no data; needs a PO ruling on keeping history.
- 2026-10-04 po: ruled 392 keeps full history (`closed` marker, undo/release mark not delete); REQ 62 says "each" edit.
- 2026-10-04 dev: 392 done in 31b5f83 (migration 0043 closed; tests test_ui_node_edits.py, test_migrations.py driven through the page via TestClient; mutations: latest_edit ignoring closed, release not closing, undo not closing each fail tests).
- 2026-10-04 qa: round 1 FAIL at 31b5f83. Drove hrono serve + playwright on a scratch db: github and bitbucket-discovery links correct, Edits list for reader and admin, undo then second undo, release, cap. Re-ran mutations: latest_edit ignoring closed (4 fail), no cap (1 fail), gitlab one-segment branch (survives, followup). Blocking: release after an undo overwrites closed='undone' with 'released', so the Edits list drops the undone tag (edits.py:217). Followups: backlog/E039-followups.md.
- qa round 2 at c3e16fe: PASS. The round-1 blocker is fixed: _close (src/hrono/edits.py:217) now closes only an open row. Drove rename, undo, release through the real app routes on a migrated db; the row stays 'undone' and the tag still shows. Mutations: dropping the 'AND closed IS NULL' guard fails the new test; skipping release's _close fails test_handing_back_clears_the_undo_so_a_regeneration_stands. Ruff clean; 89 affected tests pass. Followups in backlog/E039-followups.md (added the c3e16fe commit-body line).
- 2026-10-04 po: review ACCEPT at c3e16fe. 391/392 Done-when met per qa drive and tests (creds stripped, closed marker, cap, reader view); README matches. Minor followups in backlog/E039-followups.md.
- merged to main at c3e16fe
