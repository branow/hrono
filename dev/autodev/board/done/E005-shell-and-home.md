---
id: E005
title: the shell and the home page — no overflow, and a home that says if it is up to date
priority: high
depends_on: []
requirements: [17, 18, 20, 75, 77, 78, 79, 94]
---

## Goal
Every page overflows by 4px, hints cover what they explain, the top bar breaks
at 800px, and home shows four numbers. Fix the frame every page sits in, and
make home answer "is it up to date, is anything running". Detail: archive/215,
screenshots in ui-review-2026-10-03/.

## Tickets

### 1 no overflow, hints in view, a browser test that keeps it so
Change: fix overflow and hint placement; top bar collapses at narrow widths.
Done when:
- [ ] a browser test over every UI route fails on horizontal overflow at 800,
  1100, 1440px
- [ ] no hint overlaps its anchor's content or leaves the viewport
Look at: server/templates/base.html and its CSS

### 2 navigation, empty states, feedback
Change: nav = Home, Map, Ask, Runs, Health, Usage, Export, Settings, Guide
(only pages that exist); every empty state offers a button, not a CLI command;
every action returns with a plain statement of what it did.
Done when:
- [ ] current page is marked on every route, topic pages included
- [ ] every empty state has a next action
Look at: base.html, server/ui/views.py

### 3 home answers the four questions
Change: per source last read, commit, behind or not; a running job with live
progress; what needs attention; what the last run did. Drop the "Open the map"
card.
Done when:
- [ ] a source that is behind shows as behind
- [ ] a running job is on home and updates live (SSE)
- [ ] before/after screenshots, both themes, in evidence/E005/
Look at: server/templates/overview.html, server/ui/overview.py

## Out of scope
- spend on home (E008); wording pass (E007)

## Log
- 2026-10-03 po: created from #215.
- 2026-10-03 po: folded backlog page-overflows-4px-at-1440 (E006 screenshots: scrollWidth 1444 on /ui/jobs, /ui/config; suspect .tip[data-tip]) into T1.
- 2026-10-03 dev: round 1 started, worktree epic/E005.
- 2026-10-03 dev: T1 4767d14 (tip rewritten as one floating box; browser test over 14 routes x 800/1100/1440; mutations: hint placement, clamp, chip wrap), T2 e4d289c (tabs table, empty-state macro, shared done/error banner; 6 mutations killed in test_ui_frame.py).
- 2026-10-03 dev: T3 1588970 (sources via git ls-remote, cached 60s; live SSE running card; real-repo + real-uvicorn browser tests; mutations: behind/current, cache ttl, last-run pick, not-compared, SSE path, dead returncode guard removed). Evidence in evidence/E005/.
- 2026-10-03 qa: round 1 FAIL at 1588970. Drove home/tabs/banners/overflow in Chromium (scoped tree, empty tree with a run, 800 dark); mutations: hint-always-above killed, unreachable->current killed, banner run link removed SURVIVED, rstrip removed survived. Findings: home lists sources outside the tree; empty-tree run not live; no test through the real sync; banner run link untested; 10s browser teardown; /ui/login missing from route test; README order; dead data-tip-below/.left.
- 2026-10-03 dev: round 2 70ab52b fixes all 9 findings (tree-scoped survey; live empty-tree callout; real git_sync seam test; banner link asserted in the banner; browser closes before server; login, empty-tree home, map in browser tests; README order; dead markup). Mutations killed: banner link removed, rstrip removed.
- 2026-10-03 qa: round 2 PASS at 70ab52b. All 9 round-1 findings verified. Drove an empty tree's first sync in Chromium at 800px dark (live callout 0/3 to 1/3, no Sync now while it runs, page reloads to idle when the run ends). Gate: ruff clean, 503 passed 1 skipped, slow teardown gone. Mutations, all killed: scope filter removed, Running-now swap, data-live removed from callout, banner link removed, rstrip removed, header Sync-now guard removed. Note: the empty-state tip 'You have N registered already' now counts the tree's sources, not every registered one.
- 2026-10-03 po: review ACCEPT at 70ab52b. All Done-when met per qa + screenshots; README/CONTRIBUTING updated. Trial merge onto main: pyproject conflict only (keep pytest-xdist AND playwright), suite 47.5s -n auto (browser tests ~9s). Req 20 met as the up-to-date chip, no timestamp.
- merged to main at ebad3d8 (rebased, full suite 1990 passed)
