<!-- level 1, node 502, children [100, 130, 157, 169, 179, 180, 187, 209, 210, 231, 238, 241, 267, 269, 282, 283, 290, 291, 297, 312, 324, 344, 353, 363, 364, 434] -->

# Parent Brief: BC Registries (BCROS / LEAR / sbc-auth / sbc-pay) OpenShift & Docker Deployment Artifacts

**What this is:** A large collection of condensed, mostly partial or truncated OpenShift/Kubernetes templates, Dockerfiles, Makefiles, nginx configs and Docker Compose files. They belong to the BC Government registries stack. The stack includes `lear` (legal-api, colin-api, entity-* queue services, jobs), `coops-ui`, `sbc-auth` (auth-api, auth-web, account-mailer), `sbc-pay` (bcol-api, payment DB, notebook-report), NATS Streaming, PostgreSQL and Oracle. Namespaces seen: `cc892f-*` (the newer Silver cluster, most common), `6e0e49`, `78c88a`, `gl2uos-tools`, `l4ygcl-tools`, `hak2zo-dev`, `fsxqpf-prod`, `1rdehl-*`, `d893f6-tools`. Nearly everything uses `${...}` parameters that `oc process | oc apply` must fill in.

## Routing guide (where to look)

**1. NATS Streaming + Postgres backing store** (`fsxqpf-prod`, `hak2zo-dev`)
- NATS runs as 3 replicas in clustered mode. Cluster id is `queuenet`. Store is SQL against `postgresql-nats-dev:5432/nats-db`. It has a PVC `cluster-log-path` at `/mnt/natsdata`. The Service exposes ports 4222 and 8222.
- The Postgres DeploymentConfig uses the Recreate strategy and is backed by PVC `postgresql-nats-dev`. Credentials come from ConfigMap `nats-db`.
- A setup guide covers the files `nats-deploy.yml`, `nats-service.yml`, `postgres-deploy.yml`, `postgres-service.yml` and `scripts.sql`.
- A compose variant runs `nats-streaming` (ports 4222 and 8222, 512m memory limit), optionally with MinIO (`minio` / `minio123`, bucket `lear` or `businesses`).

**2. Database templates**
- `${NAME}-deploy` PostgreSQL 10 template (sbc-pay). Defaults: db `pay-db`, PVC class `gluster-file-db`, 512Mi memory limit.
- `postgresql-dc` template (db `bcros`, PostgreSQL 9.6). Its companion Secret template has the base64 value `Zm9vYmFyCg==`.
- Postgres 12 template for `tracker`.
- A Payment DB doc, unfinished.

**3. Build templates (ImageStream + BuildConfig)**
- Shared parameter set (NAME, GIT_REPO_URL, GIT_REF, SOURCE_CONTEXT_DIR, OUTPUT_IMAGE_TAG, CPU/MEMORY). It covers these services:
  - lear, branch `master`: colin-api, legal-api, data-reset-tool, email-reminder, future-effective-filings, update-colin-filings, update-legal-filings and the `queue_services/` services entity-pay, entity-bn, entity-emailer and entity-filer.
  - lear, branch `main`: filings-notebook-report and the sftp-* jobs.
  - sbc-auth, branch `development`: auth-api and account-mailer.
  - sbc-auth / sbc-pay, branch `master`: notebook-report. The name appears under both repos.
- Docker-strategy Python builds use `python:3.8.5` or `3.8.6-buster` from Artifactory with pull secret `artifactory-creds`. Pip is pinned to 20.1.1, 20.3.3 or 21.1.2.
- Source-strategy S2I builds:
  - `entity-filer` and `legal-api` from the fork `bsnopek-freshworks/lear`, on `python:3.7`.
  - `coops-ui-inter` (`nodejs:8`), then `coops-ui` (Caddy runtime, `WEB_APP_CONTEXT_PATH=cooperatives`).
- bcol-api build template (`sbc-pay`).
- Oracle-client and Oracle-image builds (see item 7).

**4. Deploy templates**
- **API/queue service parameter sets:**
  - Queue services in `cc892f` (entity-pay, entity-bn, entity-digital-credentials, entity-emailer, entity-filer) and `6e0e49` (account-mailer). TAG=dev, ROLE=queue.
  - API services: auth-api (`6e0e49`), colin-api, data-reset-tool and legal-api (`cc892f`). Each has a Service, Route (edge TLS, HAProxy IP allow list), HPA and DeploymentConfig. The legal-api / data-reset-tool DeploymentConfig has a DB pre-hook `pre-hook-update-db.sh`.
- **Other deploy templates:**
  - bcol-api deploy template with a Jaeger sidecar.
  - The `coops-ui` deploy template (Caddy, ConfigMaps, HPA).
  - A coops-ui / legal-api style template with a full env block and NATS.
  - The `entity-filer` template.
- **CronJob parameter sets** (`cc892f`, plus `notebook-report` in `6e0e49` and `78c88a`), with cron schedules:
  - Hourly: future-effective-filings, update-colin-filings, update-legal-filings.
  - Daily: email-reminder (07:00), filings-notebook-report (14:30).
  - SFTP: sftp-gazette (Tuesday 01:30), sftp-icbc-report (12:50 except Monday), sftp-nuans-report (07:55 Tuesday to Saturday).

**5. Runbooks and docs**
- OpenShift 4 migration (PVC Migrator, `pg_dumpall`).
- auth-api / auth-web build and deploy via `oc` labels.
- The `oc process | oc apply` flow for the BuildConfig (tools namespace) and DeploymentConfig / CronJob (dev, test, prod, selected by `TAG`).
- A Legal Entities COLIN API README.
- A Flask API deployment template named `${NAME}-${TAG}-deployment-template`.
- Sentry docker-compose setup.

**6. RBAC and CI**
- GitHub CI/CD Role and RoleBinding (`github-cicd`).
- Jenkins `edit` RoleBinding.
- `system:image-puller` bindings from `cc892f-tools`.
- Jenkins pipeline BuildConfig `oradb-startup-pipeline` (ref `379-oracle-pipeline`).
- Makefiles for the Python jobs and services. They share a CI flow of lint, test and Docker build, and a CD flow where `TAG_NAME` drives dev, test or prod through `oc tag`. Services covered include email-reminder, notebook-report, the sftp-* jobs, furnishings, involuntary-dissolutions, bcol_api, ftp-poller and payment-jobs.

**7. Oracle 12.2 in containers**
- Dockerfile variants run as `learDev` with arbitrary UIDs (1003…). Supplemental groups are 54321 and 54322.
- `dockerInit2.sh`, startup and shutdown scripts.
- A CDEV import procedure (`impdp`, schema `COLIN_MGR_DEV`).
- The `oradb1` DeploymentConfig in `gl2uos-tools`.

**8. Frontend and nginx**
- Static-serving nginx (port 8080, `/business` and `/business/auth`, CSP allowing Hotjar, LaunchDarkly and Sentry).
- Mock-API proxy configs (port 80, backends on :4010).
- A Node/Nginx Dockerfile.
- Firebase hosting config for the SPA `business-filings-dev`.

**9. Python code and containers**
- `version.py` modules: `get_run_version()` appends `OPENSHIFT_BUILD_COMMIT`. There are also an outlier utilities module and a PDF certification helper.
- Python 3.8 Dockerfiles for the job scripts, plus one 3.12 variant.
- Devcontainers.

**10. Docker Compose for local dev**
- Prefect Server stack (core-1.1.0).
- Postgres 11 test DBs (legal_api, tracker, lear, authdb, paydb) and Jaeger.
- SFTP (`atmoz/sftp`).
- A devcontainer with NATS.
- Sentry stack.

## Cross-cutting cautions

- **Truncation and placeholders:** Many manifests are cut off, with empty `objects`, empty specs, blank `image` fields or null `creationTimestamp`. Treat them as drafts. Every `${VAR}` must be substituted. `${{VAR}}` is the integer form in OpenShift. Mixed syntax and `{{...}}` placeholders appear and need checking.
- **Hardcoded namespaces and values:** Namespace IDs, domains, registry paths, the Artifactory host and the `artifactory-creds` secret are hardcoded and must exist or be overridden per cluster.
- **Dev TAG ambiguity:** Dev is deployed without `TAG`, and notes disagree on what the default is.
- **Outdated stacks:** Python 3.7 and 3.8, old pip pins, PostgreSQL 10, nginx 1.18, `nats-streaming` and PyPDF2 are all EOL or deprecated.
- **No autoscaling:** MIN_REPLICAS and MAX_REPLICAS (or REPLICA_MIN and REPLICA_MAX) are 1 across the board, so HPAs do nothing and each service is a single point of failure. Requests of 10m CPU and 10Mi memory are very low.
- **Rolling strategy:** The 1s update and interval periods are aggressive.
- **Probes:** 1s probe timeouts are tight.
- **Security issues:**
  - Hardcoded or placeholder credentials: MinIO, the Prefect and Sentry passwords, the SFTP user, and `Zm9vYmFyCg==` for every field of the Postgres Secret.
  - `sslmode=disable` to Postgres.
  - A client secret in a ConfigMap.
  - `unsafe-eval` and `unsafe-inline` in the CSP.
  - nginx `/nginx_status` with `allow all`.
  - Empty `securityContext` and `chmod 777` directories.
- **Config bugs flagged:**
  - Recreate strategy combined with `maxSurge` and `maxUnavailable`, which is invalid.
  - Secret key mismatch: `database-username` against `database-user`.
  - Selector and label mismatches, such as a Service selecting `deploymentconfig` while labels use `app`.
  - A ConfigMap value missing its closing brace: `${DATABASE_PORT`.
  - Typos in names: `acccess`, `sentry.ioo`.
  - Duplicate ports, and a duplicate ENTRYPOINT in the Oracle Dockerfiles.
  - A `PYTHONPATH` that doesn't match the script location.
  - `oradb1` `observedGeneration` 31 against `latestVersion` 13.
  - A conflict in what `JOB_BACKOFF_LIMIT=0` means.
  - Cron timezone and comment mismatches, for example sftp-icbc-report.
- **Operational:**
  - Recreate causes downtime.
  - Data migration needs downtime.
  - Deleting PVCs is irreversible.
  - The DB pre-hook `Abort` blocks rollouts.
  - The `createbuckets` service has a startup race with MinIO.
  - Shared `db-data` volumes weaken isolation.
  - The `host` network mode breaks `forwardPorts`.
- **Repo and branch hygiene:** Several defaults point at a personal fork (`bsnopek-freshworks`). Branch names are inconsistent (`master`, `main`, `development`, `devops-rc1`). Verify the repo and branch before building.
