<!-- level 1, node 506, children [270, 272, 278, 279, 281, 322, 323, 333, 359, 393, 406, 407, 413, 418, 419, 427, 428, 432, 443] -->

# Parent brief: BC Registries payments/auth codebase (EFT short names, pay-api, jobs, auth-api, bcol-api)

## Scope
Condensed notes on several related BC Registries (Province of British Columbia, Apache 2.0) Python/Flask services and their pytest suites:
- **pay-api**: EFT short names, refunds, statements, accounts, payment requests, routing slips (FAS), fees.
- **pay-queue**: TDI17 EFT file parsing and reconciliation.
- **jobs/tasks**: batch jobs that talk to CFS/CAS/PayBC.
- **bcol-api**: BC Online profiles and payments.
- **auth-api**: orgs, users, products, invitations, affiliations.

## 1. EFT short-name feature (pay-api)
- **Endpoints**
  - `/eft-shortnames` (roles SYSTEM, MANAGE_EFT) covers search, summaries, history, links and `/payment`. Payment actions are `APPLY_CREDITS`, `CANCEL` and `REVERSE`.
  - `/shortname-refund` has GET, POST (202) and PATCH `/<id>`. PATCH is for `EFT_REFUND_APPROVER` only.
- **Services**
  - `EFTRefundService`: create, update, `handle_invoice_refund`, and credit reverse/refund.
  - `EFTShortnameHistorical`: five `create_*` methods plus `search` with the derived `is_reversible_statement` flag.
  - EFT credit service: `apply_eft_credit`, `process_owing_statements`.
  - Reversal pipeline: `reverse_payment_action`.
  - Link management: statuses PENDING, LINKED, INACTIVE, PENDING_REFUND, REFUNDED, COMPLETED, CANCELLED.
- **Models and DTOs**
  - Models: `EFTShortnames`, links, `EFTShortnamesHistorical`. Their `__mapper_args__` whitelists silently drop unlisted columns.
  - DTOs: `EFTShortNameGetRequest`, `SummaryGetRequest`, `RefundPatchRequest`.
- **Tests and factories**
  - Tests: payment action, history, links, search, summaries, refund API, invoice refund (6 cases), CORS preflight.
  - Factories: `factory_eft_*`.
  - Data helpers: `create_eft_summary_search_data`, `create_eft_search_data`.

## 2. TDI17 file parsing and reconciliation (pay-queue)
- **Parsers**
  - `EFTBase` is the shared base.
  - `EFTHeader` (type 1), `EFTRecord` (type 2) and `EFTTrailer` (type 7) are fixed-width, 140 characters per line.
  - Errors are modeled by `EFTError` and `EFTParseError`.
  - Reconciliation enums are `SourceTransaction`, `RecordType`, `Column`, `Status` and `TargetTransaction`.
- **Pipeline**
  - Steps: parse, validate, filter by location, aggregate per shortname, create credits, apply pending payments.
  - Any error rolls back and marks the file FAILED.
  - Failures send an error email through the notify API.
  - Amounts are in cents.

## 3. Jobs/tasks (batch, CFS/CAS integration)
- **Runner**
  - `invoke_jobs.py <JOB_NAME>` dispatches 15 job types.
  - There are about 19 trivial shell wrappers, one per job, with no error handling.
- **CFS and invoicing**
  - CFS account creation and PAD activation.
  - Invoice creation for PAD, EFT, Online Banking and routing slips (RS).
  - EFT link/reverse receipts via the `EFTCIL{id}` receipt number.
  - Routing-slip link, correction and void.
- **Disbursement and refunds**
  - EJV and AP CGI feeder files.
  - Direct Pay refunds, the BCOL refund sync, distribution fixes and stale payments.
- **Statements and notifications**
  - Statement generation and statements-due notifications.
  - Unpaid-invoice and statement notifications to the mailer.
- **Tests**
  - Tests for the above, including statement/payment-method transitions, using `freeze_time`.

## 4. pay-api test suites (API, service, model, utils)
- **Accounts and payment requests**
  - Account create/update (201 sync, 202 async).
  - Fees: `TRF01`=1.5, `TRF02`=1.0.
  - Payment requests by method.
  - Routing slips (FAS).
  - Refunds, statements, transactions.
- **Services and utils**
  - Service tests: BCOL, PayBC, DirectPay, OAuth, flags, hashing, notify.
  - Utils: business-day and holiday calculations.
  - Config/version/ops/meta tests, and CORS preflight tests for all endpoints.
- **General RefundService**
  - Covers routing-slip and invoice refunds, with partial-refund helpers.
- **Email templates**
  - Refund issued, refund decision, payment reversed.

## 5. bcol-api tests
- Endpoints: bcol-profiles (409 on a duplicate active `bcol_id`), payments, profiles, meta and ops.
- Mocks: `MockLDAP`, SOAP profile/payment mocks and JWT helpers.
- Other: config loader, `BcolSoap` singleton.

## 6. auth-api suites
- **Org and user**
  - Task API (staff review), user API, `check_auth()`.
  - Org payment integration with a mocked pay-api, `OrgService`, `UserService`.
- **Products**
  - `ProductService` subscriptions.
  - Qualified-supplier (MHR) approve, reject and resubmit flows.
  - Keycloak group sync.
  - Product notifications.
- **Invitations and affiliations**
  - Affiliation invitations and regular invitations, covering API, model and service levels.
  - Affiliations, and login-source rules (GOVM vs REGULAR).

## Cross-cutting cautions
- **Status codes follow state.** 202 means async work (EFT, unlinked PAD, online banking, CFS down). 201 and 200 are synchronous. Bank verification returns 200 even for invalid accounts.
- **Broad exceptions.** Most jobs and tasks use broad `except` blocks that log to Sentry and continue. This hides failures. The CFS create-then-GET retry uses a blind 10s sleep.
- **Weak or dead tests.**
  - Several tests assert `True`.
  - Some assertions come after a `with pytest.raises` block and never run.
  - Some tests are skipped with `@skip_in_pod`, some copy-pasted docstrings are wrong, and some tests have duplicated assertions.
- **Test pollution.** Config or flag resets happen after the assertions (`ALLOW_LEGACY_ROUTING_SLIPS`, `MAX_NUMBER_OF_ORGS`). Hardcoded ids and usernames can collide. Factories are inconsistent about calling `.save()`.
- **Notable code bugs flagged.**
  - `RefundService` `requested_by`/`decision_made_by` getters recurse infinitely, and `get_refund_partials_by_payment_line_item_id` filters on the wrong column.
  - The `PATCH /shortname-refund` log line names the wrong function.
  - `create_funds_received` lacks `@user_context`.
  - The EJV `batch_type` filter looks inverted for non-GA batches.
  - The `StatementNotificationTask` walrus expression assigns a boolean, not a length.
  - `DistributionTask.STATUS_NOT_PROCESSED` is named backwards.
  - The `_create_statement_records` class variables leak dates between calls.
  - The routing-slip docstring says "pending" but the query uses LINKED.
  - Blueprint routes lacking `@_jwt.requires_auth`.
  - The f-string SQL in the BCOL sync is an injection risk.
  - The `MockLDAP` return type is wrong.
  - Some modules are truncated to imports, so correctness can't be judged (the EFT task, the EJV tasks, statements-due, the statement service).
- **Business rules worth remembering.**
  - **Reversal:** a statement reversal needs payment within 60 days and all invoices PAID. Any PENDING, PENDING_REFUND or REFUNDED link blocks it.
  - **Refund editing:** refunds are editable only while PENDING_APPROVAL.
  - **Consolidated invoices:** consolidated-invoice refunds are forbidden.
  - **`apply_eft_credit`:** it returns silently on insufficient balance.
  - **Rejected orgs:** REJECTED orgs don't block `bcol_id` reuse.
  - **Parent and child products:** they share status in the MHR flows.
  - **Resubmission:** it needs both REJECTED and `can_resubmit`.
  - **GOVM orgs:** they auto-approve and require a STAFF login source.
  - **`login_source`:** it is cleared after an invitation is accepted.
  - **Time-sensitive jobs:** the statements-due job must run at 08:00 UTC or later, after the statements job. The Direct Pay refund cron runs 6–8 UTC, but CAS feedback arrives after 11pm.
