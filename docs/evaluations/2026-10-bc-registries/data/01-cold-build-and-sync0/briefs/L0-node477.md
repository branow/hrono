<!-- leaf 477, 39 members -->

**What this is:** A set of condensed notes on a BC Registries-style account and business-management web app. It is mostly Vue 2/3 single-file components, with Vuetify, Pinia, a partly legacy Vuex store, LaunchDarkly flags and role-gated `v-can` directives. It also includes one Alembic database migration. Some summaries are truncated or unnamed.

## Groupings

**1. App shell and account settings**
- **Shell:** the sticky header and layout. It uses the Vuex+Pinia hybrid, handles account switching, builds breadcrumbs, shows the alert banner, and rerenders on `refreshKey`.
- **Account Info page:** the main settings page, which is incomplete. It composes these children:
  - `AccountDetails`: org name, branch, business type and size.
  - `AccountMailingAddress`: wraps `BaseAddressForm`.
  - `AccountAccessType`: a radio form for Regular or Government (GOVN) access.
  - `AccountBusinessTypePicker`: business type and size selects.
  - An unnamed account-type selector: Individual, Business or Government, with an org-name autocomplete.
  - Suspend and unsuspend dialogs.
- **Alerts and cards:** `AccountInactiveAlert`, `AccountSuspendAlert` (NSF vs. other suspension) and `DeactivateCard`, which shows PAD removal only for PREMIUM accounts.
- **Activity and API keys:** `ActivityLogs` and `ExistingAPIKeys`. Both are paginated or tabular `v-data-table` views, and both use `AccountChangeMixin`.
- **Shared pattern:** the view-only / edit toggle. It appears in `AccountDetails`, `AccountMailingAddress` and `AccountAccessType`, and each emits `update:viewOnlyMode` plus a save event.

**2. Products, fees and statements**
- **Product list and card:** a "Products and Services" container with a `Product` card per item. `SelectProductService` is the stepper version of the same selection.
- **Fees and terms:** `ProductFeeViewEdit` and `ProductTOS`.
- **Statements:** a `Statements` list and a `StatementSettings` modal. Both depend on the `EnableEFTPaymentMethod` flag and both use `ITEMS_PER_PAGE=5`. `ActivityLogs` uses the same pagination constants.

**3. Onboarding, terms and linking**
- `TermsOfUse` and `TermsOfServiceView` handle accepting the terms and routing afterward.
- A "link with BC Online?" chooser picks between a PREMIUM org and an UNLINKED_PREMIUM org.
- A BC Online account card shows the BC Online (bcol) account details.
- A numbered-company tooltip changes its text with the `EnableBcCccUlc` flag.
- A block of shared SCSS covers badges, buttons and `::v-deep` overrides.

**4. Business affiliations and entities**
- **Dashboard:** the entity dashboard, which contains `AffiliatedEntityTable`. Each row has an `AffiliationAction` button and menu, and `EntityDetails` shows alert tooltips.
- **Adding businesses:** `SearchBusinessNameRequest` (Incorporated vs. NameRequest) adds a business directly for staff. Other users go through the manage-business dialog, which has a passcode/certification form and an `AccountAuthorizationRequest` sub-form.
- **Removal:** `PasscodeResetOptionsModal`.
- **Shared dialogs:** the dashboard uses many `ModalDialog` instances, mostly with `dialog-class="notify-dialog"` and `max-width="720"`.

**5. Staff and admin tools**
- **Account Management:** a tabbed view (Active, Invitations, Pending Review, Rejected, Suspended, Inactive), each tab gated by role.
- **Staff modals:** `StaffCreateAccountModal` and `AccessRequestModal`. The latter has reject, on-hold and move-to-pending variants.
- **Business tools:** the BN (Business Number) manager and two dissolution views, a batch-size editor and a "ready for D1 dissolution" count.

**6. Database**
- Alembic migration `06eda339e0d5` (from `09c44f82c03c`) creates `account_payment_settings`. It moves `org.preferred_payment_code` into the new table with a default of `'CC'` and adds the index `ix_org_access_type`. The downgrade reverses this.

## Caution:

**Data and migration**
- The upgrade's data insert has no rollback if it fails, so orgs can lose payment settings.
- The downgrade assumes `account_payment_settings` is still populated, so dropping it loses data.

**Silent data loss or state bugs**
- `AccountAccessType` offers only REGULAR and GOVN. An org with GOVM defaults to REGULAR on mount, and saving overwrites GOVM.
- `AccountMailingAddress` emits both `update:viewOnlyMode` and `update:resetAddress` on Edit/Cancel. A parent that handles only one loses unsaved changes.
- `DeactivateCard` gates `padRemovalTitle` by type at render time, so changing the type later won't update it without re-initialising the component.
- The BC Online link chooser's `loadComponent(true)` resets account state. Its mount logic depends on the prior org state, and overlapping conditions may leave stale state.
- The header rerenders on `refreshKey` to force the account-switch UI update.
- `SearchBusinessNameRequest` resets `BusinessLookup` only by incrementing `businessLookupKey`.

**Silent failures and missing error UI**
- `AccountDetails` blocks save silently when `isOrgBusinessTypeValid` is false.
- `AccountBusinessTypePicker` logs code-load failures without showing the user an error. Its watch fires on either field without distinguishing them.
- `ExistingAPIKeys` shows no error UI if a revoke fails silently. Its alert text defaults to the error state and flips on success. It also has the typo `apliKeyList`.
- `AccountAuthorizationRequest` shows hardcoded help-desk text for every error and doesn't surface its `unknown-error` emit.
- `AccountInactiveAlert` shows an empty date if `modified` is missing.
- `AccountInactiveAlert` also formats `moment()`, which is the current time rather than the `modified` value.
- `AccountSuspendAlert` computes `totalTransactionAmount` and `totalPaidAmount` but never renders them.

**Async, sync and initial-value problems**
- `Statements` calls the async `enableEFTPaymentMethod` synchronously in a computed, which may return a Promise instead of a boolean.
- The numbered-company tooltip calls `LaunchDarklyService.getFlag()` synchronously, and its `|| false` masks undefined.
- Several values start as placeholders and show wrong data until loaded:
  - The dissolution batch-size field `numberOfBusinessesNonEdit` starts at -1.
  - `businessesReadyforDissolutionNumber` starts at -1.
  - The batch-size field stays -1 if mounting or the store call fails.

**Logic that looks inverted or inconsistent**
- `TermsOfUse` has two risks. Its version comparison looks inverted, since it returns true when the user's version is greater than the latest. String comparison of versions like `d1`, `d2`, `d10` also fails, so numbers must be extracted.
- `EntityDetails` priorities are inverted (PROCESSING=5, DISSOLUTION=1) against an ascending sort. `generateMessage()` can return null, which crashes the sort.
- `TermsOfServiceView` runs the affidavit redirect check before the token routing, so the affidavit flow can gate users before profile creation.
- `ProductFeeViewEdit` uses a whitelist for ESRA and a blacklist for other products, so a misconfiguration could expose the wrong fee codes.
- The BN manager's mask captures 9 digits while real CRA numbers can be 9 or 15. Its `businessNumber` stays optional even after the CRA checkbox is checked.

**Permissions**
- `canManageAccounts` in Products needs both the StaffManageAccounts role and a GOVM/GOVN account, so non-staff can't manage fees.
- In Account Management, `canSuspendAccounts` includes `StaffViewAccounts`, so view access also shows suspend options.
- The suspend button works both ways, depending on the account's status. `v-can` directives gate VIEW_ADDRESS and DEACTIVATE_ACCOUNT. A TODO notes the mailing-address `v-can` needs a refactor.

**Incomplete or truncated excerpts**
- The Account Info page is truncated before its state, computed values and methods.
- The account-type selector never defines `setBusinessTypeAndCode()`.
- `AccessRequestModal` is cut off mid-`callAction()`, and the `OnholdOrRejectCode` values are not shown.
- `AccountChangeMixin` is opaque, so the behaviour of `setAccountChangedHandler()` is unknown.

**Architecture and maintainability**
- Vuex and Pinia are mixed, with "Remove Vuex with Vue 3" comments but no clear upgrade path.
- Several components have performance or fragility risks:
  - A deep watch on `tableDataOptions` fires on every pagination change.
  - `ActivityLogs` assigns `formatDate` at class level.
  - `Product` duplicates its header in two branches and passes many props.
  - `AffiliatedEntityTable` disables `vue/no-template-shadow` and assumes `item.nameRequest` always exists.
  - `AffiliationAction` keeps per-item `actionDropdown[index]` state that goes stale if the list reorders. Its LaunchDarkly flags are split on spaces with no validation.
- `AccountDetails` changes labels dynamically with `isGovnGovmOrg`.
- `StatementSettings` has two related behaviours. EFT locks the other frequencies, and `emailRecipientInput` is cleared after selection.
- The account-type selector uses `displayGovnType`, which enables GOVN when `currentAccountSettings.id` is undefined. Its `accountType` watch needs an `isInitialized` flag.
- The entity dashboard's dialogs share props, so a central change must touch every ref.
- The manage-business dialog's passcode max length varies (firm 150, cooperative 9, other 15), and its cert fields apply only to firms.
- `PasscodeResetOptionsModal` emits with an email only when resetting.
- Typos are used consistently, so they work but confuse maintainers:
  - `resetoCurrentSelectedProducts`
  - `onisTOSALreadyAcceptedChange`
  - `selctedAccount`
  - `apliKeyList`
- `StaffCreateAccountModal` builds its routes inconsistently, since the GOVM path lacks a leading slash.
- `SelectProductService` passes an undocumented `forceRemove`.
- The BC Online account card's `mounted()` has a redundant `|| false`, and an empty `bcolAccountDetails` triggers edit mode.
- The shared styles rely on `--v-*` variables, `::v-deep` and `!important` to override Vuetify.

## Members

- sbc-auth: auth-web/src/App.vue
- sbc-auth: auth-web/src/components/auth/account-deactivate/DeactivateCard.vue
- sbc-auth: auth-web/src/components/auth/account-settings/account-info/AccountAccessType.vue
- sbc-auth: auth-web/src/components/auth/account-settings/account-info/AccountDetails.vue
- sbc-auth: auth-web/src/components/auth/account-settings/account-info/AccountInfo.vue
- sbc-auth: auth-web/src/components/auth/account-settings/account-info/AccountMailingAddress.vue
- sbc-auth: auth-web/src/components/auth/account-settings/activity-log/ActivityLog.vue
- sbc-auth: auth-web/src/components/auth/account-settings/advance-settings/ExistingAPIKeys.vue
- sbc-auth: auth-web/src/components/auth/account-settings/product/ProductPackage.vue
- sbc-auth: auth-web/src/components/auth/account-settings/statement/Statements.vue
- sbc-auth: auth-web/src/components/auth/account-settings/statement/StatementsSettings.vue
- sbc-auth: auth-web/src/components/auth/common/AccountBusinessType.vue
- sbc-auth: auth-web/src/components/auth/common/AccountBusinessTypePicker.vue
- sbc-auth: auth-web/src/components/auth/common/AccountInactiveAlert.vue
- sbc-auth: auth-web/src/components/auth/common/AccountSuspendAlert.vue
- sbc-auth: auth-web/src/components/auth/common/LinkedBCOLBanner.vue
- sbc-auth: auth-web/src/components/auth/common/NumberedCompanyTooltip.vue
- sbc-auth: auth-web/src/components/auth/common/Product.vue
- sbc-auth: auth-web/src/components/auth/common/ProductFeeViewEdit.vue
- sbc-auth: auth-web/src/components/auth/common/ProductTOS.vue
- sbc-auth: auth-web/src/components/auth/common/TermsOfUse.vue
- sbc-auth: auth-web/src/components/auth/create-account/AccountTypeSelector.vue
- sbc-auth: auth-web/src/components/auth/create-account/PremiumChooser.vue
- sbc-auth: auth-web/src/components/auth/create-account/SelectProductService.vue
- sbc-auth: auth-web/src/components/auth/manage-business/AffiliatedEntityTable.vue
- sbc-auth: auth-web/src/components/auth/manage-business/AffiliationAction.vue
- sbc-auth: auth-web/src/components/auth/manage-business/EntityDetails.vue
- sbc-auth: auth-web/src/components/auth/manage-business/EntityManagement.vue
- sbc-auth: auth-web/src/components/auth/manage-business/PasscodeResetOptionsModal.vue
- sbc-auth: auth-web/src/components/auth/manage-business/SearchBusinessNameRequest.vue
- sbc-auth: auth-web/src/components/auth/manage-business/manage-business-dialog/AccountAuthorizationRequest.vue
- sbc-auth: auth-web/src/components/auth/manage-business/manage-business-dialog/ManageBusinessDialog.vue
- sbc-auth: auth-web/src/components/auth/staff/DissolutionSchedule.vue
- sbc-auth: auth-web/src/components/auth/staff/account-management/StaffAccountManagement.vue
- sbc-auth: auth-web/src/components/auth/staff/account-management/StaffCreateAccountModal.vue
- sbc-auth: auth-web/src/components/auth/staff/admin/AdministrativeBN.vue
- sbc-auth: auth-web/src/components/auth/staff/review-task/AccessRequestModal.vue
- sbc-auth: auth-web/src/views/auth/TermsOfServiceView.vue
- sbc-auth: auth-web/src/views/auth/staff/InvoluntaryDissolution.vue
