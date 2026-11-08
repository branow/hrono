# t12 credit control (try 2): run B, graded against the checklist

The code was graded, not NOTES.md. NOTES.md was used only for the decisions on the open questions. Paths are relative to the workspace `blind12b/B/`. Scores: 1 met, 0.5 partly met, 0 missed.

Cross-cutting facts used below:

- `$_SESSION['CustomerLogin']` is never set. `includes/session.php:364-368` sets only the local `$CustomerLogin`. So the customer-login branches at CustomerCreditHistory.php:13 and includes/CreditControlFunctions.php:30 are dead code.
- All seven new pages set `$ViewTopic = 'AccountsReceivable'` with their own `$BookMark`. doc/Manual/ManualAccountsReceivable.html has only the `AccountsReceivable` anchor. The new ManualCreditControl.html has only `CreditControl`, so no page's bookmark anchor exists.
- install/sql/demo.sql is not touched. A demo install loads only demo.sql for data and records DBUpdateNumber = 44 (InstallFunctions.php:615/635), so a demo site gets the new tables but no scripts, systypes, tokens, menus or config rows.
- The over-limit hold runs whenever `CheckCreditLimits > 0` (DeliveryDetails.php:344, EDIProcessOrders.php:1019, RecurringSalesOrdersProcess.php:213, api_salesorders.php:536). The seed default is 1 (warn), so warn mode now holds orders.

## A. BRD requirements (BR-01..BR-43)

| # | Score | Evidence |
|---|---|---|
| A1 | 1 | CreditReview.php:91 inserts date, user, outcome (confirmed/raised/reduced/watch/stop/normal), old and new limit, notes and next review date. |
| A2 | 1 | New customers get CreditControlDefaultNextReview() from CreditControlReviewMonths: Customers.php:287, api_customers.php:360, Z_ImportDebtors.php:429. Existing customers: 44.php:179. |
| A3 | 1 | creditreviews has no update or delete path. The history is listed at CreditReview.php:225. |
| A4 | 1 | The limit changes inside the review transaction (CreditReview.php:90-104, CreditControlSetLimit at :97). |
| A5 | 1 | Stop and off-stop are review outcomes, and notes are required (CreditReview.php:85). CreditControlSetStatus logs old and new status, user and NOW() (CreditControlFunctions.php:150-171). |
| A6 | 1 | Stop is refused at DeliveryDetails.php:297, EDIProcessOrders.php:897, RecurringSalesOrdersProcess.php:98 and api_salesorders.php:345. Dispatch and invoice are blocked unless released: ConfirmDispatch_Invoice.php:48/779 and api_salesorders.php:822. Release is at CreditControlReport.php:14. (CounterSales.php still only warns.) |
| A7 | 0.5 | Customers.php:144 keeps the stored status and limit for users without token 17. But API ModifyCustomer still writes holdreason and creditlimit, Z_ImportDebtors sets both, and CreditStatus.php (token 3) can still change the meaning of every hold code except 90/91 (CreditStatus.php:65). |
| A8 | 1 | The existing watch warning is at SelectOrderItems.php:440. Watched orders from the last 60 days are listed at CreditControlReport.php:143-160. |
| A9 | 0.5 | Status shows in the SelectCustomer.php:154 banner, CreditReview, AgedDebtors.php:325 and order entry. But CustomerInquiry.php:169 and CustomerAccount.php:232 still print "ACCOUNT ON HOLD" for a watched customer. |
| A10 | 0.5 | New orders over the limit are held (DeliveryDetails.php:344), and EDI, recurring and API orders are held too. Release is at CreditControlReport.php:14. A modified order (DeliveryDetails.php:620 branch) is never re-checked, so raising an existing order over the limit goes through. |
| A11 | 1 | The API returns error 1174 "This customer account is on hold. Please contact us" (api_errorcodes.php:189, api_salesorders.php:346). DeliveryDetails.php:298 shows the same message. |
| A12 | 1 | The number of stages, days, subject and wording are set in CreditControlSetup.php:62-96. Three stages are seeded (44.php:144). |
| A13 | 1 | Email goes to the statement contact (DunningRun.php:83). Customers with no email are flagged in the preview and their letters are shown for posting (DunningRun.php:146). |
| A14 | 1 | The run is started by credit control. It shows a preview with untickable rows (DunningRun.php:158-180) and sends only ticked customers (:109). |
| A15 | 1 | The stage moves one step at a time, only on overdue undisputed items, and only within the current overdue episode (DunningRun.php:28-70, CreditControlLastStage). A gap check stops repeat letters (:70). |
| A16 | 1 | dunninglog records date, stage, method, amount, currency and invoices (DunningRun.php:131). |
| A17 | 1 | The letter carries the customer currency and lists the overdue invoices (DunningRun.php:95-100 and :114). |
| A18 | 1 | debtortrans.disputed is set at CreditReview.php:127. CreditControlOverdueItems drops disputed items (CreditControlFunctions.php:218), so they are not chased or charged. |
| A19 | 1 | Interest, fee or both, with rate, fee and charge days set in CreditControlSetup.php (:13 params). |
| A20 | 1 | nointerest and nofees are set with a reason at CreditReview.php:111. They are honoured at CreditCharges.php:68-74. |
| A21 | 0.5 | Type 70 is raised in the customer currency, and statements (by typename) and CustomerInquiry (misc row) show it. CustomerAccount.php:281-363 still drops types 70/71/72. |
| A22 | 1 | Preview, untick and confirm (CreditCharges.php:141-155, :97). Per-month guard at :75 plus UNIQUE (debtorno, chargemonth, chargetype). |
| A23 | 1 | Income accounts come from CreditControlInterestAct and FeeAct (CreditControlFunctions.php:344, :349-351). |
| A24 | 1 | A waiver needs a reason. It posts type 71, allocates to the charge and reverses the GL (CreditControlFunctions.php:372-391, CreditCharges.php:27). |
| A25 | 1 | CreditWriteOffs.php writes off part or all of the balance with a required reason. |
| A26 | 1 | A write-off whose home amount is above CreditControlWriteOffLimit waits (CreditWriteOffs.php:81). Approval needs token 21 (:92). |
| A27 | 1 | Type 72 credit, allocated oldest first. GL credit to debtors at original rates, debit to bad debt, difference to salesexchangediffact (CreditControlFunctions.php:397-435). |
| A28 | 1 | The "put on stop" checkbox defaults on from config (CreditWriteOffs.php:119). The stop is applied on posting (:28). |
| A29 | 1 | The write-off report by period shows customer, amount, reason, requested by and approved by (CreditWriteOffs.php:151-161). |
| A30 | 1 | CreditControlReport.php lists reviews due (:96), over limit by how much (:99), and watch/stop (:102). It filters by rep (:26) and currency (:80) and totals in home currency (:118). |
| A31 | 1 | AgedDebtors.php:286-288 and :323-325 add status, limit and last reminder. |
| A32 | 1 | creditcontrollog records reviews, status, limit, reminders, charges, waivers, write-offs, disputes and exemptions. It is shown at CreditReview.php:237. |
| A33 | 1 | CreditControlCanSeeCustomer limits reps to their own customers (CreditControlFunctions.php:34-39, used at CreditReview.php:36 and CustomerCreditHistory.php:29). The report forces the rep filter (CreditControlReport.php:26). |
| A34 | 1 | Edit forms and actions need CanDoCreditControl (CreditReview.php:44). Reps see the page read-only. |
| A35 | 0.5 | CustomerCreditHistory.php (token 1) shows balance, reminders and charges. The customer portal menu is hard-coded in index.php and does not link it, so a customer reaches the page only by typing the URL. |
| A36 | 0 | The own-account check reads the never-set `$_SESSION['CustomerLogin']` (CustomerCreditHistory.php:13). A customer login can pass ?DebtorNo= (:15) and CreditControlCanSeeCustomer returns true. |
| A37 | 1 | Charges, waivers and write-offs each post balanced GL to debtorsact under gllink_debtors (CreditControlFunctions.php:348, :383, :428). |
| A38 | 1 | Z_CheckDebtorsControl.php is rewritten on gltotals (:116), split by kind. It also lists entries that differ (:138) and GL postings to debtors with no customer entry. |
| A39 | 1 | Upgrade 44.php and install/sql/tables plus data seeds cover live and new (non-demo) sites. (Demo installs are broken; see regressions.) |
| A40 | 1 | All customers stay "normal" and get a review date (44.php:179). The CSV load of status, limit and date logs each change (CreditControlSetup.php:105-128). |
| A41 | 1 | Customers who are not overdue keep the same invoices, statements and postings. (The EDI `=` to `==` fix and the warn-mode hold are behaviour changes; see regressions.) |
| A42 | 1 | doc/Manual/ManualCreditControl.html covers reviews, stop and watch, the run, charges, write-offs and the report. Outline entry added. |
| A43 | 1 | "Note for sales staff" section in ManualCreditControl.html. |

**A = 39.5 / 43**

## B. Rules away from the change

| # | Score | Evidence |
|---|---|---|
| B1 | 1 | Status = holdreason → dissallowinvoices 1 or 2 (CreditControlFunctions.php:71-86, 44.php:116). salesorders.creditheld is an order hold, not a customer flag. |
| B2 | 1 | ConfirmDispatch_Invoice.php:48 and :779. |
| B3 | 1 | RecurringSalesOrdersProcess.php:98 (stop) and :213-215 (over-limit hold, no auto-invoice). |
| B4 | 1 | EDIProcessOrders.php:897 (stop) and :1019 (hold). |
| B5 | 1 | api_salesorders.php:345 (header), :544 (line hold) and :822 (InvoiceSalesOrder refuses). |
| B6 | 0.5 | Reuses GetCreditAvailable (DeliveryDetails.php:345, etc.) and skips when CheckCreditLimits = 0. But 1 (warn) and 2 (prohibit) are treated the same: both hold. |
| B7 | 1 | Z_ChangeCustomerCode.php:75-78/110-113 (new columns) and :193 (the five new tables). |
| B8 | 0 | The Customers.php delete guard is unchanged (delete at :371). The new debtorno tables neither block the delete nor are deleted. |
| B9 | 0.5 | Z_ImportDebtors.php:429 stamps nextreviewdate, but $FieldHeadings (:37) is not extended and nointerest/nofees are not carried. |
| B10 | 0 | InsertCustomer only stamps nextreviewdate (api_customers.php:360). ModifyCustomer still writes holdreason, creditlimit and the new columns unvalidated. |
| B11 | 1 | NewSysType 70/71/72 (44.php:110-112) and install/sql/data/creditcontrol_systypes.sql. |
| B12 | 1 | GetNextTransNo in CreditControlInsertDebtorTrans (CreditControlFunctions.php:279). It is always called inside the caller's DB_Txn_Begin. |
| B13 | 0.5 | GetPeriod is used (CreditControlFunctions.php:345/374/412), but ProhibitPostingsBefore is neither checked nor shown. |
| B14 | 1 | gllink_debtors == 1 gate. The AR side goes to CompanyRecord['debtorsact'] (:348-351, :383-386, :428-433). |
| B15 | 0.5 | EnsureGLEntriesBalance is called before commit (CreditCharges.php:35/122, CreditWriteOffs.php:23). On imbalance the code still commits and reports success. |
| B16 | 1 | GL = amount / rate. Charges post positive. Waivers and write-offs post negative ovamount (:347, :381, :414). |
| B17 | 0 | InsertGLTags is never called. |
| B18 | 0 | The bad-debt and income accounts are only checked to exist in chartmaster (CreditControlSetup.php:42-50). A control account is not refused. |
| B19 | 0.5 | Waivers and write-offs allocate themselves at posting (CreditControlAllocate :320), and receipts can allocate to type 70 (all unsettled debits). Types 71/72 are not in the 11/12 lists (CustomerAllocations.php:481/538), and no diffonexch is recorded. |
| B20 | 1 | Write-off exchange difference goes to salesexchangediffact (CreditControlFunctions.php:433). |
| B21 | 0.5 | CustomerInquiry shows the new types only as misc rows (CustomerInquiry.php:597 else branch). CustomerAccount.php:281-363 drops them. |
| B22 | 1 | debtortrans.salesperson comes from the first branch's salesman (CreditControlFunctions.php:282, :299). |
| B23 | 1 | UNIQUE onechargepermonth (install/sql/tables/creditcharges.sql) plus the pre-check at CreditControlFunctions.php:332-338. |
| B24 | 0.5 | The GL accounts are config values, not companies columns. That avoids the GetConfig and positional-INSERT hazards, but there is no CompanyPreferences entry and no GLAccounts.php delete guard. |
| B25 | 0.5 | CreditControlDueDateSQL matches AgedDebtors (CreditControlFunctions.php:194-199). Reminder bands are stage days, and PastDueDays1/2 are not used. |
| B26 | 1 | Open items use `balance > 0.005` throughout (CreditControlFunctions.php:217, DunningRun.php:33, CreditCharges.php:53). Never settled. |
| B27 | 0.5 | custcontacts.statement = 1 first (DunningRun.php:84), but it falls back to custbranch.email (:88). LIMIT 1 contact, no IsEmailAddress. |
| B28 | 0.5 | No PDF. Letters are plain-text email, and posted letters are on-screen HTML (DunningRun.php:146-151). |
| B29 | 1 | `$Mailed !== true` means not recorded, so the letter is retried (DunningRun.php:118-121). No attachment, so no temp file. |
| B30 | 0.5 | Filtered in CreditControlReport.php:26/161, CreditReview and CustomerCreditHistory. Not filtered in DunningRun, CreditCharges or CreditWriteOffs lists. |
| B31 | 0 | Dead `$_SESSION['CustomerLogin']` check (CustomerCreditHistory.php:13, CreditControlFunctions.php:30). A customer can open any debtorno. |
| B32 | 0 | Hard-coded tokens: `define('CREDIT_CONTROL_TOKEN', 17)` and `define('CREDIT_APPROVAL_TOKEN', 21)` used with in_array (CreditControlFunctions.php:16-25). No false-script entry. |
| B33 | 0.5 | NewScript for all 7 pages (44.php:162-168) and install/sql/data/creditcontrol_scripts.sql. Missing from install/sql/demo.sql. No $PageSecurity in pages. |
| B34 | 1 | AddColumn, CreateTable (exact names), NewSysType, InsertRecord, NewConfigValue, NewScript and NewMenuItem. Guarded one-line UpdateDBNo at 44.php:181-182. (The CreateTable SQL repeats ENGINE/CHARSET, which the helper appends again.) |
| B35 | 1 | install/sql/tables creditreviews, creditcontrollog, dunningstages, dunninglog, creditcharges and creditwriteoffs. Dates default '1000-01-01'. |
| B36 | 0.5 | Seeds are one statement per new install/sql/data/creditcontrol_*.sql file. None are in install/sql/demo.sql. |
| B37 | 0.5 | Menu rows for roles 1-9 (creditcontrol_menuitems.sql) plus NewMenuItem (44.php:170-175). Config uses NewConfigValue plus a data seed, not demo.sql. Settings are on CreditControlSetup.php, not SystemParameters.php. |
| B38 | 1 | Only helpers present in all four UpgradeDB_* variants (plus executeSQL). No AddCalculatedColumn. |
| B39 | 0 | No UIGeneralFunctions. Already-escaped POST is escaped again, e.g. DB_escape_string($Notes) (CreditReview.php:94), Reason in CreditWriteOffs.php:75 and every CreditControlLog reason. |
| B40 | 0.5 | $Title, $ViewTopic and $BookMark are set before header.php on all pages. There is a manual page and a ManualOutline entry. But every BookMark (CreditReview, DunningRun, CreditCharges, CreditWriteOffs, CreditControlReport, CreditControlSetup, CustomerCreditHistory) points into ManualAccountsReceivable.html, which has none of those anchors. |

**B = 25.5 / 40**

## Totals

- A: 39.5 / 43
- B: 25.5 / 40
- Total: 65 / 83
- Correctness: 3 / 5. The design is broad and coherent: stop enforced on every named route and at dispatch, balanced ledger postings with currency difference, a sound reminder episode, a working reconciliation. Against it: a customer-login privacy leak, demo installs left without scripts and systypes, a GL imbalance that still commits, double-escaped text, modified orders bypassing the over-limit hold, and warn-mode sites now holding orders. Nothing was run.
- Conventions: 2.5 / 5. 44.php, install tables, data seeds, NewSysType, scripts and menus follow project practice. Against that: demo.sql not mirrored, hard-coded token numbers, no UIGeneralFunctions, double escaping, no InsertGLTags, settings outside SystemParameters/CompanyPreferences, and help bookmarks with no anchors on every new page.

## Regressions

1. Privacy: CustomerCreditHistory.php is token 1 and trusts ?DebtorNo= because the customer-login check is dead (CustomerCreditHistory.php:13-15). A customer login can read any customer's balance, reminders and charges.
2. Help is broken on all seven new pages. manual.js looks for the bookmark anchors in ManualAccountsReceivable.html, and none exist there.
3. Demo installs: demo.sql has no rows for the new scripts, systypes 70-72, tokens 17/21, menus or config. DBUpdateNumber is written as 44, so update 44 never runs. Pages are denied, and any posting fails the systypes FK. NOTES.md wrongly says update 44 runs on first login.
4. Warn mode: the seed default is CheckCreditLimits = 1, and the new code holds orders whenever it is > 0. Sites that only warned now get over-limit orders held, and those orders cannot be dispatched or invoiced (including API InvoiceSalesOrder) until released.
5. EDIProcessOrders.php:900: `if ($CreateOrder = true)` was changed to `==`. EDI orders with parse errors, which used to be created, are now dropped.
6. EnsureGLEntriesBalance rolls back silently on an imbalance. CreditCharges, the waiver and CreditWriteOffs then call DB_Txn_Commit and report success, and later writes autocommit.
7. Notes and reasons are stored double-escaped (backslashes before quotes) and are HTML-encoded twice on display.
8. CustomerAccount.php silently drops types 70/71/72 while its balance includes them.
9. Deleting a customer with no transactions leaves orphaned creditreviews, creditcontrollog and dunninglog rows.
10. CreditCharges' month is a free yyyy-mm label charged on today's balances. The per-month guard is per label, so the same overdue balance can be charged again under a different month label.
