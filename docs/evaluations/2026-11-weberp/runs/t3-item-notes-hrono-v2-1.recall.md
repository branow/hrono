hrono recall from tree "weberp": the passages most likely to answer this prompt, one per topic, best first. Each is a slice of a page of the map; the page states the whole part. Read the pages listed here before anything else in the map, best first, and the overview only for the parts they leave out.

Pages, best first:
1. /Users/orest/hrono-weberp/exports/4cb937f79e8b57063bd47132413abdac8abbcbdc/weberp-sales-purchasing-stock-work-order-gl-and-master-data--151/weberp-zimport-utilities-and-stockcounts-csv-bulk-import-pag-56/brief.md  (brief of topic 56)
2. /Users/orest/hrono-weberp/exports/4cb937f79e8b57063bd47132413abdac8abbcbdc/weberp-installer-seed-data-schema-api-qa-mrp-petty-cash-admi-150/weberp-repository-configuration-issue-templates-readme-and-t-36/brief.md  (holds README.md (webERP))
3. /Users/orest/hrono-weberp/exports/4cb937f79e8b57063bd47132413abdac8abbcbdc/weberp-installer-seed-data-schema-api-qa-mrp-petty-cash-admi-150/weberp-seed-data-system-settings-config-menu-items-menuitems-8/brief.md  (brief of topic 8)
4. /Users/orest/hrono-weberp/exports/4cb937f79e8b57063bd47132413abdac8abbcbdc/weberp-sales-purchasing-stock-work-order-gl-and-master-data--151/weberp-stock-item-maintenance-stocks-php-plus-the-zchangesto-72/brief.md  (holds Stocks.php (webERP))
5. /Users/orest/hrono-weberp/exports/4cb937f79e8b57063bd47132413abdac8abbcbdc/weberp-installer-seed-data-schema-api-qa-mrp-petty-cash-admi-150/weberp-install-seed-data-configuration-menus-scripts-registr-9/brief.md  (brief of topic 9)
6. /Users/orest/hrono-weberp/exports/4cb937f79e8b57063bd47132413abdac8abbcbdc/weberp-database-upgrade-and-migration-scripts-149/weberp-2-9-2-9a-upgrade-script-help-table-text-new-columns-a-14/brief.md  (holds sql/mysql/upgrade2.9-2.9a.sql (webERP))
7. /Users/orest/hrono-weberp/exports/4cb937f79e8b57063bd47132413abdac8abbcbdc/weberp-installer-seed-data-schema-api-qa-mrp-petty-cash-admi-150/weberp-install-data-menuitems-modules-and-systypes-seed-fixt-10/brief.md  (brief of topic 10)
8. /Users/orest/hrono-weberp/exports/4cb937f79e8b57063bd47132413abdac8abbcbdc/weberp-accounts-receivable-accounts-payable-bank-and-gl-post-152/weberp-fixed-assets-depreciation-item-maintenance-register-a-110/brief.md  (holds FixedAssetItems.php (webERP))
9. /Users/orest/hrono-weberp/exports/4cb937f79e8b57063bd47132413abdac8abbcbdc/weberp-installer-seed-data-schema-api-qa-mrp-petty-cash-admi-150/weberp-csv-import-utilities-for-customers-debtors-and-branch-55/brief.md  (brief of topic 55)
10. /Users/orest/hrono-weberp/exports/4cb937f79e8b57063bd47132413abdac8abbcbdc/weberp-sales-purchasing-stock-work-order-gl-and-master-data--151/weberp-utility-pages-customer-branch-csv-import-zimportcustb-52/brief.md  (brief of topic 52)

### 1. brief of topic 56

- Fixed asset error text says "more than 3 characters" while the code checks only `strlen==0` or `>50`.
- Stocks: the `locstock` rows are created for every location. `ItemPDF` has to hold a filename or `none`. Stocks does not check that `CategoryID`, `TaxCat` or `MBFlag` references exist beyond the checks listed.
- Suppliers does not check that `CurrCode`, `SupplierType`, `PaymentTerms`, `TaxGroup` or `FactorID` exist.
- Suppliers does not check latitude or longitude.
- `StockCounts.php` has no live Enter or View body in the source shown, so nothing about saving counts follows from it. Its import template is only a download; no importer reading `StockCode, QtyCounted, Reference` is in this topic.


### 2. README.md (webERP)

## Introduction

webERP is a free open-source ERP system, providing best practise, multi-user business administration and accounting tools
over the web. For further information and for a full list of features, please visit the support site at: https://www.weberp.org/

## Demo

A live demo of the latest (currently RC) release is available on the webERP support site, where you can log in and experiment
with all the webERP features: https://www.weberp.org/demo/



### 3. brief of topic 8

# webERP seed data: system settings (`config`), menu items (`menuitems`), script security levels (`scripts`) and demo stock rows

Seed and fixture data for the webERP database, mostly as SQL INSERTs. It holds shop and system configuration keys, the `menuitems` navigation rows per security role, `scripts` page-security levels, and demo stock data. Nothing here runs logic. The menu rows are read at login by `webERP/includes/MainMenuLinksArray.php`. `webERP/install/sql/data/menuitems.sql` carries an installer copy of the menu rows. `webERP/sql/updates/5.php` creates the tables and fills the menu with `NewMenuItem()` calls.

## Contract


### 4. Stocks.php (webERP)

if (isset($_POST['LongDescription'])) {
	$LongDescription = AddCarriageReturns($_POST['LongDescription']);
} else {
	$LongDescription = '';
}
echo '<field>
		<label for="LongDescription">' . __('Part Description') . ' (' . __('long') . '):</label>
		<textarea ' . (in_array('LongDescription', $Errors) ? 'class="texterror"' : '') . '  name="LongDescription" cols="40" rows="3">' . stripslashes($LongDescription) . '</textarea>
	</field>';



### 5. brief of topic 9

## Hazards
- The installer silently aborts on any step failure. This leaves a partly built database and no message.
- The config file has demo values (test@company.com, ShopMode=test, jurisdiction `????`).
- Rerunning a fixture has no duplicate guard.
- The scripts data is truncated (trailing comma).
- Menu and token administration have no transaction or audit log.

## Sources to open first
- `webERP/install/sql/data/config.sql`: all system parameters and shop terms.
- `webERP/install/sql/data/scripts.sql`: page security levels.
- `webERP/install/sql/data/securitygroups.sql`, `securityroles.sql` and `securitytokens.sql`: the permission model.
- `webERP/install/sql/data/menuitems.sql`: the menu.
- `webERP/install/sql/data/prodspecgroups.sql` and `currencies.sql`: the other seed data.

### 6. sql/mysql/upgrade2.9-2.9a.sql (webERP)

This description is used in the look up boxes provided each time the stock item is invoiced, credited or adjusted. There is also the facility to enter long descriptions for each part which show on the screens that customers could access to place orders. This field allows very long descriptions or even features and benefits to be described for the item. The intention for this field is that it could be used for producing a company catalogue or for online ordering by customers who may need more information about a product. It is only the description (short) that displays on invoices and credit notes.\r\n<br /><br />\r\n<font size="+1"><b>Categories</b></font>\r\n<br /><br />\r\nThese categories need to be set up first - from the System Setup tab of the menu. 

### 7. brief of topic 10

| id | name |
|---|---|
| 0 | Journal - GL |
| 1 | Payment - GL |
| 2 | Receipt - GL |
| 3 | Standing Journal |
| 4 | Journal Template Number |
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
| 39 | Sales Commision Accruals |
| 40 | Work Order |
| 41 | Asset Addition |


### 8. FixedAssetItems.php (webERP)

if (isset($_POST['LongDescription'])) {
	$LongDescription = AddCarriageReturns($_POST['LongDescription']);
} else {
	$LongDescription ='';
}
echo '<field>
		<label for="LongDescription">' . __('Asset Description') . ' (' . __('long') . '):</label>
		<textarea ' . (in_array('LongDescription',$Errors) ?  'class="texterror"' : '' ) .'  name="LongDescription" required="required" title="" cols="40" rows="4">' . stripslashes($LongDescription) . '</textarea>
		<fieldhelp>' . __('Enter the lond description of the asset including specs etc. Up to 255 characters are allowed.') . '</fieldhelp>
	</field>';

if (!isset($New) ) 

### 9. brief of topic 55

# webERP CSV import utilities for customers (debtors and branches) and suppliers: `Z_ImportDebtors.php` and `Z_ImportSuppliers.php`

Two utility pages upload a CSV file and write customer or supplier master data to the database. `Z_ImportDebtors.php` reads and writes `debtorsmaster` and `custbranch`, reads `debtortrans`, and calls `GetNextTransNo(500)`. `Z_ImportSuppliers.php` is only partly shown: its form state and field headings.



### 10. brief of topic 52

- The same file uploaded twice inserts on the first run. On the second run with UpdateIfExists off it only lists the branches as existing. With it on, it re-updates them with the same values.
- Fields are put into SQL by string concatenation (`'" . $_POST['DebtorNo'] . "'`). The code shown has no escaping, so it relies on `ContainsIllegalCharacters` for some fields only. Fields such as SpecialInstructions have no illegal-character check.
- ContactName, Email, PhoneNo and FaxNo are checked only `!== null`, so empty strings are tested too. Empty Email fails `FILTER_VALIDATE_EMAIL`, so email is effectively required unless the value is null.
- Longitude is checked for numeric content but the latitude/longitude defaults apply only when `$Latitude` is not set.

