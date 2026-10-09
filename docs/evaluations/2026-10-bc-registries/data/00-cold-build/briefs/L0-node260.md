<!-- leaf 260, 17 members -->

**What this is:** A set of condensed notes on vault-to-application mappings, which look like secret-store configurations. Each vault name maps to the applications whose secrets it holds. They seem to come from several related BC Registries-style services: entity/filings, pay, and auth. Three entries are empty arrays with no data.

**Groupings present**

1. **Entity/filings configs.** The `entity` vault appears in most of these entries.
   - Core apps that recur: `postgres-legal`, `sentry`, `launchdarkly`, `entity-service-account`, `filings-jobs`, `jwt`.
   - NATS-related variants: `nats-emailer`, `nats-filer`, `nats-furnishings`.
   - Variants by purpose:
     - Emailer: adds `email-reminder`.
     - Furnishings: adds `furnishings`, `sftp-bclaws`, `sftp-bcmail`.
     - Filer: adds `involuntary-dissolutions`, `legal-api`.
     - Minimal: `filings-jobs`, `entity-service-account`, `sentry`.
     - Earliest: `colin-api`, `test-oracle`, `sentry`, `jwt`, `launchdarkly`.
   - `shared` → `nats` accompanies most of them. One variant adds `naics`.
   - `api` → `mras-api`, `report-api-gotenberg` appears in two of them.
   - Other single-vault additions:
     - `minio` → `base`, `lear`
     - `bbdc` → `aca-py`
     - `nats` → `entity-events-listener`

2. **Relationship/auth configs.** The `relationship` vault holds the database and JWT apps.
   - `postgres-auth` and `notebook-report`
   - `jwt`
   - `sentry` → `relationship-api` is paired with it throughout.
   - `keycloak` → `jwt-base`, and `payment-external-services` → `bcol`, appear in one four-mapping entry.

3. **Pay configs.** These share a `pay` or `relationship` base and add payment-specific vaults.
   - `pay` → `postgres-pay`, `notebook-report-pay`
   - `relationship` → `postgres-pay`, `pay-api`, `pay-admin`, `jwt`, plus `payment-jobs` and `ftp-poller` in the largest entry
   - Shared pattern: `shared` → `api-endpoints`, `encryption-key`; `keycloak` → `jwt-base`, `sbc-auth-admin`; `payment-external-services` → `paybc`, `cfs`; `launchdarkly` → `pay`
   - `gcp-queue` variants: `base`, `account-events-listener`, `payment`, `account-mailer`, `gtksf3`, `topics`
   - `minio` → `payment-jobs`, `base`
   - `entity` → `colin-api` (a cross-reference)

4. **Empty entries.** Three entries are empty arrays.

**Caution:**
- Binding is one vault to one application name. It's unclear what happens if credentials rotate or an application is renamed.
- `shared` holds only `nats` in several entries. Check whether that's intentional or incomplete.
- `nats-furnishings` and `furnishings` are listed separately in the `entity` vault. This could be duplication or a scope boundary problem.
- `nats` (in `shared`) and `nats-filer` (in `entity`) are distinct applications despite similar names.
- What the `vault` key represents is unclear: storage tier, permission scope, or secret engine type.
- Each vault is a separate secret namespace. The listed applications store secrets there. They aren't every app that uses that vault's data.
- `minio` appears twice with different apps. This is probably intentional but risks accidental duplication in maintenance.
- `gcp-queue` appears twice in one entry. Merge the two or verify the duplication is intentional.
- `relationship` serves two applications in one entry. Verify that `sentry` → `relationship-api` isn't a typo or incomplete.
- Some entries are minimal, with no descriptions or metadata. Whether the multi-vault configs are complete is unclear.
- Verify that the one-to-one vault-to-application mapping assumption holds.

## Members

- lear: colin-api/devops/vaults.json
- lear: data-reset-tool/devops/vaults.json
- lear: jobs/email-reminder/devops/vaults.json
- lear: jobs/filings-notebook-report/devops/vaults.json
- lear: jobs/furnishings/devops/vaults.json
- lear: jobs/future-effective-filings/devops/vaults.json
- lear: jobs/involuntary-dissolutions/devops/vaults.json
- lear: jobs/sftp-icbc-report/devops/vaults.json
- lear: jobs/update-colin-filings/devops/vaults.json
- lear: jobs/update-legal-filings/devops/vaults.json
- lear: legal-api/devops/vaults.json
- sbc-auth: jobs/notebook-report/devops/vaults.json
- sbc-pay: bcol-api/devops/vaults.json
- sbc-pay: jobs/notebook-report/devops/vaults.json
- sbc-pay: jobs/payment-jobs/devops/vaults.json
- sbc-pay: pay-admin/devops/vaults.json
- sbc-pay: pay-api/devops/vaults.json
