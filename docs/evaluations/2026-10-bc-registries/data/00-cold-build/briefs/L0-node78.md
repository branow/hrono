<!-- leaf 78, 9 members -->

This group is a set of repeated condensations of one BC (British Columbia) cooperative registry record: CENTRAL INTERIOR COMMUNITY SERVICES CO-OP (identifier CP0001965). The condensations restate the same three parts in turn (the business record, the registered office, and two officer records) and overlap heavily.

**Business record (eventId 102095978)**
- Legal type CP (cooperative), jurisdiction BC, state ACT (active), businessNumber null.
- Founded 2004-04-28; last AGM 2018-11-05; last annual report 2018-12-31; last ledger timestamp 2019-12-13T22:44:29.
- Registered office (officeCode RG): 51 4TH AVENUE SOUTH, WILLIAMS LAKE, BC V2G 1J6, CANADA. Delivery and mailing addresses are identical, with addressId 103332862.

**Officer records (two, repeated in several condensations)**
- Both condensations give the officers' address as 2046 MCPHERSON WYND, WILLIAMS LAKE, BC V2G4V7, addressId 103339247. Delivery and mailing are identical.
- Officer 1 is named inconsistently: ROBERT IAN MCLAUGHLIN in one condensation and KIRSTEN STARK in another. Both give startEventId 101990169. One shows cessationDate null.
- Officer 2 has appointment date 2017-11-23 in one condensation and 2009-09-21 in the other. The latter lists addresses 103339247 and 103339248, with postal code V2G2W5 and city "WILLIAM LAKE".
- Several fields are empty strings, and one snippet is cut off.

**Caution:**
- The delivery and mailing addresses share one addressId (103332862). They are not independent copies, so an update or mutation could affect both.
- The officer records have duplicate address objects, empty fields and a truncated snippet, so the data looks incomplete. The same addressId on both records is unusual.
- The city is spelled WILLIAMS LAKE in some records and WILLIAM LAKE in others. It is unclear whether this is a data error or intentional, so downstream code must handle both.
- The condensations disagree on the officers. Officer 1 is named differently, and Officer 2 has two different appointment dates. Verify against the source record before relying on any of these.

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
