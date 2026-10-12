-- The change journal: every row a run inserted, updated or deleted in the
-- tables that make up a tree, with the row as it was before. It is what makes
-- a run revertible and what says which topics a sync touched. The triggers
-- that write it are generated from the schema on every open
-- (`db/journal.py`), so a column or table added later is journaled without
-- anyone remembering to.
CREATE TABLE changes (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    run        TEXT NOT NULL,
    tbl        TEXT NOT NULL,
    op         TEXT NOT NULL CHECK (op IN ('insert', 'update', 'delete')),
    row        INTEGER NOT NULL,
    before     TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX changes_run ON changes (run, id);

-- A run that was reverted. Its journal stays, as history.
CREATE TABLE reverts (
    run         TEXT PRIMARY KEY,
    reverted_at TEXT NOT NULL,
    reverted_by TEXT
);
