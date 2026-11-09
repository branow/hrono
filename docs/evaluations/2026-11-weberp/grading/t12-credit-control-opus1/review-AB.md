# Review: T12 Credit Control — implementation A vs implementation B

Reviewer stance: webERP maintainer who would have to merge and maintain one of these. I read both diffs and trees in full where it mattered, compared them against the base tree, and checked the key claims against base code (`GetCreditAvailable`, `EnsureGLEntriesBalance`, `GetConfig.php`, `session.php` input escaping, `gltotals` triggers, `CustomerAccount.php`, `index.php` customer menu, `UpgradeDB_*` helpers). I did not rely on either NOTES.md.

Both implementations are large (~6,000 diff lines each). Both are serious, mostly complete pieces of work, and they share the same basic architecture:
- credit status = existing `debtorsmaster.holdreason` → `holdreasons.dissallowinvoices` (0 normal / 1 stop / 2 watch; base already half-supports 2 = watch);
- an audit log table plus reviews, dunning stages/letters/items, disputes, charges, write-offs and write-off items;
- new systypes 13/14/45/46/47 and tokens 21 (credit control) / 22 (write-off approval);
- one shared `includes/CreditControlFunctions.php`;
- upgrade script `sql/updates/44.php` plus install seeds, demo.sql, menus and a manual chapter.

They differ in many details, and those details decide the comparison.

---

## 1. Completeness

| Area | A | B |
|---|---|---|
| Credit reviews (BR-01..04) | Yes. `custcreditreviews`; limit and status change in the same transaction as the review; history read-only | Yes. Same design in `RecordCreditReview()`; review date is datetime; also checks "confirmed" outcome = unchanged limit |
| Next review date for new customers (BR-02) | Customers.php, Z_ImportDebtors, API. Separate shorter "high-risk" period (`CreditReviewMonthsHighRisk`) for watch/stop | Customers.php, Z_ImportDebtors, API. One period only; the high-risk period is left to the user |
| Next review date for existing customers at go-live (BR-40, AC-11) | **No.** Upgrade leaves `NULL`; Finance must run "Set Review Dates" in settings or the import. Documented, but AC-11 is not met after upgrade alone | Yes. Upgrade sets +12 months; import overrides |
| Stop/watch with reason and audit (BR-05) | Yes | Yes |
| Stop enforced on every route (BR-06) | Order entry (DeliveryDetails, incl. modifications), web shop, API header, EDI (**refused**, with email advice), recurring (skipped). Dispatch/invoice/picking/API invoice check the **live** customer status plus a hold record | Order entry (new orders), web shop, API header, EDI (**accepted but held**), recurring (skipped and recurrence advanced). Going on stop sets `salesorders.credithold=1` on all open orders; upgrade backfills this. Dispatch/picking/API invoice check the flag. Also covers SpecialOrder, CounterSales, Contracts and the SelectSalesOrder list |
| Only credit control changes status/limit (BR-07, AC-03) | Customers.php (fields locked), API ModifyCustomer, CreditStatus.php moved to token 21 | Same, plus Z_ImportDebtors goes through the logged functions. CreditStatus.php refuses to change the meaning of a status code that customers already have |
| Watch: warning plus list for credit control (BR-08, AC-04) | Records a "noted" row in `creditorderholds` **at the time the order is taken**, so the list is accurate history | Lists recent orders of customers who are on watch **now**. Orders taken while on watch disappear from the list once the customer goes back to normal, and orders taken before the watch appear on it |
| Status visible everywhere (BR-09) | `ShowCreditStatusWarnings()` in SelectCustomer, order entry, dispatch, inquiry, account | `ShowCreditStatusBanner()` in the same places, plus SelectSalesOrder shows "Credit Hold" instead of the Invoice link |
| Over-limit hold (BR-10, AC-05) | New setting `CreditHoldOverLimit`, **default on**. Exposure re-checked when an order grows beyond its released value | Reuses the existing `CheckCreditLimits` with a new value 3 ("hold"). **Default stays 1 (warn)**, so BR-10 is off until an admin turns it on. Re-checked when value grows, **including direct line edits in SelectOrderItems/IntoCart** |
| Web shop "your account is on hold" (BR-11) | Yes, and fixes the base bug where watch customers could not order from the portal | Yes, and fixes the same bug |
| Dunning stages, emails, preview, exclusion, no repeat stage, paid customers skipped (BR-12..16, AC-06) | Yes. Stage is the max stage already sent for the items still overdue. Minimum gap between letters. "Final notice" flag feeds the report | Yes. Cycle logic based on the last letter date against the oldest due date. Shows "not due, and why" list. **Records why a customer was left out.** Tracks email failures (`method='F'`) |
| Letters in customer currency with invoice list (BR-17) | Yes | Yes, as a fixed-width table |
| Disputes (BR-18) | Yes. Dispute rows are kept with resolution, so there is a history | Yes. Settling **deletes** the dispute row; history survives only in the log |
| Interest/fees, exemptions, preview, no double charge, GL accounts (BR-19..23, AC-07) | Yes. Interest = net overdue × rate/12. Unique key (debtor, period, type). GL balance checked **before commit** with rollback | Yes. Interest is daily pro-rata per item for the days overdue in the month (more defensible). Unique key (debtor, month, type). Uses base `EnsureGLEntriesBalance` |
| Waiver to ledger (BR-24) | Yes, at the charge's rate. Refuses if the charge is already paid | Yes, at the charge's rate. Allows waiving a paid charge, which leaves an unallocated credit (reasonable) |
| Write-off, approval, GL with FX difference, auto-stop, report (BR-25..29, AC-09) | Yes. Separate approval page (token 22); requester cannot approve; at approval, items already paid are silently trimmed | Yes. Approval sits on the write-off page, so the FD needs token 21 **and** 22; requester cannot approve; items are re-validated and approval refuses if they are no longer outstanding. Default approval limit 0 = everything needs approval |
| Bad debt recovery (open question 7) | Yes (type 47) | Yes (type 47) |
| Credit control report (BR-30) | Yes. Exposure = balance + open orders | Yes. Over-limit uses balance only |
| Aged debtors status/limit/last stage (BR-31) | Yes | Yes |
| Per-customer audit history (BR-32) | Yes | Yes |
| Reps see only their own customers (BR-33/34) | Yes | Yes, plus `SalesmanCustomerFilterSQL()` used in lists |
| Portal: reminders and charges (BR-35/36, AC-10) | Lists added to **CustomerAccount.php**. The customer portal menu (`index.php`) links only to CustomerInquiry.php, so **customers have no way to navigate to it**. Own-account lock added to both pages. HTML letter view | New `CustomerCreditHistory.php`, **linked from the portal menu**. Own-account lock on all pages. PDF letter view |
| Charges shown on the customer account (BR-21) | Base CustomerAccount.php only renders types 10/11/12; A adds an "other types" branch, so charges, waivers and write-offs show | **Not handled.** On-screen CustomerAccount silently omits type 13/14/45/46/47 rows while the balance includes them. PDF statements are fine because they use typename generically |
| GL ↔ ledger reconciliation (BR-37/38, AC-08) | New `DebtorsControlReconciliation.php` (works). Also patched `Z_CheckDebtorsControl.php`, which in this base queries a non-existent `chartdetails` table, so the patch is to a script that cannot run | **Rewrote `Z_CheckDebtorsControl.php` in place** on `gltotals` (maintained by triggers) with per-transaction drill-down. Fixes a broken base page instead of adding a second one |
| Go-live import (BR-40) | `CreditStatusImport.php`. Validates the whole file first and loads nothing if any line is wrong | `Z_ImportCreditStatus.php` with a test-run (rollback) mode. Errors skip the row |
| Manual and sales note (BR-42/43) | ManualCreditControl.html with a sales-staff section, ManualOutline, ManualCreditStatus | Same scope |

Net on completeness: roughly even. A misses go-live review dates and portal reachability. B misses charges on the on-screen account and leaves BR-10 off by default.

## 2. Correctness

**Ledger postings and FX.** Both are correct as far as I could verify:
- Charges debit debtors control and credit the chosen income account at the customer rate.
- Waivers reverse at the original charge rate, so no FX difference arises.
- Write-offs are a credit at today's rate. Bad debt is debited at today's rate, and the allocation realises the exchange difference against `salesexchangediffact` with the same sign convention as `CustomerAllocations.php`. I checked the signs.
- `diffonexch` is maintained on both sides of the allocation.
- Both reconciliation formulas (`amount/rate − diffonexch` on credits) agree with each other and with how allocations post.

Differences:
- A rounds home amounts before posting and verifies the GL nets to zero before commit (`CreditControlGLBalances`), rolling back otherwise. That is safer.
- B posts unrounded home amounts and relies on base `EnsureGLEntriesBalance`. Base behaviour there is to roll back and then let the caller "commit" and print success, which is a known base quirk that B inherits.

**Transactions.** Both wrap each business action in `DB_Txn_Begin/Commit`.
- A sends dunning emails after commit; if sending fails, the letter row still says `email`. A does list the failure on screen.
- B sends the email inside the transaction and then marks `F` on failure. If anything rolled back after the send, the email would already be out. This is minor for both.

**Text escaping.** `session.php` already runs `DB_escape_string(htmlspecialchars())` on all POST/GET values.
- A passes those values into functions that escape again. Newlines in review/status reasons end up stored as a literal `\n` in the event log. This is cosmetic.
- B handles it on purpose with `CCInput()` (`stripcslashes`). That has its own oddity: a user typing `\n` gets a newline.

**Config types.** `GetConfig.php` casts numeric config to float.
- A noticed this and reads GL account codes straight from the config table, keeping leading zeros.
- B's `CreditControlConfig()` prefers `$_SESSION`, so an account like `04900` becomes `4900`. On charts with leading-zero codes, B would post to the wrong account, or `CreditControlGLSetupErrors` would block it. This is a real but edge-case bug.

**Hold enforcement design.**
- A checks the *live* stop status at dispatch and stores holds in a side table. Taking a customer off stop releases their old orders automatically. A released over-limit order is only re-held when it passes through DeliveryDetails. **Lines changed directly in SelectOrderItems on an existing order, which webERP writes immediately, bypass the re-check**, and dispatch does not compare the value with `releasedvalue`. SpecialOrder.php orders are never evaluated for the limit.
- B uses a `salesorders.credithold` flag set at every entry point, including IntoCart/SelectOrderItems direct edits and SpecialOrder. This is more thorough. The cost is that a customer taken off stop still has every pre-stop order on hold until each one is released individually. That matches the strict wording of BR-06, but AC-02 suggests users will expect orders to flow again.

**Recurring orders while on stop.**
- A skips the run without advancing `lastrecurrence`. After the stop is lifted, the missed recurrences are created over the following runs, one per run, which is a supply backlog the business would not want.
- B advances the recurrence and logs the skipped one. B is better here.

**Upgrade.** Both are idempotent and use the standard helpers.
- A grants the new tokens to **every role holding token 15**. That is robust.
- B hard-codes `secroleid 8`. That is fragile on live systems where role 8 has been renamed or deleted.
- A seeds or reuses hold reasons more carefully (it checks that its fixed codes 90/91/97–99 are free).
- B also adds indexes on the new columns and backfills `credithold`.
- A adds foreign keys from every new table to `debtorsmaster`. B adds almost none.

## 3. Fit with webERP

- **Configuration.** B reuses `CheckCreditLimits` and `GetCreditAvailable()`. A invents a parallel `CreditHoldOverLimit` setting and duplicates the credit-available calculation. B is the webERP way.
- **Reports and printables.** B's reminder letters are Dompdf PDFs, including a batch print of all letters that need posting, which matches current webERP PDF practice. A uses an HTML page.
- **Existing scripts.** B repairs `Z_CheckDebtorsControl.php`. A adds a second reconciliation page and leaves the old one broken while appearing to have updated it.
- **Security idioms.**
  - B uses the established "NB Not a script" pseudo-script rows (`CreditControlAuthority`, `WriteOffApproval`), so the tokens can be reconfigured in Page Security without code changes.
  - A hard-codes tokens 21/22 in `CanManageCredit()`. That works, but admins cannot remap the tokens.
- **Menus, scripts, install seeds, demo.sql, systypes, ManualOutline.** Both follow the conventions. B uses `__()` on menu captions inside 44.php, which is harmless.
- **Forms.** Both use the fieldset/field/fieldhelp markup and `type="date"` inputs, which base already uses widely. B uses `<button name=... value=id>` per row and `SortedColumn` headers, which is slightly more modern-webERP.
- **Customer code change.** A updates every credit table in `Z_ChangeCustomerCode.php`. B does not touch it.

On balance B fits webERP better, with the exception of the customer-code change.

## 4. Structure and code quality

- **A.** Clean and readable. The function library is small (~750 lines). Business logic is split: posting and charge/dunning logic lives partly in the pages (`ProposeCharges`, `DunningProposal` defined inside the page scripts), and SQL INSERTs are inline in pages (reviews, write-offs, charges). There is some duplication (exposure SQL appears in three places). Hold types and statuses are stringly typed (`'stop'`, `'limit'`, `'watch'`) alongside constants.
- **B.** Larger library (~1,250 lines), but almost all business rules live in it: `RecordCreditReview`, `ProposeDunningRun`, `CalculateCreditCharges`, `PostCreditCharge`, `WaiveCreditCharge`, `RequestWriteOff`, `PostWriteOff`. Pages are thin. The header comment states that callers own the transaction. Names are consistent. This is easier to test and to call from the API or cron later.
- **Naming.** A: `custcreditevents`, `creditwriteoffs`, `dunningstages`. B: `creditcontrollog`, `writeoffs`, `dunninglevels`. Both are fine. B's `writeoffs` is a little generic for a shared schema.
- **Comments.** Both are well commented with BR references. B's NOTES-style "why" comments are slightly better targeted.

B is easier to maintain.

## 5. Regressions

**A**
- `Z_CheckDebtorsControl.php` was edited but remains broken (base issue, not new). A second reconciliation page now exists.
- `CreditHoldOverLimit` defaults to 1. On upgrade, every order that takes an existing customer over a (possibly stale) limit is held immediately. This is intended by the BRD, but it is a visible behaviour change on day one, and A does not tie it to the existing `CheckCreditLimits` setting, so the two can contradict each other (for example "prohibit" alongside "hold").
- Recurring orders back up while a customer is on stop.
- Changing the meaning of a hold reason in CreditStatus.php silently stops or releases every customer on it, with no audit entry.
- Customers.php refuses to delete a customer with credit history. This is new behaviour, but appropriate.

**B**
- `Z_ChangeCustomerCode.php` is not updated and there are no foreign keys, so changing a customer code orphans the whole credit history, reviews, letters, charges and write-offs. That directly hurts the audit requirement.
- CustomerAccount.php hides charge, waiver and write-off rows while the balance includes them. This is a base limitation that B now makes much more visible.
- `Z_CheckDebtorsControl.php` pagesecurity changes from its previous token to 8, so users who could run it before may lose access.
- Taking a customer off stop leaves all old orders held until each is released.
- CounterSales with `CheckCreditLimits=3` now behaves like "prohibit". This is documented and defensible.

## 6. What a maintainer would have to fix before merging

**A (most serious first)**
1. Make reminders and charges reachable in the portal: link them from the `index.php` customer menu, or add them to CustomerInquiry.php.
2. Set `nextreviewdate` for existing customers in 44.php (BR-40/AC-11).
3. Re-check credit when an existing order's lines are changed directly in SelectOrderItems/IntoCart, or compare against `releasedvalue` at dispatch. Evaluate SpecialOrder.php orders.
4. Fold `CreditHoldOverLimit` into `CheckCreditLimits` (add a "hold" value) instead of a parallel setting. Reuse `GetCreditAvailable`.
5. Remove the edit to `Z_CheckDebtorsControl.php` and either fix that script or replace it with the new reconciliation page. Don't ship two.
6. Advance `lastrecurrence` (or ask) when skipping recurring orders for stopped customers.
7. Stop double-escaping already-escaped POST text into the log. Record email failures on the letter row.
8. Guard CreditStatus.php against changing the meaning of a code that is in use, or at least log it.
9. Produce letters as PDF (Dompdf) like the rest of webERP.

**B (most serious first)**
1. Update `Z_ChangeCustomerCode.php` for all new tables (and add foreign keys to `debtorsmaster` / `debtortrans`, as A does). Block or handle customer deletion when history exists.
2. Render the type 13/14/45/46/47 rows in CustomerAccount.php (BR-21).
3. Fix `CreditControlConfig()` to read GL account codes as text (leading-zero chart codes).
4. Grant tokens 21/22 to the roles holding token 15 rather than hard-coded role 8.
5. Decide the go-live default for `CheckCreditLimits=3` with the business. At minimum, the upgrade notes and the manual must tell the administrator to switch it on, or AC-05 fails.
6. Offer a "release all stop-held orders" option when a customer is taken off stop.
7. Send the dunning email after commit.
8. Keep dispute rows with a resolution instead of deleting them.
9. Give the write-off approval its own entry point so the FD does not need token 21.
10. Restore the original pagesecurity of `Z_CheckDebtorsControl.php`, or document the change.
11. Reconsider EDI orders for stopped customers: BR-06/AC-02 read as "refuse", while B accepts and holds them.

## 7. Other observations

- Both independently got the multi-currency write-off and the debtors-control formula right, which is the hardest part of the brief.
- A's pre-commit GL balance check, "validate the whole import file first", and the approval page that prevents self-approval are good habits.
- B's "left out of this run, because…" audit entries, the "not due and why" list, the import test-run mode, the CreditStatus meaning guard and the batch PDF of letters to post are thoughtful features for the people who will use this.
- A's high-risk review period directly answers BR-02's "shorter for higher-risk customers". B leaves that to manual date choice.
- A's watch-order record is the more accurate reading of BR-08.
- B's daily-prorated interest is more defensible to auditors than A's flat 1/12 of the annual rate.

## 8. Verdict

**I would rather merge B — barely.** B fits webERP better:
- it reuses `CheckCreditLimits`, `GetCreditAvailable` and `EnsureGLEntriesBalance`;
- it produces PDF letters;
- it repairs the broken debtors-control check instead of duplicating it;
- it keeps the business logic in one library;
- it covers more order routes, including direct line edits, SpecialOrder and CounterSales.

A is better on data integrity: foreign keys, customer-code change, GL balance check before commit, text-safe GL codes, charges shown on the account screen, and accurate watch history. But A's portal display is effectively unreachable, its go-live review dates need a manual step, and it invents parallel settings and pages. B's main gaps (customer-code change, account screen, default for over-limit holds) are each a small, well-understood fix.

- **A: 6.5 / 10**
- **B: 7 / 10**
