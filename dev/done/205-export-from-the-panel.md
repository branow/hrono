---
id: 205
title: export from the panel — preview the shape, download the archive
priority: high
size: medium
depends_on: [204]
spec_refs: [REQUIREMENTS.md#10 (83-85, 71)]
---

## Context
Export is the MVP deliverable and the panel has no trace of it. A curator cannot see what an agent will be handed without a terminal.

## Description
An Export page, for every role (export is a reader endpoint today).

Choose the hop limit; see the shape #204 reports — levels, pages per level, widest page, file count, total size — before producing anything; browse the rendered pages in place (root page first, follow links); download the whole export as one archive.

The archive needs an endpoint (`GET /trees/{name}/export.zip` or a format parameter) because the dashboard has no build step and cannot zip in the browser. `hrono tree export` gains nothing the panel lacks and the panel offers nothing the CLI lacks: same options, same files.

Show a copyable snippet for handing the tree to an agent: the CLI export command for this tree and server.

Topics with an unusable brief (#217) are flagged in the preview, because the export's root page is the first thing an agent reads.

## Acceptance criteria
- [ ] the page shows the export's shape for the chosen hop limit before download
- [ ] the rendered pages can be read in the panel, links between them work
- [ ] the downloaded archive unpacks to the same files, byte for byte, as `hrono tree export` with the same options
- [ ] an unbuilt tree gets a next step, not a 404 page
- [ ] a reader can do all of it
- [ ] driven in a real browser, including the download

## Out of scope
Scheduling exports. Pushing an export anywhere.

## Review log
- 2026-10-03 po: authored from the requirements review and the UI review of the same day, at the user's request.
- 2026-10-03 dev: started (batch 204+205, the export chain).
- 2026-10-03 dev: done in d154a2d. `export/produce.py` is now the ONE producer: `produce(conn, tree, levels)` -> files + shape (+ the collapsed tree), `archive(files)` -> a zip with entries in path order, a fixed 1980 timestamp and utf-8 bytes, so the same export is the same archive. `GET /trees/{n}/export` and the new `GET /trees/{n}/export.zip?levels=` (Reader; Content-Disposition `<tree>-export-<levels>.zip`) both call it; the browser's cookie authenticates the zip like any API route. New page `/ui/trees/{t}/export` (Reader, an "Export" tab): hop-limit input (min 2) with "Show this shape"; stats: hops, pages per level, entries on the widest page (with the 40 budget in its hint), file count + bytes; an over-budget callout when the widest page exceeds it; a "Hand it to an agent" block with `hrono profile add <tree> --server <this server> --token <your token>` and `hrono tree export <tree> -o ./<tree>-export --levels N`; the rendered page in place (`prose.linked` — the same escaped CommonMark renderer, with each relative .md link rewritten to the panel's view of that file), crumbs back to root.md; Download .zip. Topics in the export whose brief is missing or was stored `flagged` are listed first with the reason and a link (#217's own definition of unusable can extend `_flagged` later). Unbuilt tree: 200 with "Nothing to export yet" and a link to the overview. Also: `render._heading` is public `heading` now (the page names flagged topics with it). Tests (tests/server/test_ui_export.py, all as a READER): shape shown before download; root -> child -> section by following the page's own links; the zip == `_materialize` of the manifest byte for byte, and two downloads are identical; flagged + missing briefs listed; unbuilt next step; hop limit chosen on the page drives the zip link and the snippet. Mutations, all KILLED: resolver returns the raw href; ignore `flagged`; ignore a missing brief; CRLF in zip entries; always show root.md; drop the unbuilt branch. Real browser (Chromium via playwright, uvicorn serving a maintain-built 40-file tree, signed in as a reader): Export tab -> 4 hops, 1/2/5/14 pages, widest 3, 62 files; set 2 hops -> 1/14, widest 14, 55 files; clicked a child, then a section, both rendered in place; Download .zip -> `default-export-2.zip`, 55 entries, byte-identical to the CLI's materialised folder for the same options. Screenshots: .autodev/board/evidence/205/export-root.png (first shot caught the cross-page fade mid-way; retaken), export-child.png. Gate: clean, 1632 passed.
- 2026-10-03 qa: PASS at d154a2d. Worktree gate, import path asserted inside it, bytecode off: ruff format --check clean, ruff check clean, pytest 1632 passed / 3 skipped. Re-ran dev's "resolver returns the raw href" -> killed. Real browser (Chromium/playwright) against a worktree server on a copy of the local test database, signed in through /ui/login as the READER `looker`: Overview -> Export tab (marked current) -> shape shown before any download (2 hops, 1 / 7, widest 32, 134 files, 785,079 bytes); the flagged-brief callout lists the one `asks-the-caller` topic; followed a child link in root.md, then a section link, both rendered in place with crumbs; set hops to 2 via the form -> URL carries levels=2; clicked Download .zip -> `click-export-2.zip`, unzipped and `diff -r` against `hrono tree export click --levels 2` from the same server through a real profile: identical, 134 files. Unbuilt tree `nosuch` -> 200 "Nothing to export yet" with a link to the overview. 1440/800, light/dark screenshots in evidence/205-qa/; the only horizontal overflow (4px at 1440, top bar wrap at 800) is the shell defect #215 owns. Links are resolved only to files in the manifest, anything else becomes `#page`; `page` outside the manifest falls back to root.md; html=False in the renderer; the token snippet carries a placeholder, never a token.
  Notes, not blocking: (1) depends on #204, which is kicked back — `/trees/{n}/export.zip` and this page call the same `produce()`, so #204's fix of the unbounded/exponential hop limit covers them, but the page's `max="30"` input is client-side only. (2) The "two downloads are identical" test does not guard the fixed zip timestamp: mutating `date_time=_EPOCH` to the current local time in export/produce.py leaves tests/server/test_ui_export.py and tests/export green (48 passed), because both downloads land in the same 2-second zip tick. Byte-identical ARCHIVES are dev's claim, not an AC (the AC is the unpacked files, verified above); assert the entries' date_time if the claim is to stand. (3) Polish seen through the render of #204: a title cut at 80 chars can end on a dangling " —" ("…Python's CLI framework —"), and a summary cut at 160 ends mid-phrase with no ellipsis.
- 2026-10-03 po: ACCEPTED at d154a2d. Looked at qa's 1440 screenshot: shape before download, flagged briefs first, the page reads in place. Every criterion holds. qa's note 2 (the fixed zip timestamp is unguarded) is accepted as is — the criterion is the unpacked files. Note 3 (titles cut on a dangling dash, summaries cut mid-phrase) goes to #212, which owns titles. What the screenshot shows about the DATA is not this ticket's defect and is serious: see #217.
