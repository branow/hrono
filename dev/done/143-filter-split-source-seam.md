---
id: 143
title: filter and split stop assuming a git working tree
priority: medium
size: medium
depends_on: [142]
spec_refs: [build-order.md#T40, build-order.md#M8, design-sketch-v1.md]
---

## Context
The last third of #055. After #142 a non-git source can be synced into the
cache, and the next two ops still assume what git left there: a filesystem tree
of files to walk, with paths and extensions to filter and language-aware
splitting keyed off them. A Confluence space is not a directory of files, and
forcing it to pretend to be one would push the compromise into every later
source type.

## Description
Define the per-type seam these two ops need, and keep git's implementation as
it is behind it:

- Decide the contract first and write it in the ticket's review log before
  coding: what `filter` and `split` actually need from a source is a sequence of
  addressable UNITS — an identity (path or its equivalent), bytes, and enough
  type information to pick a splitter. Git yields files; another type yields
  pages. Name the unit and keep it the same shape for every type.
- Per-type entries in the same table shape as #142's syncers: the git entry
  walks the working tree exactly as today, applies the same include/exclude and
  size rules, and hands the same bytes to the same splitters.
- The generic path must keep hrono's identity rules intact: the URI stays
  `<source-type>://<instance>/<path>#chunk-<n>@<version>`, `hash` stays the
  raw-byte dedup key, and a section still reassembles byte-identically from its
  passages.

## Acceptance criteria
- [x] `filter` and `split` consume a per-type unit source; the git entry
      reproduces today's behaviour (existing tests pass unchanged).
- [x] A test drives both ops over a FAKE non-filesystem source type registered
      into the table — no engine edit — and the sections/passages it produces
      obey the URI scheme and the byte-identical reassembly rule.
- [x] Adding a source type touches a model variant and table entries only.
- [x] `ruff format`, `ruff check --fix`, `pytest` clean.

## Out of scope
- Any real non-git reader.
- Changing the splitters themselves or the passage packing.

## Review log
- 2026-09-23 po: authored as the read third of #055.

- 2026-09-23 dev: CONTRACT, as the ticket asked before coding. A source type
  yields UNITS: `Unit(path, body)`. `path` is the unit's identity inside the
  source and lands verbatim in the URI, so it must be stable across syncs for
  the same logical unit; it carries an EXTENSION because the splitters pick a
  grammar from it and the section budget scales by it — a wiki names its pages
  `spaces/ENG/onboarding.md` rather than teaching the splitters a second way to
  choose. `Reader` holds three callables: `instance(config)` (the addressable
  identity of the source itself — only the reader knows its config's shape),
  `units(config, cache)` for the whole source, and `unit(config, cache, path)`
  for ONE, because the incremental path must not re-read nine thousand units to
  apply three changes.

  `READERS["git"]` keeps every git behaviour: `ingestable` (globs, size gate,
  symlinks, null-byte sniff) is now the git reader's internals rather than
  ingest's only way to see a source. `filter.py` itself is untouched.

  Beyond the two ops the ticket names, `diff` and `reconcile` go through the
  reader too. That was not gilding: they are the UPDATE path, hrono's
  differentiator, and leaving them walking the cache by hand would have made
  the seam cosmetic — a second source type could be split once and never
  updated. `diff.current_files` asks the reader what the source holds now, and
  `reconcile` takes a `fetch(path) -> Unit` instead of a cache directory.

  Tests in `tests/ingest/test_reader_dispatch.py` drive split and diff over a
  reader with NO filesystem behind it, and check the URI scheme and #029's
  byte-identical reassembly hold for it. Mutations run, all killed:
  - split calling `git_units` directly instead of the reader -> 2 fail.
  - an unmapped type raising `KeyError` instead of `SplitError` -> 1 fails.
  - the instance derived from a git url whatever the type -> 3 fail.
  - the diff walking the cache instead of asking the reader -> 1 fails.

  Filed #144 in the backlog: the spec's `#chunk-n` URI fragment is emitted by
  nothing, and recall's document key only works because every passage of a
  section already shares one URI. Found while asserting identity here.

- 2026-09-23 qa: PASSED. The contract is written down before the code, as the
  ticket asked, and the tests drive both ops over a reader with no filesystem
  behind it. Re-ran dev's first mutation (split calling `git_units` directly ->
  2 fail) and added one dev did not: `reconcile` fetching the OLD path's bytes
  for a changed unit -> 7 fail across ingest and tree. The incremental path is
  genuinely pinned, not just the full split.

  Driven live: after sync+split on a real repo, edited a file, re-synced and
  ran `update` — the changed section's stored body is the NEW text and the
  embeddings followed, so diff -> reconcile -> embed runs through the reader.
  The run then failed at the LLM step with "no text model available", which is
  correct for a database with no text model registered and is #109 doing its
  job.

  Extending the seam to `diff`/`reconcile` beyond the ticket's letter is the
  right call and I would have filed it as a follow-up otherwise: a source type
  that can be split once and never updated would break hrono's core promise.

  #144 (the never-emitted `#chunk-n` fragment) is correctly filed rather than
  fixed here, and the test says which rule it is actually asserting.

- 2026-09-23 po: CLOSED, including the extension to `diff`/`reconcile`. That
  was the right judgement and I would have rejected the narrow reading: hrono's
  differentiator is incremental update, so a source type that can be ingested
  once and never updated is not a source type we support. The three tickets
  together now mean the next reader (T42 Confluence, T43 Notion) is a model
  variant, a syncer, and a reader — no engine edits anywhere.
