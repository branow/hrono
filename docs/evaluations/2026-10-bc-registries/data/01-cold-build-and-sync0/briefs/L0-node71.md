<!-- leaf 71, 20 members -->

This is a set of condensed notes on a minified, browserified Faker.js bundle (with some Postman dynamic-variable glue). It covers the generator API, the helper and validation modules, and a large body of locale data. Most of it is bundler output, so the notes describe module contents rather than readable source.

## Groupings

**1. Postman dynamic variables (top-level code)**
- The code imports faker and defines `LOCALES` (148 BCP 47 tags taken from Chromium `l10n_util.cc`) and `DIRECTORY_PATHS` (57 paths from `/Applications` to `/var/yp`). It cuts off at `const dynamicGenerators =`.
- `dynamicGenerators` has 50+ entries, each shaped `{description, generator: faker.module.method}`. The `$`-prefixed keys are:
  - Core and ID: `$guid`, `$timestamp`, `$isoTimestamp`, `$randomInt` (1–1000), `$randomUUID` (36 characters), `$randomPassword` (15 alphanumeric characters), `$randomLocale`, `$randomWords` (2–5 words).
  - Phone: `$randomPhoneNumber` and `$randomPhoneNumberExt`.
  - File paths: `$randomFilePath` and `$randomDirectoryPath`.
  - Category families: address, commerce, company, database, date, finance, hacker, image URLs, internet, lorem, name, random and system.
- A regex builder turns the keys into `{{key}}` patterns joined by `|`, escapes `[${}]`, compiles the result with the global flag and exports it as `dynamicGeneratorsRegex`.

**2. Faker API surface (generator modules)**
- Address, commerce, company, database and date, plus the `fake` templating engine (`{{module.method(args)}}`).
- Finance, git, hacker and helpers:
  - Finance covers account numbers, routing numbers, masks, currency, bitcoin/litecoin/ethereum addresses, credit cards, IBAN, BIC and transaction descriptions.
  - Git covers branch, commit entries and messages, and SHAs (40-hex and 7-hex).
  - Hacker covers abbreviation, adjective, noun, verb, ingverb and phrase.
  - Helpers include `randomize`, `slugify`, the symbol replacers, `regexpStyleStringParse`, `shuffle`, `mustache` and the card/transaction builders.
- Internet: avatar, email, exampleEmail, userName, protocol, url, domain parts, ip/ipv6, userAgent, color, mac and password.
- Random and system generators, including vehicle data (manufacturer, model, type, fuel, VIN, color), seeded by a Mersenne Twister.
- Image providers (modules 13–17):
  - `image()` picks from 13 categories.
  - picsum.photos supports seed, grayscale and blur.
  - lorempixel and Unsplash are also supported.
  - Module 17 is the main Faker constructor, which holds locales, a fallback locale and lazy-loaded services.
- User-agent generator: picks a browser by weight (Chrome 0.451, IE 0.275, Firefox 0.194, Safari 0.062, Opera 0.016), then a platform, then builds the string.

**3. IBAN validator (module 12)**
- It holds 81 country formats, each with `{country, total, bban:[{type,count}], format}`. The types are `n` (numeric), `c` (alphanumeric) and `a` (letters).
- It also holds an `iso3166` list of 246 codes, plus `mod97` and `toDigitString` (A=10 … Z=35).

**4. Locale data bundles (Browserify modules)**
Each locale is a set of small modules for names, addresses, phone formats and so on.

| Locale | Modules | Contents |
|---|---|---|
| Czech | 88 | 1000+ city names, "Abertamy" to "Žulová" |
| German | 122–141+ | Name templates, phone patterns, 16 states, 200+ country names |
| Australia, Ocker, Bork, Canada, Great Britain, Ireland, India | 347–400+ | Streets, names, provinces/counties, postcodes, phone formats |
| Spanish | 443–462 | Building numbers, 100+ cities, 249 countries, 52 provinces, 42 street suffixes, 97 timezones, `6##` mobile phones; also adjectives, materials, products, names and business suffixes |
| Georgian | not given | 9 phone patterns, company suffixes and name patterns, domains and free-mail providers |
| Portuguese | not given | Last names, titles, phone formats, 200+ cities, commerce, month and weekday names |
| Russian | 998–1010 | Name templates, 72 phone formats, 47 cities, 200+ countries, apartment format |
| Swedish | 1123–1137 | Address, company, internet, name, phone, commerce, team and date data |

## Caution:
- **Chromium source:** the `LOCALES` comment points at a Chromium GitHub line that may have changed.
- **Path conventions:** `DIRECTORY_PATHS` mixes Unix/Linux, BSD (`/rescue`) and macOS (`/Applications`, `/Library`, `/System`, `/Users`, `/private/*`) paths.
- **Phone generators:** `$randomPhoneNumber` uses `format(0)` to exclude extensions. `$randomPhoneNumberExt` prepends a random prefix manually. Don't mix them up.
- **Naming inconsistency:** `fullName` uses the older `faker.name.findName`. `$randomPassword` is exactly 15 characters and `$randomUUID` is 36.
- **Regex escaping:** the escaping turns `$`, `{` and `}` into literals. Keys containing those characters match literally, not as grouping operators.
- **`nearbyGPSCoordinate()`:** the boolean parameter is `isMiles` (true means miles, false means km).
- **Helpers module:** the code is minified and its license is unknown. `regexpStyleStringParse` mutates its input string.
- **IBAN data:** the `bban` array and `format` string must stay in sync by hand. Format abbreviations are undocumented. CS and SU appear twice in `iso3166`. Total length includes the 2 check digits, and the notes give actual BBAN length as total − 4.
- **Image providers:**
  - The minified variable names obscure the logic.
  - placeimg uses HTTP and the others use HTTPS.
  - Grayscale and blur work only on picsum.
  - The Unsplash query regex is strict, and invalid queries are silently dropped.
- **Internet module:** `userName()` hides its internal pattern choices. With `memorable=true`, `password()` negates its pattern parameter.
- **Bundling artifacts:** module IDs, `dup:` references and `arguments[4][39][0].apply` chains are Browserify output and not stable identifiers. Changes require rebundling, and a source map is needed to debug.
- **German data:** the country list has outdated entries such as "Jugoslawien" and "ehemalige jugoslawische Republik Mazedonien".
- **Spanish data:** phone formats are hardcoded to the 6-prefix mobile standard. "lérida" is lowercase while other provinces are title-case.
- **Phone placeholders:** `#` in phone formats is a literal placeholder that the generator must substitute with digits.
- **Seeding:** the random module's seed defaults to a timestamp, so it is predictable. Regex and array conversions inside closures make the code fragile to modify.
- **User agents:** generated strings don't guarantee real OS and browser version pairings, so parsing them for detection will fail on many outputs.

## Members

- lear: legal-api/tests/performance/libs/shim/dynamic.js
- lear: legal-api/tests/performance/libs/shim/dynamic.js
- lear: legal-api/tests/performance/libs/shim/dynamic.js
- lear: legal-api/tests/performance/libs/shim/dynamic.js
- lear: legal-api/tests/performance/libs/shim/faker.js
- lear: legal-api/tests/performance/libs/shim/faker.js
- lear: legal-api/tests/performance/libs/shim/faker.js
- lear: legal-api/tests/performance/libs/shim/faker.js
- lear: legal-api/tests/performance/libs/shim/faker.js
- lear: legal-api/tests/performance/libs/shim/faker.js
- lear: legal-api/tests/performance/libs/shim/faker.js
- lear: legal-api/tests/performance/libs/shim/faker.js
- lear: legal-api/tests/performance/libs/shim/faker.js
- lear: legal-api/tests/performance/libs/shim/faker.js
- lear: legal-api/tests/performance/libs/shim/faker.js
- lear: legal-api/tests/performance/libs/shim/faker.js
- lear: legal-api/tests/performance/libs/shim/faker.js
- lear: legal-api/tests/performance/libs/shim/faker.js
- lear: legal-api/tests/performance/libs/shim/faker.js
- lear: legal-api/tests/performance/libs/shim/faker.js
