<!-- leaf 110, 14 members -->

These condensations summarize Jest/Vue Test Utils suites for dialog components in a Vue + Vuetify + Pinia app (business registry UI). Each suite mounts a dialog and checks its title, body text, child components, buttons, and emitted events.

## Groupings

**1. Error dialogs with role-dependent ContactInfo**

These share one pattern. A normal user (`keycloakRoles=['']`) sees the ContactInfo component. A staff user (`keycloakRoles=['staff']`) does not. Each suite sets up `Vue.use(Vuetify)`, `setActivePinia(createPinia())` and `useRootStore()`.

- **FetchErrorDialog**: title "Unable to Fetch Data", a dashboard link, and the action "Return to dashboard".
- **NotEligibleExtensionDialog**: title "Not Eligible for Extension", body text, and an "OK" button.
- **TechnicalErrorDialog**: title "Error", the message "We could not process…", and a "Close" button.
- **CancelPaymentErrorDialog**: three cases.
  - A normal user sees the generic message plus "contact us" text.
  - A staff user sees the generic message without "contact us".
  - An `errors` prop (array of `{error, path}`) shows "due to following errors:" and the error message.
- **PaymentErrorDialog**: six tests with `contentclass='payment-error-dialog'`.
  - Generic message for normal and staff users.
  - Error and warning arrays render (3 `p` elements, 2 or 4 `span` elements).
  - The Exit button ("Back to My Dashboard") emits `exit`.
- **SaveErrorDialog**:
  - Generic message: "Unable to Save FILING", with Exit and Retry buttons.
  - Staff message: same, without contact info.
  - `errors` array: "Unable to Save Filing", with an OK button only.
  - `warnings` array: "Filing Saved with Warnings", with an OK button only.
  - Exit click emits `exit`.

**2. Generic and standing dialogs**

- **GenericErrorDialog**: hidden when the `dialog` prop is false or unset. By default it shows "An error occurred", "Please contact us:", ContactInfo and a "Close" button. Custom `title` and `text` props override the defaults. Clicking the button emits `close`.
- **NotInGoodStandingDialog**: four tests.
  - `message='dissolve'` shows "cannot be dissolved…not in good standing".
  - `message='changeCompanyInfo'` shows "cannot be viewed or changed".
  - With no message, it falls back to "Please contact BC Registries staff".
  - The close button emits `close`.
  - Each test checks `contentclass='not-in-good-standing-dialog'` and that ContactInfo is present.

**3. Dissolution confirmation dialogs (by business type)**

The tests vary by `CorpTypeCd` and its `BusinessConfig`.

| Type | Title | Paragraphs | Legal framework | Button |
|---|---|---|---|---|
| Sole Proprietorship (SP) | "Dissolution" | 3 | Partnership Act | "Continue with Dissolution" |
| General Partnership (GP) | "Dissolution" | 3 | Partnership Act | "Continue with Dissolution" |
| Benefit Company (BEN) | "Voluntary Dissolution" | 2 | Business Corporations Act | "Continue with Voluntary Dissolution" |

- SP and GP differ only in the type name and a comma before "ceasing".
- The SP/GP closing paragraph reads "Make sure your business information is up to date before dissolving."

**4. Form and action dialogs**

- **AddCommentDialog**: title "Add Detail", a DetailComment child, and save and cancel buttons. Initial state is `comment=''` and `detailCommentValid=false`. Cancel emits `close=[false]`. Save emits `close=[true]` with an `axios.post` stub.
- **AddStaffNotationDialog**: covers four filing types: standard, administrative dissolution, put back on, and admin freeze.
  - Constants: `NOTATION_MAX_LENGTH=2000` and `MAX_FILE_SIZE=30`.
  - The notation is required, with error text that varies by type. Its length is capped at 2000 characters.
  - The court order number has a minimum length of 5 and a maximum of 20.
  - A court order or an upload is required, with the error "Enter a Court Order and/or upload file".
  - Save POSTs to `businesses/{identifier}/filings` and emits `close(true)`.
- **StaffPaymentDialog**: props `dialog` and `staffPaymentData` (`option`, `routingSlipNumber`, `isPriority`). Title "Staff Payment", with "Exit Payment" (emits `exit`) and "Submit" (emits `submit`) buttons. Initial state is `validate=false` and `staffPaymentFormValid=true`.

## Caution:
- **Test setup**
  - Call `setActivePinia()` before any store access.
  - Set `document.body.setAttribute('data-app', 'true')` to suppress Vuetify's target warning.
  - Mutations to `rootStore` (such as pushing `keycloakRoles` in the CancelPaymentErrorDialog staff test) persist into later tests unless reset.
- **Event triggering**
  - Use `mount`, not `shallowMount`, when testing event triggers. For example, SaveErrorDialog's exit click fails to emit with `shallowMount`.
  - In AddCommentDialog, the save test calls `vm.save()` directly because `trigger('click')` was broken in that version.
  - StaffPaymentDialog must stub StaffPayment in the Exit and Submit tests, or nested event errors occur. Because of the stub, `staffPaymentFormValid` has to be set manually.
- **Timing**
  - AddStaffNotationDialog has a comment saying awaiting two statements "doesn't work as expected", which points to a reactivity timing issue and possible flakiness.
  - NotInGoodStandingDialog test 4 uses `Vue.nextTick()` after the click, which may not cover all async work. Its fallback text is only substring-checked.
- **Role values**
  - Normal users are `keycloakRoles=['']` (an array with an empty string), not `[]`. It is unclear what the empty string means.
  - PaymentErrorDialog uses `[]` for normal users, so the two conventions are inconsistent.
- **Template differences**
  - The admin freeze case in AddStaffNotationDialog uses different selectors (`v-card-title-stub`, `v-card-text-stub`). It has no notation form and no CourtOrderPoa.
  - SP and GP cite the Partnership Act, while BEN cites the Business Corporations Act.
  - SP and GP have 3 paragraphs and BEN has 2, so the `.length` check differs.
- **Legacy patterns**
  - `wrapper.destroy()` is used in the GenericErrorDialog and NotInGoodStandingDialog tests. It is a Vue 2 pattern, deprecated in Vue 3.
  - GenericErrorDialog tests assume ContactInfo exists and never check its props or state.
  - StaffPaymentDialog sets `Vue.config.silent=true`, which hides prop-mutation warnings.
- **Naming**
  - PaymentErrorDialog tests use both `dialog-okay-button` and `dialog-ok-button`, a possible typo.

## Members

- business-filings-ui: tests/unit/AddCommentDialog.spec.ts
- business-filings-ui: tests/unit/AddStaffNotationDialog.spec.ts
- business-filings-ui: tests/unit/AddStaffNotationDialog.spec.ts
- business-filings-ui: tests/unit/AddStaffNotationDialog.spec.ts
- business-filings-ui: tests/unit/CancelPaymentErrorDialog.spec.ts
- business-filings-ui: tests/unit/ConfirmDissolutionDialog.spec.ts
- business-filings-ui: tests/unit/FetchErrorDialog.spec.ts
- business-filings-ui: tests/unit/GenericErrorDialog.spec.ts
- business-filings-ui: tests/unit/NotEligibleExtensionDialog.spec.ts
- business-filings-ui: tests/unit/NotInGoodStandingDialog.spec.ts
- business-filings-ui: tests/unit/PaymentErrorDialog.spec.ts
- business-filings-ui: tests/unit/SaveErrorDialog.spec.ts
- business-filings-ui: tests/unit/StaffPaymentDialog.spec.ts
- business-filings-ui: tests/unit/TechnicalErrorDialog.spec.ts
