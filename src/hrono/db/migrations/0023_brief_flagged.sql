-- The brief shape flag. A reply that is not a summary at all — a question back
-- to the caller, an assistant refusal — passes the faithfulness gate, because
-- the gate only asks whether claims are supported, and a non-answer invents
-- nothing. The op retries once and, if the second reply is no better, stores it
-- WITH the reason here: a flagged brief an operator can find and regenerate
-- beats a topic missing from the map. Empty means the reply looked like a
-- brief.
ALTER TABLE briefs ADD COLUMN flagged TEXT NOT NULL DEFAULT '';
