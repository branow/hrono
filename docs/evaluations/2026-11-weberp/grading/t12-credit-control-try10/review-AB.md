# Review: T12 Credit Control, implementation A vs implementation B

Reviewer stance: I am the webERP maintainer who would have to merge this and live with it. I read both diffs in full, read the touched parts of both trees, and checked the claims that matter against the base tree (`scratchpad/base`). Nothing was executed (no PHP or DB here), so "would fail" below means I traced it through the code.

## Summary

Both implementations make the same main design choice, and it is the right one. Stop and watch are built on webERP's existing credit status (`debtorsmaster.holdreason` → `holdreasons.dissallowinvoices`: 0 normal, 1 stop, 2 watch). They don't add a second flag. Both add the same kinds of things:

- a `creditheld` flag on sales orders,
- review, log, dunning, charge and write-off tables,
- new debtortrans types in the 51–5x range,
- tokens 21 and 22,
- an update `44.php`, install seeds and demo seeds,
- a manual chapter.

The scope is close to identical. The difference is in execution:

- **A** gets the accounting and the enforcement routes more right. That covers FX differences on write-offs and waivers, netting unallocated cash before charging interest, month-end dating, extending the existing debtors-control integrity check, and blocking the API invoice route. It has no crash-level bugs that I found. Its gaps are functional: watch customers still can't use the web shop, the portal account page doesn't show the new charge rows, and a fresh install has no stop or watch status to use.
- **B** covers the user-facing side more thoroughly: a status banner on SelectCustomer, reminders and charges on the portal account page, watch customers allowed in the web shop. It also follows webERP's convention for GL accounts (columns on `companies`). But it ships two hard breakages:
  1. A fresh non-demo install can no longer insert the company record.
  2. The reminder run's email call breaks when webERP is set up for SMTP.

  It also leaves the existing integrity and movement reports misreporting the new transaction types.

---

## 1. Completeness against the BRD

| Area | A | B |
|---|---|---|
| Reviews (BR-01..04) | `CreditReview.php`. Limit, status, next date and exemptions are saved in one transaction with the review row. The outcome is derived from what changed. Review history is append-only. | `CreditControl.php`. The user picks the outcome and its consistency is validated (raise must raise, and so on). Limit, status and next date change in one transaction. |
| Review date on new accounts (BR-02) | Customers.php, Z_ImportDebtors, API InsertCustomer. | The same three. |
| Stop/watch with reason, who, when (BR-05) | Via a review with notes. Every change goes through `CreditSetHoldReason` and is logged. | A dedicated "Change status" form with a required reason, plus via review. |
| Stop on every order route (BR-06) | DeliveryDetails (sales office and portal), RecurringSalesOrdersProcess, EDI, API header, ConfirmDispatch_Invoice, **API InvoiceSalesOrder**. | DeliveryDetails, Recurring, EDI, API header, ConfirmDispatch_Invoice. **The API invoice route is not blocked.** |
| Only credit control changes stop or limit (BR-07) | Customers.php no longer writes `creditlimit` or `holdreason` on update. A new account gets the default limit and a normal status unless the user holds token 21. The API ModifyCustomer strips the fields. | Customers.php restores the stored values for non-controllers on update. **A non-controller can still set the opening limit on a new account** (readonly is client-side only). |
| Watch: still supplied, warned, listed (BR-08) | Warnings and a held/watch orders page. **Watch customers still cannot order in the web shop**: base `SelectOrderItems.php:539` only lets status `0` through on the portal path, and A did not touch it. | Fixed (`!= 1`). Warnings and a held/watch orders list. |
| Status visible wherever staff look (BR-09) | CustomerInquiry/CustomerAccount banners, existing order-entry warnings, aged debtors. | All of the above **plus a SelectCustomer banner**, which is where staff actually "look at a customer". |
| Over-limit orders held (BR-10) | A new `CheckCreditLimits = 3` "hold" mode in SystemParameters. The upgrade forces 0/1 → 3, but a fresh install stays at 1 (warn). | A `CreditHoldOverLimit` flag that applies when CheckCreditLimits > 0. The default config is 1, so it works out of the box. |
| Customer told they are on hold (BR-11) | Existing portal message, plus A's CreditHistory. | Existing portal message, plus explicit messages in DeliveryDetails and CustomerAccount. |
| Dunning stages, wording, days (BR-12) | `DunningStages.php`: any number of stages, a final-notice flag, **wording per language with English fallback** and placeholders. | Stages edited inside `CreditControlSetup.php`: days, subject, body, autostop. One language. The invoice table is appended to the body. |
| Email to accounts contact, list the no-email ones (BR-13) | Statement contacts. Letters for post are listed with their full text. | Statement contacts. "Record as posted" button. **Email breaks on SMTP setups** (see §2). |
| Preview, exclude, weekly run (BR-14) | Yes. | Yes. |
| Escalation only while overdue, no repeats (BR-15) | Highest stage reached; no repeat of a stage within the current overdue episode; a minimum gap between any two letters. | Highest stage reached; the same stage is not repeated within N days. **The final notice repeats every N days for as long as the debt stays unpaid.** |
| Reminder recorded with invoices and amount (BR-16) | `dunninglog` stores the full letter text. | `dunninglog` stores invoices and amount, not the letter text. |
| Disputed invoices (BR-18) | Yes, excluded from both dunning and interest. | Yes, excluded from both. |
| Interest and fee settings (BR-19) | Rate, fee, days, and GL accounts in config through `CreditControlSettings.php`. | Rate, fee and days in config; GL accounts on `companies` through CompanyPreferences, the webERP convention. |
| Exemptions (BR-20) | Yes. | Yes. |
| Customer currency, separate items, statement (BR-21) | Types 51 (interest) and 52 (fee) are separate. Statements and CustomerInquiry show them. **CustomerAccount.php does not render them** (base only renders 10/11/12, `CustomerAccount.php:281-385`), so the portal account lists lines that don't add up to the balance. | One type, 51, with descriptive text. **B adds a CustomerAccount branch for 51–53** and lists reminders and charges there. |
| Preview, confirm, no double charge (BR-22) | Yes. A unique key on (debtor, month, type), plus a re-check at post time. | Yes, with the same unique key. |
| Waiver reaches the ledger (BR-24) | Yes. The waiver is at today's rate, allocated to the charge, and the FX difference is posted. | Yes. The waiver is at the charge's own rate for the remaining balance only, so a paid charge can't be waived. |
| Write-off, approval, FX, auto-stop, report (BR-25..29) | Yes. **Requester ≠ approver is enforced.** The FX difference goes to the exchange-difference account. | Yes. The FX difference is folded into bad debt by giving the write-off an effective rate. No segregation of duties. |
| Credit control report (BR-30) | Yes. Filters by rep and currency, home-currency totals, a look-ahead window for reviews due. | Yes. |
| Aged debts show status, limit, last stage (BR-31) | Yes. | Yes. |
| Per-customer audit history (BR-32) | `creditlog` plus `CreditHistory.php`, with role-filtered views. | `creditlog` shown on `CreditControl.php`. |
| Reps see only their own customers (BR-33/34) | Yes. | Yes. |
| Portal shows reminders and charges (BR-35/36) | Via `CreditHistory.php`, which portal users can open (token 1). The `?CustomerID=` hole in CustomerInquiry/CustomerAccount is closed using a new `LoginCustomerID`. | On CustomerAccount itself. The same hole is closed using `$CustomerLogin`. |
| GL and sub-ledger agree, diagnose differences (BR-37/38) | Extends the existing `Z_CheckDebtorsControl.php` for the new types and fixes its `DiffTotal` bug. Lists entries missing from either side. Also updates CustomerBalancesMovement and DebtorsAtPeriodEnd. | A new all-time `CreditReconciliation.php`. **The existing integrity check, movement report and period-end report are not taught the new types.** |
| Install and upgrade (BR-39/40) | Update 44, in-place data-file edits, demo seeds, a dry-run-then-confirm import utility. **No stop or watch hold reason is seeded on a fresh install** (base has no `holdreasons` data at all). | Update 44, `zz_credit_*` data files, demo seeds, missing stop/watch statuses created on both install and upgrade, an all-or-nothing import. **The fresh non-demo install breaks** (see §2). |
| Staff guide and sales note (BR-42/43) | `ManualCreditControl.html` plus outline. Pages use `$ViewTopic='CreditControl'`, so the help links reach the new chapter. | The same. Pages use `$ViewTopic='AccountsReceivable'`, so the help links land in the wrong chapter. |

Things the business didn't spell out but webERP needs:

- Both handle `Z_ChangeCustomerCode` (moving the new tables) and the API.
- A also blocks customer deletion when credit records exist.
- B also updates `Z_ChangeGLAccountCode` for its three new company accounts, and makes `GetConfig.php` tolerate the columns not existing yet. That second one is a nice piece of upgrade-ordering awareness.

## 2. Correctness

### B: confirmed breakages

1. **Fresh non-demo install fails to create the company.** B adds three columns to `companies` (`install/sql/tables/companies.sql`). The installer inserts the company positionally: `INSERT INTO companies VALUES (1, …, '5600')` with 28 values (base `includes/InstallFunctions.php:505-532`). B didn't touch that file. On the new 31-column table MySQL rejects the row with a column-count mismatch, so a new installation has no company record. B's NOTES say the demo insert was extended, but this one was missed. This is BR-39 ("any new installation") broken.
2. **The reminder run breaks under SMTP.** `CreditAccountsEmails()` returns a list (`['a@b.com']`). In SMTP mode `SendEmailFromWebERP` → `SendEmailBySmtp` treats the keys as addresses: `foreach ($To as $ToAddress => $ToName) addAddress($ToAddress, …)` (base `MiscFunctions.php:854`). That calls `addAddress(0, 'a@b.com')` on a `PHPMailer(true)`. PHPMailer throws on invalid addresses in exception mode, and nothing catches it. So the weekly run dies on the first customer for any company using SMTP. The `mail()` path happens to handle numeric keys. A builds `$Emails[$email] = ''` and works in both modes.
3. **Existing reports misreport the new types.** `Z_CheckDebtorsControl.php` only counts types 10/11/12, so every month with charges or write-offs shows a red difference. `CustomerBalancesMovement.php` puts any non-10 type into "credits", so positive interest charges show as credits. B wrote a new reconciliation page instead of fixing these.
4. **API invoicing isn't blocked.** `api_salesorders.php InvoiceSalesOrder` will still invoice a held order or one for a stopped customer (BR-06).
5. **`Customers.php` (B) for non-controllers.** The status `<select>` is `disabled`, so `$_POST['HoldReason']` is never posted. Line 143 then compares an undefined key. That raises a notice and shows the "Only credit control can change…" warning on every save, even when nothing was touched. It is harmless to the data, but it will generate bug reports.
6. **Double escaping in the audit trail.** `$_POST` is already escaped by `session.php`, and `LogCreditEvent` escapes again, so reasons containing quotes are stored with backslashes. B admits this in NOTES. For an audit trail meant for auditors, it should be fixed. `LogCreditEvent` also doesn't pass the rollback flag, so a failed log insert inside a transaction won't roll it back.
7. **Money details.**
   - Interest is computed on gross overdue items, with no netting of unallocated receipts or credits, so customers who have paid on account are over-charged.
   - Charges and write-offs are always dated today in the current period. "Charge October" run on 3 November lands in November.
   - Interest is a flat 1/12 per month regardless of month length (acceptable as a documented choice).
8. **Fee on fees.** A customer whose only overdue items are earlier charges is still picked up for a fresh monthly late fee.

### B: what is good

- `CreditPostDebtorTrans` calls `EnsureGLEntriesBalance`.
- The write-off posts exactly what debtors control carries for the items cleared (each item at its own rate). The control account clears cleanly, with no separate FX line. That's a legitimate and simple treatment.
- The update is guarded by `Errors == 0`, which is the current convention (`43.php`).
- The upgrade creates stop and watch statuses only when they're missing.
- `GetConfig` tolerates the new columns not existing yet.

### A: problems

1. **Watch customers are blocked in the web shop.** The portal path in base `SelectOrderItems.php:539` accepts only `dissallowinvoices == 0`. A's NOTES describe the existing watch handling but missed that this branch contradicts BR-08 for web-shop customers. It's a one-line fix.
2. **Portal account page.** Charges, waivers and write-offs are included in the balance but not listed on `CustomerAccount.php`, the portal statement page (see table). A's NOTES claim the new types print "on the existing statement, account inquiry and portal without touching those pages". That holds for the statement PDF and CustomerInquiry, but not for CustomerAccount. A partly compensates through `CreditHistory.php`, which portal users can open and which lists reminders and charges, but the account page itself looks wrong.
3. **No stop or watch status on a fresh install.** Base ships no `holdreasons` rows, and A doesn't seed any. Consequences:
   - `CreditStopReasonCode()` returns false, so the auto-stop after a write-off or final notice silently does nothing.
   - The go-live import rejects "stop" and "watch" lines until someone creates the statuses by hand.
   - The manual tells admins to do this, but it should be seeded.
4. **Upgrade changes a live setting.** The upgrade rewrites `CheckCreditLimits` 0/1 → 3. That's what BR-10 asks for, but it's a behaviour change applied silently on the live system, and it's inconsistent with a fresh install (which stays at 1). In mode 3, CounterSales and Contracts only warn; they don't hold. Counter sales invoice immediately, so an over-limit counter sale goes straight through.
5. **Unescaped output.** Review notes, `creditlog.description` and write-off reasons are echoed without `htmlspecialchars` in CreditReview, CreditHistory and CreditWriteOffs. It's stored XSS from credit-control users to auditors. The risk is low because it's internal, but it's sloppy next to the otherwise careful escaping.
6. **Upgrade guard.** `44.php` calls `UpdateDBNo` unconditionally, the older pattern of `42.php`. It should be guarded like `43.php`.
7. **Charges into closed periods.** Charges for a past month are dated at that month's end without checking `ProhibitPostingsBefore`, so they could post into a closed period.
8. **Minor.**
   - On a modified order, DeliveryDetails evaluates over-limit with value 0, so the increase isn't checked. B behaves the same way.
   - N+1 queries in AgedDebtors, the dunning preview and the charges preview. That's fine at 900 customers.

### A: what is good

- `CreditInsertDebtorTrans` and `CreditAllocate` mirror CustomerAllocations. The FX difference is posted debtors↔`salesexchangediffact`, and I checked the sign with a worked example: the invoice at rate 1 is written off at rate 2, and debtors control clears to zero.
- The waiver nets against the charge.
- The interest base excludes earlier charges and nets unallocated cash.
- Charges are dated at month end.
- Requester ≠ approver is enforced.
- The import is dry-run by default and rolls back unless confirmed.
- A single `CreditOrderCheck()` is used by every order route, so there's one rule to maintain.

### Both

- `CreditStatus.php` is still token 3 (AR clerk, purchasing officer). Anyone with it can switch the kind of an existing hold reason, for example change "On Stop" to normal. That takes every customer on that reason off stop with no log entry. It undermines BR-07 in both, and neither moved the page or logged changes there.

## 3. Fit with webERP

- **Pages and forms.** Both use the standard `session.php` / `header.php` / `prnMsg`, fieldset/field forms and FormID. Both are fine.
- **Settings.** B is more idiomatic for GL accounts: they live on `companies` and are edited in CompanyPreferences, with `Z_ChangeGLAccountCode` updated. But B then needs installer changes it didn't make. A keeps the accounts in `config` and edits them on its own settings page. That's less conventional, but it's self-contained and safe to upgrade.
- **Credit-limit mode.** A extends the existing `CheckCreditLimits` option with a third value, which fits webERP better. B's extra `CreditHoldOverLimit` flag, which only matters when CheckCreditLimits is Warn, is a second setting interacting with the first and is harder to explain.
- **Install data.** A edits the existing per-table data files, which is the convention, while keeping each file a single statement. B adds `zz_credit_*` files that depend on glob ordering and `INSERT … SELECT` from `securityroles`. That works, but it's a new pattern that a future table-dump regeneration (`Z_CreateTableFiles`) would not reproduce.
- **Updates.** B follows the guarded `UpdateDBNo` convention; A doesn't.
- **Manual.** Both add `ManualCreditControl.html` and an outline entry. A's `$ViewTopic='CreditControl'` makes context help land in the new chapter. B's `'AccountsReceivable'` does not.
- **Existing utilities.** A extends `Z_CheckDebtorsControl` (and fixes its pre-existing DiffTotal-before-assignment bug), CustomerBalancesMovement and DebtorsAtPeriodEnd. That's the right place. B duplicates the concern in a new page and leaves the old ones wrong.
- **Translations.** Neither adds .po strings. That's normal for webERP, where they're extracted later.
- **CreditStatus.php edit.** B rewrote the branches cleanly. A left `if (true) { … } else { … }` with a dead else branch, which a maintainer would reject on sight.

## 4. Structure and code quality

- **A.** About ten focused pages and a 390-line `CreditControlFunctions.php`. Naming is consistent (`Credit*`), and there are named constants for types and tokens. `CreditOrderCheck` is the single gate. The comments explain business intent. The weak spots are the `if (true)` hack, unescaped output in three places, and log writes wrapped in their own tiny `DB_Txn_Begin/Commit` blocks in places where they could just join the surrounding transaction.
- **B.** A one-page-per-customer hub (`CreditControl.php`, about 380 lines with five POST actions) plus focused pages. The function library is similar in size. Naming is a bit mixed (`GetCreditStatus`, `SetCreditStatus`, `LogCreditEvent`, `CreditOverdueItems`). Output escaping is consistently good. `CreditPostDebtorTrans` with `$HomeAmountOverride` is a neat way to handle the write-off. B does duplicate the over-limit logic in three places (DeliveryDetails inline, `CreditHoldIfOverLimit`, the API), where A has one function.

Both are maintainable. A is a little more uniform. B is a little cleaner on presentation.

## 5. Regressions

**A**
- Upgrading flips CheckCreditLimits on live systems: "do not check" and "warn" both become "hold".
- Customers.php no longer lets *anyone* edit limit or status, including administrators. That's intended, but it's a visible workflow change.
- Pre-upgrade portal sessions see nothing until the user logs in again (documented).
- Hold reasons stored as -1 are rewritten to 0, which changes the "ACCOUNT ON HOLD" banners for those customers. That is arguably a fix.

**B**
- Fresh install breaks.
- The debtors-control integrity check and the customer balances movement report become wrong once any charge or write-off exists.
- Non-controllers get a spurious warning on every customer save.

## 6. What a maintainer must fix before merging

### A (most serious first)

1. `SelectOrderItems.php` portal branch (line 539): change `== 0` to `!= 1` so that watch customers can order in the web shop (BR-08).
2. `CustomerAccount.php`: render types 51–54 (or add a generic `else` row like CustomerInquiry has) so that the portal account lines add up to the balance (BR-21/35).
3. Seed stop and watch `holdreasons` on fresh install, and create any missing ones in `44.php`. Otherwise auto-stop and the go-live import silently fail.
4. Don't silently migrate `CheckCreditLimits` on upgrade, or at least make install and upgrade consistent. Decide what mode 3 means for CounterSales and Contracts.
5. Escape output of notes, log descriptions and write-off reasons.
6. Replace the `if (true)` blocks in `CreditStatus.php`. Restrict that page to token 21, or log changes to a reason's kind.
7. Guard `UpdateDBNo` with `$_SESSION['Updates']['Errors'] == 0`.
8. Respect `ProhibitPostingsBefore` when dating charges into a past month.

### B (most serious first)

1. `includes/InstallFunctions.php`: add the three new values to the positional `companies` INSERT, or better, name the columns. A fresh install is broken without this.
2. `CreditAccountsEmails()`: return `[$email => '']` so the SMTP path works.
3. Teach `Z_CheckDebtorsControl.php`, `CustomerBalancesMovement.php` and `DebtorsAtPeriodEnd.php` the new types, or retire them in favour of the new page. As it stands, the existing integrity check reports false differences.
4. Block held and stopped orders in `api_salesorders.php InvoiceSalesOrder`.
5. `Customers.php`: don't rely on a disabled select. Use a hidden field or `isset()`, and enforce the opening limit server-side for non-controllers.
6. `LogCreditEvent`: stop double-escaping `$_POST` text, and pass the rollback flag inside transactions.
7. Net unallocated credits out of the interest base. Date charges at the end of the charged month and post them to that period.
8. Stop the final notice re-sending every N days indefinitely, or make that an explicit setting.
9. Set `$ViewTopic='CreditControl'` on the new pages.
10. Fix the `CreditStatus.php` token issue (same as A). Consider requester ≠ approver for write-offs.

## 7. Other observations

- Both NOTES files are candid that nothing was executed. B's NOTES claim "the demo seed … plus the positional `companies` insert extended", which shows B knew positional inserts were a hazard, yet it missed the installer's own one.
- A's dunning letters store the full rendered text, and the portal can show it. For auditors, that's better evidence than B's invoice list.
- A's credit control report has a "reviews due within N days" look-ahead, which suits Maria's Monday routine (user story 1).
- A's `CreditHistory.php` gives three graded views: full audit for token 21 or 8, rep view, customer view with watch status hidden. That's a thoughtful way to cover BR-32/33/35 with one page.
- B's per-stage "put on stop when sent" is more flexible than A's single global auto-stop-after-final setting.
- B's `GetConfig.php` guard is a detail many contributors miss: the config is loaded before the update runs.

## 8. Verdict

**I'd rather merge A, somewhat.**

The two are close in scope and both picked the right foundation. A's defects are gaps in coverage: the web-shop watch branch, the portal account rows, seed data, and a heavy-handed setting migration. Each is a small, local fix, and none corrupts data or crashes a core workflow. A's ledger handling (FX on write-offs and waivers, netting, month-end dating, extending the existing integrity check) and its route coverage (including API invoicing) are what I'd least want to rework.

B is nicer in several user-facing places, and its GL-account placement is more idiomatic. But as delivered it breaks a fresh non-demo install, it breaks the reminder run on SMTP mail setups, and it leaves the month-end integrity tools reporting false differences. Those are exactly the things BR-37/39 and AC-08/11 test. They're individually easy to fix once found, but more of them land on the maintainer, and they're more serious.

**Scores: A 7/10, B 5/10.**
