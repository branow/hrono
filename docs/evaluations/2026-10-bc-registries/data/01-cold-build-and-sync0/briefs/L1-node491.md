<!-- level 1, node 491, children [8, 10, 14, 25, 26, 35, 36, 40, 43, 56, 147, 163, 170, 171, 177, 183, 192, 194, 226, 256, 257, 521, 522, 544, 545, 546] -->

# Parent brief: Postman collections for the BC registries APIs (colin_api, legal-api, auth-api)

This group is a set of Postman collection fragments, scripts and captured responses. They cover the **colin_api** business-filings service, the BC Registries **auth API**, the **legal-api** k6 performance setup, and a fixture import/export API. Most entries are truncated, and there are many exact duplicates. Almost everything is hardcoded to test fixtures. Bodies, schemas and full test logic are often missing.

## Routing guide

**1. colin_api captured responses and request records** (`{{url}}/api/v1/businesses/...`)
- **Business record:** `GET /businesses/CP0002098` is repeated about 12 times.
  - Payload: LAKES ARTISAN COOPERATIVE, type CP, jurisdiction BC, status Active, corpState ACT.
  - Dates: foundingDate 2010-10-15, lastAgmDate 2017-09-11.
  - `businessNumber` is null in every business response.
- **Other business records:** CP0001965 (CENTRAL INTERIOR COMMUNITY SERVICES CO-OP) is the main one. Sub-resources of CP0002098 (`/office`, `/directors`) have mostly truncated bodies.
- **Filing GETs:** `/businesses/{CP|BC|BEN}/{id}/filings/{type}?eventId=…` covers annualReport, changeOfAddress, changeOfDirectors, changeOfName (CP0001248), specialResolution (CP0002108, CP3490248), historic and dissolution/voluntary (BC/0702216).
  - Event IDs come from env vars such as `arEventId`, `coaExtraEventId` and `codExtraEventId`, or are literal (103251079, 103251082).
  - Other requests: `/office`, `/parties`, `/sharestructure`, `/names/TR` and `/businesses/event/CP/{id}`.
- **Version evolution seen in headers:**
  - 0.1.0a0.dev (July 2019, Werkzeug 0.15.4, Python 3.6.5)
  - 2.0.0–2.4.0 (late 2019, Werkzeug 0.16.0, Python 3.7.4)
  - 2.27.0 (Dec 2021, Werkzeug 1.0.1, Python 3.8.8)
- **Common response traits:** 200 or 201 with `application/json` and wildcard CORS. Bodies are mostly truncated.
- **Common request trait:** a `Content-Type: application/json` request header that is disabled and so not sent.

**2. POST filing requests and templated identifiers**
- **Hardcoded cooperative IDs:** CP0001965, CP0002098 and CP0001164.
- **Variable-driven BC/BEN/BC-company IDs:** `{{newCorpNum}}`, `{{newCorpNumForCor}}` and `{{newCorpNumForCorAll}}`.
- **Filing types:** incorporationApplication, alteration, correction, transition, dissolution (BC0702216) and changeOfAddress/changeOfDirectors.
- **Many snippets:** about two dozen near-identical POST skeletons have no URL or payload.
- **Identifier format:** it is inconsistent. The pattern varies between `BC{{newCorpNum}}` and bare `{{newCorpNum}}`.

**3. colin_api Postman test scripts** (assertions in JavaScript)
- **Baseline checks:** response time (10000 or 20000ms), status 200 (201 for creates), and JSON content-type.
- **Change of Directors (COD):**
  - Director reconciliation: loop `directors`, splice names from hardcoded `current` and `ceased` lists, and assert both end empty.
  - Field checks: `cessationDate` is null for current directors and equals `today` for ceased ones. `startEventId` must be below `codExtraEventId+1`.
  - Custom-director branching for CUSTOM1, CUSTOM2 and LAUREN.
- **Business, header and event checks:**
  - Business-record checks: LAKES ARTISAN COOPERATIVE and CP0002098.
  - Filing header assertions on `date`, `name`, `certifiedBy` and `email`.
  - Event-type mapping: `filing_typ_cd` OTANN, OTADD and OTCDR.
- **Filing lookups with fixed values:** special resolution, change of name, filing history (HF) and future filings (FE).
- **AR flow:** create saves `arEventId`.
- **Other filing types:** incorporation application, dissolution (one party with one Custodian role), alteration, correction and directors.
- **Utility checks:** corp-number generators, ops/meta health checks (`readyz`, `healthz`, `meta/info`), reset and share-structure checks.
- **Pre-request script:** it sets `today` as YYYY-MM-DD, and one variant also sets fixed `cessationDate` and `appointmentDate`.

**4. Auth-API collection** (`{{api_url}}`, `{{auth-api-base-url}}`)
- **Request families:**
  - User, org and entity contacts (POST/PUT).
  - Affiliations, invitations and affidavits.
  - Test-data resets, with `userToken`, `memberToken`, `bceidToken` and `staffToken`.
  - Account, org and membership lifecycle, with TermOfUse and staff operations.
  - API keys.
- **Typical test checks:** response time < 10000ms, status 200 or 201, no error, JSON body and substring checks on `response.text()`.
- **Variables saved:** the tests save `username`, `org_identifier`, `invitation_id`, `member_id` and tokens for later requests.
- **OAuth2 client-credentials pre-request script:** about a dozen variants fetch tokens such as `accessToken`, `memberAccessToken`, `bceidAccessToken` and `staffAccessToken`.
- **Outlier:** a 1Password-to-OpenShift secrets CLI.

**5. Fixture import/export API** (`/api/fixture/...`)
- **Export:** GET `export/{id}` and per-table exports for BC1219957, BC1218877, BC1218875 and CP0001405. Tests save `binary_response` and assert 200.
- **Delete:** DELETE `delete/BC0123000` and `delete/CP0001405`.
- **Import:** POST "post all tables" requests, which assert 201. They target `localhost:5000/api/fixture/import/BEN`, plus one `import/CP` request.

**6. Postman metadata and k6 performance setup**
- **Postman metadata:**
  - Environment "LEAR Colin Local", with `url=http://localhost:5000`.
  - Collections "colin-api" (v0.108) and "Load Business Flow".
- **k6 setup:**
  - Postman-to-k6 shim.
  - Vendored URI.js v1.19.11, with its punycode and SLD helpers.
  - A generated k6 script for legal-api test, using identifier FM0276213.
  - Workflow: export the Postman collection, run `npm run convert:postman`, hand-fix auth and headers, then run `k6 run`.

**7. Empty or truncated fragments**
- Many empty `prerequest` and `test` listeners, where `exec` is `[]` or `[""]`.
- Benefit Incorporation "CTST" request stubs.
- Annual-report and dissolution payload fragments, with `date` 2019-12-13 and 2021-12-10.

## Cautions that apply across the group
- **Hardcoded fixtures:** these include business IDs, director names, dates and values. Tests break if the data changes or if they run out of order. The `today` env var and the saved variables (`arEventId`, `newCorpNum*`, `codExtraEventId`, tokens) must be set first.
- **Known oddities or likely copy-paste errors:**
  - Misspelled `documnent_key`, plus `memeberAccessToken` and `istermsaccepted`.
  - The API-key tests assert `filingTypeCode='OTADR'`.
  - The "POST TA" content-type expects `application/vnd.github.v3+json`.
  - "GET CON CP0002098" actually uses CP0001248.
  - `multipart/form-data` on DELETE requests.
  - Disabled `Content-Type` on bodied requests such as `tax_ids`.
  - "GET New Corp Number, BC" is actually a POST.
- **Fragile assertion patterns:**
  - `splice` mutates the expected lists, so re-runs don't repopulate them.
  - Directors in neither list can pass silently.
  - `codExtraEventId+1` may concatenate strings.
  - Substring checks on text pass on unrelated content.
  - Existence-only checks accept empty arrays.
  - `||`/`&&` precedence in the TR names test.
- **Auth risks:** the token is stored in both `pm.environment` and `pm.variables`. There is no error handling if the token fetch fails. Resets clear tokens unconditionally. The BCeID tokens are empty placeholders.
- **Unknown schemas:** most response bodies and request payloads are truncated or missing, so schemas can't be evaluated. The collection definitions are cut off.
- **Stale versions:** the 2019-era stack (Werkzeug 0.15/0.16, Python 3.6/3.7, colin_api 0.1.0a0.dev to 2.4.0) may not match the current API (2.27.0 seen in 2021).
- **k6/URI.js notes:**
  - Generated k6 JS isn't production-ready. Delete `options.headers` in `libs/shim/core.js` so state doesn't leak between requests.
  - The `absoluteTo` bug: `substring(-2)` should be `slice()`.
