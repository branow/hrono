# Probe ground truth (checked in webERP at 842d073, 2026-11-05)

Q1. Two different expressions.
- `CustomerAccount.php:146,157,169`: `DATE_ADD(DATE_ADD(debtortrans.trandate, INTERVAL 1 MONTH), INTERVAL (paymentterms.dayinfollowingmonth - DAYOFMONTH(debtortrans.trandate)) DAY)` (via the `interval()` helper).
- `CustomerInquiry.php:84,91,99` and `AgedDebtors.php:44,55,66`: `ADDDATE(last_day(debtortrans.trandate), paymentterms.dayinfollowingmonth)`.

Q2. `includes/LoginFunctions.php` (~lines 201-240), at login when the config `UpdateCurrencyRatesDaily` is set and older than today: fetches rates (`ExchangeRateFeed` ECB via `GetECBCurrencyRates`/`GetCurrencyRate` in `includes/MiscFunctions.php`, else another feed), runs `UPDATE currencies SET rate=...`, then sets `UpdateCurrencyRatesDaily` to CURRENT_DATE. It does NOT revalue foreign-currency bank accounts; only a manual rate change in `Currencies.php` (lines ~167-204) posts a bank-account exchange adjustment (to `exchangediffact`). This is the defect PR #845 fixed.

Q3. Not the same.
- Customer allocations (`CustomerAllocations.php:165`), `Z_AutoCustomerAllocations.php:198`, `BankReconciliation.php:73` and `Currencies.php:204`: `$_SESSION['CompanyRecord']['exchangediffact']`.
- Supplier allocations (`SupplierAllocations.php:205`): `$_SESSION['CompanyRecord']['purchasesexchangediffact']`.
- Both are columns of the `companies` table, set in `CompanyPreferences.php`.

Scoring: right = names the correct files/expressions and the difference; partial = the gist without the specific difference; wrong/don't know otherwise.
