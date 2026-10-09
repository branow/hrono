<!-- leaf 188, 6 members -->

This group is a set of condensed technical config and API-spec fragments from two unrelated sources. One is an OpenSSL/TSA configuration. The other is a partial OpenAPI 3.0.0 spec (`bcol-api-1.0.0.yaml` v1.0, server `http://localhost:3000`) for a BC Online (BCOL) profile and payment API.

## OpenSSL / TSA configuration

**Core and CA setup**
- Globals are `HOME=.`, `oid_section=new_oids` and `openssl_conf=default_conf`.
- CA defaults use `dir=./demoCA`, with subdirectories `certs`, `crl`, `newcerts` and `private`, plus serial tracking.
- `req` uses `string_mask=utf8only`.

**Extensions and policies**
- `usr_cert` sets `basicConstraints=CA:FALSE`, `subjectKeyIdentifier=hash`, `authorityKeyIdentifier=keyid,issuer` and an `nsComment`.
- `v3_ca` sets `basicConstraints=critical,CA:true`, `subjectKeyIdentifier=hash` and `authorityKeyIdentifier=keyid:always,issuer`.
- `crl_ext` sets `authorityKeyIdentifier=keyid:always`.
- `policy_match` requires a match on countryName, stateOrProvinceName and organizationName.
- `policy_anything` makes everything optional except commonName, which must be supplied.
- The proxy certificate extension is `proxyCertInfo=critical,language:id-ppl-anyLanguage,pathlen:3,policy:foo`.

**Timestamping (TSA)**
- The TSA policy OIDs are `tsa_policy1=1.2.3.4.1`, `tsa_policy2=1.2.3.4.5.6` and `tsa_policy3=1.2.3.4.5.7`.
- `tsa_config1` points at `$dir/tsaserial`, `$dir/tsacert.pem` and `$dir/private/tsakey.pem`.
- It signs with `sha256`. Its default policy is `tsa_policy1`, and `tsa_policy2` and `tsa_policy3` are the other allowed policies.
- It accepts the digests `sha1`, `sha256`, `sha384` and `sha512`.
- Its accuracy is `secs:1,millisecs:500,microsecs:100`.

**SSL**
- `MinProtocol=TLSv1.2` and `CipherString=DEFAULT@SECLEVEL=1`.

## BCOL API (OpenAPI)

All three endpoints use `application/json`, and their schemas are `$ref`s into `../../../bcol-api/src/bcol_api/schemas/schemas/`.

| Endpoint | Schema | Notes |
|---|---|---|
| `POST /profiles` (`verify_profile`, returns `200`) | `profile_response.json` | The request body uses `accounts_request.json`. The example sends `userId="test"` and `password="password"`. |
| `POST /payments` (returns `200 OK`) | `payment_response.json` | |

- **Profile example:** the response is for userId `PB25020`, account `180670`, authCode `M`, accountType `B`, and user "BRIDGER, JULIE". The org is "BC ONLINE TECHNICAL TEAM DEVL" with orgType `LAW`.
  - It includes a phone, a fax and a Victoria-area BC address (postal code V8X 5J8).
  - `profileFlags` has 16 entries: OSBR, ADS, COLIN_TYPE, COMP, ICBC, MH, LTO, SES, PPR, VS, CCREF, CCREL, ATSOURCE, COURT_SERVICES, EMERGIS and LOCATION_CODE.
- **Payment example:** `statutoryFee '-700'`, `tsFee '-150'`, `totalAmount '-850'`, `gst '+00'`, `pst '+00'`, account `180670`, user `PB25020`, `feeCode BSH105`, `key TEST` and `sequenceNo '0001'`. The date is `'20191125:125330505'`.

## Caution:
**OpenSSL config**
- Leave `crlnumber` commented out to produce a V1 CRL (Netscape compatibility).
- `unique_subject=no` allows multiple certificates with an identical subject.
- `copy_extensions=copy` is disabled by default as a caution flag.
- Old Netscape browsers crash on BMPStrings and UTF8Strings, despite the `utf8only` mask.
- `proxyCertInfo` must be present and critical for proxy certificate support. The config comment stresses this is mandatory.

**OpenAPI spec**
- The filename in the title doesn't match typical OpenAPI convention.
- The spec is incomplete and truncated.
- The schema paths use relative traversal (`../../../`), which is fragile if the file moves.
- The request example is stringified JSON, not a native object.
- In the profile example, `gstStatus` and `pstStatus` are empty strings, but `gstStatusDesc` and `pstStatusDesc` say "Must-Pay".
- Payment fee fields are negative strings (such as `'-700'`) and GST/PST are positive-zero strings (`'+00'`), so parse them as numbers carefully.
- The payment date format is `YYYYMMDDHHmmssSSS` with no delimiters. The example value `'20191125:125330505'` contains a colon, so it doesn't match that format.
- `key: 'TEST'` suggests the payment data is mock or test data.

## Members

- sbc-pay: bcol-api/scripts/openssl.cnf
- sbc-pay: bcol-api/scripts/openssl.cnf
- sbc-pay: docs/docs/api_contract/bcol-api-1.0.0.yaml
- sbc-pay: docs/docs/api_contract/bcol-api-1.0.0.yaml
- sbc-pay: docs/docs/api_contract/bcol-api-1.0.0.yaml
- sbc-pay: docs/docs/api_contract/bcol-api-1.0.0.yaml
