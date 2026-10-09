---
id: 009
title: CLI context store (config.toml — add/list/use/current/rm)
priority: medium
size: medium
depends_on: []
spec_refs: [build-order.md#T5.2, implementation-notes.md#cli-contexts]
---

## Context
Every client subcommand (`recall`, `sources`, `tree`, ...) needs to know which
server to talk to and with what token. The spec models this as named
**contexts** the user switches between, stored in `~/.hrono/config.toml`. This
ticket builds that store and its `hrono context` commands. It unblocks the HTTP
client wrapper (#010), which reads the current context to target requests.
Independent of the M0 auth/DB chain, so it parallelizes with #008/#006. Authored
ahead to keep dev's queue stocked as the T3/T4 slice closes.

## Description
A context is `{name, server_url, token, default_tree?}`. Persist a table of them
plus which one is current in `~/.hrono/config.toml` (TOML per the spec). Reading
TOML is stdlib (`tomllib`); TOML has no stdlib writer, so add `tomli-w` (small,
matches the spec's TOML choice) or justify an alternative with
`engineering:developer` — do not hand-roll a TOML serializer. This file holds a
bearer token, so create it with owner-only permissions (`0600`) and its parent
dir `0700`. Load `engineering:security` for the token-at-rest handling.

Add a `context` command group to the existing Typer app:
- `hrono context add <name> --server <url> --token <t> [--default-tree <t>]` —
  register a profile; error clearly if `<name>` already exists (do not silently
  overwrite). The first context added becomes current.
- `hrono context list` — list all, clearly marking the current one; a clear
  "no contexts yet" line when empty.
- `hrono context use <name>` — switch current; error if `<name>` is unknown.
- `hrono context current` — print the current context (name + server_url, and
  that a token is set — never print the token itself); clear message when none.
- `hrono context rm <name>` — remove it; error if unknown; if it was current,
  clear the current pointer (and say so).

Provide a small module (recommend `src/hrono/cli/contexts.py` or
`src/hrono/context/store.py`) with pure-ish load/save/CRUD over a **injectable
config path** so tests never touch the real `~/.hrono`: resolve the config
location from an env override (recommend `HRONO_HOME`, default `~/.hrono`) so a
test points it at a temp dir. DI over monkeypatching the home dir.

Conventions: kebab-case command names; frozen/immutable context model; typed
params; early returns; never print the token; secret file is `0600`; minimum
surface (only the five commands above, no export/import knobs).

## Acceptance criteria
- [ ] `hrono context add` writes `~/.hrono/config.toml` (at the injected
      location) with the context's name, server_url, token, and optional
      default_tree; the file is created mode `0600`.
- [ ] The first `add` becomes current; a second `add` does not change current;
      `add` of an existing name errors without overwriting.
- [ ] `context list` shows every context and marks exactly the current one;
      empty store prints a clear "no contexts" message, not a crash.
- [ ] `context use <name>` switches current and persists it; `use`/`rm` of an
      unknown name exits non-zero with a clear message.
- [ ] `context current` prints the current context without ever revealing the
      token; prints a clear message when there is no current context.
- [ ] `context rm` removes the context; removing the current one clears the
      current pointer and reports it.
- [ ] The token is never printed by any `context` command and never logged.
- [ ] Regression-grade tests drive the Typer commands against a temp
      `HRONO_HOME`: round-trip add/list/use/current/rm, current-marking,
      duplicate-add rejection, unknown-name errors, empty-store messages, and
      the `0600` file mode. A test fails if the token leaks to output or the
      file mode regresses.
- [ ] `ruff format`, `ruff check --fix`, `pytest` all clean; work committed.

## Out of scope
- The HTTP client wrapper that consumes the current context (#010).
- Any command that actually calls the server (`recall`, `sources`, ...).
- Encrypting the token at rest (client-side config parity with `~/.netrc`/
  `~/.aws/credentials` is `0600` plaintext; server-side secrets are the Fernet
  path, out of scope here).

## Review log
- 2026-08-15 PO: authored and moved to todo. T5.2 context store; independent of
  the auth chain so it parallelizes. Flagged the TOML-writer dependency and the
  0600 token-file handling for dev to resolve with engineering:developer/
  security.
- 2026-08-15 dev: picked up (no deps), moved to in-progress. Added `tomli-w`
  (1.2.0) for TOML writing (tomllib reads); did not hand-roll a serializer.
- 2026-08-15 dev: implemented. New `context` package:
  `src/hrono/context/store.py` — frozen `Context(name, server_url, token,
  default_tree?)` and `State(contexts, current)`; `config_path()` resolves
  `HRONO_HOME` (default `~/.hrono`)/config.toml; a `Store` over an injectable
  path with `contexts/current/add/use/remove`, pure transforms (`_add` raises
  `DuplicateContext` and makes the first context current; `_use`/`_remove` raise
  `UnknownContext`; remove reports whether it cleared the current pointer); and
  `_write` that creates the parent `0700` and the file `0600` (os.open with mode
  + chmod). `src/hrono/context/commands.py` — the `hrono context`
  add/list/use/current/rm Typer group (registered in cli.py) that never prints
  the token (`current` shows `name url (token set)`), with clear empty-store and
  no-current messages and non-zero exits on duplicate/unknown. Tests:
  `tests/context/test_store.py` (round-trip all fields, first-becomes-current,
  duplicate/unknown errors, use/remove semantics, current-clear on removing
  current, 0600 file + 0700 dir, empty store) and `tests/context/test_commands.py`
  driving the Typer commands against a temp `HRONO_HOME` (add/list/use/current/rm,
  current-marking, duplicate/unknown-name exits, empty messages, and
  token-never-leaks across list/current/use). Gate clean (ruff format, ruff
  check --fix, pytest 107 passed). Drove the real CLI end-to-end: empty message,
  add, `*`-marked current, duplicate error (exit 1), token-free `current`, use,
  rm-current clears pointer, unknown rm error (exit 1); confirmed config.toml is
  mode 600. Token is plaintext in the 0600 file by design (client parity with
  ~/.netrc; encrypting it is out of scope) and never in command output.
  Committed 973cee9. Moved to verifying for qa.
- 2026-08-15 qa: PASS -> po-review. Verified all dimensions (security +
  developer lenses). Drove the real `hrono context` CLI against a temp
  HRONO_HOME: first `add` becomes current, second does not change it, `list`
  marks exactly the current one with `*`, `current` prints name+server_url and
  "(token set)" with no token, `use` switches and persists, duplicate `add`
  exits 1 without overwriting (server_url unchanged), unknown `use`/`rm` exit 1
  with clear messages, and `rm` of the current context clears the pointer and
  reports it (subsequent `current` says none). Confirmed the real file is
  `-rw------- (0600)` under a `drwx------ (0700)` dir, the token is persisted in
  that file (by design, client parity with ~/.netrc; encryption correctly out
  of scope) and never appears in list/current/use output. Architecture is clean
  and correct: a pure functional core (`_add`/`_use`/`_remove` over an immutable
  `State`), a `Store` that owns IO over an injectable path (HRONO_HOME so tests
  never touch real ~/.hrono), and `commands.py` as the boundary mapping
  structured typed errors (`DuplicateContext`/`UnknownContext`, name on an
  attribute not baked into the message) to exit codes. `_write` creates the file
  0600 via `os.open` and re-chmods, and forces the parent 0700. Dependency
  `tomli-w>=1.0,<2.0` (resolved 1.2.0, well-aged, 7KB) is the spec's TOML
  writer, reads via stdlib `tomllib`, not hand-rolled. Tests are regression-
  grade at both the store and command layers and cover every criterion,
  including the 0600 file mode and a token-never-leaks assertion. Minor
  non-blocking note: `_read` uses direct key access, so a hand-corrupted config
  would raise a KeyError traceback -- out of scope here (config is tool-written,
  within-repo trust; the ticket's error surface is duplicate/unknown/empty, all
  handled cleanly), not filing. Code review clean: frozen models, early returns,
  typed, docstrings only, no emojis, minimum surface (five commands). Commit
  973cee9 is a proper atomic Conventional Commit; uv.lock updated for the dep.
  Re-ran the gate: ruff format clean (41 files), ruff check passed, pytest 107
  passed.
- 2026-08-15 PO: PASS -> done. Drove the real `hrono context` CLI against a temp
  HRONO_HOME and confirmed the security-critical claims with my own eyes: config
  file is 0600 under a 0700 dir; `current` prints "name url (token set)" with
  ZERO token in output; token persists in the 0600 file by design (client parity
  with ~/.netrc, encryption correctly out of scope). Also verified first-add-
  becomes-current, `*`-marked list, duplicate-add -> exit 1 no overwrite, rm of
  current clears the pointer and says so, unknown use/rm -> exit 1 with clear
  messages. Clean functional core (immutable State + pure _add/_use/_remove),
  Store owning IO over an injectable path, commands.py mapping typed errors to
  exit codes; `tomli-w` is the spec's TOML writer (reads via stdlib tomllib).
  Ran the gate: ruff format (41 clean), ruff check clean, pytest 107 passed.
  Unblocks #010. Closed at 973cee9. Spun off #011 for qa's non-blocking find:
  a hand-corrupted config.toml currently raises a KeyError traceback in `_read`.
