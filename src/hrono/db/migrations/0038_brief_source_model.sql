-- E019: a brief is gated against the condensations of the model its job's
-- scope named, and read back later with no job in sight. `source_model` is
-- that condense model, recorded with the brief, so the read-time material is
-- exactly what the brief was written from.
--
-- '' is a brief that recorded none (written before this column, by hand, or
-- from child briefs); it reads the install's own condense model, as before.
ALTER TABLE briefs ADD COLUMN source_model TEXT NOT NULL DEFAULT '';
