<!-- leaf 101, 22 members -->

This group is a set of condensed notes on the **Filing History List feature of a Vue 3 app** (a BC business-registry style UI). It covers the Pinia/Vuex state store that backs the list and a large family of Vitest/Vue test specs for the `FilingHistoryList` component. Most of the test specs are `it.skip`'d, and the rest are mostly commented out or marked "FUTURE".

## Groupings

### 1. Store and state layer
- **`FilingHistoryListStateIF`**: the state model. Its fields are the dialog flags (`addCommentDialog`, `downloadErrorDialog`, `fileCorrectionDialog`, `loadCorrectionDialog`), `currentFiling`, `filings[]`, the loading flags (`loadingAll`, `loadingOne`, `loadingOneIndex`), and `panel`. The `useFilingHistoryListStore` definition is cut off in the excerpt.
- **Getters**:
  - `getFilings` filters out filings missing required fields or with `displayLedger === false`.
  - `getTotalAgmExtensionDuration(year)` sums AGM extension months.
  - `getPendingCoa` returns a pending change of address.
  - `getHistoryCount`, `isAuthorizedToContinueOut` and the per-dialog and per-loading getters round out the set.
- **Actions**:
  - Setters for each state field.
  - `loadFilings(id)`, `setFilings` and `toggleFilingHistoryItem(index)`, which lazy-loads and shows a 250ms spinner.
  - `loadComments` and `loadDocuments`, plus `showCommentDialog` and `hideCommentDialog(needReload)`.

### 2. Test scaffolding and fixtures
- **Setup files**:
  - One file wires Vuetify, Vuelidate, the Pinia stores, and mocked axios/sinon.
  - One imports `filings.json` with `ENTITY_INC_NO = 'CP0000840'` and defines predicate helpers (`isPaperOnly`, `isCorrection`, `isAlteration`, the amalgamation variants, `isStaff`, and others).
  - One uses a store-mocked suite with `itIf` conditional tests.
- **Shared fixtures**: `BC1234567`, `CP1002587`, the `SAMPLE_FILINGS` constant, and an incorporation-application payload with name translations, offices, parties, and share structure.

### 3. Expand/collapse and display tests, by filing type
These specs follow one pattern: mount, assert title and subtitle, click the expand button, then assert which detail components render and which don't. The variations are the filing type and the expected component.
- **Incorporation Application (IA)**:
  - Completed, named company and numbered company.
  - Future-effective, pending and paid.
  - The "View Details" test.
- **Alteration**:
  - Empty, completed, and future-effective.
- **Continuation**:
  - Continuation In, which renders `ContinuationIn`.
  - Consent to Continuation Out and Continuation Out.
- **Restoration**: Full and Limited.
- **Staff and registrar filings**: Court Order, Registrar's Notation and Order, and `StaffFiling` generally.
- **Paper-only**: expect `PaperFiling` and a "Request a Copy"/"Close" button.
- **AGM**: AGM Location Change and AGM Extension. Their test bodies are identical, and only the filing type and the expected component (`DefaultFiling` or `AgmExtension`) differ.
- **Amalgamation**: regular, horizontal, and vertical.
- **Other**:
  - The empty state.
  - The label-branching suite for `.item-header__subtitle` and `.expand-btn`.
  - The `displayLedger` filter test.
  - The `disableChanges` test.
  - The future-effective change of address tooltip test.

### 4. Documents and comments
- A comments button that is hidden at count 0 and shows "Details (N)" otherwise.
- `DocumentsList` visibility and the 'View Documents'/'Hide Documents' toggle.
- Five download buttons (Annual Report (2019), Address Change, Director Change, My Static Document.pdf, Receipt).
- Two suites: "with Court Order documents" (sinon) and "with documents" (`vi.spyOn`).

### 5. Correction redirect tests
Three specs click the menu, choose "File a Correction", pick the staff radio, and start. They then verify `window.location.assign` is called with the edit URL plus `correction-id`. They cover:
- Special Resolution (CP1002587, 145190).
- IA for BC1234567 (85114).
- IA for CP1002587 (85114).

## Caution:
- **Store logic is incomplete.** The `useFilingHistoryListStore` definition is cut off. `currentFiling` is optional in the type but has no default shown. It is unclear whether `loadingOne` and `loadingOneIndex` are coupled.
- **Store getters and actions:**
  - `getTotalAgmExtensionDuration` is a higher-order getter, so call it as `getTotalAgmExtensionDuration(year)`.
  - `getHistoryCount` uses `this.getFilings`, so it breaks if destructured.
  - `getFilings` silently filters invalid filings and logs to the console, so the filtered-out filings never surface.
  - `isAuthorizedToContinueOut` appears to return true when there is no consent-continuation-out filing, so an empty filings list grants authorization.
  - `loadComments` flattens the nested `comment.comment` structure and sorts newest first with `new Date()` comparison.
  - `loadDocuments` includes `fileNumber` only for staff on `uploadedCourtOrder`.
- **Most tests don't run.**
  - Most of the display specs are `it.skip`'d. Some skip lists are unexplained, and some suites have only the last test active.
  - Many component-existence assertions (`CompletedAlteration`, `CompletedIa`, `PendingFiling`) are commented out. This suggests removed components, so check whether they are still needed.
  - Most of the type-based suite is commented out and marked "FUTURE". Only amalgamation and paper-only are fully covered.
  - The label-branching suite has many commented branches and no default assertion.
- **Test data issues:**
  - The KEYCLOAK_TOKEN `exp` (1575072811) is in 2019, but the test dates are in 2020.
  - Test 3 of the correction specs reuses `correction-id=110514` from Test 2 even though the business is different. This is likely a copy-paste error, and the id should be 85114.
  - `commentsCount` has a typo variant, `commentsCounts`, in `FILING_WITHOUT_DOCUMENTS_LINK`.
  - One alteration test labels `effectiveDate='2020-04-24'` as "future effective" even though it is in the past.
  - Future-effective dates are hardcoded to 2099 so they always compare after now.
  - The paper-only filing's 2099 effective date is deliberate.
- **Test mechanics:**
  - One file mixes sinon and Vitest `vi.spyOn`.
  - `flushPromises()` is required after clicks for transitions.
  - Button labels flip after a click ('View' to 'Hide', 'Request a Copy' to 'Close').
  - `isStaff` treats "Administrative Dissolution" specially by `displayName`, not by type.
  - `ENTITY_INC_NO` must match the entity in `filings.json`.
  - Some tests assert the absence of other components, not just the presence of the expected one.

## Members

- business-filings-ui: src/interfaces/filing-history-list-state-interface.ts
- business-filings-ui: src/stores/filingHistoryListStore.ts
- business-filings-ui: src/stores/filingHistoryListStore.ts
- business-filings-ui: src/stores/filingHistoryListStore.ts
- business-filings-ui: tests/unit/FilingHistoryList1.spec.ts
- business-filings-ui: tests/unit/FilingHistoryList1.spec.ts
- business-filings-ui: tests/unit/FilingHistoryList1.spec.ts
- business-filings-ui: tests/unit/FilingHistoryList1.spec.ts
- business-filings-ui: tests/unit/FilingHistoryList1.spec.ts
- business-filings-ui: tests/unit/FilingHistoryList1.spec.ts
- business-filings-ui: tests/unit/FilingHistoryList1.spec.ts
- business-filings-ui: tests/unit/FilingHistoryList1.spec.ts
- business-filings-ui: tests/unit/FilingHistoryList1.spec.ts
- business-filings-ui: tests/unit/FilingHistoryList1.spec.ts
- business-filings-ui: tests/unit/FilingHistoryList1.spec.ts
- business-filings-ui: tests/unit/FilingHistoryList1.spec.ts
- business-filings-ui: tests/unit/FilingHistoryList1.spec.ts
- business-filings-ui: tests/unit/FilingHistoryList1.spec.ts
- business-filings-ui: tests/unit/FilingHistoryList1.spec.ts
- business-filings-ui: tests/unit/FilingHistoryList2.spec.ts
- business-filings-ui: tests/unit/FilingHistoryList2.spec.ts
- business-filings-ui: tests/unit/FilingHistoryList2.spec.ts
