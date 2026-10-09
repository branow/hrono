<!-- leaf 486, 12 members -->

This is a set of condensed summaries of Flask/Flask-RESTX API resource modules from a BC (Province of British Columbia) legal-filings service, nearly all Apache 2.0 licensed (2019). The modules cover business lookup and creation, tasks (to-dos), comments, and documents, plus the filings routes.

## Groupings

**Business lookup and creation (`BusinessResource`)**
- **GET `/<identifier>`**:
  - A 'T'-prefixed identifier means a temp registration. One summary says it is rejected. The v2 summary says it returns 200 with "No information on temp registrations".
  - A missing business returns 404, and an unauthorized caller gets 401.
  - `?slim=true` returns lightweight JSON plus an `alternateNames` array.
  - The default response is full JSON plus warnings, `allowable_actions`, and submitter/lastModified taken from the most recent filing.
  - `?allowed_filings=true` calls `get_allowed(state, legal_type, jwt)`.
  - `?account=<id>` is limited to SYSTEM_ROLE or ACCOUNT_IDENTITY. It sets `accountId` if the business is affiliated with that account.
- **POST**: Checks the filing type against `Filing.FILINGS` (incorporationApplication or registration, or `CoreFiling.NEW_BUSINESS_FILING_TYPES` in v2). It calls `RegistrationBootstrapService.create_bootstrap()`, then `register_bootstrap()`, and returns the filing via `ListFilingResource.put()`. Errors are BAD_REQUEST for an invalid type and SERVICE_UNAVAILABLE if bootstrap creation fails.

**Tasks (`/<identifier>/tasks`, `TaskListResource`)**
- **Name Request (NR) handling**: An NR identifier is queried with `namex.query_nr_number()` and checked with `namex.validate_nr()`. If it isn't consumable, the response is 403. A business-less NR gets an incorporate-NR to-do.
- **`construct_task_list(business)`**:
  - It fetches filings in DRAFT, PENDING, PENDING_CORRECTION and ERROR status.
  - It checks payment status through `PAYMENT_SVC_URL`.
  - It computes the next annual report (AR) year and backfills missing AR years up to the current year, using `business.get_ar_dates()`.
  - The older version also adds a conversion to-do and skips AR for SP/GP.
- **Helpers**: `create_todo`, `create_incorporate_nr_todo`, and `create_conversion_filing_todo` (in the older version only).

**Comments (`/comments`)**
Three modules share one pattern. Each has GET (all comments, or one by `comment_id`) and POST. POST runs `_basic_checks`, then `authorize(action=['add_comment'])`, then `validate(json_input)`. It then saves a Comment with `staff_id` from `User.get_or_create_user_by_jwt(g.jwt_oidc_token_info)` and `timestamp=datetime.utcnow()`. It returns 201 CREATED.
- **Business-level** (`/<identifier>/comments`): Selects comments where `filing_id IS NULL`, and saves with `business_id`.
- **Filing-level** (`/<identifier>/filings/<filing_id>/comments`): Filters by `filing_id`, and `_basic_checks` confirms the filing belongs to the business. The newer variant makes PUT, PATCH and DELETE return 405. A comment's `filingId` must match the URL.

**Documents**
- **Business documents** (`/<identifier>/documents[/<document_name>]`):
  - Requires 'view' authorization.
  - Returns a document list, or a PDF or JSON for a named document.
  - For COOP (`CP`) businesses, it adds certified rules and memorandum, drawn from specialResolution filings via `rulesInResolution` and `memorandumInResolution`.
- **Filing documents** (`/<identifier>/filings/<filing_id>/documents`, `/{legal_filing_name}`, `/static/{file_key}`):
  - Returns a document list or a PDF.
  - Receipts come from the payment service and are only available for certain filing statuses.
  - Files are served from `MinioService` or Filing storage.

**Filings (`/<identifier>/filings[/<filing_id>]`, `ListFilingResource`)**
- GET returns a single filing or the ledger.
- POST and PUT save or modify a filing. They handle draft-only versus complete filings, historical COLIN and pre-epoch filings, and resubmission from the change-requested state.
- DELETE removes a filing unless it is locked, and deregisters the bootstrap for a temp registration.

**Cross-cutting pattern:** Temp registrations (T-prefixed identifiers) take a different lookup path from regular businesses. They use `RegistrationBootstrap`, `Filing.get_temp_reg_filing`, or `filing_model.business_id` instead of `Business.find_by_identifier`.

## Caution:
- POST silently deletes the bootstrap when registration fails (`with suppress(Exception): bootstrap.delete()`), which masks errors.
- Business-level comments filter on `filing_id IS NULL`, so they exclude filing-level comments. `_basic_checks` reads the JSON body, which is None on GET. The user comes from `g.jwt_oidc_token_info`, which requires a JWT context.
- `# noqa: I001` comments override import-order rules, and a final `# noqa: I003` suggests route-decorator formatting conflicts with line-counting linters.
- **Tasks:**
  - NR validation runs twice (at the start and again on append).
  - The payment API call blocks list retrieval on a timeout, and nothing in it is async.
  - `last_ar_year` can be None, so `founding_date` is the fallback.
  - AR rules differ for co-ops and corps, and `business.get_ar_dates()` handles that.
  - In the older version, a payment connection failure returns the bare string `'pay_connection_error'`. The caller checks it by string equality, which is fragile.
- **Filing comments:**
  - `filing_id` must match in the URL and the JSON body.
  - `staff_id` comes from the JWT.
  - The timestamp is set server-side in UTC.
  - A filing that belongs to a different business returns 404.
  - The authorization action `['add_comment']` is matched by string.
  - Temp registrations use `Filing.get_temp_reg_filing` and then `Business.find_by_internal_id()`.
  - The exception handler returns the exception's status code, or defaults to CREATED for POST and ACCEPTED otherwise.
- **Business search v2:**
  - A business can be affiliated with several accounts, so the code checks that `q_account` matches one of them, not that it is the only one.
  - Temp registrations silently return 200 instead of being treated as valid businesses.
- **Business comments:** T-prefixed identifiers go through `FilingModel`, not `Business.find_by_identifier`, and use different lookup logic.
- **Business documents:** Lookups use the `DocumentType.COOP_RULES` and `COOP_MEMORANDUM` enums. The code checks `rulesInResolution` as a boolean, not for existence. It uses the walrus operator for conditional assignment.
- **Filing documents:**
  - Temp registrations bypass the business lookup and use `filing_model.business_id` directly.
  - The receipt `effective_date` is sent as an empty string if it equals `filing_date`.
  - Minio file ownership isn't validated. Only the `filing_id` match is checked.
- **Filings:**
  - Conditional paths in `saving_filings` are complex.
  - The "epoch" filing concept isn't defined here.
  - Locked filings can't be deleted.

## Members

- lear: legal-api/src/legal_api/resources/v1/business/business.py
- lear: legal-api/src/legal_api/resources/v1/business/business_comments.py
- lear: legal-api/src/legal_api/resources/v1/business/business_filings.py
- lear: legal-api/src/legal_api/resources/v1/business/business_tasks.py
- lear: legal-api/src/legal_api/resources/v1/business/filing_comments.py
- lear: legal-api/src/legal_api/resources/v2/business/business.py
- lear: legal-api/src/legal_api/resources/v2/business/business_comments.py
- lear: legal-api/src/legal_api/resources/v2/business/business_documents.py
- lear: legal-api/src/legal_api/resources/v2/business/business_filings/business_documents.py
- lear: legal-api/src/legal_api/resources/v2/business/business_filings/business_filings.py
- lear: legal-api/src/legal_api/resources/v2/business/business_tasks.py
- lear: legal-api/src/legal_api/resources/v2/business/filing_comments.py
