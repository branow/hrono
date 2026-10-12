# today (sample 1)

# auth-api (BC Registries Authorization API)

A Flask REST service for managing orgs, users, memberships, invitations, affiliations (org↔business links), affidavits, product subscriptions and staff-review tasks. It is made of four layers:

- **HTTP resources.** Versioned `/api/v1` blueprints.
- **Service layer.** Business logic, plus outbound calls to Keycloak, pay-api, legal-api/NAMEX, BCOL, MinIO, the API Gateway, LaunchDarkly and a GCP queue.
- **SQLAlchemy models.** Includes code tables and the `authorizations_view` DB view.
- **Schemas.** Marshmallow and JSON Schema.

## How the layers fit together

- **Request path:** Keycloak JWT → resource (`schema_utils.validate` against a draft-07 JSON Schema) → service class → model → Marshmallow schema → camelCased JSON (`camelize_json`).
- **Errors:** `Error` enum members (`exceptions/errors.py`) are raised as `BusinessException`. Every endpoint turns one into `{code, message}` at `status_code`. Schema failures return 400 with `{'message': errors}`.
- **Authorization:** Authorization is spread across several places:
  - `UserContext`
  - `role_validator`
  - `services/authorization.py` (the 403 decorator)
  - `utils/roles.py`
  - membership/org-status permissions (`services/permissions.py`, `Permissions` model)
  
  Each branches on STAFF, SYSTEM, API_GW or regular user.
- **Events:** The activity log (`ActivityLogPublisher`, read back via `services/activity_log.py`) and mailer events (`publish_to_mailer`) go out as CloudEvents on the GCP queue. The queue is exposed as the `queue` singleton in `services/gcp_queue`.
- **Audit:** `BaseModel` stamps created/modified fields from the JWT and writes activity records for versioned models.
- **Review workflow:** Org, product, affidavit and BCEID-admin flows create review tasks in PENDING_STAFF_REVIEW. `services/task.py::update_task` dispatches by relationship type (ORG / PRODUCT / USER).

## Cross-cutting conventions

- Payloads are camelCase and the DB is snake_case. Conversion happens at the service, model and schema boundaries.
- Soft deletion and computed status are used throughout. `Org.delete` sets INACTIVE, and a PENDING invitation reads as EXPIRED after its expiry date without any DB update.
- Code tables (`BaseCodeModel`, served generically by `services/codes.py`) supply defaults through `default=True` `.first()` lookups.
- Schemas drop `None` values and `versions` keys (`BaseSchema`). Public variants mask emails.
- Failures of side channels (mailer, cache build, Keycloak group changes, logging setup) are logged or swallowed rather than raised.

## Hazards that span the area

- **Non-atomic flows.** Many multi-step flows have no transaction: org API access, affidavit approval, anonymous-user deletion, and the sole-admin check in `update_membership`, which can race. Side-channel failures leave partial state with no error.
- **Silent failures.**
  - `.first()` lookups return None.
  - Hardcoded default `1` for membership and user status codes.
  - `fetch_codes` collapses every failure to `UNDEFINED_ERROR`.
  - `BaseModel._get_current_user` has a bare except, so audit ids can be null.
  - `ValidatorResponse` can't be reset.
- **Known code bugs:**
  - `ServiceUnavailableException.status_code` is the enum name string, not the number.
  - `user.py` has malformed dicts on error paths.
  - `role_validator` with only `not_allowed_roles` rejects every request.
  - `Entity.validate_pass_code` compares plaintext to a hash.
  - The activity-log postal-code key is `postal_code` where the data is `postalCode`.
  - `_removing_products_and_services` is unmapped.
- **Weak JSON Schemas.** Many fields use the catch-all `^(.*)$`. Several files are malformed, with nested duplicate keys where `items` should be, misplaced properties, and defaults that contradict their types. `validate()` raises on an unknown schema id. The password regex allows only `!@#$%^&*` as special characters. The API gateway sanitizer silently strips and truncates, so different inputs can collapse to the same value.
- **Config.** `config.py` hardcodes RSA test keys. `ProdConfig` regenerates `SECRET_KEY` on each start if it is unset. Test-only endpoints (`/test`, `reset_bp`) mount only when `FLASK_ENV` is development or testing.

## Where to start

| Need | Open |
|---|---|
| Blueprint registration | `resources/endpoints.py`, `resources/v1/__init__.py` |
| Org, user endpoints | `resources/v1/org.py`, `resources/v1/user.py` |
| Authorization | `services/authorization.py`, `utils/role_validator.py`, `utils/user_context.py` |
| Org, affiliation, membership, invitation, task, product workflows | `services/org.py`, `affiliation.py`, `membership.py`, `invitation.py`, `task.py`, `products.py` |
| Outbound integrations | `services/api_gateway.py`, `keycloak.py`, `rest_service.py` |
| Errors | `exceptions/errors.py`, `exceptions/__init__.py` |
| Models and audit | `models/base_model.py`, `org.py`, `invitation.py`, `views/authorization.py` |
| Code tables | `services/codes.py`, `models/permissions.py` |
| Serialization | `schemas/base_schema.py`, `schemas/org.py` |
| JSON Schema loading | `schemas/utils.py`, `schemas/schemas/*.json` |
| Activity log | `services/activity_log.py` |
| DTOs and enums | `models/dataclass.py`, `utils/enums.py` |
| App factory | `__init__.py` |

# today (sample 2)

# auth-api (BC Registries Authorization API)

Flask REST service that manages orgs, users, memberships, invitations, affiliations (org↔business links), affidavits, product subscriptions and staff-review tasks. It is organized in layers: HTTP resources (`/api/v1`) → service classes → SQLAlchemy models, with JSON Schema validation on input and Marshmallow schemas on output. Outbound calls go to Keycloak, pay-api, legal-api/NAMEX, BCOL, MinIO, the API Gateway and LaunchDarkly. Events go to a GCP queue (account-mailer and activity log).

## How the layers fit together
- **Request path:** a Keycloak JWT is authenticated (`auth.py`, `UserContext`, `@user_context`). The body is validated with `schema_utils.validate` against draft-07 JSON Schemas. The resource calls a service. The service uses models and Keycloak. It dumps results through `BaseSchema` subclasses, and `camelize_json` camelCases the response.
- **Errors:** services raise `BusinessException(Error.X)`, where `Error` is the enum of message and HTTP status. Each endpoint turns it into `{code, message}` at `status_code`. Schema failures return 400. `ValidatorResponse` collects validation errors instead of raising.
- **Events:** `publish_to_mailer` and `ActivityLogPublisher` send CloudEvents through the singleton `GcpQueue`. Models also write activity records (sqlalchemy_continuum), which `services/activity_log.py` reads back.
- **Roles and permissions:** roles come from `realm_access.roles` (`utils/roles.py`). `services/authorization.py`, `permissions.py` and `role_validator` apply them. The reference code tables (`services/codes.py`) feed defaults and lookups.

## Cross-cutting conventions
- **Soft deletes and computed state:** `Org.delete` sets INACTIVE, finders skip INACTIVE and REJECTED, and invitation expiry is computed on read.
- **Review workflow:** a risky org, product or user change becomes PENDING_STAFF_REVIEW plus a Task. `services/task.py::update_task` dispatches by relationship type (ORG, PRODUCT, USER) and then syncs Keycloak groups.
- **Emails:** masked through `mask_email` for public schemas. Staff actor names are replaced for non-staff viewers.
- **Hidden fields:** `BaseSchema` drops None values and `versions` everywhere.

## Hazards that recur
- **Swallowed failures:** these only log or are silently ignored: `publish_to_mailer`, `add_or_remove_users_from_group`, `build_cache`, `setup_logging`, bare `except` blocks, and the `fetch_codes` fallbacks. Several flows are non-atomic: affidavit approval, entity plus affiliation saves, the sole-admin check, and `ApiGateway.has_api_access`.
- **Schemas that look strict but aren't:**
  - The `^(.*)$` pattern accepts anything.
  - Several schemas are malformed (duplicate nested keys, wrong defaults, a trailing comma).
  - `validate()` raises on an unknown `schema_id`.
  - The password special characters are limited to `!@#$%^&*`.
  - The gateway sanitizer truncates and drops characters.
- **Known bugs:**
  - `ServiceUnavailableException.status_code` is a string name.
  - Malformed dicts in `user.py` error paths raise TypeError.
  - `role_validator` with only `not_allowed_roles` rejects every request.
  - `Entity.validate_pass_code` compares plain text with a hash.
  - The activity-log postal code key is wrong (`postal_code` vs `postalCode`).
  - `_removing_products_and_services` is not mapped.
  - `Membership.reset` commits twice.
  - Query-string flags arrive as strings and are always truthy.
- **Hardcoded defaults:** the membership and user status defaults are the integer `1`, and `.first()` lookups return None silently.
- **Config:** test RSA keys are hardcoded, and `ProdConfig` regenerates `SECRET_KEY` on each start if unset.

## Open first
- `resources/v1/org.py` and `user.py`, with `resources/endpoints.py`: endpoints and blueprint mounting.
- `services/org.py`, `affiliation.py`, `task.py`, `products.py`, `membership.py`, `invitation.py`: business workflows.
- `services/authorization.py` and `utils/role_validator.py`: access control.
- `services/api_gateway.py`, `keycloak.py`, `rest_service.py`: outbound integrations.
- `models/base_model.py`, `org.py`, `invitation.py`, `views/authorization.py`: persistence.
- `schemas/base_schema.py`, `schemas/utils.py` and `schemas/schemas/*.json`: serialization and validation.
- `exceptions/errors.py` and `exceptions/__init__.py`: the error catalogue.
- `services/activity_log.py`: activity-log authorization and formatters.

# area-core (sample 1)

# auth-api (BC Registries Authorization API)

A Flask REST service that manages orgs, users, memberships, invitations, affiliations, affidavits, product subscriptions and staff-review tasks. It takes JWT-authenticated HTTP requests and Pub/Sub pushes. It hands work to the database (SQLAlchemy), Keycloak, legal-api, NAMEX, pay-api, BCOL, notify-api, the API Gateway, MinIO and LaunchDarkly. It publishes activity-log and mailer events to GCP queues.

## Parts
- **HTTP layer, authorization helpers and supporting services**: versioned `/api/v1` endpoints, JWT roles, `UserContext`, `role_validator`, and the authorization decorator.
- **auth-api service layer (BC Registries auth-api)**: business workflows for org, affiliation, invitation, membership, task, product, affidavit and user.
- **auth-api service layer (Flask)**: app factory, Keycloak, REST client, API Gateway, flags, MinIO, `ActivityLogPublisher`, and DTO dataclasses.
- **Auth API data models (SQLAlchemy persistence layer)**: models, audit columns, activity records, search helpers and the authorizations view.
- **Auth API: code tables and code lookup service**: read-only reference tables, `Codes.fetch_codes`, and default lookups.
- **Serialization schemas, activity-log and task services**: Marshmallow schemas that turn models into API JSON, plus the activity-log and task-search services.
- **JSON Schema layer for the BC Registries auth API**: draft-07 schemas with `schemas/utils.py` `validate`.
- **Validation schemas, feature flags and gateway string sanitizer**: user, bulk-user, api-key, contact and entity request schemas, `flags.json`, and the gateway string sanitizer.
- **auth-api: shared support code**: the `Error` enum, `BusinessException`, `ValidatorResponse`, contact and documents services, tracing and logging.

## How the parts work together
**Request flow**
1. A resource in the HTTP layer authenticates the JWT and calls `schema_utils.validate(json, schema_id)` (JSON Schema layer, plus the request schemas in the validation part).
2. It calls a service class in the service layer, for example `OrgService.create_org`.
3. The service uses the data models (`save`, finders) and the code tables for defaults.
4. It calls out to Keycloak, pay-api and similar through `RestService` and `KeycloakService`.
5. It publishes mail with `publish_to_mailer` and activity events with `ActivityLogPublisher`.
6. The result is dumped through the schemas (`BaseSchema`, `OrgSchema`) and camelCased by `camelize_json`.
7. A `BusinessException` is caught by the endpoint and returned as `{code, message}` at `status_code`.

**Review-task flow**
1. A service creates a review task when an org, product or BCeID admin needs staff review.
2. A staff `PUT` on a task calls `TaskService.update_task`. This dispatches by relationship type: ORG → `OrgService.approve_or_reject`, PRODUCT → `update_product_subscription`, USER → `approve_or_reject_bceid_admin`.
3. For a PRODUCT task, the resource then calls `ProductService.update_org_product_keycloak_groups`.

**Org state:** `OrgService.create_org` sets PENDING_STAFF_REVIEW or PENDING_INVITE_ACCEPT. `approve_or_reject` moves it to ACTIVE or REJECTED. `patch_org` moves it to SUSPENDED. `delete_org`, via `Org.delete`, moves it to INACTIVE.

**Invitation status:** `Invitation.status` and `AffiliationInvitation.status` in the models are computed. Services move them to ACCEPTED or FAILED. Pending ones read as EXPIRED once past expiry.

**Activity log:**
- Write path: `BaseModel.save` writes activity records, and services publish events through `ActivityLogPublisher`.
- Read path: `fetch_activity_logs` formats entries.

## Shared rules
- Errors are `BusinessException(Error.X)`, with the message and HTTP code in `errors.py`.
- Roles (ADMIN, COORDINATOR, USER, STAFF, SYSTEM) come from the JWT. Permission checks use `get_permissions_for_membership`.
- Request JSON is camelCase, models use snake_case, and responses are camelCased again.
- Dumped schemas drop `None` values and `versions`.

## Hazards
- Many multi-step flows are non-atomic and swallow failures. Examples: `ApiGateway` sets `has_api_access` before the key exists. `add_or_remove_users_from_group` only logs failures. `publish_to_mailer` logs only. `Affidavit.approve_or_reject` never saves.
- `ServiceUnavailableException.status_code` is a string name, and `role_validator` with only `not_allowed_roles` rejects everything. Handlers that assume numeric codes or sane role rules misbehave.
- Schemas often look strict but are not: the `^(.*)$` pattern accepts anything, and malformed nested keys mean some `$ref`s are ignored. `validate()` raises on an unknown `schema_id`. Code-table `.first()` lookups return None silently, and the hardcoded default `1` is never checked against the table.

# area-core (sample 2)

# auth-api (BC Registries Auth API)

Flask REST service that manages accounts, orgs, users, memberships, invitations, affiliations, products, tasks and documents. It takes Keycloak-JWT HTTP requests and GCP Pub/Sub pushes. It hands work to the database (SQLAlchemy), Keycloak, legal-api, NAMEX, pay-api, BCOL, notify-api, MinIO, LaunchDarkly, the API Gateway and a GCP queue (account-mailer and activity-log events).

## Parts
- **auth-api: HTTP layer, authorization helpers and supporting services**: the `/api/v1` endpoints, JWT/role checks, the 403/401 decorators, permissions and Keycloak resource handlers.
- **auth-api service layer (BC Registries auth-api)**: business logic for orgs, memberships, invitations, affiliations, affidavits, products, users and review tasks.
- **auth-api service layer (BC Registries Auth API, Flask)**: the app factory, Keycloak/REST/MinIO/API Gateway clients, flags, the activity-log publisher and the DTOs and enums.
- **Auth API data models (SQLAlchemy persistence layer)**: persistence, audit columns, activity records and the authorizations view.
- **Auth API: code tables and code lookup service**: reference tables and `Codes.fetch_codes`.
- **Serialization schemas, activity-log and task services (auth-api)**: model-to-JSON Marshmallow schemas, the activity-log and task-search services, and the cattrs converter.
- **JSON Schema layer for the BC Registries auth API**: draft-07 request/response schemas and `schemas/utils.py` (`validate`).
- **auth-api: validation schemas, feature flags and gateway string sanitizer**: more request schemas (anonymous/bulk user, api key, contact, entity), `flags.json` and the gateway sanitizer.
- **auth-api: shared support code (errors, tracing, logging, small services)**: the `Error` enum, `BusinessException`, `ValidatorResponse`, tracing and logging setup, and small services (contact, documents).

## How the parts work together
**Request flow.**
1. A resource in the HTTP layer authenticates the JWT and checks the role (`role_validator`, `UserContext`, `services/authorization.py`).
2. It validates the body with `schema_utils.validate` against the JSON Schema layer (and the validation schemas part). A failure returns 400.
3. It calls a service class in the business service layer (for example `OrgService`, or `TaskService.update_task`).
4. The service uses the models (`save`, finders, `create_from_dict`) and reads codes through the code tables part.
5. The service calls out via `RestService`, `KeycloakService`, `ApiGateway` or `MinioService`.
6. The result is dumped by the serialization schemas and camelCased by `camelize_json`.
7. Any `BusinessException(Error.X)` is caught by the endpoint and returned as `{code, message}` at `status_code`.

**Activity-log flow.**
1. Services call `ActivityLogPublisher` to publish a CloudEvent to `AUTH_EVENT_TOPIC`.
2. Models using `VersionedModel` also write activity records through `BaseModel.save`.
3. `fetch_activity_logs()` reads the entries back and formats them through `_build_string()`.

**Review-task flow.**
1. A service (org, product or affidavit creation) creates a review task and sets PENDING_STAFF_REVIEW.
2. `PUT` on a task calls `TaskService.update_task`. It dispatches by relationship type: ORG → `OrgService.approve_or_reject`, PRODUCT → `update_product_subscription`, USER → `approve_or_reject_bceid_admin`.
3. For a PRODUCT task, the resource then calls `ProductService.update_org_product_keycloak_groups`.
4. Task search goes through `fetch_tasks` and the task-search service.

**Org status.** The org service sets ACTIVE or REJECTED through `approve_or_reject`, SUSPENDED through `patch_org`, and INACTIVE through `Org.delete()`. The model only blocks type-code changes.

**Invitation status.** The invitation and affiliation-invitation services set it to accepted, failed or retried. The model reports PENDING as EXPIRED once past expiry, with no DB write.

## Shared rules
- Errors use the `Error` enum wrapped in `BusinessException`.
- Roles and statuses come from `utils/roles.py` and `utils/enums.py`.
- Emails go through `publish_to_mailer`.
- Staff identity is masked for non-staff in activity logs.

## Hazards
- Many multi-step flows are non-atomic and swallow failures. Examples: `publish_to_mailer` only logs, `add_or_remove_users_from_group` only logs, `Affidavit.approve_or_reject*` never saves, and `ApiGateway` sets `has_api_access` early. Work can be left half-done.
- Callers assume things the parts do not guarantee. `validate()` raises on an unknown `schema_id`. `ServiceUnavailableException.status_code` is a string, not a number. Many JSON schemas accept anything through the `^(.*)$` pattern. `.first()` default lookups return None silently.
- The activity-log formatter skips postal code (key mismatch) and an unmapped action. `BaseModel._get_current_user` can store null audit ids.

# area-flows (sample 1)

# auth-api (BC Registries Auth API)

A Flask REST service that manages orgs, users, memberships, invitations, affiliations, affidavits, products and staff-review tasks. It takes Keycloak-JWT HTTP requests and Pub/Sub pushes. It hands work to SQLAlchemy models and to Keycloak, legal-api, NAMEX, pay-api, BCOL, notify-api, MinIO, the API Gateway and LaunchDarkly. It publishes activity-log and mailer events to GCP queues.

## Flows

**Any request**
1. The endpoint modules in "auth-api: HTTP layer, authorization helpers and supporting services" authenticate the JWT (`auth.py`). `UserContext` reads roles and account id, and `role_validator` or the `services/authorization.py` decorator returns 401 or 403.
2. `schema_utils.validate` checks the body against the "JSON Schema layer for the BC Registries auth API" (`utils.py::validate`). Failures return 400.
3. The endpoint calls a service class from "auth-api service layer". `BusinessException` becomes `{code, message}` at the error's status code, using the "auth-api: shared support code" `Error` enum.
4. The service reads or writes "Auth API data models". `BaseModel.save` fills the audit columns and, for versioned models, writes activity records.
5. The response is dumped through the "Serialization schemas, activity-log and task services" and camelized.

**Org creation and review**
1. POST org: `OrgService` runs the chained validators and creates the org.
2. GOVM orgs become PENDING_INVITE_ACCEPT. GOVN orgs, and BCEID or EXTRA_PROVINCIAL orgs without an approved affidavit, become PENDING_STAFF_REVIEW and get a review task.
3. Staff `PUT` on the task calls `TaskService.update_task`. ORG tasks go to `OrgService.approve_or_reject`, which sets ACTIVE or REJECTED, calls `AffidavitService.approve_or_reject` and mails admins through `publish_to_mailer`.
4. PRODUCT tasks go to `update_product_subscription`. The resource then calls `ProductService.update_org_product_keycloak_groups`.
5. USER tasks go to `approve_or_reject_bceid_admin`.

**Team invitation and membership**
1. `InvitationService` (ADMIN, COORDINATOR or STAFF) creates the invitation. Its status is computed, and a PENDING invitation reads as EXPIRED after its expiry.
2. `accept_invitation` creates the membership. `_get_status_based_on_org` sets ACTIVE, PENDING_STAFF_REVIEW or PENDING_APPROVAL.
3. PATCH on the org member calls `update_membership`, which syncs Keycloak groups. It sends MEMBERSHIP_APPROVED when the status becomes ACTIVE.

**Business affiliation**
1. `AffiliationService.create_new_business_affiliation` validates the name request (NR) or passcode.
2. The affiliation invitation flow (`_validate_prerequisites`) is accepted or refused through `_verify_permissions`. Accept creates the affiliation. Refuse sets FAILED.
3. `get_affiliation_details` merges NAMEX and LEAR data.

**API key**
1. `ApiGateway.create_key` provisions a Keycloak client and group membership, then POSTs the consumer or `/apikeys`. Sandbox also creates a payment account.

**Code lookup**
1. `Codes.fetch_codes` in "Auth API: code tables and code lookup service" serializes the matching code table.

**Activity log and tasks**
1. `fetch_activity_logs()` (ADMIN or STAFF only) formats the entries. The task search calls `TaskModel.fetch_tasks`.

## Other parts

- **auth-api: validation schemas, feature flags and gateway string sanitizer**: request schemas for anonymous and bulk users, API keys, contacts and entities, `flags.json`, and the gateway string sanitizer.
- **`ActivityLogPublisher`** (in the service layer): publishes CloudEvents of activity.
- **`ValidatorResponse`, `Tracer`, `setup_logging`, `GcpQueue`**: error collection, tracing, logging and the queue singleton, all in the shared support code.

## Hazards

- Many steps are non-atomic and swallow failures. `ApiGateway` sets `has_api_access` before the key exists. `publish_to_mailer` and the Keycloak group changes only log failures. The sole-admin check in `update_membership` can race.
- `ServiceUnavailableException.status_code` is a string, not an HTTP code. `user.py` error dicts are malformed and raise TypeError. Handlers that rely on these get wrong or crashing error responses.
- Validation is weaker than it looks. Most JSON schemas use `^(.*)$`, and several nest duplicate keys where `items` belongs. `validate()` raises on an unknown schema id.

# area-flows (sample 2)

# auth-api (BC Registries Auth API)

A Flask REST service that manages orgs, users, memberships, invitations, affiliations, affidavits, products and staff-review tasks. It takes Keycloak-JWT HTTP requests and Pub/Sub pushes. It hands work to Keycloak, legal-api, NAMEX, pay-api, BCOL, notify-api, MinIO, the API Gateway, LaunchDarkly, and the GCP queue (account-mailer and activity-log events).

## Flows

**1. Create an org**
1. A request reaches the **HTTP layer** (`resources/v1/org.py`). It checks the JWT and validates the body with `schema_utils.validate`, using the **JSON Schema layer** (`org.json`, `payment_info.json`).
2. The **service layer** (`services/org.py`) runs chained validators: BCOL credentials, account limit, `access_type`, duplicate name.
3. The org is created. GOVM becomes PREMIUM with PENDING_INVITE_ACCEPT. GOVN, or BCEID/EXTRA_PROVINCIAL without an approved affidavit, goes to PENDING_STAFF_REVIEW and a review task is created.
4. The **data models** persist it, and `BaseModel` writes audit columns and activity records. `ActivityLogPublisher` publishes the event, and `publish_to_mailer` sends mail.
5. Schemas serialize the response.

**2. Staff approve or reject (task)**
1. PUT in `resources/v1/task.py` calls `services/task.py::update_task`, which dispatches by relationship type.
2. ORG goes to `OrgService.approve_or_reject`, which sets ACTIVE or REJECTED and notifies admins. For AFFIDAVIT_REVIEW it also calls `AffidavitService.approve_or_reject`.
3. PRODUCT goes to `update_product_subscription`. The resource then calls `ProductService.update_org_product_keycloak_groups`.
4. USER goes to `approve_or_reject_bceid_admin`. An approved affidavit sets `user.verified`.

**3. Invite a member and accept**
1. `resources/v1/invitation.py` calls `services/invitation.py`. It needs ADMIN, COORDINATOR or STAFF.
2. `_get_status_based_on_org` sets the status. For PENDING_STAFF_REVIEW, `_create_affidavit_review_task` creates a task.
3. `accept_invitation` creates the membership. `services/membership.py` enforces role rules and syncs Keycloak groups.
4. `patch_organization_member` in the resource sends MEMBERSHIP_APPROVED when the status becomes ACTIVE.

**4. Affiliate a business**
1. `services/affiliation.py::is_authorized` checks the passcode or party name.
2. `create_new_business_affiliation` validates the NR and saves the affiliation. `get_affiliation_details` merges NAMEX and LEAR data.
3. Affiliation invitations are handled by a separate service. `accept` creates the affiliation and `refuse` sets FAILED.

**5. API key issue**
1. `ApiGateway.create_key` checks whether the consumer exists.
2. A new consumer gets a Keycloak client, group membership, and in sandbox a pay account. It is then POSTed to the gateway. An existing consumer gets a POST to `/apikeys`.
3. `revoke_key` and `get_api_keys` require ADMIN or STAFF.

**6. Reference-data lookup**
`Codes.fetch_codes(table)` finds the code model, reads all rows, and serializes each with the table's schema, falling back to `BaseCodeSchema`.

**7. Activity log read**
`fetch_activity_logs()` requires ADMIN or STAFF. It formats entries via `_build_string()` and masks staff actor names for non-staff viewers.

## Other parts
- **Authorization helpers** (`services/authorization.py`, `utils/role_validator.py`, `UserContext`, `permissions.py`): role and membership checks the endpoints share.
- **Shared support code**: `Error` enum, `BusinessException`, `ValidatorResponse`, `Tracer`, and logging setup.
- **Serialization schemas** (Marshmallow, cattrs): convert models to camelCase API JSON.
- **Validation schemas and gateway sanitizer**: `bulk_user.json`, `anonymous_user.json`, `flags.json`, and `api_gateway.py`'s string sanitizer.
- **Code tables**: reference models plus `UserSettings`.
- **`RestService`, `KeycloakService`, `Flags`, `MinioService`**: outbound clients.

## Hazards
- **Non-atomic multi-step flows.** The affidavit, entity, affiliation and membership saves are separate. `ApiGateway` sets `has_api_access` before the later steps finish. Keycloak group changes only log failures. Mailer failures are swallowed. Partial failures leave inconsistent state with no error raised.
- **Error-path bugs.** `ServiceUnavailableException.status_code` is a string name, not a number. Malformed dicts in `resources/v1/user.py` raise TypeError on error paths. `Entity.validate_pass_code` compares plain text with a hash.
- **Weak validation and silent defaults.** Many JSON schemas use `^(.*)$` or have broken structure, so they accept nearly anything. `validate()` raises on an unknown schema id. `.first()` code lookups return None silently. The hardcoded default `1` for membership and user status is never checked against the table.
