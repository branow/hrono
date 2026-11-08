# Credit control: maintainer review of implementations A and B

Reviewer stance: a webERP maintainer who would have to merge and maintain one of these. I read both diffs and the new pages and include files in full. I checked the claims that matter against the webERP base tree (installer, upgrade helpers, session handling, the GL tables). I did not read NOTES.md.

## Summary

Both implementations take the same sound basic decision. Stop and watch are not a new field: they are the existing `debtorsmaster.holdreason` with `holdreasons.dissallowinvoices` (0 normal, 1 stop, 2 watch). Every existing hold check in webERP therefore keeps working. Both add the same kinds of tables: reviews, an audit log, dunning stages and log, charges and write-offs. Both add `debtortrans.disputed`, a per-order credit-hold flag, three new systypes, two security tokens and an upgrade script `44.php`. Both post their own debtors-ledger and GL entries.

Each one has one defect that would block a merge, and each of those is a one-line fix:

- **A breaks every fresh (non-demo) install.** `install/sql/data/menuitems.sql` now holds two `INSERT` statements. The installer runs each data file with a single `mysqli_query()` (`InstallFunctions.php`, the `glob(.../data/*.sql)` loop), which cannot run more than one statement. The whole file fails, so a new company gets **no menu items at all**.
- **B leaks other customers' data in the customer portal.** `CustomerCreditHistory.php` (security 1, so open to customer logins) and `CreditControlCanSeeCustomer()` test `$_SESSION['CustomerLogin']`. That session key does not exist anywhere in webERP; the real flag is the global `$CustomerLogin` set in `includes/session.php`. A logged-in customer can open `CustomerCreditHistory.php?DebtorNo=ANYONE` and see that customer's balance, reminder letters and charges. This breaks BR-36 and AC-10.

Beyond those two, B covers more of what the business asked for. It blocks API invoicing, holds orders per line, lets credit control release pre-stop orders, has a go-live spreadsheet loader and a reconciliation page that actually works. A is more careful in several places: foreign-currency postings, waiver guards, configurable status mapping, portal isolation and watch customers in the web shop. A's month-end reconciliation is built on a page that no longer runs.

---

## 1. Completeness

| Area | A | B |
|---|---|---|
| Credit reviews (BR-01..04) | Yes: `CreditCustomer.php`, outcomes, limit and status changed in the same transaction, next review date. | Yes: `CreditReview.php`, same shape. |
| Next review date on new customers (BR-02) | Customers.php, Z_ImportDebtors, API InsertCustomer, upgrade backfill. | Same set, plus a bulk "set review dates" action in setup. |
| Stop/watch with reason and audit (BR-05) | `CreditSetStatus` + `creditevents`. | `CreditControlSetStatus` + `creditcontrollog`. |
| Only credit control changes stop or limit (BR-07, AC-03) | Token 21 (staff) and 22 (Finance Director). Customers.php fields disabled for others, but see the Customers.php bug below. | Token 17 (staff) and 21 (FD). Customers.php keeps the stored values for non-credit-control users and logs changes. |
| Stop enforced: sales office and web shop orders | DeliveryDetails (new and modified orders; a released order is allowed). | DeliveryDetails (new and modified orders). |
| Stop enforced: EDI | Yes; logs a "blocked" event. | Yes; also fixes the old `if ($CreateOrder = true)` bug (A fixes it too). |
| Stop enforced: standing orders | Yes; the template is not advanced, so the order is raised later. | Yes, the same. |
| Stop enforced: API order header | Yes (new error code 1174). | Yes (new error code 1174, quotations exempt). |
| No dispatch or invoice on pre-stop orders (BR-06) | ConfirmDispatch_Invoice checked on entry and again before posting. | The same, **plus API `InvoiceSalesOrder`**. A leaves API invoicing open. |
| Credit control can release a pre-stop order (BR-06) | The logic honours `creditholdstate=2`, but **no screen sets it for a stopped customer's order**. The release button only lists orders held for being over the limit. | Yes: the report lists stopped customers' open orders with a Release button. |
| Watch: warn and list orders (BR-08, AC-04) | Warning already exists in order entry. The worklist shows open orders for watched customers. Watch customers can now order in the web shop (`!= 1` instead of `== 0`). | The report lists watched customers' orders (last 60 days). Watch customers are **still refused by the web shop**, as in base, which contradicts "watch can still be supplied". |
| Status visible where staff look (BR-09) | CustomerInquiry header gets a link to the credit page. | SelectCustomer shows a status banner and two menu links. |
| Over-limit orders held (BR-10, AC-05) | Adds a new `CheckCreditLimits = 3` "Hold for credit control approval" mode. **Off by default**: config stays at 1, so out of the box nothing is held. API hold is decided at header time only (customer already over the limit); the order value is ignored. | Holds whenever `CheckCreditLimits > 0`, which includes the default 1. Checked after the lines are written in EDI, recurring and API (`GetCreditAvailable() < 0` includes this order), so it is accurate. This changes what "warn" meant for existing sites; see Regressions. |
| Web shop shows "on hold" (BR-11) | Already in base; A also shows it on the portal page. | Already in base; the API message says to contact us. |
| Dunning stages configurable (BR-12) | Settings page: add, edit and delete stages; placeholders. | Setup page: edit stages; placeholders. |
| Email to the accounts contact, list customers to post to (BR-13) | Every `custcontacts.statement=1` address; letters with no email are printed for posting. | The first statement contact, else the branch email; letters with no email are printed for posting. |
| Preview and exclude before sending (BR-14) | Yes (`Send[debtor]` array). | Yes (`Send_<debtor>` names; PHP rewrites `.` and spaces in POST names, so debtor codes containing those break). |
| Pay means no next letter, no repeat stage (BR-15) | Re-checked at send time; uses the current overdue episode plus a minimum gap. **Jumps straight to the highest stage that applies**, so a first contact at 65 days gets the final notice. | Moves up **one stage at a time** within the overdue episode, with a gap. Closer to "escalating". |
| Dunning record (BR-16), currency (BR-17) | `dunninglog`: amount, currency and invoices. Letters in the customer's currency. | The same. Letter totals hard-coded to 2 decimals. |
| Disputed invoices (BR-18) | Per invoice, with reason, logged. | Per invoice, with reason, logged. |
| Interest and fees (BR-19) | Rate (days/365 of the month), flat fee, days; options for **fee per overdue invoice** and **interest on charges** (open questions 2 and 3). | Rate/12, flat fee, days. Interest only on invoices, never on charges. |
| Exemptions (BR-20) | One flag for both interest and fees. | **Separate** no-interest and no-fees flags, as the BRD says ("and/or"). |
| Preview, confirm, no double charge (BR-22) | Yes; unique key on (debtor, month, type). | Yes; same unique key plus an explicit check. |
| Waive with reason, reaches the GL (BR-24) | Yes; waives only the **unpaid** balance at the charge's rate and allocates it. | Yes, but always waives the **full** amount and allocates it, even if the charge is partly paid (over-allocation). |
| Write-off, approval over a limit, auto-stop (BR-25, 26, 28) | Yes. | Yes; also refuses a request that would exceed balance minus pending requests. |
| Write-off report (BR-29) | On the write-offs page, by date range. | On the write-offs page. |
| Credit control report (BR-30) | `CreditControl.php`: reviews due, over limit, watch/stop, held orders, "final notice sent, not stopped"; rep and currency filters; home-currency totals. | `CreditControlReport.php`: reviews due, over limit, watch/stop, held, stopped and watched orders; rep and currency filters; home-currency totals. |
| Aged debtors status, limit, last stage (BR-31) | Yes (column colspans not adjusted in detail rows). | Yes, with colspans fixed. |
| Per-customer audit history (BR-32) | Yes (`creditevents`, shown on the credit page). | Yes (`creditcontrollog`, shown on the review page). |
| Reps see only their customers (BR-33, AC-10) | Yes (`custbranch.salesman`). | Yes. |
| Portal (BR-35, 36) | `CustomerCreditPortal.php`, customer taken from `www_users.customerid`, cannot be overridden. A also hardens CustomerInquiry for portal users. **No link in the customer-login menu** (`index.php` hard-codes that menu). | `CustomerCreditHistory.php`; **cross-customer leak** (see the summary). No link in the customer-login menu either. |
| Month-end agreement and "why" (BR-37, 38, AC-08) | Adds a column to `Z_CheckDebtorsControl.php`, but that page still reads `chartdetails`, **which update 20 dropped**. The page fails with a SQL error, so BR-37/38 are not delivered. | **Rewrites `Z_CheckDebtorsControl.php` on `gltotals`**, split by transaction type, and adds two drill-down tables: transactions where the ledger and GL disagree, and GL postings with no customer entry. This is the only working answer to BR-38. |
| Live system and go-live (BR-39, 40, AC-11) | The upgrade maps existing hold reasons by flag, backfills review dates and writes a "status at go-live" history row. **No spreadsheet loader**; stops have to be entered one at a time. | The upgrade creates stop/watch reasons and backfills review dates. **CSV loader** in setup (debtor, status, limit, next review). |
| Staff guide (BR-42, 43) | A section inside ManualAccountsReceivable.html, including a sales note. | A new ManualCreditControl.html, registered in ManualOutline.php, plus ManualSecuritySchema rows, including a sales note. |

On completeness, B covers more of the BRD's enforcement and month-end needs. A covers more of the open-question options and keeps the portal and the web shop right.

## 2. Correctness

### Ledger and currencies

- **A** posts through one helper, `CreditPostTransaction`. The debtors-control line is derived as minus the sum of the other lines, so every journal balances by construction. The debtortrans rate is `CustAmount / HomeAmount`.
  - Charges are posted at today's rate.
  - Waivers reverse at the charge's own rate.
  - Write-offs are valued at the **original rates of the invoices they settle**.

  The result is that `ovamount/rate` on the customer ledger equals the GL debtors movement exactly. No exchange difference ever arises. For BR-27 ("including any currency difference") A's answer is "there is none, because we relieve debtors at the value it was booked at". That is defensible accounting and reconciles cleanly.
- **B**'s write-off credits debtors control at the original rates, debits bad debt at today's rate, and posts the difference to `salesexchangediffact`. The GL balances and reads literally as BR-27. But the write-off debtortrans row is stored at **today's** rate and **`diffonexch` is not set** on either side of the allocation, as `CustomerAllocations.php` does. As a result, B's own reconciliation page will show every foreign-currency write-off as a ledger-versus-GL difference. B's caption admits this ("usually exchange difference..."). For a multi-currency business this undermines AC-08's "agree".
- B hard-codes `round(..., 2)` for home amounts instead of using the company's decimal places. A uses `CompanyRecord['decimalplaces']`.
- B calls `EnsureGLEntriesBalance()` after charges, waivers and write-offs. That is the webERP way and good practice. A doesn't need it, because its journals balance by construction.
- Waiver: B over-allocates a partly paid charge (`alloc` goes above the amount, the balance goes negative). A refuses a waiver when nothing is unpaid and waives only what is open.

### Sequences and transactions

- Both call `GetNextTransNo()` inside the transaction.
- B takes `FOR UPDATE` on the debtor's open items in the write-off.
- A's Finance Director approval sets `status='approved'` **outside** the posting transaction. If posting then fails (no GL account, balance changed), the request is left in an `approved` state that neither the pending list nor the report can act on: it is orphaned. B keeps it pending on failure.
- A's charge posting checks for duplicates in PHP and then relies on the unique key. A duplicate-key error after the debtortrans and GL inserts is not rolled back (`DB_query` without the transaction flag). The window is small, but it is not atomic.

### Status mapping

- **A** stores which hold-reason code means normal, watch and stop in config, validates it against the flag, falls back to the lowest code of that kind, and lets Finance change it in settings. That is robust on any live database.
- **B** creates stop and watch reasons (code 90 or above) and **hard-codes "normal" as reason code 0**.
  - `CreditControlSetStatus('normal')` silently returns false if code 0 does not exist. The review is recorded, but the stop is **not** lifted, and the user is not told.
  - `Customers.php` forces `HoldReason = 0` for new customers entered by non-credit-control users. `debtorsmaster.holdreason` has a foreign key to `holdreasons`, so on any database without code 0 (a fresh install, or an older install that used the classic "1 Good History") **the sales office can no longer create customers**.

### Hold enforcement on every route

| Route | A | B |
|---|---|---|
| Sales office and web shop orders | ✔ | ✔ |
| Counter sales and special orders | already blocked in base | already blocked in base |
| EDI | ✔ | ✔ |
| Recurring orders | ✔ (and auto-invoice suppressed when held) | ✔ (and auto-invoice suppressed when held) |
| API order | ✔ | ✔ |
| Dispatch and invoice in UI | ✔ | ✔ |
| API invoice | **✘** | ✔ |
| Release of pre-stop order | logic only, no UI | ✔ |

### Email

Both call `SendEmailFromWebERP` and record a letter only when it sent successfully; a failed send is retried on the next run. Both build plain-text bodies.

### Install and upgrade

- **A, fresh install:** broken menus (see the summary). It does seed sensible hold reasons (1 normal, 20 watch, 30 stop, matching classic webERP data) and the config, tokens, scripts and systypes.
- **A, demo install:** a separate `creditcontrol_demo.sql` run through `PopulateSQLDataBySQLFile` (which does split statements). It inserts config, tokens, scripts and menus. The demo hold reasons have no watch or stop flag, so A tells the user to define them, which is graceful.
- **A, upgrade:** the new tables carry foreign keys to `debtorsmaster.debtorno`, and `CreateTable` forces utf8mb4. On an older install still in utf8mb3, MySQL 8 refuses a foreign key between columns of different charsets, so five tables would fail to create. This is a real risk for "our existing live system". Otherwise the upgrade is well behaved: it reuses existing reasons, is idempotent, and records the go-live status.
- **B, fresh install:** separate `creditcontrol_*.sql` data files, each a single statement, so they load. There is no "normal" reason; see the reason-0 problem above.
- **B, demo install:** **nothing.** The demo path loads only `demo.sql`, and `DBUpdateNumber` is set to the latest number, so `44.php` never runs either. On a demo company every new page is refused (no `scripts` rows), no tokens or config exist, and no stages are seeded.
- **B, upgrade:** no foreign keys, so no charset risk, but also no referential integrity. Its `CreateTable` SQL already ends in `ENGINE=... CHARSET=...` and the helper appends the same again. MySQL tolerates repeated table options, so this is redundant rather than fatal (not run here).

### Other correctness items

- **A, Customers.php:** `$CreditHoldSQL = "" . $CreditHoldSQL . "";` (the same for the limit). The variables stay empty for everyone, so the UPDATE never writes `holdreason` or `creditlimit`. A credit controller who changes a limit or status in Customer Maintenance gets "Customer updated" and nothing changes. `CreditLogMaintenanceChange()` is dead code as a result.
- **A, CreditStatus.php not touched:** a watch reason shows as "NO INVOICING", and saving it in that screen silently turns watch (2) into normal or stop (0 or 1).
- **B, CreditStatus.php:** protects its stop and watch reasons from edit and delete, and labels watch correctly. However, the page now calls `CreditControlReasonCode()` on every load, which can INSERT hold reasons and rewrite config: a write on a GET.
- **Both double-escape.** `session.php` already runs `DB_escape_string(htmlspecialchars())` over all `$_POST` and `$_GET` values. B escapes them again everywhere, and A does in `LogCreditEvent`. Quotes in notes and reasons are stored with backslashes. B also `htmlspecialchars` already-encoded values on output (`&amp;amp;`).
- **Both** put help links on `$ViewTopic` values that do not match where the manual text was written. A's anchors are in AccountsReceivable but the pages say ARTransactions, ARInquiries or Setup. B registers a CreditControl topic but its pages say AccountsReceivable. So the help icon lands on the wrong page in both.

## 3. Fit with webERP

- **Pages:** both follow the webERP page skeleton (session.php, header and footer, `prnMsg`, `FormID`, `selection` tables, `__()`), plus the upgrade helpers (`AddColumn`, `CreateTable`, `NewScript`, `NewMenuItem`, `NewConfigValue`, `NewSysType`, `InsertRecord`).
- **Install seeds:**
  - A edits the existing per-table seed files, which is the convention, but did it wrong for menuitems.
  - B invents a parallel set of `creditcontrol_*.sql` files. This works for fresh installs but scatters seed data away from where release maintainers look, and it forgets the demo path entirely.
- **Security:** A takes the next free token numbers (21, 22) and gives them to Accountant and Sysadmin. B fills the gap at 17 plus 21, and also gives AR Clerk the credit-control token. Both use `SalesmanLogin` for rep scoping, as webERP does.
- **Customer-login detection:** neither uses webERP's own `$CustomerLogin`. A reads `www_users.customerid`, which works but would also lock a staff user who has a default customer. B reads a session key that does not exist, which is the leak above.
- **GL:** B's use of `EnsureGLEntriesBalance` is idiomatic. A's balanced-by-construction helper is fine too. A follows webERP's exchange-difference model more closely by avoiding a difference; B half-implements it (no `diffonexch`).
- **Translations:** A adds the new systypes to `DatabaseTranslations.php`, which is the webERP convention for translatable type names. B does not.
- **Dates:** both use `<input type="date">` with Y-m-d in places, rather than webERP's `class="date"` with `DefaultDateFormat`. This is minor, but it is not house style.
- **Manual:** B's new chapter plus outline plus security schema is the more complete integration. A's in-chapter section is acceptable.
- **Settings:** A puts the hold mode into SystemParameters (`CheckCreditLimits=3`) and everything else in its own settings page. B keeps all its settings in its setup page.

## 4. Structure and code quality

- Both have one shared include and around seven pages; the sizes are similar (about 3.5k and 3.1k diff lines).
- A's include is cohesive: one posting helper, one allocation helper, overdue-position logic and status mapping. A few page-local functions (`CreditCalculateCharges`, `CreditWriteOffPlan`, `CreditPostWriteOff`) live in the pages. The comments explain the "why" well.
- B centralises more of the posting logic in the include (`PostCharge`, `WaiveCharge`, `PostWriteOff`), which makes the pages thinner. Some leftover logic is muddled; for example, in `DunningCandidates` `$Next` is computed twice and the first value is thrown away.
- Naming: A uses `Credit*` and `creditevents`. B uses `CreditControl*`, `CanDoCreditControl` and `creditcontrollog`. Both are readable.
- The Customers.php edit in A is a visible bug that suggests it was not exercised. B's `$_SESSION['CustomerLogin']` suggests the portal was never tested with a customer login.
- B's rewrite of `Z_CheckDebtorsControl.php` is a whole-page replacement. It is justified because the old page was dead, but it is a bigger review surface.

## 5. Regressions

**A**

1. Fresh non-demo install: the menuitems data file fails, so there are no menus for anyone.
2. Customer Maintenance no longer saves credit limit or status for anyone, including credit control, and does not say so.
3. Upgrade on utf8mb3 databases: the new tables fail to create because of the foreign-key charset mismatch.
4. Customers with credit-control history can no longer be deleted (intended for audit, but new behaviour).

**B**

1. On databases without hold reason 0, non-credit-control users cannot create customers (FK error), and "back to normal" silently does nothing.
2. `CheckCreditLimits = 1` ("warn") now **holds** over-limit orders on every route. That is what the BRD wants, but it silently changes the meaning of an existing setting for every site that upgrades.
3. Demo installs: all credit control pages are refused.
4. Portal: cross-customer disclosure.
5. CreditStatus.php writes to holdreasons and config on page load.

## 6. What a maintainer must fix before merging

**A**, most serious first:

1. Merge the credit-control menu rows into the single existing `INSERT` in `install/sql/data/menuitems.sql`, or move them to their own data file.
2. Fix `Customers.php` so credit control's edits to `holdreason` and `creditlimit` are written. Remove the no-op string concatenation and build the real `holdreason='..', creditlimit='..',` fragments.
3. Rewrite `Z_CheckDebtorsControl.php` on `gltotals`. It is dead today, so BR-37 and BR-38 do not work. A "why" drill-down like B's should be added.
4. Add a release action for orders of stopped customers, which BR-06 needs; set `creditholdstate=2` from the watch/stop list.
5. Block `InvoiceSalesOrder` in the API for held orders and stopped customers.
6. In the upgrade, create tables with the debtorsmaster charset (`CharacterSet('debtorsmaster')`), or drop the foreign keys.
7. Approve-then-post must be one transaction, or the request must revert to pending on failure.
8. Decide the default for `CheckCreditLimits` (the BRD wants holding) and document it in the upgrade notes.
9. Add a go-live CSV loader for the spreadsheet stop list (BR-40).
10. Update CreditStatus.php to offer and label watch (2), so editing a reason there cannot drop watch.
11. Add a link to the portal page in the customer-login menu in `index.php`.

**B**, most serious first:

1. Use webERP's global `$CustomerLogin` (or `www_users.customerid`) in `CustomerCreditHistory.php` and `CreditControlCanSeeCustomer()`.
2. Stop hard-coding reason 0 as "normal". Store a configurable normal reason (as A does), seed one on fresh install, report a failure when lifting a stop, and give new customers a valid default.
3. Seed the demo install: config, tokens, scripts, menus and stages.
4. Write-offs: set `diffonexch` on the allocated items and the write-off, as CustomerAllocations does, so that the ledger and the GL agree in home currency.
5. Waiver: waive only the unpaid balance, or refuse partly paid charges.
6. Make the hold behaviour an explicit setting, or at least flag the change of meaning of `CheckCreditLimits=1` in the upgrade.
7. Allow watch customers to order in the web shop (`!= 1`).
8. Move the lazy reason creation out of CreditStatus.php page load.
9. Remove the double escaping and double encoding.
10. Use `Send[...]` arrays rather than `Send_<debtorno>` field names.
11. Use the company's decimal places instead of 2.
12. Add a link to the portal page in the customer-login menu in `index.php`.

## 7. Other observations

- Good in A: the overdue position nets unallocated cash, so a customer who paid but whose cash is not yet allocated is not chased or charged. B does the same with `min(overdue, balance)`. A's settings validate hold-reason kinds and GL accounts. A's worklist adds "final notice sent, still overdue, not on stop" for open question 4.
- Good in B: an optional automatic stop on final notice (open question 4); a protected CreditStatus; output consistently `htmlspecialchars`-ed; the reconciliation drill-down is genuinely useful to an accountant.
- Both log charges, waivers and write-offs into the per-customer history, so BR-32 is covered by both.
- Neither offers a printable PDF letter for the post-by-hand case; both just show the text on screen. That is acceptable for v1, but webERP users would expect a PDF like statements.

## 8. Verdict

**B, barely.**

Both have a merge-blocking one-liner: A's install breaks menus, B's portal leaks across customers. Once those are fixed:

- **B** delivers more of what the business actually asked for: every route enforced including API invoicing, release of pre-stop orders, a working month-end reconciliation with a "why", a go-live loader, and separate interest and fee exemptions.
- **A** is the more careful ledger implementation (exact foreign-currency reconciliation, a safe waiver) and handles status mapping and portal isolation better. However, its month-end tool doesn't run, it is missing release and API-invoice enforcement, and it quietly breaks Customer Maintenance.
- **B**'s remaining problems (hard-coded reason 0, no demo seeds, `diffonexch`) are design fixes of about the same size as A's (reconciliation rewrite, release UI, Customers.php).

On balance I would rather start from B, but not by much.

- **A: 5 / 10**
- **B: 6 / 10**
