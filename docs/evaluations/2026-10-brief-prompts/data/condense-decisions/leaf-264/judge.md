9 facts cite this leaf's files.

| prompt | words | facts conveyed | runs' range | detail share | contradicted | cited files named |
|---|---|---|---|---|---|---|
| `today` | 1053 | 0.55 | 0.5-0.61 | 0.17 | 0 | 7/7 |
| `purpose-budget` | 517 | 0.5 | 0.5-0.5 |  | 0 | 3/7 |
| `decisions` | 2115 | 0.55 | 0.5-0.61 | 0.27 | 0 | 7/7 |
| `decisions-ctx` | 1506 | 0.44 | 0.44-0.44 |  | 0 | 7/7 |
| `decisions-tight` | 1302 | 0.42 | 0.33-0.5 |  | 0 | 7/7 |
| `core` | 375 | 0.45 | 0.33-0.56 | 0.13 | 0 | 7/7 |
| `core-scaled` | 719 | 0.61 | 0.61-0.61 |  | 0 | 7/7 |
| `core#2` | 498 | 0.53 | 0.44-0.61 |  | 0 | 7/7 |
| `core-states` | 727 | 0.61 | 0.61-0.61 | 0.25 | 0 | 2/7 |
| `core-states#2` | 654 | 0.36 | 0.28-0.44 | 0.25 | 0 | 3/7 |
| `(input)` | 3395 | 0.67 | 0.61-0.72 |  | 0 | 7/7 |

Per fact (score per prompt):

| # | fact | today | purpose-budget | decisions | decisions-ctx | decisions-tight | core | core-scaled | core#2 | core-states | core-states#2 | (input) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | PaymentService.create_invoice picks the payment method from the request's paymentInfo/methodOfPayment, falling… | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 0 | 1 | 2 | 1 |
| 2 | The fee comes from a FeeSchedule row that is valid for the corp type, filing type and date (fee_start_date/fee… | 2 | 2 | 2 | 1 | 2 | 1 | 2 | 2 | 2 | 2 | 2 |
| 3 | Each fee becomes a payment line item through PaymentLineItem.create. That call attaches the active distributio… | 2 | 2 | 2 | 1 | 2 | 1 | 2 | 2 | 2 | 2 | 2 |
| 4 | PadService.create_account stores the bank institution, transit and account numbers on a new CfsAccount with st… | 1 | 0 | 2 | 1 | 0 | 1 | 0 | 0 | 1 | 0 | 2 |
| 5 | _apply_eft_pending_payments calls EFTShortnames.process_payment_action with APPLY_CREDITS for each linked acco… | 0 | 1 | 0 | 0 | 0 | 1 | 1 | 0 | 0 | 0 | 0 |
| 6 | When a PAD settlement row is NOT PAID or a reversal (PADR/PAYR), the pay-queue's _process_failed_payments sets… | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 1 | 0 | 1 |
| 7 | Unlocking happens when a credit card transaction completes. PaymentTransaction.update_transaction calls Paymen… | 0 | 1 | 1 | 1 | 1 | 0 | 1 | 1 | 1 | 0 | 1 |
| 8 | Invoice._add_dynamic_fields sets is_payment_action_required only when the invoice is CREATED and the payment m… | 2 | 0 | 2 | 2 | 2 | 0 | 2 | 1 | 2 | 0 | 2 |
| 9 | After the payment provider returns, auth-web's PaymentReturnView PATCHes pay-api 'payment-requests/{id}/transa… | 1 | 2 | 1 | 1 | 1 | 1 | 1 | 2 | 1 | 2 | 2 |
