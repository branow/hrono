<!-- level 1, node 510, children [82, 114, 115, 172, 175, 178, 195, 220, 221, 222, 264, 265, 266, 340, 380, 420] -->

# Parent brief: BC Registries Keycloak (SSO) tooling and sbc-auth stack

This brief covers a family of artifacts for the BC Registries / SBC Keycloak setup: Postman collections and environments, realm-export fragments, Flask-Admin and Keycloak service code, local-dev Docker infrastructure, and Vue front-end services. Many fragments are truncated or repeated.

## 1. Postman: Keycloak client creation ("Keycloak SSO Client Creation", id 7415e2a2-…)
- **Purpose:** It creates OIDC clients such as `bca-web` and `vitalstats-web`. The collection's `item` array is empty or incomplete.
- **Request:** `POST {{keycloak-base-url}}auth/admin/realms/fcf0kpqr/clients`.
- **Environment "Keycloak-DEV"** (id 60d4e6d4-…):
  - Variables: `keycloak-base-url`, `service-account-id`, `service-account-secret`, `client-id`, `root-url`, `valid-redirect-urls`, `web-origins`.
  - The 2022 export points at `dev.oidc.gov.bc.ca` with service account `sbc-auth-admin` and adds `*-array` variables.
  - The 2020 export points at `sso-dev.pathfinder.gov.bc.ca` with `keycloak-sa`.
- **Scripts:**
  - A pre-request script splits the comma-separated `valid-redirect-urls` and `web-origins` into `*-array` JSON variables. `web-origins` defaults to `['*']`.
  - Collection OAuth2 fetches a `client_credentials` token on every request.
- **Client template:**
  - OIDC, standard flow and direct access grants on, implicit off.
  - Variants: public client with PKCE S256, confidential, or service-account-disabled.
  - Embedded audience mappers: `aud-account-services-mapper` and `aud-entity-services-mapper`.
  - Default scopes `web-origins` and `roles`, optional scope `offline_access`.
- **Mapper fragments:** audience (`account-services`, `entity-services`, `sbc-auth-web`), `idp_userid`, `access_type`→`accessType`, user attributes, and standard profile mappers.

## 2. Postman: passcode user import
- **Collections:**
  - "KeyCloak User Creation - RH" and "- RH copy" (ids fd15f7ec…, 54c0fb60…).
  - "passcode user importer" (2afef774-…).
- **Environment and data:** The Dev KeyCloak environment has clientId `sbc-auth-cron-job` and defaultGroup `basic/editor`. The data file has `IncNumber`/`Passcode` records.
- **Request chain** (each step passes a value to the next through an environment variable):
  1. Create user, with source=`PASSCODE`.
  2. Get the user id (`userId`).
  3. Reset the password (`temporary:false`).
  4. Get the group id (`groupId`).
  5. Add the user to the group.
- **Variants:** The importer uses `corp_num`, `corp_typ_cd`, `temp_password`, and `adminToken`/`adminRefreshToken`. Its "Logout admin" request is really a userinfo GET.

## 3. Other Postman collections
- **legal-api:** Get Business, Tasks and Filings, plus the data-reset-tool.
- **auth-api:** users, orgs, members, entities, documents and invitations requests, with role-specific token variables.
- **Others:** the api-gw-account-keys, lear-integration and pay-api environments.
- **Token scripts:** password-grant and refresh-token scripts store `token` and expiry fields. They never check expiry.
- **Stray item:** a `FeeCode` SQLAlchemy model.
- **Separate OAuth config:** `pay-admin` on `dev.loginproxy.gov.bc.ca`, realm `bcregistry`.

## 4. Realm export ("demo" realm, sbc-auth)
- **Realm roles:** CP, offline_access, staff, uma_authorization, tester, colin, edit, view, public_user, anonymous_user, account_holder, premium, job, system and sandbox. Different chunks list different subsets, and all are non-composite.
- **realm-management client roles:** `view-users`, `view-clients` and `realm-admin` are composite. The other roles are plain.
- **Groups:**
  - admins, users, public_users, account_holders and anonymous_users.
  - Extended variant: gov_account_users, ppr, api_gateway_users, api_gateway_sandbox_users, bca, vs and mhr_*.
- **Defaults:** `defaultRoles` are `offline_access` and `uma_authorization`; `defaultGroups` is `/users`.
- **Clients:**
  - `realm-management`: bearer-only, with a contradictory standard flow.
  - `sbc-auth-web`: confidential, with placeholder secret `1111111111`.
  - `sbc-auth-admin`: service-account client, with placeholder secret `2222222222`.
- **Service-account users:**
  - `service-account-realm-management` has minimal rights.
  - `service-account-sbc-auth-admin` has broad manage-users, manage-authorization, query-*, create-client and manage-clients rights.
- **Client scopes:** The client-scope fragment (`web-origins`/`roles`, optional `offline_access`) and the standalone `access` object are repeated.

## 5. Protocol mapper sets (OIDC and SAML), repeated across fragments
- **User mappers:** username→`preferred_username`, firstName→`firstname` or `given_name`, lastName→`lastname` or `family_name`, email, full name, displayName, and `Source Mapper` (source→`loginSource`).
- **Realm roles:** multivalued, access token only.
- **Hardcoded claims** (same value for every user):
  - `preferred_username`=`sbc-auth-admin`
  - `firstname`=`sbc-auth`
  - `lastname`=`admin`
  - `CORP_TYPE`=`CP`
  - `product_code`=`BUSINESS`
- **Session notes:** `clientAddress`, `clientId` and `clientHost`.
- **Audience:** `sbc-auth-web`, access token only.
- **SAML:** a role-list mapper with attribute `Role`.

## 6. Backend code (auth service)
- **`KeycloakService`:**
  - User and group CRUD.
  - OTP reset.
  - Bulk group add/remove via async aiohttp.
  - `create_client` and `get_service_account_user`.
  - Upstream BCROS and local Keycloak config.
- **Supporting code:**
  - `KeycloakUser` dict wrapper.
  - A deprecated `/keycloak/users?role=` endpoint.
  - A `Keycloak` OIDC singleton (`has_access`).
- **`remove_users.py` cleanup job:** it deletes users from the upstream IDP and Keycloak realms, with an `-exclude` list. The default realm is `fcf0kpqr`.
- **Flask-Admin layer:**
  - `SecuredView` is Keycloak-role gated (`admin_view`/`admin_edit`).
  - `IndexView` is hidden.
  - There are views for CorpType, FeeCode, FilingType (via `CodeConfig`), DistributionCode and FeeSchedule.
  - One parametrized test covers all of them.

## 7. Local-dev Docker Compose
- **Stack:** Keycloak (12.0.2, 15.0.0 or 16.1.0 arm64) on port 8081 with the `demo` realm imported from `./setup`. nginx on 8080 and Stoplight Prism 3.3.0 mocks on 4010 (bcol, pay, reports, paybc, auth, notify).
- **Optional extras:** NATS, MinIO, an SFTP variant and a Pub/Sub emulator.
- **Startup script:** it polls `/auth/realms/demo`.

## 8. Vue/TypeScript front-end services
- **Axios clients:** Keycloak, Sentry and trace clients. All skip the auth header for minio URLs.
- **Auth API services:** User, Org, Permission, Codes, Invitation, AffiliationInvitation, Activity, Task, Bcol, Staff and Document.
- **Legal and payment services:** `LegalServices`, a combined auth/legal v2 service, `PayServices`, `PaymentService` with EFT shortnames, and `useDownloader`.
- **Lookups, store and config:** business/NR/VON lookups, the Pinia activity and org stores, and MHR qualified-supplier requirement text.

## Key cautions
- **Secrets:** Plaintext secrets appear in the Postman environment exports (`sbc-auth-cron-job`, legal-dev `client_secret`), in the compose files (admin/admin, minio/minio123, `ftp_user:ftp_pass`) and in the placeholder client secrets. Rotate them and use a secrets manager.
- **Hardcoded realm and hosts:**
  - Realm `fcf0kpqr` is hardcoded in URLs and script defaults.
  - Hosts differ across exports: `sso-dev.pathfinder.gov.bc.ca` (legacy), `dev.oidc.gov.bc.ca`, and `dev.loginproxy.gov.bc.ca`.
  - The trailing-slash convention on `keycloak-base-url` is inconsistent.
- **Truncation and duplication:** Most JSON is truncated, so full structure is unknown. Duplicate "RH copy" collections need a canonical choice.
- **Mapper pitfalls:**
  - Hardcoded claims override real user data.
  - Realm roles reach only the access token, not the ID token or userinfo.
  - The audience must be exactly `sbc-auth-web`.
  - Claim names are inconsistent (`firstname` vs `given_name`).
  - The username mapper is defined twice with different claims.
  - `aud-sbc-auth-web-mapper-REMOVE` is still active.
- **Script and request fragility:**
  - `web-origins` silently defaults to `*`, which is too permissive for production.
  - Tests lack guards: `jsonData[0].id` with an empty result leaves `userId` undefined, and later steps fail silently.
  - Passcodes are integers, so leading zeros are lost, and IncNumber must be lowercase.
  - Token scripts never check expiry, and errors are only logged.
- **Compose and script risks:**
  - `OVERWRITE_EXISTING` on Keycloak import wipes state.
  - Prism mocks fetch specs from GitHub, so they fail offline.
  - The healthcheck syntax is faulty in some variants.
  - The startup script has no timeout.
  - Keycloak 12 is end-of-life, and `docker-compose` is deprecated.
- **Code-level bugs and quirks:**
  - `DistributionCodeConfig` lists `stop_ejv` twice.
  - The async bulk-update `asyncio.run()` calls run add and remove sequentially.
  - The test assertions pass vacuously.
  - `KeycloakUser.password` raises `KeyError` unless the setter ran first.
  - `remove_users` splits an empty `-exclude` into `['']` and only matches the `bcros/` prefix.
  - Front-end services have inconsistent error handling: many return null, false or `{}`, others throw.
  - Blob responses are typed as `'json'`, and the IE-only `msSaveOrOpenBlob` is still referenced.
- **Privilege and design inconsistencies:**
  - `service-account-sbc-auth-admin` is broadly privileged.
  - The `realm-management` client's bearer-only and standard-flow settings contradict each other.
  - Group roles are uniform (`edit` only) across the mhr_* groups.
  - `defaultGroups` assigns only `/users`.
