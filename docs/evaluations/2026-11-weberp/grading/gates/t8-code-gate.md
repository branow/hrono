## T8 audit: customer balance adjustments (code-gate run)

Workspace: /Users/orest/hrono-weberp/runs/t8-customer-adjustments-code-gate. All file:line references are to the staged new files, unless marked as base code.

**Counts: 13 met, 7 partly, 2 missed.**

| # | Verdict | Evidence |
|---|---|---|
| 1 | met | `define('CUSTOMER_ADJUSTMENT_TYPE', 15)` and `GetNextTransNo(CUSTOMER_ADJUSTMENT_TYPE)` (includes/CustomerAdjustmentFunctions.php:13,59). No new systype, no type 11. |
| 2 | met | `DB_Txn_Begin()` / `DB_Txn_Commit()` in both pages. Every insert/update uses `DB_query($SQL,$ErrMsg,'',true)`, which rolls back and exits. Write-off errors call `DB_Txn_Rollback()`. |
| 3 | met | `$PeriodNo = GetPeriod($TranDate)` is used for both `debtortrans.prd` and `gltrans.periodno`. |
| 4 | partly | `rate`, signed `ovamount` and `reference`/`invtext` are set, and the generated `balance` column is never written. But a manual adjustment is posted with `PostCustomerAdjustment(..., $Customer['rate'], '', $_SESSION['SalesmanLogin'])` (CustomerAdjustment.php ~110): branchcode is empty and salesperson is the login, not the branch's salesman. This copies CustomerReceipt.php:454-466. A write-off does take the invoice's branch and salesperson. |
| 5 | partly | Manual amount: `filter_number_format` then `round($Amount, $DecimalPlaces)`, shown with `locale_number_format`. The write-off amount `$Balance = $Invoice['total'] - $Invoice['alloc']` (functions:175) is never rounded before it goes into ovamount, custallocns and GL. |
| 6 | met | `if ($_SESSION['CompanyRecord']['gllink_debtors'] == 1)` (functions:97) |
| 7 | met | Debtors control gets `$LocalAmount = $Amount / $Rate`, the chosen account gets `-$LocalAmount`, both type 15 with the same typeno, then `EnsureGLEntriesBalance` runs. Signs are right: an increase debits control and credits the chosen account; a decrease does the reverse. The lines net to exactly zero (not rounded, same as CustomerReceipt). |
| 8 | met | `glaccountusers ... AND glaccountusers.canupd = 1` and `if ($GLAccount == $_SESSION['CompanyRecord']['debtorsact'])` (functions:29-44). This is checked again on POST. Bank accounts are refused too. |
| 9 | missed | No tag field and no `InsertGLTags` anywhere in the diff. |
| 10 | met | No `gltotals` or `chartdetails` writes. The gltrans triggers exist (sql/updates/17.php:52,60). |
| 11 | met | One custallocns row, invoice `alloc = alloc + $Balance, settled = 1`, adjustment `alloc = -$Balance, settled = 1`, all in the caller's transaction (functions:191-214). |
| 12 | partly | The difference is avoided by design, not recorded: the write-off posts at `$Invoice['rate']` ("posted at the exchange rate of the invoice so there is no exchange difference"). No `diffonexch` is set and nothing goes to `salesexchangediffact`. A write-off dated today carries a historical rate, so any currency movement lands in the bad-debt account. |
| 13 | met | Line 481 has `OR (debtortrans.type=15 AND debtortrans.ovamount<0)`. Lines 538 and 578 add `type=15` inside the existing `ovamount<0` clause. The debit list (base lines ~255-265) has no type filter, so a positive adjustment appears there. |
| 14 | partly | Uses the same `WriteOffCustomerInvoice` per invoice, lists before posting and reports count and total. But the threshold is in home currency, `debtortrans.balance / debtortrans.rate < '$Threshold'`, at each invoice's historical rate. Other currencies are converted, not compared in the customer's currency. No SalesmanLogin filter. |
| 15 | met | Z_CheckDebtorsControl.php:104 `AND (type=10 OR type=11 OR type=15)` |
| 16 | met | DebtorsAtPeriodEnd.php:26 `(debtortrans.type=11 OR debtortrans.type=12 OR debtortrans.type=15)` |
| 17 | partly | CustomerInquiry.php is unchanged. Its `else` branch (base :620-669) shows a GL link to users with GL rights but never an allocation link. A type-15 branch was added to CustomerAccount.php instead, with an allocation link but no GL link. CustWhereAlloc handles 15 correctly. |
| 18 | met | PrintCustStatements uses `__($MyRow['typename'])` with no type filter, and AgedDebtors has no type filter. |
| 19 | partly | Registered in scripts and menu, and the SelectCustomer link is gated by PageSecurityArray (not hardcoded). But it uses a new token 21, `('CustomerAdjustment.php',21,...)`, not CustomerReceipt's token 3 (scripts.sql). Menu items exist only for role 8, not for roles 3, 5 and 6, which hold token 3. |
| 20 | met | sql/updates/44.php uses existing helpers with the right signatures: `NewSysType`, `NewSecurityToken`, `NewScript`, `InsertRecord` (UpgradeDB_mysql.php:34,55,72,624). Install scripts, securitytokens, securitygroups and menuitems match, and demo.sql has the same rows. Only difference: `NewScript` leaves the description empty. |
| 21 | partly | The section is in ManualARTransactions.html, not ManualAccountsReceivable.html, with `$ViewTopic='ARTransactions'` and `$BookMark` set. The ManualOutline entry sits between "allocating to invoices" and "Differences on exchange", but the section is at the end of the file. `$BookMark='CustomerSmallBalanceWriteOff'` has no matching anchor. |
| 22 | missed | Forms are hand-written (`<input type="date" ...>`, a hand-built GL `<select>`), although `FieldToSelectOneGLAccount` and `FieldToSelectOneDate` exist (UIGeneralFunctions.php:149,173). |

## Other mistakes (all verified)

1. **Write-off of another customer's invoice (wrong behaviour).** `WriteOffCustomerInvoice` loads the invoice by id only (functions:164) and never checks the customer. The page checks `debtorno` only when it renders the confirm form. Posting `ConfirmWriteOff` with any `WriteOffID` writes off another customer's invoice, and the success message shows the current customer's currency.
2. **SalesmanLogin is ignored (wrong behaviour).**
   - CustomerAdjustment's open-invoice list, the write-off and the small-balance list have no `salesperson` filter, while CustomerAccount and CustomerAllocations filter on it.
   - A manual adjustment posted by a normal user gets `salesperson=''`, so salesman logins never see it or allocate it.
3. **Access is narrower than the receivables pages (convention).** Token 21 is granted to role 8 only, with menu items for role 8 only. Giving the token to another role later shows no menu entry.
4. **The account page and the inquiry page differ (wrong behaviour).** CustomerAccount has no GL link for adjustments; CustomerInquiry has no allocation link (see item 17).
5. **Small-balance threshold (wrong behaviour versus the checklist).** Foreign invoices are converted at their historical rate, and the converted total shown is not what the GL posts in today's terms.
6. **Small issues (convention).**
   - Write-off amounts are not rounded (`$Balance`), so float noise can reach ovamount, custallocns.amt and GL.
   - GL amounts are never rounded to home decimals (the same as CustomerReceipt).
   - 44.php's `NewScript` inserts an empty description, while the install data has a description.
   - `NewSysType(15)` is redundant but harmless.
7. **Manual (convention).** The outline order does not match the section position, and the small-balance bookmark anchor is missing.
8. **CustWhereAlloc (convention, minor).** For a negative type 15 with no allocations it shows the receipt-specific message, "This transaction was a receipt of funds...".

**The modified existing pages still do what they did before:**
- CustomerAllocations, Z_AutoCustomerAllocations, Z_CheckDebtorsControl and DebtorsAtPeriodEnd only add type 15.
- CustomerBalancesMovement only moves positive type 15 from credits to debits. Before, a positive adjustment would have been miscounted as a credit.
- PDFCustTransListing: the added `break` changes nothing.
- CustWhereAlloc: the refactor is equivalent, and an unknown type now defaults to 10.
- SelectCustomer: the added link is gated by token.

No PHP syntax or column-name errors were found. There is no double posting and no write to `balance`.