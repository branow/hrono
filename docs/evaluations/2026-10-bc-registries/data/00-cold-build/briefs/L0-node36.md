<!-- leaf 36, 23 members -->

This group is a set of roughly two dozen near-duplicate condensations of the same Postman request fragment. Every one is cut off, so none contains a usable request definition.

**Common content (all entries)**
- Method: `POST`
- Header: `Content-Type: application/json` (one entry notes `type: text`)
- Body: `mode: raw`, with the body value truncated or missing

**Variations in how the truncation is described**
- **Skeleton wording:** "Postman POST request skeleton… content incomplete." This is the most frequent form.
- **Fragment wording:** "Incomplete JSON Postman request object fragment… Unable to condense incomplete data."
- **Truncated mid-body:** "Incomplete Postman request: `POST`… JSON truncated mid-body."
- **Cut off at the raw value:** "Section incomplete—truncated at 'raw' value." These entries say the body payload is missing and the schema should be verified before the template is used.
- **Bare or minimal:** one entry has only the method and header, one has only the raw body mode, and one reads "POST request fragment… body: [truncated/missing]."

**Missing from every entry**
- The URL
- The actual JSON payload
- Any field names

Because of this, the endpoint and the purpose of the request cannot be recovered from the group.

Caution:
- The body is truncated mid-definition in most entries, so the snippet is unusable or non-functional as-is.
- Some entries say the body is cut off mid-field and will fail if executed. Verify the full payload before running anything.
- One entry notes the excerpt is likely part of a larger Postman request definition.
- One entry notes intent cannot be inferred from the fragment alone.
- The body payload is missing from the "raw"-truncated entries. Confirm the expected schema before using them as a template.

## Members

- lear: colin-api/tests/postman/colin-api.postman_collection.json
- lear: colin-api/tests/postman/colin-api.postman_collection.json
- lear: colin-api/tests/postman/colin-api.postman_collection.json
- lear: colin-api/tests/postman/colin-api.postman_collection.json
- lear: colin-api/tests/postman/colin-api.postman_collection.json
- lear: colin-api/tests/postman/colin-api.postman_collection.json
- lear: colin-api/tests/postman/colin-api.postman_collection.json
- lear: colin-api/tests/postman/colin-api.postman_collection.json
- lear: colin-api/tests/postman/colin-api.postman_collection.json
- lear: colin-api/tests/postman/colin-api.postman_collection.json
- lear: colin-api/tests/postman/colin-api.postman_collection.json
- lear: colin-api/tests/postman/colin-api.postman_collection.json
- lear: colin-api/tests/postman/colin-api.postman_collection.json
- lear: colin-api/tests/postman/colin-api.postman_collection.json
- lear: colin-api/tests/postman/colin-api.postman_collection.json
- lear: colin-api/tests/postman/colin-api.postman_collection.json
- lear: colin-api/tests/postman/colin-api.postman_collection.json
- lear: colin-api/tests/postman/colin-api.postman_collection.json
- lear: colin-api/tests/postman/colin-api.postman_collection.json
- lear: colin-api/tests/postman/colin-api.postman_collection.json
- sbc-auth: docs/keycloak-client-postman/collection.json
- sbc-auth: docs/keycloak-client-postman/collection.json
- sbc-auth: docs/sso-client-creator/Keycloak SSO Client Creation.postman_collection.json
