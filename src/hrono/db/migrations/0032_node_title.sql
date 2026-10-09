-- A topic a human renamed keeps that name.
--
-- A node had no title: the export derives one from its brief's first real
-- line. That is right by default and wrong the moment an operator disagrees —
-- the next brief regeneration would re-derive the name they just replaced.
-- A stored title is preferred when set, and a rename pins the brief so the
-- line it was derived from cannot move underneath it.
ALTER TABLE nodes ADD COLUMN title TEXT;
