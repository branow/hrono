---
id: 026
title: Filter — globs + size cap + null-byte sniff (T13)
priority: high
size: medium
depends_on: [025]
spec_refs: [build-order.md#T13, implementation-notes.md#sources]
---

## Context
A synced repo contains files we never want to ingest — vendored deps, lockfiles,
binaries, huge blobs. The filter decides which files from the synced cache
(#025) are eligible to be split and indexed, so the pipeline never wastes work
(or pollutes the tree) on noise. It applies the source's `filter` config, with
baked defaults when omitted. Pure classification over the synced file tree.

## Description
Add a filter (recommend `src/hrono/ingest/filter.py`) that, given a synced source
cache path and the source's `filter` config, yields the set of ingestable file
paths. Three gates, all must pass:
- **Glob exclude**: exclude files matching any pattern in `filter.exclude`
  (globs via `Path.full_match`, per the spec). When `filter` is omitted, use the
  baked defaults from CLAUDE.md/spec (e.g. `**/node_modules/**`, `**/*.lock`).
  Keep the default patterns as data.
- **Size cap**: drop files larger than `filter.max_size_mb` (baked default when
  omitted, e.g. 2 MB).
- **Null-byte sniff**: for any file no pattern caught, sniff a leading chunk for a
  NUL byte and drop it as binary (the spec's "null-byte sniff for anything no
  pattern caught").
Also skip the VCS metadata dir (`.git`) and non-regular files. The result is a
deterministic, sorted set of repo-relative paths eligible for splitting.

Make it a pure function of (cache path, filter config) so it is unit-testable
against a fixture tree with no network. Field keys `snake_case`. Do not read/emit
file contents beyond the size stat and the null-byte sniff — content splitting is
T14.

## Acceptance criteria
- [ ] Files matching an `exclude` glob (via `Path.full_match`) are dropped;
      with no `filter` config, the baked default excludes apply.
- [ ] Files larger than `max_size_mb` are dropped; the baked default cap applies
      when omitted.
- [ ] A file containing a NUL byte in its head (that no glob caught) is dropped as
      binary; a normal UTF-8/text file is kept.
- [ ] `.git` metadata and non-regular files are never included; the result is a
      deterministic, sorted set of repo-relative paths.
- [ ] The default exclude patterns and default size cap are expressed as data,
      not inline literals scattered through the logic.
- [ ] Regression-grade tests run against a fixture tree: excluded-by-glob,
      over-size, binary-null-byte, kept-text, `.git` skipped, and default-config
      behavior; a test fails if a binary/oversize/excluded file slips through.
- [ ] `ruff format`, `ruff check --fix`, `pytest` all clean; work committed.

## Out of scope
- Splitting/chunking the kept files (T14).
- Per-file hashing / identity / storage (T15).
- Source-type-specific content selection beyond git file trees (page/doc scope
  selectors are handled at the reader/source level, M8).

## Review log
- 2026-08-15 PO: authored as T13. Pure classification over the #025 synced cache;
  default patterns + cap as data; null-byte sniff only for files no glob caught,
  matching the spec.

- 2026-08-16 dev: picked up (dep 025 in done/), implemented. New
  `src/hrono/ingest/filter.py::ingestable(cache, filter_config)` — pure, returns
  a sorted tuple of repo-relative posix paths. Three gates in order: glob exclude
  via `Path.full_match`, size cap (`max_size_mb`), then a null-byte sniff (first
  8 KB) for anything no glob caught; skips `.git` and non-regular files. Defaults
  baked as data from the spec (`_DEFAULT_EXCLUDE = ("**/node_modules/**",
  "**/*.lock")`, `_DEFAULT_MAX_SIZE_MB = 2.0`), applied per-key when the source's
  `filter` config omits one. Reads no content beyond the size stat + sniff
  (splitting is T14). Tests: `tests/ingest/test_filter.py` — kept text vs dropped
  glob/binary/.git, glob matching, null-byte drop, .git skip, size cap (custom +
  default), custom-exclude override, deterministic sort. Gate clean (ruff format,
  ruff check --fix, pytest 262 passed). Drove it over a realistic tree: defaults
  keep src+docs, drop node_modules/lock/png/.git; custom exclude and tiny cap
  behave. Committed 2ef9994. Moved to verifying.
- 2026-08-16 qa: FAIL -> back to todo. One blocking security defect on AC
  "`.git` metadata and non-regular files are never included".

  Finding (symlinks escape the synced cache -> host-file ingestion / traversal):
  `src/hrono/ingest/filter.py:28` gates on `not path.is_file()`, but
  `Path.is_file()` FOLLOWS symlinks and reports the target's type - so a symlink
  whose target is a regular file passes the gate and is included, EVEN WHEN the
  target lives outside the synced cache. hrono ingests heterogeneous, often
  untrusted source repos, and git checks out symlinks (mode 120000) verbatim on
  clone (#025), so a source repo containing `ln -s /etc/passwd leak.txt` (or any
  absolute/`../` symlink escaping `.hrono/cache/sources/<name>/`) causes the
  downstream split/hash/index pipeline to READ AND INDEX files outside the
  synced cache - a path-traversal / information-disclosure vector into the
  knowledge base (later served to agents via recall). Verified against a fixture:
  `ingestable(cache, None)` returned `('escape.txt', 'etc_hosts.txt',
  'real.txt')` where `escape.txt` -> an external host file and `etc_hosts.txt`
  -> `/etc/hosts`. A symlink is a non-regular file, so this violates the AC
  directly.

  Why the tests miss it: `tests/ingest/test_filter.py` only covers regular files,
  `.git`, size, and null-byte - there is no symlink case, so the suite is green
  while symlink traversal is possible.

  Required change: reject symlinks at the filter boundary. Simplest correct
  behavior (matches "non-regular files never included"): skip any symlink -
  `if path.is_symlink(): continue` before the `is_file()` check. If following
  in-repo symlinks is genuinely wanted, instead resolve and CONFIRM CONTAINMENT:
  include only when `path.resolve()` is within `cache.resolve()` (e.g.
  `path.resolve().is_relative_to(cache.resolve())`) AND the resolved target is a
  regular file. Add a regression test with a symlink escaping the cache (both an
  absolute target like `/etc/hosts` and a relative `../` target) asserting it is
  NOT in the result - a test that fails if an escaping symlink is ingested (and,
  if in-repo symlinks are kept, a case proving containment).

  Everything else verified and sound (do not re-litigate on return): the three
  gates (glob exclude via `full_match`, size cap, null-byte sniff only for files
  no glob caught), `.git` skip, defaults-as-data (`_DEFAULT_EXCLUDE` /
  `_DEFAULT_MAX_SIZE_MB` / `_SNIFF_BYTES`), custom vs default vs empty `exclude`
  behavior, and the sorted deterministic repo-relative result - all confirmed by
  a fixture-tree drive. Gate is clean (ruff format/check, pytest 262 passed);
  the fix should keep it so and add the symlink test.

## dev (re-fix after qa bounce) — 2026-08-16

qa was right: `is_file()` follows symlinks, so a link in the cache pointing at
`/etc/hosts` (absolute) or `../secret` (relative) passed the "regular file"
gate and would be ingested — a traversal / info-leak. Fix per qa's simplest
correct option: skip any symlink at the filter boundary
(`path.is_symlink()` before `is_file()`), matching "non-regular files never
included". No target is stat'd or read, so nothing outside the cache is
touched. rglob does not descend symlinked dirs (recurse_symlinks=False), so a
symlinked directory is also never traversed.

Regression tests added: escaping symlinks (absolute → outside file, relative
`../` target) assert NOT ingested; an in-cache symlink-to-file also skipped.
Both fail if the guard is removed. Gate clean: ruff format/check, pytest
264 passed. Commit 7ab6951.
- 2026-08-16 qa: PASS -> po-review. Re-verified; the blocking symlink-traversal
  defect is resolved. Re-ran the exact kickback repro - a source cache with a
  symlink to an external host file, a symlink to `/etc/hosts`, and a dangling
  relative `../` escape now yields `ingestable(cache, None) == ('real.txt',)`:
  every symlink is excluded, so the pipeline can no longer read/index files
  outside `.hrono/cache/sources/<name>/`. The new tests
  (`test_symlink_escaping_the_cache_is_never_ingested` for absolute + `../`
  targets, and `test_symlink_to_a_file_inside_the_cache_is_also_skipped`) fail
  if a symlink is ingested. All previously-verified behavior still holds (glob
  exclude / size cap / null-byte sniff / `.git` skip / defaults-as-data / sorted
  deterministic result). Fix commit 7ab6951 is a proper atomic Conventional
  Commit (`fix:`). Re-ran the gate: ruff format clean (97 files), ruff check
  passed, pytest 264 passed.
- 2026-08-16 PO: PASS -> done. This ticket earned a qa security bounce: the first
  cut gated on `is_file()`, which FOLLOWS symlinks, so a source repo with a
  symlink to an external/host file (absolute, `/etc/hosts`, or a relative `../`
  escape) would ingest files OUTSIDE `.hrono/cache/sources/<name>/` into the
  knowledge base - a path-traversal / info-disclosure vector. Fixed by skipping
  symlinks at the boundary (`path.is_symlink()` before `is_file()`) with rglob
  not descending symlinked dirs. Independently reproduced the exact escape (3
  escaping symlinks + a symlinked dir in the cache) -> `ingestable` returns only
  the real in-cache file (`('real.txt',)`); the vector is closed. 026's own tests
  (10) pass and the three gates (glob exclude via full_match, size cap, null-byte
  sniff for uncaught files), `.git` skip, and defaults-as-data all hold. Note:
  the full pytest suite currently shows one failure + a reformat, but that is
  #028's UNCOMMITTED in-progress error-migration polluting the working tree
  (auth/users/errors), not 026 - 026 is committed at 7ab6951 and gated clean
  (264) per qa. Unblocks #032. Closed at 7ab6951.
