<!-- level 1, node 507, children [54, 106, 119, 127, 131, 134, 273, 301, 303, 308, 309, 310, 313, 317, 321, 325, 326, 327, 335, 336, 341, 342, 343, 345, 354, 355, 365, 366, 367, 368, 374, 375, 376, 377, 385, 388, 391, 392, 399, 400, 401, 411, 412, 433, 435, 436, 447, 450, 479, 532, 533, 601, 602, 611, 612] -->

# bcgov Business/Auth/Pay Stack: Parent Brief

This brief condenses about 50 child notes on the BC Registries (Province of British Columbia, mostly Apache 2.0) Python/Flask microservice family: lear, sbc-auth, sbc-pay, business-filings-ui, business-pay and related repos. Almost all children are boilerplate, config, packaging or test scaffolding. Little is real logic.

## 1. Quality and CI config
- **SonarQube** (business-filings-ui, lear, sbc-auth, sbc-pay):
  - All use UTF-8 and `projectVersion=Autoscan`.
  - Test paths and CPD settings are mostly commented out.
  - Sources by repo:
    - business-filings-ui: `src/`, excluding `src/resources/*`.
    - lear: sources commented out, with exclusions for deprecated, conftest and migrations paths.
    - sbc-auth: `auth-api/src/auth_api` and `auth-web/`.
    - sbc-pay: `pay-api`, `bcol-api` and `report-api`.
  - sbc-auth uses the same path for both exclusion settings.
- **Codecov**:
  - The shared baseline is `require_ci_to_pass`, range 70–100, patch status off and `project.default: false`, so only named flags are checked.
  - Test paths are ignored, and comments use `require_changes: true`.
  - Backend targets: sbc-auth and sbc-pay use 80% on `development`, lear uses `auto`, and sbc-auth's authweb UI flag is 35%.
  - `max_report_age: false` means no age limit, not disabled.
  - Lear has 9 flags and sbc-pay has 5. The authapi, statusapi and authweb flags belong to sbc-auth.
- **Lint and test configs** (`setup.cfg`, flake8, pylint, isort, pytest, coverage):
  - They follow one template with line length 120 and a migrations/tests exclusion. F401 is ignored in `__init__.py`, and isort `multi_line_output` is 3 or 4.
  - Pay Team services (bcol_api, ftp_poller, payment_jobs, admin, pay_api, pay_queue) require Python ≥3.12. The older lear and auth packages require ≥3.6 to 3.8.
  - **Recurring problem:** coverage uses a non-standard `[report:run]` section, which may be ignored. Its patterns are over-broad (`from`/`import`) and have unescaped dots. `--strict` is deprecated, and `universal=1` is vestigial on Python-3-only projects. Line length is set separately in each tool, so the settings can conflict.
- **Dev-requirements files**: pytest and flake8 with 5–6 plugins, pylint, pylint-flask and coverage. Lovely-pytest-docker appears in some. Older variants pin pytest ≤4.x–5.x, isort <5, pydocstyle <4 and flake8 5.0.4. pytest-asyncio 0.18.3 is pinned in several.

## 2. Dependencies and packaging
- **Modern stack** (Python ^3.12, Flask 3.0.x, SQLAlchemy 2.0, Poetry): pay-api, pay-queue, payment-jobs, pay-admin, ftp-poller and bcol-api. Dev deps are shared.
- **Legacy stack** (Flask 1.1.2, Werkzeug <2 or 0.16.1, SQLAlchemy <1.4, protobuf 3.15–3.19, NATS/STAN clients, Jinja2 2.11.x): auth-api, the lear queue services, notebook/report jobs and many manifests.
- **Git dependencies** are the main fragility:
  - They include `registry_schemas` (business-schemas, pinned from 2.5.x to 2.18.28), `legal_api`/`colin-api`/`entity_queue_common` (lear subdirectories, usually unpinned), `gcp-queue`, `sbc-common-components`, `sql-versioning` and `simple-cloudevent` (daxiom).
  - Many point at personal forks or feature branches (seeker25, thorwolpert, `21537`, `22982-EFT-Wire`, `small_tweaks`, `lib_logging`, `refactor_queues`), or at `main`. Builds are not reproducible, and a deleted branch breaks them.
  - `#egg=` syntax is deprecated.
- **`setup.py`**:
  - The shared template reads the version from `version.py` with a regex plus `ast.literal_eval`. It reads `requirements.txt` and drops `git+` lines silently. Those dependencies must be installed separately.
  - Many trivial `setup.py` files give only a name and `find_packages()`.
  - MANIFEST.in files are mostly standard. Schema globs are shallow.
- **Version modules**: PEP 440 `__version__` files. Seen versions include 0.1.0, 1.0.0, 2.0.1, 2.10.5, 2.18.4, 2.80.0 and 2.128.0. Some builds append `OPENSHIFT_BUILD_COMMIT` or `VCS_REF`, and a missing hash falls back silently.
- **Notebook/report requirements**: a Jupyter, pandas and spacy stack, plus a Prefect pipeline (prefect 2.7.3), all with 2019–2020 pins. One variant pairs requests 2.32.2 with urllib3 1.21.1, which conflicts.

## 3. Runtime config pattern
- **Flask config**: `config.py` loads `.env` and defines `_Config` plus Dev/Test/Prod classes. `get_named_config()` raises `KeyError` for unknown names.
  - Env names: staging, default and production map to `ProdConfig`. 'testing' maps to `TestConfig`.
  - **Security issues:** ProdConfig generates a random `SECRET_KEY` if the env var is unset. Some bases hardcode `'a secret'`. A `SENTRY_DSN` of `'null'` is cleared.
  - Other defects: a bug where `CGI_INBOX_FILE_PREFIX` reads the feedback env var; the placeholder `NAICS_API_URL`; and test vs prod env var name differences.
  - The STAN `client_id` is random 88-bit hex per startup.
- **Gunicorn**: the config reads `GUNICORN_PROCESSES`, `GUNICORN_THREADS` and `GUNICORN_TIMEOUT`, with `forwarded_allow_ips='*'`.
  - Defaults are 1×1, a bottleneck. The documented defaults conflict (1, 3 or 4 threads).
  - The GCP target is 8 threads, timeout 0 and 1 process.
  - There is a `GUNICORN_WORKER_CONNECIONS` typo. One variant has a `pre_fork` 5-second sleep as a Traction API workaround.
  - Startup is `gunicorn -b 0.0.0.0:8080 wsgi:application`, so the lowercase `application` name is required by OpenShift s2i.
- **WSGI entry points** bind `0.0.0.0` with `debug=False`. Default ports vary: 8080, 5001 and 5002/5032.
- **Minio wrappers** (put/get object): `file_size` defaults to 0. `MinioService.put_minio_file` has a crash bug where `os.stat` is called on the destination key.
- **SFTP**:
  - `SftpConnection` (paramiko) and the pysftp `SFTPService` variants (gazette, ICBC, NUANS, CAS, CGI).
  - Disabling host verification (`SFTP_VERIFY_HOST='false'`) and `AutoAddPolicy` are dev-only. Private keys are written to disk.
  - `SFTP_VERIFY_HOST.lower()` raises `AttributeError` if the variable is unset.

## 4. Services and workers
- **Pay queue** (sbc-pay, GCP Pub/Sub push):
  - `POST /` routes CloudEvents: CAS → `reconcile_payments`, CGI ack/feedback → `reconcile_distributions`, EFT → `reconcile_eft_payments`, and INCORPORATION/REGISTRATION → `update_temporary_identifier`. Health checks are at `/ops`.
  - The worker catches all exceptions and returns 200, so there are no retries.
- **Business-pay**: applies payments to Filings from Pub/Sub. It uses `verify_gcp_jwt`. Empty messages and already-paid filings return 200. Only a 404 requeues. A `continuationIn` filing goes to staff review.
- **FTP poller**: CAS, CGI and EFT pollers follow the pattern SFTP → Minio → backup directory → queue. Exceptions are largely swallowed. An invalid job name only logs. `sys.argv[1]` is unchecked.
- **Filer, emailer, BN and digital-credentials workers** (lear `queue_services`): NATS/STAN consumers on `entity_queue_common`.
  - `entity_queue_common` has the Flask extension, `ServiceWorker`, probes on port 7070 and message builders.
  - `OperationalError`, `FilingException`, `EmailException` and `BNException` are re-raised to requeue. Anything else is dropped.
  - Risks: `nest_asyncio.apply()` patches globally, deprecated `get_event_loop` appears in launchers, and an unseeded random STAN `client_id`.
  - `process_filing` has 25 elif handlers.
  - The emailer has 20+ processors for AGM, amalgamation, continuation-in, dissolution, incorporation, registration, restoration, NR and others.
  - **Recurring issue:** a failed receipt fetch is only logged and the email is still sent. Restoration crashes when status is neither PAID nor COMPLETED. Special Resolution overwrites its PDFs.
- **Account-mailer and auth-queue** (sbc-auth, Pub/Sub):
  - Both check idempotency through `PubSubMessageProcessing`. Account-mailer returns 200 even on failure.
  - It has nine handlers and 25 generic message types. It uses the `TemplateType` enum, which has the live typo `paymanet_pending`.
  - auth-queue handles NSF lock/unlock, Name Request affiliation and activity logs.
- **Jobs** (lear):
  - **Furnishings**: 3-stage involuntary dissolution. Stage 1 sends email or mail and SFTPs letters to BCMAIL+. Stages 2 and 3 create GAZETTE furnishings, and the post-processor uploads XML to BCLAWS. A likely bug: the XPRO letter step updates `_bc_mail_furnishings`.
  - **Involuntary dissolution job**: cron-gated by `enable-involuntary-dissolution`.
  - **Others**: AR email reminder, future-effective filings, COLIN sync (`update_colin_filings`) and a manual-filings check.
  - Launchers are `cd /opt/app-root && python <job>.py` with no error handling.
- **COLIN→LEAR migration**: Prefect flows (Corps, SP-GP, Affiliation) feed `EventFilingService` and `FilingJsonFactoryService`.
  - The ETL transform code hardcodes "PREFECT ETL FLOW TEST" markers, which would pollute production.
  - `populate_previous_party_officer` uses an undefined variable.
  - The year-1 date sentinel is overwritten.
- **Legal API**:
  - Business warnings (`check_warnings`, firm and corp checks, amalgamation) and a Contributor Covenant Code of Conduct. Report contacts differ between copies, and both are BC gov addresses.
  - Models, services and other modules (`Filing` status enums and so on) are mostly stubs. Business constants and error templates also appear.

## 5. Docker and dev environment
- **Legacy images**: Python 3.8.x buster, pip 20.1.1, `/opt/app-root`, user 1001. One image bundles Oracle instant client 21.1 with aggressive file deletion.
- **Modern images**: multi-stage Poetry builds on Python 3.9/3.12 bullseye. They use user `web` (UID 1000) and BuildKit cache mounts, and gunicorn in production. The `APP_ENV` logic is described inconsistently, and one variant has a pipe typo.
- **Devcontainers**: Python, Oracle, TypeScript/Node and Jupyter variants. `entity-emailer` has a hardcoded `lear` DB password.
- **`.gitignore` templates**: Python/Node with a typo `__mock__`, and a Dockerfile with invalid `EXPOSE 8080:8080`.
- **READMEs**: names-family APIs (ALPHA 2018, with a JWT "hack"), entity-* services with empty sections, local Postgres setup (a hardcoded superuser `lear`), Sentry snippets, and pay-admin setup. The business-filings-ui README is incomplete and its links point to the wrong repo.

## 6. Tests
- **Legal API tests** hit Oracle through `@oracle_integration`. They depend on hardcoded fixtures (CP0001965, 2019-03-08) and shared module-level state. Re-runs fail because Postman tests mutate data.
- **Queue and STAN tests** use deprecated `loop=` arguments and 2-second waits. Some are broad-except tests that can't fail. Several are skipped.
- **Shared helpers and fixtures**: `EPOCH_DATETIME`, `FROZEN_DATETIME`, `add_years` (leap day lands on Mar 1) and factories. `utcfromtimestamp` is deprecated.
- **Smaller notes**: `skip_in_pod` uses an identity check, so the string "False" doesn't skip. Alembic migration `98bee9969323` has an asymmetric downgrade. Many test packages are docstring-only stubs.

## Cross-cutting cautions
- **Reproducibility**: unpinned or branch-pinned git dependencies, and EOL pins (Flask 1.1.2, Werkzeug <2, SQLAlchemy <1.4, protobuf ≤3.19, pip 20.1.1).
- **Error handling**: broad `except` blocks that swallow errors, and queue workers that return 200 or drop messages. Retry semantics depend on which exceptions are re-raised.
- **Security**: hardcoded or random secrets, `forwarded_allow_ips='*'`, disabled SSH host verification, plaintext passwords and credentials in config and the 1Password script.
- **Duplicates and stubs**: many files are license-only or docstring-only (Apache 2.0, copyright 2018–2024). Treat them as placeholders.
