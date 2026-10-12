=== auth-api/src/auth_api/__init__.py ===

Initializes and configures the Authorization API Flask application with all extensions and middleware.

The factory creates a Flask app configured for the given run_mode (defaults to FLASK_ENV or 'production') via config.CONFIGURATION[run_mode]. Conditionally initializes Sentry if SENTRY_ENABLE equals 'true' and SENTRY_DSN exists. Initializes extensions: flags, db, ma, mail, queue, endpoints. Unless in testing, setup_jwt_manager() configures JWT with role callback get_roles extracting a_dict['realm_access']['roles']. before_request stores request.environ.get('HTTP_ORIGIN', 'localhost') in g.origin_url. after_request applies: add_version() adding API version header from get_run_version(), camelize_json() converting response JSON to camelCase (excluding swagger.json), set_access_control_header() setting Access-Control-Allow-Origin to '*' and Access-Control-Allow-Headers to 'Authorization, Content-Type, registries-trace-id, invitation_token, account-id'. build_cache() clears cache then, unless TESTING=True, calls PermissionService.build_all_permission_cache() and ProductService.build_all_products_cache(); exceptions logged silently.

GOTCHA: get_roles accesses a_dict['realm_access']['roles'] without null checking; missing keys crash requests.
GOTCHA: Cache build exceptions are broadly caught and logged but not re-raised, silencing startup failures.

=== auth-api/src/auth_api/extensions/mail.py ===

Extension configuration: Exports a Mail() instance (mail) that the application initializes on startup for email functionality. The pylint disable=invalid-name comment indicates the lowercase module-level naming is intentional. To change email behavior, modify where this instance is configured during application initialization.

=== auth-api/src/auth_api/models/dataclass.py ===

Defines data transfer objects and search filter dataclasses for the auth API. Activity carries org_id, action, name with optional value, id, type, actor_id for logging. AffiliationInvitationSearch filters on status_codes, invitation_types, from_org_id, to_org_id, sender_id, approver_id, entity_id, affiliation_id, is_deleted (default False). AffiliationInvitationData DTO contains id, type, affiliation_id, business_identifier, recipient_email, sent_date, accepted_date, status, additional_message plus nested EntityDetails (business_identifier, name, corp_type, state, corp_sub_type) and OrgDetails (id, name) for both from_org and to_org. Affiliation holds org_id, business_identifier with optional email, phone, certified_by_name. DeleteAffiliationRequest takes org_id, business_identifier, optional email_addresses, reset_passcode (default False), log_delete_draft (default False). OrgSearch filters on name, branch_name, business_identifier, statuses list, access_type list, bcol_account_id, id, decision_made_by, org_type, page, limit. SimpleOrgSearch on id, name, branch_name, search_text, statuses list, exclude_statuses bool, page, limit. TaskSearch filters status list, relationship_status, name, start_date, end_date, type, modified_by with submitted_sort_order defaulting to 'asc', page to 1, limit to 10. KeycloakGroupSubscription carries user_guid, product_code, group_name, group_action (KeycloakGroupActions enum). ProductReviewTask for org_id, org_name, product_code, product_description, product_subscription_id, user_id, optional external_source_id.

=== auth-api/src/auth_api/models/user.py ===

SQLAlchemy ORM model for User records in the Auth service, storing KeyCloak user information including GUID. Establishes relationships with Membership, Org, and UserStatusCode models; uses enums for LoginSource, Status, and UserStatus; integrates UserContext for session management. (Apache License header and standard ORM imports follow.)

=== auth-api/src/auth_api/services/activity_log_publisher.py ===

Publishes activity stream events. Accepts Activity with actor_id (optional), action, name, id, value, org_id. If actor_id is missing and Flask context g has 'jwt_oidc_token_info', fetches current user from UserModel.find_by_jwt_token() and sets actor_id to user.id (or None if lookup fails). Constructs data dict with actorId, action, itemType='ACCOUNT', itemName, itemId, itemValue, orgId, remoteAddr, createdAt (from datetime.now()). Creates SimpleCloudEvent with id=uuid.uuid4(), source='sbc-auth-auth-api', subject=None, type=QueueMessageTypes.ACTIVITY_LOG.value, time=UTC ISO datetime, data=data dict. Publishes to CONFIG.AUTH_EVENT_TOPIC via queue.publish(GcpQueue.to_queue_message(event)). Catches Exception: logs to Sentry and current_app.logger, does not re-raise.

GOTCHA: createdAt uses naive datetime.now() while CloudEvent time uses UTC-aware datetime.now(tz=timezone.utc).

=== auth-api/src/auth_api/services/api_gateway.py ===

Service managing API gateway integrations with Keycloak-based authentication and authorization. Uses REST services with organization models and user context management to control access via groups (GROUP_ACCOUNT_HOLDERS, GROUP_API_GW_SANDBOX_USERS, GROUP_API_GW_USERS) and roles (ADMIN, STAFF). Class implementation not shown in provided content.

Manages API key generation and revocation for organizations to access API Gateway, with Keycloak client provisioning and environment-specific consumer management.

Inputs: org_id (int), request_json with environment (defaults 'sandbox'; or configured API_GW_CONSUMER_EMAIL) and keyName; api_key for revocation

Outputs: consumerKey list with apiKey, keyStatus, email, environment fields

Main flow: create_key checks if consumer exists via _consumer_exists email lookup. For new consumers: generates Keycloak client, adds service account to GROUP_API_GW_USERS (prod) or GROUP_API_GW_SANDBOX_USERS (sandbox) plus GROUP_ACCOUNT_HOLDERS, creates sandbox payment account with _create_payment_account (dummy bank values), POSTs consumer with Keycloak credentials. For existing: POSTs to /apikeys. revoke_key finds email_id from all keys or raises DATA_NOT_FOUND, PATCHes revoke endpoint. get_api_keys queries both environments per email, filters for keyStatus='approved' via _filter_and_add_keys.

Decisions: environment defaults 'sandbox', selects API_GW_KEY/API_GW_NON_PROD_KEY; _get_email_id returns configured value or org_id[-sandbox]@API_GW_EMAIL_SUFFIX; revoke/get auth requires ADMIN or STAFF; payment account skips if PAY_API_SANDBOX_URL unset; _get_api_consumer_endpoint returns API_GW_CONSUMERS_API_URL or API_GW_CONSUMERS_SANDBOX_API_URL per environment.

GOTCHA: org.has_api_access set before subsequent operations complete; no transaction guarantee.
GOTCHA: _create_payment_account hardcodes dummy values: bankInstitutionNumber '000', bankTransitNumber '00000', bankAccountNumber '0000000'.

=== auth-api/src/auth_api/services/flags.py ===

Wrapper service around LaunchDarkly's feature flag SDK, evaluating flags per user with graceful fallback.

Inputs: flag name (str), optional User object, optional default value. Outputs: boolean (`is_on()`) or flag value (`value()`).

Flow: On init, sets up LaunchDarkly client if `AUTH_LD_SDK_KEY` config exists or environment is not production. In testing, uses local flags.json file via Files data source; otherwise uses LaunchDarkly API. Query methods convert User to LaunchDarkly Context (with `idp_userid`, `firstname`, `lastname` fields) or create anonymous context, then call `client.variation(flag, context, default)`.

Decisions: (1) Initialize if SDK_KEY present OR not production; (2) If testing environment, load from flags.json, else use LaunchDarkly; (3) If client unavailable, log warning and return default.

GOTCHA: Service returns the default value (False for `is_on()` if unspecified) when LaunchDarkly is unreachable and no local config exists—no exception raised.

=== auth-api/src/auth_api/services/invitation.py ===

Service for managing invitation data in the auth API. Loads Jinja2 templates for email rendering with autoescape=True and application configuration via get_named_config. Coordinates Keycloak authentication, email publication via publish_to_mailer, Invitation and Membership models, InvitationStatus and InvitationType enumerations, Task creation, Activity logging, authorization checking (check_auth), and user roles (ADMIN, COORDINATOR, STAFF, USER).

=== auth-api/src/auth_api/services/keycloak.py ===

Keycloak administration utilities module that provides a service class for managing Keycloak identity operations. The file imports dependencies for async HTTP requests (aiohttp), synchronous requests, Flask context, exception handling (BusinessException), role constants (GROUP_ACCOUNT_HOLDERS, GROUP_ANONYMOUS_USERS, GROUP_GOV_ACCOUNT_USERS, GROUP_PUBLIC_USERS), enums for Keycloak operations (KeycloakGroupActions, LoginSource, ContentType), user context management, and a KeycloakUser integration class. The KeycloakService class is declared but its implementation is not shown in the provided content chunk.

Keycloak identity service: manages user group memberships, fetches users by role, and resets OTP credentials.

`add_or_remove_product_keycloak_groups` separates KeycloakGroupSubscription items by group_action (ADD_TO_GROUP or REMOVE_FROM_GROUP) and calls async `add_or_remove_users_from_group` for each batch. That fetches admin token (KEYCLOAK_ADMIN_USERNAME + KEYCLOAK_ADMIN_SECRET from config, or upstream KEYCLOAK_BCROS_* variants), looks up group IDs recursively (searching subGroups), then fires HTTP requests with aiohttp.TCPConnector(limit=40): PUT to add users, DELETE to remove. `get_user_emails_with_role` fetches users assigned a role and returns firstName, lastName, email. `_reset_otp` sets requiredActions=['CONFIGURE_TOTP'] then deletes credentials where type=='otp'. `_find_group_or_subgroup_id` recursively walks the groups tree.

GOTCHA: `add_or_remove_users_from_group` logs errors (ClientConnectionError, TimeoutError, Exception, non-204 status) but does not raise them; the function silently succeeds even if batch requests fail, and callers cannot detect partial failures.

=== auth-api/src/auth_api/services/keycloak_user.py ===

Wraps a Keycloak user dictionary, providing typed property accessors for fields (username, email, firstName, lastName, id, credentials, attributes, enabled) and managing required login actions.

Input: optional user dict. Output: JSON string of the user dict via `value()`.

Main flow stores user data and exposes properties: setting `user_name` defaults `first_name` to the username if unset; setting `password` creates a `credentials` array with `type='password'`; setting `attributes` copies key-value pairs into the dict. Methods `update_password_on_login()` and `configure_totp_on_login()` append `RequiredAction.UPDATE_PASSWORD.value` or `RequiredAction.CONFIGURE_TOTP.value` to `requiredActions` list, initializing the list if absent.

GOTCHA: `password` getter assumes `credentials[0]` exists—will raise `KeyError` or `IndexError` if credentials is missing or empty.
GOTCHA: `value()` returns JSON string but type hint declares `Dict`.

=== auth-api/src/auth_api/services/membership.py ===

Initializes the Membership service module, which manages organizational memberships for users. Sets up a Jinja2 templating environment (`ENV`) with FileSystemLoader and autoescape enabled, and retrieves application configuration (`CONFIG`) via `get_named_config()`. The module depends on Flask, Keycloak authentication, activity logging, email publishing, and product/user services to support membership operations between organizations and users.

=== auth-api/src/auth_api/services/minio.py ===

Wrapper for MinIO object storage that generates pre-signed upload and download URLs for documents.

create_signed_put_url takes file_name and optional prefix_key (defaults to AFFIDAVIT_FOLDER_NAME), extracts file extension by splitting file_name on '.' and taking the last part, generates key as f'{prefix_key}/{uuid}.{file_extension}', calls minio_client.presigned_put_object on MINIO_BUCKET_ACCOUNTS with 5-minute expiry, returns dict with 'preSignedUrl' and 'key' fields.

create_signed_get_url takes key, calls minio_client.presigned_get_object on MINIO_BUCKET_ACCOUNTS with 1-hour expiry, returns URL string.

_get_client reads MINIO_ENDPOINT, MINIO_ACCESS_KEY, MINIO_ACCESS_SECRET, and MINIO_SECURE from current_app.config, constructs and returns Minio instance.

GOTCHA: File extension extraction via split('.')[-1] fails silently on filenames without dots or produces unexpected results with multiple dots.

=== auth-api/src/auth_api/services/org.py ===

Service for managing Organization data in auth-api's authentication system. Works with Org, User, Membership, Contact, Task, and Affidavit models; validates access types, account limits, BCOL credentials, duplicate org names, and payment types; integrates services for users, contacts, products, tasks, affidavits, and Keycloak; tracks activity logging and publishes emails to mailer; enforces roles ADMIN and STAFF; manages status via OrgStatus, OrgType, PaymentMethod enums.

=== auth-api/src/auth_api/services/products.py ===

Service for managing Product and Product Subscription data. The file defines one constant, `QUALIFIED_SUPPLIER_PRODUCT_CODES`, holding three ProductCode values: `MHR_QSLN`, `MHR_QSHD`, `MHR_QSHM`. The `Product` class definition begins but contains no methods in the provided excerpt. Dependencies include SQLAlchemy for database queries, Keycloak integration via `KeycloakService`, task and activity logging services, and notification utilities. (Shown content is incomplete—no main flow visible.)

=== auth-api/src/auth_api/services/rest_service.py ===

Service module for making synchronous and asynchronous REST API calls with configurable retry logic and error handling.

Imports setup for sync (`requests`) and async (`aiohttp`) HTTP clients; exception types `ClientConnectorError`, `ReqConnectionError`, `ConnectTimeout`, `HTTPError`; Flask context (`current_app`, `request`); and utilities `AuthHeaderType`, `ContentType` enums and `cache` decorator. Defines `RETRY_ADAPTER`: HTTPAdapter with Retry policy of `total=5` retries, `backoff_factor=1`, and `status_forcelist=[404]` to retry on 404 responses. Main service methods not shown in this fragment.

Wraps HTTP requests (POST/PUT/PATCH/DELETE/GET) with OAuth 2.0 token extraction and error handling for Flask.

**Input**: endpoint URL, optional Bearer token (auto-extracted from current request Authorization header if absent), auth_header_type (AuthHeaderType.BEARER default), content_type (ContentType.JSON default), request body, additional_headers dict, boolean control flags.

**Output**: requests.Response object; ServiceUnavailableException on network error or 5xx response; HTTPError on other HTTP errors.

**Flow**: POST/PUT/PATCH/DELETE route through _invoke(rest_method) which generates headers (Content-Type, optional Authorization formatted with auth_header_type template, merged additional_headers), JSON-encodes body if needed, calls requests.METHOD() with CONNECT_TIMEOUT. GET has separate path with optional session retry and 404-log suppression. get_service_account_token() returns cached Keycloak OAuth token via client credentials grant. call_posts_in_parallel() async-POSTs to multiple URLs concurrently, aggregates JSON responses.

**Decisions**: 
- generate_token=True and token absent → extracts from Authorization header via _get_token()
- content_type=JSON → json.dumps() body
- Connection errors (ReqConnectionError, ConnectTimeout) → ServiceUnavailableException
- HTTPError with 5xx → ServiceUnavailableException; other status → re-raise HTTPError as-is
- GET with retry_on_failure=True → mounts RETRY_ADAPTER on session
- GET with skip_404_logging=True plus 404 status → skips error log (raises exception anyway)
- Parallel POST with non-OK response or ClientConnectorError → ServiceUnavailableException

GOTCHA: put() method signature and _invoke() call omit additional_headers and generate_token parameters, inconsistent with post/patch/delete. GOTCHA: put() docstring says "POST service", delete() docstring says "Patch service" (copy-paste errors). GOTCHA: _get_token() removes "Bearer " prefix without validating it exists.

=== auth-api/src/auth_api/services/task.py ===

Task service managing task operations with Jinja2-templated notifications. Initializes Jinja2 Environment (ENV) with FileSystemLoader('.') and autoescape=True for template rendering. Imports models (Task, User, Org, Membership), UserService, exceptions (BusinessException, Error), task enums (TaskStatus, TaskAction, TaskRelationshipStatus, TaskRelationshipType), and publish_to_mailer utility.

=== auth-api/src/auth_api/services/user.py ===

Provides user information management for BC government auth API; this is the imports and setup section only.

Imports models: User, Org, Membership, Contact, ContactLink and UserSchema; external services: KeycloakService, KeycloakUser, check_auth; internal services: ContactService, DocumentService, ActivityLogPublisher, publish_to_mailer; roles: ADMIN, CLIENT_ADMIN_ROLES, COORDINATOR, STAFF, Role; enums: AccessType, ActivityAction, DocumentType, IdpHint, LoginSource, OrgStatus, Status, UserStatus; utilities: UserContext, util functions. Creates ENV as Jinja2 Environment with FileSystemLoader('.') and autoescape=True. Apache 2.0 licensed.

=== auth-api/src/auth_api/services/validators/__init__.py ===

Package marker for the validators services module. The docstring declares intent to "Expose all of the Services used in the validator," but the file contains no imports or code implementing this—currently a placeholder.

=== auth-api/src/auth_api/status.py ===

Configuration file providing named HTTP status code constants and classification functions for readable code. Classification functions take integer codes and return boolean: true if code falls in 100–199 (`is_informational()`), 200–299 (`is_success()`), 300–399 (`is_redirect()`), 400–499 (`is_client_error()`), or 500–599 (`is_server_error()`). Named constants map status codes to identifiers: `HTTP_200_OK = 200`, `HTTP_404_NOT_FOUND = 404`, covering codes 100–511.

=== auth-api/src/auth_api/utils/api_gateway.py ===

Utility helper module to create API gateway client users. Imports `secrets` for cryptographic randomness and `uuid` for unique identifier generation. No function implementations provided in the shown content.

The file does not exist at the specified path, and only the function signature is provided without the implementation body. I cannot condense a function without seeing its actual code—what it contains, what decisions it makes, what it returns, and what could be dangerous about it. 

Please provide the complete function implementation or correct file path so I can deliver the condensed summary as instructed.

Generates API Gateway client credentials dictionary with unique identifier, secret token, and environment-specific client ID.

Generates _id from uuid4 (converted to string) and _secret from secrets.token_urlsafe(36). Conditionally appends '-sandbox' to client_id_pattern when env != 'prod'. Formats _client_id using client_id_pattern.format(account_id=account_id). Creates and returns client_json dictionary.

GOTCHA: Code snippet terminates at `client_json: dict =` — full dictionary structure and return statement not visible.

Configures a Keycloak OAuth2/OpenID Connect client for service account authentication to the API gateway. Dictionary injects _id, _client_id, _secret into id, clientId, secret. Disables all standard OAuth flows (standardFlowEnabled, implicitFlowEnabled, directAccessGrantsEnabled: False) while enabling serviceAccountsEnabled: True. Sets clientAuthenticatorType: 'client-secret', publicClient: False, enabled: True, fullScopeAllowed: True, protocol: 'openid-connect'. All SAML attributes: 'false'. redirectUris and webOrigins empty.

Keycloak OpenID Connect protocol mappers configuration that defines how user attributes, session data, and hardcoded values populate ID, access, and userinfo tokens for a client.

Incoming: `_client_id` variable and `account_id` (converted to string).

Outgoing: Dict with `protocolMappers` (list of 17 mappers), `defaultClientScopes` (['web-origins', 'roles']), and empty `optionalClientScopes`.

Mapper flow and decisions:
- **User session mappers** (oidc-usersessionmodel-note-mapper): Extract clientId, clientAddress, clientHost from session notes → id and access tokens.
- **Hardcoded claim mappers** (oidc-hardcoded-claim-mapper): Push _client_id into preferred_username, full name, username, given name, name, idp_userid; push 'API_GW' into loginSource; push str(account_id) into Account-Id—all route to userinfo, id, and/or access tokens.
- **User property mappers** (oidc-usermodel-property-mapper): Pull email and lastName from user attributes → userinfo, id, access tokens.
- **Role mappers**: realm roles (multivalued, access token only); role list (SAML, Basic format).
- **Audience mappers** (oidc-audience-mapper): Four service audiences (account-services, ppr-services, entity-services, business-search-service) → access token only.

GOTCHA: "given name" mapper writes _client_id to claim.name='lastname', not a given-name claim.
GOTCHA: "full name" and separate "name" mapper both hardcode _client_id to claim.name='name'—duplicate configuration.

=== auth-api/src/auth_api/utils/endpoints_enums.py ===

Defines named constants for endpoint paths used by the authentication API. EndpointEnum class provides four route paths: API_V1 = '/api/v1', API = '/api', TEST_API = '/test', with DEFAULT_API = API_V1. String enum members enable type-safe endpoint references throughout the auth API system.

=== auth-api/src/auth_api/utils/enums.py ===

Configuration file defining enumeration constants for the auth API system.

Provides 30+ enum classes mapping names to values: authorization schemes (BASIC, BEARER), HTTP content types, notification types, corporation types (NR, CP, BC, BEN, ULC, GP, SP, etc.), payment methods (CC, DRAWDOWN, DIRECT_PAY, PAD, EJV, EFT) and account statuses (CREATED, PENDING, FAILED), user/organization membership statuses, document types, access types (REGULAR, BCEID, EXTRA_PROVINCIAL, GOVM, GOVN), task relationship types (ORG, AFFIDAVIT, PRODUCT, USER), task statuses (OPEN, COMPLETED, HOLD, CLOSED), task action types (AFFIDAVIT_REVIEW, ACCOUNT_REVIEW, PRODUCT_REVIEW, QUALIFIED_SUPPLIER_REVIEW), activity actions, suspension reason codes, and queue sources. Most enums map string values; Status and UserStatus use integers (1-5). AffiliationInvitationType and PatchActions include from_value() classmethods checking _value2member_map_, returning None if value not found.

GOTCHA: from_value() returns None for unknown values—callers must handle None explicitly.
GOTCHA: Status uses integers (1-5) while nearly all others use strings, risking type confusion.
GOTCHA: OrgStatus and TaskRelationshipStatus define identical value sets.
GOTCHA: NRActionCodes marked FUTURE in comments (ASSUMED, RESTORATION, RESUBMIT) may be incorrect or unused.

=== auth-api/src/auth_api/utils/passcode.py ===

Hashes and validates passcodes using bcrypt, a utility module. `passcode_hash(passcode)` takes a string; if truthy, generates salt via `bcrypt.gensalt()`, hashes with `bcrypt.hashpw()`, encodes result as string; if falsy, returns None. `validate_passcode(passcode, hashed_passcode)` takes two strings; if both truthy, encodes both as bytes and returns `bcrypt.checkpw()` result; if either falsy, returns False.

GOTCHA: Type hint `passcode_bytes: str` incorrectly declares bytes from `.encode()`. Variable `hashed_passcod_bytes` appears to misspell the parameter name. Null-handling inconsistent: `passcode_hash()` returns None for falsy input, `validate_passcode()` returns False.

=== auth-api/src/auth_api/utils/roles.py ===

Configuration of roles and membership for access control. Roles: VIEWER, EDITOR, PUBLIC_USER, ACCOUNT_HOLDER, GOV_ACCOUNT_USER, ANONYMOUS_USER, ACCOUNT_IDENTITY, MANAGE_EFT, SYSTEM, TESTER, STAFF, STAFF_VIEW_ACCOUNTS, STAFF_MANAGE_ACCOUNTS, STAFF_SEARCH, STAFF_CREATE_ACCOUNTS, STAFF_MANAGE_BUSINESS, STAFF_SUSPEND_ACCOUNTS. Membership types: STAFF, COORDINATOR, ADMIN, USER. Valid statuses by type: person (ACTIVE, PENDING_APPROVAL, PENDING_STAFF_REVIEW); org (ACTIVE, NSF_SUSPENDED, SUSPENDED, PENDING_INVITE_ACCEPT, PENDING_STAFF_REVIEW); subscription (ACTIVE, PENDING_STAFF_REVIEW, REJECTED). Role groupings: CLIENT_ADMIN_ROLES=(COORDINATOR, ADMIN); CLIENT_AUTH_ROLES=(COORDINATOR, ADMIN, USER); ALL_ALLOWED_ROLES=(COORDINATOR, ADMIN, USER, STAFF). Excluded fields: status_code, type_code. Premium org types: PREMIUM, SBC_STAFF, STAFF.

=== auth-api/src/auth_api/utils/util.py ===

Utilities module providing helper functions for the auth API.

Includes: `camelback2snake()` and `snake2camelback()` convert dictionary keys between cases via humps library functions `decamelize` and `camelize`. `Singleton` metaclass enforces single instance per class, storing in `_instances` dict. `digitify()` extracts digits from a string and returns as integer using regex `\D`. `escape_wam_friendly_url()` base64-encodes a parameter, then URL-encodes it with `urllib.parse.quote` and `safe=''`. `mask_email()` splits on `@`, replaces characters beyond the first 2 in both username and domain with `*`; returns unmodified email if split doesn't yield exactly 2 parts. `get_request_environment()` returns `'sandbox'` if `FLASK_ENV` equals `'production'` AND `AUTH_WEB_SANDBOX_HOST` from config appears in `request.host_url`, else `None`. `extract_numbers()` joins digits from input string; returns `None` if input is `None`.

GOTCHA: `mask_email()` silently skips masking if email doesn't split into exactly two parts.

=== auth-api/tests/unit/services/test_minio.py ===

Unit test suite for MinioService—verifies pre-signed URL generation for uploads and downloads to Minio object storage.

Two tests: `test_create_signed_put_url` calls `MinioService.create_signed_put_url('affidavit-test.pdf', prefix_key='Test')`, checks the returned dict has 'key' starting with 'Test/' and ending '.pdf', and 'preSignedUrl'. `test_create_signed_get_url` creates a temp file, generates a PUT URL via `create_signed_put_url`, uploads via `requests.put(preSignedUrl, files=files)`, then calls `MinioService.create_signed_get_url(key)` and fetches via `requests.get(preSignedUrl)`. Both verify prefix_key is prepended to the object key and file extension is preserved.

GOTCHA: File handle opened but never closed.
GOTCHA: Upload and download requests never checked for success status.

=== pay-api/src/pay_api/utils/endpoints_enums.py ===

Configuration file defining enumeration constants for API endpoint route paths. EndpointEnum class extends str and Enum, providing four string values: API_V1 ('/api/v1'), API ('/api'), TEST_API ('/test'), and DEFAULT_API (defaults to API_V1). Used throughout the pay API to reference standardized endpoint prefixes consistently.
