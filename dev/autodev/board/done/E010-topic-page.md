---
id: E010
title: the topic page — sections you can tell apart, facts before hashes
priority: medium
depends_on: [E005]
requirements: [28, 58, 76]
---

## Goal
Where a curator spends their time: a false root warning, eleven rows reading
"CHANGES.md core", hashes level with facts. Detail: archive/214.

## Tickets

### 1 root is root, breadcrumb, facts first
Done when:
- [ ] the root shows no warning; a real orphan still does
- [ ] full breadcrumb from root on every topic page
- [ ] who wrote the brief, when, model, tokens up front; hashes behind "details"
  (price is out of scope: no brief-to-ledger link; see backlog brief-cost-needs-a-ledger-link)
Look at: server/ui/nodes.py, templates/node.html

### 2 sections you can tell apart
Change: each row shows heading/symbol, line range, size, fit; sort by fit,
filter by path, paged.
Done when:
- [ ] sections of one file are distinguishable; misfits sort first

### 3 actions in the page head
Change: rename, edit brief, note, Structure menu (reparent/merge/split/
dissolve, still confirming); pinned state at top.
Done when:
- [ ] every edit reachable from the head, absent for a reader
- [ ] each destructive confirm states what will change before it runs
- [ ] existing node-page and surgery tests pass; screenshots in evidence/E010/

### 4 a section is listed once
Change: `_members` LEFT JOINs `condensations` on content_hash alone, so a
section condensed by two models renders twice (and its `id="section-N"`).
Take the condensation from the brief's recorded condense model.
Done when:
- [ ] a section condensed by two models is one row; ids are unique
Look at: server/ui/nodes.py `_members`

## Out of scope
- the map (E014)
- a money price for a brief (needs a migration; backlog)

## Log
- 2026-10-03 po: created from #214.
- 2026-10-03 po: waits E007 (node.html copy E007 rewrites).
- 2026-10-03 po: +T4 from backlog node-page-lists-a-member-once-per-condense-model (E011 qa).
- 2026-10-03 po: waits E009 (both edit server/ui/nodes.py).
- 2026-10-03 po: E009 merged (421a0df); starting — no file overlap with E013 (registry/first run).
- 2026-10-03 dev: T1-T4 in one commit (entangled in nodes.py/node.html); verified by test_ui_node (7 new) + screenshots evidence/E010; mutations: _is_root, line-start cmp, focus page, condense model all fail a test. Tokens not money: brief has no priced ledger row, label now Tokens.
- 2026-10-03 qa: round 1 FAIL at 1bb37e4 — drove root/leaf/32-section topic on a copy of hrono-click (admin, reader, dark, 390px); T4 recorded-model join unguarded (mutation survives), mid-line section end untested, Cost not shown, dead `orphan` key, one commit for four tickets. Findings in qa verdict.
- 2026-10-03 dev round 2 at d8aa7de: fixed qa 1 (join picks the recorded model; two-model test now records it first; mutating the ORDER/model filter fails it), 2 (no-final-newline section test; dropped +not endswith fails it), 4 (orphan removed), 6 (path nowrap-width, heading wraps). Mid-line test rode in the finding-1 commit. OPEN, needs PO ruling: finding 3 'cost up front' cannot be priced, since a brief stores no job id and llm_calls has no node link, so a price needs a migration; tokens-only stands. Finding 5 (T1-T4 one commit) is a PO/merge ruling.
- 2026-10-03 qa: round 2 FAIL at d8aa7de — 739 affected tests pass; fixes 2, 4, 6 hold (newline mutation killed; path no longer breaks, re-driven at 1440/390). Finding 1 still open: dropping the recorded-model ORDER term survives because scribe-9 is also the alphabetical MIN. Findings 3 (cost) and 5 (one commit) need a PO ruling. Findings in qa verdict.
- 2026-10-03 po ruling: qa 3 — tokens-only accepted, T1 Done-when amended; price needs a brief->ledger link, filed to backlog. qa 5 — 1bb37e4 (T1-T4) and 6372223 (two fixes) accepted as-is, no history rewrite; any further fix is one commit per finding. Only qa 1 remains.
- dev r3: c305938 qa finding 1 fixed (other model alpha-old sorts before scribe-9, written last); mutation dropping the DESC term fails the test, restored.
- 2026-10-03 qa: round 3 PASS at c305938 — 885 tests in tests/server+summarize pass, ruff clean; source unchanged since round-2 drive at d8aa7de (test-only fix). Finding 1 closed: recorded-model term flipped to ASC and replaced by a constant both fail test_a_section_condensed_by_two_models_is_one_row; findings 3, 5 settled by PO ruling.
- 2026-10-03 po: review ACCEPT at c305938 — T1-T4 Done-when met per qa rounds 1-3 and evidence/E010; root/orphan, breadcrumb, Details, confirm hints, filter/pager, one row per section; README describes the page.
- merged to main at c305938
