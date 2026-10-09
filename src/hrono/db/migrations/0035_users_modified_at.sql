-- `users` records when a row was created; without this nothing says when it
-- was last touched, and `admin reset-token` would rotate a credential and
-- leave no trace. The audit an operator actually does with this table -- "is
-- anyone still carrying a token nobody has rotated?" -- needs this column.
--
-- Backfilled to `created_at`: a row nobody has touched was last modified when
-- it was made. NOT NULL with no default, because a default would let a future
-- insert forget to stamp it and read as "created just now" for ever.
ALTER TABLE users ADD COLUMN modified_at TEXT;
UPDATE users SET modified_at = created_at WHERE modified_at IS NULL;
