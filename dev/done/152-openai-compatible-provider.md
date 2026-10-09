---
id: 152
title: the openai-compatible provider — a local server at a declared endpoint
priority: medium
size: small
depends_on: [151]
spec_refs: [build-order.md#T44.3, implementation-notes.md]
---

## Context
The spec's third api-key provider is "openai-compatible (local LLM servers:
ollama/vllm/lm-studio; endpoint set, auth usually `{"method":"none"}`)". Once
#151 exists, this is the same wire protocol with two differences: the endpoint
is REQUIRED, and there may be no key at all.

## Description
- Register `openai-compatible` in `_PROVIDERS` and in the encoder table,
  reusing #151's client with the connection's `endpoint` and an optional key.
- Validation: `GET <endpoint>/v1/models` answers 200. A local server that is
  not running must fail the write with a reachability message, not a traceback.
- An `openai-compatible` connection with no `endpoint` is already rejected by
  its model (the field is required); confirm with a test rather than assuming.

## Acceptance criteria
- [x] A text model on an `openai-compatible` connection completes against a
      local server, key or no key.
- [x] An embedding model on one embeds against the same server.
- [ ] Registering one whose endpoint refuses the connection fails the write
      with a clear message.  **NOT DONE — see #153.**
- [x] Driven over a real local HTTP round trip (#108).
- [x] `ruff format`, `ruff check --fix`, `pytest` clean.

## Out of scope
Provider-specific quirks (ollama's native API, vllm extensions).

## Review log
- 2026-09-23 po: authored.

- 2026-09-23 dev: the client half is done and driven against a real local
  server: a completion and an embedding with NO key at all (the usual case for
  ollama/vllm/lm-studio), the endpoint honoured rather than api.openai.com, a
  dead port surfacing as one `LLMError`, and the model rejecting a connection
  that declares no endpoint.

  One thing the ticket did not anticipate: an endpoint may or may not already
  end in `/v1`. Ollama's own docs give `http://localhost:11434/v1` while a
  proxy is usually a bare host, so appending `/v1` unconditionally would post
  to `/v1/v1/chat/completions` for half of all users. Both spellings now reach
  the same place, with a test that drives both.

  THE VALIDATION CRITERION IS NOT MET, and I am not claiming it. I wrote it —
  a per-provider default runner (anthropic authenticates with `x-api-key`, the
  openai-shaped ones with a bearer header) plus `_validate_openai` and
  `_validate_openai_compatible` — and it turned two existing tests red, because
  they register `openai` and `openai-compatible` connections with no server
  running and expect 201. Those tests are RIGHT to change and I cannot change
  them: `tests/registry/test_connections.py` and
  `tests/registry/test_connection_validation.py` are both blocked from every
  tool by the sensitive-canary hook (they hold obviously-fake api keys in their
  fixtures). Rather than ship half-validation or a red suite, I reverted that
  file and filed #153.

  Mutations run, all killed: `/v1` appended unconditionally -> 3 fail; a
  keyless connection refused -> 5; the endpoint ignored -> 11.

- 2026-09-23 qa: PASSED ON WHAT IT SHIPPED, with its third criterion correctly
  left unticked and carried to #153. Re-ran dev's endpoint-ignored mutation
  (11 fail across the batch).

  The `/v1` handling is the kind of detail that decides whether a feature works
  for real users: ollama's own documentation gives `http://localhost:11434/v1`,
  and half of all local-server users would have posted to `/v1/v1/...`. Dev
  found it by driving a real server rather than asserting a url, which is the
  argument for #108 in one line.

  On the blocked files: this is the third ticket stopped by the canary hook
  (#146, #153, and this). The tickets are honest about it and nothing was
  faked, but the operator should allowlist the fixture pattern — the cost is
  now a ticket per encounter.

- 2026-09-23 po: CLOSED on its client half; the validation criterion moves to
  #153 with its reason recorded. I am closing rather than holding because what
  shipped is complete and useful on its own — a local model server works end to
  end today — and the missing piece is a write-time check, not a runtime one.

  T44 is now done except that check: anthropic, claude-code, openai and
  openai-compatible all serve completions, and the two openai-shaped ones serve
  embeddings.
