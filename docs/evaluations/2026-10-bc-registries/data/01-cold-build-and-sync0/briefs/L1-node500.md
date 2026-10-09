<!-- level 1, node 500, children [9, 11, 12, 13, 16, 17, 18, 22, 24, 27, 28, 29, 30, 31, 32, 33, 34, 37, 44, 49, 50, 51, 57, 69, 70, 78, 79, 287, 293, 562, 563, 564, 573, 574] -->

# Parent brief: BC registry fixtures, exports and API types

## What this is
The children are fragments (mostly truncated, many near-duplicates) of one test and fixture ecosystem for the BC Registries / LEAR Legal API. The material falls into four kinds:
- Corporate filing JSON payloads and registry extracts.
- Postman test scripts and request bodies.
- Byte-encoded CSV/ZIP database exports and import configs.
- TypeScript and OpenAPI type definitions.

A few unrelated street and place-name lists (Czech, German, Polish, Slovak, Georgian) are also present. Most data is test fixtures with placeholder values. Some real-looking personal data appears.

## Routing by content

### 1. Officer and director records (the largest group)
All use one schema: `appointmentDate`, `cessationDate`, `startEventId`/`endEventId`, `title`, `actions`, `officer` (firstName, lastName, middleInitial), `deliveryAddress` and `mailingAddress`. Each address has addressId, street, city, region, country, postalCode, deliveryInstructions and streetAddressAdditional.

**By business:**
- **LAKES ARTISAN COOPERATIVE (CP0002098, Burns Lake, founded 2010-10-15).**
  - Officers: CANDICE M LITTLE, BEATE MARQUARDT, LORNA HANNETT, PAULA LAURIE, KELLY TURFORD, and test officers TESTER TESTING, TESTER2, TESTER3 and TESTER4.
  - Shared startEventIds: 103219412, 103251080, 102095955 and 101990302.
  - addressIds run 102555536–102555540 and 1035048xx.
  - Candice M Little and Beate Marquardt were ceased in 2019 (endEventId 102095981).
- **CENTRAL INTERIOR COMMUNITY SERVICES CO-OP (CP0001965, Williams Lake, founded 2004-04-28).**
  - Officers: NANCY GALE, AL GIDDENS, JANICE BRECK, CHAD MATTHIES, ANGELA AMMAN, LINDA BERG, KIRSTEN STARK, DEANA CONDE GARZA, IRENE WILLSIE, EDWARD KOZUKI and ROBERT IAN MCLAUGHLIN.
  - Shared startEventIds: 103219287 and 101990169.
  - addressIds run 102554860–102554870 and 1033392xx.
- **Manhattan Co-operative Housing Association (CP0001164, Vancouver, Thurlow Street).**
  - Officers: LAUREN ELDRIDGE, JAMES MAXWELL, PHIL MONDOR, GARNET MCPHEE, SIMON KAULBACK, DIANA JEFFRIES, DAVID PLEWES and the "CUSTOM1/CUSTOM2" template officers.
  - startEventId 103218513; addressIds 102550761–102550768.
- **Other co-ops (single records):** CP0002108 (First Avenue Athletes Village Housing Co-operative) and CP0001248 (Oak Bay Housing Cooperative).
- **Generic 2024 API-spec samples.** These use fake people (Jane, Bob and Doe Smith, API Specs, Joe Swanson, BCREGTEST names, LEKSHMI GOKUL and MALLIKA), with `appointed`, `ceased`, `addressChanged` and `nameChanged` actions. The `prev*` name fields are populated only for `nameChanged`.

### 2. Filing payload shapes and fixtures
- **Co-op filings:**
  - Annual report: header, business, offices and directors.
  - Change of address: TEST STREET 1 / PO BOX 7357 / T3S 7E4, addressIds 102604820 and 102604821, event 103251079.
  - Change of directors: events 103251078–103251082, Postman bodies certified by "Tester Testing" (tester@testing.com).
  - Historical paper-only filings for CP0002098 (events 1019903xx and 1020247xx–102024809).
- **BC/BEN company filings.** These are Postman requests with `{{newCorpNum}}`-style variables:
  - Incorporation application (parties Joe P. Swanson, Xyz Inc., Test Director; share class with 2 series; NR1234567).
  - Alteration, transition, correction (correctedFilingId 4; diffs on nameRequest, parties and offices) and amalgamation (horizontal and vertical short form).
  - Amalgamating businesses BC0883189 and BC0883230.
  - Continuation-in and SP registration specs.
- **Dissolution.**
  - BC0702216 / 0702216 ("0870868 B.C. LTD." and M & D NEALIS CONTRACTING LTD.), voluntary, custodian Jane/john doe at 1012 Douglas St, Victoria. Events 9178264 and 9178266.
  - A 2024 spec version: custodial office at 200-940 Blanshard St.
- **Address and office samples.**
  - Victoria (Blanshard, Helen Rd), Richmond (TEST D/M), Surrey, Montréal (wrongly region BC) and Pickering ON.
  - Delivery ID is mailing ID + 1.
  - OpenAPI schemas: Address (streetAddress ≤50, addressCity ≤40, postalCode ≤15, addressRegion ≤2, deliveryInstructions ≤80), Office and Region.

### 3. Postman test scripts
- They are JavaScript assertions with the same skeleton: response time, status, Content-Type and `filing.*` existence checks. After that they use hardcoded fixture values.
- Fixtures: CP0002098, CP0001965, '0702216', and the addresses "TEST CITY"/"TEST STREET 1", T3S 7E4 and V8P1A1.
- Filing types: AR, COA, COD, transition and voluntary dissolution.
- Status codes are 200 or 201. 201 variants set `arEventId`, `coaEventId`, `codEventId` and similar environment variables.

### 4. Database export (byte-encoded ZIP/CSV)
- **Format:** decimal-ASCII byte dumps of a ZIP, truncated. The tables are `businesses`, `filings`, `offices`, `addresses`, `parties`, `party_roles`, `share_classes`, `share_series`, `aliases` and `transaction`, each with a `_version` history table plus `parties-addresses` link tables. They carry `transaction_id`, `end_transaction_id` and `operation_type`.
- **Sample entity:** 1218890 B.C. LTD. (BC1218890), business_id 3722, transaction 13774, with Montréal and Pickering addresses.
- **Data-reset-tool import config:** a JSON array of `{key, type: "file", src}` entries for BC1219957, BC1218877, BC1218875 and CP0001405. Block 1 holds core files. Block 2 holds history, share and alias files, some `disabled` with `src: []`. Every `src` is under `/Users/kjinnah/...`.

### 5. TypeScript and front-end types
- **Filing and API types:** the `bcgov/business-schemas`-based filing interfaces (amalgamation, dissolution, restoration, correction, FilingData, ApiFilingIF, ApiBusinessIF, TaskTodoIF, TodoItemIF, NameRequestIF, RootStateIF, AgmExtEvalIF), the index barrel and small utility interfaces.
- **Data models:** AddressIF, OfficerIF, DirectorIF, PartyIF, RoleIF and the Empty* constants.
- **Configuration:** the VUE_APP_* configuration interface.
- **Validators:** Vuelidate address rules and date validators.
- **UI types:** TableHeaderIF, FormIF, AlertMessageIF, PaymentErrorIF, StepsIF, the Keycloak user interface and PdfInfoIF.

### 6. Unrelated place-name lists
Plain data arrays: Prague/Czech streets, German streets, Polish towns, Bratislava streets and Georgian country names. They have no logic and many duplicates.

## Cross-cutting cautions
- **Truncation:** nearly every fragment is cut off mid-record, so counts, field lists and full headers are unreliable. Verify against the source.
- **Empty strings versus null:** postalCode, title, endEventId, middleInitial, deliveryInstructions and streetAddressAdditional are `""`. Active officers have `cessationDate: null`. Test for falsy values, not null.
- **Shared and duplicated IDs:**
  - Delivery and mailing addresses are often identical and share one addressId.
  - Several officers share one startEventId (a batch event or a data error).
  - addressId reuse is inconsistent across summaries (102555540, 102550768).
  - Event 102024804 is listed as both an annual report and a change of directors.
  - Check IDs before joining on them.
- **Unrendered placeholders:** `{{today}}`, `{{cessationDate}}`, `{{appointmentDate}}`, `{{newCorpNum}}` and similar must be substituted before submission. `learEffectiveDate` may be a typo for `legalEffectiveDate`. The dissolution header has isFutureEffective true even though its dates are in 2021.
- **Typos and format inconsistencies:**
  - "VACOUVER" instead of Vancouver.
  - "WILLIAM LAKE" versus "WILLIAMS LAKE".
  - Lowercase postal code "t3s 7e4".
  - Montréal addresses with region BC.
  - Alberta-style T3S paired with BC.
  - Inconsistent country values: "CANADA", "Canada" and "CA".
  - "registration-sucess-response".
  - `IncorporationAddressIf`.
- **Conflicting summaries:** officer names, dates and IDs differ between summaries of the same business, for example Kelly Turford, Officer 1 and 2 at CP0001965, and lastAgmDate for CP0002098.
- **Test data and PII:** values like TEST CITY, tester@testing.com, H0H0H0 and no_one@never.get are fixtures. Real-looking names, addresses and emails (the dissolution custodian, Burns Lake and Williams Lake residents) should be scrubbed before reuse in examples.
- **Hardcoded fixtures:** the tests and the data-reset config embed specific IDs, dates and a local user path, so they break for other data or machines.
- **Binary handling:** the ZIP dumps must be decoded as bytes (UTF-8 multibyte for accents, then decompressed). Never edit them as text.
- **TypeScript:**
  - Do not assign the Empty* constants directly. Copy them first.
  - `$refs` and `data` are typed `any`.
  - `NameRequestIF.applicants` is likely wrongly a single object.
  - Entity-specific fields return undefined for the wrong entity type.
- **Place-name lists:** duplicates may be intentional. Decode as UTF-8, use diacritic-insensitive matching, and don't rely on `.toLowerCase()` for Georgian.
