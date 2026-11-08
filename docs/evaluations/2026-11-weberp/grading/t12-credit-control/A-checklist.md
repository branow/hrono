# t12 credit control: grading of run A (blind)

- Run diff: `scratchpad/blind12/A.diff` (3541 lines, 49 files)
- Workspace: `scratchpad/blind12/A/`
- Base: `scratchpad/base/` (4cb937f79e8b)
- Task: `tasks/t12-credit-control/brd.md` (BR-01..BR-43). Checklist: `tasks/t12-credit-control/checklist.md`. Rule details: `grading/t10-credit-control/rules/`.
- All claims were checked in the code, not in the run's NOTES.md. NOTES.md was read only for the decisions on the BRD's open questions. File:line refers to the workspace.

Scoring: met 1 / partly 0.5 / missed 0.

The run built the whole BRD: reviews, stop/watch on holdreason, enforcement on order entry, EDI, recurring orders, the API header and dispatch/invoice, an optional over-limit hold (CheckCreditLimits = 3), a dunning run, month-end interest and fees with waivers, write-offs with approval, a worklist, aged-debtors columns, a portal page, a ledger check and the manual. Shared logic is in `includes/CreditControlFunctions.php`. Nothing was executed.

## A. The BRD (43)

| id | score | justification |
|---|---|---|
| A1 | 1 | `CreditCustomer.php:45-100` inserts into `creditreviews` the date (NOW()), user, outcome (confirmed/raised/reduced/watch/stop/normal), old and new limit, notes and next review date (`:80-83`). |
| A2 | 0.5 | New customers get `CreditNextReviewDate()` from `CreditReviewMonths` (`Customers.php:278`, `api_customers.php:359-361`, `Z_ImportDebtors.php:429`), set in `CreditControlSettings.php:148-149`. There is only one period; nothing gives higher-risk customers a shorter one. |
| A3 | 1 | Review history shown at `CreditCustomer.php:334-352`. No code updates or deletes `creditreviews`, and `Customers.php:359-367` refuses to delete a customer with credit history. |
| A4 | 1 | `CreditCustomer.php:78-97`: the review row, `CreditSetLimit` (limit UPDATE plus a 'limit' event with the review notes) and the next-review date are written in one transaction. |
| A5 | 1 | `CreditSetStatus` (`CreditControlFunctions.php:147-174`) changes holdreason and logs user, time and reason. A reason is required (`CreditCustomer.php:103-122`). |
| A6 | 0.5 | New orders are refused for a stopped customer in DeliveryDetails.php:328-349 (sales office and web shop), EDIProcessOrders.php:896-903, RecurringSalesOrdersProcess.php:95-103 and api_salesorders.php:280-288. Dispatch and invoice are blocked unless released in ConfirmDispatch_Invoice.php:111-119,623-630. The API `InvoiceSalesOrder` (`api_salesorders.php:799ff`) has no check, and CounterSales.php still only warns for a held account. |
| A7 | 0.5 | `CreditCustomer.php` actions need token 21. Customers.php no longer writes holdreason or creditlimit for existing customers (`:139-149`). The API `ModifyCustomer` still writes both for any API user, and the `Z_ImportDebtors.php` update path still overwrites them with no history. |
| A8 | 1 | Watch customers can order (SelectOrderItems.php:438-441 warns, :540 now allows watch in the portal path). Credit control lists open orders for watch customers (`CreditControl.php:133-169`). |
| A9 | 0.5 | Status shows in CustomerInquiry.php:173, CreditCustomer.php:170, AgedDebtors.php:323, the worklist and at order entry (watch warning, stop refusal). SelectCustomer.php, the main staff customer screen, still shows no credit status. |
| A10 | 0.5 | `CreditOrderCheck` holds new orders (`creditholdstate=1`) in DeliveryDetails.php:344-347, EDIProcessOrders.php:904-907, RecurringSalesOrdersProcess.php:162-171 and the API (only if already over the limit, `:289-291`), and `CreditOrderBlockReason` blocks dispatch until released. It works only when CheckCreditLimits = 3; the seeded default is still 1 (warn), so out of the box nothing is held. Edited orders and counter sales are never held. |
| A11 | 1 | A portal customer on stop gets "your account has been put on hold ... contact the credit control personnel" (SelectOrderItems.php:577), and CustomerCreditPortal.php:33-35 says the account is on hold. |
| A12 | 1 | `dunningstages` table with three seeded stages (30/45/60, the third a final notice warning of stop and charges; 44.php:191-196). Finance edits, adds and deletes stages, days and wording in CreditControlSettings.php:87-121,209-234. |
| A13 | 1 | Emails go to `custcontacts.statement=1` contacts (`CreditControlFunctions.php:400-409`, CreditReminders.php:55-65). Customers with no email are shown with the letter text to post (`:81-87,128`). |
| A14 | 1 | CreditReminders.php: a user-started run with a preview of customer, stage, days and amount and a tick box per customer (`:93-137`). Only ticked customers are sent (`:34-35`). |
| A15 | 1 | `CreditReminderDue` (`CreditControlFunctions.php:363-397`) needs a net overdue amount, skips a stage already sent in the current overdue cycle and enforces `CreditDunningMinDays`. It is re-checked at send time (CreditReminders.php:41). |
| A16 | 1 | `dunninglog` row with date, stage, invoice list, amount and method (CreditReminders.php:67-70), plus a 'reminder' event. |
| A17 | 1 | `CreditBuildLetter` (`CreditControlFunctions.php:413-429`) lists each overdue item with due date and the amount in the customer's currency. |
| A18 | 1 | `debtortrans.disputed` (44.php:16), set with a reason in CreditCustomer.php:138-152 and excluded from overdue items (`CreditControlFunctions.php:308`), so it is neither chased nor charged. |
| A19 | 1 | CreditCharges.php: interest (rate × net overdue × days/365) and/or a flat fee (`:88-95`). Rate, fee and days-overdue are settings (CreditControlSettings.php:160-186). |
| A20 | 0.5 | One `chargeexempt` flag exempts a customer from both (CreditCustomer.php:124-131, CreditCharges.php:74). It cannot exempt from interest only or from fees only. |
| A21 | 0.5 | Charges are type 51 in the customer's currency with a descriptive invtext/reference (CreditCharges.php:122-131). Statements and CustomerInquiry show any type by its systypes name. CustomerAccount.php renders only types 10/11/12, so the charges are missing from that account page. |
| A22 | 1 | Preview with tick boxes and a confirm prompt (CreditCharges.php:166-203). Re-runs are skipped per customer, month and type (`:84-87,119`), backed by a UNIQUE key (44.php:99). |
| A23 | 1 | `CreditInterestAct`/`CreditLateFeeAct` are chosen in settings (CreditControlSettings.php:182-186) and used as the credit side (CreditCharges.php:131). Posting is refused while unset (`:102-107`). |
| A24 | 1 | Waive with a required reason, posted as type 52 to the same GL account at the charge's rate and allocated to the charge (CreditCharges.php:26-62). |
| A25 | 1 | CreditWriteOffs.php:110-152: all or part of the open balance, with a required reason, limited to what is owed. |
| A26 | 1 | Above `CreditWriteOffLimit` (home currency) the request stays pending (`:140-149`) until a token-22 user approves (`:84-107`). |
| A27 | 1 | `CreditPostWriteOff` (`:43-79`) posts type 53, debits the bad debt account and credits debtors control at the original invoice rates, and allocates oldest-first so the balance falls. Valuing at the posted rates means no currency difference arises; this is stated in NOTES.md. |
| A28 | 1 | `putonstop` defaults from `CreditStopOnWriteOff` and can be unticked per write-off (`:173-176`). `CreditSetStatus(...'stop')` runs inside the posting (`:70-76`). |
| A29 | 1 | Write-off report by period with customer, amount, home amount, reason, requested by, approved by and status (CreditWriteOffs.php:208-245). |
| A30 | 1 | CreditControl.php: reviews due or overdue (`:172-199`), over limit and by how much in home currency (`:201-235`), watch/stop (`:237-270`), held and watch orders. Rep filter (forced for SalesmanLogin, `:44,55`) and currency filter (`:52-54`); totals in home currency. |
| A31 | 1 | AgedDebtors.php:286-288,323-325 add credit status, credit limit and last reminder stage. |
| A32 | 1 | `creditevents` logs reviews, stop/watch, limit changes, releases, reminders, charges, waivers, write-offs, disputes and notes. Customers.php changes are logged too (`:218`). Per-customer history at CreditCustomer.php:354-369. |
| A33 | 1 | `CreditRepCanSee` guards CreditCustomer.php:35. CreditControl.php forces the rep's customers. Reps see status, limit, balance, overdue and reminders, but not reviews, notes, charges or write-offs (`:176,334,355`). |
| A34 | 1 | Reps can view but every change in CreditCustomer.php needs token 21. Customers.php no longer writes limit or status (`:139-149`). |
| A35 | 0.5 | CustomerCreditPortal.php shows balance, reminders and charges for the logged-in customer. The customer menu is hard-coded in index.php:73-95, which was not changed, and no link reaches the page, so a customer can open it only by typing the URL. Charges do appear in Account Status (CustomerInquiry), but reminders do not. |
| A36 | 1 | The portal page reads the debtor from `www_users.customerid` (`CreditControlFunctions.php:74-78`). CustomerInquiry.php:27-33 now forces a portal user's own account, which closes the existing `?CustomerID=` hole. |
| A37 | 1 | Every charge, waiver and write-off posts a balanced debtors-control entry with the debtortrans row (`CreditPostTransaction`, `CreditControlFunctions.php:451-513`), so the sub-ledger and the GL move together. |
| A38 | 1 | Z_CheckDebtorsControl.php:124-137 adds types 51-53 as their own column in the period reconciliation. |
| A39 | 0.5 | 44.php covers upgrades, and install tables and data mirror it. A fresh non-demo install loads `install/sql/data/menuitems.sql` in one mysqli_query, and that file now holds two INSERT statements, so it fails and the install gets no menus at all. On a demo install the demo hold reasons have no `dissallowinvoices` value (-1), and `creditcontrol_demo.sql` seeds no normal/watch/stop reason, so every status change fails with "No credit status of this kind is defined". |
| A40 | 0.5 | Existing customers keep their hold reason, so current stops stay stops, and get a review date (44.php:200). The date is hard-coded to 12 months, not the Finance setting. A starting history row is written for stop/watch customers (`:203-210`). There is no dedicated way to load the spreadsheet stop list: NOTES points to Z_ImportDebtors, which logs nothing. |
| A41 | 1 | Invoices, statements and postings are unchanged for customers who are not overdue. The new blocks apply only to stop, and the hold applies only when CheckCreditLimits = 3. |
| A42 | 1 | ManualAccountsReceivable.html:204-249 covers reviews, stop/watch, the customer page, the worklist, the reminder run, month-end charges, write-offs and the ledger check. |
| A43 | 1 | ManualAccountsReceivable.html:247-248 "A note for sales staff: watch and stop", including who to contact. |

**A = 38 / 43**

## B. Rules away from the change (40)

| id | score | justification |
|---|---|---|
| B1 | 1 | Stop/watch use holdreason → `dissallowinvoices` 1/2 (`CreditControlFunctions.php:14-16,83-101,147-174`), with configurable codes. There is no parallel customer flag; `salesorders.creditholdstate` is an order-level approval state. |
| B2 | 1 | ConfirmDispatch_Invoice.php:111-119 (opening the order) and :623-630 (ProcessInvoice). |
| B3 | 1 | RecurringSalesOrdersProcess.php:95-103 skips stopped customers and leaves the template due. Over-limit orders are held and not auto-invoiced (`:162-171`). |
| B4 | 1 | EDIProcessOrders.php:895-910: no order for a stopped customer, a line goes in the email, and an event is logged. |
| B5 | 0.5 | `InsertSalesOrderHeader` refuses a stopped customer with new error 1174 (api_salesorders.php:280-288). `InvoiceSalesOrder` (`:799ff`) does not check. |
| B6 | 0.5 | Order checks use GetCreditAvailable (`CreditOrderCheck`, `CreditControlFunctions.php:237-252`) and follow CheckCreditLimits, with the new option 3. The worklist's over-limit list (CreditControl.php:202-217) and CreditCustomer.php:173 use `SUM(balance) > creditlimit` without open orders, a second formula. |
| B7 | 1 | Z_ChangeCustomerCode.php:76-77,110-111 add both columns to the re-INSERT, and :215-220 move all five new tables. |
| B8 | 1 | Customers.php:357-368 refuses the delete when any of the five credit tables has rows, before anything is deleted. |
| B9 | 0.5 | Z_ImportDebtors.php:406,429 fills nextreviewdate on insert. The columns are not appended to `$FieldHeadings`, so they cannot be imported. |
| B10 | 0 | api_customers.php:359-362 only defaults nextreviewdate on insert, with no validation. ModifyCustomer still writes holdreason, creditlimit and the new columns unchecked. |
| B11 | 1 | Types 51/52/53 through `NewSysType` (44.php:128-130), `install/sql/data/systypes.sql`, the demo file and DatabaseTranslations.php. |
| B12 | 1 | `GetNextTransNo` is called inside `CreditPostTransaction` (`CreditControlFunctions.php:455`), always after `DB_Txn_Begin` (CreditCharges.php:50,130; CreditWriteOffs.php:57). |
| B13 | 0.5 | `GetPeriod` is used for prd and periodno (`CreditControlFunctions.php:457`). The posting date is always today. `ProhibitPostingsBefore` is not checked or shown. |
| B14 | 1 | GL rows are written only when `gllink_debtors == 1`, and the AR side goes to `CompanyRecord['debtorsact']` (`:497-511`). |
| B15 | 0 | No `EnsureGLEntriesBalance`. Balance holds only because the debtors line is derived as minus the total (`:507-510`). |
| B16 | 1 | Home = customer amount / rate. Charges are positive; waivers and write-offs negative. The stored rate is cust/home (`:461`). |
| B17 | 0 | No `InsertGLTags` after the gltrans inserts. |
| B18 | 0 | The bad-debt (and income) account picker lists every chartmaster account (CreditControlSettings.php:123-130) and accepts the debtors control account. |
| B19 | 1 | Write-offs and waivers are allocated at posting through `custallocns` and alloc/settled (`CreditAllocate`, `:516-525`). Charges are positive items that receipts can be allocated to. |
| B20 | 0.5 | No exchange difference is posted to `salesexchangediffact`. The write-off is valued at the invoices' own rates (CreditWriteOffs.php:24-40), so none arises by design. |
| B21 | 0.5 | CustomerInquiry.php's else-branch shows the new types by systypes name. CustomerAccount.php (`:281-382`, types 10/11/12 only) was not extended, so charges, waivers and write-offs are dropped there. |
| B22 | 1 | `debtortrans.salesperson` comes from the customer's branch salesman (`CreditControlFunctions.php:463,491`). |
| B23 | 1 | The page skips months already charged (CreditCharges.php:84-87,119), and `UNIQUE KEY onechargepermonth` backs it (44.php:99). |
| B24 | 0 | The GL accounts are `config` rows (CreditInterestAct/LateFeeAct/BadDebtAct), not `companies` columns. There is no GetConfig, CompanyPreferences or GLAccounts delete-guard change, so a chosen account can be deleted. |
| B25 | 0.5 | `CreditDueDateSQL` (`:282-287`) uses the AgedDebtors rule (daysbeforedue vs last_day+dayinfollowingmonth). Stage and charge thresholds are their own day counts, not the PastDueDays1/2 bands. |
| B26 | 1 | Open items use `debtortrans.balance` (`:307,324`; CreditWriteOffs.php:25), never `settled`. |
| B27 | 1 | `custcontacts.statement = 1`, filtered by IsEmailAddress (`CreditControlFunctions.php:400-409`). |
| B28 | 0 | No PDFs. Letters are plain-text email bodies. |
| B29 | 0.5 | A send counts only when `=== true` (CreditReminders.php:58-63), and there is no temp file. The recipients are passed as a numeric list, which SMTP mode (`SendEmailBySmtp` reads keys as addresses) turns into address "0". |
| B30 | 0.5 | CreditControl.php and CreditCustomer.php apply the rep filter. The reminder run, charge preview, waiver list and write-off lists (CreditReminders.php:94-98, CreditCharges.php:72-75,207-223, CreditWriteOffs.php:185-224) have none (they are token-21 pages). |
| B31 | 1 | Portal and CustomerInquiry take the debtor from `www_users.customerid` (`CreditControlFunctions.php:74-78`, CustomerInquiry.php:27-33). |
| B32 | 0 | Hard-coded token numbers: `CreditUserHasToken(21)` and `(22)` (`CreditControlFunctions.php:28-35`). There is no scripts-table "false script". |
| B33 | 1 | All seven pages are registered in 44.php:141-147, `install/sql/data/scripts.sql` and the demo seed (`install/sql/creditcontrol_demo.sql`, loaded after demo.sql by InstallFunctions.php:619-622). No page sets `$PageSecurity`. |
| B34 | 0.5 | Helpers throughout, CreateTable with exact names, and a guarded one-line UpdateDBNo (44.php:212-214). The go-live backfill and history rows are raw `executeSQL` UPDATE/INSERT…SELECT (`:200,203-210`): idempotent, but not through helpers. |
| B35 | 1 | install/sql/tables/ files for all six new tables, and the columns are mirrored in debtorsmaster.sql, debtortrans.sql and salesorders.sql, with '1000-01-01' datetimes. |
| B36 | 0.5 | Seeds are in install/sql/data/* and in a separate `install/sql/creditcontrol_demo.sql` rather than install/sql/demo.sql. `install/sql/data/menuitems.sql` now has two INSERT statements, so the one-query loader fails the whole file. |
| B37 | 0.5 | `NewMenuItem` is used in 44.php:149-154. The seeds cover only some roles (worklist 1-8, the others 6/8/7), and menuitems.sql breaks as above. Config is added with NewConfigValue and in config.sql, but none of it is in SystemParameters.php; it lives on a separate settings page. |
| B38 | 1 | Every helper used (AddColumn, AddIndex, CreateTable, NewSysType, NewSecurityToken, InsertRecord, NewScript, NewMenuItem, NewConfigValue) exists in all four UpgradeDB_* variants. No AddCalculatedColumn. |
| B39 | 0 | Forms are hand-written; no UIGeneralFunctions. POST reasons already escaped by session.php are escaped again in `LogCreditEvent` (`CreditControlFunctions.php:138`), e.g. status, dispute and release reasons. |
| B40 | 0.5 | $Title/$ViewTopic/$BookMark are set before header.php. The anchors (CreditCharges, CreditReminders, CreditWriteOffs, CreditControl, CreditCustomer...) are in ManualAccountsReceivable.html, but the pages point to ViewTopic ARTransactions/ARInquiries/Setup, whose files lack those ids, so context help breaks. |

**B = 25.5 / 40**

## Totals

- A = 38 / 43, B = 25.5 / 40, total = 63.5 / 83
- Correctness: 3 / 5. The design is complete and mostly coherent: stop enforced at order and dispatch, re-checked at send and post time, balanced postings at consistent rates, a duplicate-month guard, allocation of write-offs and waivers. Against that are the defects below: the fresh-install menu failure, the no-op credit fields in Customers.php, SMTP-mode email, the demo hold reasons, the unguarded API invoice path, and the hold that is off by default. Nothing was run.
- Conventions: 3 / 5. It reuses holdreasons, GetCreditAvailable, GetNextTransNo/GetPeriod, NewSysType, the update helpers with a guarded UpdateDBNo, install table mirrors and systypes translations. Against that: hard-coded tokens 21/22, double escaping, no UIGeneralFunctions, no EnsureGLEntriesBalance or GL tags, GL accounts in config rather than companies, a two-statement data file, a side demo file, and help topics that do not match the manual page.

## Regressions and defects

1. Fresh non-demo install: `install/sql/data/menuitems.sql` now contains a second `INSERT INTO menuitems` statement. InstallFunctions.php loads each data file with one `mysqli_query`, so the whole file fails ("Database tables could not be populated") and the new install has no menu items at all, not just no credit-control ones.
2. Customers.php:143-147: `$CreditHoldSQL = "" . $CreditHoldSQL . "";` is a no-op, so the UPDATE never includes holdreason or creditlimit, even for token-21 users. Customer maintenance can no longer change either field for anyone, and the read-only and disabled hints mislead credit control. The disabled HoldReason select is not posted, so a validation redisplay reads an undefined `$_POST['HoldReason']`.
3. CreditReminders.php:58: `SendEmailFromWebERP(..., $Emails, ...)` passes a numeric list. With SmtpSetting = 1, `SendEmailBySmtp` calls `addAddress(0, 'x@y')`; PHPMailer (exceptions on) throws on the invalid address and the run dies. It works with the default mail() mode.
4. Demo install: the demo holdreasons have `dissallowinvoices` -1, and `creditcontrol_demo.sql` adds no normal/watch/stop reasons or their config codes. `CreditHoldReasonCode` therefore returns null for every kind, and stop/watch/normal changes, reviews with a status outcome and stop-on-write-off all fail.
5. CreditWriteOffs.php:93-94: approval sets `status='approved'` outside the posting transaction. If the posting then fails (GL account unset, balance changed), the request leaves the pending list and cannot be posted or rejected from the UI.
6. The over-limit hold needs CheckCreditLimits = 3. The seed and existing sites stay at 1, so BR-10 is off until someone changes System Parameters. Contracts.php ignores mode 3 (no warning).
7. Bypasses left open: API `InvoiceSalesOrder` invoices orders for stopped customers. API `ModifyCustomer` and `Z_ImportDebtors` updates change holdreason and creditlimit with no permission check or history. CounterSales still only warns for a held account.
8. Context help on every new page points to a manual file without the matching anchors (manual.js throws on the missing ids).
