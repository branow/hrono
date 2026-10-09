<!-- level 1, node 505, children [55, 89, 120, 211, 280, 315, 334, 369, 405, 408, 425, 462, 463, 465, 466, 471, 474, 480, 481, 482] -->

**Overall:** This brief condenses summaries of the BC Registries (Province of British Columbia) codebase. It covers the legal-api/LEAR entity system, auth-api, pay-api, colin_api, entity-filer, a data_reset_tool, report-scheduler jobs and queue workers. The material falls into notebooks, migrations, test infrastructure, models and services, and tooling. It is mostly Flask, SQLAlchemy and PostgreSQL, plus NATS/STAN, GCP PubSub, Keycloak and papermill.

## 1. SQL/Jupyter reporting notebooks
These notebooks use `%load_ext sql` with `PG_*` env vars or `Config.SQLALCHEMY_DATABASE_URI`. They write CSV or text files under `data/`.
- **Entity/LEAR stats**
  - Cooperative and firm stats: Cooperatives Monthly Stats (SP/GP by city and postal code), Filings Monthly Stats (CP COMPLETED, `coop_filings_monthly_stats_for_{MONTH_YEAR}.csv`) and a 4-query cooperative notebook that writes `cooperative_monthly_stats_for_[MONTH_YEAR].csv`.
  - Daily incorporation stats cover incorporationApplication and BEN/BC alterations for the previous day (PST). Output is `incorporation_filings_daily_stats_{datestr}.csv`.
  - Gazette (CP/XCP): one notebook inserts into `sent_to_gazette` and writes 4 files (CHANGEOFNAME, DISSOLUTION, INCORPORATION, RESTORATION). Another runs the matching UPDATEs that set `sent_to_gazette_date = now()`.
  - BC firms extracts: `data/from_openshift.txt` and the fixed-width `BCFN_MR_YYYYMMDD_[rowcount].gz`.
  - Ops tracking: the CRA integration notebook lists unprocessed `request_tracker` rows. The Filing Issues notebook lists PAID filings that haven't completed and sends them to Google Sheets and Rocket Chat.
- **Auth:** Auth Weekly Stats on `orgs` and `users`, written to `auth_weekly_stats_till_YYYY-MM-DD.csv`.
- **Pay/reconciliation** (papermill `partner_code`: CSO, VS, RPT, ESRA)
  - Invoice Reconciliation Daily Stats writes `{partner_code}_daily_reconciliation_{date}.csv`.
  - Reconciliation Monthly Stats has a disbursement query for CSO and VS only, and a `revenue_letter` PDF through the report API.
  - Pay Weekly Stats writes `weekly_pay_stats_till_{yesterday}.csv`.
- **Notebook cautions**
  - Hardcoded dates in the CRA notebook.
  - Misspelled variables (`disslouted`, `inlude_last_number_of_days`).
  - Hardcoded credentials, service account path and Rocket Chat webhook in the Filing Issues notebook, which is a serious security risk.
  - The `from_openshift` extract fails with `%%sql not found`.
  - The BCFN_MR legal name is truncated at 454 characters.
  - Timezone handling is inconsistent: `AT TIME ZONE 'PST'` ignores DST, and conversion is applied in only some queries.
  - The firms monthly stats use a hardcoded -27 day offset.
  - The papermill `parameters` tag is required.
  - `data/` must exist.
  - Python 3.8 is end of life.

## 2. Report-scheduler jobs
These are Flask and papermill runners that execute notebooks and email results through SMTP.
- **Config:** `.env` feeds a `Config` class that builds `postgresql://` URIs. Recipient and schedule variables include `MONTH_REPORT_DATES`, `WEEKLY_REPORT_DATES`, `PARTNER_CODES` and `*_RECONCILIATION_RECIPIENTS`.
- **Runners:**
  - An error-alert runner for `generate_files.ipynb`, with an FTP/SFTP step. An extended variant adds `update_database.ipynb` and archiving.
  - Daily and monthly filings reports, which route recipients by notebook basename.
  - A weekly auth report, which handles `auth.ipynb`.
  - A partner reconciliation scheduler, which loops over partner codes.
- **Cautions**
  - Env vars default to `''`, so a missing config fails silently.
  - A routing mismatch silently skips the email.
  - `temp.ipynb` and `data/` are not always cleaned up.
  - Recipient parsing with `strip('][').split(', ')` is fragile.
  - On the 1st of the month, monthly and daily reports both run.
  - Plaintext DB password in the URI.

## 3. Alembic migrations
- **Scaffolding** (README stub, `alembic.ini` logging, `env.py`, `script.py.mako`)
  - `env.py` uses Flask `current_app`, escapes `%` as `%%` and skips empty autogenerate migrations.
  - Variants add `include_object` and `exclude_tables`, or `SKIPPED_MIGRATIONS`.
  - Variant `file_template` and the exclusion list covers `*_version`, `activity`, `transaction` and similar tables.
  - Migration `786dac4b44ef` creates `message_processing`, but its downgrade drops a nonexistent `ix_message_processing_source`.
- **Pay migrations** (2019 to late 2024)
  - Index-only migrations: invoice_references, ejv_invoice_links, invoices, routing_slips, payments.
  - Nullable column adds: overdue_date, sequence, disbursement_date, receipt_number, statements flags, invoice_references.is_consolidated, cfs_accounts.payment_method.
  - NSF table lineage: `b65365f7852b → fccdab259e05 → 0b1f9c35b1fb`.
  - EFT evolution, including the `eft_refund_email_list` create and drop cycle.
  - EJV link restructuring: `04b8a7bed74e` renames ejv_invoice_links to ejv_links.
  - Version-to-history rollout: `fb3ba97b603a` and `52ed2340a43c`.
  - Data fixes and view changes (`7fddd6ffe782`, `6468cb5380db`).
  - Practice: set `statement_timeout` for large tables (20000, up to 900000 ms).
  - Risks: destructive or empty downgrades, NOT NULL on live data, index naming mismatches, ~30-minute runtimes (`5cb9c5f5896c`) and short email columns.
- **Auth migrations** (~70)
  - Root is `414773385d34`.
  - Audit columns (`27718cfe1ef6`) and a 19-index migration (`2229cbcaaa93`).
  - Many add-column migrations that also touch `_version` tables.
  - Length, type and rename changes (`desc` to `description` across 11 tables).
  - Drops of `account_payment_settings` (irreversible) and of unused indexes.
  - Terms-of-use and document data migrations.
  - Status and data migrations: `PENDING_AFFIDAVIT_REVIEW` to `PENDING_STAFF_REVIEW`, and product subscriptions from BCOL profiles.
  - Merge stubs, such as `886fa2608e93`.
  - Risks: SQL injection through interpolated values, failing downgrades, a mismatched header in `09c44f82c03c` and truncated entries.

## 4. Test infrastructure
- **conftest and fixtures**
  - Services: colin_api, legal_api, auth-api, pay-api, entity-filer, digital_credentials, queue workers.
  - Shared pattern: session-scoped `app`, `db` (drop and `upgrade()`), `client`, `jwt`.
  - Function-scoped `session` with a SAVEPOINT restarted by `after_transaction_end`.
  - `stan` and `entity_stan` (NATS/STAN), `stan_server` (Docker) and `not_raises`.
  - `freeze_datetime_utcnow` with `FROZEN_DATETIME`.
  - `auto` (Docker mocks via `USE_DOCKER_MOCK`).
  - `initialize_pubsub` (emulator at localhost:8085).
  - Monkeypatch mocks for auth, notify, keycloak, minio and pub/sub.
- **Markers:** `skip_in_pod` (`POD_TESTING`), `colin_api_integration`, `integration_affiliation`, `integration_namex_api`, `oracle_integration`, `skip_coop_ia`.
- **Config:** local `.env` files (auth-api Postgres on 54330/54331, pay-api on 54332/54333) and `TestConfig` / `ProdConfig` with hardcoded test keys.
- **Integration tests:**
  - NATS/STAN `test_connect`, payment queue worker tests (`test_complete_worker`) and queue helpers.
  - DB and SFTP connection tests (`test_connection_failed`, `test_connection_succeed`, `test_sftp_connection_succeed`).
  - Notebook report tests (`processnotebooks` for daily, monthly, weekly).
- **EFT tests:** model persistence, `EftService` refund and reverse, `EFTTask` link scenarios, payment and partial-refund endpoints, and TDI17 file-format parser tests.
- **Cautions**
  - `POD_TESTING=False` is still truthy, so the tests are skipped.
  - Savepoint logic depends on `trans._parent.nested`.
  - Destructive `db` setup is for TEST mode only.
  - Session-scoped fixtures leak state, and the `FakeOidc` class state is never reset.
  - `premium_user_mock` has a `{{ }}` syntax error.
  - `@pytest.fixture('function')` is invalid.
  - `DATABASE_TEST_PORT="543313"` looks like a typo.
  - `ProdConfig` generates a random secret key at import.
  - The tests need real services and hardcode sleeps.

## 5. Models, schemas and services
- **Pay-api models:**
  - Every model uses `__mapper_args__['include_properties']` as a whitelist for rolling upgrades.
  - Base classes: `BaseModel`, `BaseSchema`, `Audit`, `CodeTable`, `CustomQuery`.
  - Main models: `FeeSchedule`, `AccountFee`, `DistributionCode`, `PaymentAccount`, `CfsAccount`, `Credit`, `CasSettlement`, `PaymentTransaction`, `RefundsPartial`, `Statement`, `StatementSettings`.
  - Status-code tables: `CfsAccountStatusCode`, `InvoiceStatusCode`, `PaymentStatusCode` and others. `StatementInvoices` is a relation table.
  - EFT models: `EFTCredit`, `EFTCreditInvoiceLink`, `EFTFile`, `EFTRefund`, `EFTTransaction`, `EjvLink`, `Refund`.
- **Auth-api models and schemas:**
  - `Org`, `User`, `Entity`, `Contact`, `ContactLink`, `Membership`, `Permissions`, `Affiliation`, `Invitation`, `InvitationMembership`, `ProductSubscription`, `AuthorizationView`, `Documents`, `OrgSettings` and several lookup models.
  - Marshmallow schemas for these models, with camelCase and field remaps.
  - Bases: `BaseCodeModel`, `VersionedModel`, deprecated `ma.ModelSchema`.
- **Auth-api services:**
  - `AffiliationService`, `AffiliationInvitation`, `Invitation`, `Org`, `Membership`, `Task`, `User`, `Product`, `Contact`.
  - The `@user_context` / `check_auth` decorator.
  - Org, entity and user Flask routes.
- **Legal-api models:** `Business`, `Filing`, `Address`, `Office`, `Party`, `PartyRole`, `Amalgamation`, `Batch`, `Furnishing`, `Review`, `RequestTracker`, `RegistrationBootstrap`, `DCConnection`, `DCDefinition` and other digital-credential models, `XmlPayload`, plus setup and DB-creation scripts.
- **NAICS:**
  - `NaicsStructure` and `NaicsElement` models, with search endpoints `GET /api/v2/naics` and `/<code_or_key>`.
  - A `NaicsService` client.
  - A separate Reviews API with one-way status transitions.
  - Tests with hardcoded counts.
- **Cautions**
  - Rolling-upgrade whitelists silently ignore new columns, and a missing comma in `EFTRefund.include_properties` is a bug.
  - Soft deletes: `Org`, `User` and `Comment`.
  - Lookups that assume a single default row.
  - Remapped field names silently drop data.
  - `ContactSchema` doesn't mask email.
  - Inconsistent return types: list vs single object.
  - A PATCH on a missing membership succeeds silently.
  - Typos (`originss`, `optjons`, `authorisations`).
  - Raw f-string SQL in `DCDefinition.deactivate` and the data migrations.
  - `Entity.reset()` references undefined columns.
  - Fragile internal SQLAlchemy usage in `clear_event_listeners`.

## 6. `data_reset_tool`
- **Purpose:** snapshots and restores business data as CSV, JSON or Excel for repeatable test scenarios.
- **Packaging:** version 2.17.0.
- **Routes:** export (`/api/fixture/export/...`), import (`/api/fixture/import/...`, `?rebuild=true`) and delete (`/api/fixture/delete/<id>`, 18 tables).
- **Config and app:** `create_app(run_mode)` with Dev, Test and Prod configs, and a `FIXTURE_BLUEPRINT`.
- **Cautions**
  - Only CP and XCP identifiers are accepted, not BC.
  - SQL is built by string interpolation.
  - `psycopg2.connect()` runs at import.
  - The default environment is production if `FLASK_ENV` is unset.
  - Two `__init__` modules are empty placeholders.

## 7. Unrelated material
The collection also holds a minified user-agent bundle, Chai docs, a Postman request for `POST /api/v1/users/contacts`, and DB upgrade and creation shell scripts with no error handling.
