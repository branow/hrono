CREATE TABLE users (
    name       TEXT PRIMARY KEY,
    role       TEXT NOT NULL CHECK (role IN ('reader', 'writer', 'admin')),
    token_hash TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL
);
