# t12 credit control, try 7, implementation A: checklist grading

Graded from the code in the workspace (paths relative to the workspace root),
not from NOTES.md. NOTES.md was used only for the decisions on the BRD's open
questions (section 9). Scores: met 1, partly 0.5, missed 0.

## A. BRD requirements

| # | Score | Evidence |
|---|---|---|
| A1 BR-01 review record | 1 | CreditControlCustomer.php:100-167 stores date, user, outcome (confirmed/raised/reduced/watch/stop), old/new limit, notes, next date in `creditreviews` (sql/updates/44.php:36-47) |
| A2 BR-02 next review date for every customer | 1 | new customers: Customers.php:308, Z_ImportDebtors.php:431, api_customers.php:367 via CreditControlFunctions.php:148-158; period set by Finance in CreditControlSetup.php:201-205. There is one standard period for everyone; the review sets a shorter date per customer |
| A3 BR-03 history kept, immutable | 1 | listed at CreditControlCustomer.php:415-432; the application has no edit or delete path for `creditreviews` |
| A4 BR-04 limit changes inside the review | 1 | CreditControlCustomer.php:130-159: one transaction for the review insert, the `debtorsmaster.creditlimit` update and the log |
| A5 BR-05 stop/unstop with reason, who, when | 1 | CreditControlCustomer.php:170-188 requires a reason; CreditControlFunctions.php:126-145 logs user and time in `creditlog` |
| A6 BR-06 no orders by any route, no dispatch/invoice | 0.5 | new orders blocked at DeliveryDetails.php:340, api_salesorders.php:280-282, EDIProcessOrders.php:897-902 and RecurringSalesOrdersProcess.php:96-100; dispatch is blocked at ConfirmDispatch_Invoice.php:114, 623. The API `InvoiceSalesOrder` (api_salesorders.php:796) still invoices existing orders for a customer on stop |
| A7 BR-07 only CC/FD change stop or limits | 0.5 | Customers.php:28-72 disables the fields and ignores them server side; the credit pages need token 21. Gaps: the API `ModifyCustomer` (api_customers.php:386) still changes limit and holdreason, and CreditStatus.php (token 3, AR clerk) can redefine what the stop status means |
| A8 BR-08 watch: supplied, warned, listed | 1 | the existing warning at SelectOrderItems.php:438-440; the portal fix at SelectOrderItems.php:540; watched orders listed at CreditControlOrders.php:87-88, 117 |
| A9 BR-09 status visible | 1 | CustomerInquiry.php:166-182, CustomerAccount.php:232-239, AgedDebtors.php:281, 305, CreditControlCustomer.php:264, order entry warnings |
| A10 BR-10 over-limit orders held | 1 | CheckCreditLimits option 3 (SystemParameters.php:479) runs CreditControlHoldOrderIfOverLimit (CreditControlFunctions.php:192-222) at DeliveryDetails.php:556, 770, EDIProcessOrders.php:1019, RecurringSalesOrdersProcess.php:216 and api_salesorders.php:533; held orders are blocked at invoicing (CreditControlFunctions.php:163-178) and released at CreditControlOrders.php:23-40 |
| A11 BR-11 web shop tells customer account on hold | 0.5 | portal: CustomerCreditAccount.php:88-91. The web-shop API error `CustomerOnCreditStop` reuses code 1158 (api_errorcodes.php:173), which is already `NoCompanyRecord` and described as "Unable to read company record" (api_errorcodes.php:174, 351), so the shop gets the wrong message |
| A12 BR-12 stages configurable | 1 | CreditControlSetup.php:103-156 (add/delete stage, days, subject, wording); seeded with three stages at 44.php:241-247 |
| A13 BR-13 email to accounts contact; no-email listed | 1 | CreditControlReminders.php:66-75 (`custcontacts.statement=1`), 170-181, 212-223 |
| A14 BR-14 run with preview and exclusions | 1 | CreditControlReminders.php:227-250 preview with tick boxes; 158-166 sends only the ticked customers |
| A15 BR-15 only move up while overdue; no repeat | 1 | CreditControlFunctions.php:284-296 (stage from unpaid chased items); CreditControlReminders.php:119-134 (next stage only, gap days) |
| A16 BR-16 each reminder recorded | 1 | CreditControlReminders.php:183-205 (`dunningletters` with date, stage, amount; `dunninglettersdetail` per invoice; log) |
| A17 BR-17 own currency, overdue invoices | 1 | CreditControlReminders.php:142-155 |
| A18 BR-18 disputed invoice not chased or charged | 1 | CreditControlCustomer.php:213-248; excluded at CreditControlFunctions.php:256-261 |
| A19 BR-19 interest/fee/both, settings | 1 | CreditControlCharges.php:55-111; settings at CreditControlSetup.php:207-229 |
| A20 BR-20 exemptions | 1 | CreditControlCustomer.php:191-210; applied at CreditControlCharges.php:100-105 |
| A21 BR-21 own currency, on account and statement as separate items | 0.5 | separate types 51/52 with a narrative (CreditControlFunctions.php:302-378) show on the statement and on CustomerInquiry. CustomerAccount.php:286-390 renders only types 10/11/12, so the charges do not appear on the customer account screen |
| A22 BR-22 preview, confirm, never twice | 1 | CreditControlCharges.php:196-219 preview with confirm; 92-105 skips a month already charged; UNIQUE `onceamonth` key at 44.php:131 |
| A23 BR-23 post to chosen income accounts | 1 | CreditControlCharges.php:149-158 with accounts from CreditControlSetup.php:224-227 |
| A24 BR-24 waive with reason, reaches ledger | 1 | CreditControlCharges.php:114-132, CreditControlFunctions.php:493-532 |
| A25 BR-25 write off all or part with reason | 1 | CreditControlWriteOffs.php:35-83 |
| A26 BR-26 FD approval above threshold | 1 | CreditControlWriteOffs.php:67-80, 86-117 (Finance Director only, cannot approve own request) |
| A27 BR-27 reduce balance, bad debt GL, currency difference | 1 | CreditControlFunctions.php:443-488 (type 53 credit, bad debt account); exchange difference at CreditControlFunctions.php:426-436 |
| A28 BR-28 auto stop unless CC decides | 1 | CreditControlWriteOffs.php:151-152 (ticked by default); CreditControlFunctions.php:481-486 |
| A29 BR-29 write-off report | 1 | CreditControlWriteOffs.php:191-240 (customer, amount, reason, requested by, approved by) |
| A30 BR-30 credit control report | 1 | CreditControlReport.php:24-190 (due reviews, over limit with amount over, watch/stop; rep and currency filters; home-currency totals) |
| A31 BR-31 aged debt shows status, limit, last stage | 1 | AgedDebtors.php:281-283, 305-312, 327-329 |
| A32 BR-32 per-customer audit history | 1 | `creditlog` written for reviews, status, limits, reminders, charges, waivers and write-offs; shown at CreditControlCustomer.php:435-449 and CustomerCreditAccount.php:137-152 |
| A33 BR-33 reps see own customers only | 1 | CreditControlFunctions.php:536-550; CustomerCreditAccount.php:67; CreditControlReport.php:24-26 |
| A34 BR-34 reps see but cannot change | 1 | Customers.php:28-29, 610, 640 (disabled fields); the credit pages need token 21 |
| A35 BR-35 portal shows reminders, charges, balance | 1 | CustomerCreditAccount.php:81-134, 155-180 (script token 1, which the customer role 7 has; menu rows for every role) |
| A36 BR-36 customer sees only own account | 1 | CustomerCreditAccount.php:23-25 |
| A37 BR-37 debtors agree with GL | 1 | every charge, waiver and write-off posts to `debtorsact` (CreditControlFunctions.php:365-376); CustomerBalancesMovement.php, DebtorsAtPeriodEnd.php and Z_CheckDebtorsControl.php:104 handle the new types |
| A38 BR-38 find why they differ | 1 | Z_CheckDebtorsControl.php:156-231 lists transactions that differ from their ledger posting and direct journals to the control account |
| A39 BR-39 live and new install | 1 | sql/updates/44.php; install/sql/tables/*.sql and install/sql/data/creditcontrol*.sql (the demo install is not covered; see B36) |
| A40 BR-40 go-live state | 1 | 44.php:254-265 gives every customer a review date and keeps the current status; CreditControlImport.php loads the stop list with a check-only first pass |
| A41 BR-41 no change for customers not overdue | 1 | debtorsmaster and debtortrans are not altered; the new behaviour applies only to customers on stop, watch, or overdue |
| A42 BR-42 staff guide | 1 | doc/Manual/ManualAccountsReceivable.html:204-270 covers every item |
| A43 BR-43 note for sales staff | 1 | ManualAccountsReceivable.html:263-265 |

**A = 41 / 43**

## B. Rules away from the change

| # | Score | Evidence |
|---|---|---|
| B1 hold = holdreason/dissallowinvoices | 1 | CreditControlFunctions.php:86-145, with no parallel flag (44.php:181-224 maps normal/watch/stop to holdreasons) |
| B2 dispatch/invoice | 1 | ConfirmDispatch_Invoice.php:114-123, 623-628 |
| B3 recurring | 1 | RecurringSalesOrdersProcess.php:96-100, 216-221 |
| B4 EDI | 1 | EDIProcessOrders.php:897-902 |
| B5 API order/invoice | 0.5 | order header blocked at api_salesorders.php:280; `InvoiceSalesOrder` (api_salesorders.php:796) and `ModifySalesOrderHeader`/`ModifySalesOrderLine` have no check |
| B6 CheckCreditLimits + GetCreditAvailable | 0.5 | the hold reuses GetCreditAvailable (CreditControlFunctions.php:206) under option 3; CreditControlReport.php:109, 156 uses its own formula, balance + open orders - limit |
| B7 Z_ChangeCustomerCode | 1 | Z_ChangeCustomerCode.php:251-256 renames all new debtorno tables; debtorsmaster has no new column |
| B8 Customers.php delete | 0.5 | Customers.php:390 deletes `debtorcredit`; the `creditlog` rows (for example NEWACCOUNT, written at Customers.php:309) and `creditreviews` rows are left orphaned |
| B9 Z_ImportDebtors | 1 | debtorsmaster has no new column; the review date is created at Z_ImportDebtors.php:431 |
| B10 API Modify/InsertCustomer | 0 | `ModifyCustomer`/`InsertCustomer` (api_customers.php:386, 362) still accept creditlimit/holdreason changes; NOTES admits the gap |
| B11 systypes | 1 | 44.php:153-156 NewSysType 51-54; install/sql/data/creditcontrol_systypes.sql; DatabaseTranslations.php |
| B12 GetNextTransNo in transaction | 1 | CreditControlFunctions.php:322, called inside DB_Txn_Begin (CreditControlCharges.php:142, CreditControlWriteOffs.php:62, 100) |
| B13 GetPeriod + ProhibitPostingsBefore | 0.5 | GetPeriod at CreditControlFunctions.php:323; nothing checks ProhibitPostingsBefore, so charges are back-dated to month end (CreditControlCharges.php:158) unchecked |
| B14 gllink_debtors, debtorsact | 1 | CreditControlFunctions.php:365-376, 427-436 |
| B15 EnsureGLEntriesBalance | 0 | never called in CreditControlFunctions.php or the pages |
| B16 amount/rate, signs | 1 | CreditControlFunctions.php:364-374 |
| B17 InsertGLTags | 0 | absent |
| B18 refuse control account for write-off | 0 | CreditControlSetup.php:66-74 checks only that the account exists |
| B19 allocation | 0.5 | write-offs and waivers are auto-allocated at posting (CreditControlFunctions.php:384-438); types 53/54 are not added to CustomerAllocations.php:481, 538, 578, so an unallocated remainder cannot be allocated later |
| B20 exchange difference | 1 | CreditControlFunctions.php:405, 426-436 to `salesexchangediffact` |
| B21 CustomerAccount/Inquiry show new types | 0.5 | CustomerInquiry shows them in its misc branch; CustomerAccount.php:286-390 is not extended and drops them |
| B22 salesperson | 1 | CreditControlFunctions.php:316, 360 |
| B23 no double charge | 1 | CreditControlCharges.php:92-105; UNIQUE key at 44.php:131 |
| B24 GL accounts in companies | 0 | the accounts are kept in `config` (44.php:235-237); no companies column, CompanyPreferences or GLAccounts delete guard |
| B25 due-date rule | 1 | CreditControlFunctions.php:226-231 matches AgedDebtors.php:39-46 |
| B26 open items by balance | 1 | CreditControlFunctions.php:260 |
| B27 statement=1 contacts | 1 | CreditControlReminders.php:68 |
| B28 Dompdf | 0.5 | no Cpdf, but letters are plain-text email or an HTML print page (CreditControlReminders.php:18-37, 172); no PDF |
| B29 SendEmailFromWebERP === true | 1 | CreditControlReminders.php:172-176 (no temp file) |
| B30 SalesmanLogin on every list/run/report | 0.5 | applied in CreditControlReport.php:24 and CustomerCreditAccount.php:67; not in the lists of CreditControlReminders.php:80-94, CreditControlCharges.php:57-79, CreditControlOrders.php:42-76, CreditControlWriteOffs.php:159-218 or CreditControlCustomer.php:42-47 |
| B31 customer own debtorno | 1 | CustomerCreditAccount.php:23-25 |
| B32 no hard-coded token numbers | 0 | `in_array(21, ...)` at CustomerInquiry.php:170; CC_TOKEN 21/22 at CreditControlFunctions.php:19-34 instead of a false script |
| B33 scripts in update + scripts seed + demo.sql | 0.5 | NewScript at 44.php:165-173 and creditcontrol_scripts.sql; nothing in install/sql/demo.sql. The pages set no $PageSecurity |
| B34 44.php helpers, guarded UpdateDBNo | 0.5 | helpers and guard are used (44.php:271-273); there is a raw `executeSQL` INSERT at 44.php:258 (idempotent through NOT IN, but against the rule) |
| B35 install tables, no zero dates | 1 | install/sql/tables/*.sql use '1000-01-01' |
| B36 seeds in data + demo.sql | 0.5 | data files are one statement each; install/sql/demo.sql is untouched, so a demo install has no tokens, scripts, menus, config or systypes |
| B37 menus every role; config via NewConfigValue + seeds + SystemParameters | 0.5 | menus: NewMenuItem 44.php:176-184 and seeds for roles 1-9; config: NewConfigValue and the seed are there, but the settings are on their own page, not SystemParameters.php (only option 3 is added there) |
| B38 helpers in all UpgradeDB variants | 1 | all helpers used exist in all four UpgradeDB_* files |
| B39 UIGeneralFunctions; no double escaping | 0 | the forms are hand-written; already-escaped POST text is escaped again (CreditControlFunctions.php:78 on $_POST notes and reasons; :523 waive reason) |
| B40 Title/ViewTopic/BookMark; manual anchors + ManualOutline | 0.5 | variables are set before header.php and the anchors exist (ManualAccountsReceivable.html:204-262); there is no ManualOutline.php entry |

**B = 26.5 / 40**

## Totals

- A 41/43, B 26.5/40, total 67.5/83
- Correctness 4/5: complete and coherent design on the existing credit status. Gaps: API invoicing on stop, the API error-code clash, CustomerAccount drops the charges, no GL balance check, no tags, no ProhibitPostingsBefore check.
- Conventions 3/5: idiomatic page skeletons, helpers and seeds. Against that: hard-coded tokens, no UIGeneralFunctions, double escaping, a raw SQL insert in the update, demo.sql missed, settings off SystemParameters/companies, no ManualOutline entry.

## Regressions

1. api/includes/api_errorcodes.php:173: `CustomerOnCreditStop` = 1158 collides with `NoCompanyRecord`, so API clients see "Unable to read company record".
2. install/sql/demo.sql is not updated: a demo install has the new tables but no tokens, scripts, menus, config or systypes 51-54. The pages cannot be reached and the posted types have no systypes row.
3. Customers.php:390: the delete leaves orphan `creditlog`/`creditreviews` rows.
4. CustomerAccount.php: interest, fee, waiver and write-off rows are silently omitted from the account screen.
5. Double-escaped text in `creditlog` descriptions and waiver reasons (display is partly masked by `double_encode=false`).
6. Charges post to a past month end with no ProhibitPostingsBefore check, and no gltrans tags.
7. api_customers.php:366-368: `InsertCustomer` creates the `debtorcredit` row before the debtorsmaster insert, which leaves an orphan if that insert fails.
