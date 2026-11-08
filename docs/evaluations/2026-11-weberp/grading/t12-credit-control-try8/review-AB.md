# Blind review: t12 credit control, implementation A vs implementation B

Reviewer stance: a webERP maintainer who would have to merge and maintain this. I read the BRD, both diffs and the full trees, and compared them with the base tree. I checked the claims below in the code, not in either NOTES.md.

Both implementations take the same basic approach. Credit status is the existing `debtorsmaster.holdreason` -> `holdreasons.dissallowinvoices`, with 1 = stop and 2 = watch, which matches how `SelectOrderItems.php` and `CounterSales.php` already read it. Both add a `creditheld` flag on `salesorders` (0 none, 1 held, 2 released), new `debtortrans` types for charges, waivers and write-offs, security tokens 21 and 22, a dunning table set and a review table. They also gate the same order routes (DeliveryDetails, EDI, recurring orders, API, ConfirmDispatch_Invoice). So the differences are in depth, correctness and fit, not in architecture.

---

## 1. Completeness

| Area | A | B |
|---|---|---|
| Credit reviews, immutable history, limit changed by the review (BR-01..04) | Yes. `CreditReview.php`, `creditreviews` keeps the old and new limit and hold reason. | Yes. `CreditControl.php` hub page. |
| Next review date for new customers (BR-02) | Customers.php, Z_ImportDebtors, API InsertCustomer | Same, plus an optional review period per customer (`reviewmonths`) for higher-risk accounts |
| Stop and watch with a reason, who and when (BR-05) | Only through Credit Review; Customers.php no longer edits limit or status | Through CreditControl.php. Controllers can still change limit and status in Customers.php, and that path records no reason, only "reason code N (customer maintenance)". |
| Block every order route (BR-06) | Sales office and web shop (DeliveryDetails), EDI, recurring, API header and API invoice, dispatch | Same routes. B also fixes the base `if ($CreateOrder = true)` bug in EDI, which switches on validation that was already there. |
| Watch customers still supplied in the web shop (BR-08) | **No.** The portal path in `SelectOrderItems.php` (`dissallowinvoices == 0`) is unchanged, so a watched customer is turned away and told "your account has been put on hold". | Yes. `!= 1`, with a customer-facing message for stop. |
| Over-limit orders held and released (BR-10) | New option 3 on the existing `CheckCreditLimits` setting, release page `CreditHeldOrders.php` | New `CCHoldOverLimitOrders` setting, release from the report |
| Web shop message for a customer on stop (BR-11) | Base message (shows the internal reason text) | `CCCustomerStopMessage()`, a plain message |
| Dunning stages, wording, preview and exclusion, re-check at send, gap rule (BR-12..16) | Yes. Wording per language (`dunningtexts`), the full letter text stored in `dunninglog` | Yes. One wording, letter text not stored |
| Emailing letters (BR-13) | Works with both mail() and SMTP | **Broken under SMTP** (see section 2) |
| Disputed items not chased or charged (BR-18) | Yes | Yes |
| Interest and fee, exemptions, preview, no double charge, GL accounts, waiver (BR-19..24) | Yes. Separate types 51 and 52, so a statement reads "Late Payment Interest" and "Late Payment Fee". | Yes. One type 51 "Interest and Fee Charge" for both, so a statement (typename + transno only) cannot tell them apart. |
| Write-off, threshold approval, auto-stop, report (BR-25..29) | Yes. Requester cannot approve their own request. Report on the same page. | Yes, with a separate report page. No separation of duties. |
| Credit control report: rep and currency filter, home totals (BR-30) | Yes, with a "due within N days" look-ahead | Yes, and lists held orders and watch orders as well |
| Aged debtors shows status, limit and last stage (BR-31) | Yes, as columns (screen and PDF) | Yes, as a small line under the name |
| Audit history per customer (BR-32) | `creditlog` + `CreditHistory.php` | `creditcontrollog` on CreditControl.php |
| Reps see only their own customers (BR-33/34) | Yes | Yes |
| Portal: reminders and charges, own account only (BR-35/36) | Yes. Adds `LoginCustomerID` and forces CustomerInquiry and CustomerAccount to the logged-in customer. This closes the existing hole where a portal user could pass `?CustomerID=` for another customer. | Partly. A new `CustomerCreditPortal.php` with a link from index.php, but it reads `$_SESSION['CustomerID']`, which CustomerInquiry.php lets a portal user overwrite. The cross-customer hole stays open and now also covers reminders and charges. |
| Ledger agreement and finding differences (BR-37/38) | Extends the existing `Z_CheckDebtorsControl.php` (and fixes its `$DiffTotal` ordering bug), lists unmatched entries, updates DebtorsAtPeriodEnd and CustomerBalancesMovement for the new types | A new `DebtorsReconciliation.php`. Does not update CustomerBalancesMovement, so type 51 charges show as "credits". |
| Go-live: existing customers and the stop list (BR-39/40) | All next review dates +12 months. A CSV importer (`Z_ImportCreditStatus.php`) with a dry run, for the spreadsheet stop list. | Next review dates spread over the period (CRC32), which is thoughtful. No import: the stop list has to be keyed in by hand. |
| Staff guide (BR-42/43) | A new manual chapter `ManualCreditControl.html` + TOC entry in ManualOutline.php, with a go-live section and a note for sales staff | A section inside ManualAccountsReceivable.html with Help markers, including a sales-staff paragraph |

Overall A covers more of what the feature needs in webERP: the go-live import, multilingual letters, stored letter text, separate charge types on statements, existing reports made aware of the new types, and the portal isolation. B has three useful extras that A lacks: per-customer review periods, hold reasons seeded on a fresh install, and an API invoice-time limit check.

## 2. Correctness

**Ledger and currency**
- A: charges and waivers post debtors control against the chosen income account. Write-offs and waivers are posted at the current rate and allocated through `CreditAllocate()`, which copies `CustomerAllocations.php` exactly. That covers the diff formula, the `diffonexch` on both sides, and the `salesexchangediffact` versus `debtorsact` posting with the same signs as base. That is the standard webERP model, and it meets "including any currency difference" (BR-27). A write-off is refused if the net balance (after unallocated receipts and credits) or the open items do not cover it.
- B: the write-off is valued at the original rates of the items it clears. B then **overwrites the write-off row's `rate` with the average rate** so that `ovamount/rate` matches the GL. The ledger agrees, but the currency difference is buried in bad debt rather than posted as an exchange difference, and a stored rate that was never a real rate is confusing for later reports. `CCWriteOffCeiling()` ignores unallocated receipts and credits, so a write-off can push the customer into credit. Waivers are posted at the charge's own rate. That is consistent, but the same pattern (no `diffonexch`) applies.
- A's charge rows have no `salesperson` or branch, so they drop out of the salesman-filtered statements in PrintCustStatements. B sets both from the first branch.
- B reads GL account settings straight from `config`, because GetConfig.php turns numeric-looking values into floats and would strip leading zeros. That is a real catch A does not make.

**Sequences and transactions**: both use `GetNextTransNo` per new type and wrap postings in `DB_Txn_Begin/Commit`. B's `EnsureGLEntriesBalance` call is a nice touch.

**Email**: B builds `From` as `coyname<email>` and passes a numerically indexed `$Emails` array. With `SmtpSetting=1`, `SendEmailBySmtp` calls `setFrom("Name<addr>")` and `addAddress(0, 'addr')` on `new PHPMailer(true)`. Both fail validation in the vendored PHPMailer and **throw uncaught exceptions**, so the reminder run dies on the first customer with an email address. It only works with PHP `mail()`. A passes a plain address and an address-keyed array, so it is correct in both modes.

**Hold enforcement**: both gate the same routes. A's check for an edited existing order passes value 0, so an order raised above the limit while being edited is not re-held. B excludes the order from available credit and checks the new value. A's API hold at header time is based on value 0, so it only catches customers already over the limit. B's API checks again at invoice time with the real order value. Against that, A is the only one whose stop message is not shown for watch, and A's web shop wrongly blocks watched customers (section 1).

**Dunning logic**: both send the highest stage reached, so a customer first chased at 70 days gets the final notice at once. A's "already sent this episode" rule (letters since the oldest item fell due) handles new episodes correctly. B's rule (skip if stage <= last stage and the last letter is under 90 days old) blocks the first letter of a fresh overdue episode for up to 90 days after an earlier final notice.

**Install versus upgrade**:
- A: a fresh install seeds no hold reasons, so stop and watch do not exist until someone creates them. A fresh install also keeps `CheckCreditLimits=1` (warn), while the upgrade forces 3 (hold), so the two drift apart. `Z_ChangeCustomerCode.php` copies `debtorsmaster` by an explicit column list and A did not add its three new columns, so a code change loses the next review date and the exemptions. `UpdateDBNo` is not guarded by the error count.
- B: seeds 90/91/92 hold reasons in both install and upgrade, guards `UpdateDBNo`, and updates Z_ChangeCustomerCode properly. Both add the demo data correctly (demo.sql is standalone).

**Other bugs**:
- A, `CreditHistory.php`: `$SeesEverything = !$IsPortalUser and (...)`. `=` binds tighter than `and`, so every staff user, reps included, sees the full audit log and the waiver reasons for the customers they can see.
- A, `CreditStatus.php`: leaves `if (true) { ... } else { ... }` dead branches.
- B: deletes a dunning stage through a GET link.
- B, CreditCharges: the waive buttons sit inside the same form as "Confirm and post", so pressing Enter in a waiver reason field submits the post button. The confirm() dialog still guards it.

## 3. Fit with webERP

- **Settings**: A extends the existing `CheckCreditLimits` setting (SystemParameters, SelectOrderItems, the IntoCart include, Contracts, CounterSales) and the existing `CreditStatus.php` hold-reason editor (watch becomes a selectable kind). That is the project's own vocabulary. B adds a parallel `CCHoldOverLimitOrders` that ignores `CheckCreditLimits`, so there are now two settings for one concept.
- **Reports**: A reuses `Z_CheckDebtorsControl.php` and makes DebtorsAtPeriodEnd and CustomerBalancesMovement aware of the new types. B writes a new reconciliation page and leaves CustomerBalancesMovement misclassifying its charges.
- **Security**: A puts setup at token 10, which the Accountant role (Finance) already has, and gives token 21 to the Accountant and Admin roles. B puts setup at 15 (sysadmin only) and gives token 21 to Admin only. A's choice matches who the BRD says configures it. B's menu puts "Credit Control Setup" under system / Reports, which is an odd section.
- **Manual**: A follows the one-file-per-ViewTopic pattern that `ManualContents.php` loads (`Manual<Topic>.html` + ManualOutline TOC). B appends to the AR manual with Help markers. Both are acceptable. A's chapter is more complete.
- **Pages and forms**: both use the standard header and footer, FormID, `fieldset/field`, `prnMsg`, `locale_number_format` and `ConvertSQLDate`. Neither produces a PDF for posted letters. Both print HTML text, which falls short of how webERP does statements.
- **Upgrade helpers**: both use `CreateTable/AddColumn/NewSysType/NewSecurityToken/NewScript/NewMenuItem/NewConfigValue/InsertRecord` correctly.

## 4. Structure and code quality

- A: one function library (`CreditControlFunctions.php`, constants for types and tokens) and one page per job (review, run, charges, write-offs, held orders, report, history, settings, stages, import). It is easy to find things, with a little repetition in the page scaffolding. The allocation and exchange code is the cleanest part. Weak spots are the `if (true)` leftovers, the precedence bug, and the plain `include` of a file that defines constants, which works but is fragile.
- B: one function library plus a per-customer hub page that does reviews, status, exemptions, notes and disputes. That is convenient for the user but a long page. `CCCreditAvailable()` duplicates `GetCreditAvailable()` with one extra condition instead of extending it. `CCSetting()`'s "ends in Act -> read from DB" rule is clever but hidden magic. The comments are good and explain why.
- Both are readable. A is a little more webERP-native. B is a little more self-contained.

## 5. Regressions

- A:
  - Existing upgraded sites with `CheckCreditLimits` 0 or 1 silently become "hold". That is right for this business but surprising for upstream.
  - Credit limit and status can no longer be edited in Customers.php by anyone, which changes the established workflow.
  - Hold reasons with -1 are normalised to 0.
  - Z_ChangeCustomerCode drops the new columns.
  - Watched customers are blocked in the portal (and shown "on hold") once watch reasons are used.
- B:
  - Over-limit holding is on by default on upgrade regardless of `CheckCreditLimits`.
  - The EDI `==` fix starts enforcing validations that were silently ignored. That is correct, but EDI orders that used to go through may now be rejected.
  - CustomerBalancesMovement shows charges as credits.
  - With SMTP, the new reminder run throws a fatal error. That is not a regression of old behaviour, but it is a crash.

## 6. What must be fixed before merging

**A** (most serious first):
1. `SelectOrderItems.php` portal branch: allow `dissallowinvoices != 1` and show a neutral message for stop. Today watched customers cannot order in the web shop and are told they are on hold.
2. Seed stop, watch and normal hold reasons in `install/sql/data` (and in the upgrade if none exist). Make the fresh-install `CheckCreditLimits` match the upgrade, or stop forcing 3 on upgrade and let the release notes and manual tell Finance to switch it.
3. Add `nextreviewdate, interestexempt, feeexempt` to the `debtorsmaster` copy in `Z_ChangeCustomerCode.php`.
4. Fix the `$SeesEverything` precedence (`&&` or parentheses).
5. Set `salesperson` (and the branch) on charge, waiver and write-off rows so rep-filtered statements include them.
6. Re-check the credit limit with the new value when an existing order is edited. Value the API hold on the lines, or check at invoice time as B does.
7. Remove the `if (true)` dead branches in CreditStatus.php. Wrap `UpdateDBNo` in the error check.
8. Consider starting at stage 1 rather than jumping to the final notice on the first contact.

**B** (most serious first):
1. Reminder email: pass a plain From address and an address-keyed `$To` array, so it does not throw under SMTP.
2. Portal isolation: take the customer from the login (as A does), and stop CustomerInquiry and CustomerAccount from accepting `?CustomerID=` from portal users. Otherwise BR-36 fails.
3. Write-off: limit it to the net balance (including unallocated credits). Post the exchange difference to `salesexchangediffact` the CustomerAllocations way instead of rewriting the write-off's rate.
4. Separate types (or at least separate type names) for interest and fees, so statements describe them (BR-21). Update CustomerBalancesMovement for the new types.
5. Customers.php: either remove limit and status editing, or require and record a reason. Today a controller can bypass the review trail.
6. Fold `CCHoldOverLimitOrders` into `CheckCreditLimits`. Reuse `GetCreditAvailable` (add an exclude parameter) instead of the copy.
7. Fix the dunning "already sent" rule for new overdue episodes.
8. Give Finance (not only sysadmin) access to the setup and stage pages. Make stage delete a POST.
9. Provide a way to load the go-live stop list (BR-40), even a simple CSV import.

## 7. Other observations

- Good in A: dry-run import, separation of duties on write-off approval, letters stored verbatim for the auditors, multilingual letter templates (BRD open question 9), and closing a real pre-existing portal data leak.
- Good in B: hold reasons seeded on install, review dates spread over the year, a per-customer review period, reuse of `custnotes` for collection-agency notes, a portal menu link on index.php, the EDI assignment bug found and fixed, and the leading-zero account code trap avoided.
- Neither offers a printable PDF letter for customers without email. Both rely on printing an HTML list.
- Neither handles BRD open question 12 (group credit limits), which is reasonable to leave.

## 8. Verdict

**I would rather merge A, somewhat.** A fits webERP better: it extends the existing credit-limit setting, hold-reason editor, debtors-control check and period reports instead of building parallel ones. Its money handling follows the CustomerAllocations exchange-difference model. It closes the portal cross-customer hole that BR-36 needs, and it ships a go-live import and fuller documentation. Its defects are real but small and local:
- the portal watch block
- no hold-reason seed on a fresh install
- Z_ChangeCustomerCode columns
- a precedence bug

B has good ideas and better install hygiene, but it carries two defects that break core requirements on typical installations: reminder emails crash under SMTP, and portal customers can see other customers' reminders and charges. It also has weaker write-off accounting (FX folded into bad debt, a rewritten rate, a ceiling that ignores credits) and a duplicated over-limit setting.

- **A: 7/10**
- **B: 5.5/10**
