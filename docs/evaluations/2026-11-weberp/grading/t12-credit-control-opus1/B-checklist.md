# t12 credit control — run B checklist grading

Graded against `tasks/t12-credit-control/checklist.md`, using the code in the workspace `blindop/B/` and the diff `blindop/B.diff`. NOTES.md was used only for decisions on BRD open questions. Paths are relative to the webERP root. `CCF` = `includes/CreditControlFunctions.php` (new file).

## A. BRD requirements (BR-01..BR-43)

| # | Score | Evidence |
|---|---|---|
| A1 BR-01 | 1 | Review records date, user, outcome, old/new limit, status, notes, next date: `CCF:345-386`; form at `CreditControlCustomer.php:111-152` |
| A2 BR-02 | 1 | Next review date on new accounts from `CreditReviewMonths`: `CCF:396`, `Customers.php:236-239`, `Z_ImportDebtors.php:431`, `api/includes/api_customers.php:359-361`; existing customers set in `sql/updates/44.php:248` |
| A3 BR-03 | 1 | Reviews are insert-only, with no edit or delete path. History shown at `CreditControlCustomer.php:498-529` |
| A4 BR-04 | 1 | The limit and status change inside the review: `CCF:372-373` |
| A5 BR-05 | 1 | Stop and release need a reason and are logged with user and time: `CreditControlCustomer.php:154-168`, `CCF:301-329` |
| A6 BR-06 | 1 | Sales office `DeliveryDetails.php:326-337` / `SelectOrderItems.php:521`; web shop `api/includes/api_salesorders.php:342-346`; EDI held `EDIProcessOrders.php:1012-1014`; standing orders skipped `RecurringSalesOrdersProcess.php:96-110`; existing orders held `CCF:276-298` and blocked at `ConfirmDispatch_Invoice.php:115,702` and in picking lists |
| A7 BR-07 | 1 | Token 21 required to change status or limit: `Customers.php:26-27,213`; `CreditControlCustomer.php:105-109`; `CreditStatus.php` raised to token 21 (`44.php:181`); API gated at `api_customers.php:502` |
| A8 BR-08 | 1 | Watch warning `CCF:247-248` shown in `SelectOrderItems.php:448-449`; customers on watch can still order (`SelectOrderItems.php:556-557`); list of watch orders at `CreditControlOrders.php:115-183` |
| A9 BR-09 | 1 | Status banner on `SelectCustomer.php`, `SelectOrderItems.php:449`, `ConfirmDispatch_Invoice.php:113`, `CustomerInquiry.php`/`CustomerAccount.php`, and `Customers.php` |
| A10 BR-10 | 1 | `CheckCreditLimits`=3 holds the order: `CCF:418-441`. Applied on every route (DeliveryDetails, SpecialOrder, Recurring, EDI, API). Released at `CreditControlOrders.php:20-31`. Setting 3 is a go-live step stated in NOTES |
| A11 BR-11 | 1 | Portal message at `SelectOrderItems.php:521-524`, `DeliveryDetails.php:332`; API error 1174 in `api_errorcodes.php` |
| A12 BR-12 | 1 | Stages configurable (number, days, wording) at `DunningLevels.php:23-74`; 3 seeded in `44.php:230-238` |
| A13 BR-13 | 1 | Accounts contacts at `CCF:678-687`; customers to post listed at `DunningRun.php:186` and in the post-run table at `DunningRun.php:78-99` |
| A14 BR-14 | 1 | Prepare, review, untick with a reason, then send: `DunningRun.php:138-200,39-57` |
| A15 BR-15 | 1 | One stage at a time, re-worked out at send time, minimum days between letters: `CCF:740-791`, `DunningRun.php:39-64` |
| A16 BR-16 | 1 | Letter, items and amount recorded at `CCF:829-866` |
| A17 BR-17 | 1 | Customer currency and list of overdue items: `CCF:796-825` |
| A18 BR-18 | 1 | Disputes at `CCF:519-543`. Disputed items are excluded by default in `CCF:475-516`, so letters and interest both skip them |
| A19 BR-19 | 1 | Rate, fee and days settings at `CreditControlParameters.php`; calculation at `CCF:889-987` |
| A20 BR-20 | 1 | Exemptions at `CreditControlCustomer.php:170-186` and `CCF:968-981` |
| A21 BR-21 | 0.5 | Separate types 13/14 are posted in the customer currency (`CCF:991-1040`) and statements print every type. However, `CustomerAccount.php:290-372` still renders only types 10/11/12, so charges do not appear on the on-screen account statement |
| A22 BR-22 | 1 | Preview and confirm at `CreditCharges.php:130-189`; once per month enforced by a unique key (`44.php:117`) plus a check (`CCF:930-937`) |
| A23 BR-23 | 1 | Income accounts from parameters: `CCF:995,1008-1009` |
| A24 BR-24 | 1 | Waiver with reason, posted to the GL: `CCF:1045-1084`, `CreditControlCustomer.php:213-233` |
| A25 BR-25 | 1 | All or part of each item, with a reason: `BadDebtWriteOff.php:160-201` |
| A26 BR-26 | 1 | Approval above the limit (token 22, approver must differ from requester): `CCF:1129-1131`, `BadDebtWriteOff.php:41-72` |
| A27 BR-27 | 1 | Bad debt GL posting plus the exchange difference: `CCF:1174-1182`, `CCF:629-649` |
| A28 BR-28 | 1 | Stop checkbox ticked by default `BadDebtWriteOff.php:289`; applied at `CCF:1198-1200` |
| A29 BR-29 | 1 | `BadDebtWriteOffReport.php:51-131` shows customer, amount, reason, requester and approver |
| A30 BR-30 | 1 | `CreditControlReport.php:97-184` has review due, over limit by amount, stop and watch sections, rep and currency filters, and home-currency totals |
| A31 BR-31 | 1 | `AgedDebtors.php:286-288,331-333` shows status, limit and last reminder |
| A32 BR-32 | 1 | `creditcontrollog` written by every action (`CCF:132-155`); shown at `CreditControlCustomer.php:532-563` |
| A33 BR-33 | 1 | `CCF:86-108` filter used in `CreditControlCustomer.php:59,95`, `CreditControlReport.php:97`, `CustomerCreditHistory.php`, `PDFDunningLetter.php:56` |
| A34 BR-34 | 1 | Reps can view; actions gated at `CreditControlCustomer.php:105-109`; fields read-only at `Customers.php` (CreditAuthority) |
| A35 BR-35 | 1 | `CustomerCreditHistory.php:73-130` (letters, charges, balance), token 1, menu link in `index.php` |
| A36 BR-36 | 1 | Customer logins forced to their own code: `CustomerCreditHistory.php:16-17`, `CustomerAccount.php:27-32`, `CustomerInquiry.php:27-32`, `CCF:86-90` |
| A37 BR-37 | 1 | Every posting balances against `debtorsact`, including the exchange difference on write-off (`CCF:1174-1182,645-648`) |
| A38 BR-38 | 1 | `Z_CheckDebtorsControl.php:117-180` lists each transaction where the sub-ledger and the GL differ |
| A39 BR-39 | 1 | `sql/updates/44.php`, plus the install table and data files |
| A40 BR-40 | 0.5 | Next review date set for everyone (`44.php:248`), stop-list import at `Z_ImportCreditStatus.php`, open orders of stopped customers held (`44.php:241-245`). However, existing customers keep their current status instead of starting as "normal". NOTES gives a reason, but this is not one of the BRD's open questions |
| A41 BR-41 | 1 | No change to invoice, statement or posting logic for customers who are not overdue; hold mode 3 is opt-in |
| A42 BR-42 | 1 | `doc/Manual/ManualCreditControl.html` covers reviews, stop and watch, the reminder run, charges, write-offs and the report |
| A43 BR-43 | 1 | Sales note at `ManualCreditControl.html:116-123` |

**A = 42 / 43**

## B. Rules away from the change

| # | Score | Evidence |
|---|---|---|
| B1 | 1 | Credit status stays `holdreason`→`dissallowinvoices` 0/1/2 (`CCF:1-20`, `CreditStatus.php` select); `salesorders.credithold` is per order, not a parallel customer flag |
| B2 | 1 | `ConfirmDispatch_Invoice.php:112-123` checks on open and `:701-709` checks again at posting |
| B3 | 1 | `RecurringSalesOrdersProcess.php:96-110` skips on stop; over-limit orders held with no auto-invoice (`:221,231`) |
| B4 | 1 | `EDIProcessOrders.php:1012-1014` |
| B5 | 1 | `api_salesorders.php:342-346` (InsertSalesOrderHeader), `:821-825` (InvoiceSalesOrder), holds applied on line changes |
| B6 | 1 | Settings 0/1/2 still honoured, 3 added; `GetCreditAvailable` reused at `CCF:430` |
| B7 | 0 | `Z_ChangeCustomerCode.php` not changed. The explicit column list (`:44`) loses nextreviewdate/interestexempt/feeexempt, and the 7 debtorno-keyed tables are not moved |
| B8 | 0 | `Customers.php:376` delete path not changed: no guard and no cleanup for creditreviews, creditcontrollog, dunningletters, creditcharges or writeoffs |
| B9 | 0.5 | `Z_ImportDebtors.php:431` writes a default nextreviewdate on insert, but `$FieldHeadings` (`:38`) is not extended, so none of the new columns can be imported |
| B10 | 0.5 | `ModifyCustomer` strips and gates credit fields (`api_customers.php:493-528`), but nextreviewdate/exempt values are written unvalidated. `InsertCustomer` still accepts any holdreason or creditlimit without the token |
| B11 | 1 | Types 13/14/45/46/47 in `44.php:151-155`, `install/sql/data/systypes.sql`, `install/sql/demo.sql:21256` |
| B12 | 1 | `GetNextTransNo` is called inside the caller's `DB_Txn_Begin` (`CCF:996,1059,1167,1225`; `CreditCharges.php:60`, `BadDebtWriteOff.php:65`) |
| B13 | 0.5 | `GetPeriod` used (`CCF:997,1061,1169`), but there is no `ProhibitPostingsBefore` check and the shifted date is not shown |
| B14 | 1 | GL rows only when `gllink_debtors==1`, AR side posted to `debtorsact`: `CCF:1007-1010,1067-1070,1173-1176` |
| B15 | 0.5 | `EnsureGLEntriesBalance` is called before commit (`CreditCharges.php:63`, `BadDebtWriteOff.php:67`), but the commit follows straight after with no check, so the page does not stop on an imbalance |
| B16 | 1 | `amount / rate`; charges positive (`CCF:1008`), write-off/waiver negative (`CCF:1066,1172`) |
| B17 | 0 | No `InsertGLTags` after any `gltrans` insert (`CCF:605-625`) |
| B18 | 0 | The bad debt account picker lists every account (`CreditControlParameters.php:89-99,185`), and the control account is not refused |
| B19 | 0.5 | Write-off is posted already allocated (`CCF:1180-1182`), and charges and recovery are debits that can be allocated to. A waiver whose remainder is not allocated (`CCF:1064`) is type 45, which `CustomerAllocations.php:481,538` cannot allocate from |
| B20 | 1 | Exchange difference to `salesexchangediffact` at `CCF:645-648` |
| B21 | 0 | `CustomerAccount.php:290-372` and `CustomerInquiry.php` type branches not extended for 13/14/45/46/47 |
| B22 | 1 | `debtortrans.salesperson` taken from the branch salesman: `CCF:599` |
| B23 | 1 | Unique key `OneChargePerMonth` (`44.php:117`) plus a pre-check (`CCF:930-937`) |
| B24 | 0 | GL accounts kept in `config` (`CreditInterestAct`/`CreditFeeAct`/`BadDebtAct`), not in `companies`: no CompanyPreferences change, no GetConfig change, no GLAccounts delete guard |
| B25 | 0.5 | `DueDateSQL` matches AgedDebtors (`CCF:465-470`), but dunning bands are their own days, not `PastDueDays1/2` |
| B26 | 1 | Open items selected by `ROUND(balance, decimalplaces)` (`CCF:500`), not `settled` |
| B27 | 1 | `custcontacts.statement=1` at `CCF:679` |
| B28 | 1 | `PDFDunningLetter.php:8,10,83` use Dompdf with `SetDomPDFOptions` |
| B29 | 1 | `=== true` test at `CCF:873-876` (failure recorded as 'F'). Letters are plain text with no PDF attachment, so there is no temp file |
| B30 | 0.5 | Filter applied in `CreditControlReport.php:21`, `CreditControlCustomer.php:59`, `ProposeDunningRun` (`CCF:724`). Missing in `CreditControlOrders.php:37,115`, `BadDebtWriteOffReport.php:51`, `CreditCharges.php`, and the `BadDebtWriteOff.php` pending list |
| B31 | 1 | `CCF:86-90`; `CustomerAccount.php:27-32`, `CustomerInquiry.php:27-32`, `CustomerCreditHistory.php:16`, `PDFDunningLetter.php:56` |
| B32 | 1 | False scripts `CreditControlAuthority`/`WriteOffApproval` (`44.php:177-178`) read via `PageSecurityArray` at `CCF:59-75` |
| B33 | 1 | All 12 pages in `44.php:164-175`, `install/sql/data/scripts.sql:2`, `install/sql/demo.sql:21257`; no `$PageSecurity` in any page |
| B34 | 1 | `44.php`: idempotent helpers, `CreateTable` with exact names and no ENGINE, `UpdateDBNo` on one line inside the Errors guard (`:250-252`) |
| B35 | 1 | 9 new `install/sql/tables/*.sql` files plus the debtorsmaster/salesorders edits, all with ENGINE/utf8mb4 and no zero dates |
| B36 | 1 | `install/sql/data/{config,menuitems,scripts,systypes,securitytokens,securitygroups,holdreasons,dunninglevels}.sql`, one statement per file, plus `install/sql/demo.sql:21254-21276` |
| B37 | 0.5 | Menus: `NewMenuItem` (`44.php:185-196`) and seed rows for roles 1-9. Config: `NewConfigValue` plus seeds, but the settings are on a new `CreditControlParameters.php`, not `SystemParameters.php` (only option 3 added there, `SystemParameters.php:479`) |
| B38 | 1 | Helpers used (`CreateTable`, `AddColumn`, `AddIndex`, `NewSysType`, `NewSecurityToken`, `InsertRecord`, `UpdateField`, `NewScript`, `NewMenuItem`, `NewConfigValue`) all exist in the four `UpgradeDB_*` variants; no `AddCalculatedColumn` |
| B39 | 0.5 | No double escaping: `CCInput` strips session escaping (`CCF:43-46`), and output uses `htmlspecialchars(...,false)`. But no form uses `UIGeneralFunctions` (all hand-written selects) |
| B40 | 0.5 | `$Title`/`$ViewTopic`/`$BookMark` set before header.php, and a `ManualOutline.php` entry exists. Two bookmark anchors are missing from `ManualCreditControl.html`: `CreditControlParameters` (`CreditControlParameters.php:11`) and `ReminderStages` (`DunningLevels.php:10`) |

**B = 29 / 40**

## Totals

- A: 42 / 43
- B: 29 / 40
- Total: 71 / 83
- Correctness: 4 / 5. Broad and mostly sound. Postings balance; holds are applied on every order route; write-off exchange differences are handled. Defects:
  - (a) Reminder emails pass a numerically indexed address list (`CCF:873`) to `SendEmailFromWebERP`. Under SMTP (`SmtpSetting`≠0), `SendEmailBySmtp` calls `addAddress(0, 'x@y')` on a PHPMailer created with exceptions on (`includes/MiscFunctions.php:810,854-855`). That throws on the invalid address in the middle of the run, inside an open transaction.
  - (b) Imbalances are not stopped after `EnsureGLEntriesBalance`.
  - (c) No `ProhibitPostingsBefore` check.
  - (d) Nothing was run (NOTES says so).
- Conventions: 3 / 5. Follows the update/seed/scripts/menu, Dompdf, transaction-flag, `__()` and false-script patterns. Misses:
  - `UIGeneralFunctions`;
  - `InsertGLTags`;
  - the companies/CompanyPreferences pattern for GL accounts (config plus a separate parameters page instead);
  - two manual anchors.

  It also adds a new `Z_` utility (`Z_ImportCreditStatus.php`).

## Regressions / risks

- `Customers.php` delete orphans the new debtorno-keyed rows. Every new account now gets a `creditcontrollog` "Opened" row, so this affects every customer that is deleted (B8).
- `Z_ChangeCustomerCode.php` drops `nextreviewdate`/`interestexempt`/`feeexempt` and leaves the credit tables pointing at the old code (B7).
- Interest, fee, waiver, write-off and recovery rows count in the balance on `CustomerAccount.php` but are not listed there (B21).
- With SMTP mail configured, the reminder run fails on the first emailed letter (see correctness).
- Behaviour changes:
  - `CreditStatus.php` now needs token 21.
  - `Z_CheckDebtorsControl.php` has been rewritten and moved to token 8.
  - API `ModifyCustomer` refuses credit fields without token 21.
  - Staff without token 21 can no longer set a limit or status on new customers.
  - `CounterSales.php` treats mode 3 as "prohibit".
- `CounterSales.php` still only warns for an on-stop cash-sale customer, as in base. It is not covered by the new stop checks.
