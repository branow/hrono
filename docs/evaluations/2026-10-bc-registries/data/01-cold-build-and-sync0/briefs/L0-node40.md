<!-- leaf 40, 10 members -->

**What this is:** A set of condensed notes on Postman test scripts from one API test collection. The API is a Canadian business-filings service (`/api/v1/businesses/CP/...`). Each entry lists the assertions for one request, and most carry GOTCHAs about brittleness.

**Baseline assertions (nearly every request):**
- Response time under a threshold. It is 20000ms everywhere except the two "Current directors" requests, which use 10000ms.
- Status 200. The one exception is the annual-report create request, which expects 201.
- `Content-Type` equals `application/json`.

**Groupings**

1. **Director listings** (`GET Current directors CP0002098` and `GET Current directors ULC`). These are the same pattern. Both assert that `jsonData.directors` exists and, for each director, check:
   - `appointmentDate`, `deliveryAddress`, `endEventId`, `officer` and `title` exist.
   - `cessationDate` is null.
   - `startEventId` < `codExtraEventId+1`, read from the environment.

2. **Hardcoded-fixture filing lookups.** Each checks that `filing.<type>`, `filing.business` and `filing.header` exist. It then compares against fixed expected values:
   - **Special resolution** (two entries, a test suite and a POST script, with identical assertions):
     - Business identifier is `CP0002108`.
     - Header date is `2019-05-16`.
     - Header name is `specialResolution`.
     - `availableOnPaperOnly` is true.
     - `resolution`, `meetingDate` and `eventId` exist.
   - **Change of name** (`GET CON CP0002098`):
     - Business identifier is `CP0001248`.
     - Header date is `2018-05-10`.
     - Header name is `changeOfName`.
     - `availableOnPaperOnly` is false.
     - `legalName` and `eventId` exist.

3. **Filing history and future filings.**
   - **`GET HF CP0002098`:** the response is an array. Each `filing` has `business` and `header` (with `name`). All filings are dated before `2019-03-08`.
   - **`GET FE CP0002098`:** a minimal check of the three baseline assertions against `{{url}}/api/v1/businesses/CP/CP0002098/filings/future`.

4. **Annual report (AR) flow.** Three requests whose assertions are almost identical:
   - **Create** (status 201): saves `jsonData.filing.annualReport.eventId` to the environment as `arEventId`.
   - **`GET last AR`** and **`GET AR by id`**: both check `annualReportDate` and `header.date` against the `today` environment variable.
   - **Shared checks:**
     - `filing.annualReport`, `filing.business` and `filing.header` exist.
     - `header.name` is `annualReport`.
     - `email` and `certifiedBy` exist.
     - `eventId` exists.

**Caution:**
- `cessationDate` must be explicitly `null`, not merely absent or falsy. This applies to both director tests.
- `startEventId` has a dynamic upper bound of `codExtraEventId+1` from the environment.
- Special resolution:
  - `availableOnPaperOnly=true` is hardcoded, so the test breaks if the schema changes.
  - The date `2019-05-16` is hardcoded with no tolerance.
  - The identifier `CP0002108` is hardcoded and must be updated if the test data changes.
- Change of name: the identifier `CP0001248` and the date `2018-05-10` are hardcoded, so the test fails if the fixture changes.
- Filing history (`GET HF`):
  - The "Bob Date" `2019-03-08` is hardcoded with no explanation.
  - There are no null-safety checks, so it crashes if `filing.header.name` is missing.
- Future filings (`GET FE`): the 20000ms threshold differs from the 10000ms used for the director requests. `CP0002098` is hardcoded in both the URL and the request name.
- AR create:
  - `arEventId` is set at environment scope. Confirm that this is intended for downstream tests, rather than collection or global scope.
  - The `annualReportDate` equality check may fail if the time component differs.
- AR reads (`GET last AR`, `GET AR by id`):
  - They depend on the `today` variable being set beforehand.
  - The comparison is an exact string match, not date logic. A missing variable or a timezone or format mismatch fails the test, reportedly silently.
  - The 20000ms threshold is very loose, which suggests integration or external-API conditions.

## Members

- lear: colin-api/tests/postman/colin-api.postman_collection.json
- lear: colin-api/tests/postman/colin-api.postman_collection.json
- lear: colin-api/tests/postman/colin-api.postman_collection.json
- lear: colin-api/tests/postman/colin-api.postman_collection.json
- lear: colin-api/tests/postman/colin-api.postman_collection.json
- lear: colin-api/tests/postman/colin-api.postman_collection.json
- lear: colin-api/tests/postman/colin-api.postman_collection.json
- lear: colin-api/tests/postman/colin-api.postman_collection.json
- lear: colin-api/tests/postman/colin-api.postman_collection.json
- lear: colin-api/tests/postman/colin-api.postman_collection.json
