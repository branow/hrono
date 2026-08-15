CREATE TABLE registry (
    collection TEXT NOT NULL,
    name       TEXT NOT NULL,
    config     TEXT NOT NULL,
    key_id     INTEGER REFERENCES keys (key_id),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (collection, name)
);
