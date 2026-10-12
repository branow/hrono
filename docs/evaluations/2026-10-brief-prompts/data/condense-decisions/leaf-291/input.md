=== legal-api/src/legal_api/resources/v1/business/business_filings.py ===

REST API resource for retrieving, creating, modifying, and deleting business filings; temporary registrations (identifier starts with 'T') use separate CoreFiling and RegistrationBootstrap data sources.

**GET**: Returns filing(s) as JSON or PDF. Checks authorization. For temp registrations: fetches from CoreFiling; if filing status is PENDING, calls payment service (PAYMENT_SVC_URL) to inject `isPaymentActionRequired` and `paymentMethod` into response; for certain types (amalgamationApplication, incorporationApplication, continuationIn) returns PDF instead. For regular businesses: fetches by ID or lists all COMPLETED and PAID filings. Query param `original=true` returns raw filing; else processes and adds document metadata via DocumentMetaService.

**PUT** (POST delegates to it): Validates and saves filings. Query param `draft=true` skips validation and completion; `only_validate=true` returns validation result only. Unless draft or historical/before-epoch: validates filing against business. Saves filing, calls complete_filing, returns filing JSON. Header `accountId` passed to completion step.

**DELETE**: Removes filing and associated MinIO storage. If identifier starts with 'T': deregisters and deletes RegistrationBootstrap. Blocks deletion if `filing.deletion_locked=true`.

GOTCHA: Payment service call silently logs error but doesn't halt GET response if connection fails. GOTCHA: PUT handler has bare `except Exception` with only `print(err)`, no proper error propagation.

These static helper methods validate, save, and process business filings. `_save_filing` is the primary entry point: takes client request JSON and user, identifies Business or RegistrationBootstrap (identifiers starting 'T'), and creates new or updates existing Filing by filing_id. Sets source from filing['header']['source'] (default: Filing.Source.LEAR.value); if COLIN, parses filing_date from header['date'] and appends ColinEventId objects from header['colinIds'] to colin_event_ids, else sets filing_date to UTC now. Sets effective_date from header['effectiveDate'] or UTC now, then saves. Returns (business or bootstrap, filing, error dict, HTTPStatus). `_validate_filing_json` validates request JSON against rsbc_schemas 'filing' schema. `_process_colin_filing` is post-save: if colin_event_ids exists and filing precedes EPOCH filing, copies transaction_id and calls filing.set_processed(business.legal_type); else publishes filing to queue. Returns success unless colin_event_ids missing or exception occurs. `_get_legal_type` extracts legal_type from filing JSON for incorporationApplication or registration, else from business.legal_type.

GOTCHA: `_process_colin_filing` broad-except catches all exceptions (including queue.publish_json(), filing.set_processed(), filing.save()) and masks with generic 'unable to publish for post processing' message.

GOTCHA: `_save_filing` mutates input json_input dict for bootstrap filings, setting filing['business']['identifier'] = bootstrap.identifier before assigning to filing.filing_json.

Internal API for managing business filings and synchronizing colin_event_ids with an external Colin system; serves cron jobs and colin service.

**InternalFilings.GET** (no status): Retrieves completed filings for Colin, enriches each filing_json with: filingId, learEffectiveDate (from filing.effective_date.isoformat()), and business metadata (legalName if missing). Skips filings where filing_type is 'lear_epoch' OR (filing_type is 'correction' AND business.legal_type is COOP). For corrections, looks up ColinEventId by correctedFilingId; skips filing if not found, else adds correctedFilingColinId from first result. Returns all matching filings as JSON array, 200 OK.

**InternalFilings.GET** (with status): Returns filing.json for all filings matching status parameter, 200 OK.

**InternalFilings.PATCH** (filing_id): Requires COLIN_SVC_ROLE. Reads colinIds array from request JSON. For each colin_id, creates ColinEventId object, appends to filing.colin_event_ids, saves filing. Returns filing.json, 202 ACCEPTED.

**ColinLastUpdate.GET** (no param): Returns {'maxId': last_event_id[0]} from colin_last_update table's most recent row, 200 OK. If colin_id provided, looks up ColinEventId.get_by_colin_id(colin_id), returns {'colinId': colin_event_id_obj.colin_event_id}, 200 OK.

**ColinLastUpdate.POST** (colin_id): Requires COLIN_SVC_ROLE. Inserts colin_id into colin_last_update (last_update=current_timestamp, last_event_id=colin_id), calls GET to return result.

GOTCHA: ColinLastUpdate.POST uses unparameterized f-string in SQL query (`{colin_id}`), enabling SQL injection. GOTCHA: Malformed error dict returned on exception: `{'message: failed to update colin_last_update.', 500}` (missing quote, wrong structure). GOTCHA: InternalFilings.PATCH saves filing repeatedly in loop, once per colin_id.

=== legal-api/src/legal_api/resources/v1/business/business_tasks.py ===

Endpoint that returns a JSON list of pending tasks for a business: incomplete filings and upcoming annual reports due.

GET handler queries business by identifier (or validates NR if identifier starts with 'NR'); for NR, calls namex.query_nr_number and namex.validate_nr, returning FORBIDDEN if not consumable. If business doesn't exist but is NR, creates incorporate NR to-do. Otherwise constructs task list by: retrieving filings with status DRAFT, PENDING, PENDING_CORRECTION, or ERROR; for each with payment_status_code='CREATED' and payment_token, fetches payment details from PAYMENT_SVC_URL via requests.get, catching ConnectionError or Timeout to return string 'pay_connection_error' (checked later with `rv == 'pay_connection_error'`). Calculates next_ar_year from business.last_ar_year or business.founding_date.year; increments by count of incomplete annualReport filings; loops through years until datetime.utcnow().year, creating AR to-do items with enabled=True only if no pending_filings exist and year matches start_year. Each task has task object, order index, and enabled boolean.

GOTCHA: payment API failures return a string sentinel rather than raising an exception.

=== legal-api/src/legal_api/resources/v1/business/filing_comments.py ===

REST API resource for retrieving and creating comments on business filings. GET with comment_id returns that comment (404 if not found); without it returns all comments for the filing. POST requires add_comment authorization (401 if denied), validates the input, confirms filingId in JSON matches the URL filing_id (400 if mismatch), creates Comment with text, staff_id set to current user's ID, filing_id, and current UTC timestamp, then saves. Both methods perform basic checks: verify business exists and filing belongs to business (404 if either fails).

GOTCHA: On save failure (BusinessException), returns err.status_code or HTTPStatus.CREATED for POST — maps error responses to success status code if status_code is not set. GOTCHA: Validation and authorization errors embed errors array into response JSON rather than using standard error response structure.

=== legal-api/src/legal_api/resources/v2/business/business.py ===

Retrieves business information from a legal filing registry or creates new business filings.

Input: GET receives business identifier string plus optional query params (slim, allowed_filings, account); POST receives JSON with filing data (header.accountId, header.name, filing.nameRequest).

Output: GET returns business JSON; POST returns filing save result.

GET /<identifier>: Looks up Business by identifier. Returns "No information on temp registrations" if identifier starts with 'T', or 404 if not found. If request.args.get('slim') == 'true', returns business.json(slim=True) with alternateNames added; otherwise returns full JSON enriched with check_warnings() → warnings, get_allowable_actions() → allowable_actions, CoreFiling.get_most_recent_filing_json() → submitter and lastModified. If allowed_filings=true, adds allowedFilings from get_allowed(). If account param present and jwt.has_one_of_roles([SYSTEM_ROLE, ACCOUNT_IDENTITY]) is true, fetches account via AccountService.get_account_by_affiliated_identifier() and adds accountId only if it matches an org.id.

POST: Validates filing_type in CoreFiling.NEW_BUSINESS_FILING_TYPES (BAD_REQUEST if invalid). Creates RegistrationBootstrap via RegistrationBootstrapService.create_bootstrap(filing_account_id) (SERVICE_UNAVAILABLE if fails). Extracts business_name from json_input['filing'][filing_type]['nameRequest']['nrNumber'] or uses bootstrap.identifier. Gets legal_type and corp_type_code from Filing.FILINGS[filing_type]. Registers via RegistrationBootstrapService.register_bootstrap() (if fails, suppress-wrapped bootstrap.delete() then SERVICE_UNAVAILABLE). Calls saving_filings(identifier=bootstrap.identifier).

GOTCHA: Authorization check commented out pending issue #22143.
GOTCHA: suppress(Exception) on bootstrap.delete() silently hides deletion failures.

=== legal-api/src/legal_api/resources/v2/business/business_comments.py ===

Flask API for retrieving and creating comments attached to business entities.

GET endpoints return comments filtered by business_id where filing_id is null; POST creates a comment after authorization and validation. Both routes resolve business via Business.find_by_identifier(), or for T-prefixed identifiers via FilingModel.get_temp_reg_filing() then Business.find_by_internal_id(). GET /<identifier>/comments returns JSON list of all comments; GET /<identifier>/comments/<comment_id> returns single comment or 404. POST validates JSON body via validate(json_input, False), checks authorized(identifier, jwt, action=['add_comment']), creates Comment with comment text from json_input['comment']['comment'], staff_id from User.get_or_create_user_by_jwt(g.jwt_oidc_token_info), business_id, and timestamp=datetime.utcnow().

Errors: missing business (404), POST without JSON body (400), unauthorized (401), validation failure (err.code with err.msg added to response), BusinessException on save (err.status_code).

GOTCHA: Comments filtered by filing_id.is_(None), excluding filing-attached comments.

=== legal-api/src/legal_api/resources/v2/business/business_digital_credentials.py ===

Three REST API endpoints for managing digital business credentials: revoking, deleting, and processing webhooks from aca-py.

**revoke_credential** (POST): Validates business identifier, active DCConnection, and issued_credential by credential_id (404 if missing). Reads 'reissue' boolean from JSON body (default False); sets reason to DCRevocationReason.SELF_REISSUANCE if reissue else SELF_REVOCATION. Calls digital_credentials.revoke_credential with connection_id, credential_revocation_id, revocation_registry_id, reason; returns 500 if None. Sets is_revoked=True and saves; returns 200.

**delete_credential** (DELETE): Validates business and issued_credential by credential_id (404 if missing). If credential_exchange_id exists, calls digital_credentials.fetch_credential_exchange_record then remove_credential_exchange_record; returns 500 if remove returns None. Deletes issued_credential; returns 200.

**webhook_notification** (POST): Routes by topic_name. 'connections': updates connection_id, connection_state, is_active if state is 'active' or 'completed'. 'issuer_cred_rev': sets credential_revocation_id, revocation_registry_id if state='issued'. 'issue_credential_v2_0': sets date_of_issue, is_issued=True if state='done'. Catches exceptions, logs, re-raises; returns 200 on success.

GOTCHA: revoke_credential sets is_revoked and calls save() without transaction; if save fails after remote revocation succeeds, local DB becomes inconsistent with external system.

GOTCHA: webhook_notification catches and re-raises exceptions, causing 500 response instead of acknowledging receipt; may cause aca-py to retry.

=== legal-api/src/legal_api/resources/v2/business/business_documents.py ===

API endpoint to retrieve business documents for an entity, returning a list of available documents or a specific document in PDF or JSON format.

Route `/<identifier>/documents` (optional `/<document_name>`) requires JWT auth and 'view' authorization for the identifier. Returns 401 if not authorized, 404 if business not found. For document list, returns JSON with document URLs including 'summary' document; if business legal_type is COOP, adds 'certifiedRules' and 'certifiedMemorandum' with metadata (file_key, name, uploaded filing_date). For specific document, validate_document_request() checks document validity, then returns PDF or JSON based on request.accept_mimetypes. Coop documents pulled via Document.find_by_business_id_and_type() for COOP_RULES and COOP_MEMORANDUM; for each, finds the associated Filing, generates document URL and filename from business.identifier and filing_date. Checks for specialResolution filings where filing_json['filing']['alteration']['rulesInResolution'] or 'memorandumInResolution' is True, and if found, adds includedInResolution fields with the resolution filing_date.

GOTCHA: if sr_rules_resolution is non-empty but rules_document is None, accessing info['certifiedRules']['includedInResolution'] will KeyError because info['certifiedRules'] was never created.

=== legal-api/src/legal_api/resources/v2/business/business_filings/business_documents.py ===

Provides REST endpoints to retrieve documents and filing receipts for a business entity: lists documents associated with a filing, returns PDF documents by name or file key, or generates a receipt PDF via the payment service.

Accepts: `identifier` (business code, or 'T' prefix for temp registration), `filing_id`, optional `legal_filing_name` (document type), optional `file_key` (file identifier). Returns: JSON document list or PDF bytes at 200/404/401/400.

Flow: Authorizes via JWT. For 'T' identifier, fetches filing then business by `filing_model.business_id`; otherwise looks up business by identifier. Validates filing exists. If neither `legal_filing_name` nor `file_key` given, returns `_get_document_list()`. If PDF requested and `legal_filing_name` starts with 'receipt', calls `_get_receipt()` which POSTs to `PAYMENT_SVC_URL/{payment_token}/receipts` with corp name, filing dates, and tax ID, returning response content. If `file_key` given, fetches from Minio via `MinioService.get_file()` after validating `document.filing_id == filing.id`.

GOTCHA: Completed temp-registration filings return empty document list without validating filing exists. GOTCHA: Payment service errors are logged but response returned unchanged—caller cannot distinguish success from failure.

=== legal-api/src/legal_api/resources/v2/business/business_filings/business_filings.py ===

Cancels a filing's payment and resets it to DRAFT status. Input: business identifier (string; 'T'-prefixed for temp registrations) and filing_id (int). Output: JSON filing with 202 ACCEPTED on success; error objects with appropriate status codes on failure. Authorization required (edit action). Retrieves filing: if identifier starts 'T', queries by Filing.temp_reg and Filing.id; else calls Business.get_filing_by_id(). Returns 400 if no filing_id, 401 if unauthorized, 404 if filing not found. Makes DELETE request to PAYMENT_SVC_URL/{filing.payment_token} with JWT bearer token and 20.0s timeout. If response status is OK or ACCEPTED, calls filing.reset_filing_to_draft(). On ConnectionError or Timeout: logs and returns 500. On BusinessException: returns its error and status_code.

GOTCHA: Unauthorized error message incorrectly says "delete" instead of "cancel". GOTCHA: If reset_filing_to_draft() throws BusinessException after successful payment cancellation, the payment remains cancelled but the request fails.

Service module that retrieves, enriches with documents and payment status, and validates business filings.

Input: filing identifier, filing ID, query parameters (original, type, accept-mimetypes, start, size, effective_date), JSON filing data, JWT. Output: JSON filing with documents, payment details, review comments; or error responses.

**Single filing:** If `original=true` return raw filing. If PDF accept-header return PDF report. Otherwise load filing, add documents via DocumentMetaService. Check status: PENDING → fetch payment update from PAYMENT_SVC_URL using paymentToken, update with isPaymentActionRequired and paymentMethod; CHANGE_REQUESTED/APPROVED/REJECTED with review result → add latestReviewComment. Merge common ledger items and return redacted.

**Ledger listing:** Validate effective_date (ISO 8601 via _is_valid_date), reject PDF requests. Return paginated COMPLETED and PAID filings.

**Filing completion:** If source is COLIN use process_colin_filing; else for non-draft: if filing_type in NEW_BUSINESS_FILING_TYPES with nrNumber and effective_date past NR expiration call namex.update_nr_as_future_effective, set effective_date, create invoice.

**Deletion lock:** Draft alteration of limited/unlimited company → UNAUTHORIZED "must complete to become BC Benefit Company"; draft or pending status → UNAUTHORIZED; else → FORBIDDEN.

**Authorization:** Extract filing_type from header.name, get filing_sub_type via Filing.get_filings_sub_type, state from business or default ACTIVE, legal_type from business or nameRequest. Verify authorized and is_allowed checks.

GOTCHA: Payment service connection errors (ConnectionError, Timeout) caught and logged but swallowed—filing continues without payment details.

Persists business filings to the ledger. Distinguishes bootstrap (identifier starts 'T') from regular business filings. POST creates Filing, PUT updates existing. For COLIN-source filings: parses colinIds from filing['header'], checks if filing_date < epoch_filing[0].filing_date (where epoch_filing is sole Filing with Status.EPOCH); if yes, adopts epoch_filing[0].transaction_id and marks processed; else publishes to queue for post-processing. Sets filing_date to utcnow() unless source is COLIN or filing in change_requested_status. Sets effective_date from filing['header']['effectiveDate'] or utcnow(). Sanitizes HTML in specialResolution.resolution and correction.resolution before persisting. Validates against 'filing' schema.

GOTCHA: is_before_epoch_filing returns False if epoch_filing count ≠ 1, masking missing or duplicate epoch records.
GOTCHA: Broad Exception handler in process_colin_filing conceals underlying errors.
GOTCHA: filing_json type-hinted as str but used as dict.

Handles invoice creation and related operations for business filing submissions: extracting business/filing metadata, submitting to payment service, managing effective dates, deleting associated files, and generating invoice details.

`create_invoice(business, filing, filing_types, user_jwt, payment_account_id)` extracts mailing address and corp_type from filing JSON via filing-type-dependent paths (NEW_BUSINESS_FILING_TYPES, conversion, or default); builds payload with businessInfo (business.identifier, corp_type, business.legal_name, mailing_address fields: city, postal_code, region, street, country) and filingInfo (filing.id, filing_types, folioNumber if present); adds accountInfo for STAFF_ROLE or SYSTEM_ROLE (routingSlip, bcolAccountNumber, datNumber from filing header); POSTs to payment_svc_url with Bearer token; on 201/200 saves payment_token, payment_status_code, payment_account, submitter_roles and returns (isPaymentActionRequired, HTTPStatus.CREATED); on 400 saves error type and returns (payment_error_type, HTTPStatus.PAYMENT_REQUIRED); connection errors or other status return (error message, HTTPStatus.PAYMENT_REQUIRED) without updating filing.

`set_effective_date(business, filing)` sets futureEffectiveDate to tomorrow 1-minute-after-midnight for changeOfAddress filings when business.legal_type is not COOP.

`is_future_effective_filing(filing_json)` returns true if header effectiveDate > current UTC time.

`delete_from_minio(filing)` deletes by filing type: incorporationApplication/alteration → rulesFileKey, memorandumFileKey; dissolution → affidavitFileKey; courtOrder → fileKey; continuationIn → foreignJurisdiction.affidavitFileKey and authorization.files[].fileKey.

`details_for_invoice(business_identifier, corp_type)` returns empty list if identifier falsy or starts 'T', else [{label: 'Registration Number:' for SP/GP else 'Incorporation Number:', value: identifier}].

GOTCHA: Connection/timeout errors return without persisting filing payment fields. GOTCHA: `set_effective_date` directly modifies protected `_filing_json` attribute.

Resubmits a filing for review, updating its review status and extracting key identifiers from the filing JSON structure.

Input: Filing object with populated filing_json. Output: None (modifies Review in database).

Extracts from filing_json['filing'][filing.filing_type]: nr_number from nameRequest, identifier from foreignJurisdiction. Finds completing party by matching party.roles[].roleType='Completing Party', returns officer firstName+optional middleName+lastName. Sets Review status=ReviewStatus.RESUBMITTED, nr_number, identifier, completing_party, submission_date=datetime.datetime.utcnow(). Appends last ReviewResult (with updated submission_date) to review.review_results and saves review. Calls filing.resubmit_filing_to_awaiting_review(submission_date).

GOTCHA: No validation of filing_json structure—KeyError if nameRequest or foreignJurisdiction missing.

GOTCHA: get_completing_party assumes party['officer'] exists and has firstName, lastName fields without checking.

=== legal-api/src/legal_api/resources/v2/business/business_tasks.py ===

Retrieves pending business tasks via REST API endpoint.

For identifier (business ID or NR number): if NR, fetches and validates via namex service—returns 403 if invalid. Returns JSON with task array; each task contains task object, order (int), and enabled (bool). If business missing but NR valid, creates incorporate todo. If business exists, constructs list from: pending filings (status DRAFT, PENDING, PENDING_CORRECTION, ERROR), conversion filing (when compliance warning MISSING_REQUIRED_BUSINESS_INFO present and no existing conversion filing), and due annual reports (excluded for entity_types_no_ar ['SP', 'GP']). For filings with payment_status_code 'CREATED' and payment_token, fetches payment details from PAYMENT_SVC_URL, adding isPaymentActionRequired and paymentMethod to filing header; connection errors return 503.

GOTCHA: Compliance warnings set on business object as business.compliance_warnings and business.warnings, but these are not persisted.

=== legal-api/src/legal_api/resources/v2/business/colin_sync.py ===

Provides internal API endpoints for syncing completed business filings to Colin (government registry): fetches filings in Colin-ready format with pagination, and records Colin event IDs after sync.

**GET /internal/filings**: Returns completed filings paginated by `page` and `limit` query params. Skips filings of type `lear_epoch` or corrections on COOP businesses. For each filing, includes `filingId`, dates (`filing_date`, `effective_date`), and business details—fetched via `VersionedBusinessDetailsService` using `transaction_id` if available, else current. For `correction` type: appends `correctedColinId` from `ColinEventId.get_by_filing_id()`, skipping if none found. For `amalgamationApplication` (horizontal/vertical): calls `set_from_primary_or_holding_business_data()` to populate legal name, parties (directors + completing party), offices, and share classes from the primary/holding business by role; swallows exceptions and skips that filing. For `dissolution` with `filing_sub_type='involuntary'`: adds batch processing `meta_data`. Returns `{filings: [...], page, limit, pages, total}`.

**PATCH /internal/filings/{filing_id}**: Accepts JSON `{colinIds: [...]}`, creates `ColinEventId` objects, appends each to `filing.colin_event_ids`, saves, returns updated filing JSON.

GOTCHA: Exceptions during amalgamation data enrichment are caught and logged but the filing skipped silently. GOTCHA: Logging calls use `.Error` (capital E) instead of `.error`.

Syncs COLIN event IDs and tax IDs between a business registry system and the legal database via internal API endpoints requiring UserRoles.colin JWT.

**GET /internal/filings/colin_id[/<colin_id>]**: If colin_id provided, returns its colin_event_id from ColinEventId record (404 if not found). Otherwise queries colin_last_update, returns most recent last_event_id as maxId (404 if empty), or propagates exception.

**POST /internal/filings/colin_id/<colin_id>**: Inserts colin_id as last_event_id into colin_last_update with current_timestamp, commits, calls GET endpoint.

**GET /internal/tax_ids**: Returns JSON array of identifiers from Business.get_all_by_no_tax_id() (excludes COOPs, SP, GP from tax-id syncing).

**POST /internal/tax_ids**: Accepts JSON dict of identifier→tax_id pairs. For each, finds Business by identifier, sets tax_id field, saves. Logs errors for missing identifiers but continues processing; returns 201 success regardless.

GOTCHA: POST /colin_id uses f-string SQL interpolation for colin_id, enabling SQL injection.
GOTCHA: POST /colin_id error response is malformed tuple: `{'message: failed...', 500}` (missing closing quote on key).
GOTCHA: POST /tax_ids returns 201 success even when some identifier updates failed.

=== legal-api/src/legal_api/resources/v2/business/filing_comments.py ===

Retrieves and creates comments on business filings via REST API endpoints.

**GET endpoints** query Comment records by filing_id, returning all comments for a filing or a single comment by comment_id after validating the business and filing exist.

**POST endpoint** creates a new Comment: accepts comment text and filing_id in JSON body; authorizes the user has 'add_comment' permission; validates the request filing_id matches the URL parameter; constructs Comment with text, staff_id from JWT token, filing_id, and current UTC timestamp; saves to database. Returns the saved Comment as JSON with 201 CREATED.

**Routing**: PUT, PATCH, DELETE return 405 METHOD_NOT_ALLOWED.

**_basic_checks helper** validates preconditions: for GET requests, if identifier starts with 'T' (temporary registration), looks up Business via Filing.get_temp_reg_filing() and Business.find_by_internal_id(); otherwise via Business.find_by_identifier(). Confirms business exists and filing belongs to it; for POST, confirms request body contains JSON. Returns (None, None) on success or (error_dict, status_code) on failure.

GOTCHA: POST exception handler returns CREATED/ACCEPTED status even when catching BusinessException — error not reflected in response code.

=== legal-api/src/legal_api/resources/v2/document.py ===

API resource module for managing documents stored in Minio object storage, supporting upload pre-signing, retrieval, and deletion.

**Inputs & outputs:**
`GET /api/v2/documents/<file_name>/signatures` returns pre-signed PUT URL (200 OK). `DELETE /api/v2/documents/<document_key>` returns success message (200 OK) or "Filing is not a draft" (403 FORBIDDEN) or error (500). `GET /api/v2/documents/<document_key>` returns PDF binary (200 OK) or error (500).

**Main flow:**
`get_signatures()` calls `MinioService.create_signed_put_url(file_name)`. `delete_minio_document()` calls `is_draft_filing(document_key)` which finds Document by file_key, retrieves its Filing by document.filing_id, and returns True if document not found OR filing.status equals Filing.Status.DRAFT.value; delete proceeds via `MinioService.delete_file()` only if True. `get_minio_document()` calls `MinioService.get_file(document_key)` and returns response.data as application/pdf. Both DELETE and GET wrap all operations in try/except, returning 500 INTERNAL_SERVER_ERROR on Exception.

All routes require JWT auth and allow cross-origin requests.

GOTCHA: `is_draft_filing()` returns True if Document not found, permitting deletion of non-existent documents.
GOTCHA: Broad exception handling swallows all errors and returns generic messages.

=== legal-api/src/legal_api/services/minio.py ===

Wraps Minio S3-compatible object storage to upload, download, and delete business documents via signed URLs.

Generates upload URLs (`create_signed_put_url`) valid 5 minutes; creates a random key from UUID + original file extension, returns both the pre-signed PUT URL and the key. Generates download URLs (`create_signed_get_url`) valid 1 hour for a given key. Uploads via `put_file(key, data, length)`, downloads via `get_file(key)` (caller must close response and release connection), retrieves metadata via `get_file_info(key)`, and deletes via `delete_file(key)`. All operations target the `MINIO_BUCKET_BUSINESSES` bucket. Client obtained from `_get_client()` using `MINIO_ENDPOINT`, `MINIO_ACCESS_KEY`, `MINIO_ACCESS_SECRET`, and `MINIO_SECURE` from Flask app config.

GOTCHA: `put_file` declares `length` parameter as string type, inconsistent with typical file-size integer semantics. GOTCHA: `get_file` returns a streaming response requiring explicit caller cleanup (close, release_conn); no wrapper-level resource management.
