<!-- leaf 84, 29 members -->

This set is a collection of condensed Jupyter notebooks from the BC Registries "lear" legal-API repo. They are test and ops tooling for loading, creating and repairing business filings, and for calling the services around them: Colin, Namex, auth, payment and Minio. It covers shared helper notebooks, test-data loaders, end-to-end creation flows and one-off maintenance scripts.

## Shared utility and config notebooks

- **Environment config:** The Legal API notebook sets up the DB (`host.docker.internal:5353`, db `lear`), the dev service URLs, NATS and Flask app init. It also has `stop_on_false`/`stop_on_true` and `get_latest_correction_filing`.
- **Service clients:**
  - COLIN API utils: `create_filing`, `get_filing_events_for_corp` and related functions.
  - LEGAL API utils: `get_lear_token`, `update_in_good_standing`, `remove_voluntary_dissolution_filing` and others.
  - Auth API utils: `get_auth_token`, `affiliate_nr_to_account`, `affiliate_nr_to_entity`, `get_identifier_from_affiliations`, `get_account_by_affiliated_identifier`, `get_user_by_username`.
  - NAMEX API utils: `get_namex_token`, `create_nr`, `create_nr_payment`, `update_nr_state`, `update_nr_name` and others.
- **Business-state and payment helpers:** `reset_vd_data`, `create_filing_payment_transaction` and `submit_filing_invoice`.
- **Factories and payloads:**
  - Filing factories: `factory_completed_filing`, `factory_pending_filing`, `factory_pending_IA_filing` and `factory_file_upload`.
  - IA payloads: `factory_empty_ia_payload`, `factory_coop_ia_payload` and `factory_ben_ia_payload` (cut off).
  - Special resolution and invoice: `factory_empty_coop_special_resolution_payload`, `factory_empty_invoice_payload` and `create_invoice`.
  - Name Request payloads: `factory_create_nr_payload`, `factory_create_nr_payment_payload` and `factory_update_nr_name_payload`.
- **Small standalone helpers:** `get_element_type_from_label` (NAICS labels) and the `LocalTimezone`/`USTimeZone` classes (Eastern, Central, Mountain, Pacific).

## Test-data loaders (COOP)

These notebooks build test businesses and filings in the TEST database.
- **Incorporation-application loaders:** Create `RegistrationBootstrap` records and incorporation application filings, validate the ledger, then register the entity and affiliations with auth-dev. Identifiers vary: `CP0000842` with bootstrap `T123456789`, and an earlier variant with bootstrap `T22222212`.
- **`CP0000840` loader:** Builds incorporation application, alteration, change of address and change of directors filings.
- **Filing-type batch:** Repeats one pattern for annualReport, conversion, specialResolution, dissolution, transition, courtOrder and registrarsNotation.
- **Variant filings:** Registrar's Order, Annual Report with bundled legalFilings, Correction, Special Resolution with 5 comments, F.18, and paper-only filings (incorporation application, alteration), plus an alteration with a court order.
- **Alteration pair with auth flow:** Completed and pending alteration cells, followed by the OIDC token, entity and affiliation calls.

## End-to-end creation flows

- **Create NRs:** Make COOP/CORP Name Requests (BC or CP) through payment and approval. The browser payment step is manual.
- **Create COOP change of name:** A special resolution filing and invoice. It needs an NR, auth and lear tokens, and the account lookup.
- **Create BEN / COOP from a Name Request:** Two near-identical flows, one for BEN and one for CP. Each follows this sequence:
  1. Affiliate the NR.
  2. Create a draft IA.
  3. Submit the IA.
  4. Pay.
  5. Look up the identifier through auth.
  6. Optionally update good standing.
- **Load COOP to Lear:** Pulls events from the Colin API, creates the filing, queues it by hand with `q_cli.py`, applies the remaining events, and registers the entity with auth.

## Maintenance and data scripts

- **Fix alteration metadata:** Backfills `_meta_data` (legal types and names) for completed alterations.
- **Backfill Lear users:** Fills in missing first name, last name and email from the auth API.
- **Good standing and VD reset:** Calls `update_in_good_standing` and `reset_vd_data`, with an optional rollback.
- **NAICS import generator:** Produces alembic output from the StatsCan CSVs for 2022, version 1.
- **Notebook metadata fragment:** Records Python 3.9.10 as the kernel version.

Caution:
- **Hardcoded credentials and IDs:** Two notebooks embed the base64 client credentials for `entity-notebook-service-account` (`170e88e8-0a57-4d3c-b7f2-770cc2e1456f`). Account IDs (668, 2596, 446) are also hardcoded. Move the credentials to env vars or a secret store and don't commit them.
- **Environment mismatch:** `DEPLOYMENT_ENV=production` is paired with `*-dev` endpoints. The client IDs and secrets are blank and must be filled in before use.
- **Likely bugs:**
  - `get_identifier_from_affiliations()` filters on the undeclared `approved_nr_name`, not its `nr_name` parameter.
  - `update_in_good_standing()` looks backwards: in good standing sets the founding date to now, otherwise to two years ago.
  - Dissolution and Transition both use `SPECIAL_RESOLUTION` content, probably a copy-paste error.
  - One loader uses `T12121212` in API calls but `T22222212` as the bootstrap identifier, and its `business` object is never created.
  - `create_nr()` and `create_nr_payment()` rely on `create_nr_json` and `create_payment_json`, which must already be defined.
- **Silent failures:**
  - `suppress(IndexError, KeyError, TypeError)` in the alteration fix skips missing name data without logging.
  - `get_element_type_from_label` returns `None` for unknown labels, and matching is case- and whitespace-sensitive.
- **Overwrite risk:** The user backfill updates all three fields when any one is truthy. This can replace existing names with `None`.
- **Manual and timing steps:**
  - The Colin load needs a hand-run `./q_cli.py -f {filing.id}`.
  - NR payment is completed in the browser, and an error dialog afterward is expected.
  - Allow a few minutes after saving a draft and after payment before the next step.
  - Payment is automatic only with `entity-notebook-service-account`.
  - Good-standing and VD operations need a lear DB port-forward.
- **Ordering and dependencies:**
  - Notebooks rely on prior runs, such as `default-bcr-business-setup-TEST`, for `FILING_HEADER`, `INCORPORATION` and the URL constants.
  - `remove_voluntary_dissolution_filing` must clear `_payment_token` before deleting, or the filing stays locked.
  - `flag_modified` is required for JSON `_meta_data` changes.
  - The `assert identifier` cell crashes if the identifier is unset.
- **Fragile test data:**
  - The PDF path `/workspaces/lear/tests/data/data/pdfs/valid.pdf` is hardcoded.
  - File sizes (20624), timestamps and NR test values are hardcoded.
  - `factory_coop_ia_payload` mixes BCREGTEST names with a real-looking Maple Ridge address, so check it for production data.
  - Special resolution hardcodes `legalType: 'CP'`.
  - Applicant `emailAddress` is `None` where the other fields use empty strings.
- **Process and runtime quirks:**
  - `skip_status_listener` bypasses normal status setting.
  - `freeze_time` wraps transaction creation, so transaction timestamps are frozen too.
  - `TIMEOUT` is read from the environment as a string.
  - Colin `corp_num` is trimmed to 7 characters only for COMP.
  - `LocalTimezone.fromutc` can be wrong for historical dates.
  - The notebook metadata Python version (3.9.10 or 3.9.7) may not match the running kernel.
  - The NAICS generator needs `iopub_data_rate_limit` raised and opens the structure file twice.
  - The BEN/COOP creation notebooks and the loaders create incomplete filings, so downstream integrations such as receipts won't work.

## Members

- lear: tests/data/Alterations_update_metadata/fix_alteration_filing_metadata.ipynb
- lear: tests/data/XXXX_load_COOP-CPXXXXX.ipynb
- lear: tests/data/common/auth_api_utils.ipynb
- lear: tests/data/common/colin_api_utils.ipynb
- lear: tests/data/common/legal_api_utils.ipynb
- lear: tests/data/common/legal_api_utils.ipynb
- lear: tests/data/common/legal_api_utils_test_data.ipynb
- lear: tests/data/common/legal_api_utils_test_payload_data.ipynb
- lear: tests/data/common/legal_api_utils_test_payload_data.ipynb
- lear: tests/data/common/naics_utils.ipynb
- lear: tests/data/common/namex_api_utils.ipynb
- lear: tests/data/common/namex_api_utils_test_payload_data.ipynb
- lear: tests/data/common/utility.ipynb
- lear: tests/data/default-bcr-business-setup-TEST.ipynb
- lear: tests/data/ledger/Ledger_Load_COOP_Test_Data-ONLY_IA-PENDING.ipynb
- lear: tests/data/ledger/Ledger_Load_COOP_Test_Data-ONLY_IA.ipynb
- lear: tests/data/ledger/Ledger_Load_COOP_Test_Data.ipynb
- lear: tests/data/ledger/Ledger_Load_COOP_Test_Data.ipynb
- lear: tests/data/ledger/Ledger_Load_COOP_Test_Data.ipynb
- lear: tests/data/ledger/Ledger_Load_COOP_Test_Data.ipynb
- lear: tests/data/misc/backfill_user_data.ipynb
- lear: tests/data/naics/create_alembic_import_data_from_naics_csvs.ipynb
- lear: tests/data/nr/XXXX_create_nr_XXXXX.ipynb
- lear: tests/data/special_resolution/XXXX_create_coop_change_of_name_sr_XXXXX.ipynb
- lear: tests/data/special_resolution/XXXX_create_coop_change_of_name_sr_XXXXX.ipynb
- lear: tests/data/voluntary_dissolution/XXXX_create_ben_voluntary_dissolution_XXXXX.ipynb
- lear: tests/data/voluntary_dissolution/XXXX_create_ben_voluntary_dissolution_XXXXX.ipynb
- lear: tests/data/voluntary_dissolution/XXXX_create_coop_voluntary_dissolution_XXXXX.ipynb
- lear: tests/data/voluntary_dissolution/XXXX_create_coop_voluntary_dissolution_XXXXX.ipynb
