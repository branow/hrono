# T12 Credit Control: Maintainer Review of Implementations A and B

Reviewer stance: a webERP maintainer deciding whether either branch could be merged and maintained. I read both diffs and trees in full and checked the important claims against the base tree (`includes/session.php`, `includes/InstallFunctions.php`, `includes/UpgradeDB_*.php`, `includes/DateFunctions.php`, `install/sql/tables/debtortrans.sql`, `CounterSales.php`, `sql/updates/43.php`). I did not rely on either branch's NOTES or summary files.

## Summary

**Neither branch can be merged.** Neither delivers a working credit-control feature. Both fail at install time. Neither reaches the core enforcement routes (sales orders, web shop, EDI, recurring orders, dispatch/invoice). Neither makes a single ledger posting.

- **A** is a set of seven plain CRUD/report screens: reviews, status, history, write-off request/approval, settings and a report. They follow webERP page conventions reasonably well. A also adds one enforcement hook, in `CounterSales.php`.
- **B** is one screen (`CreditReviews.php`), an unused helper library, ten table definitions and a broken upgrade script, plus about 1,200 lines of markdown that describe features that do not exist.

A is the better starting point, but only because it contains more salvageable code.

---

## 1. Completeness against the BRD

| Area | A | B |
|---|---|---|
| Credit reviews (BR-01..04) | Page exists; records the review and updates the limit and next review date. The date handling is broken (see §2). | Page exists, same shape, same date bug. |
| Next review date for new customers (BR-02) | Not done. `Customers.php` is untouched, so no default is set. | Not done. |
| Stop/watch with reason and audit (BR-05) | `CreditCustomerStatus.php` plus a `creditactions` log. | Table `creditstatus` defined; no page writes to it. |
| Stop enforcement on every route (BR-06) | Only `CounterSales.php` (the cash-sale counter, the least relevant route). Not in `SelectOrderItems.php`, `ConfirmDispatch_Invoice.php`, `RecurringSalesOrdersProcess.php`, EDI import or the shop/API. | None. |
| Role restriction (BR-07, BR-34) | None. No scripts registered and no tokens assigned (see §3). | Broken check that denies everyone (see §2). |
| Watch warning / visibility (BR-08, BR-09) | Warning only on CounterSales. No badge on `SelectCustomer.php`, `CustomerInquiry.php` or order entry. | None. |
| Over-limit hold (BR-10) | None. | `CheckCreditLimitWithOrder()` written but never called. |
| Web shop "account on hold" message (BR-11) | None. | None. |
| Dunning run, preview, exclusions, email (BR-12..17) | Settings for 3 stages and a `creditreminders` table only. No run page, no email, no letter or PDF. The stage count is fixed at three, against the BRD. | Config table and seed text only. No run, no email. |
| Disputed invoices (BR-18) | `debtortrans.disputed` column (in an un-runnable script); no UI. | `creditdisputedinvoices` table; no UI. |
| Interest/fees, exemptions, preview, no double charge, GL, waivers (BR-19..24) | Settings and a `creditcharges` table. No run, no exemption flag, no postings. | Config table, exemptions table and posted table with a `UNIQUE(debtorno, charge_period)`, which is a good idea. No run, no postings. |
| Write-offs with approval, GL, auto-stop, report (BR-25..29) | Request/approve pages and threshold logic; sets status to stop. **Posts nothing**: no `debtortrans`, no `gltrans`, balance unchanged, no FX difference. Reject deletes the record. | Table only. |
| Credit control report (BR-30) | Three lists (due for review, over limit, watch/stop). No rep or currency filter, no home-currency totals, and the balance maths is wrong. | None. |
| Aged debt columns (BR-31) | Not done. | Not done. |
| Per-customer audit history (BR-32) | `CreditCustomerHistory.php` covers reviews, status, write-offs, reminders and charges. Reasonable. | `creditcontrolactions` table plus a `RecordCreditAction()` helper that is never called. |
| Rep scoping (BR-33) | None. | None. |
| Customer portal (BR-35, BR-36) | None. | None. |
| Month-end reconciliation (BR-37, BR-38) | Nothing posts, so nothing to reconcile. | Same. |
| Install and upgrade (BR-39, BR-40) | Broken on both (see §2). No upgrade script at all. No initial next-review-date backfill and no stop-list load. | Upgrade script exists but is broken. Fresh install lacks the columns. |
| Manual and sales note (BR-42, BR-43) | Not done. `doc/Manual` untouched; `$BookMark`s point to nothing. | Not done. Markdown dropped in the repo root instead. |

Neither branch does the work the business left implicit but the feature needs: menu entries, `scripts`/security-token registration, a transaction type for interest/fee/write-off in `systypes`, statement printing of the new items, or reuse of the existing hold-reason mechanism. On coverage, A is perhaps 20–25% of the BRD as working-if-installed screens. B is under 5%.

## 2. Correctness

### Both

- **Neither branch is installed by the webERP installer.**
  - `CreateTables()` (`includes/InstallFunctions.php:300`) runs each `install/sql/tables/*.sql` file through a single `mysqli_query`. That call cannot run more than one statement.
  - A's `Z_Upgrade_AddCreditControl.sql` (7 `ALTER`s) and `Z_InitializeCreditControl.sql` (`INSERT`) are therefore errors. They also sort *before* the lowercase table files under `glob()`, so they run before `debtorsmaster` and `creditconfig` exist. The installer reports "Database tables could not be created".
  - B never touches `debtorsmaster.sql`, so a fresh B install has no `creditstatus`, `nextreviewdate` or `lastreviewed` column, and `CreditReviews.php` fails on the first query.
- **No new page is reachable.** Neither branch adds rows to `scripts`.
  - `session.php:331-337` looks up `$_SESSION['PageSecurityArray'][basename(SCRIPT_NAME)]`. When the entry is missing, it shows "The security settings on your account do not permit you to access this function" and stops, even for admin.
  - Neither branch adds menu entries to `MainMenuLinksArray.php`.
- **Both convert dates the wrong way.**
  - Both call `ConvertSQLDate()` on user-entered dates. That function converts SQL→display, not display→SQL (`DateFunctions.php:360`).
  - A user date such as `15/05/2027` fails `EnsureSQLDateFormat`, prints an error, and returns `'01/01/1000'`, which is then inserted into a `DATE` column. Under strict SQL mode the review insert fails; otherwise it stores garbage. Either way AC-01 fails.
  - The correct function is `FormatDateForSQL()`.
- **No transactions.** Multi-step writes have no `DB_Txn_Begin`/`DB_Txn_Commit`: the review insert plus limit update, the status log plus status update, and the write-off insert plus stop.
- **SQL injection everywhere.**
  - Neither branch escapes `$_POST` or `$_GET` values before concatenating them into SQL. Examples: `DebtorNo`, `Reason`, `Notes`, and settings values.
  - A apostrophe in a reason ("customer's cheque bounced") breaks the query.
  - webERP's `DB_escape_string` convention is ignored.
  - B uses `FILTER_SANITIZE_STRING`, which is deprecated since PHP 8.1. It HTML-encodes quotes, which mangles stored data rather than escaping it properly.

### A specifically

- **Write-offs are bookkeeping only.**
  - The customer balance and the GL are untouched, so BR-25, BR-27 and AC-08/09 are unmet.
  - The threshold is compared in the customer's currency against a home-currency setting.
  - Approve does not check that the row is still pending, so it can be "approved" twice. It also has no role check.
  - Reject `DELETE`s the request, which destroys audit evidence (BR-32).
- **Wrong balance maths.**
  - The over-limit report and `GetOutstandingBalance` use `SUM(ovamount) WHERE settled=0`. That ignores tax, freight, discount and allocations, so part-paid invoices count in full.
  - Balances in different currencies are summed together.
  - The base table already has a generated `balance` column (`debtortrans.sql:27`), which A should have used.
- **Status page has no checks.**
  - `CreditCustomerStatus.php` accepts any `Status` value and does not check that the customer exists before writing.
  - `ActionType` is a pointless one-option select.
- **Settings are not checked.**
  - GL codes are free text and not validated against `chartmaster`.
  - The seeded defaults (`4070`, `4071`, `6950`) may not exist in a given chart of accounts.
  - Reminder day thresholds are not validated as increasing.
- **Missing column breaks CounterSales.** `CounterSales.php` now selects `debtorsmaster.creditstatus`, a column A cannot create (see the installer problem above). The query fails, which **breaks the point-of-sale page on every installation**.
- **Status shown inconsistently.** In `CounterSales.php`, `creditstatus==2 || dissallowinvoices==1` now exits with a "cannot be invoiced" message. That part is fine. But `creditstatus` and `holdreasons` are two independent stop mechanisms, and the rest of webERP knows only the second.
- **Dead code.** `includes/CreditControlFunctions.php` is never included by any page, and it ends with a `?>` closing tag.

### B specifically

- **The upgrade script `sql/updates/44.php` is wrong throughout.** (The number 44 itself is correct; base ends at 43.)
  - `AddColumn('debtorsmaster', 'creditstatus', 'ENUM…', 'String')` passes arguments in the wrong order. The signature is `AddColumn($Column, $Table, $Type, $Null, $Default, $After)`, so the call tries to add a column named `debtorsmaster` to a table named `creditstatus`. `DB_table_exists('creditstatus')` is false at that point, so it silently does nothing. None of the three columns is ever added.
  - `CreateTable('creditreviews', 'creditreviews.sql')` passes a *file name* where SQL is expected. It executes `creditreviews.sql ENGINE=InnoDB …`, a syntax error, so all ten tables fail.
  - The seed `INSERT`s and the `nextreviewdate` backfill then fail.
  - `UpdateDBNo` is never reached, so the upgrade re-runs and fails on every visit.
- **Every page request is denied.**
  - `$page_security = 'CreditControl'` is set *after* `session.php` has already done its check, so it has no effect.
  - The manual check `in_array('CreditControl', AllowedPageSecurityTokens)` compares against integer tokens and is always false.
  - Every user gets "Access denied", even if the script were registered.
- **Every form submission is rejected.** B's forms omit `FormID`, so `session.php:379` rejects every POST with "This form was not submitted with a correct ID".
- **Other defects in `CreditReviews.php`.**
  - It includes `header.php` before setting `$Title`, and uses lowercase `$title`.
  - It uses gettext `_()` instead of the project's `__()`.
  - It uses ad-hoc `page_title_bar`/`table` markup instead of webERP's `page_title_text`/`selection` classes.
  - `$NewLimit ? … : 'NULL'` treats a limit of 0 as "no change", so a limit can never be cut to zero.
  - Choosing "Put on Stop" as the decision changes nothing.
- **Helper bugs (moot, since the helpers are never called).**
  - `CheckCreditLimitWithOrder` multiplies by `rate` (wrong direction) and compares against a limit held in the customer's currency.
  - `GetCustomerOverdueBalance` ages by `trandate`, not due date.
  - `ShouldSendReminder` skips the whole customer if *any* invoice is disputed.
- **Uses `balance` correctly.** In B's favour: its balance helper uses the generated `balance` column properly.

## 3. Fit with webERP

- **Security and menus:** neither registers scripts or tokens, or adds menu links. That is the most basic step of adding a page to webERP. A at least follows the standard `require(__DIR__.'/includes/session.php')` → `$Title/$ViewTopic/$BookMark` → `header.php` pattern, uses `FormID`, `prnMsg`, `<fieldset>/<field>` forms and the `selection` table class. B invents its own access check and markup.
- **Upgrades:** webERP upgrades are `sql/updates/NN.php` scripts using `AddColumn`, `CreateTable`, `NewScript`, `NewConfigValue` and `UpdateDBNo`.
  - A has none, and wrongly put migrations into the install tables directory.
  - B has the right file in the right place, which is the right idea, but every helper call is wrong.
- **Configuration:** webERP keeps system settings in `config` (`$_SESSION[...]`, via `NewConfigValue` and `SystemParameters.php`). A invents a key/value `creditconfig` table. B invents `interestfeeconfig` and `reminderlettersconfig`. Per-stage letter text in a table is defensible, but the scalar settings belong in `config`.
- **Existing hold mechanism ignored:** webERP already has hold reasons (`holdreasons.dissallowinvoices`, `CreditStatus.php`). They are enforced in `SelectOrderItems.php`, `CustomerReceipt.php`, `AgedDebtors.php`, `PrintCustStatements.php` and others. The natural design is to drive stop/watch from that mechanism, add an audit log and access control, and extend its enforcement to the missing routes. Both branches add a parallel `creditstatus` that nothing else respects. That is the most important design mistake in both.
- **Ledger and other conventions:**
  - Neither uses `GetNextTransNo`, `systypes`, `debtortrans`/`gltrans` with `ExRate`, `DB_Txn_*`, or `SendEmailFromWebERP`.
  - Neither produces a PDF letter.
  - Neither adds translations (beyond wrapping strings) or manual pages.
  - A at least sets `$ViewTopic`/`$BookMark`.
- **Repo hygiene:** B commits `IMPLEMENTATION_SUMMARY.md`, `INTEGRATION_GUIDE.md` and `NOTES.md` (about 1,250 lines) into the webERP root. A commits `NOTES.md`. Neither belongs in the tree.

## 4. Structure and code quality

- **A**
  - Seven pages with heavily duplicated scaffolding: the same customer-code picker form, the same `$StatusText` array four times, and the same status-history table twice.
  - Customer selection is a raw code text box rather than webERP's customer search or the session's selected customer.
  - Amounts are echoed raw rather than with `locale_number_format`.
  - Notes and reasons are truncated with `substr` and an unconditional `...`.
  - Readable and simple, but it would need consolidating before it could live in the tree.
- **B**
  - Mixed PHP/HTML template style that does not match the project.
  - Inconsistent column naming (`action_type`, `user_id` next to `reviewedby`, `debtorno`).
  - Status values are `ENUM` strings where the rest of webERP uses small ints with lookup tables.
  - A large helper library, none of it reachable.
  - The schema design is somewhat more thoughtful, for example the unique period constraint on charges, an exemptions table and dispute rows per transaction. None of it is wired up.

## 5. Regressions

- **A:**
  - `CounterSales.php` now selects `debtorsmaster.creditstatus`. Because A cannot add that column on install or upgrade, **the counter-sales (POS) page errors on every installation**.
  - A fresh install's table-creation step reports failure because of the two `Z_*.sql` files. Depending on how the installer proceeds, the install may be aborted.
- **B:**
  - The upgrade to DB version 44 always errors and re-runs on every login that triggers the update check. Any later real update `44.php` would collide with it.
  - The fresh install itself still succeeds; the new tables are created, just unused.
  - No existing page is modified, so there is no runtime regression elsewhere.

## 6. What a maintainer would have to fix before merging (most serious first)

### Common to both (effectively a rewrite)

1. **Install and upgrade.** Write a proper `sql/updates/NN.php`: `AddColumn` with the correct argument order, `CreateTable` with inline SQL, `NewScript` for every page, `NewConfigValue` for settings, and a backfill of `nextreviewdate`. Also change `debtorsmaster.sql`, the table files and the `scripts`/`config` seed data for fresh installs.
2. **Security.** Register scripts with a security token that only credit control and the Finance Director hold, and add menu entries.
3. **Stop/watch design.** Build stop/watch on top of `holdreasons` (or make `creditstatus` drive it). Then enforce it in:
   - `SelectOrderItems.php`
   - `ConfirmDispatch_Invoice.php`
   - `RecurringSalesOrdersProcess.php`
   - the EDI order import
   - the shop/API
   - `SpecialOrder.php`
   - and keep the existing `CounterSales.php` hook.
4. **Over-limit hold and release.** Add over-limit holding and a release workflow for orders (BR-10).
5. **Ledger postings.** Write-offs, interest/fees and waivers need `debtortrans` + `gltrans` in transactions, with `GetNextTransNo`, exchange rates, FX difference to the bad-debt account, and allocation against the invoices.
6. **Dunning run.** Preview, exclusions, stage progression only while still overdue, a minimum interval, `SendEmailFromWebERP`, a PDF letter and a no-email list.
7. **Month-end charges run.** Preview, exemptions, a no-double-charge guard and waiver.
8. **Dates.** Replace `ConvertSQLDate` with `FormatDateForSQL` for all user input.
9. **Escaping.** Escape every value with `DB_escape_string`; validate numeric and GL inputs against `chartmaster`.
10. **Report, scoping and aged debt.** Rep and currency filters, home-currency totals, rep scoping (`$_SESSION['SalesmanLogin']`), the BR-31 columns in `AgedDebtors.php`, and portal views for customer logins.
11. **Documentation and clean-up.** Manual pages under `doc/Manual`, and remove the root markdown files.

### A-specific

- Remove or guard the `creditstatus` dependency in `CounterSales.php` until the column exists.
- Delete the `Z_*.sql` files.
- Never delete rejected write-offs; mark them as rejected instead.
- Use `balance` rather than `ovamount`.
- Include or delete `CreditControlFunctions.php`.

### B-specific

- Fix `44.php` (wrong `AddColumn`/`CreateTable` usage).
- Add `FormID` to forms.
- Remove the bogus `$page_security` check.
- Use `__()` and webERP markup.
- Write the other ~10 pages that the tables imply.

## 7. Other observations

- **A** got some details right: requiring a reason for status changes and write-offs, putting the customer on stop after a write-off (BR-28, though with no override as the BRD allows), and a combined per-customer history page that an auditor could use. Its `creditreviews` table has a foreign key to `www_users`, which is good for audit integrity.
- **B's** schema shows better domain thinking than its code: per-period uniqueness, dispute rows, exemptions with effective dates, and `gltrans`/`debtortrans` link columns. But a design sketch is not an implementation. B's docs claim, for example, an "immutable audit trail", which nothing enforces, and GL posting, which does not exist. Those claims are misleading to a reviewer.
- **Neither prevents editing or deleting past reviews at the database level** (BR-03). That is acceptable, since webERP generally relies on the UI not offering it.
- **Neither handles `RecurringSalesOrders` or EDI.** Those are explicitly named in the BRD and in AC-02.

## 8. Verdict

**I'd rather merge A, somewhat.** Neither is mergeable. Both need essentially a rewrite of install/upgrade, security, enforcement and all ledger work.

- **A:** if an administrator added the columns and script rows by hand, its status, history, write-off request/approval, settings and report screens would mostly run. Its pages follow webERP's page and form conventions, and it touches at least one enforcement route.
- **B:** delivers one page that cannot be opened (string token check), cannot be submitted (no `FormID`) and cannot be installed (broken `44.php`, no `debtorsmaster` columns), plus unused helpers and a lot of documentation.
- **A's regression:** A carries a real regression (CounterSales breaks without the column) that B does not. That narrows A's lead but does not erase it.

**Scores: A 2/10, B 1/10.**
