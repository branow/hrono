<!-- level 1, node 494, children [85, 101, 107, 110, 132, 189, 190, 223, 245, 271, 286, 346, 457] -->

# Parent brief: BC Registries Vue front-end (business-filings-ui and auth-web)

**What this covers.** Condensed notes on a BC Government (BCSans, BC Gov blue and gold) Vue 2 + TypeScript + Vuetify front end. It is the business-filings-ui dashboard (v7.3.24) and the auth-web app (v2.6.92). Both are mid-migration from Vue 2/Vuex to Vue 3/Pinia. Class components with `@Prop`/`@Watch`/`@Emit` sit beside `defineComponent`, and `::v-deep` beside `:deep()`. Common stores are `useBusinessStore`, `useRootStore`, `useFilingHistoryListStore`, `useUserStore`, `useOrgStore` and `useConfigurationStore`. Shared pieces are `ContactInfo`, `EnumUtilities`, `DateUtilities`, `sbc-common-components` and `@bcrs-shared-components/*`.

## Routing guide

**1. Styling and design tokens.** SCSS/CSS theme layer.
- Tokens: `$gray0–9`, `$BCgovBlue0–9` (primary `$BCgovBlue5` #003366), `$BCgovGold0–9` (primary `$BCgovGold5` #fcba19), `$app-*` colors, `$px-10–36`.
- Also here: BCSans `@font-face`, layout shell (`.app-container`, `.view-container`, `.container` 1360px), Vuetify overrides (buttons, dialogs, inputs), `.base-table__*`, the split-button actions, tooltips (RGBA(73,80,87,.95) bubble with `:after` arrows), utility classes, and `.loading-container` / `.auto-fade-out`.
- The Vuetify theme config (primary #1669bb, error #D3272C, `customProperties: true`) is in the components group below.
- Imports use `@/assets/scss/theme.scss`, so the `@` alias must resolve.
- Gotchas: tokens are duplicated with slightly different values (`$app-green`), `$BCgovBullet` is misnamed, and many overrides need `!important`.

**2. Dialogs.** About 25 Vuetify dialogs, mostly persistent and 45rem wide.
- Error and unable-to dialogs show `ContactInfo` only when `!isRoleStaff`. Each emits `close`, `exit`, `retry`, `okay`, `proceed` or `toggle`, and the parent must handle them.
- Families:
  - Download, Technical, Fetch, Resume, LoadCorrection and NameRequestInvalid dialogs.
  - Payment, Save and Delete error dialogs, and NotEligibleExtension.
  - NotInGoodStanding, which has dissolve, change-info and generic bodies.
  - BC Wallet credential dialogs.
  - Change-of-address, dissolution and `ConfirmCancelButton` dialogs.
  - `AddCommentDialog`, `AddStaffNotationDialog`, `StaffPaymentDialog`, the correction-type dialog and `manage-business-dialog`.
- A barrel file exports 23 dialogs, and `ConfirmDialog` comes from `@bcrs-shared-components`.
- Gotchas:
  - `DeleteErrorDialog` has a likely AND/OR bug in its title logic.
  - `v-html` in `PaymentErrorDialog` is an XSS risk.
  - Staff users get no contact path.
  - `AddCommentDialog` doesn't check for an empty comment.
  - The correction-type watcher is dead code.
- The `PaymentMethod` SQLAlchemy model is an unrelated backend outlier.

**3. Dialog tests.** Jest/VTU suites for the dialogs above.
- Normal users get `keycloakRoles=['']` and staff get `['staff']`. PaymentErrorDialog uses `[]`.
- Dissolution tests vary by `CorpTypeCd`: SP and GP cite the Partnership Act and BEN cites the Business Corporations Act.
- Gotchas:
  - Call `setActivePinia` first.
  - Use `mount`, not `shallowMount`, for click tests.
  - Stub `StaffPayment`.
  - `wrapper.destroy()` is legacy.
  - `rootStore` mutations leak between tests.

**4. Filing-history feature.**
- **Store:** `FilingHistoryListStateIF` and `useFilingHistoryListStore`, with the `getFilings` filter (silently drops invalid filings), `loadComments` and `loadDocuments`.
- **Specs:** `FilingHistoryList` specs are mostly `it.skip` or commented out and marked "FUTURE". Only amalgamation and paper-only are fully covered.
- **Components:**
  - `FilingHistoryList.is()` picks among 15 renderers (`availableOnPaperOnly` must be checked first). Shared parts are `FilingTemplate`, `HeaderActions`, `DocumentsList`, `DetailsList`, `FiledLabel`, the Subtitle* family and the Body* family.
  - Per-type renderers: Alteration, Amalgamation, ContinuationIn/Out, Consent*, DissolutionVoluntary, IncorporationApplication, ChangeOfAddress, the restoration variants, `AgmExtension`, `StaffFiling` and `PaperFiling`.
  - The `item`-prop family (`PendingTemplate`/`DefaultFiling`) handles pending items.
  - Tools: `StaffNotation`, `ConversionDetails`, PDF upload (pdfjs plus presigned URL) and `FileUploadPreview`.
- **Gotchas:**
  - Several components fall back to `'[unknown]'` instead of failing.
  - There are `v-html` XSS risks in `StaffFiling` and the payment error component.
  - `DetailsList` has apparently inverted staff-name logic.
  - There are typos and bugs (`foreignJusrisdictionCountry`, `'<br/'`).
- **Component-test suites:** Vitest/VTU specs cover heading and paragraph checks per component.
  - Several suites are `describe.skip`: AlterationFiling, BodyFutureEffective, BodyFutureEffectivePending, PaperFiling, StaffFiling.
  - Other suites cover `EntityHeader`, the payment status components, form inputs (`ForeignJurisdiction`, `FileUploadPdf`, `DetailComment`) and `ContactInfo`.
  - Dates convert to Pacific time.

**5. Dashboard and todo list.**
- **Dashboard container:** `fetchData()` runs server date, then Keycloak, then business or bootstrap data, then Launch Darkly. The `reloadData` event refetches. Dashboard layout has Alerts, To Do, Pending, and Filing History on the left, with Custodian, addresses and directors or proprietors/partners on the right.
- **Action menus:** these are dialog pairs plus navigation methods, with `filingId='0'` as the "new filing" magic value.
- **Todo list (the core):** `loadFilingItem` dispatches to about 18 type loaders. Other parts are `doResumeFiling`, the delete flow, and `checkIfProcessed` polling. Template `v-else-if` order is critical.
- **Small components:** the Payment* components and `AffiliationInvitationDetails`.
- **Legal obligations card:** `getObligations` is used in its template but never defined.
- **Alerts panel:** 7 prioritized alert panels in a fixed order (InDissolution first), with the `pointer-events` pattern and NaN as the closed state.
- **Address and party lists:** these use the "Same as above" `isSame` check.
- **Pending list.**
- **Gotchas:** the loaders repeat heavily, errors are only logged with `console.error`, and the Launch Darkly feature flags gate behavior.

**6. Filing forms and app shell.**
- **App.vue:** 7 dialogs, store hydration and breadcrumbs.
- **Shared save workflow:** `onClickSave`, `onClickSaveResume` and `onClickFilePay`, then `saveFiling`. Other parts are the fee codes, 402 handling, `StaffPaymentDialog` and `goToDashboard`.
- **Forms:** AGM extension (eligibility handlers), AGM location change, Amalgamation type selector, AmalgamationOut, Annual Report, Consent*/ContinuationOut, Change of Directors and Office Address.
- **AGM fields:** `AgmDate`, `AgmYear` and `AgmLocation`.
- **Gotchas:**
  - The `goToDashboard` dialog logic is inverted (Yes does nothing, Cancel discards).
  - The double-save guard in AmalgamationOut is wrong.
  - The `validComponents`/`validFlags` pair must be synced by hand.
  - Some notes are truncated.

**7. Generic UI components (auth-web and shared).**
- Display: `DateTooltip`, `IconTooltip`, `CardHeader`, `VcardTemplate`, `LearnMoreButton`, `ExpandableHelp`, `BaseVExpansionPanel`, `InterimLanding`.
- Steppers: `Stepper` (wizard), `Steppable`/`StepperStub`, the route stepper and `InfoStepper`.
- Navigation and data: `ManagementMenu`, `DateRangeFilter`, `PPRLauncher`, `GLCodeDetailsModal` (script incomplete).
- Marketing: a testimonial carousel (interval leak, one quote).
- Theme: the Vuetify theme.
- Gotchas:
  - `InfoStepper` step-4 index bug.
  - `BaseVExpansionPanel` renders `v-html`.
  - `import.meta.url` in `PPRLauncher` is Vite-only.

**8. Auth-web views and flows.**
- Thin wrappers: `NonBcscInfoView`, Dashboard, the digital-credentials gate (blank flash during the permission check) and Transactions.
- Interim landing pages: LeaveTeam, PageNotFound and ProfileDeactivated, which depend on i18n keys.
- Sign-in, sign-out and login wrappers around `sbc-common-components`: `Signin`, `SignoutView` and the Login page.
- Account flow: `AcceptInviteView` (terms, affidavit and profile redirects, then accept) and `AccountSwitching` (the un-awaited `completeAccountSwitch` is a race).
- Standalone: `NameRequestButton` and `AdminDashboardView`.
- Gotchas: Vuex and Pinia are mixed, with TODOs marking the migration.

**9. Tooling, config and infrastructure.**
- Config:
  - EditorConfig (2-space indent, 120-character lines), Prettier (single quotes, no semicolons) and three ESLint variants.
  - TS configs (`strict` contradicted by `noImplicitAny` and `strictNullChecks` being off in business-filings-ui, and `strict: false` in auth-web).
  - The Vite configs, `VUE_APP_` env prefix, the legacy webpack config and the Volar Vetur plugin.
  - Vitest with jsdom (`threads` setting), a Nightwatch e2e (fragile 5s wait) and the dependency lists (Vue 2.7.16 and 2.6.14, both EOL).
  - The i18n loader (English only).
- Infrastructure:
  - Vue JSX and `*.vue` shims.
  - Barrel exports, and datatable helpers (`DEFAULT_ITEMS_PER_PAGE=5`, session-storage pagination).
  - Directives `v-can` and `v-display-mode` (Vue 2 hooks).
  - The bootstrap flow (`ConfigHelper` → LaunchDarkly → Sentry → Hotjar → `syncSession` → `renderVue`).
  - `VueCompositionAPI` is deliberately registered twice, and must be imported first.
  - A global event bus and the router hooks.

## Cross-cutting cautions
- **Migration friction:**
  - Vue 2 hooks, deprecated syntax and class decorators are mixed with Vue 3 forms.
  - Vuex and Pinia are both active, so don't mix state access.
  - Several lint rules are disabled and must be re-enabled for Vue 3.
- **Security:** `v-html` appears in several components (`StaffFiling`, the payment error components, `BaseVExpansionPanel`, table headers). Sanitize the content.
- **Silent fallbacks:** `'[unknown]'`, NaN `filingId` and `console.error`-only handling hide bad data.
- **Magic values:** `filingId='0'` means a new filing (above 0 is a draft, NaN is invalid).
- **Persistent dialogs:** parents must wire every emitted event.
- **Skipped or incomplete code:** many skipped specs, truncated sources and dead code. Check before relying on any of them.
