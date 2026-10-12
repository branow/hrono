# today (sample 1)

# legal-api (BC Registries): overview

A Flask service for business filings in the BC registry. It validates, saves, prices, reports on and authorizes filings, and it wraps the external systems around them. Business data lives in Postgres (SQLAlchemy Continuum versioning). The REST surface is v1 (Flask-RESTX, `/api/v1`) plus v2 (blueprints under `/api/v2`, `/api/v2/businesses`, `/api/v2/admin`).

## Layers and where to start
| Layer | Components |
|---|---|
| App/routing | `create_app`, `resources/endpoints.py` (`Accept-Version` redirects, v1 default), `EndpointEnum`, `V2Endpoint.init_app`, `ops.py` |
| Filing REST flow | v2 `business_filings/business_filings.py` (v1 is the older copy), `colin_sync.py`, `business_tasks.py`, `reviews.py`, `internal_services.py` |
| Domain/models | `core/filing.py`, `core/meta/filing.py` (`FilingMeta`), `models/filing.py` (`FILINGS`, status listeners), `models/business.py`, `BusinessIdentifier` |
| Validation | `services/filings/validations/validation.py` (`validate` dispatch), `common_validations.py`, per-filing validators, comment validators, `business_checks` warnings |
| Authorization | `services/authz.py` (`authorized`, `get_allowed_filings`, blockers), `decorators.py` (`requires_traction_auth`) |
| External wrappers | `AccountService`, `namex.py`, COLIN, NAICS, `digital_credentials.py` (Traction/ACA-Py), MRAS, Minio, payment service (`PAYMENT_SVC_URL`) |
| Reports/PDF | `reports/report.py`, `business_document.py`, `report_v2.py` (Gotenberg), `furnishing_documents_service.py`, `PdfService`, `RegistrarInfo` |
| Infra | `Flags` (LaunchDarkly), `publish_event` (NATS CloudEvents), `errorhandlers.py`, `BusinessException`/`Error` |

## Shared conventions
- Every business route follows one pattern: look up the business (404), call `authorized()` (401), validate (400), persist.
- Identifiers starting `T` are temporary bootstrap registrations. They resolve through `RegistrationBootstrap`/`Filing.temp_reg` instead of `Business`, and they have to be cleaned up on delete.
- The filing JSON is `header` plus `filing.<type>`, and it drives fee codes, templates, ledger entries and validation.
- The status listeners and `locked`/`deletion_locked` guard the filing lifecycle.
- Versioned snapshots at a `transaction_id` rebuild history for reports and COMPLETED JSON.
- Errors have two forms. `Error(status, [dicts])` is returned by validators (422 for schema failures, 400 for business rules). `BusinessException` is raised by models and services. The schema error dict shapes differ: `path`/`error` for comments, `error`/`path` for filings.
- Staff, system and COLIN roles get special paths (`UserRoles`, `COLIN_SVC_ROLE`, `REDACTED_STAFF_SUBMITTER`).
- Rendered output goes through external services: the report service, Gotenberg and Minio.

## Cross-cutting hazards
- **Silent failure is the dominant pattern.**
  - `publish_event` and `Flags.is_on` swallow errors, so events are lost and flags read as off.
  - Wrappers (Traction deletes, NAICS, COLIN) return None.
  - `ReportV2` and the furnishing batch skip failed letters.
  - `save_filing` errors in the POST/PUT path are printed and execution continues.
  - `/bnmove` and the v1 tax-ID POST return success for missing businesses.
  - Missing-key validators raise `KeyError` and `ZeroDivisionError` instead of returning an `Error`.
- **Non-atomic multi-step writes** leave orphans or inconsistent state:
  - affiliation and entity creation, and bootstrap deregistration;
  - payment cancel followed by the draft reset;
  - review followed by the filing update;
  - the BN move;
  - credential revocation followed by the local save.
- **Cross-business reads:** `ShareClass`, `Alias` and `Resolution` are looked up by global ID without an ownership check.
- **Security:** `POST /internal/filings/colin_id/<id>` builds SQL with an f-string. The digital-credential JWT is decoded without signature verification.
- **Known bugs:**
  - `datetime.utcnow().strptime` is used on the directors `date` param.
  - `cors_preflight` always sends `Allow: GET`.
  - `RegistrarInfo` raises IndexError for dates before 1970.
  - Many docstrings are copy-pasted and wrong.

# today (sample 2)

# legal-api (BC Registries): overview

A Flask service for BC business filings. It exposes v1 (Flask-RESTX) and v2 (blueprints) REST resources and persists to Postgres through SQLAlchemy and Continuum versioning. It does three kinds of work:
- **Pre-submission validation** of filings.
- **Rendering** of PDF and JSON documents.
- **Gating and orchestration** of filings against external systems: payment, namex, COLIN, Minio, NATS, Account/Auth, Traction, MRAS, LaunchDarkly, and the report and Gotenberg render services.

## Where things live
| Concern | Entry points |
|---|---|
| App factory, config | `create_app(run_mode)`, `publish_event` (`services/__init__.py`) |
| Routing and versions | `resources/endpoints.py`, `resources/v1/__init__.py`, `resources/v2/__init__.py`, `EndpointEnum` |
| Filing CRUD, fees, resubmit | `resources/v2/business/business_filings/business_filings.py` (v1 is the older copy) |
| Filing state and JSON | `models/filing.py` (status listeners, `FILINGS`), `core/filing.py`, `core/meta/filing.py` |
| Validation | `services/filings/validations/validation.py::validate`, `common_validations.py`, comments `validate` |
| Warnings | `check_warnings`, `check_business`, `involuntary_dissolution` |
| Access control | `services/authz.py`, `decorators.py` |
| Reports | `reports/report.py`, `business_document.py`, `report_v2.py`, `PdfService`, `RegistrarInfo` |
| Integrations | `AccountService`, `digital_credentials.py`, `namex.py`, `colin.py`, `flags.py` |
| Errors | `BusinessException`, `Error`, `errorhandlers.py` |
| Colin sync and internal | `v2/business/colin_sync.py`, `v2/internal_services.py` (`/bnmove`) |

## Conventions that cut across the code
- **Validators return values, not exceptions.** They return `None` or an `Error(status, [{path, error}])`. Schema failures are 422 and business-rule failures are 400. The comment and filing validators order `error` and `path` differently.
- **Two-step access pattern.** Resources look up the business (404), call `authorized()` (401), validate (400), then persist. Admin and internal routes use `UserRoles` or `COLIN_SVC_ROLE`.
- **Temp identifiers.** Identifiers starting with `T` mean a draft registration and are resolved through `RegistrationBootstrap` and `temp_reg`, not `Business`. Deletion must also remove the bootstrap.
- **Filing status** is derived by model listeners (with `skip_*_listener` bypasses). It is not set freely. Locked filings can't be deleted.
- **Legal-type branching.** Rules diverge for COOP, SP/GP and corporations in validation, fees, tasks, reports and warnings.
- **Versioned snapshots.** Reports and filing JSON for completed filings are rebuilt from history at `transaction_id`.
- **Staff and non-staff differences.** These cover submitter redaction (`REDACTED_STAFF_SUBMITTER`), date limits and amalgamation checks.
- **Event flow.** Changes publish CloudEvents to NATS subjects (emailer, filer, entity-event).

## Hazards that recur
- **Silent failure is the dominant pattern.**
  - Broad `suppress` or `except` blocks hide errors.
  - `publish_event` and `Flags.is_on` swallow exceptions.
  - `ReportV2` and the furnishing merge return None.
  - Traction and NAICS calls return None.
  - `/bnmove` and the v1 internal POST return success despite failures.
  - `save_filing` errors are printed and ignored.
- **Non-atomic multi-step writes** leave orphans or inconsistent state. Examples are affiliation and entity creation, payment cancel then draft reset, Traction revoke then local save, and the bootstrap delete.
- **Cross-business reads.** `ShareClass`, `Alias` and `Resolution` are looked up by global ID without checking the business.
- **Known bugs and security issues:**
  - `datetime.utcnow().strptime` in the directors `date` handling.
  - An f-string SQL injection in `/internal/filings/colin_id`.
  - JWTs decoded with `verify_signature=False`.
  - Validators that raise `KeyError` or `ZeroDivisionError`, or return the wrong type.
  - `RegistrarInfo` raises IndexError for dates before 1970.
- **Docstrings are unreliable.** Many are copy-pasted. Don't trust them over the code.

# area-core (sample 1)

# legal-api (BC Registries): filings, validation, reports and external integrations

Flask service that builds the app, exposes v1/v2 REST endpoints for businesses and filings, validates filings, derives fees and documents, and renders PDFs. It hands work to payment, namex, Colin, Account/Auth, Traction, MRAS, Minio, the NATS queue, a report service and Gotenberg.

## Parts
- **App factory, config and REST resources (v1/v2):** `create_app`, read endpoints, admin, internal and ops routes, and `publish_event`.
- **HTTP resource layer: routing and versioning:** Mounts v1 namespaces and v2 blueprints, negotiates `Accept-Version`, and holds small endpoints (comments, directors, share classes, signatures).
- **Business filings, tasks, comments, documents and Colin sync:** Filing save, payment, completion, resubmit and delete; to-dos; Colin sync endpoints.
- **Core, errors and filing REST endpoints:** `Filing` domain, `FILINGS`/`FilingMeta`, error handlers, LaunchDarkly flags, and the v2 filing endpoint.
- **Models, core helpers and a few resources/services:** SQLAlchemy models, filing status rules, review workflow, involuntary-dissolution eligibility.
- **Filings, fees, documents, reports and authorization:** Fee codes, document manifest, redaction, ledger, `authz` filing eligibility, and versioned history.
- **Filing validation, effective-date handling and warnings:** Per-filing-type validators and business warnings.
- **Validation entry points:** Package exports for the filing, comment, document and warning validators.
- **Reports and PDF generation:** Filing, summary/seal and furnishing PDFs, and registrar stamping.
- **Service layer and decorators for external integrations:** Account/Auth, Traction, NameX, COLIN, NAICS wrappers and access decorators.

## How the parts work together
**Filing submit (POST/PUT):**
1. The v2 filing endpoint in `business_filings.py` saves the filing. It validates unless the request is a draft or a historical or pre-epoch filing.
2. Validation goes through the entry point `filings.validate`, which runs `validation.py::validate`. That schema-validates, dispatches by filing key, and returns an `Error`. Name request checks use the NameX wrapper.
3. `_get_filing_types` derives fee codes and `_create_invoice` posts to the payment service. The payment token is saved on the filing.
4. `complete_filing` publishes to the queue, or `_process_colin_filing` handles COLIN-source filings.
5. For new businesses, `create_bootstrap` and `register_bootstrap` in the Account service wrapper create the temp `T` identifier and its affiliation.

**Review:** `POST /reviews/{id}` writes a `ReviewResult`, updates `Review` and `Filing`, and publishes to the emailer subject. It also publishes to the filer subject for an approved filing whose effective date has passed. Resubmit moves the review to RESUBMITTED.

**Reports:** a request goes to `reports.get_pdf` and `Report.get_pdf`. Static types come from Minio. Others use filing JSON, or versioned history through `get_company_details_revision`. `RegistrarInfo` supplies the registrar. Furnishing letters go through `ReportV2` to Gotenberg and are merged by `FurnishingDocumentsService`.

**Filing states:** the `Filing` model's status listener sets DRAFT, PENDING, PAID, COMPLETED and EPOCH. Review code sets AWAITING_REVIEW, CHANGE_REQUESTED, APPROVED, REJECTED and RESUBMITTED. Cancelling payment calls `reset_filing_to_draft()`, which returns the filing to DRAFT. COMPLETED filings whose parent is also COMPLETED read as CORRECTED.

## Shared rules
- Auth is JWT. `authorized()` or `authz` is checked per route: 401 when denied, 404 for an unknown business.
- Identifiers starting `T` are temp registrations, resolved through bootstrap and the filing rather than `Business`.
- Validators return `Error` (400 for business rules, 422 for schema) or None.
- Versioned lookups use `transaction_id`, and rows with `operation_type == 2` are excluded.
- Staff submitters are shown as `REDACTED_STAFF_SUBMITTER` to non-staff.

## Hazards
- Failures are swallowed across parts, so work is lost silently. Examples: `publish_event`, `Flags.is_on`, `ReportV2`, furnishing batches, `save_filing` in the POST path, and `/bnmove`.
- Multi-step writes are not atomic. Payment cancel and draft reset, review and filing updates, affiliation create and delete, and bootstrap deletion can leave orphans or out-of-sync state.
- Child records are fetched globally without a check against the business in the path (`ShareClass`, `Alias` and `Resolution`). `datetime.utcnow().strptime()` is used for `date` parameters in directors.

# area-core (sample 2)

# legal-api (BC Registries): filings, validation, reports and external integrations

Flask service that builds the app, exposes v1/v2 REST resources for businesses, filings, tasks, comments, documents, admin and internal endpoints, and enforces filing rules. It takes work from the UI, JWT clients, Colin service and cron jobs. It hands work to Postgres models, the payment service, NATS (emailer, filer, entity-event subjects), Minio, namex, Colin, MRAS, Account/Auth API, Traction, and report and Gotenberg renderers.

## Parts
- **Reports and PDF generation (legal-api):** renders filing, business-document and furnishing PDFs and stamps registrar certification.
- **Legal API: service layer and decorators for external integrations:** access gates (`authz`, decorators) and wrappers for Account/Auth, Traction, NameX, COLIN and NAICS.
- **Filing validation, effective-date handling and business warnings (legal-api):** pre-submission validators, warning checks, effective-date helpers and the Colin event model.
- **legal-api core, errors, and filing REST endpoints:** `Filing` domain, errors, feature flags, and v2 filing GET/POST/PUT/DELETE.
- **Validation entry points for filings, comments, documents and business warnings (legal-api services):** package exports of validators and the comment and schema validators.
- **legal-api: models, core helpers and a few resources/services (BC business registry):** SQLAlchemy models, filing status rules, review workflow, involuntary dissolution, versioned lookups.
- **Legal API: filings, fees, documents, reports and authorization:** fee codes, document manifest, ledger, redaction, filing-eligibility authz, report data.
- **Business filings, tasks, comments, documents and Colin sync (legal-api REST layer):** v1/v2 resources for filings, tasks, comments, documents, payment and Colin sync.
- **legal-api HTTP resource layer: routing, versioning and small endpoints:** version negotiation, mounts, comments, directors, share classes.
- **legal-api: app factory, config, and REST resources (v1/v2):** `create_app`, read endpoints, admin/internal/ops endpoints, event publishing.

## How the parts work together
**Filing submit (POST/PUT):**
1. The filing REST endpoints (v2 `business_filings.py`; v1 is the older copy in the filings REST layer) check authorization via the filing-eligibility authz.
2. Unless `draft=true`, they call `validate` (`services/filings`, defined in the validation part), which runs `validate_against_schema` (422) then the per-type validators (400). `only_validate=true` returns here.
3. `_save_filing` stores the Filing. `_set_effective_date` sets future-effective dates and may call `namex.update_nr_as_future_effective`.
4. `_get_filing_types` derives fee codes and `_create_invoice` posts to `PAYMENT_SVC_URL`, saving `payment_token`.
5. `complete_filing` runs. COLIN-source filings go to `process_colin_filing`, which either adopts the epoch transaction (`set_processed`) or publishes to the queue.
6. In the models, the status listener moves the filing: DRAFT → PENDING (payment token) → PAID → COMPLETED (transaction_id).

**New business:** the POST business resource calls `create_bootstrap`, `register_bootstrap` (which calls `AccountService.create_affiliation`, rolled back by `delete_affiliation`), then `saving_filings`. Identifiers starting `T` resolve through RegistrationBootstrap.

**Review:** `POST /reviews/{id}` writes `ReviewResult` and sets the Filing status. `set_review_decision` sets CHANGE_REQUESTED, APPROVED or REJECTED. It publishes to the emailer and, once the effective date has passed, to the filer. The resubmit module calls `resubmit_filing_to_awaiting_review`.

**Cancel payment and delete:** the payment DELETE is followed by `reset_filing_to_draft()`. Filing DELETE is refused when `locked` and, for `T` identifiers, also removes the bootstrap and Minio files.

**Reports:** `reports.get_pdf` → `Report.get_pdf` reads versioned data (`get_company_details_revision`), stamps via `RegistrarInfo`/`PdfService`, and POSTs to the report service. `BusinessDocument` serves summary and seal, validated by `validate_document_request`. `ReportV2` and `FurnishingDocumentsService` render dissolution letters through Gotenberg.

**Colin sync:** the Colin service GETs `/internal/filings` and PATCHes `colinIds`. `ColinLastUpdate` tracks the last event.

**BN move:** `/bnmove` updates `tax_id`, creates a registrar's notation filing and publishes events through `publish_event`.

## Shared rules
- Business routes call `Business.find_by_identifier` (404), then `authorized()` (401).
- Validators return `Error` or `None` (422 schema, 400 rules). Handlers turn exceptions into JSON.
- Feature flags come from `Flags.is_on`.
- Versioned queries use `transaction_id <=` the target and drop `operation_type == 2`.
- Submitter redaction uses `REDACTED_STAFF_SUBMITTER`.

## Hazards
- Failures are swallowed across parts: `save_filing` errors in POST/PUT, `publish_event`, the `Flags` methods, and `ReportV2` and batch furnishing PDFs (letters silently go missing). Filings can be partly saved and events or letters lost with no error.
- Multi-step writes are not atomic: payment cancel then draft reset, review and filing updates, `/bnmove`, and the affiliation and bootstrap rollback. A failure midway leaves orphaned or out-of-sync records.
- Several lookups assume the record belongs to the business or exists: `Alias`, `Resolution` and `ShareClass` are looked up globally. Some validators raise `KeyError` or `IndexError` instead of returning an `Error`.

# area-flows (sample 1)

# legal-api (BC business registry)

The legal-api Flask service builds the app, exposes the v1/v2 REST surface for business data and filings, validates filings, and renders PDF reports. It hands work to the payment service, namex, Colin, MRAS, the Account/Auth APIs, Traction, Minio, NATS (emailer, filer and entity-event subjects), the report service and Gotenberg. It takes work from the UI, JWT clients, the Colin service and cron jobs.

## Flows

### 1. Submit or update a filing (POST/PUT `/<identifier>/filings`)
1. **Business filings, tasks, comments, documents and Colin sync** and **legal-api core, errors, and filing REST endpoints** receive the filing JSON. The `edit` authorization is checked. `T`-prefixed identifiers go through `RegistrationBootstrap` instead of `Business`.
2. Unless `draft=true`, or the filing is historical or before the epoch, `validate` runs (**Filing validation, effective-date handling and business warnings**). It schema-validates, then dispatches by filing key. Failures return 400, or 422 for schema errors. `only_validate=true` stops here.
3. `set_effective_date` sets future-effective dates, and `namex.update_nr_as_future_effective` is called when the NR would expire first (**Legal API: service layer and decorators**).
4. `_save_filing` creates or updates the `Filing`. The model status listener (**legal-api: models, core helpers**) sets DRAFT, PENDING, PAID or COMPLETED from the payment and transaction fields.
5. `_get_filing_types` derives the fee codes (**Legal API: filings, fees, documents, reports and authorization**). `create_invoice` POSTs to `PAYMENT_SVC_URL` and saves `payment_token`, moving the filing to PENDING. A payment failure returns 402.
6. `complete_filing` publishes to the queue. COLIN-source filings go through `process_colin_filing`. A filing before the epoch adopts the epoch `transaction_id` and calls `set_processed`.
7. A filing in CHANGE_REQUESTED is instead resubmitted: the Review becomes RESUBMITTED and `resubmit_filing_to_awaiting_review` is called.

### 2. Create a new business
1. POST business (v2) checks the type against `NEW_BUSINESS_FILING_TYPES`.
2. `create_bootstrap` makes a `T` identifier. `register_bootstrap` calls `AccountService.create_affiliation`, and rolls back with `delete_affiliation` on failure.
3. `saving_filings` then follows flow 1. Failures return 503.

### 3. Staff review
1. `POST /reviews/{id}` (**models, core helpers**) accepts a decision only from AWAITING_REVIEW or RESUBMITTED. It writes a `ReviewResult` and `set_review_decision` moves the filing to APPROVED, CHANGE_REQUESTED or REJECTED.
2. It publishes to the emailer subject. It also publishes to the filer subject when the filing is APPROVED and its effective date has passed.

### 4. Delete a draft or cancel payment
1. DELETE needs `filing_id` and authorization. `deletion_locked` filings are refused.
2. `delete_from_minio` removes the files and the DB row is deleted. For a `T` identifier the bootstrap is also deregistered.
3. Cancelling payment calls DELETE on the payment service, then `reset_filing_to_draft()`.

### 5. Download a filing or business document
1. `validate_document_request` (**Validation entry points**) checks legal type, status and good standing.
2. The manifest builder (**Legal API: filings, fees, documents…**) lists documents by status. `Report.get_pdf` (**Reports and PDF generation**) fetches static types from Minio, or POSTs template and data to `REPORT_SVC_URL`. `BusinessDocument` does the same for summary and seal.
3. `PdfService.stamp_pdf` adds the registrar certification.
4. Furnishing letters use `ReportV2` through Gotenberg. `FurnishingDocumentsService` merges batches with a cover.

### 6. Colin sync
1. The Colin service calls `/internal/filings` (**Business filings, tasks…**). It lists completed filings, enriched with `learEffectiveDate`, and skips `lear_epoch`.
2. It PATCHes `colinIds` back.

### 7. BN move
1. `/bnmove` (**app factory, config, and REST resources**) updates `tax_id` and creates a completed `registrarsNotation` filing.
2. It publishes `bc.registry.bnmove` to the emailer subject and `bc.registry.business.bn` to the entity-event subject.

## Other parts
- **legal-api HTTP resource layer: routing, versioning and small endpoints**: mounts v1 namespaces and v2 blueprints, negotiates `Accept-Version` and handles CORS and the comments, directors and share-class endpoints.
- **Validation entry points…**: `comments` validate runs schema (422), then business rules (400).
- **Legal API: service layer…**: `requires_traction_auth`, `can_access_digital_credentials`, `authz`, and the COLIN and NAICS clients.
- **legal-api core, errors…**: `BusinessException` and `Error` handlers, and `Flags` (LaunchDarkly).
- Tasks, involuntary-dissolution eligibility, digital-credential endpoints and `get_warnings` live in their respective parts above.

## Hazards
- **Partial saves and split commits:** `save_filing` errors in POST/PUT are caught and printed, so a filing can be half-saved. Payment cancel, `reset_filing_to_draft` and review updates are separate commits, and a failure between them leaves the records out of sync.
- **Silent failure:** `publish_event`, `Flags.is_on`, `ReportV2` and batch merging swallow errors. Events, feature flags and furnishing letters can disappear with no signal. `/bnmove` returns 200 on failure.
- **Cross-record access:** Alias, Resolution and ShareClass lookups ignore the business in the path, and the `date` parsing in the directors endpoints likely raises.

# area-flows (sample 2)

# legal-api: filings, validation, reports and external integrations

The BC Registries legal-api is a Flask service that exposes REST endpoints (v1 namespaces, v2 blueprints) for business filings and business data. It validates filings, computes fees and documents, renders PDFs, and wraps external services. It takes work from the UI, JWT clients, the Colin service and cron jobs. It hands work to Postgres models, the payment service, the NATS emailer/filer/entity-event subjects, Minio, namex, Colin, MRAS, the Account/Auth APIs, Traction and the report/Gotenberg services.

## Flows

### Submit or update a filing
1. **Resource layer** (`resources/v2/business/business_filings/business_filings.py`; v1 is the older copy) receives POST/PUT. The `resources/endpoints.py` hook has already negotiated the API version.
2. **Authorization** (`services/authz.py`, `decorators.py`) checks `edit` and `is_allowed()`, which requires DRAFT or CHANGE_REQUESTED.
3. **Filing validation, effective-date handling and business warnings** runs `validate(business, filing_json, account_id)`, unless the request is `draft=true`, historical or pre-epoch. Failures, or `only_validate=true`, return before saving. Schema errors give 422 and rule errors give 400.
4. `save` creates or updates the `Filing` model, and `set_effective_date` sets the future-effective date. A new-business filing past NR expiry calls `namex.update_nr_as_future_effective`.
5. `_get_filing_types` derives fee codes, and `create_invoice` POSTs to the payment service. It saves `payment_token` and the payment status, and the model listener moves the filing to PENDING and then PAID.
6. `complete_filing` publishes to the filer queue. A COLIN-source filing goes to `process_colin_filing`, which either publishes or, for pre-epoch filings, adopts the epoch transaction and calls `set_processed`, which leads to COMPLETED.
7. A filing in CHANGE_REQUESTED is resubmitted: `Review` becomes RESUBMITTED and `resubmit_filing_to_awaiting_review` runs.

### Staff review
1. `POST /reviews/{id}` (`resources/v2/admin/reviews.py`) accepts a decision only from AWAITING_REVIEW or RESUBMITTED.
2. It writes a `ReviewResult` and calls `set_review_decision()`, which sets CHANGE_REQUESTED, APPROVED or REJECTED.
3. It publishes to the emailer subject, and to the filer subject once an APPROVED filing's effective date has passed.

### Create a new business
1. `v2/business/business.py` checks the type is in `NEW_BUSINESS_FILING_TYPES`.
2. **Legal API: service layer and decorators** (`bootstrap.py`) runs `create_bootstrap` (a temp `T…` identifier) and `register_bootstrap`, which calls `AccountService.create_affiliation` and rolls back with `delete_affiliation` on failure.
3. `saving_filings` saves the filing. A failure gives 503.

### Cancel payment or delete a draft
1. Cancel: DELETE to the payment service, then `reset_filing_to_draft()`.
2. Delete: blocked when `locked`. Otherwise `delete_from_minio` runs and the row is removed. For `T` identifiers the bootstrap is also deregistered.

### Read filings, ledger and documents
1. GET goes to `ListFilingResource.get_single_filing` or `get_ledger_listing`.
2. `core/filing.py` `get_json` picks raw or versioned JSON by status, and redaction hides staff submitters.
3. The document manifest is built from `FilingMeta.get_all_outputs`.
4. **Reports and PDF generation** renders on request: `Report.get_pdf` for filings, `BusinessDocument` for summary and seal, and `ReportV2` and `FurnishingDocumentsService` for furnishing letters.

### Colin sync
1. Colin service and cron jobs call `v2/business/colin_sync.py` GET, which lists completed filings.
2. They PATCH `colinIds` back, and `ColinLastUpdate` tracks the last event.

### Business-number move
1. `/bnmove` (`v2/internal_services.py`, system role) updates `tax_id`.
2. `create_registrars_notation_filing()` creates a completed registrar's notation filing.
3. `publish_event` sends the BN events to the emailer and entity-event subjects.

## Other parts
- **Validation entry points for filings, comments, documents and business warnings**: package exports for `validate`, `validate_document_request`, `check_warnings`, plus the comment validators.
- **legal-api HTTP resource layer**: mounts the v1 namespaces and v2 blueprints. It also holds comments, directors and share-class reads.
- **legal-api: app factory, config, and REST resources**: `create_app`, the address/party/alias reads, admin configuration, request tracker, digital-credential endpoints, ops and MRAS.
- **legal-api core, errors, and filing REST endpoints**: `BusinessException`, `Error`, the error handlers and `Flags` (LaunchDarkly).
- **legal-api: models, core helpers and a few resources/services**: `Business`, `Filing` and the other models, the involuntary-dissolution eligibility service, and versioned lookups.

## Hazards
1. **Partial saves and split commits.** Exceptions in `save_filing` are caught and printed, so a filing can be half-saved with no error. Review, filing and payment-cancel updates commit separately. Bootstrap, affiliation and Traction rollbacks can leave orphans.
2. **Silent failure.** `Flags.is_on` returns False on any error. `publish_event` swallows exceptions, `ReportV2` and the furnishing merge return None, and Traction and NAICS calls return None. Features turn off, events are lost and letters go missing with no signal.
3. **Cross-business and unchecked lookups.** `ShareClass`, `Alias` and `Resolution` are fetched by ID without a business-ownership check. Missing filings raise IndexError or AttributeError in reports, and the `datetime.utcnow().strptime` date parsing in the directors endpoints likely fails.

# area-map (sample 1)

# legal-api guide

This area is the BC Registries legal-api Flask service. It exposes REST endpoints for businesses and their filings, validates and prices filings, renders PDF reports, and wraps external services. It hands work to the payment service, namex, Colin, Minio, the Account/Auth APIs, Traction, MRAS, Gotenberg, the report service and the NATS queue.

## Parts

- **Legal API: app factory, config, and REST resources (v1/v2)**: builds the app and serves the read endpoints for addresses, directors, parties and share classes. Also covers the admin, internal and ops endpoints. Answers: how the app starts, how BN move and request-tracker events are published, how digital-credential connections behave, who may call internal routes.
- **legal-api HTTP resource layer: routing, versioning and small endpoints**: mounts the v1 namespaces and v2 blueprints and negotiates versions. Answers: where a route is mounted, how `Accept-Version` redirects work, how comments, directors and share classes are served, how CORS preflight works.
- **Business filings, tasks, comments, documents and Colin sync**: the resources that create, update and delete filings, tasks, comments and documents. Answers: how a filing is saved, paid for, resubmitted or deleted, how to-dos are built, how completed filings sync to Colin.
- **legal-api core, errors, and filing REST endpoints**: shared plumbing: `Filing`, error handling, feature flags and the v2 filing endpoints. Answers: how a v2 filing request flows, how errors become JSON, how flags are evaluated.
- **Filing validation, effective-date handling and business warnings**: the pre-submission validators and the business-warning checks. Answers: why a filing is rejected, what rules a filing type has, how future-effective dates are set, how warnings are produced.
- **Validation entry points for filings, comments, documents and business warnings**: the package exports that resources call, plus the comment and filing schema validators. Answers: where `validate`, `check_warnings` and `validate_document_request` live, and how schema errors (422) differ from rule errors (400).
- **Legal API: filings, fees, documents, reports and authorization**: fee-code derivation, the document manifest, the ledger, redaction, versioned history and which filings a user may start. Answers: what fee code applies, which documents are downloadable, why a filing is blocked.
- **legal-api: models, core helpers and a few resources/services**: the SQLAlchemy models, status rules, the review workflow and involuntary-dissolution eligibility. Answers: how filing status changes, how staff reviews work, how identifiers are validated, who is eligible for dissolution.
- **Legal API: service layer and decorators for external integrations**: access gates and clients for the Account/Auth APIs, Traction, NameX, COLIN and NAICS. Answers: how bootstrap affiliations are made, how a name request is validated, how credentials are issued.
- **Reports and PDF generation**: renders filing, business-document and furnishing PDFs and stamps registrar certification. Answers: how a PDF is produced, which template applies, how dissolution letter batches are merged.

## Cross-part flows

- **Filing submission**: Business filings, tasks, comments, documents and Colin sync, then Filing validation, effective-date handling and business warnings (it uses the Validation entry points), then Legal API: filings, fees, documents, reports and authorization (fee codes), then the payment service (the `payment_token` returns to the filing). Models persist the result.
- **New business**: Business filings, tasks, comments, documents and Colin sync, then Legal API: service layer and decorators (a bootstrap identifier and an affiliation), then NameX validation.
- **Review**: legal-api: models, core helpers and a few resources/services publishes status to the emailer and filer queues.
- **Report download**: a resource, then Reports and PDF generation, with filing and history data from Legal API: filings, fees, documents, reports and authorization.
- **Colin sync**: the Colin sync endpoints read completed filings and write back `colinIds`.
- **Errors and flags**: legal-api core, errors, and filing REST endpoints supplies both to all resource parts.

# area-map (sample 2)

# legal-api guide

This area is the BC Registries legal-api Flask service. It builds the app, serves the v1 and v2 REST surface for businesses and filings, validates and stores filings, and renders PDFs. It calls out to payment, namex, COLIN, Account/Auth, Traction, MRAS, Minio, Gotenberg and the report service. It publishes events to NATS for the emailer, filer and entity-event subjects.

## Parts

- **legal-api: app factory, config, and REST resources (v1/v2)**: app creation, `publish_event`, read endpoints for business data, admin, internal and BN-move endpoints. Open it for how events are published, how BN moves work, or how digital-credential connections behave.
- **legal-api HTTP resource layer: routing, versioning and small endpoints**: mount points, `Accept-Version` negotiation and redirects, CORS, plus comments, directors and share-class routes. Open it for where an endpoint is mounted and how v1 and v2 are routed.
- **Business filings, tasks, comments, documents and Colin sync (legal-api REST layer)**: filing save, invoice, cancel, resubmit and delete flows, tasks, documents, Colin sync and tax IDs. Open it for how a filing is paid, deleted or synced to Colin.
- **legal-api core, errors, and filing REST endpoints**: v2 filing GET/POST/PUT/DELETE gating, error classes and handlers, and feature flags. Open it for how errors become JSON or why a flag reads off.
- **Filing validation, effective-date handling and business warnings (legal-api)**: per-filing-type validators, effective-date rules and business warning checks. Open it for why a filing is rejected or which warning code applies.
- **Validation entry points for filings, comments, documents and business warnings (legal-api services)**: the public validator exports, plus comment and filing schema validation. Open it for where each `validate` lives and what error shape it returns (422 or 400).
- **legal-api: models, core helpers and a few resources/services (BC business registry)**: the models, filing status rules, the review workflow and involuntary-dissolution eligibility. Open it for how filing status is set, how reviews are decided, or who is eligible for dissolution.
- **Legal API: filings, fees, documents, reports and authorization**: fee-code derivation, the document manifest, the ledger, redaction, versioned history and which filings a user may start. Open it for fee codes, allowed filings and blockers.
- **Legal API: service layer and decorators for external integrations**: wrappers for Account/Auth, Traction, NameX, COLIN and NAICS, plus access decorators and bootstrap affiliation. Open it for name request validation, affiliations or credential issuance.
- **Reports and PDF generation (legal-api)**: PDF and JSON rendering for filings, summary and seal documents, and furnishing letters, plus registrar stamping. Open it for how a PDF is produced or stamped.

## Cross-part flows

- **Filing submission:** Business filings, tasks, comments, documents and Colin sync, or legal-api core, errors, and filing REST endpoints → Validation entry points → Filing validation, effective-date handling and business warnings (filing JSON in, `Error` or `None` out) → Legal API: service layer and decorators (name request and affiliation checks) → Legal API: filings, fees, documents, reports and authorization (fee codes) → payment service (`payment_token` saved on the filing) → legal-api: models, core helpers (status set).
- **Review:** legal-api: models, core helpers (`POST /reviews`) → NATS emailer and filer subjects → the Business filings part (resubmit).
- **Colin sync:** Business filings, tasks, comments, documents and Colin sync → legal-api: models, core helpers (epoch handling) → the queue.
- **Document download:** Business filings, tasks, comments, documents and Colin sync (documents) → Legal API: filings, fees, documents, reports and authorization (manifest) → Reports and PDF generation (PDF bytes).
- **BN move:** legal-api: app factory, config, and REST resources → models (tax_id and registrar's notation filing) → NATS events.
- **Routing:** legal-api HTTP resource layer: routing, versioning and small endpoints → whichever resource part owns the route.
