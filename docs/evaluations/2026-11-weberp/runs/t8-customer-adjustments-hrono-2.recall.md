hrono recall from tree "weberp": the passages of the map that best match this prompt, best first. Each is a few lines of a brief or a source file; open the brief named with it for the whole part.

### Passage 1, from the brief /Users/orest/hrono-weberp/exports/4cb937f79e8b57063bd47132413abdac8abbcbdc-threads/weberp-installer-seed-data-schema-build-ci-and-project-histo-150/weberp-install-seed-data-menu-items-module-list-and-transact-10/brief.md

- Journal - GL 0, Payment - GL 1, Receipt - GL 2, Standing Journal 3, Journal Template Number 4.
  - Sales Invoice 10, Credit Note 11, Receipt 12, Journal - Debtors 15, Location Transfer 16, Stock Adjustment 17, Purchase Order 18, Picking List 19.
  - Purchase Invoice 20, Debit Note 21, Creditors Payment 22, Creditors Journal 23, Purchase Order Delivery 25.
  - Work Order Receipt 26, Work Order Issue 28, Work Order Variance 29, Sales Order 30, Shipment Close 31, Contract Close 32.
  - Cost Update 35, Exchange Difference 36, Tenders 37, Stock Requests 38, Sales Commision Accruals 39 (spelled so in the data).
  - Work Order 40, Asset Addition 41, Asset Category Change 42, Delete w/down asset 43, Depreciation 44.
  

### Passage 2, from the brief /Users/orest/hrono-weberp/exports/4cb937f79e8b57063bd47132413abdac8abbcbdc-threads/weberp-installer-seed-data-schema-build-ci-and-project-histo-150/weberp-shared-includes-formatting-locale-pdf-commission-emai-58/brief.md

| Type | Name |
    |---|---|
    | 0 | Journal - GL |
    | 1 | Payment - GL |
    | 2 | Receipt - GL |
    | 3 | Standing Journal |
    | 10 | Sales Invoice |
    | 11 | Credit Note |
    | 12 | Receipt |
    | 15 | Journal - Debtors |
    | 16 | Location Transfer |
    | 17 | Stock Adjustment |
    | 18 | Purchase Order |
    | 19 | Picking List |
    | 20 | Purchase Invoice |
    | 21 | Debit Note |
    | 22 | Creditors Payment |
    | 23 | Creditors Journal |
    | 25 | Purchase Order Delivery |
    | 26 | Work Order Receipt |
    | 28 | Work Order Issue |
    | 29 | Work Order Variance |
    | 30 | Sales Order |
    | 31 | Shipment Close |
    | 32 | Contract Close |
    | 35 | Cost Update |
    | 36 | Exchange Difference |
    | 37 | Tenders |
    | 38 | Stock Requests |
    

### Passage 3, from the brief /Users/orest/hrono-weberp/exports/4cb937f79e8b57063bd47132413abdac8abbcbdc-threads/weberp-installer-seed-data-schema-build-ci-and-project-histo-150/weberp-threads-pull-requests-merged-feature-bundles-installe-205/brief.md

- Option 2 was chosen: remove the automatic calls to `AdjustBankAccountsDueToCurrencyExchangeRate()` from `LoginFunctions()` (lines 216-218 and 236-238).
- The alternative, a frequency setting (Manually/Daily/Monthly/Yearly) in `SystemParameters.php`, was not taken.
- Other code changes in the pull stay.
- Before this change, with automatic daily rate updates on, foreign-currency bank accounts were not updated and needed manual "Calculate and Post Exchange Difference" from `BankReconciliation.php`.
- With the logic from `Currencies.php`, the bank accounts are updated.
- Reasoning given: bank accounts are revalued monthly or yearly, not daily, because daily revaluation floods `gltrans`. SSAP 20 says the user controls when adjustments happen, normally at month end or year end.


### Passage 4, from the file BankReconciliation.php (webERP), described in the brief /Users/orest/hrono-weberp/exports/4cb937f79e8b57063bd47132413abdac8abbcbdc-threads/weberp-finance-and-ledger-area-152/weberp-bank-matching-bank-reconciliation-daily-bank-transact-123/brief.md

__('This will create a general ledger journal to write off the exchange difference in the current balance of the account. It is important that the exchange rate above reflects the current value of the bank account currency') . ' - ' . __('Are You Sure?') . '\');" /></td>
			</tr>';
	}

	

### Passage 5, from the brief /Users/orest/hrono-weberp/exports/4cb937f79e8b57063bd47132413abdac8abbcbdc-threads/weberp-finance-and-ledger-area-152/weberp-api-debtor-transactions-gl-accounts-groups-sections-s-62/brief.md

- **API credit note vs. `Credit_Invoice.php`:** The interactive credit note starts from one existing invoice (header must match exactly 1 row), checks quantities ≥0, price ≥0 and discount 0–100%, and checks `qtyinvoiced >= credit qty` for `WriteOff`, `Return` and `ReverseOverCharge`. It requires a write-off GL code for `WriteOff`. The API credit note starts from caller-supplied lines. It has no tie to an invoice, no quantity-credited limit, no check for negative values, and no serial handling. It allocates against any open invoices of the debtor.
