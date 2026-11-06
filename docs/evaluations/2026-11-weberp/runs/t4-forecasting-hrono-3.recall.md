hrono recall from tree "weberp": the passages most likely to answer this prompt, one per topic, best first. Each is a slice of a page of the map; the page states the whole part. Read the pages listed here before anything else in the map, best first, and the overview only for the parts they leave out.

Pages, best first:
1. /Users/orest/hrono-weberp/exports/4cb937f79e8b57063bd47132413abdac8abbcbdc/weberp-installer-seed-data-schema-api-qa-mrp-petty-cash-admi-150/weberp-repository-configuration-issue-templates-readme-and-t-36/brief.md  (brief of topic 36)
2. /Users/orest/hrono-weberp/exports/4cb937f79e8b57063bd47132413abdac8abbcbdc/weberp-installer-seed-data-schema-api-qa-mrp-petty-cash-admi-150/weberp-install-data-menuitems-modules-and-systypes-seed-fixt-10/brief.md  (brief of topic 10)
3. /Users/orest/hrono-weberp/exports/4cb937f79e8b57063bd47132413abdac8abbcbdc/weberp-sales-purchasing-stock-work-order-gl-and-master-data--151/weberp-maintenance-pages-reference-data-forms-areas-credit-s-120/brief.md  (brief of topic 120)
4. /Users/orest/hrono-weberp/exports/4cb937f79e8b57063bd47132413abdac8abbcbdc/weberp-database-upgrade-and-migration-scripts-149/weberp-database-update-scripts-sql-updates-numbers-1-7-10-11-26/brief.md  (brief of topic 26)
5. /Users/orest/hrono-weberp/exports/4cb937f79e8b57063bd47132413abdac8abbcbdc/weberp-installer-seed-data-schema-api-qa-mrp-petty-cash-admi-150/weberp-xml-rpc-api-entrypoint-session-bootstrap-login-and-11/brief.md  (brief of topic 11)
6. /Users/orest/hrono-weberp/exports/4cb937f79e8b57063bd47132413abdac8abbcbdc/weberp-installer-seed-data-schema-api-qa-mrp-petty-cash-admi-150/weberp-test-harness-installer-anonymous-logged-in-page-acces-15/brief.md  (holds tests/install/InstallerTest.php (webERP))
7. /Users/orest/hrono-weberp/exports/4cb937f79e8b57063bd47132413abdac8abbcbdc/weberp-installer-seed-data-schema-api-qa-mrp-petty-cash-admi-150/weberp-seed-data-system-settings-config-menu-items-menuitems-8/brief.md  (brief of topic 8)
8. /Users/orest/hrono-weberp/exports/4cb937f79e8b57063bd47132413abdac8abbcbdc/weberp-database-upgrade-and-migration-scripts-149/weberp-legacy-mysql-upgrade-scripts-sql-mysql-upgrade-sql-3--147/brief.md  (brief of topic 147)
9. /Users/orest/hrono-weberp/exports/4cb937f79e8b57063bd47132413abdac8abbcbdc/weberp-installer-seed-data-schema-api-qa-mrp-petty-cash-admi-150/language-and-manual-administration-gettext-po-tools-user-man-40/brief.md  (brief of topic 40)
10. /Users/orest/hrono-weberp/exports/4cb937f79e8b57063bd47132413abdac8abbcbdc/weberp-reporting-and-document-output-153/weberp-financial-and-document-reports-pdf-html-spreadsheet-o-140/brief.md  (holds SuppPriceList.php (webERP))
11. /Users/orest/hrono-weberp/exports/4cb937f79e8b57063bd47132413abdac8abbcbdc/weberp-installer-seed-data-schema-api-qa-mrp-petty-cash-admi-150/weberp-includes-database-connection-session-login-bootstrap--50/brief.md  (brief of topic 50)

### 1. brief of topic 36

## Sources to open first

- `webERP/config.distrib.php`: all `config.php` keys and defaults.
- `webERP/includes/session.php`: how the keys are used at login, plus the security checks.
- `webERP/includes/Login.php`: the company selection and demo logic.
- `webERP/api/includes/api_session.php`, `webERP/api/includes/api_php.php`: the API session and login.
- `webERP/install/pages/page_6.php`: the order in which the installer writes everything.
- `webERP/phpunit.dist.xml`: the `TEST_*` keys.
- `webERP/composer.json`: dependencies and the PHP platform pin.
- `webERP/README.md`: requirements and install and upgrade steps.

### 2. brief of topic 10

# webERP install data: menuitems, modules and systypes seed fixtures

These are SQL INSERT fixtures that fill three tables at install: `menuitems` (navigation entries), `modules` (module list per security role) and `systypes` (transaction-type registry). They call nothing. The tables are read at login by `webERP/includes/MainMenuLinksArray.php`, and `webERP/index.php` uses what that file builds to draw the menu.



### 3. brief of topic 120

# webERP maintenance pages: reference-data forms (areas, credit status, customer/supplier/sales types, departments, employees, MRP demand types, maintenance tasks, manufacturers, payment methods, related items, translations, commission types, salespeople, shippers, tax provinces, units of measure, work centres) and Z_ clean-up utilities



### 4. brief of topic 26

## Sources to open first
- `webERP/Z_UpgradeDatabase.php`: runner, `executeSQL`, `updateDBNo`, and the error counters.
- `webERP/includes/session.php`: the `HighestFileName` version check, the redirect, and the `sessions` table use.
- `webERP/sql/updates/17.php`: the `gltotals` triggers.
- `webERP/sql/updates/5.php`: the full menu and module list.
- `webERP/sql/updates/1.php`: the sales commission schema.
- `webERP/includes/InstallFunctions.php`: the install-time `DBUpdateNumber`.

### 5. brief of topic 11

# webERP XML-RPC API: entrypoint, session bootstrap, login and settings/reference-data functions



### 6. tests/install/InstallerTest.php (webERP)

{
		/// @todo allow using a phpunit env var to allow forcing removal of these if found (and also dropping the db schema),
		///       or is it too dangerous for end users?
		///       In the end it might be better to add a 2nd tests which runs the installer after config.php exists,
		///       and adds a new company
		if (file_exists(self::$rootDir . '/config.php') || is_dir(self::$rootDir . '/companies/' . $_ENV['TEST_DB_SCHEMA'])) {
			$this->markTestSkipped('config.php is already present. Will not run the installer test');
		}

		$crawler = $this->request('GET', self::$baseUri . '/install/index.php');

		// page 0
		$this->assertStringContainsString('Welcome to the webERP installer', $crawler->filter('body > div.wizard > h1')->text(), 'Missing title in installer page 0');
		

### 7. brief of topic 8

- The menu is only navigation. Real access is checked by `scripts.pagesecurity` and the user's role tokens, which are a separate copy (for example `PcAssignCashTabToTab.php` is shown at levels 6 and 12). Changing a menu row does not change a page's security level, and changing `scripts` does not hide a menu link.
- `5.php` populates menus through helper calls and not SQL, so the installer SQL copy (`webERP/install/sql/data/menuitems.sql`) and the update script can drift. For example, the installer's `/SupplierTenderCreate.php?New=Yes` and `?Edit=Yes` rows exist in the seed copy. The 5.php condensation shows PO Reports with only 4 items, while the installer seed has 5 (it adds `/POFinancialPlanning.php` at 20). A later update adds the difference.


### 8. brief of topic 147

# webERP legacy MySQL upgrade scripts (`sql/mysql/upgrade*.sql`, 3.03 → 4.15.2)

These are one-shot DDL/DML scripts that move a webERP database from one release to the next. They take no input. `webERP/UpgradeDatabase.php` reads them line by line and runs them. They write to the shared application tables (`config`, `scripts`, `securitytokens`, `www_users` and others) and finally set `config.VersionNumber`.



### 9. brief of topic 40

## Sources to open first
- `webERP/Z_poEditLangModule.php`: the most complex editor, with merge, edit and compile.
- `webERP/Z_poEditLangHeader.php`: header editing and file rotation.
- `webERP/Z_poEditLangRemaining.php`: untranslated entries.
- `webERP/Z_poAddLanguage.php`: language creation.
- `webERP/Z_poRebuildDefault.php`: template rebuild.
- `webERP/Z_poAdmin.php`: the menu page.
- `webERP/AutomaticTranslationDescriptions.php`: item-description translation.
- `webERP/ManualContents.php` and `webERP/GenerateManualPDF.php`: manual display and PDF.
- `webERP/includes/TranslationFunctions.php`: the Google call.

### 10. SuppPriceList.php (webERP)

'<meta name="author" content="WebERP " . $Version">
					<meta name="Creator" content="webERP https://www.weberp.org">
				</head>
				<body>
				<div class="centre" id="ReportHeader">
					' . $_SESSION['CompanyRecord']['coyname'] . '<br />
					' . __('Supplier Price List for').' '.$CurrentOrAllPrices . '<br />
					' . __('Printed') . ': ' . date($_SESSION['DefaultDateFormat']) . '<br />
					' . __('Supplier') . ' - ' . $_POST['supplier'] . ' - ' . $SupplierName . '<br />
					' . __('Category') . ' - ' . $Categoryname . '<br />
					' . __('Currency') . ' - ' . $CurrCode . '<br />
				</div>
				<table>
					<thead>
						<tr>
							<th class="SortedColumn">' . __('Code') . '</th>
							<th class="SortedColumn">' . __('Description') . '</th>
							<th class="SortedColumn">' . 

### 11. brief of topic 50

- In: `$_GET`/`$_POST`, `$_SESSION`, `$_SERVER['SCRIPT_NAME']`, and the globals from `config.php` (`$Host`, `$DBUser`, `$DBPassword`, `$DBPort` (default 3306), `$DBCharset`, `$DBType`, `$DatabaseName`, `$RootPath`, `$PathPrefix`, `$AllowAnyone`, `$PageSecurity`).
- Login form fields posted to `index.php`: `CompanyNameField`, `UserNameEntryField`, `Password`, `FormID`, `NewLogin=Yes`.
- Out, SQL: through `DB_query` to `www_users`, `sessions`, `favourites`, `audittrail`, `auditscripts`, `config`, `currencies`, `securitygroups`, `modules`, `menuitems`, `accountsection`, `paymentmethods`, `pagesecurity`, `companies`, `emailsettings`, `locations`, `locationusers`, `periods`, `areas`, `salesman`, `stockcategory`, `systypes`, `manufacturers`, `contracts`, `contractbom`, `contractreqts`.
