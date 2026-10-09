<!-- level 3, node 517, children [515, 516] -->

**BC Registries ecosystem: parent brief**

This brief covers the bcgov BC Registries repos: lear, Legal API, sbc-auth, sbc-pay, colin_api, business-filings-ui, auth-web, business-pay, the COLIN→LEAR ETL, entity-filer, entity-bn and data_reset_tool. It also covers the specs, infra, docs, fixtures and bundled third-party artifacts around them. Code is mostly Apache 2.0, © Province of British Columbia. business-pay is BSD-3-Clause. Nearly all fragments are truncated, duplicated or templated, so check the source before relying on any contract. Treat placeholders (`no_one@never.get`, Tester Testing, `{{today}}`, `${…}`) as variables. Namespaces are `cc892f` (lear), `6e0e49` (auth) and `78c88a` (pay). The realm is `fcf0kpqr`. Hosts are `*.apps.silver.devops.gov.bc.ca`, plus legacy pathfinder hosts.

## Routing map

**1. Templates**
- PDF reports and certificates use Jinja2/HTML with `[[file.html]]` includes. They cover Amalgamation, Continuation, Dissolution, Good Standing, Incorporation, Name Change, Restoration and Status certificates, plus about 35 filing and summary documents.
- Emails cover filing confirmations, Name Request lifecycle, restoration (`base_template` → `RES-common` → `RES-PAID`/`RES-COMPLETED`), account and auth, and payment (PAD, EFT, refunds, statements).
- Integration code includes SBN hub XML (CPPR → BCSBNHUB), org/membership functions and the entity-emailer `dissolution_notification`.
- Scaffolding includes auth-web i18n catalogs, GitHub issue/PR templates and Excel `styles.xml`.

**2. Front end** (Vue 2→3, Vuex→Pinia, Vuetify; migration unfinished)
- **business-filings-ui (v7.3.24):**
  - Stores: `useBusinessStore`, `useRootStore`, `useFilingHistoryListStore`.
  - Mixins: `AllowableActionsMixin`, `FilingMixin`, `DateMixin` → `DateUtilities`.
  - About 25 persistent dialogs whose parents must wire every emitted event.
  - A 15-renderer filing-history picker.
  - Todo list: `loadFilingItem` has about 18 loaders, and `filingId='0'` means a new filing.
  - Digital Business Card credentials flow.
  - Entity enums, configs and `EnumUtilities`.
- **auth-web (v2.6.92):**
  - `useOrgStore` (about 80 exports), an 8-check router guard and 40+ routes.
  - Onboarding and invites, team and affiliations.
  - Staff tools: account and continuation review, GL codes.
  - Product fees, NSF suspension/unlock, EFT short-name mapping and refunds.
- **Tooling:** Vite, Vitest and ESLint. Bootstrap order is `ConfigHelper` → LaunchDarkly → Sentry → Hotjar → `syncSession` → `renderVue`.
- **Tests:** VTU with Jest, Vitest or sinon. Examples are COOP `CP0001191` and BCOMP `BC0007291`, plus many auth smoke tests.
- **Cautions:**
  - `v-html` XSS risk (`StaffFiling`, payment errors, `BaseVExpansionPanel`, `CautionBox`).
  - `eval()` in `compareYyyyMmDd`.
  - The `goToDashboard` dialog logic is inverted.
  - `getObligations` is undefined.
  - Silent `'[unknown]'` fallbacks.
  - `createLocalVue` and `setMethods` break on Vue 3.
  - Vue 2.6 and 2.7 are EOL.

**3. Backend services** (Flask/SQLAlchemy/PostgreSQL, NATS/STAN → GCP Pub/Sub migration in progress, Keycloak)
- **Legal API v1/v2 (LEAR):**
  - Models: Business, Filing, Party, Amalgamation, Batch, Furnishing, dc_*.
  - One validator per filing type, allowable-filing and fee-code rules, a blocker engine.
  - Services: reports (`ReportMeta`/`Report`), documents, involuntary dissolution, NAICS.
  - Document availability: PAPER_ONLY and PENDING give 404, PAID and COMPLETED give 200.
- **colin_api:** wraps legacy Oracle COLIN data and needs `COLIN_SVC_ROLE`. Models are Business (good standing), Party, Filing, Office and ShareObject.
- **sbc-pay:**
  - pay-api: 21 blueprints, `PaymentSystemFactory`, `include_properties` whitelists, routing slips, EFT and refunds.
  - pay-queue: reconciles CAS, CGI/EJV, EFT and TDI17 files.
  - Also ftp-poller, payment-jobs, pay-admin, bcol-api and report-api.
- **sbc-auth:** auth-api (24 blueprints), auth-queue, account-mailer, and Keycloak/ApiGateway.
- **Filing pipeline:**
  - entity-filer dispatches about 25 filing types. A BN retry count of 9 means 10 attempts.
  - Also entity-bn (CRA via BN Hub), entity-emailer, digital-credentials, the events listener, business-pay (sets PAID) and `entity_queue_common`.
- **Batch jobs and ETL:**
  - Jobs: email-reminder, involuntary-dissolutions (3 stages), furnishings (gazette XML and SFTP), future-effective-filings, update-colin-filings.
  - Prefect flows `corps-flow` and `sp-gp-flow`, the COLIN→PG runbook and the Oracle 12.2 Docker build.
- **Report-scheduler and notebooks:** Papermill and SMTP runners, plus SQL stats and ops notebooks.
- **data_reset_tool:** `/api/fixture/export|import|delete`, version 2.17.0. Only CP/XCP identifiers are accepted.
- **Service skeleton:** `create_app(run_mode)`, a config map, a JWT manager, `/ops` healthz/readyz, and Sentry/LaunchDarkly.

**4. Alembic migrations** (about 300 or more)
- **pay-api:** fee seeding, routing slips, EFT and refunds, EJV/CGI, NSF.
- **auth-api:** `authorizations_view` rebuilds, about 33 permission migrations, about 25 product-code migrations.
- **LEAR:** amalgamations, furnishings, reviews, dc_*, batches.
- **Scaffolding:** about 17 empty merge stubs, `786dac4b44ef`, and `dede70a6df1e`.

**5. Postman, k6 and test code**
- **Postman and k6:** colin_api and Auth API collections with hardcoded fixtures (CP0002098, CP0001965, CP0001164, BC0702216 and others), OAuth2 token scripts, and a k6 legal-api setup.
- **conftest patterns:** session-scoped app and db, SAVEPOINT sessions, STAN and Pub/Sub emulators. Markers are `skip_in_pod` and `oracle_integration`.
- **Suites:** legal-api (permission matrices, validators), entity-filer, auth_api, pay_api and colin_api. Boilerplate meta, ops, config and CORS tests are repeated across services.
- **Feature-flag fixtures:** `disable-nr-check` bypasses name-request validation.

**6. Fixtures and data**
- Officer and director records (CP0002098, CP0001965, CP0001164) share a shape: `appointmentDate`, `cessationDate` (null = active), `startEventId`, `officer`, addresses.
- Filing payloads include BEN incorporation, correction, dissolution and amalgamation, with the 1218890 B.C. LTD. (BC1218890) sample.
- Other items: CSV/ZIP dumps, a Jan 2023 BN Hub failure set, the CP0000840 ledger and PayBC invoice and receipt fixtures.
- Subscriber and Director Search legal agreements are included.
- Unrelated street-name lists (Czech, Slovak, German, Georgian, Polish) are included.

**7. API specs** (OpenAPI, JSON Schema draft-07)
- Covered: CAS/CFS/PayBC (test host `heineken.cas.gov.bc.ca`), BCOL, Pay API v1.0.7, routing slips (FAS), Auth/Accounts v1.0.1, Notify v1.0.0, Report v1.0, Business Registry, and the Legal API v2 spec (about 24 filing types).
- Problems: heavy truncation, validation-free patterns (`^(.*)$`), wrong `$id` values, typos (`adress.json`, `indentifier`), numbers typed as strings, wildcard CORS, and external `bcrs.gov.bc.ca` refs that must resolve.

**8. Keycloak/SSO**
- **Pieces:** Postman collections, a `demo` realm export, `KeycloakService`, `remove_users.py`, Flask-Admin views, and Docker Compose (Keycloak 12/15/16, nginx, Prism, NATS, MinIO).
- **Cautions:**
  - Placeholder or plaintext secrets (`admin/admin`).
  - The hardcoded realm `fcf0kpqr`.
  - Mapper claims override real user data.
  - `web-origins` defaults to `*`.
  - Token scripts never check expiry.
  - `service-account-sbc-auth-admin` is broadly privileged.
  - `OVERWRITE_EXISTING` wipes state.

**9. Infra, CI/CD and docs**
- **CI/CD:** Makefiles (about 17, on a `TAG_NAME` flow), GitHub Actions CI and CD (OpenShift, GCP Cloud Deploy), the OpenShift 4 migration, Firebase PR previews, vault-to-app mappings, the BCROS Jenkins repo, Prefect and devcontainer notes, and Codecov and SonarQube.
- **OpenShift manifests:** the 3-replica `nats-streaming-6`, Postgres templates, bcol-api, coops-ui (Caddy), entity-filer, BuildConfigs and CronJobs, HPA, DeploymentConfig with probes on port 7070, and jobs with `activeDeadlineSeconds: 1600`.
- **Logging and shell:** INI logging configs with `setup_logging(conf)`, and an `.env` loader snippet that breaks on quotes.
- **Feature flags:** the LaunchDarkly wrapper silently skips init when `LD_SDK_KEY` is missing in production.

**10. SchemaSpy 6.0.0 docs and DB schemas** (AdminLTE 2, Bootstrap 3.3.5)
- Generated HTML for the payments DB (`fee_schedule`, `invoice`, `payment`, `receipt`, with money as float8) and the auth/org DB (`user`, `org`, `membership`, `affiliation`, `entity`, `contact`).
- Page JS has hardcoded column indexes, `eval()` and `user-scalable=no`.
- Row counts are unreliable, and DOT edges read child → parent.

**11. Browserified third-party bundles** (Postman/k6)
- Contents: Node polyfills, crypto (`bn.js`, `elliptic`, `aws4`, CryptoJS), parsers (Cheerio, `xml2js`, `sax`), Ajv, Chai 4.3.3 with the Postman `pm` shim, Lodash 4.17.21, Faker, and Papa Parse.
- Do not hand-edit these. Module IDs are unstable.
- Gotchas: OAEP is hardcoded to SHA-1, PBKDF2 defaults to 1 iteration, RC4 is broken, `coerceTypes` mutates caller data, and the xml2js `defaults` attribute and character keys are swapped.

## Business rules worth knowing
- Good standing is 1 year + 2 months + 1 day, with a 2004-03-29 cutoff.
- NR renewal adds 56 days from the original expiry.
- The PAD NSF fee is $30.
- CP requests its own BN. Other types are auto-assigned.
- XPRO is cancelled, and domestic types are dissolved.
- EFT reversal requires payment within 60 days. Refunds are editable only while PENDING_APPROVAL.
- Statements-due must run at 08:00 UTC or later.

## Cross-cutting cautions
- **Security:**
  - Hardcoded credentials appear in compose files, notebooks (a Rocket Chat webhook), test RSA keys and `SECRET_KEY='a secret'`.
  - f-string SQL appears in the Legal API `/internal/filings/colin_id`, data_reset_tool, colin_api `ProgramAccount`, the ETL and the BCOL sync.
  - Other risks: `verify_signature=False` in `send_credential`, CORS `*`, `forwarded_allow_ips='*'`, disabled SFTP host verification, plaintext `Entity.passCode`, MD5, and `|safe` or `autoescape false` in templates.
  - Also watch for `curl | bash` installs, an empty `securityContext`, and a permissive CSP.
- **Silent failures:**
  - Broad excepts swallow errors. pay-queue and account-mailer return 200 and drop messages.
  - Missing env vars default to `''`.
  - Missing template context renders blank.
  - Feature-flag helpers deny silently.
  - A short payment still marks an invoice PAID.
  - Existence-only test assertions pass on wrong data.
- **Migration hazards:**
  - Broken, lossy or destructive downgrades, including `TRUNCATE CASCADE`.
  - Docstring `down_revision` can differ from the code, so trust the code.
  - `max(id)+1` races, and `_version` drift.
  - Merge stubs hide the real work in their parents.
- **Known bugs and typos** (some are live names, so renaming needs a coordinated change):
  - Bugs:
    - `update_filing_court_order` tests `if not Filing:`.
    - `ShareObject` stores `has_max_share` inverted.
    - Pay `Receipt.find_by_invoice_id_and_receipt_number` drops its filter.
    - `StatementRecipients` email getter returns `_lastname`.
    - `RefundService` getters recurse infinitely.
    - The EJV `batch_type` filter looks inverted.
    - `Reset` assigns `start_date = end_date`.
    - JSON diff `oldValue`/`newValue` are reversed.
    - `deletion_locked` returns 401.
  - Typos: `'paymanet_pending'`, `memeberAccessToken`, `documnent_key`, `learEffectiveDate`, `inovice_id`, `new_otions`.
- **Time and data:**
  - `AT TIME ZONE 'PST'` ignores DST.
  - `createUtcDate` months are 0-indexed.
  - Empty string vs null.
  - IDs are reused across records (`startEventId`, `addressId`, filingId 112751).
  - Enums must be passed as `.value` strings.
  - Decode dumps as UTF-8.
  - Redact the Jane/John Doe custodian data.
- **Test fragility:**
  - Tests depend on live Oracle, Postgres or Docker, hardcoded fixture IDs and shared state.
  - Many suites are skipped, empty or smoke-only. Some tests never run (`tpost_valid_ar`) or have duplicate IDs.
  - Deep-copy shared fixtures.
- **Staleness:**
  - EOL pins: Flask 1.1, Werkzeug <2, SQLAlchemy <1.4, Python 3.8, `flask_script`, PG 9.6/10, nodejs:8, the `ubuntu-20.04` runner, `batch/v1beta1`.
  - Workflows pinned to `@main`/`@master`, and branch- or fork-pinned git dependencies.
  - Hardcoded fees, contact numbers and dates.
- **Ops traps:**
  - `FLASK_ENV` defaults to production.
  - `POD_TESTING=False` is still truthy.
  - Oracle `rownum=1` with `ORDER BY`.
  - The Oracle→PG transfer needs triggers disabled, and the `'BC'` prefix covers only 3 of the 11 corp types.
  - Dev keys are blank, so features are disabled.
  - Hardcoded `TAG_NAME="dev"`.
  - Cron times are in UTC.
  - OpenShift templates mix `${VAR}` and `${{VAR}}`, so check which engine applies.
- **Generated artifacts:** regenerate SchemaSpy HTML, bundles and exports from their sources. Do not hand-edit them.
