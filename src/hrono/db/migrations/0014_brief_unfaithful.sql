-- The mechanical faithfulness gate's verdict per brief: a JSON array of
-- identifier tokens the brief used that have no literal support in its source.
-- Empty '[]' = faithful. A brief is FLAGGED, not blocked — a single fabricated
-- token should not fail a whole build — so this is surfaced in tree health, not
-- a hard failure. Defaulted so briefs written before the gate read as faithful.

ALTER TABLE briefs ADD COLUMN unfaithful TEXT NOT NULL DEFAULT '[]';
