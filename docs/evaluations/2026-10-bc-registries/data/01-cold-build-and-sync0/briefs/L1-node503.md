<!-- level 1, node 503, children [129, 139, 145, 146, 155, 156, 186, 261, 318, 319] -->

# Parent brief: Kubernetes/OpenShift deployment config fragments (legal-API / BC Registries-style ecosystem)

The children are condensed notes on parameterized deployment manifests. Many are truncated or duplicated. Together they cover CronJobs, Jobs, secret-backed env blocks, pod/container specs, an OpenShift Template, an HPA, DeploymentConfig and PostgreSQL stacks, and a vault-to-application mapping.

## Contents by routing signal

1. **CronJob spec**
   - Ten identical copies.
   - Fields: `schedule: "${SCHEDULE}"`, `concurrencyPolicy: Forbid`, `successfulJobsHistoryLimit: ${{SUCCESS_JOBS_HISTORY_LIMIT}}`, `failedJobsHistoryLimit: ${{FAILED_JOBS_HISTORY_LIMIT}}`, and an incomplete `jobTemplate`.

2. **CronJob metadata, truncated at `spec:`**
   - Name `${NAME}-${TAG}`. Labels use `${NAME}`, `${TAG}` and `${ROLE}`.
   - Most variants use `batch/v1beta1`, which is deprecated. One uses `batch/v1`.
   - The labels split into `name`/`environment`/`role` versus `app`/`role`.

3. **Secret-backed env blocks (`valueFrom.secretKeyRef`)**
   - Mostly from `${NAME}-${TAG}-secret`.
   - **NATS and service integration:** `NATS_*`, `SENTRY_DSN`, `ACCOUNT_SVC_*`, `COLIN_URL`, `LEGAL_API_URL`.
   - **Database:** `DATABASE_*`, `PG_*` and `PAY_*`. The split `PG_*` pattern draws on `postgresql-${TAG}-secret` and `legal-api-${TAG}-secret`.
   - **Email and report recipients/schedules:** daily, weekly and monthly report jobs, plus `EMAIL_SMTP`.
   - **SFTP and gazette:** `BCREG_FTP_*`, `SFTP_*`.
   - **Payment reconciliation:** `*_RECONCILIATION_RECIPIENTS`, `WEEKLY_PAY_RECIPIENTS`.

4. **Pod-spec settings**
   - Nine batch-style copies: `restartPolicy: Never`, `activeDeadlineSeconds: 1600`, `terminationGracePeriodSeconds: 30`, `dnsPolicy: ClusterFirst`.
   - One long-running variant: `restartPolicy: Always`, an empty `securityContext`, `schedulerName: default-scheduler`.

5. **Container spec**
   - Name `${NAME}-${TAG}`.
   - Image `${IMAGE_REGISTRY}/${IMAGE_NAMESPACE}/${NAME}:${TAG}`, `imagePullPolicy: Always`.
   - Command `cd /opt/app-root; ./run.sh`.
   - Eight copies are truncated at env. One adds resources: limits 250m CPU / 2Gi memory, requests 50m CPU / 256Mi memory.

6. **Job manifest template**
   - Mostly metadata and label stubs: label set `app`/`role` or `name`/`environment`/`role`, with `backoffLimit` as `${{JOB_BACKOFF_LIMIT}}` or `{{JOB_BACKOFF_LIMIT}}`.
   - One full spec: six env vars from the secret, `restartPolicy: Never`, `activeDeadlineSeconds: 1600`.

7. **OpenShift Template v1 for a CronJob**
   - Truncated at the `objects` array.
   - Name is `${NAME}-cronjob`, labels `app=${NAME}`.

8. **Vault-to-application mappings**
   - Vaults include `shared`, `entity`, `gcp-queue`, `relationship`, `keycloak`, `minio`, `sentry`, `launchdarkly`, `API`, `web-url`, `database`, `api` and `bbdc`.
   - The `application` field is always an array.

9. **HorizontalPodAutoscaler v1**
   - Targets DeploymentConfig `${NAME}-${TAG}`.
   - Scales between `${{MIN_REPLICAS}}` and `${{MAX_REPLICAS}}`.
   - Labels are `name`, `environment` and `role`.

10. **Application DeploymentConfig and Service**
    - Port 8080, 1 replica, Rolling strategy, ImageChange trigger.
    - Probes are `/readyz` and `/healthz` on port 7070 in most copies, or `/ops/*` in one.
    - Two variants add a pre-hook, `pre-hook-update-db.sh`, with Abort on failure.
    - One variant uses a Recreate strategy with `activeDeadlineSeconds` of 21600.

11. **PostgreSQL stack**
    - Container on port 5432, secret-sourced credentials, a PVC, a Secret and a ClusterIP Service.
    - Includes TCP liveness and `psql` readiness probes.
    - Also includes several skeletal DeploymentConfig and Template fragments with no spec.

## Cross-cutting caution

- **Templating syntax is mixed:** `${VAR}` and `${{VAR}}` (and sometimes `{{VAR}}`) appear together. The `${{}}` form is used for numeric values: history limits, backoff limit and replicas. Confirm that the processing engine (OpenShift Template, envsubst, Helm and so on) handles each form, and that substitution happens before deploy. Unsubstituted `${NAME}`, `${TAG}` and `${ROLE}` stay literal.
- **Truncated or incomplete fragments:** CronJob metadata, the Template `objects` array, the `jobTemplate`, the env sections and the DeploymentConfig specs are cut off. Their validity can't be assessed.
- **Inconsistent labels and names between variants:** `app` versus `name`/`environment`, `${NAME}` versus `${NAME}-${TAG}`, and `${NAME}-cronjob` versus `${NAME}`. Confirm which variant is authoritative. Service selectors omit `role`.
- **Deprecated API:** `batch/v1beta1` for CronJob. Use `batch/v1`.
- **Secret and key fragility:**
  - A missing secret or key stops the pod from starting.
  - Key names are case-sensitive and inconsistent, for example `DB_PORT` versus `DATABASE_PORT`.
  - Secret names are inconsistent: `postgresql-${TAG}-secret`, `legal-api-${TAG}-secret` and `${NAME}-${TAG}-secret`.
- **Batch failure semantics:** `restartPolicy: Never` plus `activeDeadlineSeconds: 1600` (about 26.7 min) means a timeout fails the pod permanently, with no retry.
- **Resource and rollout risks:**
  - The 2Gi limit against the 256Mi request can lead to eviction.
  - Rolling update on 1 replica can leave no ready pod.
  - Probes use port 7070 while the container port is 8080.
  - The pre-hook Abort policy blocks rollouts if the DB script fails.
  - `run.sh` must exist in the image.
- **Security:**
  - An empty `securityContext` and empty capabilities apply no restrictions.
  - The PostgreSQL Secret uses plaintext `stringData`.
- **Vault mapping ambiguities:**
  - `base`, `account-mailer` and `ftp-poller` appear under more than one vault.
  - `nats` appears in both `shared` and `entity`.
  - The uppercase `API` vault name is case-sensitive.
  - `gcp-queue` is listed twice in one note, so it's unclear whether the lists merge or the last one wins.
  - The IDs `a083gt` and `gtksf3` are opaque.
