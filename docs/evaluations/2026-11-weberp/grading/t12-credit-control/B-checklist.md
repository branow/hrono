# t12 credit control: run B, graded against the checklist

The code was graded, not NOTES.md. NOTES.md was used only for the decisions on the open questions. Paths are relative to the workspace `blind12/B/`. Scores: 1 met, 0.5 partly met, 0 missed.

Cross-cutting fact used below: `$_SESSION['CustomerLogin']` is never set anywhere. `includes/session.php:364-368` sets only the local `$CustomerLogin`. So every new customer-login branch is dead code (CustomerCredit.php:17, CustomerInquiry.php:166/171, SelectOrderItems.php:545, DeliveryDetails.php:342, includes/CreditControlFunctions.php:148).

## A. BRD requirements (BR-01..BR-43)

| # | Score | Evidence |
|---|---|---|
| A1 | 1 | CustomerCredit.php:107 inserts into creditreviews: date, user, outcome (confirmed/raised/reduced/watch/stop), old and new limit, notes, next review. |
| A2 | 1 | New customers get CreditNextReviewDate() from CreditReviewMonths: Customers.php:297, api_customers.php:360, Z_ImportDebtors.php (nextreviewdate on insert). Existing customers: 44.php:194. |
| A3 | 1 | creditreviews is insert-only. No edit or delete path exists. Listed at CustomerCredit.php (Credit Reviews table). |
| A4 | 1 | The limit is updated in the same transaction as the review: CustomerCredit.php:107-119 (DB_Txn_Begin..Commit). |
| A5 | 1 | CreditSetStatus logs old and new status, user and time (includes/CreditControlFunctions.php:116). A reason is required (CustomerCredit.php ChangeStatus). |
| A6 | 1 | Stop is enforced in DeliveryDetails.php:332 (sales office and web shop), EDIProcessOrders.php:899, RecurringSalesOrdersProcess.php:94, api_salesorders.php:358. Dispatch and invoice are blocked unless released: ConfirmDispatch_Invoice.php:608, api_salesorders.php:814. Release is in CreditHeldOrders.php:27. (CounterSales.php still only warns. It is not a named route.) |
| A7 | 0.5 | Customers.php:27/144 ignores limit and status changes without token 21. But CreditStatus.php (token 3) can still change what a hold code means (CreditStatus.php:70). API ModifyCustomer leaves holdreason and creditlimit open. Z_ImportDebtors sets them too. |
| A8 | 1 | Staff get a watch warning at order entry (SelectOrderItems.php:440 path). Watched orders are listed at CreditHeldOrders.php:78. (The same warning also reaches customers, see A35.) |
| A9 | 0.5 | The status shows in SelectCustomer.php:153 (banner), CustomerInquiry.php:173, CustomerCredit and AgedDebtors. But CustomerAccount.php:232 and CustomerReceipt.php:1064 still print "ACCOUNT ON HOLD" for a watched customer. |
| A10 | 1 | CreditHoldOrderIfOverLimit (includes/CreditControlFunctions.php:202) is called at DeliveryDetails.php:565/777, EDI:1022, Recurring:216 and API:536. Release is in CreditHeldOrders.php:76. Dispatch is blocked while held. |
| A11 | 1 | The web-shop path shows "your account has been put on hold ... contact" (SelectOrderItems.php customer branch). DeliveryDetails.php:332 refuses at save. |
| A12 | 1 | DunningStages.php:25/50 sets the number of stages, the days and the wording. Three default stages are seeded (44.php InsertRecord dunningstages; install data/dunningstages.sql). |
| A13 | 1 | Recipients are custcontacts statement=1 (CreditControlFunctions.php:256-259). Customers with no email are listed for posting (DunningRun.php:229 and the "letters to post" block). |
| A14 | 1 | The run is started manually with a preview and untick-to-exclude (DunningRun.php:218). |
| A15 | 1 | Eligibility is recomputed at send (DunningRun.php:37/90). Stages go up by one per letter, within an episode (DunningRun.php:73). There is a minimum gap of DunningMinDaysBetween days (DunningRun.php:34). |
| A16 | 1 | dunningletters stores the date, stage, invoices and amount (DunningRun.php:150). The send is also logged to creditlog. |
| A17 | 1 | The amount is in the customer currency and the overdue invoices are listed in the letter (DunningRun.php:100 DunningInvoiceText, {invoices}). |
| A18 | 1 | debtortrans.disputed is set in CustomerCredit.php:170. It is excluded from chasing (DunningRun.php:198) and from interest (CreditCharges.php:78). |
| A19 | 1 | Interest, fee or both are supported. Rate, fee and minimum days come from settings (CreditCharges.php:59; CreditControlSettings.php). |
| A20 | 1 | debtorsmaster.nointerest/nofees are set with a reason (CustomerCredit.php:144) and honoured in CreditCharges.php. |
| A21 | 1 | Type 45 is in the customer currency with invtext. It appears on statements (PrintCustStatements selects all types) and as a misc row in CustomerInquiry. |
| A22 | 1 | Preview then "Confirm and Post" (CreditCharges.php:235). Double charging is blocked by the unique key plus FOR UPDATE (CreditCharges.php:176). |
| A23 | 1 | Income accounts are chosen in settings (InterestIncomeAct/LateFeeIncomeAct) and posted at CreditControlFunctions.php:325-345. |
| A24 | 1 | A waiver needs a reason, posts type 46 to the GL and is allocated to the charge (CreditCharges.php:118/143). |
| A25 | 1 | Full or partial write-off with a required reason (BadDebtWriteOff.php:104). |
| A26 | 1 | Above WriteOffApprovalLimit the write-off stays Pending until a token 22 user approves it (BadDebtWriteOff.php:21/58). |
| A27 | 1 | CreditPostWriteOff (CreditControlFunctions.php:395) posts the credit to the customer and to BadDebtAct, allocates it and posts the exchange difference to salesexchangediffact (:377-385). |
| A28 | 1 | The StopCustomer checkbox defaults on; BadDebtPost puts the customer on stop (BadDebtWriteOff.php:26-47). |
| A29 | 1 | CreditWriteOffReport.php:28 shows period, customer, amount, reason, requested by and approved by. |
| A30 | 1 | CreditControlReport.php lists review due (:83), over limit by how much, and watch/stop. It filters by rep (:22) and currency (:52) and totals in home currency. |
| A31 | 1 | AgedDebtors.php:286/316 shows credit limit, status and last reminder stage. |
| A32 | 1 | creditlog records reviews, status, limit, reminders, charges, waivers and write-offs (CreditControlFunctions.php:85). It is shown at CustomerCredit.php:376. |
| A33 | 1 | Reps are limited by CreditUserMaySee via custbranch.salesman (CreditControlFunctions.php:147, CustomerCredit.php:54) and in CreditControlReport.php:22. |
| A34 | 1 | Actions need token 21 (CanAct). The Customers.php fields are read-only for reps and their posted values are ignored. |
| A35 | 0.5 | Reminders, charges and balance can be seen (CustomerCredit.php:319/337). But the customer-login mode never triggers. A customer sees the staff view: status (watch included), limit, review notes and internal history. That contradicts the stated decision on Q10 (CustomerInquiry.php:173 also shows "ACCOUNT ON WATCH"). |
| A36 | 0 | CustomerCredit.php is token 1 and takes ?DebtorNo=. Because `$_SESSION['CustomerLogin']` is never set, CreditUserMaySee returns true and a customer login can open any customer's credit file (CustomerCredit.php:17/54). |
| A37 | 1 | Every posting debits or credits debtorsact against the contra account, with the exchange difference on allocation (CreditControlFunctions.php:325-345/377). |
| A38 | 1 | CreditReconciliation.php:33/67/84 shows customer balances vs gltotals plus the two lists of unmatched items. |
| A39 | 1 | sql/updates/44.php for upgrades. install tables, data and demo for fresh installs. |
| A40 | 0.5 | Existing customers get a review date (44.php:194; 12 months hard-coded, not CreditReviewMonths). Old -1 values are normalised (44.php:168). There is no way to load the spreadsheet stop list in bulk; it is one customer at a time. |
| A41 | 1 | Invoices, statements and postings are unchanged for non-overdue customers. |
| A42 | 1 | doc/Manual/ManualAccountsReceivable.html:204 onward covers reviews, stop and watch, the run, charges, write-offs and reports. |
| A43 | 1 | ManualAccountsReceivable.html:251 has the "For sales staff" note (watch and stop meaning, contact credit control). |

**A = 40 / 43**

## B. Rules away from the change

| # | Score | Evidence |
|---|---|---|
| B1 | 1 | Status = holdreason → dissallowinvoices 1 or 2 (CreditControlFunctions.php:34). CreditStatus.php:222 can now set 2. No parallel flag. |
| B2 | 1 | ConfirmDispatch_Invoice.php:608 blocks a stopped customer or a held order. |
| B3 | 1 | RecurringSalesOrdersProcess.php:94 (stop) and :216 (over-limit hold, no auto-invoice). |
| B4 | 1 | EDIProcessOrders.php:899 (stop) and :1022 (hold). |
| B5 | 1 | api_salesorders.php:358 (header), :536 (lines hold), :814 (InvoiceSalesOrder refuses). |
| B6 | 0.5 | Reuses GetCreditAvailable (CreditControlFunctions.php:220). The hold runs on its own CreditHoldOverLimit setting (:203) and ignores CheckCreditLimits 0/1/2. |
| B7 | 1 | Z_ChangeCustomerCode.php:76 (new columns) and :208 (the five new tables). |
| B8 | 0 | The Customers.php delete guard is unchanged. creditlog, creditreviews and the other new tables neither block the delete nor are deleted with it. |
| B9 | 0.5 | Z_ImportDebtors sets nextreviewdate on insert, but $FieldHeadings (Z_ImportDebtors.php:37) is not extended. nointerest and nofees are not carried. |
| B10 | 0 | InsertCustomer only stamps nextreviewdate (api_customers.php:360). ModifyCustomer still lets holdreason, creditlimit and the new columns be written unvalidated. |
| B11 | 1 | NewSysType 45/46/47 (44.php:120), install data/systypes.sql, demo.sql:532. |
| B12 | 1 | GetNextTransNo inside the caller's transaction (CreditControlFunctions.php:293). |
| B13 | 0.5 | GetPeriod is used (:292), but ProhibitPostingsBefore is neither checked nor shown. |
| B14 | 1 | gllink_debtors==1 gate, AR side to CompanyRecord['debtorsact'] (:325-336). |
| B15 | 0.5 | EnsureGLEntriesBalance is called before commit (BadDebtWriteOff.php:52, CreditCharges.php). The code does not stop on an imbalance: DB_Txn_Commit follows unconditionally. |
| B16 | 1 | GL = amount / rate (:326). Charges positive; waivers and write-offs negative. |
| B17 | 0 | InsertGLTags is never called after the gltrans inserts. |
| B18 | 0 | BadDebtAct is only checked to exist in chartmaster (CreditControlSettings.php:58). A control account is not refused. |
| B19 | 0.5 | Write-offs and waivers allocate themselves at posting (CreditAllocate :352). Types 46/47 are not added to the hard-coded 11/12 lists in CustomerAllocations.php:481. |
| B20 | 1 | Exchange difference to salesexchangediffact and debtorsact (CreditControlFunctions.php:377-390). |
| B21 | 0.5 | CustomerInquiry shows the new types only as generic misc rows (CustomerInquiry.php:601 else). CustomerAccount.php:281-363 still drops types 45/46/47. |
| B22 | 1 | debtortrans.salesperson comes from custbranch.salesman (:308). |
| B23 | 1 | UNIQUE (debtorno, chargemonth, kind) plus a FOR UPDATE check (creditcharges.sql; CreditCharges.php:176). |
| B24 | 0.5 | The GL accounts are kept as config values, not companies columns. That avoids the GetConfig and positional-INSERT hazards, but there is no GLAccounts.php delete guard and no CompanyPreferences entry. |
| B25 | 0.5 | CreditDueDateSQL matches AgedDebtors (CreditControlFunctions.php:26). Reminder bands are stage days; PastDueDays1/2 are not used. |
| B26 | 0.5 | Open items use `settled = 0 AND balance > 0` (CreditControlFunctions.php:249/411, CreditCharges, DunningRun). They still depend on settled. |
| B27 | 1 | custcontacts.statement=1 with IsEmailAddress (CreditControlFunctions.php:256-262). |
| B28 | 0.5 | No PDF is produced. Letters are plain-text email, and posted letters are an on-screen HTML page, so no Dompdf letter exists. |
| B29 | 1 | `SendEmailFromWebERP(...) !== true` means not sent and not recorded (DunningRun.php:137-140). There is no attachment, so no temp file. |
| B30 | 0.5 | Filtered in CreditControlReport.php:22 and CustomerCredit (CreditUserMaySee). Not filtered in DunningRun, CreditHeldOrders, CreditWriteOffReport, CreditReconciliation or BadDebtWriteOff lists. |
| B31 | 0 | The customer-login check reads the never-set `$_SESSION['CustomerLogin']` (CustomerCredit.php:17, CreditControlFunctions.php:148). A customer can open any debtorno. |
| B32 | 0 | The permissions are hard-coded tokens: `define('CREDIT_CONTROL_TOKEN', 21)` and `in_array($Token, AllowedPageSecurityTokens)` (CreditControlFunctions.php:13/21). There is no false-script entry. |
| B33 | 1 | All 10 pages are in 44.php:131-140, install data/scripts.sql and demo.sql. No page sets $PageSecurity. |
| B34 | 1 | 44.php uses AddColumn, CreateTable (exact names), NewSysType, NewScript, NewMenuItem, NewConfigValue and InsertRecord. Guarded one-line UpdateDBNo at 44.php:198-199. |
| B35 | 1 | install/sql/tables/creditlog, creditreviews, dunningstages, dunningletters, creditcharges and writeoffs .sql. Dates default '1000-01-01'. No zero dates. |
| B36 | 1 | Seeds are in data/*.sql (one statement each: config, scripts, menuitems, systypes, securitytokens, securitygroups, holdreasons, dunningstages) and in install/sql/demo.sql:521-560. |
| B37 | 0.5 | Menu rows for roles 1-9 (menuitems.sql) plus NewMenuItem. Config uses NewConfigValue and both seeds, but the settings are on a separate CreditControlSettings.php page, not in SystemParameters.php. |
| B38 | 1 | Only helpers present in all four UpgradeDB_* variants (plus executeSQL from Z_UpgradeDatabase). No AddCalculatedColumn. |
| B39 | 0 | No UIGeneralFunctions. Already-escaped POST is escaped again, e.g. DB_escape_string($_POST['Notes']) (CustomerCredit.php:107), Reason in BadDebtWriteOff.php:104, CreditLogEvent notes. |
| B40 | 0.5 | $Title, $ViewTopic and $BookMark are set before header.php on every page. The manual has anchors for CreditControl, CustomerCredit, DunningRun, CreditCharges, BadDebtWriteOff and CreditControlReport. The bookmarks CreditHeldOrders, CreditReconciliation, CreditWriteOffReport, CreditControlSettings and DunningStages have no anchor. |

**B = 26.5 / 40**

## Totals

- A: 40 / 43
- B: 26.5 / 40
- Total: 66.5 / 83
- Correctness: 3 / 5. The feature is broad and coherent: stop and hold on every named route, a balanced ledger, a sound reminder episode. But customer-login detection is broken everywhere, which leaks other customers' credit files and shows watch to customers. There is no stop on a GL imbalance, and POST text is double-escaped. Nothing was run.
- Conventions: 3 / 5. Upgrade and install mirroring, scripts, menus, systypes and tokens follow project practice. Against that: hard-coded token numbers, no UIGeneralFunctions, double escaping, no InsertGLTags, settings outside SystemParameters, and five help bookmarks with no anchor.

## Regressions

1. Privacy: CustomerCredit.php is token 1 and trusts ?DebtorNo=. A customer login (role 7) can read any customer's limit, status, review notes and internal credit history (CustomerCredit.php:17/54; CreditControlFunctions.php:148).
2. Customers now see the watch status ("ACCOUNT ON WATCH", CustomerInquiry.php:173; the watch warning at SelectOrderItems.php:545). Undefined-index warnings come from `$_SESSION['CustomerLogin']` at SelectOrderItems.php:545 and DeliveryDetails.php:342.
3. On upgrade, CreditHoldOverLimit defaults to 1 and ignores CheckCreditLimits. Every order for a customer at or over the limit is now held and cannot be dispatched or invoiced, including API InvoiceSalesOrder, even on sites that set CheckCreditLimits = 0.
4. Stored notes and reasons are double-escaped (backslashes appear before quotes).
5. After a silent rollback by EnsureGLEntriesBalance, the code still commits and logs success. Later writes autocommit.
6. The help link breaks (manual.js throws) on CreditHeldOrders, CreditReconciliation, CreditWriteOffReport, CreditControlSettings and DunningStages.
7. Behaviour change: demo hold reasons 1, 2, 4, 5, 7 and 8 now block invoicing. Demo customers on those codes are on stop.
