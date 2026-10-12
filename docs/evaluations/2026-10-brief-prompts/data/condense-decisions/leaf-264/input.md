=== pay-api/src/pay_api/services/distribution_code.py ===

Service encapsulating a distribution code with five accounting dimensions (client, responsibility_centre, service_line, stob, project_code) plus optional linked service-fee distribution code and validity dates. Wraps DistributionCodeModel DAO with lazy initialization.

When _dao is set: mirrors all attributes from model; if model holds service_fee_distribution_code_id, loads that related DistributionCodeModel and caches its five dimensions (prefixed service_fee_*) and name.

Properties expose and update individual fields. Five setters (name, project_code, service_fee_client, stop_ejv, account_id) check whether value differs before syncing to DAO; others (client, responsibility_centre, service_line, stob) sync unconditionally. Date setters (start_date, end_date) always sync.

Static methods: find_all() queries all DistributionCodeModel rows and serializes via DistributionCodeSchema; find_by_id(id) returns one serialized row; find_active_by_account_id(account_id) fetches active code for account and wraps in new service instance.

GOTCHA: service_fee_* property setters (stob, line, responsibility_centre, name, project_code) update only instance variables, never _dao — changes will not persist.
GOTCHA: Changing service_fee_distribution_code_id via setter does not reload related service-fee dimensions; reload occurs only when entire _dao is replaced.
GOTCHA: Inconsistent change detection across setters — five check equality, others do not.
GOTCHA: Docstring for service_fee_line property says "Return the service_fee_centre" (incorrect).

Manages distribution codes (financial allocations) in the payment system: saves or updates them, links them to fee schedules, and cascades invoice-revenue updates when allocation components change.

**Input**: distribution_details dict with client, responsibilityCentre, serviceLine, projectCode, stob, serviceFeeDistributionCodeId, disbursementDistributionCodeId, accountId, startDate (optional), endDate (optional); distribution_id for updates; fee_schedules list with feeScheduleId.

**Output**: Serialized distribution code objects or lists of fee schedules via DistributionCodeSchema.

**Flow**: `save_or_update` loads existing record if dist_id provided, parses dates (defaults startDate to today UTC if omitted), assigns all fields, checks if client/responsibilityCentre/serviceLine/projectCode/serviceFeeDistributionCodeId changed. If changed AND updating: calls InvoiceModel.update_invoices_for_revenue_updates on this dist_id and on all distributions using this as their service fee distribution. Resets stop_ejv to False, saves. `find_fee_schedules_by_distribution_id` queries and serializes. `create_link` creates DistributionCodeLinkModel entries and bulk-saves.

**Decision**: Cascade invoice updates trigger only on existing records with code changes, not on creation.

GOTCHA: Comment "Reset stop jv for every dave" appears to be a typo (should be "save").

=== pay-api/src/pay_api/services/eft_short_names.py ===

Builds SQLAlchemy queries to search EFT short names with linked payment accounts, statements and invoices, filtering on link status, account details, and amounts owing.

Main flow: `get_search_query()` assembles a base query on EFTShortnameModel, joins a links subquery (EFTShortnameLinksModel with PaymentAccountModel and CfsAccountModel), then joins a statement summary subquery (grouped invoices by payment_account_id, excluding CANCELLED/REFUND_REQUESTED/REFUNDED statuses, filtering to EFT method only). Filters apply conditionally based on `search_criteria` parameters: statement_id, amount_owing, account_id, account_name, account_branch, short_name, type. If is_count=False, adds payment columns (account_name with branch stripped if concatenated via "-", account_branch, total_owing, latest_statement_id); if is_count=True, skips these joins. Link state filtering: UNLINKED matches short names with no links having status != UNLINKED; LINKED matches status in [PENDING, LINKED]. Amount_owing==0 matches 0 OR NULL; other amounts match exactly. Results ordered by short_name, auth_account_id.

GOTCHA: Branch name is concatenated to account name for reporting ("name-branch"), then regex-stripped for filtering; mismatch causes filters to fail silently. Links subquery uses DISTINCT(auth_account_id) with ORDER BY updated_on DESC, keeping only the most recent link per account per short name.

=== pay-api/src/pay_api/services/fas/comment.py ===

Service to create and retrieve comments attached to routing slips in the payment system, validating that the routing slip exists before any operation.

**Inputs:** `create()` takes comment text and routing slip number; `find_all_comments_for_a_routingslip()` takes routing slip number.

**Outputs:** `create()` returns comment as dict; `find_all_comments_for_a_routingslip()` returns dict with 'comments' key holding list of comment dicts.

**Main flow:** Both methods check if routing slip exists via `RoutingSlipModel.find_by_number()`. If not found, raise `BusinessException(Error.FAS_INVALID_ROUTING_SLIP_NUMBER)`. Create validates, then constructs `CommentModel` with comment text and routing_slip_number, calls `flush()` then `commit()`, returns serialized dict. Find retrieves all comments via `CommentModel.find_all_comments_for_a_routingslip()`, serializes via `CommentSchema`, returns wrapped in dict.

**State:** Service wraps a `CommentModel` DAO; maintains synced instance properties (_id, _comment, _timestamp, _routing_slip_number, _submitter_name) that mirror DAO fields through dual-direction property setters.

=== pay-api/src/pay_api/services/fas/routing_slip.py ===

Service class managing routing slip (payment receipt) state and persistence through a DAO. Initializes with lazy-loaded RoutingSlipModel; properties (id, number, payment_account_id, status_code, total, remaining_amount, total_usd) sync bidirectionally with DAO via getter/setter. 

Inputs: routing slip fields (strings, ints, Decimals). Outputs: search() returns dict with page, limit, total, items (serialized subset). create_daily_reports() aggregates daily totals by payment method and currency: queries routing slips for a date (excluding VOID status), then for each slip decides: if payment_account.payment_method == PaymentMethod.CASH.value, increment no_of_cash by 1, else increment no_of_cheque by len(routing_slip.payments). For both paths, if total_usd is not None, add to corresponding USD totals. Sends aggregated report dict to OAuthService.post(). validate_and_find_by_number() checks config ALLOW_LEGACY_ROUTING_SLIPS: if false, validates number digits, then calls find_by_number(). find_by_number() deserializes slip and populates allowedStatuses via RoutingSlipStatusTransitionService. get_links() returns parent and children routing slips. commit(), flush(), rollback(), save() delegate to DAO.

GOTCHA: Cheque count uses len(routing_slip.payments) per slip; cash count is 1 per slip—asymmetry if slips contain multiple payments.
GOTCHA: remaining_amount setter docstring says "Set the amount", not "Set the remaining_amount".
GOTCHA: USD totals remain zero if any slip has total_usd = None.

=== pay-api/src/pay_api/services/fee_schedule.py ===

Manages and calculates fees for business filings by corp type and filing type, supporting account-level overrides and multiple fee surcharges.

**Input:** corp_type and filing_type_code (both required), valid_date, and optional kwargs: quantity, is_priority, is_future_effective, waive_fees. **Output:** FeeSchedule object with calculated Decimal amounts for fee_amount, priority_fee, future_effective_fee, service_fees, waived_fee_amount; total property sums all to produce final bill.

**Main flow:** find_by_corp_type_and_filing_type looks up FeeScheduleModel by corp/filing type and date; raises BusinessException(Error.INVALID_CORP_OR_FILING_TYPE) if missing or both inputs absent. Creates FeeSchedule, applies quantity multiplier. Checks AccountFeeModel for account-level fee overrides; if account_fee exists and apply_filing_fees is False, sets fee_amount and waived_fee_amount to 0. Applies surcharges: if is_priority and fee_schedule_dao.priority_fee and apply_filing_fees, adds priority_fee; if is_future_effective and fee_schedule_dao.future_effective_fee and apply_filing_fees, adds future_effective_fee. If waive_fees flag set, zeros fee_amount, priority_fee, future_effective_fee, and service_fees.

**Properties delegate to FeeScheduleModel DAO; gst and pst always return 0.** 

GOTCHA: quantity setter multiplies fee_amount in-place—successive calls multiply repeatedly. fee_end_date setter typed as str but property expects date.

=== pay-api/src/pay_api/services/invoice.py ===

Service wrapping an InvoiceModel DAO that maintains internal state synchronized with the database. Lazy-loads the DAO on first access via the _dao property. All 21 properties (id, payment_method_code, invoice_status_code, payment_account_id, bcol_account, refund, payment_date, refund_date, total, paid, payment_line_items, corp_type_code, receipts, routing_slip, filing_id, folio_number, service_fees, business_identifier, dat_number, cfs_account_id, details, created_on) sync bidirectionally to the DAO when set. find_by_id(identifier, skip_auth_check=False, one_of_roles=ALL_ALLOWED_ROLES) queries InvoiceModel by id, raises BusinessException(Error.INVALID_INVOICE_ID) if not found, calls _check_for_auth() against one_of_roles unless skip_auth_check=True, returns wrapped Invoice. asdict(include_dynamic_fields=False) serializes via InvoiceSchema, optionally adding dynamic fields. populate() wraps a DAO. Delegates save(), commit(), flush(), rollback() to DAO.

GOTCHA: total property setter docstring says "Set the fee_start_date" but actually sets total.
GOTCHA: business_identifier declared as str but setter expects int.
GOTCHA: details declared as Dict but setter docstring says str.
GOTCHA: _dao setter performs multiple property assignments; if any fails, partial state persists.

Provides invoice operations for a payment system: PDF generation, retrieval by payment or business identifier, and overdue status checking.

create_invoice_pdf(identifier, user_context) retrieves InvoiceModel by id (raises BusinessException.INVALID_INVOICE_ID if missing), fetches PaymentAccountModel and CfsAccountModel, calls OAuthService to get org and contact info from AUTH_API_ENDPOINT, determines invoice_number from references[0].invoice_number or generates via generate_transaction_number(), constructs filing_types array from payment_line_items (businessIdentifier becomes empty string if starts with 'T'), posts template to REPORT_API_BASE_URL with invoiceNumber, fees, total, gst, serviceFees, filingTypes, and accountContact, returns (pdf_response, reportName).

find_invoices_for_payment(payment_id, reference_status=ACTIVE) wraps InvoiceModel DAOs in Invoice objects; find_invoices(business_identifier) returns {'invoices': [Invoice.asdict(),...]}; has_overdue_invoices(payment_account_id) checks if any InvoiceModel.invoice_status_code equals OVERDUE; _add_dynamic_fields(invoice, calculate_dynamic_fields) conditionally adds is_payment_action_required=true (when status_code=CREATED and payment_method in DIRECT_PAY/CC/ONLINE_BANKING) and is_online_banking_allowed from CodeService query (set false if any line_item.future_effective_fees != 0).

GOTCHA: business_identifier cleared to empty string when starts with 'T' — purpose unclear
GOTCHA: org_contact defaults to {} when contacts array missing; subsequent .get('city') etc. could fail
GOTCHA: Debug logs '>find_by_id' and '>OAuthService responded to receipt.py' don't match function and file names

=== pay-api/src/pay_api/services/invoice_reference.py ===

Service managing invoice reference operations: creates, retrieves by invoice_id or invoice_number, and persists to database.

Creates a new reference via `create(invoice_id, invoice_number, reference_number)` with status set to `InvoiceReferenceStatus.ACTIVE.value`, saves to DB via `ReferenceModel.save()`. Retrieves existing references using static methods: `find_active_reference_by_invoice_id()` or `find_completed_reference_by_invoice_id()` (filtered by status via `ReferenceModel.find_by_invoice_id_and_status()`) or `find_any_active_reference_by_invoice_number()` (via `ReferenceModel.find_any_active_reference_by_invoice_number()`). Returns `InvoiceReference` instance or None. Properties (id, invoice_id, invoice_number, reference_number, status_code) sync bidirectionally with underlying `ReferenceModel` DAO via `_dao` property getter/setter.

GOTCHA: `find_completed_reference_by_invoice_id()` and `find_any_active_reference_by_invoice_number()` assign the DAO without checking if it is None, unlike `find_active_reference_by_invoice_id()`.

=== pay-api/src/pay_api/services/non_sufficient_funds.py ===

Service to manage Non-Sufficient Funds (NSF) records and generate statements for invoices with insufficient payment processing.

Accepts invoice_id, invoice_number, cfs_account, and description; saves NSF records linked to invoices. Queries all unpaid NSF invoices for an account via `query_all_non_sufficient_funds_invoices()` which joins Invoice, InvoiceReference, NonSufficientFunds, PaymentAccount, and PaymentLineItem tables, filtering by `auth_account_id` and excluding `InvoiceStatus.PAID`. Aggregates amounts using subqueries: calculates `amount_remaining` (invoice total minus paid), `nsf_amount` (max PaymentLineItem.total where description equals `ReverseOperation.NSF.value`), and combined totals. Returns invoices as InvoiceSearchModel, statements, and three aggregate floats: `total_amount`, `total_amount_remaining`, `nsf_amount`. For PDF generation, fetches account and CFS account details via OAuth calls, formats template variables including conditionally-formatted `suspendedOn` date, posts to `REPORT_API_BASE_URL` with template name `'non_sufficient_funds'`.

GOTCHA: `create_non_sufficient_funds_statement_pdf()` accesses `invoice['invoices'][0]['id']` without bounds checking—will crash if no invoices returned.

=== pay-api/src/pay_api/services/payment.py ===

Manages payment records for accounts, grouping related invoices per payment. Tracks: id, payment_system_code, payment_method_code, payment_status_code, payment_account_id, invoice_number, cons_inv_number, payment_date, invoice_amount, paid_amount, receipt_number, created_by, paid_usd_amount (all synced to underlying PaymentModel DAO). create() takes payment_method, payment_system (strings), optional payment_status (defaults PaymentStatus.CREATED.value), invoice_number, invoice_amount, payment_account_id; creates, saves, returns Payment. find_by_id() retrieves by id. search_account_payments() takes auth_account_id, status, page, limit; queries, groups (payment, invoice) result tuples by payment.id, returns dict with 'total', 'page', 'limit', 'items' (each item: payment dict with 'invoices' array). GOTCHA: search_account_payments assumes results ordered by payment.id for correct grouping.

Retrieves account purchase history, formats invoice data, and generates payment reports in CSV or PDF format.

**Inputs/Outputs**: auth_account_id, search_filter (Dict), page, limit, content_type → paginated dict {total, page, limit, items}; report response.

**Flow**:

search_purchase_history(): If search_filter empty or all values falsy, max_no_records = TRANSACTION_REPORT_DEFAULT_TOTAL config value; else 0. Query PaymentModel. Call create_payment_report_details() to convert purchases via Converter.unstructure/remove_nones. Return paginated dict.

generate_payment_report(): Fetch invoice status_code descriptions from CodeService.find_code_values_by_type(Code.INVOICE_STATUS.value); replace each invoice status_code with matching description. **Decision**: If content_type == ContentType.CSV.value, call _prepare_csv_data() for template; else fetch account contacts from AUTH_API_ENDPOINT and prepare PDF template with account info. Call ReportService.get_report_response().

get_invoices_totals(): Sum total, statutoryFees (total - service_fees), serviceFees, paid; calculate due (total - paid); format created_on dates.

_prepare_csv_data(): Per invoice, sum gst/pst from line_items; build comma-joined descriptions; format row values.

GOTCHA: search_purchase_history() silently caps unfiltered requests to TRANSACTION_REPORT_DEFAULT_TOTAL, overriding return_all parameter.

GOTCHA: generate_payment_report() accesses contact['contacts'][0] without checking length—IndexError if empty.

=== pay-api/src/pay_api/services/payment_account.py ===

Service layer for payment account operations: retrieves accounts, searches EFT accounts, serializes account data with conditional CFS bank details, and publishes queue events for account creation notifications.

**Inputs & outputs:** `find_by_id(account_id)` returns PaymentAccount wrapping PaymentAccountModel; `search_eft_accounts(search_text)` queries PaymentAccountModel joined to CfsAccountModel, filters by payment_method=EFT, CFS status in [ACTIVE, PENDING], eft_enable=True, searches auth_account_id/name/branch_name with wildcards, orders by exact match then ID descending, limits 20 results, returns unstructured dict; `asdict()` returns account dict with conditional cfs_account sub-object; `create_account_event_payload(event_type, receipt_info, include_pay_info)` returns dict with accountId, accountName, and event-specific fields.

**Main decisions:** `asdict()` includes CFS details if payment_method in [PAD, ONLINE_BANKING, EFT] OR if DRAWDOWN with PAD in pending activation—shows future CFS for PAD, current for others. Masks bank_account_number based on user role (user.can_view_bank_account_number()); includes bank details only if user.is_system() or user.can_view_bank_info(). For EJV method, includes DistributionCode; includes AccountFeeSchema if fees exist. `_is_pad_in_pending_activation()` returns true if pad_activation_date is in future and future CFS status in [PENDING, PENDING_PAD_ACTIVATION]. `_calculate_activation_date()` adds PAD_CONFIRMATION_PERIOD_IN_DAYS + 1 days, rounds to 00:00:00, converts to UTC. `publish_account_mailer_event_on_creation()` publishes queue message only for PAD. `create_account_event_payload()` branches: NSF_UNLOCK_ACCOUNT adds invoiceNumber, receiptNumber, paymentMethodDescription, invoice; PAD_ACCOUNT_CREATE adds padTosAcceptedBy; include_pay_info adds paymentInfo dict with masked bank_account_number.

**GOTCHA:** `_publish_queue_message()` catches all exceptions, logs to current_app.logger and Sentry, but does not re-raise—failures to publish account creation emails are silent.

=== pay-api/src/pay_api/services/payment_line_item.py ===

Service that creates and manages payment line items for business filings, tracking filing fees, priority fees, service fees, taxes (GST, PST), waivers, and distribution codes.

**Input:** `create()` takes `invoice_id` and `FeeSchedule` object containing fee_amount, gst, priority_fee, pst, future_effective_fee, waived_fee_amount, service_fees, quantity, fee_schedule_id, description. **Output:** PaymentLineItem instance with properties synced to internal PaymentLineItemModel DAO.

**Flow:** Sets quantity to 1 if not provided; initializes line_item_status_code to LineItemStatus.ACTIVE; if total or service_fees > 0, finds active DistributionCode for the fee_schedule_id and sets fee_distribution_id; if waived_fee_amount > 0, checks whether user has Role.STAFF—only staff can set waived_by field, else raises BusinessException(Error.FEE_OVERRIDE_NOT_ALLOWED); flushes DAO to DB; returns new PaymentLineItem wrapping the saved DAO. `find_by_id()` retrieves by line ID. All properties bidirectionally sync with DAO via getters/setters.

**GOTCHA:** fee_distribution stays None if total and service_fees are both ≤ 0, causing potential missing distribution info downstream.

=== pay-api/src/pay_api/services/payment_transaction.py ===

Service managing payment transaction lifecycle: creates and transitions transactions for payments and invoices.

Input: payment_id or invoice_id with request_json (clientSystemUrl, payReturnUrl).
Output: PaymentTransaction with id (uuid), status_code, payment_id (int), client_system_url, pay_system_url, transaction_start_time/end_time (datetime), pay_system_reason_code; serialized via PaymentTransactionSchema.dump().

create_transaction_for_payment(payment_id, request_json): Requires payment exists, status=CREATED, else INVALID_PAYMENT_ID; validates clientSystemUrl.

create_transaction_for_invoice(invoice_id, request_json): Requires invoice exists (else INVALID_INVOICE_ID); raises INVALID_TRANSACTION if payment_method=PAD; creates Payment if absent.

_create_transaction(payment, request_json, invoice=None): Raises COMPLETED_PAYMENT if payment.payment_status_code in (COMPLETED, DELETED); cancels existing PaymentTransactionModel with status!=CANCELLED (status_code→CANCELLED, transaction_end_time→now()); creates new transaction with status_code=CREATED; populates pay_system_url (invoice or payment).

Validates redirect URL only for payment_method in (CC, DIRECT_PAY), else INVALID_REDIRECT_URI.

GOTCHA: Existing active transaction cancelled and saved synchronously before new transaction created.

Manages payment receipts, queries transaction history, and publishes transaction status events to a message queue.

`__save_receipt` persists receipt data: given invoice and receipt_details (receipt_number, receipt_date, receipt_amount), queries for existing Receipt by invoice.id and receipt_number—creates new Receipt if missing or updates date and amount if found—flushes to database and returns the Receipt object.

`find_by_invoice_id` retrieves transaction history: queries PaymentTransactionModel for all transactions matching invoice_id, returns {'items': [array of transaction dicts populated from DAOs]}.

`publish_status` emits transaction status to GCP queue: if transaction_dao.status_code is COMPLETED and invoice.invoice_status_code is PAID, publishes status COMPLETED; if COMPLETED but invoice not PAID, logs and returns (no publish); otherwise publishes TRANSACTION_FAILED. On exception during publish, logs warning and sets transaction_dao.status_code to EVENT_FAILED.

`create_event_payload` formats published message: constructs PaymentToken(invoice.id, status_code, invoice.filing_id, invoice.corp_type_code), converts to dict with camelCase keys via humps.camelize.

GOTCHA: `__save_receipt` uses `if not receipt.id` to distinguish new vs. existing; if id is 0, creates duplicate instead of updating.
GOTCHA: `publish_status` catches Exception broadly, swallowing all errors; queue failures only log warning and mark EVENT_FAILED, never propagated.
GOTCHA: `publish_status` returns silently with no status published when transaction COMPLETED but invoice not PAID—the status update is dropped.

=== pay-api/src/pay_api/services/receipt.py ===

Generates payment receipts by calling a Report API to create PDFs, and retrieves receipt data for display.

**Inputs:** `create_receipt` takes invoice_identifier, filing_data dict with optional fileName, and user bearer token. `get_receipt_details` takes filing_data, invoice_identifier, skip_auth_check flag. `get_nsf_receipt_details` takes payment_id.

**Outputs:** `create_receipt` returns pdf_response from OAuthService. `get_receipt_details` and `get_nsf_receipt_details` return receipt_details dict containing invoiceNumber, receiptNumber, paymentMethod(Description), filingIdentifier, bcOnlineAccountNumber, and nested invoice object (camelcase-formatted with createdOn as local date).

**Flow:** `create_receipt` extracts fileName from filing_data, calls `get_receipt_details` to populate template variables, merges with filing_data, POSTs to REPORT_API_BASE_URL via OAuthService with bearer token. `get_receipt_details` checks if invoice is pending (payment_method_code in PAD/EJV/EFT AND status ≠ PAID); raises error if not pending and no receipts exist; includes routingSlipNumber only if PaymentSystem.INTERNAL; sets receiptNumber to None if pending, otherwise invoice's first receipt number. `get_nsf_receipt_details` finds completed invoices for payment, selects NSF invoice (payment_method_code == CC), combines all other invoices into it (extends payment_line_items and details; sums totals, service_fees, paid); creates synthetic empty Invoice if no CC invoice exists.

GOTCHA: receipt_number setter docstring says "Set the filing_fees" but sets receipt_number. GOTCHA: In `get_nsf_receipt_details`, synthetic NSF Invoice created without full initialization when none exists.

=== pay-api/src/pay_api/services/report_service.py ===

Submits report generation requests to a remote report-api service using OAuth bearer authentication.

ReportRequest dataclass holds five inputs: content_type, report_name, template_name, template_vars, populate_page_number. ReportService.get_request_payload() converts these to a camelCase dictionary (reportName, templateName, templateVars, populatePageNumber). ReportService.get_report_response() (decorated with @user_context to inject the authenticated user's bearer_token) calls OAuthService.post() to send this payload to the REPORT_API_BASE_URL endpoint, using BEARER authentication with JSON request content type and Accept header set to the requested content_type. Returns the raw response from report-api.

=== pay-api/src/pay_api/services/statement.py ===

Statement service: retrieves statements with amount-owing calculations and EFT transaction lookups.

Lazy-loads StatementModel DAO; properties (id, frequency, from_date, to_date, payment_account_id) bidirectionally sync to DAO. Input: statement_id (int), auth_account_id (str), page/limit; Output: statement records with amount_owing computed.

find_by_id queries statement, joins amount_owing from invoices with status PARTIAL/APPROVED/OVERDUE, summed as total−paid. find_by_account_id filters by auth_account_id; if is_owing=True then filters amount_owing > 0; orders by to_date DESC then frequency priority (MONTHLY→1, WEEKLY→2, DAILY→3, default→4); paginates. is_eft_statement returns True if ordered_invoices[0].payment_method_code == EFT or EFT in statement.payment_methods. get_invoices_owing_amount sums unsignalled EFT invoices with status SETTLEMENT_SCHEDULED/APPROVED/OVERDUE (total−paid). get_statement_eft_transactions joins through EFTCredit and EFTCreditInvoiceLink to retrieve COMPLETED transactions. calculate_due_date adds 1 month + 8 hours to target_date, returns ISO string or None.

GOTCHA: payment_account_id setter type-hints str, not int. GOTCHA: frequency setter type-hints int, should match StatementFrequency enum. GOTCHA: calculate_due_date returns None despite str return annotation. GOTCHA: amount_owing attached dynamically post-query, not in schema.

Generates EFT payment statement reports (PDF/CSV) and account financial summaries, tracking invoice balances and underpayment conditions.

**In:** statement_id, auth_account_id, content_type, calculate_under_payment bool; **Out:** (report_response, report_name) tuple; summary dict {total_invoice_due, total_due, oldest_due_date, short_name_links_count, is_eft_under_payment}; statements list.

get_statement_report builds report_name from StatementFrequency—DAILY: 'bcregistry-statements-{from_date}.{ext}', others: 'bcregistry-statements-{from_date}-to-{to_date}.{ext}'—retrieves statement/invoices, constructs PaymentReportInput with template_name=StatementTemplate.STATEMENT_REPORT.value and results from PaymentService.create_payment_report_details, adds statement_summary if is_eft_statement() true, returns PaymentService.generate_payment_report output.

get_summary queries invoices with status in [SETTLEMENT_SCHEDULED, PARTIAL, APPROVED, OVERDUE] and payment_method=EFT, sums (total-paid) as total_due, finds oldest_to_date; sets is_eft_under_payment=true if calculate_under_payment AND active EFTShortnameLinksModel AND 0 < EFTCreditModel.get_eft_credit_balance < owing (from EFTShortnameStatus.LINKED or PENDING short names), else None.

_populate_statement_summary returns {lastStatementTotal, lastStatementPaidAmount from previous statement invoices, latestStatementPaymentDate (max payment_date or None), dueDate}.

populate_overdue_from_invoices sets statement.is_overdue=true if any invoice status=OVERDUE, returns modified statements.

GOTCHA: Invoice status changes after statement generation; is_overdue reflects current statuses, not historical state.

Service for generating interim payment statements when billing frequency changes.

**determine_payment_methods** (inputs: invoice_detail_tuple, pay_account, optional existing_statement; returns: string): Collects payment_method from invoice tuples where auth_account_id matches pay_account.auth_account_id, joins comma-separated. Decision: if no methods found but existing_statement provided → return existing_statement.payment_methods; else → return pay_account.payment_method or empty string.

**generate_interim_statement** (inputs: auth_account_id string, new_frequency string; returns: StatementModel or None): Creates partial statement from current period start through today:
1. Checks StatementSettingsModel.find_active_settings(auth_account_id): if None (account creation without defaults) → return None
2. Closes active statement: sets to_date=today, saves
3. Queries PaymentModel.get_invoices_and_payment_accounts_for_statements using date range from get_first_and_last_of_frequency(today, active_settings.frequency)
4. Determines payment_methods via determine_payment_methods
5. Creates StatementModel with is_interim_statement=True; notification_status_code=NotificationStatus.PENDING if account.statement_notification_enabled else SKIP
6. Bulk-saves StatementInvoicesModel entries (statement.id linked to each invoice.id)
7. Gets or creates latest StatementSettingsModel, updates frequency=new_frequency and from_date=today+timedelta(days=1), saves

GOTCHA: Statement to_date equals today, truncating the calculated period end.

=== pay-api/src/pay_api/services/statement_recipients.py ===

Manages retrieval and updates of email notification recipients and settings for payment accounts. find_statement_notification_details(auth_account_id) retrieves all recipients for the account and its PaymentAccount record, returning a dict with 'recipients' (array via NotificationSchema) and 'statement_notification_enabled' boolean (defaults False). update_statement_notification_details(auth_account_id, notification_details dict) creates or updates the PaymentAccount with values from 'accountName' and 'statementNotificationEnabled' keys, saving it. For recipients: if notification_details['recipients'] is not None, deletes all existing recipients then bulk-saves new ones from input; if absent or None, skips recipient updates. Wraps StatementRecipientsModel with lazy DAO, properties for id, auth_user_id, firstname, lastname, email, payment_account_id, and asdict() serialization via NotificationSchema.

GOTCHA: email property getter returns _lastname, not _email. Type annotations in _dao setter incorrect (firstname int, lastname/email datetime; all should be strings).

=== pay-api/src/pay_api/services/statement_settings.py ===

Service to manage statement frequency settings for payment accounts and calculate billing period boundaries during frequency changes.

Wraps a `StatementSettingsModel` DAO with properties syncing to it. Input: `auth_account_id` (string), `frequency` (StatementFrequency enum name). Output: dictionary with `current_frequency` (serialized model) and `frequencies` array (each entry: `frequency` name and `start_date` for all options).

`find_by_account_id` retrieves the latest active settings record and calculates next start dates for all frequency options using `_get_end_of()`.

`update_statement_settings` handles frequency changes: if no settings exist, creates first record; if a future-dated settings record exists that isn't yet active (latest but not current), ends it today to handle rapid re-changes; then ends the current settings at the period end of the longer of old/new frequencies (`_find_longest_frequency`), and creates a new settings record starting the next day. Frequencies rank: DAILY < WEEKLY < MONTHLY.

`find_accounts_settings_by_frequency` queries active settings (from_date ≤ valid_date, to_date null or ≥ valid_date) by frequency. If `from_date` and `to_date` supplied, also excludes accounts with interim statements overlapping that range.

GOTCHA: Rapid frequency changes can leave unapplied records in the database until explicitly inactivated by a later change.
