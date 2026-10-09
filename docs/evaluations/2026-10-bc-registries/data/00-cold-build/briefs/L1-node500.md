<!-- level 1, node 500, children [9, 11, 12, 13, 16, 17, 18, 22, 24, 27, 28, 29, 30, 31, 32, 33, 34, 37, 44, 49, 50, 51, 57, 60, 69, 70, 78, 79, 244, 287, 288, 293, 387, 429, 467] -->

# Parent brief: BC Registries / LEAR test and fixture data

**What this is.** The children are fragments of one ecosystem, the BC (Canada) corporate registry (LEAR, the Legal API, and the BC Registries UI and email services). Most are truncated JSON payloads, Postman test scripts, CSV export dumps, or code fixtures. Many are near-duplicates. Nearly all of it is test or archival data, not production.

## Routing by content type

**1. Officer/director appointment records (the bulk).**
- Shared shape: `appointmentDate`, `cessationDate` (null means active), `startEventId`, `endEventId`, `title`, `actions`, `officer` (first name, last name, middle initial), and `deliveryAddress` and `mailingAddress`. The addresses carry `addressId`, city, region, country, postal code, street, additional street and delivery instructions.
- Recurring datasets:
  - **Lakes Artisan Cooperative (CP0002098, Burns Lake).**
    - Officers: Candice M Little, Beate Marquardt, Lorna Hannett, Paula Laurie, Kelly Turford, and test officers Tester Testing, Tester2 and Tester3.
    - Key IDs: startEventId 103219412 and 103251080/82, and addressIds 1025555xx and 1035048xx.
  - **Central Interior Community Services Co-op (CP0001965, Williams Lake).**
    - Officers: Nancy Gale, Al Giddens, Janice Breck, Chad Matthies, Angela Amman, Kirsten Stark, Linda Berg, Deana Conde Garza, Edward Kozuki, Irene Willsie and Robert Ian McLaughlin.
    - Key IDs: startEventId 103219287 and 101990169.
  - **Vancouver Thurlow Street officers (Manhattan Co-op CP0001164).**
    - Officers: Lauren Eldridge, James Maxwell, Phil Mondor, Garnet McPhee, Diana Jeffries and others.
    - Key IDs: startEventId 103218513 and addressIds 1025507xx.
  - **2024 API-spec samples.** Officer actions appointed, ceased, addressChanged and nameChanged (Doe Smith, Jane Smith, Bob Smith → API Specs), a voluntary dissolution with custodial office 200-940 Blanshard St, and a director with officer id 584282.
- Typical gotchas:
  - Delivery and mailing addresses are often identical and share one `addressId`.
  - Many officers share a startEventId.
  - "VACOUVER" and "WILLIAM LAKE" are typos.
  - Several officers have conflicting names or dates across summaries.

**2. Filing payloads and fixtures.**
- Filing types: annual report, change of address, change of directors, incorporation (BEN), alteration, transition, correction, special resolution, dissolution (voluntary, custodian), amalgamation (horizontal and vertical), registration (SP), continuation-in and cooperative.
- Related fragments:
  - A Postman fixture set for CP0002098 and for BC{{newCorpNum}}.
  - Correction diffs against a filed incorporation application.
  - A dissolved entity, 0702216 "M & D Nealis Contracting Ltd." (BC0702216 "0870868 B.C. Ltd." in another fragment). Its custodian is Jane Doe or John Doe at 1012 Douglas St, Victoria.
  - Historical paper-only CP0002098 filings from 2010 to 2017, plus CP0002108 and CP0001248.
  - A Joe P. Swanson / Xyz Inc. / Test Director incorporation fixture, all dated 2018-01-01.
- Gotchas:
  - `{{today}}` and other `{{…}}` placeholders must be substituted.
  - `learEffectiveDate` is probably a typo for `legalEffectiveDate`.
  - The business ID in some headers is inconsistent.

**3. Postman test scripts.**
- They are hard-coded to fixtures, such as CP0002098, CP0001965, V8P1A1, T3S 7E4 and "CANADA".
- They mix `.to.eql` with `.to.exist`. Role filters that only use `.to.exist` pass on empty arrays.
- `verify_office` is undefined in the snippets.

**4. CSV/ZIP export dumps.**
- Decimal-byte-encoded ZIP chunks from the data-reset-tool export (`exports/*.csv`).
- Tables: businesses, filings, offices, addresses, parties, party_roles, share_classes, share_series, aliases and transaction, each with a `_version` history table.
- Business BC1218890 (id 3722) is the sample.
- Gotchas:
  - They must be decoded as bytes, with UTF-8 handled for É/é.
  - They are truncated.
  - Montréal addresses show region BC.
- A related import-config JSON points to local paths (user `kjinnah`) for BC1219957, BC1218877, BC1218875 and CP0001405.

**5. Code, schemas and tests.**
- **TypeScript interfaces** for the Vue business-filing UI: AddressIF, DirectorIF, PartyIF and ApiFilingIF.
- **OpenAPI schemas** for Address, Office and region, plus party and cooperative fixtures.
- **Warning mapping** `REFERER_WARNINGS_MAPPING`, and pytest tests that only accept BC and CA addresses for amalgamation and continuation-in filings.
- **Email service fixtures and tests**, with CloudEvents-style queue messages and `prep_*` filing builders.
- **SQL migration** adding `annualReportFilingYear`.
- **Alembic migration** for terms of use.

**6. Legal text.** The Subscriber agreements for BC Registries Business and Cooperatives (Team Member vs. User), a Director Search Tool agreement, and the PAD migration. Fee and dispute terms are $30 late fee, 90-day dispute window, and 60 days' termination notice.

**7. Reference lists.** Raw street and place name lists in Czech, Slovak, German, Georgian and Polish. They contain many duplicates and are truncated, so they need UTF-8 and locale-aware handling.

## Cross-cutting cautions
- **Truncation:** nearly every fragment is cut off mid-record, so counts and fields are incomplete.
- **Empty strings vs null:** postalCode, title, endEventId, middleInitial, deliveryInstructions and streetAddressAdditional are empty strings, not null. Active records have a null `cessationDate` and an empty `endEventId`.
- **Test data:** the fixtures use placeholders such as TEST CITY, Tester Testing, tester@testing.com, H0H0H0, V8P1A1 and no_one@never.get. Do not use them as real values. The Jane/John Doe custodian data may look like real personal data, so redact it.
- **ID reuse:**
  - startEventId is shared across batches of officers.
  - addressId is sometimes shared by delivery and mailing, and sometimes reused across officers or conflicting across summaries.
  - Check uniqueness before joining on either.
- **Summaries conflict** on officer names, dates and IDs across duplicates, so check the source JSON before relying on any value.
