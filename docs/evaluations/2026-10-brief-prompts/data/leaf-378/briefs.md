# today

# business-pay (queue_services/business-pay)

A small Python/Flask queue-worker service from the Province of British Columbia (BSD 3-Clause) that applies payment-completion events to business Filings. It marks filings PAID, creates staff Reviews for `continuationIn` filings, and publishes messages to the Filer and Email queues. Tech: Flask, SQLAlchemy (PostgreSQL), NATS Streaming (STAN), GCP Pub/Sub CloudEvents with OAuth bearer auth, Sentry, pytest.

## Application core
- `__init__.py`: `create_app()` factory (defaults to ProdConfig). Initializes the db, registers endpoints, activates the GCP and standard queue services, and enables Sentry if SENTRY_DSN is set.
- `config.py`: Dev/Test/Prod Config classes, selected via `get_named_config(name)`. Loads `.env`. Settings cover the PostgreSQL URI, NATS (servers, client name, cluster ID, queue, filer and emailer subjects), GCP service account, Sentry DSN and the payment service URL.
- `wsgi.py`: entry point. Runs the app on PORT (default 8080) at 0.0.0.0.
- `utils.py`: `get_run_version()` and `_get_commit_hash()`, which reads VCS_REF.
- `utils/__init__.py`: empty package header.
- `utils/base.py`: `BaseMeta` metaclass (supports the `in` operator) and `BaseEnum.get_enum_by_value()`.

## Database layer (`database/`)
- `db.py`: the `db` SQLAlchemy instance and `Base`.
- `filings.py`: `Filing` model. It has a status enum (DRAFT, PENDING, PAID, COMPLETED, etc.), a JSONB `filing_json`, and payment fields. Provides `save()` and `get_filing_by_payment_token()`.
- `review.py`: `Review` model and `ReviewStatus` enum (AWAITING_REVIEW, CHANGE_REQUESTED, RESUBMITTED, APPROVED, REJECTED). Its `filing_id` is a required foreign key.
- `__init__.py`: re-exports Filing, Review and ReviewStatus.

## HTTP resources (`resources/`)
- `__init__.py`: registers `pay_filer_endpoint` at root and `ops_endpoint` at `/ops`, with `strict_slashes = False`.
- `pay_filer.py`: the main worker. It receives a SimpleCloudEvent with a PaymentToken (id, status_code, filing_identifier, corp_type_code) and looks up the Filing by payment token. It then marks the filing PAID and sets payment_completion_date. For `continuationIn` it creates a staff Review. Otherwise it publishes to the filer queue if effective_date ≤ payment_completion_date. Finally it publishes to the email queue.
  - Returns 200 (message removed) for empty or garbled events, MHR/BTR corp types, a null filing_identifier with a BC corp type, and duplicate payments.
  - Returns 404 (requeued) if the filing is not found.
- `ops.py`: `healthz` and `readyz` GET endpoints returning hardcoded 200 JSON.

## Services (`services/`)
- `__init__.py`: module-level `gcp_queue` and `queue`. Message builders `create_filing_msg` (`{"filing": {"id": ...}}`) and `create_email_msg` (`{"email": {"filingId", "type", "option": "PAID"}}`).
- `gcp_auth.py`: `verify_gcp_jwt` checks the bearer token against `SUB_AUDIENCE`, `email_verified`, and `SUB_SERVICE_ACCOUNT`.
- `queue.py`: NATS Streaming publisher. It connects lazily on first publish and disconnects at Flask teardown. It offers sync `publish_json()` and async `async_publish_json()`, and uses nest_asyncio.

## Tests
- `tests/data/create_database.sql`: schema fixture for the `filings` table. It covers filing, payment, submitter and processing fields, plus flags such as paper_only, colin_only and deletion_locked.
- `tests/integration/test_worker_queue.py`: posts a COMPLETED payment CloudEvent for a PENDING annualReport filing (id=12). It asserts that exactly the filing and email NATS messages arrive within 2 seconds. Uses pytest-asyncio and mocks OAuth and STAN.
- `tests/unit/test_version.py`: asserts `get_run_version()` returns a truthy value.
- The `__init__.py` files in the test packages are license-only.

## Caution
- **Wrong "FED" assumption:** the filer publish is skipped only when effective_date > payment_completion_date, which is how future-effective filings are held back. Don't read it as a type check.
- **Swallowed errors:** after a filing is marked PAID, all publish exceptions are suppressed, so a failed queue publish is silent. `get_filing_by_payment_token()` also swallows exceptions and returns None, which looks the same as "not found" and triggers a 404 requeue.
- **Auth returns strings:** `verify_gcp_jwt` returns "" on success and an error message on failure. Callers must check truthiness and must not expect a boolean or an exception.
- **Hardcoded email option:** `create_email_msg` always sets `"option": "PAID"`, whatever the filing type.
- **Column naming:** `Filing.payment_token` maps to the DB column `payment_id`.
- **Health checks are fake:** `readyz` checks no dependencies. `healthz` and `readyz` always return 200.
- **Config quirks:** the default NATS_SERVERS has a trailing comma, which yields an empty element after the split. SENTRY_DSN of the string `'null'` becomes an empty string. NATS_FILER_SUBJECT may be a misspelling.
- **`create_app(**kwargs)`** ignores its kwargs.
- **wsgi.py** uses Flask's dev server (`app.run()`), not a production WSGI server.
- **utils:** both `utils.py` and a `utils/` package exist, so the name is ambiguous. `VCS_REF="missing"` is treated as unset.
- **Queue handling:** `is_closed` catches RuntimeError and prints to stdout.
- **Test fragility:** in the integration test, `found_filing_msg` and `found_email_msg` are never initialized. If the messages don't match the expected JSON, the test fails with NameError instead of a clear assertion.
- **Schema:** many nullable columns are conditional on filing type and workflow stage. Their business rules are undocumented.

# blackbox-sections

## Purpose
The business-pay service is a queue worker for the Entity Payment flow. It receives payment-completion events, marks the matching Filing as PAID, and then either queues the filing for the Filer or creates a staff Review. It also queues an email notification. FED filings are not sent to the Filer.

## Inputs
- GCP Pub/Sub push CloudEvents (`SimpleCloudEvent`) posted to the root endpoint handled by `pay_filer`. The payload is a `PaymentToken` with `id`, `status_code`, `filing_identifier` and `corp_type_code`.
- Each request carries a bearer token, which `gcp_auth.verify_gcp_jwt` checks.
- The `filings` table, read through the `Filing` model and looked up by payment token.
- Environment variables loaded from `.env` by `config.py`:
  - PostgreSQL connection settings.
  - NATS settings.
  - GCP service-account settings (`SUB_AUDIENCE`, `SUB_SERVICE_ACCOUNT`).
  - `SENTRY_DSN`.
  - The payment service URL.
  - `PORT` and `VCS_REF`.
- GET requests to `/ops/healthz` and `/ops/readyz` from the orchestrator.

## Outputs
- HTTP responses to Pub/Sub. 200 means the message is removed. 404 means it is requeued.
- Database writes:
  - The Filing is set to PAID with a `payment_completion_date`.
  - A `Review` row is created for continuationIn filings.
- JSON messages published to NATS Streaming:
  - Filer subject: `{"filing": {"id": ...}}`
  - Email subject: `{"email": {"filingId": ..., "type": ..., "option": "PAID"}}`
- Health-check JSON.
- Optional Sentry error reports.

## Concepts and rules
- **Payment token to filing**: `Filing.payment_token` maps to the database column `payment_id`. `Filing.get_filing_by_payment_token()` finds the filing.
- **Filing status** enum: DRAFT, PENDING, PAID, COMPLETED, CORRECTED, ERROR, APPROVED, AWAITING_REVIEW, CHANGE_REQUESTED, REJECTED, EPOCH, PENDING_CORRECTION.
- **ReviewStatus** enum: AWAITING_REVIEW, CHANGE_REQUESTED, RESUBMITTED, APPROVED, REJECTED. A `Review` requires a status and a `filing_id`.
- **Acknowledge and drop (200)** in these cases:
  - The event is empty or garbled.
  - The corp type is MHR or BTR.
  - `filing_identifier` is null and the corp type is a BC type.
  - The payment is a duplicate.
- **Requeue (404)** when the filing is not found.
- **Routing after PAID**:
  - `filing_type == "continuationIn"` creates a staff Review and does not go to the Filer.
  - Otherwise the filing goes to the Filer queue only if `effective_date <= payment_completion_date`.
  - A future-dated (FED) filing is skipped.
  - The email message is published afterwards.
- **BaseEnum / BaseMeta** (`utils/base.py`): `in` checks membership by value, and `get_enum_by_value()` does a reverse lookup that returns None if nothing matches.
- **Auth**: `verify_gcp_jwt` checks the token audience, `email_verified`, and that the email equals the configured service account.

## Flows
1. Pub/Sub POSTs a CloudEvent to the root endpoint, and the JWT is verified.
2. The worker parses the `PaymentToken` and applies the early-exit rules above.
3. It loads the Filing by payment token. If none is found, it returns 404.
4. It sets the status to PAID, sets `payment_completion_date`, and saves.
5. It creates a Review for continuationIn. Otherwise, if the effective date has been reached, it publishes the filing message to NATS.
6. It publishes the email message and returns 200.

`create_app()` builds the Flask app. It initializes the database, registers the blueprints, and activates the GCP queue and the NATS queue service. Sentry is enabled only when `SENTRY_DSN` is set.

## Where to look
- `src/business_pay/resources/pay_filer.py`: the core event-handling logic and routing rules.
- `src/business_pay/services/__init__.py`: the message builders and the `gcp_queue` and `queue` instances.
- `src/business_pay/services/gcp_auth.py` and `services/queue.py`: token verification and NATS publishing.
- `src/business_pay/database/filings.py` and `review.py`: the models and status enums.
- `src/business_pay/config.py`: all settings.
- `tests/integration/test_worker_queue.py`: an end-to-end example of the expected messages.

## Caution
- `verify_gcp_jwt` returns an error string, or an empty string when valid. It never returns a boolean or raises, so callers must test truthiness.
- After the filing is marked PAID, publish errors are suppressed. A filing can therefore be PAID but never queued, and the event is still acknowledged.
- `get_filing_by_payment_token()` swallows all exceptions and returns None. A database error therefore looks like "not found" and causes a requeue.
- `create_email_msg` hardcodes `"option": "PAID"` for every filing type.
- `readyz` and `healthz` return fixed 200 responses and check no dependencies.
- `wsgi.py` runs Flask's development server through `app.run()`, not a production WSGI server.
- `create_app(**kwargs)` ignores its kwargs.
- The default `NATS_SERVERS` has a trailing comma, which leaves an empty entry after a split.
- `SENTRY_DSN='null'` becomes an empty string.
- `VCS_REF="missing"` is treated as unset.
- `NATS_FILER_SUBJECT` may be a misspelling of "FILTER", so check the name before relying on it.
- `queue.is_closed` catches `RuntimeError` and prints to stdout.
- `utils.py` and the `utils/` package both exist. This is ambiguous for imports such as `get_run_version`.
- In the integration test, `found_filing_msg` and `found_email_msg` are never initialized. A mismatch in the published messages raises `NameError` instead of a clear assertion failure.

# blackbox-free

# business-pay (queue service)

## Purpose
A small Flask worker that reacts to **payment-completion events** for business filings. It marks the matching filing as paid, then either hands it to the Filer queue or creates a staff review, and finally notifies the email queue. It is a push-style worker: it does not poll anything. It sits between the payment system and the filer and emailer services.

## Inputs and outputs
- **In:** HTTP POST of a GCP Pub/Sub push message wrapping a CloudEvent. The payload is a `PaymentToken` with `id`, `status_code`, `filing_identifier` and `corp_type_code`. The request carries a Google OAuth bearer token.
- **Reads and writes:** the shared Postgres `filings` table, and `reviews` for review records. Filings are looked up by payment token.
- **Out:**
  - JSON messages published to NATS Streaming, on the filer subject (`NATS_FILER_SUBJECT`) and the emailer subject.
  - Filing: `{"filing": {"id": <id>}}`
  - Email: `{"email": {"filingId": <id>, "type": <filing_type>, "option": "PAID"}}`
  - HTTP status codes back to Pub/Sub. 200 means the message is acknowledged and removed. 404 means it is requeued and redelivered.
- **Also exposed:** `/ops/healthz` and `/ops/readyz`, which are for orchestrator probes.

## Main flow (`resources/pay_filer.py`)
1. Verify the caller with `services/gcp_auth.verify_gcp_jwt`. It checks the token audience (`SUB_AUDIENCE`), `email_verified`, and that the email matches `SUB_SERVICE_ACCOUNT`.
2. Parse the CloudEvent. If the body is empty or garbled, return 200 (drop it).
3. Drop with 200 for `MHR` or `BTR` corp types. Also drop when `filing_identifier` is null and the corp type is a BC type.
4. Load the `Filing` by payment token. If none is found, return 404 so the message is retried. This handles the race where the filing row is not yet committed.
5. If the filing is already paid (a duplicate event), return 200 and do nothing.
6. Set the status to `PAID` and set `payment_completion_date`, then save.
7. Branch on filing type:
   - `continuationIn` creates a staff `Review` (status `AWAITING_REVIEW`) and does not go to the filer.
   - Any other type is published to the filer queue only if `effective_date <= payment_completion_date`. Future-dated (FED) filings are skipped.
8. Publish the email message.
9. Return 200.

## Concepts and states
- **Filing** (`database/filings.py`) maps the existing filings table and is shared with other services. Its status enum is DRAFT, PENDING, PAID, COMPLETED, CORRECTED, ERROR, APPROVED, AWAITING_REVIEW, CHANGE_REQUESTED, REJECTED, EPOCH and PENDING_CORRECTION. This service essentially moves a filing to PAID. `get_filing_by_payment_token()` is the lookup.
- **Review / ReviewStatus** (`database/review.py`). The states are AWAITING_REVIEW, CHANGE_REQUESTED, RESUBMITTED, APPROVED and REJECTED. A review requires a `filing_id` and a status. `save()` commits immediately.
- **Queue publishing** (`services/queue.py`) has a lazy NATS/STAN connection that is made on the first publish and closed at Flask teardown. It offers `publish_json` and `async_publish_json`. `services/__init__.py` builds the messages with `create_filing_msg` and `create_email_msg`, and holds the module singletons `gcp_queue` and `queue`.
- **Enums** (`utils/base.py`): `BaseEnum` adds `in` membership checks and `get_enum_by_value`.
- **Config** (`config.py`): `get_named_config` returns Dev, Test or Prod config. It covers the DB URI, NATS settings, GCP credentials, the Sentry DSN and the payment URL.
- **App factory:** `create_app()` in `__init__.py` wires the DB, the endpoints and the queues, and enables Sentry if a DSN is set.

## Where to start
- `resources/pay_filer.py` has all the business logic.
- `services/__init__.py`, `services/queue.py` and `services/gcp_auth.py` cover the messages, the publishing and the auth.
- `database/filings.py` and `database/review.py` hold the models.
- `config.py` and `__init__.py` cover setup.
- `tests/integration/test_worker_queue.py` shows the expected end-to-end behaviour. `tests/data/create_database.sql` is the test schema.

## Hazards
- **Failed publishes are invisible.** Publish failures are swallowed after the filing is saved as PAID, so a failed publish is neither retried nor surfaced. The filing then stays PAID and never reaches the filer. `get_filing_by_payment_token()` also swallows all exceptions and returns None. A database error therefore looks like "not found" and produces a 404 requeue.
- **Return codes drive redelivery.** 200 drops the message and 404 retries it. Changing a branch's code changes retry and loss behaviour.
- **Auth returns a string.** `verify_gcp_jwt` returns an empty string on success and an error message on failure. Callers must check truthiness, not a boolean.
- **The email option is fixed.** `create_email_msg` always sends `"option": "PAID"`, whatever the filing type.
- **Column and name mismatches.** `Filing.payment_token` maps to the DB column `payment_id`. The `filings` schema is shared and has many nullable, filing-type-dependent columns. `NATS_FILER_SUBJECT` may be a misspelling of "FILTER", so check the spelling before renaming it.
- **Config quirks.** The default `NATS_SERVERS` has a trailing comma, which gives an empty entry after splitting. `SENTRY_DSN` of the string `'null'` becomes empty. `create_app(**kwargs)` ignores its kwargs.
- **Health checks are static.** `readyz` returns a fixed 200 and checks no dependencies.
- **Dev server in production.** `wsgi.py` runs `app.run()` (the Flask development server) on `PORT`, default 8080. It is not a production WSGI server.
- **Version quirk.** `utils.get_run_version` treats `VCS_REF="missing"` as unset.
- **Duplicate `utils`.** Both `utils.py` and a `utils/` package exist under `business_pay`, which can cause import ambiguity.
- **Test fragility.** The integration test needs NATS Streaming. It also crashes with a `NameError`, instead of failing cleanly, when the expected messages do not arrive.

# purpose-budget

# business-pay queue service

A small Flask worker for the Entity Payment flow. It receives payment-completion events, marks the matching filing as paid, and then either queues the filing for the Filer or creates a staff review. It also notifies the email queue. It is meant for people operating or changing the filings pipeline.

## Inputs and outputs
- **In:** GCP Pub/Sub push CloudEvents (`SimpleCloudEvent`) carrying a `PaymentToken` (id, status_code, filing_identifier, corp_type_code). Requests are authenticated by `services/gcp_auth.py`.
- **Reads/writes:** the shared PostgreSQL `filings` table and the `reviews` table, through SQLAlchemy models.
- **Out:** NATS Streaming messages to the filer subject and the email subject. Also an HTTP response, whose status code decides whether Pub/Sub removes or redelivers the message.

## Ideas it owns
- **Payment application** (`resources/pay_filer.py`): looks up a `Filing` by `payment_token` and sets it PAID with `payment_completion_date`.
- **Routing after payment:**
  - If `filing_type` is `continuationIn`, it creates a staff `Review` (status AWAITING_REVIEW).
  - Otherwise it publishes to the filer queue, but only when `effective_date <= payment_completion_date`. Future-dated (FED) filings are skipped.
  - It then publishes to the email queue.
- **Ack semantics:**
  - 200 (message dropped) for empty or garbled events, MHR/BTR corp types, a null `filing_identifier` with a BC corp type, and duplicate payments.
  - 404 (message requeued) when the filing is not found.
- **Message shapes** (`services/__init__.py`): `create_filing_msg` builds `{"filing":{"id"}}`. `create_email_msg` builds `{"email":{"filingId","type","option":"PAID"}}`.
- **Token verification** (`gcp_auth.verify_gcp_jwt`): checks the bearer token against `SUB_AUDIENCE` and `SUB_SERVICE_ACCOUNT`, and requires `email_verified`.
- **Enum helpers** (`utils/base.py`): `BaseEnum` and `BaseMeta` add `in` checks and `get_enum_by_value`.

## Main flow
1. `wsgi.py` calls `create_app()`, which sets up the DB, registers the blueprints, and starts the GCP and NATS queue services.
2. A POST arrives at the root route. The bearer token is verified and the CloudEvent is parsed.
3. The filing is fetched and the early-exit rules are applied.
4. The filing is marked PAID and committed. Then the filer message (or review) and the email message are published.

`/ops/healthz` and `/ops/readyz` return fixed 200 responses.

## Open first
- `src/business_pay/resources/pay_filer.py`: all the decision logic.
- `src/business_pay/services/queue.py` and `services/__init__.py`: NATS publishing and message builders.
- `src/business_pay/database/filings.py` and `review.py`: the models.
- `tests/integration/test_worker_queue.py`: the expected end-to-end behaviour.

## Hazards
- Once the filing is marked PAID, publish failures are swallowed. A filing can therefore be PAID but never queued, and the message is not retried.
- `get_filing_by_payment_token` swallows exceptions and returns `None`, so a DB error looks like "not found" (404, requeue).
- `payment_token` maps to the column `payment_id`.
- `create_email_msg` hardcodes `option: "PAID"`.
- `gcp_auth` returns an error string, or an empty string on success, rather than raising an exception. Callers must check truthiness.
- `readyz` checks no dependencies.
- `wsgi.py` uses Flask's dev server.
- The default `NATS_SERVERS` value has a trailing comma, which leaves an empty element after splitting.
- The `NATS_FILER_SUBJECT` key may be misspelled.
- `create_app(**kwargs)` ignores its kwargs.
- The integration test hits a `NameError` if the expected messages don't arrive, because its loop variables are never initialised.
- There are both a `utils.py` module and a `utils/` package. Check which one is imported.

# decisions

# business-pay queue service

A small Flask worker that receives GCP Pub/Sub CloudEvents announcing payment results. It marks the matching Filing as paid, then hands it on to the Filer queue and the email queue, or creates a staff Review. It belongs to the BC Registries business filings system (`queue_services/business-pay`).

## Entry and wiring
- `wsgi.py` calls `create_app()` and runs Flask's development server (`app.run()`) on `PORT` (default 8080), bound to 0.0.0.0 with debug off.
- `business_pay/__init__.py`: `create_app(config=ProdConfig)` initialises the DB and registers the endpoints. It also activates `gcp_queue` and `queue`, and enables Sentry only if `SENTRY_DSN` is set. It accepts `**kwargs` and ignores them.
- `config.py`: `load_dotenv()` plus `get_named_config(name)`, which returns a DevConfig, TestConfig or ProdConfig. It holds:
  - the Postgres URI (optionally via a Unix socket);
  - the NATS settings: `NATS_SERVERS`, `NATS_CLIENT_NAME`, `NATS_CLUSTER_ID`, `NATS_QUEUE`, `NATS_FILER_SUBJECT`, `NATS_EMAILER_SUBJECT` and the subscription/publish options;
  - the GCP service-account credentials;
  - the Sentry DSN and the payment service URL.
  - Defaults are Postgres 5432, NATS 127.0.0.1:4222 and environment "prod".
- `resources/__init__.py` registers `pay_filer_endpoint` at the root and `ops_endpoint` at `/ops`, with `strict_slashes = False`.
- `resources/ops.py` exposes `healthz` and `readyz`. Both return HTTP 200 with a fixed JSON message and check no dependencies.

## Inbound message and auth
- A Pub/Sub push arrives at the pay_filer endpoint as a SimpleCloudEvent. Its payload is a PaymentToken with `id`, `status_code`, `filing_identifier` and `corp_type_code`.
- `services/gcp_auth.py` `verify_gcp_jwt(request)` reads the bearer token and calls `id_token.verify_oauth2_token()` with audience `SUB_AUDIENCE`. It requires `email_verified` to be true and `email` to equal `SUB_SERVICE_ACCOUNT`. It returns `""` when the token is valid and an error string otherwise.

## Decisions in `resources/pay_filer.py`
- The handler acknowledges with 200, so the message is dropped, in these cases:
  - the event is empty or garbled;
  - `corp_type_code` is MHR or BTR;
  - `filing_identifier` is null and the corp type is a BC type;
  - the payment is a duplicate.
- It returns 404, so the message is requeued, if no Filing matches the payment token. The lookup is `Filing.get_filing_by_payment_token`.
- Otherwise the flow is:
  1. Set the filing status to PAID and `payment_completion_date`.
  2. If `filing_type == "continuationIn"`, create a staff Review.
  3. Otherwise, if `effective_date <= payment_completion_date`, publish `create_filing_msg` to the filer queue. Future-dated filings (FED) are skipped.
  4. Publish `create_email_msg` to the email queue.

## Outbound messages (`services/__init__.py`)
- Filer: `{"filing": {"id": identifier}}`.
- Email: `{"email": {"filingId": identifier, "type": filing_type, "option": "PAID"}}`. `option` is hardcoded to `"PAID"` for every filing type.
- `services/queue.py` is a NATS Streaming (STAN) publisher with `publish_json()` and `async_publish_json()`. It connects lazily on the first publish and disconnects at Flask teardown. It exposes `is_connected` and `is_closed`.

## Data
- `database/filings.py` `Filing` has these fields: `id`, `effective_date`, `filing_type`, `filing_sub_type`, `filing_json`, `payment_completion_date`, `payment_status_code`, `payment_token`, `status` and `payment_account`. The `status` enum has 12 values, from DRAFT through PENDING_CORRECTION. `payment_token` is mapped to the DB column `payment_id`.
- `database/review.py` `Review` holds `nr_number`, `identifier`, `completing_party`, `status` (required), `submission_date`, `creation_date` and a required `filing_id`. `save()` commits immediately. `ReviewStatus` has AWAITING_REVIEW, CHANGE_REQUESTED, RESUBMITTED, APPROVED and REJECTED.
- `database/db.py` holds the shared `db` and `Base`. `database/__init__.py` re-exports `Filing`, `Review` and `ReviewStatus`.
- `utils/base.py` `BaseEnum`/`BaseMeta` make `in` work on enum values and add `get_enum_by_value()`.
- `utils.py` `get_run_version()` returns the package version plus `VCS_REF`, unless `VCS_REF` is "missing".

## Behaviour pinned by tests
- The integration test posts a COMPLETED payment for a PENDING annualReport filing (id 12). It expects exactly two NATS messages within 2 seconds: `{"filing":{"id":12}}` and `{"email":{"filingId":12,"type":"annualReport","option":"PAID"}}`.
- The unit test only checks that the version string is non-empty.
- `tests/data/create_database.sql` is the filings table fixture.

## Hazards
- Once the filing is marked PAID, publish failures are suppressed. A filing can stay PAID without ever being sent to the filer or email queue, and the message is still acknowledged.
- `get_filing_by_payment_token` swallows every exception and returns None. A DB error therefore looks like "not found" and returns 404, which requeues the message.
- `verify_gcp_jwt` returns a string rather than raising. A caller that does not check its truthiness will accept unauthenticated requests.
- `readyz` and `healthz` always report healthy, even when the DB or NATS is down.
- `NATS_SERVERS` defaults to a value with a trailing comma, so splitting it leaves an empty element. `wsgi.py` also runs the Flask dev server, not a production WSGI server.

# map

# business-pay queue service

A small Flask worker (part of the BC Registries Entity filings system) that applies payment-completion events to Filings. It receives GCP Pub/Sub CloudEvents carrying a PaymentToken (id, status_code, filing_identifier, corp_type_code), authenticated by a Google OAuth bearer token. It updates the filings database and publishes JSON messages to NATS Streaming, to the Filer queue and the Emailer queue (GCP queue services are also wired in).

## Main flows

**Payment event (`resources/pay_filer.py`)**
1. `gcp_auth.verify_gcp_jwt` checks the bearer token. It returns an empty string when the token is valid and an error message otherwise, so callers must test truthiness. It verifies the token against `SUB_AUDIENCE`, requires `email_verified`, and requires the email to equal `SUB_SERVICE_ACCOUNT`.
2. The event is parsed. Empty or garbled events, MHR/BTR corp types, and a null `filing_identifier` with a BC corp type return 200, so the message is removed from the queue.
3. The Filing is looked up with `Filing.get_filing_by_payment_token`. If none is found, the handler returns 404 and the message is requeued. If the filing is already paid (a duplicate), it returns 200.
4. The filing is marked PAID and `payment_completion_date` is set.
5. If `filing_type` is "continuationIn", a staff `Review` is created.
6. Otherwise, if `effective_date <= payment_completion_date`, `create_filing_msg` publishes `{"filing": {"id": ...}}` to the filer subject. Future-dated filings (FED) are not published.
7. `create_email_msg` publishes `{"email": {"filingId", "type", "option": "PAID"}}` to the email queue.

**Health (`resources/ops.py`)**
- `/ops/healthz` and `/ops/readyz` return a fixed 200 JSON message.

**App startup (`__init__.py`, `wsgi.py`, `config.py`)**
- `create_app(config)` defaults to ProdConfig. It initialises the db, registers the endpoints (`pay_filer_endpoint` at root, `ops_endpoint` at `/ops`, non-strict slashes) and activates both queue services. It enables Sentry only if `SENTRY_DSN` is set.
- `wsgi.py` runs `app.run()` on `PORT` (default 8080).

## Source map

- `__init__.py`: the app factory. `**kwargs` is accepted but ignored.
- `config.py`: DevConfig, TestConfig and ProdConfig, selected by `get_named_config(name)`. Holds the Postgres URI, NATS settings, GCP credentials, the Sentry DSN and the payment URL. `.env` is loaded.
- `database/db.py`: the SQLAlchemy `db` and `Base`.
- `database/filings.py`: the Filing model. `payment_token` maps to column `payment_id`. It has the `status` enum (DRAFT, PENDING, PAID, COMPLETED and others), `save()` and `get_filing_by_payment_token()`.
- `database/review.py`: the `ReviewStatus` enum and the Review model, which has a required filing FK. `save()` commits immediately.
- `database/__init__.py`: re-exports Filing, Review and ReviewStatus.
- `resources/pay_filer.py`: the payment handler described above.
- `resources/ops.py`: the health endpoints.
- `resources/__init__.py`: blueprint registration.
- `services/__init__.py`: the `gcp_queue` and `queue` instances, and the message builders `create_filing_msg` and `create_email_msg`.
- `services/gcp_auth.py`: the bearer-token verification.
- `services/queue.py`: a NATS Streaming (STAN) publisher with a lazy connection on first publish. It disconnects at Flask teardown and offers sync `publish_json` and async `async_publish_json`. It uses nest_asyncio.
- `utils.py`: `get_run_version()`, which returns the package version plus `VCS_REF` when that is set.
- `utils/base.py`: `BaseMeta` and `BaseEnum`. `in` checks membership by constructing the value, and `get_enum_by_value` does reverse lookup.
- Trivial: LICENSE, empty package `__init__` files (`utils/__init__.py`, the tests' `__init__.py`).

## Tests

- `tests/integration/test_worker_queue.py` inserts a PENDING annualReport filing (id 12) whose `payment_id` matches the token. It mocks Google OAuth and NATS, then posts a COMPLETED payment event. It asserts that exactly two NATS messages arrive within 2 seconds: `{"filing":{"id":12}}` and `{"email":{"filingId":12,"type":"annualReport","option":"PAID"}}`.
- `tests/unit/test_version.py` asserts that `get_run_version()` returns a truthy value.
- `tests/data/create_database.sql` is the filings table schema fixture. Many columns are nullable and there are flag columns such as `paper_only`, `colin_only` and `deletion_locked`.

## Hazards

1. **Swallowed publish errors.** After the filing is marked PAID, publish exceptions are suppressed. A failed filer or email publish still returns success, so the message is not retried and the filing is never queued.
2. **Auth returns a string, not a boolean.** `verify_gcp_jwt` returns "" on success. Code that treats the return value as a boolean inverts the check.
3. **Silent lookup failure.** `get_filing_by_payment_token` catches all exceptions and returns None. A database error therefore looks like "filing not found" (404 and requeue).
4. **Hardcoded email option and filer subject.** `create_email_msg` always sends `"option": "PAID"`, whatever the filing type. The config key `NATS_FILER_SUBJECT` may be misspelled.
5. **Config and runtime quirks.**
   - The default `NATS_SERVERS` has a trailing comma, which leaves an empty element after splitting.
   - A `SENTRY_DSN` of "null" becomes an empty string.
   - `readyz` checks nothing.
   - `wsgi.py` runs the Flask development server.

# decisions-ctx

# business-pay queue service

A small Flask worker in `queue_services/business-pay` that receives payment-completion events from GCP Pub/Sub. It marks the matching filing PAID, then hands the filing on to the filer queue and the emailer queue. It is one of the LEAR `queue_services` workers, alongside entity-filer and entity-emailer.

## Inputs and outputs

**In:** an authenticated HTTP POST carrying a GCP Pub/Sub push envelope.
- The envelope wraps a CloudEvent, parsed as a `SimpleCloudEvent`.
- The event data is a `PaymentToken` with `id`, `status_code`, `filing_identifier` and `corp_type_code`.
- `services/gcp_auth.py` verifies the bearer token from the Authorization header with `id_token.verify_oauth2_token()`.
  - The audience is `SUB_AUDIENCE`.
  - The token's `email_verified` claim must be true.
  - The token's `email` must equal `SUB_SERVICE_ACCOUNT`.

**Out:** JSON messages published to NATS Streaming (STAN) through `services/queue.py`. Messages go to `NATS_FILER_SUBJECT` and `NATS_EMAILER_SUBJECT`. The message builders are in `services/__init__.py`:
- `create_filing_msg(identifier)` returns `{"filing": {"id": identifier}}`.
- `create_email_msg(identifier, filing_type)` returns `{"email": {"filingId": identifier, "type": filing_type, "option": "PAID"}}`.

**Health endpoints:** `/ops/healthz` and `/ops/readyz` return a fixed 200 JSON message (`api is healthy` / `api is ready`).

## Decisions in `resources/pay_filer.py`

The HTTP response code tells Pub/Sub what to do with the message. 200 removes it. 404 requeues it for redelivery.

| Condition | Outcome |
|---|---|
| Empty or garbled message | 200, dropped |
| `corp_type_code` is MHR or BTR | 200, dropped |
| `filing_identifier` is null and the corp type is a BC type | 200, dropped |
| No `Filing` found for the payment token | 404, requeued |
| Filing is already paid (duplicate payment) | 200, dropped |
| Otherwise | Filing is set to PAID and `payment_completion_date` is set |
| `filing_type == "continuationIn"` | A staff `Review` is created and nothing goes to the filer queue |
| Any other type and `effective_date <= payment_completion_date` | A filing message is published to the filer queue |
| Future-dated filings (FED) | Not published to the filer queue |
| After the PAID marking | An email message is published to the emailer queue |

## Data

- **`database/filings.py`:** the `Filing` model.
  - Fields: `id`, `effective_date`, `filing_type`, `filing_sub_type`, `filing_json`, `payment_completion_date`, `payment_status_code`, `payment_token`, `payment_account` and `status`.
  - `status` is an enum covering DRAFT, PENDING, PAID, COMPLETED, ERROR, AWAITING_REVIEW and others.
  - `get_filing_by_payment_token()` looks up a filing.
  - `save()` persists one.
- **`database/review.py`:** the `Review` model and the `ReviewStatus` enum (AWAITING_REVIEW, CHANGE_REQUESTED, RESUBMITTED, APPROVED, REJECTED).
  - Fields: `nr_number`, `identifier`, `completing_party`, `status`, `submission_date`, `creation_date` and the required `filing_id`.
  - `save()` commits immediately.
- **`database/db.py`:** the `db` and `Base` objects.
- **`utils/base.py`:** `BaseEnum`, whose metaclass makes `in` work by value and which adds `get_enum_by_value()`.

## Where to start

- `resources/pay_filer.py` holds all the business logic.
- `services/__init__.py` holds the message builders and the `gcp_queue` and `queue` instances.
- `services/queue.py` holds the NATS publisher. It connects lazily on the first publish and disconnects at Flask teardown.
- `config.py` holds the environment settings (database, NATS, GCP, Sentry).
- `__init__.py` holds `create_app()`, which sets up the database, the endpoints, the queues and optional Sentry.
- `wsgi.py` is the entry point. It runs `app.run()` on `PORT` (default 8080).

The integration test pins the end-to-end behaviour. A COMPLETED payment event for a PENDING `annualReport` filing (id 12) produces exactly two NATS messages: `{"filing":{"id":12}}` and `{"email":{"filingId":12,"type":"annualReport","option":"PAID"}}`.

## Hazards

- **Publish failures are lost silently.** After the filing is marked PAID, publish exceptions are suppressed. A failed publish leaves the filing PAID but never sent to the filer or emailer, and Pub/Sub still gets a 200, so it will not retry.
- **Auth returns a string, not a boolean.** `gcp_auth` returns an empty string when the token is valid and an error message when it is not. A caller must check the return value's truthiness, and ignoring it skips authentication.
- **Lookup errors look like "not found".** `get_filing_by_payment_token()` swallows every exception and returns None. A database error therefore produces a 404 requeue, as if the filing did not exist.
- **The email option is always "PAID".** `create_email_msg` hardcodes `"option": "PAID"` whatever the filing type.
- **Config traps.**
  - The `NATS_SERVERS` default has a trailing comma, which leaves an empty entry after splitting.
  - A `SENTRY_DSN` of the string `'null'` is converted to an empty string.
  - `wsgi.py` uses Flask's development server, not a production WSGI server.
