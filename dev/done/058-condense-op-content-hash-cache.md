---
id: 058
title: `condense` op + content-hash cache (T20) — the map stage
priority: high
size: big
depends_on: [057, 032, 023, 021]
spec_refs: [build-order.md#T20, summarization-experiments.md, implementation-notes.md, how-hrono-works.md]
---

## Context
T20, the MAP stage of the settled two-layer summarization recipe
(summarization-experiments.md). `condense` reduces each stored section to its
essential information via a cheap LLM call, and — this is the point — caches the
result by the section's CONTENT HASH so an unchanged section is NEVER re-
condensed. That content-addressed cache is what makes cluster/brief rebuilds
incremental (only new/changed files pay map cost), exactly like the embeddings
table. The reduce stage (per-cluster brief) is T21/#059, not this ticket.

The recipe is SETTLED — bake it, do not re-derive: per-section condensation,
length follows content density (no token cap — a hard cap starves dense files and
CAUSES fabrication), identifiers/values copied VERBATIM (never inferred), plus
`GOTCHA:` lines for non-obvious hazards. These instructions already live in the
seeded `condense`-role prompt (`registry/prompts.py`) — the op renders that
prompt, it does NOT hardcode summarization vocabulary in code.

## Description
Register a `condense` job op (into #023's registry) that runs the map stage over
a scope's sections, on the #057 completion client:
- **Resolve** the `condense`-role text model, the `condense`-role prompt
  (already seeded, #021), and the connection. OPEN QUESTION for dev — how a role
  maps to a model: the `Model` (#018) has `kind` but no `role` field, and there
  is no role->model config yet. RECOMMENDED default (YAGNI): resolve the sole
  `text`-kind model, mirroring `embed/model.py`'s "the one embedding model, or
  the named one in scope"; raise a clean error if several exist and none is
  named. Do NOT build a role-mapping config until multiple text models coexist
  (that is its own ticket when it is real). Confirm this reading before coding.
- **Cache table** (forward-only migration): `condensations` keyed for embed-once/
  skip-if-exists — at least (content_hash, model) unique, storing the condensed
  `text`, `input_tokens`, `output_tokens`, and `created_at`. Key on the same
  `content_hash` the embeddings table uses (#031/#032), so a section shared by
  content is condensed once ever.
- **Per section**: look up (content_hash, model); if present, SKIP (no LLM call);
  else render the condense prompt over the section's content, call the #057
  client, persist text + token usage.
- **Lock discipline** (mandatory, like #035/#040): load the scope's sections +
  the already-cached content_hashes UNDER the #008 lock, RELEASE it, make the LLM
  calls OUTSIDE the lock, re-acquire only to persist. Never hold the lock across
  an LLM call.
- **Failure isolation**: a section whose LLM call fails fails its own leaf
  cleanly (domain error), leaving the rest pending; idempotent re-run fills only
  the gaps (skip-if-exists).
- References/URIs are appended mechanically from metadata at BRIEF time, not here
  (T21) — out of scope.

## Acceptance criteria
- [ ] `condense` is registered and runs as a job over a scope of sections, on the
      injected #057 client.
- [ ] Each section is condensed via the seeded `condense`-role prompt rendered
      over its content; no summarization vocabulary is hardcoded in the op.
- [ ] Results are cached by content hash: a re-run over unchanged sections makes
      ZERO new LLM calls (asserted with a fake client call-counter) — the
      incremental promise.
- [ ] Condensed text + input/output token usage are persisted per content hash.
- [ ] Heavy LLM work runs OUTSIDE the #008 lock (load under lock -> release ->
      call -> re-acquire to persist); a failing section fails its leaf cleanly.
- [ ] Baked recipe: no token cap; the op does not truncate section content before
      condensing; identifiers-verbatim/GOTCHA come from the prompt, not code.
- [ ] Tests use a FAKE completion client (no network/tokens): skip-on-cache-hit,
      prompt-rendered-with-content, persistence + token recording, lock
      discipline, failure isolation. `ruff format`, `ruff check --fix`, `pytest`
      all clean; work committed.

## Out of scope
- The reduce stage / per-cluster `brief` and provenance (T21 / #059).
- Cost/USD derivation (raw tokens only here).
- Model routing by cluster coherence (Haiku vs Sonnet) — deferred open item.
- Upper levels, freshness/judge, export.

## Review log
- 2026-08-23 PO: authored as T20 (map stage) split from the LLM-client seam
  (#057). Content-hash cache = the incremental lever, so the load-bearing
  acceptance criterion is "re-run makes zero LLM calls". Recipe constants baked
  from summarization-experiments.md (no token cap, verbatim identifiers, GOTCHA
  lines) and already seeded as the condense prompt. Flagged the role->model
  open question with a YAGNI default (sole text model) for dev to confirm rather
  than guess.
- 2026-08-24 dev: DONE, committed 53b39c8, handoff to qa. Added `hrono/summarize/`
  (`condense.py` op + `store.py`) and migration 0010 `condensations`
  (content_hash, model_name PK; text + input/output tokens + created_at; FK to
  contents; mirrors the embeddings table).
  - CONFIRMED the PO's YAGNI default: `_resolve_text_model` takes the sole
    `text`-kind model, or the one named in the job scope (mirrors
    embed/model.resolve_embedding_model); clean LLMError on none/ambiguous. No
    role->model config built (deferred until multiple text models coexist).
  - Prompt: renders the sole `role=condense` prompt from the registry (seeded
    #021) via `template.replace("{content}", body)` — zero summarisation
    vocabulary in code; errors cleanly on missing/ambiguous prompt.
  - Cache/skip: `store.pending` returns DISTINCT SECTION content hashes lacking a
    condensation for the model (passages/path bodies never condense). Re-run over
    unchanged sections makes ZERO LLM calls (asserted with a fake-client counter)
    — the incremental lever.
  - Lock discipline (#035/#040): pending sections loaded UNDER the #008 lock,
    released, each LLM call made OUTSIDE the lock, lock re-acquired only to
    persist THAT section — so a failing call fails the leaf cleanly while every
    section condensed before it is kept, and an idempotent re-run fills only the
    gaps (both asserted).
  - No token cap / no truncation (baked). Client is injected behind #057's
    `Completion` protocol; `_default_client` builds `AnthropicClient(db, cipher)`
    from `context.cipher` (the worker already supplies it — see #057 handoff).
    Registered into OPS + app.py startup.
  Verified: ruff format/check clean; pytest 413 passed / 1 skip (+11 condense
  tests: registration, per-section persist + token recording, zero-call re-run,
  prompt rendered over content, shared-content-condensed-once, failure-isolation
  with gap-fill, no/multiple text model, named-model disambiguation, no prompt,
  worker dispatch with join). Left the pre-existing `.gitignore` edit out of the
  commit.
- 2026-08-24 qa: PASS -> po-review. Verified every dimension:
  - Load-bearing incremental criterion holds end-to-end: I drove the REAL op on a
    mutated corpus — condense 3 sections (3 calls), add ONE new section, re-run ->
    exactly 1 call for the new section only, 4 cached total. This is the core
    "a change touches only affected nodes" promise, working through the op, not
    just a unit stub. `test_rerun_makes_zero_llm_calls` covers the unchanged case.
  - Lock discipline correct by construction: `completion.complete()` sits OUTSIDE
    any `database.connect()` block; pending sections + model + template load under
    one lock, the lock releases, each LLM call runs unlocked, and persistence
    re-acquires per section — same shape as #035/#040. The failure-isolation test
    proves per-section commits (a mid-loop failure keeps earlier condensations;
    an idempotent re-run fills only the gap).
  - Recipe baked correctly: the op renders the seeded `role=condense` prompt via
    `template.replace("{content}", body)` with zero summarisation vocabulary in
    code; no token cap, no truncation of section bodies. Confirmed the seeded
    condense prompt actually contains `{content}`.
  - Cache shape: migration 0010 `condensations` PK (content_hash, model_name),
    FK to contents, token usage on the row — mirrors the embeddings table, so a
    section shared by content is condensed once ever and a model swap re-condenses
    under the new key. `store.pending` uses NOT EXISTS over DISTINCT section
    hashes (passages/paths never condense); `upsert` is INSERT OR IGNORE.
  - PO's open question resolved correctly with the confirmed YAGNI default:
    `_resolve_text_model` = the sole text model or the one named in scope (mirrors
    embed/model.resolve_embedding_model); no role->model config built. Clean
    LLMError on none/ambiguous/no-prompt.
  - Security: content-only op, no secret handled here — the provider key stays
    inside #057's cipher-fed client; the condensations table is content-only.
  - Worker test correctly uses `worker.join(timeout=5)` after stop — the #040
    teardown-race lesson was applied; summarize suite stable across repeat runs
    (no segfault). Commit 53b39c8 is atomic and a clean Conventional Commit; ruff
    clean; full suite 413 passed / 1 skip.
  Observations for PO (non-blocking, NOT defects): (1) the op sends the entire
  rendered template as the user `content` with `system=""` — a fine choice given
  the seeded prompt bundles instructions + `{content}` in one template. (2) There
  is no guard that a `condense`/`brief` prompt actually contains `{content}`; the
  seeded defaults have it, but a user editing the prompt to drop the placeholder
  would silently condense without the section body. Consider a prompt-validation
  hook that requires `{content}` when brief-role prompts land (#059/#061) — a
  small hardening, not needed for this ticket. (Pre-existing unrelated
  `.gitignore` edit remains uncommitted, out of this ticket's commit.)
- 2026-08-24 PO review: PASS -> done. Verified independently. Read condense.py /
  store.py / migration 0010: `pending` skips via NOT EXISTS over DISTINCT section
  content hashes (zero calls on re-run); the lock is released before every LLM
  call and re-acquired per-section to persist (failure isolates, gap-fill on
  re-run); the seeded `role=condense` prompt is rendered via
  `template.replace("{content}", body)` with no summarisation vocabulary in code;
  cache keyed (content_hash, model_name) FK contents — mirrors the embeddings
  table. Ran the incremental/failure tests (3 pass), all 11 summarize tests,
  ruff clean, full suite 413 passed / 1 skip. Dev confirmed the YAGNI role->model
  default (sole text model / named-in-scope). All 7 acceptance criteria met,
  including the load-bearing zero-call-on-re-run. Closed. Spun off #066 for qa's
  observation #2 (no guard that a content-consuming prompt keeps its `{content}`
  placeholder — a silent footgun #059/#061 also inherit); did NOT hold #058 for
  it. Observation #1 (whole template as user content, system="") is a fine design
  choice given the seeded prompt bundles instructions + `{content}` — no action.
