<!-- level 1, node 512, children [90, 211, 387, 415, 430, 439, 446, 451, 452, 458, 461, 467, 468, 475, 476, 487, 488, 489, 598, 599, 600, 629, 630] -->

# Parent brief: test-support and test-suite condensations for BC Registries services

## What this set is
These are condensed notes on pytest suites, fixtures, config and a few production modules. They come from the BC Province (Apache 2.0) registries codebase. The services are **legal_api**, **entity-filer**, **entity-emailer/queue workers**, **auth_api**, **pay_api**, **colin_api** and a pay job/SFTP service. There are also small feature-flag and pytest-debug snippets.

## Routing by area

**Flags and tooling**
- Test-fixture flag sets: `string-flag="a string value"`, `bool-flag=true`, `integer-flag=10`. Business flags include `enable-involuntary-dissolution`, `enable-legal-name-fix`, `namex-nro-decommissioned`, `enable-eft-payment-method`, `disable-nr-check` and `disable-specific-service-provider`.
- A pytest debug config (`justMyCode=false`).
- LaunchDarkly `Flags` service tests for legal_api, pay_api (`PAY_LD_SDK_KEY`) and auth_api.

**Test infrastructure**
- Fixtures: conftest modules (session-scoped `app`/`db`, per-test SAVEPOINT `session`), Docker mocks (keycloak, minio, stan), user/role mocks, and FakeOidc.
- Skip markers: `skip_in_pod`, `RUN_*_TESTS`, `oracle_integration`.
- Config: local `.env` files and `TestConfig`/`ProdConfig` modules, with hardcoded test keys.
- Shared factories and helpers (`create_business`, `create_filing`, `factory_*`, `prep_*`), filing JSON templates, and datetime/dict helpers.
- Config tests (`get_named_config`, `SECRET_KEY`), meta/version tests, CORS preflight, `/ops` health, and MinioService.

**Filing validation (legal_api)**
- Production validators: a router plus about 25 per-type validators, shared helpers (PDF, party names, foreign jurisdiction, name request, share structure, court order), and address and warning lookup tables.
- Per-type suites:
  - Amalgamation, continuation in/out and CCO, incorporation, alteration, change of name/address/directors, and dissolution.
  - Restoration, special resolution, AGM, annual report and admin freeze.
  - Firms (SP/GP registration, conversion, change of registration and correction), and generic, IA and CP special-resolution corrections.
  - Court orders.
- Address and share-class matrices: the BC/CA-only address cases and the class/series matrix across entity types.
- Fee codes, `get_allowed_filings` permission matrices with blocker scenarios, and digital credentials.

**Filing processors (entity-filer)**
- Worker and processor tests: CRA/BN hub tests with retry (`retry_number=9`), corrections, conversion, incorporation, registration, amalgamation, restoration, dissolution, put-back-on, change of address, transition, continuation-in and CCO.

**Email and queue**
- The emailer `process()` function, CloudEvents-style queue payloads, and email-content tests.

**Models, endpoints and documents (legal_api)**
- Model tests: batch/furnishing/configuration, party/resolution/comment, review/ReviewResult, and DCConnection/RequestTracker.
- Endpoint tests: v1 and v2 businesses and sub-resources, admin/reviews, MRAS, and error handlers.
- Filing document endpoints, `DocumentMetaService`, ledger, reports and PDFs, and name request/namex.

**auth_api**
- Models and schema (Affidavit, Task, UserStatusCode), plus the Flags, passcode and `validate_roles` utilities.
- Resource, model and service tests.
- Enums, org/product/API-key/documents/CORS endpoint tests, and scenario/factory helpers.

**pay_api**
- Model tests for CorpType, FilingType, PaymentMethod, PaymentSystem, Payment, Receipt, NSF and PaymentTransaction.
- A pay runbook and the Zenhub release sync script.

## Cross-cutting cautions
- **Test hygiene**
  - Many tests mock heavily and don't assert that the mocks were called.
  - Shared module-level templates are mutated, so `deepcopy` is essential.
  - Some parametrize decorators are cut off, and some helpers are undefined in the snippets (`COA_FILING`, `base_url`, `factory_incomplete_statuses`, `AMALGAMATION_APPLICATION`).
  - There are duplicated test IDs and files.
- **Known bugs and typos**
  - `lists_are_equal` returns True only if the last pair matched.
  - `create_party` has a copy-paste condition bug.
  - `premium_user_mock` has a syntax error.
  - `('PAID')('COMPLETED')` is missing a comma.
  - `DATABASE_TEST_PORT="543313"` looks like a typo.
- **Skip and env gotchas**
  - `skip_in_pod` and `RUN_*` markers skip on any falsy or `'False'` value.
  - Production flags silently disable without an SDK key.
- **Domain rules**
  - Validators return `None` on success, otherwise an `Error` or a list of `{error, path}`.
  - Correction filings bypass the other validations.
  - Staff and general-user permissions differ sharply, and general users on HISTORICAL businesses get none.
  - Date and timezone logic is fragile (DST, UTC vs the legislation timezone, hardcoded offsets, `utcnow`).
- **Test-only secrets** (RSA keys, `'TEST'`, `minio123`) are in source. Never commit real credentials.
