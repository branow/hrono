# t12 credit control: maintainer review of A and B

Reviewer stance: senior webERP maintainer who would have to merge and maintain one of these. I judged the code only, against
the BRD and against how the base tree (`scratchpad/base/`) already works. I checked the claims below in the code, not in NOTES.md.

Both are about the same size (A: 48 files, +2897/-33; B: 47 files, +2862/-71). Both make the same central design choice, and it is
the right one for webERP: credit status stays on `debtorsmaster.holdreason`, and `holdreasons.dissallowinvoices` means
0 = normal, 1 = stop and 2 = watch. Order entry, counter sales and special orders in the base tree already treat 2 as "watch",
so existing screens keep working. Both add review, history, dunning, charge and write-off tables. Both add update `sql/updates/44.php`,
security tokens 21 and 22, new systypes, menu entries, a manual section and the order-route hooks. The differences are in the
details, and the details are where each one breaks.

---

## 1. Completeness

| Area | A | B |
|---|---|---|
| Reviews with outcome, limit, notes, next date; limit updated in the same transaction (BR-01..04) | Yes (`CreditCustomer.php`) | Yes (`CustomerCredit.php`) |
| Next review date for new customers (UI, import, API) | Yes | Yes (also logs "account opened") |
| Stop / watch with reason, who and when (BR-05) | Yes, via `CreditSetStatus` + `creditevents` | Yes, via `CreditSetStatus` + `creditlog` |
| A way to *define* a watch status code | **No.** `CreditStatus.php` is untouched and still only offers 0/1. Watch codes exist only if 44.php or the non-demo seed created them. Saving a watch code in that form resets it to 0 | **Yes.** `CreditStatus.php` now offers Invoice OK / Watch / Stop |
| Stop blocks: sales office, web shop, EDI, recurring, API order creation | Yes | Yes |
| Stop/hold blocks dispatch and invoice | `ConfirmDispatch_Invoice.php` only. **API `InvoiceSalesOrder` is not guarded** | `ConfirmDispatch_Invoice.php` **and** API `InvoiceSalesOrder` |
| Credit control can release an order of a customer on stop (BR-06 "unless credit control releases them") | **No UI.** Only `creditholdstate = 1` (over-limit) orders get a release button. `CreditOrderBlockReason` honours state 2, but nothing sets state 2 for a stop-blocked order | Yes, `CreditHeldOrders.php` has a "customers on stop" table with release |
| Over-limit hold (BR-10) | Only when System Parameters `CheckCreditLimits = 3`, a new option. Default config is 1, so it is **off out of the box**. New orders only: amending an existing order past the limit is not held. API holds only if the customer is *already* over the limit at header time | On by default (`CreditHoldOverLimit=1`). Evaluated after the lines are written, on new **and** amended orders, per API line, and before API invoicing |
| Watch: warn order taker; credit control sees watched orders (BR-08) | Yes (worklist section) | Yes (`CreditHeldOrders.php`, banner on `SelectCustomer.php`) |
| Web shop tells a stopped customer to contact us (BR-11) | Base message kept; portal page warns | Message exists, but it keys on `$_SESSION['CustomerLogin']`, which is never set (see 2), so customers get the staff wording |
| Dunning stages configurable, preview, untick, email, post list, log (BR-12..16) | Yes | Yes |
| "A customer who pays must not get the next letter" (BR-15) | Nets unallocated receipts and credit notes against overdue (`CreditUnallocatedCredit`) | **No netting.** A customer who paid but whose receipt is unallocated is still chased (and charged interest) |
| Escalation | Jumps straight to the highest stage that qualifies, so a customer 60+ days overdue who was never chased gets the **final notice first** (at go-live, that is everyone old) | Moves up one stage at a time. Optional auto-stop after the final letter |
| Disputed invoices (BR-18) | Per-invoice dispute/settle with reason | Bulk checkbox save with one reason |
| Interest and/or fee, rate, fee, days, GL accounts (BR-19, 23) | Yes, plus fee per invoice and interest-on-charges options (open questions 2, 3) | Yes. Interest is per invoice for the days actually overdue in the month |
| Exempt interest **and/or** fees (BR-20) | One flag for both | Two flags, as asked |
| Preview and confirm, no double charge (BR-22) | Per-customer tick boxes + unique key | Whole list confirm + unique key + `FOR UPDATE`. Only months that have ended can be charged (A allows the current month) |
| Waiver with reason, reaches GL (BR-24) | Yes, waives the unpaid remainder | Yes, refuses partly paid charges |
| Write-off, approval threshold, auto-stop, report (BR-25..29) | Yes. Threshold and settings are token 22 (Finance Director) | Yes. Settings are token 21, so **the credit controller can raise the approval limit**, which defeats BR-26 |
| Credit control report filterable by rep and currency, home totals (BR-30) | Worklist (`CreditControl.php`) | `CreditControlReport.php` |
| Aged debtors: status, limit, last stage (BR-31) | Yes (colspan of detail and total rows not adjusted) | Yes, colspans adjusted |
| Audit history per customer (BR-32) | Yes | Yes |
| Reps see only their own customers (BR-33/34) | Yes | Yes |
| Portal: customer sees own reminders and charges, only own account (BR-35/36) | Yes. Dedicated `CustomerCreditPortal.php`, customer read from `www_users`. Also closes the existing hole in `CustomerInquiry.php` | **Broken.** See 2: any customer login can open any customer's full internal credit page |
| Ledger agreement and finding differences (BR-37/38) | Extends the existing `Z_CheckDebtorsControl.php` to include the new types | New `CreditReconciliation.php` that lists unmatched debtortrans and GL rows (useful), but `Z_CheckDebtorsControl.php` is not updated, so the existing utility now misreports |
| Install, upgrade, go-live (BR-39/40) | Upgrade good (creates normal/watch/stop codes, logs go-live status). Demo install gets no stop/watch codes | Upgrade, non-demo seed and demo.sql all consistent; normalises `-1` hold codes to 0 |
| Manual and sales note (BR-42/43) | Yes | Yes, and corrects the old "credit limit is memorandum only" text |

Net completeness: B covers more of the hold and release paths and fits the status maintenance screen. A covers the portal,
payment netting and authority split properly. Neither imports the spreadsheet stop list. Both expect credit control to
set stops after go-live, which the BRD allows.

## 2. Correctness

### B: customer-portal isolation does not work (blocker)

`CustomerCredit.php` and `CreditUserMaySee()` decide "is this a customer login?" from `$_SESSION['CustomerLogin']`.
Nothing in webERP sets that session key. `session.php` sets a local `$CustomerLogin`, and a grep of base and B finds no
assignment. So `$IsCustomerLogin` is always false. The script is registered at token 1, which customer roles hold, and
`CreditUserMaySee()` falls through to `return true` for a non-rep user. Result:
- a portal customer who opens `CustomerCredit.php?DebtorNo=OTHER` sees another customer's balance, limit, watch/stop status,
  review notes, the internal history and reminder recipients;
- even on their own account the customer sees the internal view (watch status, review notes, history), which BR-36
  and open question 10 rule out.

The same dead key is used in `DeliveryDetails.php`, `SelectOrderItems.php` and `CustomerInquiry.php` for the "do not tell
the customer about watch" logic, so a customer on watch does see the watch warning. This fails AC-10 outright.

### A: customer maintenance silently drops credit limit and status edits (regression)

In `Customers.php`:
```php
if ($CanEditCredit) {
    $CreditHoldSQL = "" . $CreditHoldSQL . "";
    $CreditLimitSQL = "" . $CreditLimitSQL . "";
}
```
Both strings stay empty for everyone, and the UPDATE no longer contains `holdreason=` or `creditlimit=`. A credit controller
who changes the limit or status on the customer form gets "Customer updated", and nothing changes. `CreditLogMaintenanceChange()`
then finds no change to log. The dedicated credit page still works, so the feature survives, but a long-standing core screen
now lies to its users.

### Ledger postings and currencies

- **A** (`CreditPostTransaction`): the debtortrans row carries the customer amount and a derived rate. GL lines are given in
  home currency, and the debtors-control line is computed as the negative sum, so the journal always balances. Charges post
  at the current rate. Waivers reverse at the charge's own rate. Write-offs post at the *historical* rates of the invoices
  they settle (`CreditWriteOffPlan`), so bad debt equals what debtors control holds for those invoices and no exchange
  difference arises. That is sound, but it books the FX effect inside bad debt rather than as "currency difference" (BR-27
  wording). Allocations update `alloc`/`settled` on both sides correctly.
- **B** (`CreditPostDebtorTrans` + `CreditAllocate` + `CreditPostExchangeDifference`): posts at the current rate, allocates
  oldest first, accumulates `(amt/creditRate - amt/debitRate)`, and posts the movement to `salesexchangediffact` against debtors
  control with the same sign convention as `CustomerAllocations.php`. Every posting ends with `EnsureGLEntriesBalance`. This is
  the more webERP-native treatment and matches BR-27 literally. It does not write `diffonexch` on the debit rows, as
  `CustomerAllocations.php` does. That is minor.
- Both use their own systypes with `GetNextTransNo`, so sequences are fine. A uses 51-53 and adds them to
  `DatabaseTranslations.php`. B uses 45-47 and adds no translations.
- **B's** `CreditReconciliation.php` computes customer home balances as `SUM(balance/rate)`. That ignores `diffonexch`, so
  any customer with past FX allocations shows a "difference" that the page cannot explain.

### Input handling (webERP escapes `$_POST` in `session.php`)

- **B** re-escapes already-escaped POST data with `DB_escape_string` (`DunningStages.php`, `CreditLogEvent`, write-off reason,
  waiver reason). In `DunningStages.php` this turns every line break into literal `\r\n` text as soon as Finance edits a letter,
  which breaks the one screen where Finance sets the wording. B also wraps already-encoded DB text in `htmlspecialchars`
  again, so `O'Brien` displays as `O&#039;Brien`. Email letters insert `debtorsmaster.name` undecoded (`&amp;` in emails).
- **A** mostly follows the base convention (raw POST into SQL, decoded with `html_entity_decode` when building emails).
  It double-escapes only inside `LogCreditEvent`, so multi-line review notes lose their line breaks in the history only.

### Transactions

Both wrap each posting (charge, waiver, write-off plus stop, review plus limit plus status) in `DB_Txn_Begin/Commit`. B passes
`$Transaction=true` to `DB_query` so a failure rolls back. A does not, and relies on the connection dropping. A posts an
approved write-off after flipping status to `approved` outside the transaction. If posting then fails, the row sits in
`approved`, which no screen lists.

### Hold enforcement on every route

| Route | A | B |
|---|---|---|
| Sales office order (DeliveryDetails) | stop yes, hold new only | stop yes, hold new + amended |
| Web shop (customer login) | stop yes | stop yes |
| EDI | stop + hold | stop + hold |
| Recurring | stop + hold, auto-invoice suppressed | stop + hold, auto-invoice suppressed |
| API order | stop yes, hold header-level only | stop yes, hold per line |
| Dispatch/invoice UI | yes (load and process) | yes (every render before process) |
| API invoicing | **no** | yes |
| Release of a stop-blocked order | **no UI** | yes |

## 3. Fit with webERP

- **Status maintenance:** B extends `CreditStatus.php` so watch can be maintained where users already maintain statuses.
  A leaves it as is and adds a "which code means normal/watch/stop" mapping in its own settings, an invention that
  `CreditStatus.php` can silently undo.
- **Over-limit setting:** A reuses the existing `CheckCreditLimits` System Parameter (new value 3). That is a good idea but
  off by default. B adds a separate `CreditHoldOverLimit` config that overlaps the existing setting.
- **Install:** B puts demo data into `demo.sql`, as webERP does. A adds `install/sql/creditcontrol_demo.sql` and a new step in
  `InstallFunctions.php`, a new pattern. A's install menu rows (selected roles) also differ from what its upgrade's
  `NewMenuItem` produces (all roles). B is consistent across upgrade, seed and demo.
- **Schema:** A gives the new tables foreign keys to `debtorsmaster`, as webERP tables usually have. B has none. B uses
  `NOT NULL DEFAULT '1000-01-01'` dates, the webERP convention. A uses NULL dates.
- **Security:** A puts settings and approval at token 22 and operations at 21. B puts settings at 21.
- **Existing utilities:** A updates `Z_CheckDebtorsControl.php`. B leaves it wrong and adds a parallel report.
- **Pages, forms, manual:** both follow the usual page skeleton, `prnMsg`, `FormID`, `fieldset/field`, `$ViewTopic/$BookMark`,
  and the manual Help Begin/End markers. B also updates the existing Customers section of the manual.
- **Translations:** A registers the new systypes in `DatabaseTranslations.php`. B does not.

## 4. Structure and code quality

- **A:** one function library (543 lines), five main pages (worklist, customer credit, reminders, charges, write-offs with
  their report) plus settings and portal. The worklist page doubles as the credit control report. The library is coherent:
  `CreditOrderCheck`, `CreditOrderBlockReason`, `CreditOverduePosition` and `CreditReminderDue` are reusable and well named.
  `CreditCustomerRecord` is called often (N+1 queries in previews), which is fine at 900 customers. Status is passed as
  `'normal'/'watch'/'stop'` strings mapped to codes through config, which adds indirection.
- **B:** a smaller library (438 lines) and more single-purpose pages (report, held orders, reconciliation, write-off report,
  dunning stages, dunning run, charges, write-off, settings, customer credit). Each page is easier to read on its own, and the
  posting helpers mirror `CustomerAllocations.php`, which a maintainer will recognise. There is some duplication (review-date
  arithmetic is repeated inline in the API and import, and "type IN (10, charge) AND settled = 0" is repeated four times).
  The `onclick="this.form.WaiveID.value=…"` trick for waiver is fragile.
- Neither adds a PDF for the letters. Both print posted letters as `<pre>` blocks on screen. That is acceptable but not
  webERP's usual PDF route.

## 5. Regressions

- **A:** Customer maintenance no longer saves credit limit or status, for anyone (see 2). `SelectOrderItems.php` customer
  login now admits `-1` and watch customers (intended). AgedDebtors detail rows keep `colspan="6"` under a 9-column header.
- **B:** `Z_CheckDebtorsControl.php` now shows a difference whenever charges, waivers or write-offs exist. 44.php rewrites any
  `dissallowinvoices = -1` hold codes to 0. That is defensible, but it changes how `CustomerInquiry` flags those customers.
  demo.sql reclassifies the demo hold codes (several become stop). The portal leak is a new hole, not a regression of an
  existing one, but it is the worst defect in either submission.

## 6. What a maintainer must fix before merging

**A** (most serious first)
1. `Customers.php`: restore `holdreason='…',` and `creditlimit='…',` in the UPDATE for token-21 users (the assignments are no-ops).
2. Guard API `InvoiceSalesOrder` with `CreditOrderBlockReason`.
3. Add a release action for open orders of customers on stop (set `creditholdstate = 2`), as BR-06 requires.
4. Hold over-limit orders when an existing order is amended, and evaluate API holds per line, not at header time only.
5. Decide the default: either ship `CheckCreditLimits = 3` or say clearly in the upgrade that BR-10 needs it.
6. Escalate one stage at a time, or at least never open with the final notice.
7. Extend `CreditStatus.php` to offer watch (2), so the existing form cannot reset a watch code. Seed stop and watch codes in the demo install.
8. Split the exemption into interest and fees. Restrict charging to ended months. Fix the AgedDebtors colspans. Drop the double escape in `LogCreditEvent`.
9. Fold `creditcontrol_demo.sql` into `demo.sql`, and make the install menu rows match the upgrade.

**B** (most serious first)
1. Replace every `$_SESSION['CustomerLogin']` with the real test (`global $CustomerLogin` or the token-count rule from
   `session.php`). Force `$DebtorNo = $_SESSION['CustomerID']` for customer logins in `CustomerCredit.php` and `CustomerInquiry.php`.
2. Remove the second `DB_escape_string` on POST data (`DunningStages.php` above all) and the second `htmlspecialchars` on
   output. Decode entity-encoded names in letters.
3. Net unallocated receipts and credits before chasing or charging (BR-15, AC-06).
4. Move `CreditControlSettings.php` to token 22 so the controller cannot change the write-off approval limit.
5. Add types 45-47 to `Z_CheckDebtorsControl.php`. Include `diffonexch` in `CreditReconciliation.php`.
6. Add the systypes to `DatabaseTranslations.php`, foreign keys on the new tables, and set `diffonexch` on the debit side of write-off allocations.

## 7. Other observations

- A's worklist "final notice sent, still overdue, not on stop" list is a nice answer to open question 4 that leaves the decision with Maria.
- A records the go-live status of already-held customers as history rows, which gives auditors a starting point.
- B's "Debtors Ledger Reconciliation" listing of debtortrans without GL rows, and GL rows without debtortrans, is a genuinely
  useful month-end tool for BR-38, even with the FX blind spot.
- B posts charges for a month with `FOR UPDATE` against concurrent runs. That is a careful touch.
- A protects credit history from customer deletion and code change. B handles code change only.

## 8. Verdict

**I would rather merge A, somewhat.**

Both are serious, complete-looking implementations with one bad defect each, plus a set of smaller gaps. B's defect is worse in
kind: it exposes one customer's internal credit file to every other portal customer, against an explicit requirement, and its
escaping bug breaks the letter-wording screen Finance has to use. A's defect is a no-op assignment that makes the customer form
silently ignore credit edits. That is embarrassing but contained, because the dedicated credit page does the job and logs it. A
also gets the authority split, the payment netting and the existing integrity check right. B is better on enforcement
breadth (API invoicing, amended orders, releasing stop-blocked orders), on the status screen and on FX treatment. Those are
real merits, so the margin is not large.

- **A: 6/10**
- **B: 5/10**
