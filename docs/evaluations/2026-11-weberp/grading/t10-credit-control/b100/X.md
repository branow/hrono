# t10 credit control: blind grade of run X

Inputs: `tasks/t10-credit-control/brd.md`, `checklist.md`, `grading/t10-credit-control/rules/*.md`, the diff `blind/X.diff` and the workspace `blind/X/`, checked against `base/`. Claims were checked in the code; NOTES.md was not taken as evidence. Line numbers refer to files in `X/`.

**Totals: A 14.5/15, B 33.5/40, all 48/55. Correctness 4/5, conventions 4/5.**

## A. The request (15)

| id | score | justification |
|---|---|---|
| A1 | 1 | `install/sql/tables/creditreviews.sql` and `sql/updates/44.php:13-34`: keyed on debtorno with an FK to debtorsmaster; reviewdate, userid, outcome, old/new limit, old/new holdreason, nextreviewdate, `comments text`. |
| A2 | 1 | `includes/CreditControlFunctions.php` `CreditSaveReview`: DB_Txn_Begin, then the review INSERT and the debtorsmaster UPDATE (creditlimit, holdreason, nextreviewdate), both with `$Transaction=true`, then commit. |
| A3 | 1 | `debtorsmaster.nextreviewdate` (`install/sql/tables/debtorsmaster.sql`, 44.php:7). It is set by a review, on create in `Customers.php:254`, in the `Z_ImportDebtors.php` insert and by the API `InsertCustomer` default. 44.php:113-123 back-fills existing customers. |
| A4 | 0.5 | `CreditReviews.php`: history newest first (`ORDER BY reviewdate DESC, id DESC`), linked from `CustomerInquiry.php:163` and the `Customers.php` edit form. A mistaken review can only be voided (struck through, `CreditReviews.php` VoidReview block), not edited, and voiding does not undo the limit or hold change. The item says "editable". |
| A5 | 1 | `CreditReviewDue.php`: days-ahead filter; shows balance, overdue (by reminder-level SQL), limit, `GetCreditAvailable`, lastpaiddate; Dompdf PDF. |
| A6 | 1 | `CreditStatus.php` can now define `dissallowinvoices=2`. `CreditInvoicingBlock` warns on watch and goes on (`DeliveryDetails.php:340`, `ConfirmDispatch_Invoice.php:769`). `CustomerInquiry.php:166` shows "ON WATCH". |
| A7 | 1 | Token 21, granted only to role 8 (`securitygroups.sql`, 44.php). `CreditSaveReview` requires it. `Customers.php` UPDATE no longer writes holdreason/creditlimit, and the API gates them. |
| A8 | 1 | `CreditReminderLevelSQL`: level 1 when due, 2 at PastDueDays1, 3 at PastDueDays2, using the AgedDebtors CASE logic. |
| A9 | 1 | `CreditReminders.php`: preview table, untick checkboxes, Send. The UNIQUE key `onceperlevel(debtortransid, reminderlevel)` plus the pending check stop a level being sent twice for the same invoices. |
| A10 | 1 | `SendReminder`: a Dompdf letter emailed to statement contacts. No contacts, a PDF failure or `$Sent !== true` rolls the DB rows back, and failures are listed under "Reminders NOT sent". |
| A11 | 1 | `CreditReviews.php` "Reminders Sent" table: date, level, recipients, invoices included. |
| A12 | 1 | `LateCharges.php`: user picks the month and customers. Interest is per invoice in the customer's currency; the fee is converted at the currency rate. |
| A13 | 1 | `CreditPostTransaction(13, …)`: a debtortrans row in customer currency, with gltrans debtorsact +, latechargeact − when gllink_debtors=1. |
| A14 | 1 | `BadDebtWriteOff.php`: chosen invoices or WholeBalance; a reason of at least 3 characters is required; type 14 posted to baddebtact and allocated to the invoices it clears. |
| A15 | 1 | `doc/Manual/ManualAccountsReceivable.html:33-55`: a Credit Control section with anchors CreditReviews, CreditReviewDue, CreditReminders, LateCharges, BadDebtWriteOff. |

## B. Rules away from the change (40)

| id | score | justification |
|---|---|---|
| B1 | 1 | Hold is holdreason → `holdreasons.dissallowinvoices` (0/1/2), `CreditControlFunctions.php` `CreditCustomerState`/`CreditHoldState`. There is no parallel flag; `creditreminders.onhold` is only a snapshot of the letter. |
| B2 | 1 | `ConfirmDispatch_Invoice.php:767-775` blocks before GetNextTransNo(10). |
| B3 | 1 | `RecurringSalesOrdersProcess.php:104-111`: on hold, it rolls back the open txn (begun at :95) and skips. |
| B4 | 1 | `EDIProcessOrders.php:895-901`: `$Order->DebtorNo` is set at :527/:624, and a held account stops `$CreateOrder`. |
| B5 | 1 | `api/includes/api_salesorders.php:278-283` (InsertSalesOrderHeader) and `:804-811` (InvoiceSalesOrder) return CustomerOnHold (1900). |
| B6 | 1 | No new credit-limit check, and CheckCreditLimits is untouched. `CreditReviewDue.php` uses `GetCreditAvailable`. |
| B7 | 1 | `Z_ChangeCustomerCode.php:113-124`: the four tables are moved, and nextreviewdate is carried by an UPDATE…JOIN right after the re-INSERT (not by adding it to the column list, but the column is kept in the same transaction). |
| B8 | 1 | `Customers.php:359-373`: creditreminderitems, creditreminders, creditcharges and creditreviews are deleted with the customer inside DB_Txn_Begin/Commit. |
| B9 | 0.5 | `Z_ImportDebtors.php:403-427`: the insert sets nextreviewdate to the default interval, but the column is not appended to `$FieldHeadings` (:37), so it cannot be imported. |
| B10 | 1 | `api_customers.php:359-368` (InsertCustomer: date validated with VerifyNextReviewDate/1901, default set, holdreason needs token 21) and `:499-506` (ModifyCustomer: creditlimit/holdreason/nextreviewdate need token 21). |
| B11 | 1 | systypes 13 "Late Payment Charge" and 14 "Bad Debt Write-off" are in `install/sql/data/systypes.sql`, `install/sql/demo.sql` and `NewSysType` (44.php:74-75). Both numbers were free at base. |
| B12 | 1 | `CreditPostTransaction` calls GetNextTransNo after DB_Txn_Begin (`LateCharges.php` Run loop, `BadDebtWriteOff.php:85-100`). |
| B13 | 0.5 | GetPeriod is used for prd and periodno, but there is no check against or display of ProhibitPostingsBefore (GetPeriod clamps silently). The charge date is the month end of a month that can be up to 12 months back. |
| B14 | 1 | `CreditPostTransaction`: GL rows only when `gllink_debtors == 1`; AR side is `companies.debtorsact` (read directly, same value as CompanyRecord). The write-off exchange-difference rows are gated too (`BadDebtWriteOff.php:116`). |
| B15 | 0 | No `EnsureGLEntriesBalance` anywhere in the new code (grep finds none in the 5 pages or `CreditControlFunctions.php`). |
| B16 | 1 | `$Local = round($Amount / $Rate)`. Charges pass a positive amount and write-offs `-$Total`. Debtors +, other account −. |
| B17 | 0.5 | `InsertGLTags($Tags)` is called once, after the second gltrans insert in `CreditPostTransaction`, so the debtors-control row is never tagged. The write-off exchange-difference rows get no tag call. |
| B18 | 1 | `CreditAccountPostable` refuses debtorsact/creditorsact/grnact/payrollact/commissionsact/retainedearnings and any non-P&L account. `BadDebtWriteOff.php:58` checks it. |
| B19 | 1 | Charges (type 13, settled=0) are listed as allocation targets in `CustomerAllocations.php` (base :262 selects any settled=0 type). The write-off is allocated through custallocns when posted (`BadDebtWriteOff.php:107-115`). |
| B20 | 1 | `BadDebtWriteOff.php:102-133`: per-invoice diff `amt/rate_wo − amt/rate_inv`, diffonexch updated, GL to salesexchangediffact and debtorsact under type 14, matching CustomerAllocations. |
| B21 | 0 | `CustomerAccount.php` is unchanged (it drops types other than 10/11/12). `CustomerInquiry.php` only gained a link and the watch banner, so types 13/14 have no print/email/allocate handling. |
| B22 | 1 | The debtortrans INSERT includes salesperson: the branch salesman (charges) or the invoice's salesperson (write-off). |
| B23 | 1 | `creditcharges` has UNIQUE `onceamonth(debtorno, chargemonth)`, plus a "done" pre-check and rollback on duplicate (`LateCharges.php` Run loop). |
| B24 | 0.5 | Done: companies columns, `CompanyPreferences.php` form and UPDATE, `GLAccounts.php` delete guard, `InstallFunctions.php` and `install/sql/demo.sql` positional INSERTs. Not done: the `GetConfig.php` column list / SHOW COLUMNS guard (the code reads companies directly instead). The demo seeds 8200/7900 do not exist in the demo chartmaster. |
| B25 | 1 | `CreditDueSQL`/`CreditOverdueBandSQL` copy `AgedDebtors.php:36-70` exactly (daysbeforedue vs ADDDATE(last_day, dayinfollowingmonth), PastDueDays1/2). |
| B26 | 1 | Open items are selected by `ROUND(debtortrans.balance, dp) > 0` everywhere; settled is never used as the filter. |
| B27 | 1 | `CreditReminders.php`: `custcontacts … statement=1`, filtered with IsEmailAddress and de-duplicated. |
| B28 | 1 | `CreditReminders.php` and `CreditReviewDue.php`: `use Dompdf\Dompdf`, `SetDomPDFOptions.php`, `new Dompdf($DomPDFOptions)`. |
| B29 | 0.5 | `$Sent !== true` counts as failed and the file is unlinked, but the temp PDF goes to `sys_get_temp_dir()`, not `$_SESSION['reports_dir']` (`CreditReminders.php` SendReminder). |
| B30 | 1 | `CreditSalesmanCustomerSQL`/`CreditSalesmanTransSQL` are applied in reminders, charges, the review-due report and the reminder/charge history, and `CreditCanSeeCustomer` guards the per-customer pages. |
| B31 | 0.5 | `CreditReviews.php` forces `$DebtorNo = $_SESSION['CustomerID']` for a customer login, but the page is registered at token 2 and the customer role (7) holds only tokens 0,1, and there is no customer menu link (index.php). A customer cannot reach their reminders and charges. |
| B32 | 0 | Hard-coded `define('CREDIT_CONTROL_TOKEN', 21)` and `in_array(CREDIT_CONTROL_TOKEN, AllowedPageSecurityTokens)` (`CreditControlFunctions.php:9-13`); no "false script" scripts row / PageSecurityArray lookup. |
| B33 | 1 | All 5 pages are in NewScript (44.php), `install/sql/data/scripts.sql` and `install/sql/demo.sql`; none sets $PageSecurity. |
| B34 | 1 | `sql/updates/44.php`: AddColumn/CreateTable (exact names, no ENGINE)/NewConfigValue/NewSysType/NewScript/NewMenuItem/InsertRecord/UpdateField. Guarded `UpdateDBNo(...)` on one line as in base 43.php. |
| B35 | 1 | `install/sql/tables/creditreviews.sql`, `creditreminders.sql`, `creditreminderitems.sql`, `creditcharges.sql`; '1000-01-01' sentinels, no zero dates. |
| B36 | 1 | Config, scripts, menuitems, systypes, securitytokens and securitygroups seeded in both `install/sql/data/*.sql` and `install/sql/demo.sql`. Every data file is still one statement. (The stale `sql/demo.sql` was also edited, which is harmless but unnecessary.) |
| B37 | 1 | Menu rows for roles 1-9 for all 5 pages in both seeds, and NewMenuItem in 44.php. NewConfigValue for 6 keys, plus config.sql, demo.sql and SystemParameters.php fields and saves. |
| B38 | 1 | Every helper used (NewSysType, NewSecurityToken, InsertRecord, UpdateField, AddColumn, CreateTable, NewMenuItem, NewScript, NewConfigValue) exists in all four UpgradeDB_* variants. No AddCalculatedColumn. |
| B39 | 0.5 | No double escaping (POST values are used as already escaped by session.php). The new pages' forms are hand-written `<select>`/`<input>`; UIGeneralFunctions is used only in the existing CompanyPreferences fields. |
| B40 | 1 | Every new page sets $Title/$ViewTopic='AccountsReceivable'/$BookMark before header.php. ManualAccountsReceivable.html has `id="AccountsReceivable"` and each bookmark anchor, and the topic is in ManualOutline.php:86. |

B items at 0: B15, B21, B32. B items at 0.5: B9, B13, B17, B24, B29, B31, B39.

## Correctness 4/5

The core flows are sound. Reviews are atomic. The hold gate covers all five routes. The reminder ageing matches AgedDebtors, with a DB-enforced no-repeat rule, and a failed email rolls back. Charges have a DB-enforced once-a-month rule. The write-off allocation and exchange difference mirror CustomerAllocations.

Defects:
- No GL balance check before commit.
- A customer login cannot open `CreditReviews.php` (token 2), so BRD 6.2 is not delivered.
- Charges and write-offs are invisible on `CustomerAccount.php`. Charges can be printed only through a `PrintCustTrans.php?InvOrCredit=Charge` link and have no email path.
- The demo default accounts 8200/7900 are not in the demo chart, so the new pages refuse to post until the accounts are re-chosen.
- `Customers.php:1008`: `isset($_POST['New']) AND CreditControlUser() ? '' : 'disabled…'` binds as `AND (…?…)`. The edit form's hold select is therefore never disabled, and it prints "1". The change is ignored on save.
- Voiding a review does not reverse its limit or hold change.

## Conventions 4/5

The install and upgrade work follows the project's conventions:
- The update file uses idempotent helpers.
- New tables get table files with sentinel dates.
- Both seed paths are covered, with menus for every role.
- Config goes in SystemParameters, and the GL accounts in CompanyPreferences with the delete guard.
- PDFs use Dompdf, and email goes through SendEmailFromWebERP with `=== true`.
- Strings use `__()`, and posting queries pass `$Transaction=true`.

Against: a hard-coded token number, hand-written forms instead of UIGeneralFunctions, a temp file outside reports_dir, the edit to the stale `sql/demo.sql`, and odd whitespace in the `Customers.php`/`Z_ImportDebtors.php` UPDATE lists.

## Regressions (existing behaviour changed or broken)

1. `Customers.php` edit UPDATE no longer writes creditlimit or holdreason for anyone, including credit control. This is intended by the design (changes go through a review), but it changes the existing screen.
2. The `Z_ImportDebtors.php` update path no longer updates creditlimit or holdreason of existing customers.
3. API `ModifyCustomer` now returns error 1902 whenever creditlimit, holdreason or nextreviewdate is sent by a user without token 21. Existing XML-RPC clients that send full customer records break, against the API backward-compatibility rule.
4. `DeliveryDetails.php:338-346` blocks saving quotations for held customers too. Before, only orders were blocked, and only at order entry.
5. `Customers.php` delete now cancels when users or contracts refer to the customer. Before, it warned and deleted.
6. `PrintCustTrans.php` credit-note branch reused for charges via `InvOrCredit=Charge`: credit-note printing is unchanged (the ternaries default to the old values).
