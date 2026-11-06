hrono recall from tree "weberp": the passages of the map that best match this prompt, best first. Each is a few lines of a brief or a source file; open the brief named with it for the whole part.

### Passage 1, from the file install/sql/data/scripts.sql (webERP), described in the brief /Users/orest/hrono-weberp/exports/4cb937f79e8b57063bd47132413abdac8abbcbdc-threads/weberp-installer-seed-data-schema-build-ci-and-project-histo-150/weberp-install-seed-data-config-currencies-product-spec-grou-9/brief.md

('CustomerAccount.php',1,'Shows customer account/statement on screen rather than PDF'),('CustomerAllocations.php',3,'Allows customer receipts and credit notes to be allocated to sales invoices'),('CustomerBalancesMovement.php',3,'Allow customers to be listed in local currency with balances and activity over a date range'),('CustomerBranches.php',3,'Defines the details of customer branches such as delivery address and contact details - also sales area, representative etc'),('CustomerInquiry.php',1,'Shows the customers account transactions with balances outstanding, links available to drill down to invoice/credit note or email invoices/credit notes'),('CustomerPurchases.php',5,'Shows the purchases a customer has made.'),

### Passage 2, from the file sql/demo.sql (webERP), described in the brief /Users/orest/hrono-weberp/exports/4cb937f79e8b57063bd47132413abdac8abbcbdc-threads/weberp-installer-seed-data-schema-build-ci-and-project-histo-150/weberp-seed-data-system-settings-config-menu-items-menuitems-8/brief.md

('CustomerAccount.php',1,'Shows customer account/statement on screen rather than PDF'),('CustomerAllocations.php',3,'Allows customer receipts and credit notes to be allocated to sales invoices'),('CustomerBalancesMovement.php',3,'Allow customers to be listed in local currency with balances and activity over a date range'),('CustomerBranches.php',3,'Defines the details of customer branches such as delivery address and contact details - also sales area, representative etc'),('CustomerInquiry.php',1,'Shows the customers account transactions with balances outstanding, links available to drill down to invoice/credit note or email invoices/credit notes'),('CustomerPurchases.php',5,'Shows the purchases a customer has made.'),

### Passage 3, from the file issues/issue-760.md (webERP-threads), described in the brief /Users/orest/hrono-weberp/exports/4cb937f79e8b57063bd47132413abdac8abbcbdc-threads/weberp-database-installation-and-upgrade-149/weberp-database-schema-upgrades-and-installation-issue-threa-175/brief.md

My suspicion is that something about your exact database schema caused the upgrade system to not behave as expected. Hopefully @timschofield with his intimate understanding can help understand what happened and how to correct it. If you have regular backups of your database, it may be helpful to restore an old database from before the trouble started and then execute the upgrade scripts one by one with maximum error reporting and logging, and examining the database after each for expected behavior. This could be a long and laborious process but should be successful in identifying the cause.



### Passage 4, from the brief /Users/orest/hrono-weberp/exports/4cb937f79e8b57063bd47132413abdac8abbcbdc-threads/weberp-database-installation-and-upgrade-149/weberp-sql-upgrade-scripts-3-00-4-03-8-schema-and-data-migra-148/brief.md

- Only mysql, mysqli and mariadb are upgraded. Any other `DBType` prints 'Only mysql upgrades are performed seamlessly at this time'.
- OldVersion 'Manual' applies no SQL.

## Connections


### Passage 5, from the file CustomerAccount.php (webERP), described in the brief /Users/orest/hrono-weberp/exports/4cb937f79e8b57063bd47132413abdac8abbcbdc-threads/weberp-finance-and-ledger-area-152/weberp-customer-and-supplier-account-inquiries-plus-po-back--107/brief.md

. ")
				THEN debtortrans.balance
				ELSE 0 END
			END) AS overdue1,
			Sum(CASE WHEN paymentterms.daysbeforedue > 0 THEN
				CASE WHEN TO_DAYS(Now()) - TO_DAYS(debtortrans.trandate) > paymentterms.daysbeforedue
				AND TO_DAYS(Now()) - TO_DAYS(debtortrans.trandate) >= (paymentterms.daysbeforedue +
				" . $_SESSION['PastDueDays2'] 