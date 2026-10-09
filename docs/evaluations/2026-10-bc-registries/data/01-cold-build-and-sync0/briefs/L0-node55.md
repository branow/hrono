<!-- leaf 55, 17 members -->

**What this is:** A set of condensed summaries of Jupyter notebooks that run SQL against PostgreSQL databases for BC registry operations. The databases cover the entity/LEAR, auth and pay systems. The notebooks produce periodic stats, reports, reconciliation files and gazette extracts. Most use `%load_ext sql` with `displaylimit=5`. Most build the connection from `PG_USER`, `PG_PASSWORD`, `PG_HOST`, `PG_PORT` and `PG_DB_NAME`, or from `Config.SQLALCHEMY_DATABASE_URI`. Most also write results to CSV or text files under `data/`.

## Groupings

**1. Entity/LEAR filings and business stats (PG_* env vars)**
- *Cooperative monthly stats*: Cooperatives Monthly Stats, which actually covers SP/GP firm registrations grouped by city and postal code. Also Filings Monthly Stats (CP filings with status COMPLETED, saved as `coop_filings_monthly_stats_for_{MONTH_YEAR}.csv`) and the cooperative notebook that runs 4 queries (created and dissolved by year, director counts, non-BC businesses with directors). It appends to `cooperative_monthly_stats_for_[MONTH_YEAR].csv`.
- *Daily incorporation stats*: filings from the previous day (PST), covering incorporationApplication and BEN/BC alterations. Output is `incorporation_filings_daily_stats_{datestr}.csv`.
- *Gazette notebooks (CP/XCP)*: "Filings Daily Stats" appears in two forms.
  - One inserts into `sent_to_gazette` and writes 4 files: COOP_GAZETTE_CHANGEOFNAME, DISSOLUTION, INCORPORATION and RESTORATION.
  - The other runs the 4 matching UPDATE statements that set `sent_to_gazette_date = now()`.
  - Its metadata variant records the kernelspec (Python 3.8.0, nbformat 4.2).
- *BC firms data extracts (SP/GP)*: A "Filings Daily Stats" notebook writes `data/from_openshift.txt`, with state code, legal type, identifier and name. A BCFN_MR notebook builds a fixed-width Master Record file, gzipped as `BCFN_MR_YYYYMMDD_[rowcount].gz`.
- *Operational/issue tracking*:
  - The CRA integration notebook queries `request_tracker` for unprocessed requests: "Cannot inform CRA" responses or retry_number=9. It reported 75 rows, and Ops retriggers them via the admin UI.
  - The Filing Issues notebook lists PAID filings that haven't completed. It uploads them to Google Sheets, posts a Rocket Chat notification and keeps a rolling window of 7 tabs.

**2. Auth stats**
- *Auth Weekly Stats*: queries `orgs` and `users`, producing weekly, last-year and by-year account and login-option (BCEID/BCSC) counts. Output is `auth_weekly_stats_till_YYYY-MM-DD.csv`.

**3. Pay/reconciliation (`Config` URI, papermill-parameterized by `partner_code`)**
- *Invoice Reconciliation Daily Stats*: appears in two near-identical forms. Both query yesterday's invoices joined to `invoice_references` for PAD/EJV/DRAWDOWN. They export `{partner_code}_daily_reconciliation_{YYYY-MM-DD}.csv`.
- *Reconciliation Monthly Stats*:
  - A monthly summary of PAID PAD/EJV invoices.
  - A disbursement query that runs only for CSO and VS.
  - A Keycloak token request.
  - A `generate_report` function that POSTs to the report API for a `revenue_letter` PDF. Partner addresses are listed for CSO, VS, RPT and ESRA.
- *Pay Weekly Stats*: payment account counts by payment method, weekly invoice counts, and NRO counts. Output is `weekly_pay_stats_till_{yesterday}.csv`.

## Caution:
- **CRA notebook**: CRA rejection emails never appear in `request_tracker`; Ops receives them separately. Dates are hardcoded and must be updated for each weekly run.
- **Daily incorporation stats**: three append-mode writes go to one file with no separators. If all queries return empty, the file holds only headers or messages with no clear boundaries.
- **Cooperative monthly stats**: variables are misspelled `stat_cooperative_disslouted` and `df_cooperative_disslouted`, and the misspelling is replicated in the code.
- **Filings Monthly Stats**: SQL uses a `PST` conversion. The relative month is computed with `relativedelta` outside SQL.
- **Firms monthly stats**: uses a hardcoded `-27` day offset instead of a proper month delta. The filename says last_month but the query filters on `founding_date`, not the filing date.
- **Gazette insert notebook**: `sent_to_gazette` is a dedup log with null `sent_to_gazette_date`. The notebook doesn't show the UPDATE that fills this in.
- **Gazette update notebook**: has no transaction scope, so concurrent updates to `sent_to_gazette.filing_id` risk race conditions. It sets `now()` with no external gazette verification. The queries run sequentially, and later ones continue if an earlier one fails.
- **Notebook metadata**: Python 3.8.0 reached end of life in October 2024, so an update is recommended.
- **from_openshift extract**: shows `UsageError: Cell magic %%sql not found`, so the SQL magic failed to load. The notebook won't run until the environment or cell ordering is fixed.
- **BCFN_MR**: all dates assume America/Vancouver, so output dates will be off by hours if the DB or system uses another timezone. The legal name field is fixed at 454 characters, and longer names are silently truncated.
- **Filing Issues notebook**:
  - DB credentials, the service account JSON path and the Rocket Chat webhook URL are hardcoded, which is a major security risk.
  - The variable `inlude_last_number_of_days` is misspelled.
  - `AT TIME ZONE 'PST'` ignores DST.
  - The fee mismatch check only logs and doesn't error.
- **Auth Weekly Stats**:
  - `current_date - 1` is the upper bound (yesterday).
  - The UTC→PST conversion is applied in only some queries.
  - The `timedelta(373)` and `timedelta(366)` "last year" ranges don't align to a 365-day window.
- **Invoice Reconciliation Daily Stats**:
  - Papermill needs the `parameters` tag on the cell, or external parameterization breaks.
  - The date math `-1 - interval '1 days'` is redundant but evaluates correctly. It is designed for a previous-day run.
  - The DataFrame conversion expects a dataframe name prefix from the SQL result variable.
  - `'america/vancouver'` is database-specific and may not work on all systems.
- **Reconciliation Monthly Stats**:
  - The timezone chain must be applied consistently to all date fields, or results shift.
  - The disbursement query adds an extra -5 day offset.
  - `monthly_reconciliation_disbursed` stays None if `partner_code` isn't CSO or VS.
  - The revenue letter uses AT TIME ZONE twice, so verify that logic.
  - The print statement says "payment_receipt.pdf" but the file is `{partner_code}_revenue_letter.pdf`.
  - Empty results are printed but don't fail.
- **Pay Weekly Stats**:
  - Only the NRO queries convert timezone, so date interpretation is inconsistent.
  - The `data/` directory must exist or the script crashes.
  - The filename uses yesterday's date regardless of when the script runs.

## Members

- lear: jobs/entity-bn/tracker-errors.ipynb
- lear: jobs/filings-notebook-report/daily/incorpfilings.ipynb
- lear: jobs/filings-notebook-report/monthly/cooperative.ipynb
- lear: jobs/filings-notebook-report/monthly/coopfilings.ipynb
- lear: jobs/filings-notebook-report/monthly/firm-registration-filings.ipynb
- lear: jobs/sftp-gazette/notebook/generate_files.ipynb
- lear: jobs/sftp-gazette/notebook/generate_files.ipynb
- lear: jobs/sftp-gazette/notebook/update_database.ipynb
- lear: jobs/sftp-icbc-report/notebook/generate_files.ipynb
- lear: jobs/sftp-nuans-report/notebook/generate_files.ipynb
- lear: tests/data/Filing_Issues.ipynb
- sbc-auth: jobs/notebook-report/weekly/auth.ipynb
- sbc-pay: jobs/notebook-report/daily/cso_reconciliation_details.ipynb
- sbc-pay: jobs/notebook-report/daily/vs_reconciliation_details.ipynb
- sbc-pay: jobs/notebook-report/monthly/reconciliation_summary.ipynb
- sbc-pay: jobs/notebook-report/monthly/reconciliation_summary.ipynb
- sbc-pay: jobs/notebook-report/weekly/pay.ipynb
