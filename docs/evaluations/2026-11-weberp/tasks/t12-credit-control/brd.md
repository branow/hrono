# Business Requirements Document: Credit Control

| | |
|---|---|
| Prepared for | Finance Director |
| Prepared by | Business Analyst, Finance |
| Version | 1.0 (draft for sign-off) |
| Status | For review by Finance, Sales and IT |

## 1. Purpose

This document sets out what the business needs from a credit control capability in our ERP system. Today credit control lives in a spreadsheet and in the head of our credit controller. The board has asked that it move into the ERP, so that the same rules are applied to every customer every time, so that sales staff and customers cannot get around them, and so that our auditors can see what was decided, by whom and when.

The document describes the business behaviour we want. It does not say how the software should be built.

## 2. Background

We are a wholesale distributor with about 900 trade customers on account. Customers are billed in several currencies. Orders reach us in four main ways: entered by our sales office, placed by customers through our web shop, sent to us electronically by larger customers, and raised automatically from standing monthly orders.

Last financial year our bad debt write-offs were well above what the board considers acceptable. A review found the main causes were:

- Customers kept being supplied after they had stopped paying, because the "stop list" was a spreadsheet that the sales office and the web shop did not check.
- Credit limits were set once when the account was opened and rarely looked at again.
- Reminder letters were sent irregularly, depending on how busy the credit controller was.
- We charged no interest or late fees, so slow payers had no reason to pay on time.
- Write-offs were posted inconsistently, and at year end the auditors had trouble matching the sales ledger to the general ledger and to the decisions behind each write-off.

We already use the ERP for sales orders, invoicing, customer accounts, statements and the general ledger, so the credit control work should sit there too.

## 3. Stakeholders

| Stakeholder | Interest |
|---|---|
| Finance Director (sponsor) | Lower bad debt, consistent control, a clean audit. |
| Maria, Credit Controller | Runs credit control day to day: reviews, stops, reminders, charges, write-offs. |
| Deputy Credit Controller | Covers for Maria with the same authority. |
| Financial Accountant | Month-end close; the ledger must agree with customer accounts. |
| Sales Manager and sales reps | Need to know which of their customers are on stop or on watch; must not be able to override it. |
| Sales office / order entry | Must be stopped from processing orders for customers on stop. |
| Customers | See their own reminders, interest and fees; receive reminder letters by email. |
| External auditors | Need a trail of credit decisions, charges and write-offs. |
| IT / system administrator | Installs and configures the change on our live system. |

## 4. Scope

### 4.1 In scope

1. Periodic credit reviews of customers, recording the outcome, notes and the next review date.
2. Putting customers "on stop" (also called "on hold" or "frozen") and taking them off stop.
3. A softer "watch" status for customers we are worried about but still supply.
4. Overdue reminder letters ("chasers", "dunning letters") in escalating stages, sent by email.
5. Interest and/or late fees on overdue balances, charged at month end.
6. Writing off bad debts.
7. A report of customers due a credit review and customers over their credit limit.
8. Sales reps seeing only their own customers' credit information.
9. Customers seeing their own reminders and charges in the customer portal.
10. Month-end agreement between the general ledger and customer accounts.
11. Working on both our existing live system and on any new installation.
12. Updating the staff guide.

### 4.2 Out of scope

- Credit insurance and external credit-reference agency feeds.
- Debt collection agencies and legal proceedings (we will continue to handle these outside the system, though we want a note of them against the customer).
- Changes to how customers pay us, or to cash allocation.
- Customer credit applications and account opening.
- Supplier (purchase ledger) side.
- Changes to price lists, discounts or sales commissions.

## 5. Business Requirements

### 5.1 Credit reviews

- **BR-01** Credit control must be able to record a credit review against any customer. A review records the date, who did it, the outcome (for example: limit confirmed, limit raised, limit reduced, put on watch, put on stop), any new credit limit, free-text notes and the next review date.
- **BR-02** Every customer on account must have a next review date. New customers get one automatically when their account is opened, based on a standard review period set by Finance (we expect 12 months, and shorter for higher-risk customers).
- **BR-03** The full history of reviews for a customer must be kept and viewable. Past reviews cannot be changed or deleted.
- **BR-04** When a review changes the credit limit, the customer's limit must update as part of the review, so the limit and the reason for it are always recorded together.

### 5.2 Stop and watch

- **BR-05** Credit control must be able to put a customer on stop, with a reason, and take them off stop, with a reason. Each change records who did it and when.
- **BR-06** While a customer is on stop, no new orders may be accepted or released for them, by any route: the sales office, the web shop, electronic orders and standing monthly orders. Goods must not be dispatched or invoiced on existing orders taken before the stop, unless credit control releases them.
- **BR-07** Only the credit controller and the deputy (and the Finance Director) may put customers on or off stop, or change credit limits. Sales reps and sales office staff must not be able to.
- **BR-08** Credit control must be able to put a customer on "watch". A customer on watch can still be supplied, but anyone taking an order for them must be clearly warned, and credit control should be able to see orders taken for watched customers.
- **BR-09** A customer's credit status (normal, watch or on stop) must be clearly visible wherever staff look at that customer or take an order for them.
- **BR-10** Orders that would take a customer over their credit limit must be held for credit control's approval rather than accepted outright. (Today reps "just put it through".)
- **BR-11** Where a customer has asked for or been told about a stop, the customer should see in the web shop that their account is on hold and should contact us, rather than having orders silently fail.

### 5.3 Reminder letters (dunning)

- **BR-12** The system must send overdue reminder letters in escalating stages. We expect three stages to start with: a polite reminder, a firmer second letter, and a final notice warning that the account will be put on stop and charges applied. Finance must be able to set the number of stages, how many days overdue triggers each stage and the wording of each letter.
- **BR-13** Reminders must go by email to the customer's accounts contact. Customers with no email address must be listed so that credit control can post the letter.
- **BR-14** Reminders are produced in a regular run (we expect weekly) started by credit control. Before sending, credit control must be able to see who will get which letter and leave out particular customers (for example, where a payment has been promised or there is a dispute).
- **BR-15** A customer should only move up a stage if they are still overdue; a customer who pays must not get the next letter. A customer must not receive the same stage twice in a short time.
- **BR-16** Every reminder sent must be recorded against the customer: the date, the stage, what invoices it covered and the amount.
- **BR-17** Reminders must be in the customer's own currency and show their overdue invoices.
- **BR-18** Credit control should be able to mark an invoice as disputed, so that it is not chased and not charged interest until the dispute is settled.

### 5.4 Interest and late fees

- **BR-19** At month end the system must be able to charge interest on overdue balances, a fixed late fee, or both. Finance must be able to set the interest rate, the fee amount and how many days overdue a balance must be before it is charged.
- **BR-20** It must be possible to exempt individual customers from interest and/or fees (for example, key accounts or those with agreed payment plans).
- **BR-21** Charges must be raised in the customer's own currency and must appear on the customer's account and their next statement as separate, clearly described items.
- **BR-22** Before charges are posted, credit control must be able to see a list of what will be charged to whom, and confirm it. The same month must not be charged twice.
- **BR-23** Interest and fees must post to the general ledger to the income accounts that Finance chooses.
- **BR-24** Credit control must be able to waive (reverse) a charge for a customer, with a reason, and the reversal must also reach the ledger.

### 5.5 Bad debt write-off

- **BR-25** Credit control must be able to write off all or part of a customer's unpaid balance as a bad debt, with a reason.
- **BR-26** Write-offs above an amount set by Finance must be approved by the Finance Director before they take effect.
- **BR-27** A write-off must reduce the customer's balance and post to the bad debt account in the general ledger, including any currency difference.
- **BR-28** When a customer has a debt written off, the customer should be put on stop automatically, unless credit control decides otherwise.
- **BR-29** There must be a report of write-offs over a period, showing customer, amount, reason, who did it and who approved it.

### 5.6 Reporting

- **BR-30** A credit control report must list customers who are due or overdue for a credit review, customers over their credit limit (and by how much), and customers on watch or on stop. It must be filterable by sales rep and by currency, and totals must be shown in our home currency.
- **BR-31** The aged debt report must show each customer's credit status, credit limit and the last reminder stage sent.
- **BR-32** All credit control actions (reviews, stop/watch changes, limit changes, reminders, charges, waivers and write-offs) must be visible as a history per customer that the auditors can inspect.

### 5.7 Sales reps

- **BR-33** Sales reps must see credit information (status, limit, balance, overdue amounts, reminders) only for their own customers, not for other reps' customers.
- **BR-34** Reps can see but not change credit status or limits.

### 5.8 Customer portal

- **BR-35** Customers who log in to the portal must be able to see the reminder letters we have sent them and the interest and fees charged to their account, along with their balance.
- **BR-36** A customer must only ever see their own account.

### 5.9 Month end and the ledger

- **BR-37** At month end the total of all customer balances must agree with the trade debtors control account in the general ledger, after interest, fees, waivers and write-offs have been posted.
- **BR-38** If they do not agree, Finance must be able to find out why from the system.

### 5.10 Installation and rollout

- **BR-39** The capability must work on our existing live system, with all our existing customers, balances and history, as well as on a brand-new installation.
- **BR-40** On go-live every existing customer starts as "normal", with a next review date set by Finance, unless credit control loads their current status from the spreadsheet. Existing customers who are on the spreadsheet stop list today must be on stop in the system from day one.
- **BR-41** Nothing in the new capability should change how existing invoices, statements or postings behave for customers who are not overdue.

### 5.11 Documentation and training

- **BR-42** The staff guide must be updated to explain credit reviews, stop and watch, the reminder run, month-end charges, write-offs and the credit control report.
- **BR-43** Sales staff need a short note on what "watch" and "stop" mean for them and who to contact.

## 6. User Stories

1. **As Maria (credit controller)**, I want to see every Monday which customers are due a review or over their limit, so that I can work through them in order and nothing slips.
2. **As Maria**, I want to put a customer on stop once, and know that the sales office, the web shop, EDI orders and the standing orders are all blocked, so that I don't have to phone round.
3. **As the deputy credit controller**, I want the same powers and the same history as Maria, so that I can cover her holidays without asking her what she agreed with whom.
4. **As a sales rep**, I want to see when one of my customers is on watch or on stop, and why, so that I can talk to the customer before they place an order.
5. **As Maria**, I want the weekly reminder run to email the right letter at the right stage to each overdue customer, after I've had a chance to take out the ones I'm already talking to.
6. **As the Financial Accountant**, I want month-end interest and fees to post themselves to the ledger, so that the debtors control account agrees with the customer balances without manual journals.
7. **As the Finance Director**, I want to approve large write-offs before they go through, so that I know what bad debt we are taking.
8. **As a customer**, I want to see in the portal the reminders and charges on my account, so that I understand what I owe and why.
9. **As the external auditor**, I want to see for any customer who changed their credit limit or status, when and why, so that I can test the credit control process.

## 7. Acceptance Criteria (business terms)

- **AC-01** Maria records a review on a customer, raising their limit and setting next review in six months. The new limit applies straight away, and the review, with her notes, appears in the customer's history. The customer drops off the "due for review" list and reappears when the next date comes round.
- **AC-02** A customer is put on stop. An order for them cannot be completed in the sales office, through the web shop, electronically or from their standing order. When they are taken off stop, orders go through again. Both changes appear in their history with reasons.
- **AC-03** A sales rep tries to take a customer off stop or raise a limit and cannot.
- **AC-04** A customer on watch places an order: it is accepted, the person taking it sees a warning, and the order shows on credit control's list.
- **AC-05** An order that would take a customer over their limit is held and only released when credit control approves it.
- **AC-06** In the reminder run, a customer 35 days overdue gets the first letter by email; the next run, if still unpaid and past the second threshold, they get the second letter; if they pay in between, they get nothing. A customer marked disputed gets no letter. Every letter sent shows on the customer's account history and in their portal.
- **AC-07** At month end, an overdue customer is charged interest at the set rate and the set late fee in their own currency; an exempt customer is not charged; running the charges again for the same month charges nobody twice. The charges appear on the customer's statement and in the portal.
- **AC-08** After month-end charges, waivers and write-offs, the total of customer balances equals the debtors control account in the general ledger.
- **AC-09** A write-off below the approval amount reduces the customer's balance and appears in the bad debt account; one above it does nothing until the Finance Director approves it. The customer is put on stop.
- **AC-10** Rep A sees credit details for her customers and none for Rep B's customers. Customer X in the portal sees only Customer X's reminders and charges.
- **AC-11** After go-live on the live system, all existing customers, balances and history are intact, every customer has a next review date, and everyone on the old spreadsheet stop list is on stop.
- **AC-12** The updated staff guide covers every item in section 4.1 and has been read and agreed by Maria and the Sales Manager.

## 8. Assumptions

- Customers' accounts contact email addresses are mostly up to date; credit control will clean up the rest before go-live.
- Each customer already has a single sales rep assigned.
- Our terms and conditions allow us to charge interest and late fees; Legal will confirm the wording for letters.
- Credit control will provide the current stop list and credit limits from the spreadsheet for go-live.

## 9. Open Questions

1. Interest: a simple annual rate on overdue balances, or a statutory late-payment rate? Does it differ by currency or country?
2. Late fee: one flat fee per month, or a fee per overdue invoice? Should it vary by currency?
3. Do we charge interest on interest and fees that are themselves overdue?
4. Should a customer be put on stop automatically after the final reminder, or only flagged for Maria to decide?
5. How should over-limit orders from the web shop and standing orders be handled: held for approval, or rejected with a message to the customer?
6. What is the approval threshold for write-offs, and does the Financial Accountant also need to sign off?
7. If a written-off debt is later paid, how do we want it shown?
8. Should reps be told the reason for a stop, or only that the customer is on stop?
9. Do we need the reminder letters in languages other than English for overseas customers?
10. Should customers be able to see "watch" status in the portal? (Our view: no.)
11. Who covers credit decisions when both Maria and her deputy are away?
12. Do head-office/branch customer groups share one credit limit, or does each branch have its own?
