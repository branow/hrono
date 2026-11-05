# T2 checklist (from the merged change 2d8fa77..882b00c, PR #848)

1. A new company field for the unrealized currency exchange account
   (reference: `companies.currencyexchangediffact`), added by a database
   upgrade script in webERP's way (`sql/updates/NN.php` using its helpers,
   e.g. `AddColumn`), with the fresh-install schema
   (`install/sql/tables/companies.sql`) and demo data updated.
2. Existing installations keep working: the new account is initialised
   (reference: to the same value as the sales exchange account).
3. `CompanyPreferences.php` lets the user set it (a GL account picker like
   the existing exchange-variance accounts) and saves it.
4. The bank revaluation postings use the new account: the shared
   revaluation function (`includes/SQL_CommonFunctions.php`, used by
   `Currencies.php` and the login rate update) and `BankReconciliation.php`'s
   "Calculate and Post Exchange Difference".
5. Realized postings stay on the realized accounts: customer allocations
   (`CustomerAllocations.php`, `Z_AutoCustomerAllocations.php`) on the sales
   account, supplier allocations (`SupplierAllocations.php`) on
   `purchasesexchangediffact`.
6. Every place that lists or protects the company's control accounts knows
   the new one: `GLAccounts.php` (an account in use cannot be deleted),
   `Z_ChangeGLAccountCode.php` (renaming an account code updates it),
   `Z_CreateCompanyTemplateFile.php`, and where the company record is loaded
   (`includes/GetConfig.php`).
7. (Reference only, not required) the reference also renamed
   `exchangediffact` to `salesexchangediffact` with `ChangeColumnName` and
   refactored the preferences form into `includes/UIGeneralFunctions.php`.
