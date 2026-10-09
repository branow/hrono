---
id: 145
title: a domain error carries its own code, so a failure is not always internal-error
priority: medium
size: small
depends_on: [109]
spec_refs: [implementation-notes.md, build-order.md#M11]
---

## Context
#109 gave every job failure a code. It gave them all the SAME code: a
`SyncError`, an `EmbedError` and a `KeyError` all record `internal-error`,
because `errors.as_app_error` has nothing to consult. A client can now branch
on "did it fail", which is what #109 promised, but not on "what kind of
failure", which is what makes an error structured information rather than a
sentence.

This is the surviving half of #053, which is otherwise stale: the
"mapping scattered inside routes" that ticket was written against was removed
incrementally by #027, #048 and #109, and only two catch-and-re-raise sites
remain, both inside the registry ENGINE — one layer, which is where they
belong.

## Description
The op-level domain errors already exist and already carry client-safe wording.
Give them a code and let the boundary read it:

- A `DomainError` base in `hrono/errors.py` (which imports nothing, so every
  package can inherit from it) with a kebab-case `code` class attribute.
- `SyncError`, `SplitError`, `EmbedError`, `ClusterError` (and `TooFewPoints`),
  `LLMError` and `DecryptError` inherit it and declare their code. No other
  change to any of them — they keep their module, their message and their
  meaning.
- `AppError.__init__` takes an optional `code` override, and `as_app_error`
  passes the domain error's code through. Status stays 500: these are failures,
  not client mistakes.
- Anything else still becomes `internal-error` with its type only, exactly as
  #109 left it.

## Acceptance criteria
- [ ] A job failing on each domain error records that error's own kebab-case
      code and its message.
- [ ] A foreign exception (sqlite3, KeyError) still records `internal-error`
      and no driver wording.
- [ ] An `AppError` raised anywhere keeps its own code and status — unchanged.
- [ ] Codes are unique and kebab-case, pinned by a test that walks the
      subclasses rather than listing them by hand.
- [ ] `ruff format`, `ruff check --fix`, `pytest` clean.

## Out of scope
- New HTTP status codes for these: they stay 500.
- Per-provider or per-source-type sub-codes.
- Touching the registry engine's two remaining catch sites.

## Review log
- 2026-09-23 po: authored from #053's triage, which this supersedes in part.

- 2026-09-23 dev: `DomainError` lives in `errors.py` (which imports nothing, so
  every package inherits it without a cycle) and carries only a kebab-case
  `code`. `SyncError`, `SplitError`, `EmbedError`, `ClusterError`,
  `TooFewPoints` and `DecryptError` inherit it; `AppError.__init__` takes an
  optional per-instance `code` so `as_app_error` can relay a domain error's own
  code through `Internal` without inventing an AppError subclass per failure.
  Status stays 500 throughout.

  ONE ERROR IS NOT COVERED: `LLMError` lives in `src/hrono/llm/client.py`,
  which this environment's secret-scanning hook blocks every tool from reading
  or editing (it matches `max_tokens = ...` as an env-style secret assignment —
  a false positive confirmed earlier this session). `LLMError` therefore still
  reports `internal-error`. Filed as #146; it needs the operator to prefix one
  message with the hook's override tag, and is two lines once unblocked.

  Mutations run, all killed:
  - the `DomainError` branch removed from `as_app_error` -> 7 fail.
  - the per-instance `code` override ignored -> 7 fail.
  - `SyncError` reusing `embed-error` -> 3 fail (the uniqueness walk).
  - a code written `SyncError` instead of kebab-case -> 3 fail.

- 2026-09-23 qa: PASSED. Re-ran the override mutation (7 fail) and added one
  dev did not: `TooFewPoints` inheriting `ClusterError`'s code rather than its
  own still passes, by design — the walk deliberately only requires uniqueness
  among DIRECT subclasses of `DomainError`, and the test says so in a comment.
  Correct: a narrowing subclass sharing its parent's code is legitimate.

  Driven live on 8135: `POST /jobs` op=embed with no model -> `embed-error` /
  "no embedding model available"; op=split on an unregistered source ->
  `split-error` / "unknown source: ghost". Two failures a client can now tell
  apart without reading English. Gate clean, 993 passing, commit atomic.

  #146 is the right way to carry the blocked file — the ticket is honest about
  what is not covered rather than quietly claiming it.

- 2026-09-23 po: CLOSED. This is what #109 was for. An operator reading
  `embed-error` knows to register a model; reading `internal-error` they knew
  only that something broke. The `DomainError`/`AppError` split stays as it is:
  a failure inside hrono and a transport answer are different things, and the
  boundary is the one place that should know both.
