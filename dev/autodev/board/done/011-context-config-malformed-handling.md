---
id: 011
title: hrono context handles a malformed config.toml with a clear error
priority: low
size: small
depends_on: [009]
spec_refs: [build-order.md#T5.2]
---

## Context
Spun off from #009 PO review (qa non-blocking find). `~/.hrono/config.toml` is
tool-written, but it is the user's own file and they can hand-edit it. Today
`context.store._read` uses direct key access, so a corrupted or hand-broken
config (missing key, wrong type, invalid TOML) raises a raw `KeyError`/parse
traceback on every subsequent `hrono context` (and later every client) command.
The product bar says the CLI must never dump a stack trace and must give
actionable errors — a malformed config should say so and how to fix it, not
crash. Low priority (requires a hand-edit to trigger) but a real UX gap.

## Description
Make `context.store` fail gracefully when `config.toml` cannot be parsed into the
expected shape. On load, if the file is not valid TOML or does not match the
expected structure (missing/renamed keys, wrong types), raise a typed
`MalformedConfig` error that the `context` command boundary renders as a clear
one-line message naming the file path and the problem, with a non-zero exit —
mirroring the existing `DuplicateContext`/`UnknownContext` -> exit-code mapping
in `commands.py`. Do not attempt auto-repair or silent reset (never discard a
user's file); just report clearly so they can fix or remove it.

Conventions: typed error at the store layer, message rendering at the command
boundary (not baked into the exception); early returns; no traceback to the
user; the token must not appear in the error message.

## Acceptance criteria
- [ ] A `config.toml` that is invalid TOML produces a clear one-line error naming
      the path and "malformed config", non-zero exit, no traceback.
- [ ] A `config.toml` that is valid TOML but missing/renamed required keys or has
      wrong types produces the same clear typed error, not a `KeyError`
      traceback.
- [ ] A well-formed config still loads and all five `context` commands behave
      exactly as before (no regression).
- [ ] The error message never contains any token value.
- [ ] Regression-grade tests write a malformed config (both invalid-TOML and
      valid-TOML-wrong-shape) to a temp `HRONO_HOME` and assert the clear error
      + non-zero exit + absence of a traceback.
- [ ] `ruff format`, `ruff check --fix`, `pytest` all clean; work committed.

## Out of scope
- Auto-repairing or migrating an old config schema.
- Any change to the write path or the config format itself.

## Review log
- 2026-08-15 PO: authored from #009 review (qa non-blocking find). Low/small —
  a robustness gap that only triggers on a hand-edited config, but the product
  bar forbids tracebacks, so it is worth capturing.
- 2026-08-16 dev: picked up (dep 009 in done/), moved to in-progress.
- 2026-08-16 dev: implemented. Added a typed `MalformedConfig(path)` to
  `context/store.py`; `_read` now wraps parse+validate in try/except
  `(TOMLDecodeError, KeyError, TypeError, AttributeError) -> MalformedConfig`,
  and a new `_parse`/`_context` validate the shape (contexts is a dict, each
  table a dict with string server_url/token, current is str|None) so a
  hand-broken file never raises a raw KeyError/parse traceback. The command
  boundary maps it via a shared `_guard(action)` helper (mirrors the existing
  DuplicateContext/UnknownContext -> typer.Exit pattern) wrapping every store
  call in all five commands, printing `Malformed config at <path>: fix or remove
  it.` to stderr + exit 1. No auto-repair/reset (never discards the user's file);
  message never contains the token. Tests: `tests/context/test_malformed.py`
  (invalid-TOML and valid-TOML-wrong-type both -> clean error/exit/no-traceback,
  token-absent-from-error, all five commands report it, well-formed config still
  works). Gate clean (ruff format, ruff check --fix, pytest 212 passed). Verified
  on the real CLI: both malformed shapes print the one-line error + exit 1 with
  no traceback and no token; a good config lists normally. Committed 434cd84.
  Moved to verifying.
- 2026-08-16 qa: PASS -> po-review. Verified all dimensions; this closes the
  #009 review find. The fix adds a typed `MalformedConfig(path)` raised from
  `context.store._read` (wrapping `tomllib.TOMLDecodeError`/`KeyError`/
  `TypeError`/`AttributeError`), with structural validation in `_parse`/
  `_context` (isinstance guards for the contexts table, `current`, and each
  context's `server_url`/`token`/`default_tree`), and a `_guard` helper at the
  command boundary that renders "Malformed config at {path}: fix or remove it."
  on stderr and exits non-zero - mirroring the existing
  DuplicateContext/UnknownContext mapping. Drove the real CLI: an invalid-TOML
  config and a valid-TOML-wrong-shape config (server_url = 42) both produce that
  clean one-line message with exit code 1 across all five commands (list/
  current/use/rm/add), with NO traceback and NO token in the output; a
  well-formed config still loads and lists normally. Confirmed no auto-repair or
  silent reset - the user's file is reported, never discarded. (Note: two exit
  codes in my first drive were shell measurement artifacts on my side - a
  `$(...)` capture reading echo's status and an unquoted `$cmd` word-split;
  re-measured directly, every command exits 1.) Tests are regression-grade:
  parametrized invalid-TOML + wrong-shape (assert clean error, non-zero exit, no
  traceback, not a KeyError), token-never-in-error, every-command-reports, and
  well-formed-no-regression. Code review clean: typed error at the store layer,
  message at the boundary (not baked into the exception), early-return isinstance
  guards, typed, docstrings only, no emojis. Commit 434cd84 is a proper atomic
  Conventional Commit (`fix:`). Re-ran the gate: ruff format clean (78 files),
  ruff check passed, pytest 212 passed.
- 2026-08-16 PO: PASS -> done. Drove the real CLI: an invalid-TOML config and a
  valid-TOML-wrong-shape config (server_url = 42) both produce the clean one-line
  "Malformed config at <path>: fix or remove it." with exit 1, ZERO tracebacks,
  and no token in the output, across the commands; a well-formed config still
  lists normally. Typed `MalformedConfig(path)` raised at the store layer,
  rendered at the command boundary via `_guard` (mirrors Duplicate/Unknown), no
  auto-repair (user's file never discarded). Gate green (78 files, 212 passed,
  covered under commit 434cd84). Closes the #009 review find. Note: when #028
  migrates the CLI onto the AppError layer, fold MalformedConfig/DuplicateContext/
  UnknownContext (the `_guard` path) in too, for one consistent mapping. Closed
  at 434cd84.
