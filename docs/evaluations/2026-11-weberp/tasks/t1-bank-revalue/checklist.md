# T1 checklist (task: PR #845; reference change 842d073..2d8fa77)

**The reference is incomplete.** PR #845 moved the revaluation out of
`Currencies.php` into `includes/SQL_CommonFunctions.php` as
`AdjustBankAccountsDueToCurrencyExchangeRate($SelectedCurrency, $OldRate, $NewRate)`
and made `includes/LoginFunctions.php` include that file, but the login
rate update never calls it: the only call site is `Currencies.php:152`, at
2d8fa77 and still on master (checked with `git grep` on 2026-11-05). So the
automatic update still does not revalue bank accounts after the merge. Grade
against the task and this checklist, not against the reference diff; a run
that does call the revaluation from the daily update is better than the
reference on item 1.

A reviewer marks each item met / partly / missed.

1. Finds where the automatic daily update runs: `includes/LoginFunctions.php`
   (`userLogin`, the `UpdateCurrencyRatesDaily` block), and revalues the bank
   accounts on BOTH rate paths there (the ECB feed and the other/DXR feed).
2. Finds the existing revaluation logic in `Currencies.php` (a manual rate
   change posts a bank-account exchange adjustment) and reuses it (one shared
   function called from both places) rather than writing a second, different
   copy.
3. Revalues every bank account in the currency (`bankaccounts.currcode`),
   from the account's GL balance (`gltotals` up to the current period) and
   the old and new rates.
4. Posts a balanced pair of `gltrans` rows (type 36): the bank account and
   the exchange difference account
   `$_SESSION['CompanyRecord']['exchangediffact']`, with a number from
   `GetNextTransNo(36)` and the period from `GetPeriod` (the reference does
   this with `DB_query(..., true)`, no explicit transaction).
5. Reads the old rate before the `UPDATE currencies` and posts only when the
   rate changed (reference: `if ($OldRate != $NewRate)`); a feed that
   returned no rate must not produce a bogus revaluation.
6. The code it calls at login is available there (no undefined function on
   the login path). Note: the reference's `includes/session.php` change is an
   unrelated HTTPS error page and is not part of this checklist.
7. Does not break the manual path in `Currencies.php` (same posting as
   before).
