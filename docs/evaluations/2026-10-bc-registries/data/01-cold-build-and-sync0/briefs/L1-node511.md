<!-- level 1, node 511, children [84, 246, 266, 394, 414, 416, 431, 438, 444, 454, 459, 485, 486, 613, 614, 622, 623, 624, 625, 636, 637] -->

# BC Registries "lear" ecosystem: parent brief

This set covers condensed notes on the BC Registries (Province of British Columbia, mostly Apache 2.0) Python/Flask stack. It spans the Legal API, COLIN API, Payment API, Auth API and BCOL API. It also covers the email worker and events listener, the Fee Admin UI, the digital-credentials code, and a set of Jupyter test and ops notebooks.

## Components and where to look

**Jupyter notebooks (test/ops tooling)**
- Shared helpers:
  - Legal API config: DB `host.docker.internal:5353`, dev URLs, NATS.
  - Service clients: COLIN, LEGAL, Auth (`get_auth_token`, `affiliate_nr_to_account`), NAMEX (`create_nr`, `update_nr_state`).
  - Filing and IA payload factories.
- Loaders for COOP test businesses and filings, such as `CP0000842` and `CP0000840`. They cover incorporation applications (IA), alterations, annual reports, special resolutions and similar.
- End-to-end flows: Name Request (NR) creation, BEN/COOP incorporation from an NR, change of name, and loading COOP from Colin via `q_cli.py`.
- Maintenance scripts: alteration `_meta_data` fix, Lear user backfill, good standing and voluntary dissolution (VD) reset, and the NAICS import generator.

**COLIN API**
- Wraps legacy Oracle COLIN data. Endpoints cover businesses, parties, offices, events, share structure and ProgramAccount, mostly gated by `COLIN_SVC_ROLE`.
- Address model, config, `/ops` health checks and `list_routes`.

**Payment API (`pay_api`)**
- Models and services:
  - SQLAlchemy models use `include_properties` whitelists for rolling upgrades: EjvFile, InvoiceReference, NonSufficientFunds, PaymentLineItem, Receipt.
  - Services cover receipts, NSF, codes and utilities.
- The payment-system factory routes by method and role:
  - Services: BCOL, PAD, PayBC (credit card), online banking, internal, EJV, direct pay, and an incomplete deposit service.
  - Zero fees go to internal. STAFF and SYSTEM can route to BCOL.
- The main app factory registers 21 blueprints under `/api/v1`. It also has the Fee Admin UI and the exception/error enum.
- The Fee Admin UI is a Flask-Admin layer built on a Keycloak-secured `SecuredView`. It has views for CorpType, FeeCode, FeeSchedule and DistributionCode, plus a parametrized test.

**BCOL API**
- Fronts BC Online SOAP services for profile lookup and payment (`apply_charge`/`debit_account`) through a zeep `BcolSoap` singleton. It also has a credential validator.
- Role enum, RFC 7807 errors and a `.env` template.

**Auth API**
- Covers the app bootstrap, about 24 blueprints (orgs, invitations, users, entities, products, tasks, documents and others) and `MinioService`.
- Services and validators:
  - Services: authorization, `RestService`, `ResetTestData`, affidavit, entity, SimpleOrg, documents and `publish_to_mailer`.
  - Validators: access type, org limit, duplicate org and payment method.
- Activity logging (`ActivityLog`, plus the publisher), `PubSubMessageProcessing` de-duplication, `send_email`, and product-subscription notifications (MHR).
- The API Gateway key service and the Keycloak client representation (17 mappers).
- A pytest suite for entities, orgs, affiliations and users, plus JWT claim fixtures.

**Legal API (v1/v2)**
- Business sub-resources: addresses, aliases, resolutions, share classes, directors, parties, and entity search.
- Business and filing resources: business lookup and creation, tasks, comments, documents and filings.
- Digital credentials: revoke, webhook, and the `issue`/`revoke`/`replace` helpers.
- Authorization and allowed-filings tests.
- Config, routing, admin, documents, meta, name requests, request tracker and the internal/MRAS blueprints.
- Service wrappers: AccountService, RegistrationBootstrapService, NameXService, MrasService, ColinService, FurnishingDocumentsService.
- Event publishing, with `publish_event` and `publish_entity_event`.
- Dev tooling: the Prism payment mock, VS Code debug configs and `requirements`.
- Other pieces: a change-of-registration test with CRA/BN, and the Traction decorators.

**Email worker and events listener**
- Email helpers and templates, queue message-context parsing, and the `MessageProcessing` model and service.
- Events-listener Flask factory.

**JWT auth module**
- The same `JwtManager` singleton appears in several services. A Pub/Sub token-verification decorator, `ensure_authorized_queue_user`, appears alongside it.

## Recurring caution themes
- **Secrets and credentials:**
  - Hardcoded or committed:
    - Notebook client credentials for `entity-notebook-service-account`.
    - `SECRET_KEY='a secret'`.
    - Test RSA keys in `TestConfig`.
  - Missing: blank `JWT_OIDC_*`, `KEYCLOAK_*` and BCOL values silently disable auth.
  - `ProdConfig` generates a random key per startup.
- **Security issues:**
  - SQL injection via the f-string in the COLIN `colin_id` POST.
  - `send_credential` decodes a JWT with `verify_signature=False`.
  - MD5 hashing of the API key.
  - Widespread `cross_origin('*')`, including the test reset.
  - A global `Alias.find_by_id` lookup that doesn't check the alias belongs to the business.
- **Known bugs:**
  - Notebooks:
    - `update_in_good_standing` looks inverted.
    - `get_identifier_from_affiliations` filters on an undeclared variable.
  - `Receipt.find_by_invoice_id_and_receipt_number` drops its `receipt_number` filter.
  - `StatementRecipients.email` returns `_lastname`.
  - `Entity.validate_pass_code` compares an unhashed value.
  - `__all__ = ('MessageProcessingService')` is missing its comma.
  - `DistributionCodeConfig` lists `stop_ejv` twice.
  - `BcolService` has a `reduntantFlag` payload typo.
  - `logger.Error` has the wrong case.
  - `get_jurisdicions` is misspelled.
  - `cors_preflight` hardcodes `Allow: GET`.
  - `DepositService` is a stub.
  - `test_delete_contact` posts one contact and deletes another.
- **Silent failures:**
  - Broad `except Exception` blocks hide errors in many places.
  - Failed Pub/Sub, event and activity publishes are logged but never raised. In Auth, `publish_to_mailer` failures are logged only.
  - Templates skip missing parts, and `get_pdf` returns mixed types.
  - Missing roles in the auth mock give 401, not 403.
  - A failed lookup falls back to a default or `None`.
- **Config traps:**
  - `FLASK_ENV` defaults to `production` in both app factories. `DEPLOYMENT_ENV=production` is paired with dev URLs in the notebooks.
  - Duplicate `AUTH_SVC_URL` and `REPORT_SVC_URL` in `.env`.
  - `staging` is accepted by `get_named_config()` but has no entry in `CONFIGURATION`.
  - Deprecated `flask_script` and `db.engine.execute`.
  - sqlalchemy is pinned below 1.4.
  - `make_versioned()` and logging setup must run first.
  - Import-only `models` is required for Migrate.
- **Test fragility:**
  - Stacked `@patch` decorators inject mocks in reverse order.
  - Hardcoded identifiers (`FM0000001`, `CP7654321`), fees and timestamps.
  - Shared `expected` values are reused across loops.
  - Cached products make test order matter.
  - Typos in the fixture name `TestAffliationInfo` and the parameter `access_ype` are load-bearing.
- **Truncated or import-only summaries:** the fee calculation service, the Invoice and Payment transaction services, `CFSService`, the `PaymentSystemService` base, `DirectPayService`, the Org/Membership/User/Task/Invitation auth services, and `generate_client_representation`. Their logic is not visible.
- **Behavioral quirks to remember:**
  - An idempotent entity POST returns 202.
  - A PATCH needs `statusCode` and `suspensionReasonCode` together, and `action` and `accessType` together.
  - The Name Request (NR) browser payment step is manual.
  - The Colin load needs a hand-run `q_cli.py`.
  - Temp (`T`-prefixed) identifiers use bootstrap lookup paths.
  - Refunds are manual (queue-triggered).
  - GAZETTE furnishings always return 404.
