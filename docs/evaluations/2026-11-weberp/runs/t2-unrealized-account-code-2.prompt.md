# Task: a separate GL account for unrealized currency exchange differences

When a currency rate is updated, webERP adjusts the value of all
foreign-currency bank accounts to the new exchange rate, so the balance
sheet shows the current value. That is an unrealized gain or loss: the next
rate update triggers another adjustment, and no foreign currency has
actually been sold or bought.

But these adjustments are posted to the "Sales Exchange Variances GL
Account" from the company preferences, which by its definition holds
realized profit and loss: the realized P/L of sales in foreign currency. So
realized and unrealized P/L are mixed in one account.

Add a company preference for a separate "currency exchange (unrealized)
P/L" GL account, alongside the existing exchange-variance accounts, and
post the revaluation of foreign-currency bank accounts to it. Existing
installations must keep working after the upgrade.


The webERP repository is in the current directory; the task is task/task.md. There is nothing to run against: deliver the change as files.