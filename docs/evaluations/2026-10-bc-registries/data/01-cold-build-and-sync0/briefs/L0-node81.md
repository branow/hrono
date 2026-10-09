<!-- leaf 81, 16 members -->

These condensations are mostly SchemaSpy-generated Graphviz (dot 2.38, Windows 10) diagrams of one small user, action and affiliation schema. Most are `rankdir="RL"` DOT output with `arrowtail=crowodot`, `dir=back` edges. One Postman request and one `alembic_version` diagram are unrelated to that schema.

## Core schema: users and actions
- **`users`**: PK `user_id` (serial[10]). Columns: `username`, `passwd`, `firstname`, `lastname`, `display_name`, `email`, `user_source`, `sub`, `iss`, `creation_date` (timestamptz). FK `user_type_code` → `user_type`. Many diagrams truncate its columns with "...", and in the 7-table view it has a bold `BORDER="2"` frame as the central table.
- **`user_type`**: PK `user_type_code` (varchar[20]), `user_type_name` (varchar[50]), `full_desc` (varchar[250]).
- **`action`**: PK `action_code` (varchar[50]), `action_name` (varchar[100]), `action_type` (varchar[50]), `path` (varchar[500]).
- **`action_log`**: PK `log_id` (serial[10]). FKs `user_id` → `users` and `action_code` → `action`. Other columns: `target_id` (int4), `target_type` (varchar[50]), `action_date` (date), `memo` (varchar[250]).

## Affiliation cluster
- **`affiliation`**: PK `affiliation_id` (serial[10]). FKs `affiliation_status_code` (varchar[5]), `business_id` (int4) and `user_id` (int4). Date and audit columns: `effective_start_date`, `effective_end_date`, `creation_date`, `last_access_date`, `created_by_userid`, `modified_by_userid`.
- **`affiliation_business`**: PK `business_id` (serial[10]), `corp_num` (varchar[20]), `corp_type` (varchar[20]).
- **`affiliation_status`**: PK `status_code` (varchar[20]), `status_name` (varchar[200]).
- `affiliation` is the hub, linking to `users`, `affiliation_business` and `affiliation_status`.

## Variations of the same diagram
The same tables are redrawn at different scopes:
- **1-degree:** `user_type` ← `users`.
- **2-degree, partial:** `action` ← `action_log`, or `affiliation` with its three neighbours.
- **2-degree, full:** 4-table, 5-table and 7-table views of the whole schema.

Nearly every table shows 0 rows.

## Outliers
- **Payment/fee schema:** `corp_type` (PK `code`, 1 row), `fee_schedule` (11 rows) and `payment_account` (0 rows). Both child tables reference `corp_type` through `corp_type_code`.
- **`alembic_version`:** a single `version_num` varchar[32] PK column holding 1 row, which is the Alembic migration tracker.
- **Postman request:** `GET {{url}}/api/v1/businesses/CP0002098/office` returned 200 OK with JSON. The server was Werkzeug/0.15.4 on Python 3.6.5, API `colin_api/0.1.0a0.dev`, dated 15 Jul 2019. CORS allows `*` for GET, OPTIONS and HEAD.

## Caution:
- **Empty tables:** nearly every table shows 0 rows, so foreign-key cardinality is unverified. Row counts may reflect a template or snapshot rather than live data.
- **Truncated columns:** "..." marks columns collapsed in the diagram, so the full column lists are in the linked HTML.
- **Plaintext password:** `users.passwd` is a `varchar[100]` column, which suggests plaintext storage and is a security risk.
- **Non-standard edge syntax:** `arrowtail="crowodot"` is not standard Graphviz and may render unexpectedly.
- **Reversed edge direction:** `dir=back` flips the visual direction of the edges.
- **Odd edge ports:** edge ports such as `business_id.type` and `.elipses` point at the type cell or an ellipsis cell, not the column itself.
- **Windows paths:** image URLs use backslashes (`.\schemaspy/images/`), which break on macOS and Linux.
- **Postman template:** the Content-Type header is disabled in the request but present in the response, which suggests a template rather than an actual call.
- **Missing detail:** `affiliation_business` is shown as a lookup table, but the diagram gives no detail on it.

## Members

- sbc-pay: docs/databse-schema/diagrams/action.1degree.dot
- sbc-pay: docs/databse-schema/diagrams/action.2degrees.dot
- sbc-pay: docs/databse-schema/diagrams/action_log.1degree.dot
- sbc-pay: docs/databse-schema/diagrams/action_log.2degrees.dot
- sbc-pay: docs/databse-schema/diagrams/affiliation.1degree.dot
- sbc-pay: docs/databse-schema/diagrams/affiliation.2degrees.dot
- sbc-pay: docs/databse-schema/diagrams/affiliation_business.1degree.dot
- sbc-pay: docs/databse-schema/diagrams/affiliation_business.2degrees.dot
- sbc-pay: docs/databse-schema/diagrams/affiliation_status.1degree.dot
- sbc-pay: docs/databse-schema/diagrams/affiliation_status.2degrees.dot
- sbc-pay: docs/databse-schema/diagrams/corp_type.1degree.dot
- sbc-pay: docs/databse-schema/diagrams/orphans/alembic_version.1degree.dot
- sbc-pay: docs/databse-schema/diagrams/user_type.1degree.dot
- sbc-pay: docs/databse-schema/diagrams/user_type.2degrees.dot
- sbc-pay: docs/databse-schema/diagrams/users.1degree.dot
- sbc-pay: docs/databse-schema/diagrams/users.2degrees.dot
