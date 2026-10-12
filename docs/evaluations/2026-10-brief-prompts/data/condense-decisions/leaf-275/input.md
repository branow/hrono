=== queue_services/entity-filer/src/entity_filer/filing_processors/amalgamation_application.py ===

Processes an amalgamation application filing to create a new Business entity and Amalgamation record in the legal entity system.

Inputs: Filing dict with `filing.amalgamationApplication`, Filing record, Business (must be null), FilingMeta. Outputs: Business entity, updated Filing record and FilingMeta.

Main flow: (1) Validate `amalgamationApplication` exists and no Business already present; reserve next corporate number for the legal type; (2) Create Amalgamation with `filing_id`, `type`, `amalgamation_date` (from filing effective date), `court_approval` flag; (3) For each amalgamating business in filing: if `foreignJurisdiction` present, store `foreign_identifier`, `foreign_name`, `foreign_jurisdiction` (country, optional region uppercased); else find existing Business by identifier, store `business_id`, mark Business as HISTORICAL with `dissolution_date` and `state_filing_id`; (4) For horizontal/vertical types (`Amalgamation.AmalgamationTypes.horizontal`, `.vertical`), copy from the holding/primary business (`role` in [holding, primary]): legal name to filing, active directors to filing parties (reset roles to Director with current effective date), REGISTERED and RECORDS offices, share classes and resolution dates; (5) Create Business with `state` ACTIVE and attach Amalgamation; (6) Update business with filing's offices, parties, shares, name translations, court order; (7) Update filing JSON with new business `identifier`, `legalType`, `foundingDate`; if `nrNumber` present, store in filing_meta.

GOTCHA: Crashes on horizontal/vertical amalgamation if no holding/primary business found (uses bare `next()`).
GOTCHA: Directors copied then roles overwritten to only `Director` at filing's effective date; filing parties reduced to only completing party role.
GOTCHA: Filing JSON updated via protected `_filing_json` member.

=== queue_services/entity-filer/src/entity_filer/filing_processors/annual_report.py ===

Updates business filing dates and dissolution status when an annual report filing is processed.

**Inputs**: business, filing dict with 'annualReport' containing annualReportDate (required ISO string) and annualGeneralMeetingDate (optional ISO string), filing_meta container, flag_on boolean.

**Outputs**: business.last_ar_date, business.last_ar_year, conditionally business.last_agm_date; filing_meta.application_date and annual_report dict.

**Flow**: Parses annualReportDate (required). If annualGeneralMeetingDate exists and validations.annual_report.requires_agm(business) is True, parses agm_date and updates business.last_agm_date and last_ar_date. Increments business.last_ar_year or sets to founding_date.year+1 if null. If flag_on and business.in_dissolution, calls InvoluntaryDissolutionService.check_business_eligibility() with exclude_future_effective_filing=True; if eligibility is False, sets batch processing status to BatchProcessingStatus.WITHDRAWN with notes 'Moved back into good standing'. Writes dates to filing_meta.

**Decisions**: (1) ar_date required—if missing, logs error and continues; (2) agm_date optional, parsed in suppress(ValueError); (3) last_ar_year increments if set, else founding_date.year+1; (4) batch withdrawal when flag_on AND in_dissolution AND eligibility check returns False.

GOTCHA: Missing annualReportDate logs error but continues; ar_date.isoformat() call later raises AttributeError when writing filing_meta.
GOTCHA: ValueError from agm_date parsing silently suppressed; invalid ISO dates skip AGM date updates.

=== queue_services/entity-filer/src/entity_filer/filing_processors/change_of_directors.py ===

Processes change-of-directors filings to update Business director records. Input: Business object, filing dict with changeOfDirectors.directors array, filing_meta.application_date. Output: Modified Business.party_roles with updated/appointed/ceased directors; Business.last_cod_date set to application_date. For colin filings: matches directors by name (firstName+middleInitial+lastName, case-insensitive) against existing records to determine action (appointed if new, ceased if cessationDate present, modified otherwise); creates new party and role for appointed; updates existing active directors for others, using prevNames if nameChanged; ceases active directors absent from new list.

GOTCHA: Code assumes new_director['actions'] is always set, but crashes with KeyError if filing lacks colinIds (non-colin filings). GOTCHA: Name concatenation with .get() may produce TypeError if middleInitial or prevMiddleInitial is None rather than missing.

=== queue_services/entity-filer/src/entity_filer/filing_processors/continuation_in.py ===

Processes a continuation-in filing to incorporate a foreign corporation in BC, creating the initial business record with jurisdiction, documents, and corporate structure.

Inputs: filing dict with continuationIn block, Filing record, Business (must be new), FilingMeta. Outputs: persisted Business, updated Filing, FilingMeta with file keys and names.

Flow: (1) Validate continuationIn present, business is new; (2) Get corp number from filing or reserve new; (3) Create Business, set state ACTIVE; (4) Create Jurisdiction from foreignJurisdiction (country, region, legalName, identifier, incorporationDate, taxId); if affidavitFileKey, create DIRECTOR_AFFIDAVIT document; (5) Create AUTHORIZATION_FILE documents from authorization.files array; (6) Update offices, parties, shareStructure, aliases, court_order if present; (7) If not colin_event_ids, update filing_json with identifier, legalType, foundingDate.

Conditions: continuationIn missing or business not new → QueueException; no corp_num → QueueException; affidavitFileKey present (CUL: AB/NS) → append DIRECTOR_AFFIDAVIT.

GOTCHA: business parameter must be None—`if business: raise` enforces new-business-only, preventing reuse. No explicit transaction shown; jurisdictions and documents appended without visible commit. Uses `_filing_json` protected access to bypass setter.

=== queue_services/entity-filer/src/entity_filer/filing_processors/continuation_out.py ===

Processes a continuation out filing to update a business entity's state when it continues operations in a foreign jurisdiction.

Inputs: Business entity, continuation out Filing object, filing data dictionary, FilingMeta object. Extracts `continuationOut` data: legal name, continuation out date (converted to UTC via LegislationDatetime), and foreign jurisdiction details (country, region). Updates Business: sets state to HISTORICAL, state_filing_id to filing id, dissolution_date and continuation_out_date to the filing date, jurisdiction to country code (uppercased), foreign_legal_name, and foreign_jurisdiction_region (uppercased if present). Stores these values in filing_meta.continuation_out dictionary. Optionally updates court order if present via filings.update_filing_court_order(). Region extraction silently fails if missing.

GOTCHA: Missing court order, region, or other nested fields are silently ignored via `suppress()` — no errors logged or raised.

=== queue_services/entity-filer/src/entity_filer/filing_processors/dissolution.py ===

Filing processor marking a business HISTORICAL on dissolution: updates parties, custodial office, court orders, and sets dissolution_date per type and entity, and creates certified affidavit document for COOPs.

Extracts dissolution_filing from filing.get('dissolution') or raises QueueException. Gets dissolution_type from /dissolution/dissolutionType path. Sets dissolution_date to dissolutionDate (VOLUNTARY SOLE_PROP/PARTNERSHIP only) or filing.effective_date via LegislationDatetime. Deletes business.amalgamation and amalgamating_businesses if ADMINISTRATIVE type. Sets business.state = HISTORICAL and state_filing_id. Updates parties via update_parties if parties present. Creates custodialOffice via create_office and appends if successful; logs error and Sentry capture if creation fails. Sets filing_rec.order_details. Updates court order via filings.update_filing_court_order if present (suppresses errors). For COOP legal_type, calls _update_cooperative. Updates filing_meta.dissolution dict with dissolutionType and formatted dissolutionDate. If flag_on, updates BatchProcessing records (matching filing_id) from status QUEUED to COMPLETED.

_update_cooperative (skips ADMINISTRATIVE): gets affidavit file via MinioService.get_file(affidavit_file_key), creates RegistrarStampData(filing.effective_date, business.identifier), replaces file with certified copy via replace_file_with_certified_copy, creates Document(type=AFFIDAVIT, file_key, business_id, filing_id) and appends to business.documents.

GOTCHA: custodial office creation failure logs error but continues processing.

=== queue_services/entity-filer/src/entity_filer/filing_processors/filing_components/business_info.py ===

Manages business information during entity filing: sets legal type, name, NAICS codes, generates corporation numbers, and firm passpacks.

Takes business object and business_info dict containing legalType, legalName, naicsCode, naicsDescription. set_corp_type assigns business.legal_type from business_info['legalType']. set_association_type assigns business.association_type. set_legal_name uses business_info['legalName'] if present, else constructs from corp_num slice (position 1: for continue-in types; position 2: otherwise) plus Business.BUSINESSES[legal_type]['numberedLegalNameSuffix']. update_business_info chains these and sets identifier, founding_date, last_coa_date, last_cod_date all to filing.effective_date. update_naics_info sets naics_code, queries NaicsService.find_by_code for naics_key if code exists, sets naics_description. 

get_next_corp_num tries BusinessIdentifier.next_identifier for known types; else maps legal_type to 'BC', 'C', or itself, calls AccountService.get_bearer_token(), POSTs to COLIN_API/{business_type}, returns {business_type}{corpNum:07d} if status 200 and corpNum ≤ 9999999, else None. get_firm_affiliation_passcode retrieves PartyRole as of today, returns organization_name or "last_name, first_name [middle_initial]".

GOTCHA: set_legal_name doesn't validate legal_type exists in Business.BUSINESSES before access. GOTCHA: get_next_corp_num returns None silently for connection errors, non-200 responses, and out-of-range numbers without distinguishing them. GOTCHA: update_business_info sets last_coa_date and last_cod_date identically to filing.effective_date for all filing types.

=== queue_services/entity-filer/src/entity_filer/filing_processors/incorporation_filing.py ===

Processes an incorporation application filing by creating a new Business entity record and updating the Filing record and metadata.

Input: Business object (must be None), filing dict with incorporationApplication containing nameRequest, offices, parties, shareStructure, nameTranslations, courtOrder, and optional cooperative object with rulesFileKey and memorandumFileKey; Filing record; FilingMeta. Output: tuple of (Business, Filing record, FilingMeta).

Flow: extracts incorporationApplication and raises QueueException if missing or if Business already exists; determines corp number from filing_rec.colin_event_ids—if present uses filing['filing']['business']['identifier'], otherwise reserves via business_info.get_next_corp_num() and raises exception if None; creates Business and updates via business_info.update_business_info(); if cooperative object exists, retrieves rulesFileKey and memorandumFileKey from MinioService, applies RegistrarStampData certified stamp via replace_file_with_certified_copy(), appends Document records with types COOP_RULES.value and COOP_MEMORANDUM.value, sets business.association_type; sets business.state to ACTIVE; populates filing_meta.incorporation_application with nrNumber and legalName if nrNumber present; calls update_offices(), update_parties(), update_share_structure(), update_aliases(), update_filing_court_order() on respective fields if present; unless filing_rec.colin_event_ids exists, updates filing_rec._filing_json with business identifier, legalType, foundingDate.

GOTCHA: accesses filing_rec._filing_json protected member to bypass normal update mechanism.
GOTCHA: appends two Document objects for cooperative without transaction; if second append fails, first persists.

=== queue_services/entity-filer/src/entity_filer/filing_processors/restoration.py ===

Processes restoration filings to reactivate a dissolved business.

Inputs: business (Business), filing (dict with 'restoration' sub-dict), filing_rec (Filing), filing_meta (FilingMeta). Returns: None; all objects modified in-place.

Extracts restoration_filing. If nameRequest present, calls business_info.set_legal_name() and optionally records nrNumber in filing_meta.restoration. Records fromLegalName and toLegalName in filing_meta.restoration. Sets business.state to ACTIVE, clears business.dissolution_date. If expiry field exists (limited restoration), sets business.restoration_expiry_date via LegislationDatetime; else clears it; records expiry in filing_meta. Calls update_aliases() for nameTranslations, update_offices() for offices, _update_parties() for parties. Sets filing_rec.approval_type from approvalType. If 'courtOrder', parses courtOrder and calls filings.update_filing_court_order() (errors suppressed). If 'registrar' and both applicationDate and noticeDate present, sets filing_rec.application_date and filing_rec.notice_date via LegislationDatetime. Helper _update_parties() ceases existing CUSTODIAN roles by setting cessation_date to utcnow(), then calls update_parties().

GOTCHA: Court-order parsing uses suppress(IndexError, KeyError, TypeError), silently discarding malformed data.

=== queue_services/entity-filer/src/entity_filer/filing_processors/transition.py ===

Processes a transition filing to update a business record with offices, parties, share structure, provisions flag, and name translations. Extracts filing['transition'] (raises QueueException if missing), validates business exists (raises QueueException if null), sets business.restriction_ind from transition_filing.get('hasProvisions'), then conditionally updates offices, parties, share structure, and aliases via update_offices(), update_parties(), shares.update_share_structure(), and aliases.update_aliases(). Returns filing_rec.

GOTCHA: Inconsistent dict access — offices and shareStructure accessed directly (KeyError if missing), while parties and nameTranslations use .get(). Business object modified in-memory only.

=== queue_services/entity-filer/src/entity_filer/worker.py ===

Processes a business filing submission by dispatching to type-specific processors, then publishes email and events to downstream services.

**Input:** filing_submission (with business_id, effective_date, colin_event_ids), legal_filings (list of dicts, one key per filing type), filing_core_submission (json, filing_type), is_correction boolean, flags service.

**Output:** Updated Business and FilingSubmission rows in database; email and event published asynchronously.

**Flow:** Create transaction, fetch business, extract filing metadata. For each filing dict, dispatch to handler: filing.get('alteration') → alteration.process(); filing.get('annualReport') → annual_report.process(flag_on=flags.is_on('enable-involuntary-dissolution')); similarly for changeOfAddress, changeOfDirectors, changeOfName, dissolution, incorporationApplication, registration, conversion, courtOrder, registrarsNotation, registrarsOrder, correction, transition, changeOfRegistration, putBackOn, restoration, adminFreeze, consentContinuationOut, continuationOut, agmLocationChange, agmExtension, amalgamationApplication, continuationIn. Check if filing.get('specialResolution') and process independently. Set filing_submission.transaction_id and mark processed. 

**Decision:** If filing_core_submission.filing_type ∈ [AMALGAMATIONAPPLICATION, CONTINUATIONIN, CONVERSION, INCORPORATIONAPPLICATION, REGISTRATION] → update business_id (second commit), update_affiliation (skip CONVERSION), consume_nr, update_business_profile, publish MRAS; else → for ALTERATION/CHANGEOFREGISTRATION/CORRECTION/DISSOLUTION/PUTBACKON/RESTORATION call update_entity; for ALTERATION/CHANGEOFREGISTRATION/CHANGEOFNAME/CORRECTION/RESTORATION call consume_nr and update_business_profile.

**GOTCHA:** Exceptions in email and event publishing are caught broadly but only logged via capture_message with print(err); they do not halt processing or propagate.
