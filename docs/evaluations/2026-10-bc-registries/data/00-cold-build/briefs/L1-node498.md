<!-- level 1, node 498, children [157, 168, 179, 205, 242, 284, 298, 331, 332, 348, 349, 371, 390, 426, 440, 441] -->

**Parent brief: BC Registries (bcgov) CI/CD, deployment and developer docs**

This group covers documentation, build files and automation for the BC Registries and Legal Entities codebase. The repos are bcgov/lear, sbc-auth, sbc-pay and bcregistry-sre, plus a COLIN API README, a BCROS Jenkins repo and a Payment DB note. Almost all of it is condensed summaries of near-duplicate GitHub Actions workflows, Makefiles and OpenShift deployment notes. Many fragments are truncated or have empty `jobs` sections.

## Contents and routing

**1. Project docs (COLIN API README, Payment DB note)**
- COLIN API: Python/Flask, Apache 2.0, Development status as of 2019-04-09. Deploy steps are in `openshift/Readme.md`.
- Deploy pattern: `bc.yaml` goes to `cc892f-tools`. `dc.yaml` goes to dev, test and prod, with `TAG` and `APPLICATION_DOMAIN` set for test and prod.
- The Payment DB is Postgres with no build step, and the Payment API handles its schema. The doc is unfinished.

**2. OpenShift deployment notes**
- **BuildConfig/CronJob:**
  - Process `bc.yaml` to `-tools`, and `cronjob.yaml` to dev, test and prod.
  - Test and prod set `TAG`. Dev relies on the template default.
  - Run a job by hand with `oc create job --from=cronjob/...`.
  - Namespace prefixes: `cc892f` (lear), `6e0e49` (auth) and `78c88a` (pay).
- **OpenShift 4 migration runbook:**
  - Tools namespace (Jenkins, RBAC/NSP, BC/IS/pipelines).
  - Dev/test/prod (3 Postgres DBs, Keycloak, DCs).
  - Data migration with PVC Migrator or `pg_dumpall`/`psql`.
- **Notebook-report services:** filings, sftp-gazette, sftp-icbc, sftp-nuans, plus the auth and pay notebook reports.
  - Same dev flow: venv, `bc.yaml`, cronjob with `SCHEDULE`.
  - Cron times are UTC.
  - SFTP needs an SSH key and `SFTP_HOST_KEY`.
- **Container and cron images (payment-jobs, ftp-poller):** Python 3.12.2-bullseye, go-crond, Poetry, OpenShift uid handling, runner scripts around `invoke_jobs.py`.

**3. BCROS Jenkins-on-OpenShift (zcd4ou-\* namespaces)**
- Jenkins 2.176.3 image, templates, pipeline-cli v0.0.6 deploy scripts and `config.groovy`.
- Phase 1 is done (Dec 2019). Phase 2 (Enterprise DB) and Phase 3 (Jenkins orchestrator) are still to do.

**4. Makefiles (about 20 repos)**
- Shared template: `setup`, CI (pylint, flake8, pytest) and CD (build, tag, push to OpenShift, driven by `TAG_NAME`).
- Stacks: pip/venv Python, Poetry Python, Node frontends (business-filings, auth-web), a local-dev Makefile and a generic template.
- The deprecated 1Password `update-env` is still present in several.

**5. GitHub Actions CI (PR checks)**
- Shared shape: `setup-job` gate → `linting`, `testing`, `build-check` (`make build-nc`). Jobs run `make` targets, with Codecov uploads using `fail_ci_if_error: false`.
- Covered: queue services (NATS/entity-\*), jobs, Keycloak and Docker-mock APIs, pay and Postgres-backed tests, colin-api, data-reset-tool, and the `auth-web` and business-filings UIs.
- A Python 3.12 `build-check` and test/coverage variant is also covered.
- Outliers: a Sentry config and an HTML template generator.

**6. GitHub Actions CD**
- **OpenShift CD:**
  - Each service has a by-push and a by-dispatch workflow.
  - Steps: checkout, `oc login`, `make cd`, `oc rollout status` (some), and a Rocket.Chat failure notice to `#registries-bot`.
  - Services: lear (colin-api, entity-\*, legal-api, jobs, data-reset-tool), sbc-auth (auth-api, queue, account-mailer), sbc-pay (pay-api, admin, queue, payment-jobs, ftp-poller, bcol-api, notebook-report).
- **GCP CD:**
  - Calls the `bcregistry-sre` reusables `cloud-run-service-cd`, `cloud-run-job-cd`, `backend-cd` and `backend-job-cd`.
  - Triggers: `feature-legal-name` for Cloud Run, `feature-gcp` for backend.
  - Manual `target` is dev/test/sandbox/prod.
  - UI CD uses `ui-cd-node20`, and OAS CI uses `oas-ci`.
  - A SQL sync workflow copies files to `gs://auth-db-dump-prod/`.
- Governance and tooling: CODEOWNERS, the sbc-auth contributor flow (fork, rebase on `upstream/development`, `git commit -s`), release-drafter, a ZenHub release script, the Jenkins PR pipeline and a changelog config.

**7. Developer environment notes**
- Prefect ETL POC, Jupyter/devcontainer and VS Code setup for auth-api.

## Caution:
- **Hardcoded `TAG_NAME="dev"`:** This is the most common issue across the CD workflows. Dispatch inputs for test or prod may not override it. Check that `TAG_NAME` and `APP_NAME` are defined (or exported by `make cd`) before the rollout step.
- **Push-triggered GCP workflows:** `inputs.target` is empty on push, so the reusable workflow needs a default. The GCP workflows run only on `feature-legal-name` or `feature-gcp`, not `main`.
- **Unpinned reusables:** `bcregistry-sre` workflows are used at `@main`, and the Rocket.Chat action at `@master`.
- **Deprecated runner:** `ubuntu-20.04` is end-of-life. Also outdated: `actions/setup-python@v1` and Python 3.8 with pip 20.1.1 in some places.
- **Disabled and incomplete CI:** Several workflows have their test or Codecov steps commented out. An undefined `matrix.python-version` appears in some jobs. Many snippets have empty `jobs` sections. Alerts fire on failure only.
- **Hardcoded secrets and credentials:** Test values (`postgres/postgres`, `1111111111`, `2222222222`, MinIO and the Sentry `SECRET_KEY`) and a webhook `authToken` appear in plaintext. Unfilled placeholders remain, and one Codecov token may be exposed.
- **Remote execution risk:** BCROS runs `curl | bash` on pipeline-cli with no checksum, and evaluates remote Groovy. The docker-compose install is unpinned, via curl.
- **Namespace and environment mismatches:** The `cc892f`, `6e0e49` and `78c88a` IDs are hardcoded. BuildConfigs and CronJobs target different namespaces. Dev TAG behavior is ambiguous.
- **Operational hazards:** The migration needs downtime and manual DC env copying. Cron files need a trailing blank line. `oc rollout -w` can hang. Cron is in UTC. The payment-jobs `run_send_statement_notificaton` filename has a typo and an overlapping schedule.
- **Staleness and errors:** Some documents carry dates or settings from 2019, such as `GO_LIVE_DATE`. Specific bugs are the VS Code `settings.json` syntax error and the "What' new" typo.
