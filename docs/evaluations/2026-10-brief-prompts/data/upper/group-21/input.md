=== Serialization schemas, activity-log and task services (auth-api) ===

# Serialization schemas, activity-log and task services (auth-api)

Converts auth-api database models into API JSON (Marshmallow schemas, one attrs schema, one JSON-schema pair for validation). It also holds two small services, activity log and task search, and a cattrs converter. It takes model instances from the services and resources and hands back dicts. It writes nothing itself.

## Contract
- Schemas take model instances (Org, Entity, Membership, User, Invitation, Affiliation and similar) and return dicts. Nested schemas rename or prune fields, for example Org→`mailing_address`, Affiliation→`business`/`organization`, and codes→`desc`/`name`.
- `schemas/schemas/invitation.json` validates incoming invitations: `recipientEmail` and `membership[]` are required, and each item needs `membershipType` and `orgId`. `affiliation_invitation_response.json` describes the response shape.
- `services/task.py` takes a `TaskSearch` and returns `{tasks, total, page, limit}`. It calls `TaskModel.fetch_tasks` and serializes each task with `as_dict(exclude=['user'])`.
- `services/activity_log.py` takes an org id, pagination and optional `item_name`/`item_type`/`action` filters. It returns a paginated dict of formatted log entries.

## Decisions
- `BaseSchema` post_dump (`_remove_empty`): drops all `None` values and every `versions` key, even if requested. `created_by`/`modified_by` are rendered as "first last".
- `BaseSchema.__init__`: if no `fields` are given, `versions` is added to the exclude list so version tables are not queried.
- `OrgSchema` post_dump (single object only): adds `businessName` when `is_business_account` is true. It reduces the `mailing_address` list to its first element.
- `ContactSchemaPublic` and `AffiliationInvitationSchemaPublic` call `mask_email()` in post_dump to hide emails.
- `UserSettings._remove_empty`: drops falsy values except floats.
- `UserSchema.get_user_terms_object`: builds `isTermsOfUseAccepted` and `termsOfUseAcceptedVersion`.
- `ActivityLogSchema` hides `id` and `remote_addr`.
- `fetch_activity_logs()` in the activity-log service:
  - It refuses callers who are not ADMIN or STAFF.
  - Non-staff viewers see "BC Registry Staff" in place of staff actor names.
  - `_build_string()` maps each action code to a formatter function. The formatters build the description from `item_name` and `item_value`.
- `converter.py` (cattrs): Decimal→float (None→0), datetime→ISO string, and `remove_nones` strips Nones recursively.
- `SimpleOrgInfoSchema.from_row()` maps `status_code` to `status`.

## Hazards
- `_account_address_changes()` checks the key `postal_code`, but the stored keys are camelCase (`postalCode`). Postal code never appears in address-change descriptions.
- `_removing_products_and_services()` is defined but not mapped in `_build_string()`. That action is not formatted.
- `BaseSchema` crashes if a `created_by` or `modified_by` object has no `firstname`/`lastname`. UserSettings' falsy filter silently removes integer 0 and False.

## Open first
- `schemas/base_schema.py`: shared dump behaviour for nearly all schemas.
- `services/activity_log.py`: authorization, actor masking and action formatters.
- `schemas/org.py`: the most heavily remapped schema, with the `mailing_address` handling and extra post_dump logic.
- `services/task.py`: task search and pagination output.

The remaining schema files are thin model-to-JSON mappings. `extensions/__init__.py` only exports `mail`.

=== auth-api: shared support code (errors, tracing, logging, small services) ===

# auth-api: shared support code (errors, tracing, logging, small services)

A grab-bag of support modules in auth-api, not one cohesive unit. Business logic lives elsewhere. The notes for `models/org.py`, `services/affiliation.py`, `membership.py`, `task.py` and `user.py` contain only class stubs, so their behaviour is not documented here.

## Errors (`exceptions/`)
- `errors.py`: the `Error` enum. Each member carries a `message` and an HTTP `status_code` (400, 401, 403, 404, 406, 409, 500, 503), attached in `__new__`. Members cover input validation, auth, invitations, orgs, Keycloak, name requests and payments.
- `__init__.py`:
  - `BusinessException(error, exception)` takes `message`, `code` (`error.name`) and `status_code` from the Error. It keeps the original exception as `detail` and traces it via `ExceptionTracing.trace()`.
  - `ServiceUnavailableException` is for third-party failures.
  - `CustomException` is a plain object, not an Exception subclass. It carries message, status_code and an optional name.

## Validation
- `services/validators/validator_response.py`: `ValidatorResponse` collects errors instead of raising.
  - `add_error(Error)` appends the error and sets `is_valid=False`.
  - `add_info(dict)` merges metadata.

## Small services
- `services/contact.py`: `Contact.as_dict()` serialises with `ContactSchemaPublic` when `masked_email_only=True`, otherwise `ContactSchema`. None fields are dropped.
- `services/documents.py`:
  - `fetch_latest_document(document_type)` returns a `Documents` wrapper, or None.
  - `find_latest_version_by_type(document_type)` delegates to `DocumentsModel`.
  - `as_dict()` serialises via `DocumentSchema`.
- `services/gcp_queue/__init__.py`: exports the singleton `GcpQueue` instance as `queue`. Other services import it to publish.

## Infrastructure
- `tracer.py`: `Tracer.get_instance()` is a singleton around `ApiTracing(ApiTracer().tracer)`. Direct re-instantiation raises.
- `utils/custom_sql.py`: `CustomSql(name, sql)` is a data holder for custom SQL objects (views, functions).
- `utils/util_logging.py` and `logging.conf`:
  - `setup_logging(conf)` applies `logging.config.fileConfig` if the file exists.
  - The conf routes root and `api` at DEBUG to stdout, and `jaeger_tracing` at ERROR.

## Decisions
- `ValidatorResponse.is_valid` flips to False on the first `add_error` and is never reset. There is no clear method, so the object cannot be reused.
- `Contact.as_dict`: `masked_email_only` selects the public schema.
- `setup_logging`: a missing conf file prints to stderr and configures nothing.

## Hazards
- `ServiceUnavailableException.status_code` is set to `Error.SERVICE_UNAVAILABLE.name`, which is a string name, not the numeric status. Handlers that read it as an HTTP code get the wrong value.
- If the logging conf file is missing or invalid, the service runs with no logging and only a stderr message. The function's own TODO says it needs rework.
- `ValidatorResponse` cannot be reset, so a reused instance reports stale errors.

## Open first
1. `exceptions/errors.py`: the full error catalogue, with messages and status codes.
2. `exceptions/__init__.py`: how errors become exceptions, including the status_code bug.
3. `services/validators/validator_response.py`: the validation-result contract.
4. `utils/util_logging.py`, with `logging.conf`: logging setup.

=== auth-api: HTTP layer, authorization helpers and supporting services ===

# auth-api: HTTP layer, authorization helpers and supporting services

Flask REST service (auth-api) that exposes versioned `/api/v1` endpoints for accounts, orgs, users, invitations, products, tasks, documents and related resources. Each endpoint authenticates the JWT, validates the body, then delegates to a service class (OrgService, UserService, KeycloakService, ProductService and others). It also holds the role and authorization helpers those endpoints share.

## Contract
- **In:** HTTP requests with a Keycloak-issued JWT (`flask_jwt_oidc` `jwt` in `auth.py`), JSON bodies checked against named schemas via `schema_utils.validate`, and Pub/Sub pushes verified by `gcp_auth.py`.
- **Out:** JSON plus HTTP status. Every endpoint catches `BusinessException` and returns `{code, message}` at `exception.status_code`. Schema failures return 400 with `{'message': errors}`.
- **Mounting:** `resources/endpoints.py::_mount_endpoints` always loads `V1Endpoint` (`resources/v1/__init__.py`, which registers 23 blueprints). It adds the `/test` blueprint and `reset_bp` only when `FLASK_ENV` is `development` or `testing`.
- **Ops:** `/ops/healthz` runs `select 1`; `/ops/readyz` always returns 200.
- **Other:** `manage.py` runs migrations and lists routes. `config.py` holds `TestConfig` and `ProdConfig`.

## Decisions
- `utils/role_validator.py`: a decorator that returns 401 if the user lacks allowed roles or has a disallowed role.
- `utils/user_context.py::UserContext`: reads roles, login source and account id from the token (account id falls back to the `Account-Id` header). Offers `is_staff`, `is_staff_admin`, `is_system` and `is_bceid_user`.
- `services/authorization.py`:
  - `get_account_authorizations_for_org` and `get_user_authorizations_for_entity` branch on STAFF, SYSTEM+product_code, API_GW (account_id_claim) or regular user (keycloak_guid).
  - `_is_product_based_auth` is true for PARTNER product types.
  - The authorization decorator aborts with 403 for unauthorized staff, system or regular users, and `_check_for_roles` does the role check.
- `services/validators/access_type.py`: non-staff may not create ANONYMOUS or GOVM orgs. BCEID users get EXTRA_PROVINCIAL, REGULAR_BCEID or GOVN only. Missing values default to EXTRA_PROVINCIAL (BCEID) or REGULAR (other non-staff).
- `services/permissions.py::get_permissions_for_membership`: normalizes org_status to None unless it is NSF_SUSPENDED, PENDING_STAFF_REVIEW or SUSPENDED. It reads the cache and falls back to the DB. `build_all_permission_cache` fills the cache.
- `services/keycloak.py`: `join_users_group` picks the group by login source. `add_user` honours `return_if_exists` and `throw_error_if_exists`. `join_account_holders_group` and `remove_from_account_holders_group` change membership only when the role is absent or present respectively.
- `resources/v1/org.py`:
  - PATCH `/orgs/<id>` takes an action defaulting to UPDATE_STATUS.
  - DELETE `/orgs/<id>` only inactivates the org.
  - A PUBLIC_USER search without staff, system or identity roles returns an empty 200.
  - Updating an ANONYMOUS org requires STAFF_CREATE_ACCOUNTS.
- Org members:
  - `patch_organization_member` sends MEMBERSHIP_APPROVED when the status becomes ACTIVE.
  - It sends ROLE_CHANGED only when `notify_user` is true, the role is not USER and it is not the caller's own membership.
- Invitations:
  - `affiliation_invitation.py::_verify_permissions` lets an admin or coordinator of the target org accept or refuse; any other action returns 400.
  - `invitation.py` returns 401 on accept without a user.
- `user.py`:
  - POST `/bcros` creates the anonymous user, then accepts the invitation only if the creation returned 201.
  - DELETE and PATCH `/users/<username>` are allowed only for ANONYMOUS_USER; otherwise 501.
  - OTP reset is allowed only for BCeID users.
- `task.py` PUT: after `update_task`, a PRODUCT task triggers `ProductService.update_org_product_keycloak_groups`.
- `bulk_user.py`: any user with `http_status` other than 201 makes the response 207.
- `documents.py`: the token chooses the terms-of-use type (ANONYMOUS access type → director search; STAFF login source → GOVM). `_replace_current_date` fills in the date for PAD terms.
- `simple_org.py`: search with an optional status include or exclude filter, used by EFT linking.

## Hazards
- `user.py` has malformed dicts (missing colons) in `delete_user_otp`, `delete_by_username` and `patch_by_username`. They raise TypeError on those error paths.
- `role_validator` with only `not_allowed_roles` rejects every request. `_check_for_roles` lets the last constraint win.
- `keycloak.py` (resource) calls the service even when `role` is None, so the 400 is overwritten. `patch_organization_member` dereferences the membership before the None check. `/orgs/<id>/activity` style `expanded` query flags arrive as strings, so any value is truthy. `config.py` hardcodes RSA test keys, and `ProdConfig` regenerates `SECRET_KEY` on each start if unset.

## Open first
- `resources/v1/org.py`: org, member, affiliation and contact endpoints.
- `resources/v1/user.py`: user lifecycle, memberships and affidavits.
- `services/authorization.py`: authorization lookup and the 403 decorator.
- `resources/v1/__init__.py` and `endpoints.py`: blueprint registration.

=== JSON Schema layer for the BC Registries auth API ===

# JSON Schema layer for the BC Registries auth API

Holds the draft-07 JSON Schemas (`auth-api/src/auth_api/schemas/schemas/*.json`) that describe request and response payloads of the auth API, plus `utils.py`, which loads them and validates payloads. It takes JSON payloads from API resources and returns pass/fail. It writes nothing and hands no work on. A small test helper checks test payloads against schemas.

## Contract
- Schemas are keyed by `$id`, which has the form `https://bcrs.gov.bc.ca/.well_known/schemas/<name>`. They link to each other with `$ref` (for example `contacts` → `contact_response`, `orgs_response` → `org_response`, `affiliation_response` → `business` and `org_response`, `members` → `membership` → `user_response`).
- Request schemas: `affiliation`, `affiliation_invitation`, `org`, `contact`, `mailing_address`, `entity`, `user`, `termsofuse`, `document`, `bconline_credential`, `payment_info`, `org_product_subscription`, `task_request`, `affidavit`. Most use `additionalProperties: false`.
- Response schemas: `*_response`, `error`, `exception`, `paged_response`, `codes`, `products`, `user_settings_response`. These mostly allow extra properties.
- List wrappers (`contacts`, `members`, `invitations`, `affiliation_invitations`) are `{items: [...]}`.
- Error shapes: `error` requires `message`. `exception` requires `code` and `message`.
- Each file is a nested set of schema fragments with `$id` values like `#/properties/...`. Fragments often appear as separate pieces that belong to one schema.

## Decisions (`schemas/utils.py`)
- `get_schema_store()` reads every `.json` file in the schemas directory and indexes each by `$id`. With `validate_schema=True` it also runs `Draft7Validator.check_schema()`.
- `get_schema()` looks a schema up by `f'{BASE_URI}/{schema_id}'`.
- `validate(json_data, schema_id)` builds a `RefResolver` over the store and runs `Draft7Validator` with `FORMAT_CHECKER`. It returns `(True, None)` when the payload is valid. When it is invalid it returns `(False, iter_errors())`. On a `SchemaError` it returns `(False, error)`.
- `serialize(errors)` turns the errors into a list of message strings.
- Enforced constraints worth knowing:
  - `org.json`: `typeCode` is one of BASIC, PREMIUM, STAFF or SBC_STAFF (default BASIC). `name` must have no leading or trailing whitespace. `branchName` is at most 100 characters.
  - `payment_info.json`: `paymentMethod` is an enum of CC, DRAWDOWN, DIRECT_PAY, ONLINE_BANKING, PAD, EFT, WIRE and EJV.
  - `mailing_address.json`: the five required fields need `minLength` 1.
  - `affidavit.json`: `documentId` must have no leading or trailing whitespace.
  - Required fields: `affiliation` needs `businessIdentifier`. `entity` needs `businessIdentifier`. `affiliation_invitation` needs `fromOrgId` and `businessIdentifier`. `task_request` needs `relationshipStatus`.

## Hazards
- `validate()` does not check that the schema exists. An unknown `schema_id` raises instead of returning a failure.
- Many schemas are malformed or only look strict:
  - A nested duplicate key sits where `items` should be, for example `contacts` inside `contacts`, `user` inside `user`, and `orgs` in `paged_response`. Those `$ref`s are likely ignored.
  - `payment_info` puts `revenueAccount` outside `properties`.
  - Defaults contradict types, for example `isLogin`/`istermsaccepted` booleans defaulting to `""`, and `remarks` as an array defaulting to `""`.
  - `isBusinessAccount` is a boolean with a `pattern`.
  - `invitation_response` has a trailing comma.
  - `$id`s use snake_case while property names use camelCase.
  - The `^(.*)$` pattern accepts anything. `type` fields have no enum, for example in `affiliation_invitation`.
- The `fpath[-5:] == '.json'` check in `get_schema_store()` is a loose suffix test. A schema file with a bad `$id` is silently left out of the store or overwritten.

## Open first
- `auth-api/src/auth_api/schemas/utils.py`: the loader and validator, and the only logic.
- `schemas/org.json`, `payment_info.json`, `affiliation_invitation.json`: the main request schemas with real constraints.
- `schemas/org_response.json`, `user_response.json`, `affiliation_response.json`: the main response contracts.
- `auth-api/tests/utilities/schema_assertions.py`: `assert_valid_schema(data, schema_file)`. It loads from `tests/utilities/schemas/`, where `user.json` is a JSON:API user fixture.

=== auth-api: validation schemas, feature flags and gateway string sanitizer ===

# auth-api: validation schemas, feature flags and gateway string sanitizer

This part holds the static JSON Schema (draft-07) definitions that the auth-api uses to validate request payloads and response shapes. It also holds a feature-flag file and one string sanitizer for API gateway use. The notes do not show who loads the schemas or flags, so the callers are not covered here.

## Contract

- **Request schemas** (`auth_api/schemas/schemas/*.json`):
  - `anonymous_user.json`: `{username, password}`.
  - `bulk_user.json`: `{orgId: number, users: [{username, password}]}`.
  - `api_key.json`: `{keyName, environment}`. Schema ID is `https://bcrs.gov.bc.ca/.well_known/schemas/api_key`.
  - `contact.json`: `phoneExtension` and `email`.
  - `entity.json`: business fields (`businessIdentifier`, `businessNumber`, `name`, `passCode`, `corpTypeCode`, `corpSubTypeCode`, `folioNumber`, `resetPasscode`), plus `passcodeResetEmail` and `state`.
  - All except `contact.json` and `entity.json` set `additionalProperties: false`; the notes do not say whether those two do.
- **Response schemas**:
  - `user_settings_response.json`: `{id, label, type, accountType|null, urlorigin|null}` and `{urlpath, productSettings, accountStatus}`.
  - `bconline_response.json`: eight string fields from BC Online (`authCode`, `authCodeDesc`, `orgName`, `orgType`, `gstStatus`, `gstStatusDesc`, `fax`, `phone`), each defaulting to `""`.
- `flags.json` holds `flagValues` with `string-flag`, `bool-flag` and `integer-flag`. These are plain values with no logic.
- `services/api_gateway.py` takes a string `target` and returns it sanitized.

## Decisions and checks

- **Username check**: `^[^\s]+(\s+[^\s]+)*$` in `anonymous_user.json`, `bulk_user.json` and `api_key.json` (as `keyName`). It refuses empty values and leading or trailing whitespace.
- **Password check**: in `anonymous_user.json` and `bulk_user.json`, it needs a lowercase letter, an uppercase letter, a digit, one of `!@#$%^&*`, and at least 8 characters.
- **Email check**: the regex in `contact.json` and for `passcodeResetEmail` in `entity.json`.
- **`urlorigin` check**: a URL regex with an optional scheme, a domain, an optional port and an optional path.
- **API gateway sanitizer**: strips every character outside `[a-zA-Z0-9_\- .]`, then truncates to 64 characters.

## Hazards

- Most string fields use the catch-all pattern `^(.*)$`, so they accept anything. This covers `phoneExtension`, every `entity.json` string including `state` (the "ACTIVE"/"HISTORICAL" examples are not enforced), `urlpath` and `productSettings`.
- The password pattern allows only `!@#$%^&*` as special characters. Passwords using other symbols are rejected.
- The `urlpath` description says it must start with a backslash, but nothing enforces that. `resetPasscode` has `$id` `#/properties/passcodeReset`, so its `$id` does not match its name. `accountStatus` has the title "URL Path". `accountType` and `urlorigin` allow null while defaulting to `""`.
- The gateway sanitizer silently drops characters and truncates at 64, so two different inputs can collapse to the same value.

## Open first

- `auth-api/src/auth_api/schemas/schemas/entity.json`: the business entity fields plus `passcodeResetEmail` and `state`.
- `auth-api/src/auth_api/schemas/schemas/bulk_user.json` and `anonymous_user.json`: the username and password rules.
- `auth-api/src/auth_api/services/api_gateway.py`: the sanitizer.
- `auth-api/flags.json`: the feature flag values.

=== Auth API data models (SQLAlchemy persistence layer) ===

# Auth API data models (SQLAlchemy persistence layer)

Defines the Auth service's database models and a few query helpers. Services and resources call these classes to read and write users, orgs, memberships, invitations, affiliations, tasks, products and authorizations. They hand work to SQLAlchemy and the `authorizations_view` DB view.

## Contract
- **Input:** dicts from services (`create_from_dict`, `update_*_from_dict`, with camelCase keys converted to snake_case where noted), search dataclasses (`TaskSearch`, `OrgSearch`, `AffiliationInvitationSearch`), and JWT token info (`create_from_jwt_token`).
- **Output:** model instances, lists, or `(rows, total)` pages. Writes go to the DB.
- **Audit:** `BaseModel` fills created/modified timestamps and `created_by_id`/`modified_by_id` from `g.jwt_oidc_token_info`. `VersionedModel` subclasses also write activity records (sqlalchemy_continuum plus `activity_plugin` in `db.py`).
- **Shared objects:** `models/__init__.py` re-exports every model plus `db` and `ma`. It registers `DBTracing.query_tracing` on every SQL execution.
- **Query helper:** `CustomQuery.filter_conditionally` skips a filter when the criteria is None. It filters dates by day, and uses `ilike` for `is_like`.
- **Pagination:** `fetch_activity_logs_for_account` and `fetch_tasks` return `(rows, total)` pages.
- **JSON schema:** `schemas/paged_response.json` is an example paged org-list response.

## Decisions that shape behaviour
- `BaseModel.save/flush/delete` call `create_activity()` for VersionedModel unless `DISABLE_ACTIVITY_LOGS` is set. The verb is delete, update (if `modified_by` is set) or create. `reset()` skips it.
- `Org.delete()` is a soft delete that sets INACTIVE.
- Org finders exclude INACTIVE and REJECTED orgs.
- `Org` before_insert rejects STAFF and SBC_STAFF type codes (`BusinessException(INVALID_INPUT)`). before_update rejects any `type_code` change.
- `Org._search_for_statuses` hides DIRECTOR_SEARCH and GOVM orgs that still have PENDING invitations. `search_pending_activation_orgs` returns only those.
- `Org.reset()` hands the org to another member when there is more than one member or an affiliation. Otherwise it falls back to `BaseModel.reset`.
- `Invitation.status` and `AffiliationInvitation.status` are computed. A PENDING invitation reads as EXPIRED once past expiry, with no DB update. `update_invitation_as_retried` resets `sent_date` and status.
- `AffiliationInvitation.filter_by` raises ValueError if no filter is given. It always filters on `is_deleted`.
- `Membership.__init__` applies default type and status. `add_membership_for_staff` makes an ACTIVE USER membership. `remove_membership_for_staff` sets it INACTIVE. `reset()` promotes a COORDINATOR or USER when the last ADMIN goes.
- `User._get_type` and `_is_verified` (BCSC only) set user type and verification on create from JWT. `update_from_jwt_token` sets ACTIVE and only touches `login_time` when `is_login=True`. `User.delete()` is disabled.
- `Authorization.find_user_authorization_by_business_number` picks a query by parameter combination. The product variant orders ADMIN, then COORDINATOR, then USER.
- `Task.fetch_tasks` applies the optional filters. PST dates are converted to UTC, and the end date is extended to 23:59:59. It orders by `date_submitted`.
- `Task.find_by_task_relationship_id` defaults status to OPEN.
- `Entity.create_from_dict` hashes `pass_code`. Direct assignment does not.
- `Affiliation` finders filter by environment. A None environment matches NULL.

## Hazards
- `Membership.__init__` sets the `membership_type` relationship instead of `membership_type_code` when defaulting. `Membership.reset()` commits twice per promoted member.
- `BaseModel._get_current_user` uses a bare `except` and returns None, so audit user ids can be silently null. Activity logs are written after the flush, so a failure before commit leaves them inconsistent.
- `Affiliation.find_affiliation_by_ids` ignores environment, and `ContactLink` finders return only the first link. `Authorization` uses `.one_or_none()` on one path (raises on duplicates) and `.first()` on the others.

## Open first
- `base_model.py`: audit columns, activity logging, `update_from_dict`, `reset`.
- `org.py`: org lifecycle, search, type guards, `reset`.
- `invitation.py` and `affiliation_invitation.py`: invitation expiry, status and filters.
- `views/authorization.py`: authorization lookups against the DB view.

=== Auth API: code tables and code lookup service ===

# Auth API: code tables and code lookup service

SQLAlchemy models for the Auth service's reference ("code") tables, plus `services/codes.py`, which serves their contents generically. The models inherit `BaseCodeModel` (shared code, description and default columns). `services/codes.py` reads them for the API. A few unrelated small models sit alongside them (see the end).

## Contract
- **In:** `Codes.fetch_codes(code_type)` takes a table name as a string.
- **Out:** a list of dicts, one per row, or `None`. Each row is serialized with `auth_api.schemas.<tablename>.<ClassName>Schema`. If that module doesn't exist, it falls back to `BaseCodeSchema` in `auth_api.schemas.basecode_type`.
- **Storage:** read-only lookups. Other services call the per-model classmethods to resolve defaults or codes. The notes show no writes except the test fixture; rows are seeded externally.
- **Tables:** `affidavit_statuses`, `affiliation_invitation_types`, `business_size_codes`, `business_type_codes`, `corp_types`, `invitation_types`, `membership_status_codes`, `membership_types`, `org_statuses`, `org_types`, `payment_types`, `permissions`, `product_subscriptions_statuses`, `product_type_codes`, `staff_remark_codes`, `suspension_reason_codes`, `user_status_codes`.

## Decisions
- `fetch_codes`: no `code_type` returns None. Otherwise `fetch_data_model(code_type.lower())` scans `db.Model._decl_class_registry` for a `BaseCodeModel` subclass whose `__table__.fullname` matches. No match returns None. A match runs `query.all()` and serializes each row.
- `fetch_codes` wraps every exception in `BusinessException(Error.UNDEFINED_ERROR, ...)`.
- Default lookups filter `default=True` and take `.first()`:
  - `AffidavitStatus.get_default_status`
  - `AffiliationInvitationType.get_default_type`
  - `CorpType.get_default_corp_type`
  - `InvitationType.get_default_type`
  - `MembershipType.get_default_type`
  - `OrgStatus.get_default_status`
  - `OrgType.get_default_type`
  - `PaymentType.get_default_payment_type`
- Lookups by code or name:
  - `AffiliationInvitationType.get_type_by_code`
  - `InvitationType.get_type_by_code`
  - `MembershipType.get_membership_type_by_code`
  - `OrgType.get_type_for_code`
  - `ProductTypeCode.find_by_code`
  - `MembershipStatusCode.get_membership_status_by_code(name)`
  - `UserStatusCode.get_user_status_by_name(name)`
- `MembershipStatusCode.get_default_type()` and `UserStatusCode.get_default_type()` return the hardcoded integer `1`, not a row.
- `Permissions.get_permissions_by_membership` filters by `membership_type_code` and `org_status_code` and returns all matches. `get_all_permissions` returns every row. The tests pin that `UserStatusCode.get_default_type()` returns 1.

## Hazards
- Every `.first()` lookup returns None silently when no row matches, and callers get no error. Nothing enforces a single `default=True` row per table, so with several defaults the winner is arbitrary.
- The hardcoded default `1` for membership and user status is never checked against the table, so a missing seed row breaks things quietly. Those two tables use `autoincrement=False`, so ids must be supplied.
- `fetch_codes` hides the real failure behind a generic `UNDEFINED_ERROR`. A missing schema module is also swallowed by the `BaseCodeSchema` fallback, so output can lose its table-specific fields without any signal.

## Open first
- `services/codes.py`: generic code lookup and serialization.
- `models/membership_status_code.py` and `models/user_status_code.py`: hardcoded defaults and manual ids.
- `models/permissions.py`: the membership-type × org-status to actions mapping. Its docstrings are wrong, and `actions` is part of the primary key.
- `models/org_type.py`: a representative default and by-code lookup model. The other code models follow the same pattern.

## Unrelated
`models/user_settings.py` is a plain, loosely defined value object (not a table). It holds the header-menu entries: label, URL, account type and status, product settings, `additional_label`.

=== auth-api service layer (BC Registries Auth API, Flask) ===

# auth-api service layer (BC Registries Auth API, Flask)

The Flask Authorization API's application factory and service layer. It manages orgs, users, memberships, invitations, tasks and products, and hands work to Keycloak, LaunchDarkly, MinIO, the API Gateway, the pay API (REST) and a GCP queue (activity log and mailer events). `pay-api/.../endpoints_enums.py` is an unrelated duplicate of the endpoint-prefix enum (`/api/v1`, `/api`, `/test`).

## Contract
- **In:** HTTP requests with Keycloak JWTs. Roles come from `realm_access.roles` (`get_roles` in `__init__.py`). Services receive DTO dataclasses from `models/dataclass.py` (`Activity`, `OrgSearch`, `TaskSearch`, `KeycloakGroupSubscription`, `DeleteAffiliationRequest`, `ProductReviewTask`).
- **Out, activity log:** `ActivityLogPublisher` publishes a CloudEvent to `CONFIG.AUTH_EVENT_TOPIC`. Its `data` is `{actorId, action, itemType:'ACCOUNT', itemName, itemId, itemValue, orgId, remoteAddr, createdAt}`, with `source='sbc-auth-auth-api'` and `type=QueueMessageTypes.ACTIVITY_LOG`.
- **Out, other:**
  - Keycloak admin REST calls for groups, OTP and clients.
  - MinIO pre-signed URLs, returned as `{preSignedUrl, key}`.
  - API Gateway consumer and API-key calls.
  - Emails via `publish_to_mailer`.
- **Responses:** JSON is camelCased by `camelize_json`, except swagger.json. An API version header is added, and CORS is open (`*`).

## Decisions
- `ActivityLogPublisher`: if `actor_id` is missing and the JWT is present, it resolves the user with `UserModel.find_by_jwt_token`.
- `ApiGateway.create_key` (`services/api_gateway.py`):
  - A new consumer (checked via `_consumer_exists`) gets a Keycloak client from `utils/api_gateway.py`. Its service account is added to `GROUP_API_GW_USERS` (prod) or `GROUP_API_GW_SANDBOX_USERS` (sandbox), plus `GROUP_ACCOUNT_HOLDERS`. Sandbox also gets a payment account from `_create_payment_account`. Then the consumer is POSTed.
  - An existing consumer gets a POST to `/apikeys`.
  - Environment defaults to sandbox. `_get_email_id` builds `org_id[-sandbox]@suffix`.
- `ApiGateway.revoke_key` and `get_api_keys`: require ADMIN or STAFF. `revoke_key` raises `DATA_NOT_FOUND` if the key is unknown. `get_api_keys` returns only `keyStatus='approved'`, via `_filter_and_add_keys`.
- `KeycloakService.add_or_remove_product_keycloak_groups` splits by `KeycloakGroupActions` and runs async PUT (add) or DELETE (remove) batches. `_find_group_or_subgroup_id` searches subgroups recursively. `_reset_otp` sets the `CONFIGURE_TOTP` required action and deletes the OTP credentials.
- `RestService._invoke` (POST/PUT/PATCH/DELETE): network errors and 5xx become `ServiceUnavailableException`; other HTTP errors are re-raised. If no token is given it takes the one from the request's Authorization header. GET can mount `RETRY_ADAPTER` (5 retries, retries 404s). `get_service_account_token` is cached.
- `Flags`: `is_on` / `value` evaluate per user. Flags load from `flags.json` when testing. With no client they return the default.
- Role and status rules: `utils/roles.py` (`CLIENT_ADMIN_ROLES`, `ALL_ALLOWED_ROLES`, valid statuses per type). State and type enums: `utils/enums.py`.
- `MinioService`: the PUT URL lasts 5 minutes and the GET URL 1 hour.

## Hazards
- `add_or_remove_users_from_group` only logs failures. Product-group changes can partly fail with no error raised.
- `build_cache` in `__init__.py` swallows permission and product cache errors, so a broken cache fails silently at startup.
- `ApiGateway` sets `org.has_api_access` before the later steps finish, with no transaction. A failure leaves the flag set without a working key.

## Open first
- `services/api_gateway.py`: key lifecycle and Keycloak provisioning.
- `services/keycloak.py` and `services/rest_service.py`: outbound identity and HTTP behaviour.
- `__init__.py`: app factory, request and response hooks, cache build.
- `models/dataclass.py` and `utils/enums.py`: DTO and state vocabulary.

`org.py`, `invitation.py`, `membership.py`, `task.py`, `user.py` and `products.py` hold the main workflows, but their logic is not covered in these notes beyond their dependencies.

=== auth-api service layer (BC Registries auth-api) ===

# auth-api service layer (BC Registries auth-api)

The business-logic layer of a Flask auth API. It manages orgs, memberships, invitations, affiliations (org↔business links), affidavits, product subscriptions, users and staff-review tasks. It works on SQLAlchemy models, calls Keycloak, legal-api, NAMEX, pay-api, BCOL and notify-api over HTTP, and publishes events to the account-mailer GCP queue. `config.py` and `docs/dotenv_template` hold settings. `docs/dotenv_template` is a local env template with blank secrets.

## Contract
- **In:** route handlers call service classes with dicts (camelCase request JSON) or model instances. User identity comes from JWT via `@user_context`.
- **Out:** schema-dumped dicts or service wrappers. Email goes through `publish_to_mailer(notification_type, data, source)` in `utils/account_mailer.py`, which builds a CloudEvent for `ACCOUNT_MAILER_TOPIC`. It logs publish failures and does not raise them. Activity logs go through `ActivityLogPublisher`. Errors are raised as `BusinessException(Error.X)`.
- **Config:** `config.py` `get_named_config` selects Dev/Test/Prod classes.

## Decisions
- **Org create** (`org.py`): chained validators (`bcol_credentials`, `account_limit`, `access_type`, `duplicate_org_name`).
  - GOVM orgs become PREMIUM with PENDING_INVITE_ACCEPT.
  - GOVN, or BCEID/EXTRA_PROVINCIAL without an approved affidavit → PENDING_STAFF_REVIEW plus a review task.
- **Org update/delete/patch:** `update_org` handles the GOVM review flow. `delete_org` needs ADMIN/STAFF, deactivates the pay account, unaffiliates, and deactivates members. `patch_org` dispatches by PatchActions: status (SUSPENDED needs a reason), access type (whitelisted), API access.
- **Org decision:** `approve_or_reject` sets ACTIVE/REJECTED, calls `AffidavitService.approve_or_reject` for AFFIDAVIT_REVIEW, and notifies admins.
- **Affiliation** (`affiliation.py`): `is_authorized` checks passcode, or party name for SP/GP. `create_new_business_affiliation` validates the NR (status, payment, consent, applicant email/phone). `delete_affiliation` can reset the passcode. `fix_stale_affiliations` is system-only. `find_visible_affiliations_by_org_id` hides NR/TMP duplicates. `get_affiliation_details` fans out to NAMEX/LEAR and merges, dropping consumed NRs.
- **Affiliation invitation:** `_validate_prerequisites` requires a business contact email (not for REQUEST). Accept creates the affiliation, FAILED on refuse. Delete is soft for ACCEPTED, hard otherwise. `validate_token` has an expiry and refuses ACCEPTED/EXPIRED.
- **Team invitation** (`invitation.py`): needs ADMIN/COORDINATOR/STAFF. `accept_invitation` creates the membership. `_get_status_based_on_org` gives ACTIVE for GOVM, PENDING_STAFF_REVIEW for a BCEID admin that isn't verified, else PENDING_APPROVAL. `_create_affidavit_review_task` is created for PENDING_STAFF_REVIEW.
- **Membership:** `update_membership` and `deactivate_membership` enforce role rules. BCEID users cannot be ADMIN, and the sole ADMIN cannot be removed or downgraded. They sync Keycloak groups. `get_members_for_org` applies visibility rules.
- **Task** (`task.py`): `update_task` dispatches by relationship type: ORG → `OrgService.approve_or_reject`, PRODUCT → `update_product_subscription`, USER → `approve_or_reject_bceid_admin`. HOLD on ORG sends a hold email. An approved AFFIDAVIT_REVIEW sets `user.verified`.
- **Products** (`products.py`): `create_product_subscription` cascades linked/parent products, skips premium-only products for non-premium orgs, and creates a review task for PENDING_STAFF_REVIEW. `resubmit_product_subscription` needs REJECTED. Approval updates Keycloak groups.
- **Affidavit:** `create_affidavit` marks any PENDING one INACTIVE and moves its task via `_modify_task`.
- **Users:** `create_user_and_add_membership` creates users in the DB and Keycloak, with rollback. `delete_anonymous_user` blocks removal of the sole owner. `save_from_jwt_token` resets terms acceptance when a newer version exists.
- **Payment type:** `payment_type.validate` picks the method from access type, org type and `DIRECT_PAY_ENABLED`.
- **Test reset:** `reset.py` deletes TESTER-created rows.

## Hazards
- Several flows are non-atomic. `Affidavit.approve_or_reject*` never saves. Entity and affiliation saves are separate. The sole-admin check and save in `update_membership` can race. `delete_anonymous_user` makes two separate saves.
- Mailer and notification failures are swallowed or turned into generic errors. `publish_to_mailer` logs only. `validate_token` uses a bare `except`. `approve_or_reject` carries on without admin emails.
- `Entity.validate_pass_code` compares plain text with a hashed value, so it can never match. `refuse_affiliation_invitation` checks `invitation.status` where other methods use `invitation_status_code`.

## Open first
- `services/org.py`: org create, update, delete, approve and patch.
- `services/affiliation.py`: affiliation creation, visibility, details fetch.
- `services/task.py` and `services/products.py`: review-task dispatch and subscriptions.
- `services/membership.py` and `services/invitation.py`: role and status rules.
