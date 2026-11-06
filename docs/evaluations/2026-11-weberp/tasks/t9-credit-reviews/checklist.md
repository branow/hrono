# Checklist: t9 customer credit reviews (not given to the agent)

Base 4cb937f79e8b. A made-up task (no upstream reference diff), written
2026-11-06 under amendment 5 before any run. Items 1-10 are what the request
asks; items 11-17 are rules that sit away from the code a change like this
starts from, each with where the code holds it and which existing map page
(export `4cb937f...-threads`) states it.

## The request

1. A new table for reviews keyed on the customer (`debtorsmaster.debtorno`,
   with a foreign key as the customer tables have), holding review date,
   reviewer (the user), outcome, new limit, next review date, comments
   (long text).
2. The table in the install schema (`install/sql/tables/`) and created by
   a new upgrade file `sql/updates/44.php` through the upgrade helpers
   (`CreateTable`, `NewScript`, `NewMenuItem`, ...), not raw SQL.
3. A page to record, list (newest first) and correct reviews of one
   customer.
4. The reviewer is the logged-in user (`$_SESSION['UserID']`), not typed.
5. A changed limit updates `debtorsmaster.creditlimit`; "on hold" sets
   `debtorsmaster.holdreason` to a hold reason that stops invoicing
   (`holdreasons.dissallowinvoices`), not a made-up value; the review and the
   customer change are saved in one transaction.
6. Reached from the customer's page (`SelectCustomer.php`, next to notes
   and contacts), with the reviews shown there.
7. A list of customers whose next review date has passed (only each
   customer's latest review counts).
8. Dates entered and shown in the user's date format (`Is_Date`,
   `FormatDateForSQL`, `ConvertSQLDate`).
9. Strings translatable (`__()`), the form carries `FormID`.
10. A manual entry (doc/Manual, AR pages) and its outline entry.

## Rules away from the change

11. Customer code change: `Z_ChangeCustomerCode.php` moves every table
    keyed on `debtorno` to the new code (custcontacts, custnotes, custitem,
    ...). The reviews table must be added there, or a renamed customer
    loses its reviews / the rename fails on the foreign key. No code search
    from "credit review" reaches this file. Map: topic 105 lists the tables
    that utility updates.
12. Customer delete: `Customers.php` refuses or cascades per table; reviews
    must either block the delete or be deleted with the customer (not left
    orphaned, not a foreign-key error on delete). The obvious neighbour to
    copy, custnotes, is itself not deleted there. Map: topic 105 (delete
    refuses on debtortrans, salesorders, salesanalysis; leaves rows of other
    tables behind).
13. Input escaping: `includes/session.php` already runs every `$_POST` and
    `$_GET` value through `DB_escape_string(htmlspecialchars())`. The page
    must not escape again (entities growing on each save) and must not put
    escaped POST text back into the form after a save (line breaks shown as
    literal `\r\n`). Map: topic 50.
14. Access by an existing token through the `scripts` table: the AR pages
    (AddCustomerNotes, Customers, CustomerReceipt) use token 3 "Credit notes
    and AR management". No new hardcoded token, no `in_array(<n>,
    $_SESSION['AllowedPageSecurityTokens'])` constant. Map: topic 174 ("Do
    not hardcode tokens"), 220.
15. Scripts and menu rows in both the install data
    (`install/sql/data/scripts.sql`, `menuitems.sql`) and the upgrade file,
    for every role that holds the token (`NewMenuItem`), not only role 8.
    Map: topic 10 (seed data, menu items).
16. Form fields through `includes/UIGeneralFunctions.php`
    (`FieldToSelectOneDate`, `FieldToSelectOneTextArea`, ...), the newer
    convention (#828), not hand-written inputs copied from older pages.
    Map: topics 50, 123, 225.
17. Postgres: webERP keeps `UpgradeDB_postgres.php` beside the MySQL
    helpers; the upgrade uses the helpers so both work (no MySQL-only DDL in
    the upgrade file).

## Scoring

Each item met 1 / partly 0.5 / missed 0. Reported: items 1-10 and 11-17
separately, and in total. Correctness 0-5 and conventions 0-5 as in the
reviewer prompt.
