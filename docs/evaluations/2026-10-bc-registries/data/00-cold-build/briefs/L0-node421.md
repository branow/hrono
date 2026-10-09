<!-- leaf 421, 70 members -->

**Overview:** A collection of ~60 condensed Alembic database migrations from a BC registries (bcgov) business/filings schema (businesses, filings, parties, addresses, etc.), plus one unrelated item: a Zenhub GraphQL integration script. Each entry gives the revision, parent, upgrade/downgrade actions, and a gotcha.

## Groupings

**1. Add/drop single columns (the dominant pattern)**
Nullable columns added to `filings`, with downgrade dropping them:
- Dates and flags: `payment_completion_date` (bf94a1b46804), `completion_date`/`effective_date` (9b5c719f32ef), `application_date`/`notice_date` (89fe33f436c1), `paper_only` (94c2a694d51f), `colin_only` (9741616ab6d7), `deletion_locked` (78ddb7f6f8b5).
- Text and JSON: `order_details` (1fcdb213657d), `submitter_roles` (d21f6be7bd21), `payment_error_type` (54a3fc54a2cf), `tech_correction_json` JSONB (b18741f7c4d3), `status` (ed12492e70f8), `source` (7c86cc916b5c, with a data backfill).
- Court order and sub-types: three `court_order_*` columns (2dedf50a17ef), `filing_sub_type`/`approval_type` plus `restoration_expiry_date` (2afccb4603ec).

Added to `businesses` and `businesses_version`:
- `legal_type` (176f983485c8)
- `restriction_ind` (2e986c1d4de6)
- NAICS fields, party fields and a sequence (33501a263f32 → 94586877d4bc)
- `association_type` (8c74427a6c0e)
- `state`/`admin_freeze`/`state_filing_id` (da43f7bef692)

Other single-column adds:
- `users`: `login_source` (b9f84f7a7c44), `middlename` (8fef256bf5d7), `idp_userid` (1ba027b074a5)
- `dc_issued_credentials`: revocation columns (6b65b40a5164)
- `request_tracker`: `is_admin`/`message_id` (0b2af7f762bb)
- `amalgamating_business`: `foreign_jurisdiction_region` (f978e34aa8bb)
- `directors`: `mailing_address_id` (0fb2ae5711ed)
- `comments`: `filing_id` (1f01b9303b81)
- `party_roles`: `filing_id` (9147d4bc9939)
- `resolutions`: four new columns (e6ff12b18bef → 026f42f4f654)

**2. Column type changes, renames and drops**
- Widen or retype: `resolutions.resolution` to Text (0c792224fe11), `filings.status` to String(20) (361b51b824c0), `credential_id` 100→10 (8148a25d695e).
- Rename: `payment_error_type` → `payment_status_code` (7575af513efb).
- Drops: `tax_id` from parties (2e29ebe9a830), `content_type`/`file_name` from documents (bf8d4391745e), `cco_expiry_date` (9a9ac165365e), `grouping_identifier` from furnishings (bb9f4ab856b1).

**3. New tables, with `*_version` audit companions**
The versioned tables use the composite primary key (id, transaction_id) and `autoincrement=False`.
- Versioned pairs: `addresses` (1215735c3563), `directors` (860bb6075dde → bf94a1b46804), `share_classes`/`share_series` (442829649a2a), `parties`/`party_roles` (b9165c3187fc → 361b51b824c0), `resolutions` (a8f42b830d86), `aliases` (f3fb008e7b83), `documents` (8c74427a6c0e), `jurisdictions` (c4732cd8abfd), `offices` plus `office_types` (441a5e6cf682).
- Unversioned tables:
  - Core and requests: `comments` (b826412a6a65), `colin_last_update` (4ee6f0abb797 → b826412a6a65), `colin_event_ids` (92c4974ce96f), `request_tracker` (86d8aca36208), `registration_bootstrap` (1a8c89b722e2), `sent_to_gazette` (d9e21a1b82ca).
  - Domain features: `furnishings` (01b28a2bb730), `xml_payloads`/`furnishing_groups` (b14f77400786), `reviews`/`review_results` (ec9652171563), `amalgamation`/`amalgamating_business` (5238dd8fb805), `consent_continuation_outs` (9a9ac165365e), `dc_definitions`/`dc_connections`/`dc_issued_credentials` (ecfeee53451a).
- Dropped: `directors` and `directors_version` (c17d77b30bdb).

**4. Constraint, index and enum changes**
- `request_tracker` enum extensions: `filing_id`, new types (1400cc212014), then `CHANGE_PARTY` (c212a141600c).
- Foreign key swap on `addresses.office_id` (5e1faa8636c0).
- Self-FK `parent_filing_id` (ad3ef106696c).
- Unique constraints: added on `colin_event_ids` (e85053684b3c), dropped on `colin_last_update` (52553d4d6309), added on `users.idp_userid` (bddd732a9269).

**5. Seed/reference data (raw SQL)**
- `office_types` inserts: `custodialOffice` (026f42f4f654), `businessOffice` (f4f654026f42).
- `corp_types` descriptions (94586877d4bc → 9147d4bc9939).
- `configurations` table creation with seed rows (f4f93ea8887e), then dissolution settings changed (508c7466b2af).

**6. Outlier: Zenhub GraphQL integration**
This isn't a migration. It's a Python script for issues and releases, using the env vars `ZENHUB_GRAPHQL_TOKEN`, `ZENHUB_REPOSITORY_ID` and `TARGET_ZENHUB_WORKSPACE_ID`.

## Caution:
- **Unnamed foreign keys (`None`):** these make downgrades depend on the database's auto-generated names. Affected: 0fb2ae5711ed, 1a8c89b722e2, 1f01b9303b81, 9147d4bc9939, ad3ef106696c, e6ff12b18bef, e85053684b3c (unique constraint).
- **Non-reversible or broken downgrades:**
  - 2dedf50a17ef: downgrade is a no-op and leaves the columns in place.
  - 94586877d4bc → 9147d4bc9939: downgrade is a no-op.
  - 5e1faa8636c0: downgrade renames the FK to `addresses_office_id_fk`, so re-upgrading fails.
  - c17d77b30bdb: the downgrade restores the schema but not the data.
  - bf8d4391745e: downgrade recreates NOT NULL columns with no default, which fails on populated tables.
- **Data loss on downgrade or narrowing:**
  - 0c792224fe11: Text→VARCHAR(4096) truncates longer values.
  - 8148a25d695e: 100→10 chars with no pre-check.
  - 92c4974ce96f: duplicate colin_event_ids per filing are lost.
  - 9a9ac165365e: data loss if not migrated to the new table first.
  - 2e29ebe9a830: `tax_id` data is not restored.
- **Downgrades that can fail on existing data or dependencies:**
  - c212a141600c: fails if any row has `CHANGE_PARTY`.
  - da43f7bef692: `DROP TYPE state` without CASCADE.
  - 86d8aca36208: drops enums that other tables may share.
  - ec9652171563: the shared `review_status` type is dropped once and not recreated.
- **Header and docstring mismatches** (the code's `down_revision` is what counts):
  - 1215735c3563: docstring parent is `b826412a6a65`, code parent is `4ee6f0abb797`.
  - 441a5e6cf682: docstring says `176f983485c8`, code says `9b5c719f32ef`.
  - 94c2a694d51f: header says `176f983485c8`, code says `0fb2ae5711ed`.
  - d21f6be7bd21: header says `1fcdb213657d`, code says `8c74427a6c0e`.
  - ed12492e70f8: header says `1215735c3563`, code says `e6ed22dc70ca`.
- **Sequences not linked to columns:**
  - 01b28a2bb730: `grouping_identifier` has no DEFAULT.
  - bb9f4ab856b1: its downgrade does not re-attach the sequence as the default.
  - 33501a263f32 → 94586877d4bc: `business_identifier_sp_gp` has no column link.
- **Incomplete or logic risks:**
  - 1ba027b074a5: uniqueness is commented out, so it is not enforced.
  - d9e21a1b82ca: the primary key is on a nullable `filing_id`.
  - 7c86cc916b5c: a `lear_epoch` filing with a NULL event id gets source COLIN.
  - 508c7466b2af: renaming `NEW_DISSOLUTIONS_SCHEDULE` can silently break hardcoded references.
- **Types and values:**
  - 0b2af7f762bb: `server_default='0'` is a string.
  - f4f93ea8887e: config values are all strings, including `'False'`.
  - ecfeee53451a: the credential type enum is hardcoded to two values.
  - Short string limits may truncate: 6b65b40a5164 (10 chars) and f978e34aa8bb (10 chars).
- **Zenhub script:** `create_release()` hardcodes the dates 2024-01-01 to 2024-01-02, so it is stale. It parses issue IDs with a brittle regex (`\d+ -`), asserts on status codes instead of raising HTTP errors, and the timeout of 60000 is likely meant as ms but may be read as seconds.

## Members

- lear: legal-api/migrations/versions/01b28a2bb730_furnishings.py
- lear: legal-api/migrations/versions/026f42f4f654_add_custodialoffice_to_office_types.py
- lear: legal-api/migrations/versions/0b2af7f762bb_request_tracker_admin.py
- lear: legal-api/migrations/versions/0c792224fe11_change_field_type.py
- lear: legal-api/migrations/versions/0fb2ae5711ed_.py
- lear: legal-api/migrations/versions/1215735c3563_.py
- lear: legal-api/migrations/versions/1400cc212014_request_tracker_change.py
- lear: legal-api/migrations/versions/176f983485c8_.py
- lear: legal-api/migrations/versions/1a8c89b722e2_.py
- lear: legal-api/migrations/versions/1ba027b074a5_add_idp_userid_to_users.py
- lear: legal-api/migrations/versions/1f01b9303b81_.py
- lear: legal-api/migrations/versions/1fcdb213657d_add_order_details_column.py
- lear: legal-api/migrations/versions/2afccb4603ec_restoration.py
- lear: legal-api/migrations/versions/2dedf50a17ef_added_court_order_columns_to_filings_.py
- lear: legal-api/migrations/versions/2e29ebe9a830_removing_party_tax_id.py
- lear: legal-api/migrations/versions/2e986c1d4de6_.py
- lear: legal-api/migrations/versions/33501a263f32_sp_gp.py
- lear: legal-api/migrations/versions/361b51b824c0_.py
- lear: legal-api/migrations/versions/441a5e6cf682_.py
- lear: legal-api/migrations/versions/442829649a2a_.py
- lear: legal-api/migrations/versions/4ee6f0abb797_.py
- lear: legal-api/migrations/versions/508c7466b2af_misc_configurations_table_updates.py
- lear: legal-api/migrations/versions/5238dd8fb805_.py
- lear: legal-api/migrations/versions/52553d4d6309_.py
- lear: legal-api/migrations/versions/54a3fc54a2cf_.py
- lear: legal-api/migrations/versions/5e1faa8636c0_.py
- lear: legal-api/migrations/versions/6b65b40a5164_add_revocation_to_dc_credentials.py
- lear: legal-api/migrations/versions/7575af513efb_.py
- lear: legal-api/migrations/versions/78ddb7f6f8b5_add_locked_flag_to_filings.py
- lear: legal-api/migrations/versions/7c86cc916b5c_.py
- lear: legal-api/migrations/versions/8148a25d695e_change_field_type.py
- lear: legal-api/migrations/versions/860bb6075dde_.py
- lear: legal-api/migrations/versions/86d8aca36208_request_tracker.py
- lear: legal-api/migrations/versions/89fe33f436c1_add_restoration_approval_type_registrar_.py
- lear: legal-api/migrations/versions/8c74427a6c0e_document_table.py
- lear: legal-api/migrations/versions/8fef256bf5d7_add_middle_name_to_users.py
- lear: legal-api/migrations/versions/9147d4bc9939_.py
- lear: legal-api/migrations/versions/92c4974ce96f_.py
- lear: legal-api/migrations/versions/94586877d4bc.py
- lear: legal-api/migrations/versions/94c2a694d51f_.py
- lear: legal-api/migrations/versions/9741616ab6d7_.py
- lear: legal-api/migrations/versions/9a9ac165365e_cco.py
- lear: legal-api/migrations/versions/9b5c719f32ef_.py
- lear: legal-api/migrations/versions/a8f42b830d86_.py
- lear: legal-api/migrations/versions/ad3ef106696c_.py
- lear: legal-api/migrations/versions/b14f77400786_xml_payloads.py
- lear: legal-api/migrations/versions/b18741f7c4d3_technical_filing_corrections.py
- lear: legal-api/migrations/versions/b826412a6a65_.py
- lear: legal-api/migrations/versions/b9165c3187fc_.py
- lear: legal-api/migrations/versions/b9f84f7a7c44_add_login_source_to_users.py
- lear: legal-api/migrations/versions/bb9f4ab856b1_remove_group_identifier_from_furnishings.py
- lear: legal-api/migrations/versions/bddd732a9269_index_by_idp_guid.py
- lear: legal-api/migrations/versions/bf8d4391745e_cleanup_document_table.py
- lear: legal-api/migrations/versions/bf94a1b46804_.py
- lear: legal-api/migrations/versions/c17d77b30bdb_.py
- lear: legal-api/migrations/versions/c212a141600c_request_tracker_change_party.py
- lear: legal-api/migrations/versions/c4732cd8abfd_jurisdiction.py
- lear: legal-api/migrations/versions/d21f6be7bd21_submitter_roles.py
- lear: legal-api/migrations/versions/d9e21a1b82ca_add_sent_to_gazette.py
- lear: legal-api/migrations/versions/da43f7bef692_.py
- lear: legal-api/migrations/versions/e6ff12b18bef_.py
- lear: legal-api/migrations/versions/e85053684b3c_.py
- lear: legal-api/migrations/versions/ec9652171563_review.py
- lear: legal-api/migrations/versions/ecfeee53451a_digital_credentials.py
- lear: legal-api/migrations/versions/ed12492e70f8_.py
- lear: legal-api/migrations/versions/f3fb008e7b83_.py
- lear: legal-api/migrations/versions/f4f654026f42_businessoffice_office_types.py
- lear: legal-api/migrations/versions/f4f93ea8887e_add_configurations_table.py
- lear: legal-api/migrations/versions/f978e34aa8bb_add_foreign_jurisdiction_region_.py
- sbc-pay: releases/util.py
