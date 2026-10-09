<!-- leaf 621, 14 members -->

These are 15 condensed summaries of front-end unit tests from a Vue 2 + Vuetify (with Pinia) business-registry app. Most test individual components. Several are Alerts-panel tests. A few are skipped or have structural quirks.

## AGM (annual general meeting) components

- **AgmExtensionEvaluation:** 11 cases. Shared props are agmYear='2023', currentDate='2023-10-22', incorporationDate=2023-01-01 and extensionDuration=6. The flags isEligible, alreadyExtended and requestExpired are varied. Coverage:
  - basic display and warning-card display
  - eligible with a 6-month duration
  - three eligible flag combinations
  - four ineligible states, each with its own message:
    - alreadyExtended → "maximum possible extension"
    - requestExpired → "outside of time window"
    - both flags → "AGM due date from previous extension has passed"
    - evaluateResult=false → only checks that the message-box exists
- **AgmExtensionHelp:** mounts with Vuetify. It checks `.agm-extension-help`, the h3 "AGM Extension Help" and three paragraphs by substring ("A company must have an", "Shareholders entitled to", "If a company does not"). It then destroys the wrapper.
- **AgmLocation:**
  - Props are `rules` and an optional `locationValue`. It emits `update:agmLocation` and `valid`. The rules are required and max 400 characters. The component ID is `#agm-location`.
  - Five tests:
    1. Initial state: empty value, no emit, valid=false.
    2. Init with 'Toronto, Ontario, Canada': valid=true.
    3. Valid input: emits an update and valid=true.
    4. Empty input: emits an update and valid=false.
    5. 401 characters: emits an update and valid=false.
- **AgmYear:** the rules are required, max = current year + 1, and min = current year − 2.
  - Test 1: initial state is empty, no input event, valid=false.
  - Test 2: mounting with a year value gives valid=true.
  - Test 3: `onValueChanged()` plus input emits `input` and `valid` after `sleep(300)`.
  - Tests 4–5: invalid inputs (empty, below min, above max) still emit the value but give valid=false.

## Dashboard Alerts component

The tests for the Alerts component are in two shapes.

- **Aggregate suite:** imports Alerts plus 7 alert types (Amalgamation, CorporateOnline, FrozenInformation, InDissolution, MissingInformation, NotInCompliance, NotInGoodStanding). It uses shallowMount with 7 boolean data props and computed getters/setters. It checks that nothing renders without alerts, then runs 7 specs that toggle each type and check visibility and emitted count.
- **Per-alert expansion-panel tests:** each has a closed case and an opened case. The opened case clicks the details button, which changes from "View Details" to "Hide Details", and then checks the panel content.

| Alert | Panel id | h3 / title | Opened content |
|---|---|---|---|
| Future-effective amalgamation (data amalgamationDate='2024-01-31T08:00:00+00:00') | `amalgamation-panel` | "This corporation is part of an amalgamation…historical on January 31, 2024" | ContactInfo; "If you have any questions" |
| Corporate Online (goodStanding=true, BC_COMPANY, non-ben-corps flag=false) | `corporate-online-panel` | "This business must be managed in Corporate Online." | "This BC Limited Company must be"; link "Corporate Online" |
| Involuntary dissolution (BENEFIT_COMPANY, targetDissolutionDate='2024-06-11', currentDate='2024-06-01') | not given | "This business is in the process of being dissolved" | "This business will be struck"; contact info |
| Missing information (SOLE_PROP, MISSING_REQUIRED_BUSINESS_INFO warning) | `missing-information-panel` | "Missing information" | 2 paragraphs ("BC Registries is missing", "If further action is required"); ContactInfo |
| Not in compliance | `not-in-compliance-panel` | "This business is not in compliance" | "To resolve this issue, you MUST..."; ContactInfo |
| Not in good standing (goodStanding=false) | `not-in-good-standing-panel` | "This business is not in good standing" | 2 paragraphs ("The most common reason a", "If further action is required"); ContactInfo |

## Filing and list components

- **AmalgamationFiling:** two describe blocks, Regular and Horizontal, with near-identical tests. They check the title, status "FILED AND PAID", dates (Jan 1, 2021), submitter (John Doe), and the View/Hide Documents toggle. They also check `<h4>` "Amalgamation Complete" and the `<p>` "MY COMPANY has been successfully amalgamated." The filing has status COMPLETED, and the legal name is set through the Pinia business store.
- **IncorporationApplication (skipped):** two cases. One uses entityName "My Business". The other uses businessId "BC1234567" and shows "Numbered Benefit Company". Both check h4 "Incorporation Complete", 2 paragraphs and the reload container.
- **PendingList (skipped):** two cases.
  - Empty data: `#entity-in-good-standing`='No' and `#entity-date-of-incorporation`=''.
  - Business info: the `#about-the-business` card, an `mdi-domain` icon, h2 "About the Business", labels for good standing and date of incorporation, and the values 'Yes' and 'December 31, 2023'.

Caution:
- **AgmExtensionEvaluation:** several tests use identical data setup but expect different `.col-sm-9` text in row 1 depending on the flag combination. The component prioritizes one ineligibility reason over another, so order matters.
- **AgmExtensionHelp:** `wrapper.destroy()` must be called. Omitting it causes memory leaks and state pollution across the suite.
- **AgmLocation:** the test comment on case 5 says "over 100 chars", but the rule enforces 400. The test uses 401 characters to check that the rule catches overflow.
- **AgmYear:** `sleep(300)` is required because validation is debounced. Without it, event assertions fire early. `wrapper.destroy()` after each test prevents fixture leaks.
- **Alerts aggregate suite:** computed properties override the store getters through local test setup. The mocking happens at component level, not in the store.
- **Amalgamation alert:** the date is stored as ISO 8601 with a timezone but displayed as "January 31, 2024". If the formatting or parsing breaks, both tests fail. ContactInfo presence is checked, but its props and content are not.
- **AmalgamationFiling:** the Regular and Horizontal blocks repeat the same assertions and differ only in `displayName`. A fix to one must be made in both, and a parameterized test would remove the duplication.
- **Corporate Online alert:** the feature-flag mock returns null for unmocked flags, so behavior with unmocked flags is undefined.
- **Involuntary dissolution alert:** `warning.code` and `warning.message` are null, but the component still renders. Rendering depends on the `warningType` enum, not on message content.
- **IncorporationApplication:** the tests are skipped (`describe.skip`) and do not run.
- **Missing information alert:** the paragraphs are only checked when the panel is open. ContactInfo renders inside the panel.
- **Not in compliance alert:** both tests call `wrapper.destroy()` but never verify that the panel actually expands or collapses. They only check the button text and the content after the click.
- **Not in good standing alert:** `beforeAll()` sets the store state globally for every test. Panel expansion is async (`await trigger`), and the paragraphs appear only when expanded. There are no lazy-rendering checks.
- **PendingList:** `describe.skip` disables the tests. They are likely incomplete or blocked, and the component itself may not be fully implemented.

## Members

- business-filings-ui: tests/unit/AgmExtensionEvaluation.spec.ts
- business-filings-ui: tests/unit/AgmExtensionHelp.spec.ts
- business-filings-ui: tests/unit/AgmLocation.spec.ts
- business-filings-ui: tests/unit/AgmYear.spec.ts
- business-filings-ui: tests/unit/Alerts.spec.ts
- business-filings-ui: tests/unit/Amalgamation.spec.ts
- business-filings-ui: tests/unit/AmalgamationFiling.spec.ts
- business-filings-ui: tests/unit/CorporateOnline.spec.ts
- business-filings-ui: tests/unit/InDissolution.spec.ts
- business-filings-ui: tests/unit/IncorporationApplication.spec.ts
- business-filings-ui: tests/unit/MissingInformation.spec.ts
- business-filings-ui: tests/unit/NotInCompliance.spec.ts
- business-filings-ui: tests/unit/NotInGoodStanding.spec.ts
- business-filings-ui: tests/unit/PendingList.spec.ts
