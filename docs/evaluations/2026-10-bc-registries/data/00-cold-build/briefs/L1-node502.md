<!-- level 1, node 502, children [100, 130, 169, 180, 187, 209, 210, 231, 238, 267, 269, 282, 283, 290, 291, 297, 312, 324, 353] -->

# Parent Brief: BC Gov OpenShift Deployment Templates and Ops Notes

## What this is
Condensed notes on OpenShift/Kubernetes manifests, templates and parameter sets for BC Gov projects (bcros/lear business filings, sbc-pay, sbc-auth, NATS, Oracle, nginx). Most are `${...}` parameterized Templates. Many are truncated stubs or near-duplicates. Namespaces seen: `fsxqpf-prod`, `hak2zo-dev`, `gl2uos-tools`, `cc892f` (+`-tools`/`-dev`/`-test`/`-prod`), `6e0e49`, `78c88a`, `1rdehl-*`, `l4ygcl-tools`, `d893f6-tools`.

## Routing by topic

**NATS Streaming + Postgres (`fsxqpf-prod`, `hak2zo-dev`)**
- `nats-streaming-6`: 3 replicas, clustered, id `queuenet`, SQL store on `postgresql-nats-dev:5432/nats-db`, `cluster-log-path` PVC at `/mnt/natsdata`. Service exposes 4222 and 8222.
- `postgresql-nats-dev` DeploymentConfig: Recreate, PVC-backed, creds from ConfigMap `nats-db`, image trigger on `postgresql:dev`.
- Setup guide files: `nats-deploy.yml`, `nats-service.yml`, `postgres-deploy.yml`, `postgres-service.yml`, `scripts.sql`.

**Postgres templates**
- sbc-pay `${NAME}-deploy`: PG 10, DB `pay-db`, ConfigMap and Secret, PVC class `gluster-file-db`.
- `postgresql-dc` for DB `bcros`: PG 9.6, Secret key names mismatch, invalid `maxSurge` with Recreate.
- `postgresql` (`cc892f`, DB `tracker`, PG 12, 5Gi).

**sbc-pay and sbc-auth**
- `bcol-api` build and deploy templates: Jaeger sidecar, route on `pathfinder.gov.bc.ca`.
- auth-api and auth-web `oc` runbook: label-based delete includes `pvc`.
- `auth-api` service and route on Silver.

**coops-ui (bcros)**
- Deploy template: Caddy on port 2015, `WEB_APP_CONTEXT_PATH=cooperatives`, HPA, ConfigMaps. Service port 2015 vs 8080 is inconsistent.
- Build is two-stage: `coops-ui-inter` (nodejs:8) feeding `coops-ui` (`bcgov-s2i-caddy`).
- A separate deploy fragment for the API variant: DB `lear`, JWT/OIDC, NATS, pre-hook `pre-hook-update-db.sh`.

**entity-filer and other lear components**
- `entity-filer` (`pay_filer.py`): NATS subjects `entity.filing.payment` and `entity.filing.filer`.
- Queue-service params (`cc892f` dev): `entity-pay`, `entity-bn`, `entity-digital-credentials`, `entity-emailer`, `entity-filer`.
- API params: `colin-api`, `data-reset-tool`, `legal-api`.
- A Firebase hosting config for `business-filings-dev` is unrelated.

**Build templates**
- Parameter sets for lear (`master`/`main`), sbc-auth and sbc-pay services. Shared defaults: CPU 2/1, memory 2Gi.
- Python Docker BuildConfigs (3.8.5/3.8.6-buster, pip 20.1.1/21.1.2, Artifactory base with `artifactory-creds`) for notebook-report, sftp-*, future-effective and update-colin/legal filings, and the email/bn/filer services.
- Separate S2I templates: `entity-filer-bc-template` and `legal-api-build-template`, from the fork `bsnopek-freshworks/lear`.

**CronJobs (`cc892f`)**
- Schedules:
  - Hourly: `future-effective-filings`, `update-colin-filings`, `update-legal-filings`.
  - Daily: `email-reminder` (07:00), `filings-notebook-report` (14:30).
  - Weekly/weekday: `sftp-gazette`, `sftp-icbc-report`, `sftp-nuans-report`.
- `notebook-report` variants run in `6e0e49` and `78c88a`.

**RBAC and CI**
- `github-cicd` Role and RoleBindings.
- Jenkins `edit` binding.
- `system:image-puller` bindings across `cc892f` environments.
- Jenkins pipeline `oradb-startup-pipeline`.

**Oracle 12.2 (`oradb1`, `gl2uos-tools`)**
- Containerized under arbitrary UIDs, with per-environment UIDs such as 1003919999.
- Dockerfile variants and `dockerInit2.sh`.
- Start/shutdown scripts and the CDEV `impdp` import runbook.
- A Sentry docker-compose setup note.

**nginx**
- Frontend configs on port 8080 (security headers, CSP).
- Prism-style mock-API proxies to port 4010 for bcol, pay, paybc, reports, auth and notify.

**Misc**
- One Flask API deployment template note (`${NAME}-${TAG}-deployment-template`), repeated 11 times.
- A pod-spec defaults note.

## Recurring cautions
- All `${...}` and `${{...}}` placeholders must be substituted (`oc process`) before applying. Many `SUFFIX`, `NAME` and `TAG` values have no default.
- Many fragments are truncated or have empty specs or blank `image` fields, so they are not runnable as-is.
- MIN_REPLICAS equals MAX_REPLICAS (1) almost everywhere, so there is no real autoscaling or HA.
- Aggressive settings: 1s probe timeouts and 1s rolling-update periods.
- Very low CPU/memory requests (10m/10Mi).
- Outdated or EOL pins: Python 3.7/3.8, pip 20.1.1, PostgreSQL 9.6/10, nodejs:8, Oracle 12.2.
- Security:
  - Empty `securityContext`.
  - `sslmode=disable` to Postgres.
  - Hardcoded or placeholder credentials in ConfigMaps and Secrets (`Zm9vYmFyCg==`).
  - Public `/nginx_status` and CSP with `unsafe-eval`/`unsafe-inline`.
- Selector/label and key mismatches:
  - NATS Service uses `deploymentconfig` while labels use `app`.
  - `database-user` vs `database-username`.
  - Naming inconsistencies from `${COMP_NAME}` vs `${DATABASE_PORT}` in the ConfigMap name.
- Timezone: cron schedules use the cluster's local timezone, and the `sftp-icbc-report` comment disagrees with its cron.
- `JOB_BACKOFF_LIMIT=0` semantics are described inconsistently across the notes.
- Typos in the source ("acccess", "stroage", `sentry.ioo`) are copied verbatim.
- Builds point at personal forks or inconsistent branches (`master`/`main`/`development`/`devops-rc1`).
- Dockerfile ENTRYPOINT is set twice, so only the last applies.
- Recreate strategy causes downtime.
