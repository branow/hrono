# Task: revalue foreign-currency bank accounts on automatic rate updates

webERP can update exchange rates automatically every day. When it does,
the value of the foreign-currency bank accounts is not updated, so their
balances drift from the current rate and the difference has to be
reconciled by hand with "Calculate and Post Exchange Difference" in the
bank reconciliation.

Make the automatic daily exchange-rate update also bring the
foreign-currency bank accounts up to the new rates, so no manual
reconciliation is needed for the rate change.


The webERP repository is in the current directory; the task is task/task.md. There is nothing to run against: deliver the change as files.