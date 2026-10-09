---
id: E012
title: manage users in the panel — create, revoke, change role
priority: medium
depends_on: [E005]
requirements: [4, 5]
---

## Goal
`/users` and `/admin/rotate-key` exist in the API, not the panel; giving a
colleague read access needs a terminal. Detail: archive/209.

## Tickets

### 1 admin Access page
Change: list users; create with role (token shown once, copy, warning);
reissue; re-role; delete with a confirmation naming the user.
Done when:
- [ ] a new token is shown exactly once and survives no reload, URL or log
- [ ] writer/reader cannot see the page or use its routes
- [ ] driven: create a reader, sign in as them, read-only confirmed
Look at: src/hrono/auth/users.py, server/ui/

### 2 the last admin is safe
Done when:
- [ ] deleting or demoting the last admin (self included) is refused by the
  server — tested with a forged POST

### 3 rotate the master key (optional line 5)
Change: confirmed action reporting what it re-encrypted. Drop if it grows.
Look at: src/hrono/admin

## Out of scope
- SSO, per-tree roles

## Log
- 2026-10-03 po: created from #209.
- 2026-10-03 po: starting (1 free slot; new page + auth/users, least overlap with E007's template-wide copy pass; E008/E010/E011 wait on E007 files).
- 2026-10-03 dev: round 1 started, worktree .claude/worktrees/E012.
- 2026-10-03 dev: tickets 1-3 1d4549b; driven in Chromium (create reader, sign in as them: no Access tab, /ui/access 403, token absent from URL and reload); mutations: last-admin guard, demote guard, Admin->Reader on delete route, no-store header, tab gate each fail tests.
- 2026-10-03 qa: round 1 FAIL at 1d4549b — drove create/re-role/reissue/delete/rotate in Chromium plus reader sign-in (403, no tab, forged delete 403); re-ran no-store mutation (killed) and own: reissue/rotate confirm removal (killed), rotated count forced to 0 (SURVIVED). Findings: one commit for three tickets; Access tab unmarked on POST responses; API-created names with / are unmanageable (name rule belongs in auth.users); rotated count untested; /ui/access missing from browser ROUTES.
- 2026-10-03 dev: round 2 at 347bcae; split into f322523 (guard, name rule moved to auth.users), 7022a5e (page, tab pattern), 347bcae (rotation, real secret re-encrypted); /ui/access in browser ROUTES; mutations: rotated rows 0 and tab pattern reverted both fail tests. Soft-reset rewrite of 1d4549b done at qa's request.
- 2026-10-03 qa: round 2 PASS at 347bcae — all five round-1 findings fixed; 636 passed/1 skipped (server, auth, crypto, admin); drove in Chromium: create (Access tab marked at /ui/access/create), a/b refused by POST /users (422) and the panel, rotation with a real seeded connection secret reported '1 secret re-encrypted' and it decrypts under the new key, wrong old key 403, no key in page; mutations: dev's rows->0 (killed), own: name rule allowing leading dot/dash (killed).
- 2026-10-03 po: ACCEPT 347bcae — all Done-when met per qa (token once/no-store, admin-only page+routes, reader driven, last-admin 409 via forged POST and API, rotation reports count); README describes the page.
- merged to main at a3ba650
