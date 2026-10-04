-- E034: a manual edit on a topic records what it replaced, so one click can
-- put it back. `before` is the old title or the old brief text (NULL when
-- there was none); for a note it is NULL and `ref` is the note's id, which an
-- undo deletes. `who` is the user who made the edit. An undo clears the
-- topic's rows, so it is one step deep and a second undo finds nothing.
CREATE TABLE edit_log (
    id      INTEGER PRIMARY KEY,
    node_id INTEGER NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    kind    TEXT NOT NULL CHECK (kind IN ('rename', 'brief', 'note')),
    before  TEXT,
    ref     INTEGER,
    who     TEXT NOT NULL,
    made_at TEXT NOT NULL
);
CREATE INDEX edit_log_node ON edit_log(node_id, id);
