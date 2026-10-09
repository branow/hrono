<!-- leaf 45, 9 members -->

These condensations describe database fixture records of SBN (Small Business Number) hub submissions to the CRA (Canada Revenue Agency). They were logged by `BN_HUB` between 2023-01-01 and 2023-01-11. Each record is a tuple holding a file ID (`FM…`), a record ID, an action type, truncated request XML, a response or error, a status or retry code, timestamps, and flags. Nearly every record is a failure. The failures fall into two error families, one per action type.

**Error family 1: CHANGE_\* actions blocked before a Business Number exists**
- **Actions:** CHANGE_NAME, CHANGE_STATUS, CHANGE_MAILING_ADDRESS, CHANGE_DELIVERY_ADDRESS, and CHANGE_PARTY in one batch.
- **Error:** "Cannot inform CRA about this change before receiving Business Number (BN15)." The request XML must supply `businessRegistrationNumber`, `businessProgramIdentifier` and `businessProgramAccountReferenceNumber`.
- **Pattern:** The error is the same for every change type. The response is instant (about 0.04s) and `retry_cnt` is 0. Request types are SBNChangeName (documentSubType 103), SBNChangeAddress (107 for delivery, 108 for mailing) and SBNChangeStatus.
- **Examples:** FM0362085, FM0535428, FM0177850, FM0548588, FM1007385 (mailing address) and FM0474632 (status). One requestor, FM0134195, filed a NAME, DELIVERY and MAILING trio (IDs 10710–10712).

**Error family 2: INFORM_CRA rejected for `lastName` length**
- **Error:** `[ISC.0082.9465] Value is longer than maximum length`. It is returned as an `SBNErrorNotification` (documentSubType 901) pointing at `/owner/ownerIndividual/lastName`.
- **Pattern:** The request is an `SBNCreateProgramAccountRequest` (requestMode=A, documentSubType 000). `retry_cnt` or `status_code` is usually 9.
- **Examples:** FM1006814, FM1006850, FM1006857, FM1006859, FM1006865, FM1006870, FM1007002, FM1007004, FM1007005, FM1007027, FM1007064, FM1007070, FM1007072, FM1007073, FM1007077, FM1007078, FM1007386 and FM1007432.
- **Business types:** The records span unrelated businesses (couriers, lawyers, wineries, dentists, publishers, breweries, immigration, video game design, food supplements and private households).

**Record-format variants**
- **Column naming:** The same tuple is labelled differently across sources: `fileID/seqNum`, `corp_num/msg_id`, `file_ref/id`, and `tracker_errors` with `is_active=False` and `deleted=False`.
- **Timestamps:** They are UTC, usually `psycopg2.tz.FixedOffsetTimezone(offset=0)`.
- **Dates:** The date ranges are Jan 1–7, Jan 4–5, Jan 5, Jan 7–10 and Jan 10–11.
- **Repeats and links:** A file ID can repeat across rows (FM0257452 appears twice). Some rows link to user IDs such as 1182213, 1283303, 1282960–1283029 and 1521627.

Caution:
- The `lastName` error appears across many unrelated businesses, so it points to a systemic schema or length-constraint problem, not bad data in individual records.
- BN15 errors are logged with `retry_cnt=0`, so there is no automatic retry. The request XML has to be fixed and resubmitted manually. The system still queues change requests that cannot succeed until a BN is assigned.
- The same underlying problem can surface through different paths. Some rows show an explicit BN message, while others show status 9 with a null or XML-wrapped response.
- Error responses are XML-wrapped notifications, not plain text.
- `retry_cnt=9` on INFORM_CRA rows with no `doc_id` means the message was never persisted to the document table.
- Request and response XML are truncated (`... (NNNN characters truncated) ...`), so full payloads cannot be reconstructed from these fixtures.
- Parse the timezone objects explicitly, because they are `FixedOffsetTimezone` objects and not strings.

## Members

- lear: jobs/entity-bn/tracker-errors.ipynb
- lear: jobs/entity-bn/tracker-errors.ipynb
- lear: jobs/entity-bn/tracker-errors.ipynb
- lear: jobs/entity-bn/tracker-errors.ipynb
- lear: jobs/entity-bn/tracker-errors.ipynb
- lear: jobs/entity-bn/tracker-errors.ipynb
- lear: jobs/entity-bn/tracker-errors.ipynb
- lear: jobs/entity-bn/tracker-errors.ipynb
- lear: jobs/entity-bn/tracker-errors.ipynb
