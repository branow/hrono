<!-- leaf 218, 39 members -->

# Summary

This is a collection of condensed OpenAPI/Swagger fragments for the BC Registries **Auth API** (Accounts API v1.0.1, Keycloak-integrated). It covers the organization, user, entity, affiliation, and authorization endpoints, along with a few schema definitions and a robots.txt. Most fragments are partial or skeletal.

## Groupings

**1. Org resource (`/orgs`)**
- Core CRUD:
  - POST `/orgs` creates an org, as `post_orgs`. Premium users or internal callers can create, and the org starts pending.
  - GET `/orgs?org_name=` searches orgs.
  - GET, PUT and DELETE `/orgs/{org_id}` retrieve, update (`put_org`) and delete. Members can retrieve, admins can update, and owners can delete.
  - PATCH `/orgs/{org_id}/status` updates status.
  - The PUT body has `name` (required, no-extra-whitespace regex) and `typeCode`.
- Members:
  - GET `/orgs/{org_id}/members` is `get_org_members`.
  - PATCH `/orgs/{org_id}/members/{membership_id}` is `patch_org_member`. Its body is `orgMembershipRequest` (role, status, notifyUser).
  - DELETE on a membership is `delete_org_member`. It marks the record inactive, and the membership must match the current user token.
  - Invite, request and confirm flows: `/members/invite/{user_email}` (admin), `/members/request` (any user), `/members/confirm/{user_email}` (admin or invite code).
- Contacts (`/orgs/{org_id}/contacts`):
  - POST returns 201 with the contact schema.
  - PUT is `put_org_contacts`.
  - DELETE is `delete_org_contacts`.
  - All use the `contact` schema, and POST and PUT also return a 400 error.
- Affiliations (`/orgs/{org_id}/affiliations`):
  - POST is `post_org_affiliations`, returns 201, and is open to any basic user.
  - GET is `get_org_affiliations`, lists affiliated entities, and is open to any basic user.
  - DELETE `/{business_identifier}` is `delete_org_affiliation` and is owner-only.

**2. User resource (`/users`)**
- Create and search:
  - POST `/users` is an upsert from the JWT. It returns 201, or 409 in one description.
  - GET `/users?name=&email=` is a staff/admin search.
- Profile by id or token:
  - GET `/users/{user_id}` and GET `/users/{username}` (`get_user_staff`).
  - GET and DELETE `/users` (`get_user`, `delete_user`) act on the JWT's own profile.
  - PUT and PATCH `/users/{user_id}` are admin-only.
- Terms of service: PATCH `/users` is `patch_user`. It sets `isTermsOfUseAccepted` and `termsOfUseAcceptedVersion`.
- Related lists:
  - GET `/users/{user_id}/orgs`.
  - GET `/users/{user_id}/entities`.
  - GET `/users/authorizations` (`get_authorization_resource`).
  - `get-users-user-guid-settings` returns a `userSettings` array.

**3. Entity resource (`/entities`)**
- It shadows LEAR entities and stores only the data needed for affiliations.
- GET `/entities` and PUT `/entities` (business contact info) are public.
- POST `/entities` and GET `/entities/{entity_id}` are internal-only.
- DELETE `/entities/{businessIdentifier}` is the contact delete, `delete_contact_resource`.

**4. Authorization endpoints**
- Entity-level: GET `/entities/{businessIdentifier}/authorizations` is `getAuthorizations`, tag `authorization`. It appears in several fragments, most with an empty or truncated 200 body.
- Account and product level:
  - GET `/accounts/{account_id}/products/{product_code}/authorizations` is an empty stub.
  - A GET `/authorizations` fragment returns `authorizations`, with examples `{orgMembership: MEMBER|ADMIN, roles: [search, edit, make_payment]}`.
  - `getOrgAuthorizations` has no 200 body defined.
- Response examples cover owner, admin, member, staff, unauthorized, expanded_premium and expanded_cc, and all share identical headers.
- A membership-type listing gives MEMBER, ADMIN and OWNER with icons and labels.

**5. Shared boilerplate and spec metadata**
- Nearly every 200 response declares the same four headers: `X-Application-Context` (`application:prod`) and three `Access-Control-Allow-*` headers. The values are `*`, `GET, OPTIONS`, and `Content-Type, api_key, Authorization`.
- Error responses use `{code, message}`.
- Schemas: `ErrorResponse`, `Authorization` (orgMembership enum USER, COORDINATOR or ADMIN), `orgMembershipRequest` and `userSettings`.
- Security scheme: API key as a query parameter.
- Server: the mock-lear-tools.pathfinder.gov.bc.ca mock host.
- `robots.txt` allows all crawlers.

## Caution:
- **Permissions:**
  - The affiliation model is asymmetric: POST and GET allow any basic user, while DELETE is owner-only.
  - The org model is inconsistent: search is open to anyone, and confirm accepts an admin or an invite code, with no documented scope or expiry for the code.
  - User endpoints mix Bearer-token self-access with admin-only access, and mixing them up causes auth failures.
  - Entity POST and GET `/{entity_id}` are internal-only.
  - The JWT in the authorization header is not documented in the request specs for GET and DELETE `/users`.
  - DELETE membership requires the token to match, with no scope defined.
  - POST `/users` upserts, so a duplicate may silently update the existing user.
- **CORS and security:**
  - `Access-Control-Allow-Origin: *` is returned for every role. Check that this is intended.
  - The headers are identical across all role examples, so they don't reflect any role-based access.
  - The headers are hardcoded in the spec, which suggests manual CORS handling.
  - The `api_key` header is non-standard.
- **Truncated or empty definitions:**
  - The authorizations paths, the Accounts API `paths` section and the `getOrgAuthorizations` 200 body are stubs.
  - Several `$ref` targets (`contact`, `affiliation`, `authorizations`, `membership`) are not defined in the fragments, and some examples blocks are empty.
- **Schema inconsistencies:**
  - `roles` has untyped `items: {}`, and the authorizations array `items` is also `{}`.
  - The "STAFF" role isn't in the orgMembership enum.
  - The `staff` example has no orgMembership, and `unauthorized` is `{}`.
  - PATCH `/users` returns a `contact` schema although it updates user terms.
  - The membership-type schema has the typo `defaut`, while its example uses `default`.
  - `typeCode`'s pattern `^(.*)$` matches anything.
  - The `orgMembershipRequest` properties have no enum or length limits.
  - `userSettings` has `uniqueItems: true` with no identifier, so duplicate detection depends on the validator.
- **Copy-paste and typos:**
  - The `username` parameter is described as "Corp Type".
  - The 404 schema is inline, not a `$ref`.
  - The `get_user_staff` operationId sits on a generic path.
  - One description says "indentifier".
  - Header values are declared but not set.
  - The version is `1.0.1`, not `1.0`.
  - Some path parameters are not shown, for example `org_id` on GET affiliations.

## Members

- sbc-auth: auth-api/docs/affiliation_contracts.txt
- sbc-auth: auth-api/docs/contract.yaml
- sbc-auth: auth-api/docs/contract.yaml
- sbc-auth: auth-api/docs/contract.yaml
- sbc-auth: auth-api/docs/contract.yaml
- sbc-auth: auth-api/docs/contract.yaml
- sbc-auth: auth-api/docs/entity_contracts.txt
- sbc-auth: auth-api/docs/org_contracts.txt
- sbc-auth: auth-api/docs/user_contracts.txt
- sbc-auth: auth-web/public/robots.txt
- sbc-auth: docs/docs/api_contract/auth-api-1.0.0.yaml
- sbc-auth: docs/docs/api_contract/auth-api-1.0.0.yaml
- sbc-auth: docs/docs/api_contract/auth-api-1.0.0.yaml
- sbc-auth: docs/docs/api_contract/auth-api-1.0.0.yaml
- sbc-auth: docs/docs/api_contract/auth-api-1.0.0.yaml
- sbc-auth: docs/docs/api_contract/auth-api-1.0.0.yaml
- sbc-auth: docs/docs/api_contract/auth-api-1.0.0.yaml
- sbc-auth: docs/docs/api_contract/auth-api-1.0.0.yaml
- sbc-auth: docs/docs/api_contract/auth-api-1.0.0.yaml
- sbc-auth: docs/docs/api_contract/auth-api-1.0.0.yaml
- sbc-auth: docs/docs/api_contract/auth-api-1.0.0.yaml
- sbc-auth: docs/docs/api_contract/auth-api-1.0.0.yaml
- sbc-auth: docs/docs/api_contract/auth-api-1.0.0.yaml
- sbc-auth: docs/docs/api_contract/auth-api-1.0.0.yaml
- sbc-auth: docs/docs/api_contract/auth-api-1.0.0.yaml
- sbc-auth: docs/docs/api_contract/auth-api-1.0.0.yaml
- sbc-auth: docs/docs/api_contract/auth-api-1.0.0.yaml
- sbc-auth: docs/docs/api_contract/auth-api-1.0.0.yaml
- sbc-auth: docs/docs/api_contract/auth-api-1.0.0.yaml
- sbc-auth: docs/docs/api_contract/auth-api-1.0.0.yaml
- sbc-auth: docs/docs/api_contract/auth-api-1.0.0.yaml
- sbc-auth: docs/docs/api_contract/auth-api-1.0.0.yaml
- sbc-auth: docs/docs/api_contract/auth-api-1.0.0.yaml
- sbc-auth: docs/docs/api_contract/auth-api-1.0.0.yaml
- sbc-auth: docs/docs/api_contract/auth-api-1.0.0.yaml
- sbc-auth: docs/docs/api_contract/auth-api-1.0.0.yaml
- sbc-auth: docs/docs/api_contract/auth-api-1.0.0.yaml
- sbc-auth: docs/docs/api_contract/auth-api-1.0.0.yaml
- sbc-auth: docs/docs/api_contract/auth-api-1.0.0.yaml
