<!-- level 1, node 508, children [4, 48, 61, 68, 104, 111, 112, 148, 150, 159, 188, 229, 268, 320, 372, 383, 384, 539, 540, 541, 555, 556, 557, 558, 580, 581] -->

# Parent brief: BC Government / BC Registries payments, billing and auth API specs

This group is a collection of condensed OpenAPI and JSON Schema fragments, test fixtures and a few code and config notes. They all belong to the BC Government payments and account ecosystem. Most items are truncated, stubbed or auto-generated, and many carry the same flaws.

## Subsystems and where to look

**1. CAS/CFS (PayBC / Oracle ORDS) customer-account API**
- Host: `heineken.cas.gov.bc.ca:7019/ords/cas/cfs/`, a test environment.
- Hierarchy: `/cfs/parties/{party_number}/accs/{account_number}/sites/{site_number}/…`
  - Children: `conts`, `invs` (with `adjs`), `rcpts` (with `apply` and `unapply`), `cms` and `payment`.
  - Other CFS paths: `/cfs/validatepayins/` and `/cfs/parties/invs/{inv_number}/creditbalance/`.
- PayBC paths: `/paybc/payment/{paybc_ref_number}/{transaction_number}`, `/paybc-service/oauth/token/` and `/paybc-service/api/refund`.
- Schemas: `Party`, `Acc`, `Site`, `Cont`, `Inv`, `Rcpt`, `Cms`, `PaymentDetails`, `Bank_info`, `RefundRequest`, `RefundResponse`, `TokenResponse` and `ErrorResponse`.
- Fixtures use the IDs party 11111, account 4101–4103, site 29921, contacts 1001–1003, invoices 10021–10023 and receipts 123451.
- The path stubs, parameter notes and HATEOAS link blocks are all in this family. Most stubs have no method detail or schemas.

**2. BC Registries Pay API (`pay-api`, v1.0.7)**
- Servers: `pay-api[-test].pathfinder.gov.bc.ca`.
- Paths:
  - `/api/v1/fees/{business_type}/{filing_type}`
  - `/api/v1/payment-requests[/{invoice_identifier}[/receipts|/refunds]]`
  - `/api/v1/accounts[/{accountId}/payments/queries|statements[/{statementId}]]`
  - `/api/v1/accounts/transactions`
- Behavior: the `Account-Id` header is required, the payment method is chosen server-side, DELETE and refunds return 202, and the 404 types are `INVALID_INVOICE_ID`, `INVALID_ACCOUNT_NUMBER` and similar constants.
- Schemas under `bcrs.gov.bc.ca/.well_known/schemas/`:
  - Payment request: `payment_request`, `payment_info`, `filing_info`, `filing_type`, `business_info`, `contact_info` and `account_info`.
  - Fees and accounts: `account_fee`, `account_fees`, the fee distribution code and the EFT patch.
  - Invoices: `invoice`, `invoices`, `invoice_reference`, `invoice_details`, `line_item` and `receipt`.
  - Transactions and notifications: `transaction`, `payment`, `refund`, `eft_payment`, the statement notification request, the Recipients schema, the comment schemas and the filter schemas.
  - Routing slips: `routing_slip`, the link and search requests, and the refund routing-slip and `refund_shortname` schemas.

**3. FAS routing-slip subsystem (Python `pay_api`)**
- Models: `RoutingSlip` and `RoutingSlipStatusCode`.
- Services: `RoutingSlip`, `RoutingSlipStatusTransitionService` and `Comment`.
- Background task: `RoutingSlipTask`, which handles CFS account creation, link, NSF, void and correction.
- Tests: endpoints under `/api/v1/fas/routing-slips`.
- Validation: the `_validate_linking` rules and the 9-digit check-digit routine.
- Roles: `FAS_VOID`, `FAS_CORRECTION` and `FAS_REFUND_APPROVER`. Refund and write-off authorizations return 202, and self-approval is blocked.
- Code quality: many classes suppress pylint warnings (`too-many-instance-attributes` and the like).

**4. BCOL (BC Online) integration**
- `bcol-api-1.0.0.yaml` (localhost:3000): `POST /profiles` and `POST /payments`.
- Schemas: `bconline_credential`, `accounts_request`, the payment request and response, `profile_response` and `bconline_response`, plus the `adress.json` address schema (the misspelling is part of the filename).
- Also in this subsystem: BCOL fixtures such as user PB25020 and account 180670.

**5. BC Registries auth / account API (`auth-api`)**
- Servers: `auth-api[-dev|-test].apps.silver.devops.gov.bc.ca`, with the Keycloak-backed `keycloakGuid`.
- Schemas: `org`, `org_response`, `orgs`, `paged_response`, `user`, `user_response`, `userSettings`, `membership`, `members`, `affiliation`, `affiliation_response`, `affiliation_invitation(s)`, `invitation(s)`, `affidavit`, `contact_response`, `business`, `entity`, `product(s)`, `codes`, `authorizations`, the org-product subscriptions, the task response, the API key, anonymous-user and bulk-user requests, and the terms of use and document schemas.
- Example payloads: orgs 852 and 2390, authorization fixtures CP0001234–CP0002000 and menu/account list items.
- Also in this subsystem: a Firebase hosting config for `bcregistry-account-dev` and an HTTP security-header and CSP config.

**6. OpenSSL / TSA config**
- An unrelated config: CA defaults, a proxy certificate and a timestamp authority with SHA-256.

## Recurring cross-cutting cautions

- **Truncation:** many fragments are cut off, including `Inv`, `Site`, `Contact`, `Org`, `Product`, `Entity`, `Transaction`, `line_item`, `account_response` and the invoice receipts. Get the full definitions before implementing.
- **No-op validation:** `^(.*)$` is on nearly every string and matches anything. Other defects:
  - `default: ""` is applied to booleans, numbers and enums.
  - `additionalProperties: true` is common.
  - `format` and `type` are duplicated.
  - Numeric IDs are strings.
  - Dates are plain strings. One uses `"format": "datetime"` rather than `date-time`.
- **Malformed structures:**
  - `additionalProperties` is placed inside `properties`.
  - `type: object` is combined with a `$ref`.
  - Arrays use `properties` or a wrong key instead of `items`.
  - `$id` values are copy-pasted or snake_case where the key is camelCase.
  - An array type is paired with an object default.
- **Copy-paste and placeholder data:**
  - Identical IDs and timestamps are reused across examples.
  - There are duplicated entries.
  - Descriptions are wrong, for example `InvoiceRef`.
  - The 404 for fees is labeled "Created".
  - Example paths are mismatched.
  - Typos such as `auccountId`, "adress", "reduntantFlag", "cerdentials", "gmai", "Columnbia" and "payment-requeasts" appear.
- **Trailing spaces in hrefs:** the CFS link blocks have them (`…/adjs/ `, `…/conts/1001/ `, `sites/ `, `rcpts/ `). They break strict URL parsing.
- **Money and format inconsistencies:**
  - Amounts mix `$`-prefixed strings, plain strings and numbers.
  - Negative fee strings and `'+00'` taxes appear.
  - The payment date example `'20191125:125330505'` doesn't match its format.
  - `Max-Age` is a string, with one oddly set to `'application:prod'`.
  - `refundedamount` is null while `postedrefundamount` is 31.50.
  - The `Rcpt.invoices` type is unclear.
- **Security:** `Access-Control-Allow-Origin: *`, CSP `unsafe-eval` and `unsafe-inline`, and hardcoded test hosts.
- **Semantic and API design oddities:**
  - A token GET with a non-standard `Basic-Token` header.
  - A PATCH described under `Parties_PUT`.
  - `/oauth/token` returns the `Party` schema.
  - `httpStatus` in a response body.
  - Both an `accountId` path param and an `Account-Id` header.
  - Account create and update PUT both return 201.
  - Async DELETE returns 202.
  - Empty `required` arrays and empty schemas, such as `account_info`.
- **Code behavior risks (FAS):**
  - The CFS account task swallows exceptions.
  - `total_usd` can be None.
  - CORRECTION silently downgrades the status.
  - There is a `Receipt` name collision on import.
- **External `$ref`s:** most schemas depend on `bcrs.gov.bc.ca/.well_known/schemas/*` URLs resolving, plus one relative `../../../` path.
