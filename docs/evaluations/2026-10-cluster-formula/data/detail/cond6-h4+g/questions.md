## lear-filings-0 (flow)

Walk me through what happens when someone submits a brand-new incorporation application for a company that doesn't exist yet. How does it get a temporary identity, how is it validated and charged, and when and where do the real business record and registration number get created?

13 of 13 answer files indexed, 11 leaves, 3 groups.

| file | leaf: main component (share), size | group |
|---|---|---|
| `lear/legal-api/src/legal_api/models/filing.py` | 289: lear/legal-api (100%), 71<br>290: lear/legal-api (100%), 35 | 13 |
| `lear/legal-api/src/legal_api/resources/v2/business/business.py` | 291: lear/legal-api (100%), 21<br>290: lear/legal-api (100%), 35 | 13 |
| `lear/legal-api/src/legal_api/resources/v2/business/business_filings/business_filings.py` | 284: lear/legal-api (95%), 20<br>291: lear/legal-api (100%), 21<br>289: lear/legal-api (100%), 71<br>290: lear/legal-api (100%), 35 | 13 |
| `lear/legal-api/src/legal_api/services/bootstrap.py` | 218: lear/legal-api (100%), 13 | 13 |
| `lear/legal-api/src/legal_api/services/filings/validations/incorporation_application.py` | 281: lear/legal-api (100%), 40 | 13 |
| `lear/legal-api/src/legal_api/services/filings/validations/schemas.py` | 285: lear/legal-api (100%), 12 | 13 |
| `lear/legal-api/src/legal_api/services/filings/validations/validation.py` | 281: lear/legal-api (100%), 40 | 13 |
| `lear/legal-api/src/legal_api/services/namex.py` | 218: lear/legal-api (100%), 13 | 13 |
| `lear/queue_services/entity-filer/src/entity_filer/filing_processors/filing_components/business_info.py` | 275: lear/queue_services/entity-filer (100%), 11 | 25 |
| `lear/queue_services/entity-filer/src/entity_filer/filing_processors/filing_components/business_profile.py` | 276: lear/queue_services/entity-filer (100%), 29 | 25 |
| `lear/queue_services/entity-filer/src/entity_filer/filing_processors/filing_components/name_request.py` | 276: lear/queue_services/entity-filer (100%), 29 | 25 |
| `lear/queue_services/entity-filer/src/entity_filer/filing_processors/incorporation_filing.py` | 275: lear/queue_services/entity-filer (100%), 11 | 25 |
| `lear/queue_services/entity-filer/src/entity_filer/worker.py` | 360: lear/queue_services/entity-emailer (47%), 30<br>354: lear/queue_services/entity-filer (100%), 6<br>276: lear/queue_services/entity-filer (100%), 29<br>275: lear/queue_services/entity-filer (100%), 11 | 27, 25 |

## lear-filings-1 (flow)

Once a filing's invoice has been paid, how does the payment confirmation make the filing actually get applied to the business, and what's different for filings dated to take effect in the future?

13 of 13 answer files indexed, 14 leaves, 4 groups.

| file | leaf: main component (share), size | group |
|---|---|---|
| `lear/jobs/future-effective-filings/file_future_effective.py` | 346: lear/jobs/future-effective-filings (20%), 15 | 27 |
| `lear/legal-api/src/legal_api/core/filing.py` | 284: lear/legal-api (95%), 20<br>290: lear/legal-api (100%), 35 | 13 |
| `lear/legal-api/src/legal_api/models/filing.py` | 289: lear/legal-api (100%), 71<br>290: lear/legal-api (100%), 35 | 13 |
| `lear/legal-api/src/legal_api/resources/v2/business/business_filings/business_filings.py` | 284: lear/legal-api (95%), 20<br>291: lear/legal-api (100%), 21<br>289: lear/legal-api (100%), 71<br>290: lear/legal-api (100%), 35 | 13 |
| `lear/legal-api/src/legal_api/resources/v2/internal_services.py` | 318: lear/legal-api (100%), 27 | 13 |
| `lear/legal-api/src/legal_api/utils/legislation_datetime.py` | 281: lear/legal-api (100%), 40 | 13 |
| `lear/queue_services/business-pay/src/business_pay/database/filings.py` | 378: lear/queue_services/business-pay (100%), 22 | 25 |
| `lear/queue_services/business-pay/src/business_pay/resources/pay_filer.py` | 378: lear/queue_services/business-pay (100%), 22 | 25 |
| `lear/queue_services/common/src/entity_queue_common/messages.py` | 379: lear/queue_services/common (43%), 30 | 27 |
| `lear/queue_services/entity-filer/src/entity_filer/filing_meta.py` | 53: lear/data-tool (96%), 23 | 22 |
| `lear/queue_services/entity-filer/src/entity_filer/filing_processors/change_of_address.py` | 276: lear/queue_services/entity-filer (100%), 29 | 25 |
| `lear/queue_services/entity-filer/src/entity_filer/worker.py` | 360: lear/queue_services/entity-emailer (47%), 30<br>354: lear/queue_services/entity-filer (100%), 6<br>276: lear/queue_services/entity-filer (100%), 29<br>275: lear/queue_services/entity-filer (100%), 11 | 27, 25 |
| `lear/queue_services/entity-pay/src/entity_pay/worker.py` | 379: lear/queue_services/common (43%), 30 | 27 |

## lear-filings-2 (concept)

How is a filing's status lifecycle (draft, pending, paid, completed, staff review states) modeled, and what stops a filing from being edited or deleted once money is involved?

8 of 8 answer files indexed, 5 leaves, 2 groups.

| file | leaf: main component (share), size | group |
|---|---|---|
| `lear/legal-api/src/legal_api/core/filing.py` | 284: lear/legal-api (95%), 20<br>290: lear/legal-api (100%), 35 | 13 |
| `lear/legal-api/src/legal_api/exceptions/__init__.py` | 284: lear/legal-api (95%), 20 | 13 |
| `lear/legal-api/src/legal_api/models/filing.py` | 289: lear/legal-api (100%), 71<br>290: lear/legal-api (100%), 35 | 13 |
| `lear/legal-api/src/legal_api/models/review.py` | 289: lear/legal-api (100%), 71 | 13 |
| `lear/legal-api/src/legal_api/models/review_result.py` | 289: lear/legal-api (100%), 71 | 13 |
| `lear/legal-api/src/legal_api/resources/v2/admin/reviews.py` | 289: lear/legal-api (100%), 71 | 13 |
| `lear/legal-api/src/legal_api/resources/v2/business/business_filings/business_filings.py` | 284: lear/legal-api (95%), 20<br>291: lear/legal-api (100%), 21<br>289: lear/legal-api (100%), 71<br>290: lear/legal-api (100%), 35 | 13 |
| `lear/queue_services/business-pay/src/business_pay/resources/pay_filer.py` | 378: lear/queue_services/business-pay (100%), 22 | 25 |

## lear-filings-3 (concept)

How does the system decide which filings a given user may submit for a given business (for example, not allowing a change while another filing is pending, or when the company is not in good standing), and where is that decision enforced and surfaced?

7 of 7 answer files indexed, 6 leaves, 1 groups.

| file | leaf: main component (share), size | group |
|---|---|---|
| `lear/legal-api/src/legal_api/core/filing.py` | 284: lear/legal-api (95%), 20<br>290: lear/legal-api (100%), 35 | 13 |
| `lear/legal-api/src/legal_api/core/meta/filing.py` | 290: lear/legal-api (100%), 35 | 13 |
| `lear/legal-api/src/legal_api/models/business.py` | 289: lear/legal-api (100%), 71 | 13 |
| `lear/legal-api/src/legal_api/models/filing.py` | 289: lear/legal-api (100%), 71<br>290: lear/legal-api (100%), 35 | 13 |
| `lear/legal-api/src/legal_api/resources/v2/business/business.py` | 291: lear/legal-api (100%), 21<br>290: lear/legal-api (100%), 35 | 13 |
| `lear/legal-api/src/legal_api/resources/v2/business/business_filings/business_filings.py` | 284: lear/legal-api (95%), 20<br>291: lear/legal-api (100%), 21<br>289: lear/legal-api (100%), 71<br>290: lear/legal-api (100%), 35 | 13 |
| `lear/legal-api/src/legal_api/services/authz.py` | 218: lear/legal-api (100%), 13<br>281: lear/legal-api (100%), 40<br>290: lear/legal-api (100%), 35 | 13 |

## lear-filings-4 (change)

We need to add support for a brand-new type of business filing that is paid, changes business data, and produces a PDF. Which places in the API and the background services would I need to touch so it can be submitted, charged, applied, and shown with its documents?

16 of 16 answer files indexed, 15 leaves, 4 groups.

| file | leaf: main component (share), size | group |
|---|---|---|
| `lear/legal-api/report-templates/dissolution.html` | 177: lear/legal-api (98%), 41 | 19 |
| `lear/legal-api/src/legal_api/core/filing.py` | 284: lear/legal-api (95%), 20<br>290: lear/legal-api (100%), 35 | 13 |
| `lear/legal-api/src/legal_api/core/meta/filing.py` | 290: lear/legal-api (100%), 35 | 13 |
| `lear/legal-api/src/legal_api/models/filing.py` | 289: lear/legal-api (100%), 71<br>290: lear/legal-api (100%), 35 | 13 |
| `lear/legal-api/src/legal_api/reports/report.py` | 171: lear/legal-api (100%), 13<br>290: lear/legal-api (100%), 35 | 13 |
| `lear/legal-api/src/legal_api/resources/v2/business/business_filings/business_filings.py` | 284: lear/legal-api (95%), 20<br>291: lear/legal-api (100%), 21<br>289: lear/legal-api (100%), 71<br>290: lear/legal-api (100%), 35 | 13 |
| `lear/legal-api/src/legal_api/services/authz.py` | 218: lear/legal-api (100%), 13<br>281: lear/legal-api (100%), 40<br>290: lear/legal-api (100%), 35 | 13 |
| `lear/legal-api/src/legal_api/services/filings/validations/change_of_address.py` | 281: lear/legal-api (100%), 40 | 13 |
| `lear/legal-api/src/legal_api/services/filings/validations/schemas.py` | 285: lear/legal-api (100%), 12 | 13 |
| `lear/legal-api/src/legal_api/services/filings/validations/validation.py` | 281: lear/legal-api (100%), 40 | 13 |
| `lear/queue_services/common/src/entity_queue_common/messages.py` | 379: lear/queue_services/common (43%), 30 | 27 |
| `lear/queue_services/entity-emailer/src/entity_emailer/email_processors/filing_notification.py` | 24: lear/queue_services/entity-emailer (100%), 27 | 25 |
| `lear/queue_services/entity-emailer/src/entity_emailer/worker.py` | 360: lear/queue_services/entity-emailer (47%), 30<br>24: lear/queue_services/entity-emailer (100%), 27 | 27, 25 |
| `lear/queue_services/entity-filer/src/entity_filer/filing_processors/dissolution.py` | 275: lear/queue_services/entity-filer (100%), 11 | 25 |
| `lear/queue_services/entity-filer/src/entity_filer/filing_processors/filing_components/business_profile.py` | 276: lear/queue_services/entity-filer (100%), 29 | 25 |
| `lear/queue_services/entity-filer/src/entity_filer/worker.py` | 360: lear/queue_services/entity-emailer (47%), 30<br>354: lear/queue_services/entity-filer (100%), 6<br>276: lear/queue_services/entity-filer (100%), 29<br>275: lear/queue_services/entity-filer (100%), 11 | 27, 25 |

## lear-filings-5 (change)

Today only continuation-in applications go to a registry staff member for review after payment. If we wanted amalgamation applications to also require staff approval before they take effect, where would that change go and which other parts of the flow would it affect?

16 of 16 answer files indexed, 11 leaves, 4 groups.

| file | leaf: main component (share), size | group |
|---|---|---|
| `lear/jobs/future-effective-filings/file_future_effective.py` | 346: lear/jobs/future-effective-filings (20%), 15 | 27 |
| `lear/legal-api/src/legal_api/core/filing.py` | 284: lear/legal-api (95%), 20<br>290: lear/legal-api (100%), 35 | 13 |
| `lear/legal-api/src/legal_api/models/filing.py` | 289: lear/legal-api (100%), 71<br>290: lear/legal-api (100%), 35 | 13 |
| `lear/legal-api/src/legal_api/models/review.py` | 289: lear/legal-api (100%), 71 | 13 |
| `lear/legal-api/src/legal_api/models/review_result.py` | 289: lear/legal-api (100%), 71 | 13 |
| `lear/legal-api/src/legal_api/resources/v2/admin/reviews.py` | 289: lear/legal-api (100%), 71 | 13 |
| `lear/legal-api/src/legal_api/resources/v2/business/business_filings/business_documents.py` | 291: lear/legal-api (100%), 21 | 13 |
| `lear/legal-api/src/legal_api/resources/v2/business/business_filings/business_filings.py` | 284: lear/legal-api (95%), 20<br>291: lear/legal-api (100%), 21<br>289: lear/legal-api (100%), 71<br>290: lear/legal-api (100%), 35 | 13 |
| `lear/legal-api/src/legal_api/resources/v2/internal_services.py` | 318: lear/legal-api (100%), 27 | 13 |
| `lear/legal-api/src/legal_api/services/queue.py` | 246: lear/legal-api (100%), 45 | 14 |
| `lear/queue_services/business-pay/src/business_pay/database/filings.py` | 378: lear/queue_services/business-pay (100%), 22 | 25 |
| `lear/queue_services/business-pay/src/business_pay/database/review.py` | 378: lear/queue_services/business-pay (100%), 22 | 25 |
| `lear/queue_services/business-pay/src/business_pay/resources/pay_filer.py` | 378: lear/queue_services/business-pay (100%), 22 | 25 |
| `lear/queue_services/entity-emailer/src/entity_emailer/email_processors/amalgamation_notification.py` | 24: lear/queue_services/entity-emailer (100%), 27 | 25 |
| `lear/queue_services/entity-emailer/src/entity_emailer/worker.py` | 360: lear/queue_services/entity-emailer (47%), 30<br>24: lear/queue_services/entity-emailer (100%), 27 | 27, 25 |
| `lear/queue_services/entity-pay/src/entity_pay/worker.py` | 379: lear/queue_services/common (43%), 30 | 27 |

## lear-async-0 (flow)

When a client pays for a filing that has a date set in the future, what happens end to end? How does it eventually get applied to the business, and which services and scheduled jobs are involved?

9 of 9 answer files indexed, 12 leaves, 3 groups.

| file | leaf: main component (share), size | group |
|---|---|---|
| `lear/jobs/future-effective-filings/file_future_effective.py` | 346: lear/jobs/future-effective-filings (20%), 15 | 27 |
| `lear/legal-api/src/legal_api/models/filing.py` | 289: lear/legal-api (100%), 71<br>290: lear/legal-api (100%), 35 | 13 |
| `lear/legal-api/src/legal_api/resources/v2/admin/reviews.py` | 289: lear/legal-api (100%), 71 | 13 |
| `lear/legal-api/src/legal_api/resources/v2/business/business_filings/business_filings.py` | 284: lear/legal-api (95%), 20<br>291: lear/legal-api (100%), 21<br>289: lear/legal-api (100%), 71<br>290: lear/legal-api (100%), 35 | 13 |
| `lear/legal-api/src/legal_api/resources/v2/internal_services.py` | 318: lear/legal-api (100%), 27 | 13 |
| `lear/queue_services/business-pay/src/business_pay/resources/pay_filer.py` | 378: lear/queue_services/business-pay (100%), 22 | 25 |
| `lear/queue_services/common/src/entity_queue_common/messages.py` | 379: lear/queue_services/common (43%), 30 | 27 |
| `lear/queue_services/entity-filer/src/entity_filer/worker.py` | 360: lear/queue_services/entity-emailer (47%), 30<br>354: lear/queue_services/entity-filer (100%), 6<br>276: lear/queue_services/entity-filer (100%), 29<br>275: lear/queue_services/entity-filer (100%), 11 | 27, 25 |
| `lear/queue_services/entity-pay/src/entity_pay/worker.py` | 379: lear/queue_services/common (43%), 30 | 27 |

## lear-async-1 (flow)

How are filings kept in sync in both directions between the new registry system and the legacy COLIN Oracle system? What runs the sync, and how does it avoid re-sending or skipping filings?

9 of 9 answer files indexed, 8 leaves, 4 groups.

| file | leaf: main component (share), size | group |
|---|---|---|
| `lear/colin-api/src/colin_api/resources/event.py` | 152: lear/colin-api (93%), 29 | 22 |
| `lear/colin-api/src/colin_api/resources/filing.py` | 152: lear/colin-api (93%), 29<br>151: lear/colin-api (100%), 40 | 22 |
| `lear/jobs/update-colin-filings/update_colin_filings.py` | 366: lear/jobs/update-legal-filings (22%), 9 | 28 |
| `lear/jobs/update-legal-filings/update_legal_filings.py` | 366: lear/jobs/update-legal-filings (22%), 9 | 28 |
| `lear/legal-api/src/legal_api/models/colin_event_id.py` | 289: lear/legal-api (100%), 71 | 13 |
| `lear/legal-api/src/legal_api/models/filing.py` | 289: lear/legal-api (100%), 71<br>290: lear/legal-api (100%), 35 | 13 |
| `lear/legal-api/src/legal_api/resources/v2/business/business_filings/business_filings.py` | 284: lear/legal-api (95%), 20<br>291: lear/legal-api (100%), 21<br>289: lear/legal-api (100%), 71<br>290: lear/legal-api (100%), 35 | 13 |
| `lear/legal-api/src/legal_api/resources/v2/business/colin_sync.py` | 291: lear/legal-api (100%), 21 | 13 |
| `lear/legal-api/src/legal_api/services/queue.py` | 246: lear/legal-api (100%), 45 | 14 |

## lear-async-2 (flow)

How does a company that falls behind on its annual reports end up dissolved automatically? Which jobs, notices and queue messages are involved at each stage?

14 of 14 answer files indexed, 7 leaves, 4 groups.

| file | leaf: main component (share), size | group |
|---|---|---|
| `lear/jobs/furnishings/src/furnishings/stage_processors/post_processor.py` | 365: lear/jobs/furnishings (81%), 26 | 28 |
| `lear/jobs/furnishings/src/furnishings/stage_processors/stage_one.py` | 365: lear/jobs/furnishings (81%), 26 | 28 |
| `lear/jobs/furnishings/src/furnishings/stage_processors/stage_three.py` | 365: lear/jobs/furnishings (81%), 26 | 28 |
| `lear/jobs/furnishings/src/furnishings/stage_processors/stage_two.py` | 365: lear/jobs/furnishings (81%), 26 | 28 |
| `lear/jobs/furnishings/src/furnishings/worker.py` | 365: lear/jobs/furnishings (81%), 26 | 28 |
| `lear/jobs/involuntary-dissolutions/involuntary_dissolutions.py` | 366: lear/jobs/update-legal-filings (22%), 9<br>365: lear/jobs/furnishings (81%), 26 | 28 |
| `lear/legal-api/src/legal_api/models/batch_processing.py` | 289: lear/legal-api (100%), 71 | 13 |
| `lear/legal-api/src/legal_api/models/configuration.py` | 289: lear/legal-api (100%), 71 | 13 |
| `lear/legal-api/src/legal_api/models/furnishing.py` | 289: lear/legal-api (100%), 71 | 13 |
| `lear/legal-api/src/legal_api/resources/v2/business/colin_sync.py` | 291: lear/legal-api (100%), 21 | 13 |
| `lear/legal-api/src/legal_api/services/involuntary_dissolution.py` | 289: lear/legal-api (100%), 71 | 13 |
| `lear/queue_services/entity-emailer/src/entity_emailer/email_processors/involuntary_dissolution_stage_1_notification.py` | 24: lear/queue_services/entity-emailer (100%), 27 | 25 |
| `lear/queue_services/entity-emailer/src/entity_emailer/worker.py` | 360: lear/queue_services/entity-emailer (47%), 30<br>24: lear/queue_services/entity-emailer (100%), 27 | 27, 25 |
| `lear/queue_services/entity-filer/src/entity_filer/filing_processors/dissolution.py` | 275: lear/queue_services/entity-filer (100%), 11 | 25 |

## lear-async-3 (concept)

Queue messages can be delivered more than once. How does the system stop the same notification email being sent twice, and how is retrying versus dropping a message decided across the queue workers?

9 of 9 answer files indexed, 10 leaves, 2 groups.

| file | leaf: main component (share), size | group |
|---|---|---|
| `lear/queue_services/business-pay/src/business_pay/resources/pay_filer.py` | 378: lear/queue_services/business-pay (100%), 22 | 25 |
| `lear/queue_services/entity-bn/src/entity_bn/bn_processors/registration.py` | 234: lear/queue_services/entity-bn (100%), 15 | 25 |
| `lear/queue_services/entity-bn/src/entity_bn/worker.py` | 360: lear/queue_services/entity-emailer (47%), 30 | 27 |
| `lear/queue_services/entity-emailer/src/entity_emailer/message_tracker/tracker.py` | 214: lear/queue_services/entity-emailer (95%), 38<br>355: lear/queue_services/entity-emailer (100%), 6 | 25 |
| `lear/queue_services/entity-emailer/src/entity_emailer/worker.py` | 360: lear/queue_services/entity-emailer (47%), 30<br>24: lear/queue_services/entity-emailer (100%), 27 | 27, 25 |
| `lear/queue_services/entity-emailer/tracker/models/message_processing.py` | 355: lear/queue_services/entity-emailer (100%), 6 | 25 |
| `lear/queue_services/entity-emailer/tracker/services/message_processing_service.py` | 355: lear/queue_services/entity-emailer (100%), 6 | 25 |
| `lear/queue_services/entity-filer/src/entity_filer/worker.py` | 360: lear/queue_services/entity-emailer (47%), 30<br>354: lear/queue_services/entity-filer (100%), 6<br>276: lear/queue_services/entity-filer (100%), 29<br>275: lear/queue_services/entity-filer (100%), 11 | 27, 25 |
| `lear/queue_services/entity-pay/src/entity_pay/worker.py` | 379: lear/queue_services/common (43%), 30 | 27 |

## lear-async-4 (concept)

How does a business get its CRA business number (tax id), depending on the kind of entity? Once the number arrives, which downstream notifications and updates does it trigger?

13 of 13 answer files indexed, 12 leaves, 5 groups.

| file | leaf: main component (share), size | group |
|---|---|---|
| `lear/colin-api/src/colin_api/resources/business.py` | 152: lear/colin-api (93%), 29 | 22 |
| `lear/colin-api/src/colin_api/resources/program_account.py` | 152: lear/colin-api (93%), 29 | 22 |
| `lear/jobs/update-legal-filings/update_legal_filings.py` | 366: lear/jobs/update-legal-filings (22%), 9 | 28 |
| `lear/legal-api/src/legal_api/models/business.py` | 289: lear/legal-api (100%), 71 | 13 |
| `lear/legal-api/src/legal_api/resources/v2/business/colin_sync.py` | 291: lear/legal-api (100%), 21 | 13 |
| `lear/legal-api/src/legal_api/resources/v2/internal_services.py` | 318: lear/legal-api (100%), 27 | 13 |
| `lear/queue_services/entity-bn/src/entity_bn/bn_processors/registration.py` | 234: lear/queue_services/entity-bn (100%), 15 | 25 |
| `lear/queue_services/entity-bn/src/entity_bn/worker.py` | 360: lear/queue_services/entity-emailer (47%), 30 | 27 |
| `lear/queue_services/entity-digital-credentials/src/entity_digital_credentials/digital_credentials_processors/business_number.py` | 104: lear/queue_services/entity-digital-credentials (100%), 19 | 25 |
| `lear/queue_services/entity-digital-credentials/src/entity_digital_credentials/worker.py` | 104: lear/queue_services/entity-digital-credentials (100%), 19 | 25 |
| `lear/queue_services/entity-emailer/src/entity_emailer/email_processors/bn_notification.py` | 24: lear/queue_services/entity-emailer (100%), 27 | 25 |
| `lear/queue_services/entity-emailer/src/entity_emailer/worker.py` | 360: lear/queue_services/entity-emailer (47%), 30<br>24: lear/queue_services/entity-emailer (100%), 27 | 27, 25 |
| `lear/queue_services/entity-filer/src/entity_filer/worker.py` | 360: lear/queue_services/entity-emailer (47%), 30<br>354: lear/queue_services/entity-filer (100%), 6<br>276: lear/queue_services/entity-filer (100%), 29<br>275: lear/queue_services/entity-filer (100%), 11 | 27, 25 |

## lear-async-5 (change)

We want to send annual report reminder emails to cooperatives as well, and to stop sending a confirmation email when a change of directors completes. Where would these changes go, and what else would be affected?

12 of 12 answer files indexed, 12 leaves, 4 groups.

| file | leaf: main component (share), size | group |
|---|---|---|
| `lear/jobs/email-reminder/email_reminder.py` | 366: lear/jobs/update-legal-filings (22%), 9 | 28 |
| `lear/legal-api/src/legal_api/models/business.py` | 289: lear/legal-api (100%), 71 | 13 |
| `lear/legal-api/src/legal_api/models/filing.py` | 289: lear/legal-api (100%), 71<br>290: lear/legal-api (100%), 35 | 13 |
| `lear/queue_services/common/src/entity_queue_common/messages.py` | 379: lear/queue_services/common (43%), 30 | 27 |
| `lear/queue_services/entity-emailer/src/entity_emailer/email_processors/__init__.py` | 24: lear/queue_services/entity-emailer (100%), 27 | 25 |
| `lear/queue_services/entity-emailer/src/entity_emailer/email_processors/ar_reminder_notification.py` | 24: lear/queue_services/entity-emailer (100%), 27 | 25 |
| `lear/queue_services/entity-emailer/src/entity_emailer/email_processors/filing_notification.py` | 24: lear/queue_services/entity-emailer (100%), 27 | 25 |
| `lear/queue_services/entity-emailer/src/entity_emailer/email_templates/AR-REMINDER.html` | 102: lear/queue_services/entity-emailer (100%), 52 | 25 |
| `lear/queue_services/entity-emailer/src/entity_emailer/email_templates/BC-COD-COMPLETED.html` | 102: lear/queue_services/entity-emailer (100%), 52 | 25 |
| `lear/queue_services/entity-emailer/src/entity_emailer/message_tracker/tracker.py` | 214: lear/queue_services/entity-emailer (95%), 38<br>355: lear/queue_services/entity-emailer (100%), 6 | 25 |
| `lear/queue_services/entity-emailer/src/entity_emailer/worker.py` | 360: lear/queue_services/entity-emailer (47%), 30<br>24: lear/queue_services/entity-emailer (100%), 27 | 27, 25 |
| `lear/queue_services/entity-filer/src/entity_filer/worker.py` | 360: lear/queue_services/entity-emailer (47%), 30<br>354: lear/queue_services/entity-filer (100%), 6<br>276: lear/queue_services/entity-filer (100%), 29<br>275: lear/queue_services/entity-filer (100%), 11 | 27, 25 |

## auth-0 (flow)

Walk me through what happens end to end when an account administrator invites a new team member by email. How is the invitation created and emailed, what link does the invitee click, and what happens when the invitee accepts it and becomes a member?

14 of 14 answer files indexed, 10 leaves, 2 groups.

| file | leaf: main component (share), size | group |
|---|---|---|
| `sbc-auth/auth-api/src/auth_api/models/invitation.py` | 336: sbc-auth/auth-api (100%), 31 | 21 |
| `sbc-auth/auth-api/src/auth_api/models/membership.py` | 336: sbc-auth/auth-api (100%), 31 | 21 |
| `sbc-auth/auth-api/src/auth_api/resources/v1/invitation.py` | 294: sbc-auth/auth-api (100%), 50 | 21 |
| `sbc-auth/auth-api/src/auth_api/services/authorization.py` | 294: sbc-auth/auth-api (100%), 50 | 21 |
| `sbc-auth/auth-api/src/auth_api/services/invitation.py` | 351: sbc-auth/auth-api (97%), 34<br>352: sbc-auth/auth-api (100%), 40 | 21 |
| `sbc-auth/auth-api/src/auth_api/services/keycloak.py` | 351: sbc-auth/auth-api (97%), 34<br>294: sbc-auth/auth-api (100%), 50 | 21 |
| `sbc-auth/auth-api/src/auth_api/services/products.py` | 351: sbc-auth/auth-api (97%), 34<br>352: sbc-auth/auth-api (100%), 40 | 21 |
| `sbc-auth/auth-api/src/auth_api/services/task.py` | 351: sbc-auth/auth-api (97%), 34<br>184: sbc-auth/auth-api (100%), 18<br>352: sbc-auth/auth-api (100%), 40<br>148: sbc-auth/auth-api (100%), 37 | 21 |
| `sbc-auth/auth-api/src/auth_api/utils/account_mailer.py` | 352: sbc-auth/auth-api (100%), 40 | 21 |
| `sbc-auth/auth-web/src/routes/router.ts` | 235: sbc-auth/auth-web (100%), 14 | 7 |
| `sbc-auth/auth-web/src/services/invitation.services.ts` | 280: sbc-auth/auth-web (100%), 19 | 7 |
| `sbc-auth/auth-web/src/stores/org.ts` | 279: sbc-auth/auth-web (100%), 19 | 7 |
| `sbc-auth/auth-web/src/views/auth/AcceptInviteLandingView.vue` | 322: sbc-auth/auth-web (100%), 40 | 7 |
| `sbc-auth/auth-web/src/views/auth/AcceptInviteView.vue` | 322: sbc-auth/auth-web (100%), 40 | 7 |

## auth-1 (concept)

How are fine-grained permissions (for example, who can change the account address or invite members) modeled and enforced for a team member, depending on their role and on the account's status? Where do these rules live, and how does the web front end learn about them?

18 of 18 answer files indexed, 12 leaves, 3 groups.

| file | leaf: main component (share), size | group |
|---|---|---|
| `sbc-auth/auth-api/migrations/versions/2024_05_30_39b4f331c003_admin_view_address_permission.py` | 332: sbc-auth/auth-api (100%), 53 | 5 |
| `sbc-auth/auth-api/src/auth_api/__init__.py` | 351: sbc-auth/auth-api (97%), 34 | 21 |
| `sbc-auth/auth-api/src/auth_api/models/permissions.py` | 337: sbc-auth/auth-api (100%), 20 | 21 |
| `sbc-auth/auth-api/src/auth_api/models/views/authorization.py` | 336: sbc-auth/auth-api (100%), 31 | 21 |
| `sbc-auth/auth-api/src/auth_api/resources/v1/entity.py` | 294: sbc-auth/auth-api (100%), 50 | 21 |
| `sbc-auth/auth-api/src/auth_api/resources/v1/invitation.py` | 294: sbc-auth/auth-api (100%), 50 | 21 |
| `sbc-auth/auth-api/src/auth_api/resources/v1/org_authorizations.py` | 294: sbc-auth/auth-api (100%), 50 | 21 |
| `sbc-auth/auth-api/src/auth_api/resources/v1/permissions.py` | 294: sbc-auth/auth-api (100%), 50 | 21 |
| `sbc-auth/auth-api/src/auth_api/services/authorization.py` | 294: sbc-auth/auth-api (100%), 50 | 21 |
| `sbc-auth/auth-api/src/auth_api/services/membership.py` | 351: sbc-auth/auth-api (97%), 34<br>184: sbc-auth/auth-api (100%), 18<br>352: sbc-auth/auth-api (100%), 40 | 21 |
| `sbc-auth/auth-api/src/auth_api/services/permissions.py` | 294: sbc-auth/auth-api (100%), 50 | 21 |
| `sbc-auth/auth-api/src/auth_api/utils/enums.py` | 351: sbc-auth/auth-api (97%), 34 | 21 |
| `sbc-auth/auth-web/src/components/auth/account-settings/account-info/AccountInfo.vue` | 376: sbc-auth/auth-web (100%), 11<br>282: sbc-auth/auth-web (100%), 16 | 7 |
| `sbc-auth/auth-web/src/components/auth/account-settings/payment/AccountPaymentMethods.vue` | 282: sbc-auth/auth-web (100%), 16 | 7 |
| `sbc-auth/auth-web/src/services/permission.services.ts` | 280: sbc-auth/auth-web (100%), 19 | 7 |
| `sbc-auth/auth-web/src/stores/org.ts` | 279: sbc-auth/auth-web (100%), 19 | 7 |
| `sbc-auth/auth-web/src/util/common-util.ts` | 270: sbc-auth/auth-web (100%), 56 | 7 |
| `sbc-auth/auth-web/src/util/constants.ts` | 270: sbc-auth/auth-web (100%), 56 | 7 |

## auth-2 (flow)

How does a user add an existing business or a name request to their account's business list, and how is the claim verified? What happens on the reverse path, when a business is removed from the account?

10 of 10 answer files indexed, 9 leaves, 3 groups.

| file | leaf: main component (share), size | group |
|---|---|---|
| `sbc-auth/auth-api/src/auth_api/models/affiliation.py` | 336: sbc-auth/auth-api (100%), 31 | 21 |
| `sbc-auth/auth-api/src/auth_api/resources/v1/org.py` | 294: sbc-auth/auth-api (100%), 50 | 21 |
| `sbc-auth/auth-api/src/auth_api/services/activity_log_publisher.py` | 351: sbc-auth/auth-api (97%), 34 | 21 |
| `sbc-auth/auth-api/src/auth_api/services/affiliation.py` | 352: sbc-auth/auth-api (100%), 40<br>184: sbc-auth/auth-api (100%), 18 | 21 |
| `sbc-auth/auth-api/src/auth_api/services/entity.py` | 352: sbc-auth/auth-api (100%), 40 | 21 |
| `sbc-auth/auth-api/src/auth_api/services/rest_service.py` | 351: sbc-auth/auth-api (97%), 34 | 21 |
| `sbc-auth/auth-api/src/auth_api/utils/passcode.py` | 351: sbc-auth/auth-api (97%), 34 | 21 |
| `sbc-auth/auth-web/src/services/org.services.ts` | 280: sbc-auth/auth-web (100%), 19 | 7 |
| `sbc-auth/auth-web/src/stores/business.ts` | 270: sbc-auth/auth-web (100%), 56<br>279: sbc-auth/auth-web (100%), 19 | 7 |
| `sbc-auth/queue_services/auth-queue/src/auth_queue/resources/worker.py` | 306: sbc-auth/queue_services/account-mailer (58%), 19 | 18 |

## auth-3 (concept)

Some new accounts and some new administrators must be reviewed by registry staff before they become usable. How is this staff-review concept modeled, what creates a review item, and what happens when staff approve, reject or put a review on hold?

11 of 11 answer files indexed, 7 leaves, 2 groups.

| file | leaf: main component (share), size | group |
|---|---|---|
| `sbc-auth/auth-api/migrations/versions/5397c5a5b0ca_staff_pending_status_permissions.py` | 332: sbc-auth/auth-api (100%), 53 | 5 |
| `sbc-auth/auth-api/src/auth_api/models/membership.py` | 336: sbc-auth/auth-api (100%), 31 | 21 |
| `sbc-auth/auth-api/src/auth_api/models/task.py` | 336: sbc-auth/auth-api (100%), 31 | 21 |
| `sbc-auth/auth-api/src/auth_api/resources/v1/task.py` | 294: sbc-auth/auth-api (100%), 50 | 21 |
| `sbc-auth/auth-api/src/auth_api/services/affidavit.py` | 352: sbc-auth/auth-api (100%), 40 | 21 |
| `sbc-auth/auth-api/src/auth_api/services/invitation.py` | 351: sbc-auth/auth-api (97%), 34<br>352: sbc-auth/auth-api (100%), 40 | 21 |
| `sbc-auth/auth-api/src/auth_api/services/org.py` | 351: sbc-auth/auth-api (97%), 34<br>352: sbc-auth/auth-api (100%), 40 | 21 |
| `sbc-auth/auth-api/src/auth_api/services/permissions.py` | 294: sbc-auth/auth-api (100%), 50 | 21 |
| `sbc-auth/auth-api/src/auth_api/services/task.py` | 351: sbc-auth/auth-api (97%), 34<br>184: sbc-auth/auth-api (100%), 18<br>352: sbc-auth/auth-api (100%), 40<br>148: sbc-auth/auth-api (100%), 37 | 21 |
| `sbc-auth/auth-api/src/auth_api/utils/account_mailer.py` | 352: sbc-auth/auth-api (100%), 40 | 21 |
| `sbc-auth/auth-api/src/auth_api/utils/enums.py` | 351: sbc-auth/auth-api (97%), 34 | 21 |

## auth-4 (change)

We want to guarantee that an account can never be left without an active administrator: no admin should be able to leave the team, or be removed, if they are the last one. Where is the 'only administrator' rule enforced today, where are the gaps, and what would we need to touch in the API and the web app?

13 of 13 answer files indexed, 8 leaves, 2 groups.

| file | leaf: main component (share), size | group |
|---|---|---|
| `sbc-auth/auth-api/src/auth_api/exceptions/errors.py` | 184: sbc-auth/auth-api (100%), 18 | 21 |
| `sbc-auth/auth-api/src/auth_api/models/membership.py` | 336: sbc-auth/auth-api (100%), 31 | 21 |
| `sbc-auth/auth-api/src/auth_api/models/org.py` | 336: sbc-auth/auth-api (100%), 31<br>184: sbc-auth/auth-api (100%), 18 | 21 |
| `sbc-auth/auth-api/src/auth_api/resources/v1/org.py` | 294: sbc-auth/auth-api (100%), 50 | 21 |
| `sbc-auth/auth-api/src/auth_api/services/activity_log_publisher.py` | 351: sbc-auth/auth-api (97%), 34 | 21 |
| `sbc-auth/auth-api/src/auth_api/services/authorization.py` | 294: sbc-auth/auth-api (100%), 50 | 21 |
| `sbc-auth/auth-api/src/auth_api/services/keycloak.py` | 351: sbc-auth/auth-api (97%), 34<br>294: sbc-auth/auth-api (100%), 50 | 21 |
| `sbc-auth/auth-api/src/auth_api/services/membership.py` | 351: sbc-auth/auth-api (97%), 34<br>184: sbc-auth/auth-api (100%), 18<br>352: sbc-auth/auth-api (100%), 40 | 21 |
| `sbc-auth/auth-api/src/auth_api/services/products.py` | 351: sbc-auth/auth-api (97%), 34<br>352: sbc-auth/auth-api (100%), 40 | 21 |
| `sbc-auth/auth-api/src/auth_api/utils/account_mailer.py` | 352: sbc-auth/auth-api (100%), 40 | 21 |
| `sbc-auth/auth-web/src/components/auth/mixins/TeamManagementMixin.vue` | 247: sbc-auth/auth-web (100%), 24 | 7 |
| `sbc-auth/auth-web/src/services/org.services.ts` | 280: sbc-auth/auth-web (100%), 19 | 7 |
| `sbc-auth/auth-web/src/stores/org.ts` | 279: sbc-auth/auth-web (100%), 19 | 7 |

## auth-5 (change)

We want account administrators to see a new kind of entry in their account's activity history, for example when an API key is created. How do activity entries get from the place where an action happens into the history shown to the user, and what would we need to add for a new action type?

15 of 15 answer files indexed, 10 leaves, 4 groups.

| file | leaf: main component (share), size | group |
|---|---|---|
| `sbc-auth/auth-api/migrations/versions/1a46fdc4d630_permissons_for_activity_log.py` | 332: sbc-auth/auth-api (100%), 53 | 5 |
| `sbc-auth/auth-api/src/auth_api/config.py` | 352: sbc-auth/auth-api (100%), 40<br>294: sbc-auth/auth-api (100%), 50 | 21 |
| `sbc-auth/auth-api/src/auth_api/models/activity_log.py` | 336: sbc-auth/auth-api (100%), 31 | 21 |
| `sbc-auth/auth-api/src/auth_api/models/dataclass.py` | 351: sbc-auth/auth-api (97%), 34 | 21 |
| `sbc-auth/auth-api/src/auth_api/models/pubsub_message_processing.py` | 330: sbc-auth/auth-api (100%), 31 | 5 |
| `sbc-auth/auth-api/src/auth_api/resources/v1/activity_log.py` | 294: sbc-auth/auth-api (100%), 50 | 21 |
| `sbc-auth/auth-api/src/auth_api/services/activity_log.py` | 148: sbc-auth/auth-api (100%), 37 | 21 |
| `sbc-auth/auth-api/src/auth_api/services/activity_log_publisher.py` | 351: sbc-auth/auth-api (97%), 34 | 21 |
| `sbc-auth/auth-api/src/auth_api/services/authorization.py` | 294: sbc-auth/auth-api (100%), 50 | 21 |
| `sbc-auth/auth-api/src/auth_api/services/org.py` | 351: sbc-auth/auth-api (97%), 34<br>352: sbc-auth/auth-api (100%), 40 | 21 |
| `sbc-auth/auth-api/src/auth_api/services/permissions.py` | 294: sbc-auth/auth-api (100%), 50 | 21 |
| `sbc-auth/auth-api/src/auth_api/utils/enums.py` | 351: sbc-auth/auth-api (97%), 34 | 21 |
| `sbc-auth/auth-web/src/models/activityLog.ts` | 243: sbc-auth/auth-web (100%), 11 | 7 |
| `sbc-auth/auth-web/src/services/activityLog.services.ts` | 280: sbc-auth/auth-web (100%), 19 | 7 |
| `sbc-auth/queue_services/auth-queue/src/auth_queue/resources/worker.py` | 306: sbc-auth/queue_services/account-mailer (58%), 19 | 18 |

## pay-0 (flow)

When a business filing app asks the payment system to charge for a filing, what happens end to end, from the incoming request to the filing app being told the payment is done?

14 of 14 answer files indexed, 8 leaves, 1 groups.

| file | leaf: main component (share), size | group |
|---|---|---|
| `sbc-pay/pay-api/src/pay_api/factory/payment_system_factory.py` | 278: sbc-pay/pay-api (98%), 44 | 17 |
| `sbc-pay/pay-api/src/pay_api/models/distribution_code.py` | 178: sbc-pay/pay-api (100%), 31 | 17 |
| `sbc-pay/pay-api/src/pay_api/models/fee_schedule.py` | 179: sbc-pay/pay-api (100%), 40 | 17 |
| `sbc-pay/pay-api/src/pay_api/resources/v1/invoice.py` | 112: sbc-pay/pay-api (100%), 24 | 17 |
| `sbc-pay/pay-api/src/pay_api/services/base_payment_system.py` | 277: sbc-pay/pay-api (100%), 26<br>13: sbc-pay/pay-api (82%), 22<br>278: sbc-pay/pay-api (98%), 44 | 17 |
| `sbc-pay/pay-api/src/pay_api/services/bcol_service.py` | 278: sbc-pay/pay-api (98%), 44 | 17 |
| `sbc-pay/pay-api/src/pay_api/services/eft_service.py` | 277: sbc-pay/pay-api (100%), 26<br>278: sbc-pay/pay-api (98%), 44 | 17 |
| `sbc-pay/pay-api/src/pay_api/services/fee_schedule.py` | 13: sbc-pay/pay-api (82%), 22<br>264: sbc-pay/pay-api (100%), 23<br>179: sbc-pay/pay-api (100%), 40 | 17 |
| `sbc-pay/pay-api/src/pay_api/services/gcp_queue_publisher.py` | 278: sbc-pay/pay-api (98%), 44 | 17 |
| `sbc-pay/pay-api/src/pay_api/services/internal_pay_service.py` | 277: sbc-pay/pay-api (100%), 26 | 17 |
| `sbc-pay/pay-api/src/pay_api/services/pad_service.py` | 278: sbc-pay/pay-api (98%), 44 | 17 |
| `sbc-pay/pay-api/src/pay_api/services/payment_line_item.py` | 264: sbc-pay/pay-api (100%), 23 | 17 |
| `sbc-pay/pay-api/src/pay_api/services/payment_service.py` | 277: sbc-pay/pay-api (100%), 26<br>13: sbc-pay/pay-api (82%), 22<br>278: sbc-pay/pay-api (98%), 44 | 17 |
| `sbc-pay/pay-api/src/pay_api/utils/util.py` | 111: sbc-pay/pay-api (100%), 13<br>178: sbc-pay/pay-api (100%), 31 | 17 |

## pay-1 (flow)

Walk me through the lifecycle of a pre-authorized debit customer: from entering bank details, through the confirmation period and the daily batching of their purchases, to the bank settlement file that marks those purchases paid.

13 of 13 answer files indexed, 11 leaves, 3 groups.

| file | leaf: main component (share), size | group |
|---|---|---|
| `sbc-pay/jobs/ftp-poller/tasks/cas_poller_ftp.py` | 248: sbc-pay/jobs/ftp-poller (59%), 32 | 23 |
| `sbc-pay/jobs/ftp-poller/utils/utils.py` | 248: sbc-pay/jobs/ftp-poller (59%), 32 | 23 |
| `sbc-pay/jobs/payment-jobs/invoke_jobs.py` | 205: sbc-pay/jobs/payment-jobs (100%), 14 | 24 |
| `sbc-pay/jobs/payment-jobs/tasks/activate_pad_account_task.py` | 188: sbc-pay/jobs/payment-jobs (97%), 38 | 24 |
| `sbc-pay/jobs/payment-jobs/tasks/cfs_create_account_task.py` | 188: sbc-pay/jobs/payment-jobs (97%), 38 | 24 |
| `sbc-pay/jobs/payment-jobs/tasks/cfs_create_invoice_task.py` | 188: sbc-pay/jobs/payment-jobs (97%), 38 | 24 |
| `sbc-pay/pay-api/src/pay_api/config.py` | 112: sbc-pay/pay-api (100%), 24<br>278: sbc-pay/pay-api (98%), 44 | 17 |
| `sbc-pay/pay-api/src/pay_api/factory/payment_system_factory.py` | 278: sbc-pay/pay-api (98%), 44 | 17 |
| `sbc-pay/pay-api/src/pay_api/services/pad_service.py` | 278: sbc-pay/pay-api (98%), 44 | 17 |
| `sbc-pay/pay-api/src/pay_api/services/payment_account.py` | 277: sbc-pay/pay-api (100%), 26<br>13: sbc-pay/pay-api (82%), 22<br>278: sbc-pay/pay-api (98%), 44<br>264: sbc-pay/pay-api (100%), 23 | 17 |
| `sbc-pay/pay-queue/src/pay_queue/enums.py` | 172: sbc-pay/pay-queue (100%), 10 | 17 |
| `sbc-pay/pay-queue/src/pay_queue/resources/worker.py` | 105: sbc-pay/pay-queue (94%), 18 | 23 |
| `sbc-pay/pay-queue/src/pay_queue/services/payment_reconciliations.py` | 149: sbc-pay/pay-queue (100%), 16 | 17 |

## pay-2 (flow)

How does money a customer sends by electronic funds transfer to the government bank account end up paying their outstanding statement invoices, both in our database and in the government's receivables system?

11 of 11 answer files indexed, 13 leaves, 3 groups.

| file | leaf: main component (share), size | group |
|---|---|---|
| `sbc-pay/jobs/ftp-poller/tasks/eft_poller_ftp.py` | 248: sbc-pay/jobs/ftp-poller (59%), 32 | 23 |
| `sbc-pay/jobs/ftp-poller/utils/utils.py` | 248: sbc-pay/jobs/ftp-poller (59%), 32 | 23 |
| `sbc-pay/jobs/payment-jobs/invoke_jobs.py` | 205: sbc-pay/jobs/payment-jobs (100%), 14 | 24 |
| `sbc-pay/jobs/payment-jobs/tasks/eft_task.py` | 188: sbc-pay/jobs/payment-jobs (97%), 38 | 24 |
| `sbc-pay/jobs/payment-jobs/utils/auth_event.py` | 187: sbc-pay/jobs/payment-jobs (100%), 10 | 24 |
| `sbc-pay/pay-api/src/pay_api/services/eft_service.py` | 277: sbc-pay/pay-api (100%), 26<br>278: sbc-pay/pay-api (98%), 44 | 17 |
| `sbc-pay/pay-api/src/pay_api/services/eft_short_name_historical.py` | 179: sbc-pay/pay-api (100%), 40 | 17 |
| `sbc-pay/pay-api/src/pay_api/services/eft_short_names.py` | 112: sbc-pay/pay-api (100%), 24<br>13: sbc-pay/pay-api (82%), 22<br>278: sbc-pay/pay-api (98%), 44<br>264: sbc-pay/pay-api (100%), 23 | 17 |
| `sbc-pay/pay-queue/src/pay_queue/resources/worker.py` | 105: sbc-pay/pay-queue (94%), 18 | 23 |
| `sbc-pay/pay-queue/src/pay_queue/services/eft/eft_reconciliation.py` | 149: sbc-pay/pay-queue (100%), 16 | 17 |
| `sbc-pay/pay-queue/src/pay_queue/services/eft/eft_record.py` | 172: sbc-pay/pay-queue (100%), 10 | 17 |

## pay-3 (concept)

How is an account 'freeze' or 'lock' (after a bounced bank debit or an overdue electronic-transfer statement) modeled, where is it set, what blocks new charges while it is in place, and how does it get lifted?

12 of 12 answer files indexed, 8 leaves, 2 groups.

| file | leaf: main component (share), size | group |
|---|---|---|
| `sbc-pay/jobs/payment-jobs/tasks/cfs_create_invoice_task.py` | 188: sbc-pay/jobs/payment-jobs (97%), 38 | 24 |
| `sbc-pay/jobs/payment-jobs/tasks/statement_due_task.py` | 187: sbc-pay/jobs/payment-jobs (100%), 10<br>13: sbc-pay/pay-api (82%), 22 | 24, 17 |
| `sbc-pay/jobs/payment-jobs/utils/auth_event.py` | 187: sbc-pay/jobs/payment-jobs (100%), 10 | 24 |
| `sbc-pay/pay-api/src/pay_api/models/payment_account.py` | 179: sbc-pay/pay-api (100%), 40 | 17 |
| `sbc-pay/pay-api/src/pay_api/services/base_payment_system.py` | 277: sbc-pay/pay-api (100%), 26<br>13: sbc-pay/pay-api (82%), 22<br>278: sbc-pay/pay-api (98%), 44 | 17 |
| `sbc-pay/pay-api/src/pay_api/services/eft_service.py` | 277: sbc-pay/pay-api (100%), 26<br>278: sbc-pay/pay-api (98%), 44 | 17 |
| `sbc-pay/pay-api/src/pay_api/services/non_sufficient_funds.py` | 264: sbc-pay/pay-api (100%), 23 | 17 |
| `sbc-pay/pay-api/src/pay_api/services/pad_service.py` | 278: sbc-pay/pay-api (98%), 44 | 17 |
| `sbc-pay/pay-api/src/pay_api/services/payment_account.py` | 277: sbc-pay/pay-api (100%), 26<br>13: sbc-pay/pay-api (82%), 22<br>278: sbc-pay/pay-api (98%), 44<br>264: sbc-pay/pay-api (100%), 23 | 17 |
| `sbc-pay/pay-api/src/pay_api/services/payment_transaction.py` | 277: sbc-pay/pay-api (100%), 26<br>13: sbc-pay/pay-api (82%), 22<br>264: sbc-pay/pay-api (100%), 23<br>278: sbc-pay/pay-api (98%), 44 | 17 |
| `sbc-pay/pay-api/src/pay_api/utils/enums.py` | 277: sbc-pay/pay-api (100%), 26 | 17 |
| `sbc-pay/pay-queue/src/pay_queue/services/payment_reconciliations.py` | 149: sbc-pay/pay-queue (100%), 16 | 17 |

## pay-4 (concept)

How are refunds handled differently for each way a customer can pay, and how does a refund move from 'requested' to confirmed for card and BC Online payments?

15 of 15 answer files indexed, 7 leaves, 3 groups.

| file | leaf: main component (share), size | group |
|---|---|---|
| `sbc-pay/jobs/payment-jobs/services/oracle.py` | 248: sbc-pay/jobs/ftp-poller (59%), 32 | 23 |
| `sbc-pay/jobs/payment-jobs/tasks/bcol_refund_confirmation_task.py` | 188: sbc-pay/jobs/payment-jobs (97%), 38 | 24 |
| `sbc-pay/jobs/payment-jobs/tasks/cfs_create_invoice_task.py` | 188: sbc-pay/jobs/payment-jobs (97%), 38 | 24 |
| `sbc-pay/jobs/payment-jobs/tasks/direct_pay_automated_refund_task.py` | 188: sbc-pay/jobs/payment-jobs (97%), 38 | 24 |
| `sbc-pay/pay-api/src/pay_api/factory/payment_system_factory.py` | 278: sbc-pay/pay-api (98%), 44 | 17 |
| `sbc-pay/pay-api/src/pay_api/resources/v1/refund.py` | 112: sbc-pay/pay-api (100%), 24 | 17 |
| `sbc-pay/pay-api/src/pay_api/services/base_payment_system.py` | 277: sbc-pay/pay-api (100%), 26<br>13: sbc-pay/pay-api (82%), 22<br>278: sbc-pay/pay-api (98%), 44 | 17 |
| `sbc-pay/pay-api/src/pay_api/services/bcol_service.py` | 278: sbc-pay/pay-api (98%), 44 | 17 |
| `sbc-pay/pay-api/src/pay_api/services/direct_pay_service.py` | 277: sbc-pay/pay-api (100%), 26<br>13: sbc-pay/pay-api (82%), 22<br>278: sbc-pay/pay-api (98%), 44 | 17 |
| `sbc-pay/pay-api/src/pay_api/services/eft_refund.py` | 278: sbc-pay/pay-api (98%), 44 | 17 |
| `sbc-pay/pay-api/src/pay_api/services/eft_service.py` | 277: sbc-pay/pay-api (100%), 26<br>278: sbc-pay/pay-api (98%), 44 | 17 |
| `sbc-pay/pay-api/src/pay_api/services/internal_pay_service.py` | 277: sbc-pay/pay-api (100%), 26 | 17 |
| `sbc-pay/pay-api/src/pay_api/services/pad_service.py` | 278: sbc-pay/pay-api (98%), 44 | 17 |
| `sbc-pay/pay-api/src/pay_api/services/refund.py` | 277: sbc-pay/pay-api (100%), 26<br>13: sbc-pay/pay-api (82%), 22<br>278: sbc-pay/pay-api (98%), 44<br>179: sbc-pay/pay-api (100%), 40 | 17 |
| `sbc-pay/pay-api/src/pay_api/utils/constants.py` | 278: sbc-pay/pay-api (98%), 44 | 17 |

## pay-5 (change)

We need to add a new payment method where purchases are recorded immediately but invoiced in the government receivables system later by a batch, and settled through the bank settlement file. Where would this be implemented and what else would need updating?

14 of 14 answer files indexed, 7 leaves, 2 groups.

| file | leaf: main component (share), size | group |
|---|---|---|
| `sbc-pay/jobs/payment-jobs/tasks/cfs_create_account_task.py` | 188: sbc-pay/jobs/payment-jobs (97%), 38 | 24 |
| `sbc-pay/jobs/payment-jobs/tasks/cfs_create_invoice_task.py` | 188: sbc-pay/jobs/payment-jobs (97%), 38 | 24 |
| `sbc-pay/jobs/payment-jobs/tasks/ejv_partner_distribution_task.py` | 188: sbc-pay/jobs/payment-jobs (97%), 38 | 24 |
| `sbc-pay/pay-api/src/pay_api/factory/payment_system_factory.py` | 278: sbc-pay/pay-api (98%), 44 | 17 |
| `sbc-pay/pay-api/src/pay_api/services/base_payment_system.py` | 277: sbc-pay/pay-api (100%), 26<br>13: sbc-pay/pay-api (82%), 22<br>278: sbc-pay/pay-api (98%), 44 | 17 |
| `sbc-pay/pay-api/src/pay_api/services/cfs_service.py` | 278: sbc-pay/pay-api (98%), 44 | 17 |
| `sbc-pay/pay-api/src/pay_api/services/eft_service.py` | 277: sbc-pay/pay-api (100%), 26<br>278: sbc-pay/pay-api (98%), 44 | 17 |
| `sbc-pay/pay-api/src/pay_api/services/pad_service.py` | 278: sbc-pay/pay-api (98%), 44 | 17 |
| `sbc-pay/pay-api/src/pay_api/services/payment_service.py` | 277: sbc-pay/pay-api (100%), 26<br>13: sbc-pay/pay-api (82%), 22<br>278: sbc-pay/pay-api (98%), 44 | 17 |
| `sbc-pay/pay-api/src/pay_api/services/refund.py` | 277: sbc-pay/pay-api (100%), 26<br>13: sbc-pay/pay-api (82%), 22<br>278: sbc-pay/pay-api (98%), 44<br>179: sbc-pay/pay-api (100%), 40 | 17 |
| `sbc-pay/pay-api/src/pay_api/utils/constants.py` | 278: sbc-pay/pay-api (98%), 44 | 17 |
| `sbc-pay/pay-api/src/pay_api/utils/enums.py` | 277: sbc-pay/pay-api (100%), 26 | 17 |
| `sbc-pay/pay-queue/src/pay_queue/enums.py` | 172: sbc-pay/pay-queue (100%), 10 | 17 |
| `sbc-pay/pay-queue/src/pay_queue/services/payment_reconciliations.py` | 149: sbc-pay/pay-queue (100%), 16 | 17 |

## ui-0 (flow)

When a user opens a business's dashboard URL in this front end, what happens from page load to the point where the business info, to-dos and filing history are on screen? How does the app learn which business to load and where the API is, and how does it decide whether the user may see the business?

16 of 16 answer files indexed, 6 leaves, 2 groups.

| file | leaf: main component (share), size | group |
|---|---|---|
| `business-filings-ui/src/App.vue` | 232: business-filings-ui (100%), 37<br>292: business-filings-ui (100%), 33<br>195: business-filings-ui (100%), 45 | 10 |
| `business-filings-ui/src/axios-auth.ts` | 232: business-filings-ui (100%), 37 | 10 |
| `business-filings-ui/src/components/Dashboard/FilingHistoryList.vue` | 271: business-filings-ui (100%), 11 | 10 |
| `business-filings-ui/src/components/Dashboard/TodoList.vue` | 162: business-filings-ui (100%), 12 | 10 |
| `business-filings-ui/src/main.ts` | 232: business-filings-ui (100%), 37 | 10 |
| `business-filings-ui/src/router.ts` | 232: business-filings-ui (100%), 37 | 10 |
| `business-filings-ui/src/routes.ts` | 232: business-filings-ui (100%), 37 | 10 |
| `business-filings-ui/src/services/auth-services.ts` | 232: business-filings-ui (100%), 37 | 10 |
| `business-filings-ui/src/services/legal-services.ts` | 232: business-filings-ui (100%), 37<br>195: business-filings-ui (100%), 45 | 10 |
| `business-filings-ui/src/stores/businessStore.ts` | 232: business-filings-ui (100%), 37 | 10 |
| `business-filings-ui/src/stores/configurationStore.ts` | 232: business-filings-ui (100%), 37 | 10 |
| `business-filings-ui/src/stores/filingHistoryListStore.ts` | 232: business-filings-ui (100%), 37 | 10 |
| `business-filings-ui/src/stores/rootStore.ts` | 232: business-filings-ui (100%), 37<br>292: business-filings-ui (100%), 33 | 10 |
| `business-filings-ui/src/utils/set-base-route-and-business-id.ts` | 232: business-filings-ui (100%), 37 | 10 |
| `business-filings-ui/src/views/Dashboard.vue` | 195: business-filings-ui (100%), 45 | 10 |
| `sbc-auth/auth-api/src/auth_api/resources/v1/entity.py` | 294: sbc-auth/auth-api (100%), 50 | 21 |

## ui-1 (flow)

Walk me through the life of an in-app draft filing such as an annual report. How does it show up as a to-do, how is it resumed, saved as a draft, then filed and paid, and how does the dashboard notice afterwards that the filing has been processed?

14 of 14 answer files indexed, 9 leaves, 3 groups.

| file | leaf: main component (share), size | group |
|---|---|---|
| `business-filings-ui/src/App.vue` | 232: business-filings-ui (100%), 37<br>292: business-filings-ui (100%), 33<br>195: business-filings-ui (100%), 45 | 10 |
| `business-filings-ui/src/components/Dashboard/TodoList.vue` | 162: business-filings-ui (100%), 12 | 10 |
| `business-filings-ui/src/mixins/common-mixin.ts` | 195: business-filings-ui (100%), 45 | 10 |
| `business-filings-ui/src/mixins/filing-mixin.ts` | 292: business-filings-ui (100%), 33 | 10 |
| `business-filings-ui/src/routes.ts` | 232: business-filings-ui (100%), 37 | 10 |
| `business-filings-ui/src/services/legal-services.ts` | 232: business-filings-ui (100%), 37<br>195: business-filings-ui (100%), 45 | 10 |
| `business-filings-ui/src/services/pay-services.ts` | 162: business-filings-ui (100%), 12 | 10 |
| `business-filings-ui/src/stores/configurationStore.ts` | 232: business-filings-ui (100%), 37 | 10 |
| `business-filings-ui/src/utils/navigate.ts` | 232: business-filings-ui (100%), 37 | 10 |
| `business-filings-ui/src/views/AnnualReport.vue` | 195: business-filings-ui (100%), 45 | 10 |
| `business-filings-ui/src/views/Dashboard.vue` | 195: business-filings-ui (100%), 45 | 10 |
| `lear/legal-api/src/legal_api/resources/v2/business/business_filings/business_filings.py` | 284: lear/legal-api (95%), 20<br>291: lear/legal-api (100%), 21<br>289: lear/legal-api (100%), 71<br>290: lear/legal-api (100%), 35 | 13 |
| `lear/legal-api/src/legal_api/resources/v2/business/business_tasks.py` | 291: lear/legal-api (100%), 21 | 13 |
| `sbc-pay/pay-api/src/pay_api/resources/v1/code.py` | 111: sbc-pay/pay-api (100%), 13 | 17 |

## ui-2 (concept)

How does the UI decide which filings and actions a user may start for a business (for example, why a menu item is greyed out)? Where do the rules come from, and how are they combined with feature toggles on the client?

15 of 15 answer files indexed, 11 leaves, 2 groups.

| file | leaf: main component (share), size | group |
|---|---|---|
| `business-filings-ui/src/components/Dashboard/StaffNotation.vue` | 271: business-filings-ui (100%), 11 | 10 |
| `business-filings-ui/src/components/Dashboard/TodoList.vue` | 162: business-filings-ui (100%), 12 | 10 |
| `business-filings-ui/src/components/EntityInfo/EntityMenu.vue` | 271: business-filings-ui (100%), 11 | 10 |
| `business-filings-ui/src/enums/allowableActions.ts` | 209: business-filings-ui (100%), 22 | 10 |
| `business-filings-ui/src/enums/routes.ts` | 232: business-filings-ui (100%), 37 | 10 |
| `business-filings-ui/src/mixins/allowable-actions-mixin.ts` | 292: business-filings-ui (100%), 33 | 10 |
| `business-filings-ui/src/router.ts` | 232: business-filings-ui (100%), 37 | 10 |
| `business-filings-ui/src/services/legal-services.ts` | 232: business-filings-ui (100%), 37<br>195: business-filings-ui (100%), 45 | 10 |
| `business-filings-ui/src/stores/businessStore.ts` | 232: business-filings-ui (100%), 37 | 10 |
| `business-filings-ui/src/stores/rootStore.ts` | 232: business-filings-ui (100%), 37<br>292: business-filings-ui (100%), 33 | 10 |
| `business-filings-ui/src/utils/feature-flags.ts` | 232: business-filings-ui (100%), 37 | 10 |
| `business-filings-ui/src/views/Dashboard.vue` | 195: business-filings-ui (100%), 45 | 10 |
| `lear/legal-api/src/legal_api/models/business.py` | 289: lear/legal-api (100%), 71 | 13 |
| `lear/legal-api/src/legal_api/resources/v2/business/business.py` | 291: lear/legal-api (100%), 21<br>290: lear/legal-api (100%), 35 | 13 |
| `lear/legal-api/src/legal_api/services/authz.py` | 218: lear/legal-api (100%), 13<br>281: lear/legal-api (100%), 40<br>290: lear/legal-api (100%), 35 | 13 |

## ui-3 (concept)

Some dashboards belong to a business that does not exist yet, such as a draft incorporation, registration, amalgamation or continuation-in application. How is this 'temporary business' modeled in the front end, and how does the app make it look like a business on the dashboard?

11 of 11 answer files indexed, 5 leaves, 1 groups.

| file | leaf: main component (share), size | group |
|---|---|---|
| `business-filings-ui/src/App.vue` | 232: business-filings-ui (100%), 37<br>292: business-filings-ui (100%), 33<br>195: business-filings-ui (100%), 45 | 10 |
| `business-filings-ui/src/components/Dashboard/FilingHistoryList.vue` | 271: business-filings-ui (100%), 11 | 10 |
| `business-filings-ui/src/components/Dashboard/TodoList.vue` | 162: business-filings-ui (100%), 12 | 10 |
| `business-filings-ui/src/mixins/allowable-actions-mixin.ts` | 292: business-filings-ui (100%), 33 | 10 |
| `business-filings-ui/src/mixins/name-request-mixin.ts` | 292: business-filings-ui (100%), 33 | 10 |
| `business-filings-ui/src/services/legal-services.ts` | 232: business-filings-ui (100%), 37<br>195: business-filings-ui (100%), 45 | 10 |
| `business-filings-ui/src/stores/businessStore.ts` | 232: business-filings-ui (100%), 37 | 10 |
| `business-filings-ui/src/stores/configurationStore.ts` | 232: business-filings-ui (100%), 37 | 10 |
| `business-filings-ui/src/stores/filingHistoryListStore.ts` | 232: business-filings-ui (100%), 37 | 10 |
| `business-filings-ui/src/stores/rootStore.ts` | 232: business-filings-ui (100%), 37<br>292: business-filings-ui (100%), 33 | 10 |
| `business-filings-ui/src/utils/set-base-route-and-business-id.ts` | 232: business-filings-ui (100%), 37 | 10 |

## ui-4 (change)

We need to support a new business entity type on the dashboard, with its own legal certification wording, director-compliance warnings and voluntary-dissolution dialog text. Where do these per-entity texts and rules live, how are they selected at runtime, and what else would have to change?

16 of 16 answer files indexed, 8 leaves, 1 groups.

| file | leaf: main component (share), size | group |
|---|---|---|
| `business-filings-ui/src/App.vue` | 232: business-filings-ui (100%), 37<br>292: business-filings-ui (100%), 33<br>195: business-filings-ui (100%), 45 | 10 |
| `business-filings-ui/src/components/Dashboard/FilingHistoryList/filings/DissolutionVoluntary.vue` | 334: business-filings-ui (100%), 31 | 10 |
| `business-filings-ui/src/components/Dashboard/TodoList.vue` | 162: business-filings-ui (100%), 12 | 10 |
| `business-filings-ui/src/components/common/Directors.vue` | 249: business-filings-ui (100%), 26 | 10 |
| `business-filings-ui/src/components/dialogs/ConfirmDissolutionDialog.vue` | 231: business-filings-ui (100%), 27 | 10 |
| `business-filings-ui/src/mixins/resource-lookup-mixin.ts` | 140: business-filings-ui (100%), 15 | 10 |
| `business-filings-ui/src/resources/CP.ts` | 140: business-filings-ui (100%), 15 | 10 |
| `business-filings-ui/src/resources/business-config.ts` | 140: business-filings-ui (100%), 15 | 10 |
| `business-filings-ui/src/resources/index.ts` | 232: business-filings-ui (100%), 37 | 10 |
| `business-filings-ui/src/stores/businessStore.ts` | 232: business-filings-ui (100%), 37 | 10 |
| `business-filings-ui/src/stores/rootStore.ts` | 232: business-filings-ui (100%), 37<br>292: business-filings-ui (100%), 33 | 10 |
| `business-filings-ui/src/utils/feature-flags.ts` | 232: business-filings-ui (100%), 37 | 10 |
| `business-filings-ui/src/utils/set-base-route-and-business-id.ts` | 232: business-filings-ui (100%), 37 | 10 |
| `business-filings-ui/src/views/AgmExtension.vue` | 195: business-filings-ui (100%), 45 | 10 |
| `business-filings-ui/src/views/AnnualReport.vue` | 195: business-filings-ui (100%), 45 | 10 |
| `business-filings-ui/src/views/StandaloneDirectorsFiling.vue` | 195: business-filings-ui (100%), 45 | 10 |

## ui-5 (change)

Suppose the back end adds a new filing type that users should start from the business menu, save as a draft and resume, and later see in the filing history. Which parts of the front end would need to change so it shows up correctly as an action, a to-do and a history entry?

16 of 16 answer files indexed, 9 leaves, 2 groups.

| file | leaf: main component (share), size | group |
|---|---|---|
| `business-filings-ui/src/components/Dashboard/FilingHistoryList.vue` | 271: business-filings-ui (100%), 11 | 10 |
| `business-filings-ui/src/components/Dashboard/FilingHistoryList/filings/DefaultFiling.vue` | 334: business-filings-ui (100%), 31 | 10 |
| `business-filings-ui/src/components/Dashboard/FilingHistoryList/filings/index.ts` | 334: business-filings-ui (100%), 31 | 10 |
| `business-filings-ui/src/components/Dashboard/TodoList.vue` | 162: business-filings-ui (100%), 12 | 10 |
| `business-filings-ui/src/components/EntityInfo/EntityMenu.vue` | 271: business-filings-ui (100%), 11 | 10 |
| `business-filings-ui/src/enums/allowableActions.ts` | 209: business-filings-ui (100%), 22 | 10 |
| `business-filings-ui/src/enums/routes.ts` | 232: business-filings-ui (100%), 37 | 10 |
| `business-filings-ui/src/mixins/allowable-actions-mixin.ts` | 292: business-filings-ui (100%), 33 | 10 |
| `business-filings-ui/src/mixins/common-mixin.ts` | 195: business-filings-ui (100%), 45 | 10 |
| `business-filings-ui/src/mixins/filing-mixin.ts` | 292: business-filings-ui (100%), 33 | 10 |
| `business-filings-ui/src/routes.ts` | 232: business-filings-ui (100%), 37 | 10 |
| `business-filings-ui/src/services/enum-utilities.ts` | 140: business-filings-ui (100%), 15<br>292: business-filings-ui (100%), 33 | 10 |
| `business-filings-ui/src/services/legal-services.ts` | 232: business-filings-ui (100%), 37<br>195: business-filings-ui (100%), 45 | 10 |
| `business-filings-ui/src/stores/filingHistoryListStore.ts` | 232: business-filings-ui (100%), 37 | 10 |
| `business-filings-ui/src/views/AgmExtension.vue` | 195: business-filings-ui (100%), 45 | 10 |
| `lear/legal-api/src/legal_api/resources/v2/business/business_tasks.py` | 291: lear/legal-api (100%), 21 | 13 |

## cross-0 (flow)

When a business user files a fee-bearing filing (say an annual report) from the business dashboard, what happens end to end, from submission through fee calculation, online payment and confirmation, until the filing is actually applied to the business record?

23 of 23 answer files indexed, 25 leaves, 7 groups.

| file | leaf: main component (share), size | group |
|---|---|---|
| `business-filings-ui/src/views/AnnualReport.vue` | 195: business-filings-ui (100%), 45 | 10 |
| `lear/jobs/future-effective-filings/file_future_effective.py` | 346: lear/jobs/future-effective-filings (20%), 15 | 27 |
| `lear/legal-api/src/legal_api/config.py` | 108: lear/legal-api (94%), 31<br>318: lear/legal-api (100%), 27 | 14, 13 |
| `lear/legal-api/src/legal_api/models/filing.py` | 289: lear/legal-api (100%), 71<br>290: lear/legal-api (100%), 35 | 13 |
| `lear/legal-api/src/legal_api/resources/v2/business/business_filings/business_filings.py` | 284: lear/legal-api (95%), 20<br>291: lear/legal-api (100%), 21<br>289: lear/legal-api (100%), 71<br>290: lear/legal-api (100%), 35 | 13 |
| `lear/queue_services/business-pay/src/business_pay/resources/pay_filer.py` | 378: lear/queue_services/business-pay (100%), 22 | 25 |
| `lear/queue_services/business-pay/src/business_pay/services/__init__.py` | 378: lear/queue_services/business-pay (100%), 22 | 25 |
| `lear/queue_services/entity-filer/src/entity_filer/config.py` | 360: lear/queue_services/entity-emailer (47%), 30 | 27 |
| `lear/queue_services/entity-filer/src/entity_filer/worker.py` | 360: lear/queue_services/entity-emailer (47%), 30<br>354: lear/queue_services/entity-filer (100%), 6<br>276: lear/queue_services/entity-filer (100%), 29<br>275: lear/queue_services/entity-filer (100%), 11 | 27, 25 |
| `lear/queue_services/entity-pay/src/entity_pay/worker.py` | 379: lear/queue_services/common (43%), 30 | 27 |
| `sbc-auth/auth-web/src/routes/router.ts` | 235: sbc-auth/auth-web (100%), 14 | 7 |
| `sbc-auth/auth-web/src/services/payment.services.ts` | 280: sbc-auth/auth-web (100%), 19<br>270: sbc-auth/auth-web (100%), 56 | 7 |
| `sbc-auth/auth-web/src/views/pay/PaymentReturnView.vue` | 256: sbc-auth/auth-web (100%), 11 | 7 |
| `sbc-pay/pay-api/src/pay_api/resources/v1/invoice.py` | 112: sbc-pay/pay-api (100%), 24 | 17 |
| `sbc-pay/pay-api/src/pay_api/services/auth.py` | 112: sbc-pay/pay-api (100%), 24 | 17 |
| `sbc-pay/pay-api/src/pay_api/services/base_payment_system.py` | 277: sbc-pay/pay-api (100%), 26<br>13: sbc-pay/pay-api (82%), 22<br>278: sbc-pay/pay-api (98%), 44 | 17 |
| `sbc-pay/pay-api/src/pay_api/services/bcol_service.py` | 278: sbc-pay/pay-api (98%), 44 | 17 |
| `sbc-pay/pay-api/src/pay_api/services/gcp_queue_publisher.py` | 278: sbc-pay/pay-api (98%), 44 | 17 |
| `sbc-pay/pay-api/src/pay_api/services/invoice.py` | 277: sbc-pay/pay-api (100%), 26<br>13: sbc-pay/pay-api (82%), 22<br>264: sbc-pay/pay-api (100%), 23 | 17 |
| `sbc-pay/pay-api/src/pay_api/services/pad_service.py` | 278: sbc-pay/pay-api (98%), 44 | 17 |
| `sbc-pay/pay-api/src/pay_api/services/payment_service.py` | 277: sbc-pay/pay-api (100%), 26<br>13: sbc-pay/pay-api (82%), 22<br>278: sbc-pay/pay-api (98%), 44 | 17 |
| `sbc-pay/pay-api/src/pay_api/services/payment_transaction.py` | 277: sbc-pay/pay-api (100%), 26<br>13: sbc-pay/pay-api (82%), 22<br>264: sbc-pay/pay-api (100%), 23<br>278: sbc-pay/pay-api (98%), 44 | 17 |
| `sbc-pay/pay-api/src/pay_api/utils/util.py` | 111: sbc-pay/pay-api (100%), 13<br>178: sbc-pay/pay-api (100%), 31 | 17 |

## cross-1 (flow)

How does a brand-new business (incorporation, registration, amalgamation or continuation) become linked to the user's account in the account/auth system, starting from the temporary draft and ending once the real business number exists?

10 of 10 answer files indexed, 13 leaves, 5 groups.

| file | leaf: main component (share), size | group |
|---|---|---|
| `lear/legal-api/src/legal_api/core/filing.py` | 284: lear/legal-api (95%), 20<br>290: lear/legal-api (100%), 35 | 13 |
| `lear/legal-api/src/legal_api/models/filing.py` | 289: lear/legal-api (100%), 71<br>290: lear/legal-api (100%), 35 | 13 |
| `lear/legal-api/src/legal_api/resources/v2/business/business.py` | 291: lear/legal-api (100%), 21<br>290: lear/legal-api (100%), 35 | 13 |
| `lear/legal-api/src/legal_api/resources/v2/business/business_filings/business_filings.py` | 284: lear/legal-api (95%), 20<br>291: lear/legal-api (100%), 21<br>289: lear/legal-api (100%), 71<br>290: lear/legal-api (100%), 35 | 13 |
| `lear/legal-api/src/legal_api/services/bootstrap.py` | 218: lear/legal-api (100%), 13 | 13 |
| `lear/queue_services/entity-filer/src/entity_filer/filing_processors/filing_components/business_profile.py` | 276: lear/queue_services/entity-filer (100%), 29 | 25 |
| `lear/queue_services/entity-filer/src/entity_filer/worker.py` | 360: lear/queue_services/entity-emailer (47%), 30<br>354: lear/queue_services/entity-filer (100%), 6<br>276: lear/queue_services/entity-filer (100%), 29<br>275: lear/queue_services/entity-filer (100%), 11 | 27, 25 |
| `sbc-auth/auth-api/src/auth_api/resources/v1/org.py` | 294: sbc-auth/auth-api (100%), 50 | 21 |
| `sbc-auth/auth-api/src/auth_api/services/affiliation.py` | 352: sbc-auth/auth-api (100%), 40<br>184: sbc-auth/auth-api (100%), 18 | 21 |
| `sbc-auth/queue_services/auth-queue/src/auth_queue/resources/worker.py` | 306: sbc-auth/queue_services/account-mailer (58%), 19 | 18 |

## cross-2 (concept)

How are a user's permissions on a specific business (who can view it, edit/file for it, or pay for it) modeled, and how do the legal, payment and UI layers each enforce them?

16 of 16 answer files indexed, 16 leaves, 5 groups.

| file | leaf: main component (share), size | group |
|---|---|---|
| `business-filings-ui/src/App.vue` | 232: business-filings-ui (100%), 37<br>292: business-filings-ui (100%), 33<br>195: business-filings-ui (100%), 45 | 10 |
| `business-filings-ui/src/services/auth-services.ts` | 232: business-filings-ui (100%), 37 | 10 |
| `business-filings-ui/src/stores/rootStore.ts` | 232: business-filings-ui (100%), 37<br>292: business-filings-ui (100%), 33 | 10 |
| `lear/legal-api/src/legal_api/resources/v2/business/business_directors.py` | 318: lear/legal-api (100%), 27 | 13 |
| `lear/legal-api/src/legal_api/resources/v2/business/business_filings/business_filings.py` | 284: lear/legal-api (95%), 20<br>291: lear/legal-api (100%), 21<br>289: lear/legal-api (100%), 71<br>290: lear/legal-api (100%), 35 | 13 |
| `lear/legal-api/src/legal_api/resources/v2/business/business_parties.py` | 318: lear/legal-api (100%), 27 | 13 |
| `lear/legal-api/src/legal_api/services/authz.py` | 218: lear/legal-api (100%), 13<br>281: lear/legal-api (100%), 40<br>290: lear/legal-api (100%), 35 | 13 |
| `sbc-auth/auth-api/migrations/versions/1c958b749a20_org_status_added_to_authorisation_view.py` | 331: sbc-auth/auth-api (100%), 11 | 5 |
| `sbc-auth/auth-api/src/auth_api/models/permissions.py` | 337: sbc-auth/auth-api (100%), 20 | 21 |
| `sbc-auth/auth-api/src/auth_api/models/views/authorization.py` | 336: sbc-auth/auth-api (100%), 31 | 21 |
| `sbc-auth/auth-api/src/auth_api/resources/v1/entity.py` | 294: sbc-auth/auth-api (100%), 50 | 21 |
| `sbc-auth/auth-api/src/auth_api/services/authorization.py` | 294: sbc-auth/auth-api (100%), 50 | 21 |
| `sbc-auth/auth-api/src/auth_api/services/permissions.py` | 294: sbc-auth/auth-api (100%), 50 | 21 |
| `sbc-pay/pay-api/src/pay_api/resources/v1/invoice.py` | 112: sbc-pay/pay-api (100%), 24 | 17 |
| `sbc-pay/pay-api/src/pay_api/services/auth.py` | 112: sbc-pay/pay-api (100%), 24 | 17 |
| `sbc-pay/pay-api/src/pay_api/utils/constants.py` | 278: sbc-pay/pay-api (98%), 44 | 17 |

## cross-3 (concept)

How do customer email notifications about filings work across the services: what triggers them, where do recipients and receipts come from, and what actually sends the email?

16 of 16 answer files indexed, 9 leaves, 3 groups.

| file | leaf: main component (share), size | group |
|---|---|---|
| `lear/legal-api/src/legal_api/resources/v2/admin/reviews.py` | 289: lear/legal-api (100%), 71 | 13 |
| `lear/legal-api/src/legal_api/services/bootstrap.py` | 218: lear/legal-api (100%), 13 | 13 |
| `lear/queue_services/business-pay/src/business_pay/config.py` | 378: lear/queue_services/business-pay (100%), 22 | 25 |
| `lear/queue_services/business-pay/src/business_pay/resources/pay_filer.py` | 378: lear/queue_services/business-pay (100%), 22 | 25 |
| `lear/queue_services/business-pay/src/business_pay/services/__init__.py` | 378: lear/queue_services/business-pay (100%), 22 | 25 |
| `lear/queue_services/common/src/entity_queue_common/messages.py` | 379: lear/queue_services/common (43%), 30 | 27 |
| `lear/queue_services/entity-emailer/src/entity_emailer/config.py` | 360: lear/queue_services/entity-emailer (47%), 30 | 27 |
| `lear/queue_services/entity-emailer/src/entity_emailer/email_processors/__init__.py` | 24: lear/queue_services/entity-emailer (100%), 27 | 25 |
| `lear/queue_services/entity-emailer/src/entity_emailer/email_processors/dissolution_notification.py` | 24: lear/queue_services/entity-emailer (100%), 27 | 25 |
| `lear/queue_services/entity-emailer/src/entity_emailer/email_processors/registration_notification.py` | 24: lear/queue_services/entity-emailer (100%), 27 | 25 |
| `lear/queue_services/entity-emailer/src/entity_emailer/email_processors/restoration_notification.py` | 24: lear/queue_services/entity-emailer (100%), 27 | 25 |
| `lear/queue_services/entity-emailer/src/entity_emailer/worker.py` | 360: lear/queue_services/entity-emailer (47%), 30<br>24: lear/queue_services/entity-emailer (100%), 27 | 27, 25 |
| `lear/queue_services/entity-filer/src/entity_filer/config.py` | 360: lear/queue_services/entity-emailer (47%), 30 | 27 |
| `lear/queue_services/entity-filer/src/entity_filer/filing_processors/filing_components/business_profile.py` | 276: lear/queue_services/entity-filer (100%), 29 | 25 |
| `lear/queue_services/entity-filer/src/entity_filer/worker.py` | 360: lear/queue_services/entity-emailer (47%), 30<br>354: lear/queue_services/entity-filer (100%), 6<br>276: lear/queue_services/entity-filer (100%), 29<br>275: lear/queue_services/entity-filer (100%), 11 | 27, 25 |
| `lear/queue_services/entity-pay/src/entity_pay/worker.py` | 379: lear/queue_services/common (43%), 30 | 27 |

## cross-4 (change)

We want amalgamation applications, like continuations today, to go to registry staff for review after they are paid, instead of being applied right away. Where is this decided, and what else in the pipeline would the change touch?

8 of 8 answer files indexed, 8 leaves, 3 groups.

| file | leaf: main component (share), size | group |
|---|---|---|
| `lear/legal-api/src/legal_api/models/filing.py` | 289: lear/legal-api (100%), 71<br>290: lear/legal-api (100%), 35 | 13 |
| `lear/legal-api/src/legal_api/resources/v2/admin/reviews.py` | 289: lear/legal-api (100%), 71 | 13 |
| `lear/legal-api/src/legal_api/resources/v2/business/business.py` | 291: lear/legal-api (100%), 21<br>290: lear/legal-api (100%), 35 | 13 |
| `lear/legal-api/src/legal_api/resources/v2/business/business_filings/business_filings.py` | 284: lear/legal-api (95%), 20<br>291: lear/legal-api (100%), 21<br>289: lear/legal-api (100%), 71<br>290: lear/legal-api (100%), 35 | 13 |
| `lear/queue_services/business-pay/src/business_pay/database/review.py` | 378: lear/queue_services/business-pay (100%), 22 | 25 |
| `lear/queue_services/business-pay/src/business_pay/resources/pay_filer.py` | 378: lear/queue_services/business-pay (100%), 22 | 25 |
| `lear/queue_services/entity-emailer/src/entity_emailer/worker.py` | 360: lear/queue_services/entity-emailer (47%), 30<br>24: lear/queue_services/entity-emailer (100%), 27 | 27, 25 |
| `lear/queue_services/entity-pay/src/entity_pay/worker.py` | 379: lear/queue_services/common (43%), 30 | 27 |

## cross-5 (change)

Product wants the list of businesses on a user's account page (in the account/auth app) to show an extra piece of business information that only the legal registry knows. Where does that list's data come from, and what would need to change on each side?

9 of 9 answer files indexed, 12 leaves, 4 groups.

| file | leaf: main component (share), size | group |
|---|---|---|
| `lear/legal-api/src/legal_api/models/business.py` | 289: lear/legal-api (100%), 71 | 13 |
| `lear/legal-api/src/legal_api/resources/v2/business/business.py` | 291: lear/legal-api (100%), 21<br>290: lear/legal-api (100%), 35 | 13 |
| `lear/queue_services/entity-filer/src/entity_filer/filing_processors/filing_components/business_profile.py` | 276: lear/queue_services/entity-filer (100%), 29 | 25 |
| `lear/queue_services/entity-filer/src/entity_filer/worker.py` | 360: lear/queue_services/entity-emailer (47%), 30<br>354: lear/queue_services/entity-filer (100%), 6<br>276: lear/queue_services/entity-filer (100%), 29<br>275: lear/queue_services/entity-filer (100%), 11 | 27, 25 |
| `sbc-auth/auth-api/src/auth_api/config.py` | 352: sbc-auth/auth-api (100%), 40<br>294: sbc-auth/auth-api (100%), 50 | 21 |
| `sbc-auth/auth-api/src/auth_api/resources/v1/org.py` | 294: sbc-auth/auth-api (100%), 50 | 21 |
| `sbc-auth/auth-api/src/auth_api/schemas/schemas/entity.json` | 327: sbc-auth/auth-api (100%), 98<br>328: sbc-auth/auth-api (100%), 11 | 21 |
| `sbc-auth/auth-api/src/auth_api/services/affiliation.py` | 352: sbc-auth/auth-api (100%), 40<br>184: sbc-auth/auth-api (100%), 18 | 21 |
| `sbc-auth/auth-api/src/auth_api/services/entity.py` | 352: sbc-auth/auth-api (100%), 40 | 21 |
