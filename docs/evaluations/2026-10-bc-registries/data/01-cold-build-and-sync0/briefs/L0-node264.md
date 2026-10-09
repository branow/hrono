<!-- leaf 264, 27 members -->

These condensations all describe one Keycloak realm export for the "demo" realm, which looks like the SBC auth setup (it references sbc-auth-web and sbc-auth-admin). The export is split across several JSON chunks. Many chunks repeat, and a few are truncated.

## Realm-level roles
- **Roles:** CP, offline_access, staff, uma_authorization, tester, colin, edit, view, public_user, anonymous_user, account_holder, premium, job, system, and sandbox. Different chunks list different subsets, between 13 and 15 of them.
- **Settings:** All are non-composite and realm-scoped (clientRole=false, containerId "demo").
- **Descriptions:** Only offline_access, uma_authorization and sandbox ("Role to distinguish sandbox keys") have descriptions.
- **Truncation:** Several chunks cut off at `"client": {"realm-management":` or earlier, so the client-role section is missing from them.

## realm-management client roles
These roles all live in container 9e254d9e-9aa8-4357-b86e-4762544c8dce, have clientRole=true, and use `${role_*}` descriptions.
- **Plain roles:**
  - manage-identity-providers, view-realm, manage-events, manage-users, manage-realm, impersonation, manage-authorization, manage-clients (id f457fe31-…) and view-events.
  - query-realms and query-clients.
  - query-groups, view-authorization, create-client, view-identity-providers and query-users, each with its own listed id.
- **Composite roles:**
  - view-users includes query-groups and query-users.
  - view-clients includes query-clients.
  - realm-admin bundles the realm-management permissions: 17 per the summary, though the list names 18.
- **Empty clients:** sbc-auth-web and sbc-auth-admin have empty role arrays.

## Groups and defaults
- **Core groups:**
  - admins: canEdit, canView.
  - users: canView.
  - public_users: edit, public_user.
  - account_holders: account_holder.
  - anonymous_users: edit, anonymous_user.
- **Extended variant:**
  - public_users also has ppr, plus subgroups api_gateway_users (no roles) and api_gateway_sandbox_users (sandbox).
  - gov_account_users: edit, public_user, gov_account_user.
  - ppr: edit.
- **Pattern group:** bca, vs, mhr_search_user, mhr_qualified_user, mhr_manufacturer and mhr_general_user each have path `/{name}` and realmRoles ['edit'].
- **Defaults:** defaultRoles are offline_access and uma_authorization, defaultGroups is /users, and requiredCredentials is password.

## Service accounts
- **service-account-realm-management:** realm roles uma_authorization and offline_access, plus client roles uma_protection (realm-management) and view-profile and manage-account (account).
- **service-account-sbc-auth-admin:** the same two realm roles plus CP, edit, tester and system. Its client roles are manage-users, manage-authorization, query-groups, query-users, view-authorization and view-users (realm-management), plus view-profile and manage-account (account).
- Both are in /users and have no credentials or required actions.

## Fragments
- One opening snippet shows realm="demo", enabled=true, and a roles object that cuts off.
- One snippet shows the **job** and **system** roles, then cuts off at the start of `"client": { "realm-management":`.

Caution:
- **Truncated data:** Several chunks are incomplete, so the full realm configuration cannot be assessed.
- **i18n placeholders:** `${role_*}` descriptions show literally unless the locale bundle defines those keys.
- **Privileged roles:**
  - realm-admin grants impersonation, manage-realm, manage-users and manage-authorization.
  - service-account-sbc-auth-admin is more privileged than service-account-realm-management.
- **Schema differences:** Composite roles use a `composites.client` object, and some non-composite roles lack id and containerId.
- **Naming inconsistency:** Role names mix camelCase (canEdit, canView), snake_case (public_user) and bare names (edit). Check what the client code expects.
- **Group role gaps:**
  - api_gateway_users has no realm roles despite being a subgroup of public_users. Verify this is intentional.
  - The six `/{name}` groups all grant only 'edit', even though names like mhr_* suggest distinct permission tiers.
- **Default assignment:** defaultGroups assigns only /users, so admins, public_users and account_holders must be assigned explicitly.
- **No visible hierarchy:** All realm roles are non-composite, so any hierarchy must be defined elsewhere.

## Members

- sbc-auth: auth-api/tests/docker/setup/demo-realm.json
- sbc-auth: auth-api/tests/docker/setup/demo-realm.json
- sbc-auth: auth-api/tests/docker/setup/demo-realm.json
- sbc-auth: auth-api/tests/docker/setup/demo-realm.json
- sbc-auth: auth-api/tests/docker/setup/demo-realm.json
- sbc-auth: auth-api/tests/docker/setup/demo-realm.json
- sbc-auth: auth-api/tests/docker/setup/demo-realm.json
- sbc-auth: auth-api/tests/docker/setup/demo-realm.json
- sbc-auth: queue_services/account-mailer/tests/docker/setup/demo-realm.json
- sbc-auth: queue_services/account-mailer/tests/docker/setup/demo-realm.json
- sbc-auth: queue_services/account-mailer/tests/docker/setup/demo-realm.json
- sbc-auth: queue_services/account-mailer/tests/docker/setup/demo-realm.json
- sbc-auth: queue_services/account-mailer/tests/docker/setup/demo-realm.json
- sbc-pay: bcol-api/tests/docker/setup/demo-realm.json
- sbc-pay: bcol-api/tests/docker/setup/demo-realm.json
- sbc-pay: jobs/payment-jobs/tests/docker/setup/demo-realm.json
- sbc-pay: jobs/payment-jobs/tests/docker/setup/demo-realm.json
- sbc-pay: jobs/payment-jobs/tests/docker/setup/demo-realm.json
- sbc-pay: jobs/payment-jobs/tests/docker/setup/demo-realm.json
- sbc-pay: jobs/payment-jobs/tests/docker/setup/demo-realm.json
- sbc-pay: jobs/payment-jobs/tests/docker/setup/demo-realm.json
- sbc-pay: pay-api/tests/docker/setup/demo-realm.json
- sbc-pay: pay-api/tests/docker/setup/demo-realm.json
- sbc-pay: pay-api/tests/docker/setup/demo-realm.json
- sbc-pay: pay-api/tests/docker/setup/demo-realm.json
- sbc-pay: pay-api/tests/docker/setup/demo-realm.json
- sbc-pay: pay-api/tests/docker/setup/demo-realm.json
