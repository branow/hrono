---
id: 148
title: a bitbucket-workspace source discovers a workspace's repos
priority: medium
size: small
depends_on: [147]
spec_refs: [build-order.md#T41.1, implementation-notes.md]
---

## Context
The other half of T41. #147 settled every decision this one inherits — one
source row, per-repo versions, `git://` addresses, a digest source version —
so this is enumeration against a different API and one more entry in each of
the three tables.

## Description
- `BitbucketWorkspaceSource` variant: `name`, `type: "bitbucket-workspace"`,
  `owner` (the workspace slug), `auth`, optional `include`/`exclude` globs.
- Enumerate `GET /2.0/repositories/<workspace>` — bitbucket pages with a
  `next` URL in the body rather than a page counter, so follow `next` until it
  is absent. The clone url is the `clone` link with `name == "https"`.
- Instance is `bitbucket.org/<workspace>`; units address as `git`.
- Token auth clones as `x-token-auth` (already handled by `git_auth`).
- Validation: the workspace resolves (and the token authenticates if given).

## Acceptance criteria
- [x] Registering the source validates the workspace and encrypts its token.
- [x] `sync` clones every matching repo; `split` addresses each
      `git://bitbucket.org/<ws>/<repo>/<path>@<sha>`.
- [x] `next`-link pagination is driven over a real local HTTP round trip.
- [x] Nothing in the ingest ops changed to accept the type.
- [x] `ruff format`, `ruff check --fix`, `pytest` clean.

## Out of scope
Live verification against real bitbucket — deferred with the rest of the
integration pass.

## Review log
- 2026-09-23 po: authored. Stubs now, integration pass later (operator's call).

- 2026-09-23 dev: the enumeration is all that is bitbucket's. Everything #147
  had generalized into `ingest/discovery.py` on the way — the name globs,
  cloning each repo through the git syncer, the repo -> commit map, reading the
  clones back as units — so `bitbucket.py` is 120 lines of API handling and
  three table entries. `ingest/api.py` now holds the one HTTP GET/POST every
  API-backed type uses, with a transport failure arriving as `SyncError`
  carrying the exception TYPE and never a url (which could hold userinfo).

  Mutations run, all killed:
  - the `next` link ignored -> 1 fails (pagination).
  - the first clone link taken instead of the https one -> 4 fail.
  - a 404 workspace treated as an empty page -> 1 fails.
  - the instance reduced to the host, losing the workspace -> 2 fail.

- 2026-09-23 qa: PASSED. Re-ran dev's https-clone-link mutation (4 fail) and
  added one dev did not, in the code #147 and #148 now SHARE: exclude globs
  ignored in `discovery.kept` -> 1 fails. The extraction into `discovery.py`
  is the right call — #148's own module is enumeration and nothing else, and
  both types are covered by one set of tests for everything below that.

  Not driven against real bitbucket: that is the integration pass the operator
  deferred, and the ticket says so in its own Out of scope.

- 2026-09-23 po: CLOSED. T41 is complete. The shape held: the second discovery
  provider cost an enumeration function and three table entries, and pulled a
  shared `discovery` module out of #147 on the way, which is the refactor
  emerging from observed duplication rather than invented up front.
