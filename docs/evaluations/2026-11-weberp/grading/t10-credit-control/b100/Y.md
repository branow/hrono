# t10 credit control: blind grade of run Y

Graded from `blind/Y.diff` and the workspace `blind/Y/` against base
`scratchpad/base/`. Every claim was checked in the code; NOTES.md was not used.
Line numbers refer to the workspace after the run (`Y/`). `php -l` is clean on
every changed PHP file.

New files: BadDebtWriteOff.php, CreditReminders.php, CreditReviewReport.php,
CreditReviews.php, CustomerCreditNotices.php, LateCharges.php,
PrintCreditReminder.php, PrintCustCharge.php, includes/CreditControlFunctions.php,
sql/updates/44.php, install/sql/creditcontrol.sql, five install table files.
There is no change under doc/Manual.

## A. The request (15)

| id | score | justification |
|---|---|---|
| A1 | 1 | custcreditreviews keyed on debtorno with an FK to debtorsmaster (ON DELETE/UPDATE CASCADE), and columns reviewdate, reviewedby, outcome, new/old limit, nextreviewdate and `comments text` (install/sql/tables/custcreditreviews.sql:1-23; sql/updates/44.php:9-32). |
| A2 | 1 | The review INSERT and the debtorsmaster UPDATE of creditlimit/holdreason run in one DB_Txn_Begin/Commit with $Transaction=true, and validation fails roll back (CreditReviews.php:91-146). |
| A3 | 1 | debtorsmaster.nextreviewdate (debtorsmaster.sql:33, 44.php:5). It is set by a review (CreditReviews.php:137-140), on create in Customers.php (Customers.php:226-231, 257) and in API InsertCustomer (api_customers.php:327-333). |
| A4 | 1 | The history is newest first (CreditReviews.php:286). Correction is "mark entered by mistake", which reverts the account when it is the latest review (CreditReviews.php:150-188). The page is linked from the customer's credit status in Customers.php. |
| A5 | 1 | The report shows balance, overdue (aged-debtors test), limit, GetCreditAvailable and lastpaiddate, with a Days filter and Dompdf PDF (CreditReviewReport.php:22-65). |
| A6 | 0.5 | Watch (dissallowinvoices=2) warns at order entry (SelectOrderItems.php:439-441) and is selectable in a review. However, CreditStatus.php still writes only 0/1 (CreditStatus.php:67-95) and no seed creates a watch reason, so a watch status cannot be set up from the UI. |
| A7 | 1 | Hold/limit changes need token 21, granted only to role 8 (CreditControlFunctions.php:16-20, creditcontrol.sql:2-3). Customers.php no longer updates holdreason/creditlimit and shows them read-only (Customers.php:150-195, 1008-1020). |
| A8 | 1 | Levels 1/2/3 come from days past due, PastDueDays1 and PastDueDays2 (CreditControlFunctions.php:109-117). |
| A9 | 1 | Preview table with per-customer Include checkboxes and a Send button (CreditReminders.php:166-193). A repeat is blocked by NOT EXISTS on level >= (CreditReminders.php:48-51) and by UNIQUE(debtortransid, level) (custreminderlines.sql:9). |
| A10 | 1 | Dompdf letter emailed to statement contacts. A missing contact or a failed send is listed under "NOT sent" and the record is rolled back (CreditReminders.php:86-89, 128-143, 158-163). |
| A11 | 1 | CreditControlShowReminders shows date, level, invoices, amount and a link to the letter on CreditReviews.php and CustomerCreditNotices.php (CreditControlFunctions.php:250-279; CreditReviews.php:315). |
| A12 | 1 | LateCharges.php is a user-started preview/Include/Run screen (interest + fee per final notice) posted in the customer's currency with its rate (LateCharges.php:105-157). |
| A13 | 1 | Type 70 debtortrans plus gltrans debtorsact (+) / latechargeact (-), gated on gllink_debtors (LateCharges.php:124-155). |
| A14 | 1 | Chosen invoices or WholeBalance, a required reason, gltrans to baddebtact / debtorsact, allocations and a custwriteoffs row (BadDebtWriteOff.php:36-125). |
| A15 | 0 | No manual page: doc/Manual has no CreditControl file and ManualOutline.php has no entry, although every page sets $ViewTopic='CreditControl'. |

**A = 13.5 / 15**

## B. Rules away from the change (40)

| id | score | justification |
|---|---|---|
| B1 | 1 | Hold is read only through debtorsmaster.holdreason -> holdreasons.dissallowinvoices, with 1 = block and 2 = watch (CreditControlFunctions.php:77-84). No parallel flag. |
| B2 | 1 | ConfirmDispatch_Invoice.php blocks a held customer both when the order loads (:112-117) and at ProcessInvoice (:616-620). |
| B3 | 1 | RecurringSalesOrdersProcess.php:94-98 skips held customers. |
| B4 | 1 | EDIProcessOrders.php:897-901 refuses held customers. It also fixes the `$CreateOrder = true` assignment bug. |
| B5 | 1 | api_salesorders.php:279 (InsertSalesOrderHeader) and :801-808 (InvoiceSalesOrder) are blocked, and so is api_debtortransactions.php:1201 (InsertSalesInvoice). |
| B6 | 1 | No new limit check contradicts CheckCreditLimits, and the available credit uses GetCreditAvailable (CreditReviewReport.php:58, 101). |
| B7 | 1 | Z_ChangeCustomerCode.php adds nextreviewdate to the explicit column list (:76, :109) and moves the 4 new tables (:213-218). |
| B8 | 1 | Customers.php delete removes custreminders and custcreditreviews (:365-368). Charges and write-offs have debtortrans rows, which already block the delete, and all new tables cascade. |
| B9 | 0 | Z_ImportDebtors.php is untouched: nextreviewdate is not in $FieldHeadings (Z_ImportDebtors.php:37), so imported customers get NULL. |
| B10 | 1 | ModifyCustomer/InsertCustomer validate nextreviewdate and refuse holdreason/creditlimit unless the API user holds the credit-control token (api_customers.php:103-117, 322-350, 460-485). |
| B11 | 1 | systypes 70 and 71 come from NewSysType (44.php:101-102) and from creditcontrol.sql:1, which is loaded on both install paths. The ids are free in base. |
| B12 | 1 | GetNextTransNo is called after DB_Txn_Begin (LateCharges.php:118-121, BadDebtWriteOff.php:47-72). |
| B13 | 0.5 | GetPeriod is used for prd and periodno (LateCharges.php:120, BadDebtWriteOff.php:71). ProhibitPostingsBefore is never checked or shown, so a closed-month charge is moved forward silently. |
| B14 | 1 | GL rows only when gllink_debtors==1, with the AR side on companies.debtorsact (LateCharges.php:145-155, BadDebtWriteOff.php:100-121). |
| B15 | 0 | EnsureGLEntriesBalance is never called in LateCharges.php or BadDebtWriteOff.php. |
| B16 | 1 | GL = amount / rate. Charge ovamount is positive (LateCharges.php:128) and write-off ovamount is negative (BadDebtWriteOff.php:79-80). |
| B17 | 0.5 | InsertGLTags immediately follows only one gltrans insert per posting (LateCharges.php:154, BadDebtWriteOff.php:108). The debtors and exchange-difference lines carry no tag. |
| B18 | 1 | baddebtact is refused when it equals a control account, both at posting (CreditControlFunctions.php:145-158) and in CompanyPreferences.php:40-65. |
| B19 | 1 | The write-off is allocated through custallocns at posting (BadDebtWriteOff.php:89-95). Type 70 charges are unsettled debtortrans, which the CustomerAllocations.php allocate-to list accepts (any type, settled=0). |
| B20 | 1 | The exchange difference on a write-off goes to salesexchangediffact against debtorsact with the CustomerAllocations sign convention (BadDebtWriteOff.php:84-120). |
| B21 | 0 | CustomerAccount.php and CustomerInquiry.php are untouched, so types 70 and 71 are dropped from the account page or shown without links. The statement is not extended either. |
| B22 | 1 | debtortrans.salesperson is set to the first branch's salesman (LateCharges.php:129, BadDebtWriteOff.php:80). |
| B23 | 1 | UNIQUE(debtorno, chargemonth) on custlatecharges plus a NOT EXISTS filter (custlatecharges.sql:11, LateCharges.php:45-46). |
| B24 | 1 | Columns are in companies.sql and 44.php, with the CompanyPreferences form and UPDATE (:109-110, 178-179, 301-310), the GLAccounts delete guard (:127-128), the positional INSERTs (InstallFunctions.php:539-541, demo.sql:14) and Z_ChangeGLAccountCode. GetConfig is unchanged because the accounts are read straight from companies, not CompanyRecord (CreditControlFunctions.php:134-139), so login on an un-upgraded database is not at risk. |
| B25 | 1 | CreditDaysPastDueSQL and the level tests reproduce AgedDebtors' due/overdue1/overdue2 CASE exactly (CreditControlFunctions.php:97-117 vs AgedDebtors.php:38-66). |
| B26 | 1 | Open items are selected by debtortrans.balance > tolerance everywhere, with no settled=0 filter. |
| B27 | 1 | Recipients come from custcontacts.statement=1, filtered by IsEmailAddress and de-duplicated (CreditReminders.php:59-65, PrintCustCharge.php:51-56). |
| B28 | 1 | Dompdf with SetDomPDFOptions (CreditControlFunctions.php:314-321). No Cpdf. |
| B29 | 0.5 | CreditReminders tests `=== true` (:136) and unlinks the file. However, the temp file goes to sys_get_temp_dir(), not reports_dir (CreditReminders.php:124, PrintCustCharge.php:61), and PrintCustCharge ignores $Sent entirely (:63). |
| B30 | 0.5 | Scoped: the review page, report, notices and prints (CreditControlCustomerScopeSQL). Not scoped: the CreditReminders, LateCharges and BadDebtWriteOff runs and lists (no SalesmanLogin filter in those files). |
| B31 | 1 | A customer login is restricted to its own debtorno (CreditControlFunctions.php:25-50; CustomerCreditNotices.php:15-21; PrintCreditReminder.php and PrintCustCharge.php use the scope SQL). |
| B32 | 0 | The permission is a hard-coded token number: `define('CREDIT_CONTROL_TOKEN', 21)` with in_array(21, AllowedPageSecurityTokens) (CreditControlFunctions.php:7, 16-20). This is the #761 anti-pattern, with no false-script row. |
| B33 | 1 | 8 pages are registered via NewScript (44.php:113-120) and creditcontrol.sql (loaded on demo and non-demo installs). No $PageSecurity in any page. |
| B34 | 0.5 | 44.php uses idempotent helpers and CreateTable with exact names, but `UpdateDBNo` at 44.php:130 is not guarded by `$_SESSION['Updates']['Errors']==0`. |
| B35 | 1 | One install/sql/tables file per new table, with '1000-01-01' / NULL dates and ENGINE=InnoDB utf8mb4. |
| B36 | 0.5 | The seeds are not in install/sql/data/*.sql or install/sql/demo.sql. They are in a new multi-statement install/sql/creditcontrol.sql, run by an extra installer step (InstallFunctions.php:493-499, 630-636). It works on both paths, but it is not the place the rule names. |
| B37 | 1 | NewMenuItem in 44.php, plus seed menuitems for every securityroles row (creditcontrol.sql:18-23). Config comes from NewConfigValue, the seeds and SystemParameters.php (:44-55, 163-175, 508-543). |
| B38 | 1 | Every helper used (AddColumn, CreateTable, NewSysType, NewSecurityToken, InsertRecord, NewConfigValue, NewScript, NewMenuItem) exists in all four UpgradeDB_* variants. No AddCalculatedColumn. |
| B39 | 0.5 | POST is not double-escaped. However, the new forms are hand-written `<input>/<select>`, not UIGeneralFunctions (CreditReviews.php, LateCharges.php, BadDebtWriteOff.php, CreditReviewReport.php, SystemParameters additions). |
| B40 | 0.5 | $Title, $ViewTopic and $BookMark are set before header.php on every page. There is no Manual page with the anchors and no ManualOutline.php entry. |

**B = 32 / 40**

## Totals

A 13.5/15, B 32/40, all 45.5/55

**Correctness: 3.5 / 5.** The core flows are sound and transactional:

- the review saves the review and changes the account atomically;
- holds are enforced on every invoicing route;
- reminders run idempotently and roll back when the email fails;
- write-offs allocate and handle the FX difference correctly.

Gaps:

- no EnsureGLEntriesBalance;
- no ProhibitPostingsBefore check;
- charges and write-offs are invisible on CustomerAccount and the statement, so the account page does not add up;
- the watch state cannot be configured from the UI;
- the "email like an invoice" path in PrintCustCharge.php reports nothing and no page links to it;
- imported customers get no review date;
- the run pages are not scoped to sales people.

**Conventions: 3 / 5.** Good:

- sql/updates/44.php uses the helpers;
- the install table files are correct;
- PDFs use Dompdf;
- $Title is set before header.php;
- new API error codes start after 1173.

Against conventions:

- the permission is a hard-coded token number;
- UpdateDBNo is unguarded;
- seeds sit in a separate file instead of the data and demo seeds;
- forms do not use UIGeneralFunctions;
- temp files go to the system temp directory;
- there is no manual;
- the edited lines in the Customers.php UPDATE are garbled (paymentterms and salestype carry about 12 extra tabs, Customers.php:159, 163, 187, 191).

## Regressions (existing behaviour changed)

- **API backward compatibility.** InsertCustomer and ModifyCustomer now return error 1176 when the caller sends creditlimit or holdreason and the API user lacks token 21 (api_customers.php:325, 350, 462, 481). Existing web-shop integrations that send a credit limit on customer creation will start failing. This is intended by request 7.2, but it is a breaking change to the API.
- **Customers.php.** Credit limit and credit status can no longer be edited here, even by the controller: they are removed from both UPDATEs. Non-controllers who create a customer get DefaultCreditLimit and the first status that allows invoicing, whatever the form says. This is intended, but it is a behaviour change.
- **EDIProcessOrders.php.** Changing `if ($CreateOrder = true)` to `if ($CreateOrder)` means EDI messages that failed validation no longer create orders, where before they always did. This is a bug fix, but the behaviour is different.
- **SelectOrderItems.php:539 (customer-login path).** It now accepts any status other than 1 (including the demo -1 reasons and 2), where before it accepted only 0.
- **CounterSales.php.** A held cash-sale customer now blocks ProcessSale; before, it only warned.
- No PHP syntax errors. No changed signatures in existing API functions apart from the extra error returns above.
