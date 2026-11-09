# t12 credit control: run A graded against the checklist

The grading checked the code, not NOTES.md. NOTES.md was used only to confirm decisions on the BRD's open questions. Paths are relative to the workspace `blindop/A/`. Line numbers are approximate positions in the post-run files.

## A. BRD requirements (BR-01..BR-43)

| # | Score | Evidence |
|---|---|---|
| A1 BR-01 | 1 | `CreditControl.php:100-129` inserts a `custcreditreviews` row with date, user, outcome (confirmed/raised/reduced/watch/stop/normal), old and new limit, notes and next review date. |
| A2 BR-02 | 1 | New customers get a next review date in `Customers.php:~284` (`DefaultNextReviewDate`), `api/includes/api_customers.php:~360` and `Z_ImportDebtors.php:~428`. `DefaultNextReviewDate` at `includes/CreditControlFunctions.php:285` uses a standard period of 12 months and a high-risk period of 6, both set in Finance's settings. |
| A3 BR-03 | 1 | Reviews are listed at `CreditControl.php:403-429`. There is no edit or delete path for `custcreditreviews`. |
| A4 BR-04 | 1 | The limit and status change inside the review transaction: `CreditControl.php:123-124` → `ChangeCustomerCreditLimit`/`ChangeCustomerCreditStatus` with the review notes as the reason. |
| A5 BR-05 | 1 | `CreditControl.php:135-147` requires a reason. `ChangeCustomerCreditStatus` at `CreditControlFunctions.php:242-261` logs the user, NOW() and the reason to `custcreditevents`. |
| A6 BR-06 | 1 | Stop is enforced on every route: sales office and web shop in `DeliveryDetails.php:~328-339` and `SelectOrderItems.php:~515`; EDI in `EDIProcessOrders.php:~896`; recurring orders in `RecurringSalesOrdersProcess.php:~96`; API in `api_salesorders.php:~280`. Existing orders cannot be dispatched or invoiced unless released: `ConfirmDispatch_Invoice.php:~112,~641`, `GeneratePickingList.php:~178`, `PDFPickingList.php:~130` and `api_salesorders.php:~814` call `OrderCreditBlockReason`, and release is in `CreditOrderHolds.php:20`. |
| A7 BR-07 | 1 | Token 21 is required: `CanManageCredit` at `CreditControlFunctions.php:41`. The gate is applied in `CreditControl.php:62`, `Customers.php:~137-156` (limit and status read-only otherwise, `:~971,~1019`) and API `ModifyCustomer` (`api_customers.php:~492-511`). `CreditStatus.php` is moved to token 21 (`sql/updates/44.php:210`). |
| A8 BR-08 | 1 | Order entry warns about watch customers (`SelectOrderItems.php:~443`, `ShowCreditStatusWarnings` `CreditControlFunctions.php:229-232`). Their orders are noted (`EvaluateOrderCredit` `:389-401`) and listed for credit control in `CreditOrderHolds.php:126-165`. |
| A9 BR-09 | 1 | The status banner appears in `SelectCustomer.php:~151`, `CustomerInquiry.php:~175`, `CustomerAccount.php:~250`, `SelectOrderItems.php:~186`, `ConfirmDispatch_Invoice.php:~124`, `CreditControl.php:219` and the `AgedDebtors.php:~327` column. |
| A10 BR-10 | 1 | `EvaluateOrderCredit` (`CreditControlFunctions.php:322-404`) holds orders over the limit. It is called from DeliveryDetails (new and modified orders), EDI, recurring orders and the API order lines. |
| A11 BR-11 | 1 | Web-shop customer login: "account on hold, contact us" in `SelectOrderItems.php:~515-521` and `DeliveryDetails.php:~334`. API clients get error 1174 (`api_errorcodes.php:~189`). |
| A12 BR-12 | 1 | `DunningStages.php` maintains the number of stages, days overdue and wording. Three stages (30/45/60, the last a final notice) are seeded in `44.php:257-259` and `install/sql/data/dunningstages.sql`. |
| A13 BR-13 | 1 | Recipients are statement contacts (`GetCustomerAccountsEmails` `CreditControlFunctions.php:530-541`). Customers with no email are listed in the preview ("No email - post", `DunningRun.php:255`) and after the run with print links (`DunningRun.php:174-185`). |
| A14 BR-14 | 1 | Credit control starts the run in `DunningRun.php:224-265`, previews it and can untick customers per checkbox (`:248`). Only ticked customers are sent (`:111`). |
| A15 BR-15 | 1 | `DunningProposal` (`DunningRun.php:42-78`) takes the next stage from the stages already sent for items that are still overdue. It moves one stage at a time, sends nothing when net overdue is 0, and observes `DunningMinDaysBetween` (`:61-66`). |
| A16 BR-16 | 1 | `dunningletters` stores date, stage, amount and currency, and `dunninglettertrans` stores the items (`DunningRun.php:126-148`). A history event is written at `:145`. |
| A17 BR-17 | 1 | `BuildDunningLetter` (`CreditControlFunctions.php:726-745`) shows the customer currency, `{InvoiceList}` of the overdue items and the amount in customer decimals. |
| A18 BR-18 | 1 | Disputes are recorded in `CreditControl.php:169-207`. `GetOverdueItems` excludes open disputes (`CreditControlFunctions.php:498-500`), and both reminders and charges use it. |
| A19 BR-19 | 1 | `CreditCharges.php`: interest, fee or both are charged at month end (`:148-198`). Rate, fee and days overdue are set in `CreditControlSettings.php:~150-163`. |
| A20 BR-20 | 1 | `debtorsmaster.interestexempt`/`feeexempt` are set with a reason in `CreditControl.php:149-167` and honoured in `CreditCharges.php:69-90`. |
| A21 BR-21 | 1 | Charges are raised in the customer currency as separate types 13 and 14 with a narrative (`CreditCharges.php:159-170`). They are shown in `CustomerAccount.php:~402-423` (new else-branch) and in `PrintCustStatements.php` (prints every type by typename). |
| A22 BR-22 | 1 | The preview list has per-charge checkboxes and a confirmation (`CreditCharges.php:221-254`). A month is not charged twice: there is a guard at `:78-84` and a UNIQUE key (debtorno, periodno, chargetype) at `install/sql/tables/creditcharges.sql`. |
| A23 BR-23 | 1 | Interest and fees are credited to `CreditInterestAct`/`CreditFeeAct`, chosen in settings (`CreditControl.php`/`CreditCharges.php:32-33`), via `PostCreditControlTransaction` `CreditControlFunctions.php:588-599`. |
| A24 BR-24 | 1 | A waiver needs a reason. It posts type 45 at the charge's own rate, is allocated to the charge and reverses the income account (`CreditCharges.php:101-135`). |
| A25 BR-25 | 1 | `CreditWriteOff.php:58-116` writes off all or part of each item and requires a reason. |
| A26 BR-26 | 1 | Write-offs above `CreditWriteOffApprovalLimit` (home currency) stay pending (`CreditWriteOff.php:98-114`). They are approved by the token-22 holder in `CreditWriteOffApprove.php:19-56`, and the requester cannot approve their own (`:25`). |
| A27 BR-27 | 1 | `PostBadDebtWriteOff` (`CreditControlFunctions.php:668-723`) posts a type 46 credit to the bad debt account. Allocation posts the exchange difference to `salesexchangediffact` (`:642-652`). |
| A28 BR-28 | 1 | The "put on stop" checkbox is ticked by default (`CreditWriteOff.php:181`). Stop is applied on posting (`CreditControlFunctions.php:719-721`). |
| A29 BR-29 | 1 | `CreditWriteOffReport.php:49-114` shows period, customer, amount, reason, requested by and approved by. |
| A30 BR-30 | 1 | `CreditControlReport.php` covers reviews due (`:118`), over limit with the amount over (`:121-123`) and watch/stop (`:124`). It filters by rep and currency (`:96-101`) and gives home-currency totals (`:146,176-177`). |
| A31 BR-31 | 1 | `AgedDebtors.php:~312-345` adds Credit Status, Credit Limit and Last Reminder columns. |
| A32 BR-32 | 1 | `custcreditevents` records reviews, status, limit, reminders, charges, waivers, write-offs and holds. It is shown per customer in `CreditControl.php:461-485`. |
| A33 BR-33 | 1 | `UserMaySeeCustomerCredit` (`CreditControlFunctions.php:138-151`) is used in `CreditControl.php:53`, `DunningLetter.php:54` and `ShowCreditStatusWarnings`. `CreditControlReport.php:18` forces the rep's own salesman. |
| A34 BR-34 | 1 | Without token 21, actions are blocked (`CreditControl.php:62-67`) and the forms are hidden (`:250`). Customers.php shows limit and status read-only. |
| A35 BR-35 | 0.5 | Reminders and charges sections were added to `CustomerAccount.php:~447-516`, but the portal's "Account Status" link goes to `CustomerInquiry.php` (`index.php:81`), which shows charges only as plain rows and has no reminders section. CustomerAccount is reachable only by typing the URL. |
| A36 BR-36 | 1 | A customer login is forced to its own `www_users.customerid` in `CustomerAccount.php:~15-21` and `CustomerInquiry.php:~15-21`. `DunningLetter.php:46-52` refuses other customers' letters. |
| A37 BR-37 | 1 | Every posting hits `debtorsact` at amount/rate (`CreditControlFunctions.php:588-599`), and allocation exchange differences hit `debtorsact` and `salesexchangediffact`. `Z_CheckDebtorsControl.php:~125` now includes the other types. |
| A38 BR-38 | 1 | `DebtorsControlReconciliation.php:69-210` shows totals, movement by type, mismatching transactions and GL entries with no customer transaction. |
| A39 BR-39 | 1 | Upgrade path `sql/updates/44.php`. Fresh install: `install/sql/tables/*`, `install/sql/data/*`, `install/sql/demo.sql`. |
| A40 BR-40 | 1 | Existing customers keep their hold reason. Finance bulk-sets next review dates in `CreditControlSettings.php:77-85`. The spreadsheet stop list, limits and dates load through `CreditStatusImport.php:28-103`. NOTES records the decision to keep existing status. |
| A41 BR-41 | 1 | Interest and fee default to 0 and the GL accounts are empty (`44.php:247-252`). Nothing changes for customers who are not overdue, apart from the over-limit hold that BR-10 requires. |
| A42 BR-42 | 1 | `doc/Manual/ManualCreditControl.html` covers reviews, stop and watch, the reminder run, month-end charges, write-offs and the report, and is in `ManualOutline.php:~152`. |
| A43 BR-43 | 1 | `ManualCreditControl.html:24-37` has a "For sales staff - watch and stop" section with who to contact. |

**A = 42.5 / 43**

## B. Rules away from the change

| # | Score | Evidence |
|---|---|---|
| B1 | 1 | Status is held only in `holdreason`→`dissallowinvoices` (1 stop, 2 watch) (`CreditControlFunctions.php:50-57`). There is no parallel flag. `CreditStatus.php:~62-66` can now store 2. |
| B2 | 1 | `ConfirmDispatch_Invoice.php:~112` (on load) and `:~641` (at ProcessInvoice). |
| B3 | 1 | `RecurringSalesOrdersProcess.php:~96` skips stopped customers. A held order is not auto-invoiced (`:~223`). |
| B4 | 1 | `EDIProcessOrders.php:~896-903` refuses orders from stopped customers, and `:~1020` evaluates created orders. |
| B5 | 1 | `api_salesorders.php:~280` (InsertSalesOrderHeader), `:~532,~598` (lines) and `:~814` (InvoiceSalesOrder). |
| B6 | 0 | The new setting `CreditHoldOverLimit` (`CreditControlFunctions.php:343`) ignores `CheckCreditLimits`. Exposure is recomputed with a parallel formula in `GetCustomerCreditPosition` (`:97-115`) and inline in `CreditControlReport.php:77-83`, instead of `GetCreditAvailable`. |
| B7 | 1 | `Z_ChangeCustomerCode.php:~75-113` adds the 3 new columns to the column list, and `:~262-267` moves all 7 new debtorno tables. |
| B8 | 1 | `Customers.php:~368-378` blocks the delete when credit history exists and deletes the 'opened' events. Every other new table also writes an event, so the block covers them. |
| B9 | 0.5 | `Z_ImportDebtors.php:~405,~428` sets `nextreviewdate` on insert, but nothing is added to `$FieldHeadings`, so the column is not carried by the import. |
| B10 | 0.5 | `api_customers.php:~492-511` gates `creditlimit`/`holdreason` behind token 21 and logs the change. The new columns `nextreviewdate`/`interestexempt`/`feeexempt` remain writable through ModifyCustomer without validation. |
| B11 | 1 | New types 13, 14, 45, 46 and 47 are added via `NewSysType` (`44.php:179-183`), `install/sql/data/systypes.sql` and `demo.sql`. None collide with base types. |
| B12 | 1 | `GetNextTransNo` is called inside `PostCreditControlTransaction` (`CreditControlFunctions.php:548`), and every caller has already called `DB_Txn_Begin`. |
| B13 | 0.5 | `GetPeriod` is used (`:549`), but there is no check of the date against `ProhibitPostingsBefore` and the shifted date is not shown. |
| B14 | 1 | GL rows are written only when `gllink_debtors==1`, with the AR side to `CompanyRecord['debtorsact']` (`:588-599`). |
| B15 | 0.5 | A home-made `CreditControlGLBalances` (`:658-663`) is checked before commit and rolls back on imbalance, but `EnsureGLEntriesBalance` is not used. |
| B16 | 1 | GL amount is amount/rate. Charges post with a positive ovamount, and waivers and write-offs negative (`CreditCharges.php:170`, `CreditControlFunctions.php:701`). |
| B17 | 0 | `InsertGLTags` is never called after the `gltrans` inserts (`CreditControlFunctions.php:591-598,644-651`). |
| B18 | 1 | The GL account picker lists only P&L accounts with `glaccountusers.canupd=1` (`CreditControlSettings.php:97-106`), so control accounts cannot be chosen. |
| B19 | 1 | Credits (45, 46) are fully allocated at posting by `AllocateCreditControlTransaction` (`CreditControlFunctions.php:606-655`). Debits (13, 14, 47) are normal allocate-to rows in `CustomerAllocations.php`. |
| B20 | 1 | The exchange difference on a write-off or waiver allocation goes to `salesexchangediffact` and `debtorsact` (`CreditControlFunctions.php:641-652`). |
| B21 | 1 | `CustomerAccount.php:~402-423` adds an else-branch for the other types. `CustomerInquiry.php:607-640` already renders misc types. |
| B22 | 1 | `debtortrans.salesperson` is set from the branch salesman (`CreditControlFunctions.php:551-557,584`). |
| B23 | 1 | Guarded by the existing-charge check (`CreditCharges.php:78-84`) and a UNIQUE key on `creditcharges` (debtorno, periodno, chargetype). |
| B24 | 0 | The GL accounts are config rows, not `companies` columns. There is no CompanyPreferences change, no GLAccounts delete guard and no positional INSERT update. |
| B25 | 0.5 | `DueDateSQL` (`CreditControlFunctions.php:467-471`) matches AgedDebtors (daysbeforedue, or last_day + dayinfollowingmonth). Dunning and charge thresholds use their own stage days and `CreditChargeDaysOverdue`, not `PastDueDays1/2`. |
| B26 | 0.5 | Open items are taken by `balance>0`, but always combined with `settled=0` (`CreditControlFunctions.php:495-496`, `CreditCharges.php:64`, `CreditWriteOff.php:63,160`, `DunningRun.php:91`). |
| B27 | 1 | Recipients are `custcontacts.statement=1` filtered by `IsEmailAddress` (`CreditControlFunctions.php:530-541`). |
| B28 | 1 | No PDFs are produced. Letters are plain-text email plus a printable HTML view (`DunningLetter.php`). Cpdf/PDFStarter are not used. |
| B29 | 1 | Success is tested with `SendEmailFromWebERP(...) === true` and failures are listed (`DunningRun.php:151-157`). There is no attachment, so no temp file is created. |
| B30 | 0.5 | The SalesmanLogin filter is applied in `CreditControlReport.php:18`, `CreditControl.php:53` and `DunningLetter.php:54`. It is missing from `DunningRun.php` (`:81-101`, free salesman select), `CreditOrderHolds.php`, `CreditWriteOffReport.php` and `CreditCharges.php`. |
| B31 | 1 | A customer login is forced to its own debtorno in CustomerAccount, CustomerInquiry and DunningLetter (see A36). |
| B32 | 0 | Token numbers are hard-coded: `in_array(21, …)`/`in_array(22, …)` (`CreditControlFunctions.php:41-48`). There is no "false script" row. |
| B33 | 1 | All 13 new pages are in `NewScript` (`44.php:196-208`), `install/sql/data/scripts.sql` and the `demo.sql` scripts INSERT. No page sets `$PageSecurity`. |
| B34 | 1 | `44.php` uses CreateTable (exact names), AddColumn, NewSysType, NewSecurityToken, InsertRecord, NewConfigValue and NewMenuItem. `UpdateDBNo` is guarded and on one line (`:274-276`), indented as in 43.php. |
| B35 | 1 | There are 10 `install/sql/tables/*.sql` files plus the debtorsmaster columns, all using `'1000-01-01'` defaults and ENGINE/CHARSET. |
| B36 | 1 | Seeds are in both `install/sql/data/*` (each still a single statement, e.g. menuitems.sql ends with one `;`) and `install/sql/demo.sql:21254-21262`. |
| B37 | 0.5 | Menu rows exist for roles 1-9 (`install/sql/data/menuitems.sql:3-11`), with NewMenuItem and NewConfigValue in 44.php plus config seeds. The settings are in a separate `CreditControlSettings.php`, not in `SystemParameters.php`. |
| B38 | 1 | Only helpers present in all four `UpgradeDB_*` variants are used (UpdateField, InsertRecord etc. checked). There is no AddCalculatedColumn. |
| B39 | 0 | Forms are hand-rolled (no UIGeneralFunctions). `$_POST` reasons and notes are escaped again by `DB_escape_string` in `LogCreditEvent` (`CreditControlFunctions.php:179`) and `ReleaseOrderCreditHold` (`:450,457`). |
| B40 | 0.5 | `$Title`/`$ViewTopic`/`$BookMark` are set before header.php everywhere. The manual has `id="CreditControl"` and most bookmarks and is in ManualOutline, but the bookmarks `ReminderStages` (`DunningStages.php:7`) and `WriteOffReport` (`CreditWriteOffReport.php:7`) have no anchor in `ManualCreditControl.html`. |

**B = 30 / 40**

## Totals

- **A: 42.5 / 43**
- **B: 30 / 40**
- **Total: 72.5 / 83**
- **Correctness: 4 / 5.** The implementation is thorough and coherent across all order routes, the ledger postings balance, and the allocation reuses the CustomerAllocations maths. Nothing was run. Weak spots:
  - The portal path misses the reminders (A35).
  - No ProhibitPostingsBefore check.
  - Double-escaped notes in the history.
  - The over-limit hold ignores `CheckCreditLimits`.
- **Conventions: 3 / 5.** Follows the patterns for scripts, menus, install and upgrade parity, holdreasons, salesperson and exchange differences. Departures:
  - Hard-coded tokens 21 and 22.
  - No UIGeneralFunctions.
  - Double escaping.
  - No `EnsureGLEntriesBalance` or `InsertGLTags`.
  - GL accounts held in config instead of `companies`/CompanyPreferences.
  - Settings page outside SystemParameters.

## Regressions / risks

- `CreditStatus.php` moves to token 21 (`44.php:210`, demo/scripts seeds). Roles that maintained credit status codes before lose access unless they hold token 15.
- `CreditHoldOverLimit` defaults to 1, so after the upgrade every new order of a customer already over the limit is held and cannot be picked or dispatched until released. This happens regardless of the existing `CheckCreditLimits=0/1` setting.
- After the upgrade, open orders of customers already on a `dissallowinvoices=1` code are blocked at picking, dispatch and invoice until credit control releases them.
- "ACCOUNT ON HOLD" now shows only for `=1`, where it was `!=0` (`CustomerAccount.php`, `CustomerInquiry.php`). Watch and `-1` customers no longer show it. This is intended, but it changes the display.
- `CustomerAccount.php` now lists types it used to drop silently (e.g. debtor journals, type 15). This changes the on-screen statement for existing customers. It is correct, but visible.
- `SelectOrderItems.php:~553`: the customer-login check changed from `==0` to `!=1`. Demo hold reasons with `-1` are now allowed in the web shop.
- Notes and reasons written to `custcreditevents`/`creditorderholds` are double-escaped, so quotes display with backslashes.
- `api_salesorders.php:~344` adds an early return on header validation errors. This is harmless, but it changes the control flow of an existing API function.
