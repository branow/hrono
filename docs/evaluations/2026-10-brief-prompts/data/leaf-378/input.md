=== queue_services/business-pay/LICENSE ===

BSD 3 Clause License for queue_services/business-pay by the Province of British Columbia. Permits redistribution in source or binary form with modifications, provided: copyright notice and conditions are retained in source; binary distributions reproduce notice and conditions in documentation; copyright holder and contributor names are not used for endorsement without permission. Disclaims implied warranties of merchantability and fitness for a particular purpose, and holds copyright holder and contributors not liable for any direct, indirect, incidental, special, exemplary, or consequential damages.

=== queue_services/business-pay/src/business_pay/__init__.py ===

Provides a Flask application factory for the Entity Payment service, which applies payments against Filings and queues files for processing (except FED types). The `create_app()` function accepts an optional environment configuration object (defaults to ProdConfig) and returns a configured Flask app. Initializes the database, registers API endpoints, and activates both GCP and standard queue services. Sentry error tracking is conditionally enabled if SENTRY_DSN exists in config. GOTCHA: The function accepts **kwargs but does not pass or use them.

=== queue_services/business-pay/src/business_pay/config.py ===

Configuration module for the business-pay service, supplying Flask with environment-specific settings. Inputs: environment variables from .env file. Outputs: Config subclass instances (DevConfig/TestConfig/ProdConfig) containing PostgreSQL database URI (with optional Unix socket), NATS broker settings (NATS_SERVERS, NATS_CLIENT_NAME, NATS_CLUSTER_ID, NATS_QUEUE, NATS_FILER_SUBJECT, NATS_EMAILER_SUBJECT, subscription and publish options), GCP service account credentials, Sentry DSN, and payment service URL. Main flow: load_dotenv() loads .env file; get_named_config(name) returns appropriate Config subclass. Defaults: PostgreSQL 5432, NATS 127.0.0.1:4222, environment "prod", TESTING/DEBUG false. Boilerplate: BSD 3-Clause license, imports, pylint disables. GOTCHA: NATS_SERVERS default "nats://127.0.0.1:4222," has trailing comma, creating empty element after split. GOTCHA: SENTRY_DSN explicitly converts string 'null' to empty string.

=== queue_services/business-pay/src/business_pay/database/__init__.py ===

Package init establishing the public API for the business-pay database module. Re-exports Filing (from filings submodule), Review and ReviewStatus (from review submodule) to enable direct importing of these classes at the package level. BSD 3-Clause License applies.

=== queue_services/business-pay/src/business_pay/database/db.py ===

Database initialization configuration for the business-pay service. Exports db, a SQLAlchemy instance for ORM operations, and Base, the declarative model class that application models inherit from. Relies on flask_sqlalchemy for db instance management; uses default SQLAlchemy() configuration with no additional parameters.

=== queue_services/business-pay/src/business_pay/database/filings.py ===

Database model for the business-pay service to store and retrieve business filings. Takes Filing instances to save() or payment_token strings to query via get_filing_by_payment_token(); returns Filing objects with id, effective_date, filing_type, filing_sub_type, filing_json (JSONB), payment_completion_date, payment_status_code, payment_token, status (enum: DRAFT, PENDING, PAID, COMPLETED, CORRECTED, ERROR, APPROVED, AWAITING_REVIEW, CHANGE_REQUESTED, REJECTED, EPOCH, PENDING_CORRECTION), and payment_account. Uses SQLAlchemy ORM with include_properties mapper configuration.

GOTCHA: payment_token attribute maps to database column 'payment_id'.
GOTCHA: get_filing_by_payment_token() silently swallows exceptions and returns None.

=== queue_services/business-pay/src/business_pay/database/review.py ===

Database model for storing review records associated with business filings, tracking review state and completing party information. Defines ReviewStatus enum with states AWAITING_REVIEW, CHANGE_REQUESTED, RESUBMITTED, APPROVED, REJECTED. Review entity holds nr_number, identifier, completing_party, status (required), submission_date, creation_date, and filing_id (required foreign key to filings table). The save() method persists changes via immediate database commit.

=== queue_services/business-pay/src/business_pay/resources/__init__.py ===

Flask endpoint registration for a business payment service that applies payments to filings and queues non-FED submissions to Filer Q. Registers `pay_filer_endpoint` at root and `ops_endpoint` at `/ops` URL prefixes. Sets `strict_slashes = False` for flexible route matching. Actual payment logic implemented in imported `.pay_filer` and `.ops` blueprints. BSD 3-Clause License.

=== queue_services/business-pay/src/business_pay/resources/ops.py ===

Provides HTTP health-check endpoints for Kubernetes/orchestration systems to monitor the business-pay service availability.

Two GET routes return readiness signals: `healthz` returns `{'message': 'api is healthy'}` with HTTP 200 to confirm the service is running; `readyz` returns `{'message': 'api is ready'}` with HTTP 200 to confirm dependencies are initialized and the service can accept work. Both are Flask Blueprint routes. Inputs are GET requests to those paths; outputs are JSON status objects and HTTP 200. No validation, queuing, or dependency checks are performed—responses are hardcoded.

GOTCHA: The `readyz` endpoint docstring says "setupAnd ready" (typo), suggesting dependency checks, but the code returns a fixed message without checking initialization state.

=== queue_services/business-pay/src/business_pay/resources/pay_filer.py ===

Flask worker processes cloud events for business filing payments. Receives SimpleCloudEvent with PaymentToken (id, status_code, filing_identifier, corp_type_code), queries Filing by payment_token, marks filing PAID with payment_completion_date, creates staff Review if filing_type is "continuationIn" else publishes to filer queue if effective_date ≤ payment_completion_date, then publishes to email queue. Returns 200 (removed) for empty/garbled/MHR/BTR corp types, null filing_identifier with BC corp type, and duplicate payments; returns 404 (requeued) if filing not found. GOTCHA: only publishes to filer if effective_date ≤ payment_completion_date (FED filings skip). GOTCHA: publish operations suppress all exceptions after PAID marking.

=== queue_services/business-pay/src/business_pay/services/__init__.py ===

Initializes the services module for business payment processing with module-level instances and message builder utilities. `gcp_queue` (GcpQueue) and `queue` (QueueService) initialize the transport and queue layers. `create_filing_msg(identifier)` wraps an identifier in `{"filing": {"id": identifier}}`. `create_email_msg(identifier, filing_type)` returns `{"email": {"filingId": identifier, "type": filing_type, "option": "PAID"}}`. Imports `verify_gcp_jwt` from `.gcp_auth`. GOTCHA: `create_email_msg` hardcodes `"option": "PAID"` regardless of filing_type, with a TODO to externalize this as a common Enum.

=== queue_services/business-pay/src/business_pay/services/gcp_auth.py ===

Verifies GCP OAuth bearer tokens for the business-pay service. Takes a Flask request, extracts the bearer token from the Authorization header, and verifies it against Google's OAuth2 endpoint using `id_token.verify_oauth2_token()` with the audience configured in `SUB_AUDIENCE`. Checks that the token's `email_verified` claim is true and its `email` matches the service account address in `SUB_SERVICE_ACCOUNT`. Returns an empty string on valid token; returns an error message on any failure (invalid token, unverified email, or mismatched service account).

GOTCHA: Function returns a message string (empty or error) rather than a boolean or raising an exception — callers must check truthiness of the return value to detect verification failures.

=== queue_services/business-pay/src/business_pay/services/queue.py ===

Publishes JSON payment messages to NATS Streaming from Flask.

Takes Flask config (NATS_CLIENT_NAME, NATS_SERVERS, NATS_CLUSTER_ID, NATS_CONNECT_TIMEOUT, NATS_FILER_SUBJECT) and JSON payloads with optional subject; publishes UTF-8 JSON to STAN. Lazy-connects on first publish, auto-disconnects at Flask teardown. Provides sync publish_json() and async async_publish_json() methods. NATS/STAN clients stored in Flask's request-scoped g or instance. is_connected and is_closed properties reflect cluster state. Event handlers log connection changes. Uses nest_asyncio for nested event loop support.

GOTCHA: is_closed property catches RuntimeError and prints to stdout. GOTCHA: NATS_FILER_SUBJECT config key may be misspelled (FILTER?).

=== queue_services/business-pay/src/business_pay/utils.py ===

Utility module that supplies formatted version strings with optional commit hash for the business-pay service. Reads VCS_REF environment variable and package metadata; returns version string optionally appended with commit hash. get_run_version() fetches package version via importlib.metadata and calls _get_commit_hash(), returning formatted string. _get_commit_hash() returns VCS_REF if present and not equal to the literal string "missing". GOTCHA: VCS_REF="missing" is treated as if unset.

=== queue_services/business-pay/src/business_pay/utils/__init__.py ===

Package initialization for business-pay's utils module. Holds general utility functions and helpers for the service (implementation in submodules). Currently contains only a BSD 3-Clause license header and package docstring; no code or flows defined at this level.

=== queue_services/business-pay/src/business_pay/utils/base.py ===

Base enum utility module for the business payment system providing custom enum behavior. The `BaseMeta` metaclass enables the `in` operator to check membership by attempting value construction (returning False on ValueError). The `BaseEnum.get_enum_by_value()` classmethod provides reverse lookup—iterating through all enum members to find one with matching string value, returning the enum or None. Derived enums inherit both capabilities.

=== queue_services/business-pay/tests/data/create_database.sql ===

Database schema definition (test fixture) for the filings table in the business payment service, storing records of business filings with their submission, payment, and processing status.

The table holds filing metadata (filing_date, filing_type, filing_sub_type, filing_json), payment tracking (payment_id, transaction_id, payment_status_code, payment_completion_date), submission details (business_id, submitter_id, source, submitter_roles), and processing state (status, completion_date, effective_date, parent_filing_id). An auto-incrementing id sequence serves as primary key. Fields like court_order_file_number, tech_correction_json, and meta_data capture filing-specific attributes.

GOTCHA: Extensive nullable columns imply conditional fields varying by filing_type and workflow stage. Flags paper_only, colin_only, and deletion_locked suggest undocumented business rules and soft-delete logic.

=== queue_services/business-pay/tests/integration/__init__.py ===

Python package marker for integration tests of business-pay service against NATS Queue. File contains BSD 3 Clause License (Province of British Columbia) only; no implementation code.

=== queue_services/business-pay/tests/integration/test_worker_queue.py ===

Integration test of queue worker's ability to process payment completion CloudEvents and publish notifications. Receives GCP Pub/Sub CloudEvent envelopes with payment_token, statusCode, filingIdentifier via authenticated Flask endpoint; verifies worker publishes exactly 2 NATS messages with specific JSON payloads: `{"filing": {"id": 12}}` and `{"email": {"filingId": 12, "type": "annualReport", "option": "PAID"}}`. Test inserts PENDING filing (id=12, type=annualReport) with payment_id matching payment_token, posts COMPLETED payment event, and asserts both messages arrive within 2 seconds. Helpers construct CloudEvent and GCP Pub/Sub message formats. Uses pytest-asyncio, mocks Google OAuth2 verification, NATS Streaming.

GOTCHA: Loop variables found_filing_msg and found_email_msg never initialized—if messages don't match hardcoded JSON, test crashes with NameError.

=== queue_services/business-pay/tests/unit/__init__.py ===

Package initialization for unit tests in the business-pay queue service. This __init__.py marks the directory as a Python package, enabling imports of unit tests and helper routines. BSD 3-Clause licensed.

=== queue_services/business-pay/tests/unit/test_version.py ===

Unit test fixture for version utilities in the business-pay queue service. Tests that version retrieval works correctly. Single test function `test_get_version()` calls `utils.get_run_version()` from the business_pay module and asserts the result is truthy (non-empty). This validates that the version utility successfully exposes version information and returns a meaningful value.

=== queue_services/business-pay/wsgi.py ===

WSGI entry point that launches the business-pay Flask application.

Creates an app instance via `create_app()` and runs it on a port from the PORT environment variable (defaults to 8080), binding to 0.0.0.0 with debug=False. BSD 3-Clause licensed.

GOTCHA: Despite the wsgi.py filename, this uses Flask's development server (`app.run()`) rather than a production-ready WSGI application server.
