<!-- leaf 64, 11 members -->

These condensations are all fragments of an OpenAPI spec's error-handling definitions. Most are repeats of the same error-response schema, and a few are related data-model pieces.

## Default error responses
This is one pattern, repeated four times. The default (unexpected error) response returns `application/json` and references `#/components/schemas/ErrorResponse`.

## 404 Not Found responses
This pattern appears four times in near-identical form. The body is a JSON object with two string properties: `code` (the error type identifier) and `message` (the error description).
- One variant defines identical `application/json` and `application/xml` schemas for the same `{code, message}` object.

## 400 Bad Request response
This is the same `{code, message}` object, defined inline for `application/json`. The schema description says "Contains details of an error".

## Shared schema definitions
- `ErrorResponse`: `{code, message}`, an error type identifier plus a description. The default responses reference it.
- `codes`: `{code, desc, defaut}`, an object with `x-example: {}`.
- `document`: `{content, type, version_id}`.

Caution:
- Neither `code` nor `message` is marked required in the 404 schemas. Callers must handle missing or null values.
- The 400 schema is described as "Contains details of an error", but its fields are `code` and `message`. There is no `description` field.
- The 404 response defines the same `{code, message}` schema separately for JSON and XML. Extract it to a shared `$ref`, or the two copies may drift apart.
- `codes` has a misspelled field, `defaut`, which should be `default`. It likely comes from the source data.

## Members

- sbc-auth: auth-api/docs/contract.yaml
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
