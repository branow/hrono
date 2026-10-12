=== Reports and PDF generation (legal-api) ===

# Reports and PDF generation (legal-api)

Renders PDF and JSON documents for business filings, business documents (summary, seal) and furnishing (dissolution) letters, and stamps registrar certification onto PDFs. It reads filings and business data from the models, templates from `REPORT_TEMPLATE_PATH`, and static documents from MinIO. It hands rendering to external services: a report service (`REPORT_SVC_URL`) and Gotenberg/Chromium (`REPORT_API_GOTENBERG_URL`).

## Contract
- `reports.get_pdf(filing, report_type=None)` delegates to `Report`. On `FileNotFoundError` (no template) it returns 404 `{'message': 'Available on paper only.'}`.
- `Report.get_pdf()` takes a filing and returns a PDF HTTP response. It gets the data from `filing.filing_json['filing']`. It POSTs base64 template and data to `REPORT_SVC_URL`.
- `BusinessDocument` takes a business and a `document_key` ('lseal', 'summary', ...). It returns PDF bytes via the same report service, or a JSON object plus status. The JSON has a trimmed registrar (name, title, startDate, endDate) and a report datetime.
- `ReportV2` takes business, furnishing, `document_key` (DISSOLUTION or DISSOLUTION_COVER) and a variant. It POSTs HTML to Gotenberg `/forms/chromium/convert/html` with a Google ID token. It returns PDF bytes or None.
- `FurnishingDocumentsService` takes one or many `Furnishing` and returns PDF bytes. For batches it returns a merged PDF with a cover page.
- `PdfService` takes `RegistrarStampData` (certify_date, identifier, file_name, is_correction) and returns a BytesIO watermark/stamped PDF.
- `RegistrarInfo.get_registrar_info(date)` returns the registrar dict with base64 signature data URLs.

## Decisions
- `Report.get_pdf`: a type in `ReportMeta.static_reports` (certifiedRules, certifiedMemorandum, affidavit, uploadedCourtOrder) is fetched from MinIO with `MinioService.get_file()`. Anything else is rendered.
- `Report.get_pdf`: key 'alteration' becomes 'alterationNotice'.
- `Report.get_pdf`: noticeOfArticles, amendedRegistrationStatement and correctedRegistrationStatement use `VersionedBusinessDetailsService.get_company_details_revision()`. Other types use the filing JSON.
- `ReportMeta.reports`: if `hasDifferentTemplates`, the template is chosen by `business.legal_type` (default, CP, SP or GP), with a 'default' fallback. Otherwise `fileName` is used.
- `Report.get_pdf`: a non-200 response from the report service returns an error message.
- `BusinessDocument`: addresses and state changes are added for 'lseal' and 'summary'. Parties, translations and amalgamation/liquidation/continuation details are added for 'summary' only. The registration date is added for SP/GP.
- `ReportV2`: variant 'default' uses `HEADER_PATH`/`FOOTER_PATH`. Any other variant uses the mail header and footer.
- `ReportV2`: foreign registrations come from `MrasService.get_jurisdictions()`, except for EXTRA_PRO_A.
- `ReportV2`: a Canadian postal code gets a space inserted after position 3.
- `ReportV2`: the last AR date falls back to the founding date. The processed date falls back to now.
- Furnishing batch: the cover gets letterCount, pageCount (letterCount×2+1) and customBatchId from the `batch_custom_identifier` sequence. PyPDF2 merges the cover with the letters.
- `PdfService.stamp_pdf`: stamps the first page only if `only_first_page`, else all pages. `create_registrars_stamp` adds "(Corrected)" and the file name conditionally.
- `RegistrarInfo`: picks the registrar whose startDate ≤ filing date ≤ endDate (endDate may be None).

## Hazards
- `RegistrarInfo` raises IndexError if no registrar covers the date, which breaks reports for dates before 1970.
- Failures are silent. `ReportV2.get_pdf` returns None on a non-200 response or a render exception. `_merge_documents` returns None on error. In a batch, a furnishing whose PDF fails is skipped, so letters go missing without notice. Cover failure is logged but also returns None.
- Template parts are substituted by plain `str.replace` of `[[name.html]]`. This is one level deep, and the `BusinessDocument` parts list is hardcoded and must match the files on disk.

## Open first
- `reports/report.py`: `Report.get_pdf`, template selection, and the `ReportMeta` filing-to-template maps.
- `reports/business_document.py`: summary and seal generation.
- `reports/report_v2.py`: Gotenberg dissolution and cover rendering.
- `services/furnishing_documents_service.py`: batch merge and cover.

Related files: `registrar_meta.py` holds the registrar list and signatures. `pdf_service.py` has the stamp. `test_pdf_service.py` checks that the stamp lands on page 1 only.

=== Legal API: service layer and decorators for external integrations ===

# Legal API: service layer and decorators for external integrations

Flask code in legal-api that gates access (decorators, `authz`) and wraps external services: Account/Auth API, Traction (ACA-Py), NameX, COLIN, NAICS. It calls those services over HTTP and hands results to the resource endpoints.

## Contract
- **Account API** (`AccountService`): token via POST of client credentials. Entities go to `/entities`. Affiliations go to `/orgs/{account}/affiliations`. `get_account_by_affiliated_identifier` queries `/orgs?affiliation=`.
- **Auth API** (`authz._call_auth_api`): GET `entities/{identifier}/authorizations` with a Bearer token. It retries on 500/502/503/504 (5 attempts) and returns a Response, or None on error.
- **Traction**: `/out-of-band/create-invitation`, `/issue-credential-2.0/send`, `/issue-credential-2.0/records/{id}`, `/revocation/revoke`, `/connections/{id}` (DELETE), `/multitenancy/tenant/{id}/token`. All methods return `response.json()` or None.
- **NameX** (`services/namex.py`): `query_nr_number(s)` proxies to NAMEX_SVC_URL. `update_nr` PUTs `/requests/{nrNumber}` with a separately fetched client-credentials token.
- **COLIN**: GET `{COLIN_URL}/api/v1/businesses/{identifier}/public`.
- **NAICS**: GET on NAICS_API_URL, JSON or None.
- **Credential data**: `get_digital_credential_data` returns 10 name/value attribute dicts.
- **Endpoints**: `resources/v1/namerequest.py` proxies `/NameRequest/{identifier}`. `nr_type_map.py` declares the `nrTypeMap` namespace and `RequestActions`, which must match namex's RequestAction.

## Decisions
- `requires_traction_auth` (decorators.py): raises EnvironmentError if any TRACTION_* config is missing. It reuses `current_app.api_token` unless the token is missing or its `exp` has passed, then POSTs for a new one.
- `can_access_digital_credentials`: Business not found returns 404. `are_digital_credentials_allowed(business, jwt)` false returns 401.
- `authz` (user-action check): missing input is rejected. STAFF/SYSTEM/COLIN_SVC roles are allowed. ACCOUNT_IDENTITY or CA_SEARCH products get view-only access. BASIC/PUBLIC users are refused `add_comment`, and every action must appear in the auth API roles (case-insensitive).
- `namerequest`: NameX 404 returns a custom "{id} not found." message; any other response passes through; an exception aborts with 500.
- `validate_nr`: the 'disable-nr-check' flag returns all-true. APPROVED is consumable. CONDITIONAL needs consent, and consentFlag 'R' makes it consumable. consentFlag 'N' or empty waives consent and is consumable. EXPIRED sets is_expired.
- `get_approved_name` picks the name in state APPROVED or CONDITION. `has_correction_changed_name` compares the correctedFilingId paths for nrNumber and legalName. `update_nr_as_future_effective` converts the date to GMT and adds a 1-day buffer.
- Bootstrap (bootstrap.py):
  - `create_bootstrap` generates a temp identifier ('T' plus 9 characters, at least one digit) and retries 5 times on FlushError.
  - `register_bootstrap` calls `create_affiliation`; on failure it calls `delete_affiliation` and returns an error.
  - `delete_bootstrap` suppresses all errors.
- `AccountService.create_affiliation`: no token returns 401; either POST not returning 201 returns 400.
- `update_entity` PATCHes `/entities/{id}`; a non-200 response returns 400.
- `delete_affiliation` deletes the affiliation and then the entity; it returns 400 unless the affiliation call returns 200 and the entity call returns 200 or 204.
- Digital credentials:
  - `init_app` calls `_register_business_definition`. It needs BUSINESS_SCHEMA_ID and BUSINESS_CRED_DEF_ID, fetches both from Traction, and creates a DCDefinition unless a non-deleted one exists.
  - `get_digital_credential_data` handles only the business credential type. It finds or creates a DCIssuedBusinessUserCredential, and its zero-padded id becomes credential_id.
  - `extract_invitation_message_id` reads `invitation.@id`, falling back to `invitation_msg_id`.

## Hazards
- **Swallowed failures**: `suppress(Exception)` in `init_app` hides `_register_business_definition` errors, and the Traction delete methods and NAICS return None for every failure.
- **Orphans and missing checks**: `create_affiliation` leaves an orphaned entity or affiliation if one POST fails. `delete_affiliation` ignores a null token. Rollback errors in `register_bootstrap` are suppressed.
- **Wrong-looking checks**: `register_bootstrap` tests that the bootstrap object exists, not the account, when it reports the missing account number. `colin.py` returns the raw response with no status check. Only the first party role is used in credentials.

## Open first
- `services/digital_credentials.py`: Traction issuance, revocation and connection flow, plus definition registration.
- `services/account.py` (AccountService, in the bootstrap notes): token, entity and affiliation calls.
- `services/namex.py`: NR validation and NameX proxying.
- `services/authz.py` and `decorators.py`: access gates.

=== Filing validation, effective-date handling and business warnings (legal-api) ===

# Filing validation, effective-date handling and business warnings (legal-api)

Most of this part is the pre-submission validation layer for business filings in legal-api. It also holds the business-warning checks, the datetime helpers and a Colin event tracking model. Validators take a `Business` and the filing JSON. They return `None` when valid, or an `Error(HTTPStatus.BAD_REQUEST, [{'error', 'path'}])`. They are called from the filings resource and delegate to `Filing.FILINGS`, namex, Colin, Minio and AccountService where needed.

## Contract
- **Entry point:** `validation.py::validate(business, filing_json, account_id)` schema-validates the JSON, then dispatches by filing key through `Filing.FILINGS`.
- **Routing exceptions in `validate`:**
  - A `correction` key runs only `correction_validate`. Other filing keys in the same submission are skipped.
  - A COOP dissolution that isn't administrative must also carry `specialResolution`, else the error is at `/filing/specialResolution`.
  - A COOP `specialResolution` must come with `changeOfName` or `alteration`, else the error is at `/filing`.
- **Warnings:** `warning.py` collects `check_business(business)` results into a list. `business_checks/business.py` routes by legal type to `firms_check` (sole prop, partnership) or `corps_check` (corps). It adds `involuntary_dissolution_check` for `InvoluntaryDissolutionService.ELIGIBLE_TYPES`.
- **Warning format:** Each warning is `{code, message}` merged with `WARNING_MESSAGE_BASE`. The enums are in `business_checks/__init__.py`. `get_address_business_warning` maps referer, address type and condition to a code.

## Decisions
- **Shared helpers in `common_validations.py`:**
  - `validate_name_request`: skipped when the disable-nr-check flag is on. It requires `nrNumber` and `legalName` together, except for numbered corps. It checks namex `is_consumable`, the request type, the legal type and the approved name.
  - `validate_foreign_jurisdiction`: checks country and region, with the BC and US region flags.
  - `validate_court_order`: file number length 5–20, `effectOfOrder` null or `planOfArrangement`, order date not in the future.
  - `validate_pdf`: letter-size pages, at most 30MB, unencrypted.
  - `validate_party_name`: first and middle names capped at 20 characters, a COLIN sync workaround.
  - Share structure rules.
- **`incorporation_application.py`:** The effective date must be 2 minutes to 10 days ahead. COOP needs 3 directors and no incorporators. Other types need 1 incorporator plus the `min_director_count_info` directors. Exactly 1 completing party is required, except 0 for staff corrections.
- **`amalgamation_application.py`:**
  - `_validate_lear_businesses` rejects a business that is historical, has draft/pending/paid filings, or is in a future-effective amalgamation. For non-staff it also requires affiliation and good standing.
  - `_validate_foreign_businesses` blocks foreign corporations for non-staff.
  - `_validate_amalgamation_type` applies role counts for regular, horizontal and vertical types.
- **`alteration.py`:** `valid_type_changes` limits legal type transitions. `accepted_request_types` limits name request types.
- **`correction.py`:** The corrected filing must be COMPLETED or CORRECTED and belong to the business. Validators are routed by legal type. `validate_start_date` allows 90 days forward for everyone and 10 years back for staff only.
- **Other validators:**
  - `restoration.py`: limited-restoration expiry must be 1–24 months ahead. Court-order approval requires a court order.
  - `continuation_in.py`: validates through the Colin API. It requires 1 completing party and checks director minimums per type.
  - `consent_continuation_out.py`: the business must be active and in good standing. `get_active_cco` blocks a duplicate unexpired consent for the same jurisdiction.
  - `continuation_out.py`: `validate_active_cco` requires the continuation-out date to be on or after the consent's effective date.
  - `agm_extension.py`: `_calculate_granted_ext` computes extension months. The first-AGM limit is the founding date + 18 months + 5 days.
  - `annual_report.py`: `requires_agm` is true for COOP and XPRO_LIM_PARTNR. `validate_ar_year` checks the date range.
  - `admin_freeze.py`: rejects a freeze value equal to the current state.
  - `registration.py`, `conversion.py` and `change_of_registration.py` validate firm parties, offices and NAICS.
- **Effective date, `resources/v1/business/business_filings.py`:** `_set_effective_date` sets the future-effective date for incorporation and registration filings. For non-COOP change of address it uses tomorrow at 00:01 Legislation time. `_is_future_effective_filing` checks whether `effectiveDate` is in the future.
- **Colin tracking, `models/colin_update.py`:** `ColinLastUpdate` records the last Colin event ID loaded.

## Hazards
- Some validators raise on missing keys instead of returning errors:
  - `change_of_address` raises `KeyError` on a missing `addressCountry`.
  - `agm_extension` raises `KeyError` on a missing `extReqForAgmYear`.
  - `incorporation_application.validate_parties_mailing_address` divides by zero when there are no mailing addresses.
- Return types are inconsistent:
  - `change_of_directors.validate_effective_date` returns a dict, so `msg +=` fails.
  - `continuation_in` returns a list instead of an `Error` when the legal type is missing.
- Silent passes and mismatches:
  - A missing incorporation `effectiveDate` is accepted.
  - A naive datetime compared with a UTC-aware one raises `TypeError` in `_is_future_effective_filing`.
  - `validate_pdf` turns every exception into a generic "Invalid file".
  - Correction special-resolution paths use `.get('correction', {})` inconsistently.

## Open first
- `validations/validation.py`: dispatch and routing.
- `validations/common_validations.py`: shared name request, court order, PDF, share and foreign-jurisdiction checks.
- `validations/incorporation_application.py` and `validations/amalgamation_application.py`: the largest rule sets.
- `warnings/business/business_checks/firms.py` and `__init__.py`: warning codes.

`services/authz.py` had no usable content in the notes.

=== legal-api core, errors, and filing REST endpoints ===

# legal-api core, errors, and filing REST endpoints

Shared plumbing of the legal-api Flask service: the core domain surface (`Filing`, `FILINGS`/`FilingMeta`), error/exception handling, feature flags, and the v2 REST endpoints for business filings. Business filing endpoints hand work to ListFilingResource (reads), filing validation and save/complete helpers, Minio, the database, and payment/RegistrationBootstrap services. The notes also cover unrelated pieces: Sentry docs and package `__init__` re-exports.

## Contract
- **Filing endpoints** (`resources/v2/business/business_filings/business_filings.py`) take `identifier`, optional `filing_id`, filing JSON and the payment `account-id` header. They return filing JSON or `{'message': ...}` errors.
- **Errors**: `BusinessException(error, status_code)` carries a description plus HTTP code. `Error(code, msg_list)` is a non-exception container, so read `error.msg`. `get_error_message(ErrorCode, **kwargs)` formats a template via `babel`, returns None for an unknown code, and shows missing keys as their names.
- **Handlers** (`errorhandlers.py`) turn exceptions into JSON.
- **Flags** (`services/flags.py`) wrap LaunchDarkly: `Flags.is_on(flag, user)` returns a bool and `value()` returns the variation. `flags.json` is the local fallback.
- `core/constants.py`: `REDACTED_STAFF_SUBMITTER = 'Registry Staff'`, the placeholder used when a filing's submitter is hidden.

## Decisions
- GET: `filing_id or identifier.startswith('T')` calls `ListFilingResource.get_single_filing`, otherwise `get_ledger_listing`.
- POST/PUT validation runs only if `not query.draft and not is_historical_colin_filing and not is_before_epoch_filing`. Errors, or `only_validate=true`, return before saving.
- POST/PUT after save: `filing.in_change_requested_status` resubmits for review with `isPaymentActionRequired: false`. Otherwise `complete_filing` runs, and an early return happens if `response and (response_code != CREATED or filing.source == COLIN)`.
- DELETE needs `filing_id` and an authorization check. A `T`-prefixed identifier means a temp filing, so its RegistrationBootstrap is also deregistered and deleted. `filing.locked` refuses deletion. Deletion removes the Minio object and the DB row.
- `errorhandlers.handle_http_error`: a `RoutingException` passes through unchanged (redirects). Any other HTTPException returns `{'message': description}` with its code.
- `handle_uncaught_error`: logs with `exc_info` (for Sentry) and returns a generic 500.
- `Flags.init_app`: production with `LD_SDK_KEY` uses the cloud client, otherwise a local `FileDataSource`.

## Hazards
- `save_filing` exceptions in the POST/PUT path are caught and printed, then execution continues, so a filing can be partly saved with no error reported.
- If the temp bootstrap deregister/delete fails during DELETE, the filing is already gone and the bootstrap stays orphaned.
- `Flags.is_on` and `value` swallow every exception and return False. They also don't guard against `_get_client()` returning None, so a flag outage silently turns features off.

## Open first
- `resources/v2/business/business_filings/business_filings.py`: filing GET/POST/PUT/DELETE flow, validation gating, resubmit and lock checks.
- `core/filing.py` (with `core/meta`): the `Filing` domain class and `FILINGS` registry. Only the imports are in the notes; the body is not shown.
- `errorhandlers.py` and `exceptions/` (`business_exception.py`, `error_messages/utils.py`): error-to-JSON mapping and message formatting.
- `services/flags.py`: feature-flag lookups.

=== Validation entry points for filings, comments, documents and business warnings (legal-api services) ===

# Validation entry points for filings, comments, documents and business warnings (legal-api services)

Thin package layer in `legal_api.services` that exposes validators and checkers to the API resources. Most of the logic sits in submodules not shown here. Only the comment validators and the filing schema validator have visible code.

## Contract
- `services/business` exports `validate_document_request` (from `.validations.validator`). It validates document requests.
- `services/filings` exports `validate` (from `.validations.validation`). It is the filing verification entry point.
- `services/comments` exports `validate` (from `.validations.validation`).
  - Input: `comment_json` (dict) and `is_filing` (bool).
  - Output: an `Error` object, or `None` if valid.
- `services/warnings` exports `check_warnings` (from `.warning`).
- `services/warnings/business` exports `check_business` (from `business_checks.business`).
- `Error` carries an HTTP status plus a list of error dicts. The status is 422 for schema failures and 400 for business-rule failures.

## Decisions
- `comments.validations.validation.validate` runs two steps in order and stops at the first failure:
  1. `validate_against_schema` (in `schemas.py`). It calls `rsbc_schemas.validate(json, 'comment')` and returns 422 with `[{path, error}]`, where `path` is the error path joined with `/`.
  2. `comment_validate` (in `comment.py`), the business rules.
- `comment.py` `validate`, business rules:
  - An empty comment returns 400 with 'A valid comment is required.'
  - The text at `/comment/comment` is required.
  - `/comment/filingId` is required only when `is_filing=True`.
  - Errors accumulate and are returned together as 400.
- `filings.validations.schemas.validate_against_schema` calls `rsbc_schemas.validate(json, 'filing')`. It builds the error list with `build_schema_error_response()` as `{error:message, path:schemaPath}` and returns 422, or `None` if valid.

## Hazards
- Several docstrings are copy-pasted and wrong, so don't trust them.
  - The comments packages and `validation.py` talk about "filing verification" or "annual report".
  - `comments/validations/schemas.py` says "Filings are legal documents".
  - The filings `schemas.py` docstring claims an `int` return, but it returns `Error` or `None`.
- The two schema validators return differently shaped error dicts: `path`/`error` for comments, `error`/`path` (schemaPath) for filings. Consumers parsing errors must handle both.
- The `filings.validate` implementation and the document, warnings and business-check code are not visible here. Don't assume their rules from the package inits.

## Open first
1. `comments/validations/validation.py`: comment validation flow (schema, then business rules).
2. `comments/validations/comment.py`: comment business rules (required text and `filingId`).
3. `filings/validations/schemas.py`: filing schema validation and the 422 error format.
4. The `__init__.py` files: they show where each public function lives, so follow them to `validations/validator.py`, `filings/validations/validation.py`, `warnings/warning.py` and `business_checks/business`.

=== legal-api: models, core helpers and a few resources/services (BC business registry) ===

# legal-api: models, core helpers and a few resources/services (BC business registry)

This part holds the SQLAlchemy models for businesses, filings, parties, reviews, dissolution batches, digital credentials and NAICS data. It also holds small core and utility helpers, a few v1/v2 resources, and services for versioned lookups and involuntary-dissolution eligibility. Models persist to Postgres through `db` (SQLAlchemy Continuum versioning). Resources hand filings to the payment service and to the NATS emailer and filer subjects.

## Contract
- **Model access:** callers use `save()` (most models commit immediately), `find_by*` lookups, and `json` / `json()` serialization to camelCase dicts. The filing JSON is `filing.header.name` plus one key per registered filing type.
- **`POST /reviews/{id}` (resources/v2/admin/reviews.py):** writes a `ReviewResult` and updates `Review` and `Filing`. Publishes `{filing id, type, status}` to `NATS_EMAILER_SUBJECT`, and to `NATS_FILER_SUBJECT` when the filing is APPROVED and its effective date has passed.
- **`GET /reviews`:** looks up Name Request expiry dates from namex, but only for reviews in CHANGE_REQUESTED, AWAITING_REVIEW or RESUBMITTED.
- **v1 `business_filings.py`:** cancels payment at `PAYMENT_SVC_URL` with a JWT bearer token and creates invoices. It deletes uploaded files from Minio.
- **NAICS (resources/v2/naics.py):** searches by term (≥3 chars), by 6-digit code, or by UUID key.

## Decisions
- **Filing status (models/filing.py):**
  - Status auto-set listener, before insert/update: EPOCH for `lear_epoch`, then COMPLETED (transaction_id), PAID (payment date or COLIN source), PENDING (payment token), else DRAFT. It is skipped for AWAITING_REVIEW, CHANGE_REQUESTED and REJECTED, for APPROVED without a transaction, and when `skip_status_listener` is set.
  - `filing_json` setter: requires a filing type, validates against the schemas once a payment token exists (invalid input clears the token), and sets PENDING.
  - `payment_completion_date` setter: raises FORBIDDEN unless the filing is locked or has both a payment token and filing JSON.
  - `locked` and the delete listener: `locked` is true if deletion_locked, or if a payment token or colin_event_ids exist. The delete listener raises FORBIDDEN for locked filings.
  - `status` getter: a COMPLETED filing whose parent filing is also COMPLETED reads as CORRECTED.
  - `set_processed()`: sets effective_date to payment_completion_date, except for annualReport and changeOfDirectors on CP or BEN.
  - `reset_filing_to_draft()` (called by `patch()`): sets DRAFT and clears the payment token.
- **Review workflow:** `set_review_decision()` accepts only CHANGE_REQUESTED, APPROVED or REJECTED. For APPROVED with a past effective date, it sets effective_date to now. `resubmit_filing_to_awaiting_review()` requires CHANGE_REQUESTED. The review POST accepts a decision only from AWAITING_REVIEW or RESUBMITTED, and requires a comment for CHANGE_REQUESTED and REJECTED.
- **Authorization and checks (v1 `business_filings.py`):**
  - `_check_authorization()` requires the 'edit' action and `is_allowed()`.
  - `_put_basic_checks()` requires header, name and filing.
  - `_create_deletion_locked_response()` blocks alteration drafts for limited and unlimited companies (401).
  - `complete_filing()` routes COLIN-source filings to `_process_colin_filing()`.
- **Business (models/business.py):**
  - The `identifier` setter calls `validate_identifier()` (NR prefix, or `(CP|XCP|BC|C|FM)\d{7}` with a non-zero number) and raises 406 on failure.
  - `good_standing`, `get_ar_dates()` and `in_dissolution` hold the compliance rules.
  - `delete()` persists only when dissolution_date is set.
- **Involuntary dissolution (services/involuntary_dissolution.py):**
  - Eligible types are in `ELIGIBLE_TYPES`; a business must be active and have no freeze.
  - It must be overdue on annual reports (26 months) or on transition filings.
  - `check_business_eligibility()` and `get_businesses_eligible()` apply the exclusions.
  - `_check_feature_flags_filter()` applies the include/exclude account lists.
  - `warnings/.../involuntary_dissolution.py` builds the warnings.
- **Validation listeners:** Party, ShareClass and ShareSeries run before insert/update checks, each bypassable with a `skip_*_listener` flag. `Configuration` validates by name through `validate_value()`. `RegistrationBootstrap` identifiers must start with 'T'.
- **Correction detection (core/filing_helper.py):** `is_special_resolution_correction_by_meta_data` is used by reports. `..._by_filing_json` is used by the filer and emailer.
- **Versioned lookups (services/business_details_version.py):** these exclude deletes (`operation_type != 2`) and check the transaction window.
- **Identifiers (core/business.py):** `BusinessIdentifier.next_identifier()` builds type plus 7-digit zero-padded sequence.

## Hazards
- Review and filing updates, and payment cancellation followed by the draft reset, run as separate commits, so a failure between them leaves them out of sync.
- `is_special_resolution_correction_by_filing_json` raises TypeError when the filing has no `correction` key. `next_identifier()` and `_check_and_update_nr()` fail silently (None, or no error handling).
- `RequestTracker.find_by(is_admin=False)` does not filter. `ReviewResult.json` crashes when reviewer is None. `Address.create_address()` raises IndexError for an unknown country.

## Open first
- `models/filing.py`: status rules, listeners, queries and review transitions.
- `models/business.py`: identifier validation, compliance dates and JSON.
- `resources/v2/admin/reviews.py`: the staff review API and its NATS publishing.
- `services/involuntary_dissolution.py`: the eligibility query.

=== Legal API: filings, fees, documents, reports and authorization ===

# Legal API: filings, fees, documents, reports and authorization

Part of the BC registry legal API. It models filings and their state, derives fee codes and the downloadable-document manifest for each filing, builds PDF report data, and decides which filings a user may start on a business. It reads and writes the filing, business and versioned (history) tables, and calls the payment service and the org/products service.

## Contract
- **Fee/payment:** `_get_filing_types` (v1 `business_filings.py`, v2 `business_filings/business_filings.py`) turns filing JSON into `[{filingTypeCode, priority, waiveFees, futureEffective, filingDescription}]`. `_create_invoice` (v1) POSTs `businessInfo` and `filingInfo` to `PAYMENT_SVC_URL`. It saves `payment_token` and `payment_status_code`, and adds `accountInfo` for staff/system callers.
- **Business search:** `v2/business/business.py` takes a POST with `identifiers` and returns `{businessEntities, draftEntities}`. It requires SYSTEM_ROLE and serves SBC-AUTH.
- **Documents:** `document_meta.py` (V1) returns report objects (type, reportType, filingId, title, filename). The manifest builder returns `{'documents': {name: url}}` or None.
- **Authorization:** `authz.py` returns a boolean, a list of allowed filing objects (name, displayName, feeCode), and links.
- **Reports:** `reports/report.py` and `business_document.py` mutate filing/business dicts for templates. `ReportMap` maps summary/cogs/cstat/lseal to report and template names.
- **History:** `business_details_version.py` rebuilds business, party, office, share and resolution state at a `transaction_id` from versioned tables.

## Decisions
- **Fee codes:**
  - Correction uses `Filing.FILINGS['correction']`.
  - Voluntary dissolution uses the dissolution voluntary code. A coop also gets specialResolution and affidavit codes.
  - Administrative dissolution is hard-coded `NOFEE`.
  - courtOrder, registrarsNotation, registrarsOrder, putBackOn and adminFreeze use a single `code`.
  - changeOfDirectors uses the `free` code unless a director has an action other than nameChanged or addressChanged.
  - Priority is forced False for changeOfDirectors/changeOfAddress under annualReport.
  - `futureEffective` is passed only for incorporationApplication, amalgamationApplication, continuationIn, alteration and voluntary dissolution.
- **Filing JSON by status** (`core/filing.py` `get_json`): raw JSON for early statuses. APPROVED/PAID/PENDING return `tech_correction_json` or raw. COMPLETED returns versioned JSON.
- **Redaction:** `redact_submitter` returns True when the submitter has staff/system roles and the caller lacks staff. The ledger and `Filing.redacted` then show REDACTED_STAFF_SUBMITTER.
- **Ledger:** `_is_display_ledger` hides adminFreeze and involuntary dissolution. A parent filing adds correction links, and court orders go through `_add_ledger_order`.
- **Manifest:** None for PAPER_ONLY, DRAFT or PENDING. PAID and review statuses add legalFilings. COMPLETED/CORRECTED add `FilingMeta.get_all_outputs` plus `alter_outputs`. Some types are excluded from legalFilings (see source).
- **Display names:** `FilingMeta.display_name` (`core/meta/filing.py`) resolves by legal type at the filing's transaction, appends the AR year, and has special cases for correction, admin dissolution and unfreeze.
- **Authz:** `is_allowed` requires DRAFT or CHANGE_REQUESTED status. `get_allowed_filings` picks the role (staff or general) and state, filters by `legalTypes` and `businessRequirement`, then runs `has_blocker`. `business_blocker_check` builds the blockers: DRAFT_PENDING, BUSINESS_FROZEN, NOT_IN_GOOD_STANDING, AMALGAMATING_BUSINESS and IN_DISSOLUTION. HISTORICAL businesses allow only court/registrar actions and restorations. A restoration is blocked by continuationOut or an amalgamating business.
- **Document requests** (`validator.py`): checks legal_types, status and goodStanding for cstat/cogs/lseal. All failures are returned together.
- **Versioning:** versioned queries take `transaction_id <=` target, drop `operation_type == 2`, and keep rows with `end_transaction_id` None or greater than the target. Reports use this snapshot when `filing.transaction_id` is set, otherwise current rows.
- **Corrections and change-of-registration reports:** compare against `get_previous_completed_filing` plus the business revision. They flag name, address and party changes, and build `newParties` and `ceasedParties`.

## Hazards
- Unvalidated lookups raise or fail silently:
  - Missing filings or jurisdictions raise IndexError/AttributeError (`_set_continuation_in_details`, `Filing.find_by_id(parent).json`).
  - AGM extension duration outside 1-6 raises IndexError.
  - `suppress(KeyError)` hides missing address and party data in reports.
  - A document type with no rules passes validation.
- Several functions mutate shared objects:
  - `get_most_recent_filing_json` edits the storage JSON in place.
  - `business_revision_json` edits its input dict in place.
  - Correction revisions replace party and role IDs with synthetic values.
  - New share class IDs are deleted before output.
- `pycountry.search_fuzzy` can pick the wrong country or raise on unknown names. `are_digital_credentials_allowed` decodes the JWT without verifying the signature. The core `Filing.save()` writes only some fields.

## Open first
- `services/authz.py`: filing eligibility config, blocker logic, role mapping.
- `resources/v2/business/business_filings/business_filings.py`: fee-code derivation (v1 is the older copy).
- `core/filing.py` and `core/meta/filing.py`: filing state/JSON, display names, output alteration. `models/filing.py` holds the `FILINGS` fee/code map.
- `reports/report.py`: per-type report formatting and change detection.

Unrelated: `scripts/manual_db_scripts/2022_jan_31_add_ar_filing_year_to_meta_data.sql` is a one-off manual migration. It backfills `annualReportFilingYear` into AR filing metadata. It requires a manual COMMIT or ROLLBACK after its verification query returns zero rows.

=== Business filings, tasks, comments, documents and Colin sync (legal-api REST layer) ===

# Business filings, tasks, comments, documents and Colin sync (legal-api REST layer)

Flask resources (v1 and v2) that read, create, update and delete business filings and their comments, documents and pending tasks. They also expose internal endpoints for syncing completed filings to Colin. They call the payment service (`PAYMENT_SVC_URL`), namex (name requests), the filing queue, Minio storage, and the `Business`, `Filing`, `Comment`, `ColinEventId` and `RegistrationBootstrap` models.

## Contract
- **Callers:** the UI and JWT clients use `/<identifier>/filings|tasks|comments|documents`. The Colin service and cron jobs use `/internal/filings`, `/internal/filings/colin_id` and `/internal/tax_ids`, which need `COLIN_SVC_ROLE` or `UserRoles.colin`.
- **Temp registrations:** identifiers starting `T` are looked up through `Filing.temp_reg` / `get_temp_reg_filing`, or `RegistrationBootstrap`, instead of `Business`.
- **Filing JSON:** it carries `header` (`name`, `accountId`, `source`, `date`, `effectiveDate`, `colinIds`) and `filing.<type>`.
- **Payment:** `POST PAYMENT_SVC_URL` returns a `payment_token` that is saved on the filing. `GET` adds `isPaymentActionRequired` and `paymentMethod`. `DELETE /{payment_token}` cancels. `POST /{token}/receipts` produces a receipt PDF.
- **Colin sync GET:** `{filings:[...], page, limit, pages, total}`, each filing enriched with `filingId`, `learEffectiveDate` and business data. `PATCH` takes `{colinIds:[...]}`.
- **Documents:** Minio keys are a UUID plus the file extension. Signed PUT URLs last 5 minutes and GET URLs 1 hour.

## Decisions
- **Save:** `_save_filing` / save in v2 `business_filings` creates or updates a Filing. COLIN source keeps the header date and appends `ColinEventId`s. Otherwise `filing_date` is utcnow. `effective_date` comes from the header or utcnow. Resolution HTML is sanitized.
- **Colin completion:** `process_colin_filing` / `_process_colin_filing` uses `is_before_epoch_filing`. If the filing precedes the epoch, it adopts the epoch `transaction_id` and calls `set_processed`. Otherwise it publishes to the queue.
- **PUT flags:** `draft=true` skips validation and completion. `only_validate=true` returns the validation result only.
- **Invoice:** `create_invoice` returns 201 and saves the payment fields on 200/201. It returns 402 on 400, connection errors or other statuses; only the 400 case saves the error type.
- **Effective date:** `set_effective_date` pushes a non-COOP `changeOfAddress` to tomorrow 00:01. A new-business filing whose effective date is past NR expiry calls `namex.update_nr_as_future_effective`.
- **Cancel payment:** `DELETE` on the payment, then `reset_filing_to_draft()` on 200/202. Needs edit authorization.
- **Resubmit:** the resubmit module sets `Review` to `RESUBMITTED` and calls `resubmit_filing_to_awaiting_review`.
- **Delete:** blocked when `deletion_locked`. Otherwise it deletes Minio files by filing type (`delete_from_minio`) and, for `T` identifiers, the bootstrap.
- **Deletion-lock status:** a draft alteration gives 401. Draft or pending gives 401. Anything else gives 403.
- **Tasks:** `business_tasks` lists filings in DRAFT, PENDING, PENDING_CORRECTION or ERROR. For an NR with no business it adds an incorporate to-do, and returns 403 if the NR is not consumable. A v2 conversion to-do appears when `MISSING_REQUIRED_BUSINESS_INFO` is set. AR to-dos are skipped for SP/GP. v1 enables only the first due AR year.
- **POST business (v2):** `business.py` checks the filing type is in `NEW_BUSINESS_FILING_TYPES`, then calls `create_bootstrap`, `register_bootstrap` and `saving_filings`. A failure returns 503.
- **Colin sync GET:** skips `lear_epoch` and COOP corrections. It adds `correctedColinId` for corrections, handles amalgamation data and adds involuntary-dissolution `meta_data`.
- **Comments:** POST needs `add_comment` (401) and a body `filingId` equal to the URL (400). `staff_id` comes from the JWT. Business-level comments are those with a null `filing_id`.
- **Documents:** `/documents` needs `view`. COOP businesses get `certifiedRules` and `certifiedMemorandum`. Receipts are proxied from the payment service.
- **Minio delete:** `is_draft_filing` allows deletion only for DRAFT filings; otherwise 403.
- **Digital credentials:** revoke uses reason `SELF_REISSUANCE` if `reissue` else `SELF_REVOCATION`. Webhook topics are `connections`, `issuer_cred_rev` and `issue_credential_v2_0`.
- **Tax IDs:** GET lists businesses without a tax ID (not COOP/SP/GP). POST sets tax IDs.

## Hazards
- `POST /internal/filings/colin_id/<id>` builds SQL with an f-string (injection). Its error dict is malformed.
- Broad `except` in `process_colin_filing` and PUT, plus swallowed payment errors, hide failures. Queue publish failures give a generic message. v1 and v2 POST comment handlers can return 201 on a `BusinessException`. `POST /tax_ids` returns 201 even when some updates failed.
- Revoking a credential at aca-py and then failing the local save leaves the database inconsistent. Webhook exceptions return 500 and cause retries.

## Open first
- `v2/business/business_filings/business_filings.py` and its sibling modules: the filing save, completion, invoice and resubmit logic.
- `v2/business/colin_sync.py`: the Colin sync endpoints.
- `v2/business/business_tasks.py`: task building.
- `v1/business/business_filings.py`: legacy GET/PUT/DELETE.

=== legal-api HTTP resource layer: routing, versioning and small endpoints ===

# legal-api HTTP resource layer: routing, versioning and small endpoints

Mounts the legal-api REST surface (v1 Flask-RESTX namespaces, v2 Flask blueprints) and routes requests between API versions. It hands work to models (`Business`, `PartyRole`, `ShareClass`, `Comment`, `User`), `MinioService`, and the authorization helpers (`authorized()`, `jwt`). It also holds small shared utilities (CORS preflight, schema-error formatting) and the Babel instance.

## Contract
- Mount points live in `resources/constants.py` (`EndpointEnum`: `/api/v1`, `/api/v2`, `/api/v2/businesses`, `/api/v2/admin`; default is v1).
- v1 (`resources/v1/__init__.py`): `API_BLUEPRINT` (`/api/v1`) mounts the meta, businesses, documents, nameRequests and nrTypeMap namespaces. `OPS_BLUEPRINT` (`/ops`) mounts the ops health namespace. All use an apiKey `Authorization` header.
- v2 (`resources/v2/__init__.py`): `V2Endpoint.init_app` registers ten blueprints (meta, admin, businesses, digital_credentials, document, namerequest, naics, request_tracker, internal, mras). `bp_admin` and the businesses `bp` only declare prefixes; the route modules attach to them.
- Business routes (v1) are keyed by `identifier`:
  - Comments: GET `comments[/<comment_id>]`, POST `{"comment": {"comment": str}}`.
  - Directors: GET `directors[/<director_id>]?date=YYYY-MM-DD`. Returns `directors` or `director`.
  - Share classes: GET `share-classes[/<id>]`. Returns `shareClasses` or `shareClass`.
- `GET /<file_name>/signatures` returns a Minio pre-signed PUT URL.
- `GET /meta/info` returns API, SCHEMAS (and FrameWork in v2) version strings.
- `GET nrTypeMap` takes optional `nrTypeCd`, `entityTypeCd` and `requestActionCd` filters.

## Decisions
- `endpoints.py` before-request hook: an `Accept-Version` of `v1` or `v2` redirects `api.*` to `api_v1.*` or `api_v2.*` via `url_for`. After-request adds API and SCHEMAS version headers.
- Root `/` redirects permanently to v1. The 404/405 handlers send v2 paths and unversioned `/api` paths to v1. OPTIONS returns CORS headers with no redirect.
- `business_comments._basic_checks`: POST without a JSON body gives 400. Unknown business gives 404.
- Comments POST: the `add_comment` action must be authorized (401 otherwise). `validate()` failures give 400. `BusinessException` on save gives its own code (e.g. 409). The `User` is fetched or created from the JWT. Only comments with `filing_id IS NULL` are returned.
- Directors: unknown business gives 404. Not authorized for `view` gives 401. Unknown `director_id` gives 404. Otherwise `PartyRole.get_active_directors(business.id, date)` runs, with the date defaulting to today. COOP (`Business.LegalTypes.COOP`) responses drop `mailingAddress`.
- Share classes: unknown business or class gives 404. Not authorized for `view` gives 401. JWT is required.
- `V2Endpoint.init_app` raises a bare `Exception` if `app` is falsy.
- `util.cors_preflight(methods)` adds an `options` handler returning 200 with CORS headers. `build_schema_error_response` flattens schema errors into `path`, `error` and `context`.

## Hazards
- `business_directors` calls `datetime.utcnow().strptime(...)` for the `date` param. This likely raises `AttributeError` whenever `date` is supplied.
- `ShareClass.find_by_share_class_id` does not check that the class belongs to the queried business. Any viewer can read any share class ID.
- `cors_preflight` always sends `Allow: GET` whatever `methods` is. A requested version with no matching endpoint makes `url_for` fail and the client gets an error.

## Open first
- `resources/endpoints.py`: version negotiation, redirects, error handlers, headers.
- `resources/v1/__init__.py` and `resources/v2/__init__.py`: which namespaces and blueprints exist and where they mount.
- `resources/v1/business/business_comments.py`: the fullest example of the authorize, validate, persist pattern.
- `utils/util.py`: CORS and schema error helpers.

=== legal-api: app factory, config, and REST resources (v1/v2) ===

# legal-api: app factory, config, and REST resources (v1/v2)

Flask app for the BC Registries legal API. It builds the app, then exposes read endpoints for business data (addresses, aliases, directors, parties, resolutions, share classes, filings), plus admin, internal-service and ops endpoints. It hands work to the DB models, the NATS queue (`queue.publish_json`), and the external services namex, colin, MRAS, the Account service and digital credentials.

## Contract
- **App factory:** `create_app(run_mode)` in `__init__.py` loads `CONFIGURATION[run_mode]` and initializes db, schemas, flags, queue, babel, endpoints, cache and digital credentials. It also sets up Sentry and the JWT role callback.
- **Events out:** `publish_event` in `services/__init__.py` builds a CloudEvents 1.x-wip payload (type, source `LEGAL_API_BASE_URL/<identifier>`, id, time, identifier, data) and publishes it to a subject.
- **BN admin event:** `publish_entity_event()` in `v2/admin/administrative_bn.py` publishes `bc.registry.admin.bn` (header `request` defaults to `BN15`) to `NATS_ENTITY_EVENT_SUBJECT`.
- **BN move events:** `/bnmove` publishes `bc.registry.bnmove` (`oldBn`/`newBn`) to the emailer subject and `bc.registry.business.bn` to the entity-event subject.
- **Auth:** JWT via `jwt.requires_auth`. Business read routes call `authorized(identifier, jwt, action=['view'])`; admin and internal routes check `UserRoles` or `COLIN_SVC_ROLE`.

## Decisions
- Business-scoped GETs (all v2 business modules): `Business.find_by_identifier` returns 404 if the business is missing. `authorized()` returns 401 if denied.
- Addresses (`business_address.py`, v1 and v2): an invalid `addressType` returns 400. With no filters, it uses `business.offices` keyed by office type. If there are no offices, it falls back to the mailing/delivery addresses; if neither exists, 404.
- Directors and parties: `PartyRole.get_active_directors` / `get_party_roles` filter by `date` (default today). `all=true` on parties drops the date filter.
- Furnishing documents (`furnishing_documents.py`): returns 404 for a missing furnishing, one from another business, or a GAZETTE type. A variant outside default/greyscale returns 400. A PDF is served only when Accept includes `application/pdf`; a failed render returns 500.
- Namerequest (`namerequest.py`): returns the NR if the account is affiliated. Otherwise it requires an email or phone that matches the applicant (403 if neither is given, 400 on mismatch).
- Digital credentials (`business_digital_credentials.py`): an active connection returns 409 on a new invitation. A pending 'invitation' state is reused. Deleting a non-invitation connection first calls `remove_connection_record()`. Issuing a credential fails if an exchange is already pending.
- Configurations (`admin/configuration.py`): `validate_configurations()` chains the checks (non-empty, no duplicates, names exist, data types, `NUM_DISSOLUTIONS_ALLOWED` ≤ `MAX_DISSOLUTIONS_ALLOWED`). A `ValueError` rolls back.
- BN admin (`administrative_bn.py`): `create_bn_request()` needs an `admin_edit` or `bn_edit` role. It returns 400 if the business is unknown, otherwise 201.
- Request tracker (`request_tracker.py`): POST creates a `RequestTracker` (`retry_number=-1`, `is_admin=True`, BN_HUB) and publishes `RESUBMIT_<type>`. GET hides `GET_BN` entries.
- Internal v1 (`v1/business/internal_services.py`): `COLIN_SVC_ROLE` only. GET lists identifiers whose `tax_id` is null; POST sets `tax_id` per identifier.
- Internal v2 (`v2/internal_services.py`): `/bnmove` needs `UserRoles.system` and returns 400 if `oldBn`/`newBn` is missing. It updates `tax_id`, creates a completed `registrarsNotation` filing via `create_registrars_notation_filing()`, then publishes the events. `/filings/future_effective` lists future-effective filing IDs.
- Other endpoints: `dissolution.py` (staff) returns the eligible count. `mras.py` (system role) returns 500 if the service returns `None`. `nr_type_map.py` filters mappings, 404 on none. `ops.py` has healthz and readyz.

## Hazards
- **`/bnmove` hides failures:** it returns 200 even when the business is not found or payment fails, and the tax_id update and filing creation are not atomic. v1 internal POST likewise returns 201 for missing businesses.
- **Cross-business reads:** `Alias.find_by_id`, `Resolution.find_by_id` and `ShareClass.find_by_share_class_id` are looked up globally, without checking that the record belongs to the business in the path.
- **Event publishing:** `publish_event` swallows all exceptions (log and Sentry only), so events can be lost silently. `publish_entity_event` re-raises despite its comment.
- Smaller defects: v2 directors calls `datetime.utcnow().strptime()` on a `date` parameter (v2 directors `date` handling), and digital credentials decodes the JWT with `verify_signature=False`.

## Open first
- `services/__init__.py`: `publish_event` and the service singletons.
- `v2/internal_services.py`: BN move and the registrar's notation filing.
- `v2/admin/configuration.py`: validation chain for the admin configuration update.
- `v2/business/business_digital_credentials.py`: connection and credential state handling.
