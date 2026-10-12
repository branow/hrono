# today

# Legal API: business filings, comments, tasks, documents, Colin sync, and Minio (Python/Flask)

This group covers the REST resources and services of a Flask "legal-api" for a business registry (BC-style entities: COOP, SP, GP, BC companies, temporary registrations). It is organized into a v1 resource set, a v2 resource set, and a Minio storage wrapper. The main integrations are the payment service (`PAYMENT_SVC_URL`), Colin (the legacy registry), Minio, namex (name requests), and aca-py (digital credentials).

## v1 resources (`resources/v1/business/`)
- **business_filings.py**
  - GET returns one filing or the list of COMPLETED and PAID filings, as JSON or PDF. `original=true` returns the raw filing.
  - For temporary registrations (identifier starts with 'T'), GET reads from CoreFiling and RegistrationBootstrap. A PENDING filing gets `isPaymentActionRequired` and `paymentMethod` from the payment service.
  - PUT (POST delegates to it) validates and saves a filing, then calls complete_filing. `draft=true` skips validation and completion. `only_validate=true` returns only the validation result.
  - DELETE removes the filing and its Minio files. For 'T' identifiers it also deregisters and deletes the bootstrap. It is blocked when `deletion_locked` is set.
  - Static helpers: `_save_filing`, `_validate_filing_json`, `_process_colin_filing`, `_get_legal_type`. `_save_filing` handles the Colin source, `colinIds`, filing and effective dates, and epoch handling.
  - Internal API classes serve cron jobs and the Colin service:
    - `InternalFilings` GET enriches filings for Colin. It skips `lear_epoch` filings and COOP corrections.
    - `InternalFilings` PATCH, with the COLIN_SVC_ROLE role, appends `colinIds`.
    - `ColinLastUpdate` GET/POST reads and writes the `colin_last_update` table.
- **business_tasks.py** returns the to-do list: incomplete filings (DRAFT, PENDING, PENDING_CORRECTION, ERROR), the NR incorporate to-do, and upcoming annual-report tasks. Each task has a task object, an order and an enabled flag.
- **filing_comments.py** has GET and POST for filing comments. POST requires `add_comment` authorization and a matching filingId.

## v2 resources (`resources/v2/business/`)
- **business.py**
  - GET /<identifier> returns business JSON. The `slim` param gives a reduced form with alternateNames. The full form adds warnings, allowable_actions, submitter, lastModified, and optionally allowedFilings and accountId.
  - POST creates a RegistrationBootstrap and registers it, then saves a new-business filing.
- **business_comments.py** handles business-level comments (filing_id is null) and supports T-prefixed temp registrations.
- **filing_comments.py** is the v2 filing comments resource. It has a `_basic_checks` helper, and PUT, PATCH and DELETE return 405.
- **business_tasks.py** is the v2 to-do list. It adds a conversion filing when the compliance warning MISSING_REQUIRED_BUSINESS_INFO is present. It skips annual reports for SP and GP. It returns 503 when the payment service can't be reached.
- **business_digital_credentials.py** has three endpoints: revoke_credential, delete_credential, and webhook_notification for aca-py topics (`connections`, `issuer_cred_rev`, `issue_credential_v2_0`).
- **business_documents.py** lists documents (summary, and for COOPs certifiedRules and certifiedMemorandum with `includedInResolution` info) or returns a specific document as PDF or JSON.
- **business_filings/business_documents.py** lists a filing's documents, returns PDFs by name or `file_key` from Minio, and generates receipts through the payment service.
- **business_filings/business_filings.py** is a group of modules:
  - Cancels a payment and resets the filing to DRAFT.
  - A filing service that retrieves, enriches and validates filings. It adds documents, payment status and review comments. It has ledger listing with `effective_date` validation, completion logic with NR expiry handling, deletion-lock rules and authorization.
  - Persistence (POST creates, PUT updates), including Colin and epoch handling and HTML sanitizing of resolutions.
  - Invoice helpers: `create_invoice`, `set_effective_date`, `is_future_effective_filing`, `delete_from_minio`, `details_for_invoice`.
  - A resubmit-for-review routine that updates the Review record.
- **colin_sync.py** has two parts:
  - Paginated GET /internal/filings in Colin format, with amalgamation and involuntary-dissolution enrichment, and PATCH to record `colinIds`.
  - Colin event ID endpoints (GET/POST `colin_id`) and tax-ID sync (GET/POST `/internal/tax_ids`).
- **document.py** manages Minio documents. It has endpoints for a signed PUT URL, DELETE (draft filings only) and GET PDF.

## Services
- **services/minio.py** wraps Minio with:
  - `create_signed_put_url` (valid 5 minutes, key built from a UUID plus the file extension) and `create_signed_get_url` (valid 1 hour).
  - `put_file`, `get_file`, `get_file_info` and `delete_file`.
  - All operations use the `MINIO_BUCKET_BUSINESSES` bucket.

## Caution
- **Payment errors are swallowed.**
  - Several payment calls log connection errors and carry on. These include the GETs and the filing service in v1 and v2, `_get_receipt`, and invoice creation.
  - The caller can't tell success from failure. In invoice creation the filing's payment fields are not persisted.
  - v1 tasks return the string sentinel `'pay_connection_error'`, while v2 tasks return 503.
- **Broad exception handling hides errors.**
  - `_process_colin_filing` and `process_colin_filing` catch everything and return a generic message.
  - The v1 PUT handler only does `print(err)`.
  - The document.py DELETE and GET return a generic 500.
  - Suppressed bootstrap deletes in v2 business POST are silent.
  - Colin amalgamation enrichment failures silently skip the filing.
- **SQL injection and malformed errors.** POST colin_id (v1 `ColinLastUpdate` and v2 colin_sync) builds SQL with an f-string. Its error return `{'message: failed...', 500}` is malformed (missing quote).
- **Misleading status codes.**
  - Comment POST handlers return CREATED/ACCEPTED even when a BusinessException occurred, in both v1 and v2.
  - POST /internal/tax_ids returns 201 even if some identifiers failed.
  - The cancel-payment unauthorized message says "delete" instead of "cancel".
- **Non-atomic operations.**
  - `revoke_credential` saves `is_revoked` after the remote revocation, so a failed save leaves local and external state inconsistent.
  - Cancelling a payment and then failing `reset_filing_to_draft()` leaves the payment cancelled but returns an error.
  - The Colin PATCH saves once per colin_id.
  - The digital credentials webhook re-raises errors, so it returns 500 and aca-py may retry.
- **Fragile or latent bugs.**
  - In business_documents.py, a KeyError occurs if `sr_rules_resolution` is non-empty but there is no rules document.
  - `is_draft_filing` returns True for a missing Document, so a delete of a non-existent document is permitted.
  - Completed temp-registration filings return an empty document list without checking the filing exists.
  - `is_before_epoch_filing` returns False unless there is exactly one epoch filing.
  - The resubmit routine raises KeyError if `nameRequest` or `foreignJurisdiction` is missing, and assumes officer fields exist.
  - `_save_filing` mutates the input JSON for bootstrap filings.
  - `set_effective_date` writes the protected `_filing_json`.
  - Logging uses `.Error` instead of `.error`.
  - `filing_json` is type-hinted as str but used as a dict.
  - The v2 business GET authorization check is commented out (issue #22143).
  - v2 tasks set compliance warnings on the business object without persisting them.
- **Minio quirks.**
  - `put_file`'s `length` is typed as a string.
  - `get_file` returns a stream that the caller must close and release.

# purpose-budget

# Business filings, tasks, comments, documents and Colin sync (legal-api REST layer)

This part of legal-api is the Flask REST layer for a business registry. It lets clients and internal services read and write filings, list a business's to-do tasks, attach comments, fetch generated documents and receipts, and manage Minio-stored files. It also holds the internal endpoints that sync records with the Colin legacy registry. It has a v1 and a v2 version of most resources. Identifiers starting with `T` mean temporary registrations, which use a separate bootstrap path (`RegistrationBootstrap`, `CoreFiling`) in many handlers.

## Inputs and outputs
- **In:** JWT-authenticated HTTP calls from the web UI, staff and system accounts. The `COLIN_SVC_ROLE` and `UserRoles.colin` roles are used on the internal Colin endpoints. Aca-py webhooks arrive for digital credentials.
- **Out:**
  - JSON, PDF or Minio file bytes returned to callers.
  - Database writes: `Filing`, `Comment`, `ColinEventId`, `colin_last_update`, `Business.tax_id`, digital credential records.
  - Calls to the payment service (`PAYMENT_SVC_URL`): invoice creation, payment status lookup, payment cancellation and receipts.
  - Calls to namex (name requests), Minio, a filing queue and aca-py.

## Ideas it owns
- **Filing lifecycle.**
  - Validation, save and completion live in `business_filings` v1 and v2. `_save_filing` sets the source (LEAR or COLIN), `filing_date` and `effective_date`.
  - COLIN filings dated before the epoch filing copy the epoch `transaction_id` and are marked processed. All others are published to the queue.
  - `create_invoice` posts to payment and stores `payment_token` and status on the filing.
  - Cancelling a payment in v2 `business_filings` calls `reset_filing_to_draft`.
  - Deletion is blocked when `deletion_locked` is set.
  - Draft limited/unlimited-company alterations get a specific unauthorized message.
- **Tasks.** `business_tasks` builds an ordered list of `{task, order, enabled}`. It covers incomplete filings (DRAFT, PENDING, PENDING_CORRECTION, ERROR), annual reports due, a conversion task, and an incorporate task for a valid NR. SP and GP get no annual reports in v2.
- **Comments.** Comments attach either to a filing (`filing_comments`) or to a business, with `filing_id` null (`business_comments`). Posting requires the `add_comment` action.
- **Documents.** `business_documents` lists summary and COOP rules/memorandum documents. The nested filings variant lists a filing's documents and builds receipts through the payment service. `document.py` and `MinioService` handle signed upload URLs and file get and delete. Delete is allowed only for draft filings.
- **Colin sync.** `colin_sync` and v1 `InternalFilings` expose completed filings in Colin format. Corrections get a corrected Colin ID, and `lear_epoch` filings and COOP corrections are skipped. They also record `colinIds`, track `colin_last_update`, and sync tax IDs.
- **Digital credentials.** Revoke, delete and handle webhooks (connections, `issuer_cred_rev`, `issue_credential_v2_0`).

## Main flow (filing submit)
1. PUT/POST authorizes the user and validates the JSON against the `filing` schema, unless `draft=true`.
2. Save the filing, sanitizing resolution HTML.
3. Complete it: handle COLIN filings, or compute the effective date and create the invoice.
4. Return the filing JSON.

## Open first
- `resources/v2/business/business_filings/business_filings.py` (the service module for retrieval, validation, invoicing and persistence)
- `resources/v1/business/business_filings.py`
- `resources/v2/business/colin_sync.py`
- `resources/v2/business/business_tasks.py`
- `services/minio.py`

## Hazards
- **SQL injection:** `colin_id` is interpolated into SQL by f-string in both v1 `ColinLastUpdate.POST` and the v2 colin-id POST. Their error return is also a malformed dict.
- **Payment errors swallowed or inconsistent:**
  - GET filing, receipts and `create_invoice` log connection errors and continue without payment data.
  - v1 tasks return a `'pay_connection_error'` string sentinel.
  - v2 tasks return 503.
  - Cancelling a payment can succeed even if the later draft reset fails.
- **Misleading status codes:** the comment POST handlers return a success code (CREATED) when a `BusinessException` has no status code.
- **Broad exception handlers** hide real failures in `_process_colin_filing` and `process_colin_filing`. The v1 PUT handler only prints the error.
- **`is_before_epoch_filing`** returns False unless there is exactly one epoch filing.
- **Document edge cases:** a missing `Document` counts as draft, so delete is allowed. In `business_documents`, `includedInResolution` can raise `KeyError` when there is no rules document.
- **Bulk and credential updates:**
  - `POST /tax_ids` returns 201 even when some identifiers failed.
  - Revoking a credential can leave the local record out of sync after a remote success.
  - The webhook re-raises errors, which causes a 500 and aca-py retries.
- **Mutation:** `_save_filing` mutates its input JSON for bootstraps.
- **Minio:** `get_file` needs the caller to close the response and release the connection.

# decisions

# Business filings, comments, tasks, documents and Colin sync (legal-api resources and services)

This part of the BC legal-api exposes REST endpoints (v1 and v2) for business information, filings, filing comments, pending tasks, documents, digital credentials and Colin synchronisation. It also holds the Minio storage wrapper. Business identifiers starting `T` are temporary registrations, handled through bootstrap or temp-reg filings, and this branches almost everywhere. Payment is an external service at `PAYMENT_SVC_URL`.

## Boundaries

**Receives**
- JWT-authenticated HTTP requests from the UI, cron jobs and the Colin service.
- The Colin service needs `COLIN_SVC_ROLE` or `UserRoles.colin`.
- aca-py webhooks arrive at `webhook_notification`.

**Calls out to**
- **Payment service**
  - GET status for PENDING filings.
  - POST to create an invoice.
  - DELETE `{payment_token}` to cancel, with a 20s timeout.
  - POST `{payment_token}/receipts` for a receipt PDF.
- **Namex**: `query_nr_number`, `validate_nr`, `update_nr_as_future_effective`.
- **Minio**: signed URLs, put, get, delete.
- **Digital credentials (aca-py)**: `revoke_credential`, `fetch_credential_exchange_record`, `remove_credential_exchange_record`.
- **Account service**: `AccountService.get_account_by_affiliated_identifier`.
- **Queue**: `queue.publish_json` for post-processing.

**Writes**
- Filing, Comment, ColinEventId, colin_last_update, Business.tax_id, Review and ReviewResult, DCConnection and issued credentials, RegistrationBootstrap.

**Shapes**
- Filing JSON: `header` has `name`, `accountId`, `source`, `date`, `effectiveDate`, `colinIds`, and the `filing.<type>` body.
- Comment POST body: `{comment: {comment, filingId?}}`.
- Colin PATCH body: `{colinIds: [...]}`.
- Tax-id POST body: `{identifier: tax_id}`.
- Colin sync GET (v2) returns `{filings, page, limit, pages, total}`.
- Task: `{task, order, enabled}`.

## Decisions

**Business GET (v2)**
- `T` identifier: returns "No information on temp registrations". Unknown business: 404.
- `slim=true`: `business.json(slim=True)` plus `alternateNames`.
- Otherwise: full JSON plus `warnings`, `allowable_actions`, `submitter` and `lastModified`.
- `allowed_filings=true`: adds `allowedFilings`.
- `account` param: only when `jwt.has_one_of_roles([SYSTEM_ROLE, ACCOUNT_IDENTITY])`, and `accountId` is added only if it matches an org id.

**Business POST (v2)**
- `filing_type` must be in `CoreFiling.NEW_BUSINESS_FILING_TYPES`, else 400.
- Bootstrap creation or registration failure returns 503. On registration failure the bootstrap is deleted first.
- The business name is `nameRequest.nrNumber`, else the bootstrap identifier.

**Filing GET (v1)**
- Temp registration:
  - PENDING status triggers a payment lookup, which injects `isPaymentActionRequired` and `paymentMethod`.
  - amalgamationApplication, incorporationApplication and continuationIn return a PDF.
- Regular business: by ID, or list of COMPLETED and PAID filings.
- `original=true` returns the raw filing.

**Filing GET (v2 service)**
- `original=true` returns the raw filing.
- A PDF accept header returns the PDF report.
- A ledger listing requires a valid ISO `effective_date` and rejects PDF.
- Review comment: CHANGE_REQUESTED, APPROVED or REJECTED with a review result adds `latestReviewComment`.

**Filing save (PUT/POST)**
- `draft=true` skips validation and completion.
- `only_validate=true` returns the validation result only.
- Filings before the epoch or historical filings also skip validation.
- Source is COLIN or LEAR (default LEAR).
  - COLIN: filing_date comes from `header.date`, and `colinIds` become `ColinEventId`s.
  - Otherwise: filing_date is UTC now, except for COLIN source or `change_requested_status`, where it is not reset. This exception appears in the v2 persistence notes only.
- `effective_date` comes from `header.effectiveDate`, else UTC now.
- A COLIN filing dated before the sole `Status.EPOCH` filing adopts that filing's `transaction_id` and is marked processed. Otherwise it is published to the queue.
- `specialResolution.resolution` and `correction.resolution` are HTML-sanitised.
- `legal_type` comes from the filing JSON for incorporationApplication and registration, else from the business.

**Filing completion**
- COLIN source goes through `process_colin_filing`.
- Non-draft filings of a type in `NEW_BUSINESS_FILING_TYPES` with an `nrNumber` and an effective date past NR expiry call `namex.update_nr_as_future_effective`.
- `set_effective_date` sets `futureEffectiveDate` to tomorrow 00:01 for changeOfAddress when the business is not COOP.
- `is_future_effective_filing` is true when `header.effectiveDate` is later than now.

**Invoice creation (`create_invoice`)**
- The mailing address and corp_type paths depend on whether the filing is a new-business type, a conversion, or neither.
- `accountInfo` (routingSlip, bcolAccountNumber, datNumber) is added only for STAFF_ROLE or SYSTEM_ROLE.
- Payment 200/201: saves `payment_token`, `payment_status_code`, `payment_account` and `submitter_roles`, and returns `isPaymentActionRequired` with 201.
- Payment 400: saves the error type and returns 402.
- Connection error or other status: returns 402 without saving.
- `details_for_invoice` returns an empty list for a falsy or `T` identifier, else a label of "Registration Number:" for SP/GP or "Incorporation Number:".

**Filing delete**
- `filing.deletion_locked` blocks deletion. Otherwise the filing is removed, along with its Minio files via `delete_from_minio`. A `T` identifier also deregisters and deletes the bootstrap.
- Minio keys removed by type:
  - incorporationApplication and alteration: `rulesFileKey` and `memorandumFileKey`.
  - dissolution: `affidavitFileKey`.
  - courtOrder: `fileKey`.
  - continuationIn: `foreignJurisdiction.affidavitFileKey` and each `authorization.files[].fileKey`.
- Deletion-lock error code:
  - Draft alteration of a limited or unlimited company: 401, "must complete to become BC Benefit Company".
  - Draft or pending status: 401.
  - Otherwise: 403.

**Cancel payment (v2)**
- Needs the edit action. A missing `filing_id` returns 400, unauthorised 401, and a missing filing 404.
- Payment DELETE returning OK or ACCEPTED calls `filing.reset_filing_to_draft()` and returns 202.
- ConnectionError or Timeout returns 500. A BusinessException returns its own status.

**Authorization for new filings**
- Takes `filing_type` from `header.name`, plus the sub-type, and the state (business state, default ACTIVE). The legal type comes from the business or the `nameRequest`.
- Requires both `authorized` and `is_allowed`.

**Resubmit for review**
- Sets Review to RESUBMITTED with `nr_number`, `identifier`, `completing_party` and `submission_date`. The completing party is the party whose role is "Completing Party".
- Appends the last ReviewResult and calls `filing.resubmit_filing_to_awaiting_review`.

**Tasks (v1 and v2)**
- An `NR` identifier (v1) is checked through namex. If it is not consumable the response is 403. If no business exists, an incorporate todo is created.
- Included filings have status DRAFT, PENDING, PENDING_CORRECTION or ERROR.
- A filing with `payment_status_code='CREATED'` and a `payment_token` fetches payment details.
- v1: a connection failure yields the sentinel string `'pay_connection_error'`.
- v2: a connection failure returns 503.
- v1 annual reports (AR):
  - The start year is `last_ar_year` + 1, or the founding year.
  - It is incremented by the count of incomplete annualReport filings, then loops to the current year.
  - An item is `enabled` only if there are no pending filings and the year is the start year.
- v2 adds a conversion todo when the `MISSING_REQUIRED_BUSINESS_INFO` warning is present and no conversion filing exists. It also skips AR for `entity_types_no_ar` (SP, GP).

**Comments**
- v1 and v2 filing comments:
  - GET returns one comment (404 if missing) or all comments for the filing.
  - POST needs `add_comment`. Unauthorised is 401, and a `filingId` that differs from the URL is 400.
  - The comment is saved with `staff_id` from the JWT user and a UTC timestamp.
  - v2 returns 201, and PUT, PATCH and DELETE return 405.
- Business-level comments (v2): the filter is `filing_id.is_(None)`. POST validates through `validate(json_input, False)` and `authorized(..., ['add_comment'])`.
- A `T` identifier resolves through `get_temp_reg_filing` and `find_by_internal_id`.

**Documents**
- Authorisation: 'view' is required (401 if denied) and the business must exist (404).
- Business documents list:
  - Always includes `summary`.
  - COOP adds `certifiedRules` and `certifiedMemorandum`, with file_key, name and upload date.
  - `includedInResolution` is added when a specialResolution filing has `rulesInResolution` or `memorandumInResolution` true.
- Filing documents (v2):
  - With neither `legal_filing_name` nor `file_key`, the document list is returned.
  - A PDF request with a name starting `receipt` calls the payment service.
  - A `file_key` is served from Minio only if `document.filing_id == filing.id`.
- `/api/v2/documents` (generic Minio):
  - GET `<file_name>/signatures` returns a presigned PUT URL.
  - DELETE is allowed only if `is_draft_filing` is true, meaning the Document is missing or its filing is DRAFT. Otherwise 403.
  - GET returns the PDF. Errors return 500.

**Digital credentials**
- Revoke: needs an active DCConnection and an issued credential (404 otherwise). The reason is `SELF_REISSUANCE` if `reissue` else `SELF_REVOCATION`. A None result from aca-py returns 500, otherwise `is_revoked=True`.
- Delete: removes the exchange record if `credential_exchange_id` exists (500 if removal returns None), then deletes the credential.
- Webhook by `topic_name`:
  - `connections` with state `active` or `completed` sets the connection id, state and `is_active`.
  - `issuer_cred_rev` with state `issued` sets `credential_revocation_id` and `revocation_registry_id`.
  - `issue_credential_v2_0` with state `done` sets `date_of_issue` and `is_issued`.

**Colin sync**
- **Internal filings GET (v1)**
  - Skips `lear_epoch` filings, and corrections on COOP businesses.
  - For corrections, looks up `ColinEventId` by `correctedFilingId`, skips the filing if none is found, and adds `correctedFilingColinId`.
  - Each filing gains `filingId`, `learEffectiveDate` and `legalName`.
  - Given a status, it returns `filing.json` for each match.
- **Internal filings GET (v2, `colin_sync.py`)**
  - Paginated by `page` and `limit`.
  - Business data comes from `VersionedBusinessDetailsService` by `transaction_id`, else current.
  - A correction adds `correctedColinId` from `get_by_filing_id`, or the filing is skipped.
  - A horizontal or vertical amalgamationApplication fills in data from the primary or holding business via `set_from_primary_or_holding_business_data`. On exception the filing is skipped.
  - An involuntary dissolution adds batch `meta_data`.
- **PATCH `/filings/{id}`**: appends a `ColinEventId` per entry in `colinIds`. v1 requires `COLIN_SVC_ROLE` and returns 202. v2 returns the updated filing JSON.
- **colin_id GET**: with `colin_id`, returns `{colinId}` (v2 gives 404 if missing). Without it, returns `{maxId}` from the latest `colin_last_update` row (v2 gives 404 if empty).
- **colin_id POST**: inserts `colin_id` as `last_event_id` into `colin_last_update`, then calls GET.
- **Tax ids**
  - GET lists identifiers from `Business.get_all_by_no_tax_id()`, which excludes COOP, SP and GP.
  - POST sets `tax_id` per identifier.

**Minio service**
- `create_signed_put_url`: a 5-minute URL with key = UUID + the original extension; returns the URL and the key.
- `create_signed_get_url`: valid for 1 hour.
- `put_file`, `get_file`, `get_file_info` and `delete_file` all use `MINIO_BUCKET_BUSINESSES`.

## Where to open first
- `v1/business/business_filings.py`: save, delete, internal Colin endpoints, and the v1 GET.
- `v2/business/business_filings/*`: v2 filing GET and validation, persistence and `process_colin_filing`, invoice creation, cancel payment, and the resubmit-for-review code.
- `v2/business/business_filings/business_documents.py`: filing documents and receipts.
- `v2/business/business.py`: business GET and POST.
- `v2/business/business_tasks.py` and `v1/business/business_tasks.py`: tasks.
- `v2/business/colin_sync.py`: sync.
- `v2/document.py` and `services/minio.py`: generic Minio access.

## Hazards
1. **SQL injection and a malformed error in the colin_id POST.** Both versions interpolate `colin_id` into SQL with an f-string. The error return is `{'message: failed...', 500}`, which is not valid response structure.
2. **Swallowed failures hide partial work.**
   - `process_colin_filing` catches every exception (queue publish, `set_processed`, save) and reports a generic "unable to publish". The filing is saved, but its post-processing may not have happened.
   - v1 PUT only does `print(err)`.
   - `ColinLastUpdate` and the Colin sync GET (amalgamation) swallow errors and skip filings.
   - Tax-id POST returns 201 even when some identifiers failed.
3. **Payment errors are quiet or inconsistent.**
   - GET paths log connection errors and return the filing without payment details.
   - The receipt call returns the response unchanged.
   - v1 tasks return the sentinel `'pay_connection_error'` rather than raising.
   - v2 tasks return 503.
   - `create_invoice` connection errors return without saving the payment fields.
   - Cancel can cancel the payment, then fail on `reset_filing_to_draft`, leaving the payment cancelled and the filing not reset.
4. **Comment POST errors map to success codes.** On a save BusinessException the filing-comment POST falls back to 201 (v1) or CREATED/ACCEPTED (v2) when `status_code` is unset. Validation and authorisation errors also embed an errors array rather than the standard error structure.
5. **State can drift from the external system, or fail on missing data.**
   - Digital credential revoke sets `is_revoked` after the remote revocation, with no transaction.
   - The webhook re-raises exceptions and returns 500, which triggers aca-py retries.
   - `is_draft_filing` returns True for a missing Document, so deletion is allowed.
   - `is_before_epoch_filing` returns False unless exactly one epoch filing exists, so missing or duplicate epoch records go unnoticed.
   - `info['certifiedRules']['includedInResolution']` raises KeyError if a resolution applies but there is no rules document.
   - Resubmit-for-review raises KeyError if `nameRequest` or `foreignJurisdiction` is missing.

# decisions-ctx

# Business filings, tasks, comments, documents and COLIN sync (legal-api REST layer)

This part is the Flask REST resource layer of the LEAR legal-api (v1 and v2). It covers business info, filings, tasks, comments, documents, digital credentials, invoice and payment hand-off, COLIN synchronisation, and Minio storage.

## Inputs and outputs

- **Callers.** JWT-authenticated clients, plus internal callers (cron jobs, the COLIN service via `UserRoles.colin` / `COLIN_SVC_ROLE`, and aca-py webhooks).
- **Payment service (`PAYMENT_SVC_URL`).**
  - `POST` creates an invoice. The payload has `businessInfo` (identifier, corp_type, legal_name, mailing address) and `filingInfo` (filing id, filing types, optional folioNumber). `accountInfo` (routingSlip, bcolAccountNumber, datNumber) is added for STAFF_ROLE or SYSTEM_ROLE.
  - `GET` fetches payment status.
  - `DELETE /{payment_token}` cancels a payment.
  - `POST /{payment_token}/receipts` generates a receipt PDF.
- **Other services and stores.**
  - namex: `query_nr_number`, `validate_nr`, `update_nr_as_future_effective`.
  - Minio bucket `MINIO_BUCKET_BUSINESSES`.
  - The queue (publish for post-processing).
  - `AccountService`, `DocumentMetaService`, `VersionedBusinessDetailsService`.
  - aca-py (digital credentials).
- **Tables.** Filing, Business, RegistrationBootstrap, Comment, Document, ColinEventId, `colin_last_update`, Review / ReviewResult, DCConnection and issued credentials.

## Decisions

### Identifiers and temporary registrations
- An identifier starting `T` is a temporary registration, held as a filing plus RegistrationBootstrap.
- Temp registrations are looked up via `Filing.get_temp_reg_filing()` and `Business.find_by_internal_id()`.
- v2 business GET returns "No information on temp registrations" for them.
- Deleting one deregisters and deletes the bootstrap.
- `details_for_invoice` returns an empty list for `T` identifiers.
- An identifier starting `NR` is validated via namex in tasks. A failed validation returns 403.
- If the business is missing but the NR is valid, an incorporate to-do is created.

### Business GET and POST (v2)
- `slim=true` returns `business.json(slim=True)` plus `alternateNames`.
- Otherwise the full JSON is enriched with `warnings`, `allowable_actions`, and `submitter` / `lastModified` from `CoreFiling.get_most_recent_filing_json()`.
- `allowed_filings=true` adds `allowedFilings`.
- `account` adds `accountId` only if `jwt.has_one_of_roles([SYSTEM_ROLE, ACCOUNT_IDENTITY])` and the account matches an org.id.
- POST requires `filing_type` in `CoreFiling.NEW_BUSINESS_FILING_TYPES`, otherwise 400.
- A failed bootstrap creation or registration returns 503.

### Filing GET and listing
- `original=true` returns the raw filing. A PDF accept header returns a PDF report.
- v1 returns PDF for temp amalgamationApplication, incorporationApplication and continuationIn.
- A PENDING filing gets `isPaymentActionRequired` and `paymentMethod` from the payment service.
- CHANGE_REQUESTED, APPROVED or REJECTED with a review result adds `latestReviewComment`.
- The ledger lists only COMPLETED and PAID filings.
- Ledger `effective_date` must be ISO 8601 (`_is_valid_date`), and PDF requests are rejected.

### Filing save and completion
- `draft=true` skips validation and completion.
- `only_validate=true` returns only the validation result.
- Validation is skipped for historical or before-epoch filings.
- Validation runs against the rsbc_schemas `filing` schema (`_validate_filing_json`).
- Source defaults to `Filing.Source.LEAR`.
- For source COLIN:
  - `filing_date` is parsed from `header.date`.
  - `colinIds` become `ColinEventId` rows.
  - If `filing_date` is before the epoch filing's date, `transaction_id` is adopted and the filing is marked processed. Otherwise it is published to the queue.
- Otherwise `filing_date` is utcnow (except for change_requested filings in v2).
- `effective_date` comes from `header.effectiveDate`, else utcnow.
- HTML is sanitised in `specialResolution.resolution` and `correction.resolution`.
- Legal type comes from the filing JSON for incorporationApplication or registration (`_get_legal_type`), else from the business.
- For a new-business filing with an nrNumber whose effective_date is past the NR expiration, `namex.update_nr_as_future_effective` is called, the effective_date is set, and an invoice is created.
- `set_effective_date` sets futureEffectiveDate to tomorrow 00:01 for changeOfAddress when the business is not a COOP.
- `is_future_effective_filing` is true if header effectiveDate is later than now.

### Authorization
- `filing_type` is read from `header.name`, and the sub-type from `Filing.get_filings_sub_type`.
- The business state defaults to ACTIVE.
- The legal type comes from the business or the nameRequest.
- Both `authorized` and `is_allowed` must pass.
- The `add_comment` action gates comment POSTs (401 on failure).
- `view` gates documents.
- `edit` gates payment cancel.

### Invoice outcomes (`create_invoice`)
- A 200 or 201 response saves `payment_token`, `payment_status_code`, `payment_account` and `submitter_roles`. It returns `(isPaymentActionRequired, 201)`.
- A 400 saves the error type and returns 402.
- A connection error or any other status returns 402 without updating the filing.

### Deletion
- `filing.deletion_locked` blocks deletion.
- A draft alteration of a limited or unlimited company returns 401 ("must complete to become BC Benefit Company").
- A draft or pending filing also returns 401. Anything else returns 403.
- `delete_from_minio` removes files by filing type:

| Filing type | Keys removed |
|---|---|
| incorporationApplication / alteration | `rulesFileKey`, `memorandumFileKey` |
| dissolution | `affidavitFileKey` |
| courtOrder | `fileKey` |
| continuationIn | `foreignJurisdiction.affidavitFileKey`, `authorization.files[].fileKey` |

### Payment cancel
- A 200 or 202 from the payment service calls `filing.reset_filing_to_draft()` and returns 202.
- The request uses a 20s timeout. A connection error or timeout returns 500.

### Resubmit for review
- The Review is set to RESUBMITTED.
- `nr_number`, `identifier`, `completing_party` and `submission_date` are refreshed.
- The last ReviewResult is appended.
- `resubmit_filing_to_awaiting_review` is called.
- The completing party is the party whose role is `Completing Party`.

### Tasks
- Pending filings are those with status DRAFT, PENDING, PENDING_CORRECTION or ERROR.
- For a filing with `payment_status_code='CREATED'` and a `payment_token`, payment details are fetched.
  - v1 returns the sentinel `'pay_connection_error'` on failure.
  - v2 returns 503.
- Annual reports (AR) are due for each year from `last_ar_year` (or the founding year) up to the current year.
  - The start year is advanced by the count of incomplete AR filings.
  - An AR task is `enabled` only if there are no pending filings and the year equals the start year.
- ARs are excluded for SP and GP.
- A conversion filing is added when the `MISSING_REQUIRED_BUSINESS_INFO` warning is present and no conversion filing exists.

### Comments
- Business-level comments are those where `filing_id` is null. Filing comments are filtered by `filing_id`.
- A POST body `filingId` must match the URL, otherwise 400.
- `staff_id` comes from the JWT user.
- PUT, PATCH and DELETE on filing comments return 405.

### Documents (v2)
- The document list always includes `summary`.
- A COOP also gets `certifiedRules` and `certifiedMemorandum`, with file_key, name and the upload filing_date.
- `includedInResolution` is added from specialResolution filings where `rulesInResolution` or `memorandumInResolution` is true.
- A `legal_filing_name` starting `receipt` with a PDF request calls the payment receipts endpoint.
- A `file_key` is fetched from Minio only if `document.filing_id == filing.id`.
- The v2 Minio document DELETE proceeds only if `is_draft_filing` is true: the Document is not found, or its filing is DRAFT. Otherwise it returns 403.

### Digital credentials
- Revoke sets reason `SELF_REISSUANCE` when `reissue` is true, else `SELF_REVOCATION`. It returns 500 if aca-py returns None.
- Delete removes the credential exchange record first, if `credential_exchange_id` exists.
- Webhook routing is by `topic_name`:
  - `connections` updates `connection_id` and `connection_state`. `is_active` is set when the state is `active` or `completed`.
  - `issuer_cred_rev` sets `credential_revocation_id` and `revocation_registry_id` when the state is `issued`.
  - `issue_credential_v2_0` sets `date_of_issue` and `is_issued` when the state is `done`.

### COLIN sync (v1 `InternalFilings` / `ColinLastUpdate`, v2 `colin_sync.py`)
- Filings of type `lear_epoch` are skipped. So are corrections on COOP businesses.
- A correction is skipped if no ColinEventId is found for the corrected filing. Otherwise it carries `correctedColinId` (v2) or `correctedFilingColinId` (v1).
- Amalgamation applications (horizontal or vertical) pull legal name, parties, offices and share classes from the primary or holding business. Any exception skips that filing.
- A dissolution with sub-type `involuntary` adds batch `meta_data`.
- The v2 GET is paginated by `page` and `limit`, and returns `{filings, page, limit, pages, total}`.
- PATCH appends `ColinEventId` rows from `colinIds` and returns 202 (v1).
- `colin_id` GET returns `maxId`, or `colinId` if one is given. 404 is returned if nothing is found.
- `tax_ids` GET returns identifiers from `Business.get_all_by_no_tax_id()`. POST sets `tax_id` per identifier.

### Minio
- Signed PUT URLs last 5 minutes and signed GET URLs last 1 hour.
- Upload keys are UUID plus the original file extension.

## Main flows

- **Save filing.**
  1. `_validate_filing_json`.
  2. `_save_filing` creates or updates the Filing and sets dates and source.
  3. For COLIN, `_process_colin_filing`.
  4. Otherwise `complete_filing` creates the invoice.
  5. The filing JSON is returned.
- **Temp registration create.**
  1. Create the bootstrap.
  2. Register it.
  3. `saving_filings(identifier=bootstrap.identifier)`.
- **Upload.**
  1. `GET /documents/<file_name>/signatures` returns a pre-signed PUT URL.
  2. The client uploads to Minio.
  3. The filing references the key.

## Where to look first
- `resources/v2/business/business_filings/` has the filing retrieval, validation, save, invoice and resubmit modules.
- `resources/v2/business/business.py` has business GET and POST.
- `resources/v2/business/colin_sync.py` has the COLIN sync endpoints.
- `resources/v1/business/` has the legacy equivalents.
- `services/minio.py` has the storage wrapper.

## Hazards
1. **SQL injection and malformed error.** The COLIN `colin_id` POST (v1 and v2) interpolates `colin_id` into SQL via an f-string. Its error return is a malformed tuple, `{'message: failed…', 500}`.
2. **Payment failures swallowed.** On v1 and v2 filing GET the payment error is logged and the response is returned without payment fields. The v1 task sentinel `'pay_connection_error'` is a string, not an exception. Receipt generation returns the response unchanged. A failed `create_invoice` leaves the filing without payment fields.
3. **Errors reported as success.** The v1 and v2 filing-comment POST handlers map a `BusinessException` without a status code to 201 (v1) or 201/202 (v2). The broad `except` in `_process_colin_filing` masks queue, `set_processed` and save failures behind one generic message. The v1 PUT does `print(err)` only. `is_before_epoch_filing` returns False when the epoch filing count is not exactly 1.
4. **Partial or inconsistent state.**
   - A digital credential revoked at aca-py but whose local `save()` fails stays unrevoked locally.
   - A payment cancelled when `reset_filing_to_draft` then fails leaves the filing unreset.
   - The webhook re-raises, giving 500 and aca-py retries.
   - `POST /tax_ids` returns 201 even if some identifiers were missing.
   - Amalgamation enrichment failures silently drop the filing from the COLIN feed.
   - v1 PATCH saves once per colin_id.
5. **Crashes and permissive paths.**
   - `certifiedRules` is read when only a resolution exists (v2 documents), giving a KeyError.
   - Resubmit assumes `nameRequest`, `foreignJurisdiction` and `officer` fields exist.
   - `is_draft_filing` returns True for an unknown document key, so deletion is permitted.
   - Authorization on v2 business POST is commented out (issue #22143).
   - `suppress(Exception)` hides a failed bootstrap delete.
   - Minio `get_file` needs caller cleanup (close and release_conn).

# decisions-tight

# Business filings REST layer (legal-api v1/v2 resources, Minio service)

This part is the Flask API layer of the BC legal registry ("legal-api"). It handles business filings, comments, tasks, documents, digital credentials, and the internal endpoints that sync filings, event IDs and tax IDs with the external Colin system. It stores documents in Minio and talks to the payment service (`PAYMENT_SVC_URL`) and to namex. The v1 and v2 resources overlap. The v2 `colin_sync.py` and `colin_id`/`tax_ids` internal endpoints cover the same ground as v1's `InternalFilings` and `ColinLastUpdate`.

## Boundaries
- **In:** JWT-authenticated HTTP requests. Business identifiers starting with `T` mean temporary registrations. Colin service calls and cron jobs hit the internal endpoints, which need `COLIN_SVC_ROLE` or `UserRoles.colin`. aca-py posts webhooks.
- **Out:** The payment service gets `POST /…` for invoices and receipts (`{payment_token}/receipts`), `GET` for status and `DELETE {payment_token}` to cancel. Filings are published to a queue for post-processing. Minio gets file operations. The namex service gets NR lookups and `update_nr_as_future_effective`. Payment requests carry `businessInfo` and `filingInfo`, plus `accountInfo` for staff or system roles.

## Decisions
- **Temp registration (`T` prefix):** reads go through `CoreFiling` and `RegistrationBootstrap` (`Filing.get_temp_reg_filing`), not `Business`. Deleting one also deregisters and deletes the bootstrap. v2 `GET /business/T…` returns "No information on temp registrations".
- **Filing GET:**
  - `original=true` returns the raw filing.
  - A PDF accept header returns a PDF.
  - Status PENDING adds `isPaymentActionRequired` and `paymentMethod` from the payment service.
  - CHANGE_REQUESTED, APPROVED or REJECTED with a review result adds `latestReviewComment`.
  - The ledger list is COMPLETED and PAID only, and `effective_date` must be ISO 8601.
- **Filing PUT/POST (save):**
  - `draft=true` skips validation and completion.
  - `only_validate=true` returns validation only.
  - Source COLIN parses `colinIds` and the filing date from the header; any other source uses UTC now.
  - A COLIN filing dated before the single EPOCH filing adopts its `transaction_id` and is marked processed; otherwise it is published to the queue (`is_before_epoch_filing`).
  - Effective date comes from `header.effectiveDate` or now.
  - `specialResolution` and `correction` resolution text is HTML-sanitised.
  - A NR whose effective date falls past its expiration is extended through namex, then the invoice is created.
- **Delete:** blocked when `deletion_locked`. A draft alteration of a limited or unlimited company returns UNAUTHORIZED with "must complete to become BC Benefit Company". Draft or pending status returns UNAUTHORIZED. Anything else returns FORBIDDEN.
- **Invoice (`create_invoice`):**
  - 200/201 saves the payment fields and returns CREATED.
  - 400 saves the error type and returns PAYMENT_REQUIRED.
  - A connection error or any other status returns PAYMENT_REQUIRED without saving.
  - `set_effective_date` pushes changeOfAddress to the next day (one minute past midnight) unless the business is a COOP.
  - `details_for_invoice` returns an empty list for `T` identifiers.
  - `delete_from_minio` picks file keys by filing type.
- **Cancel payment:** a DELETE to the payment service answering OK or ACCEPTED triggers `reset_filing_to_draft`, and the response is 202. Connection errors return 500.
- **Tasks:**
  - Task statuses are DRAFT, PENDING, PENDING_CORRECTION and ERROR.
  - An NR identifier is validated, and a non-consumable NR returns 403.
  - A missing business with a valid NR creates an incorporate to-do.
  - v2 adds a conversion filing when the `MISSING_REQUIRED_BUSINESS_INFO` warning is present and no conversion filing exists.
  - Due annual reports are skipped for SP and GP.
  - v1 uses the `'pay_connection_error'` sentinel; v2 returns 503.
  - v1 enables an AR only when no pending filings exist and the year equals `start_year`.
- **Business GET v2:**
  - `slim=true` returns the slim JSON plus `alternateNames`.
  - `allowed_filings=true` adds `allowedFilings`.
  - `account` adds `accountId` only for SYSTEM_ROLE or ACCOUNT_IDENTITY callers, and only when it matches an org.
- **Business POST v2:** the filing type must be in `NEW_BUSINESS_FILING_TYPES`, otherwise BAD_REQUEST. Bootstrap create or register failure returns SERVICE_UNAVAILABLE. The authorization check is commented out (issue #22143).
- **Comments:**
  - Business comments are those with `filing_id` null. Filing comments require `add_comment` (401) and a URL/body `filingId` match (400).
  - v2 filing comments return 405 for PUT, PATCH and DELETE.
- **Documents:**
  - COOPs get `certifiedRules` and `certifiedMemorandum`, with `includedInResolution` when a `specialResolution` flags them.
  - `legal_filing_name` starting with `receipt` triggers a payment-service receipt.
  - `file_key` fetches from Minio only if `document.filing_id == filing.id`.
  - `is_draft_filing` gates deletion of Minio documents.
- **Digital credentials:**
  - Revoke uses SELF_REISSUANCE when `reissue` is true, otherwise SELF_REVOCATION.
  - Webhook topics are `connections` (active or completed), `issuer_cred_rev` (issued) and `issue_credential_v2_0` (done).
- **Colin sync:**
  - GET skips `lear_epoch` filings and COOP corrections.
  - A correction needs a `ColinEventId`, otherwise it is skipped.
  - Amalgamations (horizontal or vertical) pull data from the primary or holding business.
  - Involuntary dissolutions add batch `meta_data`.
  - v2 paginates with `page` and `limit`.
  - PATCH appends `ColinEventId` rows from `colinIds`.
  - `colin_last_update` holds `maxId`.
  - `tax_ids` GET lists businesses lacking a tax ID, excluding COOP, SP and GP.
- **Minio service:** signed PUT URLs last 5 minutes and GET URLs 1 hour. Keys are UUID plus the original extension, in bucket `MINIO_BUCKET_BUSINESSES`.

## Open first
- `resources/v2/business/business_filings/` holds filing retrieval, persistence, invoicing and resubmission.
- `resources/v1/business/business_filings.py` holds the v1 equivalents.
- `colin_sync.py` and the v1 internal filings resource hold the Colin sync.
- `services/minio.py` holds the storage wrapper.

## Hazards
- `POST colin_id` builds SQL by f-string (injection risk) and returns a malformed error tuple on failure.
- Payment-service failures are swallowed in most GET paths (payment fields silently absent). After a successful cancel, a failed `reset_filing_to_draft` leaves the payment cancelled but returns an error. Failed revocation bookkeeping leaves local and external state inconsistent.
- Broad excepts hide causes: `process_colin_filing`/`_process_colin_filing` report only "unable to publish for post processing". Comment POST handlers map BusinessException to a CREATED status when `status_code` is missing.
- `POST /internal/tax_ids` returns 201 even when some identifiers failed. Amalgamation enrichment failures silently skip the filing from the Colin feed.
- `is_before_epoch_filing` returns False unless there is exactly one epoch filing, so a missing or duplicate epoch record sends old COLIN filings to the queue. `is_draft_filing` returns True for unknown documents.

# core

The legal API's business-resource layer (v1 and v2) is a set of Flask REST resources for business filings, tasks, comments, documents, digital credentials and Minio storage. It also exposes internal endpoints that sync filings, event IDs and tax IDs with COLIN. It calls the payment service (`PAYMENT_SVC_URL`), namex, Minio and the filing queue, and it reads and writes Filing, Business, RegistrationBootstrap, Comment, Document and ColinEventId records.

## Contract
- **Identifiers:** a `T`-prefixed identifier means a temporary registration. It resolves through `Filing.get_temp_reg_filing` or `RegistrationBootstrap`, not `Business`.
- **Filing save:** PUT/POST validates against the `filing` schema, sets `filing_date` and `effective_date`, saves, then completes the filing. Completion either creates an invoice with the payment service (`create_invoice`) or, for COLIN-source filings, processes the filing through COLIN handling.
- **Payment calls:** these add `isPaymentActionRequired` and `paymentMethod` to GET and tasks responses. Cancelling a payment sends DELETE to `PAYMENT_SVC_URL/{payment_token}` and then resets the filing to DRAFT. Receipts are POSTed to `/{payment_token}/receipts`.
- **COLIN sync:** the `/internal/filings` endpoints return completed filings for COLIN, and PATCH records `colinIds` as `ColinEventId` rows. `colin_last_update` holds the max event ID. `/internal/tax_ids` pushes tax IDs into businesses. These endpoints require `COLIN_SVC_ROLE`/`UserRoles.colin`.

## Decisions
- **COLIN epoch:** a COLIN filing dated before the epoch filing reuses the epoch `transaction_id` and is marked processed. Otherwise it is published to the queue (`is_before_epoch_filing`, `process_colin_filing`).
- **COLIN export filter:** `lear_epoch` filings and COOP corrections are skipped. Other corrections get a corrected COLIN ID, or are skipped if none is found. Amalgamation filings are enriched from the primary or holding business.
- **Tasks:** pending filings are DRAFT, PENDING, PENDING_CORRECTION or ERROR. v2 also adds a conversion todo and skips annual reports for SP/GP. An annual-report todo is enabled only for the earliest due year, and only when no filings are pending.
- **Deletion:** `deletion_locked` blocks deletion. Draft deletes also remove Minio files by filing type (`delete_from_minio`). Documents may be deleted only if the filing is DRAFT (`is_draft_filing`).
- **Documents:** COOP businesses get certified rules and memorandum entries.

## Hazards
- The `colin_id` POST builds SQL with an f-string, so it is open to injection. Its error dict is also malformed.
- Broad `except` blocks hide failures. `process_colin_filing` masks queue and save errors. Comment POST failures can return 201. Webhook errors return 500, so aca-py retries.
- Payment connection errors are swallowed on some paths, so a filing proceeds without payment details. Revoking a credential can leave the local database out of step with the remote system.

## Open first
- `resources/v2/business/business_filings/business_filings.py`: the v2 filing flow, including invoice creation, resubmit and deletion lock.
- `resources/v2/business/colin_sync.py`: the COLIN export and sync endpoints.
- `resources/v2/business/business_tasks.py`: the pending-task list.
- `resources/v1/business/business_filings.py`: the legacy v1 filing resource.

# core-scaled

# Business REST resources, legal-api (v1 and v2)

This part is the Flask HTTP layer for business data in the legal API. It exposes filings, comments, tasks, documents, digital credentials, Colin sync and Minio file storage. It hands work to the Filing, Business, Comment and ColinEventId models, the payment service (`PAYMENT_SVC_URL`), namex, Minio, the post-save queue and aca-py. v1 and v2 overlap, and v2 is the newer version.

## Filings (v1 `business_filings.py`; v2 `business_filings/` modules)

**Contract**
- GET, PUT/POST and DELETE take an identifier, where a `T` prefix means a temporary registration (bootstrap). Query flags are `original`, `draft` and `only_validate`. The `accountId` header is passed to completion.
- GET returns filing JSON, or a PDF for some types. It adds document metadata via DocumentMetaService and, for PENDING filings, `isPaymentActionRequired` and `paymentMethod`.
- Saving writes a Filing and publishes it to the queue. It also creates an invoice by POSTing to the payment service.
- Cancel payment: DELETE to `PAYMENT_SVC_URL/{token}`, then `reset_filing_to_draft`. It returns 202.
- Document and receipt endpoints read from Minio. Receipts are POSTed to `PAYMENT_SVC_URL/{token}/receipts`.

**Decisions**
- A draft skips validation and completion.
- A COLIN-source filing keeps its own filing date and `colinIds`. If its date is before the epoch filing, it adopts the epoch transaction id and is marked processed. Otherwise it is published to the queue.
- A new-business filing whose effective date is past the Name Request (NR) expiry triggers `namex.update_nr_as_future_effective`.
- Invoice `accountInfo` is added only for staff or system roles.
- Deletion is blocked by `deletion_locked`, with the status code chosen by the lock rules.
- Deleting a filing also deletes its Minio files, by filing type.

**Hazards**
- Payment connection errors are swallowed, so a filing continues without payment details.
- The broad excepts in `process_colin_filing` / `_process_colin_filing` mask real errors.
- `is_before_epoch_filing` returns False unless exactly one epoch filing exists.
- A cancelled payment is not rolled back if `reset_filing_to_draft` then fails.

## Comments (`filing_comments.py`, `business_comments.py`)

- Filing comments are GET and POST per filing. POST requires `add_comment`, and the body `filingId` must match the URL.
- Business comments are those with `filing_id` null.
- Hazard: on a save failure (BusinessException) the POST handlers can return a success status (v1: `err.status_code or CREATED`; v2: CREATED/ACCEPTED).

## Tasks (`business_tasks.py`)

- Returns a list of `{task, order, enabled}`: incomplete filings (DRAFT, PENDING, PENDING_CORRECTION, ERROR), a conversion task and due annual reports (not for SP or GP in v2).
- For an NR identifier it validates via namex and creates an incorporate to-do.
- v1 returns the string sentinel `'pay_connection_error'` on payment failure. v2 returns 503.

## Colin sync (v1 internal filings; v2 `colin_sync.py`)

- Serves cron jobs and the Colin service.
- GET returns completed filings enriched for Colin. It skips `lear_epoch` and corrections on COOP businesses. It adds the corrected Colin id, and for amalgamations it adds primary or holding business data.
- PATCH appends `colinIds` as ColinEventId records. The colin_last_update GET/POST and the tax-id sync need the Colin role or `UserRoles.colin`.
- Hazards: the POST `colin_id` uses f-string SQL, which allows injection, and its error tuple is malformed. Amalgamation enrichment failures silently skip the filing. POST `tax_ids` returns 201 even when some updates failed.

## Business info and digital credentials (`v2/business/business.py`, `business_digital_credentials.py`)

- GET business returns JSON, or slim JSON, with warnings and allowed actions. POST creates a bootstrap and registers it.
- Credential revoke, delete and aca-py webhook endpoints update the local credential state.
- Hazards: revoke is not transactional with the remote revocation. Webhook exceptions are re-raised, which causes aca-py retries.

## Documents (`v2/document.py`, `services/minio.py`, business documents)

- Pre-signed PUT URLs are valid for 5 minutes and GET URLs for 1 hour.
- `is_draft_filing` allows deletion when the Document is not found.
- The `get_file` stream must be closed by the caller.

## Open first

- `v2/business/business_filings/business_filings.py`: the core filing logic.
- `v2/business/colin_sync.py`: Colin sync.
- `v2/business/business_tasks.py`: the to-do list.
- `services/minio.py`: file storage.

# core#2

# Legal API business resources (v1 and v2) and Minio wrapper

REST layer of the legal-api Flask app for business records, filings, comments, tasks, documents and Colin sync. It hands work to the payment service (`PAYMENT_SVC_URL`), namex (name requests), the post-filing queue, Minio storage, the aca-py digital-credentials service, and Colin through internal endpoints.

## Contract
- **Filings** (v1 `business_filings.py`; v2 `business_filings/` and `business_documents.py`): GET returns a filing or a ledger of COMPLETED and PAID filings. PUT/POST validate against the `filing` schema, save a `Filing`, then complete it. DELETE removes the filing and its Minio files. Identifiers starting with `T` are temporary registrations, backed by `RegistrationBootstrap` and `CoreFiling`.
- **Invoicing**: `create_invoice` POSTs to the payment service. It stores `payment_token` and the status on success, and returns 402 on failure.
- **Colin sync** (`colin_sync.py`, v1 internal filings): serves cron jobs and the Colin service. GET returns completed filings in Colin format. PATCH takes `{colinIds: [...]}` and writes `ColinEventId` rows. `colin_last_update` holds the max event id. `/internal/tax_ids` syncs tax ids.
- **Tasks**: returns `{task, order, enabled}` items.
- **Documents**: `document.py` handles Minio signed PUT URLs and file get/delete. `services/minio.py` wraps put/get/delete and signed URLs against the businesses bucket.
- **Comments**: business-level (`filing_id` null) and filing-level. POST needs `add_comment` authorization.

## Decisions
- COLIN-source filings dated before the EPOCH filing take its `transaction_id` and are marked processed. Others are published to the queue.
- A draft or pending filing cannot be deleted. `deletion_locked` blocks deletion.
- Colin export skips `lear_epoch` filings and COOP corrections. Amalgamation filings get data from the primary or holding business.
- Tasks come from DRAFT, PENDING, PENDING_CORRECTION and ERROR filings, plus annual reports (not for SP or GP).
- Future-effective rules: `set_effective_date` and the namex NR-expiry update.

## Hazards
- Broad `except` blocks hide failures. `_process_colin_filing`, `process_colin_filing` and the v1 PUT handler do this. Payment lookups on GET and in tasks are logged and ignored, or return a string sentinel.
- `colin_id` is interpolated into SQL with an f-string in both the v1 and v2 POST handlers (SQL injection).
- Comment POST maps save errors to a 201 status. Remote and local state can diverge, for example credential revocation and cancelled payments.

## Open first
- `v2/business/business_filings/business_filings.py`: filing service, invoice, completion and authorization.
- `v1/business/business_filings.py`: legacy filing CRUD and internal Colin endpoints.
- `v2/business/colin_sync.py`: Colin export and event ids.
- `v2/business/business_tasks.py`: task list building.

# core-states

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

# core-states#2

# Business filings, tasks, comments, documents and COLIN sync (legal-api REST resources, v1 and v2)

Flask resources for a business registry's legal API. They create, read, cancel and delete filings, list pending tasks, manage comments and documents, and sync with COLIN (the legacy registry). They call the payment service (`PAYMENT_SVC_URL`), namex (name requests), Minio storage, a queue for post-processing, and the digital-credential agent (aca-py).

## Contract
- **Filings**: the client sends filing JSON (`header.name`, `header.accountId`, `header.effectiveDate`, `header.source`, `header.colinIds`). The API returns filing JSON, or a PDF report or receipt.
- **Temp registrations**: an identifier starting with `T` means a temporary registration. It resolves through `RegistrationBootstrap` and `Filing.temp_reg` instead of `Business`.
- **Payment service**: `create_invoice` POSTs to it. `GET .../{payment_token}` supplies `isPaymentActionRequired` and `paymentMethod`. `DELETE .../{token}` cancels a payment. `POST .../{token}/receipts` produces a receipt PDF.
- **COLIN sync** (internal, `COLIN_SVC_ROLE`/`UserRoles.colin`):
  - `GET /internal/filings` returns completed filings enriched with `filingId`, dates and business details.
  - `PATCH /internal/filings/{id}` takes `{colinIds:[...]}` and appends `ColinEventId` rows.
  - `colin_id` GET/POST read and write the `colin_last_update` table (`maxId`).
  - `/internal/tax_ids` GET lists businesses without a tax id. POST takes `{identifier: tax_id}`.
- **Minio**: signed PUT URL (5 min), signed GET URL (1 h), and put/get/delete by key. Keys are UUID plus the file extension.
- **Digital credentials**: revoke, delete, and an aca-py webhook routed by `topic_name`.

## Decisions
- `_save_filing` (v1) / the v2 filing save: creates or updates a Filing, with the source defaulting to LEAR. A COLIN source keeps the header date. Otherwise `filing_date` is utcnow, except for filings in `change_requested_status`. `effective_date` comes from the header or utcnow.
- `process_colin_filing`: if `filing_date` is before the EPOCH filing, it copies the transaction id and calls `set_processed`. Otherwise it publishes to the queue.
- `draft=true` skips validation and completion. `only_validate=true` returns just the validation result. Validation uses the `filing` schema.
- `create_invoice`: 200/201 saves the payment token and status and returns CREATED. 400 returns PAYMENT_REQUIRED and saves the error type. Connection errors return PAYMENT_REQUIRED without saving.
- `set_effective_date`: for a changeOfAddress on a non-COOP business, the effective date becomes tomorrow at 00:01.
- A new-business filing whose effective date is past the NR expiry calls `namex.update_nr_as_future_effective`.
- Cancel payment (v2 `business_filings.py`): requires edit authorization (401). It DELETEs the payment, and on OK/ACCEPTED calls `reset_filing_to_draft()`. Returns 202.
- DELETE filing (v1): blocked when `deletion_locked` (UNAUTHORIZED for a draft/pending status or a draft alteration, else FORBIDDEN). Otherwise `delete_from_minio` removes the files and a `T` bootstrap is deleted.
- Resubmit for review: sets `Review` to RESUBMITTED, copies the last `ReviewResult` with a new submission date, and calls `resubmit_filing_to_awaiting_review`.
- `get_tasks`: collects DRAFT/PENDING/PENDING_CORRECTION/ERROR filings, a conversion filing when the missing-business-info warning is present, and due annual reports (excluded for SP/GP). An NR that fails validation returns 403. A payment connection error returns 503 (v2).
- `colin_sync` GET skips `lear_epoch` and COOP corrections. A correction needs a `ColinEventId` or it is skipped. Amalgamation filings are filled from the primary/holding business. Involuntary dissolutions get `meta_data`.
- Comments: POST needs `add_comment` authorization (401) and `filingId` equal to the URL id (400). `staff_id` comes from the JWT user. v2 business comments are those with `filing_id IS NULL`.
- Documents: the list depends on the filing. A COOP business adds `certifiedRules` and `certifiedMemorandum`. `is_draft_filing` gates Minio deletion.
- `revoke_credential`: the reason is SELF_REISSUANCE or SELF_REVOCATION. The remote revoke runs first, then `is_revoked=True` is saved.
- v2 business POST: only types in `CoreFiling.NEW_BUSINESS_FILING_TYPES` are accepted. It creates and registers a bootstrap, and deletes the bootstrap if registration fails.

## Hazards
- SQL injection: the `colin_last_update` POST (v1 `InternalFilings`/`ColinLastUpdate` and v2 `colin_id`) interpolates `colin_id` into SQL with an f-string. Its error return is also a malformed tuple.
- Failures are masked: `process_colin_filing` catches every exception, so a queue or save failure becomes a generic message. Payment-service connection errors in GET are only logged. The tax_ids POST returns 201 even when identifiers failed. Amalgamation enrichment errors silently skip the filing. Comment-save `BusinessException` handlers can return a CREATED/ACCEPTED status.
- Partial state: a payment cancel or a credential revoke can succeed remotely and then fail locally. This leaves the payment cancelled but the filing not reset, or the credential revoked remotely but not flagged. Webhook exceptions return 500, so aca-py retries.

## Open first
- `v2/business/business_filings/business_filings.py` and its sibling service modules: the core filing flow (retrieval, validation, completion, invoices, resubmit, deletion locks).
- `v2/business/colin_sync.py`: COLIN export, the event-id/tax-id PATCH and POST endpoints, and the SQL injection.
- `v2/business/business_tasks.py`: the to-do list.
- `services/minio.py`: storage wrapper. `v2/document.py` and `v2/business/business_documents.py` call it.
