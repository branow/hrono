---
id: 212
title: topics you can tell apart, and a map whose labels do not collide
priority: high
size: big
depends_on: []
spec_refs: [src/hrono/server/where.py, src/hrono/server/overlays.py]
---

## Context
On the review tree seven topics are called `/ + docs`, `src/click`, `src/click`, `src/click`, `src/click`, `docs`, `docs`. The label is where the files live, which is the one thing sibling topics share. With overlays on, arcs and their labels run through the topic labels.

## Description
Names. A topic's primary name is what it is about — a short title derived from its brief (the export already derives one; use the same rule so the panel and the export agree). Where it lives becomes the secondary line. A hand rename still wins. Two siblings never show the same primary name; when titles collide, disambiguate.

Use the name everywhere a topic is shown: map, side panel, "Beneath" list, breadcrumbs, search results, triage.

Map layout. Edge labels and arcs must not cross topic labels or each other: route overlay arcs below the label band and place edge labels where nothing else is. The drawing fits itself to the window on load and when the panel opens, and can be reset. Long names truncate with the full name on hover.

Legend entries become whole phrases.

Check the result on the largest tree available, not only the 8-topic one; the review could not.

## Findings from the UI review (2026-10-03)
Seen by driving the dashboard in headless Chromium against a copy of the `~/hrono-click` database (tree `click`: 8 topics, 2 levels, 126 sections, 3 runs), as admin and reader, at 1440px and 800px, light and dark. Screenshots are in `.autodev/board/ui-review-2026-10-03/`. Severity: **A** wrong or broken, **B** confusing enough to cost time, **C** polish. The tree is small, so anything that only breaks at scale was not seen; forms were opened, not submitted.

- **A** Topics are named by where their files live, so the seven topics are `/ + docs`, `src/click` x4, `docs` x2. They cannot be told apart, on the map, in the panel, or in "Beneath". Screenshot: `admin-map-1440-light.png`.
- **A** With overlays on, edge labels and arcs run through the topic labels and through each other ("18 sections" is struck through; two "0.88 similar" labels collide). Screenshot: `admin-map-edges-1440-light.png`.
- **B** The tree is drawn in the middle of an otherwise empty board and does not fit itself to the window; with the panel open it shifts and stays small.
- **B** The legend explains marks with fragments ("opens", "where it lives", "size").
- **Risk** Label collision and fit were seen at 8 topics; at 200 the same layout has not been looked at.

## Acceptance criteria
- [ ] no two sibling topics display the same primary name on a real tree
- [ ] the panel and the export use the same title for the same topic — one function, tested once
- [ ] with all overlays on, no label overlaps another label or a topic label — asserted geometrically in a test over the drawn positions, not by eye
- [ ] the map fits the window on load and with the panel open
- [ ] screenshots on a tree of 8 topics and on the largest available, in the Review log

## Out of scope
Generating titles with a new LLM call. A new graph library.

## Review log
- 2026-10-03 po: authored from the requirements review and the UI review of the same day, at the user's request.
- 2026-10-03 po: from qa's review of #205 — the shared title rule cuts at 80 chars and can end on a dangling " —"; the one-line summary cuts at 160 mid-phrase with no ellipsis. Fix both here, since this ticket owns the title function.
- 2026-10-03 dev: started.
- 2026-10-03 dev: done in b4555d4. Reproduced at HEAD first: the map still labelled by `where` (graph.py docstring chose it in #198).
  NAMES — `hrono/naming.py` is the one rule: `heading` (moved out of export/render: the hand-given title, else the brief's first non-boilerplate sentence, now ending "…" when cut) and `names(conn, ids)`: a title shared (case-insensitively) by children of the same STORED parent carries " (#<id>)" — per-topic, so every page gets the same answer. Used by: the map (line 1 = name, line 2 = folder, line 3 = count), the side panel (h2 = name, "in <folder>" under it; children named, folder in their detail line), the topic page (h1, crumbs, children, move/merge pickers; folder secondary), the Ask page, the Export page's flag list, and the exported index pages' child entries. On the map a label is cut to its slot without losing the "(#id)" (`fitted_name`), and two sibling names that only differ past the slot get the number too (`_labels`). Map slot 150->170px, 21 chars.
  LAYOUT — `server/labels.py` estimates every text box (mono fonts: 7.0/6.4px per char) and a topic's furniture (circle, 3 lines 14px apart, chevron). Overlay arcs now LEAVE each topic below its furniture (same-row arcs bow from there; cross-level lines run from under the upper topic's furniture to the top of the lower circle), and each overlay label tries points along its own path, middle first, against every topic box and every label already placed, walking down if all are taken. Canvas height follows the deepest point of any curve. Map FITS the window on load and after the panel opens/closes (viewBox scaling, floor 0.35, refit on resize) with an "Actual size / Fit to window" button. Legend in whole phrases ("a bigger circle holds more", "its brief needs writing", "the chevron opens a topic", "each topic: its name, folder and size", "scroll or drag to move around"). Panel now also counts a non-brief (#217) as needing one.
  Tests (tests/server/test_map_labels.py): no two siblings share a name on a weak-model tree (and a unique title is left alone); cut labels stay distinct and within the slot; names that only differ past the slot are told apart; the export's index entries use the same `names`; GEOMETRIC: 36 overlay links (every pair of 9 drawn topics, all three kinds) placed — no link label overlaps another, none overlaps any topic box, no two topic text lines overlap; same-row arcs start below their topic's words. Existing where-label tests now read `place`. Mutations, all KILLED: no sibling disambiguation; no cut-collision disambiguation; fitted_name drops the number; place() ignores occupied spots; placed labels not added to the taken set; export entries use the raw heading; arcs start at the circle centre (survived first — fixed with the arc test).
  Real browser (Chromium, uvicorn, admin) on two trees built from THIS repository with a stand-in writer that titles topics by a file they cover: "small" = src/hrono/[ejr]* (27 topics), "large" = src/** (132 topics, the largest I could build — the review copy has 8). Measured in the page with getBoundingClientRect over every <svg text>: small map 0 overlapping, small with all topics open + overlays 96 words 0 overlapping, large all open + overlays 494 words 0 overlapping, both with the panel open 0. Both opened fitted ("Actual size" offered). Screenshots .autodev/board/evidence/212/{small,large}-{map,edges,panel}.png. Honest limit: fitted at 132 topics the text is small (0.35 floor); "Actual size" is one click. Gate: clean, 1676 passed.
- 2026-10-03 qa: PASS at b4555d4, with observations for the PO below. Worktree gate, import path asserted inside it, bytecode off: ruff format --check clean, ruff check clean, pytest 1676 passed / 4 skipped. Re-ran dev's "place() ignores occupied spots" -> killed; new mutation "no walk-down when every candidate is taken" (labels.place returns the last candidate) -> killed (1 failed). Real browser as admin on a copy of ~/hrono-click (worktree server): the 8 topics now read by name, folder second, count third; no two siblings share a primary name; with Expand all and both overlays on (misfiled + near-duplicates), getBoundingClientRect over every SVG text: 31 texts, 0 overlaps; with the side panel open, 0 overlaps. Legend is whole phrases. Titles cut with "…" (the #205 dangling-dash finding is fixed in the shared `naming.title`). Screenshots in evidence/212-qa/ (212-crop.png is the overlay band at 2x).
  Observations, not blocking — the ACs are about LABELS and they hold, but a person will see these: (1) overlay LINES still pass through other links' labels (212-crop.png: the orange "3 chunks nearer" arc runs through the left "0.85 similar"; the long "0.74 similar" arc crosses two others) — the description's "arcs must not cross … each other" is not achievable in general and was not asserted; (2) dev's own 132-topic evidence (evidence/212/large-edges.png): with everything expanded and overlays on, the arcs form a solid band under the bottom row and the drawing runs past the right edge at the 0.35 scale floor — on load (3 drawn) it fits, as the AC asks; (3) after clicking an overlay toggle its hint bubble stays open and is cut off at the right edge of the viewport (#215's hint-bubble AC); (4) the overlay label still says "chunk(s) nearer" (#216's banned word); (5) on the review tree every name is a model refusal cut to 21 chars — #217/#221 data, not this ticket's naming rule.
- 2026-10-03 po: ACCEPTED at b4555d4. Every criterion holds as measured: one naming rule shared by panel and export, siblings kept apart, zero label overlaps asserted over the drawn positions, fits on load. qa's observations 3 and 4 belong to #215 and #216, which already own them. Observations 1 and 2 are real and are a new ticket, #222: the ACs were about labels, and at 132 topics with overlays on the map is a solid band of arcs that a person cannot read (evidence/212/large-edges.png), with names cut at 21 chars that all share a prefix.
