<!-- level 1, node 498, children [205, 242, 284, 298, 331, 332, 348, 349, 371, 390, 426, 440, 441, 536, 537, 538] -->

# BC Registries CI/CD Brief (bcgov: lear, sbc-auth, sbc-pay, bcregistry-sre)

**Scope:** This brief condenses roughly 20 repos' worth of CI workflows, CD workflows, Makefiles, READMEs, container and cron setup, and Jenkins/OpenShift tooling. Nearly everything follows a few shared templates. The differences are mainly in the service, path filter, Python or Node version, and target platform.

## 1. Shared templates

**CI (PR checks, GitHub Actions)**
- **Trigger:** `pull_request` (usually `assigned` and `synchronize`) with a path filter such as `jobs/<name>/**`, `queue_services/<name>/**` or `<service>/**`. sbc-pay uses PRs to `main` and `release/*`. There are no push triggers.
- **Defaults:** `shell: bash` and a per-component `working-directory`. Runner is `ubuntu-20.04`.
- **Jobs:** `setup-job` is a no-op gate (`run: "true"`, often `if: github.repository == '<repo>'`). `linting` (`make setup`, `make pylint`, `make flake8`), `testing` and `build-check` (`make build-nc`) all depend on it.
- **Testing:** `make setup`, then `make test`, then a Codecov upload with `fail_ci_if_error=false`. Coverage path and flag are per service, e.g. `legal-api/coverage.xml` with `legalapi`, `auth-api/coverage.xml` with `authapi`, `pay-api/coverage.xml` with `payapi`, and `bcol-api/coverage.xml` with `bcolapi`.
- **Postgres service:** `postgres:12` (Postgres 15 for one payment job) on 5432 with `postgres/postgres`. It needs explicit `pg_isready` health options.
- **docker-compose:** installed via curl from the latest GitHub release (unpinned).
- **Python versions:** 3.8 (older lear and auth jobs), 3.9.19, and 3.12 (sbc-pay, bcol, ftppoller, pay-admin).
- **Node:** 20.5.1 (business-filings UI and auth-web).

**Testing variants**
- **NATS queue services** (entity-filer, entity-bn, entity-emailer, entity-pay, entity-digital-credentials, business-create, business-event-listener) use `nats://nats:4222`, cluster `test-cluster`, and a per-service queue name. Entity-emailer adds a second `postgres-tracker:12` on 5433.
- **Scheduled jobs** (furnishings, involuntary-dissolutions) use client `entity.job.tester`.
- **Keycloak and Docker-mock API tests** (account-mailer, auth-api, bcol-api, ftppoller) use `USE_TEST_KEYCLOAK_DOCKER` and `USE_DOCKER_MOCK`. Some also use MinIO.
- **Pay tests** use a `pay-test` DB and a mock CFS at `localhost:8080/paybc-api`.
- **colin-api** is the only item with Codecov path `colin-api/coverage.xml`.

**CD (OpenShift via GitHub Actions)**
- **Variants per service:** `<svc>-cd-by-push` (dev only, repo-guarded) and `<svc>-cd-by-dispatch` (`workflow_dispatch` with an `environment` input of dev/test/prod, default dev).
- **Steps:** checkout, `oc login` with `OPENSHIFT4_LOGIN_REGISTRY` and `OPENSHIFT4_SA_TOKEN`, `make cd` (with `OPS_REPOSITORY`, `OPENSHIFT_*` and `TAG_NAME`), usually `oc rollout status dc/$APP_NAME-$TAG_NAME -n $OPENSHIFT4_REPOSITORY-$TAG_NAME -w`, then a failure-only Rocket.Chat notification to `#registries-bot` (`ROCKETCHAT_WEBHOOK`).
- **Services covered:**
  - **lear:** colin-api, data-reset-tool, email-reminder, entity-bn, entity-digital-credentials, entity-emailer, entity-filer, entity-pay, legal-api, furnishings, filings-notebook-report, future-effective-filings, involuntary-dissolutions, update-colin-filings, update-legal-filings, sftp-icbc-report and sftp-nuans-report.
  - **sbc-auth:** auth-api, auth-queue, account-mailer and notebook-report.
  - **sbc-pay:** pay-api, pay-admin, pay-queue, payment-jobs, ftp-poller, bcol-api and notebook-report.
- **Path filters** often include shared code: `queue_services/common/**` and selected `auth-api` or `pay-api` models (e.g. `cfs_service.py`).

**CD (GCP, via reusable workflows in `bcgov/bcregistry-sre@main`)**
All of these take `target` (dev/test/sandbox/prod) on manual dispatch and secrets `WORKLOAD_IDENTIFY_POOLS_PROVIDER` and `GCP_SERVICE_ACCOUNT`.
- `cloud-run-service-cd.yaml`: business-api, business-auth, business-bn, business-emailer, business-filer and business-pay. Push trigger is `feature-legal-name`.
- `cloud-run-job-cd.yaml`: email-reminder, filings-notebook-report, future-effective-filings, update-colin-filings, update-legal-filings and sftp-icbc-report. Push trigger is `feature-legal-name`.
- `backend-cd.yaml` and `backend-job-cd.yaml`: pay-admin, pay-api, pay-queue and payment-jobs. Push trigger is `feature-gcp`.
- `ui-cd-node20.yaml`: Business Filings UI and Account UI (OP_CONNECT secrets).
- `oas-ci.yaml`: Business API OAS CI.
- There is also a one-off workflow that syncs SQL under `jobs/gcp-db-data-masking/sql/**` to `gs://auth-db-dump-prod/`.

## 2. Makefiles
Nearly all Makefiles share one template.
- **Setup and CI:** `setup` (`install` then `install-dev`), `pylint` (`--rcfile=setup.cfg`), `flake8` and `pytest`.
- **CD:** driven by `TAG_NAME`. `test` tags dev→test. `prod` tags test→prod. Anything else defaults to dev: build, then tag.
- **Build:** `docker build` with `VCS_REF` and `BUILD_DATE` args.
- **Env vars:** `OPENSHIFT_DOCKER_REGISTRY`, `OPENSHIFT_SA_NAME`, `OPENSHIFT_SA_TOKEN`, `OPENSHIFT_REPOSITORY`, `TAG_NAME` and `OPS_REPOSITORY`.
- **Python/pip Makefiles:** legal_api, business_pay, entity_*, account_mailer and colin_api. Run targets differ (`bn_service.py`, `filer_service.py`, `email_service.py`, `pay_filer.py`, `flask run -p 5000`, and so on). entity_queue_common has a local build only.
- **Poetry Makefiles:** auth_api, admin (pay-admin), pay_queue and auth_queue. Flask runs on 5000 or 5001.
- **Node Makefiles:** business-filings and auth-web. They use `npm ci` and set `BUILD_TAG_NAME` (`dev-latest`, `test-latest` or `prod-latest`). `tag-production` adds a date tag.
- **Other Makefiles:** a local-dev docker-compose wrapper (`bcros_frontend`), and an unfilled generic template (`project_name='YOUR_PROJECT_NAME_HERE'`).
- **Retired feature:** `update-env` (1Password vault sync) was retired Oct 1, 2024 and is commented out in several.

## 3. Other CI/CD pieces
- **Release and project tooling:**
  - Release-drafter for payment services (main, v5), with `tag-template` `v$NEXT_PATCH_VERSION`.
  - A ZenHub release script (needs `GITHUB_ACCESS_TOKEN` and `ZENHUB_GRAPHQL_TOKEN`).
  - A sbc-auth Jenkins multibranch PR pipeline (lint, test, SonarQube, Rocket.Chat).
- **Contributor flow (sbc-auth):**
  - Fork, rebase on `upstream/development`, `git commit -s`, then a PR to `development`.
  - Default CODEOWNERS: @cameron-freshworks, @kialj876, @leksmall, @rarmitag, @severinbeauvais, @thorwolpert, @vysakh-menon-aot, @argush3.
- **Jenkins on OpenShift (lear, FreshworksStudio):**
  - Setup is role creation, `./build.sh`, then `./deploy.sh`.
  - Templates cover ImageStreams, BuildConfigs, a 10Gi PVC on `gluster-block`, a ConfigMap, a DeploymentConfig, Services, an edge-TLS Route and `jenkins_edit` RoleBindings across `zcd4ou-dev/test/prod`.
  - The plugin list has 100+ entries (blueocean 1.16.0, kubernetes 1.15.4).
  - Jenkins 2.176.3 is the base.
- **BCROS DevOps tooling:**
  - `pipeline-cli` 0.0.6 wrappers with `config.groovy`, `deploy.sh --pr= --env=`, and the 1Password CLI v0.8.0 install.
  - Phase 1 of the roadmap is done (Dec 2019). Phases 2 and 3 are not.
  - The jenkins app config uses namespace `zcd4ou-tools`.
  - Groovy init and webhook scripts for PR-environment cleanup (`oc delete` for `app=mds-dev-pr-${prNum}`) are triggered by GitHub webhooks.
- **Notebook-report cronjobs** (OpenShift, UTC cron):
  - Services: filings-notebook-report (`30 14 * * *`), sftp-gazette (`30 1 * * TUE`), sftp-icbc-report (`50 12 * * SUN,TUE-SAT`), sftp-nuans-report (`55 7 * * TUE-SAT`), and the Auth and Pay notebook reports.
  - Namespaces: cc892f (lear), 6e0e49 (auth), 78c88a (pay).
  - Build flow: `oc process` of `openshift/templates/bc.yaml` and `cronjob.yaml`.
  - The sftp services need an SSH key and `SFTP_HOST_KEY`.
- **Other dev docs:** Prefect ETL POC, Jupyter and devcontainer setup, and a VS Code setup for auth-api.
- **Payment jobs and FTP poller containers:**
  - Both use `python:3.12.2-bullseye`, go-crond 0.6.2, Poetry 1.8.3 and user `pay` (uid 1001).
  - Cron: the FTP poller runs every 30 minutes. Payment-jobs runs statements and GL-code updates (every 30 minutes) and statement notifications.
  - Runner scripts wrap `python3 invoke_jobs.py <JOB>`, with jobs CGI/EFT/CAS_FTP_POLLER.
- **Sentry config** (Postgres `db:5432`, Redis `redis:6379`) and an HTML email template generator (`generate_template`, `[[part.html]]` tokens) are outliers, not CI workflows.

## Caution
- **TAG_NAME always `dev`:** nearly every CD workflow hardcodes `TAG_NAME: "dev"`. Dispatch inputs for test or prod may not reach `make cd` unless the dispatch job overrides it. Some push jobs don't define `TAG_NAME` or `APP_NAME` at all, so `oc rollout` and `make cd` can fail with unclear errors.
- **Missing `target` on push:** GCP workflows that run on push have no `inputs.target`, so the reusable workflow needs a default.
- **Unpinned and branch-bound GCP workflows:**
  - Everything uses `bcregistry-sre@main`.
  - Auto-deploy fires only on `feature-legal-name` or `feature-gcp`, not `main`.
  - Check the spelling of `WORKLOAD_IDENTIFY_POOLS_PROVIDER` ("IDENTIFY").
- **Deprecated runner and actions:** `ubuntu-20.04` is EOL, so move to `ubuntu-24.04` or latest. `setup-python@v1` is outdated, `::set-output` is deprecated, and Rocket.Chat is pinned to `@master`.
- **Tests that don't run:** pytest and Codecov are commented out in sftp-icbc, sftp-nuans, email-reminder, filings-notebook-report, notebook-report and the sbc-pay testing job. The `matrix.python-version` reference with no matrix defined appears in future-effective-filings, update-colin-filings and update-legal-filings. Several workflows are truncated, with empty `jobs` sections.
- **Hidden failures:**
  - `fail_ci_if_error=false` masks Codecov failures.
  - Alerts fire only on failure, and `oc rollout status -w` can hang before the notification.
  - Missing `OPENSHIFT*` secrets fail late.
- **Path and trigger gaps:**
  - Narrow path filters mean unrelated changes get no check.
  - Only `assigned` and `synchronize` fire, not `opened`.
  - `github.repository` guards block forks.
  - Cross-service coupling means pay-api model changes trigger pay-admin, pay-queue and payment-jobs CI.
- **Hardcoded test secrets** (`postgres/postgres`, `2222222222`, `1111111111`, `mySecretKey`, `abcdefg`, `minio/minio123`, fake BCOL creds, the Sentry `SECRET_KEY`): keep these out of production. Check for any real token in committed files, such as the Codecov token and the Jenkins webhook `authToken` (plaintext).
- **Infrastructure fragility:**
  - Postgres needs explicit health options.
  - Unpinned docker-compose via curl can hit rate limits.
  - `TEST_NATS_DOCKER=True` is set with no NATS service container.
  - Tracker DB port 5433 and the `pay-test` DB name must match across settings.
- **Makefile hazards:**
  - A missing or unrecognized `TAG_NAME` silently falls back to the dev path.
  - `build-req` isn't idempotent.
  - Recipe lines run in separate shells, so venv activation must stay on one line.
  - Python 3.8 and pip 20.1.1 are EOL.
  - auth-web's `test` overwrites `.env`.
- **Cron and containers:**
  - Cron times are UTC (check the PST offset).
  - Cron files need a trailing blank line.
  - `exec go-crond` makes later code unreachable.
  - Runner scripts have no error handling.
  - `run_send_statement_notificaton.sh` has a typo and overlapping schedules.
  - The Oracle instant client 21.1.0 is hardcoded.
  - The executable bit needs `git add --chmod=+x`.
- **Jenkins and DevOps tooling:**
  - The Jenkins init script runs `evaluate()` on remote code.
  - Wrapper scripts pipe remote scripts into bash.
  - The Dockerfile base image is a placeholder.
  - Jenkins 2.176.3 and `jackson2-api:2.9.8` are outdated.
  - The deployment templates are truncated, with an empty container `image`, empty `github-credentials` and `JAVA_OPTS` cut off.
  - `build.sh` needs a manual PR number edit.
  - PR cleanup interpolates `prNum` unescaped (command injection), and a 25s kill timeout can leave deletes incomplete.
  - Docs have a `settings.json` quote typo, and the changelog has the typo "What' new".
