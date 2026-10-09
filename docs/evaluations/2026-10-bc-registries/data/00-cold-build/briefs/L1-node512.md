<!-- level 1, node 512, children [90, 409, 415, 430, 439, 446, 451, 452, 461, 468, 472, 475, 476, 487, 488, 489] -->

**Parent brief: BC Registries codebase test suites and fixtures (legal-api, entity-filer, auth_api, pay_api, colin_api)**

**What this is:** A set of condensed notes on mostly Apache 2.0 (Province of British Columbia) Python code. It is mainly pytest suites, plus factories, fixtures, a few source modules (validators, models, enums, BN/CRA helpers) and a pay runbook. A small group of feature-flag fixtures and a pytest debug config sits alongside it.

## Routing map

**1. Feature-flag fixtures and tooling config**
- Default flag trio: `string-flag="a string value"`, `bool-flag=true`, `integer-flag=10`. Variants add `enable-eft-payment-method`, `enable-legal-name-fix`, `disable-nr-check` and `enable-involuntary-dissolution-filter` with its nested `involuntary-dissolution-filter` (include/exclude accounts).
- `enable-involuntary-dissolution` (alone, and with `namex-nro-decommissioned: true`), `disable-specific-service-provider`, and an empty `flagValues`.
- A pytest debug config: `justMyCode=false`, `console=integratedTerminal`.
- LaunchDarkly flag-service tests in colin/auth/pay_api.

**2. Cross-service boilerplate tests** (colin_api, auth_api, pay_api)
- Meta/info endpoint, `/ops` healthz/readyz, `get_run_version`, named config and prod secret key, the CORS preflight decorator, and flags.

**3. auth_api**
- API endpoint tests: users, entities, orgs, products, API keys, authorizations, documents/affidavit, tasks, codes and more. Also model, service (including Keycloak and Minio) and utility tests.
- Source: Affidavit/Task models, enums, `Flags`, `validate_roles`, passcode functions.
- Factories and scenario data.

**4. pay_api database-layer model tests**
- Lookup models: CorpType, FilingType, PaymentMethod, PaymentSystem, StatusCode (commented out).
- Transactional models: Comment, NonSufficientFunds, Payment, PaymentAccount, Receipt, PaymentTransaction (`find_stale_records`).
- Pay runbook, covering stuck invoices, routing slips, reconciliation and PUBSUB replay, and a Zenhub release-sync script.

**5. legal-api: filings, documents and permissions**
- Parametrized document-availability fixtures (`/api/v2/businesses/{id}/filings/1/documents/{docType}`): status maps to outcome (PAPER_ONLY/PENDING give 404, PAID/COMPLETED give 200).
- Filing API v1/v2 tests (drafts, payment integration, deletion, AR/AGM, fee codes, comments, tasks, internal/COLIN).
- `DocumentMetaService`, ledger displayName, receipts, Name Request (namex) validation, business search.
- Allowed-filings permission matrices (`get_allowed_filings`) by state, legal type, role and blocker (admin freeze, in dissolution, good standing, incomplete filings, amalgamation). Digital credentials checks.

**6. legal-api: validators and their tests**
- Amalgamation (role composition regular/horizontal/vertical, foreign and LEAR business rules), continuation-in, incorporation, alteration, dissolution, registration, restoration, special resolution, court order, admin freeze.
- Firms (SP/GP) party, office and correction rules.
- Share-class and series matrix, repeated per entity type: BEN/BC/ULC/CC, and CBEN/C/CUL/CCC for continuation-in.
- Involuntary dissolution service (`_get_businesses_eligible_query`, flag filtering).
- JSON diff utilities (`Node`, `diff_dict`, `diff_list`), Business model (good standing, alternate names), AR/AGM/COD, JSON date converters, `ConsentContinuationOut`.

**7. legal-api: models, v1/v2 endpoints, reports and admin**
- Models: Batch, BatchProcessing, Furnishing(Group), Configuration, Party/PartyRole, Resolution, Comment, Jurisdiction, Document, Review/ReviewResult, DCConnection/DCDefinition, RequestTracker, Address, Alias, ShareClass/Series.
- Endpoints: v1/v2 sub-resources, admin reviews, `/admin/bn`, configurations and dissolution statistics, requestTracker, MRAS, error handlers.
- Reports/PDF tests, env-var skip markers (`RUN_*_TESTS`), snapshot helper.

**8. entity-filer: processors and workers**
- BN/CRA integration code: `has_party_name_changed`, `_inform_cra`, `_get_bn`, `_get_firm_legal_name` (top 2 names plus "et al"). BN retry, change-of-status and admin tests share one pattern: a mocked 500 gives `is_processed=False` and `retry_number=9` after 10 attempts.
- `process_filing` tests for alteration, special resolution, dissolution, incorporation, conversion, amalgamation, continuation-in, consent continuation out, restoration, put-back-on, change of address (delay logic), transition, and registration/change of registration (SP/GP).
- Correction tests: BC/BEN/CC/ULC and GP/SP, share-class and resolution-date operations, coop special-resolution corrections.
- Component processors (offices, parties, share structure) and PDF/Minio helpers.

## Cross-cutting cautions
- **Isolation and shared state:** templates and fixtures must be `deepcopy`'d. Module-level mutable fixtures leak between tests. Several tests rely on the `session` fixture for cleanup, `freeze_time` or hardcoded identifiers (`CP7654321`, `BC7654321`, `FM0000001`, `BC1156638`).
- **Weak or never-running assertions:**
  - Some assertions sit outside `with` blocks.
  - Mocks are often not verified as called.
  - `tpost_valid_ar` never runs because of its `t` prefix.
  - Some parametrize decorators are cut off.
  - Several tests have commented-out assertions.
- **Duplicated IDs and cases:** duplicate test IDs (`ben_ia_completed`, `cben_cont_in_completed`) with different expectations. Duplicate helper definitions (`create_test_user` twice).
- **Heavy mocking:** NameX, NAICS, email, events and the account service are mocked, so tests can pass while real contracts have drifted.
- **Date and timezone fragility:** DST and UTC offsets (hardcoded +08:00, T07/T08), `datetime.utcnow()` near midnight, and the CCO 6-month expiry. The `-00:00` offset is non-standard.
- **Typos that must be matched or are bugs:** `_is_business_affliated`, `factory_membersip_model`, `hashed_passcod_bytes`, `test_delete_bcros_valdiations`, `continu_in_corps`.
- **Flags:** `disable-nr-check` bypasses name-request validation entirely. In `legal_api`, `flags.is_on` mock choices change outcomes (good standing, namex). A production setup without a LaunchDarkly SDK key either silently disables flags or raises `KeyError`, depending on service. A flag's nested config (`involuntary-dissolution-filter`) must be gated on its enable flag. Flag fixtures with an empty `flagValues`, or with `enable-involuntary-dissolution` and `namex-nro-decommissioned` both true, may not reflect production state.
- **Authorization nuance:** staff get far more filings than general users, and HISTORICAL businesses give general users none. `deletion_locked` returns 401, not 403. Several endpoints require `STAFF_ROLE` or `SYSTEM_ROLE`, and an empty or basic role gets 401.
- **Semantic traps:**
  - `cessation_date=None` means active.
  - `oldValue` and `newValue` in the JSON diff are reversed.
  - Series maxShares must not exceed class maxShares.
  - `_has_pending_filing` treats PAID as pending.
  - `tax_id` is `{BN}{program_id}{ref_no zfill 4}`.
  - Retry count 9 means 10 attempts.
- **Integration dependencies:** live Minio and Keycloak, DB sequences, and env-gated skips (`@skip_in_pod`, `skipif` on falsy env vars) all affect what actually runs.
