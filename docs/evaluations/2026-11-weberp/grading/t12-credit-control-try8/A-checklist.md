# t12 credit control, try 8, implementation A: checklist grading

Graded from the code in the workspace and the diff, not from NOTES.md (NOTES.md is used only for the open-question decisions, section 9). Paths are relative to the workspace root.

## A. BRD requirements (BR-01..BR-43)

| # | BR | Score | Evidence |
|---|---|---|---|
| A1 | BR-01 review record | 1 | CreditReview.php:131-153 inserts date, userid, outcome, old and new limit, notes, next review date |
| A2 | BR-02 next review date for everyone, new customers automatic | 1 | Customers.php:224 (CreditNextReviewDate), api_customers.php:362, Z_ImportDebtors.php:428; standard period CreditControlSettings.php:72; 44.php:199 back-fills existing customers |
| A3 | BR-03 history kept, cannot be changed | 1 | CreditReview.php:329-348 is read-only; no edit or delete path for creditreviews |
| A4 | BR-04 limit changes inside the review | 1 | CreditReview.php:115-155: the limit UPDATE and the review INSERT are in one transaction |
| A5 | BR-05 stop/unstop with reason, who, when | 1 | CreditReview.php:88-91 makes notes mandatory; CreditControlFunctions.php:167-178 logs the old and new status with the reason (user and date in CreditLog:124-141) |
| A6 | BR-06 no orders on stop by any route; no dispatch | 0.5 | Blocked in DeliveryDetails.php:331-347, EDIProcessOrders.php:902-910, RecurringSalesOrdersProcess.php:103-112, api_salesorders.php:347-353, ConfirmDispatch_Invoice.php:25-42, api InvoiceSalesOrder:813-818. Not blocked in CounterSales.php:131-202, which only warns, so counter sales still invoices a stopped account (NOTES admits this) |
| A7 | BR-07 only credit control changes stop/limit | 1 | Customers.php:150-185 removes holdreason/creditlimit from UPDATE; new accounts get them only with token 21 (:215-222); api_customers.php ModifyCustomer unsets them (:475-476); pages are token 21 |
| A8 | BR-08 watch: supplied, warned, listed | 0.5 | Warnings in DeliveryDetails.php:344-346 and SelectOrderItems.php:439-441; listed in CreditHeldOrders.php:95. A watched customer in the web shop is still refused with "account on hold" (SelectOrderItems.php:539, else branch at :572-575, unchanged), so the web-shop route does not supply watched customers |
| A9 | BR-09 status visible where staff look/take orders | 1 | CustomerInquiry.php:171-181, CustomerAccount.php:234-242, Customers.php:1001-1005, AgedDebtors.php:321, SelectOrderItems.php:439-441, CreditReview.php:202-206 |
| A10 | BR-10 over-limit orders held for approval | 0.5 | Holds only when CheckCreditLimits==3 (CreditControlFunctions.php:201-209). The upgrade moves only 0 and 1 to 3 (44.php:195). A fresh install keeps '1' (install/sql/data/config.sql), and sites on 2 keep "prohibit". The API checks only the balance already on the account (api_salesorders.php:347) |
| A11 | BR-11 web-shop customer told account on hold | 1 | SelectOrderItems.php:572-575 and DeliveryDetails.php:338-340 message "contact credit control"; CustomerInquiry.php:176-177; CreditHistory.php:73-74 |
| A12 | BR-12 escalating stages, configurable number/days/wording | 1 | DunningStages.php:20-60 (days and wording per stage and language), add and remove stage at :61-80; three seeded stages in 44.php:202-214 |
| A13 | BR-13 email to accounts contact; list those without email | 1 | DunningRun.php:73-78 (custcontacts statement=1), :208 and :168-172 list customers to post to |
| A14 | BR-14 run started by credit control, preview and exclusion | 1 | DunningRun.php:179-213 preview with untickable rows; sends only the ticked ones (:116) |
| A15 | BR-15 move up only if overdue; no repeat in short time | 1 | DunningRun.php:37-39 (no overdue items means no letter), :58-64 (stage must exceed the last one sent), :66-71 (gap days) |
| A16 | BR-16 record date, stage, invoices, amount | 1 | DunningRun.php:139-150 dunninglog insert |
| A17 | BR-17 customer currency, overdue invoices | 1 | DunningRun.php:95-103 |
| A18 | BR-18 disputed not chased nor charged | 1 | CreditReview.php:163-181 marks items; CreditControlFunctions.php:241-243 excludes them; used by DunningRun.php:37 and CreditCharges.php:94 |
| A19 | BR-19 interest, fee, both; rate/fee/days set by Finance | 1 | CreditCharges.php:86-119; settings in CreditControlSettings.php:76-96 |
| A20 | BR-20 exemptions per customer | 1 | CreditReview.php:77-78,117-120; CreditCharges.php:112-116 |
| A21 | BR-21 own currency; on account and statement as separate items | 0.5 | Separate types 51 and 52 in customer currency (CreditCharges.php:143). CustomerInquiry.php:630 has a generic else that shows them. CustomerAccount.php:289-393 renders only types 10, 11 and 12, so the charges are missing from the account page |
| A22 | BR-22 preview and confirm; no double month | 1 | CreditCharges.php:156-199 preview and confirm; :108-116 plus the UNIQUE key in 44.php:109 |
| A23 | BR-23 GL to income accounts chosen by Finance | 1 | CreditControlFunctions.php:300-305; accounts picked in CreditControlSettings.php:91-95 |
| A24 | BR-24 waive with reason, reaches ledger | 1 | CreditCharges.php:41-77 (type 53 with GL through CreditInsertDebtorTrans) |
| A25 | BR-25 write off all/part with reason | 1 | CreditWriteOffs.php:97-142 |
| A26 | BR-26 approval above threshold | 1 | CreditWriteOffs.php:126-131 waits; approval needs token 22 and a different user (:67-94) |
| A27 | BR-27 reduces balance, bad debt account, currency difference | 1 | CreditWriteOffs.php:44-47; exchange difference in CreditControlFunctions.php:362-366 |
| A28 | BR-28 auto stop unless decided otherwise | 1 | CreditWriteOffs.php:56-61; checkbox defaults to on (:167-168) |
| A29 | BR-29 write-off report | 1 | CreditWriteOffs.php:212-257 shows customer, amount, reason, requested by, approved by |
| A30 | BR-30 credit control report, filters, home totals | 1 | CreditControlReport.php:59-140 |
| A31 | BR-31 aged report: status, limit, last stage | 1 | AgedDebtors.php:280-282,304-323 |
| A32 | BR-32 per-customer history | 1 | CreditHistory.php:128-150 (creditlog shows reviews, status, limit, reminders, charges, waivers, write-offs) |
| A33 | BR-33 reps see own customers only | 1 | CreditHistory.php:51 via CreditCustomerVisible (CreditControlFunctions.php:49-60); CreditControlReport.php:23-25,73 |
| A34 | BR-34 reps see, cannot change | 1 | CreditReview.php and the other change pages are token 21 (44.php:151-155); Customers.php:956-1007 shows these fields read-only |
| A35 | BR-35 portal: reminders, charges, balance | 1 | CreditHistory.php:21-22,76-126; linked from CustomerInquiry.php:181 |
| A36 | BR-36 customer sees only own account | 1 | CustomerInquiry.php:28-30, CustomerAccount.php:28-30, CreditHistory.php:21-22,51 |
| A37 | BR-37 balances agree with control account | 1 | Every new posting debits or credits debtorsact against the opposite side (CreditControlFunctions.php:300-305,362-366) |
| A38 | BR-38 find out why if not | 1 | Z_CheckDebtorsControl.php:122-136 adds types 51-54; :164-208 lists unmatched entries on both sides |
| A39 | BR-39 live and new install | 1 | sql/updates/44.php plus install/sql/tables/*, data/*, demo.sql |
| A40 | BR-40 go-live: normal, review date, stop list loaded | 1 | 44.php:191,199; Z_ImportCreditStatus.php:33-75 (check first, then load) |
| A41 | BR-41 no change for non-overdue customers | 1 | ConfirmDispatch and order checks act only on stop, watch or over-limit; no change to invoices or statements |
| A42 | BR-42 staff guide | 1 | doc/Manual/ManualCreditControl.html covers settings, reviews, stop/watch, reminders, charges, write-offs, report, reconciliation, go-live; ManualOutline.php:116-127 |
| A43 | BR-43 note for sales staff | 1 | ManualCreditControl.html:78-81 |

**A total: 41 / 43**

## B. Rules away from the change (B1-B40)

| # | Score | Evidence |
|---|---|---|
| B1 | 1 | Status is holdreason to dissallowinvoices 0/1/2 (CreditControlFunctions.php:74-110); no parallel customer flag. salesorders.creditheld is an order-level approval flag |
| B2 | 1 | ConfirmDispatch_Invoice.php:25-42 |
| B3 | 1 | RecurringSalesOrdersProcess.php:99-112; auto-invoice skipped when held (:227) |
| B4 | 1 | EDIProcessOrders.php:896-910 |
| B5 | 1 | api_salesorders.php:343-356 (header) and :811-819 (InvoiceSalesOrder) |
| B6 | 1 | CreditControlFunctions.php:201-209 follows CheckCreditLimits and reuses GetCreditAvailable; option 3 is added to the existing setting (SystemParameters.php:479) |
| B7 | 0.5 | Z_ChangeCustomerCode.php:206-211 moves the new tables. The debtorsmaster re-INSERT column list (:44-107) lacks nextreviewdate, interestexempt and feeexempt, so a rename loses them |
| B8 | 1 | Customers.php:352-362: creditreviews, dunninglog, creditcharges and creditwriteoffs block the delete |
| B9 | 0.5 | Z_ImportDebtors.php:405,428 sets nextreviewdate itself. The column is not appended to $FieldHeadings, and the exemptions are not carried |
| B10 | 0.5 | ModifyCustomer unsets holdreason, creditlimit and the new columns (api_customers.php:475-476). InsertCustomer still accepts holdreason and creditlimit unchecked, and a caller-supplied nextreviewdate is not validated (:361-363) |
| B11 | 1 | NewSysType 51-54 (44.php:135-138), systypes.sql, demo.sql |
| B12 | 1 | GetNextTransNo inside DB_Txn_Begin (CreditControlFunctions.php:270; callers CreditCharges.php:131-151, CreditWriteOffs.php:43-62) |
| B13 | 0.5 | GetPeriod is used (CreditControlFunctions.php:269). There is no ProhibitPostingsBefore check or display, so a past-month charge date (CreditCharges.php:80-82) is shifted silently |
| B14 | 1 | CreditControlFunctions.php:300-305,362 (gllink_debtors==1, debtorsact) |
| B15 | 0 | No EnsureGLEntriesBalance in any new posting |
| B16 | 1 | CreditControlFunctions.php:301-304: amount/rate; charges positive, waivers and write-offs negative |
| B17 | 0 | No InsertGLTags after the gltrans inserts (CreditControlFunctions.php:309-325) |
| B18 | 0 | CreditControlSettings.php:35-43 accepts any chartmaster account; no control-account refusal |
| B19 | 0.5 | Write-offs and waivers are allocated in code at posting (CreditControlFunctions.php:331-368). Types 53 and 54 are not added to CustomerAllocations' 11/12 source list, so a leftover waiver credit (CreditCharges.php:60-65) cannot be allocated later |
| B20 | 1 | CreditControlFunctions.php:362-366 posts to salesexchangediffact and debtorsact with the CustomerAllocations signs |
| B21 | 0.5 | CustomerInquiry.php:630 shows the new types through its generic else. CustomerAccount.php:289-393 has no else, so types 51-54 are dropped |
| B22 | 0 | CreditInsertDebtorTrans (CreditControlFunctions.php:273-296) does not set debtortrans.salesperson |
| B23 | 1 | Own guard: UNIQUE(debtorno,chargemonth,chargetype) (44.php:109) plus the check at CreditCharges.php:108-116 |
| B24 | 0 | GL accounts are config keys (44.php:180-182), not companies columns; no GetConfig, CompanyPreferences or GLAccounts delete guard |
| B25 | 0.5 | The due-date rule matches AgedDebtors (CreditControlFunctions.php:215-221). Reminder bands are separate dunningstages days, and PastDueDays1/2 are not used |
| B26 | 0.5 | Open items use `settled=0 AND balance > 0` (CreditControlFunctions.php:239-240, CreditReview.php:283-284, DunningRun.php:180), which mixes settled with balance |
| B27 | 1 | DunningRun.php:73 custcontacts.statement=1 with IsEmailAddress |
| B28 | 1 | No PDF is made; letters are plain-text email (DunningRun.php:132); no Cpdf or PDFStarter |
| B29 | 1 | DunningRun.php:132-136 counts a send only when `=== true`; no temp file is involved |
| B30 | 0.5 | Filtered in CreditControlReport.php:23-25,73 and CreditHistory.php:51. No SalesmanLogin filter in DunningRun.php:180, CreditCharges.php:170, CreditHeldOrders.php:42-60, the CreditWriteOffs.php report (:225-236) or the CreditReview.php search (:29-34) |
| B31 | 1 | Portal pinned to LoginCustomerID: CustomerInquiry.php:28-30, CustomerAccount.php:28-30, CreditHistory.php:21-22; includes/LoginFunctions.php:109-110 |
| B32 | 0 | Hard-coded tokens: CREDIT_TOKEN_CONTROL 21 and APPROVE 22 checked with in_array (CreditControlFunctions.php:18-34), plus in_array(8, ...) at CreditHistory.php:19; no false-script entry |
| B33 | 1 | All 10 new pages are in NewScript (44.php:151-160), scripts.sql and demo.sql; no $PageSecurity in any new page |
| B34 | 0.5 | Idempotent helpers and exact CreateTable names are used (44.php:11-214). UpdateDBNo at :216 is unguarded, with no `$_SESSION['Updates']['Errors'] == 0` check |
| B35 | 1 | install/sql/tables/creditcharges, creditlog, creditreviews, creditwriteoffs, dunninglog, dunningstages, dunningtexts.sql; dates default '1000-01-01' |
| B36 | 1 | Seeds in install/sql/data/{config,menuitems,scripts,securitygroups,securitytokens,systypes,dunningstages,dunningtexts}.sql (one statement each) and install/sql/demo.sql:20820-20842 |
| B37 | 0.5 | Menu rows for roles 1-9 (menuitems.sql:3-11, NewMenuItem 44.php:163-172, demo SELECT FROM securityroles). Config uses NewConfigValue and both seeds, but the settings live in CreditControlSettings.php, not SystemParameters.php (only option 3 was added there) |
| B38 | 1 | Only AddColumn, AddIndex, CreateTable, NewSysType, NewSecurityToken, InsertRecord, NewScript, NewMenuItem, NewConfigValue and executeSQL, which exist in every UpgradeDB variant; no AddCalculatedColumn |
| B39 | 0.5 | No double escaping of POST (array keys are escaped deliberately, DunningRun.php:117). Every form is hand-written; UIGeneralFunctions is not used (e.g. CreditReview.php:232-269, CreditControlSettings.php:58-65) |
| B40 | 0.5 | $Title, $ViewTopic and $BookMark come before header.php in every new page, and ManualOutline.php:116 is added. Only CreditReview and CreditControlReport have matching anchors; the bookmarks DunningRun, CreditCharges, CreditWriteOffs, CreditControlSettings, CreditHistory, CreditHeldOrders, DunningStages and ImportCreditStatus have none in ManualCreditControl.html |

**B total: 27 / 40**

## Totals

- A: 41 / 43
- B: 27 / 40
- Total: 68 / 83
- Correctness: 3.5 / 5. A thorough, coherent build on the existing hold mechanism, with every order route except counter sales guarded. Defects:
  - The charges are missing from CustomerAccount.php.
  - Watched customers are refused in the web shop.
  - A customer rename loses the new columns.
  - There is no GL balance check and no ProhibitPostingsBefore check.
  - Over-limit holding depends on the setting being 3.
  - Operator precedence bug at CreditHistory.php:19: `$SeesEverything = !$IsPortalUser and (...)` assigns only `!$IsPortalUser`, so every staff user, reps included, sees the full audit trail for the customers visible to them.
- Conventions: 3 / 5. Well registered: scripts, menus for all roles, install mirrors, idempotent helpers, `__()`. Against convention: hard-coded token numbers, unguarded UpdateDBNo, hand-written forms, a new Z_ utility, missing manual anchors, dead `if (true)` branches in CreditStatus.php:69,86, and no InsertGLTags or EnsureGLEntriesBalance.

## Regressions

1. Z_ChangeCustomerCode.php:44-107: renaming a customer drops nextreviewdate, interestexempt and feeexempt. The review date falls back to 1000-01-01, so the customer shows as overdue for review, and its exemptions are lost.
2. 44.php:195 silently changes CheckCreditLimits 0 ("do not check") and 1 ("warn") to 3 on upgrade, so sites that never checked limits start holding orders. A fresh install keeps '1', so upgrade and install behave differently.
3. 44.php:191 sets hold reasons from -1 to 0. Customer-login order entry (SelectOrderItems.php:539) used to refuse those customers, and now accepts them.
4. Portal sessions that started before the update see an empty CustomerInquiry or CustomerAccount (CreditPortalCustomer() returns ''), until the user logs in again.
5. CreditStatus.php:69,86: the checkbox became a select, which leaves dead `else` branches. Saving a hold reason now always writes the selected 0/1/2.
6. CustomerAccount.php does not render types 51-54, although they count in its balance, so the rows and the total disagree visibly once charges exist.
