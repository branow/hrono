-- A job's failure must carry a CODE, not the driver's wording (#109).
--
-- Every other surface answers in `{error: {code, message, details}}`; a job
-- recorded `str(exc)` and nothing else, so a client had a sentence to regex and
-- no field to branch on. Reproduced during #092's verification: a trigger
-- raising `RAISE(ABORT, 'poisoned mid-transaction')` inside `split` stored
-- exactly that — sqlite's phrasing, in the API's mouth.
--
-- Two columns rather than a JSON blob, to match `result` (#132) and the HTTP
-- envelope field for field: `error` stays the message so nothing reading it
-- breaks, `error_code` is the kebab-case code, `error_details` the JSON object.
ALTER TABLE jobs ADD COLUMN error_code TEXT;
ALTER TABLE jobs ADD COLUMN error_details TEXT;
