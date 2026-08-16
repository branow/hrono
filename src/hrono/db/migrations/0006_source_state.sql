CREATE TABLE source_state (
    source     TEXT PRIMARY KEY,
    version    TEXT NOT NULL,
    synced_at  TEXT NOT NULL
);
