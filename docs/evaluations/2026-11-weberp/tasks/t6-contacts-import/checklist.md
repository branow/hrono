# T6 checklist (task: bulk import of customer contacts, request in task/brd.md)

Made-up task (no merged reference), base 4cb937f79e8b. The request is in
business terms only. The conventions it depends on are decided in GitHub
discussions before the base date (in the threads source and in the
workspace's github/ folder) and are applied inconsistently in the code, so
copying the nearest script can get them wrong. Checked 2026-11-06.

A reviewer marks each item met / partly / missed, with file and line.

1. A new `Z_Import...` page registered at security level 15 (system
   administrator) in both the upgrade script and
   `install/sql/data/scripts.sql`. Discussion #789: "all import scripts
   should be system administrator"; the install data still has several
   imports at 11 (Z_ImportChartOfAccounts, Z_ImportPartCodes,
   Z_ImportGLAccountGroups, Z_ImportGLAccountSections).
2. In the Utilities module menu (module code `Utilities`, discussions #789
   and #759: the other imports are there; `NewMenuItem('Utilities', ...)`
   with a section) in the upgrade script and in
   `install/sql/data/menuitems.sql`.
3. Upgrade script `sql/updates/44.php` with webERP's helpers (`NewScript`,
   `NewMenuItem`, `executeSQL`/`UpdateDBNo` as the other update files do),
   one update file for the whole change (#789).
4. The "may update existing contacts" right is a permission the
   administrator assigns to roles without a developer: a non-script entry
   in the `scripts` table checked through
   `$_SESSION['PageSecurityArray'][...]` against
   `$_SESSION['AllowedPageSecurityTokens']`, the way `CostUpdate` works
   (StockCostUpdate.php:164-165), not a hardcoded token number (#761:
   hardcoded tokens are to be removed).
5. The administrator can actually change that permission's level:
   `PageSecurity.php` rebuilds every posted name as `<name minus 4 chars>.php`
   (lines ~19-24), so an entry without `.php` cannot be updated from the
   screen (#761). Met: the change makes it editable (or registers it in a
   form the screen can update).
6. The form uses the shared field helpers of `includes/UIGeneralFunctions.php`
   (`FieldToSelectOneFile`, `OneButtonCenteredForm`, ...) as decided in #828
   for new or changed forms, with `FormID`, `__()` strings and `prnMsg`.
7. Template download and header check as the other `Z_Import*` pages do
   (`gettemplate`, column count and header names checked).
8. CSV values are escaped for SQL (`DB_escape_string`): file contents do not
   pass through session.php's escaping of POST data.
9. Validation per row: customer exists in `debtorsmaster`; name present;
   lengths within `custcontacts` (contactname 40, role 40, phoneno 20, email
   55, notes 255); e-mail format; statement flag 0/1. Each skipped row with
   its reason; counts of added, updated, skipped.
10. Update-or-insert keyed by customer and contact name; rows that would
    update are skipped and reported for a user without the permission.
11. The statement flag maps to `custcontacts.statement`, which
    PrintCustStatements.php (line ~131) uses to choose e-mail recipients.
12. Nothing existing breaks: other imports, PageSecurity.php for ordinary
    scripts, fresh install (positional INSERTs match).
