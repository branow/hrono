# t11 credit control: grading of the code-gate run

- Run diff: `/Users/orest/hrono-weberp/runs/t11-credit-control-code-gate.diff` (1595 lines, 33 files)
- Workspace: `/Users/orest/hrono-weberp/runs/t11-credit-control-code-gate/`
- Base: `scratchpad/base/` (4cb937f79e8b)
- Task: `tasks/t11-credit-control/brd.md` (BR-01..BR-43). Checklist: `tasks/t11-credit-control/checklist.md`. Rule details: `grading/t10-credit-control/rules/`.
- All claims were checked in the code, not in the run's NOTES.md. File:line refers to the workspace.

Scoring: met 1 / partly 0.5 / missed 0.

The run built a partial slice: credit reviews, stop/watch, stop enforcement on every order route, the over-limit hold, the credit control report and the manual. It built nothing for dunning, interest and fees, waivers, write-offs, the ledger, the aged-debt columns or the portal (BR-12..BR-29, 31, 35, 37, 38). Nothing was executed.

## A. The BRD (43)

| id | score | justification |
|---|---|---|
| A1 | 1 | `CreditReview.php:100-117` inserts the review with date (CURRENT_TIMESTAMP), reviewedby (UserID), outcome (confirmed/raised/reduced/watch/stop/normal, `:36-41`), old and new limit, notes and next review date. |
| A2 | 0.5 | New customers get `DefaultNextReviewDate()` (`Customers.php` INSERT, `CreditControlFunctions.php` DefaultNextReviewDate), as do the API (`api_customers.php:359-363`) and the import (`Z_ImportDebtors.php:416`), and 44.php:46 backfills existing ones. But there is one global `CreditReviewMonths` with no shorter period for higher-risk customers, and no SystemParameters.php field, so Finance cannot set it in the UI. The demo seed backfill at `install/sql/demo.sql:20` runs before the debtorsmaster rows at `:726`, so demo customers keep 1000-01-01. |
| A3 | 1 | The review history and audit log are shown at `CreditReview.php:259-295`. No page updates or deletes `creditreviews`/`creditcontrollog`. |
| A4 | 1 | `CreditReview.php:98-137`: the review INSERT, the `creditlimit` UPDATE (`:121`) and the log row are written in one transaction. |
| A5 | 1 | `SetCreditStatus` (`CreditControlFunctions.php`) changes holdreason to 99/98/0 and logs the user, time and reason. It is called from the review with the required notes (`CreditReview.php:62-66,129-135`). |
| A6 | 1 | New orders are refused for a stopped customer in DeliveryDetails.php:329-343 (order entry and web shop), CounterSales.php:982, SpecialOrder.php:267, EDIProcessOrders.php:897-903, RecurringSalesOrdersProcess.php:96-100 and api_salesorders.php:279-286. Dispatch/invoice is blocked unless released in ConfirmDispatch_Invoice.php:24-40 and api_salesorders.php:806-811, and the release is in CreditHeldOrders.php:26-42. |
| A7 | 0.5 | Customers.php no longer writes holdreason/creditlimit, and CreditReview.php needs token 21. But `Z_ImportDebtors.php:364,369` (UpdateIfExists) still overwrites holdreason and creditlimit with no log, and the API `ModifyCustomer` (`api_customers.php:391ff`) still accepts both from any API user. |
| A8 | 1 | Watch (dissallowinvoices=2) can order (SelectOrderItems.php:540). Staff get a warning at selection (SelectOrderItems.php:439-441, SpecialOrder.php:103, CounterSales.php:133, all pre-existing). Credit control lists open watch orders (CreditHeldOrders.php:92). |
| A9 | 0.5 | Status shows on CustomerAccount.php:232-240, CustomerInquiry.php:169-176, Customers.php (disabled field) and at order entry. SelectCustomer.php, the main staff customer screen, still shows no credit status. |
| A10 | 0.5 | `HoldOrderIfOverCreditLimit` flags `creditheld=1` after save in DeliveryDetails.php:560,774, EDIProcessOrders.php:1019 and RecurringSalesOrdersProcess.php:210. It is not applied to API orders, counter sales or special orders, and it is off when CheckCreditLimits=0. At 2 the old refusal still applies before any hold. |
| A11 | 1 | A portal customer on stop gets "your account is on hold … Please contact us (credit control)" (SelectOrderItems.php:577), and CustomerAccount.php:239 shows "ACCOUNT ON HOLD - PLEASE CONTACT US". |
| A12 | 0 | Dunning not built. |
| A13 | 0 | Not built. |
| A14 | 0 | Not built. |
| A15 | 0 | Not built. |
| A16 | 0 | Not built. |
| A17 | 0 | Not built. |
| A18 | 0 | No disputed-invoice flag. |
| A19 | 0 | Interest/fees not built. |
| A20 | 0 | Not built. |
| A21 | 0 | Not built. |
| A22 | 0 | Not built. |
| A23 | 0 | Not built. |
| A24 | 0 | Not built. |
| A25 | 0 | Write-off not built. |
| A26 | 0 | Not built. |
| A27 | 0 | Not built. |
| A28 | 0 | Not built. |
| A29 | 0 | Not built. |
| A30 | 1 | CreditControlReport.php: due/overdue review (`:87`), over limit with the amount over, watch/stop, rep filter (custbranch.salesman, forced for SalesmanLogin `:20-28`), currency filter and home-currency totals (`balance/rate`, `:86`). |
| A31 | 0 | AgedDebtors.php not changed. |
| A32 | 0.5 | Reviews, status and limit changes, order holds and releases are logged and shown per customer (CreditReview.php:279-295). Reminders, charges, waivers and write-offs do not exist, and the history is only on a token-21 page. |
| A33 | 1 | The only new rep-visible page, CreditControlReport.php:20-28,55-57, forces the rep's own customers. Existing customer pages keep their SalesmanLogin filters. |
| A34 | 1 | Reps can see status and limits (report token 2, CustomerAccount/Inquiry) but cannot change them: Customers.php fields are read-only and not in the UPDATE, and CreditReview.php needs token 21. |
| A35 | 0 | No portal view of reminders or charges. |
| A36 | 0.5 | Nothing new is shown in the portal. Existing pages keep their own-account checks and watch is hidden from portal logins (CustomerAccount.php:231). Nothing was built for this requirement. |
| A37 | 0 | Not built. |
| A38 | 0 | Not built. |
| A39 | 0.5 | 44.php plus the install tables and data mirror the change. On a fresh non-demo install, `install/sql/data/creditcontrol_menuitems.sql` (`SELECT … FROM securityroles`) runs before `securityroles.sql` in glob order, so it inserts no menu rows. On the demo install, the nextreviewdate backfill runs before the customers exist. |
| A40 | 0.5 | Existing customers keep their codes and get a review date (44.php:46). There is no way to load the spreadsheet stop list in bulk: only one review at a time through CreditReview.php, and Z_ImportDebtors only for new or updated imports. |
| A41 | 1 | Invoices, statements and postings are unchanged. The only new blocks are for stop and over-limit holds. |
| A42 | 0.5 | ManualAccountsReceivable.html:196-213 covers reviews, stop/watch, over-limit and the report. It does not cover the reminder run, month-end charges or write-offs. |
| A43 | 1 | ManualAccountsReceivable.html:212-213 has the "Note for sales staff": what watch and stop mean, and to refer the customer to credit control. |

**A = 16.5 / 43**

## B. Rules away from the change (40)

| id | score | justification |
|---|---|---|
| B1 | 1 | Stop/watch = holdreason → holdreasons.dissallowinvoices 1/2 (`CreditControlFunctions.php` GetCreditStatus). The new codes are 98/99 (44.php:52-53). There is no parallel customer flag (salesorders.creditheld is an order-level approval flag). |
| B2 | 1 | ConfirmDispatch_Invoice.php:24-40 runs on every request via OrderNumber/ProcessingOrder, including the posting request. |
| B3 | 1 | RecurringSalesOrdersProcess.php:96-100 skips a stopped customer and leaves the template alone. Over-limit orders also skip auto-invoice (`:210,217`). |
| B4 | 1 | EDIProcessOrders.php:896-903: no order for a stopped customer, and a line is added to the email. |
| B5 | 1 | api_salesorders.php:279-286 (InsertSalesOrderHeader) and :806-811 (InvoiceSalesOrder). |
| B6 | 0.5 | The hold follows CheckCreditLimits and uses GetCreditAvailable (CreditControlFunctions HoldOrderIfOverCreditLimit). CreditControlReport.php:90 uses its own `balance > creditlimit` without open orders, a second formula that disagrees with order entry. |
| B7 | 1 | Z_ChangeCustomerCode.php:56,88 add nextreviewdate to both column lists, and :201-205 move creditreviews and creditcontrollog. |
| B8 | 0 | The Customers.php delete guard (`:295-355`) is unchanged. The new FKs make the `DELETE FROM debtorsmaster` at `:353` fail after custbranch/custcontacts are already deleted (`:349-352`, no transaction). |
| B9 | 0.5 | Z_ImportDebtors.php:394,416 fills nextreviewdate with a computed date, but the column is not appended to `$FieldHeadings` (`:36ff`), so it cannot be imported. |
| B10 | 0 | api_customers.php:359-363 only defaults nextreviewdate on insert. It is not validated, and ModifyCustomer still writes holdreason/creditlimit/nextreviewdate unchecked. |
| B11 | 0 | No charge or write-off types (not built). |
| B12 | 0 | Not built. |
| B13 | 0 | Not built. |
| B14 | 0 | Not built. |
| B15 | 0 | Not built. |
| B16 | 0 | Not built. |
| B17 | 0 | Not built. |
| B18 | 0 | Not built. |
| B19 | 0 | Not built. |
| B20 | 0 | Not built. |
| B21 | 0 | No new transaction types. The CustomerAccount/Inquiry edits only change the hold banner. |
| B22 | 0 | Not built. |
| B23 | 0 | Not built. |
| B24 | 0 | Not built. |
| B25 | 0 | No overdue logic. |
| B26 | 0 | No open-item selection. Only the report's balance sum uses debtortrans.balance. |
| B27 | 0 | No email. |
| B28 | 0 | No PDFs. |
| B29 | 0 | No email. |
| B30 | 0.5 | CreditControlReport.php:20-28 forces the rep filter. The customer search list in CreditReview.php:166-185 and the CreditHeldOrders.php lists apply no SalesmanLogin filter (they are token-21 only). |
| B31 | 0 | No customer-facing page built. |
| B32 | 0 | Hard-coded token: `define('CREDIT_CONTROL_TOKEN', 21)` and `in_array(21, AllowedPageSecurityTokens)` in CreditControlFunctions.php CanChangeCreditControl. There is no scripts-table "false script". |
| B33 | 0.5 | All three pages are registered (44.php:61-63, install/sql/data/creditcontrol_scripts.sql, demo.sql:16), but each sets `$PageSecurity` in the page (CreditReview.php:7, CreditHeldOrders.php:6, CreditControlReport.php:6). |
| B34 | 0.5 | 44.php uses CreateTable with exact names, AddColumn, InsertRecord, NewConfigValue, NewScript, NewMenuItem and NewSecurityToken. `UpdateDBNo` at 44.php:68 is unguarded (no `Errors == 0` check), and :46 is a raw executeSQL. |
| B35 | 1 | install/sql/tables/creditreviews.sql and creditcontrollog.sql, plus columns in debtorsmaster.sql and salesorders.sql, all with '1000-01-01'. |
| B36 | 1 | The data files (creditcontrol_config/menuitems/scripts, holdreasons, securitytokens, securitygroups) are one statement each, and demo.sql:12-20 has the matching seeds. |
| B37 | 0.5 | NewMenuItem is used in 44.php:64-66. The fresh-install seed (`creditcontrol_menuitems.sql`, SELECT from securityroles) runs before securityroles.sql, so it inserts zero rows. CreditReviewMonths etc. are config rows, but none is in SystemParameters.php. |
| B38 | 1 | Every helper used exists in all four UpgradeDB_* files (executeSQL is in Z_UpgradeDatabase.php). No AddCalculatedColumn. |
| B39 | 0 | The forms are hand-written. POST values that session.php already escaped are run through DB_escape_string again (CreditReview.php notes `:115`, keywords `:168`, CreditHeldOrders reason). |
| B40 | 0.5 | $Title/$ViewTopic/$BookMark are set before header.php. The bookmarks CreditReview/CreditHeldOrders/CreditControlReport have no anchors (only `id="CreditControl"`, ManualAccountsReceivable.html:196). AccountsReceivable is already in ManualOutline. |

**B = 12.5 / 40**

B items scored 1: B1, B2, B3, B4, B5, B7, B35, B36, B38.

## Totals

- A = 16.5 / 43, B = 12.5 / 40, total = 29 / 83
- Correctness: 2 / 5. What exists is coherent and mostly right: stop is enforced on every route and the review/limit change is atomic. But only about 40% of the BRD is built (no dunning, charges, write-offs, ledger or portal), and the install has the defects below. Nothing was run.
- Conventions: 3 / 5. It reuses holdreasons, GetCreditAvailable, the update helpers and install mirroring. Against that: $PageSecurity in pages, a hard-coded token 21, an unguarded UpdateDBNo, double escaping, no UIGeneralFunctions and missing manual anchors.

## Regressions and defects

1. Fresh non-demo install: `install/sql/data/creditcontrol_menuitems.sql` selects from `securityroles` before `securityroles.sql` is loaded (alphabetical glob in InstallFunctions.php:477), so it inserts no credit-control menu items.
2. Demo install: `UPDATE debtorsmaster SET nextreviewdate` at install/sql/demo.sql:20 runs before the debtorsmaster INSERT at :726, so every demo customer is at 1000-01-01 and shows as due for review.
3. Customers.php delete: a customer with any creditreviews/creditcontrollog row (anyone reviewed, put on stop, or with an order held) has its branches and contacts deleted (`:349-352`), then the debtorsmaster delete fails on the new FK, leaving a half-deleted customer.
4. Double escaping: review notes, release reasons and search keywords are escaped by session.php and again by DB_escape_string, so stored text gets extra backslashes or entities.
5. Customers.php: the HoldReason select is now `disabled`, so it is never posted. On a validation-error redisplay, `$_POST['HoldReason']` is undefined (`:976,988`): a PHP notice and no selected status.
6. Behaviour change: with the default CheckCreditLimits=1 ("Warn on breach"), over-limit orders are now held and cannot be invoiced until released. This is intended by BR-10 but changes what the existing setting means. New customers can no longer be created with a chosen limit or status.
7. Bypasses left open: `Z_ImportDebtors.php` UpdateIfExists (`:364,369`) and API `ModifyCustomer` change holdreason/creditlimit with no log or permission check.
