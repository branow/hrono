# T5 checklist (task: early payment discount terms, request in task/brd.md)

Made-up task (no merged reference), base 4cb937f79e8b. The request is
written in business terms only. Places below were found at the base with
`git grep` (2026-11-06); a reviewer checks each against the diff and the
base code and marks it met / partly / missed, with the file and line.

Terms and data
1. Payment terms can carry a discount percent and discount days: schema
   change by an upgrade script `sql/updates/44.php` with webERP's helpers
   (`AddColumn`, `executeSQL`, `$_SESSION['Updates']['Errors']` gating),
   the same columns in `install/sql/tables/paymentterms.sql`, and the
   maintenance page `PaymentTerms.php` (add, edit, list, validation).
   Existing terms get 0 (no discount) and behave as before.
2. The API that reads/writes terms (`api/includes/api_paymentterms.php`)
   and fresh-install / demo positional INSERTs still match the table.

Customers
3. The discount date is computed from the invoice date and discount days
   for both term kinds (days-based and day-in-following-month), the same
   way everywhere it is shown (one shared function, e.g. beside
   `CalcDueDate` in `includes/DateFunctions.php`, not copies).
4. Invoice print `PrintCustTrans.php` (PDF and HTML paths) shows discount,
   last date and amount payable by then, in the invoice currency.
5. Statement `PrintCustStatements.php` shows it per open invoice still in
   its discount period, none for invoices past it or credits.
6. `CustomerAccount.php` and `CustomerInquiry.php` show which open invoices
   can still be paid with a discount and until when.
7. Receipt entry `CustomerReceipt.php`: a receipt dated on or before the
   discount date that pays an invoice less the discount gets the discount
   recognised so the invoice is fully settled (debtortrans `ovdiscount`
   and allocation), posted like existing receipt discounts (debit
   `pytdiscountact`, credit debtors control, functional currency through
   the batch exchange rate); after the date no automatic discount.
8. No double discount with the existing ones: the customer's
   `debtorsmaster.pymtdiscount` and the receipt type's `percentdiscount`
   (CustomerReceipt.php ~line 195).
9. Other receipt paths are consistent or explicitly left manual: the API
   receipt (`api/includes/api_debtortransactions.php`) and counter sales
   or returns (`CounterSales.php`, `CounterReturns.php`).

Suppliers
10. Supplier invoice entry (`SupplierInvoice.php`; credits `SupplierCredit.php`)
    records the discount and its date at entry, as it already stores
    `supptrans.duedate` there (supplier due dates are stored, customer ones
    computed).
11. Supplier inquiry / owed screens (`SupplierInquiry.php`,
    `SupplierTransInquiry.php`) show the discount and last date.
12. Supplier payment `Payments.php`: invoices inside the period are paid
    less the discount, the discount is posted (creditors control and the
    discount account, as the existing manual supplier discount) and the
    allocation settles the invoice; past it, paid in full.
13. Payment run `SuppPaymentRun.php`: includes invoices whose discount
    expires before the next run even if not due (today it selects
    `supptrans.duedate <= AmountsDueBy`), shows the discount saved, and
    the remittance (`PDFRemittanceAdvice.php`) shows discount taken.

Unchanged and cross-cutting
14. Aged debtors / aged creditors (`AgedDebtors.php`, `AgedSuppliers.php`)
    and overdue figures (`SelectCustomer.php`, `CustomerAccount.php`) still
    use the net due date.
15. Foreign currency: discount computed and shown in the invoice currency;
    GL in functional currency at the transaction's rate.
16. Pages follow webERP's conventions: `__()` strings, `FormID`, `prnMsg`,
    no second escaping of POST data (session.php escapes it), number
    formatting with the currency's decimal places (`locale_number_format`,
    `currencies.decimalplaces`).
17. Nothing existing breaks: terms without a discount produce identical
    output; fresh install works.
