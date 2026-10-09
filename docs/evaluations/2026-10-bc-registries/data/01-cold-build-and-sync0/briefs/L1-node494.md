<!-- level 1, node 494, children [85, 101, 110, 132, 189, 223, 245, 271, 346, 457, 530, 531, 542, 543, 569, 570, 571, 572] -->

# Parent brief: BC Registries Vue front-end (business-filings-ui and auth-web)

**Scope.** These are the front-end layers of two BC Registries apps, **business-filings-ui** (v7.3.24) and **auth-web** (v2.6.92). The stack is Vue 2.x with Vuetify 2 and TypeScript. It uses class components (`vue-property-decorator`, `pinia-class`) and runs on Vite. State is moving from Vuex to Pinia (`useRootStore`, `useBusinessStore`, `useFilingHistoryListStore`, `useOrgStore`, `useUserStore`, `useConfigurationStore`). Both apps are mid-migration to Vue 3, so legacy and new syntax are mixed throughout. The visual style is BCSans with BC Gov blue (`$BCgovBlue5` #003366) and gold (`$BCgovGold5` #fcba19).

## Routing guide

### 1. Styling and design tokens (SCSS/CSS)
- **Tokens:** the `$gray0`–`9`, `$BCgovBlue0`–`9`, `$BCgovGold0`–`9` and accent ramps; `$app-blue`, `$app-red`, `$app-green`; `$px-10`–`$px-36`; the CSS root variables.
- **Base styles:** BCSans `@font-face` (weights 400 and 700 only), headings, and the `.v-application` font override.
- **Layout classes:** `.app-container`, `.app-header`, `.view-container`, and a 1360px max-width.
- **Vuetify overrides:** buttons, dialogs, alerts and inputs.
- **Components:** `.base-table__*` and the split-button actions; `.v-tooltip__content` bubbles with arrows in RGBA(73,80,87,.95), in two variants.
- **Utilities:** `.loading-container` and `.auto-fade-out`.
- **Theme:** the Vuetify theme palette (primary `#1669bb`, `customProperties: true`).
- **Import path:** the `@/assets/scss/theme.scss` import needs the `@` alias set up.

### 2. App shell, bootstrap and shared infrastructure
- **App component:** manages seven dialogs and the `store*` methods. Its route watcher refetches data on DASHBOARD.
- **Bootstrap:** `ConfigHelper` → `LaunchDarklyService` → Sentry → Hotjar → Keycloak `syncSession` → `renderVue`. `VueCompositionAPI` must be imported first, and removing it breaks the Manage Business button.
- **Shared infrastructure:**
  - The event bus.
  - Type shims for `*.vue` and the JSX namespace.
  - Barrel exports.
  - Table and pagination helpers: `DEFAULT_ITEMS_PER_PAGE=5` and session-storage helpers.
  - The `v-can` and `v-display-mode` directives, which use the Vue 2 `inserted` hooks.
- **Wrappers:** thin routing and landing wrappers (`InterimLanding` with i18n keys) and the sign-in/out wrappers around `sbc-common-components`. They also include `AcceptInviteView` and `AccountSwitching`, which are auth-web account flows.
- **Primitives:** display and stepper primitives (`Stepper`, `InfoStepper`, `DateRangeFilter`, `CardHeader`, `IconTooltip`, `DateTooltip`).

### 3. Config and tooling
- **Linting and formatting:** EditorConfig (2-space indent, 120-character lines), Prettier (single quotes, no semicolons), and three ESLint variants.
- **Compiler and build:** TypeScript configs, Vite and legacy webpack configs, and the Volar/Vetur plugin.
- **Testing:** Vitest with `@vue/test-utils` 1.3.x and jsdom, plus a Nightwatch smoke test.
- **Dependencies and i18n:** dependency lists, and an auth-web i18n loader that supports English only.
- **Env var prefix:** `VUE_APP_` is required.

### 4. Dashboard (business-filings-ui)
- **Container and layout:**
  - `Dashboard` has a left column (Alerts, To Do, Pending, Filing History) and a right column (Custodians, Addresses, Directors or Proprietor/Partners).
  - `fetchData()` runs in this order: server date, auth, data, Launch Darkly.
  - It also handles business summary download and digital credentials.
- **Alerts:** the `Alerts` container orders seven expansion panels, with InDissolution first. Others include CorporateOnline, FrozenInformation, MissingInformation, NotInCompliance and NotInGoodStanding. All use a `pointer-events` pattern and a `togglePanel` event.
- **Lists:** address, director, custodian and proprietor/partners lists, and `PendingList`.
- **Todo list:** the central piece.
  - `loadFilingItem(task)` dispatches to about 18 type-specific loaders.
  - It has first-match-wins action buttons, `checkIfProcessed()` polling, and `doResumeFiling`.
  - Related: action-menu and navigation methods, the legal-obligations card, and the small payment-status components.

### 5. Filing history UI
- **Container and shared pieces:**
  - `FilingHistoryList` picks a sub-component through `is(filing)`, where `availableOnPaperOnly` must come first. It hosts four dialogs.
  - Shared pieces: `FilingTemplate`, `HeaderActions`, `DocumentsList`, `DetailsList`, `FiledLabel`, the subtitle components, and the future-effective bodies.
- **Filing-type components:** Alteration, Dissolution, IA, ContinuationIn, Consent/ContinuationOut, Amalgamation, ChangeOfAddress, StaffFiling, AgmExtension, the LimitedRestoration variants, PaperFiling, ConversionDetails and ArDate. Several of these are thin wrappers over `FilingTemplate`.
- **Related pieces:** `StaffNotation`, `FileUploadPreview`, and the PDF upload validator (pdfjs).
- **Store:** `useFilingHistoryListStore` holds the dialog flags, the filings, loading flags and the panel. `getFilings` filters out invalid filings and `displayLedger===false`.

### 6. Filing forms (business-filings-ui)
- **Workflow pattern:**
  - Shared across all filings: Save, Save and Resume Later, File and Pay, and Cancel.
  - `saveFiling(isDraft)` and the `*Finish()` methods.
  - A 402 response means the changes were saved.
  - `haveChanges`, `filingId` (0 = new) and a `SaveErrorReasons` retry flow.
  - An affixed `SbcFeeSummary`.
- **Filings:** AGM Extension, AGM Location Change, Annual Report, Change of Directors, Office Address change, Amalgamation (type selection and out), Consent Amalgamation Out, Consent Continuation Out and Continuation Out. The last three are staff-related.
- **AGM widgets:** `AgmYear`, `AgmLocation`, `AgmDate`, `ExtensionRequest` (with its four eligibility handlers), `AgmExtensionEvaluation` and `AgmExtensionHelp`.
- **Director action helpers:** `isNew`, `isAddressChanged` and the related helpers.

### 7. Dialogs
- **Error dialog pattern:**
  - Persistent `v-dialog` with `dialog` and `attach` props (45rem).
  - `ContactInfo` shown only when `!isRoleStaff`.
  - Bare `@Emit` handlers (`close`/`exit`/`retry`/`okay`/`proceed`).
- **Error dialogs:**
  - Fetch, technical, download and load-correction.
  - Resume and save.
  - Delete and payment.
  - Business-auth, name-request and credential errors.
  - Not-eligible-for-extension.
  - NotInGoodStanding, which uses the `NigsMessage` enum.
- **Decision and form dialogs:**
  - Confirm dissolution, which varies by business type.
  - Change-of-address warning.
  - Correction-type chooser.
  - AddComment.
  - AddStaffNotation (four filing types).
  - StaffPayment.
- **Auth-web wrappers:** `ConfirmCancelButton`, the manage-business dialog and `WarningPopover`.
- **Barrel and outlier:** a barrel of about 23 dialogs, and the unrelated SQLAlchemy `PaymentMethod` model.

### 8. Test suites
- **Filing history specs:**
  - The `FilingHistoryList` specs are mostly `it.skip`, commented out or marked "FUTURE".
  - Typed filing specs cover IA, alteration, continuation, restoration, staff, paper-only, AGM and amalgamation filings. Others cover documents and comments, and the correction redirect to the edit URL with `correction-id`.
- **Dialog specs:** these use `setActivePinia(createPinia())`, `keycloakRoles` (`['']` for normal users, `['staff']` for staff), and `mount` rather than `shallowMount` for event triggers.
- **Component specs:** payment status, filing-status bodies, form inputs (`DetailComment`, `FileUploadPdf`, `ForeignJurisdiction`, `BusinessNameForeign`), `EntityHeader`, `ContactInfo` and date and tooltip formatting. Several suites use `describe.skip`.

## Cross-cutting cautions

- **Vue 2 to 3 migration.**
  - Deprecated patterns remain: `@click.native`, `beforeDestroy`, `::v-deep`, `.sync`, `inserted` hooks and `wrapper.destroy()`.
  - `:deep()` is mixed in with Vue 2 decorators.
  - Vuex and Pinia are both live, so do not mix state access between them.
  - Vue 2.6/2.7 is end-of-life, and some libraries (`pinia-class`, `vue-plugin-helper-decorator`) are barely maintained.
- **Magic values.**
  - `filingId='0'` means a new filing in routing.
  - `filingId` can be 0, NaN or positive. Pages that don't support resuming a draft redirect away when it is non-zero.
  - An unnamed `?? 'Unknown'` or `'[unknown]'` fallback hides missing data.
- **Staff vs non-staff.**
  - `ContactInfo` is inverted (non-staff only).
  - Some forms are staff-only, and `created()` can throw for non-staff.
  - Contact numbers are hardcoded (1-877-526-1526).
- **XSS.** `v-html` is used on user or API content in several places (`StaffFiling` order details, `PaymentErrorDialog` messages, the payment error component, `BaseVExpansionPanel` info, `BaseTableHeaderI.value`). Sanitize it.
- **Redirects and navigation.**
  - `window.location.assign` or `href` causes full reloads.
  - The `tempRegNumber` and `BASE_URL` session values aren't validated.
  - Store getters and the `@` alias must be configured.
- **Persistent dialogs.** Only the buttons close them, so the parent must handle every emit. Bare emits carry no payload.
- **Date handling.** Dates are converted to Pacific time through `DateUtilities`. `'[unknown]'` is the fallback, and test fixtures can be fragile around time zones and hardcoded 2099 dates.
- **Async races.** Examples: `AccountSwitching.completeAccountSwitch()` isn't awaited, the Amalgamation Out double-save guard checks `busySaving` but sets other flags, and recursive `setTimeout` polling is used in the todo list.
- **Todo-list fragility.** Loaders are heavily duplicated, the `v-else-if` order is critical, and missing item properties fail silently.
- **Test hygiene.**
  - Reset store mutations between tests.
  - Set `document.body.setAttribute('data-app','true')`.
  - Avoid hardcoded paragraph indexes.
  - Check for skipped or commented-out suites before trusting coverage.
- **Known suspect code.**
  - The `DeleteErrorDialog` title condition should likely use `&&`.
  - `getObligations` is used in the legal-obligations card template but never defined.
  - The `StaffFiling` `'<br/'` replace has a typo.
  - `foreignJusrisdictionCountry` is misspelled in `ConsentContinuationOut`.
  - Test 3 of the correction specs reuses an id that is probably wrong.
  - `isAuthorizedToContinueOut` grants authorization when no consent filing exists.
