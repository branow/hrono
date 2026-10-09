<!-- leaf 223, 16 members -->

These condensations describe the Vue/Vuetify components of a BC Registries business dashboard. Most are expansion panels, and the dashboard component lays them out. The set is incomplete: the first entry is labeled incomplete, and the Dashboard snippet shows only store getters.

## Groupings

### 1. Alert panels (shown in `Alerts`)

**Container: `Alerts`**
- It renders `v-expansion-panels` (id="alerts-container") with `:value="panel"`. It loops over a computed `alerts` array and passes `:showPanel="(panel === index)"` to each alert. It handles `@togglePanel="togglePanel(index)"`.
- It reads 7 getters from `useBusinessStore`.
- The `alerts` array is built in this priority order:
  1. InDissolution (the code comment says it "needs to be shown first (high priority)")
  2. Amalgamation
  3. CorporateOnline
  4. FrozenInformation
  5. MissingInformation
  6. NotInCompliance
  7. NotInGoodStanding
- `togglePanel(index)` sets `panel` to the index, or to NaN if it is already open.
- `@Watch('alerts', { immediate: true })` with `@Emit('count')` emits `alerts.length`. The Dashboard uses this count to hide the Alerts section when it is 0.

**Shared pattern across the 7 alert panels**
- Each is a `v-expansion-panel` with an orange alert icon, a title, and a "View Details"/"Hide Details" toggle button with a chevron.
- Each takes a required boolean prop `showPanel` and emits `togglePanel`.
- Each has a details body, and most embed `ContactInfo`.
- The styles are the same in each: `pointer-events: none` on the header and `pointer-events: auto` on the details button. They also use `:deep()` overrides on `.v-expansion-panel-content__wrap` padding and on icon and text sizes.

**Variations**

| Component | Title or message | Specifics |
|---|---|---|
| InDissolution | "This business is in the process of being dissolved" | Computes `targetDissolutionDate` from the `INVOLUNTARY_DISSOLUTION` warning's `data` and converts it to a Pacific date. Returns 'Unknown' if the warning is missing. Includes `ContactInfo`. |
| Amalgamation | Future-effective amalgamation warning | Finds the `FUTURE_EFFECTIVE_AMALGAMATION` warning. Formats the date with `DateUtilities.apiToPacificDate(date, true)`. Shows '[unknown]' if the date is missing. |
| CorporateOnline | "This business must be managed in Corporate Online." | Links to the `getCorporateOnlineUrl` config value. Describes the business type with `GetCorpFullDescription(getLegalType)`. |
| FrozenInformation | "This business is frozen" | Shows `ContactInfo`. Uses `hidePhoneNumbers`. |
| MissingInformation | "Missing information" (id="missing-information-panel") | Directs the user to BC Registries. Shows `ContactInfo`. Uses `hidePhoneNumbers`. |
| NotInCompliance | "This business is not in compliance" | Says "you MUST contact BC Registries staff". Shows `ContactInfo`. Described as Vue 2 and uses hide-actions. |
| NotInGoodStanding | "This business is not in good standing" (id="not-in-good-standing-panel") | Explains that the most common cause is an overdue annual report. Shows `ContactInfo`. Uses SCSS vars `$px-*`. |

`hidePhoneNumbers` is `isEntityFirm && !GetFeatureFlag('show-alert-phone-numbers-firm')`. It appears in FrozenInformation and MissingInformation.

### 2. Address and party lists

All of these are accordion lists with delivery and mailing address blocks. Each mailing address shows "Same as above" when `isSame(delivery, mailing, ['id'])` is true. Each address block lists `streetAddress`, `streetAddressAdditional`, city/region/postalCode, and the country name. Each uses a disabled or grayed-out state.

- **Address list (the first, incomplete entry):** If `isEntityFirm`, it renders `FirmsAddressList`. Otherwise it shows expansion panels for the registered office, plus the records office when `isBaseCompany`. A `showCompleteYourFilingMessage` flag shows "Complete your filing to display". `isCoaPending` adds an `address-overlay` class.
- **FirmsAddressList:** Shows `businessAddress` from the root store. It is disabled when `showCompleteYourFilingMessage || showGrayedOut`.
- **Directors list:**
  - It filters by `Roles.DIRECTOR` and sorts by lastName, firstName, middleName.
  - It adds a synthetic numeric `id` (1-based index) to each director.
  - It is disabled under the same conditions as FirmsAddressList.
- **CustodianListSm:** Each panel has an avatar (first letter) and `officerName(custodian)`.
- **ProprietorPartnersListSm:**
  - It returns the PROPRIETOR for sole proprietorships and all PARTNERs for partnerships.
  - It shows "(Not entered)" for empty values and emails.
  - It uses `CommonMixin` and `CountriesProvincesMixin`.
  - It has opacity 0.6 when disabled.

`officerName` returns `firstName middleInitial lastName` or `organizationName`.

### 3. Filing list

- **PendingList:**
  - It renders a `v-expansion-panels` loop with a dynamic sub-component from `is(item)`. That returns `'continuation-in'` for continuation-in filings and `'default-filing'` otherwise.
  - The `onPendingsChanged` watcher runs immediately. It expands the panel matching `highlightId` (via `header.filingId`), or the first item if there is no match.
- **Pending item panel:**
  - It is disabled, with a header showing `displayName`.
  - Its subtitle reads "PENDING STAFF REVIEW | PAID (filed by {submitter} on {submittedDate})".
  - The toggle button uses `@click.stop` and emits `toggle-panel`.
  - It uses `DateTooltip`. Its content is loaded eagerly.

### 4. Layout host

- **Dashboard:**
  - The left column holds Alerts, To Do, Pending Staff Review, and Recent Filing History. The right column holds Custodian of Records, addresses, and Proprietor/Partners or Current Directors.
  - Custodian shows when `isHistorical && custodians.length > 0`. The Proprietor/Partners or Directors section depends on `isEntityFirm`.
  - The address and director change buttons check `isAllowed(AllowableActions.ADDRESS_CHANGE)` or `DIRECTOR_CHANGE`.
  - `StaffNotation` is staff-only and sits in the filing history header.

## Caution:
- **`pointer-events` pattern (all alert panels):** The header has `pointer-events: none` and only the button has `pointer-events: auto`. Clicking the title or row will not expand the panel. Without `auto` on the button it would not respond either. `hide-actions` plus a custom button means the parent must track `showPanel` and handle `togglePanel`. The `showPanel` prop is read-only.
- **Disabled pending panel:** It is disabled but its button stays clickable through a `pointer-events: auto` override. This is unusual for a disabled component.
- **`Alerts` NaN state:** `panel` uses NaN rather than null or 0. The toggle works because NaN never equals an index, but it is unconventional.
- **`Alerts` order:** The order is hardcoded, and InDissolution must stay first. Reordering breaks the priority assumption.
- **`Alerts` store getters:** The `@Getter` decorators assume pinia-class compatibility. If the store changes, they could break silently.
- **`isSame(..., ['id'])`:** This excludes `id` from the comparison. Addresses that differ only in `id` show "Same as above".
- **Directors list `id` and `isSame`:** The synthetic `id` added to directors is ignored by the address comparison. It may not match any intended id field.
- **Address list:** `isCoaPending` adds a gray overlay, but how it affects interaction is unclear. `disabled` disables expansion entirely.
- **FirmsAddressList:** The nested v-if/v-else conditionals are hard to trace.
- **Proprietor/partners list:**
  - The proprietor lookup uses `.find()` and silently returns nothing if no PROPRIETOR exists.
  - `officerName` joins with spaces, so an empty middle initial leaves a double space.
- **`hidePhoneNumbers`:** It uses AND logic. Phone numbers are hidden only when `isEntityFirm` is true and the feature flag is absent.
- **InDissolution:** The date is nested in `warning.data`. A missing warning returns 'Unknown' without an error.
- **PendingList:** `onPendingsChanged` is async but has no `await`. The watcher runs immediately, so the first panel expands synchronously.
- **Dashboard:** The snippet shows only store getters. `isEntityFirm`, `isEntitySoleProp`, and `isEntityPartnership` drive the layout, but not all are visible. Check the computed properties for the full rendering logic.

## Members

- business-filings-ui: src/components/Dashboard/AddressListSm.vue
- business-filings-ui: src/components/Dashboard/Alerts.vue
- business-filings-ui: src/components/Dashboard/Alerts/Amalgamation.vue
- business-filings-ui: src/components/Dashboard/Alerts/CorporateOnline.vue
- business-filings-ui: src/components/Dashboard/Alerts/FrozenInformation.vue
- business-filings-ui: src/components/Dashboard/Alerts/InDissolution.vue
- business-filings-ui: src/components/Dashboard/Alerts/MissingInformation.vue
- business-filings-ui: src/components/Dashboard/Alerts/NotInCompliance.vue
- business-filings-ui: src/components/Dashboard/Alerts/NotInGoodStanding.vue
- business-filings-ui: src/components/Dashboard/CustodianListSm.vue
- business-filings-ui: src/components/Dashboard/DirectorListSm.vue
- business-filings-ui: src/components/Dashboard/FirmsAddressList.vue
- business-filings-ui: src/components/Dashboard/PendingList.vue
- business-filings-ui: src/components/Dashboard/PendingList/PendingTemplate.vue
- business-filings-ui: src/components/Dashboard/ProprietorPartnersListSm.vue
- business-filings-ui: src/views/Dashboard.vue
