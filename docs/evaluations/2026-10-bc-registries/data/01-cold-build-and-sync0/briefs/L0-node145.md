<!-- leaf 145, 20 members -->

# Kubernetes secret-backed env var blocks (legal-API ecosystem jobs)

These condensations are a set of Kubernetes container `env` fragments. Each injects configuration into a pod through `valueFrom.secretKeyRef`. Nearly all read from the secret `${NAME}-${TAG}-secret`, and the key usually matches the variable name. The fragments appear to belong to different jobs and services: queue consumers, report cron jobs, SFTP/gazette jobs, and payment reconciliation jobs.

## Groupings

**1. NATS / service-integration blocks**
- Variables: `NATS_SERVERS`, `NATS_CLUSTER_ID`, `NATS_CLIENT_NAME`, `SENTRY_DSN`, `ACCOUNT_SVC_AUTH_URL`, `ACCOUNT_SVC_CLIENT_ID`, `ACCOUNT_SVC_CLIENT_SECRET`.
- Two blocks add `PAYMENT_SVC_FEES_URL` and `NATS_EMAILER_SUBJECT`.
- Two further blocks add `COLIN_URL` and `LEGAL_API_URL`. They are near-identical apart from key order.
- Small NATS add-ons are `NATS_EMAILER_SUBJECT` alone, and `NATS_FILER_SUBJECT` with `NATS_QUEUE`.

**2. Database credentials**
- Three variants:
  - **Single secret, `DATABASE_*` keys:** `DATABASE_USERNAME`, `DATABASE_PASSWORD`, `DATABASE_NAME`, `DATABASE_HOST`, `DATABASE_PORT`. In one block these are mapped onto `PG_USER`, `PG_PASSWORD`, `PG_DB_NAME`, `PG_HOST` and `PG_PORT`.
  - **Split-secret `PG_*` pattern:** `PG_USER` and `PG_PASSWORD` come from `postgresql-${TAG}-secret` (`database-user`, `database-password`). `PG_DB_NAME`, `PG_HOST` and `PG_PORT` come from `legal-api-${TAG}-secret` (`DATABASE_NAME`, `DATABASE_HOST`, `DB_PORT`).
  - **Payment DB:** `PAY_USER`, `PAY_PASSWORD`, `PAY_DB_NAME`, `PAY_HOST`, `PAY_PORT`, all from the single secret.
- The split-secret pattern is usually followed by `APP_FILE`, `SENDER_EMAIL`, `ERROR_EMAIL_RECIPIENTS`, and often `EMAIL_SMTP`.

**3. Email and report recipients/schedules**
- Common to most report jobs: `APP_FILE`, `SENDER_EMAIL`, `ERROR_EMAIL_RECIPIENTS`, `EMAIL_SMTP`.
- Per-job variations:
  - Incorporation daily report: `INCORPORATION_FILINGS_DAILY_REPORT_RECIPIENTS`.
  - Monthly reports: `COOP_FILINGS_MONTHLY_REPORT_RECIPIENTS`, `COOPERATIVE_MONTHLY_REPORT_RECIPIENTS`, `BC_STATS_MONTHLY_REPORT_RECIPIENTS`, `MONTH_REPORT_DATES`, `RETRY_TIMES`, `RETRY_INTERVAL`, `ENVIRONMENT`. A separate block holds `MONTHLY_REPORT_DATES` alone.
  - Weekly reports: `WEEKLY_REPORT_RECIPIENTS`, `WEEKLY_REPORT_DATES`, `ENVIRONMENT`.
  - Gazette: `SFTP_GAZETTE_RECIPIENTS`.

**4. SFTP**
- Appears three times, in two variants.
- The core set is `ENVIRONMENT`, `BCREG_FTP_PRIVATE_KEY`, `BCREG_FTP_PRIVATE_KEY_PASSPHRASE`, `SFTP_HOST`, `SFTP_PORT`, `SFTP_HOST_KEY`, `SFTP_USERNAME`, `SFTP_VERIFY_HOST`.
- One variant splits this across two fragments. The first adds `EMAIL_SMTP`, `DATA_DIR` and `SFTP_ARCHIVE_DIRECTORY`. The second holds `SFTP_USERNAME`, `SFTP_VERIFY_HOST` and `SFTP_GAZETTE_RECIPIENTS`.

**5. Payment reconciliation and reporting**
- Variables: `DAILY_RECONCILIATION_RECIPIENTS`, `CSO_DAILY_RECONCILIATION_RECIPIENTS`, `VS_DAILY_RECONCILIATION_RECIPIENTS`, `MONTHLY_RECONCILIATION_RECIPIENTS`, `CSO_MONTHLY_RECONCILIATION_RECIPIENTS`, `VS_MONTHLY_RECONCILIATION_RECIPIENTS`, `WEEKLY_PAY_RECIPIENTS`, `ENVIRONMENT`, `WEEKLY_REPORT_DATES`.
- The `PAY_*` database block is in the same family.

## Caution:
- **Template variables:** `${NAME}` and `${TAG}` are not resolved in the manifest. Deployment tooling must substitute them before applying. If it doesn't, the secret name is malformed or resolves literally.
- **Missing secret or key:** Most variables come from one secret. If the secret is missing from the namespace, or any key is absent, the pod fails to start. There is no fallback, and failures give no granular diagnostics.
- **Inconsistent secret names:** The split pattern mixes `postgresql-${TAG}-secret`, `legal-api-${TAG}-secret` and `${NAME}-${TAG}-secret`.
- **Inconsistent key names:** Keys mix styles, such as `database-user` and `DATABASE_NAME`. The port key is `DB_PORT`, while other blocks use `DATABASE_PORT`. Env var names can also differ from key names, for example `PG_DB_NAME` from `DATABASE_NAME`. Keys must match exactly and are case-sensitive, so `WEEKLY_REPORT_DATES` is not `weekly_report_dates`. One condensation warns that a mismatch could silently leave a variable empty.
- **Variable lookup:** One block warns that the variables must be defined in the parent config or the secret lookup fails.
- **Formatting:** One fragment is noted as requiring space indentation, not tabs.

## Members

- lear: jobs/email-reminder/k8s/templates/cronjob.yaml
- lear: jobs/email-reminder/k8s/templates/cronjob.yaml
- lear: jobs/filings-notebook-report/openshift/templates/cronjob.yaml
- lear: jobs/filings-notebook-report/openshift/templates/cronjob.yaml
- lear: jobs/future-effective-filings/k8s/templates/cronjob.yaml
- lear: jobs/future-effective-filings/k8s/templates/cronjob.yaml
- lear: jobs/sftp-gazette/openshift/templates/cronjob.yaml
- lear: jobs/sftp-gazette/openshift/templates/cronjob.yaml
- lear: jobs/sftp-gazette/openshift/templates/cronjob.yaml
- lear: jobs/sftp-icbc-report/openshift/templates/cronjob.yaml
- lear: jobs/sftp-icbc-report/openshift/templates/cronjob.yaml
- lear: jobs/sftp-nuans-report/openshift/templates/cronjob.yaml
- lear: jobs/sftp-nuans-report/openshift/templates/cronjob.yaml
- lear: jobs/update-legal-filings/k8s/templates/cronjob.yaml
- lear: jobs/update-legal-filings/k8s/templates/cronjob.yaml
- sbc-auth: jobs/notebook-report/openshift/templates/cronjob.yaml
- sbc-auth: jobs/notebook-report/openshift/templates/cronjob.yaml
- sbc-pay: jobs/notebook-report/openshift/templates/cronjob.yaml
- sbc-pay: jobs/notebook-report/openshift/templates/cronjob.yaml
- sbc-pay: jobs/notebook-report/openshift/templates/cronjob.yaml
