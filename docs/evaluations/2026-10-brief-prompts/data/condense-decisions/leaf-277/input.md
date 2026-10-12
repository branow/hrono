=== pay-api/src/pay_api/models/payment.py ===

Payment model manages payment records and their relationships to invoices, accounts, line items, methods, statuses, and the payment system. Tracks PaymentStatus and PaymentMethodEnum enums. Validates via BusinessException, enforces user context in operations. Related tables: Invoice, InvoiceReference, PaymentAccount, PaymentLineItem, PaymentMethod, PaymentStatusCode, PaymentSystem, FeeSchedule, CorpType.

=== pay-api/src/pay_api/models/routing_slip.py ===

Routing Slip data model setup for the payment API system. Apache 2.0 license header; imports Flask application context, SQLAlchemy ORM with relationships to Invoice, Payment, PaymentAccount, Refund, and Audit models; marshmallow schemas for serialization; pytz for timezone handling; enums for RoutingSlipStatus and PaymentMethod; constants including DT_SHORT_FORMAT. No model implementation code provided.

=== pay-api/src/pay_api/schemas/__init__.py ===

Marks the payment API schemas directory as a Python package; no exports or configuration defined.

=== pay-api/src/pay_api/services/__init__.py ===

Package initializer re-exporting service classes for pay-api. Imports 22 service modules including cfs_service, distribution_code, eft_service, eft_short_name_historical, eft_short_name_summaries, eft_short_names, fee_schedule, hashing, internal_pay_service, invoice, non_sufficient_funds, payment, payment_service, payment_transaction, receipt, refund, report_service, statement, statement_recipients, statement_settings, flags, and gcp_queue. From eft_short_name_historical, also re-exports EFTShortnameHistory and EFTShortnameHistorySearch. Six class names are aliased on import: EFTShortnameHistorical→EFTHistoryService, EFTShortnames→EFTShortNamesService, EFTShortnameSummaries→EFTShortNameSummaryService, Invoice→InvoiceService, PaymentTransaction→TransactionService, Receipt→ReceiptService.

=== pay-api/src/pay_api/services/base_payment_system.py ===

Abstract base class defining the interface for payment system processors that handle transactions, invoices, and receipts across different payment methods and account types. Apache 2.0 license. Imports indicate it orchestrates between payment models (CfsAccount, Invoice, PaymentTransaction, Receipt, Credit), services (CFSService, PaymentAccount, Payment), and external systems (GCP queue publisher via QueueMessageTypes, Sentry error capture). Supports multiple payment statuses, methods, and invoice reference states; operates within Flask application context.

**Note:** The file shows only imports and docstring; implementation methods not visible in provided content.

=== pay-api/src/pay_api/services/direct_pay_service.py ===

Defines data structures for parsing PAYBC Direct Pay order status responses and refund operations.

RefundLineRequest holds revenue_account (str), refund_amount (Decimal), and is_service_fee (bool). RefundData captures refundglstatus (Optional[PaymentDetailsGlStatus]) and refundglerrormessage (str). RevenueLine represents one line: linenumber (str), revenueaccount (str), revenueamount (Decimal), glstatus (str), glerrormessage (Optional[str]), and refund_data (List[RefundData]). OrderStatus aggregates the response: revenue (List[RevenueLine]), postedrefundamount (Optional[Decimal]), refundedamount (Optional[Decimal]), paymentstatus (Optional[str]). Constants: PAYBC_DATE_FORMAT = '%Y-%m-%d', PAYBC_REVENUE_SEPARATOR = '|', DECIMAL_PRECISION = '.2f', STATUS_PAID = ('PAID', 'CMPLT').

=== pay-api/src/pay_api/services/distribution_code.py ===

Service module for managing fee calculations through distribution codes. Imports models: DistributionCode, DistributionCodeLink, Invoice; schemas: DistributionCodeSchema, FeeScheduleSchema; utilities: date parsing, timezone handling, Flask app context, ServiceTracing. Implementation body not provided in content chunk.

=== pay-api/src/pay_api/services/eft_service.py ===

Service for applying CFS EFT credits to invoices: extends DepositService to manage EFTCredit, Invoice, Payment, Statement, and Receipt entities. Links credits to invoices via EFTCreditInvoiceLink and manages status transitions using CfsAccountStatus, EFTCreditInvoiceStatus, InvoiceStatus, PaymentStatus, PaymentMethod, PaymentSystem enums. Includes refund handling via EFTRefund, historical short name tracking via EFTShortnamesHistorical, and email notifications. Only class definition and imports visible; no method implementations shown.

=== pay-api/src/pay_api/services/ejv_pay_service.py ===

Manages EJV (Electronic Journal Voucher) payments for government accounts by creating invoice references and requesting refunds based on account billability.

In create_invoice: if payment_account.billable is False, creates InvoiceReference via InvoiceReference.create(invoice.id, generate_transaction_number(invoice.id), None); if True, does nothing. In complete_post_invoice: checks if invoice_reference and invoice_reference.status_code == InvoiceReferenceStatus.ACTIVE; if so calls complete_payment(invoice, invoice_reference); regardless, calls _release_payment(invoice=invoice). In process_cfs_refund: if not payment_account.billable returns REFUNDED; if invoice.invoice_status_code == APPROVED, checks InvoiceReference.find_active_reference_by_invoice_id(invoice.id) — returns REFUND_REQUESTED if found, CANCELLED if not; otherwise returns REFUND_REQUESTED.

GOTCHA: Billable accounts skip reference creation in create_invoice; comment indicates references created elsewhere.
GOTCHA: complete_post_invoice unconditionally calls _release_payment() regardless of invoice_reference status check.
GOTCHA: Refunds not processed here; docstring says CRON job handles actual refund processing.

=== pay-api/src/pay_api/services/fas/__init__.py ===

Initialization file that exposes services used in the FAS module. Re-exports RoutingSlipService from .routing_slip and CommentService from .comment, making both available to package consumers.

=== pay-api/src/pay_api/services/fas/routing_slip.py ===

Service module managing routing slip operations in the payment system. Works with routing slip, payment, and payment account models; orchestrates status transitions via RoutingSlipStatusTransitionService; integrates OAuth authentication and role-based access control. Supports multiple payment methods (PaymentMethod), systems (PaymentSystem), and account statuses (CfsAccountStatus, RoutingSlipStatus, PaymentStatus). Includes patch actions (PatchActions) for updates, various authorization types (AuthHeaderType, Role), and response formatting (ContentType). Error handling via BusinessException and Error; utilities for time conversion (get_local_time), decimal quantization (get_quantized), date parsing (string_to_date), and user context management (UserContext, user_context decorator).

Service for routing slip lifecycle in a payment system: creates them with linked payments, links parent-child relationships, and updates status with role-based rules.

**Inputs**: `create` takes request_json with routing slip number, payments array (paymentMethod, paidAmount, paidUsdAmount, chequeReceiptNumber, paymentDate), paymentAccount.accountName, routingSlipDate. `do_link` takes rs_number and parent_rs_number. `update` takes rs_number, action (patch action enum), and request_json with status or payments.

**Outputs**: All return the routing slip as dict/RoutingSlipModel via find_by_number().

**Flow**: `create` validates slip number uniqueness via validate_and_find_by_number(), enforces all payments share one paymentMethod, enforces CHEQUE payments have paymentDate, creates PaymentAccountModel and CfsAccountModel (INTERNAL method, PENDING status), sums paidAmount and paidUsdAmount across payments, creates RoutingSlipModel with totals, creates one PaymentModel per payment, commits. `do_link` validates both slips exist, runs _validate_linking(), sets parent_number and status=LINKED, transfers remaining_amount from child to parent (child becomes 0), commits child only. `update` validates action enum, finds slip, then if UPDATE_STATUS: validates status transition and user role via _check_roles_for_status_update(); on NSF, negates and adds total_paid_to_reverse (sum of slip and all children totals); on VOID, raises RS_HAS_TRANSACTIONS if slip.invoices exist, else zeroes remaining_amount; on CORRECTION, requires payments array, calculates correction total via _calculate_correction_and_comment() (updates payment.paid_amount and paid_usd_amount, creates comment), adds correction to totals, then resets status to COMPLETE if remaining_amount==0 else ACTIVE if CfsAccountModel is PENDING or absent.

GOTCHA: In do_link, parent_routing_slip amount is modified but only routing_slip.commit() called—parent changes may not persist. GOTCHA: In _calculate_correction_and_comment(), `next(x for x in payments if...)` raises StopIteration if payment ID not found instead of proper error.

Validates routing slip linking (parent-child relationships) and routing slip number format.

For linking validation: child `routing_slip` cannot already be linked (`parent` field set or status equals LINKED), cannot be a parent (has children via `find_children`), and cannot self-link (`routing_slip.number` != `parent_rs_slip.number`). Parent cannot already be linked. Child cannot have `invoices` and cannot have NSF status. Both fail if status is REFUND_REQUESTED, REFUND_AUTHORIZED, REFUND_COMPLETED, WRITE_OFF_REQUESTED, WRITE_OFF_AUTHORIZED, WRITE_OFF_COMPLETED, COMPLETE, VOID, or CORRECTION. Raises `BusinessException` with constants: RS_ALREADY_LINKED, RS_ALREADY_A_PARENT, RS_PARENT_ALREADY_LINKED, RS_CANT_LINK_TO_SAME, RS_CHILD_HAS_TRANSACTIONS, RS_CANT_LINK_NSF, RS_IN_INVALID_STATUS.

Routing slip number validation requires `rs_number` to be exactly 9 digits. Checksum: for every 2nd digit in first 8 positions, multiply by 2 (if >9, sum the two digits); sum all 8 modified digits; calculate `(10 - (sum % 10)) % 10`; 9th digit must equal this value or raises FAS_INVALID_ROUTING_SLIP_DIGITS.

GOTCHA: `_is_linked_already` checks both `parent` field and `status == RoutingSlipStatus.LINKED.value`—these could drift out of sync.  
GOTCHA: Child `invoices` existence checked before linking, but parent `invoices` not checked.

=== pay-api/src/pay_api/services/fas/routing_slip_status_transition_service.py ===

Manages routing slip status machine transitions, preventing invalid state changes and self-approval.

`get_possible_transitions(rs_model)` looks up allowed successor statuses in `STATUS_TRANSITIONS` dict. If the result includes `REFUND_AUTHORIZED.value` and requesting user matches `refund_model.requested_by`, returns `transition_list[1:]` to remove self-approval; same logic for `WRITE_OFF_AUTHORIZED.value` against `rs_model.updated_by`. `validate_possible_transitions(rs_model, future_status)` raises `BusinessException(Error.FAS_INVALID_RS_STATUS_CHANGE)` if future status is not in allowed transitions. `get_actual_status(status)` unwraps custom status enums to `original_status`.

GOTCHA: Self-approval prevention assumes the authorization transition is at index 0 in STATUS_TRANSITIONS lists; reordering would cause wrong item to be filtered.

=== pay-api/src/pay_api/services/gcp_queue/__init__.py ===

Module initialization that exports a GcpQueue singleton instance. Imports GcpQueue and creates a module-level queue object for dependency injection across the application. No logic or decisions.

=== pay-api/src/pay_api/services/internal_pay_service.py ===

Service for internal payments (zero-dollar or staff-approved) with optional routing-slip prepaid-balance tracking.

`create_invoice()` checks `invoice.routing_slip`. If present, retrieves RoutingSlipModel and validates via `_validate_routing_slip()`. For non-zero with slip: deducts from `routing_slip.remaining_amount`; if status ACTIVE and balance < 0.01, marks COMPLETE. For zero-dollar or slip-less paths: creates InvoiceReference with `generate_transaction_number()`, sets `invoice.invoice_status_code` to CREATED. Slip-only path returns None; external CFS job sets invoice status later.

`complete_post_invoice()`: if `invoice.invoice_status_code` ≠ APPROVED, calls `complete_payment()` then `_release_payment()` to publish queue message.

`get_receipt()`: returns (invoice_number, UTC datetime.now(), invoice.total).

`get_default_invoice_status()`: returns APPROVED.

`process_cfs_refund()`: requires non-zero invoice.total and invoice.routing_slip. Validates routing slip exists and status in (ACTIVE, COMPLETE). Sets related payment `payment_status_code` to REFUNDED, increments `routing_slip.remaining_amount`, reverts slip to ACTIVE if was COMPLETE, sets `invoice.invoice_status_code` to REFUND_REQUESTED.

`_validate_routing_slip()`: if slip None, checks ALLOW_LEGACY_ROUTING_SLIPS config. Enforces status in (ACTIVE, LINKED, NSF, CORRECTION); if NSF, requires remaining_amount > 0; forbids parent slip; requires remaining_amount ≥ invoice.total.

GOTCHA: `process_cfs_refund()` checks `invoice.total == 0` twice (redundant).
GOTCHA: Slip-path in `create_invoice()` returns None; invoice.invoice_status_code set by external job.

=== pay-api/src/pay_api/services/invoice.py ===

Service module for managing invoices in a payment API system (Apache 2.0 licensed, Province of British Columbia). 

The chunk provided contains only imports and license header, not the implementation. Based on dependencies: manages `InvoiceModel` and `PaymentAccountModel` objects; integrates with `CfsAccount` (CFS accounting integration); handles authentication via `check_auth` with roles from `ALL_ALLOWED_ROLES`; uses `InvoiceStatus`, `PaymentMethod`, and `InvoiceReferenceStatus` enums; depends on `CodeService` and `OAuthService` for code lookups and OAuth flows; generates transaction numbers and formatted dates via utilities; raises `BusinessException` for errors.

**Cannot assess main flow, decision points, or gotchas without method implementations.**

=== pay-api/src/pay_api/services/payment.py ===

Service module for Payment model operations in a payment processing system. Integrates with CfsAccount, Invoice, EFT transaction models and external services (CFSService, OAuthService, ReportService). Defines PaymentReportInput dataclass to structure payment report parameters: requires content_type (str), report_name (str), template_name (str), results (dict); optionally accepts statement_summary (dict) and eft_transactions (List[EFTTransactionModel]) for transaction details. Apache 2.0 license. Chunk shows imports and dataclass definition only; main service methods not shown.

=== pay-api/src/pay_api/services/payment_account.py ===

Service to manage Payment Account operations with CFS payment system and queue integration. PaymentDetails dataclass holds payment context: account_request (Dict[str, Any]), is_sandbox (bool), pay_system (PaymentSystemService), payment_account (PaymentAccountModel), payment_info (Dict[str, Any]), previous_payment (str). Imports and dataclass definition only—service methods not shown in this excerpt.

Service class that sets up payment accounts across multiple payment systems (PayBC, CGI) and manages PAD activation, account fees, and statement settings.

`_handle_payment_details` routes by payment_system_code: PayBC finds or creates CfsAccountModel with contact_info and payment_info, then updates PAD activation; CGI end-dates any active DistributionCode (end_date = datetime.now - timedelta(days=1)) and saves revenue account as new DistributionCode; other systems deactivate pending PAD CfsAccountModel if multiple-payment-methods flag is False.

`_update_pad_activation_date` sets status ACTIVE and pad_activation_date = datetime.now(tz=timezone.utc) if is_sandbox; else calls _get_payment_based_on_pad_activation to apply payment method and activation timing.

`_get_payment_based_on_pad_activation` determines payment_method and activation_date: on first PAD (pad_activation_date missing), returns (PAD.value or previous_payment, calculated date); on repeat, if previous activation_date passed, returns (PAD.value, unchanged); within activation window, returns (PAD.value or previous_payment, unchanged).

Fee operations: save/get/delete AccountFeeModel by account_id and product; _create_or_update_account_fee persists apply_filing_fees and service_fee_code.

`_persist_default_statement_frequency` creates StatementSettingsModel with frequency = MONTHLY for EFT.value, else default.

GOTCHA: PAD accounts have 3-day production activation wait; previous_payment override bypasses it.
GOTCHA: Pending PAD accounts forced to INACTIVE status—"If we don't set this to INACTIVE the PAD job will automatically switch our payment method for us."
GOTCHA: CfsAccountModel.create_account can return None (pylint disabled); execution continues.

=== pay-api/src/pay_api/services/payment_service.py ===

I have only the file header and imports section, not the actual class implementation. To provide the condensed summary you're asking for—describing what comes in, what goes out, the main flow, and every decision the code makes—I need the full file content including the `PaymentService` class definition and its methods.

Could you provide the complete file, or is this header section the entire content you meant to condense?

=== pay-api/src/pay_api/services/payment_transaction.py ===

I only have the file header and imports from what you provided. Without seeing the actual class definition and methods in `payment_transaction.py`, I cannot provide an accurate summary of its purpose, inputs, outputs, main flow, and decision logic. Please share the complete file content.

=== pay-api/src/pay_api/services/refund.py ===

I received only the license header, module docstring, and import statements. The actual implementation code (class definitions, methods, and logic) is missing, so I cannot provide the condensation as specified. Please provide the complete file contents including the service class and its methods.

=== pay-api/src/pay_api/services/statement.py ===

Statement service class managing all statement-related operations in a payment processing system, working with invoices, payments, EFT transactions, and credits.

Imports indicate inputs: EFTCreditModel, EFTTransactionModel, InvoiceModel, PaymentModel, PaymentAccountModel, StatementModel and StatementSettingsModel; outputs shaped by StatementModelSchema. Dependencies: PaymentService (imported as PaymentService), database access via SQLAlchemy with PostgreSQL dialect features (ARRAY, INTEGER), and utility functions get_first_and_last_of_frequency and get_local_time. Enum constants available for decision points: StatementFrequency (recurrence patterns), EFTProcessStatus, InvoiceStatus, PaymentMethod, NotificationStatus, ContentType. The class body is truncated; no method flows shown in this chunk.

=== pay-api/src/pay_api/utils/enums.py ===

Enumeration configuration defining status, method, and classification constants for payment processing.

Defines 40+ enums organizing: payment/invoice/transaction/refund lifecycles (PaymentStatus: CREATED, COMPLETED, DELETED, REFUNDED, FAILED; InvoiceStatus: GL_UPDATED, GL_UPDATED_REFUND, SETTLEMENT_SCHED, PARTIAL_PAID, OVERDUE, etc.); payment methods (PaymentMethod: CC, DRAWDOWN, EFT, WIRE, ONLINE_BANKING, PAD, EJV, CASH, CHEQUE) and systems (PaymentSystem: PAYBC, BCOL, INTERNAL, CGI, FAS); user roles (Role: STAFF, VIEWER, EDITOR, SYSTEM, CREATE_SANDBOX_ACCOUNT, MANAGE_GL_CODES, EXCLUDE_SERVICE_FEES, CREATE_CREDITS, MANAGE_ACCOUNTS, plus FAS-specific and EFT-specific roles); routing slip workflow (RoutingSlipStatus with HOLD marked new; RoutingSlipCustomStatus maps cancellation actions to ACTIVE via from_key() returning None if not found); EFT operations (EFTHistoricalTypes, EFTShortnameStatus, EFTPaymentActions: CANCEL, REVERSE, APPLY_CREDITS); disbursements (DisbursementMethod: EFT, CHQ); and others (AuthHeaderType, ContentType, CfsAccountStatus, NotificationStatus, AccountType, CorpType, Product, etc.). StatementFrequency.default_frequency() returns WEEKLY. PatchActions.from_value() returns None if value not in _value2member_map_.

GOTCHA: EFTHistoricalTypes combines transaction types (FUNDS_RECEIVED, INVOICE_REFUND, STATEMENT_PAID, STATEMENT_REVERSE) with shortname refund statuses (SN_REFUND_PENDING_APPROVAL, SN_REFUND_APPROVED, SN_REFUND_DECLINED).
GOTCHA: PaymentDetailsGlStatus.RJCT has inline comment "Should have refundglerrormessage", indicating missing validation.

=== pay-api/src/pay_api/utils/paybc_transaction_error_message.py ===

Configuration file: maps PayBC payment error messages to UI-consumable status codes.

PAYBC_TRANSACTION_ERROR_MESSAGE_DICT translates raw PayBC error message strings into standardized codes for UI consumption. Converts PayBC's mixed-case messages to snake_case codes: 'PLEASE TRY AGAIN' → 'PLEASE_TRY_AGAIN', 'DECLINED'/'DECLINE' → 'DECLINED', 'INVALID CARD NUMBER' → 'INVALID_CARD_NUMBER', 'APPLICATION ERROR - SENDING REQUEST' → 'APPLICATION_ERROR_SENDING_REQUEST', 'CALL FOR AUTH' → 'CALL_FOR_AUTH', 'TRANSACTION TIMEOUT - NO AVAILABLE DEVICE' → 'TRANSACTION_TIMEOUT_NO_DEVICE', 'RESPONSE FROM BEANSTREAM IS INVALID DUE TO MODIFICATIONS OF PARAMETERS SENT' → 'BEANSTREAM_INVALID_RESPONSE', 'VALIDATION ERROR' → 'VALIDATION_ERROR', 'PAYMENT CANCELED' → 'PAYMENT_CANCELLED', 'DUPLICATE ORDER NUMBER - THIS ORDER NUMBER HAS ALREADY BEEN PROCESSED' → 'DUPLICATE_ORDER_NUMBER', 'APPROVED' → 'APPROVED', 'DECLINED EXPIRED CARD' → 'DECLINED_EXPIRED_CARD'.

GOTCHA: 'PAYMENT CANCELED' input becomes 'PAYMENT_CANCELLED' output with spelling change.
