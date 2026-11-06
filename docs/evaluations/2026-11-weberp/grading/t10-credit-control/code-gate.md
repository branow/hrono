# t10 credit control: grading of the code-gate run

- Run diff: `/Users/orest/hrono-weberp/runs/t10-credit-control-code-gate.diff` (3549 lines, 50 files)
- Workspace: `/Users/orest/hrono-weberp/runs/t10-credit-control-code-gate/`
- Base: `scratchpad/base/` (4cb937f79e8b)
- Checklist: `tasks/t10-credit-control/checklist.md`. Rule details: `grading/t10-credit-control/rules/`.
- All claims were checked in the code, not in the run's NOTES.md. File:line refers to the workspace unless it says `diff:`.

Scoring: met 1 / partly 0.5 / missed 0.

## A. The request (15)

| id | score | justification |
|---|---|---|
| A1 | 1 | `install/sql/tables/creditreviews.sql` and `sql/updates/44.php:19-38` add debtorno with an FK (ON DELETE/UPDATE CASCADE), reviewdate, reviewedby, outcome, old/new limit, nextreviewdate and `comments text`. |
| A2 | 1 | `CreditReviews.php:144-182`: DB_Txn_Begin, `SELECT … FOR UPDATE`, INSERT review, UPDATE debtorsmaster creditlimit/holdreason/nextreviewdate, all with `$Transaction=true`, then commit. |
| A3 | 1 | `debtorsmaster.nextreviewdate` (`install/sql/tables/debtorsmaster.sql:33`, 44.php:15). It is set by the review (`CreditReviews.php:175-180`), on create (`Customers.php:298-303` diff:1759), by the importer, by the API default and by Z_ChangeCustomerCode. |
| A4 | 0.5 | The history is newest first (`CreditReviews.php:277`, `CreditHistory.php:74`) and is linked from the customer page (`SelectCustomer.php` diff:197-199). "Correct" is only a "mark as entered by mistake" flag (`CreditReviews.php:72-89`). The entry cannot be edited, and the account change is not reversed. |
| A5 | 1 | `CreditReviewReport.php` takes a days filter, NULL or overdue or due-within, and shows balance, overdue (`CreditPastDueSQL(1)`), limit, `GetCreditAvailable`, lastpaiddate and a Dompdf PDF. |
| A6 | 1 | Watch is `dissallowinvoices=2`. `CreditStatus.php` can now set it (diff:1468-1474). It gives a warning in ConfirmDispatch (diff:419-421) and in SelectOrderItems (diff:2502-2516), and is a review outcome. |
| A7 | 1 | The pages and the Customers.php fields are gated on token 21 (`CreditControlFunctions.php:26-30`), which only role 8 gets. Other users see the limit and hold fields disabled, and the server ignores them (`Customers.php` diff:1707-1723). |
| A8 | 1 | Levels 1/2/3 are past due, PastDueDays1 and PastDueDays2 (`CreditControlFunctions.php:99-126`, `CreditReminders.php` candidate SQL). |
| A9 | 1 | `CreditReminders.php` shows a preview list with ticks and a Send button. A unique `(debtortransid, level)` in `creditreminderitems` plus the `maxlevel` filter stop repeats. |
| A10 | 1 | `CreditEmailPDF` returns `=== true`. On failure or no contact it rolls back and lists the customer under "Reminders NOT sent" (`CreditReminders.php` diff:803-853). |
| A11 | 1 | The "Reminders Sent" table in `CreditHistory.php:103-136` shows the date, level and each invoice. It is linked from the customer page. |
| A12 | 1 | `LateCharges.php` makes the interest and fee charges only when the user ticks and presses the button, in the customer's currency rate (`rate_fx`). |
| A13 | 1 | Type 13 is written to debtortrans, and `CreditPostGL` posts debtorsact +, latechargeact − (`LateCharges.php:239-248`). |
| A14 | 1 | `BadDebtWriteOff.php` writes off the ticked items (or all of them through the header checkbox), requires a reason, and posts to baddebtact, which is checked to be P&L and not a control account. |
| A15 | 1 | `doc/Manual/ManualCreditControl.html` covers the whole process, with an outline entry and a ManualCreditStatus update. |

**A = 14.5 / 15**

## B. Rules away from the change (40)

| id | score | justification |
|---|---|---|
| B1 | 1 | Hold uses `holdreason → holdreasons.dissallowinvoices` (1 = block, 2 = watch). There is no new flag (`GetCustomerHoldStatus`, `CreditControlFunctions.php:36-48`). |
| B2 | 1 | `ConfirmDispatch_Invoice.php:156-166` checks when the order loads and `:622-626` checks again at ProcessInvoice. |
| B3 | 1 | `RecurringSalesOrdersProcess.php:98-102` skips a held customer without moving lastrecurrence on. |
| B4 | 1 | `EDIProcessOrders.php:896-903` does not create the order and adds an email/prnMsg line. |
| B5 | 1 | `api_salesorders.php:344` (InsertSalesOrderHeader, quotations allowed) and `:850` (InvoiceSalesOrder) return the new error 1174. |
| B6 | 1 | CheckCreditLimits is not touched. The report uses `GetCreditAvailable` (`CreditReviewReport.php` diff:986). There is no parallel formula. |
| B7 | 1 | All four debtorno tables are re-pointed (`Z_ChangeCustomerCode.php:199-203`). The new column is carried by a follow-up self-join UPDATE (`:191-197`) rather than in the INSERT column list. The effect is the same on MySQL (the UPDATE syntax is MySQL-only). |
| B8 | 1 | `Customers.php:387-389` deletes the four credit tables before debtorsmaster. The FKs also cascade. |
| B9 | 0.5 | `Z_ImportDebtors.php:407,430` puts the column into the INSERT with a default date, but `$FieldHeadings` is not extended, so the value cannot be imported. |
| B10 | 1 | `api_customers.php:115-120,366-379,508-525` validates nextreviewdate as Y-m-d. ModifyCustomer rejects holdreason/creditlimit changes. InsertCustomer rejects a hold or watch status (error 1176). |
| B11 | 1 | systypes 13 "Late Payment Charge" and 14 "Bad Debt Write-off" are added in 44.php (NewSysType) and in `install/sql/data/systypes.sql` and `install/sql/demo.sql`. Both numbers are unused in the base. |
| B12 | 1 | `BadDebtWriteOff.php:111→157` and `LateCharges.php:184→199` call GetNextTransNo after DB_Txn_Begin. |
| B13 | 0.5 | GetPeriod is used (`BadDebtWriteOff.php:158`, `LateCharges.php:171`), but nothing checks or shows ProhibitPostingsBefore. A last-month charge in a closed period is silently moved to a later period while trandate keeps the month-end date. |
| B14 | 1 | GL rows are written only `if gllink_debtors == 1` (`BadDebtWriteOff.php:218`, `LateCharges.php:244`). The AR side is `companies.debtorsact`, the same value as CompanyRecord. |
| B15 | 0 | There is no `EnsureGLEntriesBalance` call in BadDebtWriteOff.php or LateCharges.php (grep: none). |
| B16 | 1 | The charge ovamount is positive and its GL amount is amount / rate_fx. The write-off ovamount is −Total with GL −Total/rate (`BadDebtWriteOff.php:192,220-222`, `LateCharges.php:245`). |
| B17 | 1 | `CreditPostGL` calls `InsertGLTags($Tags)` straight after its own gltrans INSERT (`CreditControlFunctions.php:266-285`). Tags go on the income/expense line. |
| B18 | 1 | `BadDebtWriteOff.php:35-51` refuses a non-P&L account or one in the control list. CompanyPreferences rejects control accounts on save (diff:327-344). |
| B19 | 1 | The write-off allocates itself through custallocns and updates alloc, diffonexch and settled (`BadDebtWriteOff.php:204-212`). Type 13 charges are unsettled targets, which CustomerAllocations.php:270-273 accepts for any type. |
| B20 | 1 | The diffonexch per item matches CustomerAllocations. MovtInDiffOnExch goes to salesexchangediffact +/debtorsact − (`BadDebtWriteOff.php:225-229`). |
| B21 | 1 | `CustomerAccount.php:339-371` adds a 13/14 branch. `CustomerInquiry.php:414-440` adds type 13 with PDF/email. Type 14 falls into the existing misc branch (`:647`). |
| B22 | 1 | `salesperson` is copied from the source invoice into both new debtortrans INSERTs (`BadDebtWriteOff.php:206`, `LateCharges.php:238`). |
| B23 | 1 | The `creditcharges` UNIQUE `(debtorno, chargemonth, kind, reminderid)` key and a pre-check give "already charged" (`LateCharges.php:151-157,186-195`). |
| B24 | 1 | The CompanyPreferences form/select/update, the GLAccounts delete guard (diff:1913-1925, which also fixes the missing freightact), and the positional INSERTs in `InstallFunctions.php` and `install/sql/demo.sql` (diff:3204-3218, 3291) are all done. The pages read `companies` directly, not CompanyRecord, so the GetConfig guard is not needed. |
| B25 | 1 | `CreditPastDueSQL` is a copy of the AgedDebtors due/overdue1/overdue2 CASEs (`AgedDebtors.php:37-66` vs `CreditControlFunctions.php:99-126`). |
| B26 | 1 | All open-item queries use `ROUND(debtortrans.balance, decimalplaces) > 0`. Nothing uses `settled`. |
| B27 | 1 | `CreditStatementContacts` uses `custcontacts.statement = 1` plus IsEmailAddress, keyed by address so duplicates drop out (`CreditControlFunctions.php:180-195`). |
| B28 | 1 | `CreditRenderPDF` uses Dompdf with `SetDomPDFOptions.php` and `setPaper($_SESSION['PageSize'])` (`CreditControlFunctions.php:233-246`). |
| B29 | 0.5 | It checks `=== true` and unlinks the file, but the temp file goes to `sys_get_temp_dir()`, not `$_SESSION['reports_dir']` (`CreditControlFunctions.php:250`). |
| B30 | 1 | The SalesmanLogin filters (custbranch.salesman plus debtortrans.salesperson) are in the review, history, report, reminder, charge, write-off and print-charge queries. |
| B31 | 1 | `CustomerCreditNotices.php` takes the debtorno from `www_users.customerid` (`CreditControlFunctions.php:85-91`) and filters both queries on it. |
| B32 | 0 | Hold/release permission is a hard-coded token number: `define('CREDIT_CONTROLLER_TOKEN', 21)` with `in_array(21, AllowedPageSecurityTokens)` (`CreditControlFunctions.php:15,26-30`). There is no false-script row. |
| B33 | 1 | All 8 pages are in NewScript (44.php), `install/sql/data/scripts.sql` and `install/sql/demo.sql`. No page sets `$PageSecurity`. |
| B34 | 1 | `sql/updates/44.php` uses only idempotent helpers (AddColumn, CreateTable with the exact names and no ENGINE, NewSysType, NewSecurityToken, InsertRecord, NewScript, NewMenuItem, NewConfigValue). The guarded `UpdateDBNo` is on one line (diff:3548-3550). |
| B35 | 1 | There are 5 `install/sql/tables/credit*.sql` files plus the debtorsmaster/companies columns. Dates default to `'1000-01-01'` or NULL, with no zero dates. |
| B36 | 1 | config, scripts, menuitems, systypes, securitytokens and securitygroups seeds are in both `install/sql/data/*.sql` and `install/sql/demo.sql`. Each data file is still one statement. `sql/demo.sql` is not touched. |
| B37 | 0.5 | Config uses NewConfigValue, both seeds and SystemParameters. The seed menu rows cover roles 1-8 only, while base items such as AgedDebtors cover roles 1-9 (grep of `install/sql/data/menuitems.sql`). |
| B38 | 1 | Every helper used exists in all four `UpgradeDB_*` variants. CharacterSet is guarded, the extra CreateTable argument does no harm on postgres, and AddCalculatedColumn is not used. |
| B39 | 0.5 | No POST value is escaped twice. All the new forms are hand-written `<input>/<select>` (no UIGeneralFunctions). Only the two CompanyPreferences fields use `FieldToSelectOneGLAccount`. |
| B40 | 1 | Every new page sets `$Title/$ViewTopic='CreditControl'/$BookMark` before header.php. The manual has `id="CreditControl"` and every BookMark anchor, and ManualOutline has a `CreditControl` entry. |

**B = 35.5 / 40**

## Totals

- A 14.5 / 15
- B 35.5 / 40
- All 50 / 55
- Correctness 4 / 5
- Conventions 3 / 5

Correctness, why not 5: there is no `EnsureGLEntriesBalance`, and nothing checks ProhibitPostingsBefore. The reminder transaction stays open (row locks held) while SMTP sends. The demo data's −1 hold reasons break some new paths (see the regressions below). The customer-login page cannot be reached from the customer menu. The remaining logic was checked and found right: ledger signs, exchange difference, idempotence, and review atomicity.

Conventions, why 3: the token number is hard-coded, the forms are hand-rolled, the temp file is outside reports_dir, and the menu seeds miss role 9. `REPLACE INTO config` in SystemParameters.php is MySQL-only, and so is the multi-table UPDATE in Z_ChangeCustomerCode. Positives: Dompdf, `__()`, guarded UpdateDBNo, `$Transaction=true` on the posting queries, and both seed paths kept in step.

## Regressions (existing behaviour broken)

1. **A non-controller can no longer create a customer on demo data.** `Customers.php:52-58` disables the Credit Status select. It then looks for a hold reason with `dissallowinvoices=0`. The `install/sql/demo.sql:521-530` hold reasons have no such column value, so all of them default to −1. `$_POST['HoldReason']` stays unset, and the INSERT writes `''` into the `holdreason` smallint FK, so the insert fails. On a non-demo install no hold reasons are seeded at all.
2. **API InsertCustomer rejects demo hold reasons.** `CreditHoldReasonRestricted` treats −1 as restricted (`CreditControlFunctions.php:51-56`). Any InsertCustomer that passes `holdreason` on demo data now returns error 1176.
3. **API ModifyCustomer rejects any creditlimit/holdreason change.** Existing integrations that update limits through XML-RPC now fail with error 1176 (`api_customers.php:516-524`). This is deliberate under BRD 7.2, but it changes the API contract.
4. **The customer-login order path now lets −1 and watch statuses through.** `SelectOrderItems.php` diff:2511 changes `== 0` to `!= 1`. Before, a customer login was blocked for any status other than 0. This matches the staff path, but it is a behaviour change.
5. **Held customers' existing orders can no longer be re-saved** in `DeliveryDetails.php:327-333`. The check runs on modifications as well as new orders. This is arguably intended.
6. Minor: `CreditStatus.php` turns a −1 reason into 0 when it is edited. The old checkbox did the same, so this is not new.

## Other findings (not regressions)

- `CustomerCreditNotices.php` has only a role-7 `menuitems` row. The customer-login menu is hard-coded in `index.php:73-95`, so the page is reachable only by typing the URL.
- The type-13 PDF/email links in CustomerInquiry go to `PrintCustCharge.php` (token 2), which a customer login cannot open.
- The reminder level recorded for every invoice in a letter is the customer's highest level. A newly overdue invoice in a final notice is recorded at level 3 and never gets levels 1 and 2.
- NOTES.md says nothing was run. Nothing was linted or executed.
