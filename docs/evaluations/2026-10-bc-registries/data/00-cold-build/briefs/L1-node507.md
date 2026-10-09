<!-- level 1, node 507, children [54, 106, 119, 127, 131, 134, 152, 241, 273, 292, 301, 303, 308, 309, 310, 313, 317, 321, 325, 326, 327, 335, 336, 341, 342, 343, 344, 345, 354, 355, 363, 364, 365, 366, 367, 368, 374, 375, 376, 377, 385, 388, 391, 392, 399, 400, 401, 411, 412, 416, 417, 433, 434, 435, 436, 437, 447, 450, 454, 479] -->

# BC Registries (bcgov) business/auth/pay stack: parent brief

This brief covers the many small config, packaging and test files across the BC Registries Python/Flask ecosystem. The repos are lear, sbc-auth, sbc-pay, business-filings-ui, business-pay and the COLIN→LEAR ETL. Nearly everything is Apache 2.0, © Province of British Columbia (2018–2024). The exceptions are business-pay, which is BSD-3-Clause, and a few unrelated stubs.

## 1. Quality gates (SonarQube / Codecov)

**SonarQube**
- All configs use UTF-8 and mostly `projectVersion=Autoscan`.
- Sources by repo:

| Repo | Sources |
|---|---|
| business-filings-ui | `src/` |
| lear | commented out |
| sbc-auth | `auth-api/src/auth_api` and `auth-web/` |
| sbc-pay | `pay-api`, `bcol-api` and `report-api` `src` |

- Test paths and CPD rules are mostly commented out.
- sbc-auth uses the same exclusion path for both exclusions and CPD exclusions.

**Codecov**
- Shared baseline:
  - `require_ci_to_pass: true`.
  - Coverage range 70…100.
  - Patch status off.
  - `project.default: false`, so only named flags are checked.
  - Test paths ignored.
  - Flags carry forward.
  - Comments are suppressed when coverage is unchanged (`require_changes: true`).
- Targets:

| Repo | Branch | Flags and targets |
|---|---|---|
| business-filings-ui | `master` | none |
| lear | not stated | 9 flags (colinapi, legalapi, entityemailer, entityfiler, entitypay, entitybn, entity-digital-credentials, furnishings, involuntary-dissolutions); backend target `auto` |
| sbc-auth | `development` | backend flags (authapi, statusapi, eventlistenerqueue, accountmailer) at 80%; authweb UI at 35% |
| sbc-pay | `development` | payapi, bcolapi, reportapi, paymentjobs and payqueue; backend at 80% |

- `max_report_age: false` means no age limit, not disabled.

## 2. Services, by role

**Pay stack (sbc-pay)**
- **pay-api:** the core. Its config is the largest: PayBC Direct Pay, CFS, Keycloak, Pub/Sub topics and reporting limits. It also holds FAS/CFS/PAD/routing-slip constants, JSON-schema validation utilities and the `RoutingSlip`/`Comment` services.
- **pay-queue:** a Flask worker that takes GCP Pub/Sub pushes on `POST /`. It routes CloudEvents:
  - CAS payment messages go to `reconcile_payments`.
  - CGI ack and feedback messages go to `reconcile_distributions`.
  - `EFT_FILE_UPLOADED` goes to `reconcile_eft_payments`.
  - INCORPORATION and REGISTRATION events go to `update_temporary_identifier`.
  - It returns 200 on exceptions, so there are no retries.
- **ftp-poller:** polls CAS, CGI and EFT SFTP folders. It uploads files to Minio, moves them to backup and publishes a queue message. Jobs are selected by `sys.argv[1]`.
- **payment-jobs, pay-admin, bcol-api and report-api:** the other pay services.
- **SFTP wrappers:** the pysftp and paramiko wrappers handle connections for the gazette, ICBC, NUANS, CAS and CGI jobs.

**Business filing pipeline (lear)**
- **Filer (`process_filing`):** consumes NATS filings and dispatches about 25 filing types. It publishes email and event messages, and in `cb_subscription_handler`:
  - re-raises `OperationalError` and `FilingException` so the message is requeued;
  - swallows everything else.
- **Other workers:**
  - Entity-emailer: filing, pay and notification processors with a dispatcher.
  - BN/CRA: Business Number.
  - Digital credentials.
  - Events listener, with `MessageProcessing` tracking.
- **`entity_queue_common`:** the shared NATS/STAN library with probes on port 7070.
- **business-pay:** a Flask service that receives Pub/Sub payment events and sets filings to PAID. It sends continuationIn filings to staff review and publishes to the filer and emailer queues. It returns 200 for empty or already-paid messages and 404 only when the filing isn't found.

**Auth (sbc-auth)**
- **auth-api and auth-web:** the API and Vue frontend.
- **auth-queue worker:** handles activity logs, NSF lock/unlock and Name Request auto-affiliation, with idempotency via `PubSubMessageProcessing`.
- **account-mailer:** the dispatcher for account and payment emails.
- **Config bits:** the `BCOL_PROFILE_PRODUCT_MAP` constants, and the many `SubjectType`/`TitleType` email constants.

**Batch jobs (lear)**
- email-reminder (annual report reminders).
- involuntary-dissolutions: three stages.
- furnishings: stage 1 to 3 notices, gazette XML and SFTP to BCLAWS and BCMail+.
- future-effective-filings.
- update-colin-filings.
- notebook-report jobs.
- All are launched through a one-line `python <job>.py` script in `/opt/app-root`.

**Legal API**
- **Business warnings:** `WarningType`/`BusinessWarningCodes` and the `check_warnings` → `check_business` dispatch for firms, corps and involuntary dissolution.
- **Digital credentials:** the issue, revoke and replace helpers.
- **Tests:** a large Oracle-backed suite and the shared test constants/factories. The suite includes the `oracle_integration` decorator and Postman tests.

**COLIN→LEAR ETL:** Prefect flows (`corps-flow`, `sp-gp-flow`, SP-GP-Affiliation and an old Test-ETL). Each stage is extract, clean, transform to LEAR JSON, then load. Status goes in `corp_processing` and `affiliation_processing`.

## 3. Cross-cutting conventions

- **Config modules:**
  - Each has `get_named_config(name)` with `_Config`, `DevConfig`, `TestConfig` and `ProdConfig`.
  - It uses dotenv and builds the Postgres URI from `DB_*`/`DATABASE_*`, with an optional unix socket.
  - `SENTRY_DSN` of the string `'null'` is treated as unset.
  - Names such as 'staging' and 'default' map to `ProdConfig`.
- **Packaging:**
  - Legacy services use `setup.py`/`setup.cfg`/`MANIFEST.in`.
  - The version is read from `version.py` by regex and `ast.literal_eval`.
  - `git+` requirements are filtered out of `install_requires`.
  - Modern pay services use Poetry (Python ≥3.12).
  - Versions are PEP 440 strings, with `OPENSHIFT_BUILD_COMMIT` or `VCS_REF` optionally appended.
- **Lint and test config:**
  - Line length is 120 everywhere.
  - Flake8 ignores F401 in `__init__.py`.
  - Pylint disables C0301/W0511 and more.
  - isort uses `multi_line_output` 3 or 4.
  - pytest uses coverage with html/xml reports.
  - The `[report:run]` section name is non-standard.
- **WSGI:** `application` must be lowercase for OpenShift s2i. Apps bind to `0.0.0.0` with `debug=False`, using `PORT`. Gunicorn is configured through env vars (`GUNICORN_PROCESSES`/`THREADS`/`TIMEOUT`) and `forwarded_allow_ips='*'`.
- **Containers and CI/CD:**
  - Python 3.8 (EOL) Dockerfiles with pinned pip 20.1.1, 20.3.3 or 21.1.2, `/opt/app-root`, user 1001 and port 8080.
  - Poetry multi-stage builds (`development_build` → `production_build`, user `web` UID 1000).
  - A Node 20.5.1 + nginx 1.18.0 build for the UI.
  - About 17 Makefiles share a `TAG_NAME` flow: `dev` builds, `test` retags dev→test, `prod` retags test→prod.
  - The Docker Compose stacks cover Postgres, NATS Streaming, MinIO, Jaeger, SFTP, Sentry and a Prefect Server.
- **Internal git dependencies:** `pay-api`, `sbc-common-components`, `gcp-queue`, `registry_schemas` and `legal_api`/`entity_queue_common` (lear subdirectories). Most are branch-pinned or unpinned, and some use personal forks (seeker25, thorwolpert, daxiom) and feature branches.
- **Messaging:** a legacy NATS/STAN stack is migrating to GCP Pub/Sub with `SimpleCloudEvent`. The STAN `client_id` uses `getrandbits(0x58)`, 88 random bits.

## 4. Caution

**Security**
- Hardcoded credentials appear in compose files, devcontainers and configs. Examples are Postgres `lear`/`postgres`/`secret`, MinIO `minio`/`minio123`, the SFTP `ftp_user:ftp_pass` and the Prefect passwords.
- Several secrets and keys are handled unsafely:
  - Prod configs generate a random `SECRET_KEY` per import. payment-jobs defaults to `'a secret'`.
  - Private keys are written to disk.
  - The 1Password script exposes the password on the command line.
- `forwarded_allow_ips='*'` trusts any proxy.
- SFTP `AutoAddPolicy` and `SFTP_VERIFY_HOST=false` disable host verification.
- Dockerfiles use `chmod 777`.
- Names API and Auth Queue still use a JWT "hack" and are marked ALPHA (2018).

**Dependencies and runtime**
- Most pins are old or end-of-life: Flask 1.1.x, Werkzeug <2, SQLAlchemy <1.4, protobuf 3.x, Python 3.8, `flask-restplus` and the legacy NATS clients.
- Mixed pins can conflict, for example `requests` 2.32.2 with `urllib3` 1.21.1.
- Branch and fork git dependencies are not reproducible.
- `nest_asyncio` patches the event loop globally.
- `asyncio` `loop=` arguments and `utcfromtimestamp` are deprecated.

**Error handling and data loss**
- Broad excepts that log and swallow are widespread:
  - pay-queue and account-mailer return 200 and drop messages.
  - Pollers swallow SFTP and upload failures.
  - Receipt-fetch failures send emails without the receipt.
  - Filer processors use `suppress` or bare excepts.
- Re-raising specific exceptions is the intended way to requeue.

**Known bugs and typos**
- `MinioService.put_minio_file` calls `os.stat` on the destination key.
- `update_filing_court_order` tests `if not Filing:` (the class) instead of the instance.
- `populate_previous_party_officer` uses an undefined `cp_bus_company_num`.
- The stage-one XPRO SFTP step updates `_bc_mail_furnishings`.
- SFTP config: `CGI_INBOX_FILE_PREFIX` reads the `CGI_FEEDBACK_FILE_PREFIX` env var.
- `GUNICORN_WORKER_CONNECIONS` is misspelled.
- The Special Resolution email processor lets the second PDF call overwrite the first.
- Typos that are part of live names:
  - `'paymanet_pending'` is live and needs a migration to fix.
  - `create_invountary_dissolution_filing` is used consistently in the tests.

**Config pitfalls**
- Test and prod use different env var names.
- A literal-string default such as `'email1,email2'` or `https://NAICS_API_URL/...` fails at runtime.
- `AFFILIATE_ENTITY_ACCOUNT_ID` becomes `None` unless it is purely numeric.
- `TAG_NAME` defaults to `dev`, and CD needs `oc login` and the env vars.
- BuildKit is required for the Poetry cache mounts.

**Test data and process**
- Many tests run against live Oracle/Postgres with hardcoded fixtures such as `CP0001965` and `FM0000001`, so reruns can fail.
- Several test files are empty stubs.
- Mocks, global state and module-level lists leak between tests.
- Smaller points:
  - Some READMEs are incomplete (Entity BN, Digital Credentials, Filer, business-filings-ui "TBD").
  - Docker `EXPOSE 8080:8080` is invalid.
  - The 1Password CLI is deprecated (2024).
  - The Oracle-pool timeout units are uncertain: `timeout=3600` and `waitTimeout=1500` should be verified.
  - Version conflicts exist (e.g. `GUNICORN_THREADS` default 1, 3 or 4).
  - pay-queue's `/readyz` docstring has a typo.
