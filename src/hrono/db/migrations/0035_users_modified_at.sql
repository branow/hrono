-- #042: `users` recorded when a row was created and nothing about when it was
-- last touched, so `admin reset-token` rotated a credential and left no trace.
-- The audit an operator actually does with this table -- "is anyone still
-- carrying a token nobody has rotated?" -- had no column to read.
--
-- Backfilled to `created_at`: a row nobody has touched was last modified when
-- it was made. NOT NULL with no default, because a default would let a future
-- insert forget to stamp it and read as "created just now" for ever.
ALTER TABLE users ADD COLUMN modified_at TEXT;
UPDATE users SET modified_at = created_at WHERE modified_at IS NULL;
