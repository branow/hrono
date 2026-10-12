## `lear/queue_services/entity-pay/src/entity_pay/worker.py` (section 0)

### today

NATS payment queue handler. Flow: extract payment token JSON → validate (paymentToken.corpTypeCode must exist in DB) → find filing by payment ID (retry 5× with 0.2s sleep) → check status. If COMPLETED: set payment_completion_date, publish email message, publish filing if not future-effective. If TRANSACTION_FAILED or unrecognized: log/skip. OperationalError raised (DB down). FilingException absorbed (message removed). Other exceptions logged to Sentry and message removed.

GOTCHA: Retry loop waits 200ms between attempts; if filing still missing after 5 tries, raises FilingException (silently consumed, not re-queued). Flask-SQLAlchemy required because NATS enforces one-at-a-time + await blocks async.

### behaviour

**Purpose:** NATS Streaming worker that processes payment notifications and advances filings through their lifecycle based on payment status.

**Comes in:** NATS messages with JSON payment tokens containing `paymentToken.id`, `paymentToken.statusCode`, and `paymentToken.corpTypeCode`.

**Goes out:** 
- Updates filing `payment_completion_date` in database when payment completes
- Publishes email notification via NATS when payment succeeds
- Publishes filing to NATS for processing if no effective date or effective date is in the past
- Logs errors to Sentry

**Enforces:**
- Rejects messages missing `paymentToken`, `corpTypeCode`, or unknown `corpTypeCode`
- Retries up to 5 times (0.2s intervals) to fetch the filing for a payment—handles timing where payment token arrives before filing assignment
- Skips reprocessing filings already in COMPLETED status (logs warning)
- Silently returns (no-op) for TRANSACTION_FAILED status
- Publishes email and filing only for COMPLETED payment status
- Raises QueueException for unknown status codes
- Removes messages from queue for FilingException and most errors; re-raises OperationalError to prevent queue drainage

**GOTCHA:** TRANSACTION_FAILED payments are silently ignored (TODO note indicates incomplete design). Filing retrieval delay is a workaround for async timing and not guaranteed to succeed after 5 retries.

### purpose-first

Processes payment completion messages from NATS Streaming queue and applies confirmed payments to their business filings; publishes filing for processing and notification email when ready.

Entry point is async callback `cb_subscription_handler`. Receives NATS message containing JSON with paymentToken dict including corpTypeCode, id (payment ID), and statusCode. Validates message has valid paymentToken with existing corpTypeCode. If invalid, skips message.

For valid messages, `process_payment` looks up Filing by payment ID with retry loop (up to 5 times, 0.2s sleep between attempts) to handle race condition where payment token arrives before filing is created. If filing already has status COMPLETED, logs warning and returns. If paymentToken statusCode is TRANSACTION_FAILED, returns without action. If statusCode is COMPLETED, sets filing.payment_completion_date to UTC now, commits to DB, publishes email notification, then publishes filing to processing queue if it has no effective_date or effective_date is now/past.

Unknown statusCode raises QueueException. Caught exceptions: OperationalError (database) re-raises to keep message on queue for retry; FilingException absorbs (removes message, logs to Sentry in prod); all other exceptions absorbed (message removed, logged to Sentry).

GOTCHA: payment tokens can arrive before their filings are created, requiring the retry loop. GOTCHA: TRANSACTION_FAILED payments are silently ignored (todo comment suggests improvement needed). GOTCHA: email and filing publish failures don't prevent status update — failures only logged to Sentry for manual review. GOTCHA: requires NATS Streaming's one-message-at-a-time constraint and synchronous AWAIT; Flask-SQLAlchemy would need rework for async.

### what-how

WHAT: Worker for the entity-pay service that processes payment tokens from a NATS Streaming queue and updates filing statuses accordingly; entry point is `cb_subscription_handler`.

HOW: Receives a NATS message containing a payment token JSON, extracts it, validates that it has `paymentToken`, `corpTypeCode` fields and the corp type exists. If valid, calls `process_payment`: retrieves the Filing by payment ID (retrying up to 5 times with 0.2s sleeps between attempts), checks filing status and payment status code, then: if filing is already COMPLETED, logs a warning and returns; if status is TRANSACTION_FAILED, returns silently; if status is COMPLETED, sets `payment_completion_date` to current UTC time, commits, publishes an email message to the subject in `APP_CONFIG.EMAIL_PUBLISH_OPTIONS['subject']`, and if `effective_date` is not set or is in the past, publishes the filing to `APP_CONFIG.FILER_PUBLISH_OPTIONS['subject']` (failures in email/filing publication are logged but don't fail the handler); any other status raises QueueException. Error handling in the callback: OperationalError is re-raised; FilingException is logged (in prod only) and absorbed; all other exceptions are logged and absorbed. Uses Flask-SQLAlchemy within app context; processes one message at a time due to NATS Streaming constraints.

GOTCHA: Retries finding the filing 5 times to handle eventual consistency where payment token arrives before filing creation completes.
GOTCHA: Filing already COMPLETED is not an error — logs as warning for investigation.
GOTCHA: TRANSACTION_FAILED status returns silently without marking as error or requeuing.
GOTCHA: Email and filing publication exceptions are caught and logged but do not fail payment processing.
GOTCHA: OperationalError is re-raised to not drain the queue; FilingException and other exceptions are absorbed to remove message from queue.

### purpose-lean

Worker module that processes payment notifications from NATS Streaming queue and updates filing status; entry point is **cb_subscription_handler**.

Receives messages containing payment tokens, extracts and validates them, then processes payment status. Validates token contains `paymentToken` and `corpTypeCode` fields with valid CorpType. Retries finding the Filing by payment ID up to 5 times with 0.2s delays before failing.

On payment processing:
- If filing status is `COMPLETED`: logs warning and returns
- If `statusCode` is `TRANSACTION_FAILED`: returns silently
- If `statusCode` matches Filing.Status.`COMPLETED`: sets `payment_completion_date` to UTC now, commits DB, publishes email message and filing message (unless future effective_date)
- Otherwise: raises QueueException for unknown status

Exception handling:
- `OperationalError`: re-raises (preserves message on queue to prevent drain during DB outage)
- `FilingException`: absorbs (filing not found—don't retry)
- All other exceptions: absorbs and logs (message removed from queue)

GOTCHA: NATS Streaming requires one-message-at-a-time processing; AWAIT on default loop runs synchronously—Flask-SQLAlchemy model usage depends on these constraints.

GOTCHA: Email and filing publication failures are captured to Sentry but don't prevent message completion; message still removed from queue.

GOTCHA: FilingException errors only logged to Sentry when ENVIRONMENT is `prod`.

### purpose-budget

Processes payment status messages from NATS queue, updating filing records and triggering document processing in a BC business registry.

Extracts and validates payment token JSON with corpTypeCode. Polls for linked filing by payment ID (up to 5 times, 0.2s intervals)—token may queue before database assignment. Skips if filing already COMPLETED or payment status is TRANSACTION_FAILED. On payment COMPLETED: records payment_completion_date, publishes email notification, publishes filing if not future-dated. Error handling: re-raises OperationalError to pause queue; swallows FilingException (missing filing) silently; swallows other errors after logging to Sentry.

GOTCHA: Email and filing publish errors are logged but don't halt execution; message still consumed. GOTCHA: Polling with sleep instead of true async-await makes execution synchronous despite async function signature.

## `lear/queue_services/business-pay/src/business_pay/resources/pay_filer.py` (section 0)

### today

BSD 3-Clause License (https://opensource.org/license/bsd-3-clause/). Flask endpoint processes GCP cloud events for payment filings: validates JWT, extracts payment info, checks `filing_type in ["continuationIn"]` to decide between staff review or filer queue publish, then publishes to emailer. Sets filing to PAID, creates Review for certain types. Returns 200 OK for empty messages, already-paid filings, and invalid corp_types (MHR, BTR), preventing queue retries.

GOTCHA: Empty or already-paid messages return 200 OK (removed from queue) rather than retrying; only puts back on queue if filing not found (404), as payment token might not exist yet.

### behaviour

**Purpose**: Processes payment completion cloud events and updates filing status, triggering downstream review or filing tasks and email notifications.

**What comes in**:
- HTTP POST requests containing cloud event messages (JWT-validated)
- Cloud event data with payment token (id, status_code, filing_identifier, corp_type_code)

**What goes out**:
- HTTP 200 (processed or ignored), 404 (filing not yet found), or 403 (JWT invalid)
- Queue messages to "filer" topic (subject from `FILER_PUBLISH_OPTIONS`)
- Queue messages to "emailer" topic (subject from `EMAIL_PUBLISH_OPTIONS`)
- Database updates: Filing record marked with payment_completion_date, payment_status_code="COMPLETED", status="PAID"
- Review record created (for continuationIn filings only)

**Rules and states**:
- Ignores empty/malformed messages, corp_type_codes "MHR" or "BTR", and payments with status != "COMPLETED"
- If filing already has payment_completion_date, removes from queue (duplicate)
- If filing not found: removes if (filing_identifier is None AND corp_type_code is "BC"), else retries (404)
- If filing_type is "continuationIn", creates staff Review with filing data, nr_number, identifier, completing_party name, and status AWAITING_REVIEW; filing status set to AWAITING_REVIEW.value
- If filing_type is not continuationIn and effective_date ≤ payment_completion_date, publishes to filer queue
- Always publishes to emailer queue after filing is marked paid
- Cloud event type must be "bc.registry.payment"; data keys converted from camelCase to snake_case

**GOTCHA**: Exceptions in `publish_to_filer` and `publish_to_emailer` are silently suppressed; filer publication does not trigger if effective_date > payment_completion_date (future-dated filings skipped).

### purpose-first

Applies completed payments to filing records and triggers downstream processing via queues, receiving GCP Cloud Events containing payment tokens.

**Input:** Cloud event (type `bc.registry.payment`) with fields: `id`, `statusCode`, `filingIdentifier`, `corpTypeCode`.

**Output:** Updates Filing record (sets `payment_completion_date`, `payment_status_code`, `status=PAID`); for `filing_type == "continuationIn"` creates Review record with `status=AWAITING_REVIEW`; publishes to `FILER_PUBLISH_OPTIONS` subject (if effective_date ≤ payment_completion_date and not continuationIn) and `EMAIL_PUBLISH_OPTIONS` subject.

**Main flow:** Extract PaymentToken from cloud event, verify `status_code == "COMPLETED"` and reject if `corp_type_code` in `["MHR", "BTR"]`. Look up Filing by payment token id; if not found, return 404 (retry) unless BC corp type with null `filing_identifier` (return 200). If Filing already has `payment_completion_date`, return 200. Mark Filing PAID with current UTC time. For continuationIn filings, create Review extracting `nr_number`, `identifier`, and completing party name from `filing_json["filing"][filing_type]["parties"]`; otherwise publish filing message to filer. Always publish email message. Returns 200 (drop from queue) for: empty/malformed cloud events, incomplete payment info, rejected corp types, already-processed filings, or certain not-found conditions.

**GOTCHA:** Cloud event parsing condition `if not (ce := ...) and not isinstance(ce, SimpleCloudEvent)` always evaluates the isinstance part as False when ce is falsy, making the second clause redundant. **GOTCHA:** For `continuationIn` filings, filer queue message is never published—only staff review is created. **GOTCHA:** Publish failures after filing marked PAID are silently swallowed via `suppress(Exception)`.

### what-how

WHAT: Queue worker endpoint that processes payment completion cloud events to mark filings as PAID and orchestrate downstream filer and emailer queue publications, with optional staff review creation for certain filing types.

HOW:
POST handler validates JWT and cloud event, extracts PaymentToken (from events with type "bc.registry.payment"), queries Filing by payment_token.id, updates filing with payment_completion_date and status PAID. If filing.filing_type is "continuationIn", calls create_staff_review() to record a Review; else publishes filing message to filer queue if effective_date <= payment_completion_date. Then publishes to emailer queue regardless. Converts cloud event data from camelCase to snake_case for PaymentToken initialization. Extracts completing_party from parties list by matching role "Completing Party". Returns 200 OK for invalid events, corp_type_code in ["MHR", "BTR"], already-paid filings, and corp_type_code "BC" without filing_identifier; returns 404 for missing filings (queued for retry).

GOTCHA: publish_to_filer and publish_to_emailer silently suppress exceptions—failures won't surface to queue. Filing already marked paid skips reprocessing. corp_type_code "BC" with filing_identifier == None returns 200 (removed) instead of 404 (retry), differing from other missing-filing behavior.

### purpose-lean

Worker endpoint for the business-pay queue service that processes completed payment cloud events and orchestrates filing workflow (staff review or filer publication, then email notification).

**Main flow (worker() POST endpoint):**
1. Receive cloud event from GCP queue
2. Verify JWT; reject invalid with 403 FORBIDDEN
3. Extract PaymentToken from cloud event (type "bc.registry.payment", keys converted camelCase→snake_case)
4. Skip if status_code != "COMPLETED" or corp_type_code in ["MHR", "BTR"]; return 200 OK
5. Look up Filing by payment_token.id; if not found:
   - Return 404 NOT_FOUND (retry on queue) EXCEPT
   - If filing_identifier==None and corp_type_code=="BC": return 200 OK (remove)
6. If filing.payment_completion_date already set: return 200 OK (idempotent)
7. Mark filing PAID: set payment_completion_date=now(timezone.utc), payment_status_code="COMPLETED", status=Filing.Status.PAID
8. If filing.filing_type in ["continuationIn"]: create_staff_review(filing); else publish_to_filer(filing, payment_token)
9. publish_to_emailer(filing)
10. Return 200 OK

**Supporting functions:**
- PaymentToken dataclass: id, status_code, filing_identifier, corp_type_code
- create_staff_review(filing): Create Review with status=ReviewStatus.AWAITING_REVIEW; populate nr_number, identifier from filing_json; extract completing_party from parties list (first with roleType=="Completing Party"); set filing.status=Filing.Status.AWAITING_REVIEW.value
- get_completing_party(parties): Concatenate firstName + middleName (if present) + lastName for first party with roleType=="Completing Party"; return None if not found
- publish_to_filer(filing, payment_token): Publish to FILER_PUBLISH_OPTIONS[subject] only if filing.effective_date <= filing.payment_completion_date; exceptions suppressed
- publish_to_emailer(filing): Publish to EMAIL_PUBLISH_OPTIONS[subject]; exceptions suppressed
- get_payment_token(ce): Return PaymentToken from ce.data if ce.type=="bc.registry.payment"; return None otherwise
- dict_keys_to_snake_case(d): Regex pattern `(?<!^)(?=[A-Z])` converts keys to snake_case

**Queue removal conditions (200 OK):** Empty message, invalid JWT, no payment info, status_code not COMPLETED, corp_type_code in [MHR, BTR], already paid, or BOGUS filing.
**Queue retry (404 NOT_FOUND):** Filing not found (except BOGUS case).

GOTCHA: BOGUS filings—filing_identifier==None and corp_type_code=="BC"—are silently removed from queue rather than retried, contrary to the "put back on queue if no filing" default.

GOTCHA: Exceptions in publish_to_filer() and publish_to_emailer() are suppressed; queue publish failures do not propagate or signal retry.

GOTCHA: Email queue message publishes even if filer publishing fails—no transactional ordering.

### purpose-budget

Processes payment-completion cloud events to mark filings as PAID and enqueue downstream filing and email actions.

Receives SimpleCloudEvent with PaymentToken (id, status_code, filing_identifier, corp_type_code). Updates Filing with payment_completion_date, payment_status_code="COMPLETED", status=PAID. If filing_type is "continuationIn", creates Review with nr_number, identifier, completing_party; else publishes to FILER_PUBLISH_OPTIONS queue if effective_date ≤ payment_completion_date. Always publishes to EMAIL_PUBLISH_OPTIONS queue.

GOTCHA: Returns 200 (queue removal) for empty requests, invalid cloud events, non-COMPLETED payments, corp_type_code "MHR"/"BTR", already-paid filings, and bogus filings (filing_identifier=None with corp_type="BC"). Returns 404 for missing Filing (retry). Publish exceptions silently suppressed.

## `lear/jobs/future-effective-filings/file_future_effective.py` (section 0)

### today

**Future Effective Date Service**: Flask + asyncio worker that polls legal-api for filings with future effective dates and publishes them to a NATS queue.

Setup: logging config first, env vars (NATS_SERVERS split by comma, NATS_CLUSTER_ID, NATS_FILER_SUBJECT), random 0x58-bit client_id for STAN, Sentry integration with ERROR event level.

- `create_app(run_mode)`: Flask factory, config from `config.CONFIGURATION[run_mode]`, optional Sentry init from SENTRY_DSN
- `get_bearer_token(app, timeout)`: POST to ACCOUNT_SVC_AUTH_URL with client_credentials grant, returns access_token or None on exception
- `get_filing_ids(app)`: GET `{LEGAL_API_URL}/internal/filings/future_effective` with Bearer token; raises on non-200 status
- `run(loop, app)`: connects ServiceWorker, calls get_filing_ids(), publishes each filing_id to subject as `{'filing': {'id': filing_id}}`
- `__main__`: creates app, runs async event_loop.run_until_complete(run)

GOTCHA: Broad exception catching throughout (returns None instead of raising); walrus operator `:=` in `if not (filing_ids := get_filing_ids(application))` — idiomatic Python 3.8+ but unfamiliar to some.

### behaviour

**Purpose**: Job service that discovers filings with future effective dates and queues them for entity processing.

**Incoming**:
- Fetches filing IDs from `{LEGAL_API_URL}/internal/filings/future_effective` with a bearer token obtained from `ACCOUNT_SVC_AUTH_URL` via client credentials grant.
- Environment variables: NATS servers, cluster ID, timeouts, queue subject (`NATS_FILER_SUBJECT`), auth credentials and endpoints, Sentry DSN.
- Logs config from `logging.conf`.

**Outgoing**:
- Publishes NATS messages to `NATS_FILER_SUBJECT` with payload `{'filing': {'id': <filing_id>}}` for each retrieved filing ID.
- Logs debug messages (queue success) and error messages (failures); sends errors to Sentry if `SENTRY_DSN` is set.

**Rules & behavior**:
- Runs once on startup: connects to NATS/STAN, fetches filing IDs, publishes each as a message, then exits.
- Bearer token obtained via POST with client credentials; any exception during token request is caught and returns None.
- Raises exception if legal-api response is falsy or status code is not 200.
- Catches and logs exceptions during the main run loop.
- STAN client ID randomly generated per invocation using `random.SystemRandom().getrandbits(0x58)`.
- Boilerplate: Apache 2.0 license, logging setup, Sentry integration, Flask factory pattern.

GOTCHA: `get_bearer_token` silently returns None on any exception; the downstream auth header becomes `'Bearer None'` if token acquisition fails, causing silent auth failures in the subsequent legal-api call.

GOTCHA: Empty filing list from the API is treated as no-op success (no messages published, no error raised).

GOTCHA: STAN client ID regenerates per run, breaking message ordering and idempotency if the service runs repeatedly.

### purpose-first

Picks up filings marked for future effective dates from the legal API and places them on the entity filer queue for processing.

Queries the legal API endpoint `/internal/filings/future_effective` for filing IDs using a Bearer token obtained from the account service. For each ID received, publishes a message `{'filing': {'id': filing_id}}` to the NATS subject from `NATS_FILER_SUBJECT`. Connects to NATS and STAN (streaming) queues using connection options from environment variables: `NATS_SERVERS`, `NATS_CONNECT_TIMEOUT`, `NATS_CLUSTER_ID`. Authentication credentials come from `ACCOUNT_SVC_AUTH_URL`, `ACCOUNT_SVC_CLIENT_ID`, `ACCOUNT_SVC_CLIENT_SECRET`, and `LEGAL_API_URL`; timeout is `ACCOUNT_SVC_TIMEOUT`. The main flow: `create_app()` initializes Flask with Sentry error tracking; `get_bearer_token()` posts to the auth service with client credentials; `get_filing_ids()` fetches future filings using the token; `run()` connects the queue service and publishes each filing to the subject.

GOTCHA: `get_bearer_token()` silently returns `None` on exception, but this `None` token is not checked before use in the Authorization header in `get_filing_ids()`.
GOTCHA: `get_filing_ids()` raises a bare `Exception` if the legal API response is not 200, with no error message beyond logging.
GOTCHA: `run()` only logs debug messages; errors are swallowed unless logging level is set to DEBUG.

### what-how

WHAT: Job service that retrieves filings with future effective dates from the legal API and publishes them to a NATS queue for the entity filer to process.

HOW: Loads environment config and sets up Flask with optional Sentry error tracking via `create_app()`. `get_bearer_token()` retrieves an OAuth2 client credentials token from `ACCOUNT_SVC_AUTH_URL` using `client_id` and `client_secret`. `get_filing_ids()` calls `{LEGAL_API_URL}/internal/filings/future_effective` with the bearer token, raising an exception if the response status is not 200. The `run()` async function creates a `ServiceWorker` connected to NATS with cluster config from `default_nats_options` and `default_stan_options`, retrieves filing IDs, and for each one publishes a message `{'filing': {'id': filing_id}}` to the subject from `NATS_FILER_SUBJECT`. Entry point runs the async loop. Boilerplate: logging setup, imports, environment loading.

GOTCHA: `get_bearer_token()` catches all exceptions and returns `None` silently; `get_filing_ids()` does not check for `None` and will crash when trying to add it to headers. `get_filing_ids()` raises bare `Exception` on any error. The walrus operator `if not (filing_ids := ...)` treats an empty list as "no filings found" and skips the loop; an empty response is indistinguishable from failure.

### purpose-lean

This job polls the legal-api for filings with future effective dates and publishes them to the entity filer queue for processing.

**Flow:** Flask app connects to NATS/STAN queue service → calls `get_filing_ids()` to fetch from `{LEGAL_API_URL}/internal/filings/future_effective` using a bearer token → for each filing_id received, publishes `{'filing': {'id': filing_id}}` to the subject named in `NATS_FILER_SUBJECT`.

**Inputs:** Legal-api endpoint, ACCOUNT_SVC_AUTH_URL with client credentials (ACCOUNT_SVC_CLIENT_ID, ACCOUNT_SVC_CLIENT_SECRET), NATS cluster (NATS_SERVERS, NATS_CLUSTER_ID).

**Outputs:** Messages to `subject` (NATS).

**Configuration:** Environment variables load from .env and config module; Sentry DSN optional. NATS options: `name='default_future_filing_job'`, `connect_timeout=NATS_CONNECT_TIMEOUT`. STAN options: `cluster_id=NATS_CLUSTER_ID`, `client_id=_<random 88-bit int>`.

**GOTCHA:** `get_bearer_token()` silently returns None on any exception; `get_filing_ids()` passes this None-or-token directly into Authorization header without validation, then raises bare `Exception` if response status != 200.

**GOTCHA:** `get_filing_ids()` raises `Exception` without message or specifics on API errors.

**GOTCHA:** Empty filing_id list logs "No filings found" and continues (no-op), not an error.

### purpose-budget

A batch job for the British Columbia entity filer service that queues filings with future effective dates for downstream processing.

Authenticates using `ACCOUNT_SVC_CLIENT_ID` and `ACCOUNT_SVC_CLIENT_SECRET` at `ACCOUNT_SVC_AUTH_URL`, queries `{LEGAL_API_URL}/internal/filings/future_effective` for filing IDs, then publishes each as `{'filing': {'id': filing_id}}` to the NATS subject in `NATS_FILER_SUBJECT`. Uses `ServiceWorker` to manage NATS/STAN connections; request timeout is `ACCOUNT_SVC_TIMEOUT`.

GOTCHA: `get_bearer_token()` returns None silently on error, causing downstream failures without context.
GOTCHA: `get_filing_ids()` raises bare `Exception` on non-200 API response; error detail appears only in logs.

## `lear/queue_services/business-pay/tests/integration/test_nats_stan.py` (section 0)

### today

BSD 3-Clause License header. Async test suite for NATS/STAN messaging. `test_connect()`: creates NATS client, connects STAN with "test-cluster" cluster name and client_id, subscribes to `entity_queue.main` (queue: `entity_durable_name.main`, durable: same). Publishes filing message from `create_filing_msg(identifier=12345)`, waits 2s for callback, asserts 1 message received and identifier in decoded data. `test_fixture_entity_stan()`: same but uses pre-built entity_stan fixture. `get_stan()` fixture: connects NATS (with both sync and async connects called), returns STAN client.
GOTCHA: `get_stan()` calls `await nc.connect(io_loop=event_loop)` then `await nc.connect()` again—second call likely redundant or overwrites. Timeout hardcoded to 2 seconds; slow systems may fail.

### behaviour

**Purpose:** Test suite for NATS/STAN (streaming message broker) connection setup and message publish/subscribe flow.

**What comes in:**
- NATS and STAN client fixtures with event loop and client ID
- create_filing_msg() utility that builds queue messages
- Fixtures: stan_server, future, event_loop, client_id, entity_stan

**What goes out:**
- NATS and STAN clients establish connections to "test-cluster"
- Publishes JSON-encoded filing messages to subjects like `entity_queue.main`
- Subscribes to queue groups with durable names (format: `entity_durable_name.{subject}`)
- Emits received messages to callbacks
- Closes connections after each test

**Behaviour:**
- `test_connect`: Creates NATS and STAN clients manually, subscribes with callback, publishes a filing message with identifier 12345, waits up to 2s for delivery, asserts one message received and identifier appears in payload
- `test_fixture_entity_stan`: Same flow but reuses an `entity_stan` fixture instead of manual setup
- `get_stan` fixture: Connects NATS and STAN clients (both initialized separately), returns STAN client
- Callbacks append received messages to a list and set a future when first message arrives

**GOTCHA:** `get_stan` fixture has duplicate `await nc.connect()` call (one with loop parameter, one without); generic bare `Exception` catch with print instead of logging.

### purpose-first

Integration test suite for NATS/STAN message queue connections and publish-subscribe patterns in the business-pay service.

Tests verify that NATS and STAN clients can connect to a test cluster, subscribe to entity queue subjects with durable subscriptions, and receive published messages. Both `test_connect` and `test_fixture_entity_stan` follow the same flow: subscribe to `entity_queue.main` with queue name and durable name derived from `entity_durable_name.main`, publish a filing message containing an identifier via `create_filing_msg(12345)`, wait up to 2 seconds for the callback to fire, then assert exactly one message arrived and contains the identifier string in its decoded payload.

The `get_stan` fixture establishes a NATS client connected with `io_loop`, then a STAN client connected to `"test-cluster"` with the provided `client_id`. Subscription callbacks append received messages to a list and resolve a future when the first message arrives.

GOTCHA: Exception handling in the wait-for-message block catches all exceptions but only prints and continues, masking timeout or connection failures without affecting assertions.

### what-how

WHAT: Integration test suite for NATS/STAN queue system, verifying that the message broker connects, subscribes to topics with durable names and queue groups, publishes messages, and delivers them via callbacks.

HOW: `test_connect` creates NATS and STAN clients, connects to "test-cluster" with a client_id, subscribes to subject "entity_queue.main" with queue group "entity_durable_name.main" and durable name, publishes a filing message (from `create_filing_msg(identifier)`) to that subject, waits up to 2 seconds for the callback to receive it, then asserts exactly 1 message arrived containing the identifier string. `test_fixture_entity_stan` repeats the pattern using an `entity_stan` fixture (tuple where index [1] is the STAN client). The `get_stan` fixture creates and connects both clients.

GOTCHA: `get_stan` fixture calls `nc.connect()` twice — once with `io_loop=event_loop` then again without parameters — which may cause unintended side effects.

### purpose-lean

Integration test suite for NATS/STAN messaging setup in the business-pay queue service; verifies client connection, pub/sub flow, and message receipt via callbacks.

**test_connect**: Establishes NATS and STAN clients; subscribes to `entity_queue.main` with durable queue `entity_durable_name.main`; publishes a filing message (via `create_filing_msg(identifier)`) to that subject; waits up to 2 seconds for callback to fire and collect the message; asserts exactly one message received with the identifier present in decoded payload.

**test_fixture_entity_stan**: Same flow as test_connect but uses the `entity_stan` fixture (returns STAN client at index [1]) instead of creating clients directly.

**get_stan** fixture: Connects a NATS client with provided event_loop, then connects a STAN client to `"test-cluster"` with that NATS client; returns STAN client.

GOTCHA: `get_stan` fixture calls `nc.connect(io_loop=event_loop)` followed by `nc.connect()` without arguments on the same client — likely unintended duplicate.

GOTCHA: Exception handler in both tests catches all exceptions but only prints; failures would not propagate clearly.

### purpose-budget

Integration test validating NATS Streaming message queue connectivity for the business-pay service.

Both test_connect and test_fixture_entity_stan verify the same flow: connect to NATS and STAN ("test-cluster"), subscribe to entity_queue.main with queue entity_durable_name.main and durable name of the same value, publish a filing message created via create_filing_msg(identifier=12345), and assert exactly one message arrives in the callback within 2 seconds containing the identifier. The get_stan fixture creates and returns a STAN client connected to NATS.

GOTCHA: get_stan fixture calls await nc.connect() twice—once with io_loop parameter, once bare—second may override first. GOTCHA: Exception handler in asyncio.wait_for only prints errors; timeout does not fail the test.

## `lear/queue_services/business-pay/tests/integration/test_queue_publish.py` (section 0)

### today

**Queue Services test suite** – NATS/STAN integration tests (Apache 2.0, BC)

Tests: NATS_SERVERS/NATS_CLIENT_NAME/NATS_CLUSTER_ID/NATS_FILER_SUBJECT/NATS_QUEUE config present; QueueService connect (w/ idempotency check); teardown; error/disconnect/close/reconnect callbacks log WARNING level.

GOTCHA: queue.connect() called twice to verify idempotency—second call must not fail or re-establish connection.

### behaviour

**Integration tests for NATS Streaming queue service.**

Tests QueueService's connection lifecycle and error handling with a live STAN server.

**Incoming**: Flask app with NATS config (servers, client name, cluster ID, subject, queue name); stan_server fixture; log capture; exception objects.

**Outgoing**: QueueService state assertions (is_connected, is_closed); WARNING-level log messages (error details, disconnect/close/reconnect events).

**Behavior**:
- `test_nats_stan_config`: Verifies NATS_SERVERS, NATS_CLIENT_NAME, NATS_CLUSTER_ID, NATS_FILER_SUBJECT, NATS_QUEUE are set.
- `test_queue_connect_to_nats`: Connects to NATS; calling connect() twice remains idempotent; close() sets is_closed.
- `test_queue_flask_teardown`: teardown(exception=None) closes the connection.
- `test_error_callback`: on_error(e) logs exception message at WARNING.
- `test_on_disconnect_callback`: on_disconnect() logs "Disconnected from NATS" at WARNING.
- `test_on_close_callback`: on_close() logs "Closed connection to NATS" at WARNING.
- `test_on_reconnect_callback`: on_reconnect() after connect() logs "Reconnected to NATS" at WARNING.

**GOTCHA**: Commented-out assertion on line checking queue.nats.connected_url.netloc suggests incomplete or disabled test coverage for connection URL validation.

### purpose-first

Integration test suite for the Queue Publication Service, verifying NATS/STAN connectivity and QueueService lifecycle callbacks.

Validates configuration: NATS_SERVERS, NATS_CLIENT_NAME, NATS_CLUSTER_ID, NATS_FILER_SUBJECT, and NATS_QUEUE must be set in app config.

QueueService lifecycle with stan_server fixture: connect() transitions is_connected to true; calling connect() twice remains idempotent; close() sets is_closed to true. Flask teardown(exception=None) also sets is_closed.

Callback logging at WARNING level: on_error(e=Exception) logs the exception message; on_disconnect() logs "Disconnected from NATS"; on_close() logs "Closed connection to NATS"; on_reconnect() logs "Reconnected to NATS".

Uses pytest.mark.asyncio for async test methods and caplog to assert log output contains expected strings.

### what-how

WHAT: Test suite for the QueueService integration with NATS/STAN message queue, validating configuration, connection lifecycle, and event callbacks.

HOW: Five tests validate the integration layer. test_nats_stan_config asserts presence of required config keys (NATS_SERVERS, NATS_CLIENT_NAME, NATS_CLUSTER_ID, NATS_FILER_SUBJECT, NATS_QUEUE). test_queue_connect_to_nats creates a QueueService, verifies is_connected is false initially, calls connect() and asserts is_connected becomes true, checks that calling connect() again is idempotent, then calls close() and asserts is_closed. test_queue_flask_teardown creates a QueueService and calls teardown(exception=None) to verify is_closed. Four callback tests (test_error_callback, test_on_disconnect_callback, test_on_close_callback, test_on_reconnect_callback) each create a QueueService, invoke an async callback method (on_error, on_disconnect, on_close, on_reconnect), and assert specific warning-level log messages appear: error messages for on_error, "Disconnected from NATS" for on_disconnect, "Closed connection to NATS" for on_close, "Reconnected to NATS" for on_reconnect. Tests use pytest async fixtures (app, stan_server, caplog).

GOTCHA: Line 92 contains commented-out assertion `assert queue.nats.connected_url.netloc in caplog.text`, suggesting incomplete or disabled validation.

### purpose-lean

Integration test suite for the QueueService's NATS/STAN queue connectivity and lifecycle, verifying configuration, connection management, and error-handling callbacks.

**Configuration & Connection:**
- `test_nats_stan_config`: Asserts app.config contains NATS_SERVERS, NATS_CLIENT_NAME, NATS_CLUSTER_ID, NATS_FILER_SUBJECT, NATS_QUEUE
- `test_queue_connect_to_nats`: QueueService(app).is_connected starts false → connect() sets true → reconnect() stays true → close() sets is_closed true
- `test_queue_flask_teardown`: QueueService.teardown(exception=None) sets is_closed true

**Callbacks:**
- `test_error_callback`: on_error(e=Exception) logs the exception message at WARNING level
- `test_on_disconnect_callback`: on_disconnect() logs "Disconnected from NATS" at WARNING level
- `test_on_close_callback`: on_close() logs "Closed connection to NATS" at WARNING level
- `test_on_reconnect_callback`: on_reconnect() logs "Reconnected to NATS" at WARNING level

GOTCHA: connect() called twice shows idempotent behavior (second call returns immediately with is_connected still true).

### purpose-budget

Integration test suite for the NATS/STAN Queue Publication Service, validating QueueService configuration, connection lifecycle, and error-handling callbacks.

Tests verify: required config keys (NATS_SERVERS, NATS_CLIENT_NAME, NATS_CLUSTER_ID, NATS_FILER_SUBJECT, NATS_QUEUE) are present; connect() sets is_connected flag and is idempotent (calling twice succeeds); close() sets is_closed flag; teardown() closes the queue; callbacks log specific warnings—on_error logs the exception message, on_disconnect logs "Disconnected from NATS", on_close logs "Closed connection to NATS", on_reconnect logs "Reconnected to NATS". Tests use pytest async, app and stan_server fixtures, and caplog for log verification.

## `lear/queue_services/business-pay/tests/conftest.py` (section 0)

### today

BSD 3-Clause License (© 2024 Province of British Columbia).

**Test fixtures module:**
- `create_test_db()` – creates PostgreSQL test database via SQLAlchemy; params: user, password, database, host (localhost), port (1521)
- `load_sql_file()` – loads *.sql files from `./data/` directory into test DB using pg8000
- `drop_test_db()` – terminates all connections and drops database
- `not_raises(exception)` – context manager asserting exception is NOT raised
- `@pytest.fixture(scope="session")` – `app()` (TEST config), `client()` (Flask test client), `db()` (initializes, yields, cleanup)
- `@pytest.fixture(scope="function")` – `client_id()` (random 0x58-bit ID), `session()` (nested savepoint with rollback)
- `@pytest_asyncio.fixture` – `stan()` (NATS/STAN connection, client_id scoped)

GOTCHA: `session()` fixture uses savepoint-restart pattern to allow test rollback without explicit commit; `stan()` doesn't await close (yield commented out), leaving connections open.

### behaviour

**Purpose**: Pytest configuration for the business-pay service, providing test setup, database lifecycle, and messaging fixtures.

**Comes in**:
- Environment variables: `TEST_NATS_DOCKER`, `SQLALCHEMY_DATABASE_URI`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`, `DB_HOST`, `DB_PORT`, `DATABASE_TEST_NAME`
- SQL files from `tests/data/*.sql` (loaded into test database)
- PostgreSQL connection via pg8000
- NATS/STAN cluster for messaging

**Goes out**:
- Fixtures: `app` (Flask test app in TEST mode), `client` (Flask test client), `client_id` (random unique ID per test), `db` (session-wide initialized database), `session` (function-scoped database session with automatic rollback), `stan_server`, `stan` (async NATS/STAN connection)
- Creates/drops test databases via PostgreSQL
- Loads SQL schema into test database

**Rules**:
- Database set to UTC timezone; `app`, `client`, `db` are session-scoped (shared across all tests); `session` is function-scoped with SAVEPOINT isolation
- Each test's session automatically rolls back on exit—`session.commit()` is optional and will be undone
- `not_raises()` helper inverts pytest.raises, asserting an exception does NOT occur

**GOTCHA**: NATS/STAN cleanup code (yield + close calls) is commented out—connections never close. `create_test_db` and `drop_test_db` construct raw SQL with f-strings, risking injection if database name is user-supplied. NATS startup uses `time.sleep(2)` instead of proper wait logic.

### purpose-first

Test configuration and fixtures for the business-pay queue service pytest suite.

Provides session and function-scoped fixtures for Flask app, test database, and async message queue connections. `create_test_db` and `drop_test_db` manage Postgres test database lifecycle using sqlalchemy and pg8000. `load_sql_file` executes SQL fixture files from the `data/` directory into the test database. `session` fixture establishes per-test database transactions with savepoint-based rollback isolation: each test begins a nested transaction, and the `after_transaction_end` listener restarts it after rollback, ensuring `session.commit()` calls in tests don't persist beyond the test. `db` fixture creates the database once per session, sets UTC timezone, loads SQL files, then drops it at teardown. `stan` async fixture creates a NATS connection and Stan client scoped to each test function, subscribed to events.

GOTCHA: `stan()` fixture's cleanup code (close calls) is commented out—connections will not be closed. GOTCHA: `load_sql_file` ignores the `database_uri` parameter and builds its own connection from app config. GOTCHA: `drop_test_db` silently suppresses all exceptions during cleanup.

### what-how

WHAT: Pytest configuration and fixtures for the business-pay service, providing database setup, Flask app instances, and NATS streaming connections for the test suite.

HOW: Loads test configuration via get_named_config("testing"), creates a Flask app in TEST mode via create_app(), and manages a postgres test database: create_test_db() connects with the provided user credentials and database_uri, load_sql_file() executes .sql schema files from the data/ directory, and drop_test_db() drops the database after tests. The db fixture establishes a session-wide database with UTC timezone and runs SQL setup scripts; the session fixture provides function-scoped sessions with transaction rollback—each test gets a SAVEPOINT via SQLAlchemy event listeners on after_transaction_end that restarts if the test did not commit. The stan fixture creates async NATS and NATS Streaming connections with cluster_name "test-cluster" and unique client_id per test function. Helper utilities: not_raises() asserts exceptions are NOT thrown; client_id generates unique random identifiers via SystemRandom().getrandbits(0x58).

GOTCHA: The stan fixture's yield/close statements are commented out—connections never close, leaking resources across tests.

GOTCHA: The session fixture's after_transaction_end listener accesses protected attributes trans._parent.nested to detect whether the test committed, and restarts the savepoint if not—fragile mechanism relying on SQLAlchemy internals.

### purpose-lean

Pytest configuration and fixtures for the business-pay queue service test suite, providing Flask app, database, session, and messaging client isolation for tests.

**Test database lifecycle:**
- `create_test_db()` / `drop_test_db()`: Create and destroy PostgreSQL test database (via sqlalchemy engine with AUTOCOMMIT isolation) using `SQLALCHEMY_DATABASE_URI`, `DATABASE_TEST_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`, `DB_HOST`, `DB_PORT`
- `load_sql_file()`: Load SQL scripts from `tests/data/*.sql` using `pg8000.native.Connection`, then execute via `.run(buffer)`

**Fixtures:**
- `app`: Session-scoped Flask app from `create_app(get_named_config("testing"))`
- `client`: Session-scoped Flask test client
- `client_id`: Random 64-bit hex string `client-{id}`
- `db`: Session-scoped; creates test database, runs `SET TIME ZONE 'UTC'`, loads SQL files, yields `_db`, then drops database
- `session`: Function-scoped SQLAlchemy session bound to single connection with transaction and nested savepoint; after each test, `expire_all()` and `rollback()` any commits
- `stan`: Async function-scoped; connects Nats and Stan clients to `cluster_name="test-cluster"` with client_id, subscribes, returns Stan client; requires `TEST_NATS_DOCKER` env var to start docker service
- `not_raises()`: Context manager asserting exception NOT raised (inverse of `pytest.raises`)

GOTCHA: `stan` fixture does not await close of Stan and Nats clients (cleanup code commented out).
GOTCHA: `drop_test_db` silently suppresses all exceptions (sqlalchemy.exc.ProgrammingError, pg8000.Error, Exception).
GOTCHA: `session` fixture inspects protected members `trans._parent.nested` and calls `db._make_scoped_session()`.
GOTCHA: `load_sql_file` reads from `pg8000.native.Connection` constructor parameters, ignoring passed-in `con` argument.

### purpose-budget

Pytest configuration and fixtures for the business-pay queue service tests: sets up isolated test database, Flask app, and async messaging connections.

**Inputs/Outputs**: Fixture parameters are Flask app config, test database credentials; fixtures yield configured app, database session, and NATS/Stan client. SQL files from `tests/data/*.sql` are loaded into the test database.

**Key Flow**: `app` fixture creates a Flask test instance; `db` fixture creates a PostgreSQL test database (with `CREATE DATABASE`), loads schema SQL files, and drops the database after the session. `session` fixture wraps each test in a transaction with a savepoint, using a SQLAlchemy event listener that rolls back the transaction after the test completes, ensuring test isolation. `stan` fixture connects async NATS and Stan clients with a cluster name of `"test-cluster"`.

**GOTCHA**: `session` fixture's `after_transaction_end` listener checks `trans.nested and not trans._parent.nested` to detect the test's savepoint level; this fragile check must match savepoint nesting exactly or tests may not clean up correctly. GOTCHA: `stan` fixture yields without closing connections (cleanup code is commented out). GOTCHA: `not_raises()` uses `pytest.fail()` directly instead of raising `AssertionError`, bypassing normal pytest assertion machinery.

## `lear/queue_services/business-pay/tests/conftest.py` (section 1)

### today

Async pytest fixtures for NATS/Stan testing.

**entity_stan (async, function scope):**
Connects NATS and Stan (streaming) client to cluster via `os.getenv("STAN_CLUSTER_NAME")` (required, raises ValueError if missing). Yields (nc, sc); closes both after test.

**future (function scope):**
Returns asyncio.Future(loop=event_loop) for test management.

**create_mock_coro:**
Returns helper `_create_mock_patch_coro(to_patch=None)` that creates a mocker.Mock with async wrapper. Optionally monkeypatches target. Returns (mock, async_coro_fn).

GOTCHA: entity_stan requires STAN_CLUSTER_NAME env var at runtime (not fixture param)—missing var fails fixture, not test. Commented-out event_loop code suggests it's moved to pytest-asyncio plugin config (don't manually pass event_loop). create_mock_coro's monkeypatch is optional—caller decides whether to patch.

### behaviour

Provides test fixtures for NATS/Stan messaging and async coroutine mocking.

**entity_stan** (async, function-scoped): Establishes NATS and Stan streaming connections for each test. Requires STAN_CLUSTER_NAME environment variable; raises ValueError if missing. Yields (nc, sc) connection pair and closes both after test.

**future** (function-scoped): Returns an asyncio.Future bound to the test's event_loop.

**create_mock_coro**: Returns _create_mock_patch_coro factory function. Takes optional to_patch path parameter. Creates mock object and async coroutine _coro wrapping it. If to_patch provided, patches the target path with monkeypatch.setattr to _coro; returns (mock, _coro) tuple.

GOTCHA: entity_stan has a commented-out `return sc` statement above the active `yield nc, sc`, signaling incomplete refactor from return-style to cleanup-fixture yield-style.

### purpose-first

Test fixtures and utilities for business-pay queue service tests, providing async NATS/STAN broker connections, futures, and mock coroutine factories for test functions.

`entity_stan` (async fixture, function scope): connects to NATS broker and STAN cluster (cluster name from STAN_CLUSTER_NAME environment variable and client_id parameter), yields (nc, sc) tuple, closes both on cleanup. Raises ValueError if STAN_CLUSTER_NAME is missing.

`future` (fixture, function scope): returns asyncio.Future bound to event_loop for test coordination.

`create_mock_coro` (fixture): returns factory function that builds (mock object, async coroutine) pairs where the coroutine wraps the mock; optionally monkeypatches the coroutine to a target via to_patch parameter.

GOTCHA: entity_stan yields both NATS and STAN connections (nc, sc) despite fixture name suggesting STAN only.

GOTCHA: create_mock_coro's monkeypatch line `monkeypatch.setattr(to_patch, _coro)` uses incorrect syntax—monkeypatch.setattr expects (target, name, value) or a dotted string path, not this form.

### what-how

WHAT: Test fixtures for NATS Streaming connections and async mocking in business-pay service tests.

HOW: `entity_stan` (async, function scope) connects to NATS Streaming by reading `STAN_CLUSTER_NAME` environment variable, creating `Nats()` and `Stan()` instances bound to event_loop and client_id, yielding the `(nc, sc)` tuple, then closing both on teardown. `future` (function scope) returns an `asyncio.Future` bound to event_loop for managing async test state. `create_mock_coro` (factory) accepts optional `to_patch` path and returns `(mock, _coro)` where `_coro` is an async wrapper around the mock, optionally patched via monkeypatch to the given path.

GOTCHA: `entity_stan` raises ValueError if `STAN_CLUSTER_NAME` environment variable is not set. `create_mock_coro` conditionally patches only when `to_patch` is provided.

### purpose-lean

Pytest fixtures for business-pay service tests: provides NATS/Stan messaging connections, asyncio utilities, and mock coroutine helpers.

**entity_stan** (async, function scope): Creates NATS and Stan connections for each test. Connects NATS via `io_loop`, reads `STAN_CLUSTER_NAME` env var (raises `ValueError` if missing), connects Stan with cluster name and `client_id`, yields tuple `(nc, sc)`, closes both after test runs. GOTCHA: yields both connections in sequence, so teardown closes them in reverse order.

**future** (function scope): Creates and returns an `asyncio.Future` bound to `event_loop` for test management.

**create_mock_coro**: Returns a factory function `_create_mock_patch_coro(to_patch=None)` that creates a mock object and wraps it in an async coroutine. If `to_patch` is provided (str path), patches it via `monkeypatch.setattr`; otherwise returns mock and coro unpached. GOTCHA: `to_patch` parameter optional — patching is conditional, not applied by default.

### purpose-budget

Test fixture configuration for business-pay queue service tests.

entity_stan (async, function-scoped) connects to NATS and STAN using STAN_CLUSTER_NAME env var and client_id parameter, yields both connections, closes them after test. future fixture returns an asyncio.Future for test synchronization. create_mock_coro factory fixture accepts optional to_patch parameter, returns a Mock and an async coroutine that calls the mock; patches the coroutine into to_patch location if provided.

GOTCHA: entity_stan requires STAN_CLUSTER_NAME env var and raises ValueError if missing, blocking any test that uses this fixture.

## `lear/queue_services/entity-pay/src/entity_pay/config.py` (section 0)

### today

Apache 2.0 licensed config module loading environment variables. Maps config names ('production'/'staging'/'default' → ProdConfig, 'testing' → TestConfig, 'development' → DevConfig) via get_named_config(). Base _Config sets DATABASE_URI `postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{int(DB_PORT)}/{DB_NAME}`, NATS servers, STAN cluster_id/client_id/ping_interval/ping_max_out, subscription queue and durable_name, filer/emailer subjects, SENTRY_DSN, SQLALCHEMY_TRACK_MODIFICATIONS=False. TestConfig overrides DB credentials with TEST variants. GOTCHA: TestConfig uses separate DATABASE_TEST_* env vars but same URI template format.

### behaviour

Configuration for entity-pay service: loads environment variables into Flask configuration objects for different deployment environments.

Reads environment variables from `.env` file and OS for database credentials, NATS/STAN messaging endpoints, email and filing topic names, payment service URL, and Sentry error tracking.

Returns configuration objects on demand via `get_named_config()`: `DevConfig` (DEBUG on), `TestConfig` (TESTING on, separate TEST_* database variables), or `ProdConfig` (DEBUG and TESTING off). Base `_Config` class builds database connection string from `DATABASE_*` variables, NATS options including random 64-bit client ID, and publish options for filer and email topics. Treats SENTRY_DSN value 'null' as empty string.

GOTCHA: Configuration dict at module top references 'legal_api.config' but this file is in 'entity_pay' — mismatch suggests copy-paste error or stale code. GOTCHA: SENTRY_DSN check is case-sensitive; 'NULL' or 'Null' would not be treated as empty.

### purpose-first

Configuration for the entity-pay service, a queue-based filing worker that loads environment variables for database, NATS messaging, and third-party integrations, then provides Flask config objects for dev/test/production environments.

Reads environment variables (or .env file) and exposes them via config classes: `get_named_config(name)` returns `_Config` (base with defaults), `DevConfig`, `TestConfig`, or `ProdConfig`. Each provides database connection URI from `DATABASE_HOST`, `DATABASE_PORT`, `DATABASE_NAME`, `DATABASE_USERNAME`, `DATABASE_PASSWORD` (with separate `_TEST_` variants for testing); messaging via NATS with `NATS_SERVERS` (default `nats://127.0.0.1:4222`), `NATS_CLUSTER_ID`, `NATS_CLIENT_NAME` (default `entity.filing.worker`); and subscription to `NATS_SUBJECT` (default `entity.filings`) in queue `NATS_QUEUE` (default `filing-worker`). Publishes filer events to `NATS_FILER_SUBJECT` and email to `NATS_EMAILER_SUBJECT`. Also configures `PAYMENT_SVC_URL`, `SENTRY_DSN` (normalized: treats the string `'null'` as empty), and `ENVIRONMENT`.

GOTCHA: `STAN_CONNECTION_OPTIONS` generates a random `client_id` per service startup; this could cause unintended cluster behavior if multiple instances expect a stable identity. GOTCHA: `SUBSCRIPTION_OPTIONS.durable_name` is hardcoded as `{NATS_QUEUE}_durable`; changing the queue name will not update the durable subscription name, potentially orphaning old durable state.

### what-how

WHAT: Configuration module for the entity-pay service that loads environment settings and returns configuration objects (DevConfig, TestConfig, or ProdConfig) for Flask application setup.

HOW: Loads environment variables from .env file via find_dotenv/load_dotenv. The `get_named_config(config_name)` function returns configuration objects based on the environment name, raising KeyError for unknown configs. Base `_Config` class sets defaults: PostgreSQL connection via SQLALCHEMY_DATABASE_URI built from DB_USER, DB_PASSWORD, DB_NAME, DB_HOST, DB_PORT; NATS streaming with servers (NATS_SERVERS), cluster_id, and randomly-generated client_id with ping_interval=1 and ping_max_out=5; NATS subscriptions with subject, queue, and durable_name; separate FILER_PUBLISH_OPTIONS and EMAIL_PUBLISH_OPTIONS (each with subject); Sentry DSN; and PAYMENT_SVC_URL. DevConfig sets DEBUG=True, TESTING=False. TestConfig sets DEBUG=True, TESTING=True, and overrides database env vars to DATABASE_TEST_* prefixed names. ProdConfig sets DEBUG=False, TESTING=False.

GOTCHA: SENTRY_DSN is reset to empty string if it equals 'null' (case-insensitive).
GOTCHA: STAN_CONNECTION_OPTIONS client_id is randomly generated on each module load.
GOTCHA: NATS_QUEUE env var serves double duty as both queue name and base for durable_name (with '_durable' appended).

### purpose-lean

Configuration loader for the entity-pay NATS-based filing service that selects Flask config objects matching deployment context.

get_named_config(config_name) returns config class: ProdConfig for 'production'/'staging'/'default', TestConfig for 'testing', DevConfig for 'development'; unknown names raise KeyError.

Base _Config loads environment variables into Flask settings:
- DATABASE_*: PostgreSQL connection built into SQLALCHEMY_DATABASE_URI
- PAYMENT_SVC_URL: external payment service endpoint
- SENTRY_DSN: error tracking (empty if not set)
- NATS_CONNECTION_OPTIONS: servers list (split on comma), client_name = 'entity.filing.worker'
- STAN_CONNECTION_OPTIONS: cluster_id, client_id (random per startup), ping_interval=1, ping_max_out=5
- SUBSCRIPTION_OPTIONS: subject='entity.filings', queue='filing-worker', durable_name='filing-worker_durable'
- FILER_PUBLISH_OPTIONS: subject='entity.filing.filer'
- EMAIL_PUBLISH_OPTIONS: subject='entity.email'
- SQLALCHEMY_TRACK_MODIFICATIONS = False

Environment-specific overrides:
- DevConfig: TESTING=False, DEBUG=True
- TestConfig: TESTING=True, DEBUG=True, overrides all DB_* to read DATABASE_TEST_* env vars
- ProdConfig: TESTING=False, DEBUG=False

GOTCHA: SENTRY_DSN string value 'null' (case-insensitive) converts to empty string — disabled state requires this exact string, not null/None
GOTCHA: NATS_QUEUE env var supplies both 'queue' name and base for durable_name with '_durable' suffix appended
GOTCHA: STAN client_id is random per process startup (random.SystemRandom().getrandbits(0x58)) — not stable for tracing across restarts

### purpose-budget

Configuration loader for the entity-pay queue service, providing environment-specific settings to Flask via environment variables and a base config class.

Loads .env file, then `get_named_config()` returns DevConfig, TestConfig, or ProdConfig based on environment name. Base `_Config` class sets defaults: PostgreSQL connection string built from `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`, `DB_NAME`; NATS/STAN messaging servers and connection options; payment service URL; Sentry error tracking. TestConfig uses separate `DATABASE_TEST_*` variables. STAN client_id generated randomly on each load. SENTRY_DSN treated as empty if set to the string 'null'.

GOTCHA: CONFIGURATION dict references 'legal_api.config' classes, not 'entity_pay.config'.

## `sbc-pay/docs/docs/architecture/FAS_Intgeration.md` (section 0)

### today

FAS→CFS endpoints per event:
- Routing slip create: /parties, /accs (name='BCR'?), /sites (hardcoded), /rcpts (RS#).
- Invoice create: /invs (site), /rcpts/apply.
- Cancel: /rcpts/unapply, /invs/adjs (zero).
- Partial cancel: unapply, adjs (partial), reapply.
- Refund approve: /rcpts/adjs? (refund account).
- Write-off (<$10): /rcpts/adjs (write-off account).
- NSF (cheque bounce): /rcpts/reverse?, /invs (NSF fees).
- Link RS: /rcpts/reverse? (child), /rcpts (parent).

GOTCHA: Multiple endpoints marked "?" (/rcpts/adjs?, /rcpts/reverse?) — unclear if confirmed or draft design; confirm before implementing.

### behaviour

**FAS Integration points with CFS**

**Purpose:** Maps Pay API events to CFS API operations for routing slips, invoices, and refunds.

**What comes in:** Business events — routing slip creation, invoice creation/cancellation (full or partial), refund approval, write-off (< $10), cheque bounce, RS linking.

**What goes out:** Sequential calls to CFS endpoints:
- `/parties`, `/accs`, `/sites`, `/rcpts` — during routing slip setup
- `/invs`, `/rcpts/apply` — on invoice creation
- `/rcpts/unapply`, `/invs/adjs` — on cancellation (adjust invoice to zero or partial amount, reapply receipt if partial)
- `/rcpts/adjs` — on refund approval or write-off (adjust receipt to zero; activity_name directs funds to refund or write-off revenue account)
- `/rcpts/reverse`, `/invs` — on cheque bounce (reverse receipt, create NSF fee invoice)
- `/rcpts/reverse`, `/rcpts` — on RS linking (reverse child receipt, create parent receipt)

**GOTCHA:** Endpoints marked with `?` indicate uncertainty in the design (exact operation not yet confirmed). Partial cancellation requires three separate calls in order: unapply, adjust to partial amount, reapply. Write-off and refund both use `/rcpts/adjs` but distinguish behavior via `activity_name` parameter.

### purpose-first

Specifies the CFS API endpoints the Pay API calls for different payment transaction lifecycle events (routing slip, invoice, refund, write-off, NSF, linking).

When a routing slip is created, Pay API calls CFS to create: a party (with customer name as entity number), an account (name BCR), a site (hardcoded values, no address provided), and a receipt (numbered as RS). When an invoice is created, it calls to create the invoice against the site, then apply the receipt. Full invoice cancellation unapplies the receipt then adjusts invoice to zero; partial cancellation unapplies, adjusts invoice to partial amount, then reapplies the receipt. Refund approval adjusts the receipt to zero with an activity_name to move funds to refund revenue account. Write-off (<$10) adjusts the invoice to zero with an activity_name for write-off revenue. NSF reverses the receipt (which unapplies all invoices) and creates a new invoice for NSF fees. Linking a child routing slip reverses its receipt, then creates a receipt on the parent.

GOTCHA: Site creation uses hardcoded values because no address is provided to Pay API. GOTCHA: The /rcpts/reverse endpoint unapplies all invoices as a side effect. GOTCHA: Partial cancellation requires three calls in sequence (unapply, adjust, reapply) rather than a single partial adjustment.

### what-how

WHAT: Architecture documentation for Pay_API's CFS integration, specifying endpoint sequences for financial operations: routing slip creation, invoice lifecycle (create/cancel/partially cancel), refunds, write-offs, bounced cheques, and routing slip linking.

HOW: Each operation calls CFS_API endpoints in sequence. Routing slip creation: /parties, /accs (account name hardcoded as "BCR"), /sites (hardcoded values; no address provided), /rcpts (receipt numbered as routing slip number). Invoice creation: /invs, then /rcpts/apply (payload: routing slip receipt + invoice). Full cancellation: /rcpts/unapply, /invs/adjs (adjust to zero). Partial cancellation: /rcpts/unapply, /invs/adjs (adjust to partial), /rcpts/apply. Refund approval: /rcpts/adjs (activity_name moves fund to refund revenue account). Write-off (<$10): /rcpts/adjs (activity_name moves fund to write-off revenue account). Bounced cheque: /rcpts/reverse (unapplies all invoices), /invs (new invoice for NSF fees). Routing slip link: /rcpts/reverse (child routing slip), /rcpts (create to parent).

GOTCHA: Multiple endpoints marked with "?" indicating unconfirmed design (refund /rcpts/adjs, NSF /rcpts/reverse, link /rcpts/reverse). Partial cancellation is non-transactional: unapply-adjust-apply sequence leaves intermediate states exposed.

### purpose-lean

Specification for Pay_API integration with CFS_API to manage routing slips, invoices, receipts, and financial adjustments across the transaction lifecycle.

**Routing slip creation** → POST /parties, /accs (name: BCR), /sites (hard-coded values), /rcpts (number: RS number).

**Invoice creation** → POST /invs (against site) → POST /rcpts/apply (routing slip receipt + invoice).

**Invoice cancellation** → POST /rcpts/unapply → POST /invs/adjs (to zero).

**Partial cancellation** → POST /rcpts/unapply → POST /invs/adjs (to partial amount) → POST /rcpts/apply.

**Refund approval** → POST /rcpts/adjs (to zero, activity_name moves fund to refund revenue account).

**Write-off** (<$10) → POST /rcpts/adjs (to zero, activity_name moves fund to write-off revenue account).

**Cheque bounce (NSF)** → POST /rcpts/reverse (unapplies all invoices) → POST /invs (new invoice for NSF fees).

**Routing slip linking** → POST /rcpts/reverse (child routing slip) → POST /rcpts (to parent).

GOTCHA: Endpoints /rcpts/adjs and /rcpts/reverse marked "?" indicating uncertain specifications.
GOTCHA: Site creation uses hard-coded values due to missing address data.
GOTCHA: Ambiguity on customer identifier field (entity number vs. unique number).
GOTCHA: Ambiguity on account naming convention (BCR).

### purpose-budget

Architecture documentation specifying CFS API endpoint sequences Pay API invokes for routing slip creation, invoice transactions, and lifecycle events in FAS integration.

Routing slip creation: /parties (customer) → /accs (account BCR) → /sites (hardcoded, no address) → /rcpts (receipt as RS number). Invoice creation: /invs (against site) → /rcpts/apply (receipt to invoice). Full cancellation: /rcpts/unapply → /invs/adjs (to zero). Partial cancellation: /rcpts/unapply → /invs/adjs (to partial) → /rcpts/apply. Refund: /rcpts/adjs (receipt to zero, refund revenue activity). Write-off: /rcpts/adjs (to zero, write-off revenue activity). NSF: /rcpts/reverse (unapplies all invoices) → /invs (NSF fee). Linking: /rcpts/reverse (child receipt) → /rcpts (parent receipt).

GOTCHA: Multiple endpoints marked with ?, indicating design uncertainty. Write-off endpoint /rcpts/adjs conflicts with its comment saying "Adjust the invoice" rather than "receipt."
