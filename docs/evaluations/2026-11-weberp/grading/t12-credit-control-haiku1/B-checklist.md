# t12 credit control: run B checklist

Paths are relative to the workspace `blindhk/B/`. Base is `scratchpad/base/`.

## What the diff contains

- New `CreditReviews.php`: a search page plus a review form.
- New `includes/CreditControlFunctions.php`. No file includes it.
- 10 new `install/sql/tables/credit*.sql`, `interestfee*.sql` and `reminderletter*.sql` files.
- New `sql/updates/44.php`.
- Three Markdown files: `NOTES.md`, `INTEGRATION_GUIDE.md` and `IMPLEMENTATION_SUMMARY.md`.
- No existing file changed.
- `CreditStatus.php` is described in the summary as "fully implemented". It is the unchanged base hold-reasons maintenance page; the diff has no change to it.
- Reminders, charges, write-offs, the dashboard and every order-path integration exist only as prose in the .md files.

## Defects that affect the whole run

1. **`CreditReviews.php` can't be opened.** No `scripts` row was added. `includes/session.php:331-337` looks up `$PageSecurity` from `PageSecurityArray` and, finding nothing, denies access. The page then sets its own lowercase `$page_security = 'CreditControl'` after session.php has already run (`CreditReviews.php:3`). That string is not a token number, so the page's own check at `:12` would deny access as well.
2. **The upgrade script doesn't work.**
   - `AddColumn` is called with column and table swapped and with too few arguments (`sql/updates/44.php:6-8`). The signature is `AddColumn($Column, $Table, $Type, $Null, $Default, $After)` (`base/includes/UpgradeDB_mysqli.php:233`), so `debtorsmaster.creditstatus`, `nextreviewdate` and `lastreviewed` are never added.
   - `CreateTable` is passed a file name (`'creditreviews.sql'`) where it expects SQL text (`44.php:11-20`; `UpgradeDB_mysqli.php:522` executes `$SQL . ' ENGINE=...'`). Every table creation fails.
   - The seed INSERTs and the `UPDATE debtorsmaster SET nextreviewdate` then fail too (`44.php:23-32`).
3. **Fresh installs miss the new columns.** `install/sql/tables/debtorsmaster.sql` was not given them. On both install paths, `CreditReviews.php:75` (SELECT `d.creditstatus`) and `:42` (UPDATE `nextreviewdate`) would fail.
4. **The review form posts without `FormID`** (`CreditReviews.php:129`). It also runs `filter_var(FILTER_SANITIZE_STRING)` on POST values that session.php has already escaped (`:23-27`).

## A. BRD requirements (BR-01..BR-43)

| # | Score | Evidence |
|---|---|---|
| A1 | 0.5 | `CreditReviews.php:21-34,149-176` records date, user, decision, new limit, notes and next review date. But the page is unreachable (defect 1) and `creditreviews` is never created on upgrade (defect 2). |
| A2 | 0 | New customers get no review date: `Customers.php` is unchanged. The backfill for existing customers, `44.php:32`, fails because the column was never added. |
| A3 | 0.5 | History list at `CreditReviews.php:186-215`, with no edit or delete path. Same reachability problem as A1. |
| A4 | 0.5 | `CreditReviews.php:38-40` updates `creditlimit` after the review INSERT. It is a separate, non-transactional statement, and the page is unreachable. |
| A5 | 0 | No stop/watch change page: `CreditStatus.php` is the unchanged base hold-reason maintenance page. A review decision of `put_on_stop` (`CreditReviews.php:156`) changes no status. |
| A6 | 0 | No order path changed: SelectOrderItems, the web shop, EDIProcessOrders, RecurringSalesOrdersProcess and ConfirmDispatch_Invoice are all untouched. `CheckCreditStop` (`includes/CreditControlFunctions.php:53`) is never called. |
| A7 | 0 | The permission is the hard-coded string `'CreditControl'` (`CreditReviews.php:3`). `Customers.php` still allows limit edits as before. |
| A8 | 0 | `CheckCreditWatch` (`CreditControlFunctions.php:64`) is never called. There is no list of watched-customer orders. |
| A9 | 0 | Status appears only in the unreachable review list (`CreditReviews.php:103`), not on customer or order screens. |
| A10 | 0 | No over-limit hold. NOTES.md says "hold for approval", but it is not implemented. |
| A11 | 0 | The web shop is unchanged. |
| A12 | 0 | Only a config table (`install/sql/tables/reminderlettersconfig.sql`) and seeds in the broken `44.php:23-26`. No run and no UI for Finance. |
| A13 | 0 | No email sending and no list of customers without email. |
| A14 | 0 | No reminder run or preview. |
| A15 | 0 | `ShouldSendReminder` (`CreditControlFunctions.php:143`) is unused and has no stage logic. |
| A16 | 0 | The `reminderlettersent.sql` table exists, but nothing writes to it. |
| A17 | 0 | No letters. |
| A18 | 0 | The `creditdisputedinvoices.sql` table exists, but there is no UI and no consumer. |
| A19 | 0 | The `interestfeeconfig.sql` table exists, but there is no charge run. |
| A20 | 0 | The `creditcustomerexemptions.sql` table exists, but there is no UI and no consumer. |
| A21 | 0 | No charges are raised. |
| A22 | 0 | No preview or confirm step. The unique key in `interestfeesposted.sql:15` is never exercised. |
| A23 | 0 | No GL posting. |
| A24 | 0 | No waiver. |
| A25 | 0 | No write-off function. |
| A26 | 0 | The `creditwriteoffs.sql` columns exist, but there is no workflow. |
| A27 | 0 | No posting. |
| A28 | 0 | No automatic stop. |
| A29 | 0 | No write-off report. |
| A30 | 0 | No credit control report (`CreditControlDashboard.php` does not exist). |
| A31 | 0 | `AgedDebtors.php` is unchanged. |
| A32 | 0 | The `creditcontrolactions.sql` table exists, but `RecordCreditAction` (`CreditControlFunctions.php:104`) is never called and there is no history view. |
| A33 | 0 | No rep filter: the list query at `CreditReviews.php:75-78` returns all customers. |
| A34 | 0 | Rests only on the hard-coded string token (see A7). Base screens are unchanged. |
| A35 | 0 | The portal is unchanged. |
| A36 | 0 | Nothing new is visible in the portal. |
| A37 | 0 | No postings, so nothing to reconcile. |
| A38 | 0 | No reconciliation aid. |
| A39 | 0 | The upgrade fails (defect 2). Fresh installs lack the `debtorsmaster` columns (defect 3). |
| A40 | 0 | The review-date backfill is broken (`44.php:32`). The stop-list load exists only as prose in NOTES.md. |
| A41 | 1 | No existing page, posting or statement was modified. |
| A42 | 0 | No manual page. NOTES.md and INTEGRATION_GUIDE.md are developer documents, not the staff guide. |
| A43 | 0 | No note for sales staff. |

**A = 2.5 / 43**

## B. Rules away from the change

| # | Score | Evidence |
|---|---|---|
| B1 | 0 | Adds a parallel hold flag: `debtorsmaster.creditstatus` enum plus a `creditstatus` table (`44.php:6`, `install/sql/tables/creditstatus.sql`). |
| B2 | 0 | `ConfirmDispatch_Invoice.php` is unchanged. |
| B3 | 0 | `RecurringSalesOrdersProcess.php` is unchanged. |
| B4 | 0 | `EDIProcessOrders.php` is unchanged. |
| B5 | 0 | `api_salesorders.php` is unchanged. |
| B6 | 0 | `CheckCreditLimitWithOrder` (`CreditControlFunctions.php:75-102`) is a parallel formula: it ignores `CheckCreditLimits` and doesn't use `GetCreditAvailable`. |
| B7 | 0 | `Z_ChangeCustomerCode.php` is unchanged, although it has 10 new `debtorno` tables and 3 new columns to handle. |
| B8 | 0 | The `Customers.php` delete is unchanged. The new FK tables would block it, but with a raw FK error rather than a handled check. |
| B9 | 0 | `Z_ImportDebtors.php` is unchanged. |
| B10 | 0 | The API is unchanged. |
| B11 | 0 | No `systypes` rows. |
| B12 | 0 | No transactions. |
| B13 | 0 | No `GetPeriod` call. |
| B14 | 0 | No GL rows. |
| B15 | 0 | No `EnsureGLEntriesBalance` call. |
| B16 | 0 | No GL amounts. |
| B17 | 0 | No `InsertGLTags` call. |
| B18 | 0 | No write-off account check. |
| B19 | 0 | `CustomerAllocations.php` is unchanged. |
| B20 | 0 | No exchange difference handling. |
| B21 | 0 | `CustomerAccount.php` and `CustomerInquiry.php` are unchanged. |
| B22 | 0 | No `debtortrans` rows are written. |
| B23 | 0 | No charge run. A unique key exists (`interestfeesposted.sql:15`) but nothing uses it. |
| B24 | 0 | GL codes are stored in `interestfeeconfig` (`interestfeeconfig.sql:7-8`), not in `companies`. Nothing in GetConfig, CompanyPreferences or GLAccounts. |
| B25 | 0 | `GetCustomerOverdueBalance` uses `trandate <= today - N` (`CreditControlFunctions.php:41-43`). There is no `daysbeforedue`/`dayinfollowingmonth` rule and no `PastDueDays` setting. |
| B26 | 0 | `CreditControlFunctions.php:26-27,42-43` filter on `settled = 0`, in helpers no page calls. |
| B27 | 0 | No recipients. |
| B28 | 0 | No PDFs. |
| B29 | 0 | No email. |
| B30 | 0 | No `SalesmanLogin` filter (`CreditReviews.php:75-78`). |
| B31 | 0 | No customer-login guard on the new page. |
| B32 | 0 | Hard-coded string token `'CreditControl'` (`CreditReviews.php:3,12`). No scripts-table entry. |
| B33 | 0 | No `NewScript`, no `scripts.sql`/`demo.sql` rows, and a token variable is set inside the page (`CreditReviews.php:3`). |
| B34 | 0.5 | `sql/updates/44.php` exists and uses the `AddColumn`/`CreateTable` helpers with the exact table names. But the arguments are wrong (defect 2), the seed INSERTs are raw and not idempotent (`:23-29`), and the `UpdateDBNo` guard spans 3 lines (`:34-36`). |
| B35 | 1 | `install/sql/tables/<table>.sql` exists for all 10 new tables, with no zero dates. |
| B36 | 0 | Seeds only in `44.php`. Nothing in `install/sql/data/*.sql` or `install/sql/demo.sql`. |
| B37 | 0 | No `NewMenuItem` call, no config values, and `SystemParameters.php` is unchanged. |
| B38 | 1 | Uses only `AddColumn`/`CreateTable`, which exist in all four `UpgradeDB_*` variants. No `AddCalculatedColumn`. |
| B39 | 0 | Raw HTML form with no `FormID` and no UIGeneralFunctions. POST values are escaped twice with `FILTER_SANITIZE_STRING` (`CreditReviews.php:23-27,61,129`). |
| B40 | 0 | `$title` (lowercase) is set after `header.php` (`CreditReviews.php:4,19`). No `$ViewTopic`/`$BookMark`, no manual page, no ManualOutline entry. |

**B = 2.5 / 40**

## Totals

- A = 2.5 / 43
- B = 2.5 / 40
- Total = 5 / 83
- Correctness = 0 / 5. Nothing reachable works: the only new page is blocked by session.php, the upgrade fails, and the order-path integrations were never applied.
- Conventions = 1 / 5. The table files and the `sql/updates/44.php` location are right. Everything else is wrong: the `_()`/`__()` mix, a lowercase `$title` after the header, a string token, raw HTML forms, no FormID, double escaping, no scripts or menu rows.

## Regressions

- **The upgrade to DB version 44 breaks.** `44.php:11-20` hands file names to `CreateTable` as SQL, and `AddColumn` gets swapped and missing arguments. This produces upgrade errors, `UpdateDBNo` is skipped, and the database stays at version 43 with a failing script.
- **Re-running the upgrade adds more seed errors.** The raw `reminderlettersconfig` INSERT (`44.php:23`) hits the unique key on `stage` if a table ever exists.
- **Customer deletes would fail with a raw FK error.** On fresh installs the new FK-constrained tables on `debtorsmaster.debtorno` would turn the `Customers.php` delete and `Z_ChangeCustomerCode.php` into raw FK errors once rows exist. Rows can't currently be written, since the page is unreachable.
- **No change to existing runtime behaviour**, because no existing file was edited.
