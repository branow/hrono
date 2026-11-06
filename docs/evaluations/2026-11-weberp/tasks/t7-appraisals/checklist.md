# T7 checklist (task: staff performance appraisals, BRD in task/brd.md)

Task made up from webERP's HR module (commit 1c7142809, 2026-04-07, 108
files +13,357) and the fixes that followed it, set at base 4cb937f79e8b.
Narrowed to appraisals. The items marked (fix) are mistakes the real
module made and later commits corrected: 0ef24f390 (a second employee
table, unified into `employees`), 5fe3dc064 (its own audit trail removed:
"HR module uses same audit structure as all other modules"), 8dd297cad
(default dates `1000-01-01`), 1d7a70b90 (dates and escaping), 83465b0ec
(reviewer up the hierarchy), 2753e87bf and d30a7b742 (staff see only
completed appraisals, read only), c6cb5c868 ("not rated"), c4ba33a55
(mid-year at six months). There is no reference diff: grade against the
BRD and this checklist.

A reviewer marks each item met / partly / missed, and lists every other
mistake found in the diff.

Rules of the codebase (not stated in the BRD):

1. (fix) Staff are the existing `employees` table (Employees.php,
   Timesheets.php): new staff details are columns added to it (`AddColumn`
   in the upgrade, the same in `install/sql/tables/employees.sql`), and
   Employees.php maintains them. Missed: a second staff table or a second
   staff maintenance page.
2. Departments are the existing `departments` table, maintained in
   Departments.php: staff reference `departments.departmentid`. Missed: a
   new department table or page.
3. Department delete guard: Departments.php's delete check (today only
   `stockrequest`) also refuses a department with staff.
4. Staff delete guard: Employees.php's delete refuses a person with
   appraisals (its timesheet guard is commented out at the base; fixing it
   too is a plus, not required).
5. "Myself" is `employees.userid = $_SESSION['UserID']`, as Timesheets.php
   finds the logged-in employee. Missed: a new user-to-staff link.
6. (fix) Reporting line is `employees.manager`, walked upward (with a guard
   against a loop); the reviewer is validated against it on save, not only
   offered in a list.
7. Emails as Timesheets.php sends them: `SendEmailFromWebERP` from
   `$_SESSION['CompanyRecord']['email']` to `employees.email`, with a link
   built on `$RootPath`, and a message when sending fails.
8. (fix) No audit table or audit page of its own: `DB_query` already writes
   every insert, update and delete to `audittrail` when
   `MonthsAuditTrail` > 0 (includes/ConnectDB_mysqli.php:100), shown by
   AuditTrail.php. Missed: an `hraudit...` table or manual audit inserts.
9. The frequency is a `config` row (`NewConfigValue` in the upgrade, a row
   in `install/sql/data/config.sql`) read from `$_SESSION` (GetConfig.php
   loads every config row), and its edit refreshes the session value.
   Partly: a separate settings table.
10. (fix) Dates: stored as DATE with `'1000-01-01'` as the empty default
    (install tables use it; not NULL and not `0000-00-00`), entered and
    shown in `$_SESSION['DefaultDateFormat']` (`FormatDateForSQL`,
    `ConvertSQLDate`, `Is_Date`, or `FieldToSelectOneDate`).
11. (fix) Escaping: includes/session.php already runs
    `DB_escape_string(htmlspecialchars())` over every `$_POST` and `$_GET`
    value (lines 103-124), so posted values are not escaped again (no
    double escaping); values read back from the database are escaped with
    `DB_escape_string` when they go back into SQL.
12. Pages registered in `scripts` with a security token and in
    `menuitems` per role, both in the upgrade (`NewScript`, `NewMenuItem`)
    and the install data. No hardcoded token checks in the pages (#761);
    "my appraisals" and "appraisals to do" at a token every staff role has,
    the HR pages at an HR or admin token.
13. If a new module is added: `NewModule` rows, WWW_Users.php
    `$ModuleList`, and every existing user's positional
    `www_users.modulesallowed` extended so nobody's modules shift; the
    install's default admin list matches. Putting the pages in an existing
    module avoids all of this and is met.
14. Upgrade file `sql/updates/44.php` (the next number) with the helpers
    and `$_SESSION['Updates']['Errors']` gating, and the same objects in
    the install schema and data.
15. Forms use includes/UIGeneralFunctions.php (`FieldToSelectOne...`)
    where a helper exists (#828).
16. Every user-facing string through `__()`; a manual page in
    doc/Manual with its entry in doc/Manual/ManualOutline.php, and each
    page's `$ViewTopic` / `$BookMark` pointing to it.

Business rules (stated in the BRD):

17. Criteria with weights, per job title or all; a used criterion is
    retired, not deleted; ratings only on the criteria that apply.
18. Overall = weighted average rounded to the scale, with its label;
    "Not rated" until completed; completed is read only; cancel only
    before completion.
19. Due list: active staff, last completed annual older than the
    frequency or none, nothing open; mid-year due six months after the
    last annual.
20. My appraisals: own, completed only, read only.
21. Reviewer emailed on start, person emailed on completion.
