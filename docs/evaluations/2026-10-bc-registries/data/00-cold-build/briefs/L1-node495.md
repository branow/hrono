<!-- level 1, node 495, children [176, 181, 206, 207, 302, 305, 316, 330, 361, 362, 379, 395, 410, 453, 456] -->

# Parent brief: BC Registries-style Vue 2 filings and auth front end, with test suites

## What this is
The notes describe a Vue 2 / TypeScript / Vuetify front end for BC Registries-style apps, plus one small Python backend service. Two apps are involved: a business-filings dashboard, and an auth/account-management app with staff review and EFT/payment features. The state layer is Pinia, with some Vuex and Vuelidate. Most entries describe unit tests (Vue Test Utils, Vitest or Jest, sinon, `flushPromises`). A few describe production code, fixtures or helpers.

## Routing map

**Production code**
- **Mixins:**
  - `MixinTester` is an inert test host.
  - `AllowableActionsMixin.isAllowed()` is a switch over 19 actions, using filing type, feature flag, `BUSINESS_ID` and staff role.
  - Others: `CommonMixin`, `DirectorMixin.fieldSorter`, `FilingMixin` (the correction, dissolution and restoration builders), `NameRequestMixin`, the config lookup mixin, and the module index.
- **Dates:**
  - `DateMixin` is a deprecated pass-through to the static `DateUtilities`. Only `yyyyMmDdToPacificDate` and `daysFromToday` are not deprecated.
  - The `DateUtilities` file is truncated in the notes.
- **Backend:** `InvoluntaryDissolutionService.check_business_eligibility`. The flags `ar_overdue` (26 months) and `transition_overdue` (12 months) drive eligibility.
- **Staff-review components (Vue 3 Composition API):**
  - Product fee: `ProductFee`, `ProductFeeSelector`.
  - Read-only account panels: `AccountAdministrator`, `NotaryInformation`, `PaymentInformation`, `AccountStatusTab`, `DownloadAffidavit`, `QsApplication`.
  - Continuation review displays: `ExtraprovincialRegistrationBc`, `HomeJurisdictionInformation`, `PreviousCorrespondence`, `ReviewResult`.
  - The GOVM_REVIEW composable.
  - Other production code: `CautionBox`, `useAccountChangeHandler`, `useAccount`, the date range picker, and the continuation-review types.

**Filing-app tests (business `CP0001191` COOP, `BC0007291` BCOMP)**
- **Filing pages:**
  - `AnnualReport`, `StandaloneDirectorsFiling` and `StandaloneOfficeAddressFiling`.
  - Consent and continuation out: ConsentAmalgamationOut, ConsentContinuationOut, CONTO, ContinuationOut.
  - AGM extension and AGM Location Change.
  - Shared flow checks: rendering, validity flags (`isPageValid`), restoring a draft with FAS, BCOL or no-fee payment, and File & Pay.
    - New filings use POST and redirect via `window.location.assign` to `makepayment/321/...?accountid=`.
    - Drafts use PUT and route to the dashboard.
    - Also covered: the `use-business-dashboard` flag, draft save, payload shape, and 400/402 error handling (`saveErrors`, `saveWarnings`).
- **Components and lists:**
  - `Directors` (fetch and sort, cease/undo, name edit, field validation).
  - Address lists: AddressListSm, OfficeAddresses and the summary lists.
  - Form inputs: AGMDate, AgmLocation, AgmYear, CODDate, EffectiveDate, Certify.
  - Dashboard alerts (expansion-panel pattern), filing-complete messages, and entity info/menu/definitions.
  - `StaffNotation`.
  - `EntityHeader` (badges and name display).
  - `TodoList`, the largest suite, covering states, redirects, delete/cancel, and affiliation invitations.
  - `PayServices`.
- **Root, store and service tests:**
  - `App` loading COOP, BCOMP, historical, temporary-registration and bootstrap filings.
  - Pinia stores, `Dashboard`, `LegalServices` and `AuthServices`.
  - `DateMixin`, `DateUtilities`, `AllowableActions` and `CommonMixin` tests.

**Auth-app tests**
- **Smoke and view tests:**
  - Static/marketing views, account status and suspension views, and login/event tests.
  - Dozens of component smoke tests ("is a Vue instance", element exists) for account, payment, product, staff and generic UI components.
- **Behavioral component tests:**
  - AffiliatedEntityTable, payment-flow components, Product and MemberDataTable.
  - EFT/short-name tables: `LinkedShortNameTable`, `ShortNamePaymentHistory`, `ShortNameSummaryTable`, `ShortNameRefund(View)`, `TransactionsDataTable`.
  - Lookups: `BusinessLookup` and `ShortNameLookup`.
- **Service tests:**
  - Services: `CodesService`, `PaymentServices`, `StaffService`, `UserService`, `NameRequestLookupServices`, the task service, `BusinessLookupServices`.
  - Utilities: the `CommonUtil` suite.

**Fixtures and helpers**
- **Fixtures:**
  - Business and name-request fixtures: the 14-entry `businesses`, the name-request arrays, the sole-proprietor set, and the 22-entry action lookup.
  - Org and payment mocks: `orgsDetailsByAffiliation` and `transactionResponse`.
  - Others: `KEYCLOAK_TOKEN_USER` and `KEYCLOAK_TOKEN_STAFF`, `BCOMP_*` and `FIRM_*` data, `USER_INFO`.
- **Factories and helpers:**
  - `getTestAddress` and `getTestOrg`.
  - `click`, `setValue` and `waitForUpdate`.
  - The mock router, `setupIntersectionObserverMock` and `baseVdataTable`.
  - The global Vue setup file and the Nightwatch `elementCount`.

## Recurring patterns
- **Test setup:**
  - Tests use `createLocalVue`, Vuetify and `data-app`. Many add Vuelidate, a router and Pinia.
  - They seed `sessionStorage` (`AUTH_API_CONFIG`, `BASE_URL`, `CURRENT_ACCOUNT`, `BUSINESS_ID`, `TEMP_REG_NUMBER`) with hardcoded dev or localhost URLs.
  - They mock `$t`, `window.location.assign` and feature flags.
  - Cleanup is `wrapper.destroy()`, `vi.resetModules()` and `vi.clearAllMocks()`.
- **Handlers called directly:** Click triggers often don't work, so tests call `vm.onClickFilePay()`, `onClickSave()` and `onClickSaveResume()` directly.
- **Async handling:** `flushPromises` is needed, and stubs often include `.catch(()=>{})` to silence unhandled rejections.
- **Payment option codes:** NO_FEE=0, FAS=1, BCOL=2.

## Cross-cutting cautions
- **Weak or skipped tests:**
  - Many tests are smoke-only or vacuous. Examples: `toContain('')`, a `vi.fn` whose inner function is never called, and `.findComponent` on the mounted component.
  - Many `.skip` or commented-out suites never run. Examples: PAID/Completed IA, DissolutionVoluntary, IncorporationApplication, PendingList, RegistrationFiling, FasSearchComponent, and the AGMDate and `DateUtilities` timezone tests that fail in CI.
  - A few tests have copy-paste or typo bugs, such as the `#business-address-panell` selector, misnamed suites, and duplicated tests.
- **Mock and framework mixing:**
  - Vitest `vi.*` is mixed with sinon and Jest-style APIs, which fails if the runner isn't Vitest.
  - `setMethods`, `wrapper.destroy` and `createLocalVue` are Vue 2 APIs that break on Vue 3.
  - `Vue.config.silent = true` hides warnings.
  - Mocked `$t` and a mocked `isAllowed()` that always returns true hide i18n and authorization regressions.
  - `shallowMount` or stubbed children can make existence checks pass vacuously.
- **Isolation and ordering:**
  - Module-level `sessionStorage` and Pinia state leak across tests.
  - Restores of `window.location` or sinon stubs happen only in `afterEach`/`afterAll` and are skipped if a test throws.
  - `composition-api-setup` must be imported first.
  - `vi.resetModules()` runs after mount in several suites, so it resets nothing.
  - Tests that mutate shared fixtures or store dates couple to each other.
- **Date and timezone traps:**
  - `+00:00` timestamps display a day earlier in Pacific time.
  - Hardcoded 2023 and 2022 dates are now stale (today is 2026-10-09).
  - `createUtcDate` takes a 0-indexed month, while `yyyyMmDdToDate` takes a 1-indexed month.
  - `DateMixin` is deprecated, so callers should use `DateUtilities`.
- **Production risks:**
  - `eval()` in `compareYyyyMmDd`.
  - `v-html` in `CautionBox` (XSS).
  - `GetFeatureFlag()` returns `undefined` for a missing flag, which silently denies the feature.
  - `validateAndScroll` has a -1 index bug.
  - `getAccountFromSession()` has wrong `||` precedence.
  - `useAccountChangeHandler` has no re-entry guard and leaks its listener.
  - `fieldSorter` crashes on missing fields.
  - `daysBetweenTwoDates(null, null)` returns NaN.
  - `formatAddress` mutates its input.
  - `StaffNotation` has a camelCase vs kebab-case switch mismatch that makes the switch unreachable.
  - `getNrApprovedName` looks up `NameRequestStates.CONDITION` rather than `CONDITIONAL`.
  - A hardcoded JWT sits in a fixture.
- **Fixture defects:**
  - `FIRM_PARTIES` has the typo `'roleTyp'`.
  - The BCOMP filings mock has the typo `filindId`.
  - Name-request fixtures are incomplete and have mismatched IDs.
  - `transactionResponse` totals don't match the line items.
  - Test-name copy-paste errors appear in Statements and Continuation In.
- **Data shape inconsistencies:**
  - `LegalServices` and `AuthServices` sometimes return unwrapped results and sometimes `{data}`.
  - Numeric payment enums are only commented in the tests, not asserted.
  - The "Incorporation Complete" label shown for `CONTINUATION_IN` looks wrong.
