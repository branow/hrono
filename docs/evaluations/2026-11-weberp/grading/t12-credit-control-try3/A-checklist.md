# t12 credit control, try 3: grading of run A (blind)

- Run diff: `scratchpad/blind12c/A.diff` (3019 lines, 39 files)
- Workspace: `scratchpad/blind12c/A/`
- Base: `scratchpad/base/` (4cb937f79e8b)
- Task: `tasks/t12-credit-control/brd.md` (BR-01..BR-43). Checklist: `tasks/t12-credit-control/checklist.md`. Rule details: `grading/t10-credit-control/rules/`.
- Every claim was checked in the code. NOTES.md was read only for the decisions on the BRD's open questions. File:line refers to the workspace.

Scoring: met 1 / partly 0.5 / missed 0.

The run builds credit status on the existing `holdreason` -> `holdreasons.dissallowinvoices` (0 normal, 1 stop, 2 watch; config `CreditNormalReason`/`CreditWatchReason`/`CreditStopReason` = 1/91/92). It adds: a per-customer review, status and history page (CreditReview.php); stop enforcement on DeliveryDetails, ConfirmDispatch_Invoice, EDI, recurring orders and both API functions; a reminder run (DunningRun.php); month-end interest and fees with waivers (CreditCharges.php); write-offs with approval and a period report (CreditWriteOff.php); a credit control report with a ledger-agreement table (CreditControlReport.php); a settings page; a portal page (CustomerCredit.php); and a manual section. The shared logic is in `includes/CreditControlFunctions.php`. The over-limit hold (BR-10) and the aged-debtors columns (BR-31) are listed in NOTES.md as not done. Nothing was executed.

## A. The BRD (43)

| id | score | justification |
|---|---|---|
| A1 | 1 | CreditReview.php:80-143 inserts a `creditreviews` row with the date, user, outcome (confirmed/raised/reduced/watch/stop/release), old and new limit, notes and next review date (`:111-120`). Any customer can be selected. |
| A2 | 0.5 | New customers from Customers.php:273 get `CreditNextReviewDate()` from `CreditReviewMonths` (CreditControlFunctions.php:153-160). Customers created by API `InsertCustomer` or Z_ImportDebtors.php get no date. There is one standard period only, so a higher-risk customer cannot get a shorter default. |
| A3 | 1 | Reviews and the full history are listed at CreditReview.php:382-430. No code updates or deletes `creditreviews`. Customers.php:352-364 refuses to delete a customer that has credit history. |
| A4 | 1 | The limit UPDATE (CreditReview.php:121-125) runs in the same transaction as the review insert (`:110-139`). The limit can change only with outcome raised/reduced (`:91-100`). |
| A5 | 1 | The Status action requires a reason (CreditReview.php:145-160). `SetCreditStatus` changes `holdreason` and writes a STOP/WATCH/RELEASE row with user and time (CreditControlFunctions.php:128-151, 69-88). |
| A6 | 1 | Stopped customers are refused at order commit (DeliveryDetails.php:330-333; sales office and portal), EDI (EDIProcessOrders.php:897-903), recurring orders (RecurringSalesOrdersProcess.php:98-104), API `InsertSalesOrderHeader` (api_salesorders.php:280-290) and API `InvoiceSalesOrder` (`:855-864`). Dispatch and invoice of existing orders are blocked until release (ConfirmDispatch_Invoice.php:608-612). |
| A7 | 0.5 | CreditReview.php actions need token 3 (`UserIsCreditControl`, CreditControlFunctions.php:42-44). Customers.php (token 3) still writes `creditlimit` and `holdreason` without a reason; it only logs the change (Customers.php:208-213). API `ModifyCustomer` (api_customers.php) still writes both for any API user. |
| A8 | 1 | A watch customer can still order; staff see a warning at SelectOrderItems.php:440-442 (and `:540-542` on the customer path). Open orders of watched customers are listed on CreditControlReport.php:166-208. |
| A9 | 0.5 | Status shows on CreditReview.php:219-245, the credit control report and order entry. SelectCustomer.php only gains a menu link, no status. CustomerInquiry.php:169-170 and CustomerAccount.php:232-233 print "ACCOUNT ON HOLD" for a watch customer (`!= 0`). |
| A10 | 0 | Not built (NOTES.md "Not done"). Over-limit orders are not held; the existing CheckCreditLimits warn/prohibit is unchanged. |
| A11 | 0.5 | A portal customer on stop sees "your account has been put on hold ... contact the credit control personnel" (SelectOrderItems.php:577-579), and DeliveryDetails.php:332 explains the stop. The API (NOTES.md: the web shop's route) returns `CustomerOnStop` = 1158, the same number as `NoCompanyRecord` (api_errorcodes.php:173-174), whose description is "Unable to read company record" (`:351`). |
| A12 | 1 | Three stages seeded at 30/45/60 days, the third a final notice warning of stop and charges (44.php:145-150; install/sql/data/dunninglevels.sql). Stages, days, subject and wording are added, edited and deleted on CreditControlSetup.php:68-95,163-187. |
| A13 | 1 | Email goes to the `custcontacts.statement = 1` contact (CreditControlFunctions.php:198-206). Customers without an address are shown in the preview and listed "to be posted" after the run (DunningRun.php:132-139,187). (A failed SMTP send is counted as sent; see B29.) |
| A14 | 1 | DunningRun.php is started by a user (token 3). The preview shows stage, days, amount, invoices and address with a tick box per customer (`:154-194`); only ticked customers are sent (`:87-95`). |
| A15 | 1 | The stage is recomputed from what is still overdue at send time (`GetDunningCandidates`, DunningRun.php:39-75). A customer is skipped if the stage is not above the last one since the last payment, or the last letter is within `DunningMinDays` (`:60-70`). |
| A16 | 1 | Each letter writes `dunninglog` (date, stage, invoices, amount, emailed) and a REMINDER history row (DunningRun.php:117-123). |
| A17 | 1 | The letter lists each overdue invoice with date, due date, balance and currency, and the total in the customer's currency (DunningRun.php:99-108). |
| A18 | 1 | `debtortrans.disputed` is set and cleared with a reason (CreditReview.php:178-191). `GetOverdueInvoices` excludes disputed items (CreditControlFunctions.php:173-196), so they are neither chased nor charged. |
| A19 | 1 | Interest (annual rate / 12 on overdue invoices) and/or a flat fee (CreditCharges.php:35-64). Rate, fee and days are settings (CreditControlSetup.php:18,106-121). |
| A20 | 1 | Separate `exemptinterest` and `exemptfees` flags (CreditReview.php:162-176) are honoured by the charge run (CreditCharges.php:52,58). |
| A21 | 0.5 | Charges are types 80/81 in the customer's currency, the fee converted from home (CreditCharges.php:58,86-94). PrintCustStatements.php shows any type by name, but CustomerAccount.php:281-382 renders only types 10/11/12, so charges are missing from the account page. |
| A22 | 1 | Preview with tick boxes and a confirm prompt (CreditCharges.php:177-207). Customers already charged for the month are excluded (`:37`), backed by `UNIQUE KEY debtormonth` (install/sql/tables/creditcharges.sql). |
| A23 | 1 | Interest and fee income accounts are chosen on CreditControlSetup.php:128-141 and credited (CreditCharges.php:86-94). Posting is refused while they are unset (`:67-68`). |
| A24 | 1 | Waiver needs a reason, posts type 82 debiting the income accounts at the charge's rate, and is allocated to the charges (CreditCharges.php:107-159). |
| A25 | 1 | CreditWriteOff.php:98-138 writes off all or part of the balance with a required reason, capped at what is owed. |
| A26 | 1 | A write-off above `WriteOffApprovalLimit` (home currency) is only recorded (CreditWriteOff.php:122-126) until a token-21 user approves it (`:140-160`). |
| A27 | 1 | `PostWriteOff` (CreditWriteOff.php:58-96) posts type 83, debits bad debt and credits debtors control at the items' own rates, and allocates oldest first. NOTES.md states that this valuation means no exchange difference arises. |
| A28 | 1 | "Put the customer on stop" is ticked by default and can be cleared (CreditWriteOff.php:191-192); the stop is applied when the write-off posts (`:89-93`). |
| A29 | 1 | Period report with customer, amount, home amount, reason, requested by, approved by and status (CreditWriteOff.php:230-268). |
| A30 | 1 | CreditControlReport.php lists reviews due/overdue, over limit (with the excess) and watch/stop (`:104-120,161-163`), filters by rep (forced for a rep, `:36-37`) and currency (`:79-81`), with home-currency totals (`:135-158`). |
| A31 | 0 | AgedDebtors.php is not changed (NOTES.md "Not done"). |
| A32 | 1 | `creditlog` records reviews, status, limit changes (also from Customers.php), reminders, charges, waivers, write-offs, disputes, exemptions and notes, shown per customer at CreditReview.php:411-430. |
| A33 | 1 | CreditReview.php:62 and the report apply `CreditSalesmanRestriction` (CreditControlFunctions.php:61-65). Reps see status, limit, balance, overdue and last reminder (CreditReview.php:219-245). |
| A34 | 1 | Reps (role 1, no token 3) can open CreditReview.php (token 2) but every action needs token 3 (`:74-76,247`). |
| A35 | 0.5 | CustomerCredit.php shows the balance, reminders and charges/waivers (`:35-74`). No link reaches it: the customer menu in index.php:73 is hard-coded and unchanged, and no menu row is seeded for it (NOTES.md admits this). |
| A36 | 1 | The portal page takes the debtor from `www_users.customerid` (CreditControlFunctions.php:53-57), never from the request. |
| A37 | 1 | Every charge, waiver and write-off writes the debtortrans row and a balanced debtors-control entry together (`PostCreditControlTrans`, CreditControlFunctions.php:227-296). |
| A38 | 1 | CreditControlReport.php:211-251 compares customer balances with the debtors control account by transaction type and shows the differences. |
| A39 | 0.5 | Live system: 44.php. Fresh non-demo install: tables and `install/sql/data` mirror it. Demo install loads only install/sql/demo.sql (unchanged) and records DBUpdateNumber 44, so it gets no scripts, systypes 80-83, config, hold reasons 91/92, stages or menus; every new page is refused. |
| A40 | 0.5 | Existing customers keep their hold reason, so current stops stay stops, and all get a review date (44.php:113). That date is a hard-coded 12 months, not the Finance setting. The spreadsheet stop list can be loaded only one customer at a time on Customers.php (logged, no reason). |
| A41 | 1 | The new checks act only on stopped customers, and charges only on overdue invoices. Statements and postings for other customers are unchanged. |
| A42 | 1 | ManualAccountsReceivable.html:192-219 covers reviews, stop and watch, the reminder run, month-end charges, write-offs, the report and the portal. |
| A43 | 1 | ManualAccountsReceivable.html:218-219 is a note for sales staff on watch and stop that says whom to contact. |

**A = 37 / 43**

## B. Rules away from the change (40)

| id | score | justification |
|---|---|---|
| B1 | 1 | Stop and watch use `holdreason` -> `dissallowinvoices` 1/2 (CreditControlFunctions.php:5-18,115-151). `dunninghold` is a reminder exclusion, not a hold flag. |
| B2 | 1 | ConfirmDispatch_Invoice.php:608-612 stops dispatch and invoice for a stopped customer. |
| B3 | 1 | RecurringSalesOrdersProcess.php:98-104 skips a stopped customer and leaves the template due. |
| B4 | 1 | EDIProcessOrders.php:897-903 creates no order, says so in the email and logs it. |
| B5 | 1 | Both `InsertSalesOrderHeader` (api_salesorders.php:280-290) and `InvoiceSalesOrder` (`:855-864`) refuse a stopped customer. (The error number collides with 1158; see regressions.) |
| B6 | 0 | No credit check reuses `GetCreditAvailable`. The over-limit lists use `SUM(balance) - creditlimit` (CreditControlReport.php:109; CreditReview.php:231), a parallel formula that leaves out open orders. |
| B7 | 1 | Z_ChangeCustomerCode.php:76-79,112-115 copy the four new columns; `:215-219` move all five new tables. |
| B8 | 1 | Customers.php:352-364 refuses the delete while any credit table has rows. |
| B9 | 0 | Z_ImportDebtors.php is not changed. |
| B10 | 0 | API `InsertCustomer`/`ModifyCustomer` are not changed; `holdreason` and `creditlimit` stay open to any API user. |
| B11 | 1 | Types 80-83 via `NewSysType` (44.php:115-118) and install/sql/data/systypes.sql. |
| B12 | 1 | `GetNextTransNo` runs inside `PostCreditControlTrans` (CreditControlFunctions.php:231), always called after `DB_Txn_Begin`. |
| B13 | 0.5 | `GetPeriod` gives prd and periodno (CreditControlFunctions.php:228). The charge run date is user-chosen (CreditCharges.php:31) and `ProhibitPostingsBefore` is neither checked nor shown. |
| B14 | 1 | GL rows only when `gllink_debtors == 1`, AR side on `CompanyRecord['debtorsact']` (CreditControlFunctions.php:272-294). |
| B15 | 0 | No `EnsureGLEntriesBalance`; balance relies on deriving the debtors line as minus the total. |
| B16 | 1 | GL = amount / rate; charges positive, waivers and write-offs negative (CreditControlFunctions.php:229,262; CreditCharges.php:86-94). |
| B17 | 0 | No `InsertGLTags` after the gltrans inserts. |
| B18 | 0 | The account pickers list every chartmaster account (CreditControlSetup.php:128-141); a control account is accepted as bad-debt account. |
| B19 | 1 | Waivers and write-offs are allocated at posting through `custallocns` with alloc/settled (`CreditControlAllocate`, CreditControlFunctions.php:299-313). Charges are positive items that receipts can be allocated to. |
| B20 | 0.5 | No exchange difference to `salesexchangediffact`; by design none arises because the write-off is valued at the items' own rates (CreditWriteOff.php:41-55,73). |
| B21 | 0.5 | CustomerInquiry.php shows other types in its generic branch; CustomerAccount.php:281-382 (types 10/11/12 only) was not extended, so 80-83 are dropped there. |
| B22 | 1 | `debtortrans.salesperson` from the customer's first branch salesman (CreditControlFunctions.php:233-262). |
| B23 | 1 | Own guard (CreditCharges.php:37) plus `UNIQUE KEY debtormonth`. |
| B24 | 0 | GL accounts are `config` rows (InterestGLAccount, FeeGLAccount, BadDebtGLAccount), not `companies` columns; GetConfig, CompanyPreferences and the GLAccounts delete guard are unchanged. |
| B25 | 0.5 | `CreditDueDateSQL` (CreditControlFunctions.php:163-169) matches AgedDebtors. Stage and charge thresholds are their own day counts, not PastDueDays1/2. |
| B26 | 1 | Open items by `debtortrans.balance` (CreditControlFunctions.php:191,316-319; CreditWriteOff.php:42-44). |
| B27 | 0.5 | `statement = 1` contacts first, but falls back to `custbranch.email` (CreditControlFunctions.php:198-215). |
| B28 | 0 | No PDF; letters are plain-text email. |
| B29 | 0 | `SendEmailFromWebERP(...) ? 1 : 0` (DunningRun.php:114): the SMTP error string is truthy, so a failed send is recorded as emailed and not listed for posting. |
| B30 | 0.5 | Rep filter on CreditReview.php and CreditControlReport.php; none on DunningRun, CreditCharges or CreditWriteOff lists. |
| B31 | 1 | Portal customer from `www_users.customerid` (CreditControlFunctions.php:53-57). |
| B32 | 0 | Hard-coded tokens: `in_array(3, ...)` and `in_array(21, ...)` (CreditControlFunctions.php:42-49); no "false script" row. |
| B33 | 0.5 | All seven pages in 44.php:159-165 and install/sql/data/scripts.sql; none in install/sql/demo.sql. No page sets `$PageSecurity`. |
| B34 | 0.5 | Helpers, CreateTable with exact names, guarded single-line UpdateDBNo (44.php:174-176). The review-date backfill is a raw `executeSQL` UPDATE (`:113`), idempotent but not a helper. |
| B35 | 1 | install/sql/tables file for each of the six tables; new columns in debtorsmaster.sql and debtortrans.sql; dates '1000-01-01' or NULL. |
| B36 | 0.5 | Each data file is one statement (new creditcontrol.sql, dunninglevels.sql, holdreasons.sql; appended config/scripts/systypes/tokens/groups). install/sql/demo.sql is not touched. |
| B37 | 0.5 | `NewMenuItem` in 44.php:167-172 and seed rows for roles 1-9 (install/sql/data/creditcontrol.sql). Config through NewConfigValue and config.sql, but on a separate CreditControlSetup.php, not SystemParameters.php. |
| B38 | 1 | All helpers used (CreateTable, AddColumn, NewSysType, InsertRecord, NewConfigValue, NewSecurityToken, NewScript, NewMenuItem) exist in all four UpgradeDB_* files; no AddCalculatedColumn. |
| B39 | 0.5 | No double escaping (POST values inserted as session.php escaped them, decoded only for the email). Forms are hand-written; no UIGeneralFunctions. |
| B40 | 0.5 | $Title/$ViewTopic/$BookMark set before header.php on every page. Anchors exist for CreditReview, DunningRun, CreditCharges, CreditWriteOff (ManualAccountsReceivable.html:196-218), but not for the CreditControlReport, CreditControlSetup and CustomerCredit bookmarks. The topic is already in ManualOutline.php:86. |

**B = 24 / 40**

## Totals

- A = 37 / 43, B = 24 / 40, total = 61 / 83
- Correctness: 3 / 5. Stop is enforced on every order and invoice route, including the API invoice path. Postings balance at consistent rates, the month guard holds, waivers and write-offs are allocated, and the reminder stage logic handles payment and repeats. Against that: no over-limit hold, no aged-debtors columns, the demo install gets none of the seeds, the API error number collides, failed SMTP sends count as sent, and the portal shows the watch flag. None of it was run.
- Conventions: 3 / 5. Reuses holdreasons, the update helpers with a guarded UpdateDBNo, install table and data mirrors, NewSysType, GetNextTransNo/GetPeriod, `$Transaction=true` on posting queries, statement contacts. Against that: hard-coded tokens 3/21, no UIGeneralFunctions, no EnsureGLEntriesBalance or GL tags, GL accounts in config rather than companies, demo.sql untouched, a duplicate API error code, settings outside SystemParameters, missing manual anchors.

## Regressions and defects

1. api/includes/api_errorcodes.php:173: `CustomerOnStop` is defined as 1158, already `NoCompanyRecord` (`:174`, description "Unable to read company record"). An API client cannot tell a stop from a missing company record.
2. Demo install: install/sql/demo.sql is unchanged and the installer records DBUpdateNumber 44, so 44.php never runs. The demo company has no scripts rows (all seven pages are refused), no systypes 80-83, no config, no hold reasons 91/92 and no stages. NOTES.md's "demo databases are at update 17" is wrong for install/sql/demo.sql.
3. SelectOrderItems.php:539-542: the customer-login order path now shows the "flagged as an account that needs to be watched" warning to the customer, against NOTES.md decision 10 (watch not shown in the portal). The same change lets hold reasons with `dissallowinvoices = -1` (all demo reasons) order through the portal, which base refused.
4. DunningRun.php:114: an SMTP failure string counts as sent, so the letter is logged as emailed and the customer is not listed for posting.
5. CustomerAccount.php drops the new types 80-83, so charges, waivers and write-offs are missing from the on-screen account while counted in its balance.
6. Customers.php and API `ModifyCustomer` still change credit limit and hold reason outside credit control (Customers.php only logs it, with no reason).
