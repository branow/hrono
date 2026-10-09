<!-- level 1, node 509, children [1, 3, 39, 62, 64, 133, 149, 158, 218, 219, 402] -->

# Parent Brief: BC Registries OpenAPI Spec Fragments

Nearly all of these are truncated, empty, or duplicated condensations of OpenAPI/Swagger specs for BC Government registry services. They cover the Auth/Accounts API, the Notify API, the Report API, the Business Registry API, and shared error and CORS boilerplate. Treat every fragment as partial. Most `$ref` targets are not defined in the fragments, so check the full spec before relying on any of them.

## Services and routing signal

**1. Auth / Accounts API (v1.0.1, Keycloak, sbc-auth style)**
- **`/orgs`:**
  - CRUD: `post_orgs`, `put_org`, GET `/orgs?org_name=`, and PATCH `/orgs/{org_id}/status`.
  - Members: `get_org_members`, `patch_org_member`, `delete_org_member`, plus the invite, request and confirm flows.
  - Contacts: `put_org_contacts`, `delete_org_contacts`.
  - Affiliations: `post_org_affiliations`, `get_org_affiliations`, `delete_org_affiliation`. POST and GET are open to any basic user, and DELETE is owner-only.
- **`/users`:**
  - POST `/users` is an upsert from the JWT.
  - Staff search by name or email.
  - Self-service GET and DELETE (`get_user`, `delete_user`).
  - Admin-only PUT and PATCH by id.
  - Terms-of-use PATCH (`patch_user`).
  - Related lists for orgs, entities and settings.
- **`/entities`:**
  - It shadows LEAR entities.
  - GET and PUT are public. POST and GET by `entity_id` are internal.
  - Also `get_entity_resource`, `post_contact_resource`, `put_contact_resource` and `delete_contact_resource`.
  - Entity fields: `businessIdentifier` (e.g. CP0001578) and `businessNumber` (CP0001847) are distinct values.
  - Entity schema: 9 required fields, with `contacts` in `x-example` only.
  - Request schemas: `entityRequest`, `affiliationRequest`, `invitationRequest` and `orgRequest`.
  - Contact schema: email, phone, address fields. `email` has the only real regex. Most other fields use `^(.*)$`, which validates nothing.
- **Authorization:**
  - `getAuthorizations` at `/entities/{businessIdentifier}/authorizations`, `getOrgAuthorizations`, `searchOrgs`, and `/accounts/{account_id}/products/{product_code}/authorizations`.
  - Example identifiers: CP0001234 (owner), CP0001235 (admin), CP0001236 (member), CP0001237 (staff) and CP0000000 (unauthorized).
  - The `Authorization` schema has an `orgMembership` enum.
- **Reference data:** GET `/codes` (`get_codes`, `code_type`), membership types, and `userSettings`.

**2. Notify API (v1.0.0, Apache 2.0)**
- `POST /Notification` (`Send_Notification`) returns 201 `NotificationResponse`, or 422 `HTTPValidationError`.
- `GET /api/v1/notify/{notification_id}` finds a notification.
- A status-filtered GET (example `DELIVERED`) is truncated.
- Requests use camelCase and responses use snake_case.
- `NotificationStatus` and `NotificationType` are identical but separate.
- Security is JWT bearer. Dev, Test and Prod servers are on `notify-api*.apps.silver.devops.gov.bc.ca`.

**3. Report API (v1.0)**
- `POST /reports` (`post_report`) creates a PDF report. The 200 response has no defined properties.

**4. Business Registry API**
- Business endpoints (take `identifier` in the path, `accountId` as a ref):
  - `get-business`
  - `/addresses`, using the singular `Office` schema
  - `/parties`, using the singular `party` schema
  - filings, using the Ledger schema
  - `/document/{documentName}`, which is truncated
- Filing documents: list and download under `/filings/{filingId}/documents`. The download takes a `Content-type` of `application/pdf` or `application/json`.
- `get-businesses-search`: an autocomplete with a `q` param, public (`x-internal: false`).
- Security: `api_key` (`x-apikey` header) and `jwt` (oauth2 with empty URLs and scopes).
- Shared CORS headers live in `#/components/headers`.

## Shared boilerplate

- **Errors:**
  - Default responses reference `ErrorResponse` `{code, message}`.
  - 400 `BadRequest` and 404 responses use the same `{code, message}` object, sometimes inline and duplicated for JSON and XML.
  - Neither field is required.
- **200 response headers:** `X-Application-Context`, plus `Access-Control-Allow-Origin` (`*`), `-Methods` and `-Headers`. These are hard-coded in the specs.
- **Contacts schemas:** The array "The Contacts Schema" and the `contact` object are empty shells, with no properties.
- **Stub schema refs:** `Cont`, `Inv`, `Site`, `Acc` and `Rcpt` have empty or truncated examples. The names look like abbreviations, but that is only a guess.

## Caution

- **Truncation:** Most fragments are cut off. This includes the entity and `contacts` schemas, the authorizations 200 bodies, the PUT response, `/orgs` POST and PUT, and the Notify spec after `POST /api/v1/notify/`. Verify the full definitions.
- **Typos and copy-paste errors:**
  - `defaut` for `default`.
  - `indentifier` for `identifier`.
  - `username` is described as "Corp Type".
  - `PATCH /users` returns a `contact` schema.
- **Permissions:**
  - User endpoints mix JWT self-access with admin-only access.
  - Internal-only entity endpoints.
  - The invite code has no documented scope or expiry.
  - An empty `security: []` array means no scopes are enforced.
- **CORS:** `Access-Control-Allow-Origin: *` is hard-coded in the specs. Moving it to middleware config or shared `#/components/headers` is recommended.
- **Validation:** The pattern `^(.*)$` and `''` defaults make required-looking fields accept empty strings. `minLength 1` allows whitespace. `uniqueItems` on objects is unreliable.
- **Schema mismatches:**
  - `/parties` and `/addresses` use singular schemas on plural endpoints.
  - `streetAdditional` is optional in one place and required in another.
  - The orgMembership enum omits STAFF.
  - `roles` items are untyped.
  - The 201 code is a string.
  - Request and response casing differs.
- **Examples:**
  - The example IDs (`'1234'`, `CP0000000`) and the 2019 timestamps are placeholders or stale.
  - Only one `status` value (`DELIVERED`) is documented.
  - Most examples are empty.
