# Review: Credit Control, implementations A and B

Reviewer stance: webERP maintainer who would have to merge and maintain this. I read both diffs in full, the new pages and the shared function files, and compared them with the base tree (`scratchpad/base`). I checked the key claims against the code and against webERP's own helpers (`DB_query`, `SendEmailFromWebERP`, `InstallFunctions.php`, `session.php`, `index.php`). Both trees pass `php -l` on every changed PHP file.

Both implementations share the same skeleton: the credit status is the existing `debtorsmaster.holdreason`, with `holdreasons.dissallowinvoices` 0/1/2 as normal/stop/watch (webERP already uses that in CounterSales and SpecialOrder). Each adds systypes 51/52/53 for charge, waiver and write-off, tokens 21 (credit control) and 22 (approval), a `disputed` flag on `debtortrans`, a hold state on `salesorders`, upgrade `sql/updates/44.php`, and tables for reviews, an event log, dunning stages and letters, charges and write-offs. The differences are in the details, and the details decide this.

---

## 1. Completeness

### A
- Reviews (BR-01..04): `CreditReview.php` records outcome, old/new limit, old/new status, notes and next date in one transaction. The limit is updated with the review. The history is read-only. New customers get `nextreviewdate` from `CreditReviewMonths` in `Customers.php` and the API. The upgrade dates every existing customer.
- Stop/watch (BR-05..09): status changes go through the review form, which needs a reason. Every change is logged in `creditcontrollog`. A status banner shows on SelectCustomer, CreditReview and ConfirmDispatch. CustomerInquiry and CustomerAccount show "ON WATCH" or "ON HOLD".
- Enforcement on every route (BR-06): DeliveryDetails (sales office and web shop, new and modified orders), EDI, recurring orders, API header **and lines**, ConfirmDispatch_Invoice **and API `InvoiceSalesOrder`**. Orders taken before a stop are listed on the credit control report and can be released one by one (`creditstatus = 2`). That is exactly "unless credit control releases them".
- Over-limit hold (BR-10): applies whenever `CheckCreditLimits > 0`, so it is on by default. Modified orders are re-checked against their outstanding value.
- Dunning (BR-12..18): configurable stages with add/edit, one stage at a time, a "paid since last letter" restart, a minimum gap between letters, a preview with untick, recompute at send time, email to statement contacts, a postal list, a per-customer record with the invoices covered and the amount, the customer's own currency, disputed items excluded, and a per-customer "no reminders" exemption. Optional auto-stop after the final notice (`DunningAutoStop`, answering open question 4).
- Interest and fees (BR-19..24): rate, fee and grace days are configured. Interest and fee exemptions are **separate**. Preview and confirm, with the charge month and charge date chosen by the user. A unique key on (customer, month, type) prevents a double charge. Charges are posted in the customer's currency (the fee is converted from home currency). GL accounts are chosen in Company Preferences. Waiver reverses at the charge's own rate and is allocated to it.
- Write-offs (BR-25..29): partial or full, with a reason. Approval above the limit by token 22, with approve and reject. Allocation to the oldest items first. Dr bad debt, Cr debtors at the current rate, plus an exchange difference entry so that debtors control is relieved at the original rates. Auto-stop with an opt-out checkbox. Separate write-off report.
- Reporting (BR-30..32): one credit control report covers reviews due, over limit, watch and stop, and held/pre-stop/watch orders. It filters by rep and currency and totals in home currency. AgedDebtors gains status, limit and last stage. There is a per-customer audit trail.
- Reps (BR-33/34): reps are restricted to their own customers (`custbranch.salesman`). Limit and status changes are blocked in `Customers.php` and the API (`ModifyCustomer`) without token 21.
- Portal (BR-35/36): `CustomerCreditAccount.php` shows the customer's own letters, charges and balance, taken from the session. It is linked from the customer-login home menu in `index.php`. Watch is never shown to the customer.
- Ledger (BR-37/38): new `CreditDebtorsReconciliation.php` compares the customer ledger and debtors control by transaction type and lists unmatched entries.
- Install/upgrade (BR-39/40) and manual (BR-42/43): a new `ManualCreditControl.html` registered in `ManualOutline.php`, with a section for sales staff.
- Gaps: there is no import of the stop list (both rely on existing hold codes). Demo installs are not seeded (see below). The customer-portal IDOR in `CustomerInquiry.php?CustomerID=` (it predates both changes) is not closed.

### B
- Reviews: `CreditCustomer.php` has a review form plus a **separate** "change status with reason" form, a "note" form (for agency or legal notes, which the BRD asks for) and per-invoice dispute buttons. The upgrade also writes a go-live history row for customers already on hold. That is a nice audit touch.
- Enforcement: DeliveryDetails, EDI and recurring orders are covered, the API header is checked, and ConfirmDispatch_Invoice is checked twice (on open and on process).
  - **Not covered:** API order lines, API `InvoiceSalesOrder` (an on-stop customer can still be invoiced through the API), and API `ModifyCustomer` (anyone with API access can change limit and holdreason).
  - Modified existing orders are never re-checked for the limit.
  - **No way to release an order taken before a stop.** Release only works on `creditholdstate = 1`. The manual says the opposite ("Credit control can release an individual order from the Credit Control Worklist").
- Over-limit hold: only when `CheckCreditLimits = 3`, a new option. Neither the installer nor the upgrade sets it, so out of the box over-limit orders are only warned, as today. That is how the setting has always worked, but BR-10 is not delivered until someone changes it.
- Dunning: settings and stages exist. A preview lists the customers skipped and why. The letter is recomputed at send time.
  - The stage logic picks the **highest** stage whose threshold is passed, so stages are not escalated one at a time. A customer 70 days overdue with no letter history (for example everyone at go-live) gets the FINAL NOTICE first.
  - There is no per-customer reminder exemption (only per run).
- Interest and fees: answers more of the open questions as settings (fee per invoice, interest on charges). Interest is pro-rated by days in the month. But there is a **single** `chargeexempt` flag, so a customer cannot be exempted from interest only or from fees only (BR-20 "and/or"). Charges are always dated today, whatever month is selected.
- Write-offs: the same flow, posted at the historical rate of the items settled. Request, approval queue and period report are on one page.
- Reporting: the worklist is good and adds "final notice sent, still overdue, not on stop". AgedDebtors gains the three columns. `Z_CheckDebtorsControl.php` now includes types 51-53, which reuses the existing integrity tool.
- Portal: `CustomerCreditPortal.php` is correct in itself, and B **closes the CustomerInquiry IDOR** for portal users. But the page is **not reachable by a customer**: a customer login gets the special `index.php` menu, which B did not touch. The menu item went into the AR Reports module, which customer logins never see. The page also shows raw `10/123 2026-01-01 100.00;` strings to customers as "invoices covered".
- Install: B seeds demo installs (`install/sql/creditcontrol_demo.sql` plus an `InstallFunctions.php` hook) and adds systype names to `DatabaseTranslations.php`. A did neither.

On completeness, A wins. It covers more routes and holds by default, and its portal is reachable. B has more breadth in settings, notes and go-live history, but it misses routes and has a dead portal link.

---

## 2. Correctness

### Ledger and money
- **A, wrong `settled` flag (data integrity).** `CreditWaiveCharge` and `CreditPostWriteOff` run
  `UPDATE debtortrans SET alloc = alloc + X, settled = IF(ABS(ovamount+... - alloc - X) < 0.005, 1, 0)`.
  MySQL and MariaDB evaluate single-table SET assignments left to right, so `alloc` in the second expression is already the new value. X is subtracted twice. Any item **fully** settled by a waiver or write-off keeps `settled = 0` with a zero balance. Every waived charge hits this. Money totals are unaffected, since balances are right. But every webERP screen that lists `settled = 0` items (statements' outstanding section, allocations, inquiries) will show these dead zero lines forever. B's `CreditAllocate` writes the same statement correctly (`- alloc` only).
- A's postings otherwise balance. Charges: Dr debtors, Cr income at the customer rate. Waivers: reversed at the charge's rate. Write-offs: Dr bad debt at the current rate, with a correcting debtors/exchange-difference pair so that the control account is relieved at the original rates. `EnsureGLEntriesBalance` is called.
  - The GL account fields live on `companies` with Company Preferences pickers, as the other GL accounts do, and `Z_ChangeGLAccountCode.php` was extended for them.
  - A's own reconciliation page will show a spurious per-type difference on type 53 when there is an FX write-off, because `diffonexch` is not taken into account. Cosmetic.
  - A did not update the existing `Z_CheckDebtorsControl.php`, which will now report a difference equal to all type 51-53 postings.
- B's postings balance. It derives the GL from the home amount and sets `debtortrans.rate = cust/home`, so write-offs are booked at historical value with no exchange-difference line. The ledger agrees, and that is a defensible reading of "including any currency difference". GL accounts are kept as `config` values and validated against `chartmaster`, but they are not covered by `Z_ChangeGLAccountCode.php`.
- B approval: it sets `status = 'approved'` before `CreditPostWriteOff` opens its transaction. If posting then fails (for example the customer now owes less), the request is stuck in 'approved': it is no longer in the pending list and is never posted.
- Both write a transaction per customer per charge type, so a failure mid-run leaves the earlier customers posted. That is fine. In both, an SQL error inside a transaction exits, and the open transaction is rolled back implicitly at disconnect. B omits the `$Transaction = true` argument webERP uses, but the outcome is the same.

### Currencies
- Both charge in the customer's currency and convert a home-currency fee at the current rate. Both total previews and reports in home currency. A's write-off approval limit is compared to the home value at the current rate. B compares it to the historical home value.

### Sequences
- Both use `GetNextTransNo` on new systypes 51-53. Both register the types through `NewSysType` in the upgrade and in `systypes.sql`.

### Email
- **B is broken on SMTP installs.** `CreditAccountsEmails` returns a list (`[0 => 'a@b']`). `SendEmailFromWebERP` copes with numeric keys only on the `mail()` path. The SMTP path calls `addAddress($ToAddress, $ToName)` with `$ToAddress = 0`, on a `PHPMailer(true)` that throws. So the reminder run dies on the first emailed customer.
- A passes `email => name`, which is what both paths expect. Both fall back to a postal list on screen. Neither produces a printable PDF letter, which would be the webERP way for "post the letter".

### Hold enforcement
- A covers every route listed in BR-06, including API invoicing and the release of pre-stop orders.
- B misses API lines and API invoicing, cannot release pre-stop orders, and holds only under the non-default setting 3.
- Both block at ConfirmDispatch_Invoice only. Picking lists and delivery notes are not gated in either. That is acceptable, because the invoice is where goods leave the books.

### Install and upgrade
- **Both break the fresh install.** `InstallFunctions.php` loads each `install/sql/data/*.sql` with a single `DB_query()`, which is `mysqli_query` and runs one statement only.
  - A appended a **second** `INSERT` statement to `config.sql`, `scripts.sql` and `menuitems.sql`. On a new install all three files fail completely, leaving no configuration, no script security and no menus. The installer reports "Database tables could not be populated" and the system is unusable.
  - B appended a second `INSERT` only to `menuitems.sql`, so a fresh install has an empty main menu. B folded its config rows into the existing statement and left `scripts.sql` intact, so the damage is smaller.
  - Both fixes are mechanical (merge into the existing statement), but neither author can have run a fresh install.
- Demo install: webERP's demo path loads `demo.sql` instead of `data/*.sql`. A has no config, scripts, tokens, systypes or stages there, so its pages fail on a demo database: there is no script security, and inserts hit the systypes FK. B handled this with a separate demo seed file.
- Upgrade: both `44.php` scripts are idempotent through `AddColumn`, `CreateTable`, `InsertRecord`, `NewConfigValue` and `NewScript`, and both date existing customers.
  - A reuses holdreason codes 90/91, or the lowest code of the right kind.
  - B reuses an existing code of each kind or creates one, maps them in config, and lets Finance remap them in settings. That is more robust on a live system with its own codes.
  - B's `nextreviewdate` is NULL-able. B's `CreditCustomerRecord` INNER-JOINs holdreasons, so customers with orphan hold codes become invisible ("no authority").

---

## 3. Fit with webERP

- Pages: both follow the house page shape: `session.php`, `$Title`/`$ViewTopic`/`$BookMark`, header and footer, `prnMsg`, FormID, `selection` tables, `locale_number_format`, `__()` everywhere.
- Security:
  - A gates actions inside pages through pseudo-script rows `CreditControlAction`/`CreditControlApproval` in `scripts`. That lets an admin remap the token in Page Security, but it is a small invention; webERP usually hard-codes a token number in the page, as `$PricesSecurity = 12` does.
  - B checks tokens 21/22 directly, which is closer to the precedent. B registers its worklist and customer pages at token 1 (customer-login level) and then rejects portal users in code, and it put the worklist in role 7's menu. That is untidy.
- GL accounts: A uses `companies` columns plus the Company Preferences pickers (`FieldToSelectOneGLAccount`), the established pattern. B uses `config` keys with its own settings page.
- Credit limit checking: B extended the existing `CheckCreditLimits` parameter with a third option and updated every place that tests it. That is idiomatic, but the option is off by default. A silently reinterprets the existing "warn" setting as "hold", which is a behaviour change existing users did not ask for, even though it is what this BRD wants.
- Existing Credit Status maintenance: A turned the "disallow invoices" checkbox in `CreditStatus.php` into a three-way select (normal/watch/stop). That is a real usability improvement, because the base page could not create a watch code at all. B leaves `CreditStatus.php` alone and points users to it.
- Integrity tools: B extended `Z_CheckDebtorsControl.php`. A wrote a parallel page and left the existing tool inaccurate.
- Translations: B added systype names to `DatabaseTranslations.php`. A did not.
- API: A added three error codes but **no `$ErrorDescription` entries**. B added one code with its description.
- Manual: A wrote a standalone chapter wired into `ManualOutline.php`, with `ViewTopic = 'CreditControl'` matching it. B appended a section to `ManualAccountsReceivable.html` and reused the AR topics. Both are acceptable. A's chapter is better organised. B's contains a false claim about releasing pre-stop orders.
- Upgrade scripts: both are in house style.
- PDFs: neither produces PDF letters. AgedDebtors gains columns in both. B's columns use a per-row `CreditLastReminderStage()` query, while A loads the letters once. A also widened the detail `colspan`; B did not, so B's detailed report rows are now misaligned.

---

## 4. Structure and code quality

- **A:**
  - One include of about 700 lines holds the domain logic: status, order check, invoice check, overdue data, dunning candidates, charges, posting, waive, write-off and status change. The pages are thin, and the order-check rule lives in one function that every route calls.
  - Functions are named consistently (`Credit*`), and the comments explain the business intent.
  - The duplication is small: decimal-place lookups and repeated `GetCreditStatus` calls.
  - The posting helper (`CreditPostDebtorTrans`) is reused for all three transaction types.
- **B:**
  - Also has one shared include, and it is well commented (the header comment explaining why status is not a new field is good).
  - But significant logic sits in pages: `CreditWriteOffPlan` and `CreditPostWriteOff` are defined in `CreditWriteOffs.php`, and `CreditCalculateCharges` in `CreditCharges.php`.
  - The charge and reminder previews call `CreditCustomerRecord` and `CreditOverduePosition` per customer, with several queries each (N+1). That is fine at 900 customers but wasteful.
  - The dead code in `Customers.php` (`$CreditHoldSQL = "" . $CreditHoldSQL . "";`) is a merge-quality red flag.
  - Status strings for write-offs (`'pending'`, `'approved'`, `'posted'`) are readable.
- Both concatenate request values into SQL. That relies on `session.php` escaping `$_POST`/`$_GET`, as all of webERP does. Some values are written back to HTML unescaped (notes, reasons), which matches the house style.

---

## 5. Regressions

**A**
1. Fresh install is unusable: `config.sql`, `scripts.sql` and `menuitems.sql` each have two statements.
2. Demo install: the credit control pages fail, because nothing is seeded into `demo.sql` paths.
3. Waived charges and fully written-off items stay `settled = 0`, and show as zero lines on statements, allocations and inquiries.
4. `CheckCreditLimits = 1` (warn) now holds orders. This is intended for this client, but it changes the meaning of an existing setting.
5. `Z_CheckDebtorsControl.php` now reports differences equal to all type 51-53 postings.
6. A credit-control user who changes a limit or status in `Customers.php` is not logged, which leaves an audit gap. Non-credit-control users are correctly blocked.

**B**
1. **`Customers.php` can no longer change credit limit or credit status for anyone.** Both SQL fragments are always empty. Credit control still sees editable fields, gets "Customer updated" and nothing is saved.
2. Fresh install has no menu items: `menuitems.sql` has two statements.
3. The reminder run crashes on SMTP-configured systems.
4. AgedDebtors' detailed report rows are misaligned (the colspan was not widened).
5. Staff users who happen to have `www_users.customerid` set are treated as portal customers by `CreditPortalCustomer()`. CustomerInquiry is pinned to that customer, and the credit pages are refused.

---

## 6. What a maintainer must fix before merging

### A (most serious first)
1. Merge the appended `INSERT` statements into the existing single statement in `install/sql/data/config.sql`, `scripts.sql` and `menuitems.sql`, then run a fresh install.
2. Fix the `settled` expression in `CreditWaiveCharge` and `CreditPostWriteOff` (drop the extra `- X`). Ship a repair update for rows already wrong.
3. Seed demo installs: config, scripts, tokens, security groups, systypes, menus and dunning stages.
4. Add types 51-53 to `Z_CheckDebtorsControl.php`, or point the manual at the new page and retire the inaccurate view. Account for `diffonexch` in `CreditDebtorsReconciliation.php`.
5. Add `$ErrorDescription` entries for API codes 1174-1176.
6. Log limit and status changes made in `Customers.php` by credit control. Better still, make those fields read-only there and send users to `CreditReview.php`.
7. Close the portal IDOR in `CustomerInquiry.php` for customer logins, since BR-36 requires it.
8. Make "hold over limit" an explicit option, not a reinterpretation of "warn". Add `DatabaseTranslations.php` entries for the new systypes.

### B (most serious first)
1. Fix `Customers.php`: either restore the `holdreason=`/`creditlimit=` fragments for token 21, or make the fields read-only for everyone and say so. Today it silently discards edits.
2. Pass email addresses as keys (`email => name`) to `SendEmailFromWebERP`; the SMTP path crashes otherwise.
3. Merge the second `INSERT` into the single statement in `install/sql/data/menuitems.sql`.
4. Add a release action for orders of stopped customers (state 0), or put open orders on hold when a customer is stopped, so that BR-06 works and the manual is true.
5. Guard the API: lines (stop and hold), `InvoiceSalesOrder` (stop and held), and `ModifyCustomer` (limit and holdreason need token 21).
6. Link `CustomerCreditPortal.php` from the customer-login menu in `index.php`. Show readable invoice lines.
7. Escalate dunning one stage at a time; do not jump to the highest stage passed.
8. Decide BR-10's default: set `CheckCreditLimits = 3` in the upgrade and installer, or hold whenever checking is on. Re-check modified orders.
9. Split `chargeexempt` into separate interest and fee flags. Let the charge date follow the chosen month.
10. Do not leave write-offs in 'approved' when posting fails: post first, or roll the status back.
11. Move the write-off and charge calculation functions into the include. Widen the AgedDebtors detail colspan. Add the config GL accounts to `Z_ChangeGLAccountCode.php`.

---

## 7. Other observations

- **Good in A:**
  - Recomputing the dunning and charge lists at submit time.
  - Refusing to approve a write-off when the customer now owes less.
  - Separate interest, fee and reminder exemptions.
  - The three-way Credit Status editor.
  - The release reason log.
  - Recurring orders: a stopped customer's template is left due, so the order is raised later.
  - An over-limit standing order is not auto-invoiced.
  - The sales-staff note in the manual is clear.
- **Good in B:**
  - The go-live history rows.
  - Free-text notes for agency or legal action (asked for in 4.2).
  - The "skipped and why" list in the reminder preview.
  - The "final notice sent, not on stop" worklist section.
  - The configurable hold-reason mapping.
  - Closing the CustomerInquiry IDOR.
  - Demo seed and translations.
  - Reps see only status, reminder and stop events, not internal reviews or write-offs (a reasonable answer to open question 8).
- **Bad in both:**
  - No PDF reminder letter for the postal list.
  - No bulk import for the go-live stop list. Both rely on existing hold codes, which BR-40 tolerates.
  - Both broke the fresh install the same way, which suggests neither ran it.

---

## 8. Verdict

**I would rather merge A, clearly.**

- **A's** design covers every order and invoice route, holds over-limit orders by default, and sends email correctly. Its customer portal is reachable, its ledger postings (including the exchange difference) follow webERP's own receipt handling, and its GL setup fits the existing Company Preferences pattern. Its serious faults are mechanical: three SQL seed files with a second statement, one wrong `settled` expression, and the missing demo seed. Each is a few lines to fix, and none needs a design change.
- **B** is thoughtful in places (settings, history, IDOR fix, demo seed, integrity tool). But its faults need design work as well as typo fixes:
  - it regresses customer maintenance;
  - its reminder emails crash under SMTP;
  - its letters skip stages;
  - it cannot release pre-stop orders, although its manual says it can;
  - it leaves the API invoice and line routes open;
  - it does not hold over-limit orders by default;
  - its customer page is unreachable for customers.

Scores, overall:
- **A: 6/10**
- **B: 4/10**
