<!-- level 2, node 515, children [490, 491, 493, 495, 500, 504, 505, 507, 511, 513, 514] -->

# BC Registries Ecosystem: Consolidated Brief

This brief covers the bcgov BC Registries codebase and its test and fixture material. The repos are lear, the Legal API, sbc-auth, sbc-pay, colin_api, business-filings-ui, business-pay, the COLIN→LEAR ETL, entity-filer, entity-bn and the data_reset_tool. Most code is Apache 2.0, © Province of British Columbia. business-pay is BSD-3-Clause. Nearly all fragments are truncated, and much of the material is test data, fixtures or archival, not production. Treat placeholders (`no_one@never.get`, Tester Testing, TEST CITY, `{{today}}`, `{{newCorpNum}}`) as variables, not real values.

## Routing map

**1. Templates (PDF, email, integration, front-end text)**
- **PDF reports and certificates**
  - Letter-size Jinja2/HTML with the custom `[[file.html]]` include syntax.
  - Certificates: Amalgamation, Continuation, Dissolution, Good Standing, Incorporation, Name Change, Restoration and Status.
  - About 35 filing and summary documents (CP reports, BCA applications, Notice of Articles, Business Summary, registrar letters).
  - Shared building blocks: `.chip` label macros, party and address tables, legal-type disclaimers.
- **Emails**
  - Filing confirmations; Name Request lifecycle; restoration inheritance chain `base_template` → `RES-common` → `RES-PAID`/`RES-COMPLETED`.
  - Account and auth emails; payment emails (PAD, EFT, refunds, statements).
  - Shared footers and the contact block.
- **Integration code**
  - SBN hub XML requests (CPPR → BCSBNHUB).
  - Org/membership service functions.
  - The entity-emailer `dissolution_notification` processor.
- **Scaffolding:** auth-web i18n catalogs, GitHub issue/PR templates, Excel `styles.xml` fragments.

**2. Front end (Vue 2→3, Pinia, Vuetify)**
- **business-filings-ui (entity dashboard):**
  - Stores `useBusinessStore` and `useRootStore`.
  - Filing pages, directors, address editing and the Digital Business Card credentials flow.
  - Mixins (`AllowableActionsMixin`, `FilingMixin`, `DateMixin` → `DateUtilities`).
  - Entity enums, entity configs and `EnumUtilities`.
- **auth-web:**
  - Shell, stores (org store has about 80 exports), the 8-check router guard and 40+ routes.
  - Onboarding and invite flows, account management, team and affiliations.
  - Staff tools (account review, continuation review, GL codes).
  - Product fees.
  - Payments and NSF suspension/unlock.
  - EFT short-name mapping, linking, refunds and payment reversal.
- **Test suites (Vue Test Utils, Vitest/Jest, sinon):**
  - Filing-page tests for COOP `CP0001191` and BCOMP `BC0007291`.
  - Dozens of auth smoke tests.
  - Service and util tests, plus fixtures and factories.

**3. Backend services (Flask/SQLAlchemy/PostgreSQL, NATS/STAN → GCP Pub/Sub, Keycloak)**
- **Service skeleton:** `create_app(run_mode)`, a config map, a JWT manager, `/ops` healthz/readyz, and Sentry/LaunchDarkly.
- **Legal API v1/v2 (LEAR):**
  - Models: Business, Filing, Party, Amalgamation, Batch, Furnishing, digital credentials.
  - Validators, one per filing type.
  - Allowable-filing and fee-code rules, and the blocker engine.
  - Services: reports (`ReportMeta`, `Report`), documents, involuntary dissolution, NAICS.
- **colin_api:**
  - Wraps legacy Oracle COLIN data and requires `COLIN_SVC_ROLE`.
  - Models: Business (good standing), Party, Filing, Office, ShareObject.
  - Reset (COOPER), `OracleDB`.
- **Pay (sbc-pay):**
  - pay-api, with 21 blueprints, `PaymentSystemFactory`, models with `include_properties` whitelists, routing slips, and EFT and refunds.
  - pay-queue, which reconciles CAS, CGI/EJV and EFT.
  - ftp-poller, payment-jobs, pay-admin, bcol-api and report-api.
- **Auth (sbc-auth):**
  - auth-api (24 blueprints), auth-queue, account-mailer, and the Keycloak/ApiGateway pieces.
- **Filing pipeline:**
  - entity-filer, which dispatches about 25 filing types.
  - entity-bn (CRA via BN Hub), entity-emailer, digital-credentials, the events listener, and business-pay (sets PAID).
  - Shared `entity_queue_common`.
- **Batch jobs and ETL:**
  - email-reminder, involuntary-dissolutions (3 stages), furnishings (gazette XML and SFTP), future-effective-filings, update-colin-filings.
  - Prefect ETL flows (`corps-flow`, `sp-gp-flow`), COLIN→PostgreSQL runbook, and the Oracle 12.2 Docker build.
- **Report-scheduler and notebooks:**
  - Papermill and SMTP runners.
  - SQL notebooks for entity, auth and pay stats, gazette, BC firms extract and reconciliation.
  - LEAR ops notebooks for NR creation, incorporation flows, correction and alteration.
- **data_reset_tool:** export, import and delete of fixture data (`/api/fixture/...`, version 2.17.0). Only CP/XCP identifiers are accepted.

**4. Database migrations (Alembic), about 300 or more**
- **pay-api:** schema and seeds; fee and corp-type seeding; routing slips; error codes; EFT and refunds; EJV/CGI; NSF; index-only migrations.
- **auth-api:**
  - `authorizations_view` rebuilds.
  - About 33 permission migrations.
  - About 25 product-code migrations.
  - Suspension reasons, tasks table, terms of use, `desc`→`description`.
- **LEAR:** amalgamations, furnishings, reviews, dc_* tables, batches, indexes.
- **Scaffolding and merges:** `env.py` variants, about 17 empty merge stubs, `786dac4b44ef` (`message_processing`).

**5. Postman collections and test code**
- **colin_api and Auth API collections:**
  - Hardcoded fixtures: CP0002098 Lakes Artisan, CP0001965 Central Interior, CP0001164, CP0001248, CP0002108, BC0702216, BC0664974.
  - Fixture endpoints `/api/fixture/export|delete|import`.
  - OAuth2 pre-request token scripts.
  - A CAS/ORDS HATEOAS link set.
- **k6 performance setup** for legal-api.
- **Test infrastructure:**
  - conftest patterns: session-scoped app/db, SAVEPOINT sessions, STAN/Pub/Sub emulators.
  - Markers: `skip_in_pod`, `oracle_integration`.
  - Auth, pay and legal tests.

**6. Fixtures and data**
- **Officer/director records:**
  - Lakes Artisan (CP0002098), Central Interior (CP0001965), Vancouver Thurlow St (CP0001164) and 2024 API-spec samples.
  - Shared shape: `appointmentDate`, `cessationDate` (null = active), `startEventId`, `officer`, addresses.
- **Other fixtures:**
  - Filing payloads: BEN incorporation, correction, dissolution, amalgamation, with the 1218890 B.C. LTD. (BC1218890) byte-array sample.
  - CSV/ZIP export dumps.
  - A BN Hub failure set from Jan 2023.
  - The CP0000840 ledger.
  - PayBC invoice and receipt fixtures.
  - A share-structure incorporation fixture.
- **Specs and text:**
  - OpenAPI v2.0 spec fragments (about 24 filing types).
  - Subscriber/Director Search legal agreements ($30 late fee, 90-day dispute, 60-day termination).
  - Unrelated street-name lists in Czech, Slovak, German, Georgian and Polish.

**7. Repo config and tooling**
- Codecov and SonarQube configs.
- Packaging (setup.py, Poetry), lint settings (line length 120).
- Dockerfiles (Python 3.8 EOL), about 17 Makefiles on a `TAG_NAME` flow, and compose stacks.
- Vault-to-app mappings, Firebase PR previews, Cloud Deploy pipelines for pay, and DB masking.
- 1Password-templated env.

## Cross-cutting cautions

- **Truncation:** nearly every fragment is cut off mid-record. Counts, schemas and logic can't be confirmed from the notes, so check the source.
- **Security**
  - Hardcoded credentials and secrets: compose files, notebooks (including the Rocket Chat webhook and service account), test RSA keys, `SECRET_KEY='a secret'`, a JWT in a fixture, and the 1Password master password passed as an argument.
  - SQL built with f-strings or string formatting appears in many places: the Legal API `/internal/filings/colin_id`, the data_reset_tool, colin_api `ProgramAccount`, ETL queue queries and several migrations.
  - Other risks:
    - `eval()` in `compareYyyyMmDd`, `v-html` in `CautionBox`, and `|safe` or `autoescape false` in templates.
    - `verify_signature=False` in `send_credential`.
    - CORS `*`.
    - `forwarded_allow_ips='*'` and disabled SFTP host verification.
    - `Entity.passCode` stored in plaintext, and MD5 hashing.
- **Silent failures:**
  - Broad excepts that log and swallow.
  - pay-queue and account-mailer return 200 and drop messages.
  - Missing env vars default to `''`.
  - Conditionals without an else branch.
  - Missing template context renders blank.
  - `GetFeatureFlag()` returns undefined and `Flags` returns False, which denies silently.
  - Existence-only test assertions pass on wrong data.
- **Migration hazards:**
  - Many downgrades are broken, lossy or destructive: wrong names, syntax errors, `TRUNCATE CASCADE`, unconditional deletes.
  - Docstring `down_revision` can differ from the code, so trust the code.
  - `max(id)+1` races, `datetime.now()` seeds, and `_version` table drift.
  - Merge stubs hide the real work in their parents.
- **Business rules and hardcoding**
  - Rules:
    - Good standing is 1 year + 2 months + 1 day, with a 2004-03-29 cutoff.
    - NR renewal adds 56 days from the original expiry.
    - The PAD NSF fee is $30.
    - CP requests its own BN; other types are auto-assigned.
    - XPRO is cancelled, domestic types are dissolved.
  - Hardcoded values that may go stale: contact numbers, fee amounts, time limits, 2018–2023 dates and fixture IDs.
  - Timezones: `AT TIME ZONE 'PST'` ignores DST, `+00:00` shows a day early in Pacific time, and `createUtcDate` months are 0-indexed.
- **Known bugs and typos (several are live names; renaming needs a coordinated change):**
  - Bugs:
    - `update_filing_court_order` tests `if not Filing:`.
    - `ShareObject` stores `has_max_share` inverted.
    - Pay `Receipt.find_by_invoice_id_and_receipt_number` drops its filter.
    - `StatementRecipients` email getter returns `_lastname`.
    - Inverted logic in several sorts and getters.
    - `Reset` assigns `start_date = end_date`.
  - Typos:
    - `'paymanet_pending'`, `memeberAccessToken`, `documnent_key`, `learEffectiveDate`.
    - `"VACOUVER"`, `"Pickerirng"`.
    - `inovice_id`, `new_otions`.
- **Test fragility:**
  - Tests depend on live Oracle/Postgres or Docker, hardcoded fixture IDs, and prior runs.
  - Shared state leaks (sessionStorage, Pinia, session-scoped fixtures).
  - Mocks hide authorization and i18n regressions.
  - Vue 2 APIs (`createLocalVue`, `setMethods`) break on Vue 3.
  - Many suites are skipped, empty or smoke-only.
  - Vitest, sinon and Jest are mixed.
- **Data pitfalls:**
  - Empty string vs null.
  - IDs reused across records (`startEventId`, `addressId`, `filingId` 112751), so check uniqueness before joining.
  - Paired fields must stay consistent.
  - Enum values must be passed as strings (`.value`).
  - Decode byte-array and CSV/ZIP dumps as UTF-8 (É/é).
  - Summaries conflict on officer names, dates and IDs, so check the source JSON.
  - The Jane/John Doe custodian data should be redacted.
- **Dependencies and runtime:**
  - Old and EOL pins: Flask 1.1, Werkzeug <2, SQLAlchemy <1.4, Python 3.8, `flask_script`.
  - Branch- or fork-pinned git dependencies.
  - The Vue 2→3 and Vuex→Pinia migration is unfinished, with import cycles between stores.
  - The NATS/STAN → Pub/Sub migration is in progress.
- **Ops traps:**
  - `FLASK_ENV` defaults to production.
  - `POD_TESTING=False` is still truthy.
  - Oracle `rownum=1` with `ORDER BY`.
  - The Oracle→PG transfer needs triggers disabled and commented filters removed, and the `'BC'` prefix covers only 3 of the 11 corp types.
  - Dev keys are blank, so features are disabled.
  - Pay pipelines have stub manifests and `verify: false`.
