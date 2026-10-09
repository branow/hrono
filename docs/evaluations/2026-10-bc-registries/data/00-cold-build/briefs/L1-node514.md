<!-- level 1, node 514, children [15, 45, 46, 83, 88, 185, 253, 258, 260, 294, 306, 337, 382, 389, 396, 397, 403, 423, 449, 455] -->

# Parent Brief: BC Registries Business-Filing System — Fixtures, API Specs, and Service Code

**Overview:** These child briefs describe the BC (British Columbia) business-registry ecosystem (LEAR "legal API", entity-filer/bn, pay, auth). They cover test fixtures, OpenAPI spec fragments, configs, notebooks and Python worker code. Nearly everything is test or sample data and is heavily truncated. Typical placeholders are `no_one@never.get`, "mocked submitter", paymentToken 12345, `abc.def@gov.bc.ca` and `test@gmail.com`.

## 1. Fixture and sample data
- **Incorporation payload (byte-array encoded):** "1218890 B.C. LTD." (BC1218890, BEN, founded 2020-10-23), with a correction filing dated 2020-10-29 (correctedFilingId 11086).
  - It has Montréal and Pickering (ON) address blocks, parties and roles (TESTER), and a share class.
  - It must be decoded as UTF-8, because multi-byte sequences like 195,137 and 195,169 split É and é across codes.
  - Inconsistencies: postal code L9W vs L1W, the "Pickerirng" typo, and region BC for a Montréal address.
- **BN Hub / CRA failure records (`BN_HUB`, Jan 2023):**
  - CHANGE_* actions fail with "Cannot inform CRA… before receiving Business Number (BN15)", with `retry_cnt=0`.
  - INFORM_CRA fails with `[ISC.0082.9465]` on `lastName` length, usually with retry/status 9. This looks systemic.
  - Example file IDs: FM0362085, FM1006814.
- **Ledger and invoices:**
  - The CP0000840 filing ledger (IDs 112744–112763) is all COMPLETED. It includes alterations, annual reports, a CORRECTED annual report and filingId collisions (112751).
  - Amalgamation records are for BC1234567.
  - Invoices cover BCINC 350, OTADD/OTCDR 20, serviceFees 1.5 and DRAWDOWN. The two INTERNAL OTFDR filings are fully waived.
  - The statements response has total 1319 with an empty `items` array.
- **Business entity snapshots:** BC0870884 (HISTORICAL), BC1230038, BC0870737 and BC0870731, and BC0883028, BC0882365, BC0883312 and BC0882848. The reversed `arMinDate`/`arMaxDate` values and empty-string dates are suspect. The compliance PIA/STRA records are stale (2019–2020).

## 2. API / OpenAPI spec fragments (BC Business Registry v2.0, legal API)
- **Overview and auth:** Servers run at `/business/api/v2`. Every request needs both an API key and an Account ID.
- **Filing envelope:** The Filing oneOf/anyOf covers about 24 filing types. Query params are `draft`, `only_validate` and `accountId`.
- **Filing-type schemas:** incorporation, registration, conversion, transition, amalgamation (regular, vertical, horizontal), continuationIn, alteration, change of address/directors/registration, special resolution, dissolution, restoration, AGM extension/location change and consentContinuationOut.
- **Shared schemas:** party/partyRole, officer, name_request, address, share structure (class and series), court order, business, NAICS, payment references and the compliance warnings.
- **Fee API:** `serviceFees` is included inconsistently, and `priority` and `futureEffective` each add 100 to the total.
- **Example responses:**
  - Success responses stay PENDING with `isPaymentActionRequired=true`.
  - Validation errors come back as HTTP 500 with a template-like `rootCause` string. This is a misuse of error codes, and the string needs manual parsing.
  - 401 responses use the same wrapper.
- **Common spec problems:**
  - Many schemas are truncated or have empty examples.
  - Date formats are inconsistent.
  - Fields are marked "***Item not used***".
  - The identifier regex has an unparenthesized `|`.
  - Typos are present ("idetifier", "disslution").
  - Placeholder strings are used for values.
  - Field names conflict with their descriptions.

## 3. Config and code
- **Front-end entity configs (TypeScript):**
  - There are 11 entity configs: BC, BEN, ULC, CC, CP, GP, SP and four continuation-in variants. The continuation-in variants are spreads that override only `entityType`.
  - Flows carry fee codes and certify text. Director minimums are 1 (3 for CC and CP).
  - A LaunchDarkly client supplies 18 default flags.
  - Configs are untyped, and `certifyText` is duplicated heavily.
- **Vault-to-app mappings:**
  - Entity vaults hold `postgres-legal`, the NATS apps, `sentry` and `launchdarkly`.
  - Relationship/auth vaults hold `postgres-auth` and `jwt`.
  - Pay vaults hold `paybc`, `cfs` and `gcp-queue`.
  - Three entries are empty.
- **Python legal-api rules:**
  - Fee code and filing metadata are keyed by filing and entity type. NOFEE covers staff and admin filings.
  - Allowable-filing rules cover ACTIVE and HISTORICAL states.
  - The blocker engine has six blocker checks.
  - Digital-credential eligibility and auth-API product caching (600 s) are also covered.
  - Allowable-filing and fee-code rules are duplicated across the amalgamation subtypes.
- **Entity-filer and entity-bn services:**
  - Filing processors cover each filing type, `filing_components` helpers and unit tests.
  - BN processors cover change of registration, correction, dissolution/putBackOn and async registration. They send XML to CRA via `request_bn_hub()` and expect an `SBNAcknowledgement`.
  - Digital credential worker handlers (admin revoke, BN, changeOfRegistration, dissolution, putBackOn) are driven by `cb_subscription_handler` on NATS.
  - Silent error suppression (`suppress`, bare `except`) is widespread.
  - Known bugs: `update_filing_court_order` checks `if not Filing`, and the amalgamation `next()` has no default.
  - The hypothesis converter tests use the wrong variable name.
  - Resubmission is blocked when `is_processed` is set, and only `issued_credentials[0]` is handled.
- **LEAR Jupyter notebooks:**
  - An alteration-filing workflow.
  - Direct-DB correction notebooks (correction and annual-report variants). These exist because production doesn't support historical corrections.
  - A dev-environment setup cell. It contains `docker.for.mac.localhost` and an empty `DATABASE_PASSWORD`, so check for committed secrets.

## Cross-cutting cautions
- Treat all data as fixtures or placeholders, not production data.
- Almost everything is truncated, so full structures can't be reconstructed or validated.
- Dates and timezones are inconsistent (ISO with offset, date-only, RFC-style, `FixedOffsetTimezone` objects). Parse them explicitly.
- Identifier confusion: business identifiers (BC…), filingIds, FM file IDs, NR numbers and the reused filingId 112751.
- Booleans and values like 0, null, empty strings and `paymentStatusCode=null` carry ambiguous meaning. Check semantics before using them in logic.
- Paired fields (`hasMaximumShares` with `maxNumberOfShares`, and `hasParValue` with `parValue`) must be set consistently.
- Failures often surface through different paths: explicit BN15 messages, status 9 with a null response, or generic "API backend third party service error." wrappers.
