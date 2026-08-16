-- Ingested content: bodies stored once by content hash, addressed as sections
-- (clustering/traversal unit) each nesting its passages (recall unit). A
-- section's body equals the concatenation of its passages' bodies, byte for
-- byte; position (byte range, ordinal) is data, never part of the URI.

CREATE TABLE contents (
    content_hash TEXT PRIMARY KEY,
    body         BLOB NOT NULL,
    byte_len     INTEGER NOT NULL,
    created_at   TEXT NOT NULL
);

CREATE TABLE sections (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    source       TEXT NOT NULL,
    source_type  TEXT NOT NULL,
    instance     TEXT NOT NULL,
    path         TEXT NOT NULL,
    version      TEXT NOT NULL,
    uri          TEXT NOT NULL,
    byte_start   INTEGER NOT NULL,
    byte_end     INTEGER NOT NULL,
    content_hash TEXT NOT NULL REFERENCES contents(content_hash),
    ordinal      INTEGER NOT NULL,
    created_at   TEXT NOT NULL
);

CREATE INDEX sections_source ON sections(source);
CREATE INDEX sections_uri ON sections(uri);

CREATE TABLE passages (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    section_id   INTEGER NOT NULL REFERENCES sections(id) ON DELETE CASCADE,
    source       TEXT NOT NULL,
    source_type  TEXT NOT NULL,
    instance     TEXT NOT NULL,
    path         TEXT NOT NULL,
    version      TEXT NOT NULL,
    uri          TEXT NOT NULL,
    byte_start   INTEGER NOT NULL,
    byte_end     INTEGER NOT NULL,
    content_hash TEXT NOT NULL REFERENCES contents(content_hash),
    sp_paths     TEXT NOT NULL,
    ordinal      INTEGER NOT NULL,
    created_at   TEXT NOT NULL
);

CREATE INDEX passages_section ON passages(section_id);
