---
id: 222
title: the map at scale — overlays and names a person can read on 100+ topics
priority: medium
size: medium
depends_on: [212]
spec_refs: [#212, REQUIREMENTS.md#4 (21), REQUIREMENTS.md#7 (46)]
---

## Context
Spun off from the #212 PO review. #212 made labels never overlap and the
drawing fit on load, and both hold. But on dev's own 132-topic evidence
(`.autodev/board/evidence/212/large-edges.png`) the map with everything
expanded and both overlays on is a solid orange band of arcs under the bottom
row, the drawing runs past the right edge at the 0.35 scale floor, and every
name is cut at about 21 characters so a row reads "Handles assorted mat…",
"Handles assorted mat…", "Handles assorted mat…". The 8-topic tree looks fine;
the product has to work on the trees people actually build.

## Description
Make the overlays and the names legible at a hundred topics or more, without
changing what they mean.

Overlays: an arc exists to point at ONE repair. When more than a handful are
drawn, draw them as a summary instead — per topic, a count chip ("3 misfiled",
"2 near-duplicates") that opens that topic's arcs alone on click or hover; or
cap the drawn arcs to the strongest N with a "+K more" control. The toggles
say how many there are before drawing them. Arcs never cross a label (the
labels module from #212 already knows where every label is).

Width: at the scale floor, a row wider than the window scrolls or pages
deliberately — a visible horizontal scrollbar, or the row folds under a
"+K more topics" affordance — rather than drawing past the edge.

Names: the cut length adapts to the room a column has, and when several
siblings share their first words the shared prefix is dropped from the
displayed cut so the distinguishing part survives ("Handles assorted
material" x3 -> what follows). Full name on hover stays.

Use the largest real tree available (dev's 132-topic `default`) for the
screenshots, not the 8-topic one.

## Acceptance criteria
- [ ] at 132 topics expanded with both overlays on, no more arcs are drawn than a stated cap, and the rest are reachable per topic
- [ ] no drawn arc crosses a label — asserted geometrically, as #212 did for labels
- [ ] nothing is drawn past the right edge; a too-wide row has a visible way to reach the rest
- [ ] siblings sharing a prefix display a cut that differs between them
- [ ] the 8-topic tree looks as it did after #212 (no regression; screenshots both)
- [ ] before/after screenshots on the 132-topic tree in the Review log

## Out of scope
Changing what misfiled / near-duplicate / propagation mean. A new graph
library. Non-map views (#208 owns the outline).

## Review log
- 2026-10-03 po: authored from the #212 review; observations 1 and 2 of qa's PASS entry there.
