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
- 2026-11-05 ~14:49-15:40 UTC: t3 sync to 4cb937f79 (mirror pin moved;
  start state db/snap-2d8fa77.db), job_4dbc1d91 succeeded (result:
  syncs/t3-4cb937f-job.txt). $28.48 API-equivalent (`hrono usage --by
  run`): brief 89 calls $14.81, brief-upper 11 $5.76, insights 12 calls (6
  reviews, 51 findings) $6.78, judge 132 (44 topics, all material) $0.83,
  condense 9 $0.30; 0 failures. Tree: 0 topics added or removed, 3
  sections refiled, 51 briefs rewritten. Snapshot db/snap-4cb937f.db;
  export exports/4cb937f79e8b (138 files, 3 hops, pages 1/5/132).
- 2026-11-05 15:52 UTC: t3 runs (runs/, both arms in parallel). hrono:
  102 s, 50 turns, $0.7658, 8 files +205/-4; read 4 map pages (root.md and
  the briefs of topics 56 Z-import utilities, 72 stock item maintenance,
  102 item selection), 15 reads, 19 grep/glob. code: 102 s, 43 turns,
  $0.5209, 8 files +296/-1; 9 reads, 22 grep/glob. Blind Opus review
  (grading/t3-item-notes/, coin flip 1: A=hrono, B=code; 21 turns,
  $0.6166): hrono checklist 5.5/6, correctness 3, conventions 4; code
  5.5/6, 4.5, 4; no regressions listed for either. hrono's defect: it
  escapes notes again although session.php already escapes all POST data
  (apostrophes, & and < show as entities and grow on each edit), and its
  import stores raw CSV notes unescaped. code put the import in a new
  Z_ImportStockNotes.php instead of a column in Z_ImportStocks.php
  (item 5 partly met).

## Results (pilot, one try per arm per task)

Blind Opus review; checklist items met, correctness 0-5, conventions 0-5.
Agent cost is claude-code's reported API-equivalent.

| task | arm | checklist | correctness | conventions | regressions | s | turns | agent $ | map pages read |
|---|---|---|---|---|---|---|---|---|---|
| t1-bank-revalue | hrono | 6/7 | 4 | 3 | none | 52 | 24 | 0.3496 | 4 |
| t1-bank-revalue | code | 5/7 | 4 | 2 | none | 80 | 35 | 0.3487 | - |
| t2-unrealized-account | hrono | 4.5/6 | 2 | 3 | fresh install broken | 80 | 40 | 0.3242 | 1 |
| t2-unrealized-account | code | 5.5/6 | 3 | 4 | none new | 125 | 54 | 0.3853 | - |
| t3-item-notes | hrono | 5.5/6 | 3 | 4 | none | 102 | 50 | 0.7658 | 4 |
| t3-item-notes | code | 5.5/6 | 4.5 | 4 | none | 102 | 43 | 0.5209 | - |

Sums: hrono checklist 16/19, correctness 9, conventions 10; code 16/19,
11.5, 10. (t2: both arms share the GetConfig.php pre-upgrade risk, listed
for both by the reviewer.) With one try per arm this is an observation,
not a test: on this pilot hrono did not help.

Tree cost (hrono's price table, API-equivalent; subscription-billed):
build $60.28, sync to t2 $35.35 (5 changed files), sync to t3 $28.48
(27 changed files); total $124.11. Reviews: $0.42 + $0.67 + $0.62.

## Retrospective (2026-11-05, after the pilot)

Checked against the exports and transcripts:

- The map held what the hrono arm got wrong; the arm did not read it. t3:
  the leaf brief of topic 50 (includes, session, bootstrap) states
  "`$_POST` and `$_GET` values are escaped with
  `DB_escape_string(htmlspecialchars())`"; the arm read root.md and the
  briefs of topics 56, 72, 102, and escaped again. root.md says nothing
  about escaping. t2: BankReconciliation.php is covered by topic 123's
  brief; the arm read root.md only (1 of 138 pages) and worked by grep.
- The plugin's session note and skill are written for questions ("read
  the map before any code ... to confirm the claims you make", "stop
  exploring after about 20 tool calls and write the answer"). Nothing told
  an implementing agent to read the briefs of the files it edits.
- The tasks can be found by grep: each change hangs on a searchable name
  (`exchangediffact`, `companies`, `stockmaster`). On the PDP contest task the rules
  had no shared name across stored procedures, which is where the map
  helped. The tasks were chosen for code mess, not for hidden rules.
- One try per arm cannot separate the arms: the differences are 1-1.5
  points on single runs, and t1 went to hrono.
- Cost: $63.83 of the ~$128 went to two tree syncs that only existed
  because the three tasks had three bases; my estimates for them ($16-19,
  then $25-35) were low. The syncs are expensive because lookups make
  every brief that consulted a changed shared include (SQL_CommonFunctions,
  session, GetConfig) material: 51 and 44 topics re-briefed for 5 and 27
  changed files.

Follow-ups: protocol amendment 1 (the change-task skill, rerun with 3 tries
per arm, no syncs); a backlog item on sync cost from lookups into shared
includes; whether cross-cutting conventions (input escaping, install and
upgrade steps) should reach root.md.

## Amendment 1 results (2026-11-05)

Runs: t2 and t3, hrono tries 2-4 (hrono f8004fd, change-task skill),
code tries 2-3, all five per task in parallel; t2 first, then t3. 0
failures. Reviews: grading/amend1/<task>-p<k>/, pair k = hrono try k+1 vs
code try k, own coin flip each; review cost t2 $0.75, $0.95, $0.81; t3
$0.63, $0.56, $0.62. (Code try 1 was reviewed again here, paired with
hrono try 2; its t2 scores matched the pilot review, 5.5/3/4; on t3 it got
5.5/4/4 vs 5.5/4.5/4 in the pilot.)

| task | arm | try | checklist | correctness | conventions | regressions listed | s | turns | agent $ | map pages |
|---|---|---|---|---|---|---|---|---|---|---|
| t2 | hrono | 2 | 5.5/6 | 3 | 4 | GetConfig, BankReconciliation | 88 | 54 | 0.5336 | 3 (root, 123, 41) |
| t2 | hrono | 3 | 5/6 | 3 | 4 | GetConfig, BankReconciliation | 87 | 49 | 0.5316 | 3 (root, 23, 123) |
| t2 | hrono | 4 | 5/6 | 3 | 4 | demo.sql positional INSERT | 93 | 53 | 0.4834 | 2 (root, 23) |
| t2 | code | 1 | 5.5/6 | 3 | 4 | GetConfig, BankReconciliation | 125 | 54 | 0.3853 | - |
| t2 | code | 2 | 5/6 | 2 | 4 | GetConfig, InstallFunctions positional INSERT, BankReconciliation | 107 | 66 | 0.5165 | - |
| t2 | code | 3 | 5/6 | 2 | 4 | GetConfig | 87 | 60 | 0.4643 | - |
| t3 | hrono | 2 | 5/6 | 3 | 3.5 | none | 118 | 50 | 0.7386 | 3 (root, 72, 56) |
| t3 | hrono | 3 | 5.5/6 | 5 | 5 | none | 139 | 54 | 1.0267 | 6 (root, 72, 56, 151, 105, 25) |
| t3 | hrono | 4 | 5/6 | 3 | 4 | none | 109 | 44 | 0.7882 | 5 (root, 151, 72, 56, 105) |
| t3 | code | 1 | 5.5/6 | 4 | 4 | none | 102 | 43 | 0.5209 | - |
| t3 | code | 2 | 4.5/6 | 3 | 3 | notes not deleted with the item; orphaned on code change | 97 | 44 | 0.4886 | - |
| t3 | code | 3 | 6/6 | 5 | 4 | none | 133 | 66 | 0.6883 | - |

Means (n = 3 per arm): t2 hrono checklist 5.17, correctness 3.00,
conventions 4.00; code 5.17, 2.33, 4.00. t3 hrono 5.17, 3.67, 4.17; code
5.33, 4.00, 3.67. Over both tasks: hrono correctness 3.33, code 3.17;
conventions 4.08 vs 3.83; checklist 5.17 vs 5.25. No difference beyond
the spread between tries of the same arm.

What the transcripts show: with the change-task skill the hrono arm read
2-6 map pages (pilot: 1-4) and grepped the map for the files it edits,
but no t3 try opened topic 50 (session.php, where the map states POST
data is already escaped). In t2, tries 2 and 3 read topic 123 (bank
reconciliation), yet no run of either arm, pilot included, changed
BankReconciliation.php. Agents treat the page they copy as the shared
context, not the includes every page runs through. Agent cost: hrono
$0.48-1.03 a try, code $0.39-0.69.

## Amendment 2 results (2026-11-05, harness v2: real plugin, recall on)

t3 at 4cb937f, 3 tries per arm, all six in parallel, 0 failures. Recall
attached to every hrono prompt (runs/*-hrono-v2-*.recall.md): pages of
topics 56, 8, 9, 10, 55, 52 and passages of README.md, Stocks.php,
upgrade2.9-2.9a.sql, FixedAssetItems.php; not topic 50 (session.php).
Reviews: grading/amend2/ (pair k = hrono v2-k vs code v2-k; $0.60, $0.65,
$1.05).

| arm | try | checklist | correctness | conventions | s | turns | agent $ | map pages opened | Skill calls |
|---|---|---|---|---|---|---|---|---|---|
| hrono | v2-1 | 5/6 | 4 | 4 | 116 | 43 | 0.6408 | 2 (56, 72) | 0 |
| hrono | v2-2 | 5.5/6 | 4 | 4 | 94 | 36 | 0.5232 | 0 | 0 |
| hrono | v2-3 | 4.5/6 | 3 | 3 | 97 | 43 | 0.5083 | 0 | 0 |
| code | v2-1 | 5/6 | 4 | 3 | 100 | 46 | 0.5763 | - | - |
| code | v2-2 | 5.5/6 | 3 | 4 | 92 | 45 | 0.5524 | - | - |
| code | v2-3 | 6/6 | 4 | 4 | 97 | 48 | 0.5703 | - | - |

Means: hrono 5.00, 3.67, 3.67; code 5.50, 3.67, 3.67. With recall
attached the hrono arm opened fewer map pages than without it (0-2 vs 3-6
in amendment 1) and never called the skill: it took the passages as enough
and worked by grep. On a task this size the map does not change the
outcome; recall did not bring the cross-cutting rule (escaping) because
the task text does not name it.

Cost and time (means per arm, from each run's summary.json; agent cost is
claude-code's reported API-equivalent):

| set | arm | n | seconds | turns | agent $ | output tok | cache read | cache write |
|---|---|---|---|---|---|---|---|---|
| t3 pilot (v1) | hrono | 1 | 102 | 50.0 | 0.766 | 14,568 | 1,445,672 | 82,716 |
| t3 pilot (v1) | code | 1 | 102 | 43.0 | 0.521 | 14,113 | 801,413 | 54,854 |
| t3 amend1 (v1 + change skill) | hrono | 3 | 122.0 | 49.3 | 0.851 | 16,259 | 1,560,398 | 94,109 |
| t3 amend1 | code | 3 | 110.7 | 51.0 | 0.566 | 15,205 | 984,775 | 54,210 |
| t3 amend2 (plugin + recall) | hrono | 3 | 102.3 | 40.7 | 0.557 | 13,243 | 815,875 | 65,438 |
| t3 amend2 | code | 3 | 96.3 | 46.3 | 0.566 | 13,099 | 905,604 | 63,536 |
| t2 amend1 | hrono | 3 | 89.3 | 52.0 | 0.516 | 12,539 | 771,194 | 59,125 |
| t2 amend1 | code | 3 | 106.3 | 60.0 | 0.455 | 12,368 | 736,451 | 46,086 |

With v1 the pasted note and skill (~6 KB) rode in every turn's context:
the hrono arm cost 50% more on t3. With the real plugin and recall it cost
the same as code-only ($0.557 vs $0.566) in 12% fewer turns.

## Amendment 3 results: t4 forecasting module (2026-11-06)

6 runs in parallel (harness v2, real plugin and recall), 0 failures.
Reviews grading/amend3/ (pair k = hrono k vs code k; $2.20, $2.19, $2.05).
Note: the reviewer prompt lists task.md, not brd.md; brd.md was in each
review folder and task.md names it.

| arm | try | checklist /12 | correctness | conventions | regressions | s | turns | agent $ | files | lines + |
|---|---|---|---|---|---|---|---|---|---|---|
| hrono | 1 | 11.5 | 4 | 3 | none | 836 | 112 | 3.7596 | 29 | 3,422 |
| hrono | 2 | 12 | 4 | 4 | none | 991 | 140 | 4.4310 | 32 | 3,074 |
| hrono | 3 | 12 | 4 | 4 | none | 932 | 132 | 4.1184 | 30 | 2,854 |
| code | 1 | 12 | 4 | 4 | none | 916 | 109 | 3.9913 | 31 | 3,516 |
| code | 2 | 11 | 4 | 4 | none | 921 | 147 | 4.2815 | 36 | 3,686 |
| code | 3 | 12 | 4 | 3.5 | none | 1,091 | 169 | 5.2588 | 38 | 3,124 |

Means: hrono checklist 11.83, correctness 4.00, conventions 3.67; code
11.67, 4.00, 3.83. Cost and time: hrono $4.103, 128.0 turns, 920 s,
output 142,347, cache read 8,564,649, cache write 241,592; code $4.511,
141.7 turns, 976 s, 150,125, 9,503,619, 277,084. hrono 9% cheaper, 10%
fewer turns, 6% faster.

The checklist saturated: every run, code-only included, met the hidden
rules it was built around (checked by grep in the diffs: all six rewrite
existing users' `modulesallowed`, read sales from `stockmoves`, use
`debtorsmaster.typeid`, create the forecast type in `mrpdemandtypes`; none
uses `salesorderdetails` as the reference did). In webERP these rules are
written in the code next to what the change touches (WWW_Users.php shows
the positional list), so a code search finds them. On the PDP contest task they were
spread over a SQL Server estate with no shared names.

Map use: the hrono arm opened 0 map pages and called the skill 0 times in
all three runs; it worked from the attached recall (9.4 KB: topics 36, 10,
120, 26, 11, 8, 147, 40, 50; module/menu seed data, update scripts,
session) plus grep. Recall queries the short task.md, not brd.md, and
missed MRP (topic 108) and user access (topic 118).

## t5 gate (2026-11-06): one code-only try before any comparison

Task t5-early-payment (business request only, tasks/t5-early-payment/).
Code arm, harness v2: 341 s, 118 turns, $1.922, 14 files +464/-18
(runs/t5-early-payment-code-gate.*). Audited by hand against the 17
checklist items:

- met: 1 schema and terms page; 3 one shared discount-date function; 4
  invoice; 5 statement; 6 account and inquiry; 7 receipt recognises the
  discount and settles the invoice (exact amount only); 8 no double
  discount with `pymtdiscount` or the receipt type; 14 ageing unchanged.
- partly: 11 supplier inquiry yes, SupplierTransInquiry no; 13 payment run
  includes expiring discounts and posts them, remittance advice no; 15
  currency handled in the invoice currency.
- missed: 2 terms API; 9 API receipts and counter sales; 10 supplier
  invoice entry records nothing (it reads the supplier's current terms at
  payment time, where supplier due dates are stored at entry); 12 manual
  supplier payments (Payments.php).
- extra: found the payment run's "Print and Process" never committed its
  transaction and added DB_Txn_Commit (changes existing behaviour).

Its NOTES.md names 2, 9, 12 as "not covered" and 10 as a choice: it knew
the places and left them out, so the misses are scope, not missing
knowledge.
