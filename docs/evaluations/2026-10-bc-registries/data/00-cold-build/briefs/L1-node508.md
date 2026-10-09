<!-- level 1, node 508, children [4, 48, 61, 68, 104, 112, 148, 150, 159, 184, 188, 228, 229, 320, 358, 372, 383, 384] -->

# Brief: BC Government payments, CFS and registries API specs and fixtures

These are condensed fragments of OpenAPI specs, JSON Schema (draft-07) contracts and test fixtures for BC Government payment, account and registry systems. Most are truncated mid-definition, and many are duplicated. Verify full contracts before relying on any fragment.

## Systems covered, for routing

**1. CAS/CFS customer-hierarchy API (PayBC, CFS)**
- Paths: `/cfs/parties/{party_number}/accs/{account_number}/sites/{site_number}/…`
  - Resources under a site: `conts`, `invs` (with `adjs`), `rcpts` (with `apply` and `unapply`), `cms`, and `payment`.
  - Other paths: `/paybc/payment/{paybc_ref_number}/{transaction_number}` (GET), `/paybc-service/oauth/token/`, `POST /oauth/token`, `POST /paybc-service/api/refund`, `POST /cfs/validatepayins/`, `POST /cfs/parties/invs/{inv_number}/creditbalance/`.
- Most path stubs have no methods or schemas. Methods seen are POST, PUT and a few GETs.
- Path parameters are required strings. Examples are party 11111, account 4101, site 29921, contacts 1001–1003, and receipts 10021–10023 or 123451–123453.
- PayBC API Reference v1.0.0 schemas: Party, Acc, Site, Cont, Rcpt, Inv, Cms, PaymentDetails, Bank_info, RefundRequest and RefundResponse, TokenResponse, ErrorResponse and Link.
- The test host is `heineken.cas.gov.bc.ca:7019/ords/cas/cfs/…`. Fixtures are HATEOAS-linked party, account, site and contact records.
- Issues seen:
  - Hrefs with trailing spaces.
  - Amount strings with a `$` prefix.
  - Placeholder or duplicated examples.
  - `refundedamount` null while `postedrefundamount` is 31.50.
  - A GET token endpoint, and `POST /oauth/token` returning a `Party` schema.

**2. BCOL (BC Online) integration**
- Endpoints: `POST /profiles` and `POST /payments`, served from `bcol-api-1.0.0.yaml` at `localhost:3000`.
- Request schemas: credentials and `accounts_request` (userId, password), and a payment request (feeCode, userId, invoiceNumber, …).
- Response schemas: `bconline_response` and `profile_response.json`, which refs `adress.json` (misspelled; it must resolve as written).
- Examples: account 100670 or 180670, user PB20020 or PB25020, and `profileFlags` such as OSBR, PPR and VS.
- Issues seen:
  - Typos: "cerdentials", "reduntantFlag", "Desciption".
  - Empty gst/pst status fields whose descriptions say "Must-Pay".
  - Payment amounts as signed strings.
  - A payment date example containing a colon.

**3. BC Registries Pay API (v1.0.7, `pay-api.pathfinder.gov.bc.ca`, JWT, Account-Id header)**
- Fees: `GET /api/v1/fees/{business_type}/{filing_type}`.
- Payment requests: `/api/v1/payment-requests` (with `/{invoice_identifier}`, `/receipts` and `/refunds`).
- Accounts: `/api/v1/accounts` (with `transactions`, `statements` and `payments/queries`).
- Related schemas:
  - `payment_request`, `business_info`, `filing_info`, `filing_type` (`waiveFees` is staff-only), `payment_info`, `bank_data`.
  - `account_info`, `account_fee`, `invoice`, `line_item`, `receipt`, `refund`, `transaction`.
  - `payment`, `eft_payment`, and the filter and search requests.
  - Statement notification and comment schemas.
- Errors:
  - ErrorResponse types include `INVALID_INVOICE_ID`, `INVALID_ACCOUNT_NUMBER`, `INVALID_STATEMENT_ID` and `INVALID_CORP_OR_FILING_TYPE`.
- Notes:
  - CORS is `*` with Max-Age `'3600'` as a string.
  - DELETE returns 202.
  - Statements are fetched via `Accept` as PDF or CSV.
- Issues seen: a mislabeled 404, malformed schema structure, wrong `$id` values, and typos such as `auccountId`.

**4. Routing slips (FAS)**
- Schemas: `routing_slip` (9-digit number), link request, search request, refund routing slip, and `refund_shortname`.
- Code: the model, service and task, plus status transitions (ACTIVE, COMPLETE, NSF, VOID, CORRECTION, LINKED and the refund and write-off states).
- Endpoint tests: `/api/v1/fas/routing-slips`.
- Routing slip rules:
  - `_validate_linking` runs six checks plus a status blacklist.
  - A 9-digit checksum is applied.
  - Refund approvals can't be self-approved.
  - Roles: FAS_VOID, FAS_CORRECTION and FAS_REFUND_APPROVER.
- Issues seen:
  - The task swallows exceptions.
  - `total_usd` null handling.
  - A silent downgrade on CORRECTION.
- Pylint-suppression stubs cover many models and services: Payment, Invoice, DistributionCode, FeeSchedule, PaymentAccount, PaymentTransaction, RefundService, DirectPayService and others.

**5. Auth API (sbc-auth, Keycloak-backed, `auth-api[-dev|-test].apps.silver.devops.gov.bc.ca`)**
- Schemas and examples:
  - Org, user and userSettings schemas, plus membership and invitation fragments.
  - Account, organization, affiliation, affidavit, user, contact and task response schemas.
  - Request schemas: anonymous or bulk user, API key, org product subscription, terms of use, and mailing address.
  - Products, codes and roles, fee distribution, and corp_type.
- Authorization fixtures: orgs CP0001234–CP0001239 and CP0002000, with roles view, edit and make_payment.
- Account list examples: PREMIUM and BASIC, USER_PROFILE and CREATE_ACCOUNT.
- Tags: codes, documents, entities, invitations, Meta, orgs, token, users.
- Password and username patterns are defined here.

**6. Web-app hosting and security config**
- A Firebase hosting config with an SPA rewrite for `bcregistry-account-dev`.
- A CSP and security-header block. It includes `'unsafe-eval'` and `'unsafe-inline'` in `script-src`, and `Access-Control-Allow-Origin: *`.

**7. Unrelated: OpenSSL/TSA config**
- Contains CA defaults, extensions and policies, TSA policy OIDs, sha256 signing, and TLS 1.2 with SECLEVEL=1.

## Cross-cutting patterns and cautions
- **Catch-all patterns:** nearly every string field uses `default: ""` and the no-op pattern `^(.*)$`, so nothing is validated. `additionalProperties: true` is common.
- **External refs:** schemas ref `https://bcrs.gov.bc.ca/.well_known/schemas/*`, and validation depends on those URLs resolving.
- **Copy-paste errors:** many `$id` values and titles are wrong, including `$id`s that duplicate a sibling and a title that says "first name" on a last-name field.
- **Truncation and gaps:**
  - Many definitions are cut off or empty. Examples include `Inv`, `Contact`, `Org`, `Product`, `Entity`, the Task schemas, `invoice`, `line_item`, `transaction`, and the empty `paths` in the PayBC spec.
  - Do not assume these contracts are complete.
- **Placeholder and test data:** the fixtures share ids, timestamps, hosts and names, and some contain leaked placeholders such as "None None".
- **Type mismatches:** numeric-looking IDs and amounts are strings. Booleans default to `""`. A pattern is placed on numbers.
- **Naming drift:** camelCase and snake_case mix, and `$id` values differ from property keys.
