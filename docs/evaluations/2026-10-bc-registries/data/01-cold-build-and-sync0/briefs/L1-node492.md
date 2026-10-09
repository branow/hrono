<!-- level 1, node 492, children [2, 5, 6, 38, 42, 59, 71, 72, 73, 87, 93, 108, 109, 113, 124, 135, 140, 162, 182, 200, 212, 213, 214, 216, 227, 232, 254, 255, 528, 529, 534, 535, 551, 552, 559, 560, 561] -->

# Parent brief: bundled JS dependency stacks (Browserify/webpack), plus small stray items

This batch is mostly condensed notes on browserified or webpack-bundled JavaScript libraries. Module IDs are bundle-specific, not stable. Most snippets are minified or truncated, and many entries repeat.

## Stray and trivial items
- **`options.raw.language`:** 24 near-identical notes on one JSON setting.
  - 20 say `"json"`.
  - 4 say `"text"`, written as the incomplete fragment `"options": { "raw": { "language": "text" } }`.
  - The source tool is unknown.
- **HTML snippets:**
  - A footer with a closing `</div>` and a script setting `config = { pagination: true }`. The `<script>` has no closing tag, and the scope of `config` is unclear.
  - Empty or `&nbsp;` `<p>` spacers using inline `margin-top … !important` (8–24px). The gap arithmetic differs between notes.
- **Unrelated items:**
  - An Alembic migration (`dede70a6df1e`) that recreates `authorizations_view` with `WHERE m.status = 1`.
  - A `load-testing` manifest that converts Postman collections to k6 with `@apideck/postman-to-k6`.
  - A Nightwatch `elementCount` assertion.
  - An `xml2Json` wrapper around `xml2js`.

## Node core polyfills
- **Streams (`readable-stream`):** Readable, Writable, Duplex, Transform, PassThrough, the Stream/pipe compat module, `BufferList`, async iterator, `eos`, `pipeline`, and destroy helpers.
  - Flow control: `highWaterMark`, `sync`, `awaitDrain`, cork/uncork, `_writev` batching.
  - Gotchas:
    - Transform hangs if `cb()` is never called.
    - `Symbol.hasInstance` is used for the Duplex check.
    - stdout/stderr never emit `end`.
    - `allowHalfOpen` defaults to true.
- **EventEmitter:**
  - `_events` plus `emit` fast paths.
  - A single listener is stored as a function, then promoted to an array on the second add.
  - Exceeding 10 listeners only warns.
  - `objectKeysPolyfill` returns `k` instead of `keys` (bug).
- **`buffer` (Feross), `safe-buffer`, `base64-js`, `ieee754`, `String.fromCodePoint`:**
  - `noAssert` skips bounds checks.
  - Hex decoding truncates at the first invalid character.
  - Lone surrogates become U+FFFD.
  - `__proto__` on Uint8Array fails in Firefox 4–29 and IE10.
- **Other core pieces:** `StringDecoder`, the `util` type checks (which avoid `instanceof` on purpose), the `process` shim (`nextTick` queue), `url`, `querystring` and `punycode`, `randomBytes`, `util-deprecate`.
- **UMD and loader wrappers:** `(this, require('_process'), global||self||window||{})`.
  - Export names include aws4, lodash, chai, loupe, oauth1, Papa and faker.
  - Almost all are truncated.

## Crypto stack
- **CryptoJS:**
  - Core, WordArray, encoders, MD5, SHA1/224/256/384/512 and SHA-3.
  - RIPEMD160, EvpKDF, PBKDF2 (default 1 iteration, weak) and AES.
  - DES/3DES (EDE), modes (CBC, CFB, CTR, CTRGladman, ECB, OFB), paddings, Rabbit and RC4.
  - Load order matters (SHA224 needs SHA256 first), and constants are transcription-sensitive.
- **Node crypto polyfills (browserify):**
  - Ciphers: AES/GCM, DES, CipherBase.
  - Hashes: SHA, MD5, RIPEMD160, HMAC.
  - KDFs: EVP_BytesToKey and PBKDF2.
  - Public-key and key exchange: RSA (OAEP, hardcoded SHA-1), Diffie-Hellman, ECDH, Miller-Rabin.
  - Serialization: ASN.1 (asn1.js) with DER/PEM, and X.509 key parsing.
  - Also AWS SigV4 (`aws4`).
  - Flagged bugs:
    - AES `scrubVec` has an infinite-loop bug.
    - `xorTest` is not constant-time.
    - The `credentialsCache` has no TTL.
- **bn.js:**
  - 26-bit words, so every mask and constant assumes that width.
  - Algorithms: `comb10MulTo`, `bigMulTo` (the FFT path is disabled), Knuth division, Red/Mont/MPrime reduction (K256, P25519), Tonelli-Shanks.
- **elliptic:**
  - Curves: short Weierstrass (endomorphism), Edwards, Montgomery.
  - Scalar multiplication: wNAF/JSF.
  - Preset curves: p192 through p521, curve25519, ed25519, secp256k1.
  - Also ECDSA signatures (DER) and EdDSA.
  - Also several arrays of 256-bit hex pairs with unknown purpose. One carries `naf.wnd: 7`, which suggests precomputed NAF points.

## HTML/XML/CSS stack (cheerio family)
- **Cheerio v1.0.0-rc.6:**
  - Core, attributes, traversal and manipulation.
  - Gotchas: radio/checkbox default `'on'`, `uniqueSplice` identity loss, `unwrap` skips body.
- **Parsing:**
  - parse5: tokenizer, tree builder, insertion modes, adoption agency, formatting list, location and error mixins, serializer, constants and doctype quirks.
  - htmlparser2: Parser, tokenizer, DomHandler, node classes and feed handler.
  - `entities` encode/decode and name-case maps.
- **Querying and output:**
  - css-what: selector parser and stringifier.
  - css-select: compiler, filters, positionals, pseudos.
  - nth-check, domutils and dom-serializer.
- **sax, xml2js and xmlbuilder (CoffeeScript 1.12.7):** XML parsing and building.
  - sax: 64KB buffer limit, state machine, namespaces.
  - xml2js: `defaults` 0.1 vs 0.2 swap attrkey and charkey.
  - xmlbuilder: the DOM node classes are largely stubs that throw.

## Validation, assertion and data libraries
- **Ajv (draft-07):**
  - API: compile, `compileAsync`, formats.
  - Per-keyword code generators emit JS strings. All of it runs through `new Function`.
  - Also the uri-js and punycode helpers and fast-deep-equal.
- **Chai v4.3.3:**
  - BDD (`expect`/`should`) and TDD (`assert`) interfaces.
  - Utilities: `assertion-error`, `deep-eql`, `loupe`, `type-detect`, `pathval`, `get-func-name`.
  - Gotchas: `.own` and `.nested` can't be combined, negation is ambiguous in several places, `should` modifies `Object.prototype`.
  - A Postman `pm` to k6 shim: `pm.test` wraps `k6.check`, `jsonPath` uses `eval`, and several `pm` APIs throw "not supported".
- **Faker.js and Postman dynamic variables:**
  - `dynamicGenerators` with `{{$…}}` regex.
  - An IBAN validator and image/user-agent generators.
  - A very large body of locale data (cs, sk, de, es, it, nl, ru, sv, pt, ar, az, fa, en and more). Heavy `dup:` module references. Phone formats use `#` placeholders.
  - Known data defects: Spanish typos, an invalid Dutch postcode format, outdated German country names.
- **Lodash 4.17.21:**
  - `lodash()` chain wrapper, `LazyWrapper`, caches, `createWrap` bitmasks.
  - Public array, collection, object, string and math methods. Type predicates and converters.
  - Internal `base*` helpers.
  - Gotchas:
    - `reUnicode` is a global regex.
    - `debounce`/`memoize` semantics.
    - Mutating methods: `fill`, `pull*`, `remove`, `reverse`, `merge`, `set`.
    - `template` uses `with` and `Function`.
    - Empty-array `max`/`min`/`mean`/`sum` return `undefined`.
- **Others:**
  - `Papa Parse` 5.3.2.
  - `oauth-1.0a` (option typo `parameter_seperator`).
  - `LruCache` with a doubly linked list.
  - Object prototype polyfill.

## Cross-cutting cautions
- Bundler output is minified and often truncated, so no single snippet can be fully assessed. Edit the source and rebuild, not the bundle.
- Module IDs, `dup:` references and `arguments[4][N][0].apply` chains are fragile identifiers.
- Numeric state constants, bitmasks and hex tables are error-prone. A single transcription error silently breaks hashes, ciphers or parsers.
- Security hotspots:
  - `new Function`/`eval` use (Ajv, lodash `template`, `jsonPath`).
  - Weak primitives: MD5-based KDF, RC4, 1-iteration PBKDF2.
  - The `should` prototype modification.
  - The non-constant-time GCM tag comparison.
