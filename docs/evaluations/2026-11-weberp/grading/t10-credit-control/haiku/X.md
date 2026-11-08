# t10 credit control: grading of run X

Graded blind against `tasks/t10-credit-control/checklist.md`, from the code
in the workspace (`blindh/X/`), not from NOTES.md. Files changed: five new
pages (`CreditReviews.php`, `CreditReminders.php`, `CreditReport.php`,
`CreditCharges.php`, `CreditWriteOffs.php`), four `install/sql/tables/*.sql`,
`sql/updates/44.php`, a 11-line hunk in `SelectOrderItems.php`, NOTES.md.
No other existing file was touched.

## A. The request

| Id | Score | Justification |
|---|---|---|
| A1 | 1 | `install/sql/tables/creditreviews.sql:1-16`: debtorno FK to debtorsmaster, reviewdate, reviewedby, outcome enum, newlimit, nextreviewdate, comments `text`. |
| A2 | 0.5 | `CreditReviews.php:69-106` wraps insert and debtorsmaster update in one transaction, but hold goes to a new `creditlimithold` column (`:85,:89`), not `holdreason`; update errors are not checked before commit (`:98`). |
| A3 | 0 | Column added only by `sql/updates/44.php:7-8` with 7 args to the 6-arg `AddColumn` (After = '' -> `AFTER ```, fails); not in `install/sql/tables/debtorsmaster.sql`; never set on customer create (`Customers.php` untouched). |
| A4 | 0.5 | History newest first `CreditReviews.php:146-148`; no edit/correct of a review anywhere. |
| A5 | 0.5 | `CreditReport.php:52-121`: balance, limit, last paid, days filter; no overdue amount, no available credit, no PDF. |
| A6 | 0 | Watch = `creditlimithold=1` but no review outcome sets it (`CreditReviews.php:198-204`); warning in `SelectOrderItems.php:444-451` is dead (query at `:416-426` does not select `creditlimithold`). |
| A7 | 0 | All pages `NewScript(..., 2)` `sql/updates/44.php:88-92`; tokens created but never checked; hold/release on the same page as every review. |
| A8 | 0.5 | Three levels on PastDueDays1/2 `CreditReminders.php:30-65`, but "past due" = `trandate < CURDATE()` (`:46`), days counted from invoice date, not due date. |
| A9 | 0.5 | Preview with checkboxes and send `CreditReminders.php:156-217`; repeat guard only within the same calendar month and exact invoice-list string (`:118-126`). |
| A10 | 0 | No PDF and no email at all; a row is inserted as "sent" (`CreditReminders.php:131-140`). |
| A11 | 0 | No reminder history on any customer page. |
| A12 | 0.5 | User-started run `CreditCharges.php:45-136`, but fee charged to every customer, not per final notice (`:87-89`); rate hard 1 (`:100`); `$_SESSION['Period']` is never set in webERP, so the insert SQL is broken. |
| A13 | 0 | debtortrans as type 16 = "Location Transfer" (`CreditCharges.php:94-100`); one-sided gltrans with no receivables leg (`:115-122`). |
| A14 | 0.5 | Chosen invoices or whole balance with reason `CreditWriteOffs.php:63-95`; account from config; no customer transaction, one-sided GL (`:108-114`), invoices only flagged `settled=1` (`:119-128`). |
| A15 | 0 | No manual page. |

**A = 5 / 15**

## B. Rules away from the change

| Id | Score | Justification |
|---|---|---|
| B1 | 0 | Parallel hold flag `debtorsmaster.creditlimithold` (`sql/updates/44.php:7`, `CreditReviews.php:85`). |
| B2 | 0 | `ConfirmDispatch_Invoice.php` untouched. |
| B3 | 0 | `RecurringSalesOrdersProcess.php` untouched. |
| B4 | 0 | `EDIProcessOrders.php` untouched. |
| B5 | 0 | `api/api_salesorders.php` untouched. |
| B6 | 0 | No GetCreditAvailable/CheckCreditLimits use; report has no available credit. |
| B7 | 0 | `Z_ChangeCustomerCode.php` untouched; four new debtorno tables with FK RESTRICT will block the code change. |
| B8 | 0 | `Customers.php` delete guard untouched; FK RESTRICT makes the final debtorsmaster delete fail after branches/contacts were already deleted. |
| B9 | 0 | `Z_ImportDebtors.php` untouched. |
| B10 | 0 | API customer functions untouched. |
| B11 | 0 | Reuses type 16 (Location Transfer) for charges (`CreditCharges.php:94`); write-off has no type. |
| B12 | 0 | `GetNextTransNo(16, ...)` outside any transaction (`CreditCharges.php:94`). |
| B13 | 0 | `$_SESSION['Period']` (`CreditCharges.php:100,119`; `CreditWriteOffs.php:112`), no GetPeriod. |
| B14 | 0 | No gllink_debtors check, no debtorsact leg. |
| B15 | 0 | No EnsureGLEntriesBalance; GL entries one-sided. |
| B16 | 0 | No division by rate; write-off posted positive to expense only. |
| B17 | 0 | No InsertGLTags. |
| B18 | 0 | No control-account check on CreditWriteOffGLCode. |
| B19 | 0 | Type 16 not allocatable; write-off sets `settled` instead of allocating. |
| B20 | 0 | No exchange difference handling. |
| B21 | 0 | `CustomerAccount.php`/`CustomerInquiry.php` untouched. |
| B22 | 0 | debtortrans insert has no salesperson (`CreditCharges.php:96-100`). |
| B23 | 1 | Own guard: creditcharges for the customer in the current month (`CreditCharges.php:64-73`). |
| B24 | 0 | Accounts kept as config values (`sql/updates/44.php:83-84`), not companies columns. |
| B25 | 0 | Past due from `trandate < CURDATE()` (`CreditReminders.php:46`, `CreditCharges.php:58`), no daysbeforedue/dayinfollowingmonth. |
| B26 | 0 | Filters `settled = 0` with balance (`CreditReminders.php:44-45`) and write-off writes `settled=1` (`CreditWriteOffs.php:119-128`). |
| B27 | 0 | First contact with any email, no `statement=1` (`CreditReminders.php:92-96`). |
| B28 | 0 | No PDF. |
| B29 | 0 | No SendEmailFromWebERP. |
| B30 | 0 | No SalesmanLogin filter anywhere. |
| B31 | 0 | No customer-login restriction; pages at token 2. |
| B32 | 0 | Tokens via `NewSecurityToken('Credit_Control_Manager', ...)` (string id into int tokenid, `sql/updates/44.php:95-96`), never enforced; no false script. |
| B33 | 0.5 | NewScript in `sql/updates/44.php:88-92` and no `$PageSecurity` in the pages; no scripts.sql/demo.sql rows. |
| B34 | 0.5 | `sql/updates/44.php` with CreateTable exact names and guarded UpdateDBNo (`:98-100`, not one line); AddColumn and NewSecurityToken calls are wrong, so the update errors and never records. |
| B35 | 1 | `install/sql/tables/credit{reviews,reminders,charges,writeoffs}.sql`, no zero dates. |
| B36 | 0 | No install/sql/data or install/sql/demo.sql seeds. |
| B37 | 0 | No menu rows; NewConfigValue only, no config seeds, no SystemParameters.php. |
| B38 | 1 | AddColumn, CreateTable, NewConfigValue, NewScript, NewSecurityToken exist in all four UpgradeDB_* variants. |
| B39 | 0 | Raw HTML forms, no UIGeneralFunctions; `AddslashesForSQL($_POST[...])` double-escapes (`CreditReviews.php:72-75`, `CreditWriteOffs.php:102-104`). |
| B40 | 0.5 | `$ViewTopic/$BookMark/$Title` before header.php in every page; BookMark `CreditControl` points to no manual page, no ManualOutline entry. |

**B = 4.5 / 40**

## Totals

A 5/15, B 4.5/40, all 9.5/55. Correctness 1/5. Conventions 1/5.

## Correctness notes

- Upgrade 44 cannot complete: `AddColumn` gets 7 args (After becomes `''`),
  `NewSecurityToken` gets a string id; errors keep UpdateDBNo from running,
  and the debtorsmaster columns never exist. Fresh install also lacks them.
  Every new page then fails on `creditlimithold`/`nextreviewdate`.
- `CreditReviews.php:65` uses `ConvertSQLDate` on a user date (wrong
  direction; should be FormatDateForSQL).
- Charges: `$_SESSION['Period']` undefined; `'...' || '...'` in MySQL is a
  logical OR; no branchcode in debtortrans insert; no transaction.
- Reminders are recorded as sent without being sent (NOTES admits it).
- Hold not enforced on any route: the only hook (`SelectOrderItems.php:444`)
  reads a field the query does not select.

## Regressions

- Upgrade path left in error: DB stays at 43 and 44 re-runs with errors.
- Customer delete (`Customers.php`) now fails half-way for customers with
  credit rows (FK RESTRICT), after branches and contacts are already gone.
- Customer code change (`Z_ChangeCustomerCode.php`) blocked by the new FKs.
- Write-off flags invoices `settled=1` while their balance and AR stay, and
  posts one-sided gltrans: ledger out of balance and AR control no longer
  matches customer accounts. Charges likewise one-sided and typed as
  Location Transfer.
