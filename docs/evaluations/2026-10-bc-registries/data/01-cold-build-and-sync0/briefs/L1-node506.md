<!-- level 1, node 506, children [7, 270, 272, 278, 279, 281, 322, 323, 333, 359, 393, 406, 407, 413, 418, 419, 427, 432, 443, 609, 610] -->

# PayBC-style payments/auth platform (BC Registries): test-suite and code brief

The source material is condensed notes on a BC Province (Apache 2.0) payments and auth codebase. Most of it is pytest suites, factories and mocks, and some is production code. It covers `pay_api`, the pay jobs, `auth_api`, `bcol_api`, the pay-queue EFT parsing, and a PayBC invoice/receipt fixture set.

## 1. PayBC fixtures and schemas
- **Invoices:** 10021, 10022, 10023 and a credit-memo variant. All share one test fixture:
  - ABC Co-Ops (account 4101), 2019-04-12, amount 100.
  - pbc_ref_number 10005, party 11111, site 29921.
  - WTS-INVOICE-STANDARD, term IMMEDIATE, status OP.
  - The attribute1–15 fields are null.
- **Line items:** Each invoice has one identical "Test Memo Line" (price 100, quantity 1).
- **Receipts:** 123451–123453 apply to invoice 10021 (receipt_amount 10.02, amount_applied 9.85).
- **Schemas:** The invoice schema has 22 fields, and the OpenAPI schema lists `credit_memo_number`.
- **Caution:**
  - Amounts are integers, so cents may be lost against receipts like 10.02.
  - amount_applied (9.85) differs from amount_to_apply ($9.5).
  - 123451 and 123452 are duplicate fixtures.
  - `credit_memo_number` is described as "Invoice Number".

## 2. EFT short names (pay-api / pay-queue)
- **Models, DTOs and API**
  - Models and schemas: `EFTShortnames`, the links model (statuses LINKED/PENDING/INACTIVE/PENDING_REFUND) and `EFTShortnamesHistorical`. All use `__mapper_args__` whitelists, so unmapped columns are silently dropped.
  - Request DTOs: `EFTShortNameGetRequest`, `EFTShortNameSummaryGetRequest`, `EFTShortNameRefundPatchRequest`, `EFTShortNameRefundGetRequest`.
  - Blueprint `/eft-shortnames` requires the SYSTEM and MANAGE_EFT roles. `/shortname-refund` has GET, POST (202) and PATCH, and PATCH needs `EFT_REFUND_APPROVER`.
- **Services**
  - `EFTShortnameHistorical`: five `create_*` methods plus `search`. `isReversible` is true only for a STATEMENT_PAID entry within 60 days whose latest state is not processing.
  - Short name service: payment actions APPLY_CREDITS, CANCEL and REVERSE, plus link create, patch and delete.
  - `EFTRefundService`: create, update (approve or decline), `handle_invoice_refund` and `reverse_eft_credits` / `refund_eft_credits`.
  - EFT payment service (invoice creation is deferred to a job).
  - Reversal pipeline (60-day window from the oldest EFT payment; statement_id required).
  - Credit service (`apply_eft_credit`, `process_owing_statements`).
  - Query builders: UNLINKED, and LINKED means PENDING or LINKED.
- **Reconciliation of the TDI17 bank file**
  - Parsers: `EFTBase`, `EFTHeader` (type 1), `EFTRecord` (type 2), `EFTTrailer` (type 7). They use fixed-width columns, 140 characters per line, with amounts in cents. `EFTError` has 13 codes.
  - Reconciliation enums: SourceTransaction, RecordType, Column, Status, TargetTransaction. `CREDIT_MEMO` = 'CM' in both SourceTransaction and TargetTransaction.
  - Workflow: parse, then validate the header and trailer, filter by location_id, validate the transactions, aggregate per shortname, create credits, apply pending payments. Any error rolls back and marks the file FAILED with an error email. Header and trailer rows are saved only when they have errors.
  - The tests cover failure, basic, full and rerun scenarios, plus `generate_tdi17_file` generators.
- **Email templates**
  - Refund issued, refund request decision, payment reversed.
  - BC Registries contact: 1-877-526-1526.
- **Caution**
  - A single transaction error fails the whole file.
  - Broad `except` blocks swallow errors.
  - `apply_eft_credit()` returns silently when the balance is insufficient.
  - `handle_invoice_refund` does not handle PENDING_REFUND or CANCELLED.
  - The `PATCH /shortname-refund` log text names the wrong function.
  - `create_funds_received` lacks `@user_context`.
  - The 60-day reversal window has several blocking states.
  - Link-endpoint authentication is incomplete: three routes lack `@_jwt.requires_auth`.

## 3. Pay-api tests, services and factories
- **API tests**
  - Accounts: POST needs the SYSTEM role. It returns 201 (sync) or 202 (async: EFT, unlinked PAD, online banking, CFS down).
  - Account fees (MANAGE_ACCOUNTS): TRF01 gives 1.5 and TRF02 gives 1.0.
  - Payment requests: all payment methods, fee waivers (staff only), the `ACCOUNT_IN_PAD_CONFIRMATION_PERIOD` error, and routing-slip blocks.
  - Other suites: routing slips (FAS), refunds, statements, transactions, bank-account verification, fees and distributions, codes, meta/ops, and CORS preflight on about 16 endpoints.
- **Service and model tests**
  - Payment-system factory selection, and Direct Pay, PAD, CFS, BCOL and PayBC services.
  - Fee schedule, invoice, invoice reference, payment line items and refunds.
  - Payment, payment account and payment transaction services.
  - Statement and statement settings, with interim statements on payment-method change.
  - Statement recipients, receipts, NSF, and distribution codes.
  - OAuth, Hashing, Notify and Flags services, config, and business-day/holiday utilities.
- **Factories**
  - Most return unsaved objects. Only some (such as `factory_statement_settings` and the EFT factories) call `.save()`.
  - `factory_statement` evaluates `datetime.now()` once, at definition time.
- **Caution**
  - Some tests assert nothing or assert `True`.
  - Some test names or docstrings contradict their assertions (for example "200" versus 400).
  - Unreachable assertions appear after `with` blocks.
  - Mocks and monkeypatches can hide signature changes.
  - `@skip_in_pod` tests are skipped in pod environments.
  - Invalid lookups often return an object with `id=None`, not None.
  - `RefundService` has recursive getters and mistyped setters.
  - `get_refund_partials_by_payment_line_item_id` has a likely filter bug.

## 4. Pay jobs / tasks
- **Runner:** The runner dispatches 15 job types. About 19 tiny shell wrappers run `python3 invoke_jobs.py <JOB>`. They have no error handling. The `UPDATE_STALE_PAYMENTS` script echoes `STALE_PAYMENT`, which mismatches its command.
- **CFS accounts and invoices**
  - `CreateAccountTask`, `ActivatePadAccountTask` (PAD activation after a confirmation period) and `CreateInvoiceTask`.
  - `create_invoices()` covers PAD, EFT, online banking and routing slip. The RS and PAD paths share a 10s sleep and then `CFSService.get_invoice()` after a failed create.
  - EFT/online-banking creation sets SETTLEMENT_SCHEDULED.
  - A FREEZE account gets no InvoiceReference.
- **EFT linking and reversal:** Link receipts are named `EFTCIL{id}`. The link and reverse jobs capture errors per link in Sentry and continue.
- **EJV and AP file generation**
  - `CgiEjv`, `CgiAP`, `EjvPartnerDistributionTask`, `EjvPaymentTask` and `ApTask`. They use fixed-width files with the chr(29) delimiter and an FTP/Minio upload.
  - The `batch_type` filter is inverted for non-GA batches.
- **Routing-slip state transitions:** link, correction, void and applying slips to invoices.
- **Reconciliation and refunds:** `DirectPayAutomatedRefundTask`, BCOL refund sync, `DistributionTask` (`STATUS_NOT_PROCESSED` is named backwards) and `StalePaymentTask`.
- **Notifications and statements**
  - Statement generation: weekly on Sunday (`weekday()==6`) and monthly on day 1.
  - Notification timeline: reminder 7 days before, due, then overdue (account lock).
  - Other tasks: `StatementNotificationTask`, `UnpaidInvoiceNotifyTask` (exact deadline day, online banking only) and the mailer publishers.
- **Caution**
  - Broad exceptions swallow failures.
  - Time-dependent behavior: freeze_time placement, 08:00 UTC statements-due, and a 6–8 UTC refund cron against CAS feedback arriving after 11pm.
  - An f-string SQL injection risk in the BCOL sync.
  - A PAD timezone comparison.
  - Several modules are truncated to imports (EFT, statements-due, offline invoice creation), so their correctness is unknown.

## 5. bcol_api
- **Endpoint tests:** `/api/v1/bcol-profiles`, `/payments`, `/profiles`, `/meta/info` and `/ops/healthz|readyz`.
- **Other tests:** The config loader, version, BcolProfile service and the BcolSoap singleton.
- **Fixtures:** LDAP, SOAP and JWT mocks with a hardcoded profile (PB25020).
- **Caution**
  - REJECTED orgs do not block reuse of a `bcol_id`.
  - The two profile mocks return identical data.
  - MockLDAP's `search_s` returns a scalar string, not a list of tuples.
  - Payments fields accept empty strings.

## 6. auth_api
- **Affiliation invitations**
  - API, model and service tests cover create, delete, get, update, expire, accept, authorize and reject.
  - The reject endpoint returns FAILED. Invitations expire by computed time.
  - REQUEST-type invitations never expire. Org-scoped queries match both from-org and to-org.
- **Team-member invitations:** Login-source rules: a BCEID ADMIN gets PENDING_STAFF_REVIEW. GOVM orgs auto-approve. `login_source` is cleared after acceptance.
- **Affiliation service**
  - Passcode checks, delete rules (not idempotent, environment-scoped) and visibility rules (TMP is hidden if INC exists).
  - `fix_stale_affiliations`.
- **Product subscriptions**
  - The approve, reject, hold and resubmit flow for MHR qualified suppliers. Resubmission needs both REJECTED and `can_resubmit`.
  - Parent and child products share a status.
  - Notification payloads.
  - Keycloak group sync: ADD only if membership and subscription are both ACTIVE.
- **Other suites**
  - Tasks / staff review, users (OTP, terms of use, affidavits), and `check_auth()` paths.
  - Org payment integration with a mocked pay-api, and `OrgService`, `UserService` and `ProductService`.
  - Model-level tests for Affiliation, AffiliationInvitation and Invitation.
- **Caution**
  - The autouse pub/sub mock always raises from `publish()`.
  - Tests patch `check_auth` to True.
  - There are order-dependent `MAX_NUMBER_OF_ORGS` restores.
  - Duplicated and unreachable assertions.
  - An `UnboundLocalError` inconsistency in `check_auth`.
  - `ActivityLogPublisher` is mocked, so its calls are matched with `ANY`.
  - The Keycloak parent/child test mutates the DB (`keycloak_group`, `parent_code`), which risks leaking into other tests.
