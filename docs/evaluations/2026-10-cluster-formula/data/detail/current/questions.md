## lear-filings-0 (flow)

Walk me through what happens when someone submits a brand-new incorporation application for a company that doesn't exist yet. How does it get a temporary identity, how is it validated and charged, and when and where do the real business record and registration number get created?

13 of 13 answer files indexed, 12 leaves, 5 groups.

| file | leaf: main component (share), size | group |
|---|---|---|
| `lear/legal-api/src/legal_api/models/filing.py` | 439: lear/legal-api (95%), 76<br>437: lear/legal-api (97%), 38<br>383: lear/legal-api (100%), 10 | 23, 5 |
| `lear/legal-api/src/legal_api/resources/v2/business/business.py` | 453: lear/legal-api (100%), 12<br>373: lear/legal-api (100%), 12 | 20, 7 |
| `lear/legal-api/src/legal_api/resources/v2/business/business_filings/business_filings.py` | 453: lear/legal-api (100%), 12<br>437: lear/legal-api (97%), 38 | 20, 5 |
| `lear/legal-api/src/legal_api/services/bootstrap.py` | 451: lear/legal-api (100%), 47<br>373: lear/legal-api (100%), 12 | 20, 7 |
| `lear/legal-api/src/legal_api/services/filings/validations/incorporation_application.py` | 410: lear/legal-api (100%), 43<br>436: lear/legal-api (100%), 18 | 23, 5 |
| `lear/legal-api/src/legal_api/services/filings/validations/schemas.py` | 410: lear/legal-api (100%), 43 | 23 |
| `lear/legal-api/src/legal_api/services/filings/validations/validation.py` | 410: lear/legal-api (100%), 43 | 23 |
| `lear/legal-api/src/legal_api/services/namex.py` | 451: lear/legal-api (100%), 47 | 20 |
| `lear/queue_services/entity-filer/src/entity_filer/filing_processors/filing_components/business_info.py` | 450: lear/queue_services/entity-filer (100%), 16 | 23 |
| `lear/queue_services/entity-filer/src/entity_filer/filing_processors/filing_components/business_profile.py` | 449: lear/queue_services/entity-filer (90%), 20 | 23 |
| `lear/queue_services/entity-filer/src/entity_filer/filing_processors/filing_components/name_request.py` | 449: lear/queue_services/entity-filer (90%), 20 | 23 |
| `lear/queue_services/entity-filer/src/entity_filer/filing_processors/incorporation_filing.py` | 449: lear/queue_services/entity-filer (90%), 20 | 23 |
| `lear/queue_services/entity-filer/src/entity_filer/worker.py` | 393: lear/queue_services/common (35%), 26<br>409: lear/queue_services/entity-filer (100%), 8 | 24, 5 |

## lear-filings-1 (flow)

Once a filing's invoice has been paid, how does the payment confirmation make the filing actually get applied to the business, and what's different for filings dated to take effect in the future?

13 of 13 answer files indexed, 13 leaves, 5 groups.

| file | leaf: main component (share), size | group |
|---|---|---|
| `lear/jobs/future-effective-filings/file_future_effective.py` | 397: lear/jobs/involuntary-dissolutions (26%), 31 | 23 |
| `lear/legal-api/src/legal_api/core/filing.py` | 439: lear/legal-api (95%), 76<br>437: lear/legal-api (97%), 38 | 23, 5 |
| `lear/legal-api/src/legal_api/models/filing.py` | 439: lear/legal-api (95%), 76<br>437: lear/legal-api (97%), 38<br>383: lear/legal-api (100%), 10 | 23, 5 |
| `lear/legal-api/src/legal_api/resources/v2/business/business_filings/business_filings.py` | 453: lear/legal-api (100%), 12<br>437: lear/legal-api (97%), 38 | 20, 5 |
| `lear/legal-api/src/legal_api/resources/v2/internal_services.py` | 451: lear/legal-api (100%), 47 | 20 |
| `lear/legal-api/src/legal_api/utils/legislation_datetime.py` | 410: lear/legal-api (100%), 43 | 23 |
| `lear/queue_services/business-pay/src/business_pay/database/filings.py` | 111: lear/queue_services/business-pay (79%), 19 | 14 |
| `lear/queue_services/business-pay/src/business_pay/resources/pay_filer.py` | 111: lear/queue_services/business-pay (79%), 19 | 14 |
| `lear/queue_services/common/src/entity_queue_common/messages.py` | 370: lear/queue_services/common (38%), 21 | 20 |
| `lear/queue_services/entity-filer/src/entity_filer/filing_meta.py` | 245: lear/data-tool (88%), 24 | 23 |
| `lear/queue_services/entity-filer/src/entity_filer/filing_processors/change_of_address.py` | 428: lear/queue_services/entity-filer (100%), 16 | 24 |
| `lear/queue_services/entity-filer/src/entity_filer/worker.py` | 393: lear/queue_services/common (35%), 26<br>409: lear/queue_services/entity-filer (100%), 8 | 24, 5 |
| `lear/queue_services/entity-pay/src/entity_pay/worker.py` | 393: lear/queue_services/common (35%), 26 | 24 |

## lear-filings-2 (concept)

How is a filing's status lifecycle (draft, pending, paid, completed, staff review states) modeled, and what stops a filing from being edited or deleted once money is involved?

8 of 8 answer files indexed, 7 leaves, 4 groups.

| file | leaf: main component (share), size | group |
|---|---|---|
| `lear/legal-api/src/legal_api/core/filing.py` | 439: lear/legal-api (95%), 76<br>437: lear/legal-api (97%), 38 | 23, 5 |
| `lear/legal-api/src/legal_api/exceptions/__init__.py` | 440: lear/legal-api (91%), 11 | 20 |
| `lear/legal-api/src/legal_api/models/filing.py` | 439: lear/legal-api (95%), 76<br>437: lear/legal-api (97%), 38<br>383: lear/legal-api (100%), 10 | 23, 5 |
| `lear/legal-api/src/legal_api/models/review.py` | 439: lear/legal-api (95%), 76 | 23 |
| `lear/legal-api/src/legal_api/models/review_result.py` | 439: lear/legal-api (95%), 76 | 23 |
| `lear/legal-api/src/legal_api/resources/v2/admin/reviews.py` | 451: lear/legal-api (100%), 47 | 20 |
| `lear/legal-api/src/legal_api/resources/v2/business/business_filings/business_filings.py` | 453: lear/legal-api (100%), 12<br>437: lear/legal-api (97%), 38 | 20, 5 |
| `lear/queue_services/business-pay/src/business_pay/resources/pay_filer.py` | 111: lear/queue_services/business-pay (79%), 19 | 14 |

## lear-filings-3 (concept)

How does the system decide which filings a given user may submit for a given business (for example, not allowing a change while another filing is pending, or when the company is not in good standing), and where is that decision enforced and surfaced?

7 of 7 answer files indexed, 6 leaves, 4 groups.

| file | leaf: main component (share), size | group |
|---|---|---|
| `lear/legal-api/src/legal_api/core/filing.py` | 439: lear/legal-api (95%), 76<br>437: lear/legal-api (97%), 38 | 23, 5 |
| `lear/legal-api/src/legal_api/core/meta/filing.py` | 439: lear/legal-api (95%), 76<br>383: lear/legal-api (100%), 10<br>437: lear/legal-api (97%), 38 | 23, 5 |
| `lear/legal-api/src/legal_api/models/business.py` | 439: lear/legal-api (95%), 76<br>437: lear/legal-api (97%), 38 | 23, 5 |
| `lear/legal-api/src/legal_api/models/filing.py` | 439: lear/legal-api (95%), 76<br>437: lear/legal-api (97%), 38<br>383: lear/legal-api (100%), 10 | 23, 5 |
| `lear/legal-api/src/legal_api/resources/v2/business/business.py` | 453: lear/legal-api (100%), 12<br>373: lear/legal-api (100%), 12 | 20, 7 |
| `lear/legal-api/src/legal_api/resources/v2/business/business_filings/business_filings.py` | 453: lear/legal-api (100%), 12<br>437: lear/legal-api (97%), 38 | 20, 5 |
| `lear/legal-api/src/legal_api/services/authz.py` | 396: sbc-auth/auth-api (40%), 10<br>383: lear/legal-api (100%), 10 | 20, 5 |

## lear-filings-4 (change)

We need to add support for a brand-new type of business filing that is paid, changes business data, and produces a PDF. Which places in the API and the background services would I need to touch so it can be submitted, charged, applied, and shown with its documents?

16 of 16 answer files indexed, 15 leaves, 5 groups.

| file | leaf: main component (share), size | group |
|---|---|---|
| `lear/legal-api/report-templates/dissolution.html` | 94: lear/legal-api (92%), 39 | 4 |
| `lear/legal-api/src/legal_api/core/filing.py` | 439: lear/legal-api (95%), 76<br>437: lear/legal-api (97%), 38 | 23, 5 |
| `lear/legal-api/src/legal_api/core/meta/filing.py` | 439: lear/legal-api (95%), 76<br>383: lear/legal-api (100%), 10<br>437: lear/legal-api (97%), 38 | 23, 5 |
| `lear/legal-api/src/legal_api/models/filing.py` | 439: lear/legal-api (95%), 76<br>437: lear/legal-api (97%), 38<br>383: lear/legal-api (100%), 10 | 23, 5 |
| `lear/legal-api/src/legal_api/reports/report.py` | 410: lear/legal-api (100%), 43<br>438: lear/legal-api (100%), 17 | 23, 5 |
| `lear/legal-api/src/legal_api/resources/v2/business/business_filings/business_filings.py` | 453: lear/legal-api (100%), 12<br>437: lear/legal-api (97%), 38 | 20, 5 |
| `lear/legal-api/src/legal_api/services/authz.py` | 396: sbc-auth/auth-api (40%), 10<br>383: lear/legal-api (100%), 10 | 20, 5 |
| `lear/legal-api/src/legal_api/services/filings/validations/change_of_address.py` | 410: lear/legal-api (100%), 43 | 23 |
| `lear/legal-api/src/legal_api/services/filings/validations/schemas.py` | 410: lear/legal-api (100%), 43 | 23 |
| `lear/legal-api/src/legal_api/services/filings/validations/validation.py` | 410: lear/legal-api (100%), 43 | 23 |
| `lear/queue_services/common/src/entity_queue_common/messages.py` | 370: lear/queue_services/common (38%), 21 | 20 |
| `lear/queue_services/entity-emailer/src/entity_emailer/email_processors/filing_notification.py` | 429: lear/queue_services/entity-emailer (94%), 31<br>391: lear/queue_services/entity-emailer (82%), 17 | 20, 5 |
| `lear/queue_services/entity-emailer/src/entity_emailer/worker.py` | 394: sbc-auth/queue_services/auth-queue (43%), 14<br>429: lear/queue_services/entity-emailer (94%), 31 | 24, 20 |
| `lear/queue_services/entity-filer/src/entity_filer/filing_processors/dissolution.py` | 449: lear/queue_services/entity-filer (90%), 20 | 23 |
| `lear/queue_services/entity-filer/src/entity_filer/filing_processors/filing_components/business_profile.py` | 449: lear/queue_services/entity-filer (90%), 20 | 23 |
| `lear/queue_services/entity-filer/src/entity_filer/worker.py` | 393: lear/queue_services/common (35%), 26<br>409: lear/queue_services/entity-filer (100%), 8 | 24, 5 |

## lear-filings-5 (change)

Today only continuation-in applications go to a registry staff member for review after payment. If we wanted amalgamation applications to also require staff approval before they take effect, where would that change go and which other parts of the flow would it affect?

16 of 16 answer files indexed, 11 leaves, 5 groups.

| file | leaf: main component (share), size | group |
|---|---|---|
| `lear/jobs/future-effective-filings/file_future_effective.py` | 397: lear/jobs/involuntary-dissolutions (26%), 31 | 23 |
| `lear/legal-api/src/legal_api/core/filing.py` | 439: lear/legal-api (95%), 76<br>437: lear/legal-api (97%), 38 | 23, 5 |
| `lear/legal-api/src/legal_api/models/filing.py` | 439: lear/legal-api (95%), 76<br>437: lear/legal-api (97%), 38<br>383: lear/legal-api (100%), 10 | 23, 5 |
| `lear/legal-api/src/legal_api/models/review.py` | 439: lear/legal-api (95%), 76 | 23 |
| `lear/legal-api/src/legal_api/models/review_result.py` | 439: lear/legal-api (95%), 76 | 23 |
| `lear/legal-api/src/legal_api/resources/v2/admin/reviews.py` | 451: lear/legal-api (100%), 47 | 20 |
| `lear/legal-api/src/legal_api/resources/v2/business/business_filings/business_documents.py` | 453: lear/legal-api (100%), 12 | 20 |
| `lear/legal-api/src/legal_api/resources/v2/business/business_filings/business_filings.py` | 453: lear/legal-api (100%), 12<br>437: lear/legal-api (97%), 38 | 20, 5 |
| `lear/legal-api/src/legal_api/resources/v2/internal_services.py` | 451: lear/legal-api (100%), 47 | 20 |
| `lear/legal-api/src/legal_api/services/queue.py` | 393: lear/queue_services/common (35%), 26 | 24 |
| `lear/queue_services/business-pay/src/business_pay/database/filings.py` | 111: lear/queue_services/business-pay (79%), 19 | 14 |
| `lear/queue_services/business-pay/src/business_pay/database/review.py` | 297: sbc-pay/pay-queue (50%), 12 | 20 |
| `lear/queue_services/business-pay/src/business_pay/resources/pay_filer.py` | 111: lear/queue_services/business-pay (79%), 19 | 14 |
| `lear/queue_services/entity-emailer/src/entity_emailer/email_processors/amalgamation_notification.py` | 429: lear/queue_services/entity-emailer (94%), 31 | 20 |
| `lear/queue_services/entity-emailer/src/entity_emailer/worker.py` | 394: sbc-auth/queue_services/auth-queue (43%), 14<br>429: lear/queue_services/entity-emailer (94%), 31 | 24, 20 |
| `lear/queue_services/entity-pay/src/entity_pay/worker.py` | 393: lear/queue_services/common (35%), 26 | 24 |

## lear-async-0 (flow)

When a client pays for a filing that has a date set in the future, what happens end to end? How does it eventually get applied to the business, and which services and scheduled jobs are involved?

9 of 9 answer files indexed, 10 leaves, 5 groups.

| file | leaf: main component (share), size | group |
|---|---|---|
| `lear/jobs/future-effective-filings/file_future_effective.py` | 397: lear/jobs/involuntary-dissolutions (26%), 31 | 23 |
| `lear/legal-api/src/legal_api/models/filing.py` | 439: lear/legal-api (95%), 76<br>437: lear/legal-api (97%), 38<br>383: lear/legal-api (100%), 10 | 23, 5 |
| `lear/legal-api/src/legal_api/resources/v2/admin/reviews.py` | 451: lear/legal-api (100%), 47 | 20 |
| `lear/legal-api/src/legal_api/resources/v2/business/business_filings/business_filings.py` | 453: lear/legal-api (100%), 12<br>437: lear/legal-api (97%), 38 | 20, 5 |
| `lear/legal-api/src/legal_api/resources/v2/internal_services.py` | 451: lear/legal-api (100%), 47 | 20 |
| `lear/queue_services/business-pay/src/business_pay/resources/pay_filer.py` | 111: lear/queue_services/business-pay (79%), 19 | 14 |
| `lear/queue_services/common/src/entity_queue_common/messages.py` | 370: lear/queue_services/common (38%), 21 | 20 |
| `lear/queue_services/entity-filer/src/entity_filer/worker.py` | 393: lear/queue_services/common (35%), 26<br>409: lear/queue_services/entity-filer (100%), 8 | 24, 5 |
| `lear/queue_services/entity-pay/src/entity_pay/worker.py` | 393: lear/queue_services/common (35%), 26 | 24 |

## lear-async-1 (flow)

How are filings kept in sync in both directions between the new registry system and the legacy COLIN Oracle system? What runs the sync, and how does it avoid re-sending or skipping filings?

9 of 9 answer files indexed, 11 leaves, 5 groups.

| file | leaf: main component (share), size | group |
|---|---|---|
| `lear/colin-api/src/colin_api/resources/event.py` | 253: lear/colin-api (100%), 17 | 20 |
| `lear/colin-api/src/colin_api/resources/filing.py` | 253: lear/colin-api (100%), 17<br>210: lear/colin-api (100%), 19 | 20, 5 |
| `lear/jobs/update-colin-filings/update_colin_filings.py` | 254: lear/colin-api (94%), 16 | 20 |
| `lear/jobs/update-legal-filings/update_legal_filings.py` | 397: lear/jobs/involuntary-dissolutions (26%), 31<br>437: lear/legal-api (97%), 38 | 23, 5 |
| `lear/legal-api/src/legal_api/models/colin_event_id.py` | 439: lear/legal-api (95%), 76 | 23 |
| `lear/legal-api/src/legal_api/models/filing.py` | 439: lear/legal-api (95%), 76<br>437: lear/legal-api (97%), 38<br>383: lear/legal-api (100%), 10 | 23, 5 |
| `lear/legal-api/src/legal_api/resources/v2/business/business_filings/business_filings.py` | 453: lear/legal-api (100%), 12<br>437: lear/legal-api (97%), 38 | 20, 5 |
| `lear/legal-api/src/legal_api/resources/v2/business/colin_sync.py` | 451: lear/legal-api (100%), 47<br>373: lear/legal-api (100%), 12 | 20, 7 |
| `lear/legal-api/src/legal_api/services/queue.py` | 393: lear/queue_services/common (35%), 26 | 24 |

## lear-async-2 (flow)

How does a company that falls behind on its annual reports end up dissolved automatically? Which jobs, notices and queue messages are involved at each stage?

14 of 14 answer files indexed, 9 leaves, 5 groups.

| file | leaf: main component (share), size | group |
|---|---|---|
| `lear/jobs/furnishings/src/furnishings/stage_processors/post_processor.py` | 379: lear/jobs/furnishings (100%), 18 | 24 |
| `lear/jobs/furnishings/src/furnishings/stage_processors/stage_one.py` | 379: lear/jobs/furnishings (100%), 18 | 24 |
| `lear/jobs/furnishings/src/furnishings/stage_processors/stage_three.py` | 379: lear/jobs/furnishings (100%), 18 | 24 |
| `lear/jobs/furnishings/src/furnishings/stage_processors/stage_two.py` | 379: lear/jobs/furnishings (100%), 18 | 24 |
| `lear/jobs/furnishings/src/furnishings/worker.py` | 379: lear/jobs/furnishings (100%), 18 | 24 |
| `lear/jobs/involuntary-dissolutions/involuntary_dissolutions.py` | 397: lear/jobs/involuntary-dissolutions (26%), 31 | 23 |
| `lear/legal-api/src/legal_api/models/batch_processing.py` | 439: lear/legal-api (95%), 76 | 23 |
| `lear/legal-api/src/legal_api/models/configuration.py` | 439: lear/legal-api (95%), 76 | 23 |
| `lear/legal-api/src/legal_api/models/furnishing.py` | 439: lear/legal-api (95%), 76 | 23 |
| `lear/legal-api/src/legal_api/resources/v2/business/colin_sync.py` | 451: lear/legal-api (100%), 47<br>373: lear/legal-api (100%), 12 | 20, 7 |
| `lear/legal-api/src/legal_api/services/involuntary_dissolution.py` | 439: lear/legal-api (95%), 76<br>388: lear/legal-api (100%), 64 | 23, 0 |
| `lear/queue_services/entity-emailer/src/entity_emailer/email_processors/involuntary_dissolution_stage_1_notification.py` | 429: lear/queue_services/entity-emailer (94%), 31 | 20 |
| `lear/queue_services/entity-emailer/src/entity_emailer/worker.py` | 394: sbc-auth/queue_services/auth-queue (43%), 14<br>429: lear/queue_services/entity-emailer (94%), 31 | 24, 20 |
| `lear/queue_services/entity-filer/src/entity_filer/filing_processors/dissolution.py` | 449: lear/queue_services/entity-filer (90%), 20 | 23 |

## lear-async-3 (concept)

Queue messages can be delivered more than once. How does the system stop the same notification email being sent twice, and how is retrying versus dropping a message decided across the queue workers?

9 of 9 answer files indexed, 9 leaves, 5 groups.

| file | leaf: main component (share), size | group |
|---|---|---|
| `lear/queue_services/business-pay/src/business_pay/resources/pay_filer.py` | 111: lear/queue_services/business-pay (79%), 19 | 14 |
| `lear/queue_services/entity-bn/src/entity_bn/bn_processors/registration.py` | 449: lear/queue_services/entity-filer (90%), 20<br>417: lear/queue_services/entity-filer (78%), 18 | 23, 5 |
| `lear/queue_services/entity-bn/src/entity_bn/worker.py` | 370: lear/queue_services/common (38%), 21 | 20 |
| `lear/queue_services/entity-emailer/src/entity_emailer/message_tracker/tracker.py` | 429: lear/queue_services/entity-emailer (94%), 31<br>391: lear/queue_services/entity-emailer (82%), 17 | 20, 5 |
| `lear/queue_services/entity-emailer/src/entity_emailer/worker.py` | 394: sbc-auth/queue_services/auth-queue (43%), 14<br>429: lear/queue_services/entity-emailer (94%), 31 | 24, 20 |
| `lear/queue_services/entity-emailer/tracker/models/message_processing.py` | 429: lear/queue_services/entity-emailer (94%), 31 | 20 |
| `lear/queue_services/entity-emailer/tracker/services/message_processing_service.py` | 429: lear/queue_services/entity-emailer (94%), 31 | 20 |
| `lear/queue_services/entity-filer/src/entity_filer/worker.py` | 393: lear/queue_services/common (35%), 26<br>409: lear/queue_services/entity-filer (100%), 8 | 24, 5 |
| `lear/queue_services/entity-pay/src/entity_pay/worker.py` | 393: lear/queue_services/common (35%), 26 | 24 |

## lear-async-4 (concept)

How does a business get its CRA business number (tax id), depending on the kind of entity? Once the number arrives, which downstream notifications and updates does it trigger?

13 of 13 answer files indexed, 14 leaves, 5 groups.

| file | leaf: main component (share), size | group |
|---|---|---|
| `lear/colin-api/src/colin_api/resources/business.py` | 253: lear/colin-api (100%), 17 | 20 |
| `lear/colin-api/src/colin_api/resources/program_account.py` | 253: lear/colin-api (100%), 17 | 20 |
| `lear/jobs/update-legal-filings/update_legal_filings.py` | 397: lear/jobs/involuntary-dissolutions (26%), 31<br>437: lear/legal-api (97%), 38 | 23, 5 |
| `lear/legal-api/src/legal_api/models/business.py` | 439: lear/legal-api (95%), 76<br>437: lear/legal-api (97%), 38 | 23, 5 |
| `lear/legal-api/src/legal_api/resources/v2/business/colin_sync.py` | 451: lear/legal-api (100%), 47<br>373: lear/legal-api (100%), 12 | 20, 7 |
| `lear/legal-api/src/legal_api/resources/v2/internal_services.py` | 451: lear/legal-api (100%), 47 | 20 |
| `lear/queue_services/entity-bn/src/entity_bn/bn_processors/registration.py` | 449: lear/queue_services/entity-filer (90%), 20<br>417: lear/queue_services/entity-filer (78%), 18 | 23, 5 |
| `lear/queue_services/entity-bn/src/entity_bn/worker.py` | 370: lear/queue_services/common (38%), 21 | 20 |
| `lear/queue_services/entity-digital-credentials/src/entity_digital_credentials/digital_credentials_processors/business_number.py` | 374: lear/queue_services/entity-digital-credentials (57%), 14 | 23 |
| `lear/queue_services/entity-digital-credentials/src/entity_digital_credentials/worker.py` | 393: lear/queue_services/common (35%), 26 | 24 |
| `lear/queue_services/entity-emailer/src/entity_emailer/email_processors/bn_notification.py` | 429: lear/queue_services/entity-emailer (94%), 31 | 20 |
| `lear/queue_services/entity-emailer/src/entity_emailer/worker.py` | 394: sbc-auth/queue_services/auth-queue (43%), 14<br>429: lear/queue_services/entity-emailer (94%), 31 | 24, 20 |
| `lear/queue_services/entity-filer/src/entity_filer/worker.py` | 393: lear/queue_services/common (35%), 26<br>409: lear/queue_services/entity-filer (100%), 8 | 24, 5 |

## lear-async-5 (change)

We want to send annual report reminder emails to cooperatives as well, and to stop sending a confirmation email when a change of directors completes. Where would these changes go, and what else would be affected?

12 of 12 answer files indexed, 11 leaves, 5 groups.

| file | leaf: main component (share), size | group |
|---|---|---|
| `lear/jobs/email-reminder/email_reminder.py` | 397: lear/jobs/involuntary-dissolutions (26%), 31 | 23 |
| `lear/legal-api/src/legal_api/models/business.py` | 439: lear/legal-api (95%), 76<br>437: lear/legal-api (97%), 38 | 23, 5 |
| `lear/legal-api/src/legal_api/models/filing.py` | 439: lear/legal-api (95%), 76<br>437: lear/legal-api (97%), 38<br>383: lear/legal-api (100%), 10 | 23, 5 |
| `lear/queue_services/common/src/entity_queue_common/messages.py` | 370: lear/queue_services/common (38%), 21 | 20 |
| `lear/queue_services/entity-emailer/src/entity_emailer/email_processors/__init__.py` | 429: lear/queue_services/entity-emailer (94%), 31 | 20 |
| `lear/queue_services/entity-emailer/src/entity_emailer/email_processors/ar_reminder_notification.py` | 429: lear/queue_services/entity-emailer (94%), 31 | 20 |
| `lear/queue_services/entity-emailer/src/entity_emailer/email_processors/filing_notification.py` | 429: lear/queue_services/entity-emailer (94%), 31<br>391: lear/queue_services/entity-emailer (82%), 17 | 20, 5 |
| `lear/queue_services/entity-emailer/src/entity_emailer/email_templates/AR-REMINDER.html` | 107: lear/queue_services/entity-emailer (86%), 58 | 4 |
| `lear/queue_services/entity-emailer/src/entity_emailer/email_templates/BC-COD-COMPLETED.html` | 107: lear/queue_services/entity-emailer (86%), 58 | 4 |
| `lear/queue_services/entity-emailer/src/entity_emailer/message_tracker/tracker.py` | 429: lear/queue_services/entity-emailer (94%), 31<br>391: lear/queue_services/entity-emailer (82%), 17 | 20, 5 |
| `lear/queue_services/entity-emailer/src/entity_emailer/worker.py` | 394: sbc-auth/queue_services/auth-queue (43%), 14<br>429: lear/queue_services/entity-emailer (94%), 31 | 24, 20 |
| `lear/queue_services/entity-filer/src/entity_filer/worker.py` | 393: lear/queue_services/common (35%), 26<br>409: lear/queue_services/entity-filer (100%), 8 | 24, 5 |

## auth-0 (flow)

Walk me through what happens end to end when an account administrator invites a new team member by email. How is the invitation created and emailed, what link does the invitee click, and what happens when the invitee accepts it and becomes a member?

14 of 14 answer files indexed, 12 leaves, 7 groups.

| file | leaf: main component (share), size | group |
|---|---|---|
| `sbc-auth/auth-api/src/auth_api/models/invitation.py` | 461: sbc-auth/auth-api (100%), 16 | 23 |
| `sbc-auth/auth-api/src/auth_api/models/membership.py` | 461: sbc-auth/auth-api (100%), 16 | 23 |
| `sbc-auth/auth-api/src/auth_api/resources/v1/invitation.py` | 457: sbc-auth/auth-api (99%), 68 | 20 |
| `sbc-auth/auth-api/src/auth_api/services/authorization.py` | 457: sbc-auth/auth-api (99%), 68<br>455: sbc-auth/auth-api (100%), 26 | 20, 7 |
| `sbc-auth/auth-api/src/auth_api/services/invitation.py` | 457: sbc-auth/auth-api (99%), 68<br>454: sbc-auth/auth-api (100%), 14 | 20, 7 |
| `sbc-auth/auth-api/src/auth_api/services/keycloak.py` | 448: sbc-auth/auth-api (67%), 9 | 20 |
| `sbc-auth/auth-api/src/auth_api/services/products.py` | 464: sbc-auth/auth-api (100%), 19<br>454: sbc-auth/auth-api (100%), 14<br>455: sbc-auth/auth-api (100%), 26 | 23, 7 |
| `sbc-auth/auth-api/src/auth_api/services/task.py` | 457: sbc-auth/auth-api (99%), 68<br>455: sbc-auth/auth-api (100%), 26<br>355: sbc-pay/pay-api (78%), 23 | 20, 7, 6 |
| `sbc-auth/auth-api/src/auth_api/utils/account_mailer.py` | 457: sbc-auth/auth-api (99%), 68 | 20 |
| `sbc-auth/auth-web/src/routes/router.ts` | 211: sbc-auth/auth-web (91%), 11 | 8 |
| `sbc-auth/auth-web/src/services/invitation.services.ts` | 335: sbc-auth/auth-web (78%), 27 | 8 |
| `sbc-auth/auth-web/src/stores/org.ts` | 336: sbc-auth/auth-web (100%), 19 | 9 |
| `sbc-auth/auth-web/src/views/auth/AcceptInviteLandingView.vue` | 425: sbc-auth/auth-web (100%), 44 | 3 |
| `sbc-auth/auth-web/src/views/auth/AcceptInviteView.vue` | 83: sbc-auth/auth-web (82%), 17 | 8 |

## auth-1 (concept)

How are fine-grained permissions (for example, who can change the account address or invite members) modeled and enforced for a team member, depending on their role and on the account's status? Where do these rules live, and how does the web front end learn about them?

18 of 18 answer files indexed, 12 leaves, 7 groups.

| file | leaf: main component (share), size | group |
|---|---|---|
| `sbc-auth/auth-api/migrations/versions/2024_05_30_39b4f331c003_admin_view_address_permission.py` | 176: sbc-auth/auth-api (100%), 29 | 0 |
| `sbc-auth/auth-api/src/auth_api/__init__.py` | 457: sbc-auth/auth-api (99%), 68 | 20 |
| `sbc-auth/auth-api/src/auth_api/models/permissions.py` | 464: sbc-auth/auth-api (100%), 19 | 23 |
| `sbc-auth/auth-api/src/auth_api/models/views/authorization.py` | 463: sbc-auth/auth-api (100%), 15 | 23 |
| `sbc-auth/auth-api/src/auth_api/resources/v1/entity.py` | 457: sbc-auth/auth-api (99%), 68<br>455: sbc-auth/auth-api (100%), 26 | 20, 7 |
| `sbc-auth/auth-api/src/auth_api/resources/v1/invitation.py` | 457: sbc-auth/auth-api (99%), 68 | 20 |
| `sbc-auth/auth-api/src/auth_api/resources/v1/org_authorizations.py` | 457: sbc-auth/auth-api (99%), 68 | 20 |
| `sbc-auth/auth-api/src/auth_api/resources/v1/permissions.py` | 457: sbc-auth/auth-api (99%), 68 | 20 |
| `sbc-auth/auth-api/src/auth_api/services/authorization.py` | 457: sbc-auth/auth-api (99%), 68<br>455: sbc-auth/auth-api (100%), 26 | 20, 7 |
| `sbc-auth/auth-api/src/auth_api/services/membership.py` | 457: sbc-auth/auth-api (99%), 68<br>455: sbc-auth/auth-api (100%), 26<br>462: sbc-auth/auth-api (100%), 26 | 20, 7, 23 |
| `sbc-auth/auth-api/src/auth_api/services/permissions.py` | 457: sbc-auth/auth-api (99%), 68 | 20 |
| `sbc-auth/auth-api/src/auth_api/utils/enums.py` | 457: sbc-auth/auth-api (99%), 68 | 20 |
| `sbc-auth/auth-web/src/components/auth/account-settings/account-info/AccountInfo.vue` | 444: sbc-auth/auth-web (100%), 46<br>386: sbc-auth/auth-web (100%), 20 | 3 |
| `sbc-auth/auth-web/src/components/auth/account-settings/payment/AccountPaymentMethods.vue` | 138: sbc-auth/auth-web (97%), 35 | 3 |
| `sbc-auth/auth-web/src/services/permission.services.ts` | 335: sbc-auth/auth-web (78%), 27 | 8 |
| `sbc-auth/auth-web/src/stores/org.ts` | 336: sbc-auth/auth-web (100%), 19 | 9 |
| `sbc-auth/auth-web/src/util/common-util.ts` | 327: sbc-auth/auth-web (96%), 48 | 9 |
| `sbc-auth/auth-web/src/util/constants.ts` | 327: sbc-auth/auth-web (96%), 48 | 9 |

## auth-2 (flow)

How does a user add an existing business or a name request to their account's business list, and how is the claim verified? What happens on the reverse path, when a business is removed from the account?

10 of 10 answer files indexed, 8 leaves, 6 groups.

| file | leaf: main component (share), size | group |
|---|---|---|
| `sbc-auth/auth-api/src/auth_api/models/affiliation.py` | 461: sbc-auth/auth-api (100%), 16 | 23 |
| `sbc-auth/auth-api/src/auth_api/resources/v1/org.py` | 457: sbc-auth/auth-api (99%), 68<br>455: sbc-auth/auth-api (100%), 26 | 20, 7 |
| `sbc-auth/auth-api/src/auth_api/services/activity_log_publisher.py` | 457: sbc-auth/auth-api (99%), 68 | 20 |
| `sbc-auth/auth-api/src/auth_api/services/affiliation.py` | 461: sbc-auth/auth-api (100%), 16<br>454: sbc-auth/auth-api (100%), 14 | 23, 7 |
| `sbc-auth/auth-api/src/auth_api/services/entity.py` | 457: sbc-auth/auth-api (99%), 68 | 20 |
| `sbc-auth/auth-api/src/auth_api/services/rest_service.py` | 457: sbc-auth/auth-api (99%), 68 | 20 |
| `sbc-auth/auth-api/src/auth_api/utils/passcode.py` | 420: sbc-auth/auth-api (87%), 75 | 24 |
| `sbc-auth/auth-web/src/services/org.services.ts` | 335: sbc-auth/auth-web (78%), 27 | 8 |
| `sbc-auth/auth-web/src/stores/business.ts` | 336: sbc-auth/auth-web (100%), 19 | 9 |
| `sbc-auth/queue_services/auth-queue/src/auth_queue/resources/worker.py` | 394: sbc-auth/queue_services/auth-queue (43%), 14 | 24 |

## auth-3 (concept)

Some new accounts and some new administrators must be reviewed by registry staff before they become usable. How is this staff-review concept modeled, what creates a review item, and what happens when staff approve, reject or put a review on hold?

11 of 11 answer files indexed, 7 leaves, 6 groups.

| file | leaf: main component (share), size | group |
|---|---|---|
| `sbc-auth/auth-api/migrations/versions/5397c5a5b0ca_staff_pending_status_permissions.py` | 176: sbc-auth/auth-api (100%), 29 | 0 |
| `sbc-auth/auth-api/src/auth_api/models/membership.py` | 461: sbc-auth/auth-api (100%), 16 | 23 |
| `sbc-auth/auth-api/src/auth_api/models/task.py` | 420: sbc-auth/auth-api (87%), 75 | 24 |
| `sbc-auth/auth-api/src/auth_api/resources/v1/task.py` | 457: sbc-auth/auth-api (99%), 68 | 20 |
| `sbc-auth/auth-api/src/auth_api/services/affidavit.py` | 457: sbc-auth/auth-api (99%), 68 | 20 |
| `sbc-auth/auth-api/src/auth_api/services/invitation.py` | 457: sbc-auth/auth-api (99%), 68<br>454: sbc-auth/auth-api (100%), 14 | 20, 7 |
| `sbc-auth/auth-api/src/auth_api/services/org.py` | 457: sbc-auth/auth-api (99%), 68<br>455: sbc-auth/auth-api (100%), 26 | 20, 7 |
| `sbc-auth/auth-api/src/auth_api/services/permissions.py` | 457: sbc-auth/auth-api (99%), 68 | 20 |
| `sbc-auth/auth-api/src/auth_api/services/task.py` | 457: sbc-auth/auth-api (99%), 68<br>455: sbc-auth/auth-api (100%), 26<br>355: sbc-pay/pay-api (78%), 23 | 20, 7, 6 |
| `sbc-auth/auth-api/src/auth_api/utils/account_mailer.py` | 457: sbc-auth/auth-api (99%), 68 | 20 |
| `sbc-auth/auth-api/src/auth_api/utils/enums.py` | 457: sbc-auth/auth-api (99%), 68 | 20 |

## auth-4 (change)

We want to guarantee that an account can never be left without an active administrator: no admin should be able to leave the team, or be removed, if they are the last one. Where is the 'only administrator' rule enforced today, where are the gaps, and what would we need to touch in the API and the web app?

13 of 13 answer files indexed, 11 leaves, 5 groups.

| file | leaf: main component (share), size | group |
|---|---|---|
| `sbc-auth/auth-api/src/auth_api/exceptions/errors.py` | 457: sbc-auth/auth-api (99%), 68 | 20 |
| `sbc-auth/auth-api/src/auth_api/models/membership.py` | 461: sbc-auth/auth-api (100%), 16 | 23 |
| `sbc-auth/auth-api/src/auth_api/models/org.py` | 463: sbc-auth/auth-api (100%), 15<br>462: sbc-auth/auth-api (100%), 26<br>455: sbc-auth/auth-api (100%), 26 | 23, 7 |
| `sbc-auth/auth-api/src/auth_api/resources/v1/org.py` | 457: sbc-auth/auth-api (99%), 68<br>455: sbc-auth/auth-api (100%), 26 | 20, 7 |
| `sbc-auth/auth-api/src/auth_api/services/activity_log_publisher.py` | 457: sbc-auth/auth-api (99%), 68 | 20 |
| `sbc-auth/auth-api/src/auth_api/services/authorization.py` | 457: sbc-auth/auth-api (99%), 68<br>455: sbc-auth/auth-api (100%), 26 | 20, 7 |
| `sbc-auth/auth-api/src/auth_api/services/keycloak.py` | 448: sbc-auth/auth-api (67%), 9 | 20 |
| `sbc-auth/auth-api/src/auth_api/services/membership.py` | 457: sbc-auth/auth-api (99%), 68<br>455: sbc-auth/auth-api (100%), 26<br>462: sbc-auth/auth-api (100%), 26 | 20, 7, 23 |
| `sbc-auth/auth-api/src/auth_api/services/products.py` | 464: sbc-auth/auth-api (100%), 19<br>454: sbc-auth/auth-api (100%), 14<br>455: sbc-auth/auth-api (100%), 26 | 23, 7 |
| `sbc-auth/auth-api/src/auth_api/utils/account_mailer.py` | 457: sbc-auth/auth-api (99%), 68 | 20 |
| `sbc-auth/auth-web/src/components/auth/mixins/TeamManagementMixin.vue` | 376: sbc-auth/auth-web (100%), 10 | 8 |
| `sbc-auth/auth-web/src/services/org.services.ts` | 335: sbc-auth/auth-web (78%), 27 | 8 |
| `sbc-auth/auth-web/src/stores/org.ts` | 336: sbc-auth/auth-web (100%), 19 | 9 |

## auth-5 (change)

We want account administrators to see a new kind of entry in their account's activity history, for example when an API key is created. How do activity entries get from the place where an action happens into the history shown to the user, and what would we need to add for a new action type?

15 of 15 answer files indexed, 8 leaves, 8 groups.

| file | leaf: main component (share), size | group |
|---|---|---|
| `sbc-auth/auth-api/migrations/versions/1a46fdc4d630_permissons_for_activity_log.py` | 344: sbc-auth/auth-api (98%), 93 | 0 |
| `sbc-auth/auth-api/src/auth_api/config.py` | 457: sbc-auth/auth-api (99%), 68<br>243: sbc-auth/auth-api (33%), 12 | 20, 19 |
| `sbc-auth/auth-api/src/auth_api/models/activity_log.py` | 457: sbc-auth/auth-api (99%), 68 | 20 |
| `sbc-auth/auth-api/src/auth_api/models/dataclass.py` | 463: sbc-auth/auth-api (100%), 15 | 23 |
| `sbc-auth/auth-api/src/auth_api/models/pubsub_message_processing.py` | 344: sbc-auth/auth-api (98%), 93 | 0 |
| `sbc-auth/auth-api/src/auth_api/resources/v1/activity_log.py` | 457: sbc-auth/auth-api (99%), 68 | 20 |
| `sbc-auth/auth-api/src/auth_api/services/activity_log.py` | 457: sbc-auth/auth-api (99%), 68 | 20 |
| `sbc-auth/auth-api/src/auth_api/services/activity_log_publisher.py` | 457: sbc-auth/auth-api (99%), 68 | 20 |
| `sbc-auth/auth-api/src/auth_api/services/authorization.py` | 457: sbc-auth/auth-api (99%), 68<br>455: sbc-auth/auth-api (100%), 26 | 20, 7 |
| `sbc-auth/auth-api/src/auth_api/services/org.py` | 457: sbc-auth/auth-api (99%), 68<br>455: sbc-auth/auth-api (100%), 26 | 20, 7 |
| `sbc-auth/auth-api/src/auth_api/services/permissions.py` | 457: sbc-auth/auth-api (99%), 68 | 20 |
| `sbc-auth/auth-api/src/auth_api/utils/enums.py` | 457: sbc-auth/auth-api (99%), 68 | 20 |
| `sbc-auth/auth-web/src/models/activityLog.ts` | 327: sbc-auth/auth-web (96%), 48 | 9 |
| `sbc-auth/auth-web/src/services/activityLog.services.ts` | 335: sbc-auth/auth-web (78%), 27 | 8 |
| `sbc-auth/queue_services/auth-queue/src/auth_queue/resources/worker.py` | 394: sbc-auth/queue_services/auth-queue (43%), 14 | 24 |

## pay-0 (flow)

When a business filing app asks the payment system to charge for a filing, what happens end to end, from the incoming request to the filing app being told the payment is done?

14 of 14 answer files indexed, 8 leaves, 4 groups.

| file | leaf: main component (share), size | group |
|---|---|---|
| `sbc-pay/pay-api/src/pay_api/factory/payment_system_factory.py` | 422: sbc-pay/pay-api (100%), 27 | 20 |
| `sbc-pay/pay-api/src/pay_api/models/distribution_code.py` | 431: sbc-pay/pay-api (97%), 35 | 23 |
| `sbc-pay/pay-api/src/pay_api/models/fee_schedule.py` | 431: sbc-pay/pay-api (97%), 35 | 23 |
| `sbc-pay/pay-api/src/pay_api/resources/v1/invoice.py` | 407: sbc-pay/pay-api (96%), 45 | 20 |
| `sbc-pay/pay-api/src/pay_api/services/base_payment_system.py` | 422: sbc-pay/pay-api (100%), 27<br>355: sbc-pay/pay-api (78%), 23<br>356: sbc-pay/pay-api (98%), 44 | 20, 6 |
| `sbc-pay/pay-api/src/pay_api/services/bcol_service.py` | 422: sbc-pay/pay-api (100%), 27 | 20 |
| `sbc-pay/pay-api/src/pay_api/services/eft_service.py` | 285: sbc-pay/pay-api (100%), 15<br>284: sbc-pay/pay-api (100%), 12 | 24, 6 |
| `sbc-pay/pay-api/src/pay_api/services/fee_schedule.py` | 407: sbc-pay/pay-api (96%), 45<br>356: sbc-pay/pay-api (98%), 44<br>355: sbc-pay/pay-api (78%), 23 | 20, 6 |
| `sbc-pay/pay-api/src/pay_api/services/gcp_queue_publisher.py` | 297: sbc-pay/pay-queue (50%), 12 | 20 |
| `sbc-pay/pay-api/src/pay_api/services/internal_pay_service.py` | 422: sbc-pay/pay-api (100%), 27 | 20 |
| `sbc-pay/pay-api/src/pay_api/services/pad_service.py` | 422: sbc-pay/pay-api (100%), 27 | 20 |
| `sbc-pay/pay-api/src/pay_api/services/payment_line_item.py` | 422: sbc-pay/pay-api (100%), 27 | 20 |
| `sbc-pay/pay-api/src/pay_api/services/payment_service.py` | 422: sbc-pay/pay-api (100%), 27<br>355: sbc-pay/pay-api (78%), 23<br>356: sbc-pay/pay-api (98%), 44 | 20, 6 |
| `sbc-pay/pay-api/src/pay_api/utils/util.py` | 422: sbc-pay/pay-api (100%), 27<br>356: sbc-pay/pay-api (98%), 44 | 20, 6 |

## pay-1 (flow)

Walk me through the lifecycle of a pre-authorized debit customer: from entering bank details, through the confirmation period and the daily batching of their purchases, to the bank settlement file that marks those purchases paid.

13 of 13 answer files indexed, 11 leaves, 3 groups.

| file | leaf: main component (share), size | group |
|---|---|---|
| `sbc-pay/jobs/ftp-poller/tasks/cas_poller_ftp.py` | 395: sbc-pay/jobs/ftp-poller (90%), 10 | 20 |
| `sbc-pay/jobs/ftp-poller/utils/utils.py` | 395: sbc-pay/jobs/ftp-poller (90%), 10 | 20 |
| `sbc-pay/jobs/payment-jobs/invoke_jobs.py` | 395: sbc-pay/jobs/ftp-poller (90%), 10 | 20 |
| `sbc-pay/jobs/payment-jobs/tasks/activate_pad_account_task.py` | 403: sbc-pay/jobs/payment-jobs (100%), 26 | 20 |
| `sbc-pay/jobs/payment-jobs/tasks/cfs_create_account_task.py` | 403: sbc-pay/jobs/payment-jobs (100%), 26<br>368: sbc-pay/jobs/payment-jobs (100%), 10 | 20, 6 |
| `sbc-pay/jobs/payment-jobs/tasks/cfs_create_invoice_task.py` | 403: sbc-pay/jobs/payment-jobs (100%), 26<br>355: sbc-pay/pay-api (78%), 23<br>368: sbc-pay/jobs/payment-jobs (100%), 10 | 20, 6 |
| `sbc-pay/pay-api/src/pay_api/config.py` | 407: sbc-pay/pay-api (96%), 45<br>243: sbc-auth/auth-api (33%), 12 | 20, 19 |
| `sbc-pay/pay-api/src/pay_api/factory/payment_system_factory.py` | 422: sbc-pay/pay-api (100%), 27 | 20 |
| `sbc-pay/pay-api/src/pay_api/services/pad_service.py` | 422: sbc-pay/pay-api (100%), 27 | 20 |
| `sbc-pay/pay-api/src/pay_api/services/payment_account.py` | 422: sbc-pay/pay-api (100%), 27<br>355: sbc-pay/pay-api (78%), 23<br>356: sbc-pay/pay-api (98%), 44 | 20, 6 |
| `sbc-pay/pay-queue/src/pay_queue/enums.py` | 286: sbc-pay/pay-queue (100%), 14 | 6 |
| `sbc-pay/pay-queue/src/pay_queue/resources/worker.py` | 297: sbc-pay/pay-queue (50%), 12 | 20 |
| `sbc-pay/pay-queue/src/pay_queue/services/payment_reconciliations.py` | 275: sbc-pay/pay-queue (90%), 30 | 6 |

## pay-2 (flow)

How does money a customer sends by electronic funds transfer to the government bank account end up paying their outstanding statement invoices, both in our database and in the government's receivables system?

11 of 11 answer files indexed, 11 leaves, 3 groups.

| file | leaf: main component (share), size | group |
|---|---|---|
| `sbc-pay/jobs/ftp-poller/tasks/eft_poller_ftp.py` | 395: sbc-pay/jobs/ftp-poller (90%), 10 | 20 |
| `sbc-pay/jobs/ftp-poller/utils/utils.py` | 395: sbc-pay/jobs/ftp-poller (90%), 10 | 20 |
| `sbc-pay/jobs/payment-jobs/invoke_jobs.py` | 395: sbc-pay/jobs/ftp-poller (90%), 10 | 20 |
| `sbc-pay/jobs/payment-jobs/tasks/eft_task.py` | 403: sbc-pay/jobs/payment-jobs (100%), 26<br>368: sbc-pay/jobs/payment-jobs (100%), 10 | 20, 6 |
| `sbc-pay/jobs/payment-jobs/utils/auth_event.py` | 275: sbc-pay/pay-queue (90%), 30 | 6 |
| `sbc-pay/pay-api/src/pay_api/services/eft_service.py` | 285: sbc-pay/pay-api (100%), 15<br>284: sbc-pay/pay-api (100%), 12 | 24, 6 |
| `sbc-pay/pay-api/src/pay_api/services/eft_short_name_historical.py` | 267: sbc-pay/pay-api (100%), 16 | 6 |
| `sbc-pay/pay-api/src/pay_api/services/eft_short_names.py` | 267: sbc-pay/pay-api (100%), 16<br>268: sbc-pay/pay-api (100%), 10<br>284: sbc-pay/pay-api (100%), 12 | 6 |
| `sbc-pay/pay-queue/src/pay_queue/resources/worker.py` | 297: sbc-pay/pay-queue (50%), 12 | 20 |
| `sbc-pay/pay-queue/src/pay_queue/services/eft/eft_reconciliation.py` | 286: sbc-pay/pay-queue (100%), 14<br>287: sbc-pay/pay-queue (100%), 10 | 6 |
| `sbc-pay/pay-queue/src/pay_queue/services/eft/eft_record.py` | 286: sbc-pay/pay-queue (100%), 14 | 6 |

## pay-3 (concept)

How is an account 'freeze' or 'lock' (after a bounced bank debit or an overdue electronic-transfer statement) modeled, where is it set, what blocks new charges while it is in place, and how does it get lifted?

12 of 12 answer files indexed, 9 leaves, 4 groups.

| file | leaf: main component (share), size | group |
|---|---|---|
| `sbc-pay/jobs/payment-jobs/tasks/cfs_create_invoice_task.py` | 403: sbc-pay/jobs/payment-jobs (100%), 26<br>355: sbc-pay/pay-api (78%), 23<br>368: sbc-pay/jobs/payment-jobs (100%), 10 | 20, 6 |
| `sbc-pay/jobs/payment-jobs/tasks/statement_due_task.py` | 403: sbc-pay/jobs/payment-jobs (100%), 26<br>355: sbc-pay/pay-api (78%), 23<br>368: sbc-pay/jobs/payment-jobs (100%), 10 | 20, 6 |
| `sbc-pay/jobs/payment-jobs/utils/auth_event.py` | 275: sbc-pay/pay-queue (90%), 30 | 6 |
| `sbc-pay/pay-api/src/pay_api/models/payment_account.py` | 431: sbc-pay/pay-api (97%), 35 | 23 |
| `sbc-pay/pay-api/src/pay_api/services/base_payment_system.py` | 422: sbc-pay/pay-api (100%), 27<br>355: sbc-pay/pay-api (78%), 23<br>356: sbc-pay/pay-api (98%), 44 | 20, 6 |
| `sbc-pay/pay-api/src/pay_api/services/eft_service.py` | 285: sbc-pay/pay-api (100%), 15<br>284: sbc-pay/pay-api (100%), 12 | 24, 6 |
| `sbc-pay/pay-api/src/pay_api/services/non_sufficient_funds.py` | 422: sbc-pay/pay-api (100%), 27 | 20 |
| `sbc-pay/pay-api/src/pay_api/services/pad_service.py` | 422: sbc-pay/pay-api (100%), 27 | 20 |
| `sbc-pay/pay-api/src/pay_api/services/payment_account.py` | 422: sbc-pay/pay-api (100%), 27<br>355: sbc-pay/pay-api (78%), 23<br>356: sbc-pay/pay-api (98%), 44 | 20, 6 |
| `sbc-pay/pay-api/src/pay_api/services/payment_transaction.py` | 422: sbc-pay/pay-api (100%), 27<br>355: sbc-pay/pay-api (78%), 23<br>356: sbc-pay/pay-api (98%), 44 | 20, 6 |
| `sbc-pay/pay-api/src/pay_api/utils/enums.py` | 422: sbc-pay/pay-api (100%), 27 | 20 |
| `sbc-pay/pay-queue/src/pay_queue/services/payment_reconciliations.py` | 275: sbc-pay/pay-queue (90%), 30 | 6 |

## pay-4 (concept)

How are refunds handled differently for each way a customer can pay, and how does a refund move from 'requested' to confirmed for card and BC Online payments?

15 of 15 answer files indexed, 10 leaves, 4 groups.

| file | leaf: main component (share), size | group |
|---|---|---|
| `sbc-pay/jobs/payment-jobs/services/oracle.py` | 400: sbc-pay/jobs/payment-jobs (35%), 23 | 14 |
| `sbc-pay/jobs/payment-jobs/tasks/bcol_refund_confirmation_task.py` | 403: sbc-pay/jobs/payment-jobs (100%), 26 | 20 |
| `sbc-pay/jobs/payment-jobs/tasks/cfs_create_invoice_task.py` | 403: sbc-pay/jobs/payment-jobs (100%), 26<br>355: sbc-pay/pay-api (78%), 23<br>368: sbc-pay/jobs/payment-jobs (100%), 10 | 20, 6 |
| `sbc-pay/jobs/payment-jobs/tasks/direct_pay_automated_refund_task.py` | 403: sbc-pay/jobs/payment-jobs (100%), 26 | 20 |
| `sbc-pay/pay-api/src/pay_api/factory/payment_system_factory.py` | 422: sbc-pay/pay-api (100%), 27 | 20 |
| `sbc-pay/pay-api/src/pay_api/resources/v1/refund.py` | 407: sbc-pay/pay-api (96%), 45 | 20 |
| `sbc-pay/pay-api/src/pay_api/services/base_payment_system.py` | 422: sbc-pay/pay-api (100%), 27<br>355: sbc-pay/pay-api (78%), 23<br>356: sbc-pay/pay-api (98%), 44 | 20, 6 |
| `sbc-pay/pay-api/src/pay_api/services/bcol_service.py` | 422: sbc-pay/pay-api (100%), 27 | 20 |
| `sbc-pay/pay-api/src/pay_api/services/direct_pay_service.py` | 422: sbc-pay/pay-api (100%), 27<br>355: sbc-pay/pay-api (78%), 23<br>356: sbc-pay/pay-api (98%), 44 | 20, 6 |
| `sbc-pay/pay-api/src/pay_api/services/eft_refund.py` | 284: sbc-pay/pay-api (100%), 12 | 6 |
| `sbc-pay/pay-api/src/pay_api/services/eft_service.py` | 285: sbc-pay/pay-api (100%), 15<br>284: sbc-pay/pay-api (100%), 12 | 24, 6 |
| `sbc-pay/pay-api/src/pay_api/services/internal_pay_service.py` | 422: sbc-pay/pay-api (100%), 27 | 20 |
| `sbc-pay/pay-api/src/pay_api/services/pad_service.py` | 422: sbc-pay/pay-api (100%), 27 | 20 |
| `sbc-pay/pay-api/src/pay_api/services/refund.py` | 407: sbc-pay/pay-api (96%), 45<br>355: sbc-pay/pay-api (78%), 23<br>284: sbc-pay/pay-api (100%), 12 | 20, 6 |
| `sbc-pay/pay-api/src/pay_api/utils/constants.py` | 246: sbc-pay/pay-api (74%), 23 | 14 |

## pay-5 (change)

We need to add a new payment method where purchases are recorded immediately but invoiced in the government receivables system later by a batch, and settled through the bank settlement file. Where would this be implemented and what else would need updating?

14 of 14 answer files indexed, 13 leaves, 4 groups.

| file | leaf: main component (share), size | group |
|---|---|---|
| `sbc-pay/jobs/payment-jobs/tasks/cfs_create_account_task.py` | 403: sbc-pay/jobs/payment-jobs (100%), 26<br>368: sbc-pay/jobs/payment-jobs (100%), 10 | 20, 6 |
| `sbc-pay/jobs/payment-jobs/tasks/cfs_create_invoice_task.py` | 403: sbc-pay/jobs/payment-jobs (100%), 26<br>355: sbc-pay/pay-api (78%), 23<br>368: sbc-pay/jobs/payment-jobs (100%), 10 | 20, 6 |
| `sbc-pay/jobs/payment-jobs/tasks/ejv_partner_distribution_task.py` | 403: sbc-pay/jobs/payment-jobs (100%), 26<br>402: sbc-pay/jobs/payment-jobs (100%), 14 | 20, 24 |
| `sbc-pay/pay-api/src/pay_api/factory/payment_system_factory.py` | 422: sbc-pay/pay-api (100%), 27 | 20 |
| `sbc-pay/pay-api/src/pay_api/services/base_payment_system.py` | 422: sbc-pay/pay-api (100%), 27<br>355: sbc-pay/pay-api (78%), 23<br>356: sbc-pay/pay-api (98%), 44 | 20, 6 |
| `sbc-pay/pay-api/src/pay_api/services/cfs_service.py` | 412: sbc-pay/pay-api (98%), 55<br>356: sbc-pay/pay-api (98%), 44 | 24, 6 |
| `sbc-pay/pay-api/src/pay_api/services/eft_service.py` | 285: sbc-pay/pay-api (100%), 15<br>284: sbc-pay/pay-api (100%), 12 | 24, 6 |
| `sbc-pay/pay-api/src/pay_api/services/pad_service.py` | 422: sbc-pay/pay-api (100%), 27 | 20 |
| `sbc-pay/pay-api/src/pay_api/services/payment_service.py` | 422: sbc-pay/pay-api (100%), 27<br>355: sbc-pay/pay-api (78%), 23<br>356: sbc-pay/pay-api (98%), 44 | 20, 6 |
| `sbc-pay/pay-api/src/pay_api/services/refund.py` | 407: sbc-pay/pay-api (96%), 45<br>355: sbc-pay/pay-api (78%), 23<br>284: sbc-pay/pay-api (100%), 12 | 20, 6 |
| `sbc-pay/pay-api/src/pay_api/utils/constants.py` | 246: sbc-pay/pay-api (74%), 23 | 14 |
| `sbc-pay/pay-api/src/pay_api/utils/enums.py` | 422: sbc-pay/pay-api (100%), 27 | 20 |
| `sbc-pay/pay-queue/src/pay_queue/enums.py` | 286: sbc-pay/pay-queue (100%), 14 | 6 |
| `sbc-pay/pay-queue/src/pay_queue/services/payment_reconciliations.py` | 275: sbc-pay/pay-queue (90%), 30 | 6 |

## ui-0 (flow)

When a user opens a business's dashboard URL in this front end, what happens from page load to the point where the business info, to-dos and filing history are on screen? How does the app learn which business to load and where the API is, and how does it decide whether the user may see the business?

16 of 16 answer files indexed, 9 leaves, 4 groups.

| file | leaf: main component (share), size | group |
|---|---|---|
| `business-filings-ui/src/App.vue` | 165: business-filings-ui (100%), 19<br>255: business-filings-ui (100%), 35 | 3 |
| `business-filings-ui/src/axios-auth.ts` | 335: sbc-auth/auth-web (78%), 27 | 8 |
| `business-filings-ui/src/components/Dashboard/FilingHistoryList.vue` | 91: business-filings-ui (98%), 43 | 3 |
| `business-filings-ui/src/components/Dashboard/TodoList.vue` | 165: business-filings-ui (100%), 19 | 3 |
| `business-filings-ui/src/main.ts` | 130: business-filings-ui (95%), 19 | 8 |
| `business-filings-ui/src/router.ts` | 130: business-filings-ui (95%), 19 | 8 |
| `business-filings-ui/src/routes.ts` | 130: business-filings-ui (95%), 19 | 8 |
| `business-filings-ui/src/services/auth-services.ts` | 335: sbc-auth/auth-web (78%), 27 | 8 |
| `business-filings-ui/src/services/legal-services.ts` | 335: sbc-auth/auth-web (78%), 27 | 8 |
| `business-filings-ui/src/stores/businessStore.ts` | 81: business-filings-ui (100%), 9 | 8 |
| `business-filings-ui/src/stores/configurationStore.ts` | 130: business-filings-ui (95%), 19 | 8 |
| `business-filings-ui/src/stores/filingHistoryListStore.ts` | 23: business-filings-ui (100%), 23 | 8 |
| `business-filings-ui/src/stores/rootStore.ts` | 81: business-filings-ui (100%), 9 | 8 |
| `business-filings-ui/src/utils/set-base-route-and-business-id.ts` | 130: business-filings-ui (95%), 19 | 8 |
| `business-filings-ui/src/views/Dashboard.vue` | 165: business-filings-ui (100%), 19 | 3 |
| `sbc-auth/auth-api/src/auth_api/resources/v1/entity.py` | 457: sbc-auth/auth-api (99%), 68<br>455: sbc-auth/auth-api (100%), 26 | 20, 7 |

## ui-1 (flow)

Walk me through the life of an in-app draft filing such as an annual report. How does it show up as a to-do, how is it resumed, saved as a draft, then filed and paid, and how does the dashboard notice afterwards that the filing has been processed?

14 of 14 answer files indexed, 8 leaves, 4 groups.

| file | leaf: main component (share), size | group |
|---|---|---|
| `business-filings-ui/src/App.vue` | 165: business-filings-ui (100%), 19<br>255: business-filings-ui (100%), 35 | 3 |
| `business-filings-ui/src/components/Dashboard/TodoList.vue` | 165: business-filings-ui (100%), 19 | 3 |
| `business-filings-ui/src/mixins/common-mixin.ts` | 70: business-filings-ui (100%), 17 | 8 |
| `business-filings-ui/src/mixins/filing-mixin.ts` | 70: business-filings-ui (100%), 17 | 8 |
| `business-filings-ui/src/routes.ts` | 130: business-filings-ui (95%), 19 | 8 |
| `business-filings-ui/src/services/legal-services.ts` | 335: sbc-auth/auth-web (78%), 27 | 8 |
| `business-filings-ui/src/services/pay-services.ts` | 335: sbc-auth/auth-web (78%), 27 | 8 |
| `business-filings-ui/src/stores/configurationStore.ts` | 130: business-filings-ui (95%), 19 | 8 |
| `business-filings-ui/src/utils/navigate.ts` | 130: business-filings-ui (95%), 19 | 8 |
| `business-filings-ui/src/views/AnnualReport.vue` | 255: business-filings-ui (100%), 35 | 3 |
| `business-filings-ui/src/views/Dashboard.vue` | 165: business-filings-ui (100%), 19 | 3 |
| `lear/legal-api/src/legal_api/resources/v2/business/business_filings/business_filings.py` | 453: lear/legal-api (100%), 12<br>437: lear/legal-api (97%), 38 | 20, 5 |
| `lear/legal-api/src/legal_api/resources/v2/business/business_tasks.py` | 453: lear/legal-api (100%), 12 | 20 |
| `sbc-pay/pay-api/src/pay_api/resources/v1/code.py` | 407: sbc-pay/pay-api (96%), 45 | 20 |

## ui-2 (concept)

How does the UI decide which filings and actions a user may start for a business (for example, why a menu item is greyed out)? Where do the rules come from, and how are they combined with feature toggles on the client?

15 of 15 answer files indexed, 15 leaves, 7 groups.

| file | leaf: main component (share), size | group |
|---|---|---|
| `business-filings-ui/src/components/Dashboard/StaffNotation.vue` | 91: business-filings-ui (98%), 43<br>165: business-filings-ui (100%), 19 | 3 |
| `business-filings-ui/src/components/Dashboard/TodoList.vue` | 165: business-filings-ui (100%), 19 | 3 |
| `business-filings-ui/src/components/EntityInfo/EntityMenu.vue` | 298: business-filings-ui (97%), 29 | 3 |
| `business-filings-ui/src/enums/allowableActions.ts` | 119: business-filings-ui (100%), 24 | 9 |
| `business-filings-ui/src/enums/routes.ts` | 119: business-filings-ui (100%), 24 | 9 |
| `business-filings-ui/src/mixins/allowable-actions-mixin.ts` | 70: business-filings-ui (100%), 17 | 8 |
| `business-filings-ui/src/router.ts` | 130: business-filings-ui (95%), 19 | 8 |
| `business-filings-ui/src/services/legal-services.ts` | 335: sbc-auth/auth-web (78%), 27 | 8 |
| `business-filings-ui/src/stores/businessStore.ts` | 81: business-filings-ui (100%), 9 | 8 |
| `business-filings-ui/src/stores/rootStore.ts` | 81: business-filings-ui (100%), 9 | 8 |
| `business-filings-ui/src/utils/feature-flags.ts` | 129: business-filings-ui (100%), 13 | 9 |
| `business-filings-ui/src/views/Dashboard.vue` | 165: business-filings-ui (100%), 19 | 3 |
| `lear/legal-api/src/legal_api/models/business.py` | 439: lear/legal-api (95%), 76<br>437: lear/legal-api (97%), 38 | 23, 5 |
| `lear/legal-api/src/legal_api/resources/v2/business/business.py` | 453: lear/legal-api (100%), 12<br>373: lear/legal-api (100%), 12 | 20, 7 |
| `lear/legal-api/src/legal_api/services/authz.py` | 396: sbc-auth/auth-api (40%), 10<br>383: lear/legal-api (100%), 10 | 20, 5 |

## ui-3 (concept)

Some dashboards belong to a business that does not exist yet, such as a draft incorporation, registration, amalgamation or continuation-in application. How is this 'temporary business' modeled in the front end, and how does the app make it look like a business on the dashboard?

11 of 11 answer files indexed, 8 leaves, 2 groups.

| file | leaf: main component (share), size | group |
|---|---|---|
| `business-filings-ui/src/App.vue` | 165: business-filings-ui (100%), 19<br>255: business-filings-ui (100%), 35 | 3 |
| `business-filings-ui/src/components/Dashboard/FilingHistoryList.vue` | 91: business-filings-ui (98%), 43 | 3 |
| `business-filings-ui/src/components/Dashboard/TodoList.vue` | 165: business-filings-ui (100%), 19 | 3 |
| `business-filings-ui/src/mixins/allowable-actions-mixin.ts` | 70: business-filings-ui (100%), 17 | 8 |
| `business-filings-ui/src/mixins/name-request-mixin.ts` | 70: business-filings-ui (100%), 17 | 8 |
| `business-filings-ui/src/services/legal-services.ts` | 335: sbc-auth/auth-web (78%), 27 | 8 |
| `business-filings-ui/src/stores/businessStore.ts` | 81: business-filings-ui (100%), 9 | 8 |
| `business-filings-ui/src/stores/configurationStore.ts` | 130: business-filings-ui (95%), 19 | 8 |
| `business-filings-ui/src/stores/filingHistoryListStore.ts` | 23: business-filings-ui (100%), 23 | 8 |
| `business-filings-ui/src/stores/rootStore.ts` | 81: business-filings-ui (100%), 9 | 8 |
| `business-filings-ui/src/utils/set-base-route-and-business-id.ts` | 130: business-filings-ui (95%), 19 | 8 |

## ui-4 (change)

We need to support a new business entity type on the dashboard, with its own legal certification wording, director-compliance warnings and voluntary-dissolution dialog text. Where do these per-entity texts and rules live, how are they selected at runtime, and what else would have to change?

16 of 16 answer files indexed, 10 leaves, 3 groups.

| file | leaf: main component (share), size | group |
|---|---|---|
| `business-filings-ui/src/App.vue` | 165: business-filings-ui (100%), 19<br>255: business-filings-ui (100%), 35 | 3 |
| `business-filings-ui/src/components/Dashboard/FilingHistoryList/filings/DissolutionVoluntary.vue` | 91: business-filings-ui (98%), 43 | 3 |
| `business-filings-ui/src/components/Dashboard/TodoList.vue` | 165: business-filings-ui (100%), 19 | 3 |
| `business-filings-ui/src/components/common/Directors.vue` | 298: business-filings-ui (97%), 29 | 3 |
| `business-filings-ui/src/components/dialogs/ConfirmDissolutionDialog.vue` | 112: business-filings-ui (100%), 12 | 3 |
| `business-filings-ui/src/mixins/resource-lookup-mixin.ts` | 70: business-filings-ui (100%), 17 | 8 |
| `business-filings-ui/src/resources/CP.ts` | 129: business-filings-ui (100%), 13 | 9 |
| `business-filings-ui/src/resources/business-config.ts` | 129: business-filings-ui (100%), 13 | 9 |
| `business-filings-ui/src/resources/index.ts` | 130: business-filings-ui (95%), 19 | 8 |
| `business-filings-ui/src/stores/businessStore.ts` | 81: business-filings-ui (100%), 9 | 8 |
| `business-filings-ui/src/stores/rootStore.ts` | 81: business-filings-ui (100%), 9 | 8 |
| `business-filings-ui/src/utils/feature-flags.ts` | 129: business-filings-ui (100%), 13 | 9 |
| `business-filings-ui/src/utils/set-base-route-and-business-id.ts` | 130: business-filings-ui (95%), 19 | 8 |
| `business-filings-ui/src/views/AgmExtension.vue` | 299: business-filings-ui (100%), 9<br>255: business-filings-ui (100%), 35 | 3 |
| `business-filings-ui/src/views/AnnualReport.vue` | 255: business-filings-ui (100%), 35 | 3 |
| `business-filings-ui/src/views/StandaloneDirectorsFiling.vue` | 255: business-filings-ui (100%), 35 | 3 |

## ui-5 (change)

Suppose the back end adds a new filing type that users should start from the business menu, save as a draft and resume, and later see in the filing history. Which parts of the front end would need to change so it shows up correctly as an action, a to-do and a history entry?

16 of 16 answer files indexed, 11 leaves, 4 groups.

| file | leaf: main component (share), size | group |
|---|---|---|
| `business-filings-ui/src/components/Dashboard/FilingHistoryList.vue` | 91: business-filings-ui (98%), 43 | 3 |
| `business-filings-ui/src/components/Dashboard/FilingHistoryList/filings/DefaultFiling.vue` | 91: business-filings-ui (98%), 43 | 3 |
| `business-filings-ui/src/components/Dashboard/FilingHistoryList/filings/index.ts` | 91: business-filings-ui (98%), 43 | 3 |
| `business-filings-ui/src/components/Dashboard/TodoList.vue` | 165: business-filings-ui (100%), 19 | 3 |
| `business-filings-ui/src/components/EntityInfo/EntityMenu.vue` | 298: business-filings-ui (97%), 29 | 3 |
| `business-filings-ui/src/enums/allowableActions.ts` | 119: business-filings-ui (100%), 24 | 9 |
| `business-filings-ui/src/enums/routes.ts` | 119: business-filings-ui (100%), 24 | 9 |
| `business-filings-ui/src/mixins/allowable-actions-mixin.ts` | 70: business-filings-ui (100%), 17 | 8 |
| `business-filings-ui/src/mixins/common-mixin.ts` | 70: business-filings-ui (100%), 17 | 8 |
| `business-filings-ui/src/mixins/filing-mixin.ts` | 70: business-filings-ui (100%), 17 | 8 |
| `business-filings-ui/src/routes.ts` | 130: business-filings-ui (95%), 19 | 8 |
| `business-filings-ui/src/services/enum-utilities.ts` | 119: business-filings-ui (100%), 24 | 9 |
| `business-filings-ui/src/services/legal-services.ts` | 335: sbc-auth/auth-web (78%), 27 | 8 |
| `business-filings-ui/src/stores/filingHistoryListStore.ts` | 23: business-filings-ui (100%), 23 | 8 |
| `business-filings-ui/src/views/AgmExtension.vue` | 299: business-filings-ui (100%), 9<br>255: business-filings-ui (100%), 35 | 3 |
| `lear/legal-api/src/legal_api/resources/v2/business/business_tasks.py` | 453: lear/legal-api (100%), 12 | 20 |

## cross-0 (flow)

When a business user files a fee-bearing filing (say an annual report) from the business dashboard, what happens end to end, from submission through fee calculation, online payment and confirmation, until the filing is actually applied to the business record?

23 of 23 answer files indexed, 20 leaves, 9 groups.

| file | leaf: main component (share), size | group |
|---|---|---|
| `business-filings-ui/src/views/AnnualReport.vue` | 255: business-filings-ui (100%), 35 | 3 |
| `lear/jobs/future-effective-filings/file_future_effective.py` | 397: lear/jobs/involuntary-dissolutions (26%), 31 | 23 |
| `lear/legal-api/src/legal_api/config.py` | 451: lear/legal-api (100%), 47<br>243: sbc-auth/auth-api (33%), 12 | 20, 19 |
| `lear/legal-api/src/legal_api/models/filing.py` | 439: lear/legal-api (95%), 76<br>437: lear/legal-api (97%), 38<br>383: lear/legal-api (100%), 10 | 23, 5 |
| `lear/legal-api/src/legal_api/resources/v2/business/business_filings/business_filings.py` | 453: lear/legal-api (100%), 12<br>437: lear/legal-api (97%), 38 | 20, 5 |
| `lear/queue_services/business-pay/src/business_pay/resources/pay_filer.py` | 111: lear/queue_services/business-pay (79%), 19 | 14 |
| `lear/queue_services/business-pay/src/business_pay/services/__init__.py` | 111: lear/queue_services/business-pay (79%), 19 | 14 |
| `lear/queue_services/entity-filer/src/entity_filer/config.py` | 282: lear/queue_services/entity-emailer (26%), 19 | 20 |
| `lear/queue_services/entity-filer/src/entity_filer/worker.py` | 393: lear/queue_services/common (35%), 26<br>409: lear/queue_services/entity-filer (100%), 8 | 24, 5 |
| `lear/queue_services/entity-pay/src/entity_pay/worker.py` | 393: lear/queue_services/common (35%), 26 | 24 |
| `sbc-auth/auth-web/src/routes/router.ts` | 211: sbc-auth/auth-web (91%), 11 | 8 |
| `sbc-auth/auth-web/src/services/payment.services.ts` | 335: sbc-auth/auth-web (78%), 27 | 8 |
| `sbc-auth/auth-web/src/views/pay/PaymentReturnView.vue` | 138: sbc-auth/auth-web (97%), 35 | 3 |
| `sbc-pay/pay-api/src/pay_api/resources/v1/invoice.py` | 407: sbc-pay/pay-api (96%), 45 | 20 |
| `sbc-pay/pay-api/src/pay_api/services/auth.py` | 407: sbc-pay/pay-api (96%), 45 | 20 |
| `sbc-pay/pay-api/src/pay_api/services/base_payment_system.py` | 422: sbc-pay/pay-api (100%), 27<br>355: sbc-pay/pay-api (78%), 23<br>356: sbc-pay/pay-api (98%), 44 | 20, 6 |
| `sbc-pay/pay-api/src/pay_api/services/bcol_service.py` | 422: sbc-pay/pay-api (100%), 27 | 20 |
| `sbc-pay/pay-api/src/pay_api/services/gcp_queue_publisher.py` | 297: sbc-pay/pay-queue (50%), 12 | 20 |
| `sbc-pay/pay-api/src/pay_api/services/invoice.py` | 407: sbc-pay/pay-api (96%), 45<br>355: sbc-pay/pay-api (78%), 23<br>356: sbc-pay/pay-api (98%), 44 | 20, 6 |
| `sbc-pay/pay-api/src/pay_api/services/pad_service.py` | 422: sbc-pay/pay-api (100%), 27 | 20 |
| `sbc-pay/pay-api/src/pay_api/services/payment_service.py` | 422: sbc-pay/pay-api (100%), 27<br>355: sbc-pay/pay-api (78%), 23<br>356: sbc-pay/pay-api (98%), 44 | 20, 6 |
| `sbc-pay/pay-api/src/pay_api/services/payment_transaction.py` | 422: sbc-pay/pay-api (100%), 27<br>355: sbc-pay/pay-api (78%), 23<br>356: sbc-pay/pay-api (98%), 44 | 20, 6 |
| `sbc-pay/pay-api/src/pay_api/utils/util.py` | 422: sbc-pay/pay-api (100%), 27<br>356: sbc-pay/pay-api (98%), 44 | 20, 6 |

## cross-1 (flow)

How does a brand-new business (incorporation, registration, amalgamation or continuation) become linked to the user's account in the account/auth system, starting from the temporary draft and ending once the real business number exists?

10 of 10 answer files indexed, 14 leaves, 5 groups.

| file | leaf: main component (share), size | group |
|---|---|---|
| `lear/legal-api/src/legal_api/core/filing.py` | 439: lear/legal-api (95%), 76<br>437: lear/legal-api (97%), 38 | 23, 5 |
| `lear/legal-api/src/legal_api/models/filing.py` | 439: lear/legal-api (95%), 76<br>437: lear/legal-api (97%), 38<br>383: lear/legal-api (100%), 10 | 23, 5 |
| `lear/legal-api/src/legal_api/resources/v2/business/business.py` | 453: lear/legal-api (100%), 12<br>373: lear/legal-api (100%), 12 | 20, 7 |
| `lear/legal-api/src/legal_api/resources/v2/business/business_filings/business_filings.py` | 453: lear/legal-api (100%), 12<br>437: lear/legal-api (97%), 38 | 20, 5 |
| `lear/legal-api/src/legal_api/services/bootstrap.py` | 451: lear/legal-api (100%), 47<br>373: lear/legal-api (100%), 12 | 20, 7 |
| `lear/queue_services/entity-filer/src/entity_filer/filing_processors/filing_components/business_profile.py` | 449: lear/queue_services/entity-filer (90%), 20 | 23 |
| `lear/queue_services/entity-filer/src/entity_filer/worker.py` | 393: lear/queue_services/common (35%), 26<br>409: lear/queue_services/entity-filer (100%), 8 | 24, 5 |
| `sbc-auth/auth-api/src/auth_api/resources/v1/org.py` | 457: sbc-auth/auth-api (99%), 68<br>455: sbc-auth/auth-api (100%), 26 | 20, 7 |
| `sbc-auth/auth-api/src/auth_api/services/affiliation.py` | 461: sbc-auth/auth-api (100%), 16<br>454: sbc-auth/auth-api (100%), 14 | 23, 7 |
| `sbc-auth/queue_services/auth-queue/src/auth_queue/resources/worker.py` | 394: sbc-auth/queue_services/auth-queue (43%), 14 | 24 |

## cross-2 (concept)

How are a user's permissions on a specific business (who can view it, edit/file for it, or pay for it) modeled, and how do the legal, payment and UI layers each enforce them?

16 of 16 answer files indexed, 16 leaves, 8 groups.

| file | leaf: main component (share), size | group |
|---|---|---|
| `business-filings-ui/src/App.vue` | 165: business-filings-ui (100%), 19<br>255: business-filings-ui (100%), 35 | 3 |
| `business-filings-ui/src/services/auth-services.ts` | 335: sbc-auth/auth-web (78%), 27 | 8 |
| `business-filings-ui/src/stores/rootStore.ts` | 81: business-filings-ui (100%), 9 | 8 |
| `lear/legal-api/src/legal_api/resources/v2/business/business_directors.py` | 452: lear/legal-api (100%), 11 | 20 |
| `lear/legal-api/src/legal_api/resources/v2/business/business_filings/business_filings.py` | 453: lear/legal-api (100%), 12<br>437: lear/legal-api (97%), 38 | 20, 5 |
| `lear/legal-api/src/legal_api/resources/v2/business/business_parties.py` | 452: lear/legal-api (100%), 11 | 20 |
| `lear/legal-api/src/legal_api/services/authz.py` | 396: sbc-auth/auth-api (40%), 10<br>383: lear/legal-api (100%), 10 | 20, 5 |
| `sbc-auth/auth-api/migrations/versions/1c958b749a20_org_status_added_to_authorisation_view.py` | 177: sbc-auth/auth-api (100%), 11 | 0 |
| `sbc-auth/auth-api/src/auth_api/models/permissions.py` | 464: sbc-auth/auth-api (100%), 19 | 23 |
| `sbc-auth/auth-api/src/auth_api/models/views/authorization.py` | 463: sbc-auth/auth-api (100%), 15 | 23 |
| `sbc-auth/auth-api/src/auth_api/resources/v1/entity.py` | 457: sbc-auth/auth-api (99%), 68<br>455: sbc-auth/auth-api (100%), 26 | 20, 7 |
| `sbc-auth/auth-api/src/auth_api/services/authorization.py` | 457: sbc-auth/auth-api (99%), 68<br>455: sbc-auth/auth-api (100%), 26 | 20, 7 |
| `sbc-auth/auth-api/src/auth_api/services/permissions.py` | 457: sbc-auth/auth-api (99%), 68 | 20 |
| `sbc-pay/pay-api/src/pay_api/resources/v1/invoice.py` | 407: sbc-pay/pay-api (96%), 45 | 20 |
| `sbc-pay/pay-api/src/pay_api/services/auth.py` | 407: sbc-pay/pay-api (96%), 45 | 20 |
| `sbc-pay/pay-api/src/pay_api/utils/constants.py` | 246: sbc-pay/pay-api (74%), 23 | 14 |

## cross-3 (concept)

How do customer email notifications about filings work across the services: what triggers them, where do recipients and receipts come from, and what actually sends the email?

16 of 16 answer files indexed, 11 leaves, 6 groups.

| file | leaf: main component (share), size | group |
|---|---|---|
| `lear/legal-api/src/legal_api/resources/v2/admin/reviews.py` | 451: lear/legal-api (100%), 47 | 20 |
| `lear/legal-api/src/legal_api/services/bootstrap.py` | 451: lear/legal-api (100%), 47<br>373: lear/legal-api (100%), 12 | 20, 7 |
| `lear/queue_services/business-pay/src/business_pay/config.py` | 111: lear/queue_services/business-pay (79%), 19 | 14 |
| `lear/queue_services/business-pay/src/business_pay/resources/pay_filer.py` | 111: lear/queue_services/business-pay (79%), 19 | 14 |
| `lear/queue_services/business-pay/src/business_pay/services/__init__.py` | 111: lear/queue_services/business-pay (79%), 19 | 14 |
| `lear/queue_services/common/src/entity_queue_common/messages.py` | 370: lear/queue_services/common (38%), 21 | 20 |
| `lear/queue_services/entity-emailer/src/entity_emailer/config.py` | 282: lear/queue_services/entity-emailer (26%), 19 | 20 |
| `lear/queue_services/entity-emailer/src/entity_emailer/email_processors/__init__.py` | 429: lear/queue_services/entity-emailer (94%), 31 | 20 |
| `lear/queue_services/entity-emailer/src/entity_emailer/email_processors/dissolution_notification.py` | 429: lear/queue_services/entity-emailer (94%), 31<br>391: lear/queue_services/entity-emailer (82%), 17 | 20, 5 |
| `lear/queue_services/entity-emailer/src/entity_emailer/email_processors/registration_notification.py` | 429: lear/queue_services/entity-emailer (94%), 31 | 20 |
| `lear/queue_services/entity-emailer/src/entity_emailer/email_processors/restoration_notification.py` | 429: lear/queue_services/entity-emailer (94%), 31 | 20 |
| `lear/queue_services/entity-emailer/src/entity_emailer/worker.py` | 394: sbc-auth/queue_services/auth-queue (43%), 14<br>429: lear/queue_services/entity-emailer (94%), 31 | 24, 20 |
| `lear/queue_services/entity-filer/src/entity_filer/config.py` | 282: lear/queue_services/entity-emailer (26%), 19 | 20 |
| `lear/queue_services/entity-filer/src/entity_filer/filing_processors/filing_components/business_profile.py` | 449: lear/queue_services/entity-filer (90%), 20 | 23 |
| `lear/queue_services/entity-filer/src/entity_filer/worker.py` | 393: lear/queue_services/common (35%), 26<br>409: lear/queue_services/entity-filer (100%), 8 | 24, 5 |
| `lear/queue_services/entity-pay/src/entity_pay/worker.py` | 393: lear/queue_services/common (35%), 26 | 24 |

## cross-4 (change)

We want amalgamation applications, like continuations today, to go to registry staff for review after they are paid, instead of being applied right away. Where is this decided, and what else in the pipeline would the change touch?

8 of 8 answer files indexed, 11 leaves, 6 groups.

| file | leaf: main component (share), size | group |
|---|---|---|
| `lear/legal-api/src/legal_api/models/filing.py` | 439: lear/legal-api (95%), 76<br>437: lear/legal-api (97%), 38<br>383: lear/legal-api (100%), 10 | 23, 5 |
| `lear/legal-api/src/legal_api/resources/v2/admin/reviews.py` | 451: lear/legal-api (100%), 47 | 20 |
| `lear/legal-api/src/legal_api/resources/v2/business/business.py` | 453: lear/legal-api (100%), 12<br>373: lear/legal-api (100%), 12 | 20, 7 |
| `lear/legal-api/src/legal_api/resources/v2/business/business_filings/business_filings.py` | 453: lear/legal-api (100%), 12<br>437: lear/legal-api (97%), 38 | 20, 5 |
| `lear/queue_services/business-pay/src/business_pay/database/review.py` | 297: sbc-pay/pay-queue (50%), 12 | 20 |
| `lear/queue_services/business-pay/src/business_pay/resources/pay_filer.py` | 111: lear/queue_services/business-pay (79%), 19 | 14 |
| `lear/queue_services/entity-emailer/src/entity_emailer/worker.py` | 394: sbc-auth/queue_services/auth-queue (43%), 14<br>429: lear/queue_services/entity-emailer (94%), 31 | 24, 20 |
| `lear/queue_services/entity-pay/src/entity_pay/worker.py` | 393: lear/queue_services/common (35%), 26 | 24 |

## cross-5 (change)

Product wants the list of businesses on a user's account page (in the account/auth app) to show an extra piece of business information that only the legal registry knows. Where does that list's data come from, and what would need to change on each side?

9 of 9 answer files indexed, 14 leaves, 7 groups.

| file | leaf: main component (share), size | group |
|---|---|---|
| `lear/legal-api/src/legal_api/models/business.py` | 439: lear/legal-api (95%), 76<br>437: lear/legal-api (97%), 38 | 23, 5 |
| `lear/legal-api/src/legal_api/resources/v2/business/business.py` | 453: lear/legal-api (100%), 12<br>373: lear/legal-api (100%), 12 | 20, 7 |
| `lear/queue_services/entity-filer/src/entity_filer/filing_processors/filing_components/business_profile.py` | 449: lear/queue_services/entity-filer (90%), 20 | 23 |
| `lear/queue_services/entity-filer/src/entity_filer/worker.py` | 393: lear/queue_services/common (35%), 26<br>409: lear/queue_services/entity-filer (100%), 8 | 24, 5 |
| `sbc-auth/auth-api/src/auth_api/config.py` | 457: sbc-auth/auth-api (99%), 68<br>243: sbc-auth/auth-api (33%), 12 | 20, 19 |
| `sbc-auth/auth-api/src/auth_api/resources/v1/org.py` | 457: sbc-auth/auth-api (99%), 68<br>455: sbc-auth/auth-api (100%), 26 | 20, 7 |
| `sbc-auth/auth-api/src/auth_api/schemas/schemas/entity.json` | 338: sbc-auth/auth-api (98%), 41<br>337: sbc-auth/auth-api (100%), 21 | 17 |
| `sbc-auth/auth-api/src/auth_api/services/affiliation.py` | 461: sbc-auth/auth-api (100%), 16<br>454: sbc-auth/auth-api (100%), 14 | 23, 7 |
| `sbc-auth/auth-api/src/auth_api/services/entity.py` | 457: sbc-auth/auth-api (99%), 68 | 20 |
