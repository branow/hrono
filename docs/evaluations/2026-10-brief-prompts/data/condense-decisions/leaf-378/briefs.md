# today

# business-pay queue service (Entity Payment)

A small Python/Flask service (BSD 3-Clause, Province of British Columbia, 2024) under `queue_services/business-pay`. It receives GCP Pub/Sub cloud events announcing completed payments and marks the matching Filing as PAID. It then publishes follow-up messages to NATS/STAN queues (filer and emailer). It uses SQLAlchemy (Postgres via pg8000), Sentry, and GCP JWT auth. Filings of type continuationIn get a Review record instead of going to the filer queue.

## Application bootstrap
- `wsgi.py`: entry point. Calls `create_app()` and runs on `0.0.0.0`, port from `PORT` (default 8080), `debug=False`.
- `business_pay/__init__.py`: the `create_app(environment=ProdConfig)` factory. It loads config, initializes Sentry only if `SENTRY_DSN` is set (`send_default_pii=False`), then initializes `db`, endpoints, `gcp_queue` and `queue`.
- `config.py`: `get_named_config(name)` maps production, staging and default to ProdConfig, testing to TestConfig, and development to DevConfig. Unknown names raise KeyError. It covers:
  - DB URI building (Unix socket or TCP)
  - `PAYMENT_SVC_URL`
  - Sentry
  - NATS/STAN connection and subscription options, with separate publish options for the filer and emailer subjects
  - GCP credentials and audiences
  - TestConfig, which uses `DATABASE_TEST_*` variables
- `utils.py`: `get_run_version()` returns the package version, with `-<VCS_REF>` appended unless `VCS_REF` is empty or "missing". `utils/__init__.py` is an empty placeholder package. `utils/base.py` holds `BaseEnum` (str + Enum) with `get_enum_by_value`, and `BaseMeta`, whose `__contains__` checks membership by trying to construct the member.

## HTTP resources
- `resources/__init__.py`: `register_endpoints` sets `strict_slashes=False` and registers `pay_filer_endpoint` at "/" and `ops_endpoint` at "/ops".
- `resources/ops.py`: `/healthz` and `/readyz` return static JSON with HTTP 200.
- `resources/pay_filer.py`: the core handler.
  - It validates the GCP JWT, then handles events of type `bc.registry.payment`. It finds the Filing by payment token id.
  - It returns 200 (drop the message) for:
    - empty or malformed messages
    - status other than COMPLETED
    - corp types MHR and BTR
    - filings already paid
    - the case of identifier None with corp type BC
  - It returns 404 (retry) if the filing is not found.
  - Otherwise it sets `payment_completion_date`, `payment_status_code` COMPLETED and status PAID.
  - For continuationIn it creates a Review with AWAITING_REVIEW. For other types it publishes to the filer queue when `effective_date <= payment_completion_date`.
  - It then publishes to the email queue.
  - Helpers: `dict_keys_to_snake_case()` and `get_completing_party()`.

## Services
- `services/__init__.py`: message builders `create_filing_msg` and `create_email_msg`. It also instantiates `gcp_queue` (GcpQueue) and `queue` (QueueService).
- `services/gcp_auth.py`: verifies the bearer token with Google `id_token.verify_oauth2_token`. It checks the audience (`SUB_AUDIENCE`), `email_verified`, and that the email equals `SUB_SERVICE_ACCOUNT`.
- `services/queue.py`: Flask extension for publishing JSON to NATS streaming (STAN). It has a sync `publish_json()` wrapper over `async_publish_json()`, auto-connects, and closes on app teardown. The default subject is `NATS_FILER_SUBJECT`.

## Database models
- `database/db.py`: the `db` SQLAlchemy instance and `Base`.
- `database/__init__.py`: re-exports Filing, Review and ReviewStatus.
- `database/filings.py`: minimal Filing mapping, just enough to mark a filing paid. It has a 13-value Status enum (default DRAFT), `save()`, and `get_filing_by_payment_token()`.
- `database/review.py`: Review model with a `ReviewStatus` enum (AWAITING_REVIEW, CHANGE_REQUESTED, RESUBMITTED, APPROVED, REJECTED). It has a non-null foreign key to filings and a `save()` method.

## Tests
- `tests/data/create_database.sql`: fixture creating the 29-column `filings` table.
- `tests/integration/test_worker_queue.py`: `test_complete_worker` posts a base64-wrapped Pub/Sub envelope with a mocked token verifier. It subscribes to NATS and asserts the filer message `{"filing": {"id"}}` and the email message with option PAID.
- `tests/unit/test_version.py`: asserts `get_run_version()` is truthy.
- The `__init__.py` files in the test packages contain only license headers.

## Caution
- `NATS_CONNECT_ERROR_COUNT_MAX` is a string ("10"), so numeric comparisons fail.
- The Unix socket URI appends a hardcoded `/.s.PGSQL.5432` to `DATABASE_UNIX_SOCKET`.
- `Filing.payment_token` maps to the DB column `payment_id`.
- `get_filing_by_payment_token` swallows all exceptions and returns None. The handler may then treat a DB error as "not found" (404, retry).
- Publish failures are suppressed in `pay_filer`. The filing is already marked PAID by then, so a failed publish leaves a paid filing with no filer or email message.
- Returning 200 for BC with a None identifier removes the message from the queue instead of retrying.
- `gcp_auth` returns an empty string on success and an error message on failure. Callers must check truthiness, and all exceptions are caught broadly.
- `Review.save()` commits immediately with no error handling, and is not transactional with other operations.
- The email payload hardcodes `"option": "PAID"` (a TODO says to use an Enum).
- The `ops.py` handlers are declared `async` but are purely synchronous. The `/readyz` function is just named `get`.
- `QueueService.is_closed` uses `print()` and catches RuntimeError.
- There are both `utils.py` and a `utils/` package. The two names collide, so one shadows the other.
- Test issues:
  - `create_filing()` builds SQL with unescaped f-strings (injection risk).
  - `test_complete_worker` doesn't initialize `found_filing_msg` and `found_email_msg`, so it can raise NameError.

# purpose-budget

# business-pay queue service

A small Flask service that receives GCP Pub/Sub push notifications about completed payments. It marks the matching business filing as paid and hands the filing off to downstream processors. It is meant for the backend operators and developers of the BC registry filing pipeline.

## Inputs and outputs

- **In:** an HTTP POST from GCP Pub/Sub. It carries a base64 cloud-event envelope with type `bc.registry.payment` and a PaymentToken (id, statusCode, filingIdentifier, corpTypeCode). The request is authenticated by a GCP bearer JWT.
- **Reads and writes:** the shared Postgres `filings` table, and the `reviews` table for continuation-in filings.
- **Out:** NATS streaming messages to the filer subject (`{"filing": {"id"}}`) and the emailer subject (`{"email": {"filingId", "type", "option": "PAID"}}`).
- **Probes:** `/ops/healthz` and `/ops/readyz` return static JSON.

## Ideas it owns

- **Token check.** `gcp_auth` verifies the bearer token against `SUB_AUDIENCE`. It also requires a verified email equal to `SUB_SERVICE_ACCOUNT`. It returns an empty string on success and an error message on failure, so callers must test truthiness.
- **Filing state.** The `Filing` model is a minimal mapping with a `Status` enum. The service moves a filing to `PAID` and sets `payment_completion_date` and `payment_status_code="COMPLETED"`. `payment_token` maps to the column `payment_id`.
- **Review.** `Review` (with `ReviewStatus`) records an `AWAITING_REVIEW` entry for `continuationIn` filings instead of sending them to the filer.
- **Ack and retry rules.** A 200 removes the message from the queue. A 404 makes Pub/Sub retry.

## Main flow (`resources/pay_filer.py`)

1. Verify the JWT and decode the envelope.
2. Ignore, with 200, any message that is empty, malformed, not of the payment type, or whose status is not COMPLETED.
3. Also ignore, with 200, `MHR` and `BTR` corp types, filings that already have a completion date, and `BC` payments with no filing identifier.
4. Look up the filing by payment token id. Return 404 if it is not found.
5. Set the paid fields and save.
6. For `continuationIn`, create the Review. Otherwise publish to the filer, but only if `effective_date <= payment_completion_date`.
7. Publish to the emailer.

`create_app` in `__init__.py` wires config, Sentry (optional), the db, the endpoints, `gcp_queue` and `queue`. `wsgi.py` runs it.

## Open first

- `resources/pay_filer.py`: all the business rules.
- `services/queue.py` and `services/__init__.py`: NATS/STAN publishing and the message builders.
- `database/filings.py` and `database/review.py`: the models.
- `config.py`: env-driven settings.

## Hazards

- The filing is saved as PAID before publishing. Publish errors are swallowed, so a failed publish leaves a paid filing with no filer or email message and no retry.
- `get_filing_by_payment_token` swallows all exceptions and returns None, so a database error looks like "not found" and returns 404.
- `NATS_CONNECT_ERROR_COUNT_MAX` is a string, so numeric comparisons break.
- The unix-socket DB URL appends a hardcoded `/.s.PGSQL.5432`.
- `Review.save()` commits immediately, with no error handling.
- The email option `"PAID"` is hardcoded.
- Both `ops` handlers are declared `async`, and `get()` serves `/readyz`.
- `src/business_pay/utils.py` and the `utils/` package share the name `utils`. The package would shadow the module, so check how `get_run_version` is resolved.
- The integration test builds SQL with f-strings. It needs a live NATS server and the schema in `tests/data/create_database.sql`.

# decisions

# business-pay queue service

A small Flask service in the BC Registries queue-services system. It receives GCP Pub/Sub push events announcing that a payment completed, marks the matching business filing as paid, and then publishes follow-up messages to NATS streaming queues (filer and emailer). Continuation-in filings are sent to review instead of the filer.

## Inputs and outputs

**In:** HTTP POST to `/` (blueprint `pay_filer_endpoint`, `resources/pay_filer.py`).
- The body is a Pub/Sub envelope containing a base64-encoded cloud event.
- The event has `ce.type == "bc.registry.payment"`.
- Its data is a PaymentToken with camelCase keys, converted by `dict_keys_to_snake_case()`. It carries the payment `id`, `statusCode`, `filingIdentifier` and `corpTypeCode`.
- The Authorization header holds `Bearer <GCP JWT>`.

**Out:**
- DB writes to the `filings` table (and `reviews` for continuation-in).
- NATS messages built in `services/__init__.py`:
  - Filer subject (`NATS_FILER_SUBJECT`): `{"filing": {"id": <id>}}` from `create_filing_msg`.
  - Emailer subject: `{"email": {"filingId": <id>, "type": <filing_type>, "option": "PAID"}}` from `create_email_msg`.
- HTTP status codes back to Pub/Sub: 200 acknowledges and removes the message, 404 makes it retry.

**Health:** `/ops/healthz` and `/ops/readyz` (`resources/ops.py`) return static JSON with 200.

## Decisions in `pay_filer.py`

- Auth: `services/gcp_auth.py` verifies the token with `id_token.verify_oauth2_token` against `SUB_AUDIENCE`. It requires `email_verified` and email == `SUB_SERVICE_ACCOUNT`. It returns "" on success and an error string otherwise.
- Return 200 and drop the message when any of these hold:
  - The message is empty or malformed.
  - The event type is not `bc.registry.payment`.
  - `statusCode` is not "COMPLETED".
  - `corp_type_code` is in ["MHR", "BTR"].
  - The filing already has `payment_completion_date`.
  - `filing_identifier` is None and `corp_type_code` is "BC".
- Return 404 (retry) if no Filing matches `payment_token.id`. The lookup is `Filing.get_filing_by_payment_token`.
- Otherwise, set `payment_completion_date`, set `payment_status_code = "COMPLETED"` and set `status = Filing.Status.PAID`.
- Route by filing type:
  - If `filing_type` is in ["continuationIn"], create a `Review` with `ReviewStatus.AWAITING_REVIEW`. The completing party name comes from `get_completing_party()`, which finds the party with roleType "Completing Party".
  - Otherwise, publish to the filer queue only if `effective_date <= payment_completion_date`.
- Always publish the email message.

## Data

- `database/filings.py` `Filing` is a minimal mapping with these fields:
  - `id`, `effective_date`, `filing_type`, `filing_sub_type`.
  - `filing_json` (JSONB).
  - `payment_completion_date`, `payment_status_code`.
  - `payment_token` (the DB column is `payment_id`).
  - `status`, `payment_account`.
- `Filing.Status` enum defaults to DRAFT. It includes PAID, COMPLETED, AWAITING_REVIEW and others.
- `database/review.py` `Review` has these fields:
  - `id`, `nr_number`, `identifier`, `completing_party`.
  - `status` (`ReviewStatus`: AWAITING_REVIEW, CHANGE_REQUESTED, RESUBMITTED, APPROVED, REJECTED).
  - `submission_date`, `creation_date`.
  - `filing_id` (FK, not null).
- Both models have `save()`, which commits immediately.
- `utils/base.py` has `BaseEnum`, with `get_enum_by_value` and a `__contains__` that tests by constructing the member.

## Setup and flow

1. `wsgi.py` calls `create_app()` and runs on PORT (default 8080), host 0.0.0.0.
2. `create_app` (`__init__.py`) does the following in order:
   1. Loads the config object.
   2. Initializes Sentry if `SENTRY_DSN` is set.
   3. Calls `db.init_app`.
   4. Calls `register_endpoints`, which turns off strict slashes and registers `/` and `/ops`.
   5. Calls `gcp_queue.init_app`.
   6. Calls `queue.init_app`.
3. `services/queue.py` `QueueService` is the NATS/STAN publisher.
   - `publish_json(payload, subject=NATS_FILER_SUBJECT)` wraps `async_publish_json`, which connects if disconnected.
   - The client id is the normalized client name plus random bits.
   - Connections close on app teardown.
4. `config.py`:
   - `get_named_config` maps production, staging and default to `ProdConfig`, testing to `TestConfig`, and development to `DevConfig`. Unknown names raise KeyError.
   - It builds the DB URI. If `DATABASE_UNIX_SOCKET` is set it uses pg8000 over the socket, otherwise TCP.
   - It also holds the NATS, STAN and GCP settings.
5. `utils.py` `get_run_version()` returns the package version, with `-<VCS_REF>` appended unless `VCS_REF` is empty or "missing".

## Tests

- The integration test posts a base64 envelope for a COMPLETED payment event, with `verify_oauth2_token` mocked. It expects exactly one filer message and one email message on NATS with the shapes above.
- `tests/data/create_database.sql` defines the `filings` table used by the tests.
- The unit test only checks that the version string is truthy.

## Hazards

- The filing is saved as PAID before publishing. Exceptions in `publish_to_filer` and `publish_to_emailer` are suppressed. A failed publish therefore leaves a paid filing with no downstream message, and Pub/Sub still gets 200 so it will not retry.
- `get_filing_by_payment_token` swallows all exceptions and returns None. A DB error looks like "filing not found" and produces a 404 retry loop instead of a visible error.
- `gcp_auth` returns "" for success and an error string for failure. Callers must check truthiness, and the broad exception catch hides the cause.
- `NATS_CONNECT_ERROR_COUNT_MAX` is loaded as the string '10', so numeric comparisons against it break. The socket path suffix `/.s.PGSQL.5432` is also hardcoded.
- `save()` on `Review` and `Filing` commits immediately with no error handling. The filing PAID commit and the Review creation are not one transaction, so a failure between them leaves a partial state.

# decisions-ctx

# business-pay queue service

A small Flask service that receives GCP Pub/Sub payment-completion events over HTTP, marks the matching filing as paid, and then either queues it for the filer, sends it to review, or notifies the emailer. It belongs to the LEAR `queue_services` group. It sits between the payment system, which emits the events, and entity-filer and entity-emailer, which read the NATS subjects it publishes to.

## Inputs and outputs

**In:** an HTTP POST to `/` from GCP Pub/Sub. The body is a cloud-event envelope. For a payment event, `ce.type` is `bc.registry.payment`. Its data is a `PaymentToken` with camelCase keys, including `id`, `statusCode`, `filingIdentifier` and `corpTypeCode`. `dict_keys_to_snake_case()` converts the keys to snake_case. The request carries `Authorization: Bearer <token>`.

**Out:**
- **Filer message**, published to the filer subject (`NATS_FILER_SUBJECT`): `{"filing": {"id": <filing id>}}`, built by `create_filing_msg`.
- **Email message**, published to the emailer subject: `{"email": {"filingId": <id>, "type": <filing_type>, "option": "PAID"}}`, built by `create_email_msg`. `option` is hardcoded to "PAID".
- **Database writes** to `filings` (payment fields and status) and to `reviews` (new review rows).
- **Health endpoints:** `/ops/healthz` returns `{'message': 'api is healthy'}` and `/ops/readyz` returns `{'message': 'api is ready'}`. Both return 200 with static JSON.

## Decisions in the payment handler (`resources/pay_filer.py`)

1. **Auth.** `gcp_auth` verifies the bearer token with `id_token.verify_oauth2_token`. The audience must equal `SUB_AUDIENCE`. The token must have `email_verified` true and an email equal to `SUB_SERVICE_ACCOUNT`. It returns an empty string on success and an error string otherwise. Any exception counts as failure.
2. **Return 200 (message removed from the queue, nothing done)** when any of these hold:
   - the message is empty or malformed;
   - the status code is not "COMPLETED";
   - `corp_type_code` is "MHR" or "BTR";
   - the filing already has `payment_completion_date`;
   - `filing_identifier` is None and `corp_type_code` is "BC".
3. **Return 404 (Pub/Sub retries)** when no Filing matches `payment_token.id`. Lookup is `Filing.get_filing_by_payment_token`.
4. **Filing found.** The handler sets `payment_completion_date`, sets `payment_status_code = "COMPLETED"` and sets `status = Filing.Status.PAID`.
   - If `filing_type` is in `["continuationIn"]`, it creates a `Review` with `ReviewStatus.AWAITING_REVIEW`. The completing party name comes from `get_completing_party()`, which reads the party whose `roleType` is "Completing Party". No filer message is sent on this path.
   - Otherwise it publishes to the filer, but only if `effective_date <= payment_completion_date`.
   - In both cases it publishes the email message.

## Data

- `Filing` is a minimal model of `filings`. Fields: id, effective_date, filing_type, filing_sub_type, filing_json (JSONB), payment_completion_date, payment_status_code, payment_token (column `payment_id`, up to 4096 chars), status, payment_account.
- `Filing.Status` has 12 members: COMPLETED, CORRECTED, DRAFT (the default), EPOCH, ERROR, PAID, PENDING, PENDING_CORRECTION, APPROVED, AWAITING_REVIEW, CHANGE_REQUESTED, REJECTED. `save()` commits.
- `Review` has id, nr_number, identifier, completing_party, status, submission_date, creation_date and a non-null `filing_id` foreign key. `ReviewStatus` is AWAITING_REVIEW, CHANGE_REQUESTED, RESUBMITTED, APPROVED or REJECTED. `save()` adds and commits immediately.
- `utils/base.py` has `BaseEnum`, whose `get_enum_by_value` returns the matching member or None. Its metaclass makes `in` work by attempting construction.

## Queue publishing (`services/queue.py`)

`QueueService` is a Flask extension. `publish_json(payload, subject=NATS_FILER_SUBJECT)` is a sync wrapper over `async_publish_json`, which reconnects if disconnected. It connects to NATS and STAN using `NATS_SERVERS`, `NATS_CLIENT_NAME`, `NATS_CLUSTER_ID` and `NATS_CONNECT_TIMEOUT`. Its client ID is the normalized client name plus random bits. It closes on app teardown. `gcp_queue` (GcpQueue) is also initialised at startup.

## Startup flow

`wsgi.py` calls `create_app()`, which does the following in order:
1. load config (`get_named_config`);
2. init Sentry if `SENTRY_DSN` is set;
3. `db.init_app`;
4. `register_endpoints`, which sets `strict_slashes=False` and mounts `pay_filer_endpoint` at `/` and `ops_endpoint` at `/ops`;
5. `gcp_queue.init_app`;
6. `queue.init_app`.

It then serves on `PORT` (default 8080).

Config selection in `get_named_config`: production, staging and default map to `ProdConfig`; testing maps to `TestConfig` (uses `DATABASE_TEST_*`); development maps to `DevConfig`. An unknown name raises KeyError. `DATABASE_UNIX_SOCKET`, if set, switches the database URI to a unix socket. The version string comes from `get_run_version()`, which appends `-{VCS_REF}` unless `VCS_REF` is empty or "missing".

## Where to look first

- `resources/pay_filer.py`: all handling decisions.
- `services/__init__.py`: message shapes.
- `services/gcp_auth.py`: auth.
- `services/queue.py`: NATS publishing.
- `database/filings.py` and `database/review.py`: models.
- `config.py`: environment and NATS settings.
- `tests/integration/test_worker_queue.py`: shows that a COMPLETED payment event produces exactly one filer message and one email message. The test needs a real NATS server and mocks Google token verification.

## Hazards

- **Paid but not published.** The filing is marked PAID before publishing. Exceptions from `publish_to_filer` and `publish_to_emailer` are suppressed. A failed publish leaves the filing paid with no filer or email message, and Pub/Sub does not retry.
- **Lookup errors look like missing filings.** `get_filing_by_payment_token` swallows all exceptions and returns None. A database error therefore looks like "filing not found", which returns 404 and triggers a retry, and the cause is hidden.
- **String-typed NATS limit.** `NATS_CONNECT_ERROR_COUNT_MAX` is loaded as the string '10'. Numeric comparisons against it fail.
- **Auth return value.** `gcp_auth` returns an empty string on success and an error message on failure. A caller must check truthiness.
- **Silent drops.** Several branches return 200 without doing anything: MHR/BTR, no BC identifier, already paid, and non-COMPLETED. The message is removed from the queue and nothing is recorded.

# decisions-tight

# business-pay queue service

A Flask service that receives GCP Pub/Sub payment-completion events and applies the payment to a Filing. It then hands the filing to downstream NATS queues (filer and emailer). It belongs to the BC registry `queue_services` set and shares a database with the filings API.

## Boundaries

**In:**
- `POST /` (blueprint `pay_filer_endpoint`, `resources/pay_filer.py`) takes a Pub/Sub push carrying a cloud event.
  - The bearer JWT is checked by `services/gcp_auth.py`.
  - It reads `SUB_AUDIENCE` and `SUB_SERVICE_ACCOUNT` from config. It requires `email_verified` and a matching email.
  - It returns `""` on success and an error string on failure, so callers must test truthiness.
- `GET /ops/healthz` and `GET /ops/readyz` (`resources/ops.py`) return static JSON with 200 and check nothing.

**Out:**
- NATS/STAN messages, via `services/queue.py` (`QueueService.publish_json(payload, subject)`).
  - The subject defaults to `NATS_FILER_SUBJECT`.
  - Filer message: `create_filing_msg` returns `{"filing": {"id": id}}`.
  - Email message: `create_email_msg` returns `{"email": {"filingId": id, "type": filing_type, "option": "PAID"}}`.
- Database writes to `filings` and `reviews`.

## Decisions in `pay_filer.py`

The event is processed only when `ce.type` is `"bc.registry.payment"`. The `PaymentToken` keys are converted from camelCase by `dict_keys_to_snake_case()`. The filing is looked up with `Filing.get_filing_by_payment_token(payment_token.id)`.

| Condition | Result |
|---|---|
| Message empty or malformed | 200 (drop) |
| Payment status not `"COMPLETED"` | 200 |
| `corp_type_code` in `["MHR", "BTR"]` | 200 (not handled here) |
| Filing not found | 404 (Pub/Sub retries) |
| Filing already has `payment_completion_date` | 200 (idempotent) |
| `filing_identifier` is None and `corp_type_code == "BC"` | 200 (checked before the filing lookup, so no 404 retry) |

For a filing that passes those checks, the service sets `payment_completion_date`, sets `payment_status_code = "COMPLETED"`, sets `status = Filing.Status.PAID`, and saves the filing. It then branches on `filing_type`:
- **`filing_type` in `["continuationIn"]`:** it creates a `Review` with `ReviewStatus.AWAITING_REVIEW`. The Review stores the completing party name, taken by `get_completing_party()` from the party whose `roleType` is "Completing Party". It does not publish to the filer.
- **Any other `filing_type`:** it publishes to the filer queue, but only if `effective_date <= payment_completion_date`.

In both cases it then publishes to the email queue.

## Data

- `Filing` (`database/filings.py`) is a minimal mapping with `id`, `effective_date`, `filing_type`, `filing_sub_type`, `filing_json`, `payment_completion_date`, `payment_status_code`, `payment_token`, `status` and `payment_account`.
  - `payment_token` maps to the DB column `payment_id`.
  - `Filing.Status` has 13 values, including DRAFT (the default), PAID, PENDING, COMPLETED, APPROVED, AWAITING_REVIEW, CHANGE_REQUESTED and REJECTED.
  - `save()` commits.
- `Review` (`database/review.py`) holds `nr_number`, `identifier`, `completing_party`, `status` (`ReviewStatus`: AWAITING_REVIEW, CHANGE_REQUESTED, RESUBMITTED, APPROVED, REJECTED), `submission_date`, `creation_date` and a non-null `filing_id` foreign key. Its `save()` adds and commits immediately.
- `utils/base.py` defines `BaseEnum`. Its metaclass makes `in` work by attempting construction. `get_enum_by_value` returns a member or None.
- `tests/data/create_database.sql` creates the 29-column `filings` table used by tests.

## Startup flow

`wsgi.py` runs `create_app()` and serves on `PORT` (default 8080). `create_app(environment=ProdConfig)` in `__init__.py` runs these steps in order:
1. Load config.
2. Initialize Sentry if `SENTRY_DSN` is set, with PII off.
3. Call `db.init_app`.
4. Call `register_endpoints`, which turns off strict slashes and mounts `pay_filer_endpoint` at `/` and `ops_endpoint` at `/ops`.
5. Call `gcp_queue.init_app`.
6. Call `queue.init_app`.

`QueueService` connects to NATS and STAN lazily: `async_publish_json` connects if disconnected, and `publish_json` is its synchronous wrapper. It closes on app teardown.

`config.py` selects a config class in `get_named_config`. production, staging and the default map to ProdConfig, testing maps to TestConfig, and development maps to DevConfig. An unknown name raises KeyError. If `DATABASE_UNIX_SOCKET` is set, the DB URI uses a unix socket. Otherwise it uses TCP.

`utils.get_run_version()` returns the package version. It appends `-{VCS_REF}` when `VCS_REF` is set and not `"missing"`.

## Where to look first

- `resources/pay_filer.py`: all business logic.
- `services/__init__.py`: message builders and the `gcp_queue` and `queue` singletons.
- `services/queue.py`: NATS publishing.
- `config.py`: environment and NATS options.
- `tests/integration/test_worker_queue.py`: shows that a COMPLETED payment event produces exactly one filer message and one email message on NATS.

## Hazards

1. The filing is saved as PAID before publishing, and publish errors from `publish_to_filer` and `publish_to_emailer` are suppressed. A failed publish leaves a paid filing that is never processed or notified. A retried event is dropped, because `payment_completion_date` is already set.
2. `get_filing_by_payment_token` catches every exception and returns None. A DB error therefore looks like "not found" (404 and retry) rather than a failure.
3. `NATS_CONNECT_ERROR_COUNT_MAX` is loaded as the string `'10'`, so numeric comparisons against it break.
4. The email `option` is hardcoded to `"PAID"`. Every email message is therefore a paid notice, including for `continuationIn` filings that are only awaiting review.
5. `/readyz` and `/healthz` return a fixed OK response without checking the DB or NATS. Readiness does not reflect real dependencies.

# core

The business-pay queue service receives GCP Pub/Sub payment-completion events over HTTP, marks the matching filing as paid in the shared filings database, and hands follow-up work to NATS/STAN queues (filer and emailer) or creates a review record.

## Contract
- **In:** HTTP POST of a Pub/Sub envelope to `/`, handled in `resources/pay_filer.py`. The bearer JWT is checked by `services/gcp_auth.py` against `SUB_AUDIENCE` and `SUB_SERVICE_ACCOUNT`. The base64 cloud event has type `bc.registry.payment` and carries a PaymentToken (`id`, `statusCode`, `filingIdentifier`, `corpTypeCode`). Keys are converted from camelCase.
- **Out (DB):** `Filing` gets `payment_completion_date`, `payment_status_code="COMPLETED"` and `status=PAID`. `Review` rows are written for continuation-in filings.
- **Out (NATS):** `{"filing": {"id": id}}` to the filer subject, and `{"email": {"filingId": id, "type": filing_type, "option": "PAID"}}` to the emailer subject. Both are built in `services/__init__.py` and published through `services/queue.py`.
- `/ops/healthz` and `/ops/readyz` are static health endpoints.

## Decisions (`pay_filer.py`)
- Return 200 (drop the message) when the message is empty or malformed, the status is not COMPLETED, the corp type is MHR or BTR, the filing already has a completion date, or the filing identifier is None with corp type BC.
- Return 404 (Pub/Sub retries) when the filing is not found by payment token.
- Continuation-in filings (`filing_type` in `["continuationIn"]`) get a `Review` with `AWAITING_REVIEW` and are not sent to the filer.
- Other filings go to the filer queue only if `effective_date <= payment_completion_date`.
- An email message is published in every case.

## Hazards
- The filing is committed as PAID before publishing. Exceptions from `publish_to_filer` and `publish_to_emailer` are swallowed, so a failed publish leaves a paid filing with no filer or email message and no retry.
- `Filing.get_filing_by_payment_token` swallows all exceptions and returns None, so a database error looks like "not found" and returns 404.
- `gcp_auth` returns an empty string on success and an error string on failure, so callers must check truthiness. `NATS_CONNECT_ERROR_COUNT_MAX` in `config.py` is a string, so numeric comparisons fail.

## Open first
- `resources/pay_filer.py`: all the decision logic.
- `services/queue.py` and `services/__init__.py`: NATS publishing and message shapes.
- `database/filings.py` and `database/review.py`: the minimal models. `payment_token` maps to the `payment_id` column.
- `tests/integration/test_worker_queue.py`: the end-to-end envelope and message expectations.

# core-scaled

# business-pay queue service

A Flask service that receives GCP Pub/Sub push notifications about completed payments. It marks the matching filing as paid, then hands work on to the filer and emailer NATS queues. It can also create a review record for continuation-in filings.

## Contract

- **In:** HTTP POST to `/` (`resources/pay_filer.py`). The body is a Pub/Sub envelope wrapping a cloud event of type `bc.registry.payment`. The event data is a PaymentToken, with camelCase keys converted to snake_case. The bearer JWT is verified by `services/gcp_auth.py` against `SUB_AUDIENCE` and `SUB_SERVICE_ACCOUNT`. `gcp_auth` returns an empty string on success and an error message on failure.
- **Out, NATS** (`services/queue.py`, STAN client):
  - Filer queue: `{"filing": {"id": id}}`.
  - Emailer queue: `{"email": {"filingId": id, "type": filing_type, "option": "PAID"}}`.
  - Both are built by `create_filing_msg` and `create_email_msg` in `services/__init__.py`.
- **Out, DB:** updates the `filings` table (minimal model in `database/filings.py`) and inserts into `reviews` (`database/review.py`).
- `/ops/healthz` and `/ops/readyz` return static JSON.

## Decisions (`pay_filer.py`)

- **Return 200, so the message leaves the queue:**
  - the message is empty or malformed;
  - the payment status is not COMPLETED;
  - `corp_type_code` is MHR or BTR;
  - the filing already has `payment_completion_date`;
  - `filing_identifier` is None and the corp type is BC.
- **Return 404, so Pub/Sub retries:** the filing is not found, looked up by `payment_token.id`.
- **Otherwise:**
  - set `payment_completion_date`, `payment_status_code=COMPLETED` and `status=PAID`;
  - for `continuationIn`, create a Review with status AWAITING_REVIEW, using `get_completing_party()`;
  - for other types, publish to the filer queue only if `effective_date <= payment_completion_date`;
  - always publish to the emailer queue.

## Hazards

- Publish errors from the filer and emailer are swallowed after the filing is already marked PAID. A failed publish leaves a paid filing with no downstream processing and no retry.
- `Filing.get_filing_by_payment_token` swallows every exception and returns None. A DB error then looks like "filing not found" and returns 404.
- `payment_token` maps to the column `payment_id`. `Review.save()` and `Filing.save()` commit immediately with no error handling.

## Open first

1. `src/business_pay/resources/pay_filer.py`: the handler and all the decisions above.
2. `src/business_pay/services/queue.py` and `services/__init__.py`: NATS publishing and message shapes.
3. `src/business_pay/database/filings.py`: the model and the token lookup.
4. `tests/integration/test_worker_queue.py`: end-to-end test of the two published messages.

Config (`config.py`) holds the NATS and DB settings. Note that `NATS_CONNECT_ERROR_COUNT_MAX` is loaded as a string.

# core#2

The business-pay queue service receives GCP Pub/Sub payment-completion events over HTTP. It marks the matching filing as paid, then hands work to NATS streaming queues: the filer queue, the emailer queue, or a Review record for continuation-in filings.

## Contract
- **In:** an HTTP POST at `/` from Pub/Sub. It carries a base64 envelope around a cloud event of type `bc.registry.payment`. The data holds a PaymentToken (camelCase keys, converted to snake_case) with `id`, `statusCode`, `filingIdentifier` and `corpTypeCode`. `gcp_auth` checks the bearer JWT against `SUB_AUDIENCE` and `SUB_SERVICE_ACCOUNT`.
- **DB:** it writes the `filings` table through a minimal `Filing` model, and inserts `Review` rows. `Filing.payment_token` maps to the column `payment_id`.
- **Out (NATS/STAN):**
  - Filer: `{"filing": {"id": id}}`
  - Emailer: `{"email": {"filingId": id, "type": filing_type, "option": "PAID"}}`

## Decisions (`resources/pay_filer.py`)
- Return 200 and drop the message when:
  - it is empty or malformed
  - the status is not `COMPLETED`
  - `corp_type_code` is MHR or BTR
  - `payment_completion_date` is already set
  - `filing_identifier` is None and the corp type is BC
- Return 404 so Pub/Sub retries when no filing matches the token.
- Otherwise set `payment_completion_date`, `payment_status_code="COMPLETED"` and `status=PAID`.
- `continuationIn` filings get a `Review` with `AWAITING_REVIEW`. Other filings are published to the filer queue only if `effective_date <= payment_completion_date`.
- The email message is always published.

## Hazards
- The filing is committed as PAID before publishing. `publish_to_filer` and `publish_to_emailer` exceptions are swallowed, so a failed publish leaves a paid filing that is never processed or notified, and no retry happens.
- `get_filing_by_payment_token` catches every exception and returns None. A DB error therefore looks like "not found" (404 and retry) or is hidden.
- `gcp_auth` returns "" on success and an error string on failure. Callers must check truthiness.

## Open first
- `resources/pay_filer.py`: the handler and all the decisions above.
- `services/queue.py` and `services/__init__.py`: the NATS publisher and the message builders.
- `database/filings.py` and `database/review.py`: the models.
- `tests/integration/test_worker_queue.py`: the end-to-end flow.

# core-states

# business-pay queue service

A Flask service that receives GCP Pub/Sub push events announcing payment completion. It marks the matching Filing as PAID. It then either creates a Review (for continuation-in filings) or publishes to NATS/STAN queues for the filer and emailer services. The code is in `queue_services/business-pay/src/business_pay`.

## Contract
- **In:** HTTP POST to `/` (`resources/pay_filer.py`). The body is a Pub/Sub envelope carrying a base64 cloud event. The `Authorization: Bearer <GCP JWT>` header is checked first. The event `ce.type` must be `bc.registry.payment`. Its data is a PaymentToken whose camelCase keys are converted to snake_case by `dict_keys_to_snake_case()`. The token's `id` is matched against `Filing.payment_token`, which maps to the DB column `payment_id`.
- **Out, filer queue:** `{"filing": {"id": <id>}}`, built by `create_filing_msg`.
- **Out, emailer queue:** `{"email": {"filingId": <id>, "type": <filing_type>, "option": "PAID"}}`, built by `create_email_msg`.
- **Out, DB:** updates the `filings` row. Inserts a `reviews` row with `ReviewStatus.AWAITING_REVIEW`, the completing party, and `filing_id`.
- `/ops/healthz` and `/ops/readyz` are static health endpoints.

## Decisions in `pay_filer.py`
- The token check is in `services/gcp_auth.py`. It verifies the bearer token's audience (`SUB_AUDIENCE`), `email_verified`, and an email equal to `SUB_SERVICE_ACCOUNT`. It returns `""` on success and an error string otherwise.
- Return 200, which drops the message, when:
  - the message is empty or malformed;
  - the payment status is not `COMPLETED`;
  - `corp_type_code` is in `["MHR", "BTR"]`;
  - the filing already has `payment_completion_date` (idempotency);
  - `filing_identifier` is None and `corp_type_code` is "BC".
- Return 404, which makes Pub/Sub retry, when the filing is not found.
- On a match, set `payment_completion_date`, set `payment_status_code="COMPLETED"`, and set `status=Filing.Status.PAID`.
- If `filing_type` is in `["continuationIn"]`, create a Review. `get_completing_party()` takes the name from the party with roleType "Completing Party". Otherwise publish to the filer queue, but only when `effective_date <= payment_completion_date`.
- Always publish to the email queue.
- `services/queue.py` publishes through `publish_json()`, a sync wrapper over `async_publish_json()` that reconnects if disconnected. The default subject is `NATS_FILER_SUBJECT`.

## Hazards
- The Filing is marked PAID and saved before publishing. `publish_to_filer()` and `publish_to_emailer()` suppress exceptions, so a failed publish leaves a paid filing that is never filed or emailed. The 200 response means Pub/Sub will not retry, and the already-completed check blocks any redelivery.
- `Filing.get_filing_by_payment_token` swallows every exception and returns None. A DB error therefore looks like "not found" and returns 404.
- The email `option` is hardcoded to "PAID". `NATS_CONNECT_ERROR_COUNT_MAX` in `config.py` is a string, so numeric comparisons fail.

## Open first
1. `resources/pay_filer.py` holds all the handler logic and the state transition.
2. `services/__init__.py` and `services/queue.py` hold the message builders and the NATS/STAN publisher.
3. `database/filings.py` and `database/review.py` hold the minimal ORM models and the status enums.
4. `tests/integration/test_worker_queue.py` pins the end-to-end behaviour: one envelope produces both the filer and emailer messages.

Config is in `config.py` (named configs, DB URI, NATS and GCP settings). `__init__.py` has the `create_app` factory and `wsgi.py` is the entry point. The LICENSE is BSD 3-Clause.

# core-states#2

# business-pay queue service

A Flask service that receives GCP Pub/Sub payment-completion events over HTTP. It marks the matching Filing as paid, then either sends it to the filer queue via NATS/STAN or opens a Review for continuation-in. It also publishes a "PAID" notification to the emailer queue.

## Contract
- **In:** HTTP POST at `/` (blueprint `pay_filer_endpoint`, `resources/pay_filer.py`). The body is a Pub/Sub envelope with a base64 cloud event. Events of type `bc.registry.payment` carry a PaymentToken (`id`, statusCode, filingIdentifier, corpTypeCode). Its camelCase keys are converted by `dict_keys_to_snake_case()`.
- **Auth:** the `gcp_auth.py` bearer-token check verifies the JWT against `SUB_AUDIENCE` and `SUB_SERVICE_ACCOUNT`.
- **DB:** reads and writes the `filings` table (`Filing`, a minimal mapping) and inserts into the reviews table (`Review`). Filing's `payment_token` attribute maps to the column `payment_id`.
- **Out, filer:** `{"filing": {"id": id}}` from `create_filing_msg`.
- **Out, emailer:** `{"email": {"filingId": id, "type": filing_type, "option": "PAID"}}` from `create_email_msg`.
- **Publishing:** `services/queue.py` (`QueueService.publish_json`) publishes to NATS subjects. The default subject is `NATS_FILER_SUBJECT`.
- **Ops:** `/ops/healthz` and `/ops/readyz` return static JSON.

## Decisions (`pay_filer.py`)
- Empty or malformed message, or event type not `bc.registry.payment`: return 200 (drop).
- Payment status not "COMPLETED": return 200 (drop).
- `corp_type_code` in ["MHR", "BTR"]: return 200 (ignored).
- Filing already has `payment_completion_date`: return 200 (idempotent skip).
- `filing_identifier` is None and `corp_type_code` is "BC": return 200 (not 404).
- Filing not found by `Filing.get_filing_by_payment_token`: return 404, so Pub/Sub retries.
- Filing found: set `payment_completion_date`, `payment_status_code="COMPLETED"` and `status=Filing.Status.PAID`.
- `filing_type` in ["continuationIn"]: create a `Review` with `ReviewStatus.AWAITING_REVIEW`. The completing party comes from `get_completing_party()`, which picks the party with roleType "Completing Party". No filer message is sent.
- Any other filing type: if `effective_date <= payment_completion_date`, `publish_to_filer()` publishes the filer message.
- Always publish the email message via `publish_to_emailer()`.
- `gcp_auth.py` returns "" on success and an error string on failure, so callers must test truthiness. It requires `email_verified` and an email matching the configured service account.

## Hazards
- The filing is committed as PAID before publishing. Exceptions in `publish_to_filer()` and `publish_to_emailer()` are suppressed. A failed publish therefore leaves a paid filing that is never filed or emailed, and a Pub/Sub retry is skipped by the already-paid check.
- `Filing.get_filing_by_payment_token` swallows all exceptions and returns None, so a DB error looks like "not found" (404 retry loop).
- `Review.save()` commits immediately with no error handling. It is not atomic with the filing update.

## Open first
- `src/business_pay/resources/pay_filer.py`: the whole payment flow and its drop and retry rules.
- `src/business_pay/services/queue.py` and `services/__init__.py`: NATS publishing and the message builders.
- `src/business_pay/database/filings.py` and `review.py`: the models, status enums and the `payment_id` mapping.
- `tests/integration/test_worker_queue.py`: end-to-end check of the two NATS messages. `config.py` holds the NATS and DB settings.

Other files are the app factory, the WSGI entry point, the BSD licence and test fixtures.
