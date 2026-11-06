## T7 appraisals (code-gate run): audit by reading the code

I read every changed file in `/Users/orest/hrono-weberp/runs/t7-appraisals-code-gate` and checked the base code the checklist relies on:
- `session.php:103-124` escapes every posted value with `DB_escape_string(htmlspecialchars(..., ENT_QUOTES))`.
- `ConnectDB_mysqli.php:100` writes every insert, update and delete to `audittrail`.
- `GetConfig.php:9-17` loads every config row into the session.
- The next update number is 44, because base HEAD ends at 43.
- All the upgrade helpers it calls exist in `UpgradeDB_mysql.php`, and it calls them with the right signatures.
- The `demo.sql` change is real: rows added to the config, scripts, tokens, groups and menu items inserts. It is not a rewrite of the whole file.

### Verdicts

| # | Verdict | Evidence |
|---|---|---|
| 1 | met | 44.php:6-9 adds the columns to `employees` with `AddColumn('departmentid','employees',...)`, the same in `install/sql/tables/employees.sql`. Employees.php:84-88 saves them. |
| 2 | met | 44.php:11 links `employees` to `departments.departmentid` (`AddConstraint(... 'departments','departmentid')`). Employees.php reads its department list from `departments`. |
| 3 | met | Departments.php:140-149 adds `SELECT COUNT(*) FROM employees WHERE departmentid=...` and refuses the delete. |
| 4 | met | Employees.php:160-168 refuses `appraisals WHERE employeeid=... OR reviewerid=...`. The commented-out timesheet guard is left as it was. |
| 5 | met | AppraisalFunctions.php:251 finds the user with `WHERE userid='" . $_SESSION['UserID'] . "'`. |
| 6 | met | AppraisalFunctions.php:68-83 walks `manager` upward with a `$Seen` loop guard. Appraisals.php:94 rejects a reviewer outside the chain on save (`if (!in_array($ReviewerID, $Chain))`). |
| 7 | met | Appraisals.php:152 and AppraisalReview.php:177 call `SendEmailFromWebERP($_SESSION['CompanyRecord']['email'], array(<employee>['email'])...`. The link is built on `$RootPath`, and both show a warning when sending fails. |
| 8 | met | No audit table and no audit inserts anywhere. NOTES.md relies on `DB_query` writing to `audittrail`. |
| 9 | partly | It is a config row (44.php:60, `config.sql`), and the edit refreshes the session (AppraisalCriteria.php:36). But it is read back from the database, not from `$_SESSION`: AppraisalFunctions.php:56 `SELECT confvalue FROM config WHERE confname='AppraisalFrequencyMonths'`. |
| 10 | partly | Dates are entered and shown in the user's format (`Is_Date`, `FormatDateForSQL`, `ConvertSQLDate`). But the empty default is NULL, not `'1000-01-01'`: `startdate date DEFAULT NULL` in employees.sql and `completeddate date DEFAULT NULL` in appraisals.sql. |
| 11 | met | Posted values go into SQL as they come, with no second escape (AppraisalCriteria.php:66). Values read back from the database are escaped: AppraisalReview.php:124 `DB_escape_string($Criterion['description'])` and :151 for `jobtitle`. |
| 12 | partly | Registered with `NewScript` and `NewMenuItem` and in the install data, with no hardcoded token checks. My Appraisals is on token 23, which every staff role has. But "appraisals to do" is on token 22, given only to role 8: securitygroups.sql adds `(8,21),(8,22)`, and 44.php:76 gives it only to roles holding token 15. |
| 13 | met | No new module; the pages go in the existing manufacturing (`manuf`) menus. |
| 14 | met | `sql/updates/44.php` is the next number, uses the helpers, and gates on `if ($_SESSION['Updates']['Errors'] == 0)` (line 94). The install has the same tables and rows (one small default mismatch, mistake 3 below). |
| 15 | missed | The diff has no `FieldToSelectOne...` call at all. Dates, text and textareas are hand-written `<input type="text">` and `<textarea>`, although `FieldToSelectOneDate`, `...Text` and `...TextArea` exist. |
| 16 | met | Every string goes through `__()`. ManualLabour.html has the anchors `Appraisals`, `StartingAppraisals`, `DoingAppraisals`, `AppraisalsDue` and `MyAppraisals`. ManualOutline.php has the entries, and each page sets `$ViewTopic='Labour'` and a matching `$BookMark`. |
| 17 | met | `jobtitle=''` means every job title (AppraisalFunctions.php:151). Delete is blocked once used (AppraisalCriteria.php:98-101); otherwise the criterion can only be retired. Ratings are taken only for `AppraisalCriteriaFor($Appraisal['jobtitle'])`. |
| 18 | met | AppraisalFunctions.php:137-138 rounds the weighted average half up; the label is shown with it, and "Not rated" (line 32) until completed. Completed appraisals are refused under a lock (AppraisalReview.php:105-107). Cancel updates only `status=OPEN` rows (Appraisals.php:44). |
| 19 | met | AppraisalsDue.php:44-47 takes `active=1 AND NOT EXISTS ... status=OPEN`. Line 57 makes an annual due when last annual + frequency is before today; line 60 makes a mid-year due 6 months after the last annual. |
| 20 | met | MyAppraisals.php:31-33 shows only `employeeid IN (<own ids>) AND status=COMPLETED`, through a display function with no form. Changing the id in the URL is rejected. |
| 21 | met | The reviewer is emailed on start (Appraisals.php:145-163) and the person on completion (AppraisalReview.php:169-188). |

**Counts: 17 met, 3 partly, 1 missed.**

### Other mistakes

1. **Wrong behaviour: comments come back escaped after a save, and get mangled on the next save.**
   - AppraisalReview.php:191 puts the already-escaped `$_POST` value back into the overall comment (`$Appraisal['overallcomment'] = $OverallComment;`). Lines 215 and 248 do the same with the per-criterion comments when there is an input error.
   - `DB_escape_string` has turned line breaks into the literal characters `\r\n`, and backslashes into `\\`, so the textarea shows those literals.
   - If the reviewer saves again, the page escapes them a second time, and the literal `\r\n` text is stored permanently. Saving and coming back, which the BRD asks for, corrupts multi-line comments.

2. **Wrong behaviour: most managers cannot do the appraisals assigned to them.**
   - `AppraisalReview.php` is on token 22, which only the System Administrator role gets, on install and on upgrade.
   - A manager in any other role receives the email link and is refused the page.
   - Appraisals.php:98-108 accepts any reviewer with a webERP user, without checking that their role can open the review page.

3. **Convention: the upgrade and the install disagree on `jobtitle`.**
   - 44.php:7 calls `AddColumn('jobtitle','employees','VARCHAR(50)',' NOT NULL','',...)`.
   - `AddColumn` drops an empty default (`if (isset($Default) and $Default != '')`), so upgraded databases get `NOT NULL` with no default. The install has `DEFAULT ''`.
   - In strict mode, any insert into `employees` that leaves out `jobtitle` fails on upgraded databases only.

4. **Wrong behaviour: open appraisals get stuck when someone leaves.**
   - Unticking "Still Employed" leaves the person's open appraisals open.
   - If the reviewer leaves, there is no way to give their appraisal to someone else; HR can only cancel it.

5. **Convention: two smaller points.**
   - The frequency is read from the database on every page (`GetAppraisalFrequency`), even though `$_SESSION['AppraisalFrequencyMonths']` is kept up to date.
   - The page links in emails are built from `$_SERVER['HTTP_HOST']` (AppraisalFunctions.php:166), which trusts the request's Host header.

6. **Convention: `NOTES.md` was added at the repository root.** It is the agent's own notes and does not belong in a webERP change.

No security holes found:
- The reviewer page is limited to `reviewerid IN (<own ids>)` (AppraisalReview.php:52).
- My Appraisals is limited to the person's own completed appraisals.
- Cancelling an appraisal needs the HR token.
- No other SQL injection or XSS path found: ids are cast to int, and text is stored already escaped by session.php.
- The weighted average, the due list and the status changes are correct.
