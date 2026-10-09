<!-- level 1, node 492, children [2, 5, 6, 38, 42, 59, 71, 72, 73, 76, 77, 87, 93, 102, 108, 109, 113, 124, 128, 135, 140, 161, 162, 182, 200, 212, 213, 214, 215, 216, 217, 227, 232, 233, 254, 255, 274, 275, 300] -->

# Parent brief: condensed notes on a bundled JavaScript dependency payload

This batch condenses one large browserified or webpack JavaScript bundle. It looks like the dependency tree of a Postman- or k6-style test sandbox and an AWS-signing client. Nearly everything is third-party library source, and most snippets are truncated. Module IDs are bundle-specific and change on rebuild. There are many duplicate or overlapping condensations. Two tiny items are unrelated: a JSON option fragment, and an HTML footer snippet.

## 1. Tiny, non-library fragments
- **`options.raw.language`:** 24 near-identical notes about the path `options` → `raw` → `language`. Twenty give `"json"` and four give `"text"`. The `"text"` fragments are incomplete JSON with no outer key and no closing braces. The source tool or config is unknown.
- **HTML footer:** a closing `</div>` plus a `<script>` setting `config = { pagination: true }`.
  - The `<script>` has no closing tag, so the snippet looks truncated.
  - `config` is global, with no namespace protection.
- **Spacer paragraphs:** empty or `&nbsp;` `<p>` tags used as vertical spacers.
  - They use an inline `margin-top` of 8, 16, 20 or 24px with `!important`.
  - One outlier is a border-based divider.
  - Notes disagree on whether paragraph height counts toward the gap.
  - Better practice is a CSS class, or margin and padding on adjacent elements.
- **Other stray items:**
  - A `load-testing` package manifest (v1.0.0a1.dev1), whose `postman-to-k6` script uses `@apideck/postman-to-k6`.
  - An Alembic migration, revision `dede70a6df1e`, that recreates `authorizations_view` and hard-codes `m.status = 1`.
  - A Nightwatch `elementCount` assertion.

## 2. Node core polyfills
- **Streams (`readable-stream`):** Readable, Writable, Duplex, Transform, PassThrough, BufferList, destroy/undestroy, async iterator, `eos`, `pipeline`, and the `Stream` compat module with its `pipe`.
  - Readable and Writable internals:
    - Readable uses `sync`, `flowing`, `awaitDrain`, an 8MB `MAX_HWM`, and `_read`.
    - Writable has the `cork`/`uncork` and `clearBuffer` write pipeline.
  - Gotchas:
    - A Transform hangs if `cb()` is never called.
    - Duplex defaults to `allowHalfOpen=true`.
    - `stdout` and `stderr` never emit `end`.
    - `highWaterMark` 0 is valid.
    - Some `_destroy` snippets are truncated.
- **events:** `EventEmitter` (default max listeners is 10, which only warns), `once`, `prependListener`, `removeListener`, and `rawListeners`. `objectKeysPolyfill` returns `k` instead of `keys`, which is a bug.
- **process shim:** a `nextTick` queue and cached `setTimeout`.
- **util and string_decoder:** type checks, deprecation wrapper, and `StringDecoder` (utf8, utf16le, base64, with U+FFFD on incomplete input).
- **buffer:** Feross's Buffer polyfill, `safe-buffer`, `base64-js`, `ieee754`.
  - Hex strings silently truncate at the first invalid character.
  - `utf8ToBytes` turns unpaired surrogates into `EF BF BD`.
  - `noAssert` disables bounds checks.
- **Other shims:** punycode 1.4.1, `String.fromCodePoint`, `inherits`, `Array.isArray`, `url` and `querystring` (`maxKeys` is 1000), `randomBytes` over `getRandomValues`, and an Object `getPrototypeOf`/`setPrototypeOf` polyfill.
- **UMD and Browserify wrappers:** `this`/`global`/`self`/`window` chains, `require('_process')`, and the `setImmediate` variant. Many are skeletons only, including aws4, lodash, chai, loupe, oauth1, papaparse and faker.

## 3. Crypto
- **CryptoJS:**
  - Cipher framework: cipher-core, CBC and PKCS#7, OpenSSL salt format (`Salted__`), `EvpKDF`, PBKDF2.
  - Hashes: MD5, SHA1/224/256/384/512, SHA-3, RIPEMD160.
  - Ciphers: AES, DES/TripleDES (EDE), Rabbit, RC4.
  - Gotchas: the default of 1 PBKDF2 iteration is weak, RC4 is broken, and AES key size is hard-coded.
- **bn.js:**
  - 26-bit words (mask `0x3ffffff`), `comb10MulTo`, `Red` and `Mont` reduction contexts, `divmod`.
  - Notes conflict on whether the FFT multiply path is enabled.
- **elliptic:**
  - Curves: `ShortCurve`, `EdwardsCurve` and `MontCurve`, with preset curves p192–p521, ed25519, curve25519 and secp256k1.
  - Techniques: wNAF, JSF, endomorphism, `eqXToP`.
  - Also EdDSA, `Signature` and `KeyPair`.
  - Opaque data: several arrays of 64-character hex pairs (`naf.wnd: 7` hints at NAF precomputation tables).
- **asn1.js:** DER and PEM codecs and the `Node` class.
- **Key exchange and RSA:**
  - Miller-Rabin and Diffie-Hellman (DH).
  - RSA `publicEncrypt` (OAEP hard-codes SHA-1).
  - Sign/verify modules 45–47.
  - An X.509 key parser.
- **Hashing and signing support:**
  - HMAC routing, `createHash`, HashBase and BlockHash.
  - `EVP_BytesToKey` (MD5) and PBKDF2.
  - A GCM/GHASH and AES-modes config table (also listed with the AES items).
- **AWS signing:**
  - `aws4` `RequestSigner` (Signature V4).
  - Bug: AES `scrubVec` increments `v` instead of `i`.
  - GCM tag check is described as timing-safe, but its boolean result is used.
  - ASN.1 `_decodeChoice` swallows errors.

## 4. Parsing and DOM stack
- **cheerio (1.0.0-rc.6) with:**
  - parse5: tokenizer, tree builder, adoption agency, `OpenElementStack`, location and error mixins, serializer, entities.
  - htmlparser2, `domhandler`, `domutils`, `dom-serializer`, `entities` encode/decode.
  - css-what and css-select, `nth-check`, cheerio-select positionals.
  - Also the cheerio API mixins (attributes, CSS, manipulation, traversal).
- **XML:**
  - `sax` (64KB buffer checks, namespaces).
  - `xml2js` (`defaults["0.1"]` and `["0.2"]` swap `attrkey` and `charkey`).
  - `xmlbuilder` (CoffeeScript-generated; `XMLDocumentCB`, `XMLNode`, `XMLWriterBase`, `XMLStringifier`, DTD nodes; many W3C DOM methods throw "not implemented"). `xml2Json` wraps `xml2js.parseString`.
- **Gotchas:** parse5's `AMBIGUOS_AMPERSAND_STATE` is misspelled, a bundle module (85) depends on itself, and `funescape` has a NaN-check quirk.

## 5. Validation and test tooling
- **Ajv (draft-07):**
  - Core:
    - Compiler (`new Function`), `compileAsync`, `$ref` resolution, formats, error classes.
    - Bundled URI/IRI and punycode libraries.
  - Keyword code generators:
    - Limits, `allOf`/`anyOf`/`oneOf`/`not`/`if`, `items`, `properties`, `required`, `uniqueItems`, `enum`, `format`, `$ref`, custom keywords.
    - Type coercion mutates the data and its parent.
  - Don't hand-edit generated code.
- **Chai 4.3.3:**
  - Parts: `expect`/`should`/`assert`, plugin API and utilities.
  - Deps: `deep-eql`, `loupe`, `pathval`, `type-detect`, `get-func-name`, `assertion-error`.
  - Config: `truncateThreshold` is 40.
  - Gotchas: many `.not` forms are ambiguous, and `should()` modifies `Object.prototype`.
- **Postman `pm` shim:**
  - Parts: variables, response assertion DSL, `require` limited to lodash, cheerio and crypto-js, `jsonPath`, and the `postman[Symbol.for('extend')]` registration.
  - Gotchas: `pm.sendRequest` and header access throw "not supported", and `jsonPath` uses `eval`.
  - Faker is part of this payload: `$`-prefixed dynamic variables, 148 locales (`LOCALES`), `DIRECTORY_PATHS`, and the `dynamicGeneratorsRegex`.
- **Faker.js:**
  - Generator modules: address, commerce, finance, internet, image providers, an IBAN validator (81 country formats), user-agent generator.
  - Locale data bundles: Czech, Slovak, German, Austrian/Swiss, Dutch, Spanish/Mexico, Italian, Portuguese/Brazil, Georgian, Russian, Swedish, Persian, Arabic, Azerbaijani, English and others.
  - Data quirks: the Dutch postcode `#### ??`, outdated German country names, Spanish typos, non-unique currency symbols. `#` is a literal digit placeholder, and `dup:` references make shared modules risky to edit.

## 6. General libraries
- **lodash 4.17.21:**
  - Internals: `runInContext` setup, helpers, and the `base*` implementations.
  - Wrappers: `LodashWrapper`, `LazyWrapper`, `createWrap`.
  - Public API: array, collection, function, lang, object, string, util and math methods.
  - Gotchas:
    - `reUnicode` and `reUnicodeWord` carry the `g` flag.
    - Many array methods mutate their input.
    - `template` uses the `Function` constructor.
    - `max`, `min`, `mean` and `sum` return `undefined` for an empty array.
- **jQuery 3.x:**
  - Parts: AJAX (prefilters, transports, `ajaxConvert`, `done()` handler, XHR/script/JSONP), Deferreds, attributes and props, animation, UMD wrapper.
  - Gotcha: under Node, `window` must be passed in.
- **Others:** an OAuth 1.0a client (the option `parameter_seperator` is misspelled), Papa Parse 5.3.2, and `LruCache`.

## 7. CodeMirror 5.27.4
- **Core:**
  - Styling CSS, UMD and plugin loaders, platform sniffing, DOM helpers.
  - Option registry, mode engine and `StringStream`.
  - Document model: B-tree chunks, `Doc`, history, marked text and folding.
  - Display pipeline, measurement, scrolling and scrollbars.
  - Operation batching with the R1/W1/R2/W2 phases, selection, bidi, keymaps, mouse and touch events, drag-drop.
  - Inputs: `TextareaInput` and `ContentEditableInput`.
  - Commands, indentation, paste handling, `fromTextArea`.
- **SQL mode:** one configurable tokenizer with MIME dialects: generic, MSSQL, MySQL, MariaDB, SQLite, Cassandra, PL/SQL, Hive, PostgreSQL and GQL.
- **Gotchas:** user-agent sniffing is fragile, `StringStream.match()` returns null for a non-zero match index, and `normalizeKeyMap()` mutates its input.

## Cross-cutting cautions
- Most of this is bundled or generated code. Edits need the original sources, a source map or a rebuild.
- Module IDs are unstable and differ between bundles.
- Heavy duplication and truncation mean no single snippet is authoritative.
