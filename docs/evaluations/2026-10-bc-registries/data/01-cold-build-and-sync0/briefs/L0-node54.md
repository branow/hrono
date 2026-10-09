<!-- leaf 54, 8 members -->

These condensations are SonarQube and Codecov configuration summaries for six repositories in the bcgov-style business/auth/pay stack: business-filings-ui, lear, sbc-auth, and sbc-pay. Each repo has a SonarQube config and a Codecov config. The exception is sbc-auth, which has only SonarQube details plus a separate Codecov entry. The Codecov block that mentions authapi, statusapi, and authweb is therefore sbc-auth's.

## SonarQube configs

Common traits:
- All use UTF-8 source encoding.
- Most carry `projectVersion=Autoscan`.
- Most leave test paths and CPD settings commented out.

| Project | Sources | Exclusions | Notes |
|---|---|---|---|
| business-filings-ui | `src/` | `src/resources/*` | Tests in `tests/unit`. CPD exclusions commented out. |
| lear | Commented out | `coops-ui.deprecated`, `schemas.deprecated`, `**/conftest.py`, `**/migrations/**` | Many source, test and inclusion lines are commented out. |
| sbc-auth | `auth-api/src/auth_api`, `auth-web/` | `auth-web/tests/unit/test-utils/test-data` | The same path is used for both `sonar.exclusions` and `sonar.cpd.exclusions`. All test paths are commented out. |
| sbc-pay | `pay-api/src`, `bcol-api/src`, `report-api/src` | None (commented out) | Tests and CPD rules are commented out. |

## Codecov configs

Shared baseline across all four repos:
- `require_ci_to_pass: true`
- Coverage range `70...100`, precision 2, round down
- Patch status disabled
- Project default disabled, so only named flags are checked
- Test paths ignored (`/tests/**`)
- Flags carry forward
- gcov parser: conditional and loop branch detection on, method and macro off
- Comments: layout `diff,flags,tree`, `require_changes: true`

Variations:
- **business-filings-ui**: branch `master`, `max_report_age: false`. No flags or targets are described.
- **lear**: Backend target is `auto`. Nine flags: colinapi, legalapi, entityemailer, entityfiler, entitypay, entitybn, entity-digital-credentials, furnishings, involuntary-dissolutions. They map to `colin-api/src/*`, `legal-api/src/*`, `queue_services/*` and `jobs/*`.
- **sbc-auth**: Branch `development`. Backend flags (authapi, statusapi, eventlistenerqueue, accountmailer) target 80%. The UI flag (authweb) targets 35%. Six flags map services to source paths.
- **sbc-pay**: Branch `development`, `max_report_age: false`. Backend target is 80%. Five flags: payapi, bcolapi, reportapi, paymentjobs, payqueue.

Across sbc-auth and sbc-pay the pattern is the same: an 80% backend target on `development`. The UI flag in sbc-auth is the only lower target.

## Caution:
- **Autoscan version (business-filings-ui, lear):** CI auto-updates it. In lear it looks like a possible placeholder, so verify it. Business-filings-ui exclusions apply only within `src/`, not the project root. It defines no test exclusions, so all of `tests/unit` is analyzed.
- **Commented-out paths (lear, sbc-pay, sbc-auth):** Lear's structure may have changed since the config was written, so check it. Sbc-pay's test paths (lines 10–12) must be enabled if test coverage is needed. Sbc-auth's test paths are also off.
- **Duplicate exclusion (sbc-auth):** The same path appears in both exclusion settings. This hides any intent for test-data to behave differently in each.
- **`max_report_age: false`:** It means no age limit, not disabled. Old reports are accepted.
- **`patch: false`:** There are no separate patch coverage checks, so PRs won't fail on coverage drops.
- **`project.default: false`:** Project-level checks apply only to named flags. In lear only the backend flag (target `auto`) is checked. In sbc-pay only backend at 80% is enforced. In sbc-auth targets apply only to the named flags, not all code.
- **gcov branch detection:** It is enabled selectively (conditional and loop on, method and macro off). This affects gcov parsing only.
- **`require_changes: true`:** Comments are suppressed when coverage doesn't change.

## Members

- business-filings-ui: .sonarcloud.properties
- business-filings-ui: codecov.yaml
- lear: .sonarcloud.properties
- lear: codecov.yaml
- sbc-auth: .sonarcloud.properties
- sbc-auth: codecov.yaml
- sbc-pay: .sonarcloud.properties
- sbc-pay: codecov.yaml
