---
id: 157
title: a human note on a node or section, visible in the export
priority: medium
size: small
depends_on: [154]
spec_refs: [build-order.md#T46, implementation-notes.md]
---

## Context
`POST /trees/<name>/{nodes|sections}/<id>/notes { "text": "..." }`. The spec is
explicit about why this is not just a comment field: "Notes are
export-visible: a human 'deprecated, use X' annotation flows into the rendered
tree so the traversing agent sees it." The note is FOR the agent, not for a
dashboard sidebar.

## Design, decided
- Notes are append-only history, one row per note: an operator's later
  correction should not silently erase the earlier note the team is reading.
  The export renders them newest first.
- A note does NOT pin. It is an annotation, not a correction of the map, and
  pinning a node because someone left a comment would quietly freeze the tree.
- Rendered under their own heading so an agent can tell a human's words from a
  model's summary. That distinction is the whole value.

## Acceptance criteria
- [x] A note can be added to a node and to a section; both are admin-gated.
- [x] `GET` on the entity returns its notes, newest first.
- [x] The export renders a node's notes in its page, marked as human notes and
      distinguishable from the brief.
- [x] A second note does not replace the first.
- [x] Deleting a node removes its notes.
- [x] `ruff format`, `ruff check --fix`, `pytest` clean.

## Out of scope
Editing or deleting a note (M11 if anyone asks).

## Review log
- 2026-09-23 po: authored.

- 2026-09-23 dev: `notes` is an append-only table with the same two triggers
  pins have, so a retired node or a deleted section takes its notes with it.
  The renderer already accepted a `notes` mapping (stubbed when the export was
  built); this fills it, and `GET /trees/{name}/export` passes it in.

  Writing is admin-gated, reading is not — an operator should see what a
  colleague wrote without holding admin. A note does NOT pin: annotating a
  topic is not correcting the map, and a comment that froze a tree against
  every later update would be a trap for whoever left it.

  Mutations run: notes oldest-first -> 1 fail; a note replacing the last one
  -> 1; a retired node keeping its notes -> 1.

  ONE SURVIVED AND I FIXED THE TEST, not the claim: removing
  `notes=notes.rendered(...)` from the export ENDPOINT left everything green,
  because my render test called `render()` directly. The renderer was proven
  and the surface an agent actually reads was not. There is now a test that
  drives `GET /trees/{name}/export` and finds the words in the returned files;
  that mutation fails it.

- 2026-09-23 qa: PASSED, and the export drive is the proof: after one POST the
  rendered `deploys-platform-owned-1/brief.md` carries

      ## Notes

      Deprecated. Use the platform pipeline instead.

  under its own heading, beneath the model's summary — which is exactly the
  spec's reason for the feature ("so the traversing agent sees it").

  Re-ran dev's newest-first mutation (1 fail) and added one they did not:
  `notes.rendered` returning nothing -> 3 fail.

  Dev's own surviving mutation is the one worth noting: the renderer was proven
  and the ENDPOINT was not, and the fix was a test against the real surface
  rather than a weaker claim. That is the right instinct and the same lesson
  #144 put in the prompts.

- 2026-09-23 po: CLOSED. T46 is complete.

  The decision not to pin on a note is the one I want kept: hrono's pins are a
  promise that the pipeline will not overrule a human, and spending that
  promise on a passing comment would make operators afraid to annotate
  anything. A note is a message to the next reader, and the export is where
  they are reading.
