<!-- leaf 387, 15 members -->

These condensations all come from the test suite and fixtures of a BC Registries legal-filings and email-notification system. They cover fixture builders, an email-processing function, CloudEvents-style queue messages, and pytest tests for the email and queue workers.

## Filing fixtures and data helpers
- **Static filing JSON:**
  - `COD_FILING`: identifier CP1234567, 5 directors with actions none, nameChanged, ceased, addressChanged and appointed.
  - `COD_FILING_TWO_ADDRESSES`: a changeOfDirectors filing dated 2019-07-29 with 2 directors, each with a delivery address. Descriptions disagree on mailing addresses. One says both directors have them. Another says only director1 does.
  - `COMBINED_FILING`: an annualReport (2019-07-28) that merges `COD_FILING` directors with `COA_FILING` office addresses.
- **Model helpers:** `create_filing`, `create_business`, `create_office`, `create_business_address`, `create_director`. The older versions uppercase name and address fields before saving. `create_business` is also described with `legal_type` and `legal_name` parameters and a DELIVERY address.
- **Test utilities:**
  - `Obj` and `dict_to_obj` round-trip dicts through JSON.
  - `create_mock_message` builds a Mock with a random sequence number, data and a decode method.
  - `create_batch` makes an INVOLUNTARY_DISSOLUTION batch in PROCESSING status.
  - `create_furnishing` makes an EMAIL furnishing in QUEUED status and creates the business if needed.
  - `create_party_role` builds a Party and PartyRole from an officer dict.

## Filing-prep functions (`prep_*`)
These share one pattern. Each deep-copies a template, sets the business identifier and placeholder emails, sets `payment_completion_date = filing_date`, saves, and creates a test_user submitter. For COMPLETED (or `bn`) options they also create a transaction through `versioning_manager.unit_of_work()`.
- **Type-specific builders:**
  - Consent continuation out, continuation out, restoration (adds `r_type`, default `fullRestoration`), and change of registration (branches on SOLE_PROP vs PARTNERSHIP).
  - Alteration, maintenance (uses `FILING_TYPE_MAPPER`), continuation in, and amalgamation.
  - Incorporation correction, firm correction (SOLE_PROP vs PARTNERSHIP), and CP special resolution.
  - Two CP special-resolution corrections: one for rules and one for the memorandum upload.

## Email processing (`process(email_info, token)`)
It builds the notification email:
- It loads the template `BC-{FILING_TYPE_CONVERTER[filing_type]}-{status}.html` and renders it with Jinja2.
- It gets PDF attachments through `_get_pdfs()` and recipients through `get_recipients()`.
- It builds a subject that varies by filing type and status.
- Special cases: incorporationApplication+PAID uses the name request and temp registration number, and alteration adds the staff, completing-party or user email to the recipients.
- It returns `{recipients, requestBy, content: {subject, body, attachments}}`.

## Queue event payloads
CloudEvents-like `(key, event_dict)` tuples share one schema: specversion `1.x-wip`, type, source, id, an empty `time`, datacontenttype, identifier and data.
- **Event families:**
  - Name requests (`bc.registry.names.request`): options before-expiry, expired, renewal, upgrade, refund, plus an nr_pay payment variant.
  - Dissolution (`bc.registry.dissolution`): sent by furnishingsJob.
  - Affiliation (`bc.registry.affiliation`) and business-number move (`bc.registry.bnmove`).
  - Email events: types such as alteration, annualReport and amalgamationApplication, with options PAID, COMPLETED, reminder and others.
- **Key format:** type + option + filingId, for example `alteration_COMPLETED_1112223333` and `amalgamationApplication_COMPLETED_111222335`.

## Pytest tests
- **Email content:**
  - Special resolution (PAID and COMPLETED).
  - CP special resolution correction (cp_sr@test.com), tested twice.
  - AR reminder and business-number emails.
  - Name-request notifications across 5–6 options, plus the NR receipt and incomplete-payload tests.
  - Involuntary dissolution stage 1 (6 cases).
- **Message processing (async):**
  - Subscription-handler tests for COMPLETE skipping, FAILED on QueueException or EmailException, retry success, and the retry cap at seen_count 6.
  - A parametrized exception-handling test and a test that `process_email` is patched.
- **Queue-to-email integration:** passcode reset, statement notification, payment reminder and payment due, each with `send_email` patched.

## Caution:
- **Undefined references:** `COMBINED_FILING` references `COA_FILING`, which is not defined in the snippets, so parsing will crash. `default_names_array` is also used in a parametrize but not defined.
- **Typos and syntax:**
  - `prep_alteration_filing()` has the typo 'legalype' for 'legalType'.
  - The `test_process_correction_cp_sr_email` parametrize `('PAID')('COMPLETED')` is missing a comma.
- **Silent failures in `process()`:**
  - An unmapped filing_type or invalid status in `FILING_TYPE_CONVERTER` silently fails to load the template.
  - Alteration email concatenation breaks if recipients is None.
  - `additional_info` is only populated for alteration.
- **Hardcoded values:** the placeholder emails, the test_user name and `temp_identifier` 'Tb31yQIuBw' are fixed regardless of the real user. `prep_firm_correction_filing` sets `party['officer']['email']` three times. `prep_amalgamation_filing` mixes an enum value with the literal `'bn'` in its status check.
- **Weak or misleading tests:**
  - One test patches `process_email` but never asserts it was called.
  - Another patches `_get_pdfs` to return an empty list despite mocking PDF responses.
  - `CCC_CONTINUE_IN` with `specialResolution` has no email validation.
  - The passcode-reset test uses different `isStaffInitiated` flags but identical assertions.
- **Asymmetric or fragile behavior:**
  - The INVALID_NAME dissolution case skips `send_email` and stays QUEUED, so its exception tests are asymmetric.
  - EmailException is re-raised while other exceptions are swallowed, and last-error formats differ by type.
  - Tuple keys must match the exact type+option+filingId format.
  - `time` is always empty.
  - Dissolution events appear twice with the same id but different `furnishingName` values.

## Members

- lear: queue_services/common/tests/unit/__init__.py
- lear: queue_services/entity-emailer/src/entity_emailer/email_processors/filing_notification.py
- lear: queue_services/entity-emailer/tests/unit/__init__.py
- lear: queue_services/entity-emailer/tests/unit/__init__.py
- lear: queue_services/entity-emailer/tests/unit/__init__.py
- lear: queue_services/entity-emailer/tests/unit/email_processors/test_correction_notification.py
- lear: queue_services/entity-emailer/tests/unit/test_tracker.py
- lear: queue_services/entity-emailer/tests/unit/test_tracker.py
- lear: queue_services/entity-emailer/tests/unit/test_tracker.py
- lear: queue_services/entity-emailer/tests/unit/test_tracker.py
- lear: queue_services/entity-emailer/tests/unit/test_worker.py
- lear: queue_services/entity-emailer/tests/unit/test_worker.py
- lear: queue_services/entity-emailer/tests/unit/test_worker.py
- lear: queue_services/entity-filer/tests/unit/__init__.py
- sbc-auth: queue_services/account-mailer/tests/unit/test_worker_queue.py
