---
id: 149
title: a confluence source ingests the pages of its scoped spaces
priority: high
size: medium
depends_on: [143]
spec_refs: [build-order.md#T42, implementation-notes.md, design-sketch-v1.md]
---

## Context
The first source type with no git behind it at all — the one #143's contract
was written for. Confluence is API-only: there is nothing to clone, so the
syncer MATERIALIZES what it pulls into the source's cache directory and the
reader reads it back. That is not a workaround: the contract's cache is
"where this source's current content lives", and a pulled page is current
content.

## Design, decided
- Auth is `{"method": "basic", "email", "token"}` (Atlassian's API token
  scheme), sent as HTTP basic. `token` joins `auth.key`/`auth.token` in the
  descriptor's `secret_paths`.
- `scope` is a list of typed selectors, unioned; empty or `[{"type":"all"}]`
  means everything the credential can see. v1 selectors: `space` (by `key`)
  and `page` (by `id`).
- A page is one unit. Its path is `space-<KEY>/page-<ID>.html`, because the
  splitters choose a grammar by EXTENSION (#143) and what Confluence returns
  is storage-format XHTML. Storing it verbatim keeps ingest honest — no
  lossy conversion hidden inside a reader.
- A page's version is its Confluence `version.number`, carried per unit
  (#147's `Unit.version`), so one edited page does not re-ingest a space.
- Identity: `confluence://<site host>/space-<KEY>/page-<ID>.html@<version>`,
  which is the design sketch's address (its `#Deployment-Steps` fragment is
  dropped per #144).

## Description
- The model variant, the validator entry (the base url resolves and the
  credential authenticates), the syncer entry (pull every scoped page, write
  each to the cache, record an id -> version map) and the reader entry (units
  from the cache, per-page versions).
- Follow Atlassian's `_links.next` pagination.
- The source version is a digest over the sorted page -> version map.

## Acceptance criteria
- [x] A `confluence` source registers, validates and stores its token
      encrypted.
- [x] `sync` pulls every page in scope; `split` stores sections addressed
      `confluence://<site>/space-<KEY>/page-<ID>.html@<version>`.
- [x] Two pages at different versions keep their own versions in one source.
- [x] A space selector and a page selector both work, and unioned scopes do
      not double-ingest a page.
- [x] The API is driven over a real local HTTP round trip (#108).
- [x] `ruff format`, `ruff check --fix`, `pytest` clean.

## Out of scope
- Confluence-specific chunk boundaries (the spec defers them).
- Attachments, comments, labels, and page hierarchy as tree structure.
- Live verification against a real site.

## Review log
- 2026-09-23 po: authored.

- 2026-09-23 dev: `ingest/pages.py` holds what every API-only type shares —
  materialize each pulled page into the cache, record a page -> version map,
  read them back as units carrying their own versions. `confluence.py` is the
  selectors, the two endpoints, basic auth and the page shape.

  One rule worth calling out because it is not obvious: `materialize` REPLACES
  the cache rather than merging into it. A page that leaves the scope must
  leave the cache, or every later diff reports it as present for ever. It has
  its own test, and removing the clear fails it.

  Mutations run, all killed:
  - the scope union no longer deduplicating -> 1 fails.
  - `_links.next` ignored -> 1.
  - every page reporting version 1 -> 2.
  - the cache merged instead of replaced -> 1.
  - an unknown selector silently meaning "everything" -> 1, AFTER I fixed the
    test. It SURVIVED first: the test asserted only that the message mentioned
    the selector, and the fallback path failed later with a message that also
    mentioned it. The test now registers the full listing (so a fallback would
    succeed) and asserts the failure is the "unsupported" one. My own instance
    of the trap #144 put in dev.md.

  Also fixed #141's unknown-type test, which used `type: "confluence"` as its
  example of an unregistered tag. That tag is real now, so the test had
  quietly become a check that a body with missing fields is rejected. It uses
  `sharepoint` and still asserts the known tags are named.

- 2026-09-23 qa: PASSED, driven live against a local confluence stub through
  the real server (port 8203):
  - `POST /sources` with a basic-auth body -> 201, token masked on read back
    and stored encrypted (checked in the database, not in the response).
  - `POST /jobs` op=sync -> succeeded; both pages materialized under
    `cache/sources/wiki/space-ENG/`.
  - `POST /jobs` op=split -> succeeded, sections:
      confluence | space-ENG/page-1.html | confluence://127.0.0.1:8201/space-ENG/page-1.html@7
      confluence | space-ENG/page-2.html | confluence://127.0.0.1:8201/space-ENG/page-2.html@3
    Two pages, two different versions, one source — the property the ticket
    exists for, observed rather than asserted.

  Re-ran dev's cache-replacement mutation (1 fail) and added one across both
  page types: a unit losing its own version in `pages.units` -> 2 fail.

  I accept the `.html` extension decision. It follows the #143 contract the
  splitters depend on, and storing the storage format verbatim is more honest
  than a conversion hidden in a reader.

- 2026-09-23 po: CLOSED. This is the ticket that proves #143 was worth doing:
  a source type with no filesystem, no clone and no git anywhere in it, ingested
  through the same ops as a git repo, with no engine change. The
  materialize-then-read shape is now the settled answer for every API-only
  type, and #150 used it unchanged.
