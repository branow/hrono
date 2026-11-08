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

## GitHub threads source (2026-11-06)

New hrono source type `github-threads` (6b01d65, fix 30ca8ce): a
repository's issues, pull requests and discussions, one markdown page per
thread, no diffs, cut at `until`. Registered `webERP-threads`
(timschofield/webERP, until 2026-02-27, the t3/t4 base date) and added to
tree `weberp` on a COPY of the db: `db/hrono-threads.db` (server on 8792);
`db/hrono.db` is unchanged. 858 threads (272 issues, 415 PRs, 171
discussions), 2.9 MB after the 8,000-character cut per post, 974 sections
by hrono's cut; hrono's first-build estimate $15.29. Sync job_f46aa101:
succeeded, 7.44 h (with one stall and server restart when the login
expired), $80.55 by `hrono usage --by run`, 0 failed calls. Calls:
condense 132, judge 150, brief 384, brief-upper 18, insights 18, embedding
1,149. Why five times the estimate: the threads were placed into topics
built from code, the monitor measured misfit 0.234 against a baseline of
0.061, and repair split 33 topics and migrated 219 sections, so the briefs
were written a second time (170 then 214 more), and adopt made 12 new
leaves. Record: syncs/threads-4cb937f-job.txt. Snapshot
`db/snap-4cb937f-threads.db`; export
`exports/4cb937f79e8b57063bd47132413abdac8abbcbdc-threads` (208 files, 3
hops, pages 1/5/202); the code-only export of 4cb937f is unchanged. Both arms get the same threads as files
(`~/hrono-weberp/threads-2026-02-27/` -> workspace `github/`, harness
`THREADS=`; the prompt says where they are).

## t6 gate (2026-11-06): customer contacts import, code-only with github/

Task t6-contacts-import (tasks/t6-contacts-import/): business request; its
conventions are decided in discussions #789, #759, #761, #828. Code arm,
harness v2 with THREADS: 154 s, 76 turns, $0.775, 7 files +322/-6. It
never opened or searched github/. Audit by hand:

- met: 1 security level 15 in the update and install data; 2 Utilities
  menu; 3 one update file 44.php with the helpers; 7 template and header
  check; 8 CSV values escaped with DB_escape_string; 9-11 validation,
  update-or-insert, statement flag.
- partly: 4 and 5 the update right is a NEW security token 21 checked as a
  hardcoded constant (`in_array(CUSTCONTACTS_UPDATE_TOKEN, ...)`), which an
  administrator can grant through roles, but #761 decided to move away
  from hardcoded tokens to scripts-table entries like CostUpdate.
- missed: 6 the form does not use includes/UIGeneralFunctions.php (#828).

The two misses are conventions written only in discussions.

## t7 gate (2026-11-06): staff performance appraisals, code-only with github/

Task t7-appraisals (tasks/t7-appraisals/): appraisals on the existing staff
records, made up from the HR module (1c7142809) narrowed to appraisals; its
checklist has 16 codebase rules, 7 of them mistakes the real module made
and later commits fixed, and 5 business rules. Code arm, harness v2 with
THREADS: 641 s, 147 turns, $3.46, 22 files +1,703/-18. Audit (a reading
agent, key claims checked by hand): 17 met, 3 partly, 1 missed.

- partly: 9 frequency is a config row but read back from the db, not the
  session; 10 empty dates are NULL, not '1000-01-01'; 12 the review page
  is on a new token 22 given only to role 8, so reviewers in other roles
  are refused the page the email links to.
- missed: 15 no UIGeneralFunctions helpers (#828).
- other mistakes: escaped $_POST comments put back into the form after a
  save, so line breaks become literal \r\n and are stored on the next
  save; upgrade's `jobtitle` NOT NULL without a default (the install has
  DEFAULT ''); open appraisals stay open when the person or reviewer
  leaves; email links built on HTTP_HOST.

It extended `employees`, reused `departments`, guarded both deletes, used
the Timesheets patterns, no audit table, no double escaping: the rules
the real module broke were all found by reading the neighbouring code.
The task fails the gate: too easy for code-only.

## t8 gate (2026-11-06): customer balance adjustments, code-only with github/

Task t8-customer-adjustments (tasks/t8-customer-adjustments/): a short
business ticket (4 points) for the unused transaction type 15 "Journal -
Debtors"; its 22-item checklist is mostly places far from the new page
(GL rules, exchange difference, hard-coded type lists, salesman login,
tags, access). Code arm, harness v2 with THREADS: 389 s, 128 turns, $2.77,
22 files +914/-34. Audit (a reading agent, key claims checked by hand):
13 met, 7 partly, 2 missed.

- missed: 9 no GL tags; 22 no UIGeneralFunctions helpers.
- partly: 4 manual adjustment has no branch and the login as salesperson;
  5 write-off amount not rounded; 12 no exchange difference (posted at the
  invoice's old rate, so currency movement lands in the write-off
  account); 14 clean-up threshold in home currency at historical rates;
  17 CustomerInquiry unchanged (no allocation link), CustomerAccount
  without GL link; 19 a new token 21 for role 8 only instead of the
  receivables token; 21 manual bookmark without an anchor.
- other mistakes: writing off another customer's invoice by posting its
  id (the invoice is loaded by id only); salesman logins ignored in the
  new lists.

Closer to the aim (about half) than t7's 17/21, with two real bugs.

## t8 hrono try 1 (2026-11-06): the map was never read

Harness v2, THREADS, EXPORT=4cb937f...-threads (the threads map). A first
start returned no recall (the hook timed out on the server's first call
after the sync); it was stopped and rerun, and the rerun's recall attached
5 passages, all from project-history threads (the prompt only says
"implement task/brd.md"). Run: 461 s, 161 turns, $3.33, 26 files
+799/-41. The SessionStart note was delivered, yet the agent never opened
root.md, a brief, or the hrono skill: 160 tool calls, all on the code.

Checked every hrono try for paths under exports/ in its transcript (the
note alone accounts for about 2): t1 12, t2 3/38/20/35, t3 31/35/40/17,
t4 2/2/2, t8 2. So the t4 hrono tries never read the map either: the t4
"tie" was code against code. The tasks given as a business request file
(t4, t8) are the ones where the agent skips the map.

## t8 hrono try 1, rerun after the plugin fix 71909d0 (2026-11-06)

The void try (map never read) is kept in ~/hrono-weberp/runs-void/. Plugin
fix 71909d0: recall also reads the text files the prompt names (here
task/brd.md), and the session note sends a change, also one handed over
in a file, through root.md and the area briefs first. Rerun: recall
attached 5 passages from the request's text (menu and seed data, shared
includes, a merged-PR thread, bank matching, the API's debtor
transactions). 420 s, 135 turns, $2.84, 21 files +774/-40. Map use: one
read of root.md (call 8), no area or leaf brief; one discussion opened.

Audit (a reading agent, same 22 items): 14 met, 6 partly, 2 missed
(code-only gate 13/7/2). Differences from code-only: met 17 (inquiry
allocation link) and 5 (rounding), and it blocks writing off another
customer's invoice; partly 8 (no glaccountusers, code-only met it) and
21 (no ManualOutline entry). Same misses: no tags, no UIGeneralFunctions,
no exchange difference, home-currency threshold, new token 21 for role 8,
empty branch and the login as salesperson. With the map unread, this is
code against code; the scores agree within one item.

## t8 hrono try 2, with the brief gate 8874d26 (2026-11-06)

Plugin 8874d26: reading a project file names the leaf brief that
describes it (once per brief), and an edit waits until root.md and the
edited file's briefs have been read. Run: 485 s, 169 turns, $4.35, 24 files
+1,015/-30. Map use: 11 pages read (root.md, the finance area, leaves for
allocations, inquiries, GL reports and checks, sql updates, seed data,
reports), 16 briefs pointed to, 10 edits refused until their briefs were
read.

Audit (a reading agent, same 22 items): 15 met, 5 partly, 2 missed
(code-only 13/7/2, try 1 14/6/2). New against code-only: 8 met (user's GL
accounts and not the control account), 17 inquiry links, 21 manual and
outline. Still missed: tags (9), UIGeneralFunctions (22); partly: branch
and salesperson on a plain adjustment (4), no exchange difference (12),
home-currency threshold (14), token 21 not the receivables token (19).
Other mistakes: a regression in CustWhereAlloc.php (an undefined
`$TransTypeOptions` blanks the title of every receipt and credit note);
salesman logins never see plain adjustments; the clean-up re-runs its
query on confirm.

## t9 (2026-11-06, amendment 5): customer credit reviews

Task tasks/t9-credit-reviews/ (business request; checklist of 10 request
items and 7 rules away from the change, each stated in the existing map).
Harness v2 with THREADS, threads export, no sync.

Code-only gate: 310 s, 101 turns, $1.42, 15 files +588/-9. It grepped
`custnotes` (the neighbour table) and so found Z_ChangeCustomerCode.php
and the customer delete in Customers.php, and grepped session.php for the
escaping: items 11, 12, 13 met. Missed 14 (a new token 21 and a hardcoded
`in_array(21, ...)`) and 16 (no UIGeneralFunctions). It fails the gate
(about 5 of 7 away-from-the-change items met).

hrono try 1, harness option READ_MAP=1 (the prompt also asks the hrono arm
to read root.md, the area briefs and the topic briefs the request touches,
project history included, before any edit): 287 s, 73 turns, $2.43, 12
files +603/-6. Read 14 map pages (root, 5 areas, 8 topics including 105,
seed data and menu items, sql updates); no thread topic (174, 225). Met
11, 12, 13 as code-only, and 14: scripts on the existing AR token 3, no
new token, the SelectCustomer link checked through `PageSecurityArray`.
Missed 16 (no UIGeneralFunctions). On the measured items: hrono one item
ahead (14), 28% fewer turns, 71% more cost. One try per arm: an
observation.

Across t6-t9 the code-only arm missed the token rule and UIGeneralFunctions
every time; both are written only in discussions (#761, #828), which the
map states in thread topics 174 and 225.

## t10 gate (2026-11-06, amendment 6): credit control, code-only

Harness v2 with THREADS: 1,212 s, 287 turns, $10.04, 52 files
+2,817/-43. Audit (a reading agent, grading/t10-credit-control/
code-gate.md): A 14.5/15, B 35.5/40, correctness 4, conventions 3. Missed
B15 (EnsureGLEntriesBalance) and B32 (hold permission through a scripts
entry, #761); partly B9, B13, B29, B37, B39. With 287 turns the agent read
its way to almost every rule, including the invoicing, EDI, recurring and
API hold checks, Z_ChangeCustomerCode, Z_ImportDebtors and the GLAccounts
guard. It fails the gate: given unlimited turns, code-only finds the rules
in webERP's code.

## t10 at a 100-turn budget (2026-11-06, amendment 7)

Both arms in parallel, TURNS=100 and BUDGET_NOTE=1; hrono with READ_MAP=1
and the threads export. Blind grading by a reading agent per run (labels
X/Y by coin flip, grading/t10-credit-control/b100/KEY.txt).

| arm | turns (reported) | tool calls | end | s | $ | files | A /15 | B /40 | all /55 | correctness | conventions |
|---|---|---|---|---|---|---|---|---|---|---|---|
| code (Y) | 101 | 248 | cut at max turns, no NOTES.md | 1,037 | 6.67 | 37 | 13.5 | 32 | 45.5 | 3.5 | 3 |
| hrono (X) | 231 | 230 | finished | 1,126 | 8.89 | 41 | 14.5 | 33.5 | 48 | 4 | 4 |
| code gate (no budget) | 287 | - | finished | 1,212 | 10.04 | 52 | 14.5 | 35.5 | 50 | 4 | 3 |

The budget did not bind equally: Claude Code counts a turn per model
message, the code arm called tools in parallel (248 calls in 101 turns)
and was stopped, the hrono arm called them one at a time (230 in 231) and
was not stopped at 100 (it finished with subtype success). Both did about
the same number of tool calls. hrono read 151 map pages.

hrono ahead by 1.5 B items, 2.5 overall, and +0.5/+1 on correctness and
conventions; one try per arm, within the spread seen between tries.
Both missed B15 (EnsureGLEntriesBalance), B21 (account/inquiry pages show
the new types) and B32 (#761, permission through a scripts entry), although
the map states all three and the hrono arm read the pages that hold them.

## t11 (2026-11-08, amendment 10): business-only BRD, middle dose of the map

| arm | s | turns | $ | files | map pages | A /43 | B /40 | correctness | conventions |
|---|---|---|---|---|---|---|---|---|---|
| code (gate) | 577 | 190 | 4.14 | 33 | - | 16.5 | 12.5 | 2 | 3 |
| hrono 1 (READ_MAP=3) | 349 | 116 | 2.90 | 18 | 17 | 11.5 | 11 | 2 | 3 |

The gate passed (code-only 12.5/40), but not on the rules: both arms built
only reviews, stop/watch on every order route and the report, and wrote in
NOTES.md that they left out reminders, interest and fees, write-offs, the
portal and the staff guide, citing the BRD's open questions. So the ledger
and email rules (B11-B29) were not reached by either arm. B met only by
hrono: B30 (salesman filter), B32 (hold permission through a scripts entry,
#761, missed by every code-only run t6-t11). Only by code: B5 (API order
hold), B7 (customer rename), B36. hrono read 17 map pages (middle dose, as
intended), used fewer turns and less money, and did less.

Lesson: a BRD with open questions lets both arms cut half the scope; the
task statement must ask for every requirement, the open questions decided
and written down.

## t12 (2026-11-08, amendment 11): ownership task statement

Same BRD and checklist as t11; the task statement gives the agent the
feature to own. Both arms in parallel. Blind: coin 0, A = code, B = hrono
(grading/t12-credit-control/KEY.txt). Checklist graded per run; whole
change reviewed by an Opus maintainer (review-AB.md, verbatim).

| arm | s | turns | $ | files | map pages | A /43 | B /40 | correctness | conventions | review /10 |
|---|---|---|---|---|---|---|---|---|---|---|
| code (A) | 1,169 | 241 | 8.35 | 48 | - | 38 | 25.5 | 3 | 3 | 6 |
| hrono (B) | 1,278 | 265 | 14.56 | 47 | 26 | 40 | 26.5 | 3 | 3 | 5 |

Ownership worked: both built the whole feature (t11: half). On the
checklist the arms tie (hrono +2 requirements, +1 rule). The reviewer
would merge code "by a small margin", because hrono's customer-portal page
tests `$_SESSION['CustomerLogin']`, which is never set, so any customer
login can open any customer's credit page; the map states how a customer
login is detected (rule 151 R17), and hrono did not read it. Where hrono
was better, per the review: hold enforced on more routes (API invoicing,
release of orders on stop), over-limit hold on amended orders, the watch
status added to the existing CreditStatus.php instead of a parallel
mapping, install/upgrade/demo seeds consistent, '1000-01-01' dates, a
ledger reconciliation page. Where code was better: the portal, netting
unallocated receipts before chasing, authority split (settings on the
director's token), foreign keys, Z_CheckDebtorsControl extended,
DatabaseTranslations. One try per arm: no difference beyond noise; hrono
cost 74% more.

### t12: how the hrono agent used the map (analysis, no new runs)

From the t12 transcripts (tool calls, results and context size per call):

| | code | hrono |
|---|---|---|
| source reads / greps | 61 / 78 | 59 / 58 |
| source text read (chars) | 312k | 299k |
| map pages read (chars) | 0 | 25 (490k) |
| context at the last call | | 587k tokens |
| cache reads / cost | 26.2M / $8.35 | 51.8M / $14.56 |

- The map was added to source reading, not used instead of it: hrono read
  as much source as code-only, plus about 120k tokens of briefs (leaf
  briefs are 20-27k characters each). The extra context, re-read on every
  call, is the 74% extra cost.
- Timing: root.md, 3 area briefs and 3 leaf briefs were read before the
  first write (call 76 of 264). The other 18 pages were read after code
  was written: 9 right after the gate refused an edit (12 of the 22 tool
  errors are gate refusals), the rest just before editing that file.
  Reading came after the design.
- Gaps: new files (CreditControlFunctions.php, CustomerCredit.php,
  CreditCharges.php, BadDebtWriteOff.php...) have no brief, so the gate
  never asks for the briefs of the flows they copy. hrono posted GL
  entries and allocations without reading the receipt (49), allocation
  (214), period utility (57), GL journal (124) or GL-thread (215) briefs.
  It built the customer portal without the login rule: brief 48, read
  after CustomerCredit.php was written, says only `CustomerLogin==1`, and
  hrono checked `$_SESSION['CustomerLogin']`, which is never set.
- Briefs read did not convert: of the 40 B rules, 18 have a source brief
  hrono read (hrono 11, code 12) and 22 do not (hrono 15.5, code 13.5).
  Few pages were off-target (two install schema briefs the gate asked for
  when editing salesorders.sql).
- Recall attached 3 passages (5k characters) matched to the task
  statement, which only points at task/task.md: an API invoice comment,
  the credit-limit check in SelectOrderItems.php and a seed row. Noise.

Next: amendment 12 (plan from the map before code, no recall).

Duplication between briefs and code in t12 hrono (Read results only, 250k
characters of source): 165k were files it then changed; 85k were files it
never changed, of which 18k the BRD and 65k files whose brief existed but
was not read (SQL_CommonFunctions.php, UpgradeDB_mysqli.php,
InstallFunctions.php, CustomerAllocations.php: the helpers and flows a
brief would have described). Code read for a file whose brief was already
read, without changing that file: under 1k. So the agent did not read
code it had from briefs; it read code instead of briefs, and read briefs
for the files it was about to change. The brief gate was removed and
amendment 12 rewritten to say exactly that: briefs for understanding,
code only where it changes.

### t12 hrono try 2 (amendment 12: briefs for understanding, no gate, no recall)

Graded blind against code-only try 1 (coin 0: A = code-1, B = hrono-2;
grading/t12-credit-control-try2/). Code-1 was re-graded by a fresh grader
and got the same checklist scores as before.

| | code-1 | hrono-1 | hrono-2 |
|---|---|---|---|
| A (BRD) /43 | 38 | 40 | 39.5 |
| B (rules) /40 | 25.5 | 26.5 | 25.5 |
| review /10 | 6 (vs h1), 5 (vs h2) | 5 | 6 |
| cost / minutes | $8.35 / 19 | $14.56 / 21 | $7.49 / 17 |
| source read | 312k | 299k | 196k |
| map read | 0 | 25 pages, 490k | 9 pages, 159k |
| peak context | 355k | 591k | 348k |

Reviewer: "B, barely": B enforces holds on every route including API
invoicing and releases pre-stop orders, has a working month-end
reconciliation and a go-live loader. A has the more careful ledger code
and portal isolation, but its install breaks every menu and it breaks
Customer Maintenance.

hrono repeated try 1's portal bug: `$_SESSION['CustomerLogin']`, never
set. Cause found in the map: the sales-order-entry leaf brief (37), read
in both tries, lists `CustomerLogin` among session keys; in the code it
is the local `$CustomerLogin` set by session.php. The correct rule is in
the session bootstrap brief (50), not read in either try. A brief error
the agent followed.

### t12 hrono try 3 (amendment 13: Grep the map, CustomerLogin briefs fixed by hand)

Graded blind against code-only try 1 (coin 1: A = hrono-3, B = code-1;
grading/t12-credit-control-try3/). Only hrono-3 was checklist-graded;
code-1 keeps its two identical grades (38 / 25.5).

| | code-1 | hrono-2 | hrono-3 |
|---|---|---|---|
| A (BRD) /43 | 38 | 39.5 | 37 |
| B (rules) /40 | 25.5 | 25.5 | 24 |
| review /10 | 5 (vs h2), 6.5 (vs h3) | 6 | 5 |
| cost / minutes | $8.35 / 19 | $7.49 / 17 | $6.06 / 15 |
| source read | 312k | 196k | 213k |
| map read | 0 | 9 pages, 159k | 4 pages, 76k |
| Grep calls on the map | 0 | 0 | 3 of 55 |

The portal is now right (customer from `www_users.customerid`, B31 met).
But the agent read less of the map, not more: 3 searches on the map, then
only root.md, one area brief and two leaf briefs. Reviewer: "B (code),
somewhat": code delivers more of the request (over-limit holds and
releases, aged-debtors status, an authority model, ledger agreement in
the existing integrity tool) and its dunning skips customers who paid;
hrono-3 misses BR-10, shares credit authority with purchasing and AR
clerks, breaks the demo install, and its dunning can send a final notice
right after a payment.

### t12 hrono try 4 (amendment 14), stopped at call 53

Stopped by hand at call 53, before any edit (partial transcript:
runs/t12-credit-control-hrono-4.stopped.jsonl). It read root.md, Grep'd
the map once, read 4 briefs (37, 105, the 149 area) and then went to the
source the same way as before: UpgradeDB_mysqli.php, InstallFunctions.php,
CustomerReceipt.php, Credit_Invoice.php, DeliveryDetails.php,
RecurringSalesOrdersProcess.php and the install SQL. "Learn the system
from the briefs, not from the code" and "read what Grep finds in full" did
not change the reading. Not graded.

### t12 hrono try 5 (amendment 15), stopped at call 42

Stopped by hand at call 42 (runs/t12-credit-control-hrono-5.stopped.jsonl).
The session note was delivered (it is in the transcript). The agent read
the BRD, root.md, then went to code; by call 10 it wrote "I've settled the
design direction". It read 2 leaf briefs (25, 221) and no area brief.

Map pages read (root.md included, unique) before the first code search or
code read, all t12 hrono tries:

| try | where the map instruction was | Grep sentence | pages before code |
|---|---|---|---|
| 1 | prompt (middle dose) | no | 6 |
| 2 | prompt (amendment 12) | no | 6 |
| 3 | prompt (amendment 13) | yes | 1 |
| 4 | prompt (amendment 14) | yes | 4 |
| 5 | session note only, listing in prompt | yes (in note) | 1 |

The most map before code came with the instruction in the prompt and no
Grep sentence.
