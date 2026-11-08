# t12 credit control, implementation B: checklist grade

Graded against `tasks/t12-credit-control/checklist.md` (A = BRD BR-01..43, B = rules B1-B40, details in
`grading/t10-credit-control/rules/`). The grade checks the code in the workspace after the run. NOTES.md is used only for decisions on the BRD's open questions.
Paths are relative to the workspace root. Score: 1 met, 0.5 partly met, 0 missed.

## A. BRD requirements

| id | score | evidence |
|---|---|---|
| A1 BR-01 | 1 | CreditControl.php:87 inserts into creditreviews: date, userid, outcome (5 outcomes), old and new limit, notes, next review date |
| A2 BR-02 | 1 | CCNextReviewDate() from config CCReviewMonths (CreditControlSetup.php:21), set on Customers.php:295, api_customers.php:360, Z_ImportDebtors.php:407; per-customer shorter period `reviewmonths` (CreditControl.php:137) |
| A3 BR-03 | 1 | creditreviews and creditcontrollog have insert paths only; history shown at CreditControl.php:302; Customers.php:375 blocks deleting a customer that has history |
| A4 BR-04 | 1 | CreditControl.php:87-96: review row and limit update in one transaction |
| A5 BR-05 | 1 | CreditControl.php:112-131: reason required; CCWriteLog stores userid and datetime |
| A6 BR-06 | 1 | Stop refused in DeliveryDetails.php:339 (sales office and web shop), EDIProcessOrders.php:904, RecurringSalesOrdersProcess.php:102, api_salesorders.php:284. Dispatch/invoice of earlier orders blocked unless released: ConfirmDispatch_Invoice.php:40, api_salesorders.php:810. Release at CreditControlReport.php:24 |
| A7 BR-07 | 0.5 | Token 21 gate in CreditControl.php and Customers.php:144. The API ModifyCustomer still lets any API user change holdreason/creditlimit (NOTES lists this as a gap, not a decision) |
| A8 BR-08 | 1 | Watch warning in SelectOrderItems.php (existing staff path) and DeliveryDetails.php:347. Orders for watched customers listed at CreditControlReport.php:139 |
| A9 BR-09 | 1 | Banner at SelectCustomer.php:154; status on CreditControl.php, AgedDebtors.php:312, the report; order entry warns or refuses |
| A10 BR-10 | 1 | Over-limit orders saved with creditheld=1: DeliveryDetails.php:350, EDI, recurring, API InvoiceSalesOrder; blocked at dispatch until released |
| A11 BR-11 | 1 | CCCustomerStopMessage at SelectOrderItems.php:577 and DeliveryDetails.php (customer login), also in the portal |
| A12 BR-12 | 1 | DunningStages.php:48: stage count, days and wording are editable; 3 seeded stages (44.php InsertRecord dunningstages) |
| A13 BR-13 | 1 | Email to the statement contacts (CreditControlFunctions.php:396); no-email customers listed with printable letters (DunningRun.php:104) |
| A14 BR-14 | 1 | Preview with untick (DunningRun.php:175), send only ticked (DunningRun.php:106); token 21 page |
| A15 BR-15 | 1 | Recomputed from open balances at send time; min gap and no repeat of a stage within 90 days (DunningRun.php:64-66) |
| A16 BR-16 | 1 | dunninglog: date, stage, invoices, amount (DunningRun.php:133), plus a history row |
| A17 BR-17 | 1 | Letter lists overdue items in the customer's currency (DunningRun CCDunningLetter) |
| A18 BR-18 | 1 | debtortrans.disputed set at CreditControl.php:156; excluded from dunning and interest (CreditControlFunctions.php:242) |
| A19 BR-19 | 1 | Rate, fee and days are set in CreditControlSetup.php:20-26; CreditCharges.php charges interest, fee or both |
| A20 BR-20 | 1 | exemptinterest/exemptfees per customer (CreditControl.php:137; CreditCharges.php:67) |
| A21 BR-21 | 0.5 | Type 51 rows in customer currency show in CustomerInquiry (misc row) and PrintCustStatements (systypes name). CustomerAccount.php, the on-screen account statement, drops types other than 10/11/12 (CustomerAccount.php:281-385 has no else) and was not changed |
| A22 BR-22 | 1 | Preview, then confirm (CreditCharges.php:166); recomputed on post; UNIQUE (debtorno, chargemonth, chargetype) plus a check (CreditCharges.php:75) |
| A23 BR-23 | 1 | Income accounts CCInterestAct/CCFeeAct chosen by Finance (CreditCharges.php:101-103) |
| A24 BR-24 | 1 | Waiver with a reason: type 52 credit allocated to the charge, GL reversed (CreditCharges.php:115-150) |
| A25 BR-25 | 1 | CreditWriteOff.php:95: all or part, reason required, capped at the open balance |
| A26 BR-26 | 1 | Above CCWriteOffApprovalLimit the write-off waits (CreditWriteOff.php:115-123); token 22 approves (CreditWriteOff.php:60) |
| A27 BR-27 | 1 | Type 53 allocated to items; bad debt debited at the items' historic rates, so the currency difference lands in bad debt (CreditControlFunctions.php:365-391) |
| A28 BR-28 | 1 | stopcustomer is ticked by default and can be cleared; CreditWriteOff.php:53 |
| A29 BR-29 | 1 | CreditWriteOffReport.php:41-43: customer, amount, reason, requested by, approved by, over a period |
| A30 BR-30 | 1 | CreditControlReport.php:127-136: due for review, over limit (by how much), stop, watch; rep and currency filters; over-limit total in home currency (:112) |
| A31 BR-31 | 1 | AgedDebtors.php:310-312: status, limit, last reminder stage |
| A32 BR-32 | 1 | creditcontrollog written for review, stop/watch, limit, reminder, charge, waiver, write-off and dispute; shown at CreditControl.php:302 |
| A33 BR-33 | 1 | CCUserMaySeeCustomer (CreditControl.php:54, SelectCustomer.php:154); report forced to SalesmanLogin (CreditControlReport.php:37) |
| A34 BR-34 | 1 | Reps see the page; forms render only for token 21; Customers.php keeps the stored values |
| A35 BR-35 | 1 | CustomerCreditPortal.php:42 reminders, :58 charges, balance; linked from the customer menu in index.php |
| A36 BR-36 | 1 | Debtor taken from $_SESSION['CustomerID'] only (CustomerCreditPortal.php:20-26) |
| A37 BR-37 | 1 | Every posting is balanced on debtorsact against income or bad debt; DebtorsReconciliation.php:38 compares |
| A38 BR-38 | 1 | DebtorsReconciliation.php:58 lists differing transactions and control-account postings that have no customer transaction |
| A39 BR-39 | 1 | sql/updates/44.php plus install tables, data and demo.sql |
| A40 BR-40 | 0.5 | Existing hold reasons kept and review dates spread (44.php:187). There is no way to load the spreadsheet stop list or limits in bulk, and the dates are spread by a hash, not set by Finance |
| A41 BR-41 | 0.5 | The EDI `=`→`==` fix (EDIProcessOrders.php:914) stops order creation for message functions 16/31/42/46 and unmatched customers, which changes existing behaviour unrelated to overdue status |
| A42 BR-42 | 1 | Manual section at ManualAccountsReceivable.html:204: reviews, stop and watch, reminder run, charges, write-offs, reports |
| A43 BR-43 | 1 | Note for sales staff at ManualAccountsReceivable.html:215 |

**A = 41 / 43**

## B. Rules away from the change

| id | score | evidence |
|---|---|---|
| B1 | 1 | Status read from holdreason→dissallowinvoices (CreditControlFunctions.php:78-108); no parallel customer flag (creditheld is per order) |
| B2 | 1 | ConfirmDispatch_Invoice.php:40 CCDispatchBlockReason |
| B3 | 1 | RecurringSalesOrdersProcess.php:102 (stop skips; hold disables autoinvoice) |
| B4 | 1 | EDIProcessOrders.php:899-914 |
| B5 | 1 | api_salesorders.php:284 (header) and :810 (InvoiceSalesOrder) |
| B6 | 0 | Parallel CCCreditAvailable (CreditControlFunctions.php:112) instead of GetCreditAvailable; holds follow the new CCHoldOverLimitOrders switch and ignore CheckCreditLimits (0 still holds) |
| B7 | 1 | Z_ChangeCustomerCode.php: 4 new columns in both lists; 5 tables moved (:200) |
| B8 | 1 | Customers.php:375 blocks the delete on creditcontrollog. Every row in the other four tables is written together with a log row |
| B9 | 0.5 | Z_ImportDebtors.php:407 sets nextreviewdate; $FieldHeadings is unchanged, so the new columns cannot be imported |
| B10 | 0.5 | InsertCustomer forces nextreviewdate (api_customers.php:360); ModifyCustomer does not validate the new columns, and holdreason/creditlimit are still open |
| B11 | 1 | Types 51/52/53: systypes.sql, NewSysType (44.php:121), demo.sql |
| B12 | 1 | GetNextTransNo after DB_Txn_Begin in charge, waiver and write-off paths |
| B13 | 0.5 | GetPeriod used (CreditCharges.php:93, CreditControlFunctions.php:368); no ProhibitPostingsBefore check or display |
| B14 | 1 | gllink_debtors gate; AR side to CompanyRecord['debtorsact'] |
| B15 | 0.5 | EnsureGLEntriesBalance before commit (CreditControlFunctions.php:389, CreditCharges.php); the code does not stop on an imbalance |
| B16 | 1 | CCToLocal = amount/rate (CreditControlFunctions.php:255); 51 positive, 52/53 negative |
| B17 | 0 | No InsertGLTags after any gltrans insert (CCGLEntry) |
| B18 | 0 | CreditControlSetup.php:50 checks only that the account exists; a control account is not refused |
| B19 | 1 | Credits 52/53 are allocated at posting through custallocns, alloc and settled (CreditControlFunctions.php:319); type 51 is a normal allocation target |
| B20 | 0.5 | No diffonexch and no salesexchangediffact posting; write-off valued at the items' historic rates, so the difference goes to bad debt (the BRD's wording) |
| B21 | 0.5 | CustomerInquiry shows 51-53 as misc rows; CustomerAccount.php drops them (not changed) |
| B22 | 1 | salesperson from the branch salesman (CreditControlFunctions.php:298) |
| B23 | 1 | UNIQUE onechargepermonth plus a check before posting |
| B24 | 0.5 | Accounts kept in config (CCInterestAct/CCFeeAct/CCBadDebtAct) with their own setup page, not companies columns; no GLAccounts.php delete guard |
| B25 | 0.5 | CCDaysOverdueSQL (CreditControlFunctions.php:215) uses the AgedDebtors rule; PastDueDays1/2 not used |
| B26 | 0.5 | Open items selected with `settled = 0 AND balance > tol` (CreditControlFunctions.php:240, :325), still using settled |
| B27 | 1 | custcontacts.statement=1 with IsEmailAddress, deduplicated (CreditControlFunctions.php:396) |
| B28 | 0.5 | No PDF letters at all: plain-text email and an on-screen HTML letter for posting (no Cpdf either) |
| B29 | 1 | `$Result !== true` counts as failed (DunningRun.php:124); no temp file is involved |
| B30 | 0.5 | Filter on CreditControl.php, CreditControlReport.php and the banner; none on DunningRun, CreditCharges, CreditWriteOff, CreditWriteOffReport or DebtorsReconciliation |
| B31 | 1 | CustomerCreditPortal.php:20-26 uses the session debtor only |
| B32 | 0 | Hard-coded `in_array(21, …)` / `in_array(22, …)` (CreditControlFunctions.php:30, :35); no false-script rows |
| B33 | 1 | All 10 pages: NewScript in 44.php, scripts.sql, demo.sql; no $PageSecurity in the pages |
| B34 | 1 | 44.php: CreateTable with exact names and no ENGINE, AddColumn/AddIndex/InsertRecord/NewConfigValue, guarded one-line UpdateDBNo (:192); the raw UPDATE is guarded by `WHERE nextreviewdate='1000-01-01'` |
| B35 | 1 | Six install/sql/tables files with '1000-01-01' defaults; debtorsmaster, debtortrans and salesorders updated |
| B36 | 1 | Seeds in install/sql/data (config, scripts, menuitems, systypes, securitytokens, securitygroups, creditcontrol, dunningstages; one statement each) and in install/sql/demo.sql |
| B37 | 0.5 | menuitems seeded for roles 1-9 plus NewMenuItem; config via NewConfigValue and seeds, but edited on CreditControlSetup.php, not SystemParameters.php |
| B38 | 1 | Only helpers present in all four UpgradeDB variants; executeSQL comes from Z_UpgradeDatabase.php |
| B39 | 0.5 | Forms are hand-written, without UIGeneralFunctions; no double escaping of POST (log text goes through stripslashes then DB_escape_string) |
| B40 | 0.5 | $Title/$ViewTopic/$BookMark set before header.php everywhere; anchors exist only for AccountsReceivable and CreditControl. The BookMarks CreditCharges, CreditControlReport, CreditControlSetup, CreditWriteOff, CreditWriteOffReport, CustomerCreditPortal, DebtorsReconciliation, DunningRun and DunningStages have no anchor (ManualOutline already lists AccountsReceivable) |

**B = 27.5 / 40**

## Totals

- A 41 / 43, B 27.5 / 40, total 68.5 / 83
- Correctness 4 / 5: the routes, postings, allocation, approval, dunning and portal are coherent and balanced. The gaps: a parallel credit formula that ignores CheckCreditLimits, no ProhibitPostingsBefore handling, no stop after EnsureGLEntriesBalance, charges missing from CustomerAccount.php, and ModifyCustomer left open.
- Conventions 3 / 5: strong install and upgrade discipline (44.php, table files, data seeds, demo.sql, roles 1-9, scripts rows). Against that: hard-coded tokens 21/22, no UIGeneralFunctions, no GL tags, a separate settings page instead of SystemParameters, and missing manual anchors for most BookMarks.

## Regressions

1. EDIProcessOrders.php:914: the `=`→`==` fix means EDI messages with functions 16/31/42/46 and unmatched customers no longer create orders. This changes behaviour for every customer.
2. Over-limit orders are held, and blocked at ConfirmDispatch, even when CheckCreditLimits=0, because CCHoldOverLimitOrders defaults to 1. A company that never checked limits now has orders held.
3. API InvoiceSalesOrder can now set creditheld and return the new error 1175 for over-limit orders. This changes what existing API/POS callers get back.
4. Customers.php: users without token 21 (seeded only for role 8) silently get the stored limit and hold reason, and new customers get DefaultCreditLimit with a normal reason. This is intended by BR-07, but the sales office loses a field it used to set.
5. AgedDebtors.php:312: the credit text is added to $HTML, so the PDF output also gets an extra line under every customer.
