---
id: 046
title: optional OS-keychain backend for the profile token, with the 0600 file as fallback
priority: medium
size: medium
depends_on: [009, 036, 037]
spec_refs: [implementation-notes.md#auth]
---

## Context
The CLI profile token is persisted in plaintext in the profiles TOML file,
protected by filesystem permissions only — file `0600`, directory `0700`
(`src/hrono/profile/store.py`). This is the standard CLI baseline (gh, aws,
kubectl, docker all keep credentials in a 0600 file), so it is NOT a defect.
Raised during review: could we store the token in the OS keychain (macOS
Keychain / Linux Secret Service / Windows Credential Manager) so it is encrypted
at rest and unlocked by the OS login, like polished CLIs offer?

Threat model (why this matters and when): two deployment shapes.
- DEDICATED/isolated host (the server box that runs `hrono serve`, a CI runner):
  the whole machine exists for this, few other processes, the 0600 file is fine.
- END-USER WORKSTATION: the user runs the CLI from their own account alongside
  many other agents/LLMs/tools. Any process running AS THE SAME USER can read a
  0600 file silently — no prompt, no barrier. This is the case that motivates a
  keychain, and it is increasingly common as users run many local agents.

Honest limit (set expectations, do not oversell): a keychain RAISES the bar but
does not fully close the same-uid hole. Once the login keychain / Secret Service
is unlocked, same-user processes can often still read items — macOS mitigates
with per-app ACLs tied to code signing; Linux Secret Service does not once
unlocked. Net gain: encrypted at rest + an access prompt + (macOS) app-scoped
ACLs — meaningfully better than a silently-readable plaintext file, not a hard
wall against a malicious same-user process.

## Description
Add an OPTIONAL keychain-backed secret store for the profile token, selected at
runtime, with the current 0600 file as the default fallback — never a hard
replacement:
- Introduce a small secret-backend seam (get/set/delete token by profile name).
  Two implementations: the existing TOML file (default), and a `keyring`-based
  OS-keychain backend (opt-in, e.g. an install extra like `hrono[keyring]`).
- Backend is SELECTABLE by the user: a flag / config setting (e.g.
  `--token-store keychain|file`, persisted per install) so an end user opts into
  the keychain while a dedicated host keeps the file. Document the same-uid limit
  above so the choice is informed.
- When the keychain backend is active, the TOML holds only `server_url` /
  `default_tree` and the token lives in the keychain keyed by profile name.
- MUST fall back to the file backend when no keychain is available (headless /
  CI / SSH session with no Secret Service) — detect and degrade, do not crash.
- Keep the 0600/0700 perms on the file backend unchanged.

## Acceptance criteria
- [ ] A backend seam exists; token read/write goes through it, not directly to
      the TOML, in the client path.
- [ ] Default behavior is unchanged (0600 file) with no extra installed.
- [ ] With the keyring extra + an available keychain, the token is stored in the
      OS keychain and absent from the TOML file on disk.
- [ ] On a host with no keychain, the client degrades to the file backend
      cleanly (no traceback), and this is covered by a test.
- [ ] `keyring` is an opt-in extra, not a base dependency.
- [ ] `ruff format`, `ruff check --fix`, `pytest` all clean.

## Out of scope
- Encrypting the server-side DB secrets differently — this is the CLIENT token
  only (server secrets already use Fernet + master key).
- A password/passphrase-locked file backend (keychain covers the encrypted case;
  the plain file stays the simple default).

## Review log
- 2026-08-22 stakeholder + PO: raised while reviewing the Fernet cipher. Current
  0600-file storage is the accepted CLI baseline, so this is an enhancement, not
  a fix. Scoped as an optional keyring backend with mandatory file fallback for
  headless. Low priority.
- 2026-08-22 stakeholder + PO: bumped low -> medium. Threat model added: the
  end-user-workstation case (same-uid processes read the 0600 file silently)
  motivates a user-selectable keychain backend. Trigger to pull into todo: when
  hrono is distributed to end-user workstations (vs dedicated `serve` hosts).
  Recorded the honest same-uid limit so we do not oversell the keychain.
