# t12 credit control, try 9, run B: checklist grading

Graded from the code in the post-run workspace (`blind12g/B/`) against base. There is no NOTES.md, so no open BRD question counts as decided.

Scope: the run added CustomerCredit.php, CreditControlDunning.php, CreditControlCharges.php, CreditControlSetup.php and includes/CreditControlFunctions.php, plus order-route guards, the schema, the seeds and sql/updates/44.php. The menus and the scripts table also register **CreditControlWriteOff.php, CreditControlReport.php, DebtorsGLReconciliation.php and CustomerCreditNotices.php, but none of these four files exists**. Write-offs, the credit control report, the GL reconciliation, the customer portal page and the manual are therefore absent. No code anywhere sets `salesorders.creditflag` to 3 (released).

Line numbers refer to files in the workspace.

## A. BRD requirements

| # | Score | Evidence |
|---|---|---|
| A1 BR-01 review record | 1 | CustomerCredit.php:46-129: date, userid, outcome (confirmed/raised/reduced/watch/stop/normal), old and new limit, notes, next review date go into creditreviews. |
| A2 BR-02 every customer has a next review date | 0.5 | New customers get one in Customers.php:283 (CreditNextReviewDate from CreditReviewMonths), and existing customers are back-filled at 44.php:202. API InsertCustomer and Z_ImportDebtors leave it NULL. |
| A3 BR-03 review history kept, not editable | 1 | CustomerCredit.php:400-418 lists the reviews; there is no edit or delete path. Customer delete is blocked when history exists (Customers.php:368-377). |
| A4 BR-04 limit changes with the review | 1 | CustomerCredit.php:87-110: review insert and debtorsmaster.creditlimit update happen in one transaction. |
| A5 BR-05 stop/unstop with reason, who and when | 1 | SetCreditStatus in CreditControlFunctions.php:134-163 checks the reason against the status; CustomerCredit.php:131-146 requires a note; creditcontrollog records the user and NOW(). |
| A6 BR-06 stop blocks every route, and dispatch unless released | 0.5 | New orders are refused in DeliveryDetails.php:329-351, EDIProcessOrders.php:896-913, RecurringSalesOrdersProcess.php:96-107 and api_salesorders.php:280-288. Dispatch and invoice are blocked in ConfirmDispatch_Invoice.php:155-163 and 624-630 and in api InvoiceSalesOrder (807). But nothing can release an order: creditflag=3 is never set. |
| A7 BR-07 only credit control changes stop and limits | 0.5 | Token 21 gates CustomerCredit, and Customers.php:135-150 and 973/1016 lock both fields for everyone else. API ModifyCustomer still changes holdreason and creditlimit. CreditStatus.php (token 3) still lets AR staff change what a reason does. |
| A8 BR-08 watch: warning, plus a credit control list of watched orders | 0.5 | The warning is in base SelectOrderItems.php:439 and DeliveryDetails.php (CreditCheckForNewOrder, CreditControlFunctions.php:258-262), and orders are flagged creditflag=2. The list of these orders was meant for CreditControlReport.php, which does not exist. |
| A9 BR-09 status visible wherever staff look | 0.5 | Shown on CustomerCredit.php:216-233, in order entry (base), and in CustomerInquiry/CustomerAccount (base hold banner). SelectCustomer and the other customer screens have no watch/stop indicator. |
| A10 BR-10 over-limit orders held for approval | 0.5 | Held via CreditCheckForNewOrder (CreditControlFunctions.php:251-257), but there is no approve/release function. The API creates orders with value 0, so the over-limit hold is never applied there, despite the comment at api_salesorders.php:280. |
| A11 BR-11 web shop shows "on hold, contact us" | 1 | Base SelectOrderItems.php:576, and the DeliveryDetails message includes CreditControlContactText (CreditControlFunctions.php:289). |
| A12 BR-12 configurable stages, days and wording | 1 | CreditControlSetup.php:71-119 and 256-301; three stages seeded (44.php:187-199, dunningstages.sql). |
| A13 BR-13 email the accounts contact; no-email customers listed for posting | 1 | GetAccountsEmailAddresses (CreditControlFunctions.php:322-347); CreditControlDunning.php:60-72 and 107-112 list the letters to post. |
| A14 BR-14 run started by credit control, preview, exclude customers | 1 | CreditControlDunning.php:116-159 (tick boxes), with recalculation on send at :36-46. |
| A15 BR-15 only if still overdue; no repeat stage soon | 1 | GetDunningCandidates recalculates from open items, and the CreditDunningMinDays guard is at CreditControlFunctions.php:404-412. |
| A16 BR-16 each reminder recorded with date, stage, items, amount | 1 | dunninghistory insert at CreditControlDunning.php:75-94. |
| A17 BR-17 customer currency, overdue invoices listed | 1 | MergeDunningText (CreditControlFunctions.php:350-362) uses currcode and the {invoices} list. |
| A18 BR-18 disputed invoices not chased or charged | 1 | debtortrans.disputed is set at CustomerCredit.php:178-200 and filtered out in GetOverdueItems (:194) and in the dunning and charge selects. |
| A19 BR-19 interest and/or fee, with rate, fee and days configurable | 1 | CreditControlCharges.php:41-104 and CreditControlSetup.php:19-28. |
| A20 BR-20 per-customer exemptions | 1 | debtorsmaster.exemptinterest/exemptfees: CustomerCredit.php:148-166 and CreditControlCharges.php:87-98. |
| A21 BR-21 own currency, separate items on account and statement | 0.5 | Type 60 rows in customer currency with invtext (PostCreditControlTransaction). CustomerInquiry.php and CustomerAccount.php only render types 10/11/12, so the charges do not show on the on-screen account. |
| A22 BR-22 preview and confirm; no double charge | 1 | Preview table plus confirm at CreditControlCharges.php:212-253; debtorcharges has a UNIQUE(debtorno, chargemonth, chargetype) key and is pre-checked at :72-98. |
| A23 BR-23 post to Finance's income accounts | 0.5 | The accounts are chosen in CreditControlSetup.php:58-66. GetConfig.php does not load interestincomeact or latefeeact, so in any session other than the one that saved them they are unset. The guard at CreditControlCharges.php:24 (`== '0'`) does not catch null, and the income line is posted to account ''. |
| A24 BR-24 waiver with reason reaches the ledger | 0.5 | Type 61 waiver with reason, allocated to the charge (CreditControlCharges.php:144-189). It has the same unloaded GL-account defect as A23. |
| A25 BR-25 write off all or part with reason | 0 | CreditControlWriteOff.php does not exist; only the creditwriteoffs table and type 62 were added. |
| A26 BR-26 Finance Director approval above a threshold | 0 | The setting and token 22 exist; there is no code that uses them. |
| A27 BR-27 write-off reduces the balance, bad-debt GL, currency difference | 0 | Not implemented. |
| A28 BR-28 auto stop on write-off | 0 | Not implemented. |
| A29 BR-29 write-off report | 0 | Not implemented. |
| A30 BR-30 credit control report (review due, over limit, watch/stop, rep/currency filters, home totals) | 0 | CreditControlReport.php is missing; the menu link leads nowhere. |
| A31 BR-31 aged debt shows status, limit, last stage | 0 | AgedDebtors.php is unchanged. |
| A32 BR-32 auditable history per customer | 0.5 | creditcontrollog is written for reviews, status, limit, exemptions, disputes, reminders, charges and waivers, including Customers.php:220-229, and shown at CustomerCredit.php:382-398. Write-offs, which do not exist, are not covered. |
| A33 BR-33 reps see only their own customers | 1 | UserCanSeeCustomerCredit (CreditControlFunctions.php:42-56) is enforced at CustomerCredit.php:35-39. The dunning and charge pages need token 21, which no sales role has. |
| A34 BR-34 reps view but cannot change | 1 | `$CanChange = UserIsCreditController()` on CustomerCredit.php:41; Customers.php fields are read-only or disabled for others. |
| A35 BR-35 portal shows reminders and charges | 0 | CustomerCreditNotices.php is missing; CustomerCredit.php needs token 2, which customer roles lack. |
| A36 BR-36 customer sees only their own account | 1 | UserCanSeeCustomerCredit restricts a customer login to its own CustomerID (CreditControlFunctions.php:44-46). |
| A37 BR-37 debtor balances agree with the GL control account | 0.5 | Charges and waivers post debtorsact equal to amount/rate (CreditControlFunctions.php:430-503). Write-offs are missing. EnsureGLEntriesBalance can roll back while the caller still commits. |
| A38 BR-38 find out why they disagree | 0 | DebtorsGLReconciliation.php is missing (only the base Z_CheckDebtorsControl.php exists). |
| A39 BR-39 live upgrade and new install | 0.5 | 44.php plus the install tables, data and demo files are present. Menus and scripts point to 4 missing pages, and GetConfig is not extended. |
| A40 BR-40 go-live status, review dates, stop list loaded | 1 | Existing hold reasons are kept, next review dates are back-filled (44.php:202), and CSV load is at CreditControlSetup.php:122-185. |
| A41 BR-41 no change for customers who are not overdue | 0.5 | CheckCreditLimits=1, which used to warn only, now holds over-limit orders, and these can never be released. The holdreason classes in the demo data were reclassified (demo.sql). |
| A42 BR-42 staff guide | 0 | No manual pages and no ManualOutline entry. |
| A43 BR-43 sales note | 0 | None. |

**A = 25.5 / 43**

## B. Rules away from the change

| # | Score | Evidence |
|---|---|---|
| B1 hold = holdreason → dissallowinvoices 1/2, no parallel flag | 1 | GetCreditStatus at CreditControlFunctions.php:70-97; SetCreditStatus only updates debtorsmaster.holdreason. |
| B2 hold enforced at dispatch/invoice | 1 | ConfirmDispatch_Invoice.php:155-163 and :624-630 (OrderCreditBlock). |
| B3 recurring orders | 1 | RecurringSalesOrdersProcess.php:96-107 refuses stop customers; :223 skips autoinvoice for held orders. |
| B4 EDI import | 1 | EDIProcessOrders.php:896-913, with `!$CreditRefused` on the create branch. |
| B5 API order and invoice functions | 1 | api_salesorders.php:280-288 (InsertSalesOrderHeader) and :807-811 (InvoiceSalesOrder); error code 1174. |
| B6 CheckCreditLimits 0/1/2, reuse GetCreditAvailable | 0.5 | Respects CheckCreditLimits > 0 (CreditControlFunctions.php:251) but treats 1 and 2 the same, and CreditHeadroomForOrder (:206-225) is a parallel formula instead of GetCreditAvailable. |
| B7 Z_ChangeCustomerCode handles the new tables | 0 | Z_ChangeCustomerCode.php is unchanged; creditreviews, creditcontrollog, dunninghistory, debtorcharges and creditwriteoffs are not handled. |
| B8 Customers.php delete covers the new tables | 0.5 | Only creditcontrollog blocks the delete (Customers.php:368-377); the other four debtorno tables are not checked. Most of their writers also log, so in practice it mostly holds. |
| B9 Z_ImportDebtors carries the new columns | 0 | Unchanged, so nextreviewdate is left NULL for imported customers. |
| B10 API Modify/InsertCustomer: new column, holdreason/creditlimit | 0 | api_debtors unchanged; holdreason and creditlimit stay open to the API. |
| B11 new systypes via systypes.sql and NewSysType | 0.5 | Rows 60/61/62 are in systypes.sql and demo.sql. 44.php:133-138 uses a raw INSERT…WHERE NOT EXISTS instead of NewSysType. |
| B12 GetNextTransNo inside the transaction | 1 | Callers open DB_Txn_Begin before PostCreditControlTransaction (CreditControlCharges.php:126, :175); GetNextTransNo is at CreditControlFunctions.php:450. |
| B13 GetPeriod; ProhibitPostingsBefore | 0.5 | GetPeriod at CreditControlFunctions.php:451; ProhibitPostingsBefore is not checked. |
| B14 gllink_debtors == 1, AR side to debtorsact | 1 | CreditControlFunctions.php:482-484. |
| B15 EnsureGLEntriesBalance and stop on imbalance | 0.5 | Called at :501, but the caller continues and commits after its rollback (CreditControlCharges.php:137, :184). |
| B16 GL = amount/rate, charges +, write-offs − | 1 | `$HomeAmount = $Amount / $Rate` at :433; charges positive, waivers negative. |
| B17 InsertGLTags after each gltrans insert | 0 | Not called anywhere in the GL loop (:484-500). |
| B18 write-off account refused if it is a control account | 0 | BadDebtAct accepts any chartmaster code (CreditControlSetup.php:43-50), and there is no write-off page. |
| B19 new types usable in allocation | 0.5 | Waivers are auto-allocated to their charge (AllocateCreditControlTransaction, :507-522), and type 60 debits appear in the CustomerAllocations debit list. Type 62 is never posted, and the CustomerAllocations.php:481/538 credit lists are still hard-coded to 11/12. |
| B20 exchange difference on FX write-off/allocation | 0 | No salesexchangediffact posting; the waiver is reversed at the booked rate and there is no write-off. |
| B21 CustomerAccount/CustomerInquiry show the new types | 0 | Both are unchanged; their type branches cover only 10/11/12 (CustomerInquiry.php:376-568). |
| B22 debtortrans.salesperson recorded | 1 | CreditControlFunctions.php:465 and :478 (branch salesman). |
| B23 own guard against double monthly charge | 1 | debtorcharges UNIQUE key (debtorcharges.sql) plus the pre-check at CreditControlCharges.php:72-98. |
| B24 new companies GL columns in GetConfig, CompanyPreferences, GLAccounts guard and positional INSERTs | 0.5 | Positional INSERTs updated (InstallFunctions.php:531-534, demo.sql). GetConfig.php:61-96, CompanyPreferences.php and the GLAccounts.php delete guard are untouched, which causes the A23 defect. |
| B25 due-date rule as AgedDebtors | 1 | OverdueDaysSQL (CreditControlFunctions.php:166-171) handles daysbeforedue vs dayinfollowingmonth; Finance-set stages replace PastDueDays bands, as the BRD requires. |
| B26 open items by balance | 1 | `debtortrans.balance > CurrencyTolerance` at :193 and in the candidate selects. |
| B27 recipients = custcontacts.statement=1 | 0.5 | Uses statement=1 (:327) but falls back to the branch email (:333-345). |
| B28 PDFs with Dompdf | 0.5 | No Cpdf/PDFStarter, but no PDF either: letters are plain-text email bodies. |
| B29 SendEmailFromWebERP === true; temp file | 1 | `$EmailResult !== true` → failed, not recorded (CreditControlDunning.php:63-67); no attachment, so no temp file. |
| B30 SalesmanLogin filter on every list/run/report | 0.5 | Enforced on CustomerCredit.php. SalesRepCustomerLimit is defined but never used; the dunning and charge lists are unfiltered (token-gated only); the report is missing. |
| B31 customer login sees only its own debtorno | 0.5 | Enforced in UserCanSeeCustomerCredit, but the portal page is missing, so the rule is never exercised for customers. |
| B32 permission via a scripts-table "false script", not hard-coded tokens | 0 | UserIsCreditController/UserIsCreditApprover hard-code `in_array(21/22, …)` (CreditControlFunctions.php:32-39). |
| B33 every new page in scripts (NewScript, data, demo); no $PageSecurity | 1 | 44.php:150-157, creditcontrolscripts.sql and demo.sql; the pages do not set $PageSecurity. (It also registers 4 pages that do not exist.) |
| B34 44.php idempotent helpers, CreateTable exact names, guarded UpdateDBNo on one line | 0.5 | Helpers are fine (CreateTable, AddColumn, NewScript…), but UpdateDBNo is indented inside a 3-line `if` block (44.php:204-206). |
| B35 install table files, '1000-01-01' dates | 1 | Six new tables/*.sql files; dates default '1000-01-01' (creditreviews) or are datetime NOT NULL with no zero default. |
| B36 seeds in data/*.sql and install/sql/demo.sql, one statement per file | 1 | creditcontrol.sql, creditcontrolmenuitems.sql, creditcontrolscripts.sql, dunningstages.sql and holdreasons.sql are single statements; demo.sql has matching rows. |
| B37 menu rows for every role; config via NewConfigValue, seeds and SystemParameters.php | 0.5 | NewMenuItem plus seeds for roles 1-9, and NewConfigValue plus seeds. SystemParameters.php is not touched (own settings page instead), and 3 of the 6 menu rows point to missing pages. |
| B38 only helpers present in all UpgradeDB_* variants | 1 | Uses CreateTable, AddColumn, NewSecurityToken, NewConfigValue, NewScript, NewMenuItem and executeSQL; no AddCalculatedColumn. |
| B39 UIGeneralFunctions forms; no double escaping | 0 | Hand-written fieldset HTML throughout. CreditControlLog re-escapes already-escaped POST text (DB_escape_string on Notes, HistoryNote and WaiveReason, CreditControlFunctions.php:110). |
| B40 $Title/$ViewTopic/$BookMark before header; manual page and ManualOutline | 0.5 | The variables are set before header.php on all 4 pages; there are no manual pages, anchors or ManualOutline entry. |

**B = 24 / 40**

## Scores

- A: 25.5 / 43
- B: 24 / 40
- Total: 49.5 / 83
- Correctness: 2 / 5. The run is incomplete: write-offs, the report, the reconciliation, the portal and the manual are missing. Held orders can never be released. The GL income accounts are not loaded into the session, so charges post to account ''.
- Conventions: 3 / 5. The install and upgrade layout follows project patterns, and the data files and $Title/$ViewTopic are correct. Against that: hard-coded tokens 21/22, no UIGeneralFunctions, double escaping, no manual.

## Regressions

1. **Held orders are permanently blocked.** Nothing sets `creditflag = 3`, and DeliveryDetails.php:344-350 keeps HELD on every edit. Any over-limit order entered by a non-credit-controller, or a pre-stop order that is edited, can never be dispatched or invoiced. CheckCreditLimits=1 used to warn only; it now holds.
2. **Dead links and scripts.** Menu rows for all roles and scripts rows point to CreditControlWriteOff.php, CreditControlReport.php, DebtorsGLReconciliation.php and CustomerCreditNotices.php, none of which exist.
3. **GL accounts not loaded.** GetConfig.php does not load interestincomeact, latefeeact or baddebtact. After the next login the guard at CreditControlCharges.php:24 does not fire (null is not == '0'), and charges and waivers post their income line to GL account ''. The settings form also shows blank accounts.
4. **Demo hold reasons reclassified.** demo.sql now makes 1/2/6 watch and 4/5/7/8 stop. Web-shop customers with a watch reason are still turned away by base SelectOrderItems.php:539 (`!= 0`), so "watch can still be supplied" is not met for the web shop.
5. **Commit after rollback.** If EnsureGLEntriesBalance rolls back, the caller still writes debtorcharges and log rows and commits.
6. **Double escaping.** CreditControlLog escapes POST text that session.php has already escaped, so history text can show stray backslashes.
