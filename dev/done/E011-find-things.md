---
id: E011
title: find things — text search, an outline view, file to topic
priority: medium
depends_on: [E005]
requirements: [25, 26, 27]
---

## Goal
The map is the only way in. Give readers a search box, a list view that works
at 500 topics, and a way from a known file to where hrono filed it.
Detail: archive/208.

## Tickets

### 1 search on every page
Change: top-bar search over topic names, briefs, section paths and text (the
FTS index recall keeps); results grouped by kind.
Done when:
- [ ] a word only in a section's text finds the section and its topic
- [ ] latency on the largest available tree measured and logged
Look at: src/hrono/recall (FTS), server/ui/views.py

### 2 outline view
Done when:
- [ ] the whole tree as a collapsible list (name, size, health); rows open topics

### 3 file lookup
Done when:
- [ ] a path/prefix lists its sections and their topics; parked says so;
  unknown says not ingested
- [ ] all three work for a reader

## Out of scope
- semantic search (that is Ask)

## Log
- 2026-10-03 po: created from #208.
- 2026-10-03 po: starting (1 free slot; mostly new views — outline, lookup, search; only the top-bar touch overlaps E007/E012 shell, keep it small).
- 2026-10-03 dev: round 1 started, worktree .claude/worktrees/E011.
- 2026-10-03 dev: tickets 1-3 in one commit 0a8b938 (they share the Find tab, sub-nav and server/find.py; split would not build). Verified: 26 new tests through a tree built by maintain (text-only word finds section+topic, other-tree and other-tree-parked scoping, renamed title, brief not crowded out, outline at 526 topics, files exact/prefix/unknown/parked), tests/server 539 pass, real-browser overflow test over the 4 new routes at all widths. Mutations bitten: tree scope (3 spots), title search, outline health, lookup excluding briefs; one dead guard (title IS NOT NULL) removed.
- 2026-10-03 dev: latency (ticket 1), search on a copy of the local demo database (852 sections, 7.8k passages): 11-55 ms; inflated 20x (17,312 sections, 163k passages): 215-385 ms typical, 1.5 s worst for the word "the" (matches everything); outline 240 ms at that size, lookup 44 ms.
- 2026-10-03 qa: round 1 FAIL at 0a8b938 — file lookup not scoped to the tree, untested _homes tree scope (mutation survives), one commit for three tickets; drove search/outline/files as a reader on a copy of the local demo database in chromium; re-ran dev's brief tree-scope mutation (killed) and my _homes scope mutation (survived). Findings in the qa verdict.
- 2026-10-03 dev: round 2 fix e259d2c — lookup scoped to the tree's sources or sections it files/holds pending (tree 2 + shared-path test), _homes tree scope tested, search box asserted on /ui, graph, ask, topic, jobs, guide; mutations bitten: _homes tree check, lookup source scope; 76 find/frame/browser tests pass. Single feat commit 0a8b938 left as is (cannot rewrite what qa saw); PO to accept.
- 2026-10-03 qa: round 2 FAIL at e259d2c — round-1 findings 1-3 fixed (default tree's Files on a copy of the local demo database now lists 28 hrono files, no crypto; another tree's path says Not ingested); re-ran _homes tree-scope and lookup source-scope mutations (both killed), but dropping the lookup's filed-in-tree or pending-in-tree clause survives; Not-ingested copy and README now wrong for another tree's path; one feat commit for three tickets awaits a PO ruling. Findings in the qa verdict.
- 2026-10-03 dev: round 3 fix — two lookup clauses (filed-in-tree, pending-in-tree) tested via a tree entry naming no source of the sections, both mutations bitten; Not-ingested copy and README reworded to 'not in this tree's sources'. Commit split (finding C) not done: dev may not rewrite what qa saw; needs PO ruling.
- 2026-10-03 qa: round 3 FAIL at 1d45b1c — round-2 A and B fixed (dev's filed-in-tree and pending-in-tree clause deletions both killed; copy and README reworded); my mutation dropping the pending clause's tree check (q.tree = :tree) survives, so another tree's parked section can leak into this tree's Files untested; one feat commit for three tickets still has no PO ruling. Findings in the qa verdict.
- 2026-10-03 po: stuck after 3 rounds (pending clause's q.tree = :tree untested: park a section only in another tree, assert Not ingested; README:106 rewrap). Commit history stands, as the user ruled for E018. needs-user: grant one dev round for that test + rewrap only? (rec: yes)
- 2026-10-03 po: user granted the round ("yes"). Restart: dev adds the test parking a section only in another tree (asserts Not ingested, kills the q.tree = :tree mutation) and rewraps README:106; nothing else.
- 2026-10-03 dev: round 4 fix b7a4c95 — test parks a section only in another tree with the tree's sources left out (asserts Not ingested, not parked); mutation q.tree = :tree -> 1 bitten; README:106 rewrapped; 30 find tests pass.
- 2026-10-03 qa: round 4 FAIL at b7a4c95 — the round-3 finding is fixed (dev's q.tree = :tree -> 1 mutation re-run, killed; README:106 rewrapped; 79 find/frame/browser tests pass, ruff clean); its twin survives: lookup's filed clause n.tree = :tree -> 1 (find.py:353) passes all 30 tests, and a scratch test filing f7.txt only in another tree with sources left out shows the section instead of Not ingested; 1d45b1c and b7a4c95 carry a Co-Authored-By trailer against rule 8. Search-side tree clauses (find.py:141, :143) mutated, both killed. Findings in the qa verdict.
- dev r2: 6c2e40e finding A, test_a_section_filed_only_in_another_tree_is_not_ingested_here; mutation n.tree -> 1 at find.py:353 killed. Finding B is the PO's ruling; my commit has no trailer.
- 2026-10-03 qa: round 5 PASS at 6c2e40e — round-4 A fixed: n.tree = :tree -> 1 at find.py:353 alone now fails only the new test; my n.tree != :tree mutation there killed (2 tests); ruff clean, 80 find/frame/browser tests pass, merges cleanly onto main 3cf756b; only tests changed since the browser-driven rounds, so not re-driven. PO to rule: 1d45b1c and b7a4c95 carry a Co-Authored-By trailer (rule 8), 0a8b938 holds three tickets; 6c2e40e is clean.
- 2026-10-03 po: accept at 6c2e40e — search (text-only word finds section+topic, latency logged), outline at 526 topics, file lookup's three states all met and driven; README says it. History stands as the user ruled for E018: 0a8b938's three tickets and the trailers on 1d45b1c/b7a4c95 are qa-seen and not rewritten.
- merged to main at ec0bcfb
