<!-- leaf 254, 14 members -->

This is a set of condensed module summaries from a browserified JavaScript bundle. It's mostly a crypto/ASN.1/X.509 stack (bn.js, elliptic, asn1.js, hash.js, node-dtls key parsing) plus a few general-purpose utilities.

## ASN.1 (asn1.js)
- **Core library**: exports `bignum`, `define`, `base`, `constants`, `decoders`, `encoders`. `Entity` lazily builds encoder/decoder pairs per encoding (default 'der'). `DecoderBuffer` and `EncoderBuffer` do the binary I/O, with save/restore for backtracking.
- **DER decoder**: `DERDecoder` and `DERNode` (`_decodeTag`, `_decodeList`, `_decodeStr`, `_decodeObjid`, `_decodeTime`, `_decodeInt` and others). Helpers `derDecodeTag` and `derDecodeLen` cover tags and short, long and indefinite lengths. `PEMDecoder` strips the armor, base64-decodes, then delegates to `DERDecoder`.
- **DER encoder**: `DEREncoder` and `DERNode` with `_encodeComposite`, `_encodeStr`, `_encodeObjid`, `_encodeTime`, `_encodeInt`, `_encodeBool`, `_encodeNull`, `_skipDefault` and `encodeTag`. It mirrors the decoder.

## Elliptic curve and number-theory crypto
- **EC**: constructor takes a curve name or `PresetCurve`. It provides `sign` (HmacDRBG nonce), `verify` (`mulAdd` or `jmulAdd`), `recoverPubKey` and a `KeyPair` wrapper with ECDH.
- **EdDSA Signature**: module 97, with lazily cached `R`, `S`, `Rencoded` and `Sencoded`, plus `toBytes` and `toHex`.
- **Shared utils**: `getNAF`, `getJSF`, `cachedProperty`, `parseBytes` and `intFromLE`.
- **Miller-Rabin**: `_randbelow`, `_randrange`, `test` and `getDivisor`, using Montgomery reduction.

## Hashing and low-level encoding
- **HMAC** (module 122) and **RIPEMD160** (module 123). The SHA variants (sha1–sha512) are only stubs.
- **Minimalistic utils**: UTF-8 and hex conversion, 32-bit word packing, and 32-bit and simulated 64-bit arithmetic and rotations.

## X.509 and key parsing
- **node-dtls key parser** (from Rantanen): `X509Certificate` struct and `parseKeys`. It handles CERTIFICATE, PUBLIC/PRIVATE KEY (pkcs1/pkcs8) and ENCRYPTED PRIVATE KEY (pbkdf2 plus AES). It identifies key types by OID: RSA, EC and DSA.

## General utilities
- **Containers and streams**: `LruCache` with `DoublyLinkedList`, and `BufferList`, a linked list with `consume`, `concat` and `join`. Stream destroy helpers are `destroy`, `undestroy` and `errorOrDestroy`.
- **Base64**: `byteLength`, `toByteArray` and `fromByteArray`, with URL-safe `-` and `_` accepted on decode.
- **URL**: `Url.prototype.resolveObject` merges base and relative URLs, including "psychotic" non-slashed protocols.
- **AWS request signing**: `RequestSigner` covers canonical and signed headers, credential string, env credentials and path parsing and formatting.

Caution:
- **ASN.1 buffers**: Lazy encoder/decoder creation means the first call pays the setup cost. `DecoderBuffer.isDecoderBuffer` checks `constructor.name` as a string, so it breaks across module boundaries or after bundler transpilation.
- **DER decoding**: The UTC time year pivot is 70 (00–69 → 2000s, 70–99 → 1900s). Indefinite-length encoding must be scanned to the END tag.
- **DER encoding**: `encodeTag` rejects multi-octet tags (≥0x1f). The second OID identifier must be below 40. Long-form length needs the 0x80 prefix (0x81 for 1 octet, 0x82 for 2).
- **LRU cache**: `set()` returns false when capacity is already 0, a dead state even after prune.
- **Base64**: Input length must be a multiple of 4 or it throws.
- **BufferList and streams**: `destroy()` sets `destroyed=true` before the `_destroy()` callback, so callbacks see the destroyed state. `_exportTextarea` is reused globally.
- **EC**:
  - `sign()` loops indefinitely generating k.
  - `genKeyPair()` rejects k ≥ n-1.
  - `recoverPubKey()` tries 4 recovery params and has a typo ('sencond key candinate').
  - `verify()` has two point-multiplication paths.
- **EdDSA signature**: This is minified bundle code. Validation only checks that R and S exist, not their types. Input can be an Array, Point or BN in any combination.
- **NAF/JSF utils**: These rely on bn.js methods and have no bounds validation for window size or bit length. Off-by-one or sign errors break EC crypto silently. Altering the `2 * d1 === u1 + 1` phase-shift condition breaks the algorithm.
- **HMAC**: The outer pad XOR is 0x6a (0x36 ^ 0x5c), applied in place to the key array. RIPEMD160 runs two 80-round paths in lockstep. Its lookup tables `r`, `rh`, `s` and `sh` must match the spec exactly. The summary cites RFC 1320, which is MD4's RFC.
- **UTF-8 and 64-bit math**: Surrogate pairs become 4 bytes, and other multibyte characters become 2–3. Carry propagation in `sum64_4` and `sum64_5` is manual and easy to get wrong.
- **Miller-Rabin**: `test()` and `getDivisor()` duplicate the (n-1)=2^s·d decomposition. The loop logic doesn't always return explicitly and relies on an outer prime flag.
- **Key parsing**: Decrypting an ENCRYPTED PRIVATE KEY needs the password, or parsing fails silently. The decrypted payload then falls through as a PRIVATE KEY.
- **URL resolution**: Non-slashed protocols like `mailto:` let relative paths climb above the root. Auth can end up stuck in the host field and needs extraction.
- **AWS signer**: The `parsePath` regex treats reserved characters as safe. Paths not already %-encoded can get double-encoded.

## Members

- lear: legal-api/tests/performance/libs/aws4.js
- lear: legal-api/tests/performance/libs/aws4.js
- lear: legal-api/tests/performance/libs/aws4.js
- lear: legal-api/tests/performance/libs/aws4.js
- lear: legal-api/tests/performance/libs/aws4.js
- lear: legal-api/tests/performance/libs/aws4.js
- lear: legal-api/tests/performance/libs/aws4.js
- lear: legal-api/tests/performance/libs/aws4.js
- lear: legal-api/tests/performance/libs/aws4.js
- lear: legal-api/tests/performance/libs/aws4.js
- lear: legal-api/tests/performance/libs/aws4.js
- lear: legal-api/tests/performance/libs/aws4.js
- lear: legal-api/tests/performance/libs/aws4.js
- lear: legal-api/tests/performance/libs/aws4.js
