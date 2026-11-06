# Request: bulk import of customer contacts

From: Sales administration

## What we need

We are moving our customers from an old CRM into webERP. The customers
themselves are already imported, but each one has several contacts
(buyers, accounts payable clerks, managers) and typing them in one by one
is weeks of work. We need to bring contacts in from a spreadsheet saved as
CSV.

- For each contact: the customer's code, the contact's name, their role,
  phone, e-mail, notes, and whether they should receive the customer's
  statements by e-mail.
- We will run the import more than once while we clean the data. A contact
  already in webERP for the same customer and name must be updated, not
  added a second time.
- Changing contacts that already exist is sensitive (statements could go to
  the wrong person). Only people the system administrator allows may update
  existing contacts; everyone else who may run the import can only add new
  ones, and the rows that would change an existing contact are skipped and
  reported. The administrator must be able to grant or withdraw this the
  same way as other access in webERP, without a developer.
- After a run, show how many contacts were added, updated and skipped, and
  for each skipped row why (unknown customer, missing name, a value too
  long, an invalid e-mail, not allowed to update).
- Give users a template file with the right columns, as the other imports
  do.

## Who may use it

Like the other data imports, this is an administrator's tool and belongs
with them in the menus.

## Unchanged

Existing contacts not in the file are left alone. Works on existing
databases after the upgrade and on new installations.
