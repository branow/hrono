## T8 audit: hrono-1 (customer balance adjustments)

Workspace: /Users/orest/hrono-weberp/runs/t8-customer-adjustments-hrono-1. 21 files, +774/-40. Main code is in `includes/CustomerAdjustmentFunctions.php` (CAF), `CustomerAdjustment.php` (CA) and `CustomerWriteOffSmallBalances.php` (WO). I modified no files.

| # | Verdict | Evidence |
|---|---|---|
| 1 | met | CAF:8 `define('CUSTOMER_ADJUSTMENT_TYPE', 15)`, CAF:100 `GetNextTransNo(CUSTOMER_ADJUSTMENT_TYPE)`. No new systypes row; `NewSysType(15,…)` in 44.php does nothing when the row exists. |
| 2 | met | CA:103-109 `DB_Txn_Begin()` … `DB_Txn_Rollback()` on a 0 return. WO:74-90 wraps the whole batch in one transaction. Every insert passes `DB_query(...,'',true)`. |
| 3 | met | CAF:99 `GetPeriod(ConvertSQLDate($TranDate))`. The same `$PeriodNo` goes into `prd` (CAF:125) and `periodno` (CAF:172). |
| 4 | partly | Sets rate, signed ovamount, reference, invtext, and never writes `balance`. But a plain adjustment gets `$BranchCode = ''` (CAF:59), and `salesperson` is `$_SESSION['SalesmanLogin']` (CAF:133), not the branch's salesman. A write-off gets the invoice's rate (CAF:84), not the customer currency's rate. |
| 5 | met | CA:93 `filter_number_format`, CAF:90 `round($Amount, $Customer['decimalplaces'])`, `locale_number_format` on display. |
| 6 | met | CAF:154 `if ($_SESSION['CompanyRecord']['gllink_debtors'] == 1)`. |
| 7 | met | CAF:158-159: debtors control gets `+$FunctionalAmount`, the chosen account gets `-$FunctionalAmount`, with `$FunctionalAmount = $Amount / $Rate`. Signs are right for increase and decrease. The lines are exact negatives, so they net to zero. Type 15 and the same typeno. |
| 8 | partly | Debtors control is rejected (CAF:25). There is no `glaccountusers` join, either in the dropdown (CA:151-156, WO same) or in the check. |
| 9 | missed | No tag input and no `InsertGLTags`. |
| 10 | met | Only gltrans is inserted; nothing writes gltotals or chartdetails. |
| 11 | met | CAF:138-151: a custallocns row with `amt=-$Amount`, the adjustment row gets `alloc=$Amount, settled=1`, the invoice gets `alloc = alloc + -$Amount, settled=1`. All in the same transaction, with the invoice row locked (`FOR UPDATE`). |
| 12 | partly | No `diffonexch` and no `salesexchangediffact` posting. The difference is avoided rather than recorded: CAF:83 "the write off is made at the rate of the invoice so that no exchange difference arises". The ledger is internally consistent, but this is not the checklist's design. |
| 13 | met | CustomerAllocations.php:481 `(debtortrans.type=15 AND debtortrans.ovamount<0)`. Lines 538 and 578 add type 15 under their existing `ovamount<0` filter. The debit list (line ~270) has no type filter, so positive adjustments appear there. |
| 14 | partly | It runs per invoice through `PostCustomerAdjustment` and reports the count and total (WO:85-87). The comparison is wrong for the checklist: WO:62 `balance / debtortrans.rate < $Limit` compares a home-currency limit at each invoice's rate. It never compares in the customer's currency and never skips customers in other currencies. |
| 15 | met | Z_CheckDebtorsControl.php gets an Adjustments column, and `$CalcMovement` adds `totadjustments`. |
| 16 | met | DebtorsAtPeriodEnd.php:26 `OR debtortrans.type=15`. |
| 17 | met | CustomerInquiry's `else` branch already showed the GL link for type 15. It now adds an Allocation link for negative adjustments, and the branch without GL rights gets the same cell. CustWhereAlloc handles 15 at 93-103 and 158. |
| 18 | met | PrintCustStatements selects by `settled` and joins systypes for the name, so nothing hard-codes types. CustomerAccount.php gets a type 15 branch. |
| 19 | partly | Scripts and menu are registered under AR Transactions (seq 5/6) for all roles. But the token is a new 21, granted only to role 8 (`('CustomerAdjustment.php',21,…)`), not CustomerReceipt's token 3. No hardcoded token checks. |
| 20 | met | 44.php uses `NewSecurityToken`, `InsertRecord` (signature correct), `NewScript` and `NewMenuItem`. scripts, menuitems, securitytokens and securitygroups in install match, and demo.sql has the same rows. |
| 21 | partly | The section is in ManualARTransactions.html, with `$ViewTopic='ARTransactions'` and `$BookMark` matching its anchor. Nothing is in ManualAccountsReceivable.html, and ManualOutline.php has no entry. |
| 22 | missed | The forms are hand-written: a raw `<select name="GLAccount">` and `<input type="date">`. No `FieldToSelectOneGLAccount`, `...Date` or `...Number`. |

**Counts:** 14 met, 6 partly, 2 missed.

The `diffonexch` column in item 16 is always 0 for type 15, because no exchange difference is ever posted (item 12).

### Other verified mistakes

**Wrong behaviour**
1. **Adjustments are hidden from salesman logins.** Rows posted by a non-salesman user get `salesperson=''`. Allocations, statements and CustWhereAlloc filter on `debtortrans.salesperson`, so a salesman never sees them. The worst case is a write-off: the salesman sees the invoice settled but not the adjustment that settled it. (CustomerReceipt.php:467 uses the same precedent, but there it is the poster's own receipt.)
2. **Plain adjustments have an empty `branchcode`.** Branch-based views show a blank branch.
3. **The bulk write-off can post invoices the user never saw.** WO re-runs the query when "Write Off" is pressed (WO:44-63 runs for both Preview and WriteOff), so it posts whatever matches at that moment. Invoices raised after the preview get written off unseen.
4. **No salesman restriction on the new pages.** Neither page filters customers or invoices by `SalesmanLogin`. WO writes off every customer's invoices. Low risk only because token 21 is admin-only by default.
5. **A failed balance check can still report success.** `EnsureGLEntriesBalance` rolls back on a large imbalance, but `PostCustomerAdjustment` then returns `$TransNo` and the caller commits and prints success. This is latent: the two lines always balance.
6. **The ledger account is not restricted to the user's accounts.** Any account except bank and debtors control can be chosen (item 8), and there are no tags (item 9).

**Security (verified fine)**
- Writing off another customer's invoice by id is blocked: CAF:79 checks `$Invoice['debtorno'] != $DebtorNo`.
- Inputs are escaped by the global DB_escape_string/htmlspecialchars pass in includes/session.php:107-124.

**Convention**
7. **Upgrade and install captions differ.** 44.php calls `NewMenuItem(..., __('Customer Balance Adjustment'), ...)`, which stores the upgrader's translated caption, while install stores English.
8. **Two names for type 15.** CustWhereAlloc labels it "Customer Adjustment", while the systypes name "Journal - Debtors" shows everywhere else.
9. **Non-standard date handling.** HTML5 `type="date"` with a hand-written Y-m-d regex check (CA:75-76) instead of DefaultDateFormat and the UI helpers.
10. **NOTES.md committed at the repo root.** It says nothing was run or tested.
11. **A new token instead of the receivables token.** Users who post receipts cannot use the pages until an admin edits the roles. This also bears on item 19.

No regressions found in the existing pages it modified: CustomerBalancesMovement, Z_AutoCustomerAllocations, CustomerTransInquiry, CustomerAccount, CustomerInquiry. The install/sql/demo.sql change is real and matches the install data files.