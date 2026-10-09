<!-- level 1, node 493, children [191, 199, 224, 225, 248, 249, 252, 285, 299, 338, 360, 378, 381, 442, 464, 473, 477, 478, 578, 579, 588, 589, 590, 615, 616] -->

# Parent Brief: BC Registries Vue/TypeScript Frontends (auth-web, business-filings-ui, pay services)

**What this is:** Condensed notes on the BC Registries (bcgov) frontend ecosystem. The main apps are auth-web (account, org and team management, onboarding, staff back-office, EFT/payments UI), business-filings-ui (entity-web, the dashboard and filings), and a Digital Business Card (credentials) feature. The notes also cover the pay backend deployment (pay-api, pay-admin, pay-queue, payment-jobs). The code is Vue 2 class components and Vue 3 Composition API, partway through Vuex→Pinia and Vue 2→3 migrations. It uses Vuetify, LaunchDarkly flags, `v-can` role directives, and Keycloak auth.

## Where to look (routing)

**Business-filings-ui (entity dashboard)**
- **Stores:**
  - `useBusinessStore` holds `businessInfo` getters (dates, status, name, type and warnings) and the `loadBusinessInfo()` loader, which reads `BUSINESS_ID` from sessionStorage.
  - `useRootStore` (id `'root'`) holds app state, filing and bootstrap status checks, roles, and `getReasonText()`.
- **Components:** the EntityInfo, Header, Definitions and Menu components, the read-only business and address displays, the director edit workflow, office address editing, and filing form inputs (date pickers, certify, comments, foreign jurisdiction).
- **App shell:** the barrels, the Routes enums and route table, `getVueRouter()` with its auth and feature-flag guard, `main` bootstrap, and utilities (capitalize, formatPhoneNumber, sleep, navigate, `setBaseRouteAndBusinessId`).
- **Digital Credentials:** the dashboard, table, menu, landing and info cards, the issuance stepper with `CredentialsWebSocket` (polling), and the Terms of Use. Also the Help, ModalDialog and Authorization Email Sent dialogs, and the BN request admin (`BNRequestManager`, `ResubmitRequest`).

**Auth-web: accounts, onboarding and login**
- **Account setup and creation:**
  - Account setup stepper and its landing, `AccountCreateBasic` and `AccountCreatePremium`, `BcolLogin`.
  - Govm and staff setup forms.
  - Success, pending and unauthorized pages, and `HomeView`.
- **Login-method selection:**
  - Learn-more dialogs for BCeID, BCSC and mobile card.
  - Non-BCSC affidavit path: Overview, AffidavitDownload, UploadAffidavitStep.
  - BcscPanel, LoginBCSC and the invite landings.
- **Account settings:**
  - Account Info and its children, access type, business type picker, and alerts.
  - Products, fees and TOS, statements and settings.
  - Activity logs and API keys.
  - Deactivation.
- **Affiliations:**
  - Entity dashboard and the affiliation table and actions.
  - Business lookup, name-request and add-business forms.
  - Landing "journey" views, the price list and incorporation search.
- **Team management:**
  - UserManagement and Anonymous variants, member, pending and invitation tables.
  - Bulk add, PasswordReset and profile forms.
  - Notary forms.

**Auth-web: payments and finance**
- **Payment methods:**
  - `PaymentMethods`, `AccountPaymentMethods`, `PADInfoForm`, the GL form, `MakePayment`.
  - Outstanding balances, credit card, online banking and gateway return views.
  - The payment error message.
- **NSF suspension:**
  - The suspended views, the unlock stepper (EFT 2-step, PAD 3-step), `AccountOverviewNSFView`, `ReviewBankInformation`.
  - The unlock success view, which polls `syncOrganization`.
- **EFT short names:**
  - Mapping views, summary and linked tables, account linkage, the detail page and payment history.
  - The refund views and the OPS-only MVP refund UI.
  - Account lookup autocomplete.

**Auth-web: staff back-office**
- Account management tabs, staff account tables (active, inactive, pending, rejected, suspended, invitation orgs), the org search composable and `ContinuationApplicationTable`.
- Task review page with tab builders, `AccessRequestModal`, the GL code modal, the dissolution tools and safe emails.

**Shared infrastructure (auth-web)**
- Pinia stores: business, codes, org (~80 exports), staff, task and user. The auth and configuration stores, and legacy Vuex.
- `ConfigHelper`, the router guard (8 ordered checks), route definitions and breadcrumbs.
- Mixins: `AccountMixin`, `NextPageMixin`, pagination, team-management, `DateMixin` and the org-change listener.
- Composables: `useAffiliations`, `useTransactions` and the table-composable factory.
- Header definitions and filters, TypeScript interfaces and enums (transactions, invoices, statements, EFT, tasks, orgs, affiliations, businesses, name requests), `CommonUtils`, `debounce`, and the barrel index files.

**Infra and data (pay services)**
- `VUE_APP_*` env config (dev) and 1Password `op://…/$APP_ENV/…` templates.
- Firebase PR-preview Cloud Build pipelines, and Cloud Deploy pipelines for payment-jobs, pay-admin, pay-api and pay-queue (dev→test→sandbox→prod).
- Pay backend env templates, the DB masking Docker/Cloud Build setup, and Alembic migrations (code and lookup tables, corp types, staff remark codes, resubmit flags, `account_payment_settings`).
- The cattrs converter, Zenhub/GitHub migration env vars, and the TodoList draft-deletion tests.

## Caution: highest-signal risks

**Likely real bugs**
- Business `useRootStore` getters such as `isAmalgamationTodo()` omit `this.` and would throw. The business and root stores import each other, which risks an import cycle.
- Auth-web stores:
  - `syncSuspendedStaffOrgs` assigns to `pendingInvitationOrgs`.
  - `getUserAccountSettings` uses `this.context.state`, which doesn't exist in Pinia.
  - The task store's `!pendingTasksCount` cache blocks updates when the count is 0.
  - `useStaffStore` and the business store are truncated.
- Logic and sort bugs:
  - The director `toggleAction` uses `splice(index)`, not `splice(index, 1)`.
  - `customSort` and the descending flag are inverted in several tables (PendingMember, GLCodes and the Coordinator branch of MemberDataTable).
  - `Statements.initialize()` is missing `()` on `isStatementsAllowed`.
  - The deactivation `authorised` getter is inverted.
  - `ContinuationApplicationTable.changeSort` uses `this.sortDesc` instead of `state.sortDesc`.
  - The More Actions dropdown is keyed by `nrNumber` for the icon but by `id` for `v-model`.
  - `TermsOfUse` version comparison is inverted.
  - `AccountAccessType` overwrites GOVM with REGULAR on save.
  - `viewOnlyMode('address')` has a wrong signature.
  - The `shortnamerefund` route passes the wrong prop.
  - The 8770c44d3d66 migration inserts `description` into a `desc` column.
  - Polling watch conditions in `CredentialsWebSocket` are inverted.
  - The `isFormValid()` name is backwards in `ShortNameFinancialDialog`.
  - In `AccountOverviewNSFView`, `calculateFailedInvoices()` has no error handling.
- Dead code and mismatches:
  - The "Reason for Refund" read-only branch can never render.
  - Service-fee summary shows the same value twice.
  - `AccountAccessType` and the `UserProfileView` `SupportInfoCard` are dead or unfinished.

**Silent-failure and data hazards**
- Many catch blocks only `console.log`, or swallow errors. Examples: GeneratePasscodeView, `createNumberedBusiness`, the rejected tasks table, `downloadStatement`.
- Migrations are risky: the Keycloak backfill and the CCC description change have no real downgrade, and TRUNCATE CASCADE and destructive deletes can fail on a downgrade.
- Temporary passwords are shown unmasked in the UI and stored in `state.createdUsers`.
- `BcolLogin` emits credentials on every keystroke.
- `Entity.passCode` is plaintext.

**Config and environment**
- Empty dev keys disable features: Address Complete, Sentry, Hotjar, LD (auth-web), Search/MHR API keys. Job secrets (CGI SFTP, Oracle, `EFT_HOLDING_GL`) are empty.
- `$APP_ENV` must be substituted or the `op://` references won't resolve.
- Pay pipelines:
  - Sandbox deploys to `gtksf3-tools`.
  - `verify: false` everywhere.
  - Dev uses `sa-job@` while the other stages use `sa-api@`.
  - Dev and test have no scale or resource specs.
  - The bare pay-api, pay-queue and pay-admin pipeline manifests are stubs.
- Store ID `'root'` and sessionStorage keys (`BUSINESS_ID`, `VUE_ROUTER_BASE` with its trailing `/`) are load-bearing.
- Two views mix string `'true'` flags with booleans (`affidavitNeeded`, `pendingAffidavit`, `ExtraProvincialUser`).

**Migration debt**
- Vuex remnants (`updateHeader`, "Remove with Vue 3") are mixed with Pinia.
- `::v-deep` should become `:deep()`.
- The `Steppable` and `NextPageMixin` mixins, `.sync` bindings and `this.$router` inside `setup` all need migration.
- Class and component names often don't match (e.g. AccountCreationSuccessView renders the suspension page).

**Behavioural gotchas worth remembering**
- Directors is deliberately left out of the shared barrel to avoid circular imports.
- DCRoutes is spread into CoreRoutes, so keys can collide.
- The router guard checks only for a token's existence, not its expiry.
- `Math.random()` is used for the `:name` attribute in autocompletes.
- PAD and EFT rules: EFT is one-way, and EFT→PAD is blocked while a balance is owing. Only `PaymentTypes.EFT` triggers `updateStatementNotifications()`.
- Account credit doesn't apply to credit card payments.
- `InvoiceStatus.COMPLETED` is what the API returns instead of `PAID`.
- `invoiceStatusDisplay` collapses several statuses into one label, so it can't be reversed.
- `toOrgId: null` in `handleAuthorizationEmailOption` is intentional because of a backend bug.
- The `getAuthentication()` default is the opposite of the contacts and affiliations handlers (`hasBusinessAuthentication` is true on NOT_FOUND).
- `resetoCurrentSelectedProducts`, `FolioNumberload`, `apliKeyList` and "Reponsiblity Center" are typos that exist in the code. Preserve them unless renaming everywhere.
