---
id: 182
title: the dashboard's topic page — brief, members worst-fit first, a section preview
priority: medium
size: medium
depends_on: [180, 113, 129]
spec_refs: [build-order.md#T51]
---

## Context
T51: "Node detail + members (misfit sort) + section drawer". Before T50,
because the graph links into this page and a link to nothing is not worth
drawing.

## Description
- `GET /ui/trees/{tree}/nodes/{id}` — one topic: its title and brief, where it
  sits (parent, children), its pins and notes, and its members.
- **Members worst-fit first.** `node_members.assignment_similarity` is the
  score a chunk was attached with; a NULL means a confident density-core
  placement (0009_nodes.sql). So: attached members ascending by score, then the
  core ones. The operator opening a topic to see whether it is right wants the
  chunk least likely to belong at the top, not the alphabetically first.
- A section PREVIEW inline under each member, not a full render: a section is
  ~10 KB and a topic can hold thirty. The preview keeps the topic's context on
  screen; a link goes to the whole thing.
- Forced members (#113) are marked — a forced placement is one nobody scored.

## No HTMX yet, and say why
The stack is "Jinja + HTMX" and this is the view where a pane-swap was
expected. A `<details>` element with a server-rendered preview does the same
job with no JavaScript and nothing vendored, so HTMX still has not earned its
place. It lands when a view needs an update a link and a `<details>` cannot
do — and when it does, it is a vendored file this repo serves.

## Acceptance criteria
- [x] The page shows the brief, the parent, the children and the members.
- [x] Members are ordered worst-fit first, with core placements last.
- [x] A forced member is marked as such.
- [x] A section preview is available inline without leaving the page.
- [x] Pins and notes on the topic are visible.
- [x] An unknown node, or one from another tree, is a 404 page not a traceback.
- [x] `ruff format`, `ruff check --fix`, `pytest` clean.

## Review log
- 2026-09-27 po: authored.

- 2026-09-27 dev: done, commit 9ee8897. Driven on a real server: the topic
  page renders its title, level, "chunks (2)", the worst-fit-first note and the
  members; a node from another tree is a 404.

  **The ordering is the whole view and it is the opposite of the obvious
  query.** `assignment_similarity` NULL means a CONFIDENT density-core
  placement (0009_nodes.sql), and SQLite sorts NULLs FIRST — so a plain
  `ORDER BY assignment_similarity` puts the surest members at the top of a list
  whose purpose is "show me what probably does not belong". The query sorts on
  `IS NULL` first, and the mutation that removes that fails the test.

  A forced member (#113) is marked rather than scored, because nobody scored
  it; a score of 0.00 would be a number we made up, which is the same rule
  #179 applied to dollars.

  **Still no HTMX**, and the ticket says why: a `<details>` with a
  server-rendered preview does this job with no JavaScript and nothing
  vendored. It lands when a view needs something a link and a `<details>`
  cannot do.

  One test I added beyond the criteria, and it is the one I would keep if I
  could keep only one: **section content is UNTRUSTED** — it came out of
  somebody's repository — and the preview renders it verbatim. Jinja
  autoescapes, so a `<script>` in a source file becomes `&lt;script&gt;`. The
  test asserts both halves, so the day someone reaches for `|safe` on that
  field it fails.

  Mutations, all killed: nulls sorting first -> 1 fail; the whole section
  inlined -> 1; another tree's node rendering -> 2.

  Gate clean: 1276 passed, 2 skipped.

- 2026-09-27 qa: PASS, to po-review. Gate: ruff clean, 1276 passed. Re-ran M1
  (nulls sorting first) — fails, so the ordering claim is real and not an
  accident of insertion order.

  The escaping test is the right instinct and I want to state why it matters
  more here than on most pages: this is the first view that renders CORPUS
  CONTENT. Everything before it showed hrono's own strings — statuses, counts,
  paths we generated. A section body is a file out of a repository the operator
  ingested, and the dashboard shows it to someone holding an admin cookie. The
  test pins the property rather than the implementation, so it survives a
  template rewrite.

  Checked the fixture against production shapes (#144): `add_leaf_node` takes
  `(section, FORCED, similarity)` and sets `attached` from `forced` — dev's
  first fixture read the middle field as `attached` and produced four forced
  members, which is a state production does not make. Corrected before the
  tests were trusted, and the comment now says which field is which.

- 2026-09-27 po: CLOSED. Three views, and the dashboard can now answer the
  question it exists for: is this topic right?

  "Worst fit first" is the whole ticket and it is a judgement about what an
  operator is doing when they open a topic — not browsing it, auditing it. A
  list sorted by id would have satisfied a literal reading of "members" and
  been useless.

  HTMX still has not earned its place and I am glad the ticket says so out
  loud. The stack decision named it; a decision to use something is not an
  obligation to use it before anything needs it.
