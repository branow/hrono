14 facts cite this leaf's files.

| prompt | words | facts conveyed | runs' range | detail share | contradicted | cited files named |
|---|---|---|---|---|---|---|
| `today` | 853 | 0.39 | 0.39-0.39 | 0.34 | 0 | 4/4 |
| `purpose-budget` | 575 | 0.52 | 0.46-0.57 |  | 0 | 4/4 |
| `decisions` | 1228 | 0.54 | 0.54-0.54 | 0.59 | 0 | 4/4 |
| `decisions-ctx` | 1334 | 0.54 | 0.54-0.54 |  | 0 | 4/4 |
| `decisions-tight` | 1050 | 0.5 | 0.5-0.5 |  | 0 | 4/4 |
| `core` | 419 | 0.5 | 0.5-0.5 | 0.0 | 0 | 3/4 |
| `core-scaled` | 644 | 0.52 | 0.5-0.54 |  | 0 | 4/4 |
| `core#2` | 400 | 0.64 | 0.57-0.71 |  | 0 | 3/4 |
| `core-states` | 661 | 0.48 | 0.43-0.54 | 0.36 | 0 | 4/4 |
| `core-states#2` | 736 | 0.57 | 0.57-0.57 | 0.28 | 0 | 4/4 |
| `(input)` | 1677 | 0.6 | 0.57-0.64 |  | 0 | 4/4 |

Per fact (score per prompt):

| # | fact | today | purpose-budget | decisions | decisions-ctx | decisions-tight | core | core-scaled | core#2 | core-states | core-states#2 | (input) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | The Business row is only created in the entity-filer's incorporation_filing.process. It raises if a business a… | 2 | 2 | 2 | 2 | 2 | 2 | 2 | 2 | 2 | 2 | 2 |
| 2 | After the commit, for new-business filing types the filer worker sets filing.business_id. It then calls busine… | 1 | 2 | 2 | 2 | 2 | 2 | 2 | 2 | 2 | 2 | 2 |
| 3 | entity-filer's process_filing loads the filing through core Filing.find_by_id and skips it if already COMPLETE… | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 2 | 1 | 1 | 2 |
| 4 | The filer marks completion by setting filing_submission.transaction_id and calling set_processed, which sets c… | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 2 | 0 | 1 | 1 |
| 5 | In entity-filer, add a filing_processors/<type>.py with a process() function and an elif branch in worker.proc… | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 2 | 1 | 1 | 2 |
| 6 | The entity-filer worker's process_filing skips filings that are already COMPLETED. Otherwise it sends each leg… | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 2 | 1 | 1 | 2 |
| 7 | The entity-filer dissolution processor sets the business HISTORICAL. When the flag is on, it moves QUEUED Batc… | 1 | 1 | 1 | 2 | 1 | 1 | 1 | 1 | 1 | 1 | 1 |
| 8 | The entity-filer and entity-pay workers handle duplicates using the filing itself, without a tracker table. pr… | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 9 | The entity-bn worker listens to entity events published by the entity-filer (for example 'bc.registry.business… | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 10 | Change-of-directors emails are generic filing emails. The entity-filer publishes {'email': {filingId, type, op… | 0 | 1 | 1 | 1 | 1 | 0 | 0 | 1 | 1 | 1 | 1 |
| 11 | entity-filer's process_filing applies the filing, marks it processed and then publishes a business event on NA… | 1 | 1 | 1 | 1 | 1 | 0 | 1 | 1 | 0 | 1 | 1 |
| 12 | Once the filing is processed, entity-filer's worker calls business_profile.update_affiliation for new-business… | 1 | 2 | 1 | 1 | 1 | 2 | 2 | 2 | 1 | 2 | 0 |
| 13 | These messages are produced at several lifecycle points: business-pay or entity-pay on payment (PAID), entity-… | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 |
| 14 | Basic data that auth itself stores (name, corp type, state) is pushed from lear to auth separately. After fili… | 0 | 2 | 2 | 1 | 1 | 2 | 1 | 2 | 1 | 2 | 1 |
