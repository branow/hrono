---
id: 036
title: Rename client "context" to "profile" across CLI, code, config, and spec
priority: medium
size: medium
depends_on: [009, 010]
spec_refs: [implementation-notes.md, admin-recovery-and-reset, rename-context-to-profile]
---

## Context
Promoted from a stakeholder backlog request. The client connection profiles are
called "context" today (`src/hrono/context/`, `hrono context add|use|list|
current|rm`, `[contexts]` in `config.toml`). "Context" is overloaded in an AI
knowledge-base product - the LLM context fed to an agent, the knowledge tree, the
dashboard's context/tree switcher - so a saved server+token is clearer as a
**profile** (AWS-CLI style). This reverses a settled spec choice (context matched
kubectl/gh), so it is a deliberate PO decision, not an ad-hoc edit. Do it NOW,
while only #009/#010 use the name, before M5 builds more client subcommands on it
(much cheaper to rename now than later). Independent of the M2/M3 backend chain.

Settled by PO (open questions from the request):
- The `config.toml` table IS renamed `[contexts]` -> `[profiles]` (full
  consistency; no installed base pre-release, so the breaking change is moot).
- One atomic rename/commit - never leave the codebase half-renamed.

## Description
Rename the client-profile concept from "context" to "profile" everywhere it means
a saved server+token, and NOWHERE else. Do NOT touch unrelated uses of the word
"context" (LLM context, knowledge tree, `ValidationContext`, jobs, etc.).

- **CLI**: command group `hrono profile add|use|list|current|rm` - same
  behavior, options, and output as the old commands (just renamed).
- **Code**: `src/hrono/context/` -> `src/hrono/profile/`; `Context` -> `Profile`,
  `State`/store internals renamed consistently; the config path helper and env
  override (`HRONO_HOME` stays) unchanged in behavior. Carry through the typed
  errors added since #009: `DuplicateContext`/`UnknownContext`/`MalformedConfig`
  -> `DuplicateProfile`/`UnknownProfile`/`MalformedConfig` (or Profile-scoped
  names), keeping their #028 `AppError` mapping + exact messages (adjust "context"
  -> "profile" in the message text).
- **Client**: `client/http.py`'s `from_context()` / `NoContext` -> `from_profile()`
  / `NoProfile`, same behavior; any `#010` message text "context" -> "profile".
- **Config file**: `[contexts]` table -> `[profiles]`; `current` pointer
  unchanged in shape.
- **Tests**: move/rename `tests/context/` -> `tests/profile/`; update assertions
  to the new command/message text.
- **Spec reconciliation**: update `implementation-notes.md` (external spec repo)
  to say "profile", keeping a one-line "(kubectl/gh call this a context)" note;
  scan the other spec/docs for the client-"context" term and update consistently.
  If touching the external repo is out of the dev's lane, flag it and PO will
  reconcile the spec - but the code/CLI/config/tests rename is in scope here.

## Acceptance criteria
- [ ] No client-profile feature is named "context" in CLI help, code
      identifiers, config keys, or messages - it is "profile" throughout; the
      package is `src/hrono/profile/`.
- [ ] `hrono profile add|use|list|current|rm` behave EXACTLY as the old `context`
      commands did (round-trip add/list/use/current/rm, current-marking,
      duplicate/unknown errors, malformed-config error, token never printed,
      0600 file) - verified by the moved tests.
- [ ] `config.toml` uses `[profiles]`; a profile round-trips through the renamed
      store; the token-at-rest 0600 posture is unchanged.
- [ ] The #010 client resolves the current profile (`from_profile`/`NoProfile`)
      and maps errors as before, now via the renamed types.
- [ ] Unrelated uses of "context" are UNTOUCHED (grep: `ValidationContext`,
      JobContext, LLM/tree context, etc. still present and unchanged).
- [ ] Spec term reconciled (implementation-notes.md says "profile" with the
      kubectl/gh note) - or flagged for PO if the external repo is out of lane.
- [ ] `ruff format`, `ruff check --fix`, `pytest` all clean; work committed as
      ONE atomic rename commit (no half-renamed state).

## Out of scope
- Any behavior change - this is purely a rename.
- New profile fields or commands.
- Renaming unrelated "context" concepts.

## Review log
- 2026-08-16 PO: triaged from the stakeholder `rename-context-to-profile`
  request. Medium priority (independent of the M2/M3 critical path, but land it
  before M5 client subcommands multiply the name). Settled: rename the config
  table too, one atomic commit. Must carry through #011's MalformedConfig and
  #028's AppError-mapped context errors. Flagged the external-spec update as a
  possible PO reconciliation if outside dev's lane.

## dev — 2026-08-16

Atomic rename of the client-profile concept "context" -> "profile" (one commit,
no half-renamed state), touching ONLY the saved-server+token feature.

- Package: `src/hrono/context/` -> `src/hrono/profile/` (git mv, history kept).
  `Context` -> `Profile`; `State.contexts` -> `State.profiles`; store methods
  `contexts()` -> `profiles()`, `_add/_use/_remove/_parse/_profile` renamed;
  `DuplicateContext`/`UnknownContext` -> `DuplicateProfile`/`UnknownProfile`
  (kept `MalformedConfig`), preserving their #028 AppError mapping and adjusting
  message text ("Context '..' already exists." -> "Profile ...", etc.).
- Config: `[contexts]` table -> `[profiles]`; `current` pointer shape unchanged;
  filename stays config.toml; HRONO_HOME + 0600/0700 posture unchanged.
- CLI: `hrono context ...` -> `hrono profile add|use|list|current|rm`, same
  behavior/options/output (wording "context" -> "profile"); cli.py add_typer
  name="profile".
- Client (#010): `from_context`/`NoContext` -> `from_profile`/`NoProfile`; message
  text "context" -> "profile".
- Tests: `tests/context/` -> `tests/profile/`; client test updated.

Untouched (verified by grep): `ValidationContext`, `JobContext`,
contextlib/asynccontextmanager, and all LLM/tree "context" uses.

Verified on the real binary: `hrono profile` group present (context gone);
add/list/use/current/rm round-trip; config.toml shows `[profiles.*]` + `current`
at 0600; duplicate -> "Profile '..' already exists." exit 1; unknown -> "Unknown
profile '..'." exit 1; current-clear on rm. Gate clean: ruff format/check, pytest
342. Commit f7be76e.

Spec reconciliation: implementation-notes.md lives in the external spec repo
(the design record, then kept outside this repo) — OUT OF THIS REPO/dev lane. FLAGGING for PO to
update the spec term to "profile" (with a "(kubectl/gh call this a context)"
note). Code/CLI/config/tests rename is complete here.

## qa — 2026-08-16 — PASS -> po-review

Re-ran the gate MYSELF: `ruff format --check` + `ruff check` clean, `pytest` 342
passed. Then drove the real binary (fresh `HRONO_HOME`), not on dev's word:

- CLI group renamed: `hrono profile add|use|list|current|rm` all present;
  `hrono context` is gone. Round-trip: add prod (first -> current) + dev; `list`
  marks current (`* prod`) and prints only name+server (NO token); `use dev` then
  `current` shows `dev <url> (token set)` — token masked, never revealed.
- Config: `config.toml` at 0600 (`-rw-------`) with `[profiles.prod]` /
  `[profiles.dev]` tables and `current = "dev"` — the `[contexts]` table is
  renamed as PO settled. (Client config stores the token in plaintext at 0600, as
  it did pre-rename in #009 — the Fernet boundary is the server DB, not client
  config; unchanged behavior, not a regression.)
- Errors carried through with reworded text + correct exit: duplicate -> exit 1
  "Profile 'prod' already exists."; unknown use -> exit 1 "Unknown profile
  'ghost'."; MalformedConfig -> exit 1 "Malformed config at <path>: fix or remove
  it." rm of the current profile clears the pointer.
- SECURITY: a token-BEARING malformed config still does NOT leak the token in the
  error (grep of stderr clean; message is the generic MalformedConfig line).
- #010 client: `from_profile()` resolves the current profile into a `Client`
  pointed at the configured server carrying the token; `NoProfile` raises cleanly
  when unconfigured (mapped at the #028 boundary).
- Grep audit: only "context" left in profile/client/cli is the intentional
  `(kubectl/gh call this a context.)` doc-note the ticket asked for;
  `JobContext`/`ValidationContext`/contextlib and all LLM/tree uses UNTOUCHED;
  `src/hrono/context/` removed; no `from_context`/`NoContext`/`DuplicateContext`/
  `UnknownContext` remain in src. One atomic rename commit (f7be76e).

Open item for PO (not a blocker — ticket explicitly permits flagging): the
external-spec `implementation-notes.md` term update is out of dev's lane and is
flagged above; PO to reconcile "context" -> "profile" (keeping the kubectl/gh
note) in the design record. All in-repo ACs met.
- 2026-08-16 PO: PASS -> done. Verified the rename is a clean, atomic,
  behavior-preserving refactor. Grep audit: `src/hrono/profile/` exists,
  `context/` gone; no client-profile "context" terms left in src (hrono context /
  DuplicateContext / UnknownContext / from_context / NoContext / [contexts] all
  absent); unrelated `ValidationContext`/`JobContext`/contextlib/LLM-tree uses
  UNTOUCHED. qa drove the real binary: `hrono profile add|use|list|current|rm`
  work as before, config.toml uses `[profiles.*]` at 0600, errors reworded
  (Profile already exists / Unknown profile / MalformedConfig) with correct
  exits, a token-bearing malformed config does NOT leak the token, #010 client
  uses from_profile/NoProfile. Gate 342 passed. Spec reconciliation (the one
  flagged open item, out of dev's lane): PO updated
  the design record's implementation-notes.md - section is now
  "Profiles (kubectl/gh call this a context)", commands + `[profiles]` table +
  "current profile", with a note on why it was renamed. Spec and code now agree.
  Closed at f7be76e.
