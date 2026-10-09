---
id: 151
title: the openai provider — completions, embeddings, and a validated key
priority: high
size: medium
depends_on: [107]
spec_refs: [build-order.md#T44.1, implementation-notes.md]
---

## Context
`connections` has accepted `provider: "openai"` since #015, and nothing can use
it: `llm/providers.py` maps only `anthropic` and `claude-code`, and
`embed/runner.encoder_for` only ever loads a local sentence-transformers model.
A model registered against an openai connection fails at call time — text with
"unsupported provider", embedding by silently trying to load the model NAME
locally.

## Description
- `OpenAIClient`, a `Completion` beside `AnthropicClient`: same protocol, same
  `Usage` counts, one `LLMError` for any transport/auth failure, key resolved
  and decrypted from the model's connection and never logged. Register it in
  `_PROVIDERS`.
- The embedding half: an encoder table keyed by provider, so
  `encoder_for` answers a model with a connection by building a REMOTE encoder
  and one without a connection by loading in process, as today. The openai
  entry posts to `/v1/embeddings` in the model's configured batch size.
- Validation already hits `GET /v1/models` for api-key providers — confirm the
  openai entry is wired and keep it.
- `endpoint` overrides the base url for both halves (a proxy or a gateway),
  which is also what #152 will ride on.

## Acceptance criteria
- [x] A text model on an openai connection completes through `OpenAIClient`,
      and its token counts land in the same place every other provider's do.
- [x] An embedding model on an openai connection embeds over HTTP; one with no
      connection still loads in process.
- [x] An auth failure, a transport failure and a malformed body each surface as
      one `LLMError` carrying no key material.
- [x] Both halves are driven over a real local HTTP round trip (#108).
- [x] `ruff format`, `ruff check --fix`, `pytest` clean.

## Out of scope
- Streaming, tool use, and response-format controls.
- Live verification against api.openai.com.

## Review log
- 2026-09-23 po: authored.

- 2026-09-23 dev: `llm/openai.py` serves both halves — `POST /v1/chat/
  completions` and `POST /v1/embeddings` — over httpx, and `embed/encoders.py`
  is the encoder table the embed op now dispatches through: no connection means
  load in process (the injectable seam keeps its meaning), a connection means
  the provider its connection names.

  DECISION, recorded because it departs from the stack note: this rides httpx,
  not the openai SDK. The whole point of `openai-compatible` (#152) is that
  ollama, vllm and lm-studio speak this REST shape without being openai; httpx
  is already a dependency; and a stub server in a test is then a REAL round
  trip rather than a mocked client object (#108). Two endpoints and a bearer
  header do not justify an SDK, and its retries and defaults would be one more
  thing to reason about when a local server misbehaves.

  The embedding response is re-ordered by its `index` field rather than trusted
  as sent — the API does not promise the response order matches the request's,
  and a silently reordered batch would attach every chunk to its NEIGHBOUR's
  meaning. That is the defect no single-input test can see, so it has a
  two-input test of its own.

  Mutations run, all killed: vectors keeping the response order -> 1 fails; a
  short batch accepted -> 1; the key never sent -> 1; the model's max_tokens
  ignored -> 1; every embedding model loading locally -> 2; a 401 treated as
  any other status -> 1.

- 2026-09-23 qa: PASSED. Re-ran dev's vector-order mutation (1 fail) and added
  one dev did not: input tokens never counted -> 1 fails, so the usage counts
  are pinned in both directions and not just the text.

  The httpx-over-SDK decision is accepted and recorded in the ticket where the
  next reader will find it. It is the right call for this codebase: it makes
  #152's local-server story one code path instead of two, and it is what lets
  every test here be a real round trip on a real socket.

  Not driven against api.openai.com: deferred to the integration pass with the
  rest, at the operator's direction.

- 2026-09-23 po: CLOSED. T44.1 done. An embedding model that names a
  connection now embeds over HTTP instead of silently trying to load the model
  NAME from disk, which was the quiet half of this gap and the one a user would
  have spent an afternoon on.
