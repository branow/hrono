<!-- level 2, node 515, children [490, 491, 493, 494, 495, 500, 504, 505, 507, 511, 513, 514] -->

# BC Registries / LEAR ecosystem: top-level brief

This is the combined routing brief for the bcgov Business Registry stack. It covers LEAR (legal-api, colin-api, queue workers), sbc-auth (auth-api and auth-web), sbc-pay (pay-api and its workers), business-filings-ui, bcol-api, plus their fixtures, migrations, templates and tooling. Nearly everything is truncated, fixture or test data, or boilerplate. Treat no fragment as complete or validated.

## Routing guide

**1. Templates and documents (Jinja2 with the custom `[[file.html]]` include)**
- Covers certificates, office and party tables, filing report sections (WeasyPrint PDF), letters and furnishing XML.
- Also: print CSS, email templates (filing confirmations, restoration, Name Request, auth/account, PAD), SBN hub XML (sender CPPR, receiver BCSBNHUB), auth-web i18n catalogs, GitHub issue and PR templates, and the entity-emailer pytest suites.
- Risks: a missing include or variable renders blank with no error. `|safe` and `autoescape false` allow XSS. `header.name` vs `header.reportType` mismatches, 30-character SBN truncation, and hardcoded contact numbers (1-877-526-1526, 250-387-7848).
- Copy these typos verbatim: `pendingAffidvitReviewMessage`, `govmAAccountCreationSuccessSubtext`.

**2. Postman, k6 and fixture API (colin_api, auth-api, legal-api, `/api/fixture/*`)**
- Assertions are hardcoded to fixtures: CP0002098 (LAKES ARTISAN COOPERATIVE), CP0001965, CP0001164, and `{{newCorpNum}}` variables.
- Tests depend on saved env vars (`arEventId`, `codExtraEventId`, tokens, `today`) and on run order.
- Known oddities: `documnent_key` and `memeberAccessToken` typos, wrong Content-Type expectations, and a "GET New Corp Number" that is really a POST.
- k6 shim: delete `options.headers`. URI.js `absoluteTo` bug: `substring(-2)` should be `slice()`.

**3. Front ends (Vue 2→3, Vuetify, Pinia migration)**
- **business-filings-ui (v7.3.24):** dashboard, todo list (`loadFilingItem` dispatch, polling), filing history (`is(filing)`), filing forms, dialogs.
- **auth-web (v2.6.92):** accounts, onboarding, teams, products, payments (PAD, EFT, NSF), staff back office, short names, affiliations.
- **Staff review app:** continuation-in review and account approval.
- **Shared:** `useRootStore` (id `'root'`), `useBusinessStore`, `ConfigHelper`, SCSS tokens (BCgovBlue `#003366`, gold `#fcba19`), `v-can` directives, `EnumUtilities`.
- **Pay infra:** Cloud Build and Cloud Deploy pipelines, `op://` env templates.
- Likely bugs:
  - Missing `this.` in root-store getters.
  - `splice(index)` without a count.
  - Inverted `customSort` and descending flags, and an inverted TOS version comparison.
  - Inverted polling watches.
  - `syncSuspendedStaffOrgs` assigning to the wrong state.
  - The task store's `!pendingTasksCount` cache.
- Typos that exist in the code (keep them): `resetoCurrentSelectedProducts`, `FolioNumberload`, `apliKeyList`, `foreignJusrisdictionCountry`, `paymanet_pending`.
- Security: `v-html` on API or user content (StaffFiling, PaymentErrorDialog, CautionBox), and temporary passwords shown in the UI.
- Test suites:
  - Vitest with sinon and axios stubs.
  - Many are smoke tests, `.skip`ped or commented out.
  - `Vue.config.silent` hides warnings.
  - Handlers are called directly.
  - Deprecated `wrapper.destroy`, `setMethods` and `createLocalVue` block a Vue 3 move.
  - 2022–2023 dates are stale as of 2026-10-09.

**4. Fixtures and API types**
- **Officers and directors:** CP0002098, CP0001965, CP0001164, CP0002108 and CP0001248. They share one officer, address and party schema.
- **Filing payloads:**
  - Co-op AR, COA and COD.
  - BC/BEN incorporation, alteration, correction, transition and amalgamation.
  - Dissolution BC0702216, incorporation BC1218890.
  - CP0000840 ledger. Filing ID 112751 is reused.
  - BN hub and CRA failure records.
- **Database exports:** byte-encoded ZIP/CSV. Decode bytes, never edit them as text.
- **Specs and types:** OpenAPI business filings v2.0 and TypeScript filing interfaces.
- **Unrelated place-name lists.**
- Data traps:
  - `""` vs `null`, shared addressIds and startEventIds, and unrendered `{{placeholders}}`.
  - Montréal addresses with region BC.
  - `arMinDate` later than `arMaxDate`.
  - Mixed date formats.
  - Fixtures contain PII-looking data to scrub.

**5. Database migrations (Alembic) and reconciliation**
- Separate histories, so route by revision ID:
  - **auth:** `authorizations_view`, permissions, products, invitations, suspension, tasks, TOS.
  - **pay-api:** fees, corp types, invoices, routing slips, eJV, EFT, refunds.
  - **LEAR:** businesses, filings, amalgamation, batch processing, furnishings.
- Also: JV/EJV/CFS feedback-file reconciliation, and the COLIN→PostgreSQL DbShell runbook.
- Also: Oracle 12.2 Docker build, and the `786dac4b44ef` `message_processing` migration (its downgrade drops a nonexistent index).
- Rules and risks:
  - Trust the code's `down_revision`, not the docstring.
  - Many downgrades are weak: no-ops, wrong names, or broad deletes.
  - Fee seeds use `datetime.now()`, so replays duplicate rows.
  - F-string SQL appears in many migrations.
  - Empty merge migrations change no schema.
  - Typos preserved in the schema: `inovice_id`, `new_otions`.

**6. Backend services (Python/Flask)**
- **Pay API:** payment-system factory (BCOL, PAD, PayBC, online banking, internal, EJV, direct pay), EFT module, models with `include_properties` whitelists, Fee Admin UI.
- **Auth API:** orgs, affiliations, invitations, products, tasks, activity log, API-gateway keys.
- **Legal API:** Business, Filing, Party, furnishings, digital credentials, NAICS, reporting (Report V1, V2/Gotenberg), NameX/MRAS/COLIN wrappers, `VersionedBusinessDetailsService`.
- **COLIN API:** Oracle-backed, `COLIN_SVC_ROLE`.
- **BCOL API:** zeep SOAP client.
- **Queue and job workers:**
  - Entity filer (about 25 processors), emailer, BN and digital-credentials (NATS/STAN).
  - Pay queue, account-mailer and auth-queue (Pub/Sub).
  - FTP poller (CAS, CGI, EFT), business-pay.
  - Furnishings and involuntary dissolution jobs.
  - Prefect COLIN→LEAR ETL, whose transforms contain "PREFECT ETL FLOW TEST" markers.
- **Reporting:**
  - Papermill notebooks and schedulers for stats and reconciliation.
  - A Flask data-reset tool (v2.17.0).
  - Jupyter test and ops notebooks.
- Risks:
  - SQL injection via f-strings (COLIN, data reset, migrations).
  - Secrets: `'a secret'`, a random `ProdConfig` key, and `cross_origin('*')`.
  - Swallowed exceptions and workers that return 200, so there are no retries.
  - Known bugs:
    - `StatementRecipients.email` returns `_lastname`.
    - `Receipt.find_by_invoice_id_and_receipt_number` drops its filter.
    - The `ShareObject` max-share flag is inverted.
    - `good_standing` inverted for non-ACTIVE state.
    - `Error` is not an Exception.
    - The XPRO letter step updates `_bc_mail_furnishings`.

**7. Repo, CI and packaging**
- SonarQube and Codecov configs, flake8/pylint/isort/pytest/coverage templates (the `[report:run]` section is non-standard), and dev requirements.
- **Stacks:** the modern one is Python 3.12 / Flask 3 / SQLAlchemy 2 / Poetry (pay services). The legacy one is Flask 1.1.2 / Werkzeug <2 / SQLAlchemy <1.4 / protobuf ≤3.19 (auth-api, lear).
- Git dependencies are unpinned or on personal forks and branches, so builds are not reproducible.
- Also: Gunicorn config (use the `wsgi:application` name; typo `GUNICORN_WORKER_CONNECIONS`), SFTP and Minio wrappers, Dockerfiles, devcontainers and READMEs.
- Terms and legal text: subscriber agreements and Director Search Tool terms.
- Front-end entity configs and the 18 LaunchDarkly defaults.
- Filing-type fee-code maps and the authorization engine (`is_allowed`, `get_allowable_actions`).

## Cross-cutting cautions
- **Truncation:** nearly all sources are cut off, so counts, schemas and full logic are unreliable. Verify against the source.
- **Silent failure:** missing includes, variables, flags, env vars (`''` defaults) and roles quietly produce empty, denied or default output. Broad `except` and `suppress` hide errors, and queue handlers swallow exceptions.
- **Security:** f-string SQL, `v-html`, `|safe`, wildcard CORS, `verify_signature=False`, MD5 API keys, disabled SFTP host verification, and hardcoded or committed credentials.
- **Hardcoded fixtures and business rules:** IDs, dates (AR window 1 year + 2 months + 1 day, 2019-03-08 cutoff), phone numbers and fee amounts. Tests are order-dependent.
- **Migration debt:** Vue 2→3, Vuex→Pinia, Flask 1→3, and EOL pins.
- **Test data vs. real data:** placeholder emails (`no_one@never.get`, `tester@testing.com`) are fixtures, and any real-looking PII should be scrubbed.
- **Naming traps:** `header.name` vs `reportType`, `effective_date` vs `effective_date_time`, `CONDITIONAL` vs `CONDITION`, `legalType` BC (a jurisdiction code, not a legal type), and enum values that must be read with `.value`.
