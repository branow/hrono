# Business requirements: Demand Forecasting

## Purpose

Planners need statistical demand forecasts per stock item to drive
inventory planning, production scheduling and MRP. webERP has MRP and a
manual master schedule (MRP demands) but no way to forecast demand from
sales history. This project adds a Forecasting module.

## Users and access

- A new main-menu module, "Forecasting", next to Manufacturing. Users who
  are allowed it see it; an administrator grants or removes it per user the
  same way as the other modules.
- Existing users must keep exactly the modules they have today after the
  upgrade; whether they also get Forecasting is the administrator's choice.
- Every new page is protected by page security like the rest of webERP
  (inventory/manufacturing level), appears in the menu of the roles that
  may use it, and is available both on new installations and on existing
  databases after the upgrade.
- All user-visible text is translatable.

## Functions

### 1. Sales history

- Extract the company's actual sales of each item, net of credits/returns,
  into monthly buckets per item and per stock location, for a date range
  the user chooses (24 months recommended). Re-running a range replaces
  that range, it does not double it.
- The history used for forecasting must be the same sales the rest of
  webERP reports (invoiced quantities, credits deducted), not open orders.
- Show the date range and number of items/months held.

### 2. Forecast generation

- Scope: a single item (optionally one location, or all locations
  combined), or every active item of a stock category in one operation,
  with a result summary such as "47 successful, 3 failed" and the reason
  for each failure.
- Horizon: the number of future monthly periods (typically 6-12).
- Methods (the user picks one, or asks the system for the best fit):
  1. Percent over last year: last year x (1 + p/100). Min history 12 months.
  2. Calculated percent over last year: growth computed from the last two
     years. Min 24 months.
  3. Last year to this year: same month last year. Min 12 months.
  4. Moving average of the last N periods. Min 4 months.
  5. Linear approximation through two historical points. Min 6 months.
  6. Least squares regression over all history. Min 12 months.
  7. Second degree (quadratic) regression. Min 12 months.
  8. Flexible method: user weights per prior period. Min 12 months.
  9. Weighted moving average (e.g. 40/30/20/10). Min 4 months.
  10. Simple exponential smoothing, alpha 0.1-0.9. Min 12 months.
  11. Holt's double exponential smoothing (alpha, beta). Min 12 months.
  12. Holt-Winters (alpha, beta, gamma, season length 12). Min 24 months.
- An item with less history than a method needs is reported, not
  forecast with made-up data. No negative forecast quantities.
- Best fit: hold out the most recent months, forecast them with each
  applicable method, and recommend the method with the best accuracy;
  for a category, recommend the method that does best across its items.
- One forecast per item and location is the active one (used by MRP);
  generating again replaces or supersedes it, keeping the method and
  parameters used.
- Batch generation for large categories, with progress and a result list.

### 3. Review and revision

- Search forecasts by item, category or location and show period by period
  the calculated quantity, a revised quantity the planner may enter, last
  year's actual for the same month, and the variance (highlighted when
  large).
- A revised quantity always takes priority over the calculated one,
  everywhere it is used (reports, accuracy, MRP). Clearing it restores the
  calculated quantity.

### 4. Summary forecasts

- Aggregated forecasts by stock category, customer type, sales area or
  salesperson, built from the same history, with a review screen of the
  detail behind each summary.

### 5. Accuracy

- Compare past forecasts with the actual sales that followed: MAD, POA
  (percent of accuracy), MSE and RMSE per item, per category and per
  method, for a chosen range. Flag items with low accuracy.
- A method comparison screen: one item's history forecast with several
  methods side by side with their accuracy.

### 6. Parameters

- Company-wide defaults (smoothing constants alpha, beta, gamma, season
  length, moving-average periods, hold-out months, default horizon),
  editable by an administrator and used when the user does not override
  them.

### 7. MRP integration

- Convert active forecasts (revised quantity first) into MRP demands under
  a dedicated demand type for forecasts, which exists after the upgrade,
  for a chosen date horizon, so that the existing MRP run plans purchases
  and work orders from them.
- Replace mode removes the forecast demands of the same items and horizon
  before writing new ones; incremental mode adds only periods not yet
  present. Converting twice must never double the demand. Demands entered
  by hand or from other sources are never touched.
- The Forecasting menu also links the existing MRP master schedule, MRP run
  and MRP report.

### 8. Dashboard and inquiry

- A dashboard: number of active forecasts and summary forecasts, the sales
  history range, and links to every function.
- An inquiry screen to view forecasts by item, category, location and
  period.

## Out of scope

Email or cron automation, promotional events, pricing/value forecasts and
what-if simulation.
