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
