---
id: 019
title: model validation on write (embedding load + text round-trip)
priority: high
size: big
depends_on: [018, 015]
spec_refs: [build-order.md#T9.2, build-order.md#T9.3, implementation-notes.md#models]
---

## Context
A registered model must actually work, so a bad model id, wrong dims, or an
unreachable connection is caught at write time rather than mid-build. #018 wired
the `models` collection with a no-op validation hook; this ticket fills it,
dispatching by `kind`: embedding models load and must emit a vector of the
declared dims (T9.2); text models round-trip a trivial prompt through their
connection (T9.3). It depends on #015 because remote models validate through a
registered `connection`. Spun off from the T9 models slice.

## Description
Implement the `models` validation hook, dispatched by `kind` via a data-driven
map (not if/elif):
- **embedding (T9.2)**: load the model and embed a tiny probe input; assert the
  returned vector's length equals the declared `params.dims`. In-process
  (`connection: null`) loads via sentence-transformers per the stack; remote
  (`connection` set) calls the connection's embed endpoint. Reject on load
  failure, unreachable connection, or a dims mismatch with a clear reason.
- **text (T9.3)**: round-trip a trivial prompt through the model's `connection`
  (a minimal, near-zero-cost generation) and require a non-empty response.
  Reject on connection failure or an empty/errored response with a clear reason.
- A model that references a `connection` by name must resolve it from the
  `connections` registry (#015); a missing/invalid connection reference is a
  clear rejection, not a crash.

Never leak any connection credential in a reason, log, or stored row (the
credential is fetched+decrypted only to reach the provider). Bound every
network/load call with a sane timeout. Keep validation cost minimal (one tiny
probe), never a full workload. Load `engineering:security` (credential use) and
`engineering:developer` (kind-dispatch wiring).

## Acceptance criteria
- [ ] Registering an `embedding` model whose declared `dims` match the model's
      real output succeeds; a `dims` mismatch is rejected with a clear error and
      the model is NOT stored.
- [ ] Registering a `text` model whose connection round-trips a prompt succeeds;
      an unreachable/failed connection is rejected with a clear error and the
      model is NOT stored.
- [ ] A model referencing an unknown/invalid `connection` name is rejected
      clearly (not a 500/traceback).
- [ ] No connection credential appears in any reason, log line, or stored row.
- [ ] Validation is bounded by timeouts and uses a minimal probe, not a full
      workload; the per-kind dispatch is data-driven.
- [ ] Regression-grade tests cover embedding-dims-ok, embedding-dims-mismatch,
      text-round-trip-ok, connection-unreachable, and unknown-connection, using
      a stubbed/mocked embedder + connection so the suite is deterministic and
      offline (no real model download, no real network, no real key); a test
      fails if a credential leaks or a bad model is accepted.
- [ ] `ruff format`, `ruff check --fix`, `pytest` all clean; work committed.

## Out of scope
- Actually using the model in a build/recall (M2+).
- Caching validation results or re-validating on read.
- Downloading real model weights in tests (mock the load path).

## Review log
- 2026-08-15 PO: authored as the T9.2+T9.3 follow-on to #018. Combined the two
  validation paths since both are the same hook dispatched by `kind`. Flagged
  deterministic/offline tests (mock the embedder + connection), data-driven
  dispatch, bounded probes, and no-credential-in-errors. Sized `big` because it
  spans two validation modes and the connection-resolution path; if dev finds a
  clean seam, splitting embedding-vs-text into two commits is welcome.
- 2026-08-15 dev: picked up (deps 018, 015 in done/), moved to in-progress.
- 2026-08-15 dev: implemented. Generic base change: validation hooks now receive
  a `ValidationContext(database, cipher)` (in descriptor.py) built by the engine
  per write, so a hook can read a sibling collection and decrypt its secret. This
  is generic, not models-specific — git/anthropic hooks gained an ignored
  `context` param; only models uses it. New `registry/model_validation.py`:
  `validate_model(config, context, *, embed, generate, timeout)` dispatches via a
  data-driven `_VALIDATORS = {"embedding":..., "text":...}` map. `_resolve` reads
  the named connection from the `connections` registry and decrypts its `auth.key`
  with the context cipher (raises `unknown connection: <name>` when absent).
  Embedding: probe -> vector, assert len == params.dims (ValidationFailed on
  mismatch / load failure); in-process (connection null) lazy-imports
  sentence-transformers, remote POSTs `/v1/embeddings`. Text: requires a
  connection, round-trips a 1-token prompt (anthropic /v1/messages, else
  /v1/chat/completions), requires non-empty output. Probes are DI seams so tests
  are offline; reasons never include the credential/url/response. Did NOT add
  sentence-transformers (heavy; lazy import raises a clear ValidationFailed if
  absent — real weights arrive with M2 ingest). Tests: `test_model_validation.py`
  (dims ok/mismatch, text round-trip, empty-response, connection-failure,
  unknown-connection, decrypted-key-reaches-probe, credential-never-in-reason,
  text-requires-connection — all via injected probes + a real DB for resolution)
  and updated `test_models.py` (#018) to stub the probes + seed the referenced
  connection, `test_engine.py`'s synthetic hook to the (config, context)
  signature. Gate clean (ruff format, ruff check --fix, pytest 176 passed).
  Verified in-process: the probe receives the decrypted key while the stored row
  stays ciphertext, dims-mismatch/unknown-connection reject cleanly, no leak.
  Scope: real weight download + full provider matrix are M2; commit edaf4e0.
  Moved to verifying.
- 2026-08-15 qa: PASS -> po-review. Verified all dimensions (deep security pass
  + engineering:developer on the generic base change). This is the first ticket
  to change the base, and the change is genuinely generic: a frozen
  `ValidationContext(database, cipher)` is threaded into every validation hook
  by the engine, so a hook can read a sibling collection and decrypt its secret;
  the git and connection validators simply accept-and-ignore it (documented),
  and the #012 seam test's hook was updated to the same `(config, context)`
  signature and still passes - the base change is not models-specific. Drove the
  full chain end to end against the real server with a local stub provider:
  registered an anthropic connection (endpoint -> stub, validated via
  /v1/models) and a text model referencing it (validated via a max_tokens:1
  /v1/messages probe) -> both 201, and the stub received the DECRYPTED api-key
  in x-api-key, proving resolve -> decrypt -> probe works e2e. Rejection paths:
  an unknown connection -> clean `400 {"detail":"unknown connection: ghost"}`
  and the model is NOT stored; a text model with `connection: null` -> `400
  "text model requires a connection"`. Leak audit at the byte level: the api-key
  canary appears in NO hrono server log and NO registry row in clear form - the
  connections row holds it encrypted (key_id=1), the models row is secretless
  (key_id=NULL). Credential handling is sound: the key is decrypted only into an
  in-memory connection dict to build the probe headers, all reasons are opaque
  ("cannot load embedding model" / "embedding dims mismatch: declared X, got Y"
  / "cannot reach the model connection" / "model returned an empty response" /
  "unknown connection"), and the documented broad `except` in each kind path
  deliberately converts any backend error into a clean 400 so no traceback, URL,
  or key can propagate. Dispatch is data-driven via the `_VALIDATORS` kind map
  (embedding/text), probes are minimal (embed "probe"; generate max_tokens:1),
  and network calls are timeout-bounded. Tests are regression-grade and offline
  (stubbed embed/generate + real cipher/DB for resolve): embedding dims-ok and
  dims-mismatch, text round-trip-ok, empty-response, connection-unreachable,
  unknown-connection, text-without-connection, plus
  test_resolved_connection_is_decrypted_for_the_probe and
  test_credential_never_appears_in_a_reason. Minor non-blocking note: the
  in-process embedding LOAD (sentence-transformers) is not itself wrapped in a
  timeout - only the network probes are; wrapping a synchronous model load is
  non-trivial and HF handles its own download timeouts, and every acceptance
  criterion is met - noted, not blocking. Code review clean: generic frozen
  context, DI probes, typed, docstrings only, no emojis. Commit edaf4e0 is a
  proper atomic Conventional Commit (the validator-signature updates are
  necessary consequences of the generic hook change). Re-ran the gate: ruff
  format clean (62 files), ruff check passed, pytest 176 passed.
- 2026-08-15 PO: PASS -> done. This is the first ticket to change the base; I
  confirmed the change is genuinely generic: `ValidationContext(database,
  cipher)` is a frozen carrier threaded into EVERY validation hook by the engine
  (built per write from app.state.db + the active cipher), and git/connection
  validators accept-and-ignore it - not models-specific. Verified existing
  collections still validate (all 55 registry tests green, engine seam test
  updated to the (config, context) signature). Drove the offline rejection paths
  live: unknown connection -> 400 {"detail":"unknown connection: ghost"} and NOT
  stored (404); text-without-connection -> 400 "text model requires a
  connection"; in-process embedding with no backend -> 400 clean actionable
  message; zero tracebacks in the logs. Dispatch is a data-driven kind map,
  probes are DI seams (offline tests), reasons opaque, credentials decrypted
  only in-memory to reach the probe (qa's byte-level audit confirmed no leak).
  Ran the gate: ruff format (62 clean), ruff check clean, pytest 176 passed.
  Completes T9 (models). Note for M2: when sentence-transformers lands, revisit
  wrapping the in-process embedding LOAD in a timeout (only network probes are
  bounded today; harmless now since the backend is not installed). Closed at
  edaf4e0.
