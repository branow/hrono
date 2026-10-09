<!-- leaf 334, 12 members -->

**Overall:** These condensations describe the `data_reset_tool` project, a Flask + Postgres test-fixture service from the BC Registries (Province of British Columbia) codebase. It snapshots and restores business data (businesses, addresses, directors, filings) for repeatable test scenarios. The condensations cover its packaging, configuration, app factory, and import/export/delete endpoints. Several are empty placeholder modules.

## Groupings

**1. Product overview and API surface**
- The tool exports and imports business data as JSON or Excel. It can reset a single business or all records, and `rebuild=true` drops the schema first.
- Routes: GET `/api/fixture/export/{business_id|all_YES_IM_SURE}[/excel]` and POST `/api/fixture/import[/{business_id}][?rebuild=true]`.
- Stack: Python, Flask, SQLAlchemy.
- Limits: no huge datasets, no historical versioning (flask-continuum), and no auth or payments DB interaction.

**2. Packaging and tooling config**
- `setup.cfg` and `setup.py` for `data_reset_tool` (Apache 2.0, Beta, Python ≥3.6, universal wheel).
- `setup.cfg` sets:
  - flake8: max line length 120, ignore E501, 10-character docstring minimum.
  - pylint: max line length 120, ignores migrations and test, disables C0301, W0511, W0703, R0801 and R0902.
  - isort: 120 characters, multi-line mode 3.
  - pytest: coverage to html/xml, unit tests only, ignores UserWarning.
- `setup.py` reads the version from `src/data_reset_tool/version.py` by regex, requirements from `requirements.txt` (excluding `git+` URLs), the long description from `README.md`, and the license from `LICENSE`. It uses pytest-runner and pytest. The author is listed as thor@wolpert.ca.
- `version.py` holds `__version__ = '2.17.0'` in PEP 440 format.
- A glob pattern `src/**.py` matches all Python files under `src/` recursively.

**3. App bootstrap and configuration**
- `create_app(run_mode)` loads `config.CONFIGURATION[run_mode]`, defaulting to the `FLASK_ENV` env var or 'production'. It registers `FIXTURE_BLUEPRINT` and provides a shell context of `{'app': app}`.
- The config module has a base `_Config` (`SQLALCHEMY_TRACK_MODIFICATIONS=False`, `ALEMBIC_INI='migrations/alembic.ini'`, default `DB_PORT='5432'`). Three subclasses vary the settings:
  - `DevConfig`: DEBUG=True, TESTING=False.
  - `TestConfig`: DEBUG=True, TESTING=True, with `DB_*_TEST` variants.
  - `ProdConfig`: DEBUG=False, and generates a random `SECRET_KEY` if none is set.
- `get_named_config()` maps production, staging and default to `ProdConfig`, testing to `TestConfig`, and development to `DevConfig`. It raises `KeyError` on an unknown name.

**4. Data endpoints (import, export, delete)**
- **Import:** POST `/api/fixture/import/<legal_type>[/<table>]` takes CSV. It deletes existing entries by ID, then COPYs the new data.
  - `ALL_BCOMP_TABLES` covers 23 tables.
  - `ALL_COOP_TABLES` covers 14 tables, omitting `share_*` and aliases.
  - Importing addresses nulls the foreign keys in `parties` and `parties_version`.
- **Export:** GET `/api/fixture/export/<business_identifier>[/<table>]` returns a ZIP of CSVs. A separate query builder creates a SELECT per table, keyed by `business_id`, as follows:
  - Direct `business_id` match: aliases, resolutions, share_classes, party_roles, offices, filings, businesses.
  - By `party_id`: parties and parties_version, plus separate delivery and mailing address queries.
  - By `office_id`: addresses and addresses_version.
  - By `share_class_id`: share_series, after a `_share_series_exists` check.
  - By `filing.transaction_id`: transaction.
  - Unhandled tables are logged as errors.
- **Delete:** DELETE `/api/fixture/delete/<business_identifier>` cascades across 18 tables, from `party_roles_version` through `businesses`. It commits on success and rolls back on exception.
- **Helpers:** `_get_business_id()`, `_get_id_list()` and `_create_csv()` (which uses `copy_expert` to write `exports/{filename}.csv`).
- Import and export both check the DB connection and roll back on failure.

**5. Empty placeholders**
- Two `__init__` modules contain only docstrings.

## Caution:
- **Identifier validation:** The model accepts only "CP" or "XCP" identifiers. "BC" (benefit corp) cannot be imported even when it is logically valid, which is a known bug in the underlying model.
- **Manual setup:** Loading local Oracle data into Postgres from lear-api needs manual setup via `make local-project`.
- **Glob portability:** `**` expansion depends on the tool or shell, so it is not portable everywhere.
- **E501 settings:** `ignore = E501` in pycodestyle may not suppress E501 in flake8 runs. With flake8's `max-line-length = 120`, lines over 120 characters can still trigger it.
- **Packaging:** Version parsing uses `ast.literal_eval`, and `git+` dependencies are filtered out silently.
- **Default environment:** If `FLASK_ENV` is unset, the app silently defaults to 'production', which could load unexpected config.
- **DB at import time:** `DB_CONNECTION` (`psycopg2.connect()`) is created at class definition, which happens during import. Startup fails if the DB is unavailable.
- **SQL injection:**
  - The import endpoint builds ID lists with `str(list).replace(...)`, which is vulnerable if IDs are not validated.
  - The delete endpoint interpolates values into SQL with f-strings and uses no parameterized queries.
- **Fragile address handling:** Export manipulates party address-ID strings by stripping parentheses and concatenating with a comma. This is fragile with unusual SQL tuple formatting.
- **Empty modules:** The two `__init__` modules have no implementation. They are probably placeholders that need real init logic before use.

## Members

- lear: data-reset-tool/README.md
- lear: data-reset-tool/babel.cfg
- lear: data-reset-tool/setup.cfg
- lear: data-reset-tool/setup.py
- lear: data-reset-tool/src/data_reset_tool/__init__.py
- lear: data-reset-tool/src/data_reset_tool/blueprints/__init__.py
- lear: data-reset-tool/src/data_reset_tool/blueprints/fixture.py
- lear: data-reset-tool/src/data_reset_tool/blueprints/fixture.py
- lear: data-reset-tool/src/data_reset_tool/blueprints/fixture.py
- lear: data-reset-tool/src/data_reset_tool/config.py
- lear: data-reset-tool/src/data_reset_tool/version.py
- sbc-pay: pay-api/src/pay_api/dtos/__init__.py
