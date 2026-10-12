37 facts cite this leaf's files.

| prompt | words | facts conveyed | runs' range | detail share | contradicted | cited files named |
|---|---|---|---|---|---|---|
| `today` | 1052 | 0.37 | 0.36-0.38 | 0.25 | 0 | 5/5 |
| `purpose-budget` | 711 | 0.3 | 0.28-0.31 |  | 0 | 3/5 |
| `decisions` | 1919 | 0.53 | 0.5-0.57 | 0.27 | 0 | 5/5 |
| `decisions-ctx` | 1707 | 0.55 | 0.5-0.61 |  | 0 | 2/5 |
| `decisions-tight` | 993 | 0.46 | 0.43-0.5 |  | 0 | 2/5 |
| `core` | 445 | 0.32 | 0.32-0.32 | 0.02 | 0 | 3/5 |
| `core-scaled` | 656 | 0.26 | 0.24-0.28 |  | 0 | 4/5 |
| `core#2` | 394 | 0.32 | 0.3-0.35 |  | 0 | 4/5 |
| `core-states` | 692 | 0.46 | 0.46-0.46 | 0.26 | 0 | 4/5 |
| `core-states#2` | 750 | 0.45 | 0.43-0.46 | 0.38 | 0 | 4/5 |
| `(input)` | 3263 | 0.61 | 0.47-0.76 |  | 0 | 5/5 |

Per fact (score per prompt):

| # | fact | today | purpose-budget | decisions | decisions-ctx | decisions-tight | core | core-scaled | core#2 | core-states | core-states#2 | (input) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | Creating a new-business filing goes to post_businesses (POST /businesses) in the v2 business resource. It call… | 1 | 1 | 2 | 2 | 1 | 1 | 1 | 1 | 2 | 2 | 2 |
| 2 | For an identifier starting with 'T', saving_filings validates against the RegistrationBootstrap instead of a B… | 1 | 1 | 1 | 1 | 2 | 2 | 1 | 1 | 2 | 2 | 1 |
| 3 | complete_filing calls check_and_update_nr, which may extend the name request through namex for future-effectiv… | 1 | 1 | 1 | 1 | 2 | 1 | 1 | 1 | 1 | 1 | 1 |
| 4 | For non-COOP change-of-address filings, legal-api's set_effective_date (called from complete_filing) forces th… | 0 | 0 | 1 | 2 | 2 | 0 | 0 | 0 | 1 | 1 | 2 |
| 5 | The filings endpoint's DELETE handler returns create_deletion_locked_response for locked filings. The PATCH ha… | 1 | 2 | 2 | 2 | 2 | 2 | 2 | 1 | 2 | 2 | 2 |
| 6 | A CHANGE_REQUESTED filing stays editable (the filing_json setter allows in_change_requested_status). When it i… | 1 | 0 | 2 | 2 | 0 | 1 | 0 | 0 | 2 | 2 | 2 |
| 7 | Readers depend on these statuses. The ledger lists only COMPLETED and PAID filings. Core Filing.get_document_l… | 1 | 0 | 1 | 1 | 1 | 0 | 0 | 1 | 0 | 0 | 2 |
| 8 | On submission, ListFilingResource.check_authorization runs both authorized(identifier, jwt, ['edit']) and is_a… | 1 | 1 | 2 | 1 | 0 | 0 | 0 | 1 | 0 | 1 | 1 |
| 9 | The same rules feed the UI. The GET business handler calls get_allowable_actions, which uses get_allowed_filin… | 1 | 0 | 0 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 2 |
| 10 | Register the type in the Filing.FILINGS dictionary in models/filing.py, which maps the filing name to fee code… | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 1 |
| 11 | Add an entry under the right role and state in get_allowable_filings_dict (services/authz.py) with legalTypes … | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 |
| 12 | create_staff_review reads nameRequest.nrNumber, foreignJurisdiction.identifier and the 'Completing Party' from… | 0 | 0 | 2 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 2 |
| 13 | If changes are requested, the submitter resubmits through saving_filings. In that case resubmit_filing_for_rev… | 1 | 0 | 2 | 1 | 0 | 1 | 0 | 0 | 1 | 1 | 1 |
| 14 | Documents and email are also affected. While a filing is PAID, AWAITING_REVIEW, CHANGE_REQUESTED, APPROVED or … | 1 | 0 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 1 | 1 |
| 15 | In the legal-api, ListFilingResource.complete_filing creates a pay-api invoice through create_invoice and stor… | 1 | 2 | 2 | 2 | 2 | 1 | 1 | 1 | 2 | 2 | 2 |
| 16 | Filing.get_completed_filings_for_colin returns only COMPLETED filings with no colin_event_ids. It excludes SP/… | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 2 |
| 17 | The PATCH handler update_colin_id appends ColinEventId rows to the filing. Once a filing has colin event ids, … | 1 | 1 | 2 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 2 |
| 18 | In the other direction, the update-legal-filings job reads the last processed COLIN event id from GET /interna… | 1 | 1 | 0 | 1 | 1 | 1 | 0 | 1 | 1 | 1 | 2 |
| 19 | For each event whose id is not yet in LEAR, the job fetches the filing from the colin-api and POSTs it to /bus… | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 1 | 2 |
| 20 | In the legal-api, filings with source COLIN have their header colinIds saved as ColinEventId rows (_save_colin… | 1 | 2 | 2 | 2 | 2 | 2 | 2 | 2 | 2 | 2 | 2 |
| 21 | The entity-filer dissolution processor sets the business HISTORICAL. When the flag is on, it moves QUEUED Batc… | 1 | 0 | 2 | 1 | 1 | 0 | 0 | 0 | 2 | 1 | 2 |
| 22 | For corporations synced with COLIN, the update-legal-filings job's update_business_nos gets businesses without… | 1 | 1 | 1 | 1 | 2 | 1 | 1 | 1 | 2 | 2 | 2 |
| 23 | Business.get_all_by_no_tax_id excludes COOP, SP and GP legal types. Coops do not get a business number, and SP… | 0 | 0 | 2 | 0 | 2 | 0 | 0 | 0 | 2 | 0 | 2 |
| 24 | The Legal API's tasks endpoint (construct_task_list) returns DRAFT, PENDING, PENDING_CORRECTION and ERROR fili… | 2 | 2 | 2 | 2 | 2 | 2 | 2 | 2 | 2 | 2 | 1 |
| 25 | AnnualReport.vue's fetchDraftFiling loads the draft with LegalServices.fetchFiling and rejects it unless it is… | 1 | 1 | 0 | 0 | 1 | 1 | 0 | 1 | 0 | 0 | 1 |
| 26 | From the to-do list, users can delete a draft (DELETE businesses/{id}/filings/{filingId}) or cancel a pending … | 1 | 2 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 2 |
| 27 | The rules are computed on the server. legal-api's get_allowable_actions in authz.py builds {filing: {filingSub… | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 2 |
| 28 | Since legal-api returns every DRAFT, PENDING or ERROR filing as a task, TodoList.loadFilingItem needs a new ca… | 0 | 0 | 1 | 0 | 1 | 1 | 1 | 1 | 0 | 0 | 2 |
| 29 | The UI view saves the filing to legal-api. In the v2 saving_filings endpoint, ListFilingResource.complete_fili… | 0 | 1 | 1 | 1 | 1 | 1 | 0 | 1 | 1 | 0 | 1 |
| 30 | ListFilingResource.create_invoice POSTs businessInfo, filingInfo.filingTypes and optional accountInfo (routing… | 1 | 2 | 2 | 2 | 2 | 1 | 2 | 2 | 1 | 1 | 2 |
| 31 | The legal-api v2 businesses POST (post_businesses) accepts only CoreFiling.NEW_BUSINESS_FILING_TYPES. It calls… | 1 | 0 | 1 | 1 | 1 | 1 | 0 | 1 | 1 | 1 | 1 |
| 32 | Deleting a draft temporary-registration filing in legal-api calls RegistrationBootstrapService.deregister_boot… | 2 | 0 | 2 | 2 | 2 | 0 | 0 | 0 | 1 | 1 | 2 |
| 33 | legal-api endpoints request specific actions: filing save, delete and payment-cancel use action=['edit'] (save… | 0 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 1 | 1 |
| 34 | When a submitter resubmits after CHANGE_REQUESTED, saving_filings calls resubmit_filing_for_review instead of … | 1 | 0 | 2 | 2 | 0 | 1 | 0 | 0 | 2 | 1 | 1 |
| 35 | The business list in auth reads draftStatus and draftType from legal-api's businesses search. Paid amalgamatio… | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 36 | On the legal side, search_businesses (SYSTEM role only) returns {'businessEntities': [business.json(slim=True)… | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 37 | The slim business JSON is also what auth sees for SP and GP firms, where search_businesses adds alternateNames… | 1 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 1 |
