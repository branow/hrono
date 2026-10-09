<!-- leaf 299, 17 members -->

This is a set of condensed notes on the frontend of a BC Registries–style Vue application (Vue 3 with some legacy Vue 2/Vuex code). It covers stores, configuration, routing, enums and navigation helpers. Each note carries its own gotchas.

## Groupings

### Pinia stores and state
- **`useAuthenticationStore`**: 11 getters.
  - `getAccountId` reads `sessionStorage['ACCOUNT_ID']` and falls back to `CURRENT_ACCOUNT`.
  - `getCurrentAccount` and `getCurrentUser` read from `$store.state.account`.
  - `getKeycloakGuid`, `getKeycloakRoles` and `getKeycloakToken` come from the store.
  - Other getters: `isAuthenticated`, `isPremiumAccount`, `isSbcStaff`, `isRoleStaff`.
- **Configuration store**:
  - State is `configuration`, which starts as null.
  - About 20 getters read `VUE_APP_*` values with `''` fallbacks. Composite getters such as `getMyBusinessRegistryUrl()` chain other getters.
  - Actions are `setConfiguration`, `setSessionVariables`, `setAxiosBaseUrl` and `loadConfiguration`.
  - `setSessionVariables` fills sessionStorage and window properties (`hotjarId`, `ldClientId`, `sentryDsn` and the Keycloak settings).
- **`app` store**: holds `errorMessage`, `refreshKey` and `loading`, plus `dismissError()`.
- **Store wiring modules**:
  - The Pinia setup installs `PiniaVuePlugin` and exports `useActivityStore`, `useBusinessStore`, `useCodesStore`, `useOrgStore`, `useStaffStore`, `useTaskStore` and `useUserStore`. `resetAllStores()` calls `$reset()` on each of them at logout.
  - `getVuexStore()` and `getPiniaStore()` are the factory functions. The Vuex store is empty and exists only for sbc-common-components.
- **Legacy Vuex 3 root store**: state is `refreshKey` and `loading`, with the mutations `updateHeader` and `loadComplete`. Strict mode is on outside production. A "Remove with Vue 3" comment marks it for removal.

### Routing
- **Router and guard**: history mode with `BASE_URL`. `beforeEach` runs eight ordered checks:
  1. Auth.
  2. Roles.
  3. Store sync (waits for Vuex `loadComplete`).
  4. Login page redirect.
  5. Premium-only.
  6. Terms of service (varies by login source).
  7. Account freeze.
  8. Active account (suspended, pending and missing-membership cases).
- **Route definitions**:
  - Over 40 routes, with `requiresAuth`, `requiresProfile`, `requiresActiveAccount`, `allowedRoles` and `disabledRoles`.
  - Catch-all paths: `/signin/:idpHint/:redirectUrl(.*)` and `/makepayment/:paymentId/:redirectUrl(.*)`.
  - Redirects: the root goes to `decide-business`, ADMIN to ADMIN_DASHBOARD, and STAFF and STAFF_DASHBOARD_OLD to STAFF_DASHBOARD.
  - The business dashboard route is `/account/:orgId/business`. The magic-link route decodes a base64 token.
  - The settings subtree has 9 children, from account-info to developer-access.
  - `/pay/*` and `/staff/*` routes cover short-name details, refunds, involuntary dissolution and continuation review. A `*` route goes to PageNotFound.
- **Helpers and lazy imports**:
  - `mapReturnPayVars`, `mapOrgDetails` and `mapPendingDetails` build route props. `isStaff()` checks the Keycloak roles.
  - The 10 account-settings components are lazy-loaded.

### Breadcrumbs
- **Breadcrumb factory**:
  - `getParams()` builds the `?accountid=` query string.
  - Four breadcrumbs link to external URLs: registry dashboard, my business, and staff.
  - One breadcrumb is a Vue route: DIGITAL_CREDENTIALS.
  - `getDashboardBreadcrumb()` is switched by the `use-business-dashboard` flag.
- **Breadcrumb constants**: 11 `BreadcrumbIF` objects, such as RegistryHome, StaffDashboard, ShortNameMapping, ShortNameDetails and InvoluntaryDissolution. Each has `text`, plus `to` or `href`.

### Configuration, constants and navigation helpers
- **`ConfigHelper`** (static class):
  - About 40 URL getters read `VUE_APP_*` values.
  - Session helpers are `addToSession`, `getFromSession`, `removeFromSession` and `clearSession`.
  - Business logic includes `accountSettingsRoute()`, `paymentsAllowedPerAccountType()` (varies with the `EnableCreditCardPremium` flag) and `setNrCredentials()`.
  - Defaults: the payee name is "BC Registries and Online Services" and the approval SLA is 5 days.
- **Enums**:
  - Session and role enums: `SessionStorageKeys` (28), `Role` (18), `Pages` (40+).
  - Account enums: `Account`, `AccountStatus`, `SuspensionReason*`.
  - Auth enums: `IdpHint`, `LoginSource`.
  - `InvoiceStatus` has 16 statuses.
  - Entity and Name Request types: `CorpTypes`, `LearFilingTypes`, `AffiliationTypes` and the `Nr*` enums.
- **Navigation handlers**:
  - Internal redirects are `goToDashboard` and `goToNameRequest`.
  - External links are `goToNameXUI`, `goToOneStop`, `goToCorpOnline`, `goToSocieties` and `goToFormPage`.
  - `goToFormPage` maps an entity type to a form site (LLP, LP, XLP or Corp).
  - All handlers except NameXUI call `appendAccountId()`.

## Caution:
- **Breadcrumbs**
  - `getParams()` defaults `accountId` to 0, which is falsy, so no params are appended.
  - Breadcrumbs mix `href` (external) and `to` (Vue route) navigation, so they may break if routing changes.
  - `CreatAccountBreadcrumb` is misspelled.
  - `MyBusinessRegistry` and `StaffBusinessRegistry` have identical name and href but different roles.
- **Authentication store**
  - `getCurrentAccount` and `getCurrentUser` are unavailable for 200ms or more after login.
  - `getAccountId` parses JSON from sessionStorage, which breaks if the format changes.
  - All getters assume `$store.state` exists.
- **Configuration store**
  - `configuration` can be null, and some getters access properties without checking (for example `getCreateUrl`).
  - `<any>` casts pollute `window` and bypass TypeScript.
  - `setSessionVariables` does no validation.
  - `loadConfiguration` returns a promise that isn't needed.
- **Store modules**
  - The Vuex store is empty on purpose, and calling `getVuexStore()` repeatedly re-runs `Vue.use(Vuex)`, which is idempotent but wasteful.
  - `resetAllStores()` creates new instances and doesn't clear existing references. It must be called before the old instances are discarded.
  - All three `app` store state properties are unused.
  - The root Vuex 3 store must be migrated before the Vue 3 upgrade.
- **Router guard**
  - Redirect conditions overlap and are order-dependent, so the first match wins (for example frozen plus pending membership).
  - Params like `redirectUri` must be passed along manually.
- **Router helpers and routes**
  - The decode helpers fail silently. Old invitations lack base64 encoding, and a failed magic-link decode leaves `orgId` undefined.
  - `getRoutes()` and `const routes =` are cut off.
  - Some component names don't match their folder names.
  - `requiresAuth` is inconsistent across routes (price-list and choose-authentication-method are public).
  - `disabledRoles` and `allowedRoles` use opposite logic and are easy to invert.
  - The shortnamerefund route uses `Number(route.params.shortNameId)` for the `eftRefundId` prop instead of `route.params.eftRefundId`.
- **`ConfigHelper`**
  - `paymentsAllowedPerAccountType()` changes with the feature flag.
  - The cache check is commented out, so `fetchConfig()` always re-runs.
- **Enums**
  - `InvoiceStatus.COMPLETED` is the value the API produces in place of `PAID`, so comparing against `PAID` elsewhere is a risk.
  - `GOVN_USER='AUTH_GOVN_USER'` sits alongside `GOVMAccountUser='gov_account_user'`, which suggests inconsistent naming.
- **Navigation handlers**
  - `goToFormPage()` has no validation in its default case, so an unexpected entity type silently routes to Corp forms.

## Members

- business-filings-ui: src/resources/BreadcrumbResources.ts
- business-filings-ui: src/stores/authenticationStore.ts
- business-filings-ui: src/stores/configurationStore.ts
- business-filings-ui: src/stores/index.ts
- sbc-auth: auth-web/src/resources/BreadcrumbResources.ts
- sbc-auth: auth-web/src/routes/index.ts
- sbc-auth: auth-web/src/routes/router.ts
- sbc-auth: auth-web/src/routes/router.ts
- sbc-auth: auth-web/src/routes/router.ts
- sbc-auth: auth-web/src/routes/router.ts
- sbc-auth: auth-web/src/routes/router.ts
- sbc-auth: auth-web/src/stores/app.ts
- sbc-auth: auth-web/src/stores/index.ts
- sbc-auth: auth-web/src/stores/vuex/index.ts
- sbc-auth: auth-web/src/util/config-helper.ts
- sbc-auth: auth-web/src/util/constants.ts
- sbc-auth: auth-web/src/util/navigation.ts
