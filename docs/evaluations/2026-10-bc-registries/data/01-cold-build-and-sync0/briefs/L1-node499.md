<!-- level 1, node 499, children [74, 80, 81, 105, 123, 143, 144, 208, 235, 236, 525, 526, 527] -->

**What this is:** About 100 condensed fragments of SchemaSpy-generated documentation (dot 2.38 DOT diagrams, SchemaSpy 6.0.0 HTML, XML metadata, and Alembic notes). They cover a BC Registries-style PostgreSQL system with two main Alembic-managed schemas: an auth/org schema and a payments/fee schema. A third, older users/actions/affiliation schema also appears. Nearly every table shows 0 rows, so these are schema-only or dev snapshots.

## Schemas

**1. Auth / org schema (public, 12 tables; PostgreSQL 11.2)**
- **Hub:** `org` (PK `id`, `name` varchar 250). It has FKs to:
  - `user`: `created_by` and `last_modified_by`
  - `contact`: `contact1` and `contact2`
  - `org_type`: `type_code`
  - `org_status`: `status_code`
  - `payment_type`: `preferred_payment`
- **People and identity:**
  - `user`: serial `id`, unique `keycloak_guid` (uuid), username, email, first_name, last_name, roles, created, modified.
  - `entity`: `business_identifier` (unique) and `pass_code`.
  - `contact`: address and phone fields, plus `entity_id`.
- **Link tables:**
  - `membership` → user, org, membership_type
  - `affiliation` → entity, org, user (`created_by`)
  - `contact_link`: a junction table with four nullable FKs to contact, entity, user and org
- **Lookup tables:** `org_type`, `org_status`, `payment_type` and `membership_type`. Each has PK `code` varchar 15 and `desc` varchar 100.
- **Row counts:** `contact`, `entity` and `alembic_version` have 1 row. The rest have 0.
- **Anomalies page:**
  - `affiliation` has no index.
  - `alembic_version` is a single-column table.
  - `org` has incrementing column names.
- **Migration:** Alembic `e7c262b6f986` (revises `c6e4754d28cf`) adds the `org_types` rows `STAFF` and `SBC_STAFF`.

**2. Payments / fee schema (14–15 tables)**
- **Lookups:**
  - `status_code`: 8 rows (7 in some diagrams)
  - `corp_type`, `payment_method`, `payment_system` and `alembic_version`: 1 row each
  - `fee_code`: 7 rows, with `amount`
  - `filing_type`: 11 rows
- **Central fee table:** `fee_schedule` (11 rows, PK `fee_schedule_id`). It has FKs to `filing_type`, `corp_type` and `fee_code`, a unique constraint on the three codes, and `fee_start_date` and `fee_end_date`.
- **Billing chain (all 0 rows):**
  - `payment_account` (FKs `corp_type_code`, `payment_system_code`) → `invoice`.
  - `invoice` has FKs `payment_id`, `invoice_status_code` and `account_id`, and money fields `total`, `paid` and `refund`.
  - `invoice` is the parent of `payment_line_item` (also → `fee_schedule`) and `receipt`.
  - `payment` has FKs to `payment_system`, `payment_method` and `status_code`.
  - `payment_transaction` has a uuid PK, FKs to `payment` and `status_code`, start and end timestamps, and system URLs.
- **Older or variant tables:** `fee_item` (int4 fee fields) and `transaction` (→ invoice, status_code) appear in some diagrams only.
- **Constraints:** 16 FKs, all restrict-delete.
- **Migration:** Alembic `v824f5ef280c6` (revises `e65cc8ab51cc`) inserts product code `CA_SEARCH`.

**3. Older users / actions schema**
- `users` (PK `user_id`, `username`, `passwd`, Keycloak `sub` and `iss`, `creation_date`) has an FK to `user_type`.
- `action_log` has FKs to `users` and `action`.
- `affiliation` is a hub with FKs to `users`, `affiliation_business` and `affiliation_status`.
- `users` here is separate from the org schema's `user`.

**4. Unrelated outlier**
- A Postman GET of `/api/v1/businesses/CP0002098/office` returned 200 OK. The server was Werkzeug on Python 3.6.5, API `colin_api/0.1.0a0.dev`, dated 15 Jul 2019.

## Fragment types
- **DOT diagrams:** `rankdir=RL`, `arrowtail=crowodot`, `dir=back`. They are 1-degree or 2-degree views centered on one table, and many are truncated with `...`.
- **HTML pages:** table pages, FK listings, relationship viewers with image maps and shared AdminLTE/Bootstrap 3 boilerplate. Several are empty skeletons.
- **XML metadata:** SchemaSpy XML, with the `<tables>` content missing in places.

## Caution:
- **Direction:** `dir=back` and `rankdir=RL` make arrows look reversed. The crow's-foot end is the child (FK) side.
- **Truncation:** Many diagrams and pages are cut off, with `...` or "N >" markers, so column and FK lists are partial. Some FK boxes are empty even though they claim 16–18 constraints.
- **Row counts:** These are snapshots, mostly 0, and some are inconsistent between fragments (`status_code` 7 vs 8). Don't infer production usage.
- **Restrict deletes:** Every FK blocks deleting a parent while children exist, so cleanup and migrations must run in dependency order.
- **Nullable FKs:** `contact_link` (all four FKs) and `org.contact1` and `contact2` are nullable, so rows can be orphaned or unlinked.
- **Money as float8:** Money columns (`float8[17,17]`) are imprecise, and there are no check constraints.
- **Possible type mismatches:**
  - `action_log.action_code` (varchar 20) vs `action.action_code` (varchar 50).
  - `payment_transaction.payment_id` (int4) vs the `payment.id` type, which is unspecified.
- **Security:**
  - `users.passwd` is a plain varchar, probably unhashed.
  - `entity.pass_code` may be stored in plaintext.
- **Redundant indexes:** `org_type` and `payment_type` have duplicate unique indexes on `code`, and `users` has duplicate `username` indexes.
- **Documentation artifacts:**
  - `uuid[2147483647]` and `[29,6]` or `[35,6]` are SchemaSpy display notation.
  - Port labels like `code.type` and `elipses` are not real columns.
  - `desc` is a reserved word and must be quoted.
- **Portability:** Image paths use Windows `.\schemaspy/images/` backslashes, and the HTML uses relative `../diagrams/*.png` paths with hardcoded image-map coordinates. Both break if moved or regenerated.
- **Generated output:** Don't hand-edit it, because edits are lost on regeneration. Malformed markup, such as `</TABLE>>`, comes from truncation.
