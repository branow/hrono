CREATE TABLE jobs (
    id         TEXT PRIMARY KEY,
    parent_id  TEXT,
    tree       TEXT,
    op         TEXT NOT NULL,
    scope      TEXT NOT NULL,
    status     TEXT NOT NULL CHECK (
        status IN ('pending', 'running', 'succeeded', 'failed', 'canceled')
    ),
    error      TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX jobs_status ON jobs (status);
CREATE INDEX jobs_parent_id ON jobs (parent_id);
