# t12 credit control, try 7, implementation B: checklist grading

Graded blind from B.diff and the workspace after the run (paths below are in
that workspace), against base 4cb937f. Code checked, not NOTES.md (NOTES.md
used only for open-question decisions). 1 met / 0.5 partly / 0 missed.

## A. BRD requirements

| # | score | evidence |
|---|---|---|
| A1 BR-01 review record | 1 | CreditControl.php:101-175 inserts creditreviews (date, userid, outcome, old/new limit, notes, nextreview) |
| A2 BR-02 next review date for every customer | 0.5 | Customers.php:249 + includes/CreditControlFunctions.php:143 (CreditReviewMonths) for new customers; sql/updates/44.php:13 sets existing (+12 months). Customers made by API InsertCustomer / Z_ImportDebtors get none (1000-01-01, "due now"); no shorter period for higher-risk customers |
| A3 BR-03 review history kept, immutable | 1 | CreditControl.php:466-486 read-only list; no edit/delete code anywhere |
| A4 BR-04 limit updated within the review | 1 | CreditControl.php:141-171 review insert + debtorsmaster.creditlimit update in one transaction; Customers.php UPDATEs no longer write creditlimit/holdreason (diff Customers.php:155-190) |
| A5 BR-05 stop/unstop with reason, who, when | 1 | CreditControl.php:178-187 -> includes/CreditControlFunctions.php:458-478 (holdreason update + creditlog with userid, NOW(), note) |
| A6 BR-06 stop blocks every route, and dispatch/invoice | 0.5 | DeliveryDetails.php:333-345, EDIProcessOrders.php:898-910, RecurringSalesOrdersProcess.php:45,95, api/includes/api_salesorders.php:282-291, ConfirmDispatch_Invoice.php:156,620. Not covered: API InvoiceSalesOrder (dispatch/invoice of existing orders through the web-shop API) and CounterSales.php (still only warns) |
| A7 BR-07 only credit control changes stop/limit | 0.5 | Token 21 on all credit pages (44.php:1872-1878), Customers.php:29,210,577,604 read-only fields. API ModifyCustomer still lets any API user write holdreason/creditlimit; CreditStatus.php (token 3) can flip a reason's stop/watch meaning with no log |
| A8 BR-08 watch: supply + warning + list | 1 | SelectOrderItems.php:542 lets watch through (staff warning existing at :439-441); CreditControlReport.php order list includes dissallowinvoices 2; SelectCustomer.php:153 banner |
| A9 BR-09 status visible wherever staff look/take order | 1 | SelectCustomer.php:153, CustomerInquiry.php:171-173, CustomerAccount.php:234-236, CreditControl.php status row, SelectOrderItems warnings |
| A10 BR-10 over-limit orders held | 0.5 | DeliveryDetails.php:345 (new orders), EDIProcessOrders.php, RecurringSalesOrdersProcess.php:120-122, release CreditControlReport.php:21-29, block ConfirmDispatch_Invoice.php. API holds only if the customer is already over the limit before lines are added (api_salesorders.php:291, value 0); modified orders never held |
| A11 BR-11 web shop shows account on hold | 1 | CustomerCreditHistory.php:59-62 portal message; CustomerAccount.php:234 ON STOP for portal; API returns CustomerOnStop 1174 (api_errorcodes.php) instead of silent failure |
| A12 BR-12 escalating configurable stages | 1 | dunningstages table; CreditControlParameters.php stage add/edit/delete (days, subject, wording); 3 seeds 44.php:1859-1861 |
| A13 BR-13 email to accounts contact, list no-email | 1 | CreditControlDunning.php:75 (custcontacts statement=1, IsEmailAddress, de-dup); post list CreditControlDunning.php preview "have to be posted" |
| A14 BR-14 user-run with preview and exclusions | 1 | CreditControlDunning.php preview with per-customer tick, send at :99 only ticked |
| A15 BR-15 only still-overdue move up; no repeat stage soon | 1 | CreditControlDunning.php:40-70 (recomputed at send :109, MinDays :59, stage > last stage) |
| A16 BR-16 every reminder recorded | 1 | CreditControlDunning.php:136 dunningletters (date, stage, amount, currcode, invoices) + creditlog |
| A17 BR-17 customer currency, overdue invoices | 1 | CreditDunningInvoiceText in CreditControlDunning.php ({invoices}, currcode amounts) |
| A18 BR-18 disputed not chased/charged | 1 | CreditControl.php:190-207 flag; CreditControlFunctions.php:244-270 excludes disputed from overdue/maxdays; CreditControlCharges.php candidate skips disputed |
| A19 BR-19 interest and/or fee, settings | 1 | CreditControlCharges.php:47-82; settings CreditInterestRate/CreditLateFee/CreditChargeDays (CreditControlParameters.php) |
| A20 BR-20 exemptions | 1 | CreditControl.php:209-216; CreditControlCharges.php:72-75 |
| A21 BR-21 own currency, separate items, statement | 1 | CreditControlCharges.php posts type 15 per charge in customer currency; PrintCustStatements.php type 15 line shows reference; CustomerAccount.php type 15 branch |
| A22 BR-22 preview + confirm; no double month | 1 | CreditControlCharges.php preview :181-228, post :103; latecharges UNIQUE onechargepermonth + check :63-71 |
| A23 BR-23 GL income accounts chosen by Finance | 1 | companies.latechargeinterestact/latechargefeeact set on CreditControlParameters.php; used in CreditControlCharges.php |
| A24 BR-24 waive with reason, reaches ledger | 1 | CreditControl.php:218-266 negative type 15 + GL reversal + allocation |
| A25 BR-25 write off all or part with reason | 1 | CreditControlWriteOffs.php:32-95 |
| A26 BR-26 above limit needs FD approval | 1 | CreditControlWriteOffs.php:83; CreditControlApprovals.php (token 22, self-approval refused :31) |
| A27 BR-27 reduces balance, bad debt incl. FX difference | 1 | CreditControlFunctions.php:371-440 credit allocated to oldest debts, GL at carrying value to baddebtact |
| A28 BR-28 auto stop unless decided otherwise | 1 | CreditControlWriteOffs.php StopCustomer tick default from CreditWriteOffAutoStop; CreditControlFunctions.php post-write-off stop |
| A29 BR-29 write-off report | 1 | CreditControlWriteOffs.php:146-200 (customer, amount, reason, requestedby, approvedby, period) |
| A30 BR-30 credit control report, filters, home totals | 1 | CreditControlReport.php review/over-limit(by)/watch/stop tables, rep + currency filters, home-currency totals |
| A31 BR-31 aged debt shows status, limit, last stage | 1 | AgedDebtors.php:314 + CreditControlFunctions.php:99-111 |
| A32 BR-32 audit history per customer | 1 | creditlog written for REVIEW/LIMIT/status/DISPUTE/EXEMPT/WAIVE/CHARGE/REMINDER/WRITEOFF; shown CreditControl.php:486-505 |
| A33 BR-33 reps see own customers only | 1 | CustomerCreditHistory.php:37-44; CreditControlReport.php:33 forced filter; existing SalesmanLogin checks on inquiry pages |
| A34 BR-34 reps see but cannot change | 1 | change actions only on token-21 pages; sales roles not granted 21 |
| A35 BR-35 portal: reminders, charges, balance | 1 | CustomerCreditHistory.php (token 1), index.php portal link |
| A36 BR-36 own account only | 1 | CustomerCreditHistory.php:23-25 forces $_SESSION['CustomerID'] |
| A37 BR-37 balances agree with control account | 1 | every posting debits/credits CompanyRecord debtorsact at amount/rate; Z_CheckDebtorsControl.php:128 counts type 15 |
| A38 BR-38 find reasons for differences | 1 | Z_CheckDebtorsControl.php:181-240 unmatched debtortrans / gltrans lists |
| A39 BR-39 live system and new install | 0.5 | Upgrade path 44.php fine. New install broken: companies gains 3 columns but positional INSERT INTO companies VALUES in includes/InstallFunctions.php:505 and install/sql/demo.sql:14 not updated; install/sql/data/creditcontrol.sql is 48 statements in one file (installer runs one DB_query per file); nothing in install/sql/demo.sql |
| A40 BR-40 go-live status, review date, stop list | 1 | 44.php:13 review dates; CreditControlParameters.php:86-130 CSV loader (stop/watch/normal, limit, date) |
| A41 BR-41 no change for non-overdue customers | 1 | charges/reminders only touch overdue docs; statement change only for type 15; hold behaviour behind CreditHoldOverLimitOrders |
| A42 BR-42 staff guide | 1 | doc/Manual/ManualAccountsReceivable.html new Credit Control section (reviews, stop/watch, run, charges, write-offs, report) |
| A43 BR-43 sales staff note | 1 | ManualAccountsReceivable.html "What sales staff need to know" |

**A = 40.5 / 43**

## B. Rules away from the change

| # | score | evidence |
|---|---|---|
| B1 hold via holdreason/dissallowinvoices | 1 | CreditControlFunctions.php:45-70, 458-478; CreditStatus.php:109 now writes 0/1/2; no parallel customer flag (salesorders.creditheld is order-level) |
| B2 enforced at ConfirmDispatch_Invoice | 1 | ConfirmDispatch_Invoice.php:156, 620 |
| B3 enforced in RecurringSalesOrdersProcess | 1 | RecurringSalesOrdersProcess.php:45, 95 |
| B4 enforced in EDIProcessOrders | 1 | EDIProcessOrders.php:898-910 |
| B5 enforced in API order/invoice functions | 0.5 | api_salesorders.php:282-291 InsertSalesOrderHeader only; InvoiceSalesOrder, ModifySalesOrderHeader, InsertSalesOrderLine unchanged |
| B6 CheckCreditLimits + GetCreditAvailable reuse | 1 | CreditControlFunctions.php:153-163 (CheckCreditLimits 0 = off, GetCreditAvailable) |
| B7 Z_ChangeCustomerCode | 1 | Z_ChangeCustomerCode.php:76, 111 (new columns), :259 (5 new tables) |
| B8 Customers.php delete guard | 0 | Customers.php delete chain unchanged; creditreviews/creditlog/dunningletters/latecharges/writeoffs neither block nor are deleted |
| B9 Z_ImportDebtors | 0 | not changed |
| B10 API ModifyCustomer/InsertCustomer | 0 | not changed; holdreason/creditlimit/new columns writable via API |
| B11 systypes for new transactions | 1 | reuse of type 15 "Journal - Debtors" with reason (44.php:1886 comment, NewSysType) |
| B12 GetNextTransNo inside transaction | 1 | CreditControlFunctions.php:309, callers open DB_Txn_Begin first (CreditControl.php waive, CreditControlCharges.php, :417) |
| B13 GetPeriod; ProhibitPostingsBefore | 0.5 | CreditControlFunctions.php:308 GetPeriod; no check or display of ProhibitPostingsBefore (charges dated to a chosen past month end) |
| B14 gllink_debtors gate, debtorsact | 1 | CreditControlFunctions.php:344; debtorsact used in all GL line sets |
| B15 EnsureGLEntriesBalance and stop on imbalance | 0.5 | called before commit (CreditControl.php:262, CreditControlCharges.php:172, CreditControlFunctions.php write-off) but no stop/re-check; charges loop continues after a silent rollback |
| B16 amount/rate, signs | 1 | charges positive (CreditControlCharges.php), waivers/write-offs negative, GL = amount / rate |
| B17 InsertGLTags after gltrans | 0 | no InsertGLTags call (CreditControlFunctions.php:344-362) |
| B18 write-off account not a control account | 0.5 | picker lists only P&L accounts (CreditControlParameters.php:157) but save handler only checks chartmaster existence; no ProhibitJournalsToControlAccounts check |
| B19 allocation of new types | 1 | waivers/write-offs self-allocated (CreditControlFunctions.php:273-289); type 15 charges are unsettled debits, so CustomerAllocations.php (settled=0 list) can allocate receipts to them |
| B20 FX difference to salesexchangediffact | 0.5 | difference folded into bad debt via per-invoice carrying value and synthetic EffectiveRate (CreditControlFunctions.php:400-420); no diffonexch / salesexchangediffact |
| B21 CustomerAccount/CustomerInquiry show new types | 1 | CustomerAccount.php new type 15 branch (diff :385-405); CustomerInquiry already renders other types as misc rows |
| B22 debtortrans.salesperson | 1 | CreditControlFunctions.php:325 (branch salesman) |
| B23 no double charge | 1 | latecharges UNIQUE (debtorno, chargemonth, chargetype) + CreditControlCharges.php:63-71 |
| B24 two GL accounts in companies everywhere | 0 | columns added and Z_ChangeGLAccountCode.php:90; missing CompanyPreferences, GLAccounts delete guard, positional companies INSERTs (InstallFunctions.php:505, install/sql/demo.sql:14) |
| B25 one due-date rule, PastDueDays bands | 0.5 | CreditControlFunctions.php:210-240 matches AgedDebtors rule; bands are own dunning stages, not PastDueDays1/2 |
| B26 open items by balance | 1 | CreditControlFunctions.php:210-240 balance > 0.005 |
| B27 recipients custcontacts.statement=1 | 1 | CreditControlDunning.php:75 |
| B28 Dompdf not Cpdf | 1 | no PDFs; plain-text letters (no Cpdf/PDFStarter) |
| B29 === true; temp file | 1 | CreditControlDunning.php:127; no temp files |
| B30 SalesmanLogin on every list/run/report | 0.5 | CreditControlReport.php:33, CustomerCreditHistory.php:37; not on CreditControl.php search, dunning run, charges, write-off report |
| B31 customer login own debtorno | 1 | CustomerCreditHistory.php:23-25 |
| B32 permission via scripts entry, not hardcoded token | 1 | CreditControlFunctions.php:15-23 PageSecurityArray lookup |
| B33 pages in scripts (NewScript + scripts.sql + demo.sql) | 0.5 | 44.php NewScript x8; seeds only in multi-statement install/sql/data/creditcontrol.sql, nothing in scripts.sql/demo.sql; no $PageSecurity in pages |
| B34 44.php idempotent helpers, guarded UpdateDBNo | 1 | 44.php AddColumn/CreateTable (exact names, no ENGINE)/NewConfigValue/InsertRecord/NewScript/NewMenuItem/NewSysType; guarded one-line UpdateDBNo at end; one idempotent executeSQL UPDATE |
| B35 install table files, 1000-01-01 | 1 | install/sql/tables/{creditreviews,creditlog,dunningstages,dunningletters,latecharges,writeoffs}.sql, altered debtorsmaster/debtortrans/salesorders/companies |
| B36 seeds in data/*.sql and demo.sql, one statement each | 0 | creditcontrol.sql has 48 statements (fails in installer); demo.sql untouched |
| B37 menu rows all roles; config seeds + SystemParameters | 0.5 | NewMenuItem + rows for roles 1-9 (in broken file); NewConfigValue yes, not in config.sql/demo.sql, own settings page instead of SystemParameters.php |
| B38 helpers in all UpgradeDB variants | 1 | all used helpers exist in mysqli/mysql/mariadb/postgres; no AddCalculatedColumn |
| B39 UIGeneralFunctions; no double escaping | 0.5 | all forms hand-written; escaping mostly right but CreditControlFunctions.php:472 DB_escape_string on already-escaped DebtorNo |
| B40 Title/ViewTopic/BookMark; manual anchors | 1 | every new page sets them before header.php; ManualAccountsReceivable.html anchors for every BookMark; AccountsReceivable already in ManualOutline.php |

**B = 29 / 40**

## Scores

- A: 40.5 / 43
- B: 29 / 40
- Total: 69.5 / 83
- Correctness: 3 / 5. Broad and coherent feature with consistent ledger postings, but a fresh install breaks.
- Conventions: 3 / 5. It uses the upgrade helpers, script-table permissions, `__()` and the manual. Against that: no UIGeneralFunctions, a multi-statement seed file, no demo.sql, no InsertGLTags, its own settings page and stray whitespace in Customers.php.

## Regressions

1. New installs fail. Positional `INSERT INTO companies VALUES` in includes/InstallFunctions.php:505 and install/sql/demo.sql:14 no longer match the column count (3 new companies columns), so there is no company record.
2. install/sql/data/creditcontrol.sql has 48 statements in one file, so the installer's single DB_query fails. No tokens, scripts, config, hold reasons or stages get seeded, and the demo install gets none either.
3. With the default CheckCreditLimits=1 ("warn"), over-limit orders are now held (CreditHoldOverLimitOrders defaults to 1).
4. Customers.php: nobody can edit an existing customer's credit limit or status there any more. This is intended, but it changes the page.
5. EnsureGLEntriesBalance can roll back without stopping the run, and later statements then autocommit.
6. Customers.php delete leaves orphaned credit-control rows. The API (ModifyCustomer, InvoiceSalesOrder) bypasses stop and the limit.
