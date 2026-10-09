<!-- level 1, node 504, children [7, 117, 125, 196, 201, 202, 203, 204, 230, 234, 237, 276, 289, 304, 307, 311, 339, 347, 398, 404, 421, 422, 424] -->

**Overview:** This brief covers a bcgov (BC Registries) payments, auth and business-registry codebase. It has roughly 300 condensed Alembic migrations, a few code and test modules, a PayBC invoice fixture set, a COLIN-to-PostgreSQL migration runbook and an Oracle 12.2 Docker build. Most migrations are lookup-data seeds or single-column changes. Each carries a gotcha, usually about a broken or lossy downgrade.

## Groupings

**1. PayBC-style invoicing/receivables API fixtures and schemas**
- Test fixture data: ABC Co-Ops, 2019-04-12, amount 100, provider Finance and Citizens Services.
- Invoices: 10021, 10022, 10023 and a credit-memo variant. All share pbc_ref_number '10005', party 11111, account 4101, site 29921, type WTS-INVOICE-STANDARD, status OP, term IMMEDIATE.
- Invoice lines: line 1, "Test Memo Line", unit price 100.
- Receipts: 123451–123453. Each applies 9.85 to invoice 10021 against a receipt_amount of 10.02.
- Schemas: a 22-field invoice schema and an OpenAPI schema.
- Issues: amounts are integers, which lose cents. `credit_memo_number` is described as "Invoice Number". amount_applied (9.85) differs from amount_to_apply ($9.5). Many fields are null placeholders.

**2. Payment service (pay-api) migrations**
- *Initial schema and seeds (2019–2021):*
  - Core tables: corp_type, fee_code, filing_type, fee_schedule, payment, invoice, payment_line_item and receipt.
  - Statements, routing slips, plural renames (be4475027882, b6e28faea978) and `authorizations_view`-style report views (`RPT_INVOICES`).
  - Lookup seeds: payment_method, payment_system and status_code.
- *Invoice and payment changes:*
  - invoice_reference creation (e0cacec26024, 79ba9960e1dc).
  - Moving the payment method onto the invoice (8652bf9c03ff).
  - Backfills (d2d9864164d1, populate_receipt_number_payments).
  - The status_code split into entity-specific tables (a23093f25c56).
- *Fee and corp-type seeding (~40 migrations):* CP, BC, ULC, BEN, LTD, CC, SP, GP, PPR, VS, NRO, RPT, BUS and CSO, with distribution-code links. Schema tweaks cover waived fees, service fees, the account_fees table and bcol_staff_fee_code.
- *Routing slips:*
  - Columns: parent_number (c12b11093a87, 10fa4c64f1da), refund_amount, total_usd and cas_version_suffix.
  - New statuses: WRITE_OFF, REFUND_REJECTED, CORRECTION, LINKED.
  - Comments table: cdd2ce690303.
  - The current `RoutingSlip` model.
- *Error codes:* RS_*, BCOL_* and FAS_* code inserts, plus rewrites. The BCOL help-desk text is hard-coded.
- *EFT and refunds (2023–2024):*
  - EFT tables: eft_files, eft_transactions, eft_short_names, eft_credits, eft_gl_transfers, eft_credit_invoice_links, eft_short_name_links, eft_refunds.
  - Refund tables: refunds, refunds_partial and the disbursement statuses.
- *Misc:*
  - Column adds and swaps across the payment, statement, cfs_account and distribution tables.
  - The EJV/CGI pipeline: ejv_headers, ejv_invoice_links.
  - cas_settlements, credits and account_payment_settings.
  - Merge 8f7565cf50c1.

**3. Payment reconciliation and test code**
- Contents: CAS CSV reconciliation (PAD/PADR/BOLP/EFTP/ONAC/CMAP/DRWP/ADJS), CGI/EJV fixed-width feedback parsing, NSF and routing-slip processing, AuthEvent, test factories, worker tests and a filings DDL.
- Issues: slices are hard-coded. Commits are per row, so a failure leaves partial updates. Exception handling is broad. NSF logic assumes a prior COMPLETED payment.

**4. Auth/account service migrations**
- *authorizations_view:* repeated rebuilds. Later versions add product subscriptions, payment settings and org status.
- *Permissions:* about 33 migrations that insert or delete rows by hardcoded ID, `max(id)+1` or the sequence. Actions include VIEW_ACCOUNT, MANAGE_STATEMENTS, RESET_OTP, NSF_SUSPENDED variants, view_activitylog and request_product_package.
- *Roles and users:* MEMBER/ADMIN/OWNER renamed to USER/COORDINATOR/ADMIN (437ce1f93861), `login_source` backfills, and `verified` fixes (342ec8814181).
- *Product codes (~25 migrations):*
  - Products: MHR, BUSINESS_SEARCH, NDS, CA_SEARCH, STRR, RPPR, NRO, CSO, RPT, ESRA, BCFMS, BCRHP.
  - Flags: keycloak_group, need_system_admin and the hidden/need_review/premium_only flags.
- *Org suspension:* suspension_reason_codes (OWNER_CHANGE, DISPUTE, COURT_ORDER, FRAUDULENT, PAD_NSF, OVERDUE_EFT), the SUSPENDED and NSF_SUSPENDED statuses, and `suspended_on`.
- *Invitations and affiliations:* affiliation_invitations, invitation, invitation_type, membership_type seeds, ATMP corp type and indexes.
- *Terms of use:* the documents table, versions 1–5 plus `d1` for directorsearch, and an Integer-to-String(10) change. The deletes are permanent.
- *Audit versioning:* `*_version` tables, transaction and activity.
- *Tasks table (2021):* creation, a reshaping that adds related_to/status/type, `remarks` as an ARRAY, `action` and a seed from orgs.

**5. Business registry (lear-style) migrations (~60+)**
- *Column adds:* mostly nullable additions to filings, businesses and `_version` twins (e.g., `last_ar_year`, `send_ar_ind`).
- *New tables:* amalgamations (146e135484b2), furnishings, reviews, dc_* credential tables, request_tracker, configurations, consent_continuation_outs.
- *Batch processing:* batches and batch_processing (9fc8fcdc0a22), the QUEUED enum (01dc3337e726), sequences and `meta_data`.
- *Index and data migrations:* 30 indexes (e10f724fad6d), plus CBEN corp type and configuration deletes.
- *Business eligibility clause builders:* `_has_delay_of_dissolution_filing` is unimplemented and always returns False.
- *Zenhub script:* a GraphQL script for issues and releases, not a migration.

**6. COLIN-to-PostgreSQL data transfer (lear data-tool)**
- Procedure: a 9-step runbook for moving corps data from Oracle (`cprd`) to PostgreSQL (`cprd_pg`) with DbShell.
- Target schema: about 35 tables. The corp_type filter is BC, C, ULC, CUL, CC, CCC, QA–QE.
- Notable steps: email anonymization, and a Y/N→1/0 conversion.
- Tracking tables: affiliation_processing and corp_processing.
- Unrelated items in the same material: a messaging-store schema, the BCA admin-contacts query and the BCA monthly report.

**7. Merge/no-op/stub migrations**
- About 17 empty Alembic merges (e.g., 8b49eb83f064, c0152c02cd5f, ef8a9847f953, 66ae9d618842, 19a7733fd001, e777dd2575e2, e6e295695b9a, 765d488b18dc, a0f0a77dc77f, d1b167ef61da, d804bcead371, 567df104d26c, e385e278cf3e).
- A linear no-op, b1fb7d214cb7 → c0152c02cd5f.
- An incomplete skeleton, 4efb2fdcc1ab → 08063ceec05d ("new TOS added").

**8. Oracle 12.2.0.1 Docker build scripts**
- Pipeline: paramChk.sh → untarDB.sh → configDB.sh, plus the configDBora2.sh wrapper, which tracks an EXISTING_DB flag.
- Setup: it extracts the tarballs to / and /ORCL, creates the PDB and writes sqlnet/listener/tnsnames.
- Password handling: DB_PASSWD is cleared and shell history is wiped.
- A stray migration header (down_revision b32d868d628c vs 615db0d23fee) appears in the material.

## Caution:
- **Downgrades are often broken or lossy:**
  - Wrong table or column names: 0a3ad7c041f6 (`invoices` vs `invoice`), a66de2954e70, c3a87b8ea180, bae02665e807, 1a46fdc4d630 and 68c71d35f671 (`action` vs `actions`).
  - Syntax or structure errors: e8edc889072d (extra `)`), 6a6b042b831a (`downgrade()` nested in `upgrade()`).
  - No-op or missing: many seed and BCOL-rewrite downgrades, 1283463d3b4a (none), 0420566ac811.
  - Destructive: TRUNCATE CASCADE (a4519a2af112, 4a305e1c8c69), `DELETE FROM tasks` without a WHERE clause (031a07fb0811), `delete from payment_account` on upgrade (4cc39da0bee7).
  - Deleting by hardcoded ID or by code can remove rows the migration didn't insert.
- **Docstring vs code mismatches:** always trust the `down_revision` in code. Known cases include 598bbfce4dad, 1d5b66ef7f81, 628b52a95bad, 9f63681d5e6a, 4cb0dc8e0013, 1215735c3563, 441a5e6cf682, 94c2a694d51f, d21f6be7bd21 and ed12492e70f8.
- **SQL injection:** f-string SQL appears in 331c2cdb0b94, 342ec8814181, 8652bf9c03ff, d2d9864164d1, 56c5db141909, 8eac44955fb6 and others. Use bound parameters.
- **Typos that persist:** `inovice_id` (92fed98da61c), `new_otions` (01dc3337e726).
- **Seed behavior:**
  - `datetime.now()` is used for `fee_start_date`, so values vary by run.
  - Distribution-code links are silently skipped when the named code is missing.
  - `max(id)+1` inserts race under concurrency, and string IDs go into Integer columns.
- **Version-table drift:** `_version` tables often differ from their main tables in `autoincrement`, and must be kept in sync.
- **Merge migrations:** they change nothing, so look in the parent revisions for the actual schema work.
- **Typing and precision:** Integer amounts in the PayBC schema lose cents. `server_default='False'` strings are dialect-dependent. A float `< 0.01` comparison is used in 6a6b042b831a. The `'pst'` literal in the BCA report has no daylight-saving handling.
- **Oracle-to-PG transfer:**
  - Triggers must be disabled and then re-enabled around the transfer, in order.
  - Remove the commented `corp_num`/`rownum` restrictions, or the transfer covers only test data.
  - The `'BC'` prefix applies to only 3 of the 11 corp types.
  - Y/N conversions default to 0.
- **Hardcoded values:**
  - Stale BCOL contacts in the error-code text.
  - The d55dfc5c1358 downgrade overwrites the production summary email with a test address.
  - The Zenhub script has fixed 2024 dates.
- **Passwords in shell:** the Oracle scripts pass passwords through echo into a sqlplus heredoc.
