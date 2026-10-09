---
id: 156
title: rename a topic, override its brief, and hand it back to automation
priority: high
size: medium
depends_on: [154]
spec_refs: [build-order.md#T46, implementation-notes.md]
---

## Context
The first three manual-adjustment endpoints, and the ones that make #154
visible: `PATCH /trees/<name>/nodes/<id>` (rename), `PUT .../brief` (override,
pins), `POST .../unpin` (release). Admin-gated, per the spec.

## Design, decided
- A node has NO stored title today — `export/render` derives one from the
  brief's first real line. Rename therefore adds a nullable `title` column,
  and the renderer prefers it when set. A rename pins the brief, because a
  regenerated brief would otherwise re-derive a title the operator just
  replaced.
- Overriding a brief writes the text through the same path `brief` writes
  (so its passages and FTS rows are rebuilt, #071/#125) and pins it in the
  same transaction.
- `unpin` releases every pin on the node — brief, membership and parenting —
  because a user who says "hand this back" means the node, not a kind they
  have never seen named.

## Acceptance criteria
- [x] `PATCH` sets a title; the export renders it instead of the derived one.
- [x] `PUT .../brief` replaces the text, rebuilds its passages, and pins it;
      a following `brief` run leaves it alone.
- [x] `POST .../unpin` releases it; the next `brief` run regenerates it.
- [x] All three are admin-only; a writer gets 403 and a reader 403.
- [x] Unknown node -> 404; the tree name is honoured, not ignored.
- [x] `ruff format`, `ruff check --fix`, `pytest` clean.

## Out of scope
Notes (#157) and structure surgery (#158-#160).

## Review log
- 2026-09-23 po: authored.

- 2026-09-23 dev: `hrono/edits.py` holds the operations (edit + pin in one
  transaction, always) and `server/edits.py` is a thin admin-gated shell over
  them. A node gained a nullable `title` (migration 0032) and the export
  prefers it; a rename pins the brief, because the derived title comes from
  the brief's first line and leaving that free hands the naming back to the
  model on the next run.

  An overridden brief is written through the same path `brief` writes — the
  node:// passages and their FTS rows are rebuilt — so recall answers from the
  operator's words rather than from the summary they replaced. Its provenance
  records `hand-edited` rather than a model name: a brief nobody can attribute
  is worse than one attributed to a human.

  Mutations run, all killed: a rename not pinning -> 1 fail; the export
  ignoring a stored title -> 1; an overridden brief not re-indexed -> 1; the
  tree in the path ignored -> 2.

- 2026-09-23 qa: PASSED, driven live on 8303 against a seeded two-node tree:
  - `PATCH .../nodes/1 {"title": "Deploys (platform-owned)"}` -> 200, and the
    EXPORT then renders that node's directory as `deploys-platform-owned-1/`
    with the operator's title, not the derived one.
  - `PUT .../nodes/2/brief` -> 200, and the export shows the operator's words
    where the model's summary was.
  - both pins present in the database with their reasons ("renamed by hand",
    "brief written by hand").

  Added a mutation dev did not state: `unpin_all` releasing parenting but not
  the brief -> 1 fail. "Hand this back" has to mean the node, and a partial
  release would leave the operator's brief frozen with no way to tell.

  ONE OBSERVATION, not a defect and not blocking: a rename changes the export
  DIRECTORY name, so an agent holding a deep link to the old path will not find
  it. That is the right behaviour — navigation should follow the title — but it
  is worth the PO knowing before a dashboard starts handing out links.

- 2026-09-23 po: CLOSED. The rename-changes-the-path observation is correct and
  I am accepting it deliberately: the export is regenerated whole and its paths
  have never been stable identifiers — the URI is (#144). If a dashboard later
  wants durable deep links it should link by node id, and that is M10's
  problem to solve knowingly rather than ours to pre-solve here.
