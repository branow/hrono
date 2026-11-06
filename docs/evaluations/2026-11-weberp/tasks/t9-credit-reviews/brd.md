# Business request: customer credit reviews

Our credit controller reviews each trade customer's credit every so often:
they look at how the customer pays, decide whether the credit limit stays,
goes up or goes down, or whether the account goes on hold, and write down
why. Today this lives in a spreadsheet, so nobody else sees it and reviews
are forgotten. We need it in webERP:

1. Record a credit review against a customer: the review date, who did it,
   the outcome (limit kept, limit raised, limit lowered, account on hold),
   the new credit limit where it changes, the date of the next review, and
   the controller's comments, which can run to a few paragraphs.
2. When a review changes the limit or puts the account on hold, the
   customer's account changes with it.
3. See a customer's past reviews, newest first, from the customer's page,
   and correct a review entered by mistake.
4. A list of customers whose next review date has passed.
5. Reviews belong to the customer: they stay with the customer through
   everything that can happen to the customer's account in webERP, and are
   never left behind pointing at a customer that no longer exists.

Only the people who look after customer credit may record or change
reviews. It must work on new installations and on upgrades, and be in the
manual.
