<!-- leaf 178, 8 members -->

**What this is:** A partial Postman collection, "passcode user importer" (`_postman_id` 2afef774-29c4-49bb-a634-c1992c7685ed, schema v2.1.0). It gives sample requests for creating a user through the Keycloak REST Admin API. The `item` array is incomplete, so some endpoint definitions are missing.

**Groupings**

1. **Admin authentication**
   - **Refresh token request:** POST `/auth/realms/{{realm_name}}/protocol/openid-connect/token` with `grant_type=refresh_token`. It uses `{{adminClientId}}`, `{{adminRefreshToken}}` and `{{adminClientSecret}}`. Its test script saves `adminToken` and `adminRefreshToken` to the environment.
   - **Pre-request token script:** Calls `pm.sendRequest` to the token URL with basic auth and `grant_type=client_credentials`. It stores `adminToken` and `adminRefreshToken` in both `pm.environment` and `pm.variables`, and has a `getvar(name)` helper that throws on undefined variables.
   - **Collection-level auth:** OAuth2 with `accessToken={{adminToken}}`, sent in the header.

2. **User provisioning** (all under `/auth/admin/realms/{{realm_name}}/`)
   - **Create user:** POST `users` with `username={{corp_num}}`, `enabled=true`, and attributes `corp_type=["{{corp_typ_cd}}"]` and `source=["PASSCODE"]`.
   - **Get user id:** GET `users?username={{corp_num}}`. The test script saves `jsonData[0].id` as `userId`.
   - **Update password:** PUT `users/{{userId}}/reset-password` with `{"type":"password","value":"{{temp_password}}","temporary":false}`.

3. **Group assignment**
   - **Get group id:** GET `group-by-path/{{defaultGroup}}`. The test script saves `id` as `groupId`.
   - **Assign group to user:** PUT `users/{{userId}}/groups/{{groupId}}`.
   - **User groups lookup:** GET `users/{{userId}}/groups`. Its test script also sets `groupId` from `response.id`.

4. **Session and identity**
   - **"Logout admin":** GET `/auth/realms/{{realm_name}}/protocol/openid-connect/userinfo` with Bearer `{{adminToken}}`.

**Pattern across requests:** Every request is built from `{{base_url}}` and `{{realm_name}}`. The requests pass values along through environment variables: `adminToken`, then `userId`, then `groupId`. Each step depends on the one before it.

**Caution:**
- The collection payload is truncated, so endpoint definitions are missing.
- The refresh-token test assumes `access_token` and `refresh_token` exist in the response. It fails silently if they are missing.
- These variables must be set in the Postman environment beforehand: `{{adminClientId}}`, `{{adminRefreshToken}}`, `{{adminClientSecret}}`, `{{base_url}}` and `{{realm_name}}`. The pre-request script's error ("Variable is not defined. Do you forget to select an environment?") points to the same requirement.
- "Get user id" assumes the response is an array with at least one element. An empty result or a missing `.id` leaves `userId` undefined, and the later requests fail silently.
- The password is set with `"temporary": false`, so it is not temporary even though it is sent to a reset endpoint.
- "Update password" and "Assign group to user" use `userId` from an earlier request. If that request fails or is skipped, they use a stale or undefined value.
- "Get group id" sets `groupId` only on a 200 response. After an error, "Assign group to user" fails silently with a 404.
- The request named "Logout admin" makes a userinfo GET. It does not log out or revoke anything.
- `{{adminToken}}` must be populated when the request runs, or auth fails.
- Tokens are stored in both `pm.environment` and `pm.variables`. This duplication is deliberate.

## Members

- sbc-auth: docs/passcode_importer/passcode_importer.postman_collection.json
- sbc-auth: docs/passcode_importer/passcode_importer.postman_collection.json
- sbc-auth: docs/passcode_importer/passcode_importer.postman_collection.json
- sbc-auth: docs/passcode_importer/passcode_importer.postman_collection.json
- sbc-auth: docs/passcode_importer/passcode_importer.postman_collection.json
- sbc-auth: docs/passcode_importer/passcode_importer.postman_collection.json
- sbc-auth: docs/passcode_importer/passcode_importer.postman_collection.json
- sbc-auth: docs/passcode_importer/passcode_importer.postman_collection.json
