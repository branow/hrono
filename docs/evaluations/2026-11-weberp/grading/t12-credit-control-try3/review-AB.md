# Blind review: t12 credit control, implementation A vs implementation B

Reviewer stance: webERP maintainer who would have to merge and maintain this. I read both diffs and the full trees, compared them with the base tree, and checked the important claims against the code, not against NOTES.md.

## Summary

Both implementations make the same core decision, and it is the right one for webERP. Stop and watch reuse `debtorsmaster.holdreason` → `holdreasons.dissallowinvoices` (0 normal, 1 stop, 2 watch), which order entry, counter sales, special orders, statements and inquiries already read. Neither adds a parallel status field. Both add:

- review, history, dunning, charge and write-off tables;
- `nextreviewdate` and `debtortrans.disputed`;
- new system types for charges, waivers and write-offs;
- a shared `includes/CreditControlFunctions.php`;
- an update script, `sql/updates/44.php`, plus matching `install/sql/tables`/`data` seeds;
- a section in `ManualAccountsReceivable.html`.

The differences are in coverage and in the defects.

- **A** is a little tighter, and it fixed the hold-reason maintenance page. However, it leaves out over-limit holds (BR-10) and the aged debtors columns (BR-31). It hangs all credit authority on the existing token 3, which the Purchasing Officer and AR Clerk roles also hold. Its demo install path is broken, and its dunning logic ignores unallocated cash.
- **B** covers more of the request and fits more of webERP's existing tools:
  - an over-limit hold and release flow;
  - aged debtors columns;
  - Debtors Control Integrity;
  - a portal menu entry;
  - a fix for portal URL tampering;
  - a demo install path;
  - dedicated security tokens.

  It has one severe install bug: a new install loses its whole menu. That bug has a one-line fix. B also leaves dead code in `Customers.php`, and it did not update `CreditStatus.php`.

## 1. Completeness

| Area | A | B |
|---|---|---|
| Reviews with history, next review date, limit changed with the review (BR-01..04) | Yes. Same transaction, insert-only table | Yes. Same transaction, insert-only table |
| New customers get a review date (BR-02) | `Customers.php` only | `Customers.php`, `api_customers.php` and `Z_ImportDebtors.php` |
| Stop/watch with reason, who and when (BR-05) | Yes (`creditlog`) | Yes (`creditevents`) |
| Stop on every route (BR-06) | Sales office commit (`DeliveryDetails`), dispatch/invoice, EDI, recurring, API order and API invoice | Sales office commit, dispatch/invoice (on open and again on process), EDI, recurring, API order. **API `InvoiceSalesOrder` is not blocked** |
| Release of orders taken before the stop (BR-06) | None. The only option is to take the customer off stop | Partly: `creditholdstate = 2` releases held orders. There is no UI to release an order of a stopped customer |
| Who may change status and limits (BR-07) | Token 3, which roles 3 (Purchasing Officer), 5 (AR Clerk), 6 and 8 hold. `Customers.php` still lets any token-3 user edit the limit and hold reason directly (logged) | New token 21 (credit control) and token 22 (authority, Finance Director). `Customers.php` no longer changes the limit or status on edit (see the defect in section 5) |
| Watch warning and list of watched orders (BR-08) | Yes | Yes |
| Over-limit orders held for approval (BR-10) | **Not built** (admitted) | Built: `CheckCreditLimits = 3`. Held orders appear on the worklist, can be released, and dispatch is blocked until then. Covers sales office/web shop, EDI and recurring (recurring auto-invoice is switched off when held). The API holds only if the customer is already over the limit |
| Web shop tells a stopped customer "on hold" (BR-11) | Existing message. Also tells *watched* customers they are on watch (against open question 10) | Existing message. Watch is silent. The portal page shows "on hold" |
| Dunning stages configurable, email, no-email list, preview and untick (BR-12..14) | Yes. No-email customers are listed by name only | Yes. No-email customers get the letter text printed for posting |
| Paid customer gets no next letter, no repeat stage (BR-15) | Partly: overdue is gross of unallocated receipts. Resetting on `lastpaiddate` can send a higher stage straight after a payment (see section 2) | Yes. Overdue is net of unallocated credits; the cycle is anchored on the oldest overdue item |
| Reminder recorded with invoices and amount, customer currency (BR-16/17) | Yes | Yes |
| Disputed invoices (BR-18) | Yes (invoices only) | Yes (any open debit) |
| Interest and/or fee, rate, fee, days (BR-19) | Yes. Interest is rate/12 on overdue invoices; flat fee per customer | Yes. Interest is days/365 on the net overdue balance; fee per customer or per invoice; optional interest on charges |
| Exempt interest **and/or** fees (BR-20) | Yes, separate flags, plus a "leave out of reminder runs" flag | One flag covers both. "And/or" is not met |
| Separate lines on statements (BR-21) | Types 80 and 81 | Type 51 for both, separate transactions, distinct text |
| Preview, confirm, no double charge (BR-22) | Yes, unique on (debtor, month) | Yes, unique on (debtor, month, type) |
| GL income accounts chosen by Finance (BR-23) | Yes | Yes |
| Waiver with reason, to GL (BR-24) | Yes. Reverses to the *current* configured accounts | Yes. Reverses to the account the charge actually posted to |
| Write-off, approval threshold, bad debt GL, auto-stop, report (BR-25..29) | Yes | Yes |
| Credit control report: filter by rep and currency, home totals (BR-30) | Yes | Yes (worklist), plus "final notice sent, not on stop" |
| Aged debtors shows status, limit, last stage (BR-31) | **No** | Yes (screen view only; not the PDF) |
| Per-customer audit trail (BR-32) | Yes | Yes. A go-live row is written for customers already on stop or watch |
| Reps see only their own customers (BR-33/34) | Yes | Yes. Reps are also kept from review notes and internal events |
| Portal reminders and charges, own account only (BR-35/36) | Page exists and takes the customer from `www_users`, but **there is no menu entry** for the customer role | Page with a menu entry for role 7. Also fixes `CustomerInquiry.php`, where a portal user could read any customer by changing `?CustomerID=` |
| Ledger agreement and finding out why (BR-37/38) | New per-type reconciliation table on the report | Extends the existing `Z_CheckDebtorsControl.php`, which otherwise would show the new types as an unexplained difference |
| Live upgrade, new install, existing stops kept (BR-39/40) | Upgrade fine. Fresh install fine. **Demo install broken** | Upgrade fine. Demo install handled. **Fresh install breaks the menu** (see section 2) |
| Staff guide and sales note (BR-42/43) | Yes, plus `NEWS.md` | Yes, more detailed (month-end agreement section) |

B delivers clearly more of what the business asked for. The decisive gaps are BR-10 (missing in A), BR-31 (missing in A), the authority model behind BR-07, and portal reachability.

## 2. Correctness

### Ledger and money

Both post a `debtortrans` row and balanced `gltrans`, with the debtors control line derived as the negative of the other lines. The posting is wrapped in one transaction, and allocation follows the `CustomerAllocations.php` pattern: `custallocns` plus `alloc`/`settled` on both sides.

Both value a write-off at the rates of the items it settles, allocated oldest first. Because the debit and credit use the same rate, the debtors control account moves exactly with the sub-ledger and no exchange difference arises. That is a defensible reading of BR-27.

- A computes the waiver rate as total/home over the outstanding charges, which is also correct.
- B stores the transaction rate as `CustAmount/HomeAmount` and rounds the home amount to company decimals. A does not round GL lines.

### Posting date

- A posts on a user-chosen run date, and the charge month is the month of that date.
- B posts charges, waivers and write-offs on **today's date** whatever month is selected. Running October's charges on 1 November puts them in the November period, and the month can be chosen up to 12 months back at today's rate. This is a month-end close nuisance (BR-37), not a broken ledger.

### Dunning logic

- **A** computes overdue gross of unallocated receipts. A customer who has paid, but whose cash is not yet allocated (common in webERP), is still chased and charged. Worse, letters sent before `debtorsmaster.lastpaiddate` are ignored, so after any receipt (even a partial one) the next run starts from scratch and sends the highest stage reached by days overdue. That can be the final notice, sent straight after a payment. This breaks the spirit of BR-15/AC-06.
- **B** nets unallocated credits, anchors the "already sent" check on the due date of the oldest overdue item, enforces the minimum gap, and decides again at send time.

### Hold enforcement

Both enforce stop at order commit in `DeliveryDetails.php`, which is the path used by both staff and customer orders. Both enforce it on EDI, on recurring orders (the template stays due), and at dispatch/invoice.

- A checks stop once in `ConfirmDispatch_Invoice.php`, after the lines are rendered. That covers both display and processing.
- B checks on order open and again before processing.
- A also blocks the API invoice route; B does not.

### API

A defines `CustomerOnStop` as error code **1158**, which already belongs to `NoCompanyRecord`. A client will be told "Unable to read company record" for a stopped customer. B adds 1174 with its own description.

### Install and upgrade

**B, new install.** B appends a second `INSERT INTO menuitems ...;` statement to `install/sql/data/menuitems.sql`. The non-demo installer runs each `data/*.sql` file as a single `DB_query`/`mysqli_query` call, which cannot execute two statements. The whole `menuitems` load therefore fails: a brand-new install has **no menu at all**, and the installer reports that the tables could not be populated. This is the most severe defect in either change, but the fix is trivial (one statement, or a separate file).

**A, demo install.** A's NOTES claim demo databases "are at update 17 so they run it on first login". That is true of the legacy `sql/demo.sql`, but not of the installer. `UploadData()` loads `install/sql/demo.sql`, which has no `DBUpdateNumber`, and then writes `DBUpdateNumber = HighestFileName()`, which is 44. So `44.php` never runs on a demo install. The tables exist, but the `scripts` rows, tokens, system types 80–83, config values, hold reasons 91/92 and menu items are all missing. The pages are refused by `session.php`, and any posting would fail the systypes foreign key. B adds `install/sql/creditcontrol_demo.sql` and wires it into `InstallFunctions.php`.

Both data seeds add a `holdreasons.sql`. Base fresh installs had no hold reasons at all, so this is an improvement for both.

Both upgrades are idempotent (`CreateTable`, `AddColumn`, `NewConfigValue`, `InsertRecord`) and record the DB number only when there are no errors. Both keep existing hold reasons, so customers already on stop stay on stop. Both set a review date for every existing customer, hard-coded to 12 months.

### Email

Both use `SendEmailFromWebERP` with plain text.

- A falls back to the email of the first branch when no contact is flagged.
- B uses only contacts flagged for statements, sends to all of them, and skips the customer if the email fails.

Both send the email before writing the log row, so a database failure after a successful send leaves an unrecorded letter. This is minor and the same in both.

### Input handling

`session.php` passes all `$_POST` values through `htmlspecialchars` and an escape. As a result, neither implementation's string handling breaks on quotes.

- A writes database-read text back unescaped, which is only a risk for backslashes.
- B escapes inside `LogCreditEvent` and `CreditPostTransaction`, which double-escapes backslashes from `$_POST`.

Both are cosmetic edge cases.

## 3. Fit with webERP

Both follow the page idiom: `session.php`, `header.php`/`footer.php`, `prnMsg`, `FormID`, `__()`, `DB_query`, `<fieldset>`/`<field>`, `class="selection"` tables, `$ViewTopic`/`$BookMark`. Both also follow the update-script helpers (`NewScript`, `NewMenuItem`, `NewSysType`, `NewSecurityToken`, `NewConfigValue`) and keep the install seeds in step.

**Security model.** B introduces purpose-specific tokens (21 credit control, 22 authority), which is how webERP has added authorities before (18 cost authority, 19, 20). A overloads token 3, "Credit notes and AR management". With the default roles, the Purchasing Officer and the AR Clerk can put customers on stop, change limits, post month-end charges and write off debts below the threshold. That does not meet the separation the BRD asks for, and it cannot be fixed without re-tokenising the pages.

**Existing tools.**
- B extends `Z_CheckDebtorsControl.php`, `AgedDebtors.php`, `DatabaseTranslations.php` (system type names), `SystemParameters.php` (a new `CheckCreditLimits` option, keeping 0/1/2 unchanged) and `Z_ImportDebtors.php`/`api_customers.php`.
- A writes its own reconciliation table into its report instead of fixing the existing integrity check, which stays wrong for its new types 80–83. A does not register the new type names for translation.

**Hold reason maintenance.** A changes `CreditStatus.php` from a 0/1 checkbox to a Normal/Watch/Stop select, and protects the three codes credit control uses. B leaves `CreditStatus.php` alone. That page still shows a watch code as "NO INVOICING", and saving that code silently turns it into 0 or 1. B's design depends on watch codes, so this is a real gap.

**Menus.** Both add menus for every role in the upgrade, as `NewMenuItem` does, and rely on page tokens. B's installer seeds are role-specific, which is nicer, and B gives the customer role its portal entry. A has no portal menu entry.

**Docs.** Both write a manual section with anchors. B wraps it in the `Help Begin/End` markers the manual uses; A also updates `NEWS.md`.

## 4. Structure and code quality

Both centralise their logic in one include, and both are readable.

**A** is smaller (about 2,300 added lines against B's 2,700). Its pages are self-contained, and its helper set is compact: `PostCreditControlTrans`, `CreditControlAllocate`, `GetOverdueInvoices`. Some planning functions live inside pages, such as `PlanWriteOff` and `GetChargeCandidates`.

**B** has a richer and better-named domain layer in the include:

- `CreditOrderCheck`, `CreditOrderBlockReason`, `CreditReminderDue`;
- `CreditOverduePosition`, `CreditBuildLetter`;
- `CreditSetStatus`/`CreditSetLimit`, which always write history.

The enforcement points therefore call one function instead of repeating SQL. A repeats the stop query inline twice in `api_salesorders.php`.

B's `CreditSetStatus`/`CreditSetLimit`/`CreditLogMaintenanceChange` keep the audit trail consistent from every entry point.

Weak spots in B:

- **Dead code in `Customers.php`.** `$CreditHoldSQL = "" . $CreditHoldSQL . "";` is a no-op, so the intended "token 21 may still edit here" never happens, while the comments and NOTES say it does. For a credit controller the fields look editable but are silently ignored. That is a maintenance trap.
- **Query load.** The reminder preview and charge calculation call several helpers per customer (around 5–6 queries per customer). This is acceptable at 900 customers, but it is N+1.

Weak spots in A:

- **Constants.** `CREDIT_WATCH`/`CREDIT_STOP` are 1/2 in A but map from `dissallowinvoices` 2/1. This works through `CreditStatusFromDisallow`, but it invites mistakes. B uses the flag values directly.
- **Statuses.** Write-off status is stored as integers 0/1/2 with the meaning held in a PHP array. B uses readable strings.

## 5. Regressions

**A**

- API error code 1158 collides with `NoCompanyRecord`.
- In the customer self-order path in `SelectOrderItems.php`, watched customers are now shown "account ... needs to be watched", so the web shop leaks watch status to the customer.
- A demo install yields unusable credit pages, and the demo DB is marked at 44, so the update never repairs it.
- Customers with any credit history can no longer be deleted. This is intended, and it is the same in B.

**B**

- **A new (non-demo) install has no menu**, because `menuitems.sql` now holds two statements.
- Nobody can change an existing customer's credit limit or credit status from `Customers.php` any more. That is intended for non-credit users, but it also applies to token-21 users, contrary to the code's own comment. The change is silent.
- `CreditStatus.php` corrupts watch codes when they are edited. This is a pre-existing limitation, but it now matters.
- The **CheckCreditLimits** option 3 changes the warn branches in `SelectOrderItems.php`, `SelectOrderItems_IntoCart.php` and `CounterSales.php`. That is correct, but every other place that tests `== 1` (if any remain) will treat 3 as "do not check".
- Existing behaviour for options 0/1/2 is unchanged.

## 6. What a maintainer must fix before merging

### A (most serious first)

1. Add a demo install path: seed scripts, tokens, system types, config, hold reasons and menus in the demo install, as B does, or stop claiming that the update runs.
2. Replace token 3 with dedicated credit-control and approval tokens. Lock the credit limit and hold reason in `Customers.php` to those tokens, with server-side enforcement.
3. Implement BR-10: an over-limit hold with release, blocked at dispatch.
4. Fix the dunning cycle. Net off unallocated receipts, and do not reset the stage ladder on any receipt (`lastpaiddate`), because that can send a final notice straight after a payment.
5. Give the API stop error its own code and description (it collides with 1158).
6. Add the portal menu entry for the customer role. Stop showing watch status to customers in `SelectOrderItems.php`.
7. Add credit status, limit and last stage to `AgedDebtors.php` (BR-31). Include types 80–83 in `Z_CheckDebtorsControl.php`, and register the type names in `DatabaseTranslations.php`.
8. Make waivers reverse to the GL account the charge actually used, not the current setting.

### B (most serious first)

1. Make `install/sql/data/menuitems.sql` a single statement (or move the credit menu rows to their own data file). As it stands, a fresh install has no menus.
2. Fix or remove the no-op `$CreditHoldSQL`/`$CreditLimitSQL` block in `Customers.php`. Either let token 21 edit (and log) or make the fields read-only for everyone, and say so.
3. Update `CreditStatus.php` to offer Normal/Watch/Stop, and protect the configured codes, as A did.
4. Post charges at the selected month's end, or at a chosen run date within an open period, not at today's date.
5. Split the exemption into interest and fee flags (BR-20).
6. Block `InvoiceSalesOrder` in the API for stopped customers or held orders.
7. Provide a way to release an individual order of a stopped customer, if the business wants BR-06's "unless credit control releases them" beyond held orders.
8. Guard against division by zero on a currency rate of 0 in the charges code.
9. Add the aged debtors columns to the PDF as well, not just the screen view.

## 7. Other observations

**Good in A**
- It fixes `CreditStatus.php` properly and protects the codes in use.
- Its write-off code deletes the request if a below-limit posting fails.
- It has a "leave out of reminder runs" flag per customer (useful for agreed payment plans) and lets the user choose the charge run date.
- Its in-report reconciliation by system type is useful for BR-38 diagnostics, even though it duplicates an existing tool.

**Good in B**
- The `CustomerInquiry.php` tampering fix is a genuine pre-existing security hole that the portal requirement (BR-36) exposed.
- The worklist's "final notice sent, still overdue, not on stop" list implements open question 4 sensibly.
- The go-live history rows for existing stops give auditors a starting point.
- The waiver reverses to the account the charge actually hit.
- Letters for customers without email are printed with their text.
- The interest option and fee-per-invoice option answer open questions 2 and 3 without hard-coding a choice.

**Bad in B**
- A below-limit write-off whose posting fails (for example, no bad debt account set) is left `pending` and lands in the Finance Director's queue.
- The portal page's menu item is added for every role in the upgrade, so staff see "My Account - Reminders and Charges".

**Bad in both**
- No PDF letters for posting.
- The letter text is not available in the customer's language.
- Both send the email before recording the letter.

## 8. Verdict

**B, somewhat.**

- B delivers materially more of the business request: over-limit holds and releases, aged debtors status, a proper authority model, the portal fully wired and secured, and ledger agreement in the existing integrity tool.
- B's logic for not chasing customers who have paid is correct, where A's can send a final notice right after a payment.
- B's worst defect (no menu on a new install) is severe but has a one-line fix. Its other defects are local.
- A's shortfalls are structural: a missing requirement (BR-10), credit authority shared with purchasing and AR clerks, a broken demo install, and a flawed dunning cycle. Fixing them means redoing parts of A's design.
- A did get the hold-reason maintenance page right, which B missed.

Scores: **A 5/10**, **B 6.5/10**.
