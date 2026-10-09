---
id: 209
title: manage users in the panel — create, revoke, change role
priority: medium
size: medium
depends_on: []
spec_refs: [REQUIREMENTS.md#1 (4, 5), engineering:security]
---

## Context
`/users` and `/admin/rotate-key` exist in the API and the panel has neither. An admin who wants to give a colleague read access needs a terminal.

## Description
An admin-only Access page: list users with role; create a user with a role and show the token once, with a copy control and a plain warning that it will not be shown again; reissue a token; change a role; delete a user, with a confirmation that names the user.

Guard the foot-guns server-side: an admin cannot delete or demote the last admin, including themselves.

Master-key rotation as a confirmed action on the same page, reporting what it re-encrypted. Low priority within the ticket; split it off if it grows.

Tokens never appear in a URL, a log line, or a page reload.

## Acceptance criteria
- [ ] an admin can create, reissue, re-role and delete users from the panel
- [ ] a new token is shown exactly once and survives no reload
- [ ] the last admin cannot be removed or demoted — refused by the server, tested with a forged POST
- [ ] writer and reader cannot see the page or use its routes
- [ ] driven in a real browser: create a reader, sign in as them, confirm read-only

## Out of scope
SSO, password login, per-tree permissions.

## Review log
- 2026-10-03 po: authored from the requirements review and the UI review of the same day, at the user's request.
