---
id: 032
title: storage schema (contents/passages/sections) + byte-identical reassembly + split op (T15.4)
priority: high
size: big
depends_on: [031, 030, 026, 025, 023]
spec_refs: [build-order.md#T15.4, build-order.md#T14, how-hrono-works.md, storage-v2.ipynb]
---

## Context
This lands the persistence for ingested content and wires the whole ingest chain
into a runnable op. It closes M2: after this, `sync` + `split` turn a registered
git source into stored sections and passages with content-addressed bodies,
addressable and embed-ready. The load-bearing invariant is that a section
reassembles byte-identically from its passages. The prototype `storage-v2.ipynb`
demonstrates the shape (contents / paragraphs / chunks); rewrite clean with the
production names (contents / passages / sections).

## Description
Two parts: the storage layer, then the op that fills it.

1. **Schema + store (T15.4)**. Forward-only migration for three tables:
   - `contents` — content-addressed bodies keyed by `content_hash` (the #031
     SHA-256). One row per unique hash: the raw bytes/text stored ONCE and
     (later) embedded once. Dedup: re-storing identical bytes is a no-op insert.
   - `sections` — the clustering/traversal unit: id, the four address parts +
     rendered URI (#031), `version`, byte range (start,end) as data,
     `content_hash` -> contents, source name, ordering. Status columns for later
     ops (embed/cluster) may be added by those tickets; keep this ticket to
     identity + body linkage.
   - `passages` — the recall unit: id, parent `section` id, address + byte range,
     `content_hash` -> contents, `sp_paths` (#031, one or more), order within the
     section.
   All access via the #008 `Database` lock. `snake_case` columns. Provide store
   functions to upsert a content body (dedup on hash), insert a section with its
   ordered passages, and read them back.

2. **Byte-identical reassembly**: concatenating a section's passages' bodies (in
   order) reproduces the section's body exactly; a section's body equals the
   original file's bytes over its byte range. Prove it from STORAGE (read the
   section's passages back out of the DB and concatenate), not just in memory.

3. **`split` op (T14 op / T15.4 wiring)**: register a `split` handler in the jobs
   op registry (#023) that, for a source scope leaf (#024), runs over that
   source's synced cache (#025): filter candidate files (#026), split each into
   sections + passages (#029/#030), assign identity (#031), and persist
   (dedup bodies, insert sections + passages). Idempotent: re-splitting an
   unchanged synced file produces the same hashes and does not duplicate rows.
   Runs as job leaves (one per source via fan-out), failures isolated per #023.
   (Incremental changed-file-only splitting is M7/T33+; here a run splits the
   source's current filtered file set.)

## Acceptance criteria
- [ ] The migration creates `contents` (hash-keyed, dedup), `sections`, and
      `passages` with the address parts + rendered URI, byte ranges, content_hash
      links, and passage->section parentage; applied via the existing Migrator.
- [ ] Storing two pieces with identical bytes writes ONE `contents` row (dedup on
      content_hash); distinct bytes write distinct rows.
- [ ] Byte-identical reassembly holds FROM STORAGE: reading a section's passages
      back and concatenating their bodies reproduces the section body exactly,
      and the section body equals the file's bytes over its range — asserted over
      code/docs/data fixtures.
- [ ] The `split` op, run as a job over a synced+filtered source, populates
      sections + passages + contents with correct addresses (4-part URI @commit),
      hashes, and sp_paths; a failing file's leaf fails in isolation.
- [ ] Re-running `split` on the same synced source is idempotent (same hashes, no
      duplicate content rows/sections).
- [ ] End-to-end drive: register a git source, `sync` it, run `split`, and
      observe stored sections/passages addressable by URI with reassembly intact.
- [ ] Regression-grade tests cover the schema + dedup, storage reassembly, the
      split op over a local fixture repo (offline), and idempotency; a test fails
      if reassembly loses a byte or dedup duplicates a body.
- [ ] `ruff format`, `ruff check --fix`, `pytest` all clean; work committed.

## Out of scope
- Embedding sections/passages (embed op, M2/M3) — this ticket only stores bodies
  once, keyed by the hash the embed op will use.
- Clustering / briefs / trees (M3+).
- Incremental sync-diff (changed/new/deleted classification) — that is M7/T33;
  here `split` processes the current filtered set.
- `hrono tree ... sections/passages` inspect endpoints (tree API, M3+).

## Review log
- 2026-08-16 PO: authored as T15.4 + the split-op wiring, closing M2. Storage
  reassembly must be proven FROM the DB, not just in memory - that is the whole
  point of the passages-nest-in-sections invariant. Sized `big` (schema + store +
  op wiring + e2e); split schema-vs-op into two commits if a clean seam exists.

## dev — 2026-08-16

Landed M2's storage + the split op wiring (two commits: schema+store, then op).

Schema (0007_ingest.sql): `contents` (content_hash PK, body BLOB, byte_len —
dedup on hash), `sections` (id, 4 address parts + rendered URI, version, byte
range, content_hash -> contents, source, ordinal), `passages` (id, section_id FK
ON DELETE CASCADE, address + byte range, content_hash, sp_paths JSON, ordinal).
Applied via the existing Migrator.

Store (ingest/store.py): `upsert_content` (INSERT OR IGNORE — dedup),
`clear_source` (delete sections, passages cascade — bodies kept/shared),
`insert_section`/`insert_passage`, read-backs (`get_content`, `list_sections`,
`list_passages`, `section_by_uri`, `content_count`). Raw SQL under the #008
Database lock, snake_case columns.

Split op (ingest/split_op.py, `OPS["split"]`, imported in app.py): loads config +
synced commit from `source_state` (SplitError if unknown/unsynced), derives
source_type + instance (`_instance` normalises https/ssh-scp/file URLs), filters
the cache (#026), and per file runs structure (#029) + pack sections (#030) +
identity (#031), storing bodies (dedup) + sections + passages in ONE per-source
transaction (delete-by-source then insert -> idempotent). Local cache only, no
cipher. Parses each file once.

Byte-identical reassembly proven FROM STORAGE (read a section's passages back,
concat bodies by hash == section body) over code/docs/data fixtures. e2e on a
real local git repo: register -> sync -> split -> sections addressable by
`git://<instance>/<path>@<commit>`, reassembly intact; re-split idempotent
(stable counts); identical-byte files share one content row; 2 KB data budget
splits big JSON into multiple sections; split runs through the real Worker +
fan_out to success; server startup registers the op.

Out of scope (their tickets): embedding, clustering/briefs/trees (M3+),
incremental sync-diff (M7), tree inspect endpoints. Gate clean: ruff, pytest 342.
Commits 3283e8b (schema+store), a534753 (split op). Closes M2.

## qa — 2026-08-16 — PASS -> po-review

Re-ran the gate MYSELF on 032 isolated (stashed unrelated in-flight WIP off the
tree first): `ruff format --check` clean, `ruff check` "All checks passed!",
`pytest` 342 passed. Then drove the load-bearing invariant FROM THE DB, not on
dev's word:

- e2e on a real local git repo (bare remote -> register source -> `sync` ->
  `split` via the op): 5 sections stored; `yarn.lock` excluded by the default
  filter. For every stored section, `b"".join(get_content(p.content_hash) for p
  in list_passages(section.id)) == get_content(section.content_hash) ==
  file_bytes[byte_start:byte_end]` held for ALL 5 — byte-identical reassembly
  proven from storage (passages->section->file). Sections tile each file exactly
  (concat of ranges == whole file). URIs are the 4-part `git://<instance>/<path>
  @<commit>`; passages carry `sp_paths` JSON.
- Dedup (AC): two distinct "files" with identical bytes + one distinct byte
  string -> exactly 2 `contents` rows; stored body round-trips byte-identical.
- Idempotency (AC): a second `split` of the unchanged cache left `content_count`
  29->29 and section count 5->5 (delete-by-source-then-insert in one txn; no
  duplicate bodies/sections).

Code review: `upsert_content` is `INSERT OR IGNORE` on the hash PK (dedup);
`clear_source` deletes sections with passages cascading (idempotent replace);
content upserted before the FK-linked section/passage; the whole source is one
atomic transaction (`with ... conn:`) so a mid-source file failure rolls the
source's leaf back in isolation (#023). Reads only the local cache — no cipher,
no network. Commits are two clean atomic Conventional Commits. All ACs met.
- 2026-08-16 PO: PASS -> done. Proved the load-bearing invariant FROM STORAGE
  myself: split a real file, stored bodies (content-addressed) + sections +
  passages, then read back from the DB - every section == the concat of its
  stored passages' bodies (by hash) == the file byte range, AND the whole file
  reassembles from the stored sections in order. Dedup: content_count 13->13
  after re-storing identical bytes under a second source (upsert_content INSERT
  OR IGNORE on the hash PK - bodies stored once). Idempotency: clear_source +
  re-split -> stable section count (delete-by-source-then-insert in one txn).
  qa's e2e confirmed the op wiring on a real git repo (register->sync->split via
  the real Worker/fan_out; 5 sections addressable by git://<instance>/<path>@
  <commit>, all reassembled from DB, yarn.lock filtered, 2KB data budget splits
  big JSON). Schema: contents (hash PK, dedup) / sections (4 address parts + URI,
  content_hash FK) / passages (section FK cascade, sp_paths). Ran the gate: ruff
  format (120 clean), ruff check clean, pytest 342 passed. **Closes M2 (Ingest).**
  Unblocks #035 (embed). Closed at a534753.
