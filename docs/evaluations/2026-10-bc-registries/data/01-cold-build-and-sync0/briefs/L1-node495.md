<!-- level 1, node 495, children [176, 181, 206, 207, 302, 305, 316, 330, 379, 395, 410, 453, 582, 583, 584, 585, 586, 587, 620, 621] -->

# Parent brief: BC Registries front ends (business-filings web, auth/account web, staff review) and a small Python dissolution service

**Scope.** Condensed notes on the test suites, fixtures, mixins, composables and types of several Vue 2 / Vuetify / Pinia apps from a BC Registries-style codebase. Some code is Vue 3 Composition API. A few notes cover non-test source.
- **Filings app:** annual report, change of directors, change of address, consent and continuation out, AGM extension and location change, the dashboard, the entity header and menu, the todo list, and the filing history list.
- **Auth/account app:** account setup, payment, staff and team management, and affiliated-entity tables.
- **Staff review app:** account approval and continuation-in review.
- **Backend:** one Python service.

Most suites use Vitest with sinon and axios stubs. Many are smoke tests that only assert `wrapper.vm` is truthy or that an element exists.

## Where things are

### 1. Shared mixins, date utilities and backend (filings app)
- **Mixins:**
  - `MixinTester` is an inert wrapper for mounting mixins.
  - `AllowableActionsMixin.isAllowed()` is a switch over 19 actions. It combines `isAllowedFiling`, entity-type getters, feature flags, `sessionStorage.BUSINESS_ID` and `isRoleStaff`.
  - `CommonMixin`, `DirectorMixin.fieldSorter`, `FilingMixin` (builders for correction, dissolution and restoration), `NameRequestMixin`, and a config-lookup mixin (`certifyText`, `displayName`, `directorWarning`).
  - The module index re-exports them, including `CountriesProvincesMixin` from `@bcrs-shared-components`.
- **Dates:** `DateMixin` is about 20 deprecated forwarders to the static `DateUtilities`. Only `yyyyMmDdToPacificDate` and `daysFromToday` are not deprecated. The `DateUtilities` source is truncated.
- **Backend:** `InvoluntaryDissolutionService.check_business_eligibility(identifier)` returns `(bool, EligibilityDetails)`. It uses the `ar_overdue` (26 months) and `transition_overdue` (12 months) flags, across many entity types.

### 2. Filing-page suites (filings app)
These all share one setup: Pinia stores, a mock router, stubbed axios for `businesses/<id>/filings`, `filings/123` and `tasks`, a mocked `window.location.assign`, and `sessionStorage` `BASE_URL` and `CURRENT_ACCOUNT`. Identifiers are CP0001191 (COOP) and BC0007291 (BCOMP).
- **Flows covered:**
  - **Rendering and validity:** the sub-components render, and `isPageValid`/`isEditPageValid` depend on form-valid flags plus non-empty `filingData`.
  - **Draft restoration:** FAS restores option 1, BCOL option 2 and No Fee option 0.
  - **Submit and payment redirect:** POST (`filingId=0`) redirects to `makepayment/321/...?accountid=`. PUT (`filingId=123`) routes to the dashboard. The `use-business-dashboard` flag switches to `utils.navigate`.
  - **Draft save and resume.**
  - **Payload shape:** ceased directors are handled per component, and `routingSlipNumber` is undefined for BCOMP.
  - **Errors:** 400 populates `saveErrors` and `saveWarnings`. 402 gives `[{message:'payment required'}]`.
- **Components:**
  - `AnnualReport`
  - `StandaloneDirectorsFiling`
  - `StandaloneOfficeAddressFiling`
  - Consent/continuation out: `ConsentAmalgamationOut`, `ConsentContinuationOut`, and `CONTO` (staff).
  - AGM location change and AGM extension.
  - `ExtensionRequest`
  - `ContinuationOut`
- **Display components:**
  - `Directors` (COOP and BC):
    - Re-sorts by name.
    - Handles cease/undo.
    - Handles name edit.
    - Validates new-director fields.
    - Raises compliance warnings.
  - The `*ListSm` list components, `OfficeAddresses`, and the summaries.
  - `Certify`, `AGMDate`, `CODDate`, `EffectiveDate`, `AgmYear`, `AgmLocation`.

### 3. Dashboard, header, menus and lists (filings app)
- **Root `App`:** loads existing businesses and temp-registration or bootstrap filings. Draft filings go to `rootStore.tasks` and completed ones to `filingHistoryListStore.filings`. It also loads historical businesses (voluntary dissolution, continuation out, amalgamation).
- **Other suites:**
  - `EntityHeader`, `EntityMenu`, `EntityInfo`, `EntityDefinitions`, `StaffNotation` and `HeaderActions`.
  - `TodoList`: the largest suite, with state rendering, redirects, delete and cancel, and invitations.
  - `PendingList` and `FilingHistoryList` continuation-in displays.
  - The Dashboard alerts (amalgamation, Corporate Online, dissolution, missing information, compliance, good standing).
  - `AmalgamationFiling`, `LegalServices`, `PayServices`, and the configuration actions.
- **Fixtures:** KEYCLOAK tokens, address, director and party fixtures, name-request and business arrays, and a 22-object action lookup table.

### 4. Auth/account web (auth-web)
- **Account pages:** `AccountInfo`, `AccountInformation`, `AccountAccessType`, `AccountBusinessType`, `AccountTypeSelector`, `AccountDetails`, `AccountMailingAddress`, `AccountPaymentMethods`, `ProductPackage`, `ProductFee`.
- **Alerts and views:**
  - The suspend, freeze, hold and NSF views.
  - Landing and info views.
  - `Login`, `Signout`, `DashboardView`, `PaymentReturnView`, `StaffDashboardView`, `BusinessProfileView`, and the Govm account setup.
- **Tables:**
  - `AffiliatedEntityTable` (invite sorting and status text).
  - Invitation, member and pending-member tables.
  - Staff active, suspended, rejected and inactive account tables.
  - `ContinuationApplicationTable`.
- **EFT/short-name tables and lookups:**
  - `ShortNameSummaryTable`, `ShortNamePaymentHistory`, `ShortNameRefund`, `ShortNameRefundView`
  - `LinkedShortNameTable`, `BusinessLookup`, `ShortNameLookup`
  - `TransactionsDataTable`
- **Payment components:** `PaymentMethods`, `PaymentMethodSelector`, `PaymentCard`, `PayWith*`, `PaymentErrorMessage`, `PADInfoForm`, `ReviewBankInformation`.
- **Staff dissolution UI:** `DissolutionSchedule`, `InvoluntaryDissolution`.
- **Forms and modals:** the `ManageBusinessDialog` computeds, the `EntityManagement` modals, the Stepper, a date range picker, and `CautionBox`.
- **Composables and helpers:**
  - `useAccountChangeHandler` and `useAccount`
  - the `mock()` router helper
  - `setupIntersectionObserverMock`
  - global Vue test setup and `baseVdataTable`
- **Services:** `Codes`, `Payment`, `Staff`, `User`, `Task`, `NameRequestLookup`, `BusinessLookup` and `AuthServices`, plus the `CommonUtil` suite.
- **Fixtures:** org, transaction and address factories.
- **Nightwatch:** an e2e test and an `elementCount` assertion.

### 5. Staff review app
- **Product fee:** `ProductFeeSelector` and `ProductFee`.
- **Read-only panels:** `AccountAdministrator`, `NotaryInformation`, `PaymentInformation`, `AccountStatusTab`, `DownloadAffidavit`, `QsApplication`.
- **Account info and access type:** `AccountInfo` and access type, `Agreement`.
- **Continuation review:**
  - `ExtraprovincialRegistrationBc`, `HomeJurisdictionInformation`, `PreviousCorrespondence`, `ReviewResult`.
  - The `ReviewStatus`, `ContinuationReviewIF` and `ContinuationFilingIF` types.
  - `ReviewFilterParams` and `ReviewList`.
- **GOVM_REVIEW composable:** the setup that drives approve, reject and hold.

## Cross-cutting cautions
- **Silenced warnings:** `Vue.config.silent = true` is widely used. It hides prop-mutation and other warnings.
- **Stub-style tests:**
  - Many suites are smoke tests with weak or unreachable assertions: `toContain('')`, `.toBeTruthy()` on queries, a `findComponent` on the wrapper itself, and tooltips outside the wrapper.
  - A number are `.skip`, or commented out, or placeholders: `FasSearchComponent`, `IncorporationApplication`, `PendingList`, Dissolution, Registration, and several `TodoList` blocks.
  - Mocked `$t` returns `''` or a fixed string, so i18n is never verified.
  - `shallowMount` stubs hide children.
- **Handlers called directly:** Clicks do not work in many suites, so tests call `onClickFilePay`, `onClickSave` and similar directly.
- **Mixed frameworks:** `vi.*` (Vitest) is mixed with sinon and Jest-style APIs. `wrapper.destroy()`, `setMethods` and `createLocalVue` are deprecated Vue 2 patterns that block a Vue 3 migration.
- **Cleanup and leakage:**
  - `window.location` is mocked in `beforeAll` and restored in `afterAll`, which is skipped on a throw.
  - Sinon stubs restore only in `afterEach`.
  - `sessionStorage` config and store state are set globally and leak across tests.
  - `vi.resetModules` and `vi.clearAllMocks` often run after mount.
  - Import order matters: `composition-api-setup` must come first.
- **Hardcoded config and dates:**
  - Hardcoded localhost and dev API URLs, and a hard-coded JWT.
  - AGM extension dates around 2023 are stale as of today (2026-10-09).
  - Approved name-request expirations are fixed at 2022-11-22.
  - Timezone off-by-one displays: `+00:00` dates show a day earlier, and `Statements.formatDate` shifts a day back.
- **Known source or fixture oddities:**
  - The `DateUtilities.compareYyyyMmDd` uses `eval()`.
  - Missing feature flags silently deny.
  - `validateAndScroll` can pass -1 to `getElementById`.
  - `CautionBox` uses `v-html` (XSS).
  - `useAccount.getAccountFromSession` has a dead `|| '{}'` fallback.
  - `getNrApprovedName` uses `CONDITION`, which may be a typo.
  - Typos in fixtures: `roleTyp`, `filindId`.
  - Duplicate IDs in the fixtures.
  - The StaffNotation switch keys are camelCase but the menu `data-type` values are kebab-case.
  - Copy-paste test names and misattributed assertions, such as the `ManageBusinessDialog` flags and the `ProductFee` suite named `PaymentInformation`.
  - A selector typo (`#business-address-panell`), and a duplicated `ReviewResult` test.
  - Several tests have unclear or never-assigned `store` variables.
- **Test data conventions:** `isPageValid` is driven by `setFilingData([{}])` versus `[]`, where only presence matters. Payment option numbers are 1 for FAS, 2 for BCOL and 0 for No Fee.
