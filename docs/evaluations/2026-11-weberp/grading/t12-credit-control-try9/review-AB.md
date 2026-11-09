# Review: T12 Credit Control, implementation A vs implementation B

Reviewer stance: webERP maintainer who would have to merge and look after this. I read both diffs in full, compared them with the base tree, and checked the important claims against the code. I did not rely on NOTES.md. Nothing was executed.

## Summary

The two implementations share the same core design, and it is the right one for webERP. Both treat credit status as the existing `debtorsmaster.holdreason` → `holdreasons.dissallowinvoices`, where 1 = stop and 2 = watch. The value 2 is already used by `SelectOrderItems.php`, `CounterSales.php` and `SpecialOrder.php`. Both make `CreditStatus.php` a three-way choice and add a shared `includes/CreditControlFunctions.php`. Both put the order-route checks in `DeliveryDetails.php`, `EDIProcessOrders.php`, `RecurringSalesOrdersProcess.php` and the API, and block dispatch and invoicing in `ConfirmDispatch_Invoice.php` and the API's `InvoiceSalesOrder`. Both add an update `sql/updates/44.php` plus install and demo seeds.

The difference is how much was finished:

- **A** delivers essentially the whole BRD. That covers reviews, stop/watch, held-order release, the reminder run, letter stages per language, month-end charges and waivers, write-offs with approval and a report, the credit control report, per-customer history including the portal view, aged-debtors columns, reconciliation, the go-live import, and a manual chapter. It also fixes the existing reports that classify transactions by type. It has real bugs, but they are local.
- **B** has good-quality code in what it built: the customer credit page, the dunning run, charges and waivers, settings with a CSV loader, and order-route enforcement. But it registers scripts and menu items for **four pages that do not exist**: `CreditControlWriteOff.php`, `CreditControlReport.php`, `DebtorsGLReconciliation.php` and `CustomerCreditNotices.php`. Write-offs, the credit control report, the portal view, the reconciliation and the manual are all missing. Worst of all, there is **no way to release an order held for credit control**, so every over-limit order becomes permanently un-invoiceable.

---

## 1. Completeness

| Area (BRD) | A | B |
|---|---|---|
| BR-01..04 reviews, history, limit updated with review | `CreditReview.php`. Append-only `creditreviews`; limit, status, exemptions and next date are written in one transaction; outcome is derived. | `CustomerCredit.php`. Explicit outcome with validation (raise must be higher, etc.); limit and review in one transaction. Good. |
| BR-02 review date for new customers | `Customers.php`, `Z_ImportDebtors.php`, API `InsertCustomer`. | `Customers.php` only. API and CSV-imported customers get NULL. |
| BR-05/07 stop/off with reason, who/when; only credit control | Status and limit can be changed only in `CreditReview.php` (token 21). Removed from `Customers.php` UPDATE, `Z_ImportDebtors.php` and API `ModifyCustomer`. | Status/limit read-only in `Customers.php` for non-controllers, and changes are logged. **API `ModifyCustomer` still changes `holdreason`/`creditlimit` freely.** |
| BR-06 every route blocked; existing orders not dispatched unless released | Sales office/web shop (DeliveryDetails), EDI, recurring, API header, dispatch/invoice, API invoice. Release in `CreditHeldOrders.php`. | Same routes covered. **No release mechanism exists** (`creditflag=3` is never set anywhere). |
| BR-08 watch: warning + credit control sees orders | Warning at DeliveryDetails; `CreditHeldOrders.php` lists open orders of watched customers. | Orders are flagged `creditflag=2`, but the page meant to list them (`CreditControlReport.php`) is missing. |
| BR-09 status visible | Banners on CustomerInquiry/CustomerAccount, aged debtors, review/history pages. | Only the existing base warnings and the unlinked `CustomerCredit.php`. |
| BR-10 over-limit held for approval | New `CheckCreditLimits=3` mode, used in every route; release page exists. | Held whenever `CheckCreditLimits>0`, with no release. See section 2. |
| BR-11 web shop shows "on hold" | Base behaviour kept; portal banners improved. | Base behaviour kept. |
| BR-12..17 dunning stages, email, preview/exclude, no repeat, record, currency | `DunningStages.php` (any number of stages, final-notice flag, wording per language); `DunningRun.php` preview/untick/send, `dunninglog` stores the letter text. | Stages edited in `CreditControlSetup.php`; `CreditControlDunning.php` preview/untick/send; `dunninghistory`; falls back to the branch email. Good. |
| BR-18 disputed invoices | Yes. | Yes. |
| BR-19..24 interest/fees, exemptions, preview, no double charge, GL accounts, waivers | Yes. Separate types 51/52/53; unique key per customer/month/type. | Yes. Type 60/61; unique key; waiver reversed at the original rate (better than A's). |
| BR-25..29 write-off, approval, GL with FX diff, auto-stop, report | `CreditWriteOffs.php`: threshold in home currency, approver cannot be the requester, FX difference via allocation, auto-stop, period report. | **Missing.** The table, type 62 and a menu item exist, but no page. |
| BR-30 credit control report (rep/currency filter, home totals) | `CreditControlReport.php`. | **Missing** (menu item points at a non-existent file). |
| BR-31 aged debtors status/limit/last stage | Yes. | No. |
| BR-32 per-customer audit history | `creditlog` plus `CreditHistory.php`. | `creditcontrollog`, shown in `CustomerCredit.php`. Good. |
| BR-33/34 reps see only their own customers | Yes, with a leak (see section 2). | Yes. |
| BR-35/36 portal reminders/charges, own account only | `CreditHistory.php` for portal users. Also fixes the existing CustomerInquiry/CustomerAccount `CustomerID`-in-URL hole. | **Missing** (`CustomerCreditNotices.php` does not exist). |
| BR-37/38 debtors control agreement and diagnosis | `Z_CheckDebtorsControl.php` now includes the new types and lists unmatched entries. Also `CustomerBalancesMovement.php` and `DebtorsAtPeriodEnd.php` updated. | **Missing.** The existing `Z_CheckDebtorsControl.php` only sums types 10/11/12, so B's charges show up as unexplained differences. |
| BR-39/40 live + new install, go-live load | Update 44 plus seeds; `Z_ImportCreditStatus.php` with dry-run then confirm. | Update 44 plus seeds; CSV loader in settings, all-or-nothing transaction. B also seeds `holdreasons` for fresh non-demo installs. The base has none, so this is a real fix that A lacks. |
| BR-42/43 manual and sales note | `doc/Manual/ManualCreditControl.html` and a `ManualOutline.php` entry. | None. |

Things a working credit-control feature needs that the BRD did not spell out:

- **A** covers these: customer code change (`Z_ChangeCustomerCode.php`), the delete guard, the existing reports that classify by type, and a settings page.
- **B** has the delete guard and the settings page, but not the type-classification fixes or the customer code change.

## 2. Correctness

### B

1. **Held orders can never be released (critical).** `OrderCreditBlock()` refuses dispatch/invoice when `creditflag=1`. Only `ORDER_CREDIT_RELEASED=3` lets an order through, and nothing in the tree ever writes 3. Re-editing the order keeps the flag: `DeliveryDetails.php` deliberately preserves HELD/RELEASED. That is true even when credit control edits it. The only way out is a manual database edit.
2. **Changes existing behaviour for every site with "warn on breach" (critical regression).** `CreditCheckForNewOrder` holds an order whenever `CheckCreditLimits > 0` (so also mode 1, "warn") and the user is not a credit controller. The webERP default is 1. Combined with point 1, a live site's over-limit orders become stuck after the upgrade.
3. Menus and scripts for four pages that do not exist. Users get links that fail.
4. `CustomerCredit.php`, the central page for reviews, stop/watch, disputes and exemptions, has no menu item and no link from `SelectCustomer`/`Customers`. It is reachable only from the dunning and charges lists.
5. Charges (type 60) are counted as credits in `CustomerBalancesMovement.php`, which uses "type=10 is a debit, everything else is a credit". They are also missing from `Z_CheckDebtorsControl.php`. BR-37/38 fail in the very report Finance would use.
6. The API comment says the over-limit check is applied at invoice time. It is not: `InvoiceSalesOrder` only calls `OrderCreditBlock`. API orders are never held for being over the limit.
7. Good: postings (`PostCreditControlTransaction`) are balanced, `EnsureGLEntriesBalance` is called, everything runs inside transactions, and charges are rounded to the currency's decimals. The waiver is reversed at the charge's original rate, so the income account is reversed exactly. The letter text is `html_entity_decode`d before emailing, which correctly undoes session.php's escaping. Email failures are not recorded as sent.

### A

1. **Operator-precedence bug in `CreditHistory.php:775`.** `$SeesEverything = !$IsPortalUser and (...)` assigns `!$IsPortalUser`, so every staff user who can see the customer, including sales reps, gets the full audit trail: internal notes and waiver reasons. Reps are still limited to their own customers, so this is a leak of internal detail rather than of other reps' data. It still contradicts the file's own comment. The fix is `&&` or brackets.
2. **Letter text double-encoding.** `DunningStages.php` stores `$_POST` text, which session.php has already `htmlspecialchars`'d. It then re-escapes the text into the textarea, so it grows `&amp;amp;…` on every save. `DunningLetter()` emails it without `html_entity_decode`, so an apostrophe in edited wording reaches customers as `&#039;`. The seeded texts avoid apostrophes, so this only shows once Finance edits a letter, which they will. B handled this correctly.
3. Waivers and write-offs are posted at the **current** currency rate (`CreditInsertDebtorTrans` uses `$Status['rate']`). The FX difference against the original item goes through `CreditAllocate` to `salesexchangediffact`. Debtors control is therefore consistent and BR-27's "including any currency difference" is met. However, a waiver does not reverse the interest/fee income account by exactly the amount originally posted. That is acceptable, but B's approach is cleaner for waivers.
4. Update 44 migrates `CheckCreditLimits` 0/1 to 3, so over-limit orders start being held on live systems. This is intended by BR-10 and documented in the manual ("Going live"). But it also turns on credit checking for sites that had it off, and fresh installs keep `1`, so new and upgraded installs behave differently.
5. Editing an existing order passes order value 0 to `CreditOrderCheck`, so increasing an existing order past the limit is not held.
6. `debtortrans` rows for charges and write-offs are written with `branchcode=''` and `tpe=''`. There is no FK, and receipts already do the same, but B's choice of first branch and salesperson is friendlier to rep-filtered reports.
7. Rejecting a write-off updates the row outside the transaction, and a request row is deleted again if immediate posting fails. These are minor and harmless.
8. Good: there is one enforcement rule (`CreditOrderCheck`) for every route. Allocations update `alloc`, `settled` and `diffonexch` the way `CustomerAllocations.php` does. The month-charge uniqueness is enforced by a unique key. The dunning "episode" logic (no repeat stage since the oldest item fell due, plus a minimum gap) satisfies BR-15/AC-06. The portal is pinned to `LoginCustomerID`, which closes a real existing hole. NOTES.md says existing sessions must log in again; I confirmed that in `LoginFunctions.php`.

### Common gap (both)

The base `SelectOrderItems.php` customer self-order path only proceeds when `dissallowinvoices == 0`. A **watch** customer therefore cannot order in the web shop, contrary to BR-08 ("can still be supplied"). Neither implementation fixes it. Both make watch a first-class status, which makes the bug more visible.

## 3. Fit with webERP

- **Upgrade.** A uses the stock helpers throughout (`AddIndex`, `NewSysType`, `InsertRecord`, `NewMenuItem`, `NewScript`). B uses raw `SHOW INDEX` and `INSERT … WHERE NOT EXISTS` for the same things. That works, but it is not the house idiom. Both keep `install/sql/tables`, `data` and `demo.sql` in line with the update. The installer uses either the data files or demo.sql, so the duplicated config keys are not a clash.
- **Forms and dates.** B uses `class="date"`, `Is_Date` and `FormatDateForSQL` in the user's date format, which is the webERP way. A uses HTML5 `type="date"` and `type="month"` with ISO strings and regex checks in several pages. That ignores `DefaultDateFormat` and is inconsistent with the rest of the system.
- **Settings.** A puts its accounts in `config`. B puts them on `companies`, next to `debtorsact` and `freightact`, which is more natural for GL control accounts. Both expose a dedicated settings page instead of `SystemParameters.php`. A additionally extends `SystemParameters.php` with the new credit-limit mode, which is the right place.
- **Security.** Both add tokens 21/22. A gives token 21 to Accountant and Sysadmin. B also gives it to the AR Clerk, which is arguable given "sales office must not".
- **Manual.** A follows the `ManualOutline.php` and `Manual*.html` convention. B has nothing.
- **Translations.** Neither adds .po strings. Both wrap strings in `__()`.
- **Menus.** A places items under AR Transactions/Reports/Maintenance and Utilities, which is sensible. B's menus include dead links.

## 4. Structure and code quality

- **B.** Per page, B is the tidier code: clear helper functions (`GetDunningCandidates`, `ChargeProposals`, `PostCreditControlTransaction`, `AllocateCreditControlTransaction`), named constants for statuses and flags, validation that re-checks candidates at post time, and good comments. Its `CustomerCredit.php` is a sensible single hub. The problem is that it is half a feature.
- **A.**
  - The code is also well organised: one functions file, one rule for order checks, consistent `Credit*` naming.
  - Blemishes:
    - `CreditStatus.php` is left with `if (true) { … } else { …dead… }`.
    - Indentation is mangled in the API and DeliveryDetails hunks.
    - `AgedDebtors.php` runs one query per row (N+1).
    - Date handling is duplicated with ISO strings.
  - A spreads a lot of small edits across existing files: reports, Contracts, CounterSales, IntoCart for the new mode 3. That means more merge surface, but each edit is justified.

## 5. Regressions

**B**
- Over-limit orders at "warn" sites become held, and held orders cannot be released, so invoicing stops for those customers.
- Charges distort `CustomerBalancesMovement.php` and `Z_CheckDebtorsControl.php`.
- The menu has four broken links for every role.

**A**
- `CheckCreditLimits` is silently raised to "hold" on upgrade, including for sites that had checking turned off. This is intended but should be opt-in or at least announced.
- Credit limit and status can no longer be edited in `Customers.php`, the API or the customer import. This is intended by BR-07, but it changes existing workflows and integrations.
- Portal users logged in before the upgrade see nothing until they log in again.
- Reps see internal audit notes (bug A1).

## 6. What a maintainer must fix before merging

### B (most serious first)
1. Add an order release/re-hold page that sets `creditflag` 3/1, and list held and watched orders.
2. Apply the over-limit hold only under an explicit new `CheckCreditLimits` mode, not under "warn".
3. Write the four missing pages (write-off with approval and report, credit control report, debtors/GL reconciliation, portal notices), or remove their scripts and menu items.
4. Teach `Z_CheckDebtorsControl.php`, `CustomerBalancesMovement.php` and `DebtorsAtPeriodEnd.php` about types 60–62.
5. Link `CustomerCredit.php` from the menu and from the customer selection/inquiry pages.
6. Strip `holdreason` and `creditlimit` from API `ModifyCustomer`; set `nextreviewdate` in the API and in `Z_ImportDebtors.php`.
7. Add the aged-debtors columns and the manual chapter.
8. Implement the API over-limit hold or correct the comment.
9. Fix watch customers in the web shop (common gap).

### A
1. Fix the precedence bug in `CreditHistory.php:775`.
2. `html_entity_decode` the letter subject and body before sending, and stop double-escaping in `DunningStages.php`.
3. Make the `CheckCreditLimits`→3 migration opt-in (or limit it to 1→3), and use the same default for fresh installs.
4. Replace `type="date"`/`type="month"` inputs with webERP's `class="date"` and `DefaultDateFormat` handling.
5. Seed `holdreasons` (normal/watch/stop) for fresh non-demo installs.
6. Check the over-limit hold when an existing order is edited, using the change in value.
7. Consider reversing waivers at the charge's original rate. Set branch and salesperson on the new `debtortrans` rows.
8. Clean up `if (true)` in `CreditStatus.php` and the hunk indentation; remove NOTES.md from the tree.
9. Fix watch customers in the web shop (common gap).

## 7. Other observations

- **A** found and fixed a real existing security hole: portal users could view any customer's inquiry/account by changing `CustomerID` in the URL. It also fixed an old bug in `Z_CheckDebtorsControl.php`, where `$DiffTotal` was accumulated before `$diff` was computed.
- **A** supports wording in several languages with an English fallback (Open Question 9). B does not.
- **B**'s choice of explicit review outcomes with validation, and its email fallback to the branch address, are nicer than A's.
- **B** registers a description for each script in the install seeds, but `NewScript` in the update writes an empty description, so new and upgraded installs differ cosmetically. A has the same pattern.

## 8. Verdict

**I would merge A, clearly.** A delivers a complete, coherent credit-control feature that a maintainer can finish with a short list of local fixes. B's code is pleasant where it exists, but it is missing a third of the business scope and ships broken menu links. Its over-limit hold, combined with having no release, would stop invoicing on live systems, so it cannot be merged without substantial additional work.

- **A: 7/10**
- **B: 3/10**
