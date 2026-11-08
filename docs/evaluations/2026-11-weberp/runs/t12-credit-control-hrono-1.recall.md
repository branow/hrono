hrono recall from tree "weberp": the passages of the map that best match this prompt, best first. Each is a few lines of a brief or a source file; open the brief named with it for the whole part.

### Passage 1, from the file api/includes/api_debtortransactions.php (webERP), described in the brief /Users/orest/hrono-weberp/exports/4cb937f79e8b57063bd47132413abdac8abbcbdc-threads/weberp-finance-and-ledger-area-152/weberp-api-debtor-transactions-gl-accounts-groups-sections-s-62/brief.md

/*End of CreateCreditNote method */

/** Create a customer invoice in webERP. This function will bypass the
 * normal procedure in webERP for creating a sales order first, and then
 * delivering it.

 * NB: There are no stock updates no accounting for assemblies no updates
 * to sales analysis records - no cost of sales entries in GL

 ************ USE ONLY WITH CAUTION********************
 */
function InsertSalesInvoice($InvoiceDetails, $user, $password) 

### Passage 2, from the file SelectOrderItems.php (webERP), described in the brief /Users/orest/hrono-weberp/exports/4cb937f79e8b57063bd47132413abdac8abbcbdc-threads/weberp-sales-purchasing-stock-manufacturing-master-data-repo-151/weberp-sales-order-entry-and-item-selection-pages-selectorde-37/brief.md

{  /*Check credit limits is 1 for warn and 2 for prohibit sales */
			$_SESSION['Items'.$identifier]->CreditAvailable = GetCreditAvailable($_SESSION['Items'.$identifier]->DebtorNo);

			if ($_SESSION['CheckCreditLimits']==1 AND $_SESSION['Items'.$identifier]->CreditAvailable <=0){
				prnMsg(__('The') . ' ' . htmlspecialchars($MyRow[0], ENT_QUOTES, 'UTF-8', false) . ' ' . __('account is currently at or over their credit limit'),'warn');
			} elseif ($_SESSION['CheckCreditLimits']==2 AND $_SESSION['Items'.$identifier]->CreditAvailable <=0){
				prnMsg(__('No more orders can be placed by') . ' ' . htmlspecialchars($MyRow[0], ENT_QUOTES, 'UTF-8', false) . ' ' . __(' their account is currently at or over their credit limit'),'warn');
				include('includes/footer.php');
				exit();
			}
		}

	

### Passage 3, from the file install/sql/data/scripts.sql (webERP), described in the brief /Users/orest/hrono-weberp/exports/4cb937f79e8b57063bd47132413abdac8abbcbdc-threads/weberp-installer-seed-data-schema-build-ci-and-project-histo-150/weberp-install-seed-data-config-currencies-product-spec-grou-9/brief.md

('CustomerAccount.php',1,'Shows customer account/statement on screen rather than PDF'),('CustomerAllocations.php',3,'Allows customer receipts and credit notes to be allocated to sales invoices'),('CustomerBalancesMovement.php',3,'Allow customers to be listed in local currency with balances and activity over a date range'),('CustomerBranches.php',3,'Defines the details of customer branches such as delivery address and contact details - also sales area, representative etc'),('CustomerInquiry.php',1,'Shows the customers account transactions with balances outstanding, links available to drill down to invoice/credit note or email invoices/credit notes'),('CustomerPurchases.php',5,'Shows the purchases a customer has made.'),

### Passage 4, from the brief /Users/orest/hrono-weberp/exports/4cb937f79e8b57063bd47132413abdac8abbcbdc-threads/weberp-sales-purchasing-stock-manufacturing-master-data-repo-151/timesheets-and-fixed-asset-maintenance-scheduling-weberp-30/brief.md

- **The Reminders script does not match its purpose.** The manager mail is named 'overdue' but the query lists tasks not yet due. The user pass lists tasks whose due date minus 10 days is still in the future. Neither query matches its name.
- **Tasks that are due or past due are never picked up.** Both queries need `ADDDATE(...) > CURDATE()`.
- **Overdue marking is inverted.** 'NB: THIS JOB IS OVERDUE' is appended when the due date is later than today.
- **Reminders can be run by anyone.** `$AllowAnyone=true` means anyone who can reach the URL can trigger the emails.
- **Reminders can send twice.** Each run re-sends. Nothing records what was sent.


### Passage 5, from the brief /Users/orest/hrono-weberp/exports/4cb937f79e8b57063bd47132413abdac8abbcbdc-threads/weberp-sales-purchasing-stock-manufacturing-master-data-repo-151/weberp-credit-notes-entry-screen-posting-and-delete-utility-17/brief.md

- Lines with `Quantity <= 0` are dropped from posting. A controlled line starts at Quantity 0 and is dropped unless serials are entered, so it posts only after serial entry.
- `ReverseOverCharge` changes no stock quantity. It writes a hidden stock move and a sales analysis reduction of amount and discount only. It skips the COGS credit, but see the note above on the stock-account debit.
- The location list is limited to locations with `canupd=1` for the user. The POSTed `Location` is later used without re-checking that permission.
- The posting path has no duplicate guard beyond the session being unset. A repeat POST gets "already processed" only because the session key is gone. With a reused `identifier` from a second tab, a second credit can be processed.
