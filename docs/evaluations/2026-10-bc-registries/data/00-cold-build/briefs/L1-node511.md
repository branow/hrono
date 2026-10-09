<!-- level 1, node 511, children [84, 246, 394, 414, 431, 438, 444, 445, 459, 460, 484, 485, 486] -->

# Parent brief: BC Registries (lear / Legal-entity) service codebase and tooling

This is a collection of condensed notes on the BC Registries Legal-entity ecosystem. All of it is Apache 2.0 code from the Province of British Columbia. It covers Flask/Flask-RESTX services, their tests and ops notebooks. Each service follows the same skeleton: `create_app(run_mode)`, a config map (development, testing, production, staging, default), a JWT manager reading `realm_access.roles`, `/ops` (`healthz`, `readyz`) and `/api/v1` blueprints, a `BusinessException` or `Error` enum, and Sentry and LaunchDarkly hooks.

## Routing map

- **lear notebooks (test and ops tooling).**
  - Shared helpers: Legal API config; clients for COLIN, LEGAL, Auth and NAMEX; filing and IA payload factories; payment helpers.
  - COOP test-data loaders, such as `CP0000840` and `CP0000842`.
  - End-to-end flows: create NRs, then BEN or COOP incorporation from an NR, and change of name.
  - Load COOP from COLIN into Lear.
  - Maintenance scripts: alteration `_meta_data` fix, user backfill, good-standing and VD reset, and the NAICS import generator.
- **COLIN API.**
  - Wraps legacy Oracle COLIN data. Almost every business endpoint needs the `COLIN_SVC_ROLE` role.
  - Endpoints cover businesses, parties, events, offices, share structure, ProgramAccount and `/info`.
  - Includes an `Address` model that creates its IDs differently for `CP` corporations.
- **BCOL API (`bcol_api`).**
  - Wraps the BC Online SOAP and LDAP services for payments (`/payments/bcol-accounts`) and profiles (`/profiles/bcol-profile`).
  - Uses the services `BcolPayment`, `BcolProfile` and `BcolSoap`.
  - An operations note covers fee codes, manual refunds and reconciliation with PAY-API.
- **Pay API (`pay_api`).**
  - 21 blueprints: accounts, statements, fees, invoices, payments, refunds, FAS routing slips, EFT and NSF.
  - `PaymentSystemFactory` picks among the BCOL, PayBC, PAD, EFT, EJV, Internal and Direct Pay services.
  - Models use `include_properties` whitelists for rolling upgrades. Also includes a Fee Admin UI.
- **Auth API (`auth_api`).**
  - Users, orgs, entities, contacts, memberships, affiliations, invitations, tasks, API keys, activity logs and Keycloak.
  - 24 blueprints. Services use Minio presigned URLs, Notify email and GCP Pub/Sub.
  - Includes the `ApiGateway` service and its Keycloak client representation.
  - Includes shared exception and BCOL validator modules, and Pub/Sub JWT verification (`ensure_authorized_queue_user`).
- **Auth API test suite.**
  - The User service wrapper.
  - The endpoint test skeleton (setup POST to `/users`, `factory_auth_header`, schema assertions).
  - Jwt claim and test-data fixtures.
- **Legal API (v1 and v2).**
  - v1: businesses, documents, nameRequests.
  - v2: admin (BN and configurations), digital credentials, internal filings, mras, requestTracker, NAICS and furnishings.
  - Business sub-resource GETs: addresses, aliases, resolutions, share classes, directors, parties.
  - Also: `POST /search`, business lookup and creation, tasks (to-dos), comments, documents, and filings.
  - Service layer: Account, RegistrationBootstrap, Colin, Mras, NameX, DigitalCredentials, Flags, `publish_event`.
- **Legal API tests.**
  - Authorization.
  - `is_allowed`, `get_allowed_actions` and `get_allowed_filings`.
  - Digital credentials: `is_self_registered_owner_operator`.
  - JWT helpers.

## Cross-cutting cautions

- **Secrets and config**
  - Hardcoded `SECRET_KEY='a secret'` and embedded test RSA keys.
  - Two notebooks embed `entity-notebook-service-account` credentials.
  - `ProdConfig` generates a random key at import time.
  - Several empty auth settings silently disable JWT.
  - `DEPLOYMENT_ENV=production` is paired with `*-dev` endpoints in the notebooks.
  - `FLASK_ENV` defaults to production.
  - `get_named_config` accepts `staging`, which `CONFIGURATION` lacks.
- **Security**
  - `cross_origin(origins='*')` is applied broadly.
  - Legal API `POST /internal/filings/colin_id` builds SQL by string formatting, so it is open to SQL injection.
  - `send_credential` decodes the JWT with `verify_signature=False`.
  - `Alias` lookups don't check ownership.
  - `HashingService` uses MD5.
  - `BusinessException` returns its raw code and message to clients.
- **Known bugs**
  - Pay `Receipt.find_by_invoice_id_and_receipt_number` drops its filter.
  - `StatementRecipients` email getter returns `_lastname`.
  - Auth `Entity.validate_pass_code` compares an unhashed passcode.
  - `RestService.put()` omits headers.
  - Notebook `update_in_good_standing` looks inverted, and Dissolution/Transition reuse `SPECIAL_RESOLUTION` content.
  - `cors_preflight` hardcodes `Allow: GET`.
  - `ensure_authorized_queue_user` has an inverted-looking check.
  - `CustomException` doesn't inherit from `Exception`.
  - Lowercase `logger.Error`.
  - `get_jurisdicions` is misspelled.
- **Silent failures**
  - Broad `except Exception` blocks.
  - `publish_event` and mailer publishing log only.
  - `Flags` returns False on error.
  - Failed PDF merges return None.
  - Schema `validate()` returns inconsistent tuples.
  - Org PATCH pairs (`statusCode` with `suspensionReasonCode`, `action` with `accessType`) 400 when only one is sent.
- **Fragile patterns**
  - Healthz uses Oracle-only `select 1 from dual`, and readyz is a static 200.
  - The in-memory `simple` cache doesn't suit multiple workers.
  - Models are imported only for migration discovery, and logging setup must come first.
  - `flask_script` is deprecated.
  - Two-step HTTP calls can leave orphaned records, such as `create_affiliation` and `delete_affiliation`.
- **Notebook and test quirks**
  - Notebook runs depend on prior runs, on manual steps (`q_cli.py`, NR payment in the browser, waiting a few minutes), and on a lear DB port-forward.
  - Loader filings are incomplete, so receipts won't work.
  - Hardcoded IDs, paths and timestamps.
  - Mocks replace `flask.request.headers.get` globally, with fixed far-future JWT expiry.
  - Test names and docstrings are misleading, for example `test_delete_contact` and the `TestAffliationInfo` typo.
  - Tests that nest loops reuse a single `expected` value.
