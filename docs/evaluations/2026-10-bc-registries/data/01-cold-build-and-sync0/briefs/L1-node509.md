<!-- level 1, node 509, children [1, 3, 39, 62, 64, 133, 149, 158, 217, 219, 402, 553, 554] -->

# Parent brief: BC Registries API spec fragments and AJV internals

This batch condenses OpenAPI/Swagger fragments from BC Government registry services (Notify, Report, Auth/Accounts, Business Registry/LEAR). It also includes notes on AJV's validator internals. Nearly all fragments are truncated, empty or duplicated. Most are `$ref`s to schemas defined elsewhere, with stub or missing examples.

## 1. Error responses
- **`ErrorResponse`** (`#/components/schemas/ErrorResponse`) is `{code, message}`. It backs the default and 400 responses, often as a bare snippet with no endpoint context.
- **Inline error objects:** `BadRequest` (400) and 404 define the same `{code, message}` object inline. The 404 sometimes repeats it for JSON and XML. Neither field is required.
- **Truncated GET:** two 400 snippets come from a GET operation that is cut off.

## 2. Notify API v1.0.0 and Report API v1.0
- **Notify endpoints:**
  - `POST /Notification` (`Send_Notification`) returns 201.
  - `GET /api/v1/notify/{notification_id}` returns 200.
  - A GET by `status` (example `DELIVERED`) is cut off.
- **Notify schemas:** `NotificationRequest`, `NotificationResponse`, `ContentRequest`/`ContentResponse`, `AttachmentRequest`/`AttachmentResponse`, `NotificationStatus`, `NotificationType`, `HTTPValidationError` and `ValidationError`.
- **Notify security:** JWT bearer.
- **Report API:** `POST /reports` (`post_report`) creates a PDF.

## 3. Auth/Accounts API (orgs, users, entities, affiliations, authorizations)
- **Orgs, members and contacts:**
  - Org CRUD (`post_orgs`, `put_org`, `get_org`), status updates and search.
  - Member invite, request and confirm flows, plus `patch_org_member` and `delete_org_member`.
  - Org contacts under `/orgs/{org_id}/contacts`.
- **Users:** `POST/GET /users`, `get_user`, `delete_user`, `patch_user` (terms of use), `get_user_staff`, and `userSettings`.
- **Entities and affiliations:**
  - `/entities` (POST, PUT, `get_entity_resource`) and the business contact endpoints.
  - Affiliations (`post_org_affiliations`, `get_org_affiliations`, `delete_org_affiliation`).
  - Permissions vary by role: any basic user, org owner, admin or internal only.
- **Authorizations:**
  - Several GET variants: `/entities/{businessIdentifier}/authorizations`, `/users/authorizations`, `/authorizations`, `/orgs/{org_id}/authorizations` and account/product forms.
  - Test ids run CP0001234–CP0001239, with CP0000000 as the unauthorized case.
  - The `Authorization` schema has `orgMembership` (USER, COORDINATOR or ADMIN) and `roles`.
- **Request and entity schemas:**
  - `entityRequest`, `affiliationRequest`, `invitationRequest` and `orgRequest`.
  - The business entity (required: businessIdentifier, businessNumber, contacts, corpType, created, modified, modifiedBy, name, passCodeClaimed). Its example is CP0001578.
  - Contact and address objects.
- **Reference data:** `GET /codes`, with the `codes` schema `{code, desc, defaut}`, and the `document` schema.

## 4. Business Registry (LEAR) API
- **Business endpoints:** `get-business`, addresses (Office schema), parties (`party` schema), filings (Ledger) and the document download.
- **Filing documents:** the filing documents list, and download as PDF or JSON.
- **Search:** `get-businesses-search`, a public autocomplete.
- **Shared parts:**
  - Shared `$ref` CORS headers: Allow-Methods `GET, PUT, POST, PATCH`, plus Allow-Headers and Max-Age.
  - Security: `api_key` (`x-apikey`) and `jwt` (OAuth2 with no URLs or scopes).
  - Parameters: `Account-Id`, `identifier`, `filingId` and `documentName`.

## 5. Common response pattern
Success responses carry the same four string CORS headers: `X-Application-Context`, and `Access-Control-Allow-Origin`, `-Methods` and `-Headers`. Examples are `*`, `GET, OPTIONS` and `Content-Type, api_key, Authorization`. They are hardcoded in the spec rather than set in middleware.

## 6. Stub and empty schema fragments
- **Contacts:** an array schema ("The Contacts Schema") and an object `contact` with no properties or items.
- **Component stubs with empty examples:** `Cont`, `Inv` (keys adjs, inv_info1, 10021, invs, cms), `Site`, `Acc` and `Rcpt`.
- **Notification record:** `recipientEmail`, `sentDate`, `status` and `token`.

## 7. AJV internals (unrelated to the API specs)
- **Generated-code templates:** `properties`/`patternProperties`, `required`, `uniqueItems`, the top-level schema compiler, the rule dispatcher and type coercion.
- **Instance API:** `_addSchema`, `_compile`, `chooseGetId`, `addFormat`, `errorsText` and `setLogger`.

## Cross-cutting cautions
- **Truncation:** almost everything is incomplete (cut-off operations, missing response schemas, empty examples). Verify against the full spec before relying on any fragment.
- **Weak validation:** the pattern `^(.*)$` and `minLength: 1` constrain almost nothing. Defaults of `''` make fields effectively nullable.
- **Naming issues and typos:**
  - `defaut` should be `default`.
  - "indentifier" should be "identifier".
  - `businessIdentifier` and `businessNumber` look interchangeable but are distinct values.
  - `NotificationStatus` and `NotificationType` are identical but must stay separate.
  - The `/parties` endpoint uses the singular `party` schema, and `/addresses` uses the singular `Office`.
  - Notify requests use camelCase and responses use snake_case.
- **Security and CORS:**
  - Allow-Origin is `*` everywhere.
  - The empty `security: []` and the empty OAuth scopes mean access control must be enforced in the code.
  - Permissions differ by endpoint, so check roles carefully.
- **Placeholder examples:** examples such as '1234', the 2019 timestamps and the `{test: test}` response are placeholders.
- **AJV generated code:** don't edit it by hand. Coercion mutates the caller's data, and `uniqueItems` deep-equality depends on `equal()`.
