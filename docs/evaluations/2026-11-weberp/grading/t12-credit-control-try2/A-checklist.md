# t12 credit control, try 2: grading of run A (blind)

- Run diff: `scratchpad/blind12b/A.diff` (3541 lines, 49 files)
- Workspace: `scratchpad/blind12b/A/`
- Base: `scratchpad/base/` (4cb937f79e8b)
- Task: `tasks/t12-credit-control/brd.md` (BR-01..BR-43). Checklist: `tasks/t12-credit-control/checklist.md`. Rule details: `grading/t10-credit-control/rules/`.
- Every claim was checked in the code. NOTES.md was read only for the decisions on the BRD's open questions. File:line refers to the workspace.

Scoring: met 1 / partly 0.5 / missed 0.

The run builds the whole BRD on the existing `holdreason` / `holdreasons.dissallowinvoices` (0 normal, 1 stop, 2 watch). It adds reviews, a controlled status change with history, enforcement on order entry, EDI, recurring orders, the API order header and dispatch/invoice, and an optional over-limit hold (CheckCreditLimits = 3). It also adds a dunning run, month-end interest and fees with waivers, write-offs with approval, a worklist, aged-debtors columns, a portal page, a ledger-check column and the manual. The shared logic is in `includes/CreditControlFunctions.php`. Nothing was executed.

## A. The BRD (43)

| id | score | justification |
|---|---|---|
| A1 | 1 | CreditCustomer.php:45-100 writes a `creditreviews` row with the date, user, outcome (confirmed/raised/reduced/watch/stop/normal), old and new limit, notes and next review date (`:80-83`). |
| A2 | 0.5 | A new customer gets `CreditNextReviewDate()` from `CreditReviewMonths`, set in Customers.php:278, api_customers.php:359-362 and Z_ImportDebtors.php:429. There is one period only, so a higher-risk customer cannot get a shorter one. |
| A3 | 1 | The history is shown at CreditCustomer.php:334-352. No code updates or deletes `creditreviews`. Customers.php:357-368 refuses to delete a customer that has credit history. |
| A4 | 1 | CreditCustomer.php:78-97 writes the review, `CreditSetLimit` (the limit UPDATE plus a 'limit' event carrying the review notes) and the next review date in one transaction. |
| A5 | 1 | `CreditSetStatus` (CreditControlFunctions.php:147-174) changes `holdreason` and logs the user, time and reason. A reason is required (CreditCustomer.php:103-122). |
| A6 | 0.5 | New orders for a stopped customer are refused in DeliveryDetails.php:328-349 (sales office and web shop), EDIProcessOrders.php:895-903, RecurringSalesOrdersProcess.php:95-103 and api_salesorders.php:280-288. Dispatch and invoice are blocked unless the order is released (ConfirmDispatch_Invoice.php:111-119,623-630). The API `InvoiceSalesOrder` (api_salesorders.php:799) has no check, so a pre-stop order can still be invoiced through the API. |
| A7 | 0.5 | CreditCustomer.php changes need token 21. Customers.php no longer writes `holdreason` or `creditlimit` for existing customers (`:139-149`). The API `ModifyCustomer` (api_customers.php:390-460) still writes both for any API user. The Z_ImportDebtors.php update path (`:352-369`) still overwrites them. |
| A8 | 1 | A watch customer can still order: SelectOrderItems.php:540 now lets watch (2) through in the portal path. The worklist lists open orders for watch customers (CreditControl.php:133-169). |
| A9 | 0.5 | Status shows in CustomerInquiry.php:173, CreditCustomer.php:170, AgedDebtors.php:286-288,323, on the worklist and at order entry. SelectCustomer.php, the main customer screen for staff, still shows no status. |
| A10 | 0.5 | `CreditOrderCheck` (CreditControlFunctions.php:237-252) holds over-limit orders (`creditholdstate=1`) in DeliveryDetails.php:345-347, EDIProcessOrders.php:903-906, RecurringSalesOrdersProcess.php:166-171 and the API (only when the customer is already over the limit). `CreditOrderBlockReason` blocks dispatch until release. All of this works only with CheckCreditLimits = 3, and the seeded default is still 1 (install/sql/data/config.sql), so out of the box nothing is held. Edited orders are never re-held. |
| A11 | 1 | A portal customer on stop is told the account is on hold and to contact credit control (SelectOrderItems.php:577). CustomerCreditPortal.php:33-35 says the same. |
| A12 | 1 | `dunningstages` has three seeded stages: 30, 45 and 60 days, the third a final notice warning of stop and charges (44.php:189-196). Stages, days and wording can be edited, added and deleted (CreditControlSettings.php:87-121,209-234). |
| A13 | 1 | Emails go to `custcontacts.statement=1` contacts (CreditControlFunctions.php:400-409; CreditReminders.php:55-65). A customer with no email is listed with the letter text, to be posted (`:76-87,128`). |
| A14 | 1 | CreditReminders.php is a run that a user starts. It previews customer, stage, days overdue, amount and delivery, with a tick box per customer (`:93-137`). Only ticked customers are sent (`:34-35`). |
| A15 | 1 | `CreditReminderDue` (CreditControlFunctions.php:363-397) needs a net overdue amount. It skips a stage already sent in the current overdue cycle and enforces `CreditDunningMinDays`. The check is repeated at send time (CreditReminders.php:41). |
| A16 | 1 | Each sent letter writes a `dunninglog` row (date, stage, invoice list, amount, method; CreditReminders.php:67-70) and a 'reminder' event. |
| A17 | 1 | `CreditBuildLetter` (CreditControlFunctions.php:413-429) lists each overdue item with its due date and amount in the customer's currency. |
| A18 | 1 | `debtortrans.disputed` (44.php:16) is set with a reason (CreditCustomer.php:138-152). Disputed items are excluded from overdue items (CreditControlFunctions.php:308), so they are neither chased nor charged. |
| A19 | 1 | Interest is rate × net overdue × days/365, and/or a flat fee (CreditCharges.php:88-95). Rate, fee and days overdue are settings (CreditControlSettings.php:160-186). |
| A20 | 0.5 | One `chargeexempt` flag exempts a customer from both (CreditCustomer.php:124-131; CreditCharges.php:74). A customer cannot be exempted from interest only or from fees only. |
| A21 | 0.5 | Charges are type 51 in the customer's currency, with a descriptive reference and invtext (CreditCharges.php:122-131). Statements and CustomerInquiry show any type by name. CustomerAccount.php:281-382 renders only types 10, 11 and 12, so charges are missing from that account page. |
| A22 | 1 | The charges are previewed with tick boxes and a confirm prompt (CreditCharges.php:144-204). Re-runs skip what is already charged per customer, month and type (`:84-87,119`). A UNIQUE key backs this (44.php:99). |
| A23 | 1 | `CreditInterestAct` and `CreditLateFeeAct` are chosen in the settings (CreditControlSettings.php:182-186) and posted as the credit side (CreditCharges.php:131). Posting is refused while they are unset (`:102-107`). |
| A24 | 1 | A waiver needs a reason (CreditCharges.php:26-62). It posts type 52 to the same GL account at the charge's rate and is allocated to the charge. |
| A25 | 1 | CreditWriteOffs.php:109-152 writes off all or part of the open balance, with a required reason, capped at what is owed. |
| A26 | 1 | A write-off above `CreditWriteOffLimit` (home currency) stays pending (`:139-149`) until a token-22 user approves it (`:83-107`). |
| A27 | 1 | `CreditPostWriteOff` (`:42-79`) posts type 53, debits bad debt and credits debtors control at the invoices' own rates, and allocates oldest-first so the balance falls. NOTES.md states that valuing at the posted rates means no currency difference arises. |
| A28 | 1 | `putonstop` defaults from `CreditStopOnWriteOff` and can be unticked per write-off (`:173-176`). `CreditSetStatus(...'stop')` runs inside the posting transaction (`:70-76`). |
| A29 | 1 | The write-off report covers a chosen period with customer, amount, home amount, reason, requester, approver and status (CreditWriteOffs.php:208-245). |
| A30 | 1 | The worklist lists reviews due or overdue (CreditControl.php:172-199), customers over their limit with the excess in home currency (`:201-235`) and customers on watch or stop (`:237-270`). It filters by rep (forced for a SalesmanLogin, `:44`) and by currency (`:46-54`), and totals in home currency. |
| A31 | 1 | AgedDebtors.php:286-288,323-325 add credit status, credit limit and last reminder stage. |
| A32 | 1 | `creditevents` logs reviews, stop/watch, limit changes, releases, reminders, charges, waivers, write-offs, disputes and notes (`LogCreditEvent`, CreditControlFunctions.php:132-145). It is shown per customer at CreditCustomer.php:354-369. |
| A33 | 1 | `CreditRepCanSee` guards CreditCustomer.php:35, and the worklist forces the rep's own customers (`CreditRepFilterSQL`). Reps see status, limit, balance, overdue and reminders. |
| A34 | 1 | Every change on CreditCustomer.php needs token 21 (`$CanManage`). Customers.php does not write limit or status for existing customers. |
| A35 | 0.5 | CustomerCreditPortal.php shows the logged-in customer's balance, reminders and charges. The customer menu is hard-coded in index.php:73-95 and was not changed. No link reaches the page; it is only on an AR Reports menu row for role 7. |
| A36 | 1 | The portal reads the debtor from `www_users.customerid` (CreditControlFunctions.php:74-78). CustomerInquiry.php:27-33 forces a portal user to their own account, which closes the `?CustomerID=` hole. |
| A37 | 1 | Every charge, waiver and write-off posts the debtortrans row and a balanced debtors-control entry together (`CreditPostTransaction`, CreditControlFunctions.php:451-513). |
| A38 | 1 | Z_CheckDebtorsControl.php:124-137 gives types 51, 52 and 53 their own column in the period reconciliation. |
| A39 | 0.5 | 44.php covers upgrades, and the install tables and data mirror it. On a fresh non-demo install, `install/sql/data/menuitems.sql` now holds two INSERT statements in a file loaded with one query, so the whole file fails. On a demo install, the demo hold reasons have `dissallowinvoices` = -1 (table default) and the demo seed adds no normal, watch or stop reason, so every status change fails with "No credit status of this kind is defined". |
| A40 | 0.5 | Existing customers keep their hold reason, so current stops stay stops. They get a review date (44.php:200) and a go-live history row (`:203-210`). The review date is hard-coded to 12 months, not the Finance setting. The spreadsheet stop list has no load path: NOTES.md points to Z_ImportDebtors, which writes no history. |
| A41 | 1 | Invoices, statements and postings are unchanged for customers who are not overdue. The blocks apply only to stopped customers, and the hold only when CheckCreditLimits = 3. |
| A42 | 1 | ManualAccountsReceivable.html:204-250 covers reviews, stop/watch, the customer page, the worklist, the reminder run, month-end charges, write-offs and the ledger check. |
| A43 | 1 | ManualAccountsReceivable.html:247-248 is a note for sales staff on watch and stop that says whom to contact. |

**A = 38 / 43**

## B. Rules away from the change (40)

| id | score | justification |
|---|---|---|
| B1 | 1 | Stop and watch use `holdreason` → `dissallowinvoices` 1/2 (CreditControlFunctions.php:14-16,83-101,147-174). There is no parallel customer flag. `salesorders.creditholdstate` is an order-level approval state. |
| B2 | 1 | ConfirmDispatch_Invoice.php:111-119 checks when the order is opened and `:623-630` checks again at ProcessInvoice. |
| B3 | 1 | RecurringSalesOrdersProcess.php:95-103 skips stopped customers and leaves the template due. Over-limit orders are held and not auto-invoiced (`:162-171`). |
| B4 | 1 | EDIProcessOrders.php:895-910 creates no order for a stopped customer and logs it in the email and in `creditevents`. |
| B5 | 0.5 | `InsertSalesOrderHeader` refuses a stopped customer with the new error 1174 (api_salesorders.php:280-292). `InvoiceSalesOrder` (`:799`) is not checked. |
| B6 | 0.5 | The order checks reuse `GetCreditAvailable` (CreditControlFunctions.php:248) and follow CheckCreditLimits, extended with option 3. The worklist's over-limit list (CreditControl.php:202-217) and CreditCustomer.php:173 compare `SUM(balance) > creditlimit`, a second formula that leaves out open orders. |
| B7 | 1 | Z_ChangeCustomerCode.php:75-77,109-111 add both new columns to the copied row, and `:215-220` move all five new tables. |
| B8 | 1 | Customers.php:357-368 refuses the delete while any of the five credit tables has rows. |
| B9 | 0.5 | Z_ImportDebtors.php:406,429 fills `nextreviewdate` on insert. The new columns are not appended to `$FieldHeadings`, so they cannot be imported. |
| B10 | 0 | api_customers.php:359-362 only defaults `nextreviewdate` on insert, without validation. `ModifyCustomer` still writes `holdreason`, `creditlimit` and the new columns with no restriction. |
| B11 | 1 | Types 51, 52 and 53 are added through `NewSysType` (44.php:128-130), install/sql/data/systypes.sql, the demo seed and DatabaseTranslations.php:56-58. |
| B12 | 1 | `GetNextTransNo` runs inside `CreditPostTransaction` (CreditControlFunctions.php:455), which is always called after `DB_Txn_Begin` (CreditCharges.php:50,130; CreditWriteOffs.php:57). |
| B13 | 0.5 | `GetPeriod` gives the period for both prd and periodno (CreditControlFunctions.php:457). The posting date is always today. `ProhibitPostingsBefore` is not checked or shown. |
| B14 | 1 | GL rows are written only when `gllink_debtors == 1`, with the AR side on `CompanyRecord['debtorsact']` (`:497-511`). |
| B15 | 0 | There is no `EnsureGLEntriesBalance`. The journal balances only because the debtors line is derived as minus the total (`:507-510`). |
| B16 | 1 | Home = customer amount / rate. Charges are positive; waivers and write-offs are negative. The stored rate is cust/home (`:461`). |
| B17 | 0 | No `InsertGLTags` follows the gltrans inserts. |
| B18 | 0 | The account picker lists every chartmaster account (CreditControlSettings.php:123-130). The debtors control account is accepted as the bad-debt account. |
| B19 | 1 | Write-offs and waivers are allocated at posting through `custallocns` and alloc/settled (`CreditAllocate`, CreditControlFunctions.php:516-525). Charges are positive items that receipts can be allocated to. |
| B20 | 0.5 | No exchange difference goes to `salesexchangediffact`. By design none arises: the write-off is valued at the invoices' own rates (CreditWriteOffs.php:23-40). |
| B21 | 0.5 | CustomerInquiry.php's else-branch (`:604-626`) shows the new types by systypes name. CustomerAccount.php:281-382 was not extended (types 10/11/12 only), so charges, waivers and write-offs are dropped there. |
| B22 | 1 | `debtortrans.salesperson` is set from the customer's branch salesman (CreditControlFunctions.php:463,491). |
| B23 | 1 | Months already charged are skipped (CreditCharges.php:84-87,119), backed by `UNIQUE KEY onechargepermonth` (44.php:99). |
| B24 | 0 | The GL accounts are `config` rows (CreditInterestAct/LateFeeAct/BadDebtAct), not `companies` columns. GetConfig, CompanyPreferences and the GLAccounts delete guard were not changed, so a chosen account can be deleted. |
| B25 | 0.5 | `CreditDueDateSQL` (CreditControlFunctions.php:282-287) matches the AgedDebtors rule (daysbeforedue vs last_day + dayinfollowingmonth). Stage and charge thresholds are their own day counts, not the PastDueDays1/2 bands. |
| B26 | 1 | Open items use `debtortrans.balance` (`:307,324`; CreditWriteOffs.php:25), never `settled`. |
| B27 | 1 | Recipients are `custcontacts.statement = 1`, filtered by IsEmailAddress (CreditControlFunctions.php:400-409). |
| B28 | 0 | No PDF is produced. Letters are plain-text email bodies, and posted letters are shown on screen. |
| B29 | 0.5 | A letter counts as sent only on `=== true` (CreditReminders.php:58-63), and there is no temp file. The recipients go in as a numeric list. In SMTP mode `SendEmailBySmtp` treats the keys as addresses, so the address becomes "0". |
| B30 | 0.5 | CreditControl.php and CreditCustomer.php apply the rep filter. The reminder run, charge preview, waiver list and write-off lists (CreditReminders.php:94-98; CreditCharges.php:72-75,207-223; CreditWriteOffs.php:185-224) have none. |
| B31 | 1 | The portal and CustomerInquiry take the debtor from `www_users.customerid` (CreditControlFunctions.php:74-78; CustomerInquiry.php:27-33). |
| B32 | 0 | Token numbers are hard-coded: `CreditUserHasToken(21)` and `(22)` (CreditControlFunctions.php:23-35). There is no "false script" entry in the scripts table. |
| B33 | 1 | All seven pages are registered in 44.php:141-147, install/sql/data/scripts.sql and the demo seed (install/sql/creditcontrol_demo.sql, loaded after demo.sql at InstallFunctions.php:619-622). No page sets `$PageSecurity`. |
| B34 | 0.5 | The update uses helpers, CreateTable with exact names, and a guarded UpdateDBNo (44.php:212-214). The go-live backfill and history rows are raw `executeSQL` statements (`:200,203-210`): idempotent, but not through helpers. |
| B35 | 1 | install/sql/tables has a file for each of the six new tables, and the new columns are mirrored in debtorsmaster.sql, debtortrans.sql and salesorders.sql. Dates use '1000-01-01'. |
| B36 | 0.5 | Seeds are in install/sql/data/* and in a separate install/sql/creditcontrol_demo.sql, not in install/sql/demo.sql. install/sql/data/menuitems.sql now has two INSERT statements, so its one-query load fails. |
| B37 | 0.5 | `NewMenuItem` is used in 44.php:149-154. The install seeds cover some roles only: the worklist for 1-8, the other pages for 6/8 and the portal for 7. Config goes through NewConfigValue and config.sql, but none of it is in SystemParameters.php; it has a separate settings page. |
| B38 | 1 | Every helper used (AddColumn, AddIndex, CreateTable, NewSysType, NewSecurityToken, InsertRecord, NewScript, NewMenuItem, NewConfigValue) exists in all four UpgradeDB_* files. No AddCalculatedColumn. |
| B39 | 0 | Forms are hand-written HTML, with no UIGeneralFunctions. POST reasons that session.php already escaped are escaped again by `DB_escape_string` in `LogCreditEvent` (CreditControlFunctions.php:138): status, dispute, release, exemption and note reasons. |
| B40 | 0.5 | $Title, $ViewTopic and $BookMark are set before header.php. The anchors are in ManualAccountsReceivable.html, but the pages use ViewTopic ARTransactions, ARInquiries or Setup, whose manual files lack those ids. There is no ManualOutline.php entry. |

**B = 25.5 / 40**

## Totals

- A = 38 / 43, B = 25.5 / 40, total = 63.5 / 83
- Correctness: 3 / 5. The design is complete and mostly coherent. Stop is enforced at order and at dispatch, and re-checked at send and post time. Postings balance at consistent rates, the duplicate-month guard holds, and write-offs and waivers are allocated. Against that stand the defects below: the fresh-install menu failure, the no-op credit fields in Customers.php, SMTP-mode email, the demo hold reasons, the unguarded API invoice path and a hold that is off by default. None of it was run.
- Conventions: 3 / 5. The run reuses holdreasons, GetCreditAvailable, GetNextTransNo/GetPeriod, NewSysType, the update helpers with a guarded UpdateDBNo, install table mirrors and the systypes translations. Against that: hard-coded tokens 21/22, double escaping, no UIGeneralFunctions, no EnsureGLEntriesBalance or GL tags, GL accounts in config rather than companies, a two-statement data file, a side demo file, and help topics that do not match the manual page.

## Regressions and defects

1. Fresh non-demo install: `install/sql/data/menuitems.sql` gains a second `INSERT INTO menuitems` statement. InstallFunctions.php loads each data file with one query, so the whole file fails and a new install gets no menu items at all, not only the credit-control ones.
2. Customers.php:143-147: `$CreditHoldSQL = "" . $CreditHoldSQL . "";` (and the same for the limit) does nothing, so the UPDATE never includes `holdreason` or `creditlimit`, even for token-21 users. Customer maintenance can no longer change either field for anyone, yet the form leaves them editable for credit control and reports "Customer updated".
3. CreditReminders.php:58 passes a numeric address list to `SendEmailFromWebERP`. With SmtpSetting = 1, `SendEmailBySmtp` uses the keys as addresses ("0"), and PHPMailer throws, so the run fails. The default mail() mode handles the list correctly.
4. Demo install: the hold reasons in demo.sql have `dissallowinvoices` = -1, and creditcontrol_demo.sql adds no normal, watch or stop reason, so status changes, write-off stops and review outcomes fail on the demo company.
5. The API `InvoiceSalesOrder` still invoices orders for a stopped customer or held orders.
