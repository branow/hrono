---
id: E014
title: the map at scale — overlays and names readable on 100+ topics
priority: medium
depends_on: []
requirements: []
---

## Goal
On #212's 132-topic evidence the map with overlays is a solid band of arcs,
runs past the right edge, and every name is cut to "Handles assorted mat…".
Make it legible without changing meaning. Detail: archive/222.

## Tickets

### 1 overlays summarise past a cap
Done when:
- [ ] at 132 topics, both overlays on, arcs ≤ a stated cap; the rest reachable
  per topic as a count chip
- [ ] no arc crosses a label — asserted geometrically

### 2 width and names
Done when:
- [ ] nothing drawn past the right edge; a too-wide row has a way to the rest
- [ ] siblings sharing a prefix show cuts that differ
- [ ] the 8-topic tree unchanged; before/after screenshots in evidence/E014/
Look at: server/templates/graph.html, evidence/212/

### 3 the graph test that flakes
Change: confirm whether the `browser` fixture writes through `browser.conn`
while the worker polls (#194 shape); stop the worker first or write elsewhere.
Done when:
- [ ] cause stated in the Log; `test_two_directories_of_the_SAME_NAME_are_said_once`
  passes 50 full-file runs in a row
Look at: tests/server/test_ui_graph.py, the `browser` fixture

## Out of scope
- outline view (E011)

## Log
- 2026-10-03 po: created from #222.
- 2026-10-03 po: folded backlog test-ui-graph-same-name-flakes as ticket 3.
- 2026-10-03 po: starting — touches graph.html and test_ui_graph.py; no overlap with E005/E017/E018.
- 2026-10-03 dev: round 1 started, worktree .claude/worktrees/E014.
- 2026-10-03 dev: ticket 1 + 2 e4eca67 (one commit: they share graph.html/base.html). Cap ARC_CAP=12, strongest per kind in rotation; an arc that would cut a topic word or a placed arc label steps down lanes, else is left out and counted as "+N arcs" chip per topic (?arcs=<id> shows that topic alone). Names: shared leading words dropped when a cut is needed, budget grows with the column's room. Off-window: always-visible scrollbar plus "N more topics" buttons each side. Verified on a 133-topic scratch tree (before/after in evidence/E014/, 636 arcs -> 11); drove chip click and the beyond button in Chromium. Mutations (each fails a test): cap off, row-crossing check off, level-crossing check off, unseen count one-sided, rank reversed, prefix drop off, budget fixed, chip filter inverted, under-cap passthrough off.
- 2026-10-03 dev: visible change on the 8-topic tree, by design: the root shows "Everything in the repository." whole (its column is wide) and a proximity arc steps one lane down where it ran through the "1 chunk nearer" label (before: struck through). Otherwise the SVG is identical. Pull/proximity arcs are 11 not 12 at 133 topics because one was left out for crossing.
- 2026-10-03 dev: ticket 3 872fc9b. Cause: the `browser` fixture in test_ui_graph.py wrote through browser.conn while the worker polled it (#194 shape; test_ui_graph_overlays already stopped the worker). Fix: stop and join the worker in the fixture. Honest limit: the flake did NOT reproduce here on the unfixed fixture (50 whole-file runs, and 150 single-test runs under 6x parallel load), so "cause" is by the #194 mechanism, not by observed failure; the fixed file passed 50 full-file runs twice.
- 2026-10-03 qa: round 1 FAIL at e4eca67 — an arc runs through another arc's label when arcs fan from one topic (the ?arcs= view; 4 of 9 on a 133-topic tree, seen in Chromium), tickets 1 and 2 share one commit, and the 'Arcs of X. only' button copy. Mutations re-run: cap off (killed), level-crossing check off (killed); beyond() JS dead survives, as all map JS does (no browser tests in the suite). Flake: 25 full-file runs green. Findings in the qa verdict.
- round 2: 104de56 labels clear of drawn arcs (test: fan from root, bites when place() ignores lines), button copy reworded; commit split (finding 2) not done: dev.md forbids rewriting a commit qa saw
- 2026-10-03 qa: round 2 FAIL at 104de56 — finding 1 fixed (Chromium on a 133-topic tree, arcs fanning from the root and from an upper: no arc through another arc's label; the same probe on e4eca67 finds 3-6), but the new tooltip reads 'Everything in the repository.. Click' (graph.html:56), so finding 3 is only half fixed. Commit split left to the orchestrator/PO (dev.md forbids the rewrite). Mutations: place() without drawn arcs (killed), lines.append removed (killed); curves checked on their first segment only survives. Findings in the qa verdict.
- dev round 3: tooltip of the way-back button now ends with the name (46c0d91); commit split left for orchestrator/PO.
- 2026-10-03 qa: round 3 PASS at 46c0d91 — round-2 finding 1 fixed: drove the ?arcs= view of a 133-topic tree in Chromium; the way-back tooltip reads 'Click to draw the strongest arcs of the whole map again. Showing only the arcs of: <name>', with no '..', and clicking it returns to the whole map (button gone). Format/check clean, 158 affected tests green, merges cleanly with main. Mutation: restoring 104de56's wording fails the new assertion (killed). For the PO: tickets 1+2 share commit e4eca67 (dev.md forbids the rewrite; authorize a split at merge or accept it), and the 8-topic tree is not unchanged (root name whole, one proximity arc a lane lower; evidence/E014/8-edges-*.png).
- 2026-10-03 po: ACCEPT at 46c0d91 — 133-topic map goes from a band of arcs to 11 plus +N chips, edges say "53 more topics", sibling names read apart, guide explains chips. 8-topic diffs (whole root name, one arc a lane lower) follow ticket 1's no-crossing rule: accepted. Tickets 1+2 sharing e4eca67 accepted, no split. Flake cause by #194 mechanism accepted.
- merged to main at c0a47bf
