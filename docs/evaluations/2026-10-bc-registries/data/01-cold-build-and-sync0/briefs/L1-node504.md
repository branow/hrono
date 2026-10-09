<!-- level 1, node 504, children [117, 125, 196, 201, 203, 204, 230, 234, 237, 289, 307, 311, 339, 347, 398, 422, 424, 549, 550, 567, 568, 575, 576, 577, 594, 595, 603, 604, 605] -->

# Brief: BC Registries database migrations, payment pipeline and Oracle tooling (parent summary)

**What this is:** A large body of condensed notes from the BC Registries / BC Pay ecosystem. Most of it is Alembic migration history for several separate services: auth/org management (accounts, permissions, products, invitations, tasks), pay-api (fees, invoices, EFT, routing slips, CFS/CAS, eJV), and business-filings (LEAR: businesses, filings, parties, amalgamations). Around that are:
- reconciliation and feedback-file code and tests;
- the COLIN-to-PostgreSQL transfer runbook and its DbShell scripts;
- an Oracle 12.2 Docker build set;
- a few stray SQL reports and tooling scripts.

Revision IDs recur across groups, so use them to route to the right service.

## Where things live

**Auth / org-management service**
- **`authorizations_view` recreations.**
  - Revisions: b32d868d628c, 615db0d23fee, 6848a30e95cd, dede70a6df1e, 243d9782085e, 9b3cd480fa3b, c7d122dc4e06, 22e86ed493b8, 1c958b749a20, 06c7acc047fa, d59e32d1f78b (corp_type).
  - Also here: 342ec8814181, which sets `verified` on users.
- **Permissions seeding.**
  - Single-row ADMIN/USER inserts and multi-row batches: 0f310e71e51d→c10f494d7e10, 5397c5a5b0ca, a490b2db8b13, c44fff21c830, 1a46fdc4d630, eb771b2012b7, f55e4cc1aaaa, 39b4f331c003, d00101759be4, c51a33f55be6, 445387ab801c, 765d488b18dc, b72d4946fb3c, eaef1147f25c.
  - The `request_product_package` lifecycle: 68c71d35f671, f8f82c74f1fc, c44fff21c830.
  - 69a7e464fef3: large, and it resets PPR subscriptions.
  - Id-based inserts: 598dd27fc660, d34f68927bdf, c142314f322b, 32b50299e3a3, 032248a1b370, eff007a689cb, e38ad1ce6d21, 75336ba7d252.
  - 71d7c605c31b creates the `permissions` table.
  - 437ce1f93861 renames the roles MEMBER→USER, ADMIN→COORDINATOR and OWNER→ADMIN.
- **Product codes and subscriptions.**
  - Foundation: cadc28cb38d3, 3013ef68d7f1, b22ee0cd18ad, 9b04140db7d3, 8111f90828de.
  - Single-product inserts: MHR 975fe0b2c859, BUSINESS_SEARCH 211deb552319, NDS 746771099983, CA_SEARCH 824f5ef280c6, STRR 17369fa9416d, RPPR e7f46c30d356, NRO aaa29018c0a1, CSO 37dc988611c6, RPT 304705f06971, ESRA 3f79f6dcc58d, BCFMS/BCRHP acc7e2e2c2d7, MHR_QS* b20a33cb84f2.
  - Updates and backfills: 501d1179b2f0, 9e8d6b3de6d5, 98bee9969323, 18823fc88aac, f1ce3f279b60, a0198b1e2c51.
- **Invitations, affiliations, org status.**
  - Affiliation invitations: 13121bcf368a, 27d53abf3f48, 628b52a95bad, 4a6eb0fcc93e, 144d6e8bd4df.
  - Original invitation and membership system: 9f63681d5e6a, 4a305e1c8c69, 7b0cde979ba5, a4519a2af112→4150773f899f.
  - Org status and affidavit: 648b36e69155, a37f90e6802d.
  - Indexes: 80d7590875fa.
- **Suspension.**
  - Revisions: 5053985bdfc6, 8260fac9943d, fc8b221f938f, 41fa6588c76e, acc7e2e2c2d7, e2d1d6417607.
  - Together they cover suspension reason codes, SUSPENDED/NSF_SUSPENDED statuses, and the lifecycle of the `EFT_NSF`, `PAD_NSF` and `OVERDUE_EFT` codes.
- **Tasks table.**
  - Revisions: 379f1d6b24d4, 89b1e9096ad4, 7f01a013a976, 304705f06971 (remarks→ARRAY), 9f3450623765→09dd4ea64775, 031a07fb0811→885632ab6357.
  - 885632ab6357 / d804bcead371 is a docstring-only no-op.
- **Terms of use / documents.**
  - Table creation, per-version inserts (v2–v5, and `d1` for director search), and the Integer→String(10) change on `version_id`.
  - Also: user login_time/login_source, user_version indexes, and the `*_version` audit tables with `transaction` and `activity`.
  - Also: login-source tracking (ea64b4d55bfb, f1ce3f279b60) and the user_remove_roles revision.
- **Merge stubs and a skeleton.**
  - 15 empty merge migrations (8b49eb83f064, c0152c02cd5f, ef8a9847f953, 66ae9d618842, 19a7733fd001, e777dd2575e2, e6e295695b9a, 765d488b18dc, a0f0a77dc77f, d1b167ef61da, d804bcead371, 567df104d26c, e385e278cf3e).
  - A linear no-op b1fb7d214cb7→c0152c02cd5f, and the "new TOS added" skeleton 4efb2fdcc1ab→08063ceec05d.

**Pay service (pay-api)**
- **Initial schema, lookup seeding and renames.**
  - Initial schema and seeding: 55f71addab9d, 4a4dfbf28f22, b7c4b2533f84, 0420566ac811, ac01134753e9, 1283463d3b4a, 5b1ae231f7d2, 9a540e7b411a, 92fed98da61c (statements).
  - Plural renames: be4475027882, b6e28faea978.
  - Other: 4c3b8d61d200, cc2dcab68760, 331c2cdb0b94.
- **Invoice, payment and reference tables.**
  - Revisions: 861324fa9b37, 7b8f813d7a14, 0a3ad7c041f6, 79ba9960e1dc, e0cacec26024 (`invoice_reference`), d2d9864164d1, 8652bf9c03ff, 7c19ee3a58aa, bae02665e807, 1e62e1c27b08, a66de2954e70.
  - Also: populate_receipt_number_payments (03b2c7caed21→c871202927f0).
- **Payment-account restructuring, versioning and statements.**
  - Restructuring and CFS: 06eda339e0d5, 4cc39da0bee7→7a86a5703e27, 56c5db141909 (`cfs_account`).
  - Credits and bank details: 15682073c535, 90afcc0d6d9f, 70af1f70f6bf, b624b5dbc9b9.
  - Statements: 7e51d3ce4005, 71c733c91cbf.
  - Versioning: e7fb85dbffae.
  - Keycloak backfill: 8eac44955fb6.
  - No-op merge: 8f7565cf50c1.
- **Fees and corp-type seeding.**
  - New corp types with their fees and filing types: daa392b64cb7 (CP), e6eb14b9d50e (BC), e8edc889072d (NRO), 06f6e75c18d8 (VS), b7443d501d98, c67213f860ea, e699674b1774, 2efd8e2b92a1 (PPR), cdd2ce690303, dbe9dc38ac33, 609b98d87a72, 643790dd3334 (CSO), 6a6b042b831a (BUS), e748b5c19247, b336780735dc (SP/GP), 5f7df60469fa (PPR), 44bd57ece7b0, 4cb0dc8e0013 (dissolutions), 0aa7d4deef8a (NOFEE), cf9a60955b68, 00467a306afd, 33bbd4d9a85c.
  - Data updates: e67a61c01cbb (CCC→CC), 7a86a5703e27, 8082a6c00fd7, f1ed292af77f, f7362101e761, 1ad89abae65d.
  - Schema changes: 7d16423bc042, 78951cf14ae9, 41bf37772240, 7649a31bfe39.
- **Routing slips.**
  - Columns and FKs: c12b11093a87, 10fa4c64f1da, aa9207187d6b, d73cbcdd2f25, 4a6ddf932b62.
  - Status codes: 2d025cbefda8, c3a87b8ea180, 5418ad1a5fdd.
  - Comments table: cdd2ce690303.
  - Also the current `RoutingSlip` model.
- **Error codes and status tables.**
  - Error-code inserts: 059abb33d3c3, 2c1ecdec185a, f74980cff974, 872760122cc9, f841ac43e15e.
  - BCOL text rewrites: 099ba5cf19a3, 59fc9d74101f, c61e4c535a15, 6ba89cd39cc8, 175c11863186, 9543cbcb8b79.
  - Status and width changes: 2d75a53b0cbd, a22d758c6670, bb5b5cab004b, ff2d7fe31ec9.
  - `status_code` split into five tables: a23093f25c56.
  - ACTIVE→COMPLETE data fix: 6a6b042b831a.
- **eJV and distribution codes.**
  - eJV tables: 6f0ve9f23d8c, ebee125e6877, 073b9f59b447, 9abc5b5245b6, f8408a4a782c→0d885750ded9.
  - Distribution codes: a11be9fe1a6a, 9335f4e0aa22.
  - Other: 17b404b3df45→8082a6c00fd7, 5418ad1a5fdd.
- **EFT and refunds.**
  - Refunds: 086e16326076, c3a87b8ea180, 999f11310f30, 1ec047cf4308, bacb2b859d78, cfa9e9f222f5.
  - EFT build-out: 456234145e5e, 194cdd7cf986, 2ef58b39cafc, 598bbfce4dad, ff245db0cf76, a9bf3eaeda7b.
  - Short-name linking and credits: 29867cf1bd9e, 4b3bd37727a5, 1d5b66ef7f81, 4410b7fc6437.
  - Short-name details and EFT refunds: 1fadb0e78d8c, 423a9f909079, 5aa18f715e3e, 67407611eec8, 29f59e6f147b.
- **Reconciliation code and tests.**
  - JV/EJV/AP feedback-file processing.
  - CFS settlement processing (PAD, BOLP, EFTP, ONAC/CMAP/DRWP, NSF handling, credits).
  - Routing-slip `process_nsf` and `adjust_routing_slips`.
  - Auth and mailer event publishers.
  - Test factories, integration helpers and scenario tests.
  - The `filings` DDL, the fee query, and the performance-test cleanup and load scripts.

**Business-filings service (LEAR)**
- **Core migrations.**
  - Initial schema: 98ccc973c01d.
  - `businesses` / `businesses_version` column additions: 11a256335c79, 08da65c4a94a, 5ad3243edc3e, b6997f07700a, e6ed22dc70ca, ee956cbf198a→a6e3fdc238dd, ae43b5cc0d2d, 37acd517fe98, 7e02a91ac3c6, 8bd6dc383c96, d087a6ee9230, 285e11a8f0c4, 2afccb4603ec.
  - Amalgamation: 146e135484b2, ba862cfda9e5, 5238dd8fb805.
  - Other schema and data: 6e28f267db2a, ac0065d92893, feb206b2ce65, e10f724fad6d (30 indexes), 246e135484b3 (CBEN), d55dfc5c1358.
  - Also the Business eligibility clause builders.
- **Versioned (audit) tables and new tables.**
  - Versioned tables: 1215735c3563, 860bb6075dde→bf94a1b46804, 442829649a2a, 361b51b824c0, a8f42b830d86, f3fb008e7b83, 8c74427a6c0e, 441a5e6cf682.
  - New tables: 01b28a2bb730 and b14f77400786 (furnishings), 86d8aca36208, ecfeee53451a, b826412a6a65, 1a8c89b722e2, 4ee6f0abb797, f4f93ea8887e.
  - Column additions and alterations on existing tables: 0fb2ae5711ed, 176f983485c8, 2e986c1d4de6, 94586877d4bc, da43f7bef692, 026f42f4f654, 1ba027b074a5, bddd732a9269, 0b2af7f762bb, 0c792224fe11, 8148a25d695e, c212a141600c, 7575af513efb, 5e1faa8636c0, 52553d4d6309, e85053684b3c, bb9f4ab856b1, c17d77b30bdb.
  - Data-only: 9147d4bc9939, f4f654026f42, 508c7466b2af.
- **`filings` column and FK migrations.**
  - Single-column adds: 1fcdb213657d, 54a3fc54a2cf, 78ddb7f6f8b5, 9741616ab6d7, b18741f7c4d3, d21f6be7bd21, 94c2a694d51f, 9b5c719f32ef, ed12492e70f8, bf94a1b46804, 7c86cc916b5c, 89fe33f436c1, 2dedf50a17ef.
  - FK links: 1f01b9303b81, 9147d4bc9939, ad3ef106696c, 1400cc212014.
  - Structural moves: 92c4974ce96f, 9a9ac165365e, c4732cd8abfd, ec9652171563, f978e34aa8bb.
  - Others: 2afccb4603ec, d9e21a1b82ca, 6b65b40a5164, 2e29ebe9a830, bf8d4391745e→bddd732a9269, 361b51b824c0, 026f42f4f654.
  - A Zenhub GraphQL release script sits in the same pile.
- **Batch processing.**
  - Batch tables and enums: 9fc8fcdc0a22, 01dc3337e726.
  - Added columns: a31cb1eb4b6b, 3083d361616e, ef8f033d317b, 9c95a9b28eb3.
  - Sequences: 3d8eb786f4c2 (`business_identifier_coop`), 7d486343384b (`batch_custom_identifier`).

**COLIN → PostgreSQL migration (lear data-tool)**
- A nine-step runbook: create the DB, apply the DDL, install DbShell, register the `cprd` and `cprd_pg` connections, disable triggers, run `transfer_cprd_corps.sql`, then re-enable triggers and re-index.
- Target schema: corporation, event, filing, address, corp_party and many more, plus `affiliation_processing` and `corp_processing` tracking tables.
- ETL pattern: the same `corp_typ_cd` filter everywhere, a `'BC'` prefix on only 3 of 11 types, and Y/N→1/0 flag conversion.
- Thread counts are 8 for the core tables and 3 for address.

**Oracle 12.2 Docker build**
- Scripts: paramChk.sh → untarDB.sh → configDB.sh, plus the oracle-user init script and a root wrapper that sets `ORACLE_HOME`.
- A stray Alembic header (`b32d868d628c` vs `615db0d23fee`) appears in the wrapper note.

**Unrelated one-offs**
- Messaging-store schema (v0.10.0 adds `Clients.proto`).
- BCA admin-contacts query.
- BCA monthly payment report (`'pst'` time-zone literal).

## Cross-cutting cautions

- **Header vs code mismatches.** Docstring "Revises" lines often disagree with the `down_revision` in code. Trust the code. Known cases: 598bbfce4dad, 1d5b66ef7f81, 628b52a95bad, 9f63681d5e6a, 4cb0dc8e0013, 94c2a694d51f, ed12492e70f8, d21f6be7bd21, 1215735c3563, 441a5e6cf682, 9fc8fcdc0a22.
- **Weak downgrades.**
  - No-ops: 0420566ac811, 1283463d3b4a (none), f7362101e761, daa392b64cb7, e6eb14b9d50e, 5f7df60469fa, 59fc9d74101f, c61e4c535a15, 6ba89cd39cc8, 2dedf50a17ef, 342ec8814181.
  - Delete the wrong table or column name: a66de2954e70, 0a3ad7c041f6, bae02665e807, c3a87b8ea180, 9a540e7b411a.
  - Broad deletes: 031a07fb0811→885632ab6357 deletes all tasks, and 4a305e1c8c69 and a4519a2af112 truncate with CASCADE.
  - Nested inside `upgrade()`: 6a6b042b831a.
  - Delete-by-id, delete-by-action and `max(id)+1` patterns run through the permission migrations.
  - Several downgrades lose data: column shrinks, dropped columns, tables recreated without their rows.
- **SQL injection.** F-string or concatenated SQL appears in 331c2cdb0b94, 342ec8814181, d2d9864164d1, 8652bf9c03ff, 7c19ee3a58aa, populate_receipt_number_payments, 6f0ve9f23d8c, a11be9fe1a6a, 8eac44955fb6, 56c5db141909 and 0ab62b841b88. Use bound parameters.
- **Execution-time fee dates.** Nearly every fee-schedule seed uses `datetime.now(tz=timezone.utc)` for `fee_start_date`. Dates differ by run time, replays can duplicate rows, and some distribution links are silently skipped when named rows are missing.
- **Versioning twins.** Main and `*_version` tables must stay in sync. `_version` columns often have `autoincrement=False`, and downgrades must drop in reverse order.
- **Unnamed FKs.** FK names of `None` make downgrade drops fragile.
- **Typos preserved in the schema.** `inovice_id` in `statement_invoices` (92fed98da61c, fixed in 7e51d3ce4005) and `new_otions` in 01dc3337e726.
- **Nullable adds.** New nullable columns leave NULLs on existing rows, and reads must handle them.
- **Reconciliation code.**
  - It parses fixed-width files by hardcoded index positions, which are brittle.
  - It uses broad `except Exception`, per-row commits, and partial-update risk.
  - Several tests have hardcoded dates or IDs.
- **Merge stubs.** Empty merge migrations change no schema. Look in the parent revisions for the real changes.
- **Operational hazards in the COLIN runbook.**
  - Triggers must be disabled before the transfer and re-enabled after it.
  - Commented-out `corp_num` / `rownum` limits silently restrict a run to test data.
