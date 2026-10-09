---
id: 035
title: `embed` op — in-process model runner + (hash, model) store + incremental skip (T16)
priority: high
size: big
depends_on: [032, 018, 023]
spec_refs: [build-order.md#T16, how-hrono-works.md, design-sketch-v1.md, implementation-notes.md]
---

## Context
Opens M3 (Cluster). Before sections can be clustered into topics, their content
must be embedded into vectors. The `embed` op turns stored content (from #032)
into vectors, keyed by content hash so identical bytes are embedded exactly once.
This is the first ML-in-process op: it loads a local embedding model and runs it
in batches. Everything downstream (path-blend #T17, cluster build #T18) consumes
these vectors. Load `engineering:developer` and note the #019 deferred concern
(bound/guard the in-process model LOAD - it lands here for real).

## Description
Register an `embed` job op (into the #023 op registry) plus its two pieces:

1. **In-process model runner (T16.1)**: load the embedding model named by an
   `embedding`-kind entry in the `models` registry (#018) - `connection: null`
   means in-process via `sentence-transformers` (default
   `Qwen/Qwen3-Embedding-0.6B`, 1024 dims per the model's `params.dims`). Embed a
   list of texts -> vectors in BATCHES (`params.batch_size`, default 32). Guard
   OOM: catch an out-of-memory / allocation failure and degrade gracefully
   (e.g. halve the batch and retry, or fail the leaf cleanly with a clear
   reason) rather than crashing the worker. Bound the model LOAD so a hung/huge
   load fails cleanly (the #019 note). Lazy-import sentence-transformers; a
   missing backend fails the op with a clear reason, never a traceback.

2. **(hash, model) store + incremental skip (T16.2)**: persist vectors keyed by
   `(content_hash, model_name)` in sqlite-vec (a forward-only migration for the
   embeddings vector table; dims from the model). Embedding is **content-
   addressed and embed-once**: the op selects the content hashes (from #032's
   `contents`) that have NO vector for the target model, embeds only those, and
   stores them. A re-run embeds nothing new (idempotent); duplicates are free; a
   model swap (different model_name) re-embeds under the new key without
   touching the old.

- **Job integration**: `embed` runs as a job (via #024 scope -> the content
  hashes needing a vector); one atomic unit per batch/item, failures isolated
  per #023. All DB access via the #008 `Database` lock.
- Embed the stored section + passage content (both live in `contents` by hash,
  so embedding unique hashes covers both). Briefs are embedded later (M4).

## Acceptance criteria
- [ ] The migration creates an embeddings store keyed by `(content_hash,
      model_name)` with the model's dims (sqlite-vec); applied via the Migrator.
- [ ] `embed` over stored content embeds every unique content hash missing a
      vector for the target embedding model and stores `(hash, model) -> vector`;
      a vector has the model's declared dims.
- [ ] Incremental skip / embed-once: a second `embed` run embeds nothing new
      (idempotent), and content shared by multiple pieces (same hash) is embedded
      exactly once; a different model_name re-embeds under the new key without
      disturbing the existing vectors.
- [ ] Batching + OOM guard: embedding runs in batches of `params.batch_size`; an
      induced OOM/allocation failure degrades (smaller batch or clean leaf
      failure), never crashes the worker; a missing sentence-transformers backend
      fails with a clear reason, no traceback.
- [ ] `embed` is registered in the op registry and runs as a job over scope;
      a failing item's leaf fails in isolation.
- [ ] Regression-grade tests are deterministic/offline: stub/inject the model
      runner (a fake embedder emitting fixed-dim vectors) so no real weights
      download; cover embed-once/incremental-skip, the (hash, model) keying, a
      model-swap re-embed, dims correctness, and the OOM-degrade path.
- [ ] `ruff format`, `ruff check --fix`, `pytest` all clean; work committed.

## Out of scope
- Path-blend vector (alpha concat of content + path vectors) — #T17.
- UMAP reduce / HDBSCAN / clustering — #T18.
- Embedding briefs / upper levels — M4.
- Remote (HTTP-connection) embedding models — this ticket does the in-process
  (`connection: null`) path; a remote embed path can follow if needed.

## Review log
- 2026-08-16 PO: authored to open M3, on the #032 stored content. T16.1 runner +
  T16.2 (hash, model) store combined since the op needs both. Content-addressed
  embed-once is the key property. Flagged the in-process model-LOAD bound (the
  #019 deferred note lands here) and deterministic/offline tests (inject a fake
  embedder - never download real weights in CI). Sized `big`; runner-vs-store can
  split into two commits.

## dev — 2026-08-16

Opened M3 with the `embed` op (two commits: store+runner, then op). New package
`src/hrono/embed/`.

Store (0008_embeddings.sql + embed/store.py): `embeddings(content_hash,
model_name, dims, vector BLOB, created_at, PK(content_hash, model_name))`.
Vectors are float32 blobs (sqlite-vec's native element format, queryable by its
distance fns later); dims travel per-row so models of different dimensionality
coexist. `missing(model)` = content hashes with no vector for that model (drives
incremental skip); `upsert_vector` (INSERT OR IGNORE — embed-once), `get_vector`,
`vector_count`.

Design note: a fixed-dim sqlite-vec vec0 table can't hold multiple models with
different dims under one (hash, model) key, and a static migration can't know a
model's dims, so the store is a (hash, model)-keyed table of float32 blobs (the
sqlite-vec element format) — dims-flexible, embed-once, and vec_distance-queryable
at cluster time. Flagging for review in case the team wants a vec0 shadow index
for the active model in #T18.

Runner (embed/runner.py): `embed_texts(texts, batch_size, encode)` batches and
guards OOM — on MemoryError / CUDA "out of memory" it halves the batch and
retries, degrading to size 1 before failing with a clean EmbedError; a non-OOM
error is not swallowed. `encoder_for(model_id)` builds the sentence-transformers
encoder with a bounded load (thread + join(timeout)) and lazy import (missing
backend -> clean EmbedError, never a traceback). The encoder is an injectable
seam so tests run offline with a fake emitting fixed-dim vectors.

Op (embed/op.py, `OPS["embed"]`, imported in app.py): resolves the target
embedding model (named by the job scope `{type:model,name}`, or the sole
embedding-kind model in the registry), selects missing hashes from #032
`contents`, decodes bodies to text, embeds only those in batches via the
injectable runner, and stores (hash, model) -> vector; rejects a dims mismatch
vs the model's declared `params.dims`. Local content only, no cipher. Default
encoder resolved at call time so tests can monkeypatch the backend for the Worker
run.

Verified: migration applies the embeddings table on a fresh real DB; op
registered on server startup; the real encoder path with no backend fails cleanly
("in-process embedding backend is not installed"). Tests (deterministic/offline,
fake embedder — no weights): embed-every-missing + declared dims, idempotent
re-embed, shared-content-embedded-once, model-swap re-embed under a new key,
dims-mismatch rejected, no-embedding-model error, OOM halve-and-continue,
OOM-on-single-item clean fail, non-OOM error not swallowed, missing-backend clean
reason, and embed running through the real Worker to success. Gate clean: ruff,
pytest 356.

Backend dependency: sentence-transformers is lazy/optional and undeclared,
matching the #019 model-validation precedent (avoids pulling torch into every
install). FLAGGING a follow-up to add it as an optional-extras group
(`[project.optional-dependencies] embed = [...]`) so in-process embedding is
installable without bloating the default install.

Out of scope (their tickets): path-blend (#T17), UMAP/HDBSCAN cluster (#T18),
brief/upper-level embedding (M4), remote embedding models. Commits 4630643
(store+runner), 693836f (op).

## qa — 2026-08-16 — PASS -> po-review

Re-ran the gate MYSELF: `ruff format --check` + `ruff check` clean, `pytest` 359
passed. Then drove the op + runner offline (fake fixed-dim encoder, no weights),
not on dev's word:

- Migration on a fresh real DB: `embeddings(content_hash, model_name, dims,
  vector, created_at)`, PK `(content_hash, model_name)`, FK -> contents.
- embed-once / (hash,model) keying: seeded 2 unique bodies (one duplicated) ->
  2 `contents` rows -> `embed` stored exactly 2 vectors, dims 8 as declared;
  shared body embedded once.
- Idempotent re-run embeds nothing new (still 2). Model swap (`minilm`) embeds 2
  under the new key while `qwen`'s 2 stay untouched.
- Dims mismatch (declared 8, encoder emits 5) -> EmbedError, NOTHING stored for
  that model (raise is inside the write txn -> rollback). Naming a
  generation-kind model, or having no embedding model, fails cleanly.
- Runner guards: OOM on a batch halves 3->2->1 and still returns all 3 vectors;
  OOM at size 1 -> clean "out of memory embedding a single item" EmbedError; a
  non-OOM ValueError PROPAGATES unwrapped (not swallowed, not mis-wrapped);
  missing sentence-transformers backend -> clean "in-process embedding backend is
  not installed" EmbedError (the backend is genuinely absent here, so this is the
  real import path, not a stub). Model LOAD is bounded (thread + join(timeout)),
  honoring the #019 note.
- Real Worker dispatch: enqueued an `embed` job, the Worker ran it with no
  encoder kwarg (default resolved at call time, monkeypatched offline) -> job
  `succeeded`, 2 vectors stored. Op registered in OPS on import.
- Design review: slow embedding runs OUTSIDE the #008 Database lock (read hashes
  under lock -> release -> embed -> re-acquire to store), good for the single
  writer. Reads only local content, no cipher. Two clean atomic Conventional
  Commits (store+runner, op).

Two dev-disclosed items for PO to RATIFY (not defects — code is correct and all
functional ACs pass; flagging so PO decides consciously, and can bounce to todo
if it wants a change now):
1. Storage shape: the store is a plain table of float32 blobs (sqlite-vec's
   element format, queryable by its `vec_distance_*` scalar fns at cluster time),
   NOT a `vec0` virtual table. Rationale is sound (vec0 needs fixed dims at
   creation and can't hold multiple models under one (hash,model) key; a static
   migration can't know a model's dims). The full-scan/load-all access pattern is
   exactly what UMAP-over-all wants in #T18; a vec0 shadow index for the active
   model is a #T18 call. Note: actual vec_distance querying is #T18's concern and
   is NOT exercised here (this ticket only stores + reads back, which works).
2. Backend dep: sentence-transformers is lazy/optional and undeclared (matches
   the #019 precedent, avoids pulling torch into every install). Dev flags a
   follow-up to add a `[project.optional-dependencies] embed = [...]` extras
   group. Not a blocker (missing-backend fails cleanly); PO to schedule the
   follow-up.

All in-repo functional ACs met; opens M3.
- 2026-08-16 PO: PASS -> done. Drove the embed op offline (fake fixed-dim
  encoder, no weights) against a real DB: 2 content rows (a duplicate embedded
  ONCE), embed -> 2 vectors, re-embed -> still 2 (incremental skip / idempotent),
  model swap (minilm) -> 2 under the new (hash,model) key with qwen's 2
  untouched, dims mismatch -> EmbedError with 0 stored (rollback in the write
  txn). qa verified the runner OOM halve-and-continue + single-item clean fail +
  non-OOM propagation + missing-backend clean reason + bounded model LOAD (#019
  note honored) + real Worker dispatch + embedding running OUTSIDE the #008 lock
  (read hashes under lock -> release -> embed -> re-acquire to store). Gate: ruff
  clean, pytest 359 passed. Opens M3.

  PO ratification of the two flagged items (both accepted, no change):
  1. Storage shape: the (hash,model)-keyed float32-blob table is CORRECT - vec0
     needs fixed dims at creation and is single-model, incompatible with our
     multi-model per-row-dims key; sqlite-vec's vec_distance_* scalar fns query
     blobs directly and cluster-time UMAP loads all vectors anyway. A vec0/ANN
     shadow index for the active model is a T18/recall-scale optimization, noted
     there, not needed now.
  2. Backend dep: lazy/optional sentence-transformers is correct (keeps torch out
     of the default install, matches #019; missing-backend fails cleanly). But
     there is no SUPPORTED install path today -> spun off #038 for the
     `[project.optional-dependencies] embed` extras group.
  Closed at 693836f.
