<!-- level 1, node 490, children [20, 21, 47, 58, 63, 91, 92, 94, 95, 116, 160, 250, 295, 296, 386, 518, 519, 520, 523, 524, 565, 566] -->

# BC Registries / Business Registry template and asset library — parent brief

This is a large family of templates and supporting code for BC Registries and Online Services. It covers PDF/HTML filing reports, certificates, letters, email notifications, SBN hub XML, print CSS, i18n catalogs, GitHub issue and PR templates, and unit tests for the emailer. Nearly all of it is Jinja2-style, with two conventions to know:
- **`[[path/file.html]]` includes.** This is a custom, non-Jinja syntax. A custom preprocessor must resolve it. A missing or unresolved include leaves blank or broken output, often silently.
- **`{{ var }}` and `{% if %}` bindings.** The caller must supply the variables. Missing values render empty or as literal text, and there is usually no fallback and no schema validation.

## Where to route

**1. Certificates (`certificate*` bodies, footer, seal, logo, signature, correction block)**
- Types: amalgamation, continuation, dissolution, good standing, incorporation, name change/correction, restoration and status.
- Shared skeleton: header with the incorporation number, logo, title, a "I hereby certify" clause, "Issued under my hand at Victoria", and includes of `common/certificateStyle.html`, `certificateLogo.html`, `certificateFooter.html` and `correctedOnCertificate.html`.
- Footer fragments: seal, `registrarInfo` name/title/signature, and the "ELECTRONIC CERTIFICATE" label.
- Correction block: splits `effective_date_time` on `' at '`, shows `currentRegistrarInfo`, and sets `autoescape false`.
- Type-specific switches:
  - Good standing: GP/SP use "Registration Number".
  - Name correction: keys on `header.reportType == 'certificateOfNameCorrection'`.
  - Restoration: keys on `restoration.type`.
- Risks: two date formats in dissolution and incorporation, an unguarded `amalgamatingBusinesses` loop, no fallback for an unknown restoration type, and truncated base64 images.

**2. Office address blocks**
- Mailing and delivery tables.
- Registered/records offices are two-column (`col-50`), with an `addressChanged` badge or a `.changed` flag. Business offices (GP/SP) are three-column (`col-33`).
- Legal-type filters differ by section: registered excludes GP/SP, records excludes GP/SP/CP, business is GP/SP only.
- Country prefers `addressCountryDescription` over `addressCountry`.
- Risks: a fixed two-address layout, and `streetAddressAdditional` rendering an empty div.

**3. Party tables**
- Roles: directors, proprietors/partners, incorporators, custodians, completing party, applicant, and dissolution parties. There is also a small Vue dissolution-date snippet.
- Persons sort before organizations, by lastName.
- Change labels (Added, Corrected, Name Changed, Formerly) depend on `header.name=='correction'`, `director.actions` and `.changed` flags.
- Risks: the `labelNew`, `labelChanged` and `labelCorrected` helpers are undefined in the snippets, ceased directors are hidden by `cessationDate`, and a missing Completing Party renders an empty statement.

**4. Filing report sections (PDF, mostly WeasyPrint)**
- Applications and notices: incorporation, amalgamation, continuation, transition, restoration, alteration, correction, special resolution, firm registration/change, annual report, address/director change, dissolution, and business summary.
- Cooperative (CP) reports use their own table layout and wording.
- Section blocks:
  - Business identity and metadata tables (the label varies by `reportType`/`header.name`; Business Number shows only if `taxId` is longer than 9 characters).
  - Name request and name changes.
  - Share structure.
  - Jurisdiction and continuation.
  - Restoration.
  - Effective-date sections (keyed on `header.isFutureEffective`).
  - Legal-type disclaimers (BEN/CBEN, CC/CCC, ULC/CUL).
  - Dissolution statements, including the CP s.197 cases and the s.316(1)(a) affidavit.
  - Compliance checklist.
- Risks:
  - Most blocks have no else branch and disappear silently.
  - A possible bug where the name-changes "To" column checks `fromLegalName`.
  - `resolution|safe` disables escaping, so user input can cause XSS.
  - Legal-type codes must match exactly.
  - `numberedDescription` is an unguarded last fallback.

**5. Letters and furnishing**
- Types: AGM extension, AGM location change, certified status, and dissolution/cancellation notices (NO_AR, PRTA, XPRO).
- A furnishing XML template covers DISSOLUTIONS and REGISTRATIONS CANCELLED. There is also a cover page for mailings.
- Letters need five required includes: style, the letter override, logo, registrar signature and the MOCS footer.
- Risks: `stateFilings[0]` crashes for a HISTORICAL business if the list is empty, foreign registrations are capped at 3, and wording is XPRO-specific.

**6. Print CSS, headers and footers**
- Brand colors: #234075, #1A5A96, #313132, #E2E7ED, #BCBEC5 and #003366/#fcba19. Fonts are BCSans or Calibri.
- `@page` margins vary: 1.98in/1.45in, 2.2in, and print overrides.
- Layout details: fixed `.header` at `top: -192px`, `.business-details-container` at `margin-top: -43px`, and `col-*` and `mt-*`/`ml-*`/`pt-*` utilities.
- Footer pieces: the Page X of Y text, the Ministry of Citizen's Services contact table, and a business footer showing `{{ environment }}` and `business.identifier`.
- Risks: heavy `!important`, hardcoded rem/px values, an 8rem vs 8px footer mismatch, truncated base64 assets, and `.chip` using an invalid `text-transform: upper`.
- Changing `@page` margins means also updating `.header` and `.business-details-container`.

**7. Email templates (BC Registries notifications)**
Layout pieces: shared header/footer, logo variants, email CSS, and a business-info block. Contact details are toll-free 1-877-526-1526, Victoria 250-387-7848, and BCRegistries@gov.bc.ca.
- **Filing confirmations:**
  - Types: amalgamation, alteration, annual report, address/director change, incorporation, corrections, Notice of Articles delivery, continuation in/out, AGM, firm registration, BN, special resolution and dissolution.
  - Common features: attachment lists with a Receipt, and "issued later" statements.
  - Branches: legal type (CP versus others) and `isFutureEffective`.
- **Restoration emails:** The chain is `base_template` → `RES-common` → `RES-PAID`/`RES-COMPLETED` → per-filing templates. PAID templates override only the `attachments` block.
- **Name Request emails:**
  - Expiry reminder, expired notice, renewal (56 days, or 1 year plus 56 days), priority upgrade, cancellation refunds (credit card, BC OnLine, PAD, mailed) and the NR receipt.
  - Uses `[[nr-footer.html]]`.
- **Auth / account emails:**
  - Account lifecycle: PAD lifecycle, payment received / due / reminder / statement, EFT, refunds, GL failure, account suspension / unlock / rejection / on-hold, and invitations.
  - Authorization and product access.
  - Contact routing by `contact_type`: BCOL 1-800-663-6102 or bconline@gov.bc.ca.
- **Other emails:** the account-statement email (with an Outlook VML button mismatch) and the PAD confirmation form.
- **Ops:** the Payment Reconciliation Failure alert, which is internal only.
- **Known defects:**
  - Unclosed `<span>` in several titles.
  - A truncated BN-change email.
  - Inverted `disable_specific_service_provider` and `short_name_links_count` logic.
  - A hardcoded "tomorrow 12:01 AM".
  - A silent `ar_date[0]` year assumption.
  - A duplicated PAD form head.

**8. SBN hub XML (sender CPPR, receiver BCSBNHUB)**
- Requests: SBNChangeAddress (TDI17), name change, SBNChangeStatus (`documentSubType=113`), Create Program Account (`000`) and business registration.
- Street, municipality and organization fields are truncated to 30 characters, with no indicator.
- Spaces are stripped from postal codes. `updateReasonCode` is hardcoded to 03 and `operatingNamesequenceNumber` to 1.

**9. auth-web front end**
- HTML shell: AddressComplete 2.30, `/src/main.ts`, and browserslist.
- i18n catalogs:
  - Support contacts (`techSupport*` with 250-387-7848 and 1-877-526-1526, `maximusSupport*`).
  - Team and account lifecycle.
  - Payment errors.
  - Product selection (`*Code` subtitles and descriptions).
  - Deactivation and removal (`removeNR*`, `removeIA*`, `remove{Type}*`).
  - Staff portal.
- Known typos to copy verbatim: `pendingAffidvitReviewMessage` and `govmAAccountCreationSuccessSubtext`.
- Strings contain embedded HTML, and placeholders (`{team}`, `{days}`, `{url}`) need runtime substitution.

**10. Emailer service code and tests (entity-emailer)**
- `dissolution_notification` implementation: recipients, SP/GP versus other legal types, and subject fallbacks.
- pytest suites for these processors:
  - AGM extension and location change.
  - Amalgamation, registration, change of registration, incorporation, maintenance, correction, continuation in/out and consent continuation out.
  - Restoration, special resolution, affiliation, AR reminder, business number and involuntary dissolution.
  - MRAS and NR.
  - Dissolution.
- Test patterns: mocked `_get_pdfs` and recipient lookup, and a numbered-company subject rule ("Numbered Company - …").
- The message-tracking test file is truncated.
- Recipient quirks: placeholder emails like `no_one@never.get`, and possible duplicates for SP/GP officers.

**11. Repo and misc**
- GitHub bug report, feature request (DoD and standard), Task/Ops, and PR templates (bcgov/entity, business-filings-ui, sbc-pay).
  - The `Replace_With_Short_Descriptive_Name` placeholder must be filled in by hand.
  - One PR variant says "lear license".
- Unrelated code: jQuery 3.2.1 init, and `FtpProcessor.process_ftp` (SFTP upload that skips `sftp_priv_key_file*`, uses a bare `except Exception`, and concatenates paths unsafely).
- A French test i18n object.

## Cross-cutting cautions
- The template engine must support `[[...]]` and `{{ }}` together. Context variables are assumed, not validated.
- The `header.name` vs `header.reportType` split and `effective_date` vs `effective_date_time` mismatches cause silent wrong or empty output.
- Hardcoded contact numbers, dates, 30-character truncation, and fixed print dimensions all need review when the underlying business rules change.
- Base64 images and fonts are truncated in many snippets.
- Escaping is inconsistent (`|safe` and `autoescape false` in places).
