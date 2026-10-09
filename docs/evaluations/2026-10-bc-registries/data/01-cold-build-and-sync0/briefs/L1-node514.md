<!-- level 1, node 514, children [15, 45, 46, 60, 83, 88, 185, 253, 258, 260, 294, 306, 337, 389, 396, 397, 403, 423, 429, 455, 591, 592, 593, 617, 618, 619] -->

# Parent brief: BC Registries / Business Registry corpus (fixtures, API specs, filer code)

This group condenses material from the BC Registries (Province of British Columbia) legal-entity ecosystem. Nearly all of it is truncated, test or fixture data, or spec fragments. Nothing is a complete, validated artifact.

## 1. Fixture and sample data (test records, not real)

- **Encoded incorporation payload**
  - It is a byte-array (decimal ASCII/UTF-8) payload for "1218890 B.C. LTD." (BC1218890, BEN, founded 2020-10-23).
  - A correction filing dated 2020-10-29 points to `correctedFilingId` 11086.
  - Address blocks: Montréal (4-1900 Av De l'Église, H4E 1G8, region BC) and Pickering (4-860 Brock Rd, L1W 3X3; one fragment has the typos "L9W" and "Pickerirng").
  - Other contents: roles (Completing Party, Incorporator, Director, Accountant), contact test@gmail.com, and share class "sets Shares" (CAD, max 2500).
  - Multi-byte UTF-8 sequences (195,137 and 195,169) are split across codes, so decode bytes, not codes.
- **BN hub / CRA records (BN_HUB, Jan 2023)**
  - CHANGE_* actions fail with "Cannot inform CRA… before receiving Business Number (BN15)", with `retry_cnt` 0, so there is no auto-retry.
  - INFORM_CRA fails with `[ISC.0082.9465]`, `lastName` over the maximum length. This hits many unrelated businesses, so it is systemic.
  - Example file IDs: FM0362085, FM1006814 and others.
- **Filing ledger for CP0000840** (and BC1234567 / FM0000840)
  - COMPLETED filings with IDs 112744–112763.
  - Alterations, incorporation, annual report, directors, address, resolutions, orders, dissolution, transition, continuation-out and amalgamation variants.
  - Filing ID 112751 is reused across several records. 112763 is the only future-effective one.
- **Payment and invoice records**
  - Fee schema: BCINC 350, OTADD/OTCDR 20, OTANN 30, service fee 1.5, +100 each for priority and future effective.
  - Duplicate invoices (ids 3191/3190, 3809/3602). Waived INTERNAL OTFDR filings. One empty statements page (total 1319).
- **Business entity snapshots**
  - BEN companies BC0870884 (HISTORICAL), BC1230038, BC0870737 and BC0870731.
  - Registrar T.K. SPARKS. COGS, cstat, lseal and summary report samples.
  - `arMinDate` is later than `arMaxDate` in several.
  - A PIA/STRA compliance tracker is stale (2019–2020).
- **Filing payload samples**
  - KD TEST BAKING (BC0880343), JIA TEST BC TO ULC (BC0871442), 882365 B.C. LTD. (BC0882365), 0883028 B.C. LTD. (BC0883028), 0883312 (BC0883312) and 0882848 (BC0882848, consentContinuationOut).
  - CP1234567 annual report, change-of-address and change-of-directors fixtures (Peter Griffin, Joe Swanson).
  - NR 0119436 and NR 0119514 name requests.
  - Placeholder data: 5-4761 Bay Street, abc.def@gov.bc.ca, no_one@never.get, "mocked submitter".
- **Vault-to-application mappings**
  - `entity`, `relationship`, `pay`, `shared`, `keycloak`, `gcp-queue`, `minio`, `nats` and others, mapped one-to-one to apps.
  - Three entries are empty.
- **Notebooks (LEAR `legal_api`)**
  - An alteration-via-API notebook.
  - Three direct-DB correction notebooks for CP0001790 (correction filing, annual report, and one more variant).
  - A dev environment setup cell with 16 env vars, DB creds (kial/thor) and the `docker.for.mac.localhost` host.

## 2. API specs and schemas (OpenAPI, mostly truncated)

- **Business filings API v2.0**
  - Tenets: API key plus Account ID on every request. Servers sandbox, dev, test and prod at `/business/api/v2`. License BSD-3-Clause.
  - Filing envelope: a `Filing` with `header`, `business` and `filing`, over about 24 types.
  - Query params: `draft`, `only_validate` and `accountId`.
  - `POST /businesses` handles incorporation, amalgamation (regular, vertical, horizontal), continuation in and registration. Its 201 body is undefined.
  - Success and error examples are for AGM extension, AGM location change, alteration, annual report, change of address and directors, consent continuation out, and voluntary dissolution.
  - Errors use "API backend third party service error." with an unstructured `rootCause`. Validation failures are returned as HTTP 500 or 422, and 401 is used for authorization.
  - Statuses are DRAFT/PENDING with `isPaymentActionRequired`.
- **Shared schemas**
  - Share class and series, Party, PartyRole, Officer, Court_order, Name_request, Name_translations, Contact_point, Comment, Ledger_item, Business (47 legal types, NAICS, `alternateNames`), Foreign_jurisdiction, and registrar/report metadata.
  - Items marked "***Item not used***" include Correction, Diff and Unmanaged.
- **Payment references:** `paymentMethod` enum (ONLINE_BANKING, CC, DIRECT_PAY, DRAWDOWN, INTERNAL), routing slip, folio and DAT numbers.
- **FAS→CFS endpoint mapping:** `/parties`, `/accs`, `/sites`, `/rcpts`, `/invs`, `/rcpts/adjs` and `/rcpts/reverse`. Two of these are marked uncertain.
- **Legal terms**
  - BC Registries Subscriber agreements (business and cooperatives versions).
  - Director Search Tool terms.
  - An Alembic migration setting `termsofuse` version '3' and `termsofuse_pad` 'p1'.
  - The Province can change terms without notice and carves out broad liability. Fees, disputes and termination terms are in the agreements.

## 3. Code (Apache 2.0, Province of BC)

- **Front-end config (TypeScript)**
  - Entity configs: Bc, Ben, Ulc, Cc, Cp, Gp, Sp, and four continuation-in spreads.
  - `ConfigJson` is an array of 11 configs.
  - LaunchDarkly client with 18 default flags.
- **Filing metadata and rules**
  - Filing-type to fee-code lookups (e.g. BCINC, ALTER, AMALR/V/H, DIS_VOL, RESTF/L, NOFEE).
  - Allowable-filing rules by business state (ACTIVE, HISTORICAL) with `blockerChecks`.
  - Authorization engine: `is_allowed`, `get_allowable_actions`, `business_blocker_check`.
  - Digital-credential eligibility and account products.
- **Queue workers and filer**
  - Digital-credential handlers (revoke or replace on admin revoke, BN, change of registration, dissolution, put back on). They act only on `issued_credentials[0]`.
  - The NATS entry point `cb_subscription_handler`.
  - Entity-bn: `process`, CRA inform/get-BN phases, `BNException` and `BNRetryExceededException`.
  - Admin resubmit handling.
  - Filing processors: dissolution, put back on, restoration, continuation in/out, admin freeze, annual report, incorporation, registration, amalgamation, conversion, transition, court order, registrars notation/order, special resolution, change of name/address/directors/registration, correction, alteration, AGM extension and AGM location change.
  - Shared helpers: `correct_business_data`, offices, parties, shares, aliases, resolutions, rules and memorandum.
  - Tests: dissolution (19 parametrized cases), agm_extension (4 cases), change of name, alias, converter and FilingMeta tests.
- **SQL migration:** `annualReportFilingYear`, via `jsonb_insert`. COLIN filings take the year from `annualReportDate`, and LEAR filings from `last_ar_year`.

## Cross-cutting cautions

- **Truncated or incomplete sources:** Most fragments are cut off mid-value or mid-schema. Structure, required fields and examples can't be validated or reconstructed.
- **Test and placeholder data:** Names, emails and tokens (certifiedBy=test, TESTER, test@gmail.com, paymentToken 12345, no_one@never.get) are fixtures. Don't treat them as real or hardcode them.
- **Inconsistent dates and formats:** Date-only, ISO with offset, `Z`, GMT strings, microsecond timestamps and empty strings in place of nulls all appear. `arMinDate` is later than `arMaxDate` in several records. `affectedFilings` is sometimes a stringified array. Parse timezone objects (`FixedOffsetTimezone`) explicitly.
- **ID and identifier confusion:** Filing IDs repeat (112751). Business identifiers differ from filing IDs. Identifier regexes are not fully anchored. `legalType` BC is a jurisdiction code, not a legal type. `legalName` sometimes embeds the identifier.
- **Silent failures in code:** `suppress(...)` blocks, broad excepts and early returns hide errors. This includes the `if not Filing:` bug, the NameError in hypothesis tests, the reversed guard in the conversion corps path, and the `tax_id` length check that skips the BN request. `is_processed` blocks resubmission. `skip_build=true` prevents retry escalation.
- **Error-handling semantics:** `rootCause` is an unstructured string. A "success" response can still be PENDING with payment required. BN15 errors have no auto-retry, so resubmit manually. HTTP 500 is used for validation failures.
- **Duplication and drift:** `certifyText`, amalgamation rules and the legalTypes arrays are copy-pasted. Configs are untyped, and codes and entity-type maps must be kept in sync.
- **Legal and operational risk:** Terms can change without notice. The Province excludes broad liability. Arbitration is binding, in Victoria, for the Director Search Tool. The vault mappings are one-to-one, with ambiguous `vault` semantics.
- **Security and hygiene:** Check that no secrets (an empty `DATABASE_PASSWORD`, `<account>/<secret>` placeholders) are committed. Encoded payloads hide values until decoded. Decoded address details are PII-extractable (still test data).
