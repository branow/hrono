<!-- level 1, node 513, children [23, 151, 239, 240, 243, 247, 469, 470, 483] -->

# Parent brief: BC business-registry codebases (COLIN / LEAR / Legal API / front end) and fixtures

## What this group is
This is a set of condensed notes on the BC Registries ecosystem. They cover a legacy Oracle registry (COLIN), its Flask API, the newer LEAR legal-entity service, a reporting layer, a front-end enum layer, and a data-migration codebase. There is also a test fixture and one Alembic migration. Most code is Apache 2.0, Province of British Columbia, 2019–2024. The entity types are COOP/CP, BEN, BC, ULC, CC, XPRO and firms (FM, FP, SP/GP).

## Routing by topic

**1. Test fixture and migration**
- The fixture is an incorporation application (BEN) at `/filing/incorporationApplication/shareStructure`.
  - Class 1 has max 100 shares and CAD 10 par. Its Series 1 (max 50) and Series 2 (max 100) add up to more than the class cap.
  - Class 2 has no maximum, no par value, rights/restrictions flagged true, and no series.
  - It also holds a correction diff variant, contact/name-request data (NR1234567), and `{{newCorpName}}`-style template placeholders.
- Alembic migration `786dac4b44ef` creates `message_processing`. Its `downgrade()` drops a `source` index that `upgrade()` never creates.

**2. Data-migration codebase (PostgreSQL/Oracle-style source)**
- Work-queue builders `get_unprocessed_firms_query` and `get_unprocessed_corps_query` use `sp-gp-flow` and `corps-flow`.
- Per-event detail queries cover event/filing, offices, parties, comments, names and share structure.
- Helpers: a result-set-to-dicts converter and `get_custom_corp_names()` (backslash names).

**3. COLIN data-access models (Oracle, Flask)**
- `Business`: `find_by_identifier` and `is_in_good_standing`. Good standing uses the 1 year + 2 months + 1 day rule, with a 2004-03-29 cutoff and hardcoded dissolution states.
- `Party`: role types and group/read/write/reset methods.
- `Filing`: `FILING_TYPES`, `add_filing` and its processors, `get_filing`, and `_insert_filing`.
- `ShareObject`, `ContOut`, `CorpInvolved`, `Jurisdiction`, `CorpName`, `FilingType`, `Office` and `ProgramAccount`.
- The `Reset` feature reverses COOPER-user changes. It exposes `ResetInfo` (`/cooper`) and `ResetByEventId` (`/by_event_id`).
- REST: `FilingInfo` and the AR reminder resources, all requiring `COLIN_SVC_ROLE`.
- `OracleDB` extension (cx_Oracle pool) and date/SQL utilities.

**4. LEAR (Python/Flask/SQLAlchemy)**
- Models: `Business`, `Filing` (SQLAlchemy and domain classes).
- `VersionedBusinessDetailsService` handles historical revisions.
- `ListFilingResource` plus a refactored service handle filings, payment and invoicing.
- Documents and reports: `get_document_list`, `DocumentMetaService`, `FilingMeta`, and the `Report`, `BusinessDocument` and `ReportV2` services.
- Digital credentials via Traction.
- COLIN↔LEAR sync jobs: `update_filings`, `update_business_nos`, `publish_queue_events`.
- A dissolution-state SQL migration, internal endpoints and `NrTypeMap`.

**5. Reporting layer**
- `ReportMeta`, a filing-metadata class with 38 report types, and the large `Report` class.
- Business-summary formatters, and per-filing formatters routed by `_report_key`.

**6. Front-end enums**
- Filing, entity, party, payment and name-request enums, and a barrel re-export.
- `EnumUtilities` has status, type, subtype and payment checks, plus name converters such as `filingTypeToName`.

**7. Small domain and API modules**
- `BaseEnum`/`BaseMeta`, `BusinessType`, `BusinessIdentifier`.
- Endpoint enums, `Error`/`ErrorCode`, and the filing getters and diff utility.
- Re-export packages and an incomplete `DocumentMetaService` stub.

## Cross-cutting cautions
- **SQL injection:** Many builders interpolate values with f-strings (queue queries, office/party/comment queries, `ProgramAccount`, internal endpoints, `stringify_list`). Use parameterized queries.
- **Incomplete or truncated code:** There are stubs ending mid-assignment, unclosed SQL quotes, and cut-off snippets. This covers `get_unprocessed_firms_query`, `NrTypeMap`, `DocumentMetaService` and `EnumUtilities`.
- **Debug leftovers:** The queue queries carry hundreds of commented-out `corp_num` and file-type filters.
- **Known bugs and typos:**
  - Reset assigns `start_date = end_date`.
  - `ContOut`/`Jurisdiction` log a nonexistent `event_id`.
  - `ShareObject` stores `has_max_share` inverted.
  - LEAR `good_standing` returns True for non-ACTIVE states.
  - `certificateOfNameCorrection` maps to the wrong fileName.
  - A `bn_9s` log message looks copy-pasted.
  - `event_timerstamp` is a typo.
  - Several module docstrings are stale.
- **Oracle-specific SQL:** `rownum=1` with `ORDER BY` may return the wrong "most recent" row.
- **Error handling:**
  - Broad or bare excepts swallow errors, and log-then-reraise double-logs.
  - Exception types are inconsistent.
  - `fetchone()[0]` is unguarded.
  - Filing getters return None for both a missing key and a bad type.
  - `Error` is not an Exception.
- **Business-critical hardcoding:**
  - Dates and states: the 2019-03-08 historic cutoff, 2004-03-29, and the dissolution state codes.
  - Operational values: a 20s payment timeout, and `SET_EVENTS_MANUALLY` with `first_failed_id=102125621`.
  - Identifier formats: last 7 characters, and the `A` prefix for xpro.
- **Data-shape pitfalls:**
  - Null vs false for share maximums.
  - Class vs series cap mismatch.
  - Priority semantics.
  - Enum values as strings (use `.value`).
  - Numeric action enum IDs not stable.
  - Property paths differ between todo items and state filings.
  - `operation_type != 2` presumably means "deleted".
- **Ordering and consistency:**
  - Parent/child party linking assumes ascending `start_event_id`.
  - Share-structure deletes must run in the order series → class → struct.
  - `state_filings` sort is inconsistent.
- **Sync and migration risk:** If `max_event_id = first_failed_id - 1` isn't stored, failed filings disappear. The SQL migration auto-marks rows with malformed dissolution JSON as HISTORICAL, and its COMMIT/ROLLBACK is commented out.
- **Hidden dependencies and tight coupling:** `_build_parties_list` isn't shown. `@bcrs-shared-components` is an external dependency. There are cyclic model imports and a deprecated `_app_ctx_stack`.
- **Template placeholders:** `{{...}}` values are variables, not literal text.
