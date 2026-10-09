---
id: E021
title: a secret saved after a key rotation is on the new key
priority: high
depends_on: [E012]
requirements: []
---

## Goal
After a rotation the running server still encrypts with the old key, so a
connection or source saved before the restart breaks (`KeyMismatch`) once the
server restarts on the new key: a half-rotated db. hrono must never corrupt it.

## Tickets

### 1 the running server switches to the new key on rotation
Change: a successful rotation (`/admin/rotate-key` and the Access page) swaps
every in-process holder of the key — `app.state.master_key`, `key_id`,
`cipher`, and whatever was handed the cipher at startup — under the write lock.
Done when:
- [ ] rotate, then save a connection secret, restart on the new key: it decrypts
- [ ] a secret saved after rotation is tagged with the new key_id
- [ ] a failed rotation (wrong old key) leaves the running key unchanged
- [ ] the Access page's message still says to restart with the new key
Look at: server/app.py (state setup ~L150-195), crypto/rotate.py,
registry/engine.py:302, server/users.py, server/ui/access.py

## Out of scope
- reading a new key without a restart from env/key file

## Log
- 2026-10-03 po: created from backlog secret-written-between-rotation-and-restart (found gating E012).
- 2026-10-03 po: starting (1 free slot; backend key handling, no overlap with E007/E011/E018; E008/E009/E010/E013 wait on E007's panel files).
- 2026-10-03 dev: round 1 started, worktree .claude/worktrees/E021
- 2026-10-03 dev: T1 committed e611cbe; tests/server/test_rotation_live.py via endpoint+restart; mutations (drop rekey, drop key_id swap) each fail tests. NOTE: tests/crypto/test_rotate.py::test_the_response_says_the_running_server_is_now_blind is stale in name/docstring (hook blocked me reading that file); still passes.
- 2026-10-03 qa: round 1 FAIL at 5575483. Drove API+panel rotation live, save, restart on new key (decrypts, key_id 2); dev's drop-rekey mutation kills; master_key-swap mutation survives. Findings: encrypt outside the write lock still lets an old-key row land after rotation (repro'd); stale blind-server tests in tests/crypto/test_rotate.py; unread app.state.master_key.
- 2026-10-03 po: ruling — finding 2 (stale blind-server tests in tests/crypto/test_rotate.py) deferred to backlog/stale-blind-server-tests.md; the canary hook guards that file and only the user can lift it. Not a gate for E021; do findings 1 and 3.
- 2026-10-03 dev: round 3 fix 0615448: encrypt moved under the write lock in create/replace/delete; race test fails with encrypt outside the lock (mutation run), app.state.master_key removed (nothing left to mutate); finding 2 left per PO ruling.
- 2026-10-03 po: stuck after 3 rounds (in-flight race test fires only for create_item: replace_item/delete_item encrypt-outside-lock mutations survive; app.state.key_id write-only after startup). needs-user: grant one dev round — parametrize the race test over the three writers (DI hook, no frame sniffing), drop app.state.key_id for a startup local? (rec: yes)
- 2026-10-03 po: user answered "yes": one more dev round — parametrize the race test over create/replace/delete (DI hook), drop write-only app.state.key_id. Restarting.
- 2026-10-03 dev: round 1 (extra) fix 16440cd: race test parametrized over create/replace/delete through the db.write seam (no frame sniffing); hoisting encrypt above the lock in each writer is killed by its own case; app.state.key_id dropped for a local. Gate: ruff clean, tests/server rotation+startup, crypto, registry green.
- 2026-10-03 qa: round 1 (extra) FAIL at 16440cd. Drove API rotate/save/replace/restart live (rows on key_id 4, decrypt on new key); replace/delete hoist mutations killed; own mutation (rekey after the rotation's write block) survives; race test monkeypatches db.write instead of injecting it, and its fake state still carries key_id. Findings in verdict.
- round 2 dev: a67e229 swap-before-commit test via injected SeamDb (mutation: rekey outside the lock fails it), race test injects instead of monkeypatching, key_id dropped from fake state; 7 tests pass.
- 2026-10-03 qa: round 2 PASS at a67e229. All 3 earlier findings fixed (SeamDb injected, no monkeypatch, key_id gone from fake state). Ruff clean, 388 affected tests green. Re-ran dev's mutation (rekey after the write block, killed by the swap-before-commit test) and my own (create_item encrypt above the lock, killed by race[create]). Code unchanged since the round-1 live drive.
- 2026-10-03 po: review ACCEPT at a67e229. All 4 Done-when met by qa's live drive (save after rotate decrypts on restart, new key_id, refused rotation swaps nothing, Access/API copy says restart on new key); README, docstring, panel copy updated.
- merged to main at fbc291f (dev, merge mode)
