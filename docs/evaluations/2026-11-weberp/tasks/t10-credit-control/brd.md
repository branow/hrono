# Business request: customer credit control

## Background

We sell on account to about 900 trade customers in four currencies. Credit
control today is a spreadsheet, a shared mailbox and the credit controller's
memory. Last year we wrote off more in bad debt than we earned on our two
largest product lines. The board wants credit control inside webERP, so that
the rules are applied the same way every time, by everyone, and the auditors
can see what was done.

The credit controller, Maria, and her deputy do this work. Sales people and
customers must not be able to bypass it. Accounts and the auditors need the
ledger to agree with the customer accounts at every month end.

## 1. Credit reviews

1.1 Every trade customer is reviewed at least once a year; large or risky
customers more often. A review records: the date, who did it (the person
logged in), the outcome (limit kept, raised, lowered, account put on hold,
account released from hold), the new limit where it changes, the date the
next review is due, and Maria's comments, which often run to several
paragraphs and include quotes from the customer's emails.

1.2 When a review changes the limit or the hold, the customer's account
changes at the same moment. If either part fails, neither is saved.

1.3 Each customer carries the date its next review is due. It is set by
the last review and can be set when a customer is created. It must be kept
whatever way customer details are created or changed in webERP.

1.4 From a customer's page we see the past reviews, newest first, and can
correct one entered by mistake.

1.5 A report lists customers whose review is overdue or due within a number
of days we choose, with their balance, overdue amount, limit, the credit
still available to them and the date they last paid. It can be printed as
PDF.

## 2. Holding and releasing accounts

2.1 Putting an account on hold means no new invoices for that customer, by
any route: orders keyed by staff, orders that recur automatically,
electronic orders from our big customers, orders placed through our web
shop's connection, and invoicing of orders already entered. Today some of
these routes let held customers through.

2.2 We also want a "watch" state: staff are warned but can carry on.

2.3 Only Maria and her deputy may put on hold or release. Other people who
look after customer accounts may see the hold but not change it. Every
change of hold or limit is visible in the customer's review history with
who did it and why.

2.4 When an order would take a customer over its limit, what happens
follows our existing company setting for credit limit checks; nothing new
should contradict it.

## 3. Overdue reminders

3.1 Three reminder levels: a friendly reminder once an invoice is past due,
a firm reminder at our first overdue band, and a final notice at our second
band. The bands are the ones we already use for ageing in webERP. "Past
due" must mean exactly what the invoice, the statement and the aged debtors
report already say it means.

3.2 Maria runs the reminders from a screen: she sees who would get which
level, can leave anyone out, and then sends. A customer never gets the same
level twice for the same invoices, even if the run is repeated.

3.3 Each reminder is a PDF letter on our letterhead, emailed to the
customer's contacts who receive statements. If a customer has no such
contact, or the email fails, the letter is not counted as sent and Maria
sees which ones failed. Customers on hold get the final notice wording.

3.4 Reminders sent are visible on the customer's page with date, level and
the invoices included.

## 4. Late payment charges

4.1 At month end Maria may charge interest on overdue invoices at a rate we
set, and a fixed reminder fee for each final notice sent that month. She
decides when to run it; nothing is charged without her.

4.2 Charges are customer transactions in the customer's currency: they
appear on the customer's account, inquiry and statement, count in the
aged debtors, can be printed and emailed like an invoice, and can be
matched against payments. They post to the ledger in the same period,
to an income account we choose in the company setup, with the usual
receivables account on the other side, and can carry our ledger tags.

4.3 Running the charges twice for the same month must not charge twice.

## 5. Bad debt write-off

5.1 Maria can write off what is left on chosen invoices of a customer, or
the whole balance, with a reason. The write-off goes to a bad debt expense
account we choose in the company setup; it must never be posted straight
to a control account.

5.2 A write-off clears the invoices it covers. For foreign currency
customers, the difference between the rate of the invoice and the rate of
the write-off is treated as we treat it for payments.

5.3 Write-offs are customer transactions like the charges in 4.2.

## 6. Everyone sees only what they may

6.1 Sales people who log in to webERP see credit information only for
their own customers and transactions, in every list and report of this
work.

6.2 Customers who log in see their own reminders and charges, nobody
else's.

## 7. Data

7.1 Reviews, reminders and charges belong to the customer. They stay with
the customer through everything that can happen to a customer's account
in webERP, and are never left pointing at a customer that no longer exists.

7.2 Anything new we store about customers must be safe from the outside
connection our web shop uses: it may not be changed through it unless it
is validated.

## 8. Rollout

8.1 This must work on a new installation (with or without demo data) and
on an upgrade of our existing database, without anyone running SQL by
hand. Our database is MySQL; the project also supports other databases and
we do not want to break them.

8.2 New settings (interest rate, fee, reminder wording, review interval)
go where the other company settings are. The two new ledger accounts go in
the company setup with the other default accounts, and must not be
deletable while they are in use there.

8.3 Maria's screens are on the receivables menus. The manual explains the
whole process, and the help link on each screen opens the right part of it.
