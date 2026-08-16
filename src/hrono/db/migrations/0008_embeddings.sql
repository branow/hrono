-- Vectors for stored content, keyed by (content_hash, model_name) so a body is
-- embedded exactly once per model and a model swap re-embeds under a new key
-- without disturbing the old. The vector is a float32 blob (sqlite-vec's native
-- element format, queryable by its distance functions); dims travel with the row
-- so models of different dimensionality coexist.

CREATE TABLE embeddings (
    content_hash TEXT NOT NULL REFERENCES contents(content_hash),
    model_name   TEXT NOT NULL,
    dims         INTEGER NOT NULL,
    vector       BLOB NOT NULL,
    created_at   TEXT NOT NULL,
    PRIMARY KEY (content_hash, model_name)
);

CREATE INDEX embeddings_model ON embeddings(model_name);
