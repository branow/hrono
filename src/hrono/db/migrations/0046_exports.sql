-- The export the panel shows, built when someone asks for it and kept.
-- Producing one renders every file in the tree, which takes seconds to
-- minutes on a large tree, so a job builds it and the page only reads it.
-- One per tree: the latest build replaces the one before.
CREATE TABLE exports (
    tree TEXT PRIMARY KEY,
    levels INTEGER NOT NULL,
    built_at TEXT NOT NULL,
    meta TEXT NOT NULL,
    archive BLOB NOT NULL
);
