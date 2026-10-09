---
id: 183
title: the dashboard's node graph — lazy expand, and health you can see
priority: medium
size: medium
depends_on: [182, 064, 123]
spec_refs: [build-order.md#T50.1, build-order.md#T50.2]
---

## Context
T50.1 (lazy expand/collapse + fetch) and T50.2 (layout + health encoding).
**T50.3 (non-tree edges) is deliberately NOT here** — sibling proximity and
misfit-pull are similarity computations over brief vectors, which is a
different cost and a different question from drawing the hierarchy. It gets its
own ticket once this one exists to draw them on.

## The stack answer: SVG from Jinja, no library
A hierarchy laid out level by level is arithmetic, and SVG is markup. Rendering
it server-side means no graph library to vendor, review and pin — and the
expand/collapse state is a query parameter, so a link does what a click would.
That also makes every state of the graph bookmarkable and testable as HTML.

## Description
- `GET /ui/trees/{tree}/graph?open=1,5` — the tree from its root, drawing the
  children of every OPEN node and stopping there.
- Clicking a node toggles it in `open` and reloads; clicking its label goes to
  the topic page (#182).
- **Health you can see**: size by how much a topic holds, colour by whether its
  brief is stale (#064). A stale brief is the thing an operator is looking for.
- A topic with children that are not drawn says so, or an operator cannot tell
  a leaf from a closed branch.

## Acceptance criteria
- [x] The root is drawn with no `open`; its children appear when it is opened.
- [x] A closed node with children is visibly distinct from a leaf.
- [x] Node size reflects what the topic holds; a stale brief is distinguishable
      from a fresh one.
- [x] Every node links to its topic page.
- [x] Toggling is a link, so a graph state can be bookmarked and shared.
- [x] A tree with no nodes says so rather than drawing an empty canvas.
- [x] `ruff format`, `ruff check --fix`, `pytest` clean.

## Review log
- 2026-09-27 po: authored, with T50.3 split out.

- 2026-09-27 dev: done, commit 492ed5f. Driven on a real tree: closed draws 1
  circle, opening the root draws 5 circles and 4 lines, "holds 4" on the root
  and "holds 1" on each leaf.

  **SVG from Jinja, and the expand state is a query parameter.** That pairing
  is what removed the JavaScript: a toggle is a link, so there is no client
  state to manage and no library to vendor, review and pin. It also makes every
  view of the graph a URL someone can paste to someone else, and — the part
  that mattered while writing it — a testable string rather than a screenshot.

  Two decisions worth naming:

  - **`_roots` returns every unparented topic, not the first.** A tree
    mid-repair can have several, and that is precisely the state #124 and #163
    are about; drawing only the first would hide it. A test adds a second root
    and asserts both appear.
  - **A MISSING brief counts as stale.** An operator looking at the map for
    what needs work does not care whether a brief is out of date or was never
    written — both are "this topic cannot be read yet". The mutation that
    distinguishes them fails.

  `?open=` is parsed permissively: anything that is not an id is dropped, so a
  truncated or hand-edited URL draws a smaller graph and never a 500. A view
  cannot be invalid.

  Mutations, all killed: lazy expand removed -> 2 fail; a closed branch drawn
  as a leaf -> 1; a missing brief not counted stale -> 1; only the first root
  drawn -> 1; the `open` parameter unvalidated -> 3.

  One test I rewrote before trusting it: the toggle test first asserted a
  disjunction that was true either way. It now asserts the exact hrefs — the
  root's link ADDS it when closed and REMOVES it when open — so the toggle is
  measured rather than described.

  Gate clean: 1286 passed, 2 skipped.

- 2026-09-27 qa: PASS, to po-review. Gate: ruff clean, 1286 passed. Re-ran N1
  (lazy expand removed) — 2 fail. Drove it against a real tree and the counts
  match the fixture's shape exactly.

  The decision I want endorsed is drawing EVERY root. It would have been
  natural to write `roots[0]` — a tree has a root, singular, and the recursion
  that builds it says so. But the map's job is to show an operator what is
  actually there, and "there is a second thing here that nothing points at" is
  the single most valuable thing it can say. #124 and #163 both shipped over
  exactly that state.

  Splitting T50.3 out was right. Non-tree edges are similarity computations per
  page load, which is a different cost profile and a different question from
  drawing a hierarchy; bundling them would have made this ticket's failure
  modes impossible to separate.

- 2026-09-27 po: CLOSED. The centrepiece view exists and cost no JavaScript.

  When the stakeholder chose Jinja + HTMX, the open question in my mind was
  this ticket — a node graph is the thing that usually forces a client
  framework. It did not, because the two hard parts turned out to be arithmetic
  (positions) and markup (SVG), and the interactive part is a link. Four views
  in, HTMX still has not been needed.

  T50.3 (non-tree edges) is authored as #184. T52, T54, T55 and T56 remain.
