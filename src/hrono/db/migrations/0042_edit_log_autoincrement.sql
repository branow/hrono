-- An edit_log id is never reused. Without AUTOINCREMENT, SQLite hands out
-- max(id) + 1, so once an undo empties the log the next edit takes the id a
-- stale tab still holds, and that tab's Undo would undo a different edit.
CREATE TABLE edit_log_new (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    node_id INTEGER NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    kind    TEXT NOT NULL CHECK (kind IN ('rename', 'brief', 'note')),
    before  TEXT,
    ref     INTEGER,
    who     TEXT NOT NULL,
    made_at TEXT NOT NULL
);
INSERT INTO edit_log_new(id, node_id, kind, before, ref, who, made_at)
    SELECT id, node_id, kind, before, ref, who, made_at FROM edit_log;
DROP TABLE edit_log;
ALTER TABLE edit_log_new RENAME TO edit_log;
CREATE INDEX edit_log_node ON edit_log(node_id, id);
