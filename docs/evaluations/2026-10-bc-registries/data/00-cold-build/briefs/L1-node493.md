<!-- level 1, node 493, children [191, 199, 224, 225, 248, 249, 252, 285, 299, 338, 350, 360, 370, 378, 381, 442, 448, 464, 473, 477, 478] -->

# BC Registries Frontend Ecosystem: Parent Brief

These condensations cover the BC Registries (bcgov) Vue/TypeScript ecosystem. It has three parts: the business-filings-ui (entity dashboard), the auth-web account/team/staff app, and the pay services plus EFT short-name payments. Most code is Vue 2 class components migrating to Vue 3 and Pinia, with Vuetify, LaunchDarkly flags, Keycloak auth and `v-can` role gates. There is one Alembic migration set and a group of deployment notes.

## Groupings

### 1. business-filings-ui (entity dashboard)
- **Stores:**
  - `useBusinessStore` holds `businessInfo` (26 null-initialised fields), getters for dates, status, legal name (`enable-legal-name-fix` flag), type checkers and warnings, 14 setters and `loadBusinessInfo()`. It reads `BUSINESS_ID` from sessionStorage.
  - `useRootStore` (id `'root'`) holds filing and bootstrap status, roles, tasks and parties, with 25 setters, `getReasonText()` and `loadStateFiling`.
- **Bootstrap, routing and utilities:**
  - `main` loads polyfills, Vuetify, LaunchDarkly, Sentry, Hotjar and Keycloak, and sets a custom theme.
  - `getVueRouter()` has a `beforeEach` guard for auth and the `enable-digital-credentials` flag.
  - Route table: filing routes (AGM, annual report, directors, addresses, consents, continuation out, amalgamation) plus the Digital Credentials routes.
  - Utilities: `capitalize`, `formatPhoneNumber`, `sleep`, `navigate`, and `setBaseRouteAndBusinessId` (ID regex `/^(BC|C|CP|FM)\d{7}$/`, temp reg numbers start with T).
  - The barrels re-export components, services, utils and config. Directors is deliberately excluded.
- **Entity UI:**
  - `EntityInfo`, `EntityHeader`, `EntityDefinitions` and `EntityMenu` ("More Actions": Digital Business Cards, Dissolve, Consents, AGM, Amalgamate).
  - Read-only displays: `AboutTheBusiness`, `NameRequestInfo`, office addresses, mailing address and the director list with status chips.
- **Edit forms:**
  - Director management (add, cease, edit name or address).
  - Office address editing with three inheritance checkboxes.
  - Filing form inputs: `CodDate` and effective-date pickers, `ForeignJurisdiction`, Certify, `DetailComment`, contact info.
- **Digital Business Card (credentials):**
  - `CredentialsDashboard` with Table, Menu, Landing and Info.
  - Issuance stepper with `CredentialsWebSocket` (it polls every 1s with RxJS), simple and detail steps.
  - Terms of Use (16 sections).
  - Shared `ModalDialog`, the help dialog and the Authorization Email Sent dialog.
  - `BNRequestManager` and `ResubmitRequest` for Business Number requests.
- **Tests:** TodoList draft-deletion tests (staff vs regular user).

### 2. auth-web: shell, stores and routing
- **Shell and settings:** the sticky header (Vuex+Pinia hybrid, `refreshKey`), and `AccountSettings` (left nav, `tryOrgRefresh` polling).
- **Pinia stores:**
  - `useAuthenticationStore`, plus the configuration, `app` and legacy Vuex 3 stores.
  - Business store: affiliations, `createNamedBusiness`, BN requests.
  - Codes store.
  - Org store: about 80 exports, covering orgs, members, invitations, payments, NSF, refunds, products and fees.
  - Staff store (about 30 exports), task store and user store.
- **Router and helpers:**
  - The router guard runs 8 ordered checks.
  - 40+ routes with `requiresAuth`, `allowedRoles` and `disabledRoles`.
  - Breadcrumb factory and constants.
  - `ConfigHelper` (40 URL getters), enums (`SessionStorageKeys`, `Role`, `Pages`, `InvoiceStatus`) and navigation handlers.
- **Models and utils:** interfaces and barrels for orgs, users, addresses, affiliations, transactions, invoices, EFT and short names. `CommonUtils`, `ShortNameUtils` and `debounce`.
- **Composables and headers:** `useAffiliations`, `useTransactions`, the table-data factory, Base text/select filters, and affiliation and transaction table headers.
- **Shared mixins:** `AccountMixin`, `NextPageMixin`, org-sync handler, `DateMixin`, pagination mixin and `Steppable`.

### 3. auth-web: onboarding and account setup
- **Landing and content:**
  - `HomeView` and the business-lifecycle views: Decide, IncorpOrRegister, Maintain and Name Request start.
  - `PriceListView`, `StartNewBusinessHelp`, the onboarding infopage and Terms of Use dialogs.
  - `IncorporationSearchResultView`.
- **Authentication choice:**
  - "Learn more" dialogs for BCeID (7 steps), BC Services Card Reader (8 steps) and Mobile Card (7 steps).
  - The auth method chooser, `BcscPanel` and `LoginBCSC`.
  - The non-BCSC affidavit path: Overview, `AffidavitDownload` and `UploadAffidavitStep`.
- **Invites:**
  - `AcceptInviteLandingView` (branches by BCROS, BCEID, BCSC or IDIR).
  - `BceidInviteLanding` and `CreateUserProfileView`.
  - `NonBcscAdminInviteSetupView`.
- **Account setup:**
  - `AccountCreateBasic`, `AccountCreatePremium` (BCOL link), the Govm forms and `SetupAccountForm`.
  - `AccountSetupView` stepper and the setup landing component.
  - Success, duplicate-account and unauthorized/pending pages.
  - `AccountLoginOptionPicker` and login-option settings.
  - `BusinessProfileView`, `UserProfileView` and `ReviewAccountView`.
- **Forms:** `BusinessContactForm`, `PasswordReset`, bulk add team members, `NotaryInformationForm` and `NotaryContactForm`, `AddNameRequestForm` and `GeneratePasscodeView`.

### 4. auth-web: account management, team and staff
- **Account Info:** `AccountDetails`, `AccountMailingAddress`, `AccountAccessType` (REGULAR/GOVN) and the business type picker.
- **Alerts and deactivation:** the inactive/suspended alerts, `DeactivateCard`, the deactivation flow, `ActivityLogs` and `ExistingAPIKeys`.
- **Products and statements:** `Product`, `SelectProductService`, `ProductFeeViewEdit`, `ProductTOS`, `Statements` and `StatementSettings` (gated by the `EnableEFTPaymentMethod` flag).
- **Affiliations:**
  - `EntityManagement`, `AffiliatedEntityTable`, `AffiliationAction`, `BusinessLookup` (600ms debounce), `SearchBusinessNameRequest`.
  - The manage-business dialog, `AccountAuthorizationRequest` and `PasscodeResetOptionsModal`.
- **Team and member management:**
  - `UserManagement`, `AnonymousUserManagement`, `MemberDataTable`, `PendingMemberDataTable`, the invitations table and `OrgAdminContact`.
  - `SearchFilterInput` and `TeamManagementMixin`.
- **Staff tools:**
  - `StaffAccountsTable` with Active, Inactive, Pending, Rejected and Suspended wrappers.
  - `ContinuationApplicationTable` and review pages.
  - `GLCodesDataTable`.
  - `StaffCreateAccountModal`, `AccessRequestModal` and the task approval modal.
  - Dissolution batch tools, the Staff Dashboard and `SafeEmailView`.
- **Generic infrastructure:** the base data table, `HeaderFilter`, the intersection sentinel and the sticky-actions-column SCSS recipe.

### 5. Payments and NSF (auth-web)
- **Payment methods:**
  - `PaymentMethods` selector with CREDIT_CARD, EFT, PAD, BCOL and ONLINE_BANKING.
  - `AccountPaymentMethods`, `MakePayment`, `PADInfoForm`, the GL form and `CompletePaymentDetails`.
- **Outstanding balances:** `OutstandingBalances`, `PayOutstandingBalanceView`, `PayWithCreditCard`, `PayWithOnlineBanking` and `PaymentPendingOnlineBanking`.
- **Gateway flow:** `CcPaymentView`, `CcPaymentReturnView`, `PaymentReturnView`, `PaymentView` and `PaymentErrorMessage`.
- **NSF suspension and unlock:**
  - `AccountSuspendedView`, `AccountOverviewNSFView` ($30 fee per failed PAD payment) and `ReviewBankInformation`.
  - The unlock stepper has 2 steps for EFT and 3 for PAD, with `pollForAccountUnlock` (5 tries at 2s).
  - `AccountUnlockSuccess` polls every 3s within a 10s timeout.
- **Pages:** the Transactions page and the Developer Access page.

### 6. EFT short names
- **Views:** `ShortNameMappingView` (tabbed and detail versions), `ShortNameSummaryTable`, `LinkedShortNameTable` and `UnlinkedShortNameTable`.
- **Linking:** the account lookup autocomplete (600ms debounce) and `ShortNameAccountLinkage` (Apply, Cancel, Unlink).
- **Detail and refunds:**
  - `ShortNameFinancialDialog`, `ShortNamePaymentHistory` (Reverse Payment has a 60-day limit) and `ShortNameRefund`.
  - `ShortNameRefundView` (amount must be above 0 and at most `creditsRemaining`).
  - The OPS-only MVP payment refund UI (FULL or PARTIAL).
- **Shared:** `ShortNamePaymentActions`, `PaymentService` and `CommonUtils.formatAmount`.

### 7. Database migrations (Alembic)
- **Lookup and reference tables:**
  - `business_size_codes` and `business_type_codes`, with org columns.
  - The `is_government_agency` and `is_business` flags (1e4b6359f470) and deletion of GOVM (7bf8428e568e).
  - Corp type inserts: NR, RTMP, TMP, SP/GP, ULC/LTD/CCC, the Continuation In variants and CC.
  - Org status, org type and `staff_remark_codes` seeds.
- **Schema changes:**
  - `product_codes.can_resubmit` and `tasks.is_resubmitted` (e65cc8ab51cc).
  - A Keycloak group backfill for MHR/PPR.
  - `account_payment_settings` (06eda339e0d5).
- **Other:** a cattrs converter (Decimal→float, datetime→ISO, `remove_nones`).

### 8. Deployment, CI/CD and ops
- **Frontend env config:** `VUE_APP_*` dev config for business-filings-ui (clientId `entity-web`) and auth-web (clientid `account-web`), plus 1Password-templated versions.
- **Firebase PR-preview pipelines:** Cloud Build to project `yfthig-dev`, channel `PR-$_PR_NUMBER`, posting the channel URL as a PR comment.
- **Pay Cloud Deploy pipelines:** dev→test→sandbox→prod for payment-jobs, pay-admin, pay-api and pay-queue.
- **Backend env templates:** pay-api, pay-admin, pay-queue and jobs (CGI, Oracle, EFT).
- **DB masking:** Docker image, Cloud SQL sandbox restore and anon masking.
- **Runbook snippets:** a Pub/Sub staff review publish example and `pg_stat_activity` queries.
- **Zenhub migration env vars.**

## Caution
- **Possible bugs and inverted logic**
  - **business-filings-ui**
    - Root getters such as `isAmalgamationTodo()` may call `getBootstrapFilingStatus` without `this.`.
    - Director `toggleAction` uses `splice(index)` instead of `splice(index, 1)`.
    - `ceaseDirector` fee logic looks inverted.
    - Credentials polling watch conditions are inverted.
  - **auth-web: sort and gating**
    - `customSortPending` and the GL codes `customSortActive` sorts are swapped.
    - `MemberDataTable` coordinator sort is inverted.
    - The deactivation `authorised` getter is inverted.
    - `TermsOfUse` version comparison looks inverted.
    - `EntityDetails` priorities are inverted.
  - **auth-web: stores**
    - `syncSuspendedStaffOrgs` assigns to `pendingInvitationOrgs`.
    - `getUserAccountSettings` uses `this.context.state`.
    - The task-store count cache blocks updates when the count is 0.
  - **auth-web: wiring**
    - `isStatementsAllowed` is checked without `()`.
    - `viewOnlyMode('address')` has a wrong argument shape.
    - The shortnamerefund route's `eftRefundId` prop uses `Number(route.params.shortNameId)`.
  - **Payments**
    - `Statements` calls async `enableEFTPaymentMethod` synchronously.
    - `AccountAccessType` overwrites GOVM with REGULAR on save.
  - **EFT short names**
    - The `ShortNameRefundView` read-only branch is unreachable.
    - The `isFormValid()` name is backwards.
  - **Migrations**
    - Migration 8770c44d3d66 mismatches the `desc` and `description` keys.
    - `d2cb317afb6e` downgrades to `nullable=True`.
- **Import cycles:** `useBusinessStore` and `useRootStore` import each other. Directors is excluded from the shared barrel for the same reason.
- **Silent failures:** many catch blocks only `console.log` or are empty. Examples are `GeneratePasscodeView`, the Keycloak backfill, `getCodes()` returning undefined, `createNumberedBusiness`, and the Statements download.
- **Polling and timeouts:** NSF unlock, org refresh and unlock success all stop after a fixed time without a clear fallback. They give a false failure when processing is slow.
- **Security and data:**
  - `Entity.passCode` is plaintext.
  - Temporary passwords are shown unmasked and stored in `state.createdUsers`.
  - `BcolLogin` emits credentials on every keystroke.
  - The `Keycloak` token guard doesn't check expiry.
- **Vue 3 migration debt:** Vuex `updateHeader` commits, `::v-deep`, `.sync`, the `Steppable` mixin, and `this.$router` inside `setup`. Both stores and `Vuex` remain, with no clear upgrade path.
- **Hardcoded values and typos:** `FolioNumberload`, `CreatAccountBreadcrumb`, `showReponseDialog`, `resetoCurrentSelectedProducts`, `apliKeyList`, `isAffidaventPendingAdmin`, " Number" with a leading space, "Reponsiblity Center". Many are used consistently, so renaming needs a coordinated change.
- **Config and deployment**
  - Blank dev keys (Address Complete, Sentry, Hotjar, LD client ID for auth-web, Search and MHR) disable those features.
  - `$APP_ENV` must be substituted for `op://` references to resolve.
  - Pay pipelines deploy sandbox to `gtksf3-tools`, use `verify: false`, and give dev and test no scale specs.
  - The bare pay-api/queue/admin pipeline manifests are stubs.
  - Job secrets (CGI SFTP password, Oracle credentials, `EFT_HOLDING_GL`) are empty, and port 21 is FTP.
- **Migrations:** the Keycloak backfill has an empty downgrade. TRUNCATE CASCADE in 4150773f899f and the destructive GOVM delete can fail or lose data on downgrade.
- **Truncated or missing source:** several excerpts are cut off (business store, staff store, `UserManagement`, `AccessRequestModal`, Account Info, `ShortNameAccountLinkage`, `ShortNameSummaryTable`, BCSC template, `getRoutes()`). Their behavior is unverified.
