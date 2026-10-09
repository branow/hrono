---
id: 146
title: LLMError still reports internal-error (blocked by a tooling hook)
priority: low
size: small
depends_on: [145]
---

## Context
#145 gave every domain failure its own code except one. `LLMError` is defined
in `src/hrono/llm/client.py`, and this environment's sensitive-canary hook
blocks every tool from reading or writing that file: it matches the token
`max_tokens = ...` as an env-style secret assignment. The finding is a
confirmed false positive — the file holds no credential; it was checked
earlier this session when the same hook flagged the same line.

So every LLM failure still reaches a client as `internal-error` while a sync,
split, embed, cluster or decrypt failure now names itself.

## Description
Two lines, once the file can be opened:
- `class LLMError(DomainError)` instead of `Exception`, importing
  `DomainError` from `hrono.errors`.
- `code = "llm-error"`.

Then extend `tests/jobs/test_domain_codes.py`'s parametrised case list with
`LLMError`, and add `hrono.llm.client` to the imports its uniqueness walk
forces to load.

## Acceptance criteria
- [x] A job failing on `LLMError` records `llm-error` and its own message.
- [x] The uniqueness walk covers it.
- [x] `ruff format`, `ruff check --fix`, `pytest` clean.

## Blocked on
The operator prefixing one message with `[allow-secret]` (or adding
`max_tokens` to the hook's allowlist, which is the better fix — the pattern
will keep firing on that file).

## Review log
- 2026-09-23 dev: filed from #145, which covered every other domain error.

- 2026-09-23 dev: unblocked by the operator's `[allow-secret]`. `LLMError`
  inherits `DomainError` with `code = "llm-error"`, and the parametrised case
  list plus the uniqueness walk in `tests/jobs/test_domain_codes.py` cover it
  like every other domain error. Mutations: the code removed -> 1 fails; the
  code set to `sync-error` -> 2 fail (the case and the uniqueness walk). Gate
  clean, 994 passing.

- 2026-09-23 qa: PASSED. Driven live on 8137: `POST /jobs` op=brief with no
  text model answers `{"code": "llm-error", "message": "no text model
  available", "details": {"type": "LLMError"}}`. Every domain failure hrono can
  raise now names itself; nothing is left reporting `internal-error` except a
  genuinely foreign exception, which is the #109 rule.

- 2026-09-23 po: CLOSED, and #145's series with it. Note for the operator, not
  a ticket: the canary rule that blocked this file matches `max_tokens = 4096`
  as an env-style secret assignment. It will fire again on every edit to
  `llm/client.py`. Allowlisting that identifier in `plexus-rules.json` is the
  fix; nothing in this repo needs changing for it.
