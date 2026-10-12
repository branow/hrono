# today

# Entity-filer filing processors and worker (legal-entity system)

This group documents the Python `entity-filer` queue service in `queue_services/entity-filer/src/entity_filer/`. It is a BC-registry-style legal-entity filing pipeline. `worker.py` dispatches each filing type to a processor module under `filing_processors/`. Each processor mutates a Business, Filing record and FilingMeta in place, and many of them raise `QueueException` on invalid input.

## Orchestration
- **`worker.py`** processes a filing submission inside a transaction.
  - It loops over `legal_filings`, where each dict has one key per filing type, and dispatches to the matching processor. The list of types includes alteration, annualReport, changeOf*, dissolution, incorporationApplication, registration, conversion, courtOrder, correction, transition, restoration, putBackOn, continuationOut, continuationIn, amalgamationApplication and others.
  - `specialResolution` is handled separately, after the main dispatch.
  - It sets `transaction_id` and marks the submission processed.
  - For new-business filing types (AMALGAMATIONAPPLICATION, CONTINUATIONIN, CONVERSION, INCORPORATIONAPPLICATION, REGISTRATION), it does the following:
    - It updates `business_id` in a second commit.
    - It calls update_affiliation, which is skipped for CONVERSION.
    - It calls consume_nr and update_business_profile.
    - It publishes MRAS.
  - For other types it calls `update_entity` and/or `consume_nr` and `update_business_profile`, depending on the type.
  - It then publishes email and events.
  - `annual_report` receives `flag_on` from the `enable-involuntary-dissolution` flag.

## New-business creation processors
These processors require `business` to be None, reserve or take a corporation number, create a Business with state ACTIVE, and then apply offices, parties, shares, aliases and court order.
- **`incorporation_filing.py`**
  - Uses the identifier from the filing when `colin_event_ids` is present. Otherwise it calls `business_info.get_next_corp_num()`.
  - Cooperative filings fetch rules and memorandum files from Minio, apply a certified registrar stamp, and add COOP_RULES and COOP_MEMORANDUM documents.
- **`continuation_in.py`**
  - Incorporates a foreign corporation in BC.
  - Creates a Jurisdiction.
  - Adds DIRECTOR_AFFIDAVIT and AUTHORIZATION_FILE documents.
- **`amalgamation_application.py`**
  - Creates an Amalgamation and the Business.
  - Marks amalgamating BC businesses HISTORICAL.
  - Stores foreign amalgamators by their foreign identifier, name and jurisdiction.
  - For horizontal or vertical types, copies name, directors, offices and shares from the holding or primary business.

## Existing-business state-change processors
- **`annual_report.py`**
  - Updates last_ar_date, last_ar_year and, conditionally, last_agm_date.
  - When flagged on and the business is in dissolution, it re-checks eligibility via `InvoluntaryDissolutionService`. If the business is eligible again, the batch processing status becomes WITHDRAWN.
- **`change_of_directors.py`**
  - Matches directors by name and works out appointed, ceased or modified.
  - Sets last_cod_date.
- **`continuation_out.py`**
  - Sets the business to HISTORICAL.
  - Records the foreign jurisdiction and legal name.
- **`dissolution.py`**
  - Sets the business to HISTORICAL.
  - Sets dissolution_date, which depends on the type and entity.
  - Handles parties, the custodial office and the court order.
  - For ADMINISTRATIVE type, deletes the amalgamation links.
  - Moves QUEUED BatchProcessing rows to COMPLETED when the flag is on.
  - For COOPs, `_update_cooperative` replaces the affidavit with a certified copy and adds an AFFIDAVIT document.
- **`restoration.py`**
  - Reactivates the business to ACTIVE.
  - Clears dissolution_date.
  - Sets or clears restoration_expiry_date.
  - Updates the name, aliases, offices and parties.
  - Ceases existing CUSTODIAN roles.
  - Records approval type and registrar dates.
- **`transition.py`**
  - Updates restriction_ind, offices, parties, shares and aliases.

## Shared helper
- **`filing_components/business_info.py`**
  - Sets legal type, association type, legal name (numbered names get a suffix from `Business.BUSINESSES`), and NAICS info.
  - Sets identifier, founding_date, last_coa_date and last_cod_date.
  - `get_next_corp_num` uses `BusinessIdentifier.next_identifier` or calls COLIN_API with a bearer token.
  - `get_firm_affiliation_passcode` builds the firm passcode.

## Caution
- **Missing keys and None values**
  - `change_of_directors` raises KeyError on `actions` for filings without colinIds.
  - It can also raise TypeError if a middle initial is None.
  - `transition` accesses offices and shareStructure directly (KeyError if missing) but uses `.get()` for parties and nameTranslations.
  - `business_info.set_legal_name` doesn't check that legal_type exists in `Business.BUSINESSES`.
- **Crashes on bad input**
  - `amalgamation_application` crashes on a horizontal or vertical amalgamation if there is no holding or primary business, because it uses a bare `next()`.
  - `annual_report` with a missing annualReportDate logs an error and continues, then fails with AttributeError when writing filing_meta.
- **Silent suppression of errors**
  - `continuation_out` ignores missing nested fields via `suppress()`.
  - `restoration` suppresses IndexError, KeyError and TypeError when parsing the court order.
  - Annual report AGM date ValueError is suppressed.
  - `business_info.get_next_corp_num` returns None for connection errors, non-200 responses and out-of-range numbers, and doesn't say which happened.
- **Errors that don't halt processing**
  - `dissolution` logs custodial office creation failure but keeps going.
  - `worker.py` catches email and event publishing exceptions broadly and only logs them with `capture_message` and `print`. They don't halt processing or propagate.
- **Partial writes**
  - The cooperative document appends in `incorporation_filing` are not transactional. If the second append fails, the first persists.
  - `continuation_in` shows no explicit commit around its jurisdiction and document appends.
- **Protected-member access**
  - Several processors write to the protected `filing_rec._filing_json` to bypass the setter. These are incorporation, continuation_in and amalgamation.
- **Surprising behavior**
  - `business_info.update_business_info` sets last_coa_date and last_cod_date to the filing effective date for every filing type.
  - Amalgamation directors are copied, then their roles are reset to Director with the current effective date.
  - Filing parties are reduced to only the completing party role.

# purpose-budget

# Entity-filer filing processors and worker

This part applies business filings to the legal-entity database. `worker.py` dispatches each queued filing to a type-specific processor in `filing_processors/`, then runs post-processing such as affiliation, name-request consumption, profile updates, and email and event publishing. It is for engineers maintaining filing behavior for BC corporations, co-ops and firms.

## Inputs and outputs
- **In:** a filing submission (`business_id`, `effective_date`, `colin_event_ids`), a list of `legal_filings` dicts keyed by filing type, `filing_core_submission` (`filing_type`), an `is_correction` flag, and feature flags.
- **Out:** mutated `Business` and `Filing` rows, plus `FilingMeta`, which carries data for downstream consumers. Emails and events are published asynchronously. Cooperative documents go through `MinioService`. Corporation numbers can come from COLIN (`AccountService` bearer token) or `BusinessIdentifier`.

## Main flow (`worker.py`)
1. Open a transaction, load the business, and read the filing metadata.
2. For each filing dict, call the matching processor. About 20 types are handled, among them annualReport, dissolution, incorporationApplication, restoration, transition, continuationIn, continuationOut and amalgamationApplication. `specialResolution` is processed independently.
3. Set `transaction_id` and mark the filing processed.
4. **Creation types** (amalgamation, continuation-in, conversion, incorporation, registration): commit a second time to set `business_id`. Then call `update_affiliation` (skipped for conversion), `consume_nr`, `update_business_profile` and publish MRAS.
5. **Other types:** call `update_entity` for alteration, change of registration, correction, dissolution, put-back-on and restoration. Call `consume_nr` and `update_business_profile` for alteration, change of registration, change of name, correction and restoration.

## Ideas owned by the processors
- **Business creation** (`incorporation_filing`, `continuation_in`, `amalgamation_application`): each requires `business` to be `None`. The corporation number is taken from the filing when `colin_event_ids` is present, otherwise reserved through `business_info.get_next_corp_num`. The new business is set ACTIVE.
- **Amalgamation:** each amalgamating business is either foreign (identifier, name and jurisdiction stored) or local (marked HISTORICAL). Horizontal and vertical types copy name, directors, offices and shares from the holding or primary business.
- **Lifecycle transitions:**
  - Dissolution and continuation-out set HISTORICAL and the dissolution date.
  - Restoration sets ACTIVE and clears the dissolution date. It also sets or clears the expiry date and ceases custodians.
  - Dissolution with the flag on moves queued batch-processing rows to COMPLETED. Co-op dissolutions stamp a certified affidavit.
- **Annual report:** updates `last_ar_date`, `last_ar_year` and `last_agm_date`. With the involuntary-dissolution flag on, it withdraws a batch when the business is back in good standing.
- **Directors:** `change_of_directors` matches by name to decide appointed, ceased or modified.
- **`business_info`:** helper for legal type, name, NAICS, corporation numbers and firm passcodes.

## Open first
1. `worker.py`
2. `filing_processors/filing_components/business_info.py`
3. `filing_processors/incorporation_filing.py`
4. `filing_processors/amalgamation_application.py`
5. `filing_processors/dissolution.py`

## Hazards
- **Bare `next()` crash:** amalgamation raises if no holding or primary business is found.
- **Missing AR date:** annual report logs the error but continues, then fails on `ar_date.isoformat()`.
- **Colin-only assumption:** `change_of_directors` raises `KeyError` on `actions` for non-colin filings.
- **Silent failures:**
  - `get_next_corp_num` returns `None` for connection errors, non-200 responses and out-of-range numbers alike.
  - Court-order and region parsing in continuation-out and restoration is silently suppressed.
  - Custodial-office creation failure in dissolution only logs.
  - Email and event publish errors in the worker are logged and swallowed.
- **Inconsistent access in `transition`:** offices and `shareStructure` are read directly (`KeyError` if absent), while parties and aliases use `.get`.
- **`_filing_json` writes:** several processors write the protected `_filing_json`, bypassing the setter.
- **Partial writes:** the two co-op documents in incorporation are appended without a transaction of their own. Failing between them leaves the first persisted.
- **`set_legal_name` lookup:** it does not validate that `legal_type` exists in `Business.BUSINESSES`.

# decisions

# Entity-filer filing processors and worker dispatch

This part of the entity-filer queue service applies a submitted business filing to the legal-entity database. `worker.py` dispatches each filing to a type-specific processor in `filing_processors/`. Each processor creates or updates Business, Filing and FilingMeta records. The worker then publishes email and event messages and does the follow-up work (affiliation, name-request consumption, profile update).

## Worker dispatch (`worker.py`)

**Input:** `filing_submission` (`business_id`, `effective_date`, `colin_event_ids`), `legal_filings` (list of dicts, each keyed by filing type), `filing_core_submission` (`filing_type`, json), `is_correction`, and the flags service.

**Output:** updated Business and FilingSubmission rows, plus an email and an event published asynchronously.

**Flow:**
1. Open a transaction, fetch the business, and extract the filing metadata.
2. For each filing dict, call the processor matching the key present. The keys are:
   - `alteration`, `annualReport`, `changeOfAddress`, `changeOfDirectors`, `changeOfName`, `dissolution`
   - `incorporationApplication`, `registration`, `conversion`, `courtOrder`, `registrarsNotation`, `registrarsOrder`
   - `correction`, `transition`, `changeOfRegistration`, `putBackOn`, `restoration`, `adminFreeze`
   - `consentContinuationOut`, `continuationOut`, `agmLocationChange`, `agmExtension`, `amalgamationApplication`, `continuationIn`
3. `annualReport` is passed `flag_on=flags.is_on('enable-involuntary-dissolution')`.
4. `specialResolution` is checked and processed independently of the above.
5. Set `filing_submission.transaction_id` and mark the filing processed.

**Post-processing decision on `filing_core_submission.filing_type`:**
- If the type is in {AMALGAMATIONAPPLICATION, CONTINUATIONIN, CONVERSION, INCORPORATIONAPPLICATION, REGISTRATION}:
  - Set `business_id` in a second commit.
  - Run `update_affiliation`, skipped for CONVERSION.
  - Run `consume_nr`, `update_business_profile`, and publish MRAS.
- Otherwise:
  - For ALTERATION, CHANGEOFREGISTRATION, CORRECTION, DISSOLUTION, PUTBACKON and RESTORATION, call `update_entity`.
  - For ALTERATION, CHANGEOFREGISTRATION, CHANGEOFNAME, CORRECTION and RESTORATION, call `consume_nr` and `update_business_profile`.

## New-entity processors

These processors all raise `QueueException` if their filing block is missing or a Business already exists.

**Incorporation (`incorporation_filing.py`)**
- The corp number comes from `filing['filing']['business']['identifier']` when `filing_rec.colin_event_ids` is set. Otherwise it is reserved with `business_info.get_next_corp_num()`, and the processor raises if that returns None.
- Calls `update_business_info`, then sets state ACTIVE.
- If a `cooperative` block is present:
  - It fetches `rulesFileKey` and `memorandumFileKey` from Minio.
  - It applies the `RegistrarStampData` certified stamp with `replace_file_with_certified_copy`.
  - It appends Documents of type COOP_RULES and COOP_MEMORANDUM, and sets `association_type`.
- Applies offices, parties, share structure, aliases and court order when present. `filing_meta.incorporation_application` gets `nrNumber` and `legalName` if `nrNumber` is present.
- Unless `colin_event_ids` is set, it writes `identifier`, `legalType` and `foundingDate` back into the filing JSON.

**Continuation in (`continuation_in.py`)**
- The corp number comes from the filing or is reserved; a missing one raises.
- Creates the Business as ACTIVE and a Jurisdiction from `foreignJurisdiction` (country, region, legalName, identifier, incorporationDate, taxId).
- `affidavitFileKey` present (AB/NS) adds a DIRECTOR_AFFIDAVIT document.
- Each file in `authorization.files` adds an AUTHORIZATION_FILE document.
- Applies offices, parties, shares, aliases and court order.
- Without `colin_event_ids`, it updates the filing JSON as incorporation does.

**Amalgamation application (`amalgamation_application.py`)**
1. Reserve the next corp number for the legal type.
2. Create an Amalgamation with `filing_id`, `type`, `amalgamation_date` (the filing effective date) and `court_approval`.
3. For each amalgamating business:
   - If `foreignJurisdiction` is present, store `foreign_identifier`, `foreign_name` and `foreign_jurisdiction` (country, plus region uppercased).
   - Otherwise look up the existing Business by identifier, store `business_id`, and mark that business HISTORICAL with `dissolution_date` and `state_filing_id`.
4. For `Amalgamation.AmalgamationTypes.horizontal` or `.vertical`, copy from the business whose `role` is holding or primary:
   - legal name
   - active directors, reset to the Director role at the effective date
   - REGISTERED and RECORDS offices
   - share classes and resolution dates
5. Create the ACTIVE Business, attach the Amalgamation, apply the filing's offices, parties, shares, translations and court order, and write the identifier, legalType and foundingDate to the filing JSON. `nrNumber` goes to `filing_meta`.

**Registration:** dispatched by the worker, but no processor notes are present.

## Existing-business processors

- **Annual report (`annual_report.py`):**
  - `annualReportDate` is required.
  - `annualGeneralMeetingDate` is parsed inside `suppress(ValueError)`. It updates `last_agm_date` and `last_ar_date` only when `validations.annual_report.requires_agm(business)` is true.
  - `last_ar_year` increments if set; otherwise it becomes `founding_date.year + 1`.
  - If `flag_on` and `business.in_dissolution`, it calls `InvoluntaryDissolutionService.check_business_eligibility(exclude_future_effective_filing=True)`. If the result is False, the batch processing status becomes `BatchProcessingStatus.WITHDRAWN` with the note 'Moved back into good standing'.
  - Writes `application_date` and the `annual_report` dict to `filing_meta`.
- **Change of directors (`change_of_directors.py`):**
  - For colin filings, directors are matched by case-insensitive name (firstName + middleInitial + lastName).
  - A director not found is *appointed*, with a new party and role.
  - A director with `cessationDate` is *ceased*; any other match is *modified*. A modified director uses `prevNames` if `nameChanged`.
  - Active directors missing from the new list are ceased.
  - Sets `last_cod_date` to `application_date`.
- **Continuation out (`continuation_out.py`):**
  - Sets state HISTORICAL, `state_filing_id`, `dissolution_date` and `continuation_out_date` (the filing date, converted to UTC via LegislationDatetime).
  - Sets jurisdiction to the uppercased country, plus `foreign_legal_name` and `foreign_jurisdiction_region` (uppercased).
  - Records the values in `filing_meta.continuation_out`, and updates the court order if present.
- **Dissolution (`dissolution.py`):**
  - `dissolution_date` is `dissolutionDate` only for VOLUNTARY dissolutions of SOLE_PROP or PARTNERSHIP. Otherwise it is the filing effective date via LegislationDatetime.
  - An ADMINISTRATIVE type deletes `business.amalgamation` and `amalgamating_businesses`.
  - Sets state HISTORICAL, updates parties, and creates the `custodialOffice` if present. Sets `order_details` and the court order.
  - If `flag_on`, it moves BatchProcessing rows for the filing from QUEUED to COMPLETED.
  - For COOP legal types, `_update_cooperative` (skipped for ADMINISTRATIVE) runs:
    - It fetches the affidavit from Minio.
    - It stamps it with `RegistrarStampData(effective_date, identifier)`.
    - It saves the certified copy and appends an AFFIDAVIT Document.
- **Restoration (`restoration.py`):**
  - Sets state ACTIVE and clears `dissolution_date`.
  - If `nameRequest` is present, it calls `set_legal_name`. `fromLegalName` and `toLegalName` go to `filing_meta`.
  - With `expiry` (limited restoration) it sets `restoration_expiry_date`; otherwise it clears it.
  - `_update_parties` first ceases existing CUSTODIAN roles at `utcnow()`.
  - Sets `approval_type`.
  - Sets `application_date` and `notice_date` only when the registrar block has both.
- **Transition (`transition.py`):**
  - Sets `restriction_ind` from `hasProvisions`.
  - Offices and parties are updated when present, and shares and aliases are updated through their own helpers.

## Shared helper: `filing_components/business_info.py`

- `update_business_info` sets the legal type, association type and legal name, and sets `identifier`, `founding_date`, `last_coa_date` and `last_cod_date` all to the filing effective date.
- `set_legal_name` uses `legalName` if present. Otherwise it builds the name from a slice of `corp_num` (from position 1 for continue-in types, from position 2 otherwise) plus `Business.BUSINESSES[legal_type]['numberedLegalNameSuffix']`.
- `update_naics_info` sets the NAICS code, looks it up with `NaicsService.find_by_code`, and sets the description.
- `get_next_corp_num` first tries `BusinessIdentifier.next_identifier` for known types. Otherwise it maps the legal type to 'BC', 'C' or itself, gets a bearer token, and POSTs to `COLIN_API/{type}`. It returns `{type}{corpNum:07d}` only if the status is 200 and `corpNum` ≤ 9999999.
- `get_firm_affiliation_passcode` returns the party role's `organization_name`, or "last, first [middle]".

## Hazards

1. **Amalgamation crash:** horizontal and vertical amalgamations use a bare `next()` to find the holding or primary business. They raise `StopIteration` if none exists.
2. **Failed corp-number reservation:** `get_next_corp_num` returns None for connection errors, non-200 responses and out-of-range numbers alike. Callers see only "no number".
3. **Change-of-directors failure:** `new_director['actions']` is only set for colin filings, so other filings hit a KeyError. A `None` middle initial can raise TypeError during name concatenation.
4. **Annual report without a date:** a missing `annualReportDate` is only logged, and the processor continues. It later fails with AttributeError when writing `filing_meta`.
5. **Silent swallowing:**
   - Court-order, region and nested-field errors are suppressed in `continuation_out`, `restoration` and `dissolution`.
   - A failed custodial office creation in `dissolution` is logged and processing continues.
   - Email and event publish failures in the worker are only reported through `capture_message`, so downstream messages can be lost.

# decisions-ctx

# entity-filer: filing processors and worker dispatch

The entity-filer worker takes a business filing submission and routes each filing to a type-specific processor. The processors change Business and Filing rows in the legal-entity database. After that, the worker handles the follow-on work: affiliation, name-request consumption, business profile, MRAS, entity update, and the email and event publications. The part belongs to the LEAR queue services.

## Inputs and outputs

- **Input to `worker.py`:** `filing_submission` (`business_id`, `effective_date`, `colin_event_ids`), `legal_filings` (a list of dicts with one key per filing type), `filing_core_submission` (json, `filing_type`), an `is_correction` flag, and the flags service.
- **Input to each processor:** the filing dict, the `Filing` record, the `Business` (or `None` for new-business types) and a `FilingMeta`. Some processors also take `flag_on`.
- **Output:**
  - Updated `Business`, `Filing` and `FilingSubmission` rows. `filing_submission.transaction_id` is set and the submission is marked processed.
  - `filing_meta` entries for the filing type.
  - Email and event publications, sent asynchronously.

## Dispatch decisions (`worker.py`)

- Each filing dict is routed by its key. The keys handled are `alteration`, `annualReport`, `changeOfAddress`, `changeOfDirectors`, `changeOfName`, `dissolution`, `incorporationApplication`, `registration`, `conversion`, `courtOrder`, `registrarsNotation`, `registrarsOrder`, `correction`, `transition`, `changeOfRegistration`, `putBackOn`, `restoration`, `adminFreeze`, `consentContinuationOut`, `continuationOut`, `agmLocationChange`, `agmExtension`, `amalgamationApplication` and `continuationIn`.
- `specialResolution` is checked separately and processed independently of the other keys.
- `annualReport` is called with `flag_on=flags.is_on('enable-involuntary-dissolution')`.
- If `filing_core_submission.filing_type` is one of AMALGAMATIONAPPLICATION, CONTINUATIONIN, CONVERSION, INCORPORATIONAPPLICATION or REGISTRATION:
  - `business_id` is updated in a second commit.
  - `update_affiliation` runs, except for CONVERSION.
  - `consume_nr`, `update_business_profile` and the MRAS publish run.
- Otherwise:
  - `update_entity` runs for ALTERATION, CHANGEOFREGISTRATION, CORRECTION, DISSOLUTION, PUTBACKON and RESTORATION.
  - `consume_nr` and `update_business_profile` run for ALTERATION, CHANGEOFREGISTRATION, CHANGEOFNAME, CORRECTION and RESTORATION.

## New-business processors

These processors require `business` to be `None`. They create the Business and then rewrite the filing JSON through the protected `_filing_json`.

**`incorporation_filing.py`**
- It raises `QueueException` if `incorporationApplication` is missing or a Business already exists.
- The corp number comes from `filing['filing']['business']['identifier']` when `filing_rec.colin_event_ids` is set. Otherwise it comes from `business_info.get_next_corp_num()`, and `QueueException` is raised if that returns `None`.
- It calls `update_business_info`, then sets state ACTIVE.
- With a `cooperative` object, it fetches `rulesFileKey` and `memorandumFileKey` from Minio. It stamps them with `RegistrarStampData` through `replace_file_with_certified_copy`. It adds `COOP_RULES` and `COOP_MEMORANDUM` documents and sets `association_type`.
- It updates offices, parties, share structure, aliases and court order when each is present.
- It records `nrNumber` and `legalName` in `filing_meta.incorporation_application`.
- The filing JSON is rewritten with `identifier`, `legalType` and `foundingDate` unless `colin_event_ids` is set.

**`continuation_in.py`**
- It raises `QueueException` if `continuationIn` is missing, the business is not new, or no corp number is available. The corp number comes from the filing or from a reservation.
- It creates the Business as ACTIVE and a Jurisdiction from `foreignJurisdiction`.
- If `affidavitFileKey` is present, it adds a `DIRECTOR_AFFIDAVIT` document.
- It adds an `AUTHORIZATION_FILE` document for each entry in `authorization.files`.
- It updates offices, parties, share structure, aliases and court order when present.
- The filing JSON is rewritten only when `colin_event_ids` is empty.

**`amalgamation_application.py`**
- It requires `amalgamationApplication` and no existing Business, and reserves the next corp number for the legal type.
- It creates an `Amalgamation` with `filing_id`, `type`, `amalgamation_date` (the effective date) and `court_approval`.
- For each amalgamating business:
  - If `foreignJurisdiction` is present, it stores `foreign_identifier`, `foreign_name` and `foreign_jurisdiction`, with the region uppercased.
  - Otherwise it looks up the existing Business and stores its `business_id`. It marks that business HISTORICAL, sets its `dissolution_date` and sets `state_filing_id`.
- For horizontal and vertical types, it copies data from the business whose `role` is holding or primary:
  - the legal name;
  - the active directors, with roles reset to Director at the effective date;
  - the REGISTERED and RECORDS offices;
  - the share classes and resolution dates.
- It then creates the ACTIVE Business, attaches the Amalgamation, and applies offices, parties, shares, translations and court order.
- It writes `identifier`, `legalType` and `foundingDate` into the filing JSON, and stores `nrNumber` in `filing_meta` when present.

## Existing-business processors

- **`annual_report.py`**
  - `annualReportDate` sets `last_ar_date`.
  - `annualGeneralMeetingDate` updates `last_agm_date` only when `validations.annual_report.requires_agm(business)` is true.
  - `last_ar_year` is incremented, or set to `founding_date.year + 1` when null.
  - If `flag_on`, the business is `in_dissolution`, and `InvoluntaryDissolutionService.check_business_eligibility(exclude_future_effective_filing=True)` returns False, the batch processing is set to `WITHDRAWN` with the note "Moved back into good standing".
- **`change_of_directors.py`**
  - Directors are matched by name (first + middle initial + last, case-insensitive) against existing records.
  - New directors are appointed, with a new party and role. Directors with a `cessationDate` are ceased. Others are modified, using `prevNames` when `nameChanged` is set.
  - Active directors missing from the new list are ceased.
  - `last_cod_date` is set to the application date.
- **`dissolution.py`**
  - It raises `QueueException` if `dissolution` is missing.
  - `dissolution_date` is `dissolutionDate` only for VOLUNTARY SOLE_PROP and PARTNERSHIP. Otherwise it is the effective date.
  - ADMINISTRATIVE dissolutions delete the amalgamation and amalgamating businesses.
  - It sets the business HISTORICAL with `state_filing_id`.
  - It updates parties, creates the `custodialOffice` and sets the court order.
  - For COOP and non-ADMINISTRATIVE dissolutions, `_update_cooperative` certifies the affidavit file and adds an `AFFIDAVIT` Document.
  - If `flag_on`, `BatchProcessing` rows for this filing change from QUEUED to COMPLETED.
- **`continuation_out.py`**
  - It sets the business HISTORICAL, with `dissolution_date` and `continuation_out_date` set to the UTC filing date.
  - It stores the jurisdiction (uppercased), `foreign_legal_name` and the region.
  - It records the values in `filing_meta.continuation_out` and applies the court order when present.
- **`restoration.py`**
  - It sets the business ACTIVE and clears `dissolution_date`.
  - An `expiry` field sets `restoration_expiry_date`. Without it, the date is cleared.
  - A `nameRequest` triggers `set_legal_name`.
  - It updates aliases, offices and parties. Existing CUSTODIAN roles get a `cessation_date` before the new parties are written.
  - It sets `approval_type`, the court order, and the registrar `application_date` and `notice_date`. The registrar dates are set only when both are present.
- **`transition.py`**
  - It raises `QueueException` if `transition` is missing or there is no business.
  - It sets `restriction_ind` from `hasProvisions`.
  - It updates offices, parties, shares and aliases when present.

## Shared helper: `filing_components/business_info.py`

- `update_business_info` sets the legal type, name, `identifier`, `founding_date`, `last_coa_date` and `last_cod_date`. The last three are all set to the effective date.
- `set_legal_name` uses `legalName` when present. Otherwise it builds the name from a slice of the corp number plus `Business.BUSINESSES[legal_type]['numberedLegalNameSuffix']`. The slice starts at position 1 for continue-in types and position 2 for others.
- `get_next_corp_num` tries `BusinessIdentifier.next_identifier` first. For other types it maps the legal type to `BC`, `C` or itself, gets a bearer token, and POSTs to `COLIN_API/{type}`. It returns `{type}{corpNum:07d}` only on HTTP 200 with `corpNum` ≤ 9999999. In every other case it returns `None`.
- `update_naics_info` sets the NAICS code and looks up its description through `NaicsService`.
- `get_firm_affiliation_passcode` returns the party's organization name, or "last, first [middle]".

## Hazards

1. **Business-type processors crash on missing or null data.**
   - Horizontal and vertical amalgamations crash with `StopIteration` if no holding or primary business is found.
   - `change_of_directors` raises `KeyError` on `new_director['actions']` when the filing has no colin ids.
   - A `None` middle initial can cause a `TypeError` in the name concatenation.
   - `transition` accesses offices and `shareStructure` directly, so a missing key raises `KeyError`.
2. **Annual report with no `annualReportDate`** only logs an error and carries on. It then fails with `AttributeError` when `ar_date.isoformat()` writes `filing_meta`. An invalid AGM date is silently ignored, and the AGM date is not updated.
3. **Silent failures.**
   - Court-order, region and nested-field errors are suppressed in `continuation_out`, `dissolution` and `restoration`.
   - Custodial office creation failure in `dissolution` is logged to Sentry and processing continues.
   - `get_next_corp_num` returns `None` without saying why.
4. **Multi-step work with no guarded transaction.** Documents are appended one at a time, so a failure part-way leaves the earlier ones in place. New-business types also commit `business_id` in a second commit.
5. **Publishing errors never stop processing.** Email and event failures in `worker.py` are caught broadly and only logged through `capture_message`. A filing can be processed with its notification never sent.

# decisions-tight

# Entity-filer filing processors and worker dispatch

The entity-filer queue service applies a submitted business filing to the legal-entity database. `worker.py` dispatches each filing to a type-specific processor in `filing_processors/`, then publishes email and events downstream.

## Inputs and outputs

- **Worker input:** `filing_submission` (`business_id`, `effective_date`, `colin_event_ids`), `legal_filings` (a list of dicts, one key per filing type), `filing_core_submission` (JSON with `filing_type`), an `is_correction` flag, and the flags service.
- **Worker output:** updated Business and Filing rows. It also sends an email and events asynchronously, plus a MRAS publish for new entities.
- **Processor signature:** each processor takes the filing dict, a Filing record, a Business (None for creation types) and a `FilingMeta`. It mutates them in place. Some return the Business, Filing and FilingMeta, and some return only the Filing.

## Worker flow and decisions (`worker.py`)

1. Open a transaction, fetch the business, and read the filing metadata.
2. For each dict in `legal_filings`, dispatch on which key is present. The keys are `alteration`, `annualReport`, `changeOfAddress`, `changeOfDirectors`, `changeOfName`, `dissolution`, `incorporationApplication`, `registration`, `conversion`, `courtOrder`, `registrarsNotation`, `registrarsOrder`, `correction`, `transition`, `changeOfRegistration`, `putBackOn`, `restoration`, `adminFreeze`, `consentContinuationOut`, `continuationOut`, `agmLocationChange`, `agmExtension`, `amalgamationApplication` and `continuationIn`.
   - Annual report gets `flag_on=flags.is_on('enable-involuntary-dissolution')`.
   - `specialResolution` is checked separately, so it can run alongside another key.
3. Set `transaction_id` and mark the submission processed.
4. Post-processing branches on `filing_core_submission.filing_type`:
   - **Creation types** (AMALGAMATIONAPPLICATION, CONTINUATIONIN, CONVERSION, INCORPORATIONAPPLICATION, REGISTRATION):
     - Set `business_id` in a second commit.
     - Call `update_affiliation`, except for CONVERSION.
     - Call `consume_nr` and `update_business_profile`.
     - Publish MRAS.
   - **Other types:**
     - `update_entity` runs for ALTERATION, CHANGEOFREGISTRATION, CORRECTION, DISSOLUTION, PUTBACKON and RESTORATION.
     - `consume_nr` and `update_business_profile` run for ALTERATION, CHANGEOFREGISTRATION, CHANGEOFNAME, CORRECTION and RESTORATION.

## Creation processors

All three raise `QueueException` if their filing block is missing or a Business already exists.

- **`incorporation_filing.py`**
  - Corp number: if `colin_event_ids` is set, it uses the identifier in the filing. Otherwise it calls `business_info.get_next_corp_num()` and raises if that returns None.
  - It creates the Business through `business_info.update_business_info()` and sets state ACTIVE.
  - If a `cooperative` object is present, it fetches the rules and memorandum files from Minio. It stamps them with `RegistrarStampData` via `replace_file_with_certified_copy`, then adds COOP_RULES and COOP_MEMORANDUM Documents and sets `association_type`.
  - It then applies offices, parties, shares, aliases and court order, each only if present. It records `nrNumber` and `legalName` in meta.
  - Unless `colin_event_ids` is set, it writes `identifier`, `legalType` and `foundingDate` into the filing JSON.
- **`continuation_in.py`**
  - It takes the corp number from the filing or reserves one, and raises if there is none.
  - It creates a Jurisdiction from `foreignJurisdiction`.
  - `affidavitFileKey` (AB/NS) adds a DIRECTOR_AFFIDAVIT document. `authorization.files` adds AUTHORIZATION_FILE documents.
  - It also updates offices, parties, shares, aliases and court order. The filing JSON is rewritten only when there are no `colin_event_ids`.
- **`amalgamation_application.py`**
  - It reserves a corp number and creates an Amalgamation with `type`, `amalgamation_date` and `court_approval`.
  - For each amalgamating business:
    - With `foreignJurisdiction`, it stores the foreign identifier, name and jurisdiction.
    - Otherwise it finds the Business by identifier, stores `business_id`, and marks it HISTORICAL with `dissolution_date` and `state_filing_id`.
  - For horizontal and vertical types, it copies from the business whose `role` is holding or primary:
    - legal name
    - active directors (roles reset to Director at the effective date)
    - REGISTERED and RECORDS offices
    - share classes and resolution dates
  - It then creates the ACTIVE Business and writes `identifier`, `legalType` and `foundingDate` into the filing JSON. `nrNumber`, if present, goes into meta.

## Other processors

- **`annual_report.py`**
  - It sets `last_ar_date` from `annualReportDate`. `last_agm_date` is set only when `annualGeneralMeetingDate` is present and `validations.annual_report.requires_agm(business)` is true.
  - `last_ar_year` is incremented, or set to `founding_date.year + 1` if null.
  - If `flag_on` and `business.in_dissolution`, it calls `InvoluntaryDissolutionService.check_business_eligibility(exclude_future_effective_filing=True)`. If the business is no longer eligible, the batch processing record is set to WITHDRAWN with the note "Moved back into good standing".
- **`change_of_directors.py`**
  - It matches directors by case-insensitive first, middle-initial and last name.
  - Outcome per director: appointed if new, ceased if `cessationDate` is set, otherwise modified (using `prevNames` if `nameChanged`). Active directors missing from the new list are ceased.
  - It sets `last_cod_date`.
- **`continuation_out.py`**
  - It sets the business to HISTORICAL, with `dissolution_date` and `continuation_out_date` from the UTC filing date.
  - It also sets the uppercased jurisdiction and region, and `foreign_legal_name`, and records all of these in meta.
- **`dissolution.py`**
  - `dissolution_date` is `dissolutionDate` only for VOLUNTARY dissolution of a sole proprietorship or partnership. Otherwise it is the effective date.
  - ADMINISTRATIVE dissolution deletes the amalgamation links.
  - It sets HISTORICAL, updates parties, and adds a `custodialOffice`.
  - For COOP (not ADMINISTRATIVE), `_update_cooperative` stamps the affidavit as a certified copy and adds an AFFIDAVIT Document.
  - With `flag_on`, BatchProcessing rows for this filing move from QUEUED to COMPLETED.
- **`restoration.py`**
  - It sets the business ACTIVE and clears `dissolution_date`.
  - `expiry` (limited restoration) sets `restoration_expiry_date`; otherwise the date is cleared.
  - A `nameRequest` triggers `set_legal_name`.
  - It ceases existing CUSTODIAN roles before updating parties.
  - `registrar` dates are applied only if both `applicationDate` and `noticeDate` are present.
- **`transition.py`**
  - It requires an existing business.
  - It sets `restriction_ind` from `hasProvisions`, then updates offices, parties, shares and aliases.
- **`filing_components/business_info.py`**
  - Shared helpers for the creation processors.
  - `update_business_info` sets the legal type, name and identifier, and sets `founding_date`, `last_coa_date` and `last_cod_date` to the effective date.
  - `set_legal_name` uses `legalName`, else builds a numbered name from the corp-num slice plus the `numberedLegalNameSuffix`.
  - `get_next_corp_num` tries `BusinessIdentifier.next_identifier` first, then falls back to the COLIN API.
  - `get_firm_affiliation_passcode` returns the organization name or the person's name.

## Open first

- `worker.py`: dispatch and post-processing.
- `filing_components/business_info.py`: corp numbers and naming.
- The creation processors above.

## Hazards

- A missing `annualReportDate` is only logged. The later `ar_date.isoformat()` then raises AttributeError.
- Non-COLIN `changeOfDirectors` filings raise KeyError on `actions`. A None `middleInitial` can raise TypeError.
- A horizontal or vertical amalgamation with no holding or primary business crashes on a bare `next()`.
- `get_next_corp_num` returns None for connection errors, non-200 responses and out-of-range numbers alike, so the caller cannot tell the cause.
- Failures are swallowed silently in several places:
  - email and event publishing errors are only logged;
  - a failed custodial office creation is logged and processing continues;
  - `suppress()` hides bad court orders, continuation-out fields and AGM date errors.

# core

This part is the entity-filer's filing-processing layer. `worker.py` takes a filing submission off the queue and dispatches each legal filing to a type-specific processor under `filing_processors/`. The processors change Business, Filing and FilingMeta records in the legal-entity database. The worker then hands follow-up work to downstream services: email, events, affiliation, name-request consumption, business profile and MRAS.

## Contract
- **In:** a filing submission (`business_id`, `effective_date`, `colin_event_ids`) and `legal_filings`, a list of dicts with one key per filing type, plus the core submission's `filing_type`. The worker also passes feature flags to processors.
- **Out:** each processor modifies the Business, Filing record and `filing_meta` in place, and most return the Filing record. The worker sets `transaction_id` and marks the submission processed.
- **Failures:** processors raise `QueueException` on missing blocks or invalid business state.

## Decisions
- **Dispatch:** `worker.py` picks a processor by which key is present in the filing dict. `specialResolution` is handled separately.
- **Creation types:** amalgamation application, continuation in, conversion, incorporation application and registration (a conversion skips the affiliation update). The worker commits a second time to set `business_id`, then runs `update_affiliation`, `consume_nr`, `update_business_profile` and the MRAS publish.
- **Update types:** alteration, change of registration, correction, dissolution, put back on and restoration call `update_entity`. `consume_nr` and `update_business_profile` run for alteration, change of registration, change of name, correction and restoration.
- **Annual report:** if the involuntary-dissolution flag is on and the business is in dissolution, it re-checks eligibility. If the business is no longer eligible for dissolution, the batch is set to WITHDRAWN.
- **Dissolution:** an ADMINISTRATIVE dissolution deletes the amalgamation links. A COOP dissolution stamps the affidavit. Queued batch processing records become COMPLETED.
- **Amalgamation:** horizontal and vertical types copy name, directors, offices and shares from the holding or primary business.
- **Corporation number:** `business_info.get_next_corp_num` reserves it, either locally or through the COLIN API.

## Hazards
- `get_next_corp_num` returns None for connection errors, non-200 responses and out-of-range numbers alike. Incorporation and continuation in then raise `QueueException`.
- Several processors fail with unhelpful errors. Amalgamation uses a bare `next()` when no holding or primary business exists. Change of directors raises `KeyError` on non-colin filings. Annual report raises `AttributeError` after a missing `annualReportDate` is only logged.
- Errors are swallowed silently. The worker only logs email and event publish failures. Court-order and continuation-out parsing use `suppress()`. A failed custodial office creation in dissolution is logged and processing continues.

## Open first
- `worker.py`: dispatch, commits and post-processing.
- `filing_components/business_info.py`: corporation numbers, legal names, NAICS.
- `amalgamation_application.py` and `incorporation_filing.py`: the creation flows.

# core-scaled

# entity-filer: filing processors and worker

Consumes processed filing submissions from the queue and applies each filing to the legal-entity database through type-specific processors. The worker then hands follow-on work to downstream services: affiliation, name-request consumption, business profile, MRAS, email and event publishing. Processors use shared components (`business_info`, offices, parties, shares, aliases, court orders), MinioService for documents, and COLIN API for corp numbers.

## Job 1: Dispatch a filing (`worker.py`)

**Contract:** Takes `filing_submission` (business_id, effective_date, colin_event_ids), `legal_filings` (a list of dicts, one key per filing type), `filing_core_submission` (filing_type), an `is_correction` flag and a flags service. It writes Business and FilingSubmission rows, sets `transaction_id` and marks the filing processed. It then publishes an email and an event asynchronously.

**Decisions:**
- Each legal filing dict is routed by its key (alteration, annualReport, dissolution, incorporationApplication, restoration, continuationIn, amalgamationApplication and so on) to the matching processor. `specialResolution` is handled separately.
- `annual_report` receives `flag_on` from the `enable-involuntary-dissolution` flag.
- For types AMALGAMATIONAPPLICATION, CONTINUATIONIN, CONVERSION, INCORPORATIONAPPLICATION and REGISTRATION, the worker:
  - commits the new business_id;
  - updates affiliation (skipped for CONVERSION);
  - consumes the NR;
  - updates the business profile;
  - publishes MRAS.
- For ALTERATION, CHANGEOFREGISTRATION, CORRECTION, DISSOLUTION, PUTBACKON and RESTORATION, it calls `update_entity`. The first three of those, plus CHANGEOFNAME and RESTORATION, also consume the NR and update the profile.

**Hazard:** Email and event publish errors are caught broadly and only reported via `capture_message`, so they never halt or propagate.

## Job 2: Create a new business (`incorporation_filing.py`, `continuation_in.py`, `amalgamation_application.py`)

**Contract:** Each takes a null Business, the filing dict, the Filing record and FilingMeta. It returns the new ACTIVE Business, with offices, parties, shares, aliases and court order applied. It writes the identifier, legalType and foundingDate back into the filing JSON (via the protected `_filing_json`) and records the NR number in the meta.

**Decisions:**
- If a business already exists or the block is missing, a QueueException is raised.
- The corp number comes from the filing when `colin_event_ids` is set. Otherwise it is reserved through `business_info.get_next_corp_num`, and None raises an exception.
- Incorporation for a cooperative stamps the rules and memorandum files as certified copies and adds Documents.
- Continuation-in creates a Jurisdiction, a DIRECTOR_AFFIDAVIT document and AUTHORIZATION_FILE documents.
- Amalgamation records each amalgamating business, either foreign or local. Local ones are marked HISTORICAL. Horizontal and vertical amalgamations copy name, directors, offices and shares from the holding or primary business.

**Hazards:**
- Amalgamation uses a bare `next()`, so it crashes if no holding or primary business exists.
- `get_next_corp_num` returns None silently on connection errors, non-200 responses and out-of-range numbers.
- Documents are appended without a visible transaction.

## Job 3: Update an existing business

**Contract:** Each processor mutates the Business and Filing in place, plus FilingMeta.

- **`annual_report.py`:** sets last AR and AGM dates and `last_ar_year`. With the flag on, it withdraws the in-dissolution batch ("Moved back into good standing") once the business is eligible.
- **`change_of_directors.py`:** matches directors by name, then appoints, modifies or ceases them.
- **`continuation_out.py`:** sets the business HISTORICAL and records the foreign jurisdiction.
- **`dissolution.py`:**
  - sets HISTORICAL and the dissolution date;
  - removes the amalgamation for ADMINISTRATIVE dissolutions;
  - updates the custodial office;
  - certifies the COOP affidavit;
  - completes QUEUED batch records when the flag is on.
- **`restoration.py`:** sets ACTIVE and clears the dissolution date. It sets or clears the expiry, ceases CUSTODIAN roles and sets approval type and dates.
- **`transition.py`:** updates restriction_ind, offices, parties, shares and aliases.

**Hazards:**
- Missing `annualReportDate` is only logged, then `ar_date.isoformat()` raises AttributeError.
- `change_of_directors` raises KeyError on `actions` for filings without colinIds.
- `suppress()` calls silently drop court-order, region and AGM errors, and custodial office failure in dissolution is only logged.

## Open first
- `worker.py`: dispatch table and post-processing.
- `filing_components/business_info.py`: corp-number and legal-name logic.
- `incorporation_filing.py` and `amalgamation_application.py`: new-business flows.
- `dissolution.py`: the most branching update processor.

# core#2

This part is the entity-filer's filing-processing layer. `worker.py` receives a filing submission and dispatches each legal filing to a type-specific processor in `filing_processors/`. The processors mutate the Business and Filing records in the database. The worker then updates affiliations, name requests and business profiles, and publishes email and event messages.

## Contract
- **In:** `filing_submission` (`business_id`, `effective_date`, `colin_event_ids`), `legal_filings` (a list of dicts, one key per filing type), `filing_core_submission.filing_type`, `is_correction`, and feature flags.
- **Processors:** each takes `(business, filing dict, filing_rec, filing_meta)`. They change those objects in place and write summary data into `filing_meta`.
- **Out:** updated Business and Filing rows, a transaction id, and the processed flag. Email, events, MRAS, affiliation, NR consumption and business-profile updates go to downstream services.

## Decisions
- **Dispatch (`worker.py`):** each filing key (`alteration`, `annualReport`, `dissolution`, `restoration`, `continuationIn` and so on) routes to its processor. `specialResolution` is processed separately.
- **New-entity types:** incorporation, registration, amalgamation, continuation-in and conversion. These require `business is None`.
  - The worker commits a second time to set `business_id`.
  - It then calls `update_affiliation` (skipped for conversion), `consume_nr`, `update_business_profile` and the MRAS publish.
- **Other types:** `update_entity` runs for alteration, change of registration, correction, dissolution, put-back-on and restoration. `consume_nr` and `update_business_profile` run for alteration, change of registration, change of name, correction and restoration.
- **Corp numbers (`business_info.get_next_corp_num`):** uses `BusinessIdentifier` for known types, otherwise calls COLIN. Incorporation and continuation-in reuse the filing's identifier when `colin_event_ids` is present.
- **Amalgamation:** the holding or primary business supplies the legal name, directors, offices and shares for horizontal and vertical types. Amalgamating businesses become HISTORICAL.
- **Dissolution:** ADMINISTRATIVE dissolutions delete the amalgamation. COOPs get a certified affidavit document. Queued batch-processing rows are completed when the flag is on.
- **Annual report:** may withdraw a business from involuntary dissolution once the eligibility check fails.

## Hazards
- Several processors raise on missing data. Examples are `next()` with no holding or primary business in amalgamation, `KeyError` on `actions` in change-of-directors for non-COLIN filings, and `AttributeError` in annual report when `annualReportDate` is missing.
- `suppress()` and broad `except` blocks swallow errors silently. This affects court-order parsing, AGM dates, and email or event publishing in the worker. A failed custodial office is logged but processing continues.
- `get_next_corp_num` returns `None` for every failure mode without distinguishing them.

## Open first
- `worker.py`: dispatch and post-processing.
- `filing_components/business_info.py`: corp numbers, legal names and NAICS.
- `amalgamation_application.py` and `incorporation_filing.py`: new-entity creation.

# core-states

# Entity-filer filing processors and worker

The worker dispatches each queued business filing to a type-specific processor in `filing_processors/`. The processors create or update Business, party, office, share and document records in the legal entity DB. The worker then publishes email and event messages downstream and syncs affiliation, name requests and the business profile.

## Contract
- **In:** `worker.process_filing` takes `filing_submission` (business_id, effective_date, colin_event_ids), `legal_filings` (a list of dicts, one key per filing type), `filing_core_submission` (filing_type), an `is_correction` flag and the flags service.
- **Processor signature:** each processor takes `(business, filing dict, filing_rec, filing_meta)`. Most mutate these in place. Incorporation, amalgamation and continuation-in return `(Business, Filing, FilingMeta)`. Transition returns `filing_rec`.
- **Out:** updated Business and Filing rows, `filing_meta` entries, and email and event messages published asynchronously. For some filing types, calls to the COLIN API, Minio, NAICS and the account service.

## Decisions
- **Dispatch (`worker.py`):** the filing key (`alteration`, `annualReport`, `dissolution`, `restoration` and so on) selects the processor. `specialResolution` is checked separately and processed independently.
- **New-entity types (`worker.py`):** AMALGAMATIONAPPLICATION, CONTINUATIONIN, CONVERSION, INCORPORATIONAPPLICATION and REGISTRATION trigger a second commit that sets `business_id`. They then call `update_affiliation` (skipped for CONVERSION), `consume_nr`, `update_business_profile` and the MRAS publish.
- **Existing-entity types (`worker.py`):** ALTERATION, CHANGEOFREGISTRATION, CORRECTION, DISSOLUTION, PUTBACKON and RESTORATION call `update_entity`. ALTERATION, CHANGEOFREGISTRATION, CHANGEOFNAME, CORRECTION and RESTORATION also call `consume_nr` and `update_business_profile`.
- **Annual report (`annual_report.py`):** AGM date is only applied if `validations.annual_report.requires_agm`. `last_ar_year` is incremented, or set to founding year + 1 if null. If `flag_on`, the business is `in_dissolution` and `InvoluntaryDissolutionService.check_business_eligibility` returns False, the batch processing record is set to WITHDRAWN.
- **Incorporation (`incorporation_filing.py`):**
  - Refuses if the business already exists or `incorporationApplication` is missing.
  - Uses the filing's identifier if `colin_event_ids` is present, otherwise reserves one with `business_info.get_next_corp_num`, and raises if that returns None.
  - For a cooperative, it stamps the Minio rules and memorandum files with `RegistrarStampData` and adds Documents.
- **Continuation in (`continuation_in.py`):** refuses if the business exists or no corp number is available. It creates a Jurisdiction, and creates DIRECTOR_AFFIDAVIT and AUTHORIZATION_FILE documents.
- **Amalgamation (`amalgamation_application.py`):**
  - Foreign amalgamating businesses are stored by foreign identifier. Local ones are set HISTORICAL.
  - For horizontal and vertical types, the holding or primary business's name, directors, offices and shares are copied.
- **Continuation out (`continuation_out.py`):** sets the business HISTORICAL with the jurisdiction and foreign legal name.
- **Dissolution (`dissolution.py`):**
  - The business is set HISTORICAL. `dissolution_date` comes from the filing for VOLUNTARY SOLE_PROP/PARTNERSHIP, otherwise from the effective date.
  - ADMINISTRATIVE dissolution deletes the amalgamation records.
  - For a COOP, `_update_cooperative` stamps the affidavit (skipped for ADMINISTRATIVE).
  - If `flag_on`, QUEUED batch processing records for the filing become COMPLETED.
- **Restoration (`restoration.py`):** sets the business ACTIVE and clears `dissolution_date`. `restoration_expiry_date` is set for a limited restoration and cleared otherwise. `_update_parties` ceases CUSTODIAN roles.
- **Change of directors (`change_of_directors.py`):** for COLIN filings, directors are matched by name. They are appointed if new, ceased if `cessationDate` is set, and modified otherwise. Active directors missing from the new list are ceased.
- **Transition (`transition.py`):** raises `QueueException` if `transition` is missing or the business is null.
- **Business info helpers (`filing_components/business_info.py`):** `get_next_corp_num` tries `BusinessIdentifier`, then the COLIN API. `set_legal_name` builds a numbered name when no `legalName` is given.

## Hazards
- Several processors fail silently or crash late:
  - Annual report logs a missing `annualReportDate` and continues, then raises AttributeError.
  - Change of directors raises KeyError on `actions` for non-COLIN filings.
  - Horizontal and vertical amalgamation crashes if no holding or primary business is found.
- `get_next_corp_num` returns None for connection errors, non-200 responses and out-of-range numbers alike.
- Custodial office failure in dissolution, court-order parsing in restoration and continuation-out, and email and event publishing in the worker are suppressed or only logged, so work is lost without a trace.

## Open first
- `worker.py`: dispatch and the post-commit side effects.
- `incorporation_filing.py` and `amalgamation_application.py`: the new-entity creation paths.
- `filing_components/business_info.py`: corp-number reservation and naming.
- `dissolution.py`: the state change, batch processing and coop affidavit.

# core-states#2

# Entity filer: filing processors and worker

The queue-service worker takes a submitted business filing and dispatches each filing dict to a type-specific processor in `filing_processors/`. The processors create or update Business, Party, Office, Share, Alias, Document and Jurisdiction records. The worker then publishes email and event messages to downstream services and calls Account/COLIN services for affiliation, name request (NR) consumption and profile updates.

## Contract
- **In:** `worker.py` receives `filing_submission` (business_id, effective_date, colin_event_ids), `legal_filings` (a list of dicts, one key per filing type), `filing_core_submission` (filing_type), an `is_correction` flag and the flags service.
- **Processor signature:** `(business, filing dict, filing_rec, filing_meta)`. Most mutate in place. Incorporation, continuation-in and amalgamation return `(Business, Filing, FilingMeta)`. Transition returns the Filing.
- **Out:** DB rows (Business, Filing, Document, Amalgamation, Jurisdiction, BatchProcessing), `filing_meta.<type>` dicts, and email and event messages published asynchronously.
- **External calls:** MinioService (coop affidavit, rules and memorandum files), COLIN_API and AccountService (corp numbers), NaicsService, and InvoluntaryDissolutionService.

## Decisions
- **Dispatch (`worker.py`):** each filing key selects its processor. `specialResolution` is processed independently. The annual report processor gets `flag_on=flags.is_on('enable-involuntary-dissolution')`. The worker then sets `transaction_id` and marks the filing processed.
- **New-entity types (worker.py):** AMALGAMATIONAPPLICATION, CONTINUATIONIN, CONVERSION, INCORPORATIONAPPLICATION and REGISTRATION do a second commit that sets `business_id`. They then run `update_affiliation` (skipped for CONVERSION), `consume_nr`, `update_business_profile` and the MRAS publish.
- **Existing-entity types (worker.py):** `update_entity` runs for ALTERATION, CHANGEOFREGISTRATION, CORRECTION, DISSOLUTION, PUTBACKON and RESTORATION. `consume_nr` and `update_business_profile` run for ALTERATION, CHANGEOFREGISTRATION, CHANGEOFNAME, CORRECTION and RESTORATION.
- **New-business guards:** incorporation, continuation-in and amalgamation raise `QueueException` if the Business already exists or the filing block is missing.
- **Corp number (`business_info.get_next_corp_num`):**
  - Known types use `BusinessIdentifier.next_identifier`.
  - Other types POST to COLIN_API and accept a 200 response with `corpNum` ≤ 9999999.
  - Otherwise it returns None, and the caller raises.
  - Filings with `colin_event_ids` use the identifier already in the filing, and the JSON write-back is skipped.
- **Incorporation (`incorporation_filing.py`):** creates the Business as ACTIVE. For a coop it stamps the rules and memorandum files with `RegistrarStampData` and adds COOP_RULES and COOP_MEMORANDUM documents.
- **Continuation-in (`continuation_in.py`):** creates the Jurisdiction, adds a DIRECTOR_AFFIDAVIT document if `affidavitFileKey` is present, and adds AUTHORIZATION_FILE documents.
- **Amalgamation (`amalgamation_application.py`):**
  - Foreign amalgamating entities are stored by foreign identifier, name and jurisdiction.
  - Local amalgamating businesses are set HISTORICAL with the dissolution date and `state_filing_id`.
  - Horizontal and vertical types copy name, active directors, offices and shares from the holding or primary business.
- **Dissolution (`dissolution.py`):**
  - Sets HISTORICAL and picks the dissolution date by type: `dissolutionDate` for voluntary sole proprietorship or partnership, otherwise the effective date.
  - An ADMINISTRATIVE dissolution deletes the amalgamation records.
  - Coops get a certified affidavit via `_update_cooperative`, skipped for ADMINISTRATIVE.
  - With the flag on, BatchProcessing rows for the filing move QUEUED to COMPLETED.
- **Continuation-out (`continuation_out.py`):** sets HISTORICAL and records the foreign jurisdiction and legal name.
- **Restoration (`restoration.py`):**
  - Sets ACTIVE and clears `dissolution_date`.
  - Sets `restoration_expiry_date` only for a limited restoration.
  - `_update_parties` ceases CUSTODIAN roles.
  - Registrar dates are written only if both are present.
- **Annual report (`annual_report.py`):**
  - Sets `last_ar_date` and increments `last_ar_year`.
  - Sets `last_agm_date` only if `requires_agm`.
  - If the flag is on, the business is in dissolution and `check_business_eligibility` returns False, the batch is set WITHDRAWN.
- **Change of directors (`change_of_directors.py`):** matches directors by name to decide appointed, ceased or modified. Active directors missing from the new list are ceased.
- **Transition (`transition.py`):** sets `restriction_ind` from `hasProvisions` and updates offices, parties, shares and aliases.

## Hazards
- **Silent failures:** `worker.py` catches email and event publish errors, logs them with `capture_message`, and does not stop processing. Dissolution continues if custodial office creation fails. Court-order parsing is wrapped in `suppress()` in several processors, so malformed data is dropped without a log.
- **Crashes on missing data:**
  - Amalgamation calls a bare `next()` and fails with no holding or primary business.
  - Annual report with no `annualReportDate` logs an error, then fails with AttributeError on `ar_date.isoformat()`.
  - Change of directors raises KeyError on `actions` when `colinIds` are absent.
  - Transition raises KeyError when offices or shareStructure are missing.
- **Partial writes:** the coop document appends in incorporation, and the document appends in continuation-in, are not individually transactional.

## Open first
- `worker.py`: dispatch, the new-entity versus existing-entity branches, and the commits.
- `filing_components/business_info.py`: corp number allocation, legal name and NAICS.
- `amalgamation_application.py`, `continuation_in.py`, `incorporation_filing.py`: creation of new businesses.
- `dissolution.py` and `restoration.py`: state changes and batch/coop handling.
