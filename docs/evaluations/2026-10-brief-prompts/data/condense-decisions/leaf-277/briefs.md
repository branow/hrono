# today

# pay-api: models, services, schemas and utils (BC payment API, Python/Flask/SQLAlchemy)

This group is a slice of the `pay-api` payment service (`pay_api` package, Province of British Columbia, Apache 2.0). It covers the data models, the service layer (including FAS routing slips), the package initializers, and the enum and error-message utilities. Many chunks show only the license header and imports. For those files the summary can describe dependencies but not behavior.

## Models (`models/`)
- **payment.py**: the Payment model. It links payments to Invoice, InvoiceReference, PaymentAccount, PaymentLineItem, PaymentMethod, PaymentStatusCode, PaymentSystem, FeeSchedule and CorpType. It uses the PaymentStatus and PaymentMethodEnum enums and raises BusinessException.
- **routing_slip.py**: the Routing Slip model setup. It has relationships to Invoice, Payment, PaymentAccount, Refund and Audit, plus marshmallow schemas, pytz, RoutingSlipStatus and PaymentMethod enums, and DT_SHORT_FORMAT. No implementation is shown.

## Package initializers
- **schemas/__init__.py**: marks the directory as a package and defines nothing.
- **services/__init__.py**: re-exports 22 service modules. Six classes are aliased on import:
  - EFTShortnameHistorical→EFTHistoryService
  - EFTShortnames→EFTShortNamesService
  - EFTShortnameSummaries→EFTShortNameSummaryService
  - Invoice→InvoiceService
  - PaymentTransaction→TransactionService
  - Receipt→ReceiptService
  
  It also re-exports EFTShortnameHistory and EFTShortnameHistorySearch.
- **services/fas/__init__.py**: exposes RoutingSlipService and CommentService.
- **services/gcp_queue/__init__.py**: exports a module-level `GcpQueue` singleton for use across the app.

## Payment-system services
- **base_payment_system.py**: abstract interface for payment system processors. Only imports are visible. They show use of CfsAccount, Invoice, PaymentTransaction, Receipt, Credit, CFSService, the GCP queue publisher (QueueMessageTypes) and Sentry.
- **internal_pay_service.py**: handles zero-dollar and staff-approved internal payments, with optional routing-slip prepaid balance.
  - `create_invoice` deducts from `routing_slip.remaining_amount` and marks an ACTIVE slip COMPLETE when the balance falls below 0.01.
  - For zero-dollar or slip-less invoices it creates an InvoiceReference and sets the status to CREATED.
  - `complete_post_invoice` completes and releases the payment when the invoice is not APPROVED.
  - `get_default_invoice_status` returns APPROVED.
  - `process_cfs_refund` marks the payment REFUNDED, restores the slip balance, reverts a COMPLETE slip to ACTIVE, and sets the invoice to REFUND_REQUESTED.
  - `_validate_routing_slip` checks the ALLOW_LEGACY_ROUTING_SLIPS config, allowed statuses (ACTIVE, LINKED, NSF, CORRECTION), the parent-slip restriction and sufficient balance.
- **ejv_pay_service.py**: EJV (Electronic Journal Voucher) payments for government accounts. Behavior depends on `payment_account.billable`.
  - `create_invoice` creates an InvoiceReference only when the account is not billable.
  - `complete_post_invoice` completes the payment only if the reference is ACTIVE.
  - `process_cfs_refund` returns REFUNDED, CANCELLED or REFUND_REQUESTED depending on billability, invoice status and whether an active reference exists.
- **direct_pay_service.py**: dataclasses for parsing PAYBC Direct Pay responses.
  - Classes: RefundLineRequest, RefundData, RevenueLine, OrderStatus.
  - Constants: PAYBC_DATE_FORMAT, PAYBC_REVENUE_SEPARATOR, DECIMAL_PRECISION, STATUS_PAID = ('PAID','CMPLT').
- **eft_service.py**: applies CFS EFT credits to invoices. It extends DepositService and uses EFTCredit, EFTCreditInvoiceLink, EFTRefund and EFTShortnamesHistorical. Only the class and imports are visible.

## Account, invoice, statement and other services
- **payment_account.py**: sets up payment accounts across PayBC and CGI.
  - `_handle_payment_details` routes by payment system code.
    - PayBC finds or creates a CfsAccountModel.
    - CGI end-dates the active DistributionCode and saves the new revenue account as a DistributionCode.
    - Other systems deactivate a pending PAD CfsAccountModel when the multiple-payment-methods flag is off.
  - PAD activation logic is in `_update_pad_activation_date` and `_get_payment_based_on_pad_activation`.
  - It also handles account fees (AccountFeeModel) and a default statement frequency (MONTHLY for EFT).
  - The `PaymentDetails` dataclass holds the payment context.
- **payment.py (service)**: defines the `PaymentReportInput` dataclass. Only imports and that dataclass are visible.
- **statement.py**: Statement service. Only imports are visible, covering EFT, invoice, payment and statement models, StatementFrequency and related enums.
- **distribution_code.py**: fee calculation via distribution codes. Imports only.
- **invoice.py**: invoice service. Imports only, including `check_auth`, ALL_ALLOWED_ROLES, CodeService and OAuthService.
- **payment_service.py, payment_transaction.py, refund.py**: the chunk content was missing. Only a request for the full file was returned, so nothing is known about these files.

## FAS routing slips (`services/fas/`)
- **routing_slip.py**: routing slip lifecycle.
  - `create` validates the slip number and enforces a single payment method. It requires a paymentDate for CHEQUE payments. It creates the PaymentAccount, CfsAccount (INTERNAL, PENDING), RoutingSlip and Payment records.
  - `do_link` sets the parent and LINKED status and moves the remaining amount from the child to the parent.
  - `update` handles status changes by role. NSF reverses totals, VOID zeroes the balance, and CORRECTION recalculates payments and adds a comment.
  - Linking validation blocks:
    - already-linked slips
    - slips that are already parents
    - self-links
    - children with invoices
    - NSF slips
    - slips in refund, write-off, COMPLETE, VOID or CORRECTION statuses
  - The routing slip number must be 9 digits. The check digit is computed from the first 8 digits, doubling every 2nd digit and summing digits above 9, then taking `(10 - (sum % 10)) % 10`.
- **routing_slip_status_transition_service.py**: status state machine built on the `STATUS_TRANSITIONS` dict.
  - `get_possible_transitions` removes the authorization option when the requester is the same person who requested the refund or last updated the write-off, so self-approval is blocked.
  - `validate_possible_transitions` raises FAS_INVALID_RS_STATUS_CHANGE for invalid moves.
  - `get_actual_status` unwraps custom statuses.

## Utils
- **enums.py**: 40+ enums.
  - Statuses: PaymentStatus, InvoiceStatus, RoutingSlipStatus, RoutingSlipCustomStatus, CfsAccountStatus.
  - Methods and systems: PaymentMethod, PaymentSystem.
  - Roles: Role.
  - EFT types and actions: EFTHistoricalTypes, EFTShortnameStatus, EFTPaymentActions.
  - Disbursement: DisbursementMethod.
  - Others: StatementFrequency, PatchActions, PaymentDetailsGlStatus, AuthHeaderType, ContentType, AccountType, CorpType, Product.
  - `StatementFrequency.default_frequency()` returns WEEKLY.
  - `RoutingSlipCustomStatus.from_key()` and `PatchActions.from_value()` return None when nothing matches.
- **paybc_transaction_error_message.py**: `PAYBC_TRANSACTION_ERROR_MESSAGE_DICT` maps raw PayBC error strings to snake_case UI codes. Examples are DECLINED, INVALID_CARD_NUMBER, CALL_FOR_AUTH, BEANSTREAM_INVALID_RESPONSE and DUPLICATE_ORDER_NUMBER.

## Caution
- **do_link persistence**: `do_link` changes the parent slip's amount but only calls `routing_slip.commit()` on the child. The parent change may not persist.
- **Correction lookup**: `_calculate_correction_and_comment` uses `next(...)` and raises StopIteration, not a proper business error, if a payment ID is missing.
- **Linking checks**: `_is_linked_already` checks both the `parent` field and LINKED status, which could drift apart. The child's invoices are checked before linking, but the parent's are not.
- **Self-approval filter**: the filter assumes the authorization transition is at index 0 of `STATUS_TRANSITIONS`. Reordering would filter the wrong entry.
- **EJV**: `complete_post_invoice` always calls `_release_payment`, whatever the reference status. Billable accounts skip reference creation in `create_invoice`. Refunds are not processed here, because a CRON job does that.
- **Internal pay**: on the slip path, `create_invoice` returns None, and an external CFS job sets the invoice status later. `process_cfs_refund` checks `invoice.total == 0` twice.
- **PAD**:
  - Production PAD accounts wait 3 days for activation. A `previous_payment` override bypasses the wait.
  - Pending PAD accounts are forced INACTIVE, because otherwise the PAD job switches the payment method automatically.
  - `CfsAccountModel.create_account` can return None, and execution continues.
- **Enums**:
  - EFTHistoricalTypes mixes transaction types with shortname refund statuses.
  - `PaymentDetailsGlStatus.RJCT` carries a comment, "Should have refundglerrormessage", that points to missing validation.
- **Error mapping**: 'PAYMENT CANCELED' maps to 'PAYMENT_CANCELLED', so the spelling changes.
- **Truncated content**: many files show only imports. No behavior can be inferred for invoice, statement, payment, distribution_code, base_payment_system, eft_service, payment_service, payment_transaction or refund.

# decisions

# Payment services, models and enums in pay-api (`pay_api`)

This part of the pay-api service holds the payment business logic: per-payment-method services, routing-slip (FAS) handling, payment-account setup, and the shared enums and error-message maps. Several sources were provided only as imports or headers, so their logic is not described here.

## Boundaries and shapes

- **`services/__init__.py`** re-exports the service modules and aliases six classes:
  - `EFTShortnameHistorical` → `EFTHistoryService`
  - `EFTShortnames` → `EFTShortNamesService`
  - `EFTShortnameSummaries` → `EFTShortNameSummaryService`
  - `Invoice` → `InvoiceService`
  - `PaymentTransaction` → `TransactionService`
  - `Receipt` → `ReceiptService`
- **`services/fas/__init__.py`** exposes `RoutingSlipService` and `CommentService`.
- **`services/gcp_queue/__init__.py`** exports a module-level `GcpQueue` singleton. Payment services publish queue messages through it.
- **Routing slip `create`** takes `request_json` with the routing slip number, `routingSlipDate`, `paymentAccount.accountName`, and a `payments` array. Each payment has `paymentMethod`, `paidAmount`, `paidUsdAmount`, `chequeReceiptNumber` and `paymentDate`.
- **`do_link`** takes `rs_number` and `parent_rs_number`.
- **`update`** takes `rs_number`, a patch action and `request_json` with `status` or `payments`. All three return the slip from `find_by_number()`.
- **`direct_pay_service.py`** defines the PAYBC Direct Pay response shapes:
  - `OrderStatus`: `revenue` (list of `RevenueLine`), `postedrefundamount`, `refundedamount`, `paymentstatus`.
  - `RevenueLine`: `linenumber`, `revenueaccount`, `revenueamount`, `glstatus`, `glerrormessage`, `refund_data` (list of `RefundData`).
  - `RefundData`: `refundglstatus`, `refundglerrormessage`.
  - `RefundLineRequest`: `revenue_account`, `refund_amount`, `is_service_fee`.
  - Constants: `PAYBC_DATE_FORMAT='%Y-%m-%d'`, `PAYBC_REVENUE_SEPARATOR='|'`, `DECIMAL_PRECISION='.2f'`, `STATUS_PAID=('PAID','CMPLT')`.
- **`payment.py` (service)** defines the `PaymentReportInput` dataclass. It requires `content_type`, `report_name`, `template_name` and `results`, and optionally takes `statement_summary` and `eft_transactions`.
- **`PaymentDetails`** (in `payment_account.py`) carries `account_request`, `is_sandbox`, `pay_system`, `payment_account`, `payment_info` and `previous_payment`.
- **`utils/paybc_transaction_error_message.py`** holds `PAYBC_TRANSACTION_ERROR_MESSAGE_DICT`. It maps raw PayBC messages to UI codes, for example `DECLINE` and `DECLINED` → `DECLINED`, and `PAYMENT CANCELED` → `PAYMENT_CANCELLED`. It also covers `INVALID CARD NUMBER`, `CALL FOR AUTH`, `DUPLICATE ORDER NUMBER…` → `DUPLICATE_ORDER_NUMBER`, and the Beanstream and timeout messages.

## Decisions

### Routing slip create (`fas/routing_slip.py`)
- The slip number must be unique, checked by `validate_and_find_by_number()`.
- All payments must share one `paymentMethod`.
- CHEQUE payments must have `paymentDate`.
- It creates `PaymentAccountModel` and a `CfsAccountModel` (INTERNAL, PENDING), sums the paid and USD amounts into `RoutingSlipModel`, and creates one `PaymentModel` per payment.

### Routing slip link (`do_link`)
- `_validate_linking()` raises `BusinessException` in these cases:
  - Child is already linked: `parent` is set or status is `LINKED` → `RS_ALREADY_LINKED`.
  - Child is itself a parent, per `find_children` → `RS_ALREADY_A_PARENT`.
  - Parent is already linked → `RS_PARENT_ALREADY_LINKED`.
  - Child equals parent → `RS_CANT_LINK_TO_SAME`.
  - Child has `invoices` → `RS_CHILD_HAS_TRANSACTIONS`.
  - Child is NSF → `RS_CANT_LINK_NSF`.
  - Either slip is in one of these statuses → `RS_IN_INVALID_STATUS`: REFUND_REQUESTED, REFUND_AUTHORIZED, REFUND_COMPLETED, WRITE_OFF_REQUESTED, WRITE_OFF_AUTHORIZED, WRITE_OFF_COMPLETED, COMPLETE, VOID, CORRECTION.
- On success the child gets `parent_number` and status `LINKED`. Its `remaining_amount` moves to the parent and the child becomes 0.

### Routing slip number check
- `rs_number` must be exactly 9 digits.
- The checksum doubles every second digit among the first 8, summing the digits of any result above 9.
- Those 8 values are summed, and the 9th digit must equal `(10 - sum % 10) % 10`.
- Otherwise it raises `FAS_INVALID_ROUTING_SLIP_DIGITS`.

### Routing slip update, `UPDATE_STATUS`
- `RoutingSlipStatusTransitionService.validate_possible_transitions` checks the new status against `STATUS_TRANSITIONS`. A failure raises `FAS_INVALID_RS_STATUS_CHANGE`. `_check_roles_for_status_update()` checks the user's role.
- **Self-approval:** `get_possible_transitions` drops the first transition (`transition_list[1:]`) in two cases:
  - The list includes `REFUND_AUTHORIZED` and the user is `refund_model.requested_by`.
  - The list includes `WRITE_OFF_AUTHORIZED` and the user is `rs_model.updated_by`.
- **NSF:** the total of the slip and its children is negated and added.
- **VOID:** raises `RS_HAS_TRANSACTIONS` if the slip has invoices. Otherwise `remaining_amount` is zeroed.
- **CORRECTION:** requires `payments`. `_calculate_correction_and_comment()` updates the paid amounts and writes a comment. The correction is added to the totals. The status then resets to COMPLETE if `remaining_amount == 0`. If it is not 0, the status resets to ACTIVE when the `CfsAccountModel` is PENDING or absent.

### Internal pay (`internal_pay_service.py`)
- **`create_invoice`:**
  - With `invoice.routing_slip` set, it runs `_validate_routing_slip()` and deducts the total from `remaining_amount`. If the slip is ACTIVE and the balance drops below 0.01, the slip becomes COMPLETE. It returns None, and an external CFS job sets the invoice status later.
  - With a zero total or no slip, it creates an `InvoiceReference` and sets the status to CREATED.
- **`_validate_routing_slip`:**
  - A missing slip is judged by the `ALLOW_LEGACY_ROUTING_SLIPS` config.
  - Status must be ACTIVE, LINKED, NSF or CORRECTION.
  - NSF needs a positive balance.
  - A parent slip is forbidden.
  - `remaining_amount` must be at least `invoice.total`.
- **`complete_post_invoice`:** if the status is not APPROVED, it calls `complete_payment()` and then `_release_payment()`.
- **`get_default_invoice_status`:** returns APPROVED.
- **`process_cfs_refund`:**
  - It needs a non-zero total and a routing slip whose status is ACTIVE or COMPLETE.
  - It marks the payment REFUNDED, adds the amount back to `remaining_amount`, and reverts a COMPLETE slip to ACTIVE.
  - It sets the invoice to REFUND_REQUESTED.

### EJV pay (`ejv_pay_service.py`)
- **`create_invoice`:** creates an `InvoiceReference` only when `payment_account.billable` is False.
- **`complete_post_invoice`:** calls `complete_payment` if the reference is ACTIVE. It always calls `_release_payment`.
- **`process_cfs_refund`:**

| Condition | Result |
|---|---|
| Account not billable | REFUNDED |
| Invoice APPROVED with an active reference | REFUND_REQUESTED |
| Invoice APPROVED with no active reference | CANCELLED |
| Anything else | REFUND_REQUESTED |

  A CRON job does the actual refund.

### Payment account (`payment_account.py`)
- **`_handle_payment_details` routes by payment system code:**
  - PayBC finds or creates a `CfsAccountModel`, then updates the PAD activation date.
  - CGI end-dates the active `DistributionCode` (end_date is yesterday) and saves the revenue account as a new `DistributionCode`.
  - Other systems set a pending PAD `CfsAccountModel` to INACTIVE when the multiple-payment-methods flag is off.
- **`_update_pad_activation_date`:**
  - In a sandbox, it sets the account ACTIVE with the activation date set to now.
  - Otherwise `_get_payment_based_on_pad_activation` picks the method and date:
    - First PAD: PAD, or `previous_payment`, with a computed date.
    - Activation date already passed: PAD, date unchanged.
    - Inside the activation window: PAD, or `previous_payment`, date unchanged.
- **Statement settings:** `_persist_default_statement_frequency` sets MONTHLY for EFT and the default for other methods.
- **Account fees:** `AccountFeeModel` rows are saved, fetched and deleted by account and product. `apply_filing_fees` and `service_fee_code` are persisted.

### Enums (`utils/enums.py`)
- Holds more than 40 enums for payment, invoice and routing-slip statuses, payment methods and systems, roles, and EFT history and actions.
- `StatementFrequency.default_frequency()` returns WEEKLY.
- `PatchActions.from_value()` returns None for an unknown value.
- `RoutingSlipCustomStatus.from_key()` returns None for an unknown key.
- Custom statuses map to ACTIVE, and `get_actual_status` unwraps them to `original_status`.

## Sources to open first
- `services/fas/routing_slip.py`: slip create, link and update, plus linking and number validation.
- `services/fas/routing_slip_status_transition_service.py`: the status machine.
- `services/internal_pay_service.py`, `ejv_pay_service.py`: per-method invoice flows.
- `services/payment_account.py`: account setup and PAD activation.
- `utils/enums.py`: all status and method constants.

Several sources show only imports or headers; their method logic is not covered here:
- `models/payment.py`
- `models/routing_slip.py`
- `services/base_payment_system.py`
- `services/eft_service.py`
- `services/distribution_code.py`
- `services/invoice.py`
- `services/payment_service.py`
- `services/payment_transaction.py`
- `services/refund.py`
- `services/statement.py`

## Hazards
1. `do_link` changes the parent's `remaining_amount` but commits only the child. The parent's amount may not persist.
2. `_calculate_correction_and_comment` uses `next(...)` without a default. An unknown payment ID raises `StopIteration` instead of a business error.
3. Self-approval prevention assumes the authorization transition is at index 0 of each `STATUS_TRANSITIONS` list. Reordering the list would drop the wrong transition.
4. The link check reads both the `parent` field and `status == LINKED`, so the two can drift apart. The parent's invoices are never checked.
5. Pending PAD accounts are deliberately set INACTIVE, because otherwise the PAD job switches the payment method. `CfsAccountModel.create_account` can return None and execution continues. Internal pay with a routing slip returns None from `create_invoice`, and the invoice status is set later by an external job.

# core

# Payment services, models and enums in pay-api

This part holds the payment API's service layer. It has one service per payment method (internal/routing-slip, EJV, EFT, direct pay), the FAS routing-slip workflow, payment-account setup, and the shared enums and models. It hands finished payments to a GCP queue through `_release_payment`, and it talks to CFS/PayBC.

## Contract
- **`services/__init__.py`** re-exports the service modules. It aliases `Invoice` as `InvoiceService`, `PaymentTransaction` as `TransactionService` and `Receipt` as `ReceiptService`. It also aliases three EFT short-name classes.
- **FAS routing slips:**
  - `RoutingSlipService.create` takes `request_json` with the slip number, a `payments` array and `paymentAccount.accountName`.
  - `do_link(rs_number, parent_rs_number)` links a child slip to a parent.
  - `update(rs_number, action, request_json)` changes status or corrects payments.
  - All three return the slip via `find_by_number()`.
- **`direct_pay_service.py`:** dataclasses (`OrderStatus`, `RevenueLine`, `RefundData`) that parse PAYBC order-status responses.
- **`paybc_transaction_error_message.py`:** maps raw PayBC error strings to UI codes.

## Decisions
- **Internal pay (`internal_pay_service.py`):**
  - With a routing slip, `create_invoice` deducts from `remaining_amount`.
  - It marks the slip COMPLETE when the balance falls below 0.01.
  - `_validate_routing_slip` allows only ACTIVE, LINKED, NSF and CORRECTION slips.
  - `process_cfs_refund` restores the balance and returns a COMPLETE slip to ACTIVE.
- **EJV (`ejv_pay_service.py`):** only non-billable accounts get an `InvoiceReference`. `process_cfs_refund` returns REFUNDED, CANCELLED or REFUND_REQUESTED depending on billability and invoice status.
- **Status transitions (`routing_slip_status_transition_service.py`):** `STATUS_TRANSITIONS` defines the allowed moves. The requester cannot approve their own refund or write-off.
- **Linking and number checks (`fas/routing_slip.py`):** `_validate_linking` rejects children that are already linked, are parents, have invoices or are NSF. It also rejects slips in terminal or refund statuses. A checksum on the 9-digit number is checked too.
- **Payment accounts (`payment_account.py`):** `_handle_payment_details` branches on PayBC, CGI and other systems. PAD activation timing follows `_get_payment_based_on_pad_activation`.

## Hazards
- In `do_link`, the parent's changed `remaining_amount` may not persist, because only the child is committed.
- `_calculate_correction_and_comment` uses `next(...)`, which raises `StopIteration` for an unknown payment id.
- The self-approval filter assumes the authorization transition sits at index 0 of each `STATUS_TRANSITIONS` list. Reordering the list breaks it.

## Open first
- `services/fas/routing_slip.py`: slip create, link and update logic.
- `services/fas/routing_slip_status_transition_service.py`: the state machine.
- `services/internal_pay_service.py`: balance deduction and refund handling.
- `utils/enums.py`: all status, method and role constants.

# core-states

# pay-api: payment services, routing slips (FAS) and shared enums

This is the service layer of the Python `pay-api`. It creates and settles invoices per payment system (internal, EJV, PayBC/CFS, EFT), runs the FAS routing-slip lifecycle, and sets up payment accounts. It hands completion messages to the GCP queue (`services/gcp_queue`, via `_release_payment`) and talks to CFS and PayBC. It reads and writes the SQLAlchemy models (Payment, Invoice, InvoiceReference, RoutingSlip, PaymentAccount, CfsAccount). `services/__init__.py` re-exports the services and aliases several, e.g. `Invoice`→`InvoiceService`.

## Contract
- **Routing slip `create`**: takes `request_json` with the slip number, a `payments` array (paymentMethod, paidAmount, paidUsdAmount, chequeReceiptNumber, paymentDate), `paymentAccount.accountName` and `routingSlipDate`. It returns the slip via `find_by_number()`.
- **`do_link`**: takes `rs_number` and `parent_rs_number`.
- **`update`**: takes `rs_number`, a patch `action` and `request_json` with `status` or `payments`.
- **Payment-system services**: share the `base_payment_system` interface: `create_invoice`, `complete_post_invoice`, `process_cfs_refund`, `get_receipt`.
- **`direct_pay_service.py`**: holds the dataclasses and constants for parsing PayBC Direct Pay order-status responses (`OrderStatus`, `RevenueLine`, `RefundData`, `STATUS_PAID`).
- **`paybc_transaction_error_message.py`**: maps raw PayBC error strings to UI codes. `'PAYMENT CANCELED'` becomes `'PAYMENT_CANCELLED'`.

## Decisions
- `fas/routing_slip.create`: refuses a duplicate slip number (`validate_and_find_by_number`), mixed payment methods, and CHEQUE payments without `paymentDate`. It creates the account, a PENDING INTERNAL CfsAccount, the slip with summed totals, and one Payment per entry.
- `fas/routing_slip._validate_linking`: refuses linking if the child is already linked or is a parent, links to itself, has invoices or NSF status, or if either slip is in a refund, write-off, COMPLETE, VOID or CORRECTION status. It raises the `RS_*` errors.
- Routing slip number check: 9 digits with a checksum on the 9th digit, else `FAS_INVALID_ROUTING_SLIP_DIGITS`.
- `fas/routing_slip.do_link`: sets LINKED and moves `remaining_amount` from child to parent.
- `fas/routing_slip.update` (status): checks the transition and role (`_check_roles_for_status_update`). NSF reverses the totals of the slip and its children. VOID is refused with `RS_HAS_TRANSACTIONS` if invoices exist, otherwise it zeroes the balance. CORRECTION adjusts payments, then sets COMPLETE or ACTIVE.
- `routing_slip_status_transition_service`: `STATUS_TRANSITIONS` holds the allowed moves. `get_possible_transitions` removes self-approval of refund and write-off. `validate_possible_transitions` raises `FAS_INVALID_RS_STATUS_CHANGE`.
- `internal_pay_service.create_invoice`: with a slip, deducts the invoice from `remaining_amount` and marks the slip COMPLETE below 0.01. Zero-dollar or slip-less invoices get an InvoiceReference and status CREATED.
- `internal_pay_service._validate_routing_slip`: allows ACTIVE, LINKED, NSF (balance > 0) or CORRECTION, forbids a parent slip, and requires enough balance. A missing slip is allowed only if `ALLOW_LEGACY_ROUTING_SLIPS` is set.
- `internal_pay_service.process_cfs_refund`: only for a slip-backed invoice with a non-zero total. It restores the balance, reopens a COMPLETE slip and sets REFUND_REQUESTED.
- `ejv_pay_service`: `create_invoice` makes an InvoiceReference only for non-billable accounts. `process_cfs_refund` returns REFUNDED (non-billable), CANCELLED or REFUND_REQUESTED. A cron job does the actual refund.
- `payment_account._handle_payment_details`: routes by payment system. PayBC creates a CfsAccount and updates PAD activation. CGI end-dates the old DistributionCode and saves a new one. Other systems deactivate a pending PAD account unless multiple payment methods are enabled.
- `payment_account._get_payment_based_on_pad_activation`: applies the 3-day PAD activation wait. Sandbox accounts activate immediately.

## Hazards
- `do_link` commits only the child slip, so the parent's changed amount may not persist.
- `_calculate_correction_and_comment` uses a bare `next(...)`, so an unknown payment id raises `StopIteration` instead of a business error.
- `_is_linked_already` checks both `parent` and `status == LINKED`, which can drift apart. The parent's invoices are not checked when linking.

## Open first
- `services/fas/routing_slip.py`: create, link, update, number validation.
- `services/fas/routing_slip_status_transition_service.py`: the status machine.
- `services/internal_pay_service.py`: slip balance handling and refunds.
- `utils/enums.py`: statuses, methods, roles and patch actions.

# core-states#2

# pay-api: payment services, routing slips (FAS), and shared enums

Business-logic layer of the pay-api that creates and settles invoices through a payment-system implementation for each payment method. It also runs the routing-slip (FAS) lifecycle and holds the shared enums and PayBC error-code map. It reads and writes SQLAlchemy models (Invoice, InvoiceReference, Payment, PaymentAccount, CfsAccount, RoutingSlip, Refund and others). It publishes completed-payment messages to the GCP queue through the `gcp_queue` singleton.

## Contract
- `services/__init__.py` re-exports the service modules, with aliases such as `Invoice→InvoiceService`, `PaymentTransaction→TransactionService` and `Receipt→ReceiptService`.
- Payment-system services (internal, EJV, EFT, PAD/PayBC, direct pay) implement the interface in `base_payment_system.py`. Each has `create_invoice`, `complete_post_invoice`, `process_cfs_refund` and `get_default_invoice_status`.
- `RoutingSlipService.create` takes `{number, payments[{paymentMethod, paidAmount, paidUsdAmount, chequeReceiptNumber, paymentDate}], paymentAccount.accountName, routingSlipDate}`. `do_link(rs_number, parent_rs_number)` links a child slip to a parent. `update(rs_number, action, request_json)` changes status or corrects payments. All three return the slip dict via `find_by_number()`.
- `direct_pay_service.py` holds the dataclasses for PayBC Direct Pay order-status parsing (`OrderStatus`, `RevenueLine`, `RefundData`, `RefundLineRequest`) and `STATUS_PAID = ('PAID','CMPLT')`.
- `PAYBC_TRANSACTION_ERROR_MESSAGE_DICT` (`utils/paybc_transaction_error_message.py`) maps raw PayBC error strings to UI codes. It changes the spelling `CANCELED` to `CANCELLED`.

## Decisions
- `InternalPayService.create_invoice`: a routing slip is validated by `_validate_routing_slip`, then `remaining_amount` is reduced. The slip becomes COMPLETE if it was ACTIVE and the balance falls below 0.01. Zero-dollar or slip-less invoices get an InvoiceReference and status CREATED.
- `_validate_routing_slip` allows only ACTIVE, LINKED, NSF or CORRECTION slips. An NSF slip needs a positive balance, a parent slip is refused, and the balance must cover `invoice.total`. A missing slip is allowed only if the `ALLOW_LEGACY_ROUTING_SLIPS` config is set.
- `InternalPayService.complete_post_invoice`: if the invoice is not APPROVED, `complete_payment` runs, then `_release_payment` publishes to the queue.
- `InternalPayService.process_cfs_refund`: the payment becomes REFUNDED, the slip balance is restored (COMPLETE goes back to ACTIVE), and the invoice becomes REFUND_REQUESTED.
- `EjvPayService.create_invoice`: an InvoiceReference is created only for non-billable accounts.
- `EjvPayService.complete_post_invoice` completes payment when the reference is ACTIVE, and always calls `_release_payment`.
- `EjvPayService.process_cfs_refund`: non-billable returns REFUNDED. An APPROVED invoice returns REFUND_REQUESTED if an active reference exists, else CANCELLED. Anything else returns REFUND_REQUESTED. A cron job does the real refund.
- `RoutingSlipService.create`:
  - The slip number must be unique.
  - All payments must share one method.
  - CHEQUE payments need `paymentDate`.
  - It creates the PaymentAccount, an INTERNAL/PENDING CfsAccount, the slip with summed totals, and one Payment per entry.
- `RoutingSlipService.do_link` runs `_validate_linking`, sets LINKED and `parent_number`, and moves `remaining_amount` to the parent.
- `RoutingSlipService.update`:
  - It validates the transition and the user's role with `_check_roles_for_status_update`.
  - NSF adds the negated total of the slip and its children.
  - VOID is refused with `RS_HAS_TRANSACTIONS` if invoices exist, otherwise it zeroes the balance.
  - CORRECTION runs `_calculate_correction_and_comment`, then sets COMPLETE (balance 0) or ACTIVE.
- `_validate_linking` refuses a child that is already linked, is a parent, links to itself, has invoices, is NSF, or has a parent that is already linked. It also refuses slips in refund, write-off, COMPLETE, VOID or CORRECTION status.
- Routing slip number check: exactly 9 digits plus a checksum digit, else `FAS_INVALID_ROUTING_SLIP_DIGITS`.
- `RoutingSlipStatusTransitionService`: `STATUS_TRANSITIONS` defines the allowed moves. `get_possible_transitions` removes self-approval of refund and write-off authorization. `validate_possible_transitions` raises `FAS_INVALID_RS_STATUS_CHANGE`.
- `PaymentAccountService._handle_payment_details` routes by payment system. PayBC creates a CfsAccount and sets the PAD activation date. CGI end-dates the old DistributionCode and creates a new one. Other systems deactivate a pending PAD account unless the multiple-payment-methods flag is on.
- `_get_payment_based_on_pad_activation` handles PAD timing. There is a 3-day production wait, and sandbox activates immediately.

## Hazards
- `do_link` calls `commit()` on the child slip only. The parent's changed `remaining_amount` may not be persisted.
- `_calculate_correction_and_comment` uses a bare `next(...)`. An unknown payment ID raises `StopIteration` instead of a business error.
- `_is_linked_already` checks both `parent` and `status == LINKED`, which can drift out of sync. Parent invoices are not checked when linking.

## Open first
- `services/fas/routing_slip.py`: slip create, link, update and the linking/number validation.
- `services/fas/routing_slip_status_transition_service.py`: the status machine and self-approval filter.
- `services/internal_pay_service.py` and `services/ejv_pay_service.py`: per-method invoice, completion and refund decisions.
- `utils/enums.py`: all statuses, methods and roles.

Several files (payment, payment_service, payment_transaction, refund, statement, invoice, eft_service, base_payment_system) had only imports visible, so their behaviour is not described here.
