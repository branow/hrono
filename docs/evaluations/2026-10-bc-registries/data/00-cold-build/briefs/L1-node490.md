<!-- level 1, node 490, children [19, 20, 21, 47, 52, 58, 63, 67, 91, 92, 94, 95, 116, 160, 250, 251, 295, 296, 386] -->

# BC Registries and Online Services: Template Library Brief

This brief covers the templates and related code behind BC Registries / Business Registry documents, emails and front-end text. Most are Jinja2 or HTML. Many use the custom `[[file.html]]` include syntax alongside `{{ }}` variables and `{% %}` logic.

## Contents by area

**1. PDF report and certificate templates (Letter size, print-ready)**
- **Page frame:**
  - Headers: the "Reg Report" header uses a logo plus a 94% separator line (2px #234075). It has a `{{TITLE}}` placeholder.
  - Footers: a "Page N of M" footer, a `.footer-mocs` ministry contact footer (PO Box 9431 Stn Prov Govt, Victoria; 200-940 Blanshard St), and a legacy gold/blue footer with `{{ environment }}` and `{{ business.identifier }}`.
- **Stylesheets:**
  - Current theme: palette #234075 / #1A5A96 / #313132 / #E2E7ED / #BCBEC5. BCSans is base64-embedded, with a Calibri variant. Utilities are `.mt-*`, `.pt-*` and `.col-22/33/50/67`. Tables include `.section-data-table` and `.share-structure-table`. Components include `.chip`, `.business-details-container`, `.registrar-signature` and `.letter-container`.
  - Legacy theme: Arial 12px, gold #fcba19 and blue #003366, with a fixed footer and a watermark.
- **Certificates** (one per type, with the "I hereby certify…" pattern, "Issued under my hand at Victoria…" and the includes `common/certificateStyle.html`, `certificateLogo.html` and `certificateFooter.html`): Amalgamation, Continuation, Dissolution, Good Standing, Incorporation, Name Change/Correction, Restoration (four types) and Status.
  - Fragments: footer with seal and registrar name from `registrarInfo`, a signature image, a correction block, and base64 logo/seal images.
- **Filing and business-summary documents** (about 35 templates):
  - Cooperative (CP) reports: Annual Report, Address Change, Director Change, Name Change, Voluntary Dissolution.
  - Business Corporations Act (BCA) applications: Alteration, Amalgamation, Continuation, Incorporation, Restoration, Transition, Registration, Change of Registration, Corrections, Special Resolution, Dissolution.
  - Others: Notice of Articles, Business Summary, registrar letters (AGM Extension, AGM Location Change, certified letters), dissolution and cancellation mail-outs, and a mail cover page.
  - Shared building blocks:
    - Label macros: `labelNew`, `labelChanged`, `labelNameChanged`, `labelAdded` and `labelCorrected`, all of which render `.chip` spans.
    - Section blocks: business metadata table, registrar certification, footer identifier, from→to name-change tables, share structure, addresses, restoration/dissolution/liquidation/amalgamation/continuation sections, special-resolution and correction blocks.
    - Legal-type disclaimers: BEN/CBEN, CC/CCC, ULC/CUL, plus BCA compliance notices.
    - Effective-date, dissolution-statement and approval-type conditionals.
  - Party tables: directors, proprietors/partners, incorporators, custodians, completing parties, applicants and dissolution parties. Parties are sorted persons first by lastName, then organizations by organizationName.
  - Address tables: registered, records and business offices. These use `col-50` or `col-33` layouts, `changed` flags, and `legalType` gates (GP/SP, CP).

**2. Email templates**
- **Filing confirmations and notices:**
  - Continuation in/out, AGM, incorporation, firm registration and change, alteration, special resolution, dissolution, annual report reminder, Business Number notices, corrections, Notice of Articles delivery.
  - Name Request lifecycle: expiry reminder, expired, renewal ($30 for 56 days), priority upgrade, cancellation and refund rules, and the NR receipt.
  - Restoration emails: a Jinja2 inheritance chain `base_template` → `RES-common` → `RES-PAID` / `RES-COMPLETED` → per-type templates.
- **Account and auth emails:**
  - Suspension, unlock, rejection, approval, on-hold, role change, 2FA reset.
  - Invitations (by role and login method), business authorization, passcode, and product access approval/rejection.
- **Payments:** PAD lifecycle, payment received (full, over, under), payment due/reminder, statement, manual payment due, EFT, refund and GL disbursement failure. The PAD form and Account Statement email are also here.
- **Shared email pieces:** footers and the contact block (1-877-526-1526, 250-387-7848, BCRegistries@gov.bc.ca), logos, base layout, email CSS, business-info blocks, and the `business-dashboard-link` fragment (`entity_dashboard_url`).
- **Ops alert:** an internal Payment Reconciliation Failure template.

**3. Integration and service code**
- SBN hub XML request templates (sender CPPR, receiver BCSBNHUB): change address, name and status; create program account and business registration. Strings are truncated to 30 characters and postal-code spaces are stripped.
- Org and membership service functions: `syncMembership`, `createOrg`, `validatePADInfo`, `deactivateOrg` and others.
- Entity-emailer: the `dissolution_notification` processor, plus pytest notes for the other processors. Subject, recipient and attachment rules vary by status, legal type and submitter role.
- Unrelated: a jQuery 3.2.1 summary and an SFTP `FtpProcessor.process_ftp`.

**4. Front-end and repo scaffolding**
- auth-web: the HTML shell (AddressComplete 2.30), Browserslist config, and large i18n catalogs. The catalogs cover support contacts, team and account lifecycle, payments, product selection, deactivation/removal, and the staff portal.
- GitHub issue and PR templates (bcgov/entity): bug report, feature request (two versions), task/ops issue, and PR.
- Excel `styles.xml` `<xf>` fragments that vary only by `numFmtId`. The notes' descriptions of the built-in IDs conflict with each other.

## Cross-cutting cautions

- **Custom includes:** `[[...]]` is not standard Jinja2 or HTML. Every include must resolve through the preprocessor. Otherwise the output has blank or broken sections, and failures are often silent.
- **Context binding:**
  - All `{{ }}` variables must be supplied by the caller. Missing ones render empty, render literally, or raise errors.
  - Common culprits: `entity_dashboard_url`, `context_url`, `url`, `ar_fee`, `registrarInfo.*`, `numberedDescription`, `restoration.type` and `stateFilings[0].effectiveDate`.
  - Placeholders like `pageNumber` / `totalPages` and `{{TITLE}}` also need filling.
- **Silent omission:** Most conditionals have no else branch.
  - Exact string matching on `legalType`, `restoration.type` and `'Not Available'` fails quietly.
  - Unknown types fall through.
  - Missing `header.name` / `reportType` changes the labels.
  - Empty arrays are mostly unhandled (`amalgamatingBusinesses`, `short_name_links_count == 0`).
- **Print and layout fragility:**
  - `@page` margins must be hand-synced with the header and `.business-details-container`, which use negative offsets.
  - Hardcoded rem/px spacing, `!important` overrides, and the 8rem vs 8px mismatch.
  - Base64 fonts bloat the CSS.
  - `no-page-break` and orphans/widows behave differently in weasyprint and browsers.
  - `-webkit-print-color-adjust: exact` is required.
- **Truncated or corrupt source:** Base64 logos, seals and SVGs are cut off, and several fragments are incomplete (`business-details-container`, the `numFmtId=4` snippet, `removeFirmSuccessText`, the message-tracking test).
- **Known bugs and typos:**
  - CSS: `text-transform: upper` and the `nt-3` class.
  - HTML: unclosed `<span>` in several email titles, a stray `>>` in Business Summary, a duplicate DOCTYPE/`<head>` in the PAD form, and an Outlook VML "Join Team" button vs the visible "Log in".
  - Logic: the nameChanges "To" column's `upper-text` check tests `fromLegalName`, `previousNameTranslations` is never rendered, `disable_specific_service_provider` is inverted, and the payment-due `short_name_links_count` branching is counter-intuitive.
  - Typos: `COMPLETED_SUBJECT_SUFIX`, "Affidvit" in an i18n key, `govmAAccountCreationSuccessSubtext`, and "lear license" in a PR template.
- **Security:** `|safe` on special-resolution text, `autoescape false` in the correction block, and unescaped `registry_logo_url` risk XSS. Nothing in the snippets confirms that escaping happens upstream.
- **Business-rule traps:**
  - Renewal adds 56 days from the original expiry, not from the renewal date. The 56-day vs 1-year-plus-56-days rule must be resolved server-side.
  - The PAD 3-day confirmation is a grace period, and the NSF fee fires on failure.
  - Cooperatives (CP) request their own CRA Business Number, while other types are auto-assigned.
  - XPRO is "cancelled" and domestic types are "dissolved".
  - Names and recipient lists have fallbacks that can mask missing data ("Unknown", "Numbered Company", `no_one@never.get`).
  - Duplicates are possible in dissolution recipients.
- **Test and code quality:**
  - Emailer tests mock heavily (`_get_pdfs`, the recipient lookup), so real PDF and recipient logic goes untested.
  - `validatePADInfo` returns valid when the API fails.
  - `process_ftp` hides errors and uses unsafe path concatenation.
- **Hardcoded values that may go stale:**
  - Contact numbers and addresses.
  - Time limits: "3-4 days", 10 business days, 15-minute links, "tomorrow 12:01 AM".
  - The AddressComplete 2.30 version in the file name.
  - Fee amounts.
