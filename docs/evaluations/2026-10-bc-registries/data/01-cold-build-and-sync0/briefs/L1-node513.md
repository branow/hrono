<!-- level 1, node 513, children [23, 151, 239, 240, 243, 247, 469, 483, 626, 627, 628] -->

# Parent brief: BC business-registry codebase notes (LEAR / COLIN / data migration)

The notes cover one ecosystem: BC Registries corporate-filing software. They include a share-structure test fixture, a COLIN-to-LEAR data-migration codebase, the COLIN API (Flask/Oracle), the LEAR legal API (Flask/SQLAlchemy/Postgres), a reporting layer and a front-end enum layer. Most items are condensed file or module summaries, and several are near-duplicates (resource class vs. service module).

## Where to look

**1. Test fixture and small migrations**
- **Fixture:** an incorporation application (`BEN`, NR1234567) at `/filing/incorporationApplication/shareStructure`.
  - Class 1: max 100, par CAD 10, with Series 1 (max 50) and Series 2 (max 100).
  - Class 2: no max, no par, `hasRightsOrRestrictions=true` and no series.
  - A correction-diff variant renames Class 1 to "Corrected Class 1".
  - Contact point and name-translation placeholders are `{{newCorpName}}`, `{{newCorpNum}}` and `{{newCorpNameForCorAll}}`.
- **Alembic `786dac4b44ef`:** creates `message_processing`. Its `downgrade()` drops an index that `upgrade()` never creates.
- **SQL backfill of `businesses.state`:** sets HISTORICAL for dissolved or malformed-JSON rows and ACTIVE when there is no dissolution_date. COMMIT and ROLLBACK are commented out.

**2. Data-migration source queries (COLIN-style source to the new system)**
- It has f-string SQL builders.
  - Work queues: `get_unprocessed_firms_query` and `get_unprocessed_corps_query` (flows `sp-gp-flow` and `corps-flow`).
  - Per-event detail queries: event/filing, offices, parties, comments, names and share structure.
  - Helpers: a result-set-to-dicts converter and `get_custom_corp_names()` (backslash names).
- The code is unfinished: a stub, an unclosed quote, and hundreds of commented-out test filters.

**3. COLIN API (Flask + Oracle, 2019)**
- **Models:**
  - `Business` (find_by_identifier, `is_in_good_standing`, `reset_corp_states`)
  - `Party` (grouping roles by person, end/create/reset parties)
  - `ShareObject` / `Share` / `ShareClass`
  - `ContOut`, `CorpInvolved`, `Jurisdiction`, `CorpName`, `FilingType`, `Office`, `ProgramAccount`
- **`Filing` model:** the `FILING_TYPES` map, `_insert_filing` (30+ type codes), `get_filing`, `add_filing` with its processors, and historic/future-effective filings.
- **REST:** `FilingInfo` under `/<legal_type>/<identifier>/filings`, AR reminder resources, and the `Reset` namespace (`/cooper`, `/by_event_id`). All use `COLIN_SVC_ROLE`.
- **Infrastructure:** `OracleDB` pool and date/SQL utilities.

**4. LEAR legal API (Flask/SQLAlchemy)**
- **Domain models:**
  - `Business`: LegalTypes, `good_standing`, `get_ar_dates`, finders, and `validate_identifier`.
  - `Filing`: domain class, SQLAlchemy model, status listeners and queries.
  - `FilingMeta`: display names and outputs.
- **`VersionedBusinessDetailsService`:** `get_revision()` does point-in-time reconstruction, with revision-to-JSON serializers.
- **Foundations:** `BaseEnum`/`BaseMeta`, `BusinessType`, `BusinessIdentifier`, `ErrorCode`/`Error`, filing getters, the `diff_dict`/`diff_list` utilities, API endpoint enums, and re-export packages.
- **API and services:**
  - `ListFilingResource` and its service twin (save, validate, ledger, Minio, payment invoice and fee codes).
  - Internal COLIN endpoints and the `update_filings` / `update_business_nos` / `publish_queue_events` sync job.
  - `NrTypeMap` (a stub).
  - `DocumentMetaService`.
  - Review resubmission.
  - Traction digital credentials.
- **Reporting:** `Report` / `ReportMeta` and the filing-meta container, with three renderers (business documents, filing reports, `ReportV2`/Gotenberg).

**5. Front-end enums (`EnumUtilities`)**
- Enums for filing status, sub-types, entity state, party roles, name-request states, payment methods and warnings.
- A barrel re-exporting 22 enums plus `CorpTypeCd` and `CorpClass`.
- `EnumUtilities` has status, filing-type, subtype and payment checks, and name converters (`filingTypeToName`, `dissolutionTypeToName`).

## Cross-cutting cautions

- **SQL injection and brittle SQL:**
  - The migration query builders, `ProgramAccount`, COLIN party and comment queries, and the internal LEAR endpoints (PATCH and POST) all use f-string or string-replace SQL.
  - `stringify_list` is weak protection.
  - Oracle-specific SQL such as `rownum` + `ORDER BY` can return the wrong "most recent" row.
- **Incomplete or stale code:**
  - Truncated stubs: the firms query stub, `NrTypeMap.get`, `DocumentMetaService`, the `FILINGS` assignment, `EnumUtilities`, `FILING_TYPES`, and the empty `Business` and `Party` class bodies.
  - Stale docstrings and metadata headers.
- **Known bugs and typos:**
  - The COLIN Reset `start_date = end_date` bug.
  - `ContOut` and `Jurisdiction` log a nonexistent `event_id`, which causes an AttributeError.
  - The `Error` class isn't an Exception.
  - The `ShareObject` has_max_share flag is stored inverted.
  - `good_standing` has inverted logic for non-ACTIVE state.
  - `certificateOfNameCorrection` maps to the wrong filename.
  - The malformed `{'message: ...', 500}` error dict.
  - `event_timerstamp`, "bn_9s" and "insformation" typos.
- **Business rules hardcoded:**
  - AR good-standing window of 1 year + 2 months + 1 day.
  - Date 2004-03-29.
  - The 2019-03-08 historic cutoff.
  - `SET_EVENTS_MANUALLY` with `first_failed_id=102125621`.
  - Dissolution state lists.
  - Identifier format: the last 7 characters, a 'T' prefix for temp registrations, and the `^(CP|XCP|BC|C|FM)\d{7}$` pattern.
  - COOP vs. BComp special cases.
  - Share cap 100 vs. series total 150 in the fixture.
- **Silent failure:**
  - Broad or bare excepts, `suppress(KeyError)`, `suppress(Exception)` around schema registration, and None-returning getters.
  - Unguarded `fetchone()` indexing.
  - `[[part.html]]` template markers that fail silently.
  - Unhandled filing types in `get_revision()` and the report routing default.
  - Null-vs-false semantics (`maxNumberOfShares=null` vs. `hasMaximumShares=false`).
- **Data-source and ordering assumptions:**
  - Parent-child party linking assumes rows sorted by start_event_id.
  - Share deletion order is hardcoded (series, then class, then struct).
  - Property paths differ between todo/filing items and state filings.
  - Status-listener precedence matters.
  - Correction handling overwrites `parent_filing`.
  - `include_properties` lists must be updated with columns.
- **Enum/semantic traps:**
  - Enum values must be read with `.value` (`ErrorCode`, `ReportType`).
  - Enum membership works by instantiating the enum.
  - `CONDITIONAL` vs. `CONDITION` in name-request states.
  - Numeric action-type IDs are not stable.
  - The `Roles` values are display strings.
  - The external `corp-type-module` is a hidden dependency.
