# t12 credit control, try10, run B: checklist grading

Workspace: `scratchpad/blind12h/B/`, diff `blind12h/B.diff`. Paths below are relative to the workspace. Scores: met 1 / partly 0.5 / missed 0. Graded from the code. NOTES.md was used only for the decisions on the open questions in BRD section 9.

## A. BRD requirements (BR-01..BR-43)

| # | score | evidence |
|---|---|---|
| A1 | 1 | Review stores date, user, outcome (5 kinds), old and new limit, notes and next review: `CreditControl.php:123-131` (creditreviews INSERT), outcome list at `:79-83`. |
| A2 | 1 | Every new customer gets a next review date from the `CreditReviewMonths` setting: `includes/CreditControlFunctions.php:180-183`, used in `Customers.php:293-294`, `Z_ImportDebtors.php:429`, `api/includes/api_customers.php:359-363`. Existing customers are set in `sql/updates/44.php:184-186` and in `install/sql/demo.sql` (last line). A shorter period can be set for each customer at review time. |
| A3 | 1 | Insert-only history: `LogCreditEvent` (`includes/CreditControlFunctions.php:129-153`) is shown at `CreditControl.php:342-365`. No page edits or deletes reviews. |
| A4 | 1 | The review INSERT, `SetCreditLimit`, status and next-review UPDATE run in one transaction: `CreditControl.php:121-140`. |
| A5 | 0.5 | `CreditControl.php:145-154` requires a reason, and `SetCreditStatus` logs user and time (`CreditControlFunctions.php:156-166`). A credit controller who changes status or limit in `Customers.php:225-234` is logged with an empty reason, and no reason is asked for. |
| A6 | 0.5 | Stop is blocked in `DeliveryDetails.php:328-355` (staff and web shop), `RecurringSalesOrdersProcess.php:95-100`, `EDIProcessOrders.php:895-904`, `api/includes/api_salesorders.php:279-285` and at dispatch/invoice in `ConfirmDispatch_Invoice.php:606-615`. Not blocked: the API `InvoiceSalesOrder` (`api_salesorders.php` ~:800, unchanged) still invoices for a customer on stop. `CounterSales.php:131-202` still only warns for a held cash-sale account. |
| A7 | 0.5 | Token 21 gates `CreditControl.php:68-73`. `Customers.php:135-155` keeps the stored status and limit for users without the token. The API `ModifyCustomer` can still change `holdreason` and `creditlimit` (`api/includes/api_customers.php`, unchanged). |
| A8 | 1 | Watch customers can order (`SelectOrderItems.php:539`), get the existing warning at order entry and a warning in `SelectCustomer.php:616-618`, and their orders are listed in `CreditOrderRelease.php:31-50`. |
| A9 | 0.5 | Status is shown in `SelectCustomer.php:607-620`, `CreditControl.php:205`, `CustomerAccount.php:230-238` and `AgedDebtors.php:323`. `CustomerInquiry.php:170-172` still prints "ACCOUNT ON HOLD" for a watch customer (`!= 0`), so staff see the wrong status there. |
| A10 | 1 | An over-limit order is saved with `creditheld=1` (`DeliveryDetails.php:341-353,426-434,762-766`; `CreditHoldIfOverLimit` for EDI and standing orders). It is blocked at dispatch until released (`CreditControlFunctions.php:98-115`, `CreditOrderRelease.php:16-29`). |
| A11 | 1 | The customer-login message is at `DeliveryDetails.php:333-335`, and the hold banner with "contact us" at `CustomerAccount.php:236-241`. |
| A12 | 1 | Stage count, days and wording can be edited in `CreditControlSetup.php:50-77`. Three stages are seeded (`install/sql/data/zz_credit_dunningstages.sql`, `44.php:175-180`). |
| A13 | 1 | Letters go to `custcontacts.statement=1` (`CreditControlFunctions.php:346-355`). Customers with no email are flagged and can be recorded as posted: `CreditDunningRun.php:151,117-120`. |
| A14 | 1 | The run is started by hand and shows a preview. "Leave out" checkboxes are at `CreditDunningRun.php:126-161`. |
| A15 | 1 | The stage comes only from items still overdue and not disputed, and is skipped when the net balance is ≤0 (`CreditDunningRun.php:30-56`). `CreditDunningMinDays` stops a repeat of the same stage (`:55-60`). |
| A16 | 1 | `dunninglog` stores date, stage, invoices and amount: `CreditDunningRun.php:76-99`. |
| A17 | 1 | The letter lists the overdue invoices in the customer's currency: `CreditDunningRun.php:65-74`. |
| A18 | 1 | `debtortrans.disputed` is set in `CreditControl.php:167-178`. `CreditOverdueItems` leaves disputed items out of dunning and charges (`CreditControlFunctions.php:195-220`). |
| A19 | 1 | Interest and/or fee with rate, fee and days as settings: `CreditCharges.php:15-18,86-95`, `CreditControlSetup.php:17-22`. Open questions 1-3 are decided in NOTES. |
| A20 | 1 | Per-customer interest and fee exemptions: `CreditControl.php:156-165`, checked in `CreditCharges.php:88-93`. |
| A21 | 1 | Charges are posted in the customer's currency as a separate type 51 with a description (`CreditCharges.php:124`). They show on `CustomerAccount.php:390-410` and on statements (`PrintCustStatements.php:150-157` joins systypes for every type). |
| A22 | 1 | Preview, leave-out and confirm at `CreditCharges.php:113-174`. The same month cannot be charged twice: check at `:94-101` plus the UNIQUE key in `install/sql/tables/creditcharges.sql`. |
| A23 | 1 | Posts to `interestincomeact`/`latefeeact`, which Finance chooses in `CompanyPreferences.php:263-269`. Posting is `CreditCharges.php:121-124`. |
| A24 | 1 | A waiver needs a reason, posts a type 52 credit with GL at the charge's rate and is allocated to the charge: `CreditCharges.php:21-46`. |
| A25 | 1 | Full or partial write-off with a reason: `CreditWriteOff.php:73-113`. |
| A26 | 1 | Above `CreditWriteOffLimit` the write-off waits for a token 22 approver: `CreditWriteOff.php:102-112,116-135`. |
| A27 | 1 | The write-off is allocated to open items, with GL to `baddebtact` at each item's home value, so the currency difference goes to bad debt: `CreditWriteOff.php:21-70`. |
| A28 | 1 | "Put on stop" is ticked by default and can be cleared: `CreditWriteOff.php:62-67,156-158`. |
| A29 | 1 | Report for a period with customer, amount, reason, requester and approver: `CreditWriteOff.php:188-231`. |
| A30 | 1 | `CreditControlReport.php:58-138` lists customers due for review, customers over their limit (and by how much) and customers on watch or stop. It filters by rep and currency and totals in home currency. |
| A31 | 1 | `AgedDebtors.php:286-288,323-325` adds credit status, limit and last reminder stage. |
| A32 | 1 | `creditlog` holds review, status, limit, reminder, charge, waiver, write-off and order hold/release events. Viewable in `CreditControl.php:342-365`. |
| A33 | 1 | Reps are limited to their own customers: `CreditCanSeeCustomer` (`CreditControlFunctions.php:49-56`), `CreditControl.php:41,62-66`, `CreditControlReport.php:16-18`. |
| A34 | 1 | Read-only for anyone without token 21: `CreditControl.php:68-73,220-222`. `Customers.php` fields are disabled (`:961`, `:1012`). |
| A35 | 0.5 | Reminders and charges were added only to `CustomerAccount.php:433-470`. The portal's "Account Status" link goes to `CustomerInquiry.php` (`index.php:81`), which shows neither the reminders nor the charge list. Charges appear there only as unlabelled misc rows. |
| A36 | 1 | A customer login can no longer override `CustomerID` (`CustomerAccount.php:22`, `CustomerInquiry.php:22`). `CreditCanSeeCustomer` checks the login. |
| A37 | 1 | Every posting debits or credits `debtorsact` against its counter account at the transaction's rate, and `EnsureGLEntriesBalance` is called (`CreditControlFunctions.php:258-323`). |
| A38 | 1 | `CreditReconciliation.php:26-107` compares GL with the subledger and lists transactions that do not match and journals with no customer transaction. |
| A39 | 0.5 | Upgrade path is complete (`44.php`). A fresh non-demo install breaks: the positional `INSERT INTO companies` in `includes/InstallFunctions.php:505-532` was not given the three new columns. |
| A40 | 1 | Every customer gets a review date (`44.php:184-186`). The go-live stop list and limits are loaded with `Z_ImportCreditStatus.php:18-50`. Existing statuses are kept. |
| A41 | 1 | Customers who are not overdue and are within their limit have no new invoice, statement or posting behaviour. |
| A42 | 1 | `doc/Manual/ManualCreditControl.html` covers reviews, stop/watch, reminders, charges, write-offs, the report and reconciliation. |
| A43 | 1 | "Notes for sales staff": `doc/Manual/ManualCreditControl.html:61-64`. |

**A total: 40 / 43**

## B. Rules away from the change

| # | score | evidence |
|---|---|---|
| B1 | 1 | Uses `debtorsmaster.holdreason` → `holdreasons.dissallowinvoices` (0/1/2). `CreditStatus.php:67-72,224-230` can now set 2. No parallel customer hold flag (`creditheld` is an order hold). |
| B2 | 1 | `ConfirmDispatch_Invoice.php:606-615` blocks invoicing for a customer on stop or a held order. |
| B3 | 1 | `RecurringSalesOrdersProcess.php:95-100` skips customers on stop. Auto-invoice is gated at `:214-217`. |
| B4 | 1 | `EDIProcessOrders.php:895-904`. |
| B5 | 0.5 | `InsertSalesOrderHeader` refuses a customer on stop (`api/includes/api_salesorders.php:279-285`). `InvoiceSalesOrder` is not checked. |
| B6 | 0.5 | Order holds use `CheckCreditLimits` and `GetCreditAvailable` (`DeliveryDetails.php:341-352`, `CreditControlFunctions.php:119-127`). The report's over-limit list uses its own ledger-only formula (`CreditControlReport.php:67,85`) and leaves out open orders. |
| B7 | 1 | New columns were added to the explicit column list, and the five new tables are moved: `Z_ChangeCustomerCode.php:75-78,110-113,192-197`. |
| B8 | 0 | The `Customers.php` delete guard (`:284-380`) does not know the new tables. Every new customer gets a `creditlog` row (`Customers.php:298`), which has an FK. The delete removes custbranch and custcontacts (`:375-377`), then fails on debtorsmaster (`:379`). |
| B9 | 0.5 | `Z_ImportDebtors.php:406,429` fills `nextcreditreview` with the default. The column is not added to `$FieldHeadings`, and `interestexempt`/`feeexempt` are not handled. |
| B10 | 0 | `InsertCustomer` only fills a default (`api_customers.php:359-363`). `ModifyCustomer` does not validate the new columns, and `holdreason`/`creditlimit` are still open. |
| B11 | 1 | Types 51/52/53 are added with `NewSysType` (`44.php:136-138`), in `install/sql/data/zz_credit_systypes.sql` and in demo.sql. |
| B12 | 1 | `GetNextTransNo` is called in `CreditPostDebtorTrans` (`CreditControlFunctions.php:264`), and every caller is inside `DB_Txn_Begin`. |
| B13 | 0.5 | `GetPeriod` is used (`CreditControlFunctions.php:265`). Nothing checks or shows `ProhibitPostingsBefore`. |
| B14 | 1 | GL rows are written only when `gllink_debtors==1`, and the AR side goes to `debtorsact` (`CreditControlFunctions.php:299-319`). |
| B15 | 0.5 | `EnsureGLEntriesBalance` is called before commit (`CreditControlFunctions.php:321`). The callers do not stop or re-check after an imbalance. |
| B16 | 1 | GL amount = amount/rate. Charges are posted positive and waivers/write-offs negative (`CreditCharges.php:38,124`; `CreditWriteOff.php:54-55`). |
| B17 | 0 | `InsertGLTags` is never called after the gltrans inserts (`CreditControlFunctions.php:302-319`). |
| B18 | 1 | The bad debt and income accounts can only be picked from P&L accounts (`CompanyPreferences.php:263-273`, `FieldToSelectOneGLAccount` with 'P&L'), so control accounts cannot be chosen. |
| B19 | 1 | Waivers and write-offs are allocated when posted through `CreditAllocate` (`CreditControlFunctions.php:329-343`). Type 51 debits can be allocated to by receipts in `CustomerAllocations.php`. |
| B20 | 0.5 | The write-off folds the currency difference into bad debt through an effective rate (`CreditWriteOff.php:41-55`). Nothing goes to `salesexchangediffact`. |
| B21 | 1 | `CustomerAccount.php:390-410` adds a branch for types 51-53. `CustomerInquiry.php` shows other types through its generic row. |
| B22 | 1 | `debtortrans.salesperson` is set from the branch salesman (`CreditControlFunctions.php:294`). |
| B23 | 1 | Own check (`CreditCharges.php:94-101`) plus UNIQUE `(debtorno,chargemonth,chargetype)` in `creditcharges.sql`. |
| B24 | 0.5 | Done: three columns, the GetConfig SHOW COLUMNS guard (`includes/GetConfig.php:88-94`), CompanyPreferences form and update, and demo.sql's positional insert. Missing: the `GLAccounts.php:117-126` delete guard and the positional insert in `includes/InstallFunctions.php:505-532`. |
| B25 | 0.5 | `CreditDueDateSQL` (`CreditControlFunctions.php:186-191`) follows the daysbeforedue / last_day+dayinfollowingmonth rule. The `PastDueDays1/2` bands are not used, because stages have their own thresholds. |
| B26 | 0.5 | Uses `balance > 0.005` but also filters `settled = 0` (`CreditControlFunctions.php:213-214`; `CreditWriteOff.php:27`; `CreditControl.php:168,304`). |
| B27 | 1 | `custcontacts.statement=1` with `IsEmailAddress` (`CreditControlFunctions.php:346-355`). |
| B28 | 1 | No PDFs are made (plain-text letters), and Cpdf/PDFStarter is not used. Not applicable. |
| B29 | 1 | `SendEmailFromWebERP(...) === true` is checked before recording (`CreditDunningRun.php:109-116`). There is no attachment, so no temp file. |
| B30 | 0.5 | Filter applied in `CreditControl.php:41` search, `CreditControlReport.php:16-18,73` and `CreditCanSeeCustomer`. Missing in `CreditDunningRun.php`, `CreditCharges.php` (list and waivers), `CreditWriteOff.php` report and `CreditOrderRelease.php`. |
| B31 | 1 | `CustomerAccount.php:22`, `CustomerInquiry.php:22`, `CreditControlFunctions.php:51-53`. |
| B32 | 0 | Tokens are hard-coded: `define('CREDIT_TOKEN_CONTROL', 21)` / `22` checked with `in_array` (`CreditControlFunctions.php:11-12,30-37`). There is no "false script" scripts row. |
| B33 | 1 | Every new page is in `NewScript` (`44.php:155-163`), `zz_credit_scripts.sql` and demo.sql. No `$PageSecurity` in the pages. |
| B34 | 1 | `sql/updates/44.php` (next number after 43) uses `AddColumn`, `CreateTable` with the exact names and no ENGINE, `NewSysType`, `NewConfigValue`, `NewScript`, `NewMenuItem` and `InsertRecord`. The two raw `executeSQL` statements guard themselves (`:128-133,184-186`). Guarded one-line `UpdateDBNo` at `:188-190`. |
| B35 | 1 | `install/sql/tables/{creditreviews,creditlog,dunningstages,dunninglog,creditcharges,creditwriteoffs}.sql` plus altered tables. Date defaults are `'1000-01-01'`. |
| B36 | 1 | `install/sql/data/zz_credit_*.sql` have one statement each. Seeds are mirrored at the end of `install/sql/demo.sql`. `sql/demo.sql` is untouched. |
| B37 | 0.5 | Menus use `NewMenuItem` (`44.php:165-172`), and the data seed cross-joins `securityroles` to cover every role. Config uses `NewConfigValue` plus seeds. The settings are in a separate `CreditControlSetup.php`, not `SystemParameters.php`. |
| B38 | 1 | Every helper used exists in all four `UpgradeDB_*` variants (`executeSQL` is in `Z_UpgradeDatabase.php`). There is no `AddCalculatedColumn`. |
| B39 | 0 | New forms are hand-written `<field><input>`/`<select>`, not UIGeneralFunctions (for example `CreditControl.php:227-339`, `CreditControlSetup.php:80-125`). `LogCreditEvent` runs `DB_escape_string` on POST text that session.php has already escaped (`CreditControlFunctions.php:145-148`). |
| B40 | 0.5 | `$Title`/`$ViewTopic`/`$BookMark` come before header.php, and `ManualCreditControl.html` has a ManualOutline entry. The pages use `$ViewTopic='AccountsReceivable'` with bookmarks (`CreditControl`, `CreditCharges`, …) that do not exist in `ManualAccountsReceivable.html`. The new manual's topic is never referenced, so the help anchors break. |

**B total: 29 / 40**

## Summary

- **A: 40 / 43**
- **B: 29 / 40**
- **Total: 69 / 83**
- **Correctness: 3 / 5.** The core flows are complete and coherent: reviews, the stop gate on most routes, over-limit hold and release, dunning, charges, waivers, write-offs and reconciliation. The approval and transaction structure is sound. However, the fresh non-demo install breaks, customer delete breaks, and some stop routes are still open (API invoice, counter sales).
- **Conventions: 3 / 5.** The install and upgrade work is thorough: 44.php helpers, the guard, table files, single-statement seeds, demo.sql, the GetConfig guard and Z_ChangeCustomerCode. Against that: token numbers are hard-coded, forms do not use UIGeneralFunctions, text is escaped twice, there is no InsertGLTags, settings are outside SystemParameters, and the manual topic and bookmarks do not match.

### Regressions

1. **Fresh non-demo install fails.** The `companies` table has three new columns, but the positional `INSERT INTO companies VALUES (...)` in `includes/InstallFunctions.php:505-532` was not extended, so the company row is not inserted.
2. **Customer delete is broken for new customers.** `Customers.php` writes a `creditlog` row (with an FK to debtorsmaster) when an account is opened. Delete removes custbranch and custcontacts (`Customers.php:375-377`), then the debtorsmaster delete (`:379`) fails on the FK. The customer is left without branches.
3. **Context help breaks on all new pages.** Bookmarks `CreditControl`, `CreditCharges`, `CreditDunningRun`, `CreditWriteOff`, `CreditOrderRelease`, `CreditReconciliation`, `CreditControlSetup` and `CreditControlReport` point into `ManualAccountsReceivable.html`, which has no such anchors.
4. **Stray backslashes in history.** History text with apostrophes is escaped twice and shows stray backslashes (`LogCreditEvent`).
5. **Watch shown to customers.** Watch customers see "ACCOUNT ON HOLD" in the portal's Account Status page (`CustomerInquiry.php:170-172`, unchanged). This contradicts the stated decision that customers never see watch.
6. **Demo hold reasons changed (side effect).** In `install/sql/demo.sql`, hold reasons were reseeded with 1/2 values, so demo customers with codes 1, 2, 4, 5, 7 or 8 are now on stop and blocked from ordering.
