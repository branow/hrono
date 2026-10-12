# today

# Summary: auth-api source (BC Registries "sbc-auth" Authorization API, Flask/Python) plus one pay-api file

This group is a sample of files from the Flask-based Authorization API (`auth-api/src/auth_api/`) covering the app factory, extensions, models, services, utilities, one unit test, and a duplicated endpoint enum from `pay-api`. Many chunks are only imports and setup, with the main classes not shown.

## App bootstrap and extensions
- **`__init__.py`**: Flask app factory using `config.CONFIGURATION[run_mode]`.
  - Optional Sentry setup.
  - Extensions: flags, db, ma, mail, queue, endpoints.
  - JWT manager with `get_roles`, which reads `realm_access.roles`.
  - `before_request` stores the origin in `g.origin_url`.
  - `after_request` adds a version header, camelizes JSON, and sets CORS-style headers.
  - `build_cache()` builds the permission and product caches.
- **`extensions/mail.py`**: exports a bare `Mail()` instance named `mail`.

## Models
- **`models/dataclass.py`**: DTOs and search filters.
  - Activity, AffiliationInvitationSearch/Data, Affiliation, DeleteAffiliationRequest.
  - OrgSearch, SimpleOrgSearch, TaskSearch.
  - KeycloakGroupSubscription, ProductReviewTask.
- **`models/user.py`**: SQLAlchemy User model holding Keycloak GUID data, with relationships to Membership, Org and UserStatusCode (only the header is shown).

## Services (`services/`)
- **Integration and infrastructure**
  - `api_gateway.py`: creates and revokes API keys and lists them per environment (sandbox or prod). It provisions Keycloak clients and consumers, and creates sandbox payment accounts.
  - `keycloak.py`: batch add or remove of users in Keycloak groups via aiohttp, fetches users by role, resets OTP, and does a recursive group lookup.
  - `keycloak_user.py`: wrapper around a Keycloak user dict with typed properties and required actions (UPDATE_PASSWORD, CONFIGURE_TOTP).
  - `rest_service.py`: sync and async REST wrapper.
    - POST/PUT/PATCH/DELETE go through `_invoke`.
    - GET has optional retry via `RETRY_ADAPTER` (5 retries, 404 in the forcelist).
    - Also provides a service-account token and `call_posts_in_parallel`.
    - Connection errors and 5xx responses map to `ServiceUnavailableException`.
  - `flags.py`: LaunchDarkly wrapper with `is_on()` and `value()`. It uses a local `flags.json` when testing.
  - `minio.py`: pre-signed PUT URLs (5-minute expiry) and GET URLs (1-hour expiry) for the accounts bucket.
  - `activity_log_publisher.py`: publishes an ACTIVITY_LOG CloudEvent to `AUTH_EVENT_TOPIC`.
- **Domain services (imports and setup only)**: `invitation.py`, `membership.py`, `org.py`, `products.py` (defines `QUALIFIED_SUPPLIER_PRODUCT_CODES`: MHR_QSLN, MHR_QSHD, MHR_QSHM), `task.py`, `user.py`. Several of them set up a Jinja2 `ENV` with autoescape.
- **`validators/__init__.py`**: placeholder package with no code.

## Utilities (`utils/`) and status
- **`api_gateway.py`**: builds the Keycloak client JSON for gateway service accounts.
  - Client ID and secret generation (uuid4, `secrets.token_urlsafe(36)`), with a `-sandbox` suffix when the environment is not prod.
  - Service-account-only OIDC client config.
  - 17 protocol mappers (hardcoded claims, session notes, user properties, roles) and four audience mappers.
- **`enums.py`**: 30+ enums covering auth types, corp types, payment methods, access types, task types and statuses, activity actions, and others.
- **`roles.py`**: role names, membership types and statuses, and role groupings such as `CLIENT_ADMIN_ROLES`.
- **`passcode.py`**: bcrypt hash and validate.
- **`util.py`**: case conversion, a Singleton metaclass, `mask_email`, `get_request_environment`, and digit extraction.
- **`endpoints_enums.py`**: `EndpointEnum` with `API_V1`, `API`, `TEST_API` and `DEFAULT_API`.
- **`status.py`**: HTTP status constants (100–511) and `is_*` classifiers.

## Tests
- **`tests/unit/services/test_minio.py`**: two tests for pre-signed PUT and GET URL generation, including a real upload and download round trip.

## Cross-service
- **`pay-api/.../endpoints_enums.py`**: the same `EndpointEnum` as in auth-api, repeated for the pay API.

## Caution
- **Silent failures**
  - Cache build errors at startup are logged and swallowed.
  - Keycloak group add/remove batch failures are logged but not raised, so callers can't see partial failure.
  - Activity log publishing catches all exceptions.
  - `Flags` returns the default value when LaunchDarkly is unavailable.
- **Missing-key crashes**
  - `get_roles` indexes `realm_access.roles` with no null check.
  - The `KeycloakUser.password` getter assumes `credentials[0]` exists.
- **Non-transactional**: in the API gateway service, `org.has_api_access` is set before later steps finish. The sandbox payment account uses hardcoded dummy bank values ('000', '00000', '0000000').
- **`rest_service.py` inconsistencies**
  - `put()` omits `additional_headers` and `generate_token`.
  - Docstrings for `put` and `delete` are copy-paste errors.
  - `_get_token` strips "Bearer " without validating that it's there.
  - `skip_404_logging` still raises the exception.
- **Keycloak client mappers in `utils/api_gateway.py`**: the "given name" mapper writes to `claim.name='lastname'`, and the "name" and "full name" mappers duplicate each other. Some content in this file is truncated, with the dict and return not fully visible.
- **Enums**
  - `from_value()` returns None for unknown values.
  - `Status` and `UserStatus` use ints while nearly everything else uses strings.
  - `OrgStatus` and `TaskRelationshipStatus` have identical value sets.
  - `NRActionCodes` entries marked FUTURE may be unused.
- **Timestamps**: the activity log's `createdAt` is naive local time, while the CloudEvent `time` is UTC-aware.
- **Parsing quirks**
  - MinIO extension parsing with `split('.')[-1]` is unreliable for names without a dot or with several dots.
  - `mask_email` silently skips masking if the address does not split into exactly two parts.
- **Passcode**: `passcode.py` has misleading type hints and a misspelled variable. `passcode_hash` returns None for falsy input, while `validate_passcode` returns False.
- **`keycloak_user.py`**: `value()` returns a JSON string though it is typed as `Dict`.
- **Test hygiene**: the MinIO test leaves a file handle open and never checks the upload or download status.
- **Incomplete content**: several service files (`keycloak.py`, `products.py`, `invitation.py`, `membership.py`, `org.py`, `task.py`, `user.py`) show only imports or setup. One `utils/api_gateway.py` chunk contained an error-like note instead of code, so don't assume the implementation is complete.

# decisions

# Auth API service layer, utilities and app factory (sbc-auth `auth-api`, plus one `pay-api` enum)

This part builds the Flask Authorization API app. It holds the services that call Keycloak, the API gateway, MinIO, LaunchDarkly and the activity-log and mailer queues. It also holds the shared enums, role constants and helpers. It belongs to the sbc-auth system. One `pay-api` file, `endpoints_enums.py`, is unrelated: it repeats the `EndpointEnum` path constants (`API_V1='/api/v1'`, `API='/api'`, `TEST_API='/test'`, `DEFAULT_API=API_V1`) that `auth-api` also defines.

## App factory (`auth_api/__init__.py`)
- Config comes from `config.CONFIGURATION[run_mode]`. `run_mode` defaults to `FLASK_ENV`, then `'production'`.
- Sentry starts only if `SENTRY_ENABLE=='true'` and `SENTRY_DSN` is set.
- Extensions initialised: flags, db, ma, mail, queue, endpoints.
- `setup_jwt_manager()` runs unless testing. Its role callback `get_roles` reads `a_dict['realm_access']['roles']`.
- `before_request` stores `HTTP_ORIGIN` (default `'localhost'`) in `g.origin_url`.
- `after_request` does three things:
  - `add_version()` adds the version header.
  - `camelize_json()` converts response JSON to camelCase, except swagger.json.
  - `set_access_control_header()` sets `Access-Control-Allow-Origin: *` and allows the headers `Authorization, Content-Type, registries-trace-id, invitation_token, account-id`.
- `build_cache()` clears the cache. Unless `TESTING=True`, it then runs `PermissionService.build_all_permission_cache()` and `ProductService.build_all_products_cache()`.

## Outbound integrations

### Activity log (`activity_log_publisher.py`)
- Input is an `Activity` (`org_id`, `action`, `name`, optional `value`, `id`, `type`, `actor_id`).
- If `actor_id` is missing and `g` has `jwt_oidc_token_info`, it looks up the user with `UserModel.find_by_jwt_token()` and uses `user.id`, or `None` if the lookup fails.
- Data payload: `actorId, action, itemType='ACCOUNT', itemName, itemId, itemValue, orgId, remoteAddr, createdAt`.
- The payload is wrapped in a `SimpleCloudEvent` (uuid4 id, `source='sbc-auth-auth-api'`, `type=QueueMessageTypes.ACTIVITY_LOG`, UTC time).
- It is published to `CONFIG.AUTH_EVENT_TOPIC` through `queue.publish(GcpQueue.to_queue_message(event))`.
- Any exception is sent to Sentry and the logger, and not re-raised.

### API gateway keys (`services/api_gateway.py`, `utils/api_gateway.py`)
- `environment` defaults to `'sandbox'` and picks `API_GW_KEY` or `API_GW_NON_PROD_KEY`. Both the `GROUP_*` constants and the consumer endpoint come from config.
- The consumer email comes from `_get_email_id`. It returns the configured `API_GW_CONSUMER_EMAIL`, or else `org_id[-sandbox]@API_GW_EMAIL_SUFFIX`.
- `_get_api_consumer_endpoint` returns `API_GW_CONSUMERS_API_URL` or `API_GW_CONSUMERS_SANDBOX_API_URL` for the environment.
- `create_key` first checks whether the consumer exists by email, with `_consumer_exists`.
  - **New consumer:**
    - Generate a Keycloak client from `utils/api_gateway.py`. It has a uuid4 id, a `secrets.token_urlsafe(36)` secret, and a client id from `client_id_pattern.format(account_id=...)` with `-sandbox` appended when `env != 'prod'`.
    - Add the service account to `GROUP_API_GW_USERS` (prod) or `GROUP_API_GW_SANDBOX_USERS` (sandbox), and to `GROUP_ACCOUNT_HOLDERS`.
    - For sandbox, create a payment account with `_create_payment_account`. This is skipped if `PAY_API_SANDBOX_URL` is unset.
    - POST the consumer with its Keycloak credentials.
  - **Existing consumer:** POST to `/apikeys`.
- `revoke_key` looks up the email id across all keys. If it is not found it raises `DATA_NOT_FOUND`. Otherwise it PATCHes the revoke endpoint.
- `get_api_keys` queries both environments per email and keeps only `keyStatus=='approved'` (`_filter_and_add_keys`). The result is a `consumerKey` list of `apiKey, keyStatus, email, environment`.
- Revoke and get require ADMIN or STAFF.
- The generated Keycloak client is service-account only: `standardFlowEnabled`, `implicitFlowEnabled` and `directAccessGrantsEnabled` are all False.
- Its mappers hardcode these claims:
  - `loginSource='API_GW'`
  - `Account-Id=str(account_id)`
  - `_client_id` into the username, name and `idp_userid` claims
- Audience mappers target `account-services`, `ppr-services`, `entity-services` and `business-search-service`, and apply to the access token only.

### Keycloak (`keycloak.py`, `keycloak_user.py`)
- `add_or_remove_product_keycloak_groups` splits `KeycloakGroupSubscription` items by `group_action` (`ADD_TO_GROUP` or `REMOVE_FROM_GROUP`).
- It calls async `add_or_remove_users_from_group` per batch. That function gets an admin token from `KEYCLOAK_ADMIN_USERNAME` and `KEYCLOAK_ADMIN_SECRET` (or the `KEYCLOAK_BCROS_*` variants).
- Group ids are found by `_find_group_or_subgroup_id`, which walks the group tree recursively.
- Requests go through aiohttp with `TCPConnector(limit=40)`: PUT to add, DELETE to remove.
- `get_user_emails_with_role` returns `firstName`, `lastName` and `email`.
- `_reset_otp` sets `requiredActions=['CONFIGURE_TOTP']` and deletes credentials where `type=='otp'`.
- `KeycloakUser` wraps the user dict.
  - Setting `user_name` defaults `first_name` to the username.
  - Setting `password` builds `credentials` with `type='password'`.
  - `update_password_on_login()` and `configure_totp_on_login()` append `UPDATE_PASSWORD` or `CONFIGURE_TOTP` to `requiredActions`.
  - `value()` returns a JSON string.

### REST helper (`rest_service.py`)
- POST, PUT, PATCH and DELETE go through `_invoke`. It builds the Content-Type and Authorization headers, JSON-encodes the body when `content_type` is JSON, and uses `CONNECT_TIMEOUT`.
- If `generate_token=True` and no token is passed, `_get_token()` takes the token from the current request's Authorization header.
- `ReqConnectionError`, `ConnectTimeout` and `HTTPError` with 5xx raise `ServiceUnavailableException`. Other `HTTPError` statuses are re-raised.
- GET has its own path:
  - `retry_on_failure=True` mounts `RETRY_ADAPTER` (5 retries, backoff 1, retries on 404).
  - `skip_404_logging=True` suppresses the error log on 404, but the exception is still raised.
- `get_service_account_token()` returns a cached client-credentials token.
- `call_posts_in_parallel()` posts to several URLs with aiohttp. A non-OK response or `ClientConnectorError` raises `ServiceUnavailableException`.

### Feature flags (`flags.py`)
- The LaunchDarkly client is initialised if `AUTH_LD_SDK_KEY` is set or the environment is not production.
- In testing it uses the local `flags.json` file instead of the LaunchDarkly API.
- `is_on()` and `value()` build a context from the User (`idp_userid`, `firstname`, `lastname`) or an anonymous one, and call `client.variation(flag, context, default)`.
- If the client is unavailable, they log a warning and return the default.

### MinIO (`minio.py`)
- `create_signed_put_url(file_name, prefix_key=AFFIDAVIT_FOLDER_NAME)` builds the key `{prefix}/{uuid}.{ext}`. The URL is presigned for 5 minutes on `MINIO_BUCKET_ACCOUNTS`. It returns `{preSignedUrl, key}`.
- `create_signed_get_url(key)` is presigned for 1 hour.
- The client is built from `MINIO_ENDPOINT`, `MINIO_ACCESS_KEY`, `MINIO_ACCESS_SECRET` and `MINIO_SECURE`.
- Tests pin down these behaviours: the prefix is prepended to the key, the extension is kept, and an upload followed by a download through the signed URLs works.

## Shared data and constants
- `models/dataclass.py` holds the DTOs and search filters:
  - `Activity`
  - `AffiliationInvitationSearch` (`is_deleted` defaults to False)
  - `AffiliationInvitationData` (nested `EntityDetails` and `OrgDetails`)
  - `Affiliation`
  - `DeleteAffiliationRequest` (`reset_passcode` and `log_delete_draft` default to False)
  - `OrgSearch` and `SimpleOrgSearch`
  - `TaskSearch` (sort `'asc'`, page 1, limit 10)
  - `KeycloakGroupSubscription` (`user_guid`, `product_code`, `group_name`, `group_action`)
  - `ProductReviewTask`
- `models/user.py` is the User ORM model. It stores the Keycloak GUID and relates to Membership, Org and UserStatusCode.
- `utils/enums.py` has about 30 enums. `AffiliationInvitationType.from_value()` and `PatchActions.from_value()` return None for unknown values.
- `utils/roles.py` holds these groupings:
  - `CLIENT_ADMIN_ROLES = (COORDINATOR, ADMIN)`
  - `CLIENT_AUTH_ROLES = (COORDINATOR, ADMIN, USER)`
  - `ALL_ALLOWED_ROLES = (COORDINATOR, ADMIN, USER, STAFF)`
  - valid status lists for person, org and subscription
  - premium org types (PREMIUM, SBC_STAFF, STAFF)
- `utils/passcode.py`: `passcode_hash` gives a bcrypt hash, or None for falsy input. `validate_passcode` returns False if either argument is falsy.
- `utils/util.py` helpers:
  - `get_request_environment()` returns `'sandbox'` only if `FLASK_ENV=='production'` and `AUTH_WEB_SANDBOX_HOST` appears in `request.host_url`. Otherwise it returns None.
  - `mask_email()` keeps the first 2 characters of the username and of the domain, and replaces the rest with `*`.
  - the camel/snake key converters, the `Singleton` metaclass, `digitify`, `extract_numbers` and `escape_wam_friendly_url`.
- `products.py` defines `QUALIFIED_SUPPLIER_PRODUCT_CODES` (`MHR_QSLN`, `MHR_QSHD`, `MHR_QSHM`).
- `status.py` provides HTTP status constants and the range checks `is_informational`, `is_success`, `is_redirect`, `is_client_error` and `is_server_error`.

## Services with only setup visible
`invitation.py`, `membership.py`, `org.py`, `task.py` and `user.py` show only imports and a Jinja2 `ENV` with autoescape. Their logic is not visible. `mail.py` exports a `Mail()` instance. `validators/__init__.py` is an empty placeholder.

## Open first
- `__init__.py` for startup.
- `api_gateway.py` (services and utils) for key flows.
- `keycloak.py` and `rest_service.py` for outbound calls.
- `roles.py` and `enums.py` for authorization constants.
- `dataclass.py` for DTO shapes.

## Hazards
- **Keycloak batch failures are invisible.** `add_or_remove_users_from_group` logs failures (connection errors, timeouts, non-204) and does not raise, so callers cannot detect partial group updates.
- **Startup cache failures are swallowed.** `build_cache` logs and continues, so the app can start with empty permission and product caches.
- **Gateway key creation is not transactional.** `org.has_api_access` is set before the later steps finish, and a failure leaves partial state. Sandbox payment accounts use dummy bank values (`000`, `00000`, `0000000`).
- **Feature flags fail open to the default.** With LaunchDarkly unreachable and no local config, `is_on()` silently returns the default, which is False if none is given.
- **Fragile inputs.**
  - `get_roles` crashes on a token without `realm_access.roles`.
  - `put()` and `delete()` in `rest_service` drop `additional_headers` and `generate_token` (the notes call this an inconsistency with post and patch).
  - The "given name" mapper writes to claim `lastname`.
  - File extensions come from `split('.')[-1]`.

# core

The notes describe the shared service and utility layer of the Authorization API (`auth-api`, a Flask app). That layer covers Keycloak, API-gateway keys, feature flags, MinIO, REST calls and activity events. The notes also include one unrelated file: `pay-api/.../endpoints_enums.py`, a copy of the endpoint-prefix enum (`/api/v1`, `/api`, `/test`) for the pay API.

## Role
The app factory in `auth_api/__init__.py` builds the Flask app. It wires extensions and JWT roles, and adds response headers and camelCase JSON conversion. Services call out to Keycloak, the API gateway, LaunchDarkly, MinIO, the mailer and the GCP queue.

## Contract
- **Activity events:** `activity_log_publisher.py` takes an `Activity` and publishes a CloudEvent to `AUTH_EVENT_TOPIC`. The event has source `sbc-auth-auth-api`, type `ACTIVITY_LOG`, and data keys `actorId, action, itemType='ACCOUNT', itemName, itemId, itemValue, orgId, remoteAddr, createdAt`.
- **Keycloak:** `KeycloakGroupSubscription` items are applied as batched PUT (add) and DELETE (remove) group-membership calls.
- **API keys:** `create_key` and `revoke_key` return a `consumerKey` list of `apiKey, keyStatus, email, environment`.
- **Signed URLs:** `minio.py` returns `{preSignedUrl, key}`.

## Decisions
- **API-gateway environment:** `services/api_gateway.py` defaults to `sandbox`. Prod consumers join `GROUP_API_GW_USERS` and sandbox ones join `GROUP_API_GW_SANDBOX_USERS`. Revoking and listing keys needs the ADMIN or STAFF role.
- **Feature flags:** `flags.py` returns the supplied default when LaunchDarkly is unavailable. In tests it reads `flags.json`.
- **REST calls:** `rest_service.py` turns connection errors and 5xx responses into `ServiceUnavailableException`. Other HTTP errors are re-raised as-is.
- **Roles and statuses:** `utils/roles.py` and `utils/enums.py` define the roles, status sets and role groupings.

## Hazards
- Keycloak group batches and the startup cache build log failures but never raise. Callers can't see partial or failed work.
- In `get_roles`, `a_dict['realm_access']['roles']` has no null check, so a token without it crashes the request.
- `create_key` sets `org.has_api_access` with no transaction around the later steps. The sandbox payment account uses hardcoded dummy bank values.

## Open first
- `services/api_gateway.py`: API-key lifecycle.
- `services/keycloak.py`: group membership and OTP reset.
- `services/rest_service.py`: HTTP wrappers and error mapping.
- `__init__.py`: app factory, JWT roles and the startup cache build.

# core-states

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

# core-states#2

# auth-api service layer and utilities (BC Registries Auth API)

Flask auth/account-management API: app factory, services for orgs, memberships, invitations, tasks, products, API-gateway keys, Keycloak and feature flags. It hands work to Keycloak (admin REST and aiohttp), the mailer and activity queue (GCP pub/sub), MinIO, LaunchDarkly, the API gateway consumer API and the pay-api sandbox. `pay-api/.../endpoints_enums.py` is an unrelated copy of the endpoint-prefix enum (`/api/v1`, `/api`, `/test`).

## Contract
- **In:** HTTP requests with a Keycloak JWT. Roles come from `realm_access.roles`. `g.origin_url` is set from the Origin header.
- **Out, activity log:** `ActivityLogPublisher` publishes a CloudEvent to `AUTH_EVENT_TOPIC`. Source is `sbc-auth-auth-api`, type is `ACTIVITY_LOG`. Data is `{actorId, action, itemType:'ACCOUNT', itemName, itemId, itemValue, orgId, remoteAddr, createdAt}`.
- **Out, mailer:** `publish_to_mailer` is used by the invitation, membership, task, user and org services.
- **Out, Keycloak:** group PUT/DELETE, OTP reset, client creation.
- **Out, API gateway:** `ApiGateway` calls the consumer endpoints and returns `{consumerKey: [{apiKey, keyStatus, email, environment}]}`.
- **Out, MinIO:** `create_signed_put_url` returns `{preSignedUrl, key}`. `create_signed_get_url` returns a URL string.
- **DTOs:** `models/dataclass.py` holds the search filters and DTOs shared by services: `OrgSearch`, `TaskSearch`, `AffiliationInvitationSearch`, `KeycloakGroupSubscription`, `ProductReviewTask`, `Activity`.

## Decisions
- App startup: `build_cache()` loads permission and product caches unless `TESTING`. After-request hooks camelCase JSON, except swagger.json, and add CORS and version headers.
- API keys: `ApiGateway.create_key` creates a new consumer (Keycloak client, group membership, sandbox payment account, POST consumer) when `_consumer_exists` is false. Otherwise it POSTs `/apikeys`.
- API keys: environment defaults to `sandbox`. `_get_email_id` builds `org_id[-sandbox]@API_GW_EMAIL_SUFFIX`.
- API keys: `revoke_key` raises DATA_NOT_FOUND if the key is in no consumer. `revoke_key` and `get_api_keys` require ADMIN or STAFF. `get_api_keys` keeps only `keyStatus=='approved'` (`_filter_and_add_keys`).
- API keys: `_create_payment_account` is skipped when `PAY_API_SANDBOX_URL` is unset.
- Keycloak groups: `add_or_remove_product_keycloak_groups` splits `KeycloakGroupSubscription` items by `group_action`, then `add_or_remove_users_from_group` PUTs (add) or DELETEs (remove). It finds groups with `_find_group_or_subgroup_id`, which walks subgroups recursively.
- OTP reset: `_reset_otp` sets the required action `CONFIGURE_TOTP` and deletes the `otp` credentials.
- Flags: `Flags` initialises if `AUTH_LD_SDK_KEY` is set or the environment is not production. In testing it reads `flags.json`. If no client is available it logs a warning and returns the default.
- REST calls: `RestService` turns connection errors and 5xx responses into `ServiceUnavailableException`. Other HTTP errors re-raise. It takes the bearer token from the request when none is passed. GET with `retry_on_failure` mounts `RETRY_ADAPTER` (5 retries, retries on 404). `call_posts_in_parallel` raises on any non-OK response.
- Role sets in `utils/roles.py`: `CLIENT_ADMIN_ROLES`, `CLIENT_AUTH_ROLES` and `ALL_ALLOWED_ROLES` are the authorization groupings.
- `utils/enums.py` holds the task, org, access-type and payment enums. `from_value()` returns None when the value is unknown.
- `utils/api_gateway.py` builds a Keycloak service-account client. `client_id_pattern` gets `-sandbox` appended when env is not `prod`. It uses service-account flow only and sets the `Account-Id` and `loginSource=API_GW` claims.
- `passcode_hash` and `validate_passcode` use bcrypt. `Singleton`, `mask_email` and `get_request_environment` live in `utils/util.py`.

## Hazards
- Cache build errors in `build_cache` and Keycloak group failures in `add_or_remove_users_from_group` are logged and never raised. Startup or group changes can fail silently, with no way to detect a partial failure.
- `get_roles` indexes `realm_access['roles']` without checks, so a token without them crashes the request.
- `ApiGateway` sets `org.has_api_access` before the later steps finish, with no transaction. A failed key creation can leave the flag set. The sandbox payment account uses dummy bank numbers. Activity publishing swallows all exceptions.

## Open first
1. `services/api_gateway.py`: key lifecycle, consumer, Keycloak and payment steps.
2. `services/keycloak.py`: group membership, OTP reset and role lookups.
3. `services/rest_service.py`: shared HTTP wrapper, token handling and error mapping.
4. `__init__.py`: app factory, hooks and cache build. Most business logic is in `services/org.py`, `membership.py`, `invitation.py`, `task.py`, `products.py` and `user.py`; only their imports and setup were seen.
