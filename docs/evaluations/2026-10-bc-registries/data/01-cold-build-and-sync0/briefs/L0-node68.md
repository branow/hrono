<!-- leaf 68, 16 members -->

These condensations together describe the **BC Government CAS/CFS (Corporate Accounting Services / Common Financial Services) payment API**, an OpenAPI spec. It covers refunds through PayBC, receipt handling, and party/account/site/contact/payment-detail management. The examples point to a test host, `heineken.cas.gov.bc.ca:7019`.

## Groupings

**1. Refunds (PayBC)**
- `POST /paybc-service/api/refund` takes a `RefundRequest` and returns a `RefundResponse`. It lists 200, 201, 401, 403 and 404 as status codes.
- Its 200 response references the `Cont` schema. The example is a transaction (`pbcrefnumber` '10007', CAD, PAID) with a revenue array and nested `refund_data` (`refundglstatus` CMPLT). It also has `postedrefundamount` 31.50 and `refundedamount` null.

**2. Receipts (`Rcpt` schema)**
These endpoints share the same example receipt (number '123451', party '11111', 'credit card', nested invoices and lines).
- `POST Rcpts_POST` creates a receipt.
- `GET /Rcpts` returns receipts as an array.
- `POST /Rcpts_Apply_POST` applies a receipt to invoices.
- `POST Rcpts_Unapply_POST` unapplies a receipt.
- The receipt update responses (`rcpt_info1/2/3`) differ only in receipt number. Their endpoint definition is cut off.
- Apply, unapply and create take an `invoice_info` or `Rcpt` body. Each returns 200 with `Rcpt` or 400 with `ErrorResponse`.

**3. Party, account, site and contact management**
- `POST /cfs/parties` creates a Party. The party response examples are 11111, 22222 and 33333. Each has `business_number` '000000000', `customer_name` 'customer', and links for collection, self and accounts.
- `POST /cfs/parties/{party_number}/accs/` creates an `Acc`. Its links are collection, parent, self and sites.
- `/cfs/parties/{party_number}/accs/{account_number}/sites/{site_number}/` has GET, POST and PUT. It is a stub with empty schemas.
- `POST /Conts` creates a contact (`Cont` schema).
- `POST /PaymentDetails` creates payment details for a site (bank, branch, CAD/CA, `provider` 'Finance and Citizens Services').

**4. Validation**
- `POST /cfs/validatepayins/` takes `Bank_info` and returns bank and branch details plus `CAS-Returned-Messages`. That field holds 'VALID' or codes such as 0001, 0003, 0005 and 0006.

**5. Shared schemas**
- `RefundRequest` requires `orderNumber`, `pbcRefNumber`, `txnAmount` and `txnNumber`.
- `RefundResponse`, `TokenResponse` (`access_token`, `expires_in`, `token_type`), `ErrorResponse` (`code`, `message`) and `Party` (with `Link` refs).
- Every non-refund endpoint returns `ErrorResponse` on 400.

## Caution:
- **Refund timing:** refunds take about 7 business days to appear. The cardholder's bank controls this, not PayBC.
- **Refund data consistency:** `refundedamount` is null while `postedrefundamount` is 31.50. It is unclear whether that is a bug or intended. Multiple refunds can exist per revenue line, so check that the `postedrefundamount` sum matches the `refund_data` entries.
- **Inconsistent amount formats:** in the same receipt objects, `amount_applied` is '9.85' (a string with no `$`) and `amount_to_apply` is '$9.5'. `receipt_amount` is numeric in some examples and '$10.02' in the update example. A `$` prefix in a numeric field may break parsing. Check the parser, or trim it server-side. It is unclear whether the `$` is literal.
- **Validation messages:** several validation errors are joined into one `CAS-Returned-Messages` string with no structure.
- **Hardcoded hosts and placeholders:**
  - Example URLs use the test host `heineken.cas.gov.bc.ca:7019`, which will break in production.
  - The identifiers (11111, 4101) look like they came from a live system.
  - All example parties share the same `business_number` and `customer_name`. Confirm these are placeholders, not fixtures.
  - The payment-details example uses the test account number 1234567890.
- **Link and URL typos:**
  - The `sites` href in the account response, and the `accounts` href in the create-party response, have a trailing space.
  - In the payment-details response, the parent and collection links have identical paths.
- **Incomplete spec:**
  - The receipt update endpoint's GET definition is cut off.
  - The sites endpoint has empty request and response schemas, so it has no data contract.
  - The three update examples are redundant.
- **Meaningless length limit:** `maxLength=2147483647` on `pbcRefNumber` and `txnNumber` is effectively unconstrained. It is likely a placeholder or unintentional.

## Members

- sbc-pay: docs/docs/PayBC Mocking/paybc-1.0.0.yaml
- sbc-pay: docs/docs/PayBC Mocking/paybc-1.0.0.yaml
- sbc-pay: docs/docs/PayBC Mocking/paybc-1.0.0.yaml
- sbc-pay: docs/docs/PayBC Mocking/paybc-1.0.0.yaml
- sbc-pay: docs/docs/PayBC Mocking/paybc-1.0.0.yaml
- sbc-pay: docs/docs/PayBC Mocking/paybc-1.0.0.yaml
- sbc-pay: docs/docs/PayBC Mocking/paybc-1.0.0.yaml
- sbc-pay: docs/docs/PayBC Mocking/paybc-1.0.0.yaml
- sbc-pay: docs/docs/PayBC Mocking/paybc-1.0.0.yaml
- sbc-pay: docs/docs/PayBC Mocking/paybc-1.0.0.yaml
- sbc-pay: docs/docs/PayBC Mocking/paybc-1.0.0.yaml
- sbc-pay: docs/docs/PayBC Mocking/paybc-1.0.0.yaml
- sbc-pay: docs/docs/PayBC Mocking/paybc-1.0.0.yaml
- sbc-pay: docs/docs/PayBC Mocking/paybc-1.0.0.yaml
- sbc-pay: docs/docs/PayBC Mocking/paybc-1.0.0.yaml
- sbc-pay: docs/docs/PayBC Mocking/paybc-1.0.0.yaml
