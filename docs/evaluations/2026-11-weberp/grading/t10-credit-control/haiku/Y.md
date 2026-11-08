# t10 credit control: grading of run Y

Grader: blind. Graded from Y.diff and the workspace Y/ against base 4cb937f79e8b.

The diff adds only new files: six pages (CreditReview.php, CreditHoldRelease.php,
CreditReviewDueReport.php, CreditReminders.php, CreditCharges.php,
CreditWriteOffs.php), includes/CreditControlFunctions.php, sql/updates/44.php and
NOTES.md. It changes no existing file: no order, invoice, EDI, API, customer,
inquiry, install, menu, config or manual file.

Key facts behind the scores:
- Every customer form holds the customer in an empty hidden input that nothing fills
  (CreditReview.php:107, CreditHoldRelease.php:120, CreditWriteOffs.php:82). The
  pages have no way to choose a customer, so every POST fails with "A customer must
  be selected". Reviews, hold/release and write-offs cannot be used.
- 44.php inserts into a `companysettings` table that does not exist in webERP
  (44.php:108; settings live in `config`). It also reads and writes `menuitems`
  using columns that do not exist (sortorder, parentmenu, menuitemid, description at
  44.php:132,147; the real columns are secroleid, modulelink, menusection, caption,
  url, sequence). The upgrade errors out partway through.
- includes/CreditControlFunctions.php is included by no page. CanPlaceOrder and the
  rest are dead code.
- Hold is a new parallel `debtorsmaster.holdstatus` enum (44.php:103) that nothing
  else in webERP reads.

## A. The request

| Id | Score | Justification |
|---|---|---|
| A1 | 0.5 | creditreviews has an FK, date, user, outcome, new limit, next date and longtext comments (sql/updates/44.php:7-26). It exists only in the upgrade script, and no working page can write to it (CreditReview.php:107). |
| A2 | 0 | Uses START TRANSACTION/COMMIT (CreditReview.php:62). It writes the parallel holdstatus, not holdreason (CreditReview.php:81), and relies on try/catch that DB_query never triggers. The screen also cannot be used. |
| A3 | 0 | Adds the nextreviewdate column (44.php:94). It is not set on customer create (Customers.php untouched), and the only writers are unusable screens. |
| A4 | 0 | History shows only on CreditReview.php?DebtorNo (CreditReview.php:170-200). It is not on the customer's page and cannot be edited. |
| A5 | 0 | Threshold is fixed at 30 days (CreditReviewDueReport.php:14) and there is no PDF. "Overdue" means older than 30 days, and "last paid" is MAX(trandate) of any settled row (:24), not the last receipt. |
| A6 | 0 | A 'watch' enum value exists (44.php:103), but no order or invoice screen warns on it. |
| A7 | 0 | CreditHoldRelease.php has token 3, the same as the other pages (44.php:121-128). No narrower permission. |
| A8 | 0 | Bands come from the new ReminderFirstBand/SecondBand with defaults 30/60 (CreditReminders.php:33), not PastDueDays1/2. Overdue is counted from trandate, not the due date. |
| A9 | 0 | Has a preview and selection. The no-repeat guard covers only the same customer, level and day (CreditReminders.php:62), not the invoices. Nothing is sent. |
| A10 | 0 | No PDF and no email. Rows are inserted with emailstatus 'sent' and invoices '' (CreditReminders.php:71). |
| A11 | 0 | No reminder history on the customer's page. GetCustomerReminders (CreditControlFunctions.php) is never called. |
| A12 | 0 | User-started run, but it only inserts creditcharges rows (CreditCharges.php:81,114): no currency handling, no posting. |
| A13 | 0 | No debtortrans and no gltrans rows. |
| A14 | 0 | Records a free-text creditwriteoffs row (CreditWriteOffs.php:62). Nothing is cleared or posted, there is no bad debt account, and the screen cannot be used. |
| A15 | 0 | No manual page. $ViewTopic 'CreditControl' points at nothing. |

**A = 0.5 / 15**

## B. Rules away from the change

| Id | Score | Justification |
|---|---|---|
| B1 | 0 | Parallel hold flag debtorsmaster.holdstatus (44.php:103). holdreason/dissallowinvoices are not used. |
| B2 | 0 | ConfirmDispatch_Invoice.php untouched. |
| B3 | 0 | RecurringSalesOrdersProcess.php untouched. |
| B4 | 0 | EDIProcessOrders.php untouched. |
| B5 | 0 | api_salesorders.php untouched. |
| B6 | 0 | Invents a CreditLimitCheckType config with a parallel balance formula (CreditControlFunctions.php:39-68,125). CheckCreditLimits and GetCreditAvailable are ignored. |
| B7 | 0 | Z_ChangeCustomerCode.php untouched. The ON DELETE RESTRICT FKs (44.php:24,43,64,84) will block its debtorno update. |
| B8 | 0 | Customers.php delete untouched. The FKs make the delete fail with a raw DB error instead of a guarded message. |
| B9 | 0 | Z_ImportDebtors.php untouched. |
| B10 | 0 | api_debtors.php untouched. The new columns are not validated. |
| B11 | 0 | No systypes rows and no reused type. |
| B12 | 0 | No GetNextTransNo. |
| B13 | 0 | No GetPeriod and no ProhibitPostingsBefore check. |
| B14 | 0 | No GL posting. |
| B15 | 0 | No EnsureGLEntriesBalance. |
| B16 | 0 | No GL amounts. |
| B17 | 0 | No InsertGLTags. |
| B18 | 0 | No write-off account and no control-account check. |
| B19 | 0 | Nothing allocatable. CustomerAllocations.php untouched. |
| B20 | 0 | No exchange difference handling. |
| B21 | 0 | CustomerAccount.php and CustomerInquiry.php untouched. |
| B22 | 0 | No debtortrans rows, so no salesperson. |
| B23 | 0 | The month guard only warns and then charges anyway (CreditCharges.php:43-54). It checks the current calendar month, not the charge month. |
| B24 | 0 | GL codes are put into a non-existent companysettings table (44.php:108-117). No companies columns, CompanyPreferences entry or GLAccounts guard. |
| B25 | 0 | Overdue is counted from trandate with fixed 30/60-day intervals (CreditReminders.php:44, CreditCharges.php:61). No daysbeforedue/dayinfollowingmonth, no PastDueDays. |
| B26 | 0 | Filters open items with `settled = 0` alongside balance (CreditReminders.php:45, CreditCharges.php:65). Uses settled = 1 for last paid (CreditReviewDueReport.php:24). |
| B27 | 0 | No recipients selected. custcontacts is not used. |
| B28 | 0 | No PDF at all. |
| B29 | 0 | No SendEmailFromWebERP. Rows are marked 'sent' unconditionally (CreditReminders.php:71). |
| B30 | 0 | No SalesmanLogin filter on any list (e.g. CreditReviewDueReport.php:19-27, CreditCharges.php:150). |
| B31 | 0 | No CustomerLogin handling, and the pages are open to anyone with token 2/3. |
| B32 | 0 | No hold/release permission entry. |
| B33 | 0 | Raw INSERT into scripts in 44.php:121 only. No NewScript, no scripts.sql or demo.sql seeds. |
| B34 | 0 | 44.php uses raw CREATE TABLE IF NOT EXISTS and INSERTs, not the idempotent helpers. It writes to non-existent tables and columns (44.php:108,132,147), and the UpdateDBNo guard is a multi-line block (:152-154). |
| B35 | 0 | No install/sql/tables files. |
| B36 | 0 | No seeds in install/sql/data or install/sql/demo.sql. |
| B37 | 0 | Menu rows go in with the wrong schema and no roles (44.php:147). No NewConfigValue, config seeds or SystemParameters.php entries. |
| B38 | 0 | No upgrade helpers used at all. information_schema queries are MySQL-only (44.php:90,99). |
| B39 | 0 | Hand-written fieldset HTML, not UIGeneralFunctions. POST values already escaped by session.php are escaped again (CreditReview.php:75 DB_escape_string($Comments); CreditWriteOffs.php:65). |
| B40 | 0 | No $Title before header.php (e.g. CreditReview.php:5-7), no manual page and no ManualOutline.php entry. |

**B = 0 / 40**

## Totals

A 0.5/15, B 0/40, all 0.5/55. Correctness 0/5, conventions 1/5.

- **Correctness 0:** the upgrade fails partway (non-existent companysettings table, wrong menuitems columns). No screen that needs a customer can be used, nothing posts to the ledger, nothing is emailed, and no route is blocked for held customers.
- **Conventions 1:** session.php, __(), prnMsg, FormID and locale_number_format are used. Everything else departs from webERP conventions.

## Regressions

- sql/updates/44.php errors on every upgrade: INSERT into missing `companysettings` (:108) and SELECT/INSERT on missing `menuitems` columns (:132,147). The DB version may not be bumped, and the upgrade keeps re-running.
- The new FKs with ON DELETE RESTRICT (44.php:24,43,64,84) make Customers.php delete and Z_ChangeCustomerCode.php fail with raw DB errors once a customer has any credit row.
- The ALTERs at 44.php:94,103 run only in the upgrade. A new install has no nextreviewdate or holdstatus, so every new page fails with SQL errors there. demo.sql and the install tables are untouched.
- information_schema checks are MySQL-only. Other supported databases are not handled.
