---
id: 045
title: bootstrap/reset-token messages should lead with `hrono profile add`, not the raw Bearer header
priority: low
size: small
depends_on: [007, 009, 010, 033]
spec_refs: [implementation-notes.md#auth]
---

## Context
The one-time admin token printed on first `serve` (#007, `_bootstrap_message` in
`src/hrono/cli.py`) tells the user to authenticate with a raw
`Authorization: Bearer <token>` header. That was accurate at commit 118f0d8 —
the CLI client and profiles did not exist yet, so the raw header was the only
usable path. It is now stale: the intended front door is the CLI, and a token is
stored/used via `hrono profile add <name> --server <url> --token <token>`
(`client/http.py`), after which every CLI command sends the Bearer header
itself. There is one credential (the token); Bearer is just its wire format,
shared by the CLI, curl, and any future web UI — so the message should lead with
the CLI path, not the low-level header.

The same stale raw-Bearer text is duplicated in the `admin reset-token` output
(`src/hrono/admin/commands.py:62`).

## Description
Update both messages to lead with the ergonomic CLI path and keep the raw header
as a secondary "or call the API directly" note:
- `_bootstrap_message` (cli.py) and the reset-token message (admin/commands.py):
  primary line = `hrono profile add <name> --server <url> --token <token>`;
  secondary = `Authorization: Bearer <token>` for direct API use.
- Keep the "shown ONCE, stored only as a hash, save it now" warning.
- Do NOT print the token into any profile automatically — it stays a manual,
  explicit step (the token must never be persisted by the mint path).

## Acceptance criteria
- [ ] First-run bootstrap output names `hrono profile add ... --token <token>`
      as the primary way to use the token; raw Bearer header retained as a note.
- [ ] `admin reset-token` output updated the same way (no duplicated stale text).
- [ ] The "shown once / hash-only / save it now" warning is preserved; the token
      is still never persisted by the mint/reset path.
- [ ] Tests asserting message content updated; `ruff format`, `ruff check --fix`,
      `pytest` all clean.

## Out of scope
- Auto-writing the token into a profile on bootstrap (keep it manual/explicit).
- Any web-UI onboarding copy (no web UI yet; it would consume the same token).

## Review log
- 2026-08-22 stakeholder + PO: spotted during review of #007 — message predates
  the profile/HTTP-client (#009/#010) and still points at the raw Bearer header
  instead of `hrono profile add`. Low-pri copy fix across cli.py + admin/commands.py.
- 2026-08-22 PO triage: promoted backlog -> todo. Meets Definition of Ready
  (deps 007/009/010/033 all done, testable criteria, small). Real UX fix per the
  product bar (actionable, discoverable CLI front door); low priority so it does
  not disturb the M3 critical path (040/041 are high).
- 2026-08-22 dev: started. Picked up as the only READY todo ticket (041 blocked
  on 040 which is in verifying). Copy fix across cli.py + admin/commands.py.
- 2026-08-22 dev: DONE, committed b4a9f07, handoff to qa. Both `_bootstrap_message`
  (cli.py) and `_reset_message` (admin/commands.py) now lead with
  `hrono profile add local --server http://127.0.0.1:8080 --token <token>`
  (serve's default host:port), keep `Authorization: Bearer <token>` as a secondary
  "or call the API directly" note, and preserve the "shown ONCE / hash-only /
  save it now" warning. No token is persisted by the mint/reset path — this is a
  message-string change only. Tests updated to assert both the CLI path and the
  Bearer note (test_cli.py, test_reset_token.py). Verified: gate clean (ruff
  format/check, pytest 388 passed / 1 skip); rendered both messages from the real
  functions to confirm the copy.
- 2026-08-22 qa: PASS -> po-review. Verified every dimension:
  - Acceptance criteria all met. Rendered `_bootstrap_message` and
    `_reset_message` from the real functions: both lead with `hrono profile add
    local --server http://127.0.0.1:8080 --token <token>` (primary), keep
    `Authorization: Bearer <token>` as a secondary "or call the API directly"
    note, and preserve "shown ONCE / stored only as a hash / Save it now". No
    duplicated stale raw-Bearer text remains in either.
  - Security: string-only change (diff touches message text + tests only); the
    mint/reset path still never persists the token, and the profile-add line
    uses a `<token>` placeholder rather than echoing the secret a second time.
  - Tests regression-grade: test_cli.py and test_reset_token.py now assert BOTH
    `hrono profile add` and `Bearer`, so reverting the copy fails them.
  - Commit b4a9f07 is atomic and a clean Conventional Commit (`fix:`, lowercase,
    one sentence, no body, no attribution).
  - Gate: `ruff format --check` and `ruff check` clean; 045's targeted tests
    pass; full suite is green (386 passed / 1 skip) once the two #040 cluster
    worker tests are excluded. NOTE: a bare `uv run pytest` can still SIGSEGV
    intermittently, but that is #040's already-bounced defect (worker tests
    missing `worker.join()`), NOT this ticket — #040 is back in todo/in-progress
    and tracked separately. 045 introduces no flakiness of its own.
- 2026-08-22 PO review: PASS -> done. Independently re-verified rather than
  trusting the log: rendered both functions (`_bootstrap_message`,
  `_reset_message`) — each leads with `hrono profile add local --server
  http://127.0.0.1:8080 --token <token>` (primary), keeps `Authorization: Bearer
  <token>` as a secondary "or call the API directly" note, and preserves "shown
  ONCE / stored only as a hash / Save it now". Diff (b4a9f07) is isolated to the
  two message strings + their tests; the mint/reset path persists no token and
  the profile-add line uses a `<token>` placeholder rather than echoing the
  secret a second time — the right call. Ran the gate on 045's files: `ruff
  format --check` + `ruff check` clean, 13 targeted tests pass. All four
  acceptance criteria truly met; matches the product bar (discoverable CLI front
  door, actionable). No adjacent follow-up work found. Closed.
