# t11 credit control: grading of run hrono-1 (blind, graded as "Z")

- Run diff: `scratchpad/blind11/Z.diff` (885 lines, 18 files)
- Workspace: `scratchpad/blind11/Z/`
- Base: `scratchpad/base/` (4cb937f79e8b)
- Task: `tasks/t11-credit-control/brd.md` (BR-01..BR-43). Checklist: `tasks/t11-credit-control/checklist.md`. Rule details: `grading/t10-credit-control/rules/`.
- All claims were checked in the code, not in the run's NOTES.md. File:line refers to the workspace.

Scoring: met 1 / partly 0.5 / missed 0.

The run built a narrow slice: credit reviews, stop/watch through the existing hold reasons, an append-only credit log, stop enforcement at order save, dispatch/invoice, recurring orders, EDI and the API order header, a gate on credit fields in Customers.php, and the credit control report. It built nothing for dunning, disputes, interest and fees, waivers, write-offs, the ledger, the aged-debt columns, the portal, rep views, menus, the manual or demo.sql. Nothing was executed.

## A. The BRD (43)

| id | score | justification |
|---|---|---|
| A1 | 1 | `CreditControl.php:55-120` records outcome (confirmed/raised/reduced/watch/stop, `:59`), new limit, notes, next review date; `LogCreditAction` (`includes/CreditControlFunctions.php:53-73`) stores date and user. |
| A2 | 0.5 | New customers get `DefaultNextReviewDate()` (`Customers.php:286`, `CreditControlFunctions.php:76-82`), existing ones are backfilled (`sql/updates/44.php:28-30`). But one global `CreditReviewMonths`, no shorter period for higher-risk customers, not in SystemParameters.php; API and Z_ImportDebtors inserts leave `1000-01-01`. |
| A3 | 1 | History shown read-only at `CreditControl.php:218-237`; no code updates or deletes `creditcontrollog`. |
| A4 | 1 | Limit, next review and status UPDATE plus log rows in one transaction, `CreditControl.php:101-114`. |
| A5 | 1 | Status change with mandatory reason, `CreditControl.php:122-159`; logged with user and time via `LogCreditAction`. |
| A6 | 0.5 | Blocked at order save `DeliveryDetails.php:330`, dispatch/invoice `ConfirmDispatch_Invoice.php:608-619`, recurring `RecurringSalesOrdersProcess.php:93-97`, EDI `EDIProcessOrders.php:897-901`, API header `api/includes/api_salesorders.php:282`. Not in `CounterSales.php:131` (still only checks `!= 1` at selection but a sales-office invoice route), nor API `InvoiceSalesOrder` (`api_salesorders.php:791`). No per-order release, only lifting the stop. |
| A7 | 0.5 | `Customers.php:143` keeps holdreason/creditlimit for users without the CreditControl.php token; `CreditControl.php:47` refuses reps. API `ModifyCustomer` and `Z_ImportDebtors.php` still change both unchecked. |
| A8 | 0.5 | Watch orders allowed with the pre-existing warning (`SelectOrderItems.php:439-441`, `CounterSales.php:132`). No list of orders taken for watched customers. |
| A9 | 0.5 | Status shown on `CreditControl.php:163`; elsewhere only the pre-existing "ACCOUNT ON HOLD" (`CustomerInquiry.php:169`, `CustomerAccount.php:232`), which shows watch as hold. Nothing on SelectCustomer.php. |
| A10 | 0 | Over-limit hold not built (NOTES admits). |
| A11 | 1 | Customer login on stop gets "your account has been put on hold ... contact credit control" (`SelectOrderItems.php`, pre-existing) and the new message at `DeliveryDetails.php:332`. |
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
| A25 | 0 | Write-offs not built. |
| A26 | 0 | Not built. |
| A27 | 0 | Not built. |
| A28 | 0 | Not built. |
| A29 | 0 | Not built. |
| A30 | 1 | `CreditControlReport.php`: due/overdue review, over limit with "over by", watch/stop (`:75-86,136-146`); rep and currency filters (`:17-19,61-66`); home-currency totals (`:108-110`). Balance ignores open orders (own formula, `:53-56`). |
| A31 | 0 | AgedDebtors.php not changed. |
| A32 | 0.5 | Reviews, stop/watch and limit changes are logged (`CreditControl.php:110-113,150`, `Customers.php:225`); no reminders, charges, waivers or write-offs, and API/import changes are not logged. |
| A33 | 0 | Reps get no credit view: `CreditControl.php:47` refuses them, the report needs token 21 (role 8 only). |
| A34 | 0.5 | Reps cannot change status/limit (`Customers.php:143`), but cannot see them in the new pages either. |
| A35 | 0 | Portal not built. |
| A36 | 0 | Not built. |
| A37 | 0 | No ledger work. |
| A38 | 0 | Not built. |
| A39 | 0.5 | Upgrade (`sql/updates/44.php`) and non-demo install (`install/sql/tables/*.sql`, `install/sql/data/*.sql`) covered; `install/sql/demo.sql` untouched, so a demo install has no scripts rows, token 21 or config for the new pages. |
| A40 | 0.5 | Existing customers keep their hold reason (stop stays stop) and get a review date (`44.php:28-30`), but the 12 months is hard-coded rather than read from the setting, and there is no way to load the spreadsheet stop list other than one by one. |
| A41 | 1 | No change to invoice, statement or posting logic; the new checks act only on customers on stop (`CreditControlFunctions.php:41-44`). |
| A42 | 0 | No manual page. |
| A43 | 0 | No sales note. |

**A: 11.5 / 43**

## B. Rules away from the change (40)

| id | score | justification |
|---|---|---|
| B1 | 1 | Status = `holdreason` -> `holdreasons.dissallowinvoices` (`CreditControlFunctions.php:14-29`, `CreditControl.php:133-136`); no parallel flag. |
| B2 | 1 | `ConfirmDispatch_Invoice.php:608-619` blocks invoicing for a stopped customer. |
| B3 | 1 | `RecurringSalesOrdersProcess.php:93-97`. |
| B4 | 1 | `EDIProcessOrders.php:897-901`. |
| B5 | 0.5 | `InsertSalesOrderHeader` checked (`api_salesorders.php:280-284`); `InvoiceSalesOrder` (`:791`) not. |
| B6 | 0 | No credit-limit check built; the report computes its own balance (`CreditControlReport.php:53-56`), not `GetCreditAvailable`. |
| B7 | 0 | `Z_ChangeCustomerCode.php` untouched; it ignores FKs (`:256`), so log rows stay on the old code. |
| B8 | 0 | No delete guard; the `creditcontrollog` FK makes `DELETE FROM debtorsmaster` (`Customers.php:370`) fail after branches and contacts are already deleted (`:366-368`). |
| B9 | 0 | `Z_ImportDebtors.php` untouched. |
| B10 | 0 | API ModifyCustomer/InsertCustomer untouched; holdreason/creditlimit still open. |
| B11 | 0 | No charges or write-offs built. |
| B12 | 0 | Not built. |
| B13 | 0 | Not built. |
| B14 | 0 | Not built. |
| B15 | 0 | Not built. |
| B16 | 0 | Not built. |
| B17 | 0 | Not built. |
| B18 | 0 | Not built. |
| B19 | 0 | Not built. |
| B20 | 0 | Not built. |
| B21 | 0 | Not built. |
| B22 | 0 | Not built. |
| B23 | 0 | Not built. |
| B24 | 0 | Not built. |
| B25 | 0 | No overdue logic built. |
| B26 | 0 | Not built (report sums ovamount-alloc, not `balance`). |
| B27 | 0 | No email built. |
| B28 | 0 | Not built. |
| B29 | 0 | Not built. |
| B30 | 1 | Report forces the rep filter (`CreditControlReport.php:17-18,64-66`); CreditControl.php refuses rep logins (`:47`). |
| B31 | 0 | No customer-facing page built. |
| B32 | 1 | `CanMaintainCredit` checks `PageSecurityArray['CreditControl.php']` against allowed tokens (`CreditControlFunctions.php:47-50`), no hard-coded number in pages. |
| B33 | 0.5 | `NewScript` (`44.php:41-42`) and `install/sql/data/scripts.sql` rows; no `install/sql/demo.sql` rows. No `$PageSecurity` in pages. |
| B34 | 0.5 | `44.php` with `CreateTable('creditcontrollog', ...)` and guarded one-line `UpdateDBNo` (`:44-46`), but the CreateTable SQL carries its own ENGINE/CHARSET (`:22`, helper appends again) and token/group rows go through raw `executeSQL` (`:33-39`) instead of `NewSecurityToken`. |
| B35 | 1 | `install/sql/tables/creditcontrollog.sql` and `debtorsmaster.sql` column, `'1000-01-01'` defaults, one statement each. |
| B36 | 0.5 | Seeds in `install/sql/data/{config,scripts,securitytokens,securitygroups}.sql` (single statements), none in `install/sql/demo.sql`. |
| B37 | 0.5 | `NewConfigValue` (`44.php:24`) and `config.sql` seed; no SystemParameters.php field, no menu items for any role. |
| B38 | 1 | Only AddColumn/CreateTable/NewConfigValue/NewScript/executeSQL, present in all UpgradeDB variants. |
| B39 | 0 | Hand-written fields (`CreditControl.php:182-214`), no UIGeneralFunctions; already-escaped POST/GET re-escaped (`CreditControl.php:37`, `LogCreditAction` on `$_POST['Notes']`) and notes re-encoded by htmlspecialchars on display (`:234`). |
| B40 | 0.5 | `$Title/$ViewTopic/$BookMark` before header.php in both pages (`CreditControl.php:10-13`, `CreditControlReport.php:9-12`); BookMarks point at anchors that do not exist, no manual page or ManualOutline entry. |

**B: 11 / 40**

B items scored 1: B1, B2, B3, B4, B30, B32, B35, B38.

## Totals

- A 11.5/43, B 11/40, total 22.5/83
- Correctness 2/5: what was built is coherent and enforces the stop on most routes, but it covers about a quarter of the BRD (no dunning, charges, write-offs, ledger, portal, over-limit hold) and has the regressions below.
- Conventions 3/5: update file, install tables, data seeds, scripts-table permission and SalesmanLogin filter follow the project; demo.sql, menus, SystemParameters, manual, UIGeneralFunctions and the CreateTable/NewSecurityToken helpers do not.

## Regressions

1. Deleting a customer that has any credit log row: the FK makes `DELETE FROM debtorsmaster` fail after `custbranch` and `custcontacts` were deleted (`Customers.php:366-370`, no transaction), leaving a half-deleted customer.
2. `Z_ChangeCustomerCode.php` runs with FKs off (`:256-268`), so a renamed customer loses its credit history (rows stay on the old code).
3. Demo install: `install/sql/demo.sql` has no scripts row, token 21 or config, so the new pages are unreachable and `CanMaintainCredit()` is false for every user, so nobody can change a credit limit or hold reason in Customers.php.
4. After upgrade only role 8 holds token 21 (`44.php:35-38`); every other role that could edit credit limit and hold reason in Customers.php silently loses it (intended by BR-07, but no role is set up for credit control).
5. Notes are double-escaped and double-encoded on display (`CreditControl.php:234`).
6. Customers created by the API or CSV import get `nextreviewdate = 1000-01-01` and show as due for review at once (NOTES admits).
