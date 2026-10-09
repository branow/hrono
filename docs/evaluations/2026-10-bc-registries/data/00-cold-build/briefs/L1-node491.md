<!-- level 1, node 491, children [8, 10, 14, 25, 26, 35, 36, 40, 41, 43, 56, 111, 147, 163, 170, 171, 177, 183, 192, 193, 194, 226, 256, 257, 268, 458] -->

# Parent brief: colin_api / BC Registries Postman collections and related test code

This group is mostly Postman collection artifacts for BC Registries-style APIs, with a few non-Postman code summaries. Nearly everything is hardcoded fixture data. Many entries are truncated or duplicated, so bodies, assertions and payloads are often unavailable.

## Routing: what is where

**colin_api filings and businesses (`{{url}}/api/v1/businesses/...`)**
- **Captured responses and requests**
  - Main fixture: CP0002098, LAKES ARTISAN COOPERATIVE. The sub-resources are `/office` and `/directors`.
  - Other fixtures:
    - CP0001965: CENTRAL INTERIOR COMMUNITY SERVICES CO-OP
    - CP0001248: change of name
    - CP0002108: special resolution
    - CP0001164
    - BC0702216: voluntary dissolution
    - CP3490248
    - BC0664974: transition
    - BC 0725054, 0847102 and 0876340
  - Also an event lookup and `GET /api/v1/meta/info`.
  - Filing types seen: annualReport, changeOfAddress, changeOfDirectors, changeOfName, specialResolution, historic, dissolution/voluntary, transition, incorporationApplication, alteration, correction.
  - Request fixtures take an `eventId` from environment variables (`arEventId`, `coaExtraEventId`, `codExtraEventId`, `codEventId`, `coaEventId`, `customCodEventId`).
  - Newly created corps use `newCorpNum`, `newCorpNumForCor` and `newCorpNumForCorAll`.
- **Versions and servers seen**
  - `0.1.0a0.dev` on Werkzeug 0.15.x and Python 3.6.5 (July 2019)
  - 2.0.0 to 2.4.0 on Werkzeug 0.16.0 and Python 3.7.4 (late 2019)
  - 2.27.0 on Werkzeug 1.0.1 and Python 3.8.8 (Dec 2021)
  - Dated captures may be stale.
- **Test scripts**
  - Baseline assertions: response time (10000ms or 20000ms), status 200 (201 for creates), JSON Content-Type.
  - Change of Directors (COD) scripts:
    - They loop over `directors`, splice names out of hardcoded `current` and `ceased` lists, and assert both end empty.
    - Current directors need a null `cessationDate`. Ceased directors need one equal to `today`.
    - Variants use the names CUSTOM1, CUSTOM2, LAUREN and Xyz Inc.
  - Header checks cover annualReport, changeOfAddress, changeOfDirectors and dissolution (one party, role `Custodian`).
  - Business checks assert hardcoded dates and names.
  - Other suites: ops (`readyz`, `healthz`), reset/cooper, corp-number generation, corrections, alterations, and share structure/names/parties.
  - Event-type mapping: `OTANN`, `OTADD`, `OTCDR`.
- **Prerequest scripts**
  - `today` is set as YYYY-MM-DD with zero-padded `slice(-2)`.
  - `cessationDate=2019-09-05` and `appointmentDate=2019-08-04` are static.
- **Fixture endpoints**
  - `/api/fixture/export`, `/api/fixture/delete` and `/api/fixture/import/{BEN,CP}`.
  - Fixture IDs: BC1219957, BC1218875, BC1218877, BC0123000, CP0001405.
  - Exports store `binary_response`. Imports expect 201.
- **Environments and collections**
  - "LEAR Colin Local": `url=http://localhost:5000`.
  - Collections "colin-api" (v0.108) and "Load Business Flow".
  - Saved 201 examples from several API versions.

**Auth API collection (`{{api_url}}/api/v1/...`)**
- Users and contacts: user, org and entity contacts. POST and PUT variants, with `userToken`, `memberToken` and `bceidToken`.
- Affiliations, invitations, affidavits, terms of use, orgs, memberships, and staff operations.
- `POST /test/reset` per role, clearing the token variables.
- API keys: the tests wrongly assert `filingTypeCode='OTADR'`.
- Test scripts capture tokens and IDs into environment variables: `userToken`, `memberToken`, `bceidToken`, `staffToken`, `org_identifier`, `invitation_id`, `inv_token`, `member_id`, `term_version`, `documnent_key`.
- Many checks are substring checks on `response.text()` with a 10000ms limit.
- Environment fixtures hold sample emails, phones, `business_number` CP0001847, and `service-account-*` values.
- JSON Schemas (draft-07) for affiliation invitations and generic invitations: request, response and list shapes.

**OAuth2 token pre-request scripts**
- About ten near-identical client-credentials scripts.
- The token variable differs: `accessToken`, `memberAccessToken`, `bceidAccessToken` or `staffAccessToken`. They also differ in credential variable names.
- One outlier is a 1Password-to-OpenShift secrets CLI.

**CAS/ORDS HATEOAS links**
- Host `heineken.cas.gov.bc.ca:7019/ords/cas/cfs/`.
- Example IDs: party 11111, account 4101, site 29921, invoices 10021–10023.
- The adjustments href has a trailing space.

**k6 performance setup (legal-api)**
- A Postman-to-k6 shim, with the vendored URI.js v1.19.11 (plus punycode, SLD and IPv6 helpers).
- A generated script for `legal-api-test.apps.silver.devops.gov.bc.ca`, with identifier FM0276213 and Keycloak auth.

**legal_api Python/Flask code**
- Filing validators, one per filing type (incorporation, continuation, amalgamation, restoration, dissolution, firms, alteration, change of address/directors/name, AGM, annual report, special resolution, court order, and others), with correction filings bypassing the rest.
- Services: involuntary dissolution, PDF stamping, registrar info.
- Utilities, the `/dissolutions/statistics` endpoint, and tests.

**Fragments with no usable content**
- About two dozen truncated POST request skeletons (no URL or payload).
- Empty Postman event listeners (`exec: []` or `[""]`).
- Truncated annualReport and dissolution fragments, and Benefit Incorporation and COA test stubs.

## Key cautions
- **Hardcoded fixtures:** IDs, dates and names tie tests to specific data. `splice` mutates the expected lists, so re-runs won't repopulate them.
- **Environment dependencies:** `{{url}}`, `{{api_url}}`, `today`, the `*EventId` variables, `newCorpNum*` and the token variables must be set first. An unset variable breaks requests or lets assertions pass silently.
- **Disabled `Content-Type` request header:** it is not sent. This is vestigial on GETs.
- **Weak assertions:**
  - Existence-only and substring checks pass on wrong data.
  - The 10000ms and 20000ms limits are loose.
  - The API-key tests assert an unrelated fee code.
  - `businessNumber` is always null.
- **Likely bugs or typos:**
  - `memeberAccessToken` and `documnent_key`
  - `istermsaccepted`
  - `"format": "datetime"` in the invitation schemas
  - The "GET CON CP0002098" request uses CP0001248.
  - Both sides of the "Tester Testing" vs "Tester testing" mismatch need checking.
  - The `substring(-2)` in URI.js `absoluteTo`
- **Security:**
  - CORS is `*`, including on `/dissolutions/statistics`.
  - The secrets CLI takes the master password as an argument.
  - Tokens are set in both `pm.environment` and `pm.variables`.
- **Truncation:** most entries are cut off, so response schemas and assertion logic often can't be confirmed.
- **Python validators:** they return `None` on success, so callers must check for `None` versus `Error`. Several date and time edge cases exist (AGM 5-day grace, the 90-day forward cap, mixed timezones). The code relies on Unix-only `%-d` and the walrus operator (Python 3.8+).
