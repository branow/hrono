<!-- level 1, node 499, children [53, 74, 80, 81, 105, 123, 143, 144, 173, 208, 235, 236, 373] -->

**Overall:** These briefs cover SchemaSpy-style documentation (Graphviz DOT, HTML pages and XML, mostly dot 2.38 or SchemaSpy 6.0.0 on Windows) of a BC Registries-style system on PostgreSQL 11.x. The system has an auth/org database and a payments database, both Alembic-managed. One brief covers the Python/Flask Pay API code. Two small items are unrelated: a Postman request and an Alembic migration note. Nearly every table shows 0 rows, so these are schema-only dev or test snapshots.

## Domains and tables

### 1. Payments/fees database (14–15 tables)
- **Lookup tables.** All have PK `code` (varchar 10, except `status_code` at 20).
  - `corp_type` (1 row)
  - `fee_code` (7 rows; float8 `amount`)
  - `filing_type` (11 rows)
  - `payment_method` (1 row)
  - `payment_system` (1 row)
  - `status_code` (7 or 8 rows; 8 in most sources)
- **`fee_schedule`** (11 rows, serial PK `fee_schedule_id`)
  - FKs go to `filing_type_code`, `corp_type_code` and `fee_code`. There is a composite unique constraint on those three.
  - `fee_start_date` is required and `fee_end_date` is nullable.
  - `payment_line_item` and `fee_item` reference it.
- **Billing chain.**
  - `payment_account` (FKs `corp_type_code` and `payment_system_code`) → `invoice`.
  - `invoice` has FKs `payment_id`, `invoice_status_code` and `account_id`. Its money fields are `total` (required), `paid`, `refund` and `payment_date`.
  - `invoice` → `payment_line_item`, `fee_item`, `receipt` and `transaction`.
  - `payment` (FKs to system, method and status) → `invoice` and `payment_transaction`.
  - `payment_transaction` has a uuid PK, FKs `status_code` and `payment_id`, start/end times and system URLs.
  - `payment_line_item` carries float8 fee columns. `fee_item` carries int4 fee columns.
- **Housekeeping.** `alembic_version` (`version_num` varchar 32, 1 row).
- **Migration note.** Alembic `v824f5ef280c6` (revises `e65cc8ab51cc`) adds product code `CA_SEARCH`, which is internal, hidden and system-admin only.

### 2. Org/identity database (11–12 tables)
- **`user`**
  - PK `id`.
  - Unique non-null `keycloak_guid` (uuid).
  - `username`, `email`, `first_name`, `last_name` and `roles`.
- **`org`**
  - FKs to `user` (`created_by` and `last_modified_by`).
  - FKs to `contact` (`contact1` and `contact2`).
  - FKs to `org_type` (`type_code`), `org_status` (`status_code`) and `payment_type` (`preferred_payment`).
- **Link tables.**
  - `membership` → `user`, `org`, `membership_type`
  - `affiliation` → `user`, `entity`, `org`
  - `contact_link`: junction table to `contact`, `entity`, `user` and `org`. All its FKs are nullable.
- **`entity`:** `business_identifier` (unique) and `pass_code`.
- **`contact`:** address and phone fields, with a nullable `entity_id` FK. It has 1 row.
- **Lookup tables.** `org_type`, `org_status`, `payment_type` and `membership_type` all use PK `code` varchar 15 plus `desc` varchar 100.
- **Migration note.** Alembic `e7c262b6f986` (revises `c6e4754d28cf`) adds `org_types` rows `STAFF` and `SBC_STAFF`.

### 3. Older auth schema (`users` / action / affiliation)
- **User and action tables.**
  - `users`: PK `user_id` serial; FK `user_type_code` → `user_type`; Keycloak `sub` and `iss`; `passwd`.
  - `action` and `action_log` (FKs `user_id` and `action_code`).
- **Affiliation tables.**
  - `affiliation` has FKs to `affiliation_status`, `affiliation_business` and `users`.
  - `affiliation_business` has `business_id`, `corp_num` and `corp_type`.
- **Source:** PostgreSQL 11.1 and 11.2 exports and SchemaSpy pages (Jun and Aug 2019).

### 4. BC Registries Pay API code
- **Persistence models.**
  - `Invoice` and `Payment` use an explicit `include_properties` whitelist.
  - `Invoice.search_purchase_history` is a multi-join query that raises `BusinessException` above 60000 records.
- **Serialization.** `InvoiceSchema`, `InvoiceSearchModel`, `RoutingSlipSchema` and a cattrs `Converter`.
- **Endpoints.** `POST /<account_number>/payments/queries` and `/payments/reports`.
- **Payment-system services.** The `PaymentSystemService` base class, CFS/PayBC, `DirectPayService`, and the CGI/EJV and BCOL integrations.
- **Domain services.** `DistributionCode`, `FeeSchedule`, Invoice, Payment, `PaymentAccount` (EFT/PAD rules), `PaymentService`, `PaymentTransaction` and Statements.
- **Test helper.** `create_linked_data`.

### 5. Standalone
- A Postman `GET /api/v1/businesses/CP0002098/office` returned 200 from `colin_api/0.1.0a0.dev` on Werkzeug 0.15.4 (15 Jul 2019).

## Patterns
- **Foreign keys.** Every FK is restrict/no-cascade, so deletes must run child-first.
- **Keys.** Lookup tables use a `code` PK. Others use a serial `id`, except uuid for `payment_transaction` and Keycloak GUIDs on users.
- **Page boilerplate.** The HTML fragments are AdminLTE/Bootstrap 3 pages (navbar, 1°/2° diagram image maps, empty FK and check-constraint boxes) with no data of their own.

## Caution
- **Reading DOT diagrams.** `rankdir=RL` with `dir=back` and `arrowtail=crowodot` inverts the visual arrows. Read each edge as FK child → parent. Port names such as `code.type` and labels like `elipses` are rendering artifacts, not columns. `[29,6]` is precision, not an array.
- **Incomplete sources.** Several DOT, XML and HTML fragments are truncated, with "..." marking hidden columns. Some are empty stubs, with FK boxes claiming 16–18 constraints but showing no rows. Do not infer a full schema from them.
- **Conflicting facts.**
  - `status_code` shows 7 or 8 rows.
  - `entity` shows "1 row" with 3 columns.
  - `affiliation` shows 0 rows.
  - The row counts are a snapshot and may be stale.
- **Schema oddities.**
  - Money is stored as float8, and `digits=17` is meaningless.
  - `action_log.action_code` is varchar 20 but references varchar 50.
  - `payment_transaction.payment_id` is int4, but the type of `payment.id` is not shown.
  - `uuid[2147483647]` is a doc artifact.
  - `org_type` and `payment_type` have redundant unique indexes on `code`.
  - `users` has two `username` indexes.
  - `desc` is a reserved word and must be quoted.
  - `users.passwd` and `entity.pass_code` may be stored in plaintext.
  - The invoice, payment and line-item "stubs" may be placeholders.
- **Portability.** Image paths are hardcoded Windows-style (`.\schemaspy/images/`) and break on Unix or the web. Navbar links use `../` and need the right directory depth. The `nextval(...::regclass)` defaults are PostgreSQL-specific.
- **Generated output.** The files are generated and will be overwritten. Image-map coordinates are hardcoded, and the markup has duplicate ids and a malformed `</TABLE>>`.
- **Pay API code hazards.**
  - New columns won't map until they are added to the `include_properties` whitelist.
  - Both `InvoiceSchema` and `InvoiceSearchModel` map PAID to COMPLETED and strip business identifiers that start with 'T'.
  - Several `PaymentSystemService` methods are stubs.
  - The sandbox decorators hardcode argument positions.
  - `update_transaction` marks an invoice PAID even when the payment is short.
  - `publish_status` and `_publish_queue_message` swallow exceptions.
  - Consolidation does not work for EFT.
  - `validate_bank_account` returns `bank_number` for both the number and name keys.
  - `_calculate_fees` charges service fees only once per request.
  - Some functions depend on `@user_context` injection.
