<!-- level 1, node 510, children [82, 114, 115, 172, 175, 178, 220, 221, 222, 264, 265, 340, 380, 420, 547, 548] -->

# Parent brief: BC Registries / SBC Auth Keycloak, Postman and dev-tooling notes

These notes cover Keycloak setup and automation for the BC Gov SBC Auth / BC Registries stack. The groups are listed with routing signal. Most source fragments are truncated, and many repeat each other.

## 1. Postman: "Keycloak SSO Client Creation" (id 7415e2a2-…)
- **Purpose:** Creates OIDC clients (bca-web, vitalstats-web). Request: `POST {{keycloak-base-url}}auth/admin/realms/fcf0kpqr/clients`. The collection's `item` array is empty or truncated.
- **Variables:**
  - `keycloak-base-url`
  - `service-account-id`: `keycloak-sa` in the older env, `sbc-auth-admin` in the newer
  - `service-account-secret`
  - `client-id`
  - `root-url`
  - `valid-redirect-urls` and `web-origins`: comma-separated strings, with `web-origins` defaulting to `*`
- **Environments ("Keycloak-DEV", id 60d4e6d4-…):**
  - The older export (2020) points at `sso-dev.pathfinder.gov.bc.ca`.
  - The newer export (2022) points at `dev.oidc.gov.bc.ca` and adds `*-array` variables.
  - Secret, client-id, root-url and redirect URLs are empty in both.
- **Scripts:**
  - The pre-request script splits the comma strings into `valid-redirect-urls-array` and `web-origins-array`. It asserts the redirect URLs are non-empty.
  - The collection-level OAuth2 script gets a client_credentials token on every request, with basic auth from the service account. It hardcodes realm `fcf0kpqr`, and token errors are only logged.
- **Client body template:**
  - `openid-connect` protocol, standard flow and direct access grants on, implicit off.
  - Variants: public client with PKCE S256, confidential, or service-account-disabled.
  - Embedded audience mappers (`account-services`, `entity-services`, `sbc-auth-web`).
  - Default scopes: `web-origins`, `roles`. Optional scope: `offline_access`.

## 2. Postman: user and passcode loaders
- **"KeyCloak User Creation - RH" / "RH copy" (ids fd15f7ec…, 54c0fb60…):**
  - Dev environment (2019): realm `fcf0kpqr`, client `sbc-auth-cron-job`, defaultGroup `basic/editor`.
  - Request chain driven by a data file of IncNumber and Passcode:
    1. Create user (source=PASSCODE).
    2. Get user id.
    3. Reset password.
    4. Get group id.
    5. Add the user to the group.
  - The README calls the password step "PATCH", but it is a PUT.
- **"passcode user importer" (2afef774-…):** The same chain, keyed on `corp_num`, `corp_type` and `temp_password`. It adds a refresh-token request and a pre-request token script. The "Logout admin" request just calls userinfo and does not log out.
- **auth-api collections (auth-api, auth-api-load-entities, api-gw-account-keys, data-reset-tool, lear-integration):** Mostly stubs. They use `{{api_url}}` with persona tokens and run via Newman. The environments are Auth-Api-DEV, Auth-Api-local and API-GW-ACCOUNTS-DEV (2020–2021).
- **Legal-api / pay-api Postman set:**
  - Keycloak token scripts using client credentials, password and refresh grants.
  - GET business, tasks and filings requests.
  - Environments `legal-api-perf (TST)`, `legal-dev` and the Pay API environment.
  - Variable names are inconsistent across these environments (`base_url`/`url`, `kc_url`/`auth_url`).

## 3. Keycloak realm export ("demo" realm, sbc-auth)
- **Realm roles:** CP, offline_access, staff, uma_authorization, tester, colin, edit, view, public_user, anonymous_user, account_holder, premium, job, system and sandbox. All are non-composite.
- **realm-management client roles:** Includes the composites view-users, view-clients and realm-admin.
- **Groups:**
  - Core: admins, users, public_users, account_holders, anonymous_users.
  - Extended: gov_account_users, ppr, and the api_gateway subgroups.
  - Product groups: bca, vs and the mhr_* groups, each granting only `edit`.
  - Defaults: roles `offline_access` and `uma_authorization`, group `/users`, credential `password`.
- **Clients:**
  - `realm-management`: bearer-only, yet flagged standard flow.
  - `sbc-auth-web`: standard flow plus direct access grants, with placeholder secret `1111111111`.
  - `sbc-auth-admin`: service account, with placeholder secret `2222222222`.
- **Service accounts:**
  - `service-account-realm-management` is minimal (`uma_protection`, `view-profile`, `manage-account`).
  - `service-account-sbc-auth-admin` is broad. It has realm roles CP, edit, tester and system, and manage-users, manage-authorization, query-*, view-* and create-client/manage-clients.
- **Protocol mappers:**
  - OIDC property and attribute mappers: `preferred_username`, firstName, lastName, email, full name, `displayName`, and Source Mapper (`source` → `loginSource`).
  - Realm roles: access token only.
  - Audience: `sbc-auth-web`.
  - Session notes: `clientAddress`, `clientId`, `clientHost`.
  - Hardcoded mappers: `CORP_TYPE`/`corp_type`='CP', `product_code`='BUSINESS', and `preferred_username`/`firstname`/`lastname` set to sbc-auth-admin, sbc-auth and admin.
  - SAML `saml-role-list-mapper` (attribute `Role`, Basic).
  - Naming is inconsistent between `firstname`/`given_name` and `lastname`/`family_name`.

## 4. Local dev infrastructure
- **Docker Compose stack:**
  - Keycloak on 8081 (versions 12.0.2, 15.0.0 and 16.1.0), importing realm `demo` from `./setup` with OVERWRITE_EXISTING.
  - nginx proxy on 8080.
  - Stoplight Prism 3.3.0 mocks on 4010: notify, bcol, pay, reports, paybc, auth. Specs come from raw GitHub (sbc-pay and sbc-auth).
  - Optional NATS, MinIO, an SFTP variant and a Pub/Sub emulator.
- **Helpers:** A startup script runs `docker-compose up -d` and polls the realm URL.

## 5. Code: Python and Vue
- **Python auth-api `KeycloakService`:**
  - User and group management, with group mapping by LoginSource.
  - Async bulk group updates over aiohttp.
  - OTP reset.
  - `create_client` and `get_service_account_user`.
  - A `KeycloakUser` wrapper, a deprecated Flask `/keycloak/users` endpoint, and an OIDC singleton.
  - A `remove_users.py` cleanup job that defaults to realm `fcf0kpqr`.
  - A `FeeCode` model is unrelated.
- **Vue/TypeScript front end:**
  - Axios clients (Keycloak, Sentry, trace) that add a bearer token from sessionStorage and skip minio URLs.
  - Services for auth, legal, pay, search and BCOL.
  - Pinia stores.
  - Qualified-supplier requirements for the three MHR task types.

## Cross-cutting cautions
- **Secrets:** Plaintext client secrets and passwords appear in environments and compose files, including `sbc-auth-cron-job`, the legal-dev `client_secret`, admin/admin, minio/minio123 and `test_staff`. Rotate them and move them to a vault or `.env`.
- **Hosts and realm:**
  - Hosts differ between exports (pathfinder, `dev.oidc.gov.bc.ca`, the silver cluster, `dev.loginproxy.gov.bc.ca`). Realm `fcf0kpqr` is hardcoded in many places and doesn't match `bcregistry`/`demo`. Confirm the target before running anything.
  - Some exports are old (2019–2022), and Keycloak 12 is EOL.
- **Truncated or empty collections:** The JSON is truncated, collections are empty, and duplicate "RH copy" collections may have diverged. The canonical copy is unconfirmed.
- **Unset variables:** Unset `{{variables}}` are sent literally, and template arrays must be valid JSON. Variable names are inconsistent between environments. `documnent_key` is a typo that must be matched exactly.
- **Chain fragility:** In the user-creation chain, `jsonData[0].id` and `groupId` are unguarded. Later steps fail silently if an earlier one fails. Passcodes lose leading zeros, and IncNumber must be lowercase.
- **Token handling:** Tokens are stored in both environment and variables. Postman scripts fetch tokens on every request without expiry checks. Front-end tokens in sessionStorage have no refresh.
- **Mapper pitfalls:**
  - Realm roles reach only the access token.
  - Hardcoded mappers (`preferred_username`='sbc-auth-admin', `firstname`, `lastname`, `CORP_TYPE`) override real user data.
  - The audience must be exactly `sbc-auth-web`.
  - `aud-sbc-auth-web-mapper-REMOVE` is still active.
  - `web-origins` defaults to `*`.
- **Realm export gaps:** `defaultGroups` is only `/users`. The `${role_*}` descriptions are i18n placeholders. `realm-management` has contradictory flags, and its redirect URIs and web origins are empty.
- **Infrastructure risks:**
  - Prism mocks need GitHub at startup.
  - OVERWRITE_EXISTING wipes the realm on restart.
  - The healthcheck and startup script can hang or give false passes.
  - `docker-compose` is deprecated.
- **Code issues:**
  - Python: the `KeycloakUser.password` getter can raise KeyError, the async bulk update runs add and remove sequentially, the test assertions are vacuous, and `remove_users.py` matches only the `bcros/` prefix.
  - Vue: services swallow errors and return null, `{}` or false inconsistently, and some blob typing is misleading.
