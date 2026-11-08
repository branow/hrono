# t12 credit control, try 6: grading of run A (blind)

- Run diff: `scratchpad/blind12d/A.diff` (3720 lines, 50 files)
- Workspace: `scratchpad/blind12d/A/`
- Base: `scratchpad/base/` (4cb937f79e8b)
- Task: `tasks/t12-credit-control/brd.md` (BR-01..BR-43). Checklist: `tasks/t12-credit-control/checklist.md`. Rule details: `grading/t10-credit-control/rules/`.
- Every claim was checked in the code. NOTES.md was read only for the decisions on the BRD's open questions. File:line refers to the workspace.

Scoring: met 1 / partly 0.5 / missed 0.

The run keeps credit status on `holdreason` -> `holdreasons.dissallowinvoices` (1 stop, 2 watch, codes 90/91 seeded) and adds an order-level hold `salesorders.creditstatus` (0/1 held/2 released) for over-limit orders. New pages: CreditReview.php (review, stop/watch, exemptions, disputes, history), CreditControlReport.php (due reviews, over limit, watch/stop, held orders with release), CreditDunningRun.php, CreditCharges.php (interest, fees, waivers), CreditWriteOffs.php and CreditWriteOffReport.php, CreditDebtorsReconciliation.php, CreditControlSetup.php, CustomerCreditAccount.php (portal), a manual page; shared logic in `includes/CreditControlFunctions.php`; permissions through "false script" rows `CreditControlAction` (token 21) and `CreditControlApproval` (22). Stop is enforced on DeliveryDetails, ConfirmDispatch_Invoice, EDI, recurring orders and three API functions.

Two defects decide much of the score. (1) The three new `companies` GL accounts are never added to GetConfig.php's explicit column list (includes/GetConfig.php:60-96), so `$_SESSION['CompanyRecord']['creditinterestact'|'creditfeeact'|'baddebtact']` never exist. With `gllink_debtors = 1` CreditCharges.php:23-30 always reports "account not chosen" and blocks preview and posting, and CreditWriteOffs.php:74 blocks every write-off; the waiver and write-off posting code would post to an empty account. (2) Fresh installs break: install/sql/data/config.sql, menuitems.sql and scripts.sql each gain a second INSERT statement, and the installer runs each file through one DB_query (includes/InstallFunctions.php:477-482), so all three files fail entirely. The positional `INSERT INTO companies VALUES` (InstallFunctions.php:504-528, install/sql/demo.sql:14) was not given the three new columns, so the company row fails on both install paths. Nothing was executed.

## A. The BRD (43)

| id | score | justification |
|---|---|---|
| A1 | 1 | CreditReview.php:64-145 records date, user, outcome (confirmed/raised/reduced/watch/stop/normal), old and new limit, old and new hold reason, notes and next review date (`INSERT INTO creditreviews` :115-135) for any customer. |
| A2 | 0.5 | New customers get `nextreviewdate` = today + `CreditReviewMonths` in Customers.php:259-282 and API InsertCustomer (api_customers.php:274). Z_ImportDebtors.php is unchanged (no date). One standard period only; no shorter default for higher-risk customers. |
| A3 | 1 | Full review and action history listed (CreditReview.php:309-375); no code updates or deletes `creditreviews`; Customers.php:361-370 refuses to delete a customer with credit control records. |
| A4 | 1 | Limit UPDATE (CreditReview.php:110-114) and review INSERT (:115-135) in one transaction (:104,141); raised/reduced/confirmed must match the limit entered (:76-85). |
| A5 | 1 | Stop/watch/off via the review outcome with a required reason (CreditReview.php:86-89); `CreditChangeStatus` changes `holdreason` and logs who/when/old->new/reason (CreditControlFunctions.php:686-701, 110-129). |
| A6 | 1 | Refused on save for sales office and portal (DeliveryDetails.php:337-345), EDI (EDIProcessOrders.php:904-912), standing orders (RecurringSalesOrdersProcess.php:102-107), API header/lines (api_salesorders.php:282-285, 533-537); dispatch/invoice of earlier orders blocked until release (ConfirmDispatch_Invoice.php:42-52, api_salesorders.php:828-835; CreditControlFunctions.php:184-199). |
| A7 | 0.5 | Review actions need the CreditControlAction token (CreditControlFunctions.php:11-14); Customers.php:41-57 and API ModifyCustomer (api_customers.php:413-416) keep limit and status for others. But CreditStatus.php (token 3) now lets any token-3 user change what a status does (CreditStatus.php:68-85), e.g. turn code 91 to "Invoice OK" and lift every stop. |
| A8 | 1 | Watch customers can order; warnings in SelectOrderItems.php:439-441 and DeliveryDetails.php:354-355; their open orders are listed for credit control (CreditControlReport.php:178-237). |
| A9 | 1 | Status shown on SelectCustomer.php:153 (banner), CustomerInquiry.php:166-180, CustomerAccount.php:229-243, CreditReview.php, ConfirmDispatch_Invoice.php:52, order entry warnings, AgedDebtors.php and the report. |
| A10 | 1 | Over-limit orders are held (`creditstatus = 1`) on DeliveryDetails.php:423,753, EDI :987, recurring :169-174, API lines :545-550; not dispatchable/invoiceable until released on CreditControlReport.php:21-31. Only while CheckCreditLimits > 0, decided in NOTES.md (OQ5). |
| A11 | 1 | A portal customer on stop is told the account is on hold and to contact us (SelectOrderItems.php:577, DeliveryDetails.php:341-342, CustomerInquiry.php:176-178). API returns its own code `CustomerOnCreditStop` 1174, though without an `$ErrorDescription` entry (api_errorcodes.php:189). |
| A12 | 1 | Three seeded stages 30/45/60, the third a final notice warning of stop and charges (44.php InsertRecord dunningstages; install/sql/data/dunningstages.sql); days, subject and wording edited, stages added and deleted (CreditControlSetup.php:43-96). |
| A13 | 1 | Email to `custcontacts.statement = 1` contacts (CreditControlFunctions.php:367-380); no address -> marked "to be posted", letters printed on screen after the run (CreditDunningRun.php:61-64, 77-82). |
| A14 | 1 | Run started by a user (token 21); preview of stage, days, amount and recipient with a tick box per customer (CreditDunningRun.php:89-117); only ticked customers are sent (:38-74). |
| A15 | 1 | Candidates recomputed at send time (CreditDunningRun.php:31, 39-48); one stage up only while overdue past the stage's days, reset to stage 1 when the earlier debt was paid, and `DunningMinDaysBetween` gap (CreditControlFunctions.php:331-364). |
| A16 | 1 | Every letter writes `dunningletters` (date, stage, method, recipients, amount, currency, invoice list) and a log row (CreditDunningRun.php:65-69). |
| A17 | 1 | Letter lists each overdue item with dates, due date and balance in the customer's currency, total in that currency (CreditControlFunctions.php:382-401). |
| A18 | 1 | `debtortrans.disputed` set/cleared with a log row (CreditReview.php:160-175); disputed items excluded from chasing and interest (CreditControlFunctions.php:268). |
| A19 | 0.5 | Interest (annual rate / 12) and/or flat fee with settable rate, fee and grace days (CreditControlFunctions.php:403-443; CreditControlSetup.php:14-41). With GL link on, CreditCharges.php:23-30 always fails because the accounts are not in CompanyRecord (GetConfig.php:60-96), so nothing can be charged. |
| A20 | 1 | Separate interest and fee exemptions (CreditReview.php:147-158) honoured (CreditControlFunctions.php:425,428). |
| A21 | 0.5 | Type 51 in the customer's currency with its own description (CreditControlFunctions.php:529-563); fee converted from home currency. PrintCustStatements and CustomerInquiry show it, but CustomerAccount.php:289-393 renders only types 10/11/12, so charges are missing from the on-screen statement. |
| A22 | 0.5 | Preview with tick boxes and confirm (CreditCharges.php:96-133), month guard plus `UNIQUE KEY onechargepermonth` (install/sql/tables/creditcharges.sql). The preview itself is hidden whenever the account check fails, which is always with GL link on (CreditCharges.php:96). |
| A23 | 0 | Accounts are chosen in CompanyPreferences.php:279-289, but posting reads `$_SESSION['CompanyRecord']['creditinterestact'/'creditfeeact']` (CreditControlFunctions.php:531,535), which GetConfig never loads. The chosen accounts never reach the ledger. |
| A24 | 0 | Waiver with reason posts type 52 allocated to the charge (CreditControlFunctions.php:565-608), but its GL line uses the same unloaded account (:582), and no charge can exist under GL link. The reversal cannot reach the ledger. |
| A25 | 0.5 | Full or partial write-off with a reason, capped at what is owed (CreditWriteOffs.php:49-95). Blocked whenever GL link is on (`baddebtact` not in CompanyRecord, :74). |
| A26 | 0.5 | Above `CreditWriteOffApprovalLimit` (home currency) only recorded until a CreditControlApproval user approves (CreditWriteOffs.php:29-46, 87-93). The same :74 block stops the request first under GL link. |
| A27 | 0 | Posting would credit debtors and debit `baddebtact` with an exchange difference to `salesexchangediffact` (CreditControlFunctions.php:621-684), but `baddebtact` is never loaded, so nothing reaches the bad debt account. |
| A28 | 0.5 | "Put on stop" ticked by default and applied on posting (CreditWriteOffs.php:126; CreditControlFunctions.php:677-679). Only happens when a write-off posts, which is blocked under GL link. |
| A29 | 1 | Period report with customer, amount, home amount, reason, written off by and approved by (CreditWriteOffReport.php:28-59). |
| A30 | 1 | Due/overdue reviews, over limit with amount, watch/stop lists; filter by rep and currency; home-currency totals (CreditControlReport.php:33-176). |
| A31 | 1 | AgedDebtors.php:286-288, 324-326 adds credit status, credit limit and last reminder stage (columns already selected in its SQL). |
| A32 | 0.5 | Log rows for reviews, status, limit, reminders, charges, waivers, write-offs, holds and releases (CreditReview.php:334-354). Limit or status changed by a credit control user on Customers.php, and status definitions changed on CreditStatus.php, write no history. |
| A33 | 1 | Reps limited to their own customers on CreditReview.php:49 (`CreditControlCanSee`), CreditControlReport.php:33-36, CreditWriteOffReport.php:35, AgedDebtors (existing). |
| A34 | 1 | Forms shown only with the action token (CreditReview.php:205, 241, 277); Customers.php:41-57 keeps limit and status for others. |
| A35 | 1 | CustomerCreditAccount.php shows balance, reminders, and charges and waivers (:35-82), linked from the customer menu (index.php:86), token 1. |
| A36 | 1 | Debtor taken from the login session, never the request (CustomerCreditAccount.php:16-21). |
| A37 | 0.5 | When postings happen they balance against debtors control at the posting rate (CreditControlFunctions.php:494-503). Charges, waivers and write-offs cannot post under GL link, so the month-end agreement after them is never reached. |
| A38 | 1 | CreditDebtorsReconciliation.php compares customer ledger and debtors control by type (:45-100) and lists unmatched entries on both sides (:114-165). |
| A39 | 0.5 | Live system: sql/updates/44.php. New install broken: three data files now hold two statements and fail whole (InstallFunctions.php:477-482); companies positional INSERTs have 28 values for 31 columns (InstallFunctions.php:504-528, install/sql/demo.sql:14); demo.sql has no seeds. |
| A40 | 0.5 | Existing hold reasons kept, so current stops stay stops; every customer gets a review date (44.php final executeSQL), but a hard-coded 12 months, not the Finance setting. The spreadsheet stop list is loaded one customer at a time. |
| A41 | 1 | Checks act only on stopped/over-limit customers and charges only on overdue invoices; other invoices, statements and postings unchanged. |
| A42 | 1 | doc/Manual/ManualCreditControl.html:1-48 covers reviews, stop/watch, reminder run, charges, write-offs, the report and reconciliation. |
| A43 | 1 | ManualCreditControl.html "Notes for sales staff" section explains watch and stop for reps and says to contact credit control. |

## B. Rules away from the change (40)

| id | score | justification |
|---|---|---|
| B1 | 1 | Status is `holdreason` -> `dissallowinvoices` 1/2 (CreditControlFunctions.php:35-64); no parallel customer flag (the order-level `creditstatus` is an over-limit hold). |
| B2 | 1 | ConfirmDispatch_Invoice.php:29-55 refuses stopped customers and held orders. |
| B3 | 1 | RecurringSalesOrdersProcess.php:102-107 skips stopped customers; held orders not auto-invoiced (:230). |
| B4 | 1 | EDIProcessOrders.php:897-916 does not create orders for stopped customers. |
| B5 | 1 | api_salesorders.php InsertSalesOrderHeader :279-286, InsertSalesOrderLine :528-551, InvoiceSalesOrder :824-835. |
| B6 | 0.5 | Order check follows CheckCreditLimits > 0 and uses GetCreditAvailable (CreditControlFunctions.php:163-172). The report's over-limit list uses its own formula, ledger balance minus limit (CreditControlReport.php:140), which ignores open orders. |
| B7 | 0.5 | New tables moved on rename (Z_ChangeCustomerCode.php:241-247); the explicit debtorsmaster re-INSERT column list (:44-107) lacks the five new columns, so they are lost. |
| B8 | 1 | Customers.php:361-370 blocks delete when any of the five tables has rows. |
| B9 | 0 | Z_ImportDebtors.php unchanged. |
| B10 | 0.5 | API: creditlimit/holdreason gated by the action token (api_customers.php:270-273, 413-416); the new columns (nextreviewdate, exemptions) stay writable unvalidated through ModifyCustomer's generic UPDATE. |
| B11 | 1 | Types 51/52/53 through NewSysType in 44.php and install/sql/data/systypes.sql. |
| B12 | 1 | GetNextTransNo inside DB_Txn_Begin for charges, waivers and write-offs (CreditControlFunctions.php:454, 537, 587, 635). |
| B13 | 0.5 | GetPeriod used (CreditControlFunctions.php:453); the user-entered charge date is not checked against ProhibitPostingsBefore (CreditCharges.php:53-54). |
| B14 | 1 | GL rows only when `gllink_debtors == 1`, AR side to `debtorsact` (CreditControlFunctions.php:491-502). |
| B15 | 0.5 | EnsureGLEntriesBalance only in the write-off (CreditControlFunctions.php:680), and the result is not checked; charges and waivers have none. |
| B16 | 1 | GL = amount / rate (CreditControlFunctions.php:496); charges positive, waivers and write-offs negative. |
| B17 | 0 | No InsertGLTags after any gltrans insert (CreditPostGL :506-527). |
| B18 | 1 | Bad debt account picker limited to P&L accounts (CompanyPreferences.php:287-289, `pandl=1` in UIGeneralFunctions.php:179), so no control account can be chosen. |
| B19 | 1 | Waivers and write-offs are allocated at posting via custallocns (CreditControlFunctions.php:590-596, 649-658); charges stay unsettled debits, open to manual allocation (CustomerAllocations.php:272). |
| B20 | 1 | Write-off exchange difference to `salesexchangediffact` with `diffonexch` set (CreditControlFunctions.php:663-668). |
| B21 | 0.5 | CustomerInquiry.php shows the new types in its misc branch (:620+); CustomerAccount.php:289-393 drops them. |
| B22 | 1 | `salesperson` recorded from the branch's salesman (CreditControlFunctions.php:446-490). |
| B23 | 1 | Own guard (`$Done`, CreditControlFunctions.php:407-410) plus a unique key on creditcharges. |
| B24 | 0 | CompanyPreferences form and UPDATE done (and Z_ChangeGLAccountCode); GetConfig column list, GLAccounts.php delete guard and both positional companies INSERTs not done. |
| B25 | 0.5 | Due date matches AgedDebtors (CreditDueDateSQL, CreditControlFunctions.php:202-206); PastDueDays1/2 bands not reused (own stage days). |
| B26 | 0.5 | Open items filter on `settled = 0` as well as balance (CreditControlFunctions.php:236-237; CreditWriteOffable :613-614). |
| B27 | 1 | `custcontacts.statement = 1` with IsEmailAddress (CreditControlFunctions.php:367-380). |
| B28 | 0 | No PDF; letters are plain-text email bodies. |
| B29 | 1 | `$Response === true` counts as sent, a failure is reported and not recorded (CreditDunningRun.php:52-59); no temp file used. |
| B30 | 0.5 | SalesmanLogin filter on CreditReview, CreditControlReport and CreditWriteOffReport; none on the dunning run, the charge run, the write-off pending list or the reconciliation. |
| B31 | 1 | CustomerCreditAccount.php:16-21 uses the login's CustomerID only. |
| B32 | 1 | "False script" rows CreditControlAction/CreditControlApproval (44.php NewScript; scripts.sql) checked through PageSecurityArray (CreditControlFunctions.php:11-20). |
| B33 | 0.5 | Every page in 44.php NewScript and in scripts.sql (as a second statement, which breaks the file); none in install/sql/demo.sql. No `$PageSecurity` in pages. |
| B34 | 0.5 | 44.php uses helpers, CreateTable with exact names and no ENGINE, guarded one-line UpdateDBNo; the review-date backfill is a raw executeSQL UPDATE (guarded, idempotent). |
| B35 | 1 | install/sql/tables file per new table and columns in debtorsmaster/debtortrans/salesorders/companies.sql; dates '1000-01-01'. |
| B36 | 0 | config.sql, menuitems.sql and scripts.sql now hold two statements each (one-statement rule broken, file fails); install/sql/demo.sql untouched. |
| B37 | 0.5 | NewMenuItem plus seed rows for roles 1-9; config via NewConfigValue and config.sql, but settings live on CreditControlSetup.php, not SystemParameters.php. |
| B38 | 1 | Helpers used (AddColumn, AddIndex, CreateTable, NewSysType, NewConfigValue, InsertRecord, NewSecurityToken, NewScript, NewMenuItem) exist in all four UpgradeDB_* files; no AddCalculatedColumn. |
| B39 | 0 | No UIGeneralFunctions in new forms; POST values escaped again: CreditControlLog runs DB_escape_string on details built from `$_POST['Notes']` etc. (CreditControlFunctions.php:123), CreditWaiveCharge on `$_POST['WaiveReason']` (:600). |
| B40 | 1 | $Title/$ViewTopic/$BookMark before header.php on all pages; ManualCreditControl.html has anchors for CreditControl and every bookmark used (CreditReviews, DunningLetters, InterestFees, WriteOffs, CreditControlReport, CreditReconciliation); ManualOutline.php entry added. |

## Totals

- A = 34 / 43, B = 28 / 40, total = 62 / 83
- Correctness: 2 / 5. Stop enforcement across every order and invoice route, the over-limit hold and release, and the reminder logic are solid. But with the GL link on (the normal setup, and the BRD requires GL postings), month-end charges, waivers and write-offs cannot run, because GetConfig never loads the three new accounts. Both fresh-install paths are broken by the multi-statement seed files and the unchanged positional companies INSERTs. None of it was run.
- Conventions: 3 / 5. False-script permissions, idempotent helpers with a guarded UpdateDBNo, install table mirrors, NewSysType, GetNextTransNo inside transactions, `$Transaction=true` on postings, `=== true` mail check, statement contacts, full manual anchors and outline entry. Against that: multi-statement seed files, demo.sql untouched, the companies-column checklist half done (GetConfig, GLAccounts, positional INSERTs), no UIGeneralFunctions, double escaping, no GL tags, EnsureGLEntriesBalance only once, settings outside SystemParameters.

## Regressions and defects

1. includes/GetConfig.php:60-96 does not select `creditinterestact`, `creditfeeact`, `baddebtact`. With `gllink_debtors = 1`, CreditCharges.php:23-30 and CreditWriteOffs.php:74 always refuse, and CreditPostCharge/CreditWaiveCharge/CreditPostWriteOff would post to an empty account.
2. Fresh non-demo install: install/sql/data/config.sql, menuitems.sql and scripts.sql each contain two INSERT statements. The installer sends each file as one query (InstallFunctions.php:477-482), so the whole file fails: no config, no menu items, no scripts at all.
3. Both install paths: `INSERT INTO companies VALUES (...)` (InstallFunctions.php:504-528, install/sql/demo.sql:14) supplies 28 values for the now 31-column table, so no company record is created and login stops at "company record has not yet been set up".
4. Demo install: install/sql/demo.sql has no new scripts, config, systypes, hold reasons, tokens or stages, and DBUpdateNumber 44 means 44.php never runs.
5. CustomerAccount.php:289-393 drops types 51-53 from the on-screen statement while their amounts count in its balance.
6. CreditStatus.php (token 3) can change a status's effect, lifting or imposing stop for every customer on that code, outside credit control and with no history.
7. Deleting a middle reminder stage (CreditControlSetup.php:87-96) stops escalation past it: CreditDunningCandidates requires `stage = last + 1` (CreditControlFunctions.php:349-351).
8. Z_ChangeCustomerCode.php:44-107 loses the five new debtorsmaster columns on a code change. GLAccounts.php delete guard does not protect the three new accounts. API codes 1174-1176 have no description.
