# Business request: customer balance adjustments

Our credit controller cannot correct a customer's balance in webERP. Today
they raise a fake credit note or ask the accountant for a journal, and the
customer account and the ledger stop agreeing. We need:

1. A way to adjust a customer's balance up or down, in the customer's
   currency, with a date, a reason and the ledger account it goes to.
2. Writing off what is left on an invoice: the invoice is then cleared.
3. A clean-up of small balances: every customer invoice left open with
   less than an amount we choose is written off in one go.
4. Adjustments behave like every other customer transaction: on the
   customer's account and statement, in the ledger, in the receivables
   reconciliation and reports, and they can be matched against invoices
   and payments.

Only the people we allow may do this. It must work on new installations
and upgrades, and be in the manual.
