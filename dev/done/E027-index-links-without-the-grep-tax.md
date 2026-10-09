---
id: E027
title: index-page section links stop taxing the grep arm
priority: medium
depends_on: [E022]
requirements: []
---

## Goal
E022's section links cut the walk (1,007k -> 827k tokens) but grew root.md
5.0 -> 9.5 KB, which every grep turn carries (374k -> 464k). Keep the walk
gain without the grep tax.

## Tickets

### 1 links cost less per page
Change: try (a) a path-only entry per link and (b) no links on root.md (links
only on pages below root); keep the cheaper overall, or both.
Done when:
- [ ] root.md back to <= 6 KB on hrono's own export
- [ ] on one tree, same questions (`.e2e/eval/run.py`), measured against
  `head` exported from that tree (E022's tree is gone): grep tokens below
  head on every run, walk mean within head's own run-to-run spread (a tie
  in noise passes), two runs per arm per variant;
  report in evidence/E027/
- [ ] correctness no worse than head by more than 1 question on either arm;
  the report explains the grep settler-reached drop (9/19 -> 4/19)
- [ ] a variant that loses on either arm is not shipped; the report says why
- [ ] README paragraph at line ~171 reflowed to <= 80 columns
Look at: src/hrono/export/render.py, collapse.py (250 B/entry sizing)

## Out of scope
- changing the hop limit or WIDTH

## Log
- 2026-10-03 po: created from backlog export-index-links-cost-the-grep-arm (E022 review).
- 2026-10-03 dev: T1 (b) root.md carries no section links; (a) path-only was bigger and is not shipped. Root 8,174 -> 5,465 B; walk 871k -> 833k, grep 535k/480k -> 429k/430k (target 400k missed on this rebuilt tree, floor reason in evidence/E027/README.md). Mutation: restoring the root's links fails test_the_root_page_carries_no_section_links. Tests: 447 passed (export + importers).
- 2026-10-04 qa: round 1 at 6433637 FAIL (ticket_defect): render/test/root size verified (re-rendered dev's db with the branch: root.md 5,465 B, 0 links; restoring root links fails the new test; inverting the root check fails 11), but Done-when 'grep <= 400k' is unmet (430k) and unreachable on the rebuilt tree within scope; E022 baseline gone. PO to restate the bound. Also README.md:171 is 89 chars, unflowed.
- 2026-10-04 po: ruling: grep bound restated relative to head on the rebuilt tree (absolute 400k was E022-calibrated; 430k vs head 480-535k accepted). Added: second walk run per arm, correctness within 1 question, explain settler-reached drop, README reflow.
- 2026-10-04 dev: round 2: second walk run (head 922k, noroot 961k; mean 896k vs 897k, tie), grep settler-reached drop is noise (noroot 4/19 then 9/19), README reflowed; evidence/E027/README.md updated.
- 2026-10-04 qa: round 2 at 741f873 FAIL (ticket_defect): code, test, root 5,465 B, README reflow (<=80 chars), evidence numbers all verified (re-summed walk jsonl; restoring root links fails test_the_root_page_carries_no_section_links). Only open item: Done-when 'walk tokens <= head's' is unmet as written (run 2 961k vs 922k; mean 897,162 vs 896,505, +657). Within 50k run noise; PO to rule whether a tie within variance passes or the variant must not ship.
- 2026-10-04 po: ruling (a): walk bar restated as 'mean within head's run spread'; strict <= on 2 runs can't separate a 0.07% gap from head's own 50k swing. Variant (b) passes as it stands; grep wins, walk ties. No code change; qa to re-gate.
- dev r3: no code change; PO ruling (a) amends walk criterion, head stays 741f873, back to qa.
- 2026-10-04 qa: round 3 at 741f873 PASS: re-gated against the amended walk bar; walk jsonl re-summed (head 871,310/921,701, noroot mean 897,162 inside head's spread), grep below head on both runs, correctness within 1 on both arms, root.md 5,465 B, README epic paragraph <=80 cols; ruff clean, tests/export 93 passed; mutations: restoring root links fails test_the_root_page_carries_no_section_links, inverting the root check fails 11.
- 2026-10-04 po: review ACCEPT at 741f873: root 5,465 B, grep below head on both runs, walk ties inside head's spread, correctness within 1; README/docstrings say the root carries no links.
- merged to main at 732b19d
