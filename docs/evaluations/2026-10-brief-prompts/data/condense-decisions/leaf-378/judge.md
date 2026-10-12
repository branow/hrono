12 facts cite this leaf's files.

| prompt | words | facts conveyed | runs' range | detail share | contradicted | cited files named |
|---|---|---|---|---|---|---|
| `today` | 777 | 0.69 | 0.67-0.71 | 0.51 | 0 | 5/5 |
| `purpose-budget` | 523 | 0.75 | 0.71-0.79 |  | 0 | 5/5 |
| `decisions` | 793 | 0.85 | 0.83-0.88 | 0.52 | 0 | 5/5 |
| `decisions-ctx` | 840 | 0.79 | 0.79-0.79 |  | 0 | 5/5 |
| `decisions-tight` | 771 | 0.79 | 0.75-0.83 |  | 0 | 5/5 |
| `core` | 359 | 0.75 | 0.75-0.75 | 0.17 | 0 | 5/5 |
| `core-scaled` | 383 | 0.58 | 0.58-0.58 |  | 0 | 5/5 |
| `core#2` | 323 | 0.58 | 0.58-0.58 |  | 0 | 4/5 |
| `core-states` | 486 | 0.81 | 0.79-0.83 | 0.28 | 0 | 5/5 |
| `core-states#2` | 465 | 0.81 | 0.79-0.83 | 0.28 | 0 | 5/5 |
| `(input)` | 1716 | 0.67 | 0.54-0.79 |  | 0 | 5/5 |

Per fact (score per prompt):

| # | fact | today | purpose-budget | decisions | decisions-ctx | decisions-tight | core | core-scaled | core#2 | core-states | core-states#2 | (input) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | Payment completion arrives in a queue listener: either the NATS-based entity-pay worker (process_payment) or t… | 2 | 2 | 2 | 2 | 1 | 2 | 1 | 1 | 2 | 2 | 2 |
| 2 | The pay listeners only publish {'filing': {'id': ...}} to the filer subject when the effective date is not in … | 2 | 2 | 2 | 2 | 2 | 2 | 2 | 2 | 2 | 2 | 2 |
| 3 | Staff review states are entered from business-pay's create_staff_review, which creates a Review and sets AWAIT… | 1 | 2 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 |
| 4 | Only business-pay decides that a filing needs review: pay_filer.worker has a hard-coded staff_review_required … | 2 | 2 | 2 | 2 | 2 | 2 | 1 | 1 | 2 | 2 | 1 |
| 5 | create_staff_review reads nameRequest.nrNumber, foreignJurisdiction.identifier and the 'Completing Party' from… | 0 | 0 | 1 | 1 | 1 | 0 | 0 | 0 | 1 | 1 | 1 |
| 6 | The newer GCP-based business-pay worker does the same. It marks the filing PAID and sends it to the filer only… | 2 | 2 | 2 | 2 | 2 | 2 | 2 | 2 | 2 | 2 | 2 |
| 7 | The entity-filer and entity-pay workers handle duplicates using the filing itself, without a tracker table. pr… | 1 | 1 | 2 | 1 | 1 | 2 | 1 | 1 | 2 | 1 | 2 |
| 8 | The lear business-pay worker accepts 'bc.registry.payment' cloud events with status COMPLETED and looks up the… | 2 | 2 | 2 | 2 | 2 | 2 | 2 | 2 | 2 | 2 | 2 |
| 9 | Filing email requests share one message shape, {'email': {'filingId', 'type', 'option'}}, built by entity_queu… | 1 | 2 | 2 | 2 | 2 | 2 | 2 | 2 | 2 | 2 | 2 |
| 10 | These messages are produced at several lifecycle points: business-pay or entity-pay on payment (PAID), entity-… | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 |
| 11 | The post-payment branching is hardcoded in business-pay's worker: staff_review_required = ['continuationIn'] s… | 2 | 1 | 2 | 2 | 2 | 2 | 1 | 1 | 2 | 2 | 2 |
| 12 | create_staff_review reads nameRequest.nrNumber, foreignJurisdiction.identifier and the 'Completing Party' from… | 0 | 0 | 1 | 1 | 1 | 0 | 0 | 0 | 1 | 1 | 1 |
