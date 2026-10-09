<!-- leaf 30, 13 members -->

**What this is:** A set of notes on byte-encoded (decimal ASCII) ZIP/CSV blobs. They look like fixtures or snapshots of a database export, probably for a business-registry or corporate-filings system. The business_id 3722 recurs across them. Each blob decodes to a ZIP (PK header) holding one or more CSVs under `exports/`. Most are truncated mid-stream.

**Groupings present**

1. **Parties and addresses**
   - `exports/parties.csv` and `exports/parties_version.csv`: id, party_type, first_name, middle_initial, last_name, title, organization_name, delivery_address_id, mailing_address_id. The version file adds transaction_id, end_transaction_id and operation_type.
   - `exports/addresses.csv` and `exports/addresses_version.csv`: id, address_type, street, street_additional, city, region, country, postal_code, delivery_instructions. The non-version file also has business_id and office_id. Sample rows are a Montréal mailing address (id 36540) and TEST/TESTER with address_ids 3654.
   - `exports/parties_version-addresses_version.csv` and `exports/parties-addresses.csv`: the same address columns. They are bundled with party data, and one sample is the Pickering, ON mailing address.
   - `exports/party_roles_version.csv`: id, role, appointment_date, cessation_date, business_id, party_id, plus the versioning columns. Sample row: 11084, completing_party, 3722.

2. **Share structure**
   - `exports/share_classes.csv`: id, name, priority, max_share_flag, max_shares, par_value_flag, par_value, currency, special_rights_flag, business_id. Sample: 617, "sets Shares", CAD.
   - `exports/share_series.csv` and `share_series_version.csv`: id, name, priority, max_share_flag, max_shares, special_rights_flag, share_class_id. The version file adds transaction ids.
   - `share_classes_versions.c…` is cut off.

3. **Aliases:** `exports/aliases.csv` and `exports/aliases_version.csv`: id, alias, type, business_id, plus transaction ids and operation_type in the version file. Sample: 56, TESTER, TRANSLATION, 3722.

4. **Offices and filings**
   - `exports/offices.csv` and `exports/offices_version.csv`: id, office_type, deactivated_date, business_id, plus versioning columns. Rows 4176 (recordsOffice) and 4177 (registeredOffice), both for business 3722.
   - `exports/filings.csv`: only the start of its header is visible.

**Patterns across all of them**
- Each table appears as a plain `X.csv` and an `X_version.csv`. The version file adds `transaction_id`, `end_transaction_id` and `operation_type`, which looks like SQLAlchemy-Continuum-style history tracking.
- Flags are stored as t/f.
- Timestamps carry a timezone offset (e.g. `-07`).

Caution:
- The data is raw decimal byte arrays, not human-editable text. You have to decode it to bytes, and for ZIP content also decompress it, before reading or changing anything.
- Most blobs are truncated mid-stream, so the headers and rows listed above are partial. Get the exact column order and field names from a full decode.
- UTF-8 multibyte sequences (e.g. 195,137 and 195,169 for É and é) can corrupt if you handle them at byte level. Decode to a UTF-8 string first.
- Don't parse the data as plain text. Commas (44) and newlines (10) in the array are ASCII values, not array delimiters.
- Timestamps carry a timezone offset, and t/f flags are booleans.

## Members

- lear: legal-api/tests/postman/legal-dev.postman_environment.json
- lear: legal-api/tests/postman/legal-dev.postman_environment.json
- lear: legal-api/tests/postman/legal-dev.postman_environment.json
- lear: legal-api/tests/postman/legal-dev.postman_environment.json
- lear: legal-api/tests/postman/legal-dev.postman_environment.json
- lear: legal-api/tests/postman/legal-dev.postman_environment.json
- lear: legal-api/tests/postman/legal-dev.postman_environment.json
- lear: legal-api/tests/postman/legal-dev.postman_environment.json
- lear: legal-api/tests/postman/legal-dev.postman_environment.json
- lear: legal-api/tests/postman/legal-dev.postman_environment.json
- lear: legal-api/tests/postman/legal-dev.postman_environment.json
- lear: legal-api/tests/postman/legal-dev.postman_environment.json
- lear: legal-api/tests/postman/legal-dev.postman_environment.json
