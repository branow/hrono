## T8 audit: customer-adjustments-hrono-2 (read only, no files changed)

Workspace: /Users/orest/hrono-weberp/runs/t8-customer-adjustments-hrono-2. The new posting code is in includes/CustomerAdjustmentFunctions.php (abbreviated CAF below). The two new pages are CustomerAdjustment.php and CustomerSmallBalanceWriteOff.php (abbreviated SBWO below).

**Result: 15 met, 5 partly, 2 missed.**

| # | Verdict | Evidence |
|---|---|---|
| 1 | met | CAF:15 `define('CUSTOMER_ADJUSTMENT_TYPE', 15)`, CAF:78 `GetNextTransNo(CUSTOMER_ADJUSTMENT_TYPE)`. No new systypes row in install; 44.php:11 `NewSysType(15,…)` is a harmless no-op. |
| 2 | met | CustomerAdjustment.php:88 `DB_Txn_Begin()`, then commit. All writes use `DB_query(...,true)`, which rolls back and exits on error (ConnectDB_mysqli.php:83-93). The write-off path calls `DB_Txn_Rollback()` when it finds no open invoice. |
| 3 | met | CAF:79 `$PeriodNo = GetPeriod($TransDate)`. The same `$PeriodNo` goes into `prd` and both `periodno` values. |
| 4 | partly | `rate`, signed `ovamount`, `reference`, `invtext` are set and `balance` is not written. But a plain adjustment calls `PostCustomerAdjustment(...$AdjustmentNo)` with the defaults `$BranchCode = '', $SalesPerson = ''` (CAF:73). So `branchcode` and `salesperson` are blank, and only write-offs copy the invoice's values. |
| 5 | met | CustomerAdjustment.php:70 `filter_number_format`, :75 `round($Amount, $Customer['decimalplaces'])`, `locale_number_format` for display. |
| 6 | met | CAF:115 `if ($_SESSION['CompanyRecord']['gllink_debtors'] == 1)`. |
| 7 | met | CAF:116 `$LocalAmount = round($Amount / $Rate, …)`. Debtors control gets `+$LocalAmount` and the chosen account gets `-$LocalAmount`, both type 15 with the same `typeno`, so they net to exactly 0. Signs are right: an increase debits debtors control. |
| 8 | met | CAF `CheckAdjustmentGLAccount` checks `glaccountusers … canupd = 1` and rejects `debtorsact`. The account list in CustomerAdjustment.php:187 uses the same join. |
| 9 | **missed** | Neither file has a tag field or an `InsertGLTags` call. CustomerReceipt.php:347 has one. |
| 10 | met | Nothing writes `gltotals` or `chartdetails`. |
| 11 | met | CAF:179 inserts the `custallocns` row. CAF:190 sets `alloc = -WriteOff, settled = 1` on the adjustment and CAF:197 sets `alloc = alloc + WriteOff, settled = 1` on the invoice, all in the caller's transaction. |
| 12 | partly | CAF:177 posts the write-off at `$Invoice['rate']`, so `diffonexch` is never recorded and nothing goes to `salesexchangediffact`. The design is consistent: debtors control falls by the invoice's carrying value and the reconciliation holds. It is still not the today's-rate posting with an exchange difference that the item asks for. |
| 13 | met | CustomerAllocations.php:481 `OR (debtortrans.type=15 AND debtortrans.ovamount<0)`. Lines 538 and 578 add `type=15`, with the existing `ovamount<0` filter. The debits list (around line 272) is type-agnostic, so positive adjustments appear there. |
| 14 | partly | It goes through the same `WriteOffInvoiceBalance`, one transaction per invoice, and locks with `FOR UPDATE`. But SBWO:82 `balance / rate < Threshold` compares every currency in home currency at the invoice's historical rate. It does not compare in the customer's currency or skip other currencies. The result message gives only a count and a total. |
| 15 | met | Z_CheckDebtorsControl.php adds an `SUM(...)/rate … type=15` column and includes it in `$CalcMovement`. |
| 16 | met | DebtorsAtPeriodEnd.php:26 `OR debtortrans.type=15`. |
| 17 | partly | The CustomerInquiry.php type-15 row has the allocation link and a rights-checked GL link. CustWhereAlloc.php:113 `$TitleInfo = $TransTypeOptions[$_POST['TransType']];` uses a variable that is defined nowhere (see other mistake 1). |
| 18 | met | PrintCustStatements and AgedDebtors join systypes and do not filter by type. Statements were checked and need no change. |
| 19 | partly | Both pages are registered at a new token 21 (scripts.sql, 44.php:23-24), not at CustomerReceipt.php's token 3. Only roles 6 and 8 get it. Menu rows are added under AR Transactions for all 9 roles. There are no hardcoded token checks. |
| 20 | met | sql/updates/44.php uses `NewSecurityToken`, `NewScript` and `NewMenuItem`, plus an `INSERT IGNORE` into securitygroups. Install data (securitytokens, securitygroups, scripts, menuitems) and demo.sql carry the same rows; demo.sql was checked line by line. |
| 21 | met | The sections are in doc/Manual/ManualARTransactions.html (anchors `CustomerAdjustments` and `CustomerSmallBalanceWriteOff`, inside Help Begin/End blocks). That file is the AR Transactions chapter where allocations live, not ManualAccountsReceivable.html. ManualOutline.php has the entries, and `$ViewTopic='ARTransactions'` and `$BookMark` match. |
| 22 | **missed** | The forms are hand-written `<select name="GLAccount">` and `<input type="date">`. `FieldToSelectOneGLAccount` and `FieldToSelectOneDate` exist (UIGeneralFunctions.php:149, 173) but are not used. |

## GL arithmetic
- **Increase or decrease:** `ovamount = ±Amount`. Debtors control gets `+Amount/rate` and the chosen account gets the opposite. Both values come from one rounded `$LocalAmount`, so the two lines always net to zero.
- **Edge case:** if `$LocalAmount` rounds to 0, the debtortrans row is still written with no GL lines. That leaves a tiny reconciliation drift, which is negligible.
- **Write-off:** at the invoice's rate there is no exchange difference by construction. `alloc` and `settled` follow CustomerAllocations' conventions (negative `alloc` on the credit, positive on the invoice).
- **Small balances:** each invoice is posted by the same routine, so it inherits the same arithmetic.

## Other verified mistakes
1. **Wrong behaviour, a regression in an existing page.** CustWhereAlloc.php:113 reads the undefined `$TransTypeOptions` for types 11, 12 and 15. This replaced a working ternary. The "Allocations made against …" title is now blank for every receipt and credit note, and PHP raises an undefined-variable warning plus a null-offset warning.
2. **Wrong behaviour.** Plain adjustments have `salesperson=''` and `branchcode=''`. CustomerAccount.php:114 and :186, CustWhereAlloc and CustomerAllocations filter `debtortrans.salesperson = SalesmanLogin`, so salesman users never see these rows. NOTES.md admits this.
3. **Security, minor.** Neither new page applies the SalesmanLogin restriction. Any role granted token 21 can adjust any customer. Writing off another customer's invoice by id is correctly blocked by `AND debtorno = …` in the lock query.
4. **Wrong behaviour, minor.** SBWO's WriteOff button re-runs the query with whatever is in the editable form fields at that moment. Changing the threshold or customer range after previewing writes off a set the user never saw.
5. **Wrong behaviour, minor.** CustomerAdjustment.php's GL select is `required` even when `gllink_debtors` is off, so the user must pick an account that is then ignored.
6. **Wrong behaviour, edge case.** CAF `mb_substr($Reason, 0, 50)` cuts an already-escaped string. A cut right after a backslash produces an SQL error and a rollback.
7. **Convention.** The CustWhereAlloc message for a negative type-15 row with no allocations says "This transaction was a receipt of funds…", which is misleading.
8. **Convention.** NOTES.md, a 68-line file of implementation notes, is added at the repo root. New strings are not added to `locale/`.
9. **Convention, latent.** `EnsureGLEntriesBalance` rolls back without exiting, and the caller then commits. It cannot trigger here because the two lines always net to zero.
10. **Token change.** The new token 21 means the credit controller's role has no access after install or upgrade until someone grants it by hand.

No install/upgrade mismatches found. The only description difference is in scripts: `NewScript` writes an empty description where the install data has text, which is normal for that helper.
