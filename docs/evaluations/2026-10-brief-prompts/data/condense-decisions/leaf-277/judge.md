21 facts cite this leaf's files.

| prompt | words | facts conveyed | runs' range | detail share | contradicted | cited files named |
|---|---|---|---|---|---|---|
| `today` | 1127 | 0.21 | 0.21-0.21 | 0.41 | 0 | 10/10 |
| `decisions` | 1267 | 0.17 | 0.17-0.17 | 0.29 | 0 | 10/10 |
| `core` | 372 | 0.14 | 0.14-0.14 | 0.26 | 0 | 4/10 |
| `core-states` | 569 | 0.19 | 0.14-0.24 | 0.15 | 0 | 3/10 |
| `core-states#2` | 693 | 0.21 | 0.21-0.21 | 0.21 | 0 | 4/10 |
| `(input)` | 2270 | 0.26 | 0.26-0.26 |  | 0 | 10/10 |

Per fact (score per prompt):

| # | fact | today | decisions | core | core-states | core-states#2 | (input) |
|---|---|---|---|---|---|---|---|
| 1 | The POST endpoint on the payment-requests blueprint validates the body against the 'payment_request' JSON sche… | 0 | 0 | 0 | 0 | 0 | 0 |
| 2 | PaymentService.create_invoice picks the payment method from the request's paymentInfo/methodOfPayment, falling… | 0 | 0 | 0 | 0 | 0 | 0 |
| 3 | The invoice's starting status comes from the payment system's get_default_invoice_status: CREATED by default, … | 1 | 1 | 0 | 1 | 1 | 1 |
| 4 | For methods that settle immediately or on credit (e.g. BC Online, PAD, EFT, internal), complete_post_invoice c… | 0 | 1 | 1 | 1 | 1 | 1 |
| 5 | PadService.create_account stores the bank institution, transit and account numbers on a new CfsAccount with st… | 1 | 0 | 1 | 1 | 0 | 1 |
| 6 | _apply_eft_pending_payments calls EFTShortnames.process_payment_action with APPLY_CREDITS for each linked acco… | 0 | 0 | 0 | 0 | 0 | 1 |
| 7 | The lock is stored as two nullable timestamp columns on PaymentAccount: has_nsf_invoices and has_overdue_invoi… | 1 | 0 | 0 | 0 | 0 | 0 |
| 8 | New charges are blocked by PaymentSystemService.ensure_no_payment_blockers, which raises PAD_CURRENTLY_NSF or … | 0 | 0 | 0 | 0 | 0 | 0 |
| 9 | Unlocking happens when a credit card transaction completes. PaymentTransaction.update_transaction calls Paymen… | 0 | 0 | 0 | 0 | 0 | 0 |
| 10 | The refunds endpoint under /payment-requests/<invoice_id> needs the SYSTEM, CREATE_CREDITS or FAS_REFUND role … | 0 | 0 | 0 | 0 | 0 | 0 |
| 11 | If process_cfs_refund returns no status, RefundService sets the invoice to REFUND_REQUESTED. It stamps refund_… | 0 | 0 | 0 | 0 | 0 | 0 |
| 12 | PAD (and Online Banking) refunds never return money to the bank. PadService.process_cfs_refund calls _refund_a… | 0 | 0 | 0 | 0 | 0 | 1 |
| 13 | DirectPayService.process_cfs_refund posts an automated refund to the PayBC refund API. Later the DIRECT_PAY_RE… | 1 | 1 | 1 | 1 | 1 | 1 |
| 14 | Internal (routing slip) refunds add the invoice total back to routing_slip.remaining_amount (reactivating a CO… | 2 | 2 | 1 | 2 | 2 | 2 |
| 15 | The new method code goes in the PaymentMethod enum, and its starting invoice state in InvoiceStatus (existing … | 1 | 1 | 1 | 1 | 1 | 1 |
| 16 | Add a PaymentSystemService subclass that implements the abstract create_invoice, get_payment_system_code and g… | 1 | 0 | 0 | 1 | 2 | 1 |
| 17 | Register the new service in PaymentSystemFactory.create_from_payment_method, which is used by create_invoice, … | 0 | 0 | 0 | 0 | 0 | 0 |
| 18 | In pay-api, post_invoice first runs check_auth with contains_role=make_payment. PaymentService.create_invoice … | 0 | 0 | 0 | 1 | 0 | 0 |
| 19 | Invoice._add_dynamic_fields sets is_payment_action_required only when the invoice is CREATED and the payment m… | 0 | 0 | 0 | 0 | 0 | 0 |
| 20 | After the payment provider returns, auth-web's PaymentReturnView PATCHes pay-api 'payment-requests/{id}/transa… | 0 | 0 | 0 | 0 | 0 | 0 |
| 21 | PAD, BCOL, EFT, EJV and internal pay services publish the same COMPLETED event through BaseService._release_pa… | 1 | 1 | 1 | 1 | 1 | 1 |
