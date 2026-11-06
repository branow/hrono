# Request: early payment discount terms

From: Finance (accounts receivable and accounts payable)

## What we need

Many of our customers and suppliers trade on terms like "2% 10, net 30":
the invoice is due 30 days after the invoice date, but if it is paid
within 10 days the payer may deduct 2%. Today we cannot record such terms,
so staff work out discounts by hand from a spreadsheet, discounts are
taken late or missed, and statements and reports do not show them.

We want payment terms to be able to carry an early payment discount: a
percentage and a number of days from the invoice date. Terms without it
keep working exactly as today.

## Customers

- A customer's invoice shows, besides the due date, the discount, the last
  date to take it and the amount to pay if paid by that date.
- Customer statements show the same for every open invoice still inside
  its discount period.
- When a customer's payment is entered by the discount date and settles the
  invoice less the discount, the discount is recognised automatically:
  the invoice is fully settled, and the discount is accounted for the
  same way as the discounts we already allow on receipts. After the
  discount date no discount is given automatically; staff may still grant
  one by hand as today.
- Customers who already have their own agreed prompt payment discount must
  not get two discounts for the same payment.
- The customer's account and inquiry screens show which open invoices can
  still be paid with a discount and until when.

## Suppliers

- Supplier invoices on such terms show the discount and its last date
  wherever we review what we owe.
- When we pay a supplier, invoices still inside their discount period are
  paid less the discount, and the discount we take is accounted for
  correctly; invoices past it are paid in full.
- The payment run must let us pay everything whose discount would expire
  before the next run, even if it is not yet due, and show how much
  discount we save.

## Unchanged

- Due dates, overdue amounts and the aged debtors and aged creditors
  reports stay based on the net due date, not the discount date.
- Existing terms, invoices and balances are not changed by the upgrade.
- Works for foreign currency customers and suppliers, with the discount in
  the invoice currency.
- Works on existing databases after the upgrade and on new installations.
