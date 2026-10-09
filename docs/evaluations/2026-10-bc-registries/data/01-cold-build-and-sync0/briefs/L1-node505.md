<!-- level 1, node 505, children [55, 89, 120, 280, 292, 315, 334, 369, 373, 408, 462, 463, 465, 466, 471, 474, 480, 596, 597, 606, 607, 608, 631, 632, 633, 634, 635] -->

# Parent Brief: BC Registries Notebooks, Migrations, Models and Tests

This brief covers a BC Registries (Province of British Columbia) codebase family. It spans the entity/LEAR, auth and pay services. Use it to route to the right child brief.

## 1. Reporting notebooks and schedulers (Postgres, papermill)
- **Entity/LEAR stats notebooks**
  - Cooperative monthly stats, Filings Monthly Stats (CP COMPLETED), and firms (SP/GP) by city and postal code.
  - Daily incorporation stats (previous day PST), written to `incorporation_filings_daily_stats_{datestr}.csv`.
  - Gazette CP/XCP notebooks: one inserts into `sent_to_gazette`, the other UPDATEs `sent_to_gazette_date`.
  - `from_openshift.txt` and BCFN_MR (fixed-width master record, gzipped).
  - CRA `request_tracker` unprocessed requests, and Filing Issues (PAID but not completed filings, uploaded to Google Sheets with a Rocket Chat post).
- **Auth Weekly Stats**: `auth_weekly_stats_till_YYYY-MM-DD.csv`.
- **Pay notebooks** (parameterized by `partner_code`: CSO, VS, RPT, ESRA)
  - Invoice Reconciliation Daily and Monthly: the monthly one has a disbursement query for CSO/VS and a revenue_letter PDF.
  - Pay Weekly Stats.
- **Scheduler modules** (Flask + papermill + SMTP, `.env` → `Config`)
  - Config-only modules, an error-alert runner with an FTP/SFTP step (NUANS), report schedulers that email CSV output, and a partner reconciliation scheduler.
  - Their tests cover `app`/`client_ctx` fixtures, DB and SFTP connection tests, and notebook report tests.
- **Cautions**
  - Hardcoded credentials and dates (Filing Issues, CRA).
  - Timezone inconsistencies (PST ignoring DST, conversion applied in only some queries).
  - The `from_openshift` `%%sql` magic failure.
  - Misspelled variable names.
  - Env vars defaulting to `''` fail silently.
  - Email routing keyed on the notebook basename can silently skip the email.
  - Temp files accumulate.
  - The monthly and daily jobs both run on the 1st.

## 2. Data reset tool (`data_reset_tool`, v2.17.0)
- A Flask + Postgres fixture tool for exporting, importing and deleting business data as JSON, Excel, CSV or ZIP.
- Routes are under `/api/fixture/*`.
- It covers packaging config, the `create_app` and config classes, and import/export/delete over 14–23 tables.
- Cautions: SQL injection through f-strings, the DB connection created at import time, a silent default to production, and only CP/XCP identifiers accepted.

## 3. Alembic scaffolding and migrations
- **Boilerplate**: README stub, `alembic.ini` logging variants (some with `file_template` and a table exclusion list), `env.py` variants, and `script.py.mako`.
- **Concrete migration `786dac4b44ef`**: creates `message_processing`.
- **Pay migrations**
  - Nullable columns and backfills.
  - Indexes.
  - `non_sufficient_funds`.
  - History-table rollout (`fb3ba97b603a`, `52ed2340a43c`).
  - `eft_refund_email_list` lifecycle.
  - Statement timeouts: 20 s standard, up to 15 min for some.
- **Auth migrations**
  - Column adds and alters.
  - Indexes.
  - Status lookups.
  - ToS/documents seed data.
  - Merge migrations.
  - A foundational root migration.
  - `product_migration_for_vs` (`31ec16d4f1e9`).
- **Cautions**
  - Irreversible or empty downgrades.
  - SQL injection via f-strings.
  - NOT NULL downgrades that fail on existing NULLs.
  - Ignore auto-generated FKs on `distribution_codes_history`.
  - Parent-revision mismatches.
  - The `786dac4b44ef` downgrade drops a nonexistent index.

## 4. Pay API (models, schemas, services)
- **Invoice and Payment**: models, schemas, endpoints (`/payments/queries` and `/reports`), search and the cattrs `Converter`.
- **Payment systems**: abstract base, CFS/PayBC, DirectPay.
- **Domain services**: fees, distribution codes, accounts, transactions and statements.
- **Model layer**
  - About 50 model/schema pairs, base/audit/code-table infrastructure, fees and accounts.
  - The status-code tables (`CfsAccountStatusCode` and others), plus `StatementInvoices`.
- **EFT module**: EFTCredit, EFTCreditInvoiceLink, EFTFile, EFTRefund, EFTTransaction, EjvLink, Refund, `EftService`, TDI17 parser tests and API tests.
- **Cautions**
  - `include_properties` whitelists must be kept in sync by hand.
  - The EFTRefund missing comma bug.
  - The `update_transaction` short-payment behavior.
  - Hardcoded decorator argument indexes.

## 5. Auth API (models, schemas, services)
- **Affiliations and invitations**
  - Affiliation, AffiliationInvitation and Invitation services and models.
  - Team invitations.
  - REQUEST invitations never expire.
- **Org, Membership, User and Task services**
  - Routes, `user_context`/`check_auth` and exceptions.
  - Org lifecycle: soft delete, GOVM, BCOL, suspension and affidavit review.
- **Products**
  - `ProductCode`, `ProductSubscription` and the `Product` service (create and resubmit).
- **Model layer**: code-table models, plain classes (`UserSettings`, `SimpleOrgInfoSchema`) and schema field remaps.
- **Bootstrap**: db/ma setup, `BaseModel`, `Contact`/`ContactLink`, `User`, `Entity`, `Authorizations` view, DTOs and ops scripts.
- **Vendored third-party code**: unrelated Chai and user-agent bundles.
- **Cautions**
  - Silent skips, such as premium products for non-premium orgs.
  - Hardcoded default IDs.
  - `User.delete()` is a no-op.
  - Field remaps silently drop data.

## 6. Legal API models and the filer
- **`legal_api` models**
  - Business, Filing, Address, Office, Party and PartyRole.
  - ShareClass and ShareSeries, with a skip flag for COLIN legacy migration.
  - Alias, Amalgamation, Batch, BatchProcessing, Furnishing, Review and ReviewResult, RequestTracker, XmlPayload, ColinEventId, RegistrationBootstrap, Comment, Configuration and User.
  - Filings enums and the package exports.
- **Digital credentials**: DCConnection, DCDefinition, DCIssuedCredential, DCIssuedBusinessUserCredential, the `DCRevocationReason` enum and `DigitalCredentialsHelpers`.
- **Entity filer** (`cb_subscription_handler`, NATS)
  - `process_filing` dispatches to processors for incorporation, registration, conversion, annualReport, changeOfRegistration, correction, dissolution and putBackOn.
  - Shared helpers cover parties, offices, shares, aliases, business profile and court orders.
  - Single-message processing.
- **NAICS**
  - `NaicsStructure` and `NaicsElement` models.
  - Search at `GET /api/v2/naics` and lookup by code or key.
  - `NaicsService`.
  - The Reviews API (NATS publish) is unrelated to NAICS.
- **Cautions**
  - Errors are swallowed through `suppress` and bare `except`.
  - +8h `start_date` offsets.
  - `update_filing_court_order` tests the wrong variable.
  - `DCDefinition.deactivate()` uses f-string SQL.
  - Many finders return lists vs single objects inconsistently.

## 7. Test infrastructure
- **Fixtures** (`conftest`-style)
  - Core fixtures: `app`, `db` (destructive drop and Alembic upgrade), `session` (nested savepoint rollback), `client` and `jwt`.
  - NATS/STAN: `stan`, `entity_stan`, `stan_server`, `create_mock_coro`.
  - Mocks: `verify_jwt`, the Pub/Sub emulator and minio.
  - Skip-decorator markers gated by env vars (`RUN_COLIN_API`, `RUN_AFFILIATION_TESTS`, `RUN_NAMEX_API`, `POD_TESTING`).
- **Test modules**
  - Shared constants: `FROZEN_DATETIME`, `EPOCH_DATETIME`, `add_years`.
  - STAN connect tests.
  - GCP PubSub payment worker tests (`test_complete_worker`).
  - Queue helpers.
- **Cautions**
  - Fragile savepoint logic that reads the private `_parent` attribute.
  - Deprecated `asyncio.Future(loop=...)`.
  - The invalid `@pytest.fixture('function')`.
  - Skip markers use an `is False` check.
  - Raw f-string SQL in `create_filing`.
  - Hardcoded sleeps.

## Cross-cutting cautions
- Many models use an explicit `__mapper_args__['include_properties']` whitelist so rolling upgrades work. New columns must be added to it by hand.
- F-string SQL appears in migrations, the data reset tool, models and tests.
- Silent failure patterns are widespread: broad exception handlers, `''` env defaults and no-op downgrades.
- `ma.ModelSchema` is deprecated, and remapped JSON keys (camelCase, `desc`) differ from model names.
