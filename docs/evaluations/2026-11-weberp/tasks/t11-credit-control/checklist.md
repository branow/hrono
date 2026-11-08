# Checklist: t11 credit control (not given to the agent)

Base 4cb937f79e8b, threads export. The BRD (brd.md) was written 2026-11-08
by an agent that saw no code, no checklist and no earlier BRD, from the
business side only (docs/evaluations/PRINCIPLES.md). Part A is the BRD's
own requirements; part B are the same 40 rules mined from the map and the
code for t10 (grading/t10-credit-control/rules/), unchanged, written before
this BRD existed.

Each item: met 1 / partly 0.5 / missed 0.

## A. The BRD's requirements (43)

A1-A43 = BR-01 to BR-43 of brd.md, each scored as written. Where the BRD
leaves an open question (section 9), any reasonable choice that is stated
in NOTES.md counts as met.

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

Report A (/43), B (/40) and total (/83), plus correctness 0-5 and
conventions 0-5, regressions listed. The primary score is B.
