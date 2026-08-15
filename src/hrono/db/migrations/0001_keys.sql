CREATE TABLE keys (
    key_id     INTEGER PRIMARY KEY,
    key_hash   TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL
);
