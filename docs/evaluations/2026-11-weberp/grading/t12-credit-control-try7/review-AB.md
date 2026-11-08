# Blind review: credit control, implementation A vs implementation B

Reviewer stance: senior webERP maintainer who would have to merge and maintain one of these. I read both diffs and
the full trees, and compared them with the unchanged webERP tree (`base/`). Where the code made a claim that matters
(installer behaviour, allocation and exchange difference signs, credit available, error codes, navigation), I checked
it against the base code. I did not use NOTES.md as evidence.

## Summary

Both implementations take the same sound basic route: stop and watch are the existing credit status
(`debtorsmaster.holdreason` -> `holdreasons.dissallowinvoices` 1 = stop, 2 = watch), not a new flag. Both add
reviews, an append-only credit log, staged reminders, month-end interest and fees, waivers, write-offs with
approval, a credit control report, a customer/portal view, a go-live CSV load, an upgrade script 44 and a manual
chapter. In scope they are close. They differ in how safely they install and in how carefully the details are
handled.

- **A** adds only new tables and four new debtor transaction types (51 to 54). It ships install seeds that actually
  load under the webERP installer, keeps the ledger postings and exchange differences in the CustomerAllocations
  style, ties reminder escalation to the invoices that are still unpaid, and puts the money settings behind the
  Finance Director token. Its defects are real but local: a duplicated API error code, gaps on some API routes,
  and the over-limit hold that is off after an upgrade.
- **B** changes four core tables (`companies`, `debtorsmaster`, `debtortrans`, `salesorders`) and puts its install
  seed into one multi-statement file. On a new installation this breaks the installer, including the company record
  insert (details below). B also leaves the write-off approval page unreachable from the UI and lets the credit
  controller change the write-off approval limit. Some of its accounting choices are better than A's, notably
  putting the whole carrying value of a write-off, exchange difference included, into bad debt.

## 1. Completeness

| Area | A | B |
|---|---|---|
| Reviews: outcome, notes, next date, limit changed with the review, history kept | Yes (`creditreviews`, `debtorcredit.nextreviewdate`) | Yes (`creditreviews`, `debtorsmaster.nextcreditreview`) |
| New customers get a next review date | Yes, in Customers.php, Z_ImportDebtors and the API InsertCustomer | Yes, in Customers.php only. Z_ImportDebtors and the API keep the 1000-01-01 default and so show as "never reviewed - due now" |
| Stop/watch with reason, who and when | Yes, with a log row | Yes, with a log row |
| Reps and office cannot change status or limit | Fields disabled and the server keeps the old values unless the user holds token 21 or 22 | Limit and status removed from the UPDATE for everyone, fields readonly or disabled |
| Stop on every route | Order entry (re-checked at save), order amend, portal, EDI, recurring, API header, dispatch/invoice (open and post) | Same set, except that amending an order is blocked outright with no release path |
| Over-limit hold | `creditorderholds` table. Applied after save on order entry, on amend, EDI, recurring and API lines. Needs `CheckCreditLimits = 3`, which is the default only on a new install | `salesorders.creditheld`. Applied before save on order entry, EDI and recurring. The API checks only at the header with a value of 0, so lines that push the customer over the limit are never held. Amended orders are not re-checked. Enabled by default whenever `CheckCreditLimits` is not 0 |
| Watch orders visible to credit control | CreditControlOrders.php | Section in CreditControlReport.php |
| Web shop tells the customer the account is on hold | API returns an error code, but the code collides with `NoCompanyRecord` (see 2) | API returns `CustomerOnStop` (1174), but there is no description entry for it |
| Dunning: stages, preview, exclude, email, post list, record per invoice | Yes. `dunninglettersdetail` records each invoice, and the letter text is stored so it can be printed and posted | Yes. Invoices are stored as text only. The "post" letters have no printable copy |
| Escalation rules (BR-15) | The stage comes from letters that covered items still unpaid. A full payment resets the stage. One stage at a time. Minimum gap between letters | The stage is the highest stage whose days are reached, so a first letter can be the final notice. The stage resets only after N days, so a customer who paid and then fell overdue again can be escalated |
| Disputes | Separate table with a reason, who, when and settled | `debtortrans.disputed` flag, no reason recorded |
| Interest/fees: preview, confirm, once a month, exemptions, own currency, chosen GL accounts | Yes. DB unique key on customer/month/type | Yes. Same unique key |
| Waivers reach the ledger | Yes, only on an unpaid charge, at the charge's rate | Yes, also on a part-paid charge (the remaining balance), at the charge's rate |
| Write-offs: approval above the limit, auto-stop, report | Yes. The Finance Director approves on the same page and cannot approve their own request | Yes, but the approval page has no menu item and no link anywhere, so the FD must type the URL |
| Credit control report (filter by rep and currency, home-currency totals) | Yes. Token 2, rep-restricted | Yes. Token 21, so reps cannot open it, although it contains rep-filter code |
| Aged debtors: status, limit, last stage | Three new columns | One extra line under the name |
| Rep restriction | CustomerCreditAccount and the report | CustomerCreditHistory and the report |
| Portal: reminders, charges, balance, own account only | CustomerCreditAccount.php, linked from CustomerInquiry (the portal's Account Status) | CustomerCreditHistory.php, linked from the hard-coded customer menu in index.php. Its charges are also shown as rows in CustomerAccount |
| Month-end agreement and "why not" (BR-37/38) | Z_CheckDebtorsControl includes the new types and lists mismatches per transaction. CustomerBalancesMovement and DebtorsAtPeriodEnd are adjusted | Z_CheckDebtorsControl gets a journal column and two diagnostic lists. CustomerBalancesMovement is not adjusted, so interest (type 15, positive) is counted under "credits" |
| Go-live load (BR-40) | Dedicated page with check-only mode, all-or-nothing transaction and per-line errors | Inside the settings page, no transaction, lines skipped with warnings |
| Manual and staff note | Full chapter with a sales staff note | Full chapter with a sales staff note |
| Collection agency or legal note | `collectionnote` field | Links to the existing AddCustomerNotes.php (better reuse) |
| Auto-stop after the final notice (open question 4) | Lists these customers for a decision | Same list, plus an optional setting to stop them automatically |

On features, the two are near parity. A is more precise on escalation, disputes, the go-live load and the
reconciliation reports. B has a couple of extra options. B's unreachable approval page and its API hold gap
are real holes.

## 2. Correctness

### Installation (BR-39): decisive

- **B breaks a new installation.**
  - `InstallFunctions.php` inserts the company with a positional `INSERT INTO companies VALUES (1, ...)` of 28 values,
    and `install/sql/demo.sql` does the same. B adds three columns to `install/sql/tables/companies.sql`
    (`latechargeinterestact`, `latechargefeeact`, `baddebtact`). Both inserts then fail with a column count
    mismatch, so the new system has no company record. That breaks the whole application, not only credit control.
  - The installer runs each `install/sql/data/*.sql` file with a single `DB_query`, which is a plain `mysqli_query`.
    It cannot run more than one statement, and every base data file is a single INSERT. B's
    `install/sql/data/creditcontrol.sql` holds 48 separate statements, so it fails as a whole. A new install then has
    no tokens 21/22, no scripts rows, no config values, no hold reasons and no dunning stages, and the installer
    reports "Database tables could not be populated".
- **A installs correctly.** It changes no existing table. Each seed is a separate single-statement file. The alphabetical
  order puts `config.sql` before `creditcontrol_checklimits.sql`, so the UPDATE finds its row. The new
  `install/sql/tables/*.sql` match the upgrade's CreateTable definitions, which I checked for `writeoffs`.
- Neither touches `install/sql/demo.sql`. A demo install stamps DBUpdateNumber 44 and so never runs 44.php, which
  leaves credit control unconfigured on a demo in both. For B this comes on top of the broken company insert.
- Upgrade (44.php): both are idempotent through the standard helpers. A finds or creates the Normal, Watch and Stop
  codes and stores them in config. B inserts fixed codes 100 to 102, which CreditStatus.php cannot create by hand
  (its maxlength is 2) but can still edit. B's `AddColumn` on `debtortrans` is a heavy ALTER on the largest
  customer table.

### Ledger and money

- **A** posts every movement through one function. Interest and fee debit debtors control and credit income.
  Waivers and write-offs credit debtors control and debit income or bad debt, in home currency at the rate used.
  Credits are auto-allocated by `CreditControlAllocateCredit`. I checked it line by line against
  CustomerAllocations.php: the diff on exchange has the same sign, the same `diffonexch` on both sides, and the same
  `salesexchangediffact`/`debtorsact` pair. So debtors control stays equal to the customer balances.
  Waivers post at the charge's own rate, so they reverse exactly. A write-off posts at today's rate, which sends the
  currency difference to the exchange difference account, not to bad debt. That is defensible, but BR-27 asks for
  bad debt "including any currency difference".
- **B** posts through `CreditControlPostDebtorJournal` and calls `EnsureGLEntriesBalance`. For a write-off it works
  out the carrying value of the invoices it clears, each at its own rate, and posts the journal at that effective
  rate. The whole carrying value goes to bad debt with no exchange residue. This matches BR-27 better than A.
  It allocates only to type 10/15 debits and ignores unallocated credits when it checks "owed", so a write-off
  can leave a customer in credit.
- Charges: A dates them at the chosen month end and offers the last 12 months. B dates them at month end or today
  and offers the current and two previous months. Neither checks `ProhibitPostingsBefore`. A's 12-month look-back
  makes it easier to post into a closed period.
- Interest on interest: A never charges it. B makes it a setting (open question 3).
- Transaction types: A adds 51 to 54, with translations in DatabaseTranslations.php. A's statements read "Late
  Payment Interest" and so on. CustomerAccount.php has explicit branches only for types 10, 11 and 12, so A's
  charges, waivers and write-offs do not appear as rows there. They do appear in CustomerInquiry (the portal's
  Account Status), on statements, and in A's own credit page. B reuses type 15 "Journal - Debtors", which base never
  creates, so it is safe. B appends the reference on statements and adds a type-15 branch to CustomerAccount.

### Sequences and transactions

- Both use `GetNextTransNo` and do their postings inside a transaction. A's write-off request and posting share one
  transaction. B commits the posting first and sets the stop status afterwards, outside it. That is acceptable.
- A's hold row is written after the order commits (`CreditControlHoldOrderIfOverLimit`). That is correct because
  `GetCreditAvailable` already counts the new order, but a failure between the two would leave an unheld order.
  B decides the hold before the INSERT and writes it in the same statement, which is cleaner.

### Hold enforcement

- Both block ConfirmDispatch_Invoice when the page opens and again on post. Neither blocks the API
  `InvoiceSalesOrder` or `ModifySalesOrderHeader`. CounterSales and SpecialOrder were already blocked in base.
- A: `CheckCreditLimits = 3` is a new value that SelectOrderItems does not know about, so staff see no over-limit
  warning while they enter the order, only a message after saving. It is the default only on a new install, so an
  upgraded live system holds nothing until someone changes the setting (documented, but BR-10 says "must").
- B: the over-limit hold works out of the box on upgrade, because base defaults `CheckCreditLimits` to 1. The API
  gap noted above remains.

### Email

- A decodes HTML entities in the stored wording and the customer name before mailing. This is needed because
  session.php stores form input HTML-encoded. A also records a letter as sent only after the mailer succeeds.
- B mails the stored wording and names as they are, so any wording edited on the settings page, or a name with an
  apostrophe, reaches the customer as `&#039;`. B uses `custcontacts.statement = 1` the same way A does.

### Escaping and display

- A uses `htmlspecialchars(..., false)` (no double encoding) for text that came from forms.
- B calls plain `htmlspecialchars` on text that is already encoded, so names and notes show as `&amp;#039;` all over
  its pages.
- Neither has an injection problem beyond webERP's normal reliance on session.php escaping. B's `CreditControlLog`
  leaves escaping to the caller and puts `__()` strings straight into SQL, which breaks on a translation that
  contains an apostrophe.

### API error code (A)

- A defines `CustomerOnCreditStop` as 1158, which is already `NoCompanyRecord`. A web shop client receives "Unable to
  read company record" for a stopped customer. That is wrong, and it works against BR-11.

## 3. Fit with webERP

- Upgrades: both use the standard helpers (CreateTable, AddColumn, NewScript, NewSecurityToken, NewMenuItem,
  NewSysType, NewConfigValue, UpdateDBNo). A's install seeds follow the installer's one-statement-per-file rule.
  B's do not.
- Security: A hard-codes token numbers (`in_array(21, ...)`). B resolves them through `PageSecurityArray` the way
  SelectOrderItems does, which is the more idiomatic choice.
  - A puts the settings (rates, accounts, approval limit, stages) on token 22, the Finance Director.
  - B puts them on token 21, so the credit controller can raise their own write-off approval limit, which defeats
    BR-26.
  - Who holds the tokens by default: A gives tokens 21 and 22 to the System Administrator role only. B gives token 21
    to the Accountant and System Administrator roles, and token 22 to the System Administrator.
- GL accounts: B stores them on `companies`, next to the other control accounts, and updates Z_ChangeGLAccountCode,
  which is the webERP way. A stores them in `config`, so Z_ChangeGLAccountCode will not rename them.
- Config: B reads its settings from `$_SESSION` after GetConfig, the webERP norm. A reads `config` directly with a
  static cache. The reason is defensible (cron and API), but it is a second mechanism.
- Menus: A adds nine menu items across Transactions, Reports and Maintenance. B adds a hub page and a report item, but
  has no route to the approvals page. B also adds the portal link to the hard-coded customer menu in index.php,
  which is the only way to reach the portal there. A instead links from CustomerInquiry.
- Forms and dates: A uses `<input type="date">`, which about 100 base scripts already use. B uses
  `class="date"` with DefaultDateFormat, which is also current webERP practice. Both are fine.
- CreditStatus.php: A turns the checkbox into a clean three-way select and protects the configured codes from
  deletion. B keeps the old block behind `if (false)` and runs a second UPDATE after the original insert/update.
- Translations: both wrap strings in `__()`. A also adds the new type names to DatabaseTranslations.php.
- Manual: both add a full chapter in ManualAccountsReceivable.html with anchors. A also adds a NEWS entry.

## 4. Structure and code quality

- A: one function library (`CreditControlPostDebtorTrans`, `CreditControlAllocateCredit`, `CreditControlPostWriteOff`,
  `CreditControlWaiveCharge`) used by every page, and one page per job. Pages are 120 to 450 lines and easy to
  follow. Some indentation is broken where code was spliced in (DeliveryDetails, Customers.php delete, Z_ImportDebtors,
  api_customers InsertCustomer). The customer page calls `CreditControlNewCustomer` (an INSERT ... WHERE NOT EXISTS) on
  every view.
- B: also a helper library, but the customer page is a 500-line hub doing six jobs. The waiver logic sits in the
  page rather than the library, unlike the write-off. Customers.php has whitespace damage (runs of tabs where lines
  were cut). CreditStatus.php has dead `if (false)` code. The go-live loader is hidden inside the settings page.
  Naming is mixed (`GetCreditStatus`, `CreditStatusText`, `CreditControlParam`, `CreditOverdueSummary`).
- Data model: A's separate `debtorcredit` and `creditorderholds` tables avoid touching core tables. That needs a hook
  on each customer creation path, which A added. B's columns on core tables are simpler to query but caused the
  install break above.

## 5. Regressions

- B: a new install fails (company record and seed data). This is the main regression.
- B: AR clerks can no longer edit the credit limit or credit status in Customers.php. That is intended by BR-07, and
  A does the same for users without the credit control tokens.
- B: CustomerBalancesMovement now reports interest charges as credits.
- B: CustomerInquiry and CustomerAccount relabel ACCOUNT ON HOLD as ACCOUNT ON STOP and hide the credit status line
  from customers. That is acceptable.
- A: API error code 1158 is now ambiguous for every client.
- A: `CheckCreditLimits = 3` silences the order-entry warning that values 1 and 2 give.
- A: CustomerAccount.php hides the 51 to 54 rows. The totals are unaffected because they come from balances.
- Both: watch customers can now place their own portal orders, where base blocked them. That is intended by BR-08.

## 6. What a maintainer must fix before merging

**B (most serious first)**

1. Install: stop adding columns to `companies`, or update the positional company INSERTs in `InstallFunctions.php` and
   `install/sql/demo.sql`. Split `install/sql/data/creditcontrol.sql` into single-statement files (multi-row
   INSERTs, one per table).
2. Add a menu item or link for CreditControlApprovals.php.
3. Move the settings page, or at least the approval limit and the GL accounts, behind the approval token (22).
4. API: hold the order when lines are added (InsertSalesOrderLine), add an `$ErrorDescription['1174']`, and block
   `InvoiceSalesOrder` for a stopped customer or a held order.
5. Decode HTML entities in the reminder subject, body and customer name before mailing. Stop double-encoding stored
   text on the pages.
6. Reminder escalation: do not jump straight to the final stage, and base the reset on whether the chased invoices are
   still unpaid rather than on a fixed number of days.
7. Fix CustomerBalancesMovement for type 15 debits. Give Z_ImportDebtors and the API customer insert a next review date.
8. Clean up the whitespace damage in Customers.php and the `if (false)` block in CreditStatus.php. Escape `__()` text
   in log entries.

**A (most serious first)**

1. API: give `CustomerOnCreditStop` a free code (for example 1174) with a description. Block `InvoiceSalesOrder` (and
   ideally `ModifySalesOrderHeader`) for a stopped customer or a held order.
2. Over-limit hold: turn it on in the upgrade, or ask about it explicitly, and teach SelectOrderItems to warn at entry
   when `CheckCreditLimits = 3`.
3. Show types 51 to 54 in CustomerAccount.php.
4. Write-off currency difference: post it to the bad debt account, as BR-27 asks, or get Finance to agree to the
   exchange difference account.
5. Charges: refuse posting into a period before `ProhibitPostingsBefore`. Narrow the 12-month look-back.
6. Use `PageSecurityArray` rather than the hard-coded 21/22. Consider moving the GL accounts to `companies` so that
   Z_ChangeGLAccountCode renames them.
7. Fix the spliced indentation. Stop the customer page writing to the database on every view.
8. Add the credit control seed to the demo install. This also applies to B.

## 7. Other observations

- Good in A: check-only, all-or-nothing go-live load. Printable stored letters for customers without email.
  Disputes with a reason and who settled them. `CreditControlOrders.php` brings held, stopped and watched orders
  together with release notes. Settings changes are logged. Reconciliation diagnostics compare each transaction
  with its own debtors-control posting, which is the right way to answer BR-38.
- Good in B: whole carrying value to bad debt. Optional stop after the final notice and optional interest on charges
  (both answer open questions in the BRD). Waiver of a part-paid charge. Reuse of AddCustomerNotes for legal notes.
  Settings on the companies table. Over-limit hold on by default. The hold is decided before the INSERT and written
  in the same statement.
- Both treat the review history as append-only only by not offering edit or delete. There is no database-level
  protection, which is normal for webERP.

## 8. Verdict

**I would rather merge A, clearly.** A installs, upgrades and posts to the ledger correctly, and each page has a
single job. What is wrong with A is local (an error code, API invoicing, the hold default) and can be fixed in
an afternoon. B is comparable in feature coverage and has two better accounting choices, but as delivered it breaks
a new webERP installation outright and leaves its approval page unreachable. It also weakens the segregation of
duties around write-offs, mails entity-encoded text to customers, and is rougher in code quality. B would need a
structural rework of its install and schema changes before it could be considered.

- **A: 7/10**
- **B: 4/10**
