---
id: 083
title: `sync` diff — classify new / changed / deleted / moved files between versions (T33)
priority: high
size: medium
depends_on: [025, 032]
spec_refs: [build-order.md#T33, design-sketch-v1.md, clustering-lifecycle.md]
---

## Context
First M7 (Lifecycle) ticket and the entry point of incremental update — hrono's
differentiator. `sync` (#025) already clones/pulls a git source and pins a
commit-SHA version. This ticket adds the DIFF: given the previously-synced version
and the newly-synced one, classify each affected file as NEW / CHANGED / DELETED /
MOVED (renamed), so the downstream incremental pipeline (split -> incremental
placement #068/T34 -> propagate) touches only what changed instead of re-ingesting
everything. Without this classification, "a change touches only affected nodes"
cannot start.

## Description
- Compute the file-level diff between the source's last-ingested version and the
  current sync (git makes this cheap: `git diff --name-status <old>..<new>`, with
  rename detection for MOVED). Produce a classification list: `{path, status:
  new|changed|deleted|moved, old_path?}`.
- MOVED reuses identity where possible: a renamed file with identical bytes is the
  SAME content (content_hash unchanged), so its sections/passages/vectors/
  condensations are reused, only the path/address changes — flag it so T34.3
  (moved/renamed in-place) can reuse the content vector without re-embedding.
- CHANGED vs unchanged is by content: a file whose bytes are identical after a
  pull is not "changed" (content_hash stable) even if git touched it; drive off
  content hashes, consistent with the embed/condense caches.
- The op records enough for `split` to re-split only NEW/CHANGED/MOVED files and
  to remove DELETED files' sections/passages (cascade). Respect the #026 filter
  (a file newly excluded is a delete; newly included is a new).
- Honor the existing version pin (`source_state`) — the diff is old-version ->
  new-version; on first sync everything is NEW.

## Acceptance criteria
- [ ] `sync` (or a `sync`-diff step) classifies affected files as new/changed/
      deleted/moved between the prior and current version, driven by content hash
      (a byte-identical file is not "changed").
- [ ] MOVED/renamed is detected and carries `old_path`, so identity/content can be
      reused (no re-embed of unchanged bytes).
- [ ] DELETED files are identified so their sections/passages can be removed.
- [ ] First sync classifies all files NEW; a no-op re-sync classifies nothing
      changed (drives the incremental promise).
- [ ] Respects the #026 include/exclude filter (exclusion delta = delete/new).
- [ ] `ruff format`, `ruff check --fix`, `pytest` all clean; work committed.

## Out of scope
- Incremental placement / re-clustering (T34 / #068) — this only CLASSIFIES the
  diff; placement consumes it.
- propagate / settle (T36 / T39).
- Non-git source diffing (M8 readers bring their own version/identity).

## Review log
- 2026-08-25 PO: authored as T33, M7 kickoff and the entry point of incremental
  update. Content-hash-driven new/changed/deleted/moved classification on top of
  #025's commit-SHA versions; feeds T34 (#068) placement and DELETED removal. The
  deeper M7 machinery (T34.2-4, T35-T39) is held until this + #068 land.
- 2026-08-25 dev: DONE, committed e924449, handoff to qa. `ingest/diff.py`:
  - pure `classify(old, new)` over path->content-hash maps -> Change(path, status,
    old_path) for new/changed/deleted/moved; unchanged files are silent. MOVED =
    a removed path whose content hash reappears at a new path (renamed identical
    bytes) carrying old_path; deterministic ordering.
  - `current_files(cache, filter)` hashes the cache's ingestable files (honours
    the #026 include/exclude filter, so a newly-excluded file drops out = delete,
    newly-included = new). `stored_files(conn, source)` reconstructs each prior
    file's hash from its stored sections concatenated in order (the #029 tiling
    invariant), comparable to current_files' raw-byte hashing. `diff(...)` ties
    them.
  - First sync (empty stored) -> all NEW; a no-op re-sync -> nothing (content-hash
    driven, a byte-identical pull is not "changed").
  Verified: ruff clean; pytest 540 passed / 1 skip (+8: new/changed/deleted,
  move-with-old_path, first-sync-all-new, no-op-nothing, deterministic, filter
  honoured, stored-file reconstruction, end-to-end diff). Feeds T34 placement
  (#068) + DELETED removal; #068 already landed, so T34.2-4/T35-T39 can build on
  both. Out of scope (T34+): actually re-splitting only the delta / removing
  deleted sections / propagate — this only CLASSIFIES.
- 2026-08-25 qa: PASS (commit e924449) -> po-review. Tree CLEAN at handoff (the
  E501s that were in this file's uncommitted WIP during my #068 review are fixed
  and committed). Verified every dimension end-to-end over a REAL git repo:
  - The load-bearing no-false-changes property holds: after sync+split,
    `stored_files == current_files` exactly — `stored_files` reconstructs each
    prior file hash by concatenating its stored sections in order (#029 tiling
    invariant) and it matches `current_files`' raw-byte hash, so a byte-identical
    pull classifies NOTHING as changed.
  - Mutated v2 (edit one file, delete one, `git mv` one with identical bytes, add
    one) classifies exactly: `edit.py`->CHANGED, `gone.py`->DELETED,
    `orig.py`->`moved.py` MOVED carrying old_path, `fresh.py`->NEW, unchanged
    `keep.py` silent. MOVED is a removed path whose content hash reappears at a
    new path (with a `moved_targets` guard against double-matching); a rename+edit
    correctly falls back to delete+new (content changed, no identity reuse).
  - Content-hash driven throughout; deterministic sort; honours the #026 filter
    (newly-excluded = delete, newly-included = new); first sync -> all NEW; no-op
    re-sync -> nothing. 8 unit tests cover these.
  - Correctly a STANDALONE classifier (`classify`/`current_files`/`stored_files`/
    `diff`), not wired into the sync op — matches the ticket's scope ("this only
    CLASSIFIES; placement consumes it"); T34 will wire it into incremental
    split/removal.
  - ruff clean; full suite 540 passed / 1 skip; atomic Conventional Commit.
  With #068 (stable ids) also passed, the M7 incremental-update foundation
  (classify the delta + preserve identity across rebuilds) is in place for T34+.
  (Pre-existing `.gitignore` edit still uncommitted.)
- 2026-08-25 PO review: PASS -> done. Read diff.py; tree clean, HEAD is #083's commit (e924449): ran the 8 diff tests, ruff clean, full suite 540 passed / 1 skip. classify() is correct and deterministic — CHANGED (both, hash differs), MOVED (a removed path whose content hash reappears at a new added path, old_path carried, moved_targets guards double-match; rename+edit correctly falls back to delete+new), DELETED, NEW. The load-bearing no-false-changes property holds: stored_files reconstructs each prior file's hash by concatenating its sections in order (the #029 tiling invariant), so it matches current_files' raw-byte hash and a byte-identical pull classifies NOTHING changed; honours the #026 filter (newly-excluded=delete, newly-included=new); first sync=all NEW. All acceptance criteria met. Closed. **M7 foundation COMPLETE (#068 stable ids + #083 sync diff) — the incremental-update substrate is in place; T34.2-4 placement + T35-T39 build on it.**
