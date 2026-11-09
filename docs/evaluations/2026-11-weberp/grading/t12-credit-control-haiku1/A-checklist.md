# t12 credit control, run A: checklist grading

Inputs: blindhk/A.diff and the workspace blindhk/A/. All new files are listed with their own line numbers.
Changed: CounterSales.php. New: CreditReviews.php, CreditCustomerStatus.php, CreditControlReport.php,
CreditControlSettings.php, CreditWriteOffs.php, CreditWriteOffApprovals.php, CreditCustomerHistory.php,
includes/CreditControlFunctions.php (never included anywhere), install/sql/tables/{creditreviews,creditactions,
creditreminders,creditcharges,creditwriteoffs,creditconfig,Z_Upgrade_AddCreditControl,Z_InitializeCreditControl}.sql, NOTES.md.
No sql/updates/44.php, no scripts/menu rows, and no change to debtorsmaster.sql, data/demo seeds or the manual.

Three facts apply to many items below:
- **Pages are unreachable.** None of the new pages has a `scripts` row. session.php:333-337 looks up
  `$_SESSION['PageSecurityArray'][basename]`, finds it unset and shows "Security Permissions Problem" to every user.
- **No schema on the live system.** `creditstatus`, `nextreviewdate` and `disputed` exist only in
  install/sql/tables/Z_Upgrade_AddCreditControl.sql. There is no upgrade script. On a new install,
  CreateTables (includes/InstallFunctions.php:302) globs the files in ASCII order, so `Z_*` runs before
  `creditconfig.sql` and `debtorsmaster.sql`. Each file also holds several statements in one DB_query. Both
  Z_ files fail, and the installer reports "Database tables could not be created".
- **Nothing posts.** No debtortrans or gltrans row is written anywhere. Reminders, charges, disputes and portal
  features are "framework only" (the tables exist but no code fills them).

## A. BRD requirements

| # | Score | Evidence |
|---|---|---|
| A1 BR-01 record review | 0.5 | CreditReviews.php:39-57 stores date, user, outcome, limit, notes and next date. However, :37 runs `ConvertSQLDate()` on the user's dd/mm/yyyy input instead of FormatDateForSQL, so the next review date is stored wrong. The page is also unreachable (no scripts row). |
| A2 BR-02 auto next-review date for new customers | 0 | Customers.php is untouched. Z_Upgrade_AddCreditControl.sql:3 defaults the date to 1000-01-01, so every customer is "due" at once. DefaultReviewPeriod (CreditControlSettings.php:357) is never read. |
| A3 BR-03 history kept, immutable | 1 | CreditReviews.php:119-156 shows the history. The code has no update or delete path for creditreviews. |
| A4 BR-04 limit updated with review | 1 | CreditReviews.php:59-64 updates debtorsmaster.creditlimit in the same submit as the review insert (:39). |
| A5 BR-05 stop/unstop with reason, who, when | 1 | CreditCustomerStatus.php:10-15 requires a reason. :38-58 inserts into creditactions (userid, NOW(), old/new status) and updates creditstatus. |
| A6 BR-06 block every route + dispatch | 0.5 | Only CounterSales.php:132-136 checks the stop. SelectOrderItems.php, the web shop, EDIProcessOrders.php, RecurringSalesOrdersProcess.php and ConfirmDispatch_Invoice.php are untouched. |
| A7 BR-07 only CC/deputy/FD may change status or limit | 0 | No security token or scripts row, and no role check. NOTES.md defers this to "webERP roles". |
| A8 BR-08 watch: warn on order, CC sees watched orders | 0.5 | Warning only in CounterSales.php:136-138. SelectOrderItems.php has none. There is no list of orders for watched customers; CreditControlReport.php:113-122 lists customers, not orders. |
| A9 BR-09 status visible wherever staff look | 0 | Status shows only on the new (unreachable) pages and in CounterSales on watch/stop. SelectCustomer, CustomerInquiry and order entry are untouched. |
| A10 BR-10 over-limit orders held | 0 | No order hold. The report only lists over-limit customers (CreditControlReport.php:66-111). |
| A11 BR-11 web-shop on-hold message | 0 | Not implemented. |
| A12 BR-12 escalating reminder run, configurable stages | 0 | Only settings exist (CreditControlSettings.php:88-111), with exactly 3 hard-coded stages. No run sends anything. |
| A13 BR-13 email to accounts contact; list no-email | 0 | Not implemented. |
| A14 BR-14 weekly run with preview/exclusions | 0 | Not implemented. |
| A15 BR-15 advance only if still overdue; no repeat | 0 | GetLastReminderStage and GetLastReminderDate (includes/CreditControlFunctions.php:62-75) are never called. |
| A16 BR-16 reminder recorded | 0 | creditreminders.sql exists, but no code inserts into it. |
| A17 BR-17 customer currency, overdue invoices | 0 | No letters are produced. |
| A18 BR-18 mark invoice disputed | 0 | The column exists (Z_Upgrade_AddCreditControl.sql:8), but there is no UI or code that sets it. |
| A19 BR-19 month-end interest/fee | 0 | Settings only (CreditControlSettings.php:116-126). CalculateInterest (CreditControlFunctions.php:77) is never called. |
| A20 BR-20 per-customer exemptions | 0 | Not implemented. |
| A21 BR-21 charges on account/statement | 0 | No debtortrans rows. |
| A22 BR-22 preview, confirm, no double month | 0 | Not implemented. |
| A23 BR-23 post to chosen income accounts | 0 | GL codes are configurable (CreditControlSettings.php:129-134), but nothing posts. |
| A24 BR-24 waive with reason, reaches ledger | 0 | creditcharges.sql has waived columns, but there is no code. |
| A25 BR-25 write off all/part with reason | 0.5 | CreditWriteOffs.php:53-71 records the amount and reason in creditwriteoffs only. The customer balance is unchanged and there is no check against the balance. |
| A26 BR-26 above threshold needs FD approval | 0.5 | The threshold gate works (CreditWriteOffs.php:39-51) and the approve page exists (CreditWriteOffApprovals.php:16-35). Approval is not restricted to the FD, and "take effect" only sets the status. "Reject" deletes the row (:39-40). |
| A27 BR-27 reduce balance, post bad debt + FX | 0 | No debtortrans or gltrans rows (CreditWriteOffs.php:53-76). |
| A28 BR-28 auto stop unless CC decides otherwise | 0.5 | Stop is applied at CreditWriteOffs.php:73-76 and CreditWriteOffApprovals.php:30-31. There is no opt-out, and the change is not logged in creditactions. |
| A29 BR-29 write-off report over period | 0 | CreditWriteOffApprovals.php:97-111 shows only the last 20 approved, with no period filter and no reason column. |
| A30 BR-30 CC report with filters, home-currency totals | 0.5 | CreditControlReport.php has the three lists (:26-34, :68-78, :115-122). It has no rep or currency filter and no totals. Over-limit uses SUM(ovamount) WHERE settled=0, which ignores alloc, tax and currency. |
| A31 BR-31 aged debt shows status/limit/last stage | 0 | AgedDebtors.php is untouched. |
| A32 BR-32 per-customer audit history | 0.5 | CreditCustomerHistory.php:35-232 covers reviews, status, write-offs, reminders and charges. The auto-stop on write-off (CreditWriteOffs.php:74, Approvals:30) leaves no record, and reminders and charges are never written. |
| A33 BR-33 reps see own customers only | 0 | No SalesmanLogin filter in any new page. |
| A34 BR-34 reps view but cannot change | 0 | No permission split. |
| A35 BR-35 portal shows reminders/charges | 0 | Not implemented. |
| A36 BR-36 customer sees only own account | 0 | No CustomerLogin guard. CreditCustomerHistory.php:16-20 accepts any DebtorNo. |
| A37 BR-37 debtors = GL control | 0 | Nothing posts, so this cannot hold once write-offs are "applied". |
| A38 BR-38 find reasons for differences | 0 | Not implemented. |
| A39 BR-39 live system + new install | 0 | No sql/updates/44.php. The Z_ files in install/sql/tables break CreateTables (see the facts above). |
| A40 BR-40 go-live normal + review date + stop list loaded | 0 | Every customer gets creditstatus 0 and nextreviewdate 1000-01-01. Existing holdreason stops are not mapped to creditstatus. |
| A41 BR-41 no change for non-overdue customers | 0 | CounterSales.php:117 selects debtorsmaster.creditstatus, which does not exist on an upgraded system, so CounterSales fails for everyone. |
| A42 BR-42 staff guide updated | 0 | doc/Manual is untouched. |
| A43 BR-43 sales note on watch/stop | 0 | Not present. |

**A = 7.5 / 43**

## B. Rules away from the change

| # | Score | Evidence |
|---|---|---|
| B1 hold via holdreason, no parallel flag | 0 | Adds a parallel debtorsmaster.creditstatus (Z_Upgrade_AddCreditControl.sql:2). CounterSales.php:132 ORs it with dissallowinvoices. |
| B2 hold at dispatch/invoice | 0 | ConfirmDispatch_Invoice.php is untouched. |
| B3 recurring orders | 0 | RecurringSalesOrdersProcess.php is untouched. |
| B4 EDI import | 0 | EDIProcessOrders.php is untouched. |
| B5 API | 0 | api_salesorders.php is untouched. |
| B6 CheckCreditLimits + GetCreditAvailable | 0 | Uses a parallel formula: CreditControlReport.php:72-78 and CreditControlFunctions.php:20-25 (SUM ovamount, settled=0). |
| B7 Z_ChangeCustomerCode | 0 | Not updated. Five new debtorno tables, two with FKs to debtorsmaster, would block the code change. |
| B8 Customers.php delete | 0 | Not updated. The FKs on the new tables make the delete fail with a DB error rather than a guarded message. |
| B9 Z_ImportDebtors | 0 | Not updated. |
| B10 API Modify/InsertCustomer | 0 | Not updated. |
| B11 systypes for charge/write-off | 0 | None added. |
| B12 GetNextTransNo in transaction | 0 | No transactions are posted. |
| B13 GetPeriod / ProhibitPostingsBefore | 0 | Not used. |
| B14 gllink_debtors / debtorsact | 0 | No GL posting. |
| B15 EnsureGLEntriesBalance | 0 | Not used. |
| B16 GL = amount/rate, signs | 0 | No GL posting. |
| B17 InsertGLTags | 0 | Not used. |
| B18 refuse control account for write-off | 0 | BadDebtGLCode is free text with no validation (CreditControlSettings.php:148-149). |
| B19 allocation of new types | 0 | No new types. |
| B20 exchange difference | 0 | Not implemented. |
| B21 CustomerAccount/CustomerInquiry show new types | 0 | Not updated. |
| B22 debtortrans.salesperson | 0 | No debtortrans rows. |
| B23 no double month charge | 0 | No charge run. |
| B24 GL accounts in companies + guards | 0 | GL codes are stored in a private creditconfig table, not companies. There is no GLAccounts delete guard. |
| B25 one due-date rule, PastDueDays bands | 0 | Uses debtortrans.duedate directly (CreditControlFunctions.php:28-34, :82-101). PastDueDays is not used; separate stage days are used instead. |
| B26 open items by balance | 0 | Uses `settled=0` and ovamount (CreditControlFunctions.php:21, CreditControlReport.php:75). |
| B27 recipients custcontacts.statement=1 | 0 | No email. |
| B28 Dompdf | 0 | No PDFs. |
| B29 SendEmailFromWebERP / temp file | 0 | No email. |
| B30 SalesmanLogin filter | 0 | Absent from every new page and query. |
| B31 customer login own debtorno | 0 | No guard (CreditCustomerHistory.php:16-20, CreditReviews.php:15-18). |
| B32 hold permission via scripts-table false script | 0 | No permission mechanism at all. |
| B33 pages in scripts + seeds, no $PageSecurity | 0 | No scripts rows and no NewScript calls, so every new page is refused by session.php:337. The $PageSecurity part is met, but that alone does not earn credit. |
| B34 sql/updates/44.php | 0 | Not created. |
| B35 install/sql/tables/<table>.sql, 1000-01-01 | 1 | All 6 tables have files with '1000-01-01' defaults (e.g. creditreviews.sql:4,9; creditcharges.sql:3,9). The misplaced Z_ ALTER/INSERT files in the same directory are penalised under B34/B36 and as regressions. |
| B36 seeds in data/*.sql + install/sql/demo.sql | 0 | The seed sits in install/sql/tables/Z_InitializeCreditControl.sql as one multi-row INSERT, and it runs before its table exists. Not in demo.sql. |
| B37 menu rows / NewConfigValue / SystemParameters | 0 | No menu items. Config goes in a private creditconfig table instead of `config`. |
| B38 only helpers in all UpgradeDB variants | 0 | No upgrade script, so nothing can be credited. |
| B39 UIGeneralFunctions; no double escaping | 0.5 | Forms are hand-built HTML (e.g. CreditReviews.php:82-115). There is no double escaping, because session.php's escaping is relied on. |
| B40 $Title/$ViewTopic/$BookMark before header; manual | 0.5 | Header vars are set correctly on all 7 pages (e.g. CreditReviews.php:5-8). The BookMarks point to anchors that do not exist, and there is no manual page or ManualOutline entry. |

**B = 2 / 40**

## Scores

- A: 7.5 / 43
- B: 2 / 40
- Total: 9.5 / 83
- Correctness: 1 / 5. CounterSales selects a column that only exists if someone hand-runs the SQL. All 7 new pages are blocked by session.php because they have no scripts row. The installer breaks on the Z_ files. Next-review dates are stored through ConvertSQLDate. The write-off neither posts nor reduces the balance. All SQL is built from unvalidated $_POST/$_GET, and there are no transactions.
- Conventions: 1 / 5. Header vars and FormID are right. Otherwise the change uses a private config table, a parallel hold flag, raw HTML forms, no upgrade script, data and ALTER scripts in install/sql/tables, an unused includes file with a closing `?>`, no menu or scripts entries, and no manual.

## Regressions

1. CounterSales.php:117: `debtorsmaster.creditstatus` is selected, but no upgrade adds the column. On any existing database the customer query fails, and Counter Sales breaks for every user.
2. install/sql/tables/Z_Upgrade_AddCreditControl.sql and Z_InitializeCreditControl.sql are picked up by CreateTables (InstallFunctions.php:302). They sort before `creditconfig.sql` and `debtorsmaster.sql` and contain several statements per DB_query. The new install reports "Database tables could not be created", and creditstatus and the config seeds are missing, so regression 1 applies to new installs too.
3. CounterSales.php:132-135: a cash-sale customer whose holdreason has dissallowinvoices=1 used to fall through to the existing branch. It now hits a hard `exit()` with a new message. Also, any creditstatus=2 on the location's cash-sale account now blocks the whole Counter Sales page.
4. FKs from the new tables to debtorsmaster (e.g. creditactions.sql:13) make Customers.php delete and Z_ChangeCustomerCode fail with raw DB errors once credit rows exist.
