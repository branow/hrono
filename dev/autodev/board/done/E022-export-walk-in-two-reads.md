---
id: E022
title: an export walk settles in two reads; sibling dirs never share a name
priority: medium
depends_on: [E018]
requirements: []
---

## Goal
After E018 the export still costs more than raw on hrono's own repo (walk
758k-1.09M vs 509k tokens; ~4 reads per answer vs 1.5). Let an index page say
which file to open, so an agent walks in two reads, then re-measure.

## Tickets

### 1 an index page's Children entries name the files they lead to
Change: each Children entry on an index page lists the section files beneath
it (name + link), so the agent can open the answer from the index.
Done when:
- [ ] on hrono's own export every Children entry names its section files
- [ ] the page stays within the E018 index budget (opening + Children)
- [ ] a page with a `## Notes` note is measured with the note in; tested
- [ ] `git diff --stat main...epic/E022` shows only export/, tests/export, README, evidence
Look at: src/hrono/export/render.py

### 2 sibling directories are told apart
Change: two siblings whose names slug alike get distinct slugs from their own
subject, not a -5/-15 suffix.
Done when:
- [ ] hrono's own export has no two dirs sharing a slug stem; ls in evidence/E022/
Look at: src/hrono/export/render.py `_directory`

### 3 re-measure against raw
Change: rerun `.e2e/eval/run.py` (grep + walk, 2/3 hops + raw); baseline evidence/E018/.
Done when:
- [ ] report in evidence/E022/: tokens, correct, reads, before/after
- [ ] walk tokens <= raw, or the Log says why not and what would

## Out of scope
- changing brief prompts or the hop limit

## Log
- 2026-10-03 po: created from backlog export-index-entries-name-the-file (E018 review).
- 2026-10-03 po: starting (export/render.py only; no overlap with E021 crypto/app or E007 panel copy).
- 2026-10-03 dev: round 1 started, worktree epic/E022.
- T1 eb85e00 (+ 05a56f5 file named once, 3b43130 links ranked by the facts of the entry's brief): each Children entry adds `Sections: [a/b.py](..), ... and N more` (3 files, last two path parts as the label, relative to the page). Driven on a real 268-section tree and walked by 22 agent questions. Mutations killed: cap, round-robin, relpath, label, count, entry line, distinct files, scope of facts, ranking key, fence and prose skips.
- T2 d4cf7f2: siblings whose titles slug alike take the stem of their own summary when the summaries differ (title kept when they do not). Mutations killed: group guard, silent summary, equal summaries. Real tree had no such pair, so directories.txt shows none; the tests carry it.
- T3 re-measured on a rebuilt tree (E018's db is gone), same tree before/after: walk 1,007k -> 799k (854k on a second run), reads to settler 3.9 -> 2.9-3.0; grep 374k -> 544-554k; raw walk 410k / grep 380k. NOT <= raw. Why: root.md grows 5.0 -> 11.5 KB and every turn carries it (grep, where the agent reads root and then greps, pays ~10-15k per question for nothing); the links get a two-read walk only when the section offered is the settler (8 of 22, at raw cost), else 3-8 reads. 6 links cost more (932k). What would: a corpus raw cannot be grepped or walked in 1-2 reads, or an entry that carries less per link; a smaller WIDTH would make room (collapse.py still sizes a page at 250 B per entry, now ~600). Left WIDTH alone: hop limit is out of scope. Evidence in evidence/E022/.
- 2026-10-03 qa: round 1 FAIL at 3b43130: re-exported dev's hrono.db from the qa worktree (byte-identical to after-2, 0.58 s, 0 dangling entry links), ruff clean, 210 affected tests pass; re-ran dev's _LEADS cap and fence-skip mutations plus 7 of my own (all killed). Findings: root.md 11,474 B > the 10,240 B index budget (T1 Done-when 2, untested), collapse.py docstring now false, README line 142 unwrapped, T1 in three commits, T2 summary stem can collide with another sibling's title stem.
- 2026-10-03 dev: round 2 at bdf3b78 (history reshaped as qa asked: T1 f9b6f32 = eb85e00+05a56f5+3b43130+the budget fix, T2 bdf3b78 one commit; both rewritten, hashes above are stale). T1: an index page now takes as many section links per entry (3, 2, 1, 0) as keep the page within one SECTION (10,240 B, `section_budget`), so a full-WIDTH page carries none; hrono's root.md 11,474 -> 9,507 B on the eval tree (2 links per entry; the 8,243 first logged was the stub tree h.db). collapse.py docstring and README reflowed and made true. T2: a summary stem equal to a sibling's stem is not taken (title kept), `_tell_apart` returns the renames. Mutations killed: budget check, fallback to 0, link ladder, sibling-stem guard. T3 numbers (walk 799k, grep 544k) were measured at the 11.5 KB root and are NOT re-run; a smaller root should lower both.
- 2026-10-03 qa: round 2 FAIL at bdf3b78: re-exported dev's eval tree (.scratch/hrono.db, 287 files) at the head: root.md 9,507 B with 2 links per entry, 0 dangling entry links, no shared stems, 0.75 s; ruff clean, 169 affected tests pass. Round-1 findings 1, 2, 3, 5 fixed. Re-ran dev's budget-check, fallback-0 and sibling-stem-guard mutations (killed); mine: no 1-link step and budget+3 survive. Findings: T3 report does not measure the head (8,243 B is h.db, the stub tree), budget check is 3 bytes loose, the 2/1-link steps untested, T1 commit's README carries T2's sentence.
- 2026-10-03 dev: round 3. A the T3 report now measures the head: eval tree re-exported (root.md 9,507 B, only file that differs), walk 827k tokens / 3.1 reads / 19 of 22 correct, grep 464k / 21 of 22; raw 410k / 380k, before-2 1,007k / 374k. Walk is NOT <= raw; the smaller root lowered grep (544k -> 464k) but not walk (799k/854k at 11.5 KB, 827k at 9.5 KB: variance). Evidence README and head/ updated. B the budget counts the page as written (+3 for the joining blank line and closing newline). C test of exactly-fitting and one-byte-short pages for 3, 2, 1 links; mutations killed: range stopping at 2, budget without +3, budget +6. D README sentence about alike siblings moved from T1 to T2; history rebuilt as 2 commits (8ef2cfd T1, f781307 T2); 91 export tests pass.
- 2026-10-03 qa: round 3 FAIL at f781307: round-2 A-D fixed (evidence measures the head, +3 budget, 3/2/1-link ladder tests, README sentence in T2); ruff clean, 91 export tests pass; dev's +3-removed and range-stop-at-2 mutations and my '<' and '+2' killed. Blocking: the rewritten T1 commit 8ef2cfd sits on main ec0bcfb but carries 684b78d's tree outside export, so merging reverts main's 10 commits 2025794..ec0bcfb (Find tab, glossary vocabulary, Guide audit: 2,357 lines deleted). Also: an index page's human note is appended after the link budget is measured, so a noted page can exceed one SECTION while keeping links.
- 2026-10-03 po: stuck after r3 (E: f781307 rebuilt from a 684b78d tree, merging reverts main 2025794..ec0bcfb — Find tab, vocabulary, Guide audit; F: `## Notes` added after the link budget is measured). needs-user: one more dev round — rebuild the 2 commits on ec0bcfb so `git diff --stat main...head` shows only export/, tests/export, README; count Notes in the budget + test? (rec: yes)
- 2026-10-03 po: user said yes. Restart r4: rebuild the 2 commits on current main (39dfd27), not a 684b78d tree; count Notes in the link budget + test (T1 Done-when amended).
- 2026-10-03 dev: round 4 at 1327a3a. Rebuilt the 2 commits on main 39dfd27 from the export-only patches (b75bc65 T1, 1327a3a T2); `git diff --stat main...HEAD` is README, export/ (3 files), tests/export (2 files), 700+/36-. Notes counted in the link budget (page measured with the note in); test pins exact-fit and one-byte-short with a note; mutation dropping the note from the budget killed. 92 export tests pass, ruff clean. T3 numbers unchanged (render change only affects pages with a note).
- 2026-10-03 qa: round 4 FAIL at 1327a3a: Notes now counted in the link budget (re-exported eval tree: root.md 9,507 B, 2 links/entry, 0 dangling entry links, no shared stems; root with 500/1500/4000 B notes stays <= 10,240 B, links 54->36->18); ruff clean, 173 affected tests pass; dev's note-dropped mutation and mine (note '\n' short, range stop at 2, chars not bytes, no sibling-stem guard, len(shared)>0) all killed. Blocking: T1 b75bc65 deletes README.md's 'Find is the other way in' paragraph (main 1bb37e4, lines 111-120) while the Find tab is still in the code, so merging still reverts main's docs. Minor: README 'Siblings whose titles...' sentence starts mid-paragraph on a new line after a short 'fewer on a wide page.' line (not reflowed).
- dev round 2: README fix commit 0b72d87; git diff main...HEAD -- README.md is additions only (Find paragraph kept, export paragraph reflowed to 80 cols); docs-only, no code touched.
- 2026-10-03 qa: round 5 PASS at 0b72d87: README diff vs main is additions only (Find paragraph kept, export paragraph reflowed, claims match _LEADS=3 and the 10,240 B budget); ruff clean, 173 affected tests pass; re-exported eval tree (287 files, 0.76 s, root.md 9,507 B, no dangling entry links); mutations re-run, both killed: _LEADS 3->2, note dropped from budget. The 11,500 B wide page is the same on main, so not from this epic.
- 2026-10-03 po: accept at 0b72d87. T1/T2 met as qa drove them; T3 not <= raw, explained (walk -18%, grep +24% from root growth); full suite 2246 pass in 54s; README matches. Follow-up: backlog/export-index-links-cost-the-grep-arm.md.
- merged to main at 6281aaa
