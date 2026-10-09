<!-- leaf 20, 15 members -->

This is a set of condensed notes on the BC Registries certificate templates. They are HTML/Jinja2-style files that generate official PDF certificates. Each entry gives a template's fields, includes and logic. Each also carries a GOTCHA about rendering or data assumptions.

## Groupings

**1. Certificate body templates (one per certificate type)**
All of these share a pattern. They show a header with `business.identifier` (labelled "Incorporation Number"), then a title, then an "I hereby certify that…" clause. They end with "Issued under my hand at Victoria, British Columbia on…". They set the same metadata (UTF-8, author "BC Registries and Online Services") and include `common/certificateStyle.html`, `certificateLogo.html` and `certificateFooter.html`. Where an entry lists them, the others include `correctedOnCertificate.html` and `macros.html` as well. The variations are:
- **Amalgamation:** loops over `amalgamatingBusinesses` and shows `entity.legalName (entity.identifier)`. The issued date comes from `business.formatted_founding_date`.
- **Continuation:** adds jurisdiction, `entityAct`, `formatted_founding_date_time` and `formatted_founding_date`.
- **Dissolution:** states the business was dissolved under `entityAct` on `effective_date_time`. The issue line uses `effective_date`.
- **Good Standing:** the header switches between "Registration" and "Incorporation" Number depending on `business.legalType` (GP/SP). It also shows the entity description, founding date and report date.
- **Incorporation (`macros.html`):** states the incorporation using `formatted_founding_date_time` and `formatted_founding_date`.
- **Name Change / Name Correction:** the title depends on `header.reportType == 'certificateOfNameCorrection'`. It shows `fromLegalName` and `toLegalName`, and an optional `correctedOn` date.
- **Restoration:** branches on `restoration.type` (fullRestoration, limitedRestoration, limitedRestorationExtension, limitedRestorationToFull). It uses `fromLegalName`, `formatted_dissolution_date`, `report_date` and the restoration expiry dates.
- **Status:** titled "Certificate of STATUS". It uses `entityDescription`, `formatted_founding_date`, `report_date` and `entityAct`.

**2. Footer and registrar signature fragments**
- **Footer:** a table with the seal on the left and the registrar's name and title (from `registrarInfo`) on the right. It carries the label "ELECTRONIC CERTIFICATE" and includes `certificateSeal.html` and `certificateRegistrarSignature.html`.
- **Signature:** a single `<img alt="signature">` whose `src` is `{{registrarInfo.signature}}`.
- **Correction block:** a conditional block that needs `correction` defined. It splits `effective_date_time` on ' at '. If `currentRegistrarInfo` exists, it shows the signature, name, title and "PROVINCE OF BRITISH COLUMBIA / CANADA".

**3. Logo and seal image fragments**
Three snippets embed PNGs as base64 data URIs: two `column-logo` divs and one `certificate-seal` div. All are truncated.

## Caution:
- **Custom include syntax:** `[[...]]` includes (macros, `common/*`) are not standard Jinja2 or HTML. The engine must support them, or rendering fails silently (Continuation, Dissolution, Good Standing). The footer mixes `[[ ]]` with `{{ }}`, so it needs both rendering contexts.
- **Framework bindings:** `{{registrarInfo.signature}}` means the fragment won't render as raw HTML.
- **Amalgamation:** the loop has no handling for an empty or missing `amalgamatingBusinesses`.
- **Dissolution:** `effective_date_time` vs `effective_date` suggest one is a datetime and one is date-only. The "corrected on" reference implies the template covers both original and amended certificates. All variables need context binding.
- **Incorporation:** two date formats are used (`formatted_founding_date_time` vs `formatted_founding_date`). Check which is rendered where, and whether the mismatch causes inconsistency.
- **Name Change/Correction:** if `header.reportType` isn't `certificateOfNameCorrection`, the template silently shows "NAME CHANGE".
- **Restoration:** there is no fallback if `restoration.type` is missing or not one of the four values. `fromLegalName`, `formatted_dissolution_date`, `effective_date_time`, `restoration_expiry_date` and `previous_restoration_expiry_date` render empty if undefined.
- **Status:** variables are not visibly escaped. Verify XSS protection in `common/certificateStyle.html` or the rendering layer.
- **Correction block:** `autoescape false` disables HTML escaping. The date must contain exactly ' at ' or `split()` fails.
- **Images:** base64 payloads are truncated mid-encoding in all three image fragments. Check whether this is intentional or the data is missing. Embedded base64 also bloats the markup, and the seal's `src` is never completed.

## Members

- lear: jobs/furnishings/report-templates/template-parts/common/certificateRegistrarSignature.html
- lear: legal-api/report-templates/certificateOfAmalgamation.html
- lear: legal-api/report-templates/certificateOfContinuation.html
- lear: legal-api/report-templates/certificateOfDissolution.html
- lear: legal-api/report-templates/certificateOfGoodStanding.html
- lear: legal-api/report-templates/certificateOfIncorporation.html
- lear: legal-api/report-templates/certificateOfNameChange.html
- lear: legal-api/report-templates/certificateOfRestoration.html
- lear: legal-api/report-templates/certificateOfStatus.html
- lear: legal-api/report-templates/template-parts/common/certificateFooter.html
- lear: legal-api/report-templates/template-parts/common/certificateLogo.html
- lear: legal-api/report-templates/template-parts/common/certificateRegistrarSignature.html
- lear: legal-api/report-templates/template-parts/common/certificateSeal.html
- lear: legal-api/report-templates/template-parts/common/correctedOnCertificate.html
- lear: legal-api/report-templates/template-parts/logo.html
