# Business request: staff performance appraisals

## Background

We use webERP for sales, stock, manufacturing and the ledger, and we already
keep our staff in it: each person's manager, their labour item and normal
hours, their login, and their weekly timesheets. Appraisals are done today in
spreadsheets that HR chases by email. We want them in webERP, on the same
staff records, so HR, managers and staff work from one place.

## What we need

1. **Staff details for HR.** For every member of staff HR needs to record
   the department they work in (our departments are already set up in
   webERP), their job title, the date they started, and whether they are
   still with us. People who have left are kept, but are no longer due for
   appraisals.

2. **What staff are appraised on.** HR maintains a list of criteria (for
   example "Quality of work", "Teamwork"). Each criterion has a weight, and
   applies either to every job title or to one job title only. A criterion
   that has been used in an appraisal cannot be deleted, only retired.

3. **The rating scale.** Each criterion is rated 1 to 5: 1 Unsatisfactory,
   2 Needs improvement, 3 Meets expectations, 4 Exceeds expectations,
   5 Outstanding.

4. **Starting an appraisal.** HR starts an appraisal for a member of staff,
   either an annual one or a mid-year one, with the date it is due. The
   reviewer is the person's manager by default; HR may choose another
   reviewer, but the reviewer must be someone above the person in the
   reporting line (their manager, their manager's manager, and so on). The
   reviewer is told by email that the appraisal is waiting for them, with a
   link to it.

5. **Doing an appraisal.** The reviewer sees the appraisals waiting for
   them, rates the person on each criterion that applies to their job title,
   adds a comment per criterion and an overall comment, and can save and
   come back. When the reviewer completes it, the overall result is the
   weighted average of the ratings, rounded to the nearest point of the
   scale and shown with its label. Until an appraisal is completed its
   overall result shows as "Not rated". HR can cancel an appraisal that has
   not been completed. A completed appraisal cannot be changed. When it is
   completed, the person appraised is told by email.

6. **Appraisals due.** HR wants a list of staff due an appraisal: everyone
   still with us whose last completed annual appraisal is older than the
   appraisal frequency, or who has never had one, and who has no appraisal
   open now. The frequency, in months, is a company setting HR can change;
   it starts at 12. A mid-year appraisal is due six months after the last
   annual one.

7. **My appraisals.** Any member of staff who logs in to webERP can see
   their own completed appraisals, read only: the criteria, ratings,
   comments and overall result. They do not see appraisals that are still
   open or were cancelled, and never anyone else's.

8. **Keeping the records whole.** A member of staff who has appraisals, or
   a department that has staff in it, cannot be deleted. Changes to
   appraisals must be traceable in the same way as changes to other records
   in webERP.

9. **Who can do what.** Setting up criteria and the frequency, starting and
   cancelling appraisals and the due list are for HR. Doing an appraisal is
   for reviewers; seeing one's own appraisals is for every member of staff.
   Our administrator decides which roles get each of these, the same way as
   for the rest of webERP.

10. **The usual.** It must work on a new installation and on an upgrade of
    an existing one, read and write dates in each user's date format, be
    translatable like the rest of webERP, and be described in the manual.
