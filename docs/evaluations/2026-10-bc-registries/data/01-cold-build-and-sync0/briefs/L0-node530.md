<!-- leaf 530, 18 members -->

**What this is:** A set of condensed notes on a Vue/Vuetify component library of dialogs (mostly BC Registries–style filing UI, using vue-property-decorator and Pinia `useRootStore`). There is also one outlier, a SQLAlchemy `PaymentMethod` model. Nearly every dialog is a persistent `v-dialog` with `dialog` and `attach` props, a `45rem` width, and an `isRoleStaff` getter. Most show `ContactInfo` only when `!isRoleStaff`.

## Groupings

**1. Standard error dialogs (the shared pattern)**
Each has a title, a message, a conditional `ContactInfo`, and one or two buttons that emit events. The variations are the title, the emitted events and any extra props:
- Close-only, emits `close()`: UnableToReplaceCredential ("Unable to Replace Credential"), UnableToRevokeCredential ("Unable to Revoke Credential"), DownloadErrorDialog ("Unable to Download Document") and TechnicalErrorDialog (generic message).
- Exit-only, emits `exit()`: the fetch-error dialog (button "Return to dashboard"), LoadCorrectionDialog ("Unable to Load Correction") and ResumeErrorDialog ("Unable to Resume Filing", button id `dialog-exit-button`).
- Exit and Retry, emits `exit()` and `retry()`:
  - "Unable to Access Business" (3 reasons: unauthorized, session timeout, invalid Business Identifier; content-class `business-auth-error-dialog`).
  - "Dashboard Unavailable".
  - The Incorporation Application authorization-error dialog (3 reasons: not authorized, session timeout, invalid URL).
  - NameRequestInvalidDialog. It takes a `type` prop (`NameRequestStates`: EXPIRED, CONSUMED, NOT_APPROVED, NOT_FOUND, NEED_CONSENT) and shows a different message for each.

**2. Dialogs driven by error and warning arrays**
These take `errors` and `warnings` props and change their title and buttons by state.
- DeleteErrorDialog (Vue 3, TypeScript, Pinia): "Unable to Delete Filing" or "Filing Deleted with Warnings". It emits `okay()`.
- The filing-save dialog: "Unable to Save {{filingName}}" or "{{filingName}} Saved with Warnings". It emits `exit()`, `retry()` (disabled by `disableRetry`) and `okay()`.
- PaymentErrorDialog: "Unable to Process Payment". Its width is `50rem`, not 45rem. It has `filingName`, `errors` and `warnings` props, and `numErrors` and `numWarnings` getters. It also shows PayBC hours, and its button reads "Back to My Dashboard" or "OK" depending on role. It emits `exit()`.

**3. Decision and prompt dialogs (not errors)**
- Change-of-address warning (content-class `coa-warning-dialog`, title "Address Change Effective 12:01 am"): "Return to dashboard" calls `toggle()` and "Continue to Change of Address" calls `proceed()`.
- Correction-type chooser: a CLIENT or STAFF radio group. "Start Correction" stays disabled until a type is chosen, then `checkToStart()` emits `'redirect'` with the `CorrectionTypes` value.
- Generic error dialog: props `attach`, `dialog` (v-model), `text` (default "Please contact us:") and `title` (default "An error occurred"). The text is rendered as HTML, and it emits `close()` on the button or ESC.

**4. Outside the dialog pattern**
- `PaymentMethod` SQLAlchemy model: table `payment_methods`, with `code` (String 15, primary key) and `description` (String 200, not null). `save()` adds the instance to the session and commits. `PaymentMethodSchema` is a `ma.SQLAlchemyAutoSchema` with `load_instance=True`.
- A barrel export file for about 23 dialog components. Local imports use `./Name.vue`, one comes from `@bcrs-shared-components/confirm-dialog`, and one uses an `@/` alias path.

Caution:
- **Staff see no contact info.** `ContactInfo` renders only when `!isRoleStaff`. This applies across the standard dialogs (credential, business-auth, dashboard, resume, technical, download, Incorporation Application and others), so staff get no contact path.
- **Events only signal the parent.** `close()`, `exit()`, `retry()`, `toggle()` and `proceed()` are plain `@Emit` passthroughs that do no cleanup. The parent must listen and update `dialog`. For DownloadErrorDialog, `v-model` alone won't work; the parent must handle `@close`.
- **`persistent` blocks backdrop and ESC dismissal.** Only the buttons close these dialogs. The generic error dialog adds `@keydown.esc="close()"`, which overrides this, and the Close button's state update still depends on the parent watching the emitted event.
- **DeleteErrorDialog title logic looks wrong.** `errors.length > 0 || warnings.length < 1` is true even when only warnings exist. It probably should be `&&`. `ContactInfo` is also imported unconditionally but rendered conditionally.
- **XSS risk.** PaymentErrorDialog uses `v-html` on `error.message` and `warning.message`, which renders raw HTML. Sanitize that content.
- **Dead code.** The correction-type watcher reassigns `correctionType` to itself in each case.
- **Unverified import.** `ContactInfo` is imported in the fetch-error dialog, but its source isn't shown. Check that the path is correct.
- **LoadCorrectionDialog has no recovery logic.** It passes no data to `ContactInfo` and defines no error state beyond `exit`.
- **PaymentMethod needs `include_properties`.** `__mapper_args__['include_properties']` is required for deployments with schema drift. Omitting it breaks Alembic during upgrades.
- **Barrel export path inconsistency.** `NotInGoodStandingDialog` uses the `@/` alias while all the others use `./`. Moving it or refactoring the imports risks breaking the path.

## Members

- business-filings-ui: src/components/DigitalCredentials/dialogs/ReplaceCredentialErrorDialog.vue
- business-filings-ui: src/components/DigitalCredentials/dialogs/RevokeCredentialErrorDialog.vue
- business-filings-ui: src/components/dialogs/BusinessAuthErrorDialog.vue
- business-filings-ui: src/components/dialogs/CoaWarningDialog.vue
- business-filings-ui: src/components/dialogs/DashboardUnavailableDialog.vue
- business-filings-ui: src/components/dialogs/DeleteErrorDialog.vue
- business-filings-ui: src/components/dialogs/DownloadErrorDialog.vue
- business-filings-ui: src/components/dialogs/FetchErrorDialog.vue
- business-filings-ui: src/components/dialogs/FileCorrectionDialog.vue
- business-filings-ui: src/components/dialogs/GenericErrorDialog.vue
- business-filings-ui: src/components/dialogs/LoadCorrectionDialog.vue
- business-filings-ui: src/components/dialogs/NameRequestAuthErrorDialog.vue
- business-filings-ui: src/components/dialogs/NameRequestInvalidDialog.vue
- business-filings-ui: src/components/dialogs/PaymentErrorDialog.vue
- business-filings-ui: src/components/dialogs/ResumeErrorDialog.vue
- business-filings-ui: src/components/dialogs/SaveErrorDialog.vue
- business-filings-ui: src/components/dialogs/TechnicalErrorDialog.vue
- business-filings-ui: src/components/dialogs/index.ts
