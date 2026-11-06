# Checklist: t10 customer credit control (not given to the agent)

Base 4cb937f79e8b, threads export. Made up 2026-11-06 under amendment 6,
before any run. Part A is what the request asks. Part B are rules away
from the change: each is stated in the existing map and checked in the base
code; the id in brackets points to the mined lists in
grading/t10-credit-control/rules/ (151 = sales/master data, 152 = finance,
150 = installer and project history, 149 = upgrade and reports), which give
the map page and file:line. Rules the map states wrongly, and two where map
pages contradict each other (cron pages, CurrencyTolerance), are left out.

Each item: met 1 / partly 0.5 / missed 0.

## A. The request (15)

A1 Reviews table keyed on debtorno with FK; date, user, outcome, new
limit, next review date, long comments.
A2 Review saves change creditlimit / holdreason in the same transaction.
A3 Next-review date stored per customer (new debtorsmaster column or
equivalent), set by reviews and on customer create.
A4 Review history on the customer's page, newest first, editable.
A5 Review-due report with balance, overdue, limit, available credit, last
paid; PDF.
A6 Watch state (warn only) as well as hold.
A7 Hold/release limited to a narrower permission than other AR users.
A8 Three reminder levels driven by the existing overdue bands.
A9 Reminder run screen: preview, exclude, send; no repeat of a level for
the same invoices.
A10 Reminder PDF emailed; failures listed, not counted as sent.
A11 Reminder history on the customer's page.
A12 Interest and fee charge run, user-started, in the customer's currency.
A13 Charges are customer transactions posted to GL (income vs receivables).
A14 Write-off of chosen invoices or whole balance with a reason, to a bad
debt account.
A15 Manual pages for the process.

## B. Rules away from the change (40)

Customers and holds
B1 Hold = debtorsmaster.holdreason -> holdreasons.dissallowinvoices (1
block, 2 watch); no parallel hold flag. [151 R03/R04, 149 R27, 152 R19]
B2 Hold enforced at dispatch/invoice (ConfirmDispatch_Invoice.php), not
only at order entry. [151 R01]
B3 Hold enforced in recurring order processing
(RecurringSalesOrdersProcess.php). [151 R01]
B4 Hold enforced in EDI order import (EDIProcessOrders.php). [151 R01]
B5 Hold enforced in the API order/invoice functions (api_salesorders.php).
[151 R01]
B6 Credit checks follow the CheckCreditLimits setting (0/1/2) and reuse
GetCreditAvailable, no parallel formula. [151 R05/R06, 152 R20]
B7 New debtorno tables handled by Z_ChangeCustomerCode.php, and the new
debtorsmaster column added to its explicit column list. [151 R14]
B8 Customers.php delete: new tables block the delete or are deleted with
it. [151 R12]
B9 New debtorsmaster column carried by Z_ImportDebtors.php (appended to
$FieldHeadings). [151 R28]
B10 API ModifyCustomer/InsertCustomer: the new column validated, holdreason
/creditlimit changes not left open. [151 R20, 150 R29]

Ledger
B11 New systypes rows for charge and write-off (install systypes.sql and
NewSysType), or reuse of an existing type with reason. [151 R25, 152 R05]
B12 GetNextTransNo inside the transaction. [152 R05]
B13 GetPeriod for the period; postings before ProhibitPostingsBefore
refused or shown. [152 R06]
B14 GL rows only when gllink_debtors==1, AR side to
CompanyRecord['debtorsact']. [152 R07]
B15 EnsureGLEntriesBalance before commit (and stop on imbalance). [152
R01/R02]
B16 GL amounts = amount / rate; charges positive, write-offs negative.
[152 R11]
B17 InsertGLTags right after each gltrans insert. [152 R10]
B18 Write-off account refused when it is a control account. [152 R09]
B19 Allocation: new types usable in CustomerAllocations.php (hard-coded
type 11/12 lists) or posted as an allocatable type. [152 R15]
B20 Exchange difference on foreign-currency write-off/allocation to
salesexchangediffact. [152 R16, 214]
B21 CustomerAccount.php and CustomerInquiry.php show the new types (they
drop types other than 10/11/12). [151 R24, 152 R17]
B22 debtortrans.salesperson recorded on new transactions. [152 R21]
B23 No double charge for the same month (own guard; debtortrans has no
unique key). [152 R12]
B24 Two new GL accounts in companies: GetConfig column list with SHOW
COLUMNS guard, CompanyPreferences form/update, GLAccounts delete guard,
positional companies INSERTs (InstallFunctions.php, demo.sql). [152 R08,
149 R11/R12]

Overdue and email
B25 One due-date rule matching AgedDebtors/statements (daysbeforedue vs
dayinfollowingmonth), bands PastDueDays1/2. [151 R08/R10, 149 R24]
B26 Open items by debtortrans.balance, not settled. [149 R28]
B27 Recipients = custcontacts.statement=1 (not branch email). [151 R22,
149 R15]
B28 PDFs with Dompdf (SetDomPDFOptions), not Cpdf/PDFStarter. [149 R16,
150 R16]
B29 SendEmailFromWebERP === true counts as sent; temp file in reports_dir
and unlinked. [149 R17/R18, 150 R17]

Access
B30 SalesmanLogin filter on every list, run and report. [151 R16, 149 R25]
B31 Customer login sees only its own debtorno. [151 R17]
B32 Hold/release permission through a scripts-table entry ("false
script" like CostUpdate), not a hardcoded token number (#761). [150 R01]
B33 Every new page in scripts (NewScript + scripts.sql + demo.sql); no
$PageSecurity in the page. [150 R02/R03, 149 R13]

Install and upgrade
B34 sql/updates/44.php with idempotent helpers, CreateTable with the exact
table name, guarded UpdateDBNo on one line. [149 R01-R05]
B35 install/sql/tables/<table>.sql for each new table, '1000-01-01' dates
not zero dates. [149 R08, 150 R06/R12]
B36 Seeds in both install/sql/data/*.sql and install/sql/demo.sql (not
sql/demo.sql), each data file one statement. [149 R09/R10, 150 R09]
B37 Menu rows for every role (NewMenuItem; seeds roles 1-9); new config
via NewConfigValue + config seeds + SystemParameters.php. [149 R14/R30,
151 R11]
B38 Only helpers that exist in all UpgradeDB_* variants (no
AddCalculatedColumn). [149 R07]

Conventions
B39 Forms with UIGeneralFunctions (#828); no double escaping of POST
(session.php already escapes). [150 R13, 151 R19]
B40 $Title/$ViewTopic/$BookMark before header.php; manual page with both
anchors and a ManualOutline.php entry. [149 R22/R23, 150 R30]

## Scoring

Report A (/15), B (/40) and total (/55), plus correctness 0-5 and
conventions 0-5 from the blind reviewer, regressions listed.
