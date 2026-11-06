# T4 checklist (task: the forecasting module, BRD in task/brd.md)

Task made up from webERP's forecasting module (commit ef95df0b3,
2026-03-19, 34 files +8,989), set at base 4cb937f79e8b (the tree's commit,
~500 app files before the module's real base). The BRD was written from the
module's manual (doc/Manual/ManualForecastManagement.html) in business
terms, without its file, table or SQL details.

**The reference is incomplete and was written on a later base.** Checked
2026-11-06 in the reference: (a) its sales history is
`salesorderdetails.quantity`, ordered and not invoiced, with no credits; (b)
it takes `debtorsmaster.salestype` as "customer type" (the customer type is
`debtorsmaster.typeid`); (c) it adds `custtype` and `loccode` columns to
`salesanalysis` but none of the pages that write `salesanalysis`
(ConfirmDispatch_Invoice.php, Credit_Invoice.php, CounterSales.php,
CounterReturns.php, ...) fills them; (d) it inserts the module at menu
position 7 without touching existing users' `www_users.modulesallowed`;
(e) its includes use the later `__DIR__` style. Grade against the BRD and
this checklist, not the reference.

A reviewer marks each item met / partly / missed.

1. Database for new and existing installs: an upgrade script
   `sql/updates/44.php` (the next number at the base) using webERP's
   helpers (`CreateTable`, `AddColumn`, `NewScript`, `NewMenuItem`,
   `NewModule`, `executeSQL`, `$_SESSION['Updates']['Errors']` gating), and
   the same objects in the fresh-install schema and data
   (`install/sql/tables/*.sql`, `install/sql/data/scripts.sql`,
   `menuitems.sql`, `modules.sql`).
2. Module access: the module appears in the main menu only for users allowed
   it, and WWW_Users.php can grant it (`$ModuleList`/`$ModuleListLabel`).
   Module visibility is the positional comma list
   `www_users.modulesallowed` read by `index.php` in the `modules`
   sequence order (`includes/LoginFunctions.php` explodes it), so a module
   inserted mid-list shifts every existing user's modules unless the
   upgrade rewrites their lists; `install`'s default admin list
   (`includes/InstallFunctions.php`) must match too. Met: existing users
   keep exactly their modules.
3. Page security and page structure: every new page is registered in
   `scripts` with a security level and appears in `menuitems` for the
   roles; pages follow webERP's page pattern (`includes/session.php`,
   `$Title`, header/footer, `FormID` on forms, `__()` strings, `prnMsg`),
   and do not escape POST data again (session.php already applies
   `DB_escape_string(htmlspecialchars())`).
4. Sales history is real sales: invoiced quantities net of credits (e.g.
   `stockmoves` types 10/11 with `-qty`, or `salesanalysis` actuals with
   `budgetoractual = 1` and its period mapping), in monthly buckets per
   item and location; re-extracting a range replaces it.
5. Summary forecasts by customer type, area and salesperson use the right
   fields (`debtorsmaster.typeid` for customer type, `custbranch.area` or
   `salesanalysis.area`, the salesperson) and, if columns are added to an
   existing table, every writer of that table fills them.
6. The 12 methods as specified, with minimum history enforced, no negative
   quantities, and best fit by hold-out accuracy (single item and
   category).
7. Review and revision: revised quantity overrides calculated quantity in
   review, accuracy and MRP; clearing it restores the calculated one.
8. Accuracy metrics MAD, POA, MSE, RMSE against actuals; method comparison.
9. MRP integration: writes `mrpdemands` (stockid, mrpdemandtype, quantity,
   duedate) under a forecast demand type that the upgrade creates in
   `mrpdemandtypes`; replace and incremental modes never double demand and
   never touch other demand types; MRP.php then plans from them.
10. Parameters stored and editable (alpha, beta, gamma, season length, MA
    periods, hold-out, horizon) and used as defaults.
11. Category and batch generation with per-item results and failure
    reasons; dashboard and inquiry.
12. Nothing existing breaks: menus of other modules, existing pages, fresh
    install (positional INSERTs match their tables).
