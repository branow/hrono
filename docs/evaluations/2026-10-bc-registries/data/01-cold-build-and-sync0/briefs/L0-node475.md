<!-- leaf 475, 27 members -->

This group is a set of condensed summaries of Apache 2.0-licensed (mostly Province of British Columbia) pytest suites and helpers. They come from the BC Registries `entity-filer` and `legal_api` codebase, and nearly all of them test filing processors.

## Groupings

**1. CRA / Business Number (BN) tests**
- `test_admin_bn15` covers INFORM_CRA and GET_BN with valid, empty and None business numbers.
- `test_admin_resubmit` covers the CHANGE_* request types. It resets `retry_number` from -1 to 0.
- `test_correction` (SP/GP) expects 4 `RequestTracker` records: CHANGE_NAME, CHANGE_PARTY, CHANGE_DELIVERY_ADDRESS and CHANGE_MAILING_ADDRESS.
- `test_bn15_not_available_correction` expects the same 4 trackers, left unprocessed.
- `test_registration` and `test_retry_registration` (SP/GP) cover registration with retries on `BNException`.
- All of these mock `request_bn_hub` or `_get_program_account` and build `tax_id` the same way.

**2. Component-processor unit tests (small, synchronous)**
- `test_set_corp_type` (3 cases).
- `_update_business_profile` (4 HTTP-status cases).
- `update_filing_court_order`.
- Office tests: `update_offices()` creates 2 offices and recreates them when the postal code changes.
- Party tests: `update_parties`, with `PARTIES_STRUCTURE` and `SECOND_PARTY`.
- Share-structure tests: resolution dates, share classes, and deleting 5 classes × 5 series.
- A module header for the filing component processors.

**3. Filing-type worker tests (`process_filing`)**
- AGM location change.
- Alteration (legal type, legal name, court order, coop association type).
- Special resolution (CP):
  - The processor test only checks that `special_resolution.process()` creates a `Resolution`.
  - The worker test covers `name_change` and `no_change`.
- Restoration (4 restoration types; registrar or court-order approval).
- Technical correction overlay on an annual report.

**4. Business-creation filings**
- Conversion:
  - Corporate: with and without a name request (NR), plus coop and BC company variants (BC/ULC/CC).
  - Firms: the GP/SP conversion and the proprietor new-address test.
- Incorporation:
  - Covers BC/BEN/CP/ULC/CC, with and without NR.
  - `test_get_next_corp_num` mocks the COLIN API.
- Registration (SP/GP): `registration.process()` and the affiliation call.
- Regular amalgamation application:
  - Two amalgamating entities.
  - Dissolved entities become HISTORICAL.
  - Foreign entities have their jurisdiction fields populated.

**5. Change and correction filings**
- Change of registration (GP/SP): legal name, business address and court order.
- Correction:
  - `BC_CORRECTION` fixture.
  - Name and start date, and business address.
  - Conversion correction ends in PENDING_CORRECTION.
  - CP special-resolution correction, including a nested correction of a correction.

**6. Test utilities**
- `upload_file` posts a PDF to a Minio signed URL.
- `_create_pdf_file` builds a 3-page PDF.
- `assert_pdf_contains_text` checks the text of a PDF.
- `has_expected_date_str_format` checks a date string against a format.

## Recurring patterns
- Most worker tests are parametrized by GP/SP, and sometimes by name change versus no change.
- They use deep-copied templates and a random `payment_id` from `SystemRandom().getrandbits(0x58)`.
- They mock the same external services: email, event publishing, NR consumption, business profile update and `AccountService`.

Caution:
- **tax_id format:** it is exactly `{business_number or new_bn}{business_program_id}{str(program_account_ref_no).zfill(4)}`, so a ref no of '1' becomes '0001'. Parsing that assumes a variable length breaks. In the correction tests, '993775204' (9 chars) is still treated as invalid.
- **Correction test ordering:** both correction tests expect exactly 4 tracked requests in the same order.
- **Mislabelled test case:** the third `test_set_corp_type` case is named "valid None -> BC" but actually tests C→None→C.
- **Heavy mocking:**
  - The `_update_business_profile` test mocks several endpoints, so it can pass while the real API contract has changed.
  - The alteration, correction, conversion and coop-correction tests mock many external services. They bypass side effects and don't verify that the mocks are called.
  - The special-resolution test's `consume_nr` mock returns None.
- **Stripped fields:** the office test must strip the auto-generated `id` and `addressType` fields before comparing.
- **Party tests:** parametrize fixture names are unused and the `id` differs between parties (0 vs 1). The assertion checks `filing.filing_party_roles` separately, not via `check_business`.
- **Share-structure test:** the `test_name` parameter is never used.
- **Special-resolution processor test:** only one case runs, and it is hardcoded to CP with identifier `CP1234567`.
- **AGM test:** the filing JSON is deeply nested (filing → filing → agmLocationChange), and the original is not mutated because of the deep copy.
- **Alteration tests:** `payment_id` comes from random bits and fixtures are deep-copied for isolation.
- **Conversion (corporate):**
  - `legal_name` is auto-generated as `identifier[2:] + suffix` when there is no NR.
  - Exact collection counts are asserted, so a change to `create_business` breaks the test.
- **Conversion (firms):**
  - The party role counts differ. `filing_party_roles` is always 1, while `business.party_roles` is 1 for SP and 2 for GP.
  - `SP_CONVERSION` deletes `parties[1]` only as test setup, not as a requirement.
- **Incorporation:** CP has different assertions from the other types (1 office instead of 2, no shareStructure). CC still includes `courtOrder`, although it is normally removed for CP.
- **Registration (SP/GP):**
  - Delete index [1] from the SP fixture to match the expected role counts.
  - The `pass_code` format differs by party type.
  - `corp_type_code='RTMP'` for `update_entity` matters to the auth API.
- **Amalgamation test:** it deletes the first item of `amalgamatingBusinesses` and replaces the list manually. That may not match the real filing structure.
- **Change of registration:**
  - The parametrize column order is confusing, because the first position mixes test names with entity names.
  - `nameRequest` is deleted mid-test to make the payload conditional.
  - All tests mock the same 5 services.
- **Correction fixtures:**
  - `correctedFilingId: 2` refers to the filing being corrected, not the correction itself.
  - `nameTranslations[0]` has `id: '1'` (existing, modified) and `[1]` has no id (new).
- **Correction timestamps:** `start_date` is hardcoded to `2022-01-01T08:00:00+00:00`, and the test expects an exact match including the timezone.
- **Coop special-resolution correction:** signatory names are auto-uppercased, and the `meta_data` keys `fromCooperativeAssociationType` and `toCooperativeAssociationType` are hardcoded.
- **Restoration timestamps:** the limitedRestoration expiry is stored with a hardcoded `T07:00:00+00:00` offset. Registrar dates use T08:00 and notice dates use T07:00, so the offsets differ.
- **Technical correction test:** it sets `skip_status_listener=True` and mutates `_status` directly, which is an internal field rather than the public API. Whether `tech_correction_json` assignment merges or replaces isn't documented.
- **PDF helpers:**
  - `assert_pdf_contains_text` checks only page 0.
  - `PyPDF2.PdfFileReader` is deprecated (use `PdfReader`).
  - `_create_pdf_file` repeats the same text 3 times per page.

## Members

- lear: queue_services/entity-bn/tests/unit/bn_processors/test_admin.py
- lear: queue_services/entity-bn/tests/unit/bn_processors/test_correction.py
- lear: queue_services/entity-bn/tests/unit/bn_processors/test_registration.py
- lear: queue_services/entity-filer/tests/unit/filing_processors/filing_components/__init__.py
- lear: queue_services/entity-filer/tests/unit/filing_processors/filing_components/test_business_info.py
- lear: queue_services/entity-filer/tests/unit/filing_processors/filing_components/test_business_profile.py
- lear: queue_services/entity-filer/tests/unit/filing_processors/filing_components/test_filing.py
- lear: queue_services/entity-filer/tests/unit/filing_processors/filing_components/test_offices.py
- lear: queue_services/entity-filer/tests/unit/filing_processors/filing_components/test_parties.py
- lear: queue_services/entity-filer/tests/unit/filing_processors/filing_components/test_shares.py
- lear: queue_services/entity-filer/tests/unit/filing_processors/test_agm_location_change.py
- lear: queue_services/entity-filer/tests/unit/filing_processors/test_alteration.py
- lear: queue_services/entity-filer/tests/unit/filing_processors/test_conversion.py
- lear: queue_services/entity-filer/tests/unit/filing_processors/test_incorporation_filing.py
- lear: queue_services/entity-filer/tests/unit/filing_processors/test_registration.py
- lear: queue_services/entity-filer/tests/unit/filing_processors/test_special_resolution.py
- lear: queue_services/entity-filer/tests/unit/test_worker/test_amalgamation_application.py
- lear: queue_services/entity-filer/tests/unit/test_worker/test_change_of_registration.py
- lear: queue_services/entity-filer/tests/unit/test_worker/test_conversion.py
- lear: queue_services/entity-filer/tests/unit/test_worker/test_correction_bcia.py
- lear: queue_services/entity-filer/tests/unit/test_worker/test_correction_conversion.py
- lear: queue_services/entity-filer/tests/unit/test_worker/test_correction_firms.py
- lear: queue_services/entity-filer/tests/unit/test_worker/test_correction_special_resolution.py
- lear: queue_services/entity-filer/tests/unit/test_worker/test_restoration.py
- lear: queue_services/entity-filer/tests/unit/test_worker/test_special_resolution.py
- lear: queue_services/entity-filer/tests/unit/test_worker/test_technical_correction.py
- lear: queue_services/entity-filer/tests/utils.py
