-- The log keeps every edit, so a topic page can say who made each one.
-- `closed` marks the newest row once an undo or a hand-back has used it
-- ('undone' | 'released'); NULL is an edit nobody has closed. Only the newest
-- row is ever offered for undo, and only while it is open.
ALTER TABLE edit_log ADD COLUMN closed TEXT
    CHECK (closed IN ('undone', 'released'));
