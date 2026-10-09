---
id: 150
title: a notion source ingests the pages shared with its integration
priority: high
size: medium
depends_on: [149]
spec_refs: [build-order.md#T43, implementation-notes.md]
---

## Context
The second API-only type, and the one that proves #149's materialize-then-read
shape generalizes rather than being Confluence's shape in disguise.

## Design, decided
- Auth is a bearer integration token; no base url (always api.notion.com).
  An integration only sees what is shared with it, so an empty scope or
  `[{"type": "all"}]` means "everything this token can see", enumerated
  through `POST /v1/search`.
- v1 selectors: `page` (by `id`) and `database` (by `id`).
- A page is one unit, path `page-<id>.md`, because Notion's blocks render to
  markdown-shaped text and the splitters pick by extension.
- Version is the page's `last_edited_time`, per the spec's identity rule, and
  is carried per unit.
- Identity: `notion://<workspace>/page-<id>.md@<last_edited_time>`, where the
  workspace comes from the token's own `GET /v1/users/me` bot workspace name —
  never from user config, which could disagree with the token.
- Block rendering is deliberately small: paragraph, heading 1-3, bulleted and
  numbered list items, to-do, quote, code. Anything else contributes its plain
  text if it has any. Nested children are followed one level at a time through
  `GET /v1/blocks/<id>/children`.

## Description
Model variant, validator entry (the token authenticates), syncer entry
(enumerate, fetch blocks, render, write to the cache, record id -> edited time)
and reader entry, exactly as #149.

## Acceptance criteria
- [x] A `notion` source registers, validates and stores its token encrypted.
- [x] `sync` materializes every scoped page as rendered text; `split` stores
      sections addressed `notion://<workspace>/page-<id>.md@<edited time>`.
- [x] The block renderer covers the listed types and drops nothing silently:
      an unknown block with text contributes it.
- [x] Driven over a real local HTTP round trip (#108).
- [x] `ruff format`, `ruff check --fix`, `pytest` clean.

## Out of scope
- Databases as structured rows (a database contributes its pages).
- Comments, files, and rich formatting beyond plain text.
- Live verification against a real workspace.

## Review log
- 2026-09-23 po: authored.

- 2026-09-23 dev: the renderer is where a notion page is won or lost, so it is
  the part with the most tests: the seven block kinds the ticket names, nested
  children followed depth first, and an UNKNOWN block contributing its plain
  text rather than vanishing (notion adds block types; losing a page's content
  to one is worse than rendering it unstyled).

  One contract change, and it was not optional: `Reader.instance` now takes the
  CACHE as well as the config. A notion workspace is a property of the TOKEN,
  not of user config — the spec addresses pages `notion://<workspace>/...` and
  config could disagree with the token — so the sync asks `GET /v1/users/me`
  once and records the answer beside the page map. Resolving it by calling the
  API on every split would make an ADDRESS depend on a live request, and a
  workspace renamed between two calls would split one source across two
  identities. The other four readers ignore the argument.

  Mutations run, all killed:
  - every prefix dropped from the renderer -> 2 fail.
  - an unknown block contributing nothing -> 5 fail.
  - nested blocks not followed -> 1.
  - the search cursor ignored -> 1.
  - the sync never recording the workspace -> 2.
  - an unknown selector silently meaning "everything" -> 1.

- 2026-09-23 qa: FOUND ONE, fixed in the same commit series (it is this
  ticket's own defect, and a one-line one).

  Driven end to end against a local notion stub, the address came out as
  `notion://Acme HQ/page-p1.md@2026-09-20T09:00:00.000Z` — with a SPACE in it.
  A workspace name is free text and an instance lands verbatim in a URI, so
  "Acme HQ" produced something that is not a URI at all. `notion_instance` now
  percent-encodes it (`notion://Acme%20HQ/...`); the cache keeps the name as
  the provider spelled it, so only the address is escaped. Mutation: return the
  raw name -> 2 fail.

  Everything else passed. The rendered page came back as expected:
      # Runbook
      (blank)
      When the queue backs up, drain it before restarting anything.
      (blank)
      - Check the worker log first
  Re-ran dev's unknown-block mutation (5 fail). The `Reader.instance` contract
  change is justified and I would have insisted on it: resolving a workspace by
  calling the API on every split would make an ADDRESS depend on a live
  request.

- 2026-09-23 po: CLOSED. M8's reader work is done for every type we can build
  without live credentials.

  The URI defect qa caught is worth remembering beyond this ticket: hrono's
  identity scheme assumes its parts are URI-safe, and that assumption held for
  four source types because hosts and paths happen to be safe. The first source
  whose instance is FREE TEXT broke it. Any future type whose identity comes
  from a human-typed name must escape it the same way — noted here rather than
  in a new ticket, because the rule is one line and the next reader of
  `notion_instance` will meet it.
