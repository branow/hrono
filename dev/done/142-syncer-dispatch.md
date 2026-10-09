---
id: 142
title: sync dispatches by source type instead of running git directly
priority: high
size: medium
depends_on: [141]
spec_refs: [build-order.md#T40, build-order.md#M8, design-sketch-v1.md]
---

## Context
The second third of #055. `ingest/sync.py:sync` reads the source's config and
goes straight to `git clone`/`fetch`/`reset` — there is no `if type` and no
registry of syncers, so the op IS the git syncer. Every source type needs the
same two things from this step and only these two: the current content in the
cache, and a version pinned. Git gets there with clone/pull + a commit SHA; an
API-backed source gets there with a pull + a page version or etag. The
transport is the variable; the contract is not.

## Description
Introduce the seam and move git behind it, changing no git behaviour:

- A `Syncer` protocol: given the source's decrypted config and its cache path,
  fetch current content into that path and return the version as opaque text.
  `source_state` already stores version as text; leave it alone.
- A `SYNCERS[type]` table, `{"git": git_sync}`, in the same data-driven shape as
  `OPS` / `_RESOLVERS` / `_VALIDATORS`. `sync` resolves the source, looks up its
  type, and delegates. Today's `_sync_repo` and its helpers become the git
  entry, moved (not rewritten) into their own module.
- An unknown type raises `SyncError` naming the type — a clean domain error the
  #109 boundary records with its wording intact, not a `KeyError`.
- Credential handling stays where it is: `_load_source` decrypts, the syncer
  receives plaintext and must never put it in an error message (it does not
  today — keep it that way, and keep the test that proves it).

## Acceptance criteria
- [x] `sync` dispatches through the syncer table; the git syncer clones, fetches
      and pins the commit SHA exactly as before (its existing tests pass
      unchanged, including the credential-free error test).
- [x] A source whose type has no syncer fails the job with a `SyncError` naming
      the type, and the job records it with that wording (#109).
- [x] A test registers a fake syncer into the table and drives `sync` end to end
      through the op — adding a type is a table entry, not an engine edit.
- [x] `ruff format`, `ruff check --fix`, `pytest` clean.

## Out of scope
- A real non-git syncer (M8's own per-type tickets).
- `filter` / `split` (#143).

## Review log
- 2026-09-23 po: authored as the sync third of #055.

- 2026-09-23 dev: `SYNCERS` ({"git": git_sync}) in `ingest/syncers.py`; the git
  implementation moved unchanged into `ingest/git_syncer.py`; `sync` resolves
  the source, looks the type up and delegates. `SyncError` moved to
  `hrono/ingest/__init__.py` — the same place `ClusterError` sits, and the only
  way the op and the syncers can both use it without importing each other.
  Unknown type -> `SyncError` naming the type, which #109 records verbatim
  because it is hrono's own wording.

  One thing beyond the letter of the ticket, and why: `_load_source` decrypted
  `auth.token` / `auth.key` by NAME, which is git's shape, so a reader whose
  credential sits elsewhere would silently receive ciphertext. It now decrypts
  through `registry.write.decrypt`, reading the SAME `secret_paths` the
  descriptor already declares for encryption. No new concept, and the seam is
  useless without it.

  Tests in `tests/ingest/test_syncer_dispatch.py`, including the REAL git
  syncer driven end to end through the seam against a local repo (#108).
  Mutations run, all killed:
  - `sync` calling git directly instead of dispatching -> 3 fail.
  - an unknown type raising `KeyError` instead of `SyncError` -> 1 fails.
  - the config reaching the syncer still encrypted -> 1 fails.
  - the version pinned as "" instead of the syncer's -> 5 fail.

- 2026-09-23 qa: PASSED. Criteria met, and the seam test drives the REAL git
  syncer (#108), not only a fake. Added a mutation dev did not state: the
  syncer handed the WRONG cache directory -> 7 fail, so the contract's first
  half (content where the caller asked for it) is pinned and not just the
  version.

  Driven live against a real local repo: register a git source, `POST /jobs`
  op=sync, then op=split — both succeed; sections land with
  `git://<instance>/<path>@<sha>` URIs and `source_state` pins the commit.
  Committed a second time on the origin and re-ran: the new file is picked up
  and the version moves to the new SHA.

  The out-of-ticket change (decrypting by the descriptor's declared
  `secret_paths` instead of by git's field names) is accepted: it is the same
  secrets through the same cipher, it is pinned by its own test, and without it
  the seam would hand a future reader ciphertext. Security: errors stay
  credential-free, and `git_instance` still strips a url's userinfo.

- 2026-09-23 po: CLOSED. The contract is the right one — content in the cache,
  a version pinned, nothing else — and it is the one the spec's own framing
  implies ("clone/pull is git's transport, not the abstraction"). Driving the
  real git syncer through the seam is what makes this trustworthy rather than
  merely green.
