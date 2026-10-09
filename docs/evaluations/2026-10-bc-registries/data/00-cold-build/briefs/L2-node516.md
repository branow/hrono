<!-- level 2, node 516, children [492, 494, 496, 497, 498, 499, 501, 502, 503, 506, 508, 509, 510, 512] -->

# Parent brief: BC Registries ecosystem plus vendored front-end and tooling assets

This group condenses a large set of near-duplicate, often truncated fragments. They come from BC Government (BC Registries, Legal Entities, Pay, Auth) repositories and from the third-party front-end stacks those repositories bundle. Treat every fragment as partial. Module IDs, generated code and example data are unstable placeholders.

## 1. Bundled third-party JavaScript (browserified or webpack payload)
- **Node core polyfills:**
  - `readable-stream` (Readable, Writable, Duplex, Transform), `events`, the process shim, the Feross `buffer` polyfill, `string_decoder`, `punycode`, `url` and `querystring`.
  - Gotchas: a Transform hangs if `cb()` is never called. The `events` `objectKeysPolyfill` returns `k` instead of `keys`.
- **Crypto:**
  - CryptoJS (AES, DES, RC4, SHA, MD5, PBKDF2), `bn.js`, `elliptic`, `asn1.js`, RSA and DH.
  - `aws4` (SigV4) is present.
  - Gotchas: AES `scrubVec` increments `v` instead of `i`. OAEP hard-codes SHA-1. PBKDF2 defaults to 1 iteration.
- **Parsing:**
  - cheerio 1.0.0-rc.6 with parse5, htmlparser2 and css-select.
  - `sax`, `xml2js` and `xmlbuilder`.
- **Validation and test:**
  - Ajv draft-07 (generated code, don't hand-edit).
  - Chai 4.3.3.
  - A Postman `pm` shim (`jsonPath` uses `eval`; `require` is limited to lodash, cheerio and crypto-js).
  - Faker.js (148 locales).
- **General libraries:** lodash 4.17.21, jQuery 3.x, an OAuth 1.0a client, Papa Parse 5.3.2.
- **CodeMirror 5.27.4** with the SQL mode.
- **Tiny unrelated fragments:**
  - `options.raw.language` JSON.
  - An HTML footer with a truncated `<script>`.
  - Spacer `<p>` tags.
  - A `postman-to-k6` manifest.
  - An Alembic migration, `dede70a6df1e`.

## 2. Vue front ends (business-filings-ui v7.3.24, auth-web v2.6.92)
- **Stack:** Vue 2.7 and TypeScript with Vuetify, mid-migration to Vue 3 and Pinia. Class components sit beside `defineComponent`, and Vuex beside Pinia.
- **Stores:** `useBusinessStore`, `useRootStore`, `useFilingHistoryListStore`, `useUserStore`, `useOrgStore`.
- **Areas:**
  - SCSS theme tokens: `$BCgovBlue5` #003366, `$BCgovGold5` #fcba19.
  - About 25 persistent dialogs and their Jest/VTU tests.
  - Filing history (`FilingHistoryList.is()` picks among 15 renderers).
  - Dashboard and todo list (`loadFilingItem` dispatches to about 18 loaders).
  - Filing forms and the shared save workflow.
  - Generic UI components (steppers, tooltips).
  - Auth-web views and flows.
  - Tooling and config: Vite, Vitest, ESLint, Nightwatch, and the bootstrap order (`ConfigHelper` → LaunchDarkly → Sentry → Hotjar).
- **Cautions:**
  - `v-html` XSS risks in `StaffFiling`, `PaymentErrorDialog` and `BaseVExpansionPanel`.
  - Silent `'[unknown]'` fallbacks.
  - `filingId='0'` means a new filing.
  - The `goToDashboard` dialog logic is inverted.
  - Many specs are skipped.

## 3. AdminLTE 2.3.x dashboard stack
- **AdminLTE CSS and JS (v2.3.5–2.3.8):**
  - Layout, 12 `.skin-*` skins and the `$.AdminLTE.options` config.
  - The option is misspelled `enableBSToppltip`.
  - Demo-only skin switcher.
- **Vendored libraries:**
  - Bootstrap 3.3.5/3.3.7 JS and CSS.
  - jQuery 2.2.3/3.2.1 with Sizzle.
  - jQuery UI 1.11.4, FastClick, slimScroll 1.3.8.
  - Chart.js demo dashboards.
- **Load order:** scripts load from `../bower/`, with plugins first, then AdminLTE, then `table.js` and `schemaSpy.js`. The paths are relative, so moving the folder breaks them. Everything here is EOL.

## 4. Icon fonts, DataTables and SchemaSpy 6.0.0 pages
- **Fonts:**
  - Ionicons 2.0.0, Font Awesome 4.7.0, Glyphicons.
  - Google Fonts (Indie Flower, Source Sans Pro) and BCSans. BCSans Bold is declared `font-weight: normal`.
  - Codepoints are generated and aliased.
- **DataTables with Bootstrap 3 and Buttons 1.3.1:**
  - Export backends: HTML5 (FileSaver, JSZip, pdfMake) and legacy Flash.
  - OOXML styles: `cellXfs` is 61 or 67 per different notes, and `_excelSpecials` maps to style ids 56–66.
- **SchemaSpy pages:**
  - Shared scaffold with hardcoded column indexes.
  - Table pages for "postgres" and "auth".
  - Many are empty stubs.
  - Regenerate them, don't hand-edit them.

## 5. Database documentation (SchemaSpy exports, PostgreSQL 11.x)
- **Payments DB (14–15 tables):**
  - Lookups: `corp_type`, `fee_code`, `filing_type`, `payment_method`, `payment_system`, `status_code`.
  - Billing chain: `fee_schedule` → `payment_account` → `invoice` → `payment_line_item`, `fee_item`, `receipt`, `transaction`. Also `payment` and `payment_transaction` (uuid PK).
  - Alembic `v824f5ef280c6` adds `CA_SEARCH`.
- **Org/identity DB (11–12 tables):**
  - `user`, `org`, `membership`, `affiliation`, `contact_link`, `entity`, `contact`, plus lookups.
  - Alembic `e7c262b6f986` adds `STAFF` and `SBC_STAFF` org types.
- **Older auth schema:** `users`, `action_log`, `affiliation_business`.
- **Reading the diagrams:**
  - The DOT arrows are inverted (`rankdir=RL`, `dir=back`). Read each edge as FK child → parent.
  - Every FK is restrict/no-cascade.
  - Money is float8.
  - `users.passwd` and `entity.pass_code` may be plaintext.
  - Row counts are stale snapshots, mostly 0.
- **Pay API code:** `Invoice` and `Payment` use an `include_properties` whitelist, and `search_purchase_history` raises `BusinessException` above 60000 records.

## 6. CI/CD, OpenShift and Kubernetes
- **Docs and workflows:**
  - GitHub Actions CI (setup-job gate → lint, test, build-check) and CD (OpenShift by push or dispatch, and GCP via `bcregistry-sre` reusables).
  - Makefiles for about 20 repos.
  - A COLIN API README.
  - BCROS Jenkins (zcd4ou-\* namespaces).
  - An OpenShift 4 migration runbook.
- **OpenShift templates:**
  - NATS Streaming with Postgres, Postgres variants, `bcol-api`, coops-ui (Caddy), entity-filer and other lear components, build templates, CronJobs, RBAC, Oracle 12.2 and nginx.
  - Mock-API proxies on port 4010.
- **Namespaces:** `cc892f` (lear), `6e0e49` (auth), `78c88a` (pay), plus `fsxqpf-prod`, `hak2zo-dev` and `gl2uos-tools`.
- **Manifest fragments:**
  - CronJob, Job, container and pod specs, DeploymentConfig, HPA, and a PostgreSQL stack.
  - Env comes from `secretKeyRef` on `${NAME}-${TAG}-secret`.
  - A vault-to-application mapping.
- **Cautions:**
  - Mixed `${VAR}` and `${{VAR}}` templating must be processed before applying.
  - Hardcoded `TAG_NAME="dev"` in CD workflows.
  - The GCP workflows trigger only on `feature-legal-name` and `feature-gcp`.
  - Unpinned reusables (`@main`).
  - EOL runners and pins (`ubuntu-20.04`, Python 3.8, Postgres 9.6/10, nodejs:8, Oracle 12.2).
  - `batch/v1beta1` is deprecated.
  - `restartPolicy: Never` with `activeDeadlineSeconds: 1600` means no retry.
  - A 2Gi memory limit against a 256Mi request.
  - Probes on 7070 while the container port is 8080.
  - Plaintext credentials and secrets.
  - `curl | bash` in BCROS.
  - Recreate strategy causes downtime.
  - Many fragments are truncated.

## 7. Shell and logging snippets
- **Shell:** `while read ... export $line` loading `.env`, then `source venv/bin/activate`.
  - Gotchas: `.env` loads twice, quoted values break, and a missing `.env` gives no error.
- **Python `logging` INI configs:**
  - A console handler writes to stdout. Child loggers (`api`, `pay_api`, `bcol_api`, `tracing`, `sqlalchemy.engine.Engine`) set `propagate=0`.
  - Logger levels set the effective floor.
- **`setup_logging(conf)` helper:** it uses `fileConfig` and prints status. It never raises on a missing conf, and tests use `capsys` with a weak `startswith` check.
- **Feature flags:** a LaunchDarkly `Flags.init_app` and `FileDataSource`. In production, a missing `LD_SDK_KEY` silently skips init.

## 8. Python services and test suites
- **pay-api:**
  - EFT short names: `/eft-shortnames` and `/shortname-refund`, statuses PENDING through COMPLETED, and a reversal pipeline.
  - Rules: a reversal needs payment within 60 days and all invoices PAID. Refunds are editable only while PENDING_APPROVAL.
  - Also covers accounts, refunds, statements, fees, routing slips (FAS) and `RefundService`.
- **pay-queue:** TDI17 fixed-width (140 characters) parsers `EFTHeader`, `EFTRecord` and `EFTTrailer`. Amounts are in cents, and any error rolls back and marks the file FAILED.
- **Jobs:** `invoke_jobs.py <JOB_NAME>` dispatches 15 jobs against CFS/CAS, with CGI/EJV feeder files and statements. The statements-due job must run at 08:00 UTC or later.
- **bcol-api tests:** `MockLDAP`, SOAP mocks, 409 on a duplicate active `bcol_id`.
- **auth-api tests:** orgs, users, products (MHR qualified-supplier flows), invitations and affiliations. GOVM orgs auto-approve.
- **legal-api tests and validators:**
  - Filings v1/v2, allowed-filings matrices, and validators (amalgamation, continuation-in, incorporation, dissolution, restoration, firms, share classes).
  - Document availability: PAID and COMPLETED give 200, PAPER_ONLY and PENDING give 404.
- **entity-filer tests:**
  - BN/CRA retry: a mocked 500 gives `retry_number=9`, which is 10 attempts.
  - `process_filing` per filing type, and correction tests.
- **Cross-cutting test cautions:**
  - Shared mutable fixtures need `deepcopy`.
  - Some assertions never run (outside a `with pytest.raises` block, or a `t`-prefixed `tpost_valid_ar`).
  - Heavy mocking and duplicate test IDs.
  - DST and UTC fragility.
  - Typos that must be matched (`_is_business_affliated`, `factory_membersip_model`).
  - Flag fixtures (`disable-nr-check` bypasses the name-request check).
- **Code bugs flagged:**
  - `RefundService` getters recurse infinitely.
  - `update_transaction` marks an invoice PAID on a short payment.
  - The EJV `batch_type` filter looks inverted.
  - The BCOL sync uses f-string SQL.
  - `apply_eft_credit` returns silently on insufficient balance.
  - Broad `except` blocks in jobs hide failures.

## 9. API specs and fixtures (OpenAPI, JSON Schema draft-07)
- **CAS/CFS (PayBC):**
  - Customer hierarchy under `/cfs/parties/{party}/accs/{acc}/sites/{site}/…`.
  - The host `heineken.cas.gov.bc.ca:7019` is a test host.
  - Most paths are stubs.
- **BCOL:** `POST /profiles` and `POST /payments`, with typos such as `adress.json`, which must resolve as written.
- **Pay API v1.0.7:**
  - Fees, payment-requests, accounts, statements and refunds.
  - Routing slips: 9-digit number, FAS roles, and a `_validate_linking` check.
- **Auth/Accounts API v1.0.1:** `/orgs`, `/users`, `/entities`, authorizations and `/codes`. Sample entities are CP0001234–CP0001239.
- **Notify API v1.0.0:** `POST /Notification` (201 or 422), with camelCase requests and snake_case responses.
- **Report API:** `POST /reports`.
- **Business Registry API:** business, addresses, parties, filings and documents. Business search is public.
- **Shared boilerplate:** `ErrorResponse {code, message}`, hardcoded CORS `*`, Firebase hosting and a CSP with `unsafe-eval`. A stray OpenSSL/TSA config is unrelated.
- **Cautions:**
  - The `^(.*)$` pattern and `""` defaults validate nothing.
  - External `$ref`s to `bcrs.gov.bc.ca` must resolve.
  - Copy-pasted `$id` and title errors, and typos.
  - Truncated or empty schemas.
  - Request and response casing differs.

## 10. Keycloak SSO tooling (sbc-auth)
- **Postman:**
  - Client creation: `POST .../auth/admin/realms/fcf0kpqr/clients`, with environment "Keycloak-DEV".
  - Passcode user import: create, get id, reset password, get group, add to group.
  - Collections for legal-api, auth-api and pay.
- **Realm export ("demo" realm):**
  - Roles, groups, and the clients `sbc-auth-web` and `sbc-auth-admin`.
  - Protocol mappers, including hardcoded claims.
- **Backend:**
  - `KeycloakService`.
  - `remove_users.py`, whose default realm is `fcf0kpqr`.
  - Flask-Admin `SecuredView`.
- **Local-dev Docker Compose:** Keycloak 12/15/16 on 8081, nginx on 8080, and Prism mocks on 4010.
- **Vue/TS services:** Axios clients and the auth, legal, pay and EFT services.
- **Cautions:**
  - Plaintext secrets and placeholder client secrets (`1111111111`, `2222222222`).
  - A hardcoded realm and hosts that differ between exports.
  - `web-origins` defaults to `*`.
  - Hardcoded mapper claims override real user data.
  - `service-account-sbc-auth-admin` is broadly privileged.
  - Token scripts never check expiry.
  - `OVERWRITE_EXISTING` wipes state.
  - Keycloak 12 is EOL.

## Overall cautions
- Almost everything is generated, vendored, truncated or duplicated, so no single fragment is authoritative. Verify against full sources.
- Placeholder IDs, secrets and test data appear throughout and must not be treated as real.
- Typos in names and keys are often load-bearing and must be matched exactly.
- Many components are EOL, and many tests are skipped, vacuous or mock-heavy.
