<!-- leaf 438, 9 members -->

This group is a set of condensed notes on a Python/Flask test suite for a business-registry API. The suite covers authorization, allowed filings and actions, and digital credentials. It also covers the shared JWT and OIDC test helpers.

## Endpoint authorization
**Unauthorized parties endpoint test**
- Create business `CP7654321` and mock `AUTH_SVC_URL` to return `{'roles': []}`.
- GET `/api/v2/businesses/{identifier}/parties` with the PUBLIC_USER header.
- Expect 401 with the message `'You are not authorized to view parties for CP7654321.'`

**Authorization test suite (6 parametrized cases)**
- `test_authorized_user` mocks `requests.Response` and runs the `@jwt.requires_auth` check. It expects the status given in `TEST_AUTHZ_DATA`.
- `TEST_INTEG_AUTHZ_DATA` scenarios:
  - `staff_role` and `colin_svc_role` expect OK.
  - `unauthorized_user`, `missing_action`, `invalid_action` and `add_comment_not_allowed` expect METHOD_NOT_ALLOWED.
- `test_authorized_user_integ` is the integration version. It mocks `flask.request.headers.get`.
- `test_authorized_missing_args`, `test_authorized_bad_url` and `test_authorized_invalid_roles` all expect `False`.

## Allowed filings and actions
These tests share one pattern. Each builds a JWT with roles and a username, monkeypatches `flask.request.headers.get` to return the Authorization header, then loops over `legal_types`. Each loop creates a business and asserts the result against `expected`.

- **`is_allowed()` test**
  - Params: test_name, state, filing_type, sub_filing_type, legal_types, username, roles, expected.
  - Calls `is_allowed(business, state, filing_type, legal_type, jwt, sub_filing_type, None)`.
- **`get_allowed_actions()` test**
  - Uses `get_allowable_actions(jwt, business)`.
  - Mocks `GET {AUTH_SVC_URL}/orgs/{account_id}/products?include_hidden=true`.
  - The comp-auth user (account '2') gets `[{'code': 'CA_SEARCH', 'subscriptionStatus': 'ACTIVE'}]`. Other users (account '1') get `[]`.
  - Asserts `filing.filingSubmissionLink`, `filing.filingTypes == expected`, and `viewAll == is_comp_auth`.
- **`get_allowed_filings()` parametrized test**
  - Params: test_name, business_exists, state, legal_types, username, roles, expected.
  - Builds the JWT with `helper_create_jwt()` and creates each business with `create_business(legal_type, state)`.
- **`test_allowed_filings_state_filing_check`**
  - A `validStateFiling` blocker shows a filing only if `business.state_filing` matches one of the `state_filing_types`.
  - An `invalidStateFiling` blocker shows it only if there is no match.
  - Setup optionally creates a filing and sets `business.state_filing_id`.

## Digital credentials
- **`are_digital_credentials_allowed()`** has 3 tests. It is false for type 'GP' and false if the user is not owner_operator. It is true for 'SP' with owner_operator=True.
- **`is_self_registered_owner_operator()`** has 8 tests. It is false when any of these holds:
  - There is no registration filing.
  - There are no proprietors.
  - There are no completing parties.
  - The party and user names don't match.
- It is true only when the proprietor name matches the user name. Matching is case-insensitive.
- Middle names are handled strictly. A proprietor with `middle_initial='TU'` matches only a user whose `firstname` is `'Test Tu'`.
- The tests use `@patch` decorators on `User.find_by_jwt_token` and the authz checks, plus manual JWT and header mocks in the test body.

## Test helpers
- **JWT helpers**
  - `STAFF_ROLE = 'staff'`.
  - `helper_create_jwt` builds a token with header alg RS256, typ JWT and kid `flask-jwt-oidc-test-client`.
  - The claims are iss `https://example.localdomain/auth/realms/example`, sub `43e6a245-0bf7-4ccf-9bd0-e7fb85fd18cc`, aud `example`, exp, iat, username, loginSource `IDIR`, and `realm_access.roles`.
  - `create_header` wraps the token in an `Authorization: Bearer` header.
- **Fake OIDC class**
  - `user_loggedin=True`.
  - `user_getfield(key)` returns 'Joe'.
  - `user_role()` returns None.
  - `has_access()` returns True.
  - `get_access_token()` returns 'any'.
  - `_get_token_info(token)` returns `{'roles': ['admin_view']}`.

Caution:
- An empty roles list in the auth mock yields 401, not 403. No role counts as unauthorized.
- `factory_business().save()` is implicit. The parties test doesn't create the row explicitly before mocking auth.
- Some authorization tests are marked `@not_github_ci`. Some use async declarations without awaiting results, so check promise handling.
- `monkeypatch` replaces `flask.request.headers.get` globally in the test context. The real request object is never used, only the mock.
- Comp-auth uses a different account_id ('2') because account product subscriptions are cached. Test order matters if mocked data is reused.
- The `get_allowed_filings` mock takes 2 args (one, two) and ignores the second. The same `expected` value is reused for every legal_type, so the test assumes homogeneous results. `business=None` is passed when `business_exists` is false.
- The state-filing test nests loops (legal_types × state_filing_types) but reuses one `expected`. It assumes all combinations give the same result, or that the test is parameterized externally.
- The digital credentials tests mock in two layers, decorators plus manual setattr, which makes the setup fragile. 'SP' is the passing business type and 'GP' fails. A proprietor `middle_initial` alone doesn't match unless the user's `firstname` also includes the middle name.
- The JWT exp and iat timestamps are hardcoded (valid until 2050). The token never expires in tests, so they won't catch expiry bugs.
- The fake OIDC `user_role()` returns None, not a role string. Callers must handle a falsy return.

## Members

- lear: legal-api/tests/unit/resources/v2/test_business_parties.py
- lear: legal-api/tests/unit/services/test_authorization.py
- lear: legal-api/tests/unit/services/test_authorization.py
- lear: legal-api/tests/unit/services/test_authorization.py
- lear: legal-api/tests/unit/services/test_authorization.py
- lear: legal-api/tests/unit/services/test_authorization.py
- lear: legal-api/tests/unit/services/test_authorization.py
- lear: legal-api/tests/unit/services/utils.py
- sbc-pay: pay-admin/tests/fake_oidc.py
