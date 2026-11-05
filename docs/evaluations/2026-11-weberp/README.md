# webERP: hrono on a small, messy, little-known codebase

The public counterpart of the private PDP evaluation. There, hrono helped an
agent on a legacy estate with no conventions (contest: 24.0 vs 20.0 /40 over three
tries per arm) and did not help on a cleaner one (ETL). This run asks whether
that holds on a public corpus anyone can reproduce.

## Why webERP

Chosen 2026-11-04 from nine measured candidates (sizes by hrono's own cut):

| corpus | app-code sections | why not |
|---|---|---|
| ERPNext | ~(large) | well known to models; frappe enforces one way of doing things |
| OpenEMR | 9,880 | messiest, but a tree costs ~$140-370 |
| Bahmni | - | a no-tools Sonnet answered 3 of 3 probe questions right |
| iDempiere | - | strongly conventional; ships agent docs |
| LedgerSMB | 1,285 | many PRs have no description |
| OpenBoxes | 4,024 | larger, better known |
| **webERP** | **2,003** | chosen |

webERP (github.com/timschofield/webERP, ~100 stars, project since about
2003) is about 400 flat PHP page scripts with inline SQL copied between them.
Examples of the same rule done differently: the due date of "day in following
month" terms (`CustomerAccount.php` vs `CustomerInquiry.php`,
`PrintCustStatements.php`, `AgedDebtors.php`), and a customer's balance
(`PrintCustStatements.php` sums the amounts, `CustomerAccount.php` reads
`debtortrans.balance`).

## Setup

- Workspace `~/hrono-weberp` (db, mirror, server log; not in git).
- Pin: `842d073` (2026-02-18), the parent of PR #845's merge, before the first
  candidate task PRs (#845, #848, 2026-02-19).
- Source `webERP`, excluding `locale/**`, `css/**`, `doc/**`: 962 files,
  2,003 sections.
- Models as the PDP tree (diffed, identical): condense and judge haiku,
  brief and brief-upper sonnet, insights opus, all through claude-code;
  embedding ibm-granite/granite-embedding-97m-multilingual-r2. Default prompts
  (diffed against PDP, identical).
- Tree `weberp`: lookups on, insights on at 500,000 characters.
- hrono `d215a4e`.

## Log

- 2026-11-04: build estimate 2,158 calls, ~1.3 h, ~$32.50 API-equivalent
  (PDP ran ~2.6x its estimate). Build started (`hrono tree maintain`).
- 2026-11-04 18:53 UTC: split 962 files / 2,003 sections; condense done
  (358 packed calls, ~5 sections each, 4 pack timeouts redone alone, 0
  refused, $12.78); cluster 132 topics; briefs with lookups 66 of 132 done,
  ~$0.31 a topic ($20.67 so far). Job job_ab34ec16 still running; upper
  levels and insights reviews follow. Server on 8792 (`~/hrono-weberp/h`).
- 2026-11-05: the first job failed overnight (the Mac slept: "Connection lost
  while your computer was asleep") after 67 of 132 briefs. Resumed with
  `hrono tree maintain` under `caffeinate`: condense fully cached (0 calls),
  re-cluster gave the same 132 topics, the 67 briefs kept. Built: 132 topics,
  5 level-1, root at level 2. Insights: 3 passes (topics 150, 151, 154 =
  root), 27 findings; none further due. Total API-equivalent $60.28: condense
  $12.78, brief $41.19 (253 calls, ~2 per topic with the look-again retry),
  brief-upper $3.20, insights $3.11. hrono's estimate was $32.50.
- Pilot tasks chosen (graded by blind review against the merged diff plus a
  checklist of the places the rule lives; webERP has no tests for them):
  #845 bank accounts revalued on automatic rate updates, #848 a configurable
  exchange-difference account, #878 standard costs to 8 decimals.
- 2026-11-05 12:03 UTC: familiarity probes (probes/): 0 right, 1 partial,
  2 wrong. Protocol written (protocol.md), tasks and checklists
  (tasks/). Found while writing the t1 checklist: the merged #845 never
  calls its new revaluation function from the login rate update (only
  Currencies.php:152 calls it, at 2d8fa77 and on master).
- 2026-11-05 12:06 UTC: t1 runs (runs/). hrono: 52 s, 24 turns, $0.3496,
  1 file +53/-4. code: 80 s, 35 turns, $0.3487. Blind Opus review
  (grading/t1-bank-revalue/, coin flip A=hrono): hrono checklist 6/7,
  correctness 4, conventions 3; code 5/7, 4, 2; no regressions in either.
- 2026-11-05 ~12:10-12:35 UTC: tree sync to t2's base 2d8fa77 (mirror pin
  moved; db snapshot db/snap-842d073.db). update: 5 files, 7 sections
  condensed (2 calls). propagate: judged 51 topics (best-of-3, 153 haiku
  judge calls), all 51 material, because 46 topics' briefs had looked up the
  changed shared includes (brief_uses on session.php, MiscFunctions.php,
  LoginFunctions.php, ...). The brief stage was then about to rewrite 51
  leaf briefs (~$16-19 at $0.31 each) and was STOPPED by killing the server
  before any brief call completed. Sync cost so far (haiku, API prices
  computed from tokens): judge ~$0.96, condense ~$0.08. Tree is mid-sync:
  sections at 2d8fa77, 51 leaf briefs marked stale, export for 2d8fa77 not
  made.
- 2026-11-05 12:25 UTC: on the user's go, the t2 sync resumed (db copy of
  the stopped state: db/snap-2d8fa77-midsync.db). The restarted server
  reclaimed the job; propagate re-judged only 3 topics (9 calls). Brief
  stage: 97 brief calls, 0 failures; then brief-upper. Next: when it ends,
  snapshot db/snap-2d8fa77.db, export, run t2; then the same for t3
  (pin 4cb937f79, db/snap-4cb937f.db).
- 2026-11-05 15:35 UTC: t2 sync job_e0861770 succeeded (result:
  syncs/t2-2d8fa77-job.txt). Over the whole job (both halves; `hrono usage
  --by run`, hrono's price table src/hrono/usage/prices.py, the same as the
  build figure): $35.35 API-equivalent. By role (llm_calls by job_id, same
  prices): brief 118 calls $20.43, brief-upper 12 $6.17, insights 12 calls
  (6 reviews, 62 findings) $7.64, judge 162 $1.04, condense 2 $0.08; 0
  failures. Tree: 0 topics added or removed, 10 sections refiled, 65 briefs
  rewritten. A sync over 5 changed files cost 59% of the $60.28 build,
  because briefs that looked up the changed shared includes were all judged
  material. Snapshot db/snap-2d8fa77.db; export exports/2d8fa778b57d (138
  files, 3 hops, pages 1/5/132).
- 2026-11-05 14:44 UTC: t2 runs (runs/, both arms in parallel, separate
  workspaces). hrono: 80 s, 40 turns, $0.3242, 7 files +48/-1; read 1 map
  page (root.md), 13 file reads, 13 grep/glob. code: 125 s, 54 turns,
  $0.3853, 10 files +50/-4; 13 reads, 21 grep/glob. (t1 for comparison:
  hrono read 4 map pages, 12 reads, 7 grep/glob; code 10 reads, 11
  grep/glob.) Blind Opus review (grading/t2-unrealized-account/, coin flip
  0: A=code, B=hrono; 18 turns, $0.6700): code checklist 5.5/6,
  correctness 3, conventions 4; hrono 4.5/6, 2, 3. hrono's regression: the
  new column is added mid-table in install/sql/tables/companies.sql while
  the positional company INSERTs (includes/InstallFunctions.php,
  install/sql/demo.sql) are not updated, so a fresh install fails; it also
  missed Z_CreateCompanyTemplateFile.php. Both missed BankReconciliation.php
  and both select the new column in GetConfig.php without the reference's
  SHOW COLUMNS guard.
