-- What a leaf brief's writer looked up (`summarize/lookup.py`): every tool
-- call it made and its own account of each connection, found or not. Kept
-- with the brief so a run can be audited - which connections were searched,
-- which given up on - without paying for the calls again. Empty for a brief
-- written without lookups.
ALTER TABLE briefs ADD COLUMN lookups TEXT NOT NULL DEFAULT '';
