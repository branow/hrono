---
id: 057
title: Anthropic text-completion client — the LLM call seam for M4 ops
priority: high
size: medium
depends_on: [016, 018, 004]
spec_refs: [build-order.md#T20, implementation-notes.md, design-sketch-v1.md, summarization-experiments.md]
---

## Context
Spun off from T20 (`condense`) PO authoring. Every M4 op that summarizes
(`condense`, `brief`, `brief-upper`, and later the `judge` cascade) needs to call
the LLM and get back text + token usage. Today the codebase has only connection
*validation* (`registry/connection_validation.py`, a lightweight ping) — there is
NO reusable completion client. `condense` is the first op that makes a real LLM
call, so the call seam must exist before it. This ticket builds that seam once so
`condense`/`brief`/`judge` are thin callers, mirroring how `embed/model.py`
centralizes embedding-model resolution.

## Description
A minimal, injectable text-completion client over the `anthropic` SDK:
- Input: a resolved `text`-kind model config (#018 `Model`: its `connection`,
  the provider `model` id, and `params`), a system/prompt string, and the user
  content to summarize. Output: `(text, usage)` where `usage` carries at least
  `input_tokens` and `output_tokens`.
- Resolve + decrypt the provider credential from the referenced `connection`
  (anthropic api key, Fernet-encrypted at rest, #004 cipher). The client is given
  the cipher — do NOT read plaintext secrets any other way, and never log/return
  the key. OPEN QUESTION for dev: the job `JobContext` does not currently expose
  the cipher (embed/cluster needed no secret). Thread the cipher into the op
  context (or pass it to the client from the op) — pick the smaller change and
  note it; this is the first job op that needs a decrypted secret.
- A `Completion` protocol/type is the injection seam: the real client wraps the
  SDK; ops depend on the protocol so tests inject a fake (no network, no tokens).
- Errors: any SDK/transport/auth failure surfaces as one clean domain error
  (e.g. `LLMError`) that a job leaf can fail on — never a raw SDK traceback.
- Keep it lean: text completion only. No streaming, no tool use, no retry/backoff
  policy beyond a clean error (add later if a real need appears).

## Acceptance criteria
- [ ] A completion client takes a resolved text-model config + prompt + content
      and returns `(text, usage)` with input/output token counts.
- [ ] The provider api key is read only via the #004 cipher from the model's
      `connection`; it is never logged, returned, or persisted in cleartext.
- [ ] The client is injectable behind a protocol/type; a fake client drives all
      tests with no network and no real tokens.
- [ ] An SDK/auth/transport failure raises one domain `LLMError`, not a raw SDK
      exception.
- [ ] `anthropic` SDK usage is isolated to this module (lazy/contained), so the
      rest of the code does not import it directly.
- [ ] `ruff format`, `ruff check --fix`, `pytest` all clean; work committed.

## Out of scope
- The `condense` op itself and the condensations cache (#058).
- Cost/USD derivation from tokens and brief provenance (T21 / #058 records raw
  token usage; USD pricing is a later helper).
- Non-anthropic providers, streaming, tool use, model routing by cluster
  coherence (open item, deferred).

## Review log
- 2026-08-23 PO: authored as the T20 prerequisite. `condense` is the first LLM-
  calling op and no completion client exists yet — only connection validation.
  Build the injectable call seam once (cipher-fed credential, `(text, usage)`
  out, clean `LLMError`) so #058 and every later summarization op are thin
  callers. Flagged the JobContext-cipher gap as the one design point dev resolves.
- 2026-08-24 dev: DONE, committed 318a016, handoff to qa. Added `src/hrono/llm/`
  (`client.py`): `AnthropicClient` implements the `Completion` protocol —
  `complete(CompletionRequest(model, system, content)) -> CompletionResult(text,
  Usage(input_tokens, output_tokens))`.
  - Credential: resolves the model's `connection` from the registry and decrypts
    the api key via the #004 cipher ONLY (mirrors model_validation._resolve);
    never logged, returned, or persisted in cleartext. Verified by test (the SDK
    receives the decrypted key; the stored form is ciphertext).
  - Seams: ops depend on the `Completion` protocol (fake drives their tests); the
    client's own `invoke` seam stands in for the SDK call so this module's tests
    run offline with no tokens.
  - Errors: any SDK/transport/auth failure -> one `LLMError` (plain domain error
    like EmbedError/ClusterError; a job leaf fails cleanly on it). Test proves the
    message is client-safe (does not leak a key even when the raw SDK text did).
  - Isolation: `import anthropic` is lazy and contained in `_default_invoke`
    (grep-confirmed the only anthropic import in src); a missing SDK -> clean
    LLMError.
  - Dep: added `anthropic>=0.40,<1` to main dependencies (core provider, light,
    httpx-based); tests never hit it (fakes).
  RESOLVED the PO's flagged open question: no JobContext change needed —
  `JobContext.cipher` ALREADY exists and the server already constructs
  `Worker(database, cipher=cipher)` (app.py:85), so #058's condense op gets the
  cipher from `context.cipher` and hands it to `AnthropicClient`. The stale
  "JobContext does not expose the cipher" note is superseded.
  Verified: ruff format/check clean; pytest 402 passed / 1 skip (+7 new llm
  tests). Left the pre-existing `.gitignore` edit out of the commit.
- 2026-08-24 qa: PASS -> po-review. Verified every dimension (loaded the
  claude-api reference + engineering:security for the SDK/secret surface):
  - Acceptance criteria all met. `complete(CompletionRequest)` returns
    `(text, Usage(input_tokens, output_tokens))`; injectable behind the
    `Completion` protocol (fake drives every test offline); SDK/transport/auth
    failure -> one `LLMError`, never a raw traceback; the `anthropic` import is
    lazy and grep-confirmed the ONLY anthropic import in `src/`.
  - Security (the load-bearing dimension): the provider key is read only via
    `cipher.decrypt(key_id, auth["key"])` off the connection row — faithfully
    mirrors `model_validation._resolve` (same store lookup, key_id from the row,
    cipher decrypt). Verified cipher signature `decrypt(key_id:int, ciphertext)`
    matches the call. The key is never logged, returned, or persisted: the only
    place it leaves the method is as `api_key=` into the SDK invoke. All LLMError
    messages are client-safe; `test_sdk_failure_becomes_a_clean_llmerror` proves
    the domain message stays clean even when the underlying exception text
    embeds the key. `LLMError` is a plain Exception, consistent with the other
    job-op errors (EmbedError/ClusterError/SplitError) — job failures route
    through the worker (`str(exc)` -> job.error), not the HTTP AppError handler.
  - Actually works: the DB+cipher `complete()` path is exercised end-to-end by
    the tests with a real Fernet cipher and a real connections row; I separately
    verified the one path the fake-invoke stubs can't reach — the real SDK
    attribute path in `_default_invoke` — against the installed anthropic 0.125.0
    (within the `>=0.40,<1` pin): `Anthropic(api_key, base_url).messages.create`
    exists and accepts model/max_tokens/messages/system.
  - Integrity: read-only credential lookup, no DB writes, no corruption risk;
    a failure fails the leaf cleanly.
  - Commit 318a016 is atomic and a clean Conventional Commit; ruff clean; full
    suite 402 passed / 1 skip.
  - PO's flagged open question is correctly resolved: `JobContext.cipher` already
    exists and app.py already builds `Worker(database, cipher=cipher)`, so #058's
    condense op gets the cipher from `context.cipher` — no JobContext change; this
    ticket adds only the seam (no caller yet, which is #058's job).
  Observation for PO/#058 (non-blocking, NOT a defect): if a text model configures
  `params.max_tokens` above ~16000, the non-streaming `messages.create` can raise
  (the SDK guards large non-streaming outputs) — this is caught and surfaced as a
  clean LLMError, so it fails safely; streaming is explicitly out of scope here.
  Revisit if/when a summarisation op needs very large outputs. (Pre-existing
  unrelated `.gitignore` edit remains uncommitted, out of this ticket's commit.)
- 2026-08-24 PO review: PASS -> done. Read client.py and verified the security
  surface myself (the load-bearing dimension): the provider key is read ONLY via
  `cipher.decrypt(key_id, auth["key"])` off the connection row (mirrors
  model_validation._resolve), and leaves the method only as `api_key=` into the
  invoke seam — never logged, returned, or persisted; raised `LLMError` messages
  are constant strings, so `str(exc)` (what the worker records) cannot leak the
  key even though `from exc` chains the cause. `import anthropic` is lazy and
  grep-confirmed the ONLY anthropic import in src/. Ran the checks: 7 llm tests
  pass, ruff clean, full suite 402 passed / 1 skip. All 6 acceptance criteria
  met; dev correctly proved my flagged JobContext-cipher concern was stale
  (JobContext.cipher already exists, app.py already builds Worker(.., cipher=)),
  so #058 gets the cipher from `context.cipher` with no framework change. Noted
  qa's max_tokens>~16k observation for the #058/#059 authors: the default 4096
  is fine for compact condensations, and the recipe's "no token cap" refers to
  prompt-instruction caps that starve/cause fabrication, NOT the API max_tokens
  ceiling — do not conflate the two. No spinoff. Closed. M4 LLM call seam ready;
  #058 (condense) is now unblocked.
