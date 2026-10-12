=== queue_services/business-pay/LICENSE ===

BSD 3-Clause license (Province of British Columbia, 2024) governing use of the business-pay queue service; permits redistribution with copyright notice retention and no contributor endorsement without permission.

=== queue_services/business-pay/src/business_pay/__init__.py ===

Initializes the Flask application for the Entity Payment service, which applies payments against Filings and conditionally queues file processing for non-FED types. The `create_app` factory accepts an optional `environment` configuration parameter (defaults to ProdConfig) and returns a configured Flask app. Setup flow: load config via `app.config.from_object(environment)`, conditionally initialize Sentry if `SENTRY_DSN` is present in config using FlaskIntegration with send_default_pii=False, initialize the database via `db.init_app(app)`, register HTTP endpoints via `register_endpoints(app)`, initialize the GCP queue via `gcp_queue.init_app(app)`, and initialize the queue service via `queue.init_app(app)`.

=== queue_services/business-pay/src/business_pay/config.py ===

Configuration module for the business-pay service. Loads environment variables and provides config objects via `get_named_config(config_name)`: production, staging, and default map to ProdConfig; testing maps to TestConfig; development maps to DevConfig; unknown names raise KeyError. Base Config class reads database credentials (DB_USER, DB_PASSWORD, DB_NAME, DB_HOST, DB_PORT) and builds SQLALCHEMY_DATABASE_URI—if DATABASE_UNIX_SOCKET env var is set, uses Unix socket format `postgresql+pg8000://user:password@/dbname?unix_sock={DATABASE_UNIX_SOCKET}/.s.PGSQL.5432`, otherwise TCP format with host and port. Loads PAYMENT_SVC_URL and SENTRY_DSN; clears SENTRY_DSN to empty string if its value equals 'null'. Configures NATS message broker: NATS_SERVERS split by comma, NATS_CONNECTION_OPTIONS with servers list and client name, STAN_CONNECTION_OPTIONS with cluster ID and random client_id, SUBSCRIPTION_OPTIONS with subject/queue/durable_name, and separate publish options for filer and emailer subjects. Loads GCP credentials and audiences. TestConfig inherits Config, uses DATABASE_TEST_* env vars, sets DEBUG and TESTING to True. DevConfig sets DEBUG to True, TESTING to False. ProdConfig sets both to False.

GOTCHA: NATS_CONNECT_ERROR_COUNT_MAX loaded as string '10', not integer—numeric comparisons will fail.

GOTCHA: Unix socket connection appends hardcoded `/.s.PGSQL.5432` suffix to DATABASE_UNIX_SOCKET value.

=== queue_services/business-pay/src/business_pay/database/__init__.py ===

Module initialization file that exports the public API for the business-pay database module. Re-exports Filing from the filings submodule and Review, ReviewStatus from the review submodule.

=== queue_services/business-pay/src/business_pay/database/db.py ===

Configuration module that initializes SQLAlchemy and provides the base model class for the business payment service. Creates `db` (SQLAlchemy instance with default configuration) following Flask community lowercase naming convention, then exports `db` and `Base` (extracted as `db.Model`, the declarative base for ORM model definitions). The application initializes this module at startup before loading model classes. BSD 3-Clause License.

=== queue_services/business-pay/src/business_pay/database/filings.py ===

Database model (minimal mapping) representing a filing with payment tracking, including just enough fields to mark as paid. Stores: id, effective_date, filing_type, filing_sub_type, filing_json (JSONB), payment_completion_date, payment_status_code, payment_token (max 4096 chars), status, payment_account. Status enum with 13 values: COMPLETED, CORRECTED, DRAFT, EPOCH, ERROR, PAID, PENDING, PENDING_CORRECTION, APPROVED, AWAITING_REVIEW, CHANGE_REQUESTED, REJECTED (defaults to DRAFT). Methods: save() commits to database; get_filing_by_payment_token(pay_token) queries and returns Filing or None.

GOTCHA: payment_token attribute maps to database column 'payment_id'. GOTCHA: get_filing_by_payment_token catches all exceptions silently and returns None, masking errors.

=== queue_services/business-pay/src/business_pay/database/review.py ===

Database model that stores review records linked to business filing submissions.

Stores: id (primary key), nr_number, identifier, completing_party, status, submission_date, creation_date, and filing_id (foreign key to filings table, not nullable). The status field holds a ReviewStatus enum—not nullable—with values AWAITING_REVIEW, CHANGE_REQUESTED, RESUBMITTED, APPROVED, or REJECTED. The save() method adds the review to the database session and immediately commits it.

GOTCHA: save() has no error handling; database commit failures raise unhandled exceptions. GOTCHA: save() performs immediate commit, not batched or transactional with other operations.

=== queue_services/business-pay/src/business_pay/resources/__init__.py ===

Initializer registering Flask endpoints for a payment-processing service that applies payments to filings and queues non-FED filings for processing. Takes a Flask app instance and modifies it in-place. Sets app.url_map.strict_slashes to False, allowing routes to match with or without trailing slashes. Registers two blueprints: pay_filer_endpoint from .pay_filer at "/" prefix, and ops_endpoint from .ops at "/ops" prefix.

=== queue_services/business-pay/src/business_pay/resources/ops.py ===

Operational health and readiness check endpoints for the business_pay service.

Flask blueprint "ops" registers two GET routes: /healthz runs get_healthz() returning {'message': 'api is healthy'} with HTTP 200; /readyz runs get() returning {'message': 'api is ready'} with HTTP 200. No request payloads or query parameters processed; both endpoints return static JSON responses.

GOTCHA: Function get() lacks a name indicating it serves the /readyz route. GOTCHA: Both functions declared async but contain only synchronous returns—incomplete implementation or pattern mismatch.

=== queue_services/business-pay/src/business_pay/resources/pay_filer.py ===

Processes GCP Pub/Sub cloud events containing payment completion notifications, marking corresponding business filings as paid and triggering downstream processing.

Receives cloud event with payment token via HTTP POST with GCP JWT validation. Extracts PaymentToken from event data when ce.type matches "bc.registry.payment"; searches Filing by `payment_token.id`. Returns 200 OK (remove from queue) if: message empty/malformed, payment status not "COMPLETED", corp_type_code in ["MHR", "BTR"], filing already has payment_completion_date, or (filing_identifier is None AND corp_type_code is "BC"). Returns 404 (retry) if filing not found.

When filing found: sets filing.payment_completion_date, filing.payment_status_code = "COMPLETED", filing.status = Filing.Status.PAID. If filing_type in ["continuationIn"], creates Review record with status ReviewStatus.AWAITING_REVIEW, otherwise publishes to filer queue (if effective_date <= payment_completion_date). Publishes to email queue. `dict_keys_to_snake_case()` converts PaymentToken dict keys from camelCase. `get_completing_party()` extracts name from parties with roleType "Completing Party".

GOTCHA: Exceptions in publish_to_filer() and publish_to_emailer() are suppressed; filing marked PAID before queue operations complete, so failed publishes leave filing paid without notification.
GOTCHA: Special-case handling for filing_identifier None and corp_type_code "BC" (returns 200, not 404).

=== queue_services/business-pay/src/business_pay/services/__init__.py ===

Provides factory functions and service instances for a business payment queue system.

It exports two message-creation functions: `create_filing_msg(identifier)` returns `{"filing": {"id": identifier}}`; `create_email_msg(identifier, filing_type)` returns `{"email": {"filingId": identifier, "type": filing_type, "option": "PAID"}}`. It also instantiates and exposes `gcp_queue` (GcpQueue) and `queue` (QueueService) for downstream use.

GOTCHA: email payload hardcodes "option" to "PAID"; a TODO notes this should use a common Enum instead.

=== queue_services/business-pay/src/business_pay/services/gcp_auth.py ===

Verifies GCP OAuth bearer tokens in Flask request Authorization headers, confirming they are signed by an expected service account.

Input: Flask request with Authorization header containing "Bearer <token>" format.

Output: Empty string if valid; error message string if verification fails or token is invalid.

Flow: Extract bearer token, verify it using Google's id_token.verify_oauth2_token() with audience from config (SUB_AUDIENCE). Validate the token's email_verified claim is true and email matches config SUB_SERVICE_ACCOUNT. Return error message if email verification fails, email mismatch, or any exception occurs during verification.

Uses google.oauth2.id_token, google.auth.transport.requests; reads SUB_AUDIENCE and SUB_SERVICE_ACCOUNT from Flask current_app.config.

GOTCHA: Returns empty string on success but error message on failure—callers must check truthiness to detect errors. Catches all exceptions broadly, swallowing details beyond concatenating err to message.

=== queue_services/business-pay/src/business_pay/services/queue.py ===

Flask extension for publishing JSON messages to a NATS streaming queue. Accepts `payload` (dict) and optional `subject` (string, defaults to `NATS_FILER_SUBJECT` from config); encodes as UTF-8 JSON and publishes via STAN client. `publish_json()` provides synchronous wrapper around `async_publish_json()`, which auto-connects if disconnected before publishing. Config loaded from Flask app via `init_app()`: NATS_SERVERS, NATS_CLIENT_NAME, NATS_CLUSTER_ID, NATS_CONNECT_TIMEOUT. Client ID generated by normalizing the configured client name and appending random bits. Both NATS and STAN clients established via `connect()`, closed on app teardown.

GOTCHA: `is_closed` property catches RuntimeError and uses print() instead of logger for output.

=== queue_services/business-pay/src/business_pay/utils.py ===

Provides formatted version string for the business-pay service, appending commit hash when deployed in OKD.

Inputs: `VCS_REF` environment variable and installed package version via `importlib.metadata.version`. Outputs: version string as "VERSION" or "VERSION-HASH".

`get_run_version()` extracts package name from `__name__` (first dot-separated component), retrieves version, and appends commit hash if available. `_get_commit_hash()` supplies commit hash by checking `VCS_REF`—returns it if set and not equal to "missing", else returns None.

Decision: if `VCS_REF` env var is non-empty and != "missing", append as "-{HASH}" to version; else output version alone.

=== queue_services/business-pay/src/business_pay/utils/__init__.py ===

Module initialization file for the business_pay.utils package. Currently empty; docstring indicates it will hold general utility functions and helpers for the package.

=== queue_services/business-pay/src/business_pay/utils/base.py ===

Utility module providing base enum classes for the business payment system with custom membership checking and value-based lookup.

`BaseMeta` metaclass overrides `__contains__` to check enum membership by attempting construction: if the value can be constructed as an enum member without a ValueError, it's in the enum; otherwise, it's not. `BaseEnum` combines str and Enum with BaseMeta as metaclass and adds `get_enum_by_value(cls, value: str)`, which iterates through enum members comparing `enum_value.value` against the input, returning the matching member or None if no match is found.

=== queue_services/business-pay/tests/data/create_database.sql ===

Test fixture: creates the `filings` table schema for storing business filing records with payment tracking in the queue-services system.

Input: filing metadata (type, subtype, dates), filing data (filing_json), payment data (payment_id, transaction_id, payment_status_code, payment_completion_date), filer identifiers (business_id, submitter_id), and status codes. Output: structured table with 29 columns plus auto-incrementing id sequence.

Key fields: `filing_json` holds structured filing content; `payment_id` links to payments; `payment_status_code` and `status` track filing and payment states; `tech_correction_json` holds correction data; `court_order_*` fields store court order details; flags `paper_only`, `colin_only`, `deletion_locked` control processing; `meta_data` stores additional metadata; `source`, `effective_date`, `completion_date` track temporal information; `parent_filing_id` enables filing relationships.

=== queue_services/business-pay/tests/integration/__init__.py ===

Test package initialization file serving integration tests to NATS Queue. The file contains only the BSD 3 Clause License header and is otherwise empty, marking the directory as a Python package. No configuration, fixtures, setup logic, or test utilities are defined.

=== queue_services/business-pay/tests/integration/test_worker_queue.py ===

Test suite for payment queue worker. Main test `test_complete_worker` verifies GCP PubSub envelope with cloud event (type "bc.registry.payment", statusCode "COMPLETED", filingIdentifier) triggers two NATS messages: `{"filing": {"id": <filing_id>}}` for filer and `{"email": {"filingId": <filing_id>, "type": <filing_type>, "option": "PAID"}}` for emailer. Creates event via `create_test_payment_cloud_event()`, wraps via `create_test_envelope()` with base64 encoding, POSTs to Flask endpoint, mocks `google.oauth2.id_token.verify_oauth2_token`, subscribes via `stan.subscribe()` with durable_name, waits 2 seconds, asserts message count and content.

GOTCHA: `create_filing()` uses unescaped f-string SQL, enabling injection. GOTCHA: `test_complete_worker` doesn't initialize `found_filing_msg` and `found_email_msg`; NameError if loop doesn't set both.

=== queue_services/business-pay/tests/unit/__init__.py ===

Python package initializer for business-pay queue service unit tests. File contains only a BSD 3 Clause License header and docstring ("The Unit Tests and the helper routines"); no functional code or logic.

=== queue_services/business-pay/tests/unit/test_version.py ===

Test for version utilities. Calls `business_pay.utils.get_run_version()`, stores result in `rv`, and asserts it is truthy via `assert rv`. Decision: passes if version is truthy (non-None, non-empty), fails otherwise. Verifies the version utility produces valid output.

=== queue_services/business-pay/wsgi.py ===

WSGI entry point configuration that starts the business_pay Flask application. Imports `create_app()`, instantiates the app, reads server port from PORT environment variable (default "8080"), and runs the app with `debug=False` on host `0.0.0.0`. Main flow: `create_app()` → if `__main__` triggered, retrieve PORT or use "8080" → `app.run(debug=False, port=server_port, host="0.0.0.0")`. BSD 3 Clause license header.
