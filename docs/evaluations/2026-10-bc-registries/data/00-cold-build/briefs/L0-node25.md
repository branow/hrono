<!-- leaf 25, 12 members -->

This is a set of Postman prerequest-script notes about setting date environment variables. Almost every entry is the same note repeated, and a couple vary it.

## Main pattern: `today` as YYYY-MM-DD (repeated about 9 times)

The script sets the `today` environment variable to the current date as `YYYY-MM-DD`. It builds the string from `new Date()` and zero-pads the month and day with `('0'+value).slice(-2)`. One variant spells out the full expression: `getFullYear() + '-' + ('0'+(getMonth()+1)).slice(-2) + '-' + ('0'+getDate()).slice(-2)`. The month needs `+1` because `getMonth()` is zero-based.

## Variation: hard-coded fixture dates (1 entry)

One script does the same `today` computation and also sets two fixed environment variables:
- `cessationDate` = '2019-09-05'
- `appointmentDate` = '2019-08-04'

Only `today` is regenerated on each run. The other two are static test fixtures.

## Caution:
- The `('0'+value).slice(-2)` padding works for current dates. It breaks for years ≥ 9999. It also gives the wrong result if the `Date` object's timezone differs from the local time you expect.
- The padding relies on string coercion and slicing. Refactoring it to plain string concatenation breaks it.
- `cessationDate` and `appointmentDate` are hard-coded constants, not computed. They will go stale, unlike `today`.

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
