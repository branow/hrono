# today

# Summary: pay-api service layer (`pay-api/src/pay_api/services/`)

Python service-layer modules from a payment system (BC Registries-style "pay-api") covering distribution codes, EFT, routing slips (FAS), fees, invoices, payments, receipts, statements, and reporting. Most modules follow one pattern: a service class wraps a SQLAlchemy model DAO (`XxxModel`) with lazy loading and properties that sync bidirectionally to the DAO. They also add static finders, business rules, and calls to external services (OAuth, Report API, Auth API, GCP queue).

## Groupings

### Accounting and fee configuration
- **distribution_code.py**
  - Holds five accounting dimensions: client, responsibility_centre, service_line, stob, project_code. It also holds an optional linked service-fee code and validity dates.
  - `find_all`, `find_by_id`, `find_active_by_account_id` are the finders.
  - `save_or_update` assigns fields. If client, responsibilityCentre, serviceLine, projectCode or serviceFeeDistributionCodeId changed on an existing record, it calls `InvoiceModel.update_invoices_for_revenue_updates` for this code and for all codes using it as their service fee. The cascade does not run on create.
  - `create_link` bulk-saves `DistributionCodeLinkModel` rows. `find_fee_schedules_by_distribution_id` is also here.
- **fee_schedule.py**
  - `find_by_corp_type_and_filing_type` returns a `FeeSchedule` with fee_amount, priority_fee, future_effective_fee, service_fees, waived_fee_amount and a `total`.
  - It handles quantity, account-level fee overrides (`AccountFeeModel.apply_filing_fees`), priority and future-effective surcharges, and a waive_fees flag.
  - GST and PST are always 0.
- **payment_line_item.py**
  - `create()` builds a line item from a FeeSchedule.
  - It looks up the active distribution code, and enforces staff-only fee waivers (`FEE_OVERRIDE_NOT_ALLOWED`).

### Routing slips (FAS)
- **fas/routing_slip.py**
  - Service with `search`, `find_by_number`, `validate_and_find_by_number` (honors the `ALLOW_LEGACY_ROUTING_SLIPS` config), and `get_links`.
  - `create_daily_reports` aggregates daily cash/cheque counts and USD totals per payment method and currency, excluding VOID slips. It posts the result via `OAuthService`.
- **fas/comment.py**
  - Creates and lists comments on routing slips.
  - Both operations validate that the slip exists, otherwise `FAS_INVALID_ROUTING_SLIP_NUMBER`.

### Invoices, references, NSF
- **invoice.py**
  - Invoice service with 21 synced properties.
  - `find_by_id` does the auth check, `asdict` can add dynamic fields, and `has_overdue_invoices` is also here.
  - `create_invoice_pdf` builds a PDF through the Report API with account and contact data from the Auth API.
  - `_add_dynamic_fields` computes is_payment_action_required and is_online_banking_allowed.
- **invoice_reference.py**
  - Creates ACTIVE references and finds them by invoice id with a status, or by invoice number.
- **non_sufficient_funds.py**
  - Saves NSF records.
  - Queries unpaid NSF invoices with aggregates: amount_remaining, nsf_amount, totals.
  - Generates an NSF statement PDF with template `non_sufficient_funds`.

### Payments, transactions, receipts
- **payment.py**
  - Payment records: `create`, `find_by_id`, and `search_account_payments`, which groups (payment, invoice) rows by payment id.
  - Purchase history search (`search_purchase_history`) and payment report generation (CSV or PDF) via `generate_payment_report`, `get_invoices_totals`, `_prepare_csv_data`.
- **payment_transaction.py**
  - Transaction lifecycle: `create_transaction_for_payment` and `create_transaction_for_invoice`. Creating a new one cancels the existing active transaction. Redirect URL validation applies to CC and DIRECT_PAY.
  - Also covers receipt saving (`__save_receipt`), transaction history (`find_by_invoice_id`), and queue publishing (`publish_status`, `create_event_payload`, which sends camelCase keys).
- **receipt.py**
  - `create_receipt` renders a PDF through the Report API.
  - `get_receipt_details` and `get_nsf_receipt_details` build the template data. The NSF version merges all invoices into the credit-card invoice.
- **payment_account.py**
  - `find_by_id`, `search_eft_accounts`, and `asdict`. The latter conditionally includes CFS bank details, masks the bank account number by user role, and includes the DistributionCode for EJV.
  - PAD pending-activation logic, plus account-creation event payloads and mailer publishing (only for PAD).

### EFT and statements
- **eft_short_names.py**
  - Builds the search query for EFT short names.
  - It joins link, account and statement-summary subqueries, with filters for link status, amount owing and account details.
- **statement.py**
  - Statement retrieval with computed amount_owing, owing filters and ordering by frequency.
  - EFT statement detection, EFT transaction lookup, and due date calculation.
  - EFT statement report generation: `get_statement_report` and `get_summary` (with an is_eft_under_payment flag), plus `_populate_statement_summary` and `populate_overdue_from_invoices`.
  - Interim statement generation when frequency changes: `generate_interim_statement`, `determine_payment_methods`.
- **statement_recipients.py**
  - Notification recipients and the statement_notification_enabled flag: find and update.
- **statement_settings.py**
  - Frequency settings (DAILY < WEEKLY < MONTHLY) and period-boundary logic for frequency changes.
  - `find_accounts_settings_by_frequency` can exclude accounts with overlapping interim statements.

### Reporting
- **report_service.py**
  - `ReportRequest` dataclass and `ReportService.get_report_response`.
  - It POSTs a camelCase payload to `REPORT_API_BASE_URL` using the user's bearer token.

## Caution
- **Setters that do not persist or reload**
  - In `distribution_code.py`, `service_fee_*` setters change only instance variables and never `_dao`, so the changes do not persist.
  - Changing `service_fee_distribution_code_id` does not reload the related dimensions.
  - Change detection is inconsistent across setters: five check equality and the others do not.
- **Wrong or misleading metadata**
  - Many setter docstrings and type hints are wrong. Examples: invoice `total` ("fee_start_date"), `email` getter returning `_lastname` in statement_recipients, receipt_number ("filing_fees"), the `_dao` setter hints in statement_recipients, and `calculate_due_date` returning None despite a str annotation.
  - Debug log labels in invoice.py don't match the real function or file.
- **Silent failures and swallowed errors**
  - `payment_account._publish_queue_message` catches all exceptions without re-raising.
  - `payment_transaction.publish_status` swallows exceptions and marks EVENT_FAILED. It also returns silently, publishing nothing, when a transaction is COMPLETED but the invoice is not PAID.
  - The eft_short_names branch/name regex-stripping can make filters fail silently.
- **Unchecked access**
  - These can raise IndexError or return None:
    - `invoice['invoices'][0]` in the NSF PDF.
    - `contact['contacts'][0]` in the payment report.
    - `org_contact` defaulting to `{}` in the invoice PDF.
  - Two invoice_reference finders skip a None check on the DAO.
- **Behavior differing from expectation**
  - `search_purchase_history` caps unfiltered requests to `TRANSACTION_REPORT_DEFAULT_TOTAL`, overriding `return_all`.
  - FeeSchedule's `quantity` setter multiplies `fee_amount` in place on every call.
  - `fee_distribution` stays None when total and service_fees are both ≤ 0.
  - `__save_receipt` treats id 0 as "new" and creates a duplicate.
  - In routing-slip reports, cash counts 1 per slip while cheque counts `len(payments)`. USD totals stay zero for slips with `total_usd` of None.
  - Interim statement `to_date` is set to today, truncating the period end.
  - `is_overdue` reflects current invoice statuses, not those at statement generation time.
  - Rapid frequency changes can leave unapplied settings records until a later change inactivates them.
  - In `search_account_payments`, grouping assumes results are ordered by payment id.
  - Creating a new transaction cancels and saves the existing active one synchronously first.
  - `invoice._dao` setter and `distribution_code.save_or_update` are non-transactional or partial: the former leaves partial state if an assignment fails.
  - Invoice PDF generation blanks `businessIdentifier` for values starting with 'T' (purpose unclear).
  - `eft_short_names` links use DISTINCT on auth_account_id ordered by `updated_on` DESC, keeping only the latest link per account.

# purpose-budget

# pay-api service layer (`pay_api/services`)

The business-logic layer of the BC Registries payment API. It sits between the REST resources and the SQLAlchemy models. It covers invoices, payments, receipts, statements, EFT, routing slips (FAS), fee calculation, distribution codes and reports, and it is used by API handlers and jobs.

## Inputs and outputs
- **In:** IDs and filter dicts from API handlers (invoice, payment, statement, `auth_account_id`, routing slip number), fee-schedule inputs, and user context and roles.
- **Out:** serialized dicts (via `*Schema`), service objects wrapping DAOs, PDF/CSV report responses, and GCP queue events (transaction status, account-created emails).
- **External calls:** `OAuthService` calls Auth API (`AUTH_API_ENDPOINT`) for org and contact data and Report API (`REPORT_API_BASE_URL`) for PDFs. `ReportService.get_report_response` is the shared gateway to the Report API.

## Core ideas
- **DAO-wrapper pattern:** most classes (`Invoice`, `Payment`, `PaymentLineItem`, `Statement`, `RoutingSlip`, `DistributionCode`, `InvoiceReference`, `StatementRecipients`) lazy-load a model in `_dao` and sync each property to it. Several setters have wrong type hints or docstrings. `StatementRecipients.email` returns `_lastname`.
- **Fees** (`FeeSchedule`): looks up the fee by corp type, filing type and date. It applies quantity, then the account-level `AccountFeeModel` override, then priority and future-effective surcharges, then `waive_fees`. `PaymentLineItem.create` adds the distribution code. Only staff may set a waived fee.
- **Transactions** (`PaymentTransaction`): a new transaction cancels any active one. Redirect URLs are validated only for CC and DIRECT_PAY. PAD invoices cannot start a transaction. `publish_status` sends COMPLETED only when the invoice is PAID.
- **Statements:** `StatementSettings` changes frequency by ending the current setting at the period end of the longer frequency. The interim-statement service closes the active statement and creates a partial one. Statement reports compute EFT summaries and underpayment.
- **Distribution codes:** `save_or_update` cascades `InvoiceModel.update_invoices_for_revenue_updates` when key dimensions change on an existing code.
- **Search and reporting:** the EFT short-name query (`get_search_query`) links short names to accounts and statement amounts owing. Purchase history and payment reports build CSV and PDF output. NSF and receipt services build their own PDFs.

## Main flows
- **Invoice PDF:** load invoice, account and CFS account, fetch org and contact from Auth, post a template to Report API.
- **Payment report:** `search_purchase_history`, then `generate_payment_report`, which maps status codes to descriptions and builds CSV or PDF templates.
- **Fee calculation:** `find_by_corp_type_and_filing_type`, then account override, then surcharges.

## Open first
1. `payment.py` (purchase history and reports)
2. `statement.py` (statements, summary, interim)
3. `payment_transaction.py` (transactions, receipts, events)
4. `fee_schedule.py`
5. `eft_short_names.py`

## Hazards
- `search_purchase_history` silently caps unfiltered requests at `TRANSACTION_REPORT_DEFAULT_TOTAL`.
- `generate_payment_report` indexes `contacts[0]` without a length check. `create_non_sufficient_funds_statement_pdf` indexes `invoices[0]` the same way.
- `PaymentAccount._publish_queue_message` and `publish_status` swallow exceptions, so failures are silent. `publish_status` also drops COMPLETED transactions whose invoice is not PAID.
- `DistributionCode`'s `service_fee_*` setters never write to the DAO, so changes do not persist.
- `FeeSchedule.quantity` multiplies in place on each call.
- The `Payment` grouping assumes results are ordered by `payment.id`.
- The EFT filter regex-strips the branch from the concatenated "name-branch" account name, so a mismatch makes filters fail silently.
- `Statement.is_overdue` reflects current invoice statuses, not those at generation time.
- Interim statements set `to_date` to today, which truncates the period.

# decisions

# Payment service layer (pay-api/src/pay_api/services)

This part is the service layer of the pay-api payment system. Services wrap DAO models (lazy-loaded, with properties synced to the DAO), apply business rules, and call external services: the Auth API, the Report API, the GCP queue and CFS. The notes cover several loosely related areas: accounting and fees, invoices and receipts, payments and transactions, statements and EFT, and routing slips (FAS).

## Accounting and fees

### distribution_code.py
Manages distribution codes. A code has five dimensions: client, responsibility_centre, service_line, stob and project_code. It may also have a linked service-fee code and validity dates.
- **Reads:** `find_all()` and `find_by_id()` return rows serialized through `DistributionCodeSchema`. `find_active_by_account_id()` returns a service instance. `find_fee_schedules_by_distribution_id` queries and serializes the fee schedules for a code.
- **Writes:** `create_link` bulk-saves `DistributionCodeLinkModel` rows built from the `fee_schedules` list (`feeScheduleId`).
- **`save_or_update(distribution_details, distribution_id)`**:
  - Input keys: client, responsibilityCentre, serviceLine, projectCode, stob, serviceFeeDistributionCodeId, disbursementDistributionCodeId, accountId, startDate and endDate (both optional).
  - It loads the existing record if an id is given, and defaults startDate to today (UTC).
  - It compares client, responsibilityCentre, serviceLine, projectCode and serviceFeeDistributionCodeId against the stored values.
  - **Decision:** it cascades only when something changed and the record already exists. In that case it calls `InvoiceModel.update_invoices_for_revenue_updates` for this id and for every code that uses it as its service-fee code. Creation never cascades.
  - It always resets `stop_ejv` to False before saving.
- **Service-fee dimensions:** when the DAO is set, the service loads the service-fee code's five dimensions and name, prefixed `service_fee_*`.

### fee_schedule.py
Calculates fees by corp_type and filing_type_code, with valid_date and the optional kwargs quantity, is_priority, is_future_effective and waive_fees.
- **Lookup:** `find_by_corp_type_and_filing_type` raises `INVALID_CORP_OR_FILING_TYPE` if an input is missing or no schedule matches.
- **Calculation order:**
  1. Apply the quantity multiplier.
  2. If an `AccountFeeModel` exists and `apply_filing_fees` is False, zero `fee_amount` and `waived_fee_amount`.
  3. Add `priority_fee` if `is_priority`, the schedule has one, and `apply_filing_fees` is true.
  4. Add `future_effective_fee` under the same conditions with `is_future_effective`.
  5. If `waive_fees` is set, zero `fee_amount`, `priority_fee`, `future_effective_fee` and `service_fees`.
- **Total:** `total` sums all amounts. `gst` and `pst` always return 0.

### payment_line_item.py
`create(invoice_id, FeeSchedule)` builds a line item.
- It defaults quantity to 1 and sets status to ACTIVE.
- If total or service_fees is above 0, it finds the active distribution code for the fee schedule and sets `fee_distribution_id`.
- If `waived_fee_amount` is above 0, only `Role.STAFF` may set `waived_by`. Anyone else gets `FEE_OVERRIDE_NOT_ALLOWED`.
- It flushes the DAO and returns a wrapped item.

## Invoices, references and receipts

### invoice.py
Wraps `InvoiceModel`.
- `find_by_id(identifier, skip_auth_check, one_of_roles)` raises `INVALID_INVOICE_ID` if the invoice is missing. It runs `_check_for_auth` unless `skip_auth_check` is set.
- `asdict(include_dynamic_fields)` serializes via `InvoiceSchema`. When dynamic fields are included, `_add_dynamic_fields` sets:
  - `is_payment_action_required` is true when status is CREATED and the method is DIRECT_PAY, CC or ONLINE_BANKING.
  - `is_online_banking_allowed` comes from `CodeService`. It is false if any line item has `future_effective_fees != 0`.
- `has_overdue_invoices(payment_account_id)` is true if any invoice has status OVERDUE.
- `find_invoices_for_payment` filters by reference status, which defaults to ACTIVE. `find_invoices(business_identifier)` returns `{'invoices': [...]}`.
- **`create_invoice_pdf(identifier, user_context)`**:
  - It loads the invoice, `PaymentAccountModel` and `CfsAccountModel`.
  - It gets org and contact data from `AUTH_API_ENDPOINT` via `OAuthService`.
  - The invoice number comes from `references[0].invoice_number`, or from `generate_transaction_number()` if there is no reference.
  - It builds `filingTypes` from the line items. `businessIdentifier` becomes '' if it starts with 'T'.
  - It posts to `REPORT_API_BASE_URL` with invoiceNumber, fees, total, gst, serviceFees, filingTypes and accountContact.
  - It returns `(pdf_response, reportName)`.

### invoice_reference.py
- `create(invoice_id, invoice_number, reference_number)` saves a reference with status `InvoiceReferenceStatus.ACTIVE`.
- Finders: `find_active_reference_by_invoice_id`, `find_completed_reference_by_invoice_id` and `find_any_active_reference_by_invoice_number`.

### receipt.py
- `create_receipt` calls `get_receipt_details`, merges the result with `filing_data` (optional `fileName`), and POSTs to `REPORT_API_BASE_URL` with the user's bearer token.
- **Pending decision in `get_receipt_details`:** an invoice counts as pending when its method is PAD, EJV or EFT and its status is not PAID.
  - If it is not pending and has no receipts, it raises an error.
  - `receiptNumber` is None when pending. Otherwise it is the first receipt's number.
  - `routingSlipNumber` is included only for `PaymentSystem.INTERNAL`.
- **`get_nsf_receipt_details(payment_id)`:**
  - It takes the completed invoices for the payment and picks the credit-card (CC) invoice as the NSF base.
  - It merges the other invoices into it: line items and details are extended, and total, service_fees and paid are summed.
  - If there is no CC invoice, it builds an empty synthetic `Invoice`.

### non_sufficient_funds.py
Saves NSF records (invoice_id, invoice_number, cfs_account, description).
- `query_all_non_sufficient_funds_invoices` returns, for an `auth_account_id`, all invoices that are not PAID. The join covers Invoice, InvoiceReference, NonSufficientFunds, PaymentAccount and PaymentLineItem.
- It returns `InvoiceSearchModel` rows, statements, and the floats `total_amount`, `total_amount_remaining` and `nsf_amount`. `nsf_amount` is the max line-item total where the description equals `ReverseOperation.NSF`.
- The PDF function fetches account and CFS data over OAuth, formats `suspendedOn` conditionally, and posts to `REPORT_API_BASE_URL` with template `non_sufficient_funds`.

### report_service.py
`ReportRequest` holds content_type, report_name, template_name, template_vars and populate_page_number.
- `get_report_response` posts the camelCase payload to `REPORT_API_BASE_URL` through `OAuthService.post`.
- It uses bearer auth injected by `@user_context`, a JSON request body, and an Accept header set to the requested content type.

## Payments, transactions and accounts

### payment.py
`create(payment_method, payment_system, ...)` defaults status to CREATED.
- `search_account_payments` groups (payment, invoice) rows by `payment.id` and returns `{total, page, limit, items}`.
- `search_purchase_history`: if the filter is empty or all values are falsy, `max_no_records = TRANSACTION_REPORT_DEFAULT_TOTAL`. Otherwise it is 0.
- `generate_payment_report`:
  1. It replaces each invoice `status_code` with its description from `CodeService`.
  2. For CSV (`ContentType.CSV`), it builds the template through `_prepare_csv_data`.
  3. Otherwise, it fetches account contacts from the Auth API and builds the PDF template.
  4. It calls `ReportService.get_report_response`.
- `get_invoices_totals` sums total, statutoryFees (total − service_fees), serviceFees and paid, and computes due as total − paid.

### payment_transaction.py
- `create_transaction_for_payment` requires the payment to exist and have status CREATED. Otherwise it raises `INVALID_PAYMENT_ID`.
- `create_transaction_for_invoice` requires the invoice to exist, rejects PAD invoices with `INVALID_TRANSACTION`, and creates a Payment if none exists.
- `_create_transaction`:
  - It raises `COMPLETED_PAYMENT` if the payment is COMPLETED or DELETED.
  - It cancels any existing non-CANCELLED transactions (status set to CANCELLED, end time set to now).
  - It creates a new CREATED transaction.
  - The redirect URL is validated only for CC and DIRECT_PAY. Otherwise it raises `INVALID_REDIRECT_URI`.
- `__save_receipt` looks up a receipt by invoice id and receipt_number. It creates one if missing, otherwise updates the date and amount.
- `find_by_invoice_id` returns the transaction history as `{'items': [...]}`.
- **`publish_status`:**
  - COMPLETED transaction with PAID invoice: publishes COMPLETED.
  - COMPLETED transaction with unpaid invoice: logs and does not publish.
  - Any other case: publishes TRANSACTION_FAILED.
  - On an exception it logs a warning and sets the transaction status to `EVENT_FAILED`.
- `create_event_payload` is built from `PaymentToken` (invoice id, status, filing_id, corp_type_code) with camelCase keys.

### payment_account.py
- `search_eft_accounts(search_text)` matches EFT accounts with CFS status ACTIVE or PENDING and `eft_enable=True`. It does a wildcard search on auth_account_id, name and branch_name, orders exact matches first and then ID descending, and limits to 20 rows.
- **`asdict()`:**
  - CFS details are included for PAD, ONLINE_BANKING and EFT, or for DRAWDOWN with PAD pending activation (`_is_pad_in_pending_activation`). For PAD it shows the future CFS account.
  - The bank account number is masked by user role (`can_view_bank_account_number`). Bank info is included only if the user `is_system()` or `can_view_bank_info()`.
  - EJV accounts include the DistributionCode. `AccountFeeSchema` is included if fees exist.
- `_calculate_activation_date` adds `PAD_CONFIRMATION_PERIOD_IN_DAYS` + 1 days, rounds to midnight and converts to UTC.
- `publish_account_mailer_event_on_creation` publishes only for PAD.
- `create_account_event_payload` adds extra fields by event type:
  - `NSF_UNLOCK_ACCOUNT`: invoiceNumber, receiptNumber, paymentMethodDescription and invoice.
  - `PAD_ACCOUNT_CREATE`: padTosAcceptedBy.
  - `include_pay_info`: a `paymentInfo` dict with the masked bank account number.

## Statements and EFT

### statement.py
- `find_by_id` and `find_by_account_id` attach `amount_owing`: the sum of total − paid for invoices in PARTIAL, APPROVED or OVERDUE status.
- `find_by_account_id` filters `amount_owing > 0` when `is_owing` is set. It orders by to_date DESC, then frequency (MONTHLY 1, WEEKLY 2, DAILY 3, other 4), and paginates.
- `is_eft_statement` is true if the first invoice's method is EFT, or if EFT is in `statement.payment_methods`.
- `get_invoices_owing_amount` sums EFT invoices in SETTLEMENT_SCHEDULED, APPROVED or OVERDUE.
- `get_statement_eft_transactions` joins EFTCredit and EFTCreditInvoiceLink for COMPLETED rows.
- `calculate_due_date` adds 1 month plus 8 hours and returns an ISO string.
- `get_statement_report`:
  - The name is `bcregistry-statements-{from_date}.{ext}` for DAILY, and `...-{from_date}-to-{to_date}.{ext}` otherwise.
  - It builds a `PaymentReportInput` with template `StatementTemplate.STATEMENT_REPORT`.
  - It adds a statement summary (`_populate_statement_summary`) when `is_eft_statement()` is true.
  - It returns `PaymentService.generate_payment_report` output.
- `get_summary` covers EFT invoices in SETTLEMENT_SCHEDULED, PARTIAL, APPROVED or OVERDUE. It returns `total_due`, `oldest_due_date` and the short-name link count.
  - `is_eft_under_payment` is true only if `calculate_under_payment` is set, an active link exists (LINKED or PENDING short name), and `0 < EFTCreditModel.get_eft_credit_balance < owing`.
  - Otherwise it is None.
- `populate_overdue_from_invoices` sets `is_overdue` if any invoice is OVERDUE.

### Interim statements (`generate_interim_statement`)
It runs when the billing frequency changes. It takes `auth_account_id` and `new_frequency` and returns a `StatementModel` or None.
1. It returns None if `StatementSettingsModel.find_active_settings` finds nothing.
2. It closes the active statement by setting `to_date` to today.
3. It fetches invoices for the current period, using `get_first_and_last_of_frequency(today, active_settings.frequency)`.
4. It builds `payment_methods` with `determine_payment_methods`.
   - It joins the methods of the account's own invoices with commas.
   - If none are found, it falls back to `existing_statement.payment_methods`, then to `pay_account.payment_method` or ''.
5. It creates the statement with `is_interim_statement=True`. Notification status is PENDING if `statement_notification_enabled`, otherwise SKIP.
6. It bulk-saves `StatementInvoicesModel` links.
7. It updates the latest `StatementSettingsModel` to the new frequency, with `from_date` set to today + 1 day.

### statement_settings.py
- `find_by_account_id` returns `{current_frequency, frequencies:[{frequency, start_date}]}`. The start dates are computed with `_get_end_of()`.
- **`update_statement_settings`:**
  - If there are no settings, it creates the first record.
  - If a latest record exists that is future-dated and not yet current, it ends that record today.
  - It ends the current record at the period end of the longer of the old and new frequencies (`_find_longest_frequency`, ranked DAILY < WEEKLY < MONTHLY).
  - It creates a new record starting the next day.
- `find_accounts_settings_by_frequency` selects active settings for a valid_date. If a `from_date` and `to_date` are given, it excludes accounts with interim statements in that range.

### statement_recipients.py
- `find_statement_notification_details` returns `recipients` (via `NotificationSchema`) and `statement_notification_enabled`, which defaults to False.
- `update_statement_notification_details` updates the PaymentAccount from `accountName` and `statementNotificationEnabled`.
  - If `recipients` is not None, it deletes all existing recipients and bulk-saves the new ones.
  - If it is absent or None, recipients are untouched.

### eft_short_names.py
`get_search_query(search_criteria, is_count)` builds the EFT short name search.
- **Joins:** it joins a links subquery (`EFTShortnameLinksModel`, `PaymentAccountModel`, `CfsAccountModel`) and a statement summary subquery. The summary covers EFT invoices grouped by payment account, excluding CANCELLED, REFUND_REQUESTED and REFUNDED.
- **Filters:** statement_id, amount_owing, account_id, account_name, account_branch, short_name and type.
  - **Link state:** UNLINKED means no links with status other than UNLINKED. LINKED means status in PENDING or LINKED.
  - **Amount owing:** 0 matches 0 or NULL. Other values match exactly.
- **Columns:** when `is_count` is false it adds account_name, account_branch, total_owing and latest_statement_id. Results are ordered by short_name, then auth_account_id.

## Routing slips (FAS)

### fas/routing_slip.py
- `search()` returns `{page, limit, total, items}`.
- `create_daily_reports` takes the day's slips, excluding VOID, and counts per slip:
  - If `payment_account.payment_method == CASH`, it adds 1 to `no_of_cash`. Otherwise it adds `len(payments)` to `no_of_cheque`.
  - In both cases it adds `total_usd` to the matching USD total when it is not None.
  - It posts the aggregate through `OAuthService.post()`.
- `validate_and_find_by_number` checks the number's digits only when `ALLOW_LEGACY_ROUTING_SLIPS` is false.
- `find_by_number` adds `allowedStatuses` from `RoutingSlipStatusTransitionService`.
- `get_links()` returns the parent and children slips.

### fas/comment.py
`create(comment, routing_slip_number)` and `find_all_comments_for_a_routingslip` both require the routing slip to exist. Otherwise they raise `FAS_INVALID_ROUTING_SLIP_NUMBER`. `create` flushes, commits and returns the comment as a dict. The find method returns `{'comments': [...]}`.

## Hazards
- Setters for `service_fee_*` in `distribution_code.py` change only instance variables and never reach the DAO, so those edits are not saved. Changing `service_fee_distribution_code_id` also does not reload the service-fee dimensions.
- `PaymentAccount._publish_queue_message` and `PaymentTransaction.publish_status` swallow all exceptions. Failed account emails are silent. Failed transaction events only mark `EVENT_FAILED`. A COMPLETED transaction with an unpaid invoice publishes nothing.
- `search_purchase_history` silently caps unfiltered requests at `TRANSACTION_REPORT_DEFAULT_TOTAL`, overriding any return-all request. `generate_payment_report` indexes `contact['contacts'][0]` and raises IndexError on an empty contact list.
- `statement_recipients.py` has an `email` getter that returns `_lastname`. Interim statements set `to_date` to today, which truncates the computed period end.
- `non_sufficient_funds.py` indexes `invoice['invoices'][0]` without a length check, and the NSF PDF crashes if no invoices come back. The `get_nsf_receipt_details` synthetic invoice is not fully initialized. `FeeSchedule.quantity` multiplies `fee_amount` in place on every call.

# decisions-ctx

# Payment service layer (pay-api/src/pay_api/services)

This is the business-logic layer of the BC Registries pay-api. It sits between the REST resources and the SQLAlchemy models. It covers distribution codes, fee schedules, invoices, payments, payment accounts, EFT short names, routing-slip comments, statements, and reports. Most classes wrap a model DAO lazily, with properties that sync both ways. The notes cover several loosely related areas, each described below.

## Boundaries
- **In:** REST resources pass IDs, dicts and search filters. User context supplies roles and the bearer token.
- **Out to the database:** the model DAOs (`InvoiceModel`, `PaymentModel`, `StatementModel`, `RoutingSlipModel`, `CommentModel` and others).
- **Out to other services:**
  - Auth API (`AUTH_API_ENDPOINT`) for org and contact data.
  - Report API (`REPORT_API_BASE_URL`), through `ReportService.get_report_response()` or `OAuthService.post()`.
  - A GCP queue for transaction-status and account-creation events.
  - A daily-report POST from `RoutingSlip.create_daily_reports()` through `OAuthService`.

## Fees and distribution codes

**`fee_schedule.py`** (`FeeSchedule.find_by_corp_type_and_filing_type`)
- Looks up `FeeScheduleModel` by corp type, filing type and date.
- Raises `INVALID_CORP_OR_FILING_TYPE` if either input is missing or no schedule matches.
- Applies the quantity multiplier.
- Checks `AccountFeeModel`. If an account fee exists and `apply_filing_fees` is False, `fee_amount` and `waived_fee_amount` become 0.
- Adds `priority_fee` when `is_priority` is set, the schedule has one, and `apply_filing_fees` is true.
- Adds `future_effective_fee` under the same conditions when `is_future_effective` is set.
- `waive_fees` zeroes the fee, priority, future-effective and service fees.
- `total` sums the fee components. `gst` and `pst` are always 0.

**`payment_line_item.py`** (`create(invoice_id, fee_schedule)`)
- Quantity defaults to 1 and status to `ACTIVE`.
- If `total` or `service_fees` is above 0, it looks up the active distribution code for the fee schedule and sets `fee_distribution_id`.
- If `waived_fee_amount` is above 0, only `Role.STAFF` may set `waived_by`. Anyone else gets `FEE_OVERRIDE_NOT_ALLOWED`.
- The row is flushed and returned.

**`distribution_code.py`**
- `save_or_update` loads the existing record when an id is given.
- `startDate` defaults to today (UTC).
- It assigns all fields. If `client`, `responsibilityCentre`, `serviceLine`, `projectCode` or `serviceFeeDistributionCodeId` changed on an existing record, it calls `InvoiceModel.update_invoices_for_revenue_updates`. That call runs for this distribution and for every distribution that uses it as its service-fee code.
- Creation never triggers the cascade.
- It always resets `stop_ejv` to False before saving.
- `create_link` bulk-saves `DistributionCodeLinkModel` rows. `find_all`, `find_by_id` and `find_active_by_account_id` read and serialise.

## Invoices, receipts, payments and transactions

**`invoice.py`**
- `find_by_id(identifier, skip_auth_check, one_of_roles)` raises `INVALID_INVOICE_ID` when the invoice is missing. It runs `_check_for_auth` unless `skip_auth_check` is set.
- `_add_dynamic_fields` adds `is_payment_action_required` when the status is `CREATED` and the method is DIRECT_PAY, CC or ONLINE_BANKING. `is_online_banking_allowed` comes from `CodeService`, and any line item with `future_effective_fees != 0` sets it to false.
- `has_overdue_invoices` checks for `OVERDUE` status.
- `create_invoice_pdf` takes the invoice number from `references[0].invoice_number`, or generates one with `generate_transaction_number()`. It blanks `businessIdentifier` when it starts with "T". It posts the template to the Report API.

**`invoice_reference.py`**
- `create` stores a reference with status `ACTIVE`.
- Lookups: `find_active_reference_by_invoice_id`, `find_completed_reference_by_invoice_id` and `find_any_active_reference_by_invoice_number`.

**`receipt.py`**
- `get_receipt_details` treats an invoice as pending when the method is PAD, EJV or EFT and the status is not `PAID`.
  - If it is not pending and has no receipts, it raises an error.
  - `receiptNumber` is None when pending.
  - `routingSlipNumber` is included only for `PaymentSystem.INTERNAL`.
- `get_nsf_receipt_details` picks the CC invoice as the NSF base. It merges the other invoices' line items, details, totals, service fees and paid amounts into it. If there is no CC invoice, it builds an empty `Invoice`.

**`payment.py`**
- `create` defaults the status to `CREATED`.
- `search_account_payments` groups `(payment, invoice)` rows by `payment.id`.
- `search_purchase_history` caps the result at `TRANSACTION_REPORT_DEFAULT_TOTAL` when the filter is empty or all values are falsy.
- `generate_payment_report` swaps invoice status codes for descriptions from `CodeService`. For `ContentType.CSV` it calls `_prepare_csv_data`. Otherwise it fetches contacts from the Auth API and builds the PDF template.

**`payment_transaction.py`**
- `create_transaction_for_payment` requires the payment to exist with status `CREATED`. Otherwise it raises `INVALID_PAYMENT_ID`. It also validates `clientSystemUrl`.
- `create_transaction_for_invoice` raises `INVALID_INVOICE_ID` if the invoice is missing and `INVALID_TRANSACTION` for PAD. It creates a `Payment` if none exists.
- `_create_transaction` raises `COMPLETED_PAYMENT` if the payment is COMPLETED or DELETED. It cancels any non-cancelled transaction and sets `transaction_end_time`. It then creates a new transaction with status `CREATED`.
- The redirect URL is validated only for CC and DIRECT_PAY. Other methods get `INVALID_REDIRECT_URI`.
- `publish_status`:
  - COMPLETED transaction with a PAID invoice publishes `COMPLETED`.
  - COMPLETED with an unpaid invoice publishes nothing.
  - Anything else publishes `TRANSACTION_FAILED`.
  - A publish exception sets the transaction status to `EVENT_FAILED`.
- `__save_receipt` upserts by invoice id and receipt number.

**`non_sufficient_funds.py`**
- Saves NSF records.
- Queries unpaid NSF invoices for an account. The query excludes `PAID` invoices. It computes `amount_remaining`, `nsf_amount` (the maximum line-item total where the description is `ReverseOperation.NSF`) and the totals.
- Builds the `non_sufficient_funds` PDF template.

## Accounts, EFT and statements

**`payment_account.py`**
- `search_eft_accounts` filters on EFT method, CFS status ACTIVE or PENDING, and `eft_enable`. It matches wildcards on id, name and branch, orders exact matches first, and returns at most 20 rows.
- `asdict` includes CFS details for PAD, ONLINE_BANKING and EFT, and for DRAWDOWN while PAD is pending activation. `_is_pad_in_pending_activation` is true when the activation date is in the future and the future CFS status is PENDING or PENDING_PAD_ACTIVATION.
- Bank account numbers are masked unless `user.can_view_bank_account_number()` allows them. Bank info is shown only if `user.is_system()` or `can_view_bank_info()`.
- EJV accounts add the distribution code. Accounts with fees add `AccountFeeSchema`.
- `_calculate_activation_date` adds `PAD_CONFIRMATION_PERIOD_IN_DAYS` + 1 days.
- `publish_account_mailer_event_on_creation` publishes only for PAD.
- `create_account_event_payload` adds extra fields for `NSF_UNLOCK_ACCOUNT` and `PAD_ACCOUNT_CREATE`. It adds `paymentInfo` when `include_pay_info` is set.

**`eft_short_names.py`** (`get_search_query(search_criteria, is_count)`)
- Joins the most recent link per account (`DISTINCT auth_account_id`, `ORDER BY updated_on DESC`) with a statement summary of EFT invoices. The summary excludes CANCELLED, REFUND_REQUESTED and REFUNDED.
- UNLINKED matches short names with no link whose status is not UNLINKED. LINKED matches PENDING or LINKED.
- `amount_owing == 0` also matches NULL.
- The count query skips the payment columns.
- Results are ordered by `short_name`, then `auth_account_id`.

**`statement.py`**
- `find_by_id` computes `amount_owing` from invoices in PARTIAL, APPROVED or OVERDUE status.
- `find_by_account_id` filters `amount_owing > 0` when `is_owing` is set. It orders by `to_date` descending, then frequency priority (MONTHLY, WEEKLY, DAILY).
- `is_eft_statement` is true if the first invoice or any statement payment method is EFT.
- `get_invoices_owing_amount` covers SETTLEMENT_SCHEDULED, APPROVED and OVERDUE.
- `calculate_due_date` adds 1 month plus 8 hours.
- `get_statement_report` names the file `bcregistry-statements-{from}.{ext}` for DAILY and `…-{from}-to-{to}.{ext}` otherwise. It adds `statement_summary` for EFT statements.
- `get_summary` sets `is_eft_under_payment` only when `calculate_under_payment` is set, an active LINKED or PENDING short-name link exists, and 0 < credit balance < amount owing.
- `populate_overdue_from_invoices` sets `is_overdue` if any invoice is OVERDUE.
- `generate_interim_statement` returns None if there are no active settings. Otherwise it:
  1. Closes the active statement with `to_date` = today.
  2. Builds an interim statement (`is_interim_statement=True`) over the current period.
  3. Sets the notification status to `PENDING` when `statement_notification_enabled` is on, otherwise `SKIP`.
  4. Links the period's invoices.
  5. Updates the settings to the new frequency starting tomorrow.
- `determine_payment_methods` falls back to the existing statement's methods, then the account's method.

**`statement_settings.py`**
- `update_statement_settings` creates the first record if none exists.
- It ends a future-dated, not-yet-active record today.
- It ends the current record at the period end of the longer of the old and new frequencies (DAILY < WEEKLY < MONTHLY).
- It starts the new record the next day.
- `find_accounts_settings_by_frequency` excludes accounts with interim statements overlapping a given date range.

**`statement_recipients.py`**
- `update_statement_notification_details` upserts the `PaymentAccount` from `accountName` and `statementNotificationEnabled`.
- If `recipients` is not None, it deletes all existing recipients and bulk-saves the new ones. Otherwise recipients are untouched.

## Routing slips (FAS)

**`fas/comment.py`**
- `create` and `find_all_comments_for_a_routingslip` both check the slip exists. Otherwise they raise `FAS_INVALID_ROUTING_SLIP_NUMBER`.
- `create` flushes and commits.

**`fas/routing_slip.py`**
- `create_daily_reports` excludes VOID slips. A CASH slip adds 1 to `no_of_cash`. Any other slip adds `len(payments)` to `no_of_cheque`. USD is added when `total_usd` is not None.
- `validate_and_find_by_number` validates digits when `ALLOW_LEGACY_ROUTING_SLIPS` is false.
- `find_by_number` fills `allowedStatuses` from `RoutingSlipStatusTransitionService`.

## Report service

**`report_service.py`**
- `ReportRequest` holds `content_type`, `report_name`, `template_name`, `template_vars` and `populate_page_number`.
- `get_report_response` posts the camelCase payload to `REPORT_API_BASE_URL` with bearer auth, JSON content type, and `Accept` set to the requested content type.

## Hazards
- Property setters in `DistributionCode` update only instance variables for the `service_fee_*` fields, so those changes never persist. Setting `service_fee_distribution_code_id` does not reload the service-fee dimensions.
- `PaymentTransaction.publish_status` swallows all exceptions and sets `EVENT_FAILED`. A COMPLETED transaction with an unpaid invoice drops the event silently. `PaymentAccount._publish_queue_message` also never re-raises, so account-creation emails can be lost without notice.
- `StatementRecipients.email` returns `_lastname`. `Statement.calculate_due_date` can return None.
- `NonSufficientFunds.create_non_sufficient_funds_statement_pdf` reads `invoices[0]` without a check and crashes when none exist. `Payment.generate_payment_report` reads `contacts[0]` without a length check.
- Statement settings changes can leave unapplied future records until a later change ends them. Interim statements set `to_date` to today, which truncates the calculated period. `FeeSchedule.quantity` multiplies `fee_amount` in place, so repeated calls compound.

# decisions-tight

# pay-api service layer (`pay_api/services`)

The service layer of the BC Registries pay-api. It wraps SQLAlchemy DAO models in lazily loaded service objects. It handles fees, invoices, payments, routing slips, EFT, statements and reports, and it calls the report-api, auth-api and a GCP queue. Most classes mirror DAO fields through property getters and setters, and `save()`, `commit()`, `flush()` and `rollback()` delegate to the DAO. The modules below are independent of each other apart from shared models and services.

## Fees and line items
- **`fee_schedule.py`**
  - `find_by_corp_type_and_filing_type(corp_type, filing_type_code, valid_date, **kwargs)` looks up `FeeScheduleModel`. It raises `INVALID_CORP_OR_FILING_TYPE` if the row is missing or an input is absent.
  - It applies `quantity`, then checks `AccountFeeModel`. If an account fee exists and `apply_filing_fees` is False, `fee_amount` and `waived_fee_amount` become 0.
  - `priority_fee` is added only when `is_priority` is set, the schedule has one, and `apply_filing_fees` is true. `future_effective_fee` follows the same rule with `is_future_effective`.
  - `waive_fees` zeroes the fee, priority fee, future-effective fee and service fees.
  - `total` sums the parts. `gst` and `pst` always return 0.
- **`payment_line_item.py`**
  - `create(invoice_id, fee)` sets quantity to 1 if absent and status to ACTIVE.
  - If total or service fees are above 0, it finds the active `DistributionCode` for the fee schedule and sets `fee_distribution_id`.
  - If `waived_fee_amount` is above 0, only `Role.STAFF` may set `waived_by`. Anyone else gets `FEE_OVERRIDE_NOT_ALLOWED`.
- **`distribution_code.py`**
  - `save_or_update(details, dist_id)` loads the record when updating and defaults `startDate` to today (UTC). It sets `stop_ejv` to False and saves.
  - If client, responsibilityCentre, serviceLine, projectCode or serviceFeeDistributionCodeId changed on an existing record, it calls `InvoiceModel.update_invoices_for_revenue_updates`. It calls this for the code itself and for every code that uses it as a service-fee code. Creation never cascades.
  - `create_link` bulk-saves `DistributionCodeLinkModel` rows for fee schedules.
  - `find_all`, `find_by_id` and `find_active_by_account_id` read codes. The service-fee dimensions load only when the DAO is assigned.

## Invoices, references, NSF
- **`invoice.py`**
  - `find_by_id` raises `INVALID_INVOICE_ID` if the invoice is missing. It runs `_check_for_auth` against `one_of_roles` unless `skip_auth_check` is set.
  - `asdict(include_dynamic_fields)` adds `is_payment_action_required` when status is CREATED and the method is DIRECT_PAY, CC or ONLINE_BANKING.
  - It adds `is_online_banking_allowed` from `CodeService`, set false if any line item has `future_effective_fees` other than 0.
  - `has_overdue_invoices` is true if any invoice has status OVERDUE.
  - `create_invoice_pdf` pulls org and contact data from AUTH_API_ENDPOINT. The invoice number comes from `references[0]` or `generate_transaction_number()`. A `businessIdentifier` starting with "T" is blanked. The template is posted to REPORT_API_BASE_URL.
- **`invoice_reference.py`**
  - `create` stores a reference with status ACTIVE.
  - The finders look up by invoice id plus status (active or completed) or by invoice number.
- **`non_sufficient_funds.py`**
  - It saves NSF records.
  - `query_all_non_sufficient_funds_invoices` filters by `auth_account_id`, excludes PAID invoices, and computes `amount_remaining`, `nsf_amount` (max line total whose description equals `ReverseOperation.NSF`) and totals.
  - The PDF is posted with template `non_sufficient_funds`.

## Payments, transactions, receipts
- **`payment.py`**
  - `create` defaults the status to CREATED.
  - `search_account_payments` groups `(payment, invoice)` rows by payment id.
  - `search_purchase_history` sets `max_no_records` to `TRANSACTION_REPORT_DEFAULT_TOTAL` when the filter is empty or all values are falsy, and 0 otherwise.
  - `generate_payment_report` replaces invoice status codes with their descriptions. CSV goes through `_prepare_csv_data`. Otherwise it reads the account contact from the auth API and builds the PDF template. `ReportService.get_report_response` sends the result.
- **`payment_transaction.py`**
  - `create_transaction_for_payment` needs the payment to exist with status CREATED, else `INVALID_PAYMENT_ID`.
  - `create_transaction_for_invoice` rejects PAD invoices with `INVALID_TRANSACTION` and creates a payment if none exists.
  - `_create_transaction` raises `COMPLETED_PAYMENT` for COMPLETED or DELETED payments. It cancels any non-cancelled transaction, then creates a new one.
  - The redirect URL is validated only for CC and DIRECT_PAY, else `INVALID_REDIRECT_URI`.
  - `publish_status` publishes COMPLETED only when the transaction is COMPLETED and the invoice is PAID. COMPLETED with an unpaid invoice publishes nothing. Any other status publishes `TRANSACTION_FAILED`.
  - A publish exception sets the transaction to `EVENT_FAILED`.
  - `__save_receipt` upserts by invoice id and receipt number.
- **`receipt.py`**
  - `get_receipt_details` treats an invoice as pending when the method is PAD, EJV or EFT and the status is not PAID. A non-pending invoice with no receipts raises an error.
  - It sets `receiptNumber` to None for pending invoices and includes `routingSlipNumber` only for `PaymentSystem.INTERNAL`.
  - `get_nsf_receipt_details` merges all invoices into the CC invoice.
  - `create_receipt` posts to report-api.
- **`report_service.py`**: `ReportService.get_report_response` sends a camelCase payload from a `ReportRequest` to `REPORT_API_BASE_URL` with the user's bearer token. The `Accept` header is the requested content type.

## Accounts and EFT
- **`payment_account.py`**
  - `asdict` includes CFS details for PAD, ONLINE_BANKING and EFT. It also includes them for DRAWDOWN with PAD pending activation (`_is_pad_in_pending_activation`).
  - The bank account number is masked by role. Bank details appear only for system users or when `can_view_bank_info()`. EJV adds the distribution code.
  - `search_eft_accounts` filters to EFT, CFS status ACTIVE or PENDING, and `eft_enable`. It returns at most 20 rows.
  - `publish_account_mailer_event_on_creation` publishes only for PAD. `create_account_event_payload` adds fields by event type.
- **`eft_short_names.py`**: `get_search_query` joins links and a statement summary subquery. The summary excludes CANCELLED, REFUND_REQUESTED and REFUNDED invoices and covers EFT only.
  - `UNLINKED` means no link with a status other than UNLINKED. `LINKED` means status PENDING or LINKED.
  - `amount_owing == 0` also matches NULL.

## Routing slips (FAS)
- **`fas/comment.py`**: `create` and `find_all_comments_for_a_routingslip` both raise `FAS_INVALID_ROUTING_SLIP_NUMBER` if the slip is missing. `create` flushes and commits.
- **`fas/routing_slip.py`**
  - `create_daily_reports` skips VOID slips. A CASH slip counts 1. Otherwise the cheque count adds `len(payments)`. USD totals use `total_usd` when it is not None. The report is posted through `OAuthService`.
  - `validate_and_find_by_number` checks digits when `ALLOW_LEGACY_ROUTING_SLIPS` is false.
  - `find_by_number` fills `allowedStatuses`.

## Statements
- **`statement.py`**
  - `find_by_id` and `find_by_account_id` compute `amount_owing` from PARTIAL, APPROVED and OVERDUE invoices. `is_owing` filters to amounts above 0. Order is `to_date` descending, then frequency (MONTHLY 1, WEEKLY 2, DAILY 3).
  - `is_eft_statement` is true if the first invoice's method is EFT or EFT is in `payment_methods`.
  - `calculate_due_date` returns one month plus 8 hours.
- **Statement reports**
  - `get_statement_report` names the file by frequency (DAILY uses a single date, others use a from-to range). It adds `statement_summary` only for EFT statements.
  - `get_summary` covers SETTLEMENT_SCHEDULED, PARTIAL, APPROVED and OVERDUE EFT invoices. `is_eft_under_payment` is true only if `calculate_under_payment` is set, an active LINKED or PENDING short-name link exists, and the credit balance satisfies 0 < balance < owing.
  - `populate_overdue_from_invoices` sets `is_overdue` from current invoice status.
- **Interim statements**
  - `generate_interim_statement` returns None when there are no active settings. Otherwise it closes the active statement at today and creates an `is_interim_statement` statement. Its notification status is PENDING if `statement_notification_enabled`, else SKIP. It links the invoices.
  - It then moves the settings to the new frequency starting tomorrow.
  - `determine_payment_methods` falls back to `existing_statement.payment_methods`, then to the account's payment method.
- **`statement_settings.py`**
  - `update_statement_settings` creates the first record if none exists. It ends a not-yet-active future record today. It ends the current one at the period end of the longer of the old and new frequencies, and starts the new one the next day.
  - `find_accounts_settings_by_frequency` can exclude accounts with interim statements overlapping the date range.
- **`statement_recipients.py`**: `update_statement_notification_details` upserts the `PaymentAccount` from `accountName` and `statementNotificationEnabled`. A non-None `recipients` list replaces all existing recipients. A missing or None list leaves them alone.

## Hazards
1. `distribution_code.py`: the `service_fee_*` setters change only instance variables, so they never persist. Setting `service_fee_distribution_code_id` does not reload the related dimensions.
2. `payment_transaction.publish_status` swallows all exceptions and drops COMPLETED events when the invoice is not PAID. A failed publish leaves only an `EVENT_FAILED` status behind.
3. `payment_account._publish_queue_message` logs failures and never raises, so account-creation emails can fail silently.
4. `payment.search_purchase_history` caps unfiltered requests at `TRANSACTION_REPORT_DEFAULT_TOTAL` regardless of `return_all`. `generate_payment_report` indexes `contacts[0]` unchecked. `non_sufficient_funds` indexes `invoices[0]` unchecked.
5. `statement_recipients.email` returns `_lastname`. Also, `eft_short_names` strips the branch from `account_name` with a regex when filtering. A name mismatch makes filters fail silently.

# core

The notes cover the `pay_api.services` layer of pay-api. It contains the business logic between the API resources and the models, plus calls out to Auth API, Report API and a GCP queue. It is not one cohesive component, so each area gets its own description.

**Accounting and fees**
- `distribution_code.py` saves distribution codes and links them to fee schedules. If client, responsibilityCentre, serviceLine, projectCode or serviceFeeDistributionCodeId change on an existing record, it calls `InvoiceModel.update_invoices_for_revenue_updates` for that code and for every code that uses it as its service fee. Creation never triggers this cascade.
- `fee_schedule.py` computes fees by corp and filing type. Account-level `AccountFeeModel` overrides can zero the filing fee. Priority and future-effective surcharges apply only when `apply_filing_fees` allows. `waive_fees` zeroes everything.
- `payment_line_item.py` creates line items. It looks up the active distribution code when the total or service fees are above 0. Only staff may set waived amounts.

**Invoices, payments and transactions**
- `invoice.py` and `invoice_reference.py` wrap the invoice and reference DAOs and handle invoice PDFs and overdue checks.
- `payment.py` handles payment records and purchase-history reports (CSV or PDF).
- `payment_transaction.py` creates and cancels transactions. `publish_status` sends transaction status to the queue only when the invoice is PAID.
- `receipt.py` builds receipt data and PDFs.
- `non_sufficient_funds.py` manages NSF records and statements.
- `report_service.py` posts report requests to Report API with a bearer token.

**Statements and EFT**
- `statement.py`, `statement_settings.py` and `statement_recipients.py` handle statements, frequency changes and notification recipients.
- `eft_short_names.py` builds EFT short-name search queries.
- The interim-statement service closes the active statement and creates an interim one when frequency changes.

**Accounts and routing slips**
- `payment_account.py` serializes accounts with role-dependent CFS and bank details and publishes the PAD creation event.
- `fas/routing_slip.py` and `fas/comment.py` manage routing slips and their comments.

**Hazards**
- `payment_transaction.publish_status` swallows queue errors and marks the transaction EVENT_FAILED. A COMPLETED transaction with an unpaid invoice publishes nothing. `payment_account._publish_queue_message` also swallows errors silently.
- In `distribution_code.py`, the service-fee setters (`service_fee_*`) never write to the DAO, so those changes are lost.
- `search_purchase_history` caps unfiltered requests at `TRANSACTION_REPORT_DEFAULT_TOTAL`. `statement_recipients.email` returns the last name.

**Open first**
- `distribution_code.py`: save and cascade logic.
- `payment_transaction.py`: transaction lifecycle and event publishing.
- `statement.py` and `statement_settings.py`: statement and frequency rules.
- `fee_schedule.py`: fee calculation.

# core-scaled

# Pay API service layer (`pay-api/src/pay_api/services`)

This part is the business-logic layer of a payment system. It wraps DAO models (`*Model`) in service objects whose properties sync to the DAO. It also runs the domain workflows: fees, invoices, receipts, statements, EFT, routing slips and accounting codes. Other modules call it for database queries, the Auth API and Report API (over OAuth), and a GCP queue. The notes span several jobs.

## Fee calculation and payment line items
- **Contract:** `FeeSchedule.find_by_corp_type_and_filing_type` takes corp_type, filing_type_code, valid_date, and optional quantity, is_priority, is_future_effective and waive_fees. It returns a FeeSchedule whose `total` sums fee, priority, future-effective and service fees. `PaymentLineItem.create(invoice_id, fee_schedule)` persists a line item.
- **Decisions (`fee_schedule.py`):**
  - A missing schedule raises `INVALID_CORP_OR_FILING_TYPE`.
  - An account fee override with `apply_filing_fees=False` zeroes the filing fee.
  - Priority and future-effective surcharges apply only if the DAO has them and filing fees apply.
  - `waive_fees` zeroes every amount.
  - **Decisions (`payment_line_item.py`):** A distribution code is looked up only if total or service_fees > 0. A waived amount needs `Role.STAFF`, otherwise `FEE_OVERRIDE_NOT_ALLOWED`.
- **Hazards:** The `quantity` setter multiplies in place, so repeated calls compound. The fee distribution stays None when total and service fees are 0, so downstream code may lack distribution info.

## Distribution codes
`distribution_code.py` saves or updates accounting codes and links them to fee schedules. `save_or_update` cascades `InvoiceModel.update_invoices_for_revenue_updates` only when an existing code's client, responsibility centre, service line, project code or service-fee link changes. It cascades to this code and to every code that uses it as a service fee. `stop_ejv` is reset to False on every save.
- **Hazard:** The `service_fee_*` setters change only instance variables, never the DAO, so those changes are lost.

## Invoices, references, receipts, transactions
- `invoice.py`: `find_by_id` raises `INVALID_INVOICE_ID` and enforces role checks. It also builds invoice PDFs through the Report API, finds overdue invoices, and adds `is_payment_action_required` and `is_online_banking_allowed`.
- `invoice_reference.py`: creates and finds ACTIVE and COMPLETED references.
- `receipt.py`: builds receipt PDFs and `get_nsf_receipt_details`. The NSF receipt merges all other invoices into the CC invoice.
- `payment_transaction.py`:
  - Creates transactions, cancelling any existing active one first.
  - Rejects PAD invoices, and rejects redirect URLs unless the method is CC or DIRECT_PAY.
  - `publish_status` sends COMPLETED only if the invoice is PAID, and otherwise sends TRANSACTION_FAILED.
- **Hazards:** `publish_status` swallows all errors and marks the transaction EVENT_FAILED. If the transaction is COMPLETED but the invoice is not PAID, nothing is published. `find_completed_reference_by_invoice_id` and `find_any_active_reference_by_invoice_number` do not check for None. In `__save_receipt`, a receipt with id 0 is duplicated instead of updated.

## Payments, purchase history and reports
`payment.py` creates payments, groups search results by payment id (this relies on the query ordering) and builds purchase history. `report_service.py` posts `ReportRequest` payloads to REPORT_API_BASE_URL.
- **Decisions:** An unfiltered history is capped at `TRANSACTION_REPORT_DEFAULT_TOTAL`. CSV uses `_prepare_csv_data`, and PDF fetches account contacts.
- **Hazard:** `contact['contacts'][0]` is read without a length check.

## Statements and settings
- `statement.py`: retrieves statements with `amount_owing`, computes EFT summaries and `is_eft_under_payment`, and flags overdue ones.
- `statement_settings.py`: changes frequency by ending the current setting at the period end of the longer of the old and new frequencies, then starting a new one the next day.
- Interim statements: `generate_interim_statement` closes the active statement at today. It creates an `is_interim_statement` statement, and a frequency change starts the next period tomorrow.
- **Hazard:** Rapid frequency changes can leave unapplied future settings records until a later change ends them.

## EFT, payment accounts, NSF, routing slips, recipients
- `eft_short_names.py`: `get_search_query` links a short name to accounts with link statuses (UNLINKED vs PENDING/LINKED). Amount-owing 0 also matches NULL. Branch names are stripped from account names for filtering.
- `payment_account.py`: `asdict` decides when CFS or bank details are included and masked. Queue publish failures for the PAD account-creation email are silent.
- `non_sufficient_funds.py`: totals unpaid NSF invoices and renders the PDF. It crashes if no invoices are returned.
- `fas/routing_slip.py` and `fas/comment.py`: routing slips and their comments. The daily report counts a cash slip as 1 and a cheque slip as its number of payments.
- `statement_recipients.py`: updating recipients deletes and re-saves them all. The `email` getter returns the last name.

## Open first
- `invoice.py` and `payment_transaction.py`: invoice and transaction lifecycle.
- `statement.py` and `statement_settings.py`: statement logic.
- `fee_schedule.py` and `payment_line_item.py`: fee logic.
- `eft_short_names.py`: the EFT search query.

# core#2

The notes cover the `pay_api.services` layer of pay-api, which is several loosely related domain services rather than one component. Most services wrap a SQLAlchemy model (DAO) with lazy-loaded, synced properties. They are grouped below.

**Accounting and fees**
- `distribution_code.py` saves and updates distribution codes, links them to fee schedules, and cascades invoice-revenue updates through `InvoiceModel.update_invoices_for_revenue_updates`. The cascade runs only when an existing code changes, not on creation. The `service_fee_*` setters don't write to the DAO, so those changes never persist.
- `fee_schedule.py` looks up a fee by corp type, filing type and date. It applies account-fee overrides, priority and future-effective surcharges, and `waive_fees`. The `quantity` setter multiplies in place, so repeated calls compound.
- `payment_line_item.py` creates line items with an active distribution code, and only staff may set waivers. When the total and service fees are both zero or less, no distribution is set.

**Invoices, payments and receipts**
- `invoice.py` finds invoices with an auth check and generates invoice PDFs through the Report API. It also adds dynamic fields and checks for overdue invoices.
- `invoice_reference.py` creates and finds invoice references. Two of its finders don't check for `None`.
- `payment.py` searches purchase history and builds CSV or PDF reports. Unfiltered searches are silently capped at `TRANSACTION_REPORT_DEFAULT_TOTAL`, and `search_account_payments` assumes results arrive ordered by payment id.
- `payment_transaction.py` creates transactions and cancels any active one first. It publishes status events to the queue, and a publish failure only sets `EVENT_FAILED`. A COMPLETED transaction with an unpaid invoice publishes nothing.
- `receipt.py` builds receipt details and PDFs. For NSF receipts it merges all other invoices into the credit-card invoice.
- `non_sufficient_funds.py` stores NSF records, totals unpaid NSF invoices and generates the NSF statement PDF. It crashes if no invoices are returned.
- `report_service.py` posts a camelCased payload to the report-api with the user's bearer token.

**Accounts and EFT**
- `payment_account.py` serializes accounts and shows CFS and bank details depending on payment method and user role. It publishes account-creation emails for PAD accounts only, and a publish failure is swallowed.
- `eft_short_names.py` builds the EFT short-name search query, with LINKED/UNLINKED and amount-owing filters. Account names carry a "-branch" suffix that is regex-stripped for filtering, so a mismatch makes filters fail silently.

**Statements**
- `statement.py` calculates amounts owing and EFT lookups.
- `statement_settings.py` handles frequency changes. The current setting ends at the period end of the longer of the old and new frequencies.
- Interim statements (generated when the frequency changes) close the active statement at today's date, which truncates its period.
- Summary and report generation, including the EFT under-payment flag, are covered in the notes.
- `statement_recipients.py` replaces all recipients when a list is supplied. Its `email` getter returns the last name.

**Routing slips (FAS)**
- `fas/routing_slip.py` handles search, daily reports and legacy-number validation. In the daily reports, cash counts 1 per slip but cheques count one per payment.
- `fas/comment.py` creates and lists routing-slip comments after validating that the slip exists.

**Open first:** `payment_transaction.py`, `statement.py`, `invoice.py` and `payment_account.py`.

# core-states

# Payment service layer (pay-api/src/pay_api/services)

A set of service classes over the payment DAOs/models. They handle distribution codes, EFT short names, FAS routing slips and comments, fee calculation, invoices and references, NSF, payments and purchase reports, payment accounts, line items, transactions and receipts, statements, and statement settings. They call the Auth API and Report API through `OAuthService`, publish GCP queue events, and generate PDF/CSV reports. Most classes wrap a lazily loaded DAO whose properties sync to it.

## Contract
- **Report API**: `ReportService.get_report_response()` posts a camelCase payload (reportName, templateName, templateVars, populatePageNumber) to `REPORT_API_BASE_URL` with the user's bearer token. `Invoice.create_invoice_pdf`, `Receipt.create_receipt`, NSF PDFs and `PaymentService.generate_payment_report` all go through it or OAuth directly.
- **Auth API** (`AUTH_API_ENDPOINT`): supplies org and contact info for invoice, NSF and payment PDFs.
- **Queue**: `PaymentTransaction.publish_status` sends a PaymentToken (invoice id, status, filing_id, corp_type) with camelCase keys. `PaymentAccount._publish_queue_message` sends account-creation mailer events.
- **Search/report outputs**: paginated dicts `{total, page, limit, items}`; statement reports return `(report_response, report_name)`.

## Decisions
- `FeeSchedule.find_by_corp_type_and_filing_type`: raises INVALID_CORP_OR_FILING_TYPE if the schedule is missing. An account fee with `apply_filing_fees=False` zeroes the fee. Priority and future-effective fees are added only when flagged. `waive_fees` zeroes all fees.
- `PaymentLineItem.create`: finds the active DistributionCode only if total or service_fees > 0. Waived fees require `Role.STAFF`, otherwise FEE_OVERRIDE_NOT_ALLOWED.
- `DistributionCode.save_or_update`: on an existing record, a change to client, responsibilityCentre, serviceLine, projectCode or serviceFeeDistributionCodeId calls `InvoiceModel.update_invoices_for_revenue_updates` for the code and for every code that uses it as a service fee. Creation never cascades. It always resets `stop_ejv=False`.
- `Invoice.find_by_id`: raises INVALID_INVOICE_ID if missing; `_check_for_auth` runs unless `skip_auth_check`.
- `Invoice._add_dynamic_fields`: sets `is_payment_action_required` when status is CREATED and the method is DIRECT_PAY, CC or ONLINE_BANKING. Online banking is disallowed if any line item has future-effective fees.
- `PaymentTransaction`:
  - `create_transaction_for_payment` requires a payment in CREATED status (else INVALID_PAYMENT_ID).
  - `create_transaction_for_invoice` rejects PAD (INVALID_TRANSACTION).
  - `_create_transaction` rejects COMPLETED or DELETED payments (COMPLETED_PAYMENT) and cancels any active transaction first.
  - The redirect URL is validated only for CC and DIRECT_PAY.
  - `publish_status` publishes COMPLETED only when the invoice is PAID. If the transaction is COMPLETED but the invoice is not PAID, it publishes nothing. All other cases publish TRANSACTION_FAILED. A publish error sets the status to EVENT_FAILED.
- `Receipt.get_receipt_details`: PAD, EJV and EFT invoices that are not PAID are treated as pending, so the receipt number is None. It raises an error if the invoice is not pending and has no receipts.
- `Receipt.get_nsf_receipt_details`: merges all invoices for the payment into the CC invoice.
- `PaymentAccount.asdict`: CFS details appear for PAD, ONLINE_BANKING and EFT, and for DRAWDOWN with a pending PAD activation. Bank number and bank info are gated by user role.
- `Statement`:
  - `find_by_account_id` orders by to_date, then frequency priority.
  - `is_eft_statement` decides whether an EFT summary is added to the report.
  - `get_summary` sets `is_eft_under_payment` when the linked short-name credit balance is greater than 0 but less than the amount owing.
- `StatementService.generate_interim_statement`: closes the active statement today, builds an interim statement with `NotificationStatus.PENDING` or `SKIP`, then updates the settings frequency.
- `StatementSettings.update_statement_settings`: ends a not-yet-active future record today. It ends the current record at the period end of the longer of the old and new frequencies, then starts a new record the next day.
- `StatementRecipients.update_statement_notification_details`: replaces all recipients when `recipients` is not None.
- `Comment.create` and `RoutingSlip.find_by_number` and its siblings: raise FAS_INVALID_ROUTING_SLIP_NUMBER when the slip is missing. `RoutingSlip.validate_and_find_by_number` checks digits unless `ALLOW_LEGACY_ROUTING_SLIPS`.
- `EFTShortnames.get_search_query`: LINKED means PENDING or LINKED status; UNLINKED means no links with status other than UNLINKED. An `amount_owing` of 0 also matches NULL.
- `PaymentService.search_purchase_history`: unfiltered requests are capped at `TRANSACTION_REPORT_DEFAULT_TOTAL`.
- `Payment.create`: `payment_status` defaults to `PaymentStatus.CREATED.value`.

## Hazards
- `DistributionCode` `service_fee_*` setters change only instance variables, never the DAO, so the changes are not persisted.
- Failures publishing account-creation events, and transaction status events, are swallowed. The only trace is a log line or an EVENT_FAILED status.
- Unchecked indexing crashes: `contact['contacts'][0]` in `generate_payment_report`, and `invoice['invoices'][0]` in the NSF PDF.
- Smaller traps:
  - `StatementRecipients.email` returns the last name.
  - `__save_receipt` treats id 0 as new and duplicates the receipt.
  - `Payment.search_account_payments` groups rows by payment.id and relies on the query being ordered by it.

## Open first
- `payment_transaction.py`: transaction lifecycle, queue publishing and receipts.
- `statement.py`: statement queries, EFT reports and the interim statement logic.
- `invoice.py`: invoice lookup, PDF creation and dynamic fields.
- `distribution_code.py`: the revenue-update cascade.

# core-states#2

# pay-api service layer: accounts, invoices, statements, EFT, reports

This part of pay-api (`pay_api/services/`) holds the business logic between the REST resources and the SQLAlchemy models. Most classes wrap a model DAO with lazy loading and properties that sync both ways. It reads and writes the DB, calls the Auth API, Report API and CFS through `OAuthService`, and publishes GCP queue events.

## Contract
- **In:** account ids (`auth_account_id`), invoice/payment/statement ids, routing slip numbers, and JSON dicts from the resource layer.
- **Out:** serialized dicts (via `*Schema`), service objects, or `(report_response, report_name)` tuples.
- **Report API:** `ReportService.get_report_response` POSTs a camelCase payload (`reportName`, `templateName`, `templateVars`, `populatePageNumber`) to `REPORT_API_BASE_URL` with the user's bearer token. Receipts, invoice PDFs, NSF statements and statement reports all go through it.
- **Queue:** `payment_transaction.publish_status` sends a camelCased `PaymentToken` (invoice id, status, filing_id, corp_type). `payment_account.publish_account_mailer_event_on_creation` sends account-creation mail events.

## Decisions
- `distribution_code.save_or_update`: if client, responsibilityCentre, serviceLine, projectCode or serviceFeeDistributionCodeId changed on an existing code, it calls `InvoiceModel.update_invoices_for_revenue_updates` for that code and for every code using it as service fee. Creation never cascades. It always resets `stop_ejv` to False.
- `fee_schedule.find_by_corp_type_and_filing_type` raises `INVALID_CORP_OR_FILING_TYPE` if no schedule matches.
  - An account fee with `apply_filing_fees` False zeroes `fee_amount`.
  - Priority and future-effective fees are added only when `apply_filing_fees` is true.
  - `waive_fees` zeroes all fees.
- `payment_line_item.create`: a distribution code is looked up only if total or service fees are greater than 0. A waived amount without `Role.STAFF` raises `FEE_OVERRIDE_NOT_ALLOWED`.
- `payment_transaction`:
  - `create_transaction_for_payment` requires status CREATED, else `INVALID_PAYMENT_ID`.
  - `create_transaction_for_invoice` refuses PAD invoices (`INVALID_TRANSACTION`).
  - `_create_transaction` raises `COMPLETED_PAYMENT` if the payment is COMPLETED or DELETED. It cancels any open transaction before creating a new one.
  - A redirect URL is validated only for CC and DIRECT_PAY.
- `publish_status`: COMPLETED with the invoice PAID publishes COMPLETED. COMPLETED with the invoice not PAID publishes nothing. Anything else publishes TRANSACTION_FAILED. A publish error sets the transaction to EVENT_FAILED.
- `invoice.find_by_id` raises `INVALID_INVOICE_ID` if missing and runs `_check_for_auth` unless `skip_auth_check`.
- `fas/comment` and `fas/routing_slip`: a missing routing slip raises `FAS_INVALID_ROUTING_SLIP_NUMBER`. `routing_slip.validate_and_find_by_number` skips digit validation when `ALLOW_LEGACY_ROUTING_SLIPS` is set. `create_daily_reports` skips VOID slips and posts totals to `OAuthService`.
- `payment_account.asdict`: CFS details appear for PAD, ONLINE_BANKING and EFT, and for DRAWDOWN with a pending PAD activation (`_is_pad_in_pending_activation`). Bank number masking and bank info depend on user role.
- `statement_settings.update_statement_settings`: a frequency change ends the current setting at the period end of the longer of the old and new frequencies (`_find_longest_frequency`). The new setting starts the next day.
- `statement_service.generate_interim_statement`: returns None if no active settings exist. Otherwise it closes the active statement today, creates an interim statement and its invoice links, and updates the frequency.
- `statement.get_summary`: `is_eft_under_payment` is true only if there is a linked or pending short name and 0 < EFT credit < amount owing.
- `eft_short_names.get_search_query`: UNLINKED means no links with status other than UNLINKED. LINKED means PENDING or LINKED.
- `non_sufficient_funds.query_all_non_sufficient_funds_invoices`: sums unpaid NSF invoices and excludes PAID.
- `receipt.get_receipt_details`: raises an error if the invoice is not pending and has no receipts. `get_nsf_receipt_details` merges all invoices into the CC invoice.
- `payment.search_purchase_history`: an unfiltered search is capped to `TRANSACTION_REPORT_DEFAULT_TOTAL`.
- `statement_recipients.update_statement_notification_details`: if `recipients` is not None, it deletes all existing recipients and re-inserts the new list.

## Hazards
- `distribution_code`: the `service_fee_*` setters update only instance variables, never `_dao`, so changes are not persisted.
- `payment_transaction.publish_status` and `payment_account._publish_queue_message` swallow every exception. Failed queue events are silent or only marked EVENT_FAILED. A COMPLETED transaction with an unpaid invoice drops its event.
- `statement_recipients` email getter returns `_lastname`. Several report paths index `[0]` without a length check, for example `contact['contacts'][0]` in `payment.generate_payment_report` and `invoice['invoices'][0]['id']` in `non_sufficient_funds.create_non_sufficient_funds_statement_pdf`.

## Open first
- `statement.py`: statement lookup, amount owing, summaries and report generation, plus `statement_settings.py` and the interim statement service.
- `payment_transaction.py`: transaction lifecycle, receipt saving and queue publishing.
- `payment.py`: purchase history and payment report generation.
- `distribution_code.py`: revenue-update cascade, with `fee_schedule.py` and `payment_line_item.py` for fee calculation.
