<!-- leaf 466, 9 members -->

These condensations describe a set of Apache 2.0 licensed SQLAlchemy models with Marshmallow schemas, apparently from a Province of British Columbia payments codebase. Almost all are lookup ("code table") models, and they share one pattern. The exception is `StatementInvoices`, which is a relation table.

**Shared pattern for the status-code tables**
- Each model extends `db.Model`, and most also extend `CodeTable`. It has two columns: `code` (String, primary key) and `description` (String 200, not null).
- Each sets `__mapper_args__` with `include_properties=['code', 'description']`. This is explicit field mapping meant to tolerate version skew during rolling upgrades, failed deploys and Alembic upgrades.
- Each has a paired `ma.SQLAlchemyAutoSchema` named `<Model>Schema`, with `Meta.model` set and `load_instance = True`.

**Variations within the status-code group**

| Model | Table | `code` length |
|---|---|---|
| `CfsAccountStatusCode` | `cfs_account_status_codes` | 40 |
| `DisbursementStatusCode` | not stated | 20 |
| `InvoiceReferenceStatusCode` | `invoice_reference_status_codes` | 20 |
| `InvoiceStatusCode` | `invoice_status_codes` | 20 |
| `LineItemStatusCode` | `line_item_status_codes` | 20 |
| `NotificationStatusCode` | `notification_status_codes` | 20 |
| `PaymentStatusCode` | `payment_status_codes` | 20 |
| `TransactionStatusCode` | `transaction_status_codes` | 20 |

- `CfsAccountStatusCode` is the only one with a 40-character `code`.
- The `DisbursementStatusCode` and `NotificationStatusCode` summaries don't name the schema class or the `CodeTable` base. The notification table is described as having an explicit mapper and a schema that auto-serializes to JSON.

**Relation table: `StatementInvoices`**
- It maps statements to invoices (one-to-many) in the table `statement_invoices`.
- Its columns are `id` (PK, autoincrement), `statement_id` (FK to `statements.id`, not null, indexed) and `invoice_id` (FK to `invoices.id`, not null, indexed).
- Its `include_properties` list is `['id', 'invoice_id', 'statement_id']`, kept in alphabetical order.
- The class method `find_all_invoices_for_statement(statement_identifier: str)` queries by `statement_id`.
- `StatementInvoicesSchema` is an auto schema with `load_instance=True`.

**Caution:**
- `include_properties` is not a security filter. It only hides unmapped columns from SQLAlchemy, and unmapped fields are silently ignored rather than validated.
- Adding a column to a model requires updating `__mapper_args__`, or the rolling deploy will fail.
- The explicit mapper is required for production rolling upgrades. Removing it can cause crashes when the schema and database don't align.
- `CodeTable` inheritance adds undocumented behavior.
- The `NotificationStatusCode` summary says the primary key `id` is implicitly excluded by `__mapper_args__` even though it is on the class. That could cause mapping problems if `id` is referenced elsewhere. This conflicts with the other summaries, which give `code` as the primary key, so check the source.
- The `TransactionStatusCode` summary lists `id` first in mapper ordering, which is also inconsistent with `code` being the primary key.
- In `StatementInvoices.find_all_invoices_for_statement`, the parameter is named `statement_identifier` but the query filters on `statement_id`. The naming is confusing.

## Members

- sbc-pay: pay-api/src/pay_api/models/cfs_account_status_code.py
- sbc-pay: pay-api/src/pay_api/models/disbursement_status_code.py
- sbc-pay: pay-api/src/pay_api/models/invoice_reference_status_code.py
- sbc-pay: pay-api/src/pay_api/models/invoice_status_code.py
- sbc-pay: pay-api/src/pay_api/models/line_item_status_code.py
- sbc-pay: pay-api/src/pay_api/models/notification_status_code.py
- sbc-pay: pay-api/src/pay_api/models/payment_status_code.py
- sbc-pay: pay-api/src/pay_api/models/statement_invoices.py
- sbc-pay: pay-api/src/pay_api/models/transaction_status_code.py
