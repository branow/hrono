<!-- leaf 49, 8 members -->

This group of condensations describes test-fixture JSON for officer/director records in what looks like a corporate registry system (BC, Canada). The same material is repeated many times, and a few variants add related fixtures.

**Grouping 1: Director records with delivery and mailing addresses (repeated most often)**
- Two director records share appointmentDate `2019-11-21` and cessationDate `2019-11-25`. Each has delivery and mailing addresses with identical fields.
- Record 1:
  - Officer: firstName `TESTER4`, lastName `TESTING4`, middleInitial `T`.
  - addressId `103504803`.
  - Address: city `TEST CITY2`, region `BC`, country `CANADA`, street `TESTING TESTS STREET2`, postalCode `''`, deliveryInstructions `''`.
  - Event fields: startEventId `102095955`, endEventId `''`, title `''`.
- Record 2: addressId `103504804`, city `TEST CITY3`, street `TESTING TESTS STREET3`. The snippet is truncated mid-field.
- One shorter variant folds the same data into a single summary line (cities CITY2/CITY3, addressIds 103504803/103504804, streets STREET2/STREET3). It marks the second record as incomplete.

**Grouping 2: Filing-style officer records (one variant)**
- Three officer records are described, though only two are listed:
  - An `addressChanged` action dated 2018-01-01, role Director.
  - An `appointed` action dated `{{today}}`, role Appointed.
- Shared fields:
  - name `Test [LastName]`, partyType `person`.
  - Mailing address: country `CA`, postalCode `V8P1A1`, region `BC`.
- Only streetAddress differs, "address line change" versus "address line one".
- The text cuts off at `"business": {"identifier": "BC{{newCorpNum}}", "legalName`.

**Caution:**
- Delivery and mailing addresses are duplicated with identical data. Verify whether that is intentional or a data-entry error.
- All postal codes are empty strings, and it is unclear whether they are required.
- The JSON snippets are truncated mid-object or mid-field, so the second record is incomplete in each case.
- `{{today}}` is a placeholder used for the appointment date.
- In the filing-style records, the address fields are identical except for the street. This suggests copy-paste test data.

## Members

- lear: colin-api/tests/postman/colin-api.postman_collection.json
- lear: colin-api/tests/postman/colin-api.postman_collection.json
- lear: colin-api/tests/postman/colin-api.postman_collection.json
- lear: colin-api/tests/postman/colin-api.postman_collection.json
- lear: colin-api/tests/postman/colin-api.postman_collection.json
- lear: colin-api/tests/postman/colin-api.postman_collection.json
- lear: colin-api/tests/postman/colin-api.postman_collection.json
- lear: colin-api/tests/postman/colin-api.postman_collection.json
