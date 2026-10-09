<!-- leaf 546, 9 members -->

This is a set of condensed notes on requests from a Postman collection. The collection targets a business-filings API (`{{url}}/api/v1/businesses/...`), and it appears to be a BC corporate registry test suite. Nearly every item is a GET or POST against a `/filings/<type>` endpoint. Most have an empty response array and a disabled `Content-Type: application/json` header.

## Groupings

**1. Templated-identifier filing requests (the common pattern)**
These use `{{url}}` and `{{newCorpNum}}` for the business identifier. They differ in method, jurisdiction segment and filing type.
- POST `.../businesses/BEN/{{newCorpNum}}/filings/incorporationApplication`. It sits in the "COD" folder as "POST COD" and has a test listener.
- GET `.../businesses/BC/BC{{newCorpNum}}/filings/changeOfDirectors`
- GET `.../businesses/BEN/BC{{newCorpNum}}/filings/changeOfAddress`
- GET `.../businesses/BEN/BC{{newCorpNum}}/filings/annualReport`
- POST `.../businesses/BC/BC{{newCorpNum}}/filings/transition`. It has a test listener.
- GET `.../businesses/BC/{{newCorpNum}}/filings/transition`. This one has no `BC` prefix on the number.

**2. Different variable**
- GET `.../businesses/BC/{{newCorpNumForCorAll}}/sharestructure`. It uses a different variable and a different resource (`sharestructure`, not `filings`). It has no headers or response, and it belongs to the "Transition" folder alongside "GET last TA BC0664974".

**3. Hardcoded identifiers (specific test cases)**
- GET `.../businesses/BC/BC0664974/filings/transition`
- GET `.../businesses/BC/0702216/filings/dissolution/voluntary`. This is the only nested filing subtype.

## Variations
- **Jurisdiction or entity segment:** `BC` or `BEN`.
- **Identifier format:** `BC{{newCorpNum}}`, bare `{{newCorpNum}}`, or a literal number.
- **Method:** GET, except the two POSTs, which carry test scripts.

Caution:
- The incorporationApplication POST snippet is malformed, with an incomplete object and a truncated test script.
- The transition POST is also incomplete. Its test assertions and any request body are missing.
- `{{url}}`, `{{newCorpNum}}` and `{{newCorpNumForCorAll}}` must be set in the Postman environment, or the requests and tests fail.
- The `Content-Type: application/json` header is disabled on most GETs, so it will not be sent. This could matter if the server validates headers strictly.
- The response schemas are unknown, because the response arrays are empty or not shown.
- The `BC0664974` and `0702216` requests hardcode specific businesses. They are test cases, not reusable templates.
- The identifier format is inconsistent: some URLs use `BC{{newCorpNum}}` and others use `{{newCorpNum}}`. Check which one an endpoint expects.

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
