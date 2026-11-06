# T8 checklist (task: customer balance adjustments, BRD in task/brd.md)

Made up at base 4cb937f79e8b, not from a commit: webERP defines type 15
"Journal - Debtors" (install/sql/data/systypes.sql,
includes/DatabaseTranslations.php:29) but no page creates it. The BRD is
short on purpose; every item below follows from the code or is stated in
the BRD. There is no reference diff.

A reviewer marks each item met / partly / missed, and lists every other
mistake found in the diff.

The transaction:

1. Uses the existing type 15 (no new systypes row, no fake credit note of
   type 11) and `GetNextTransNo(15)`.
2. All writes in one `DB_Txn_Begin` / `DB_Txn_Commit`, with the error
   path rolling back (as CustomerReceipt.php, GLJournal.php).
3. Period from `GetPeriod($Date)`, which moves a date before
   `ProhibitPostingsBefore` into the first open period; the `debtortrans`
   `prd` and the `gltrans` `periodno` are the same.
4. `debtortrans` row complete: `rate` (the customer currency's rate),
   signed `ovamount` (positive raises the balance, negative lowers it),
   `branchcode`, `salesperson` (from the branch; CustomerAllocations.php
   and others filter on it for `SalesmanLogin`), `reference`, `invtext`;
   never writes the generated `balance` column.
5. Amounts parsed with `filter_number_format` and rounded to the customer
   currency's `decimalplaces`; shown with `locale_number_format`.

The ledger:

6. GL only when `$_SESSION['CompanyRecord']['gllink_debtors'] == 1`.
7. Two `gltrans` lines that net to zero: the debtors control account
   (`$_SESSION['CompanyRecord']['debtorsact']`) and the chosen account,
   both in home currency (amount / rate), type 15 and the same `typeno`.
8. The chosen account is limited to the user's GL accounts
   (`glaccountusers`, as GLJournal.php:510) and may not be the debtors
   control account (the rule of GLJournal.php:355).
9. GL tags can be given and are saved with `InsertGLTags` (gltags), as
   the other posting pages do.
10. Nothing writes `gltotals` or `chartdetails` by hand: the gltrans
    triggers (sql/updates/17.php) keep the totals.

Matching (allocations):

11. Writing off an invoice's remainder allocates the adjustment to it:
    a `custallocns` row, `alloc` and `settled` updated on both
    `debtortrans` rows, in the same transaction.
12. Exchange difference on that allocation: the invoice's rate differs
    from today's, so the home-currency difference is recorded
    (`diffonexch`) and posted to `salesexchangediffact` as
    CustomerAllocations.php:120-165 does. Missed if ignored.
13. CustomerAllocations.php lets a negative adjustment be allocated: its
    lists of allocatable credits are hard-coded `type=12 OR type=11`
    (lines 481, 538, 578) and must take type 15 (negative only). A
    positive adjustment appears among the debits to allocate.
14. The small-balance clean-up runs per invoice through the same posting
    (items 1-12), skips customers in other currencies correctly (amount
    compared in the customer's currency), and reports what it wrote off.

Reports and checks that hard-code types:

15. Z_CheckDebtorsControl.php (lines 104, 116 sum types 10/11 and 12
    only) includes type 15, so the reconciliation still agrees with the
    GL.
16. DebtorsAtPeriodEnd.php:26 (`diffonexch` for types 11/12) includes 15.
17. CustomerInquiry.php shows the adjustment with its GL link and
    allocation link (its type branches cover 10, 11, 12; the `else` shows
    nothing to a user without GL rights); CustWhereAlloc.php works for
    type 15.
18. Statements (PrintCustStatements.php) and aged debtors show it with
    its type name; a check is enough if nothing needs changing.

Access, install, manual:

19. Page registered in `scripts` at the receivables transaction token
    (the token CustomerReceipt.php has), in `menuitems` under
    receivables Transactions for the roles that have it; no hardcoded
    token checks (#761).
20. Upgrade `sql/updates/44.php` with the helpers and the install data
    (scripts.sql, menuitems.sql) the same.
21. Manual: doc/Manual/ManualAccountsReceivable.html section, its
    doc/Manual/ManualOutline.php entry, `$ViewTopic` / `$BookMark`.
22. Forms with includes/UIGeneralFunctions.php helpers where they exist
    (`FieldToSelectOneGLAccount`, `...Date`, `...Number`, `...Text`; #828).
