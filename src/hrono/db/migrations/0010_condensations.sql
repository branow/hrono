-- Per-section condensations (the T20 map stage), keyed by (content_hash,
-- model_name) so a section is condensed exactly once per model and an unchanged
-- section is never re-condensed — the content-addressed cache that makes brief
-- rebuilds incremental, mirroring the embeddings table. Token usage travels with
-- the row for cost/provenance (T21). Content-only, no secret.

CREATE TABLE condensations (
    content_hash  TEXT NOT NULL REFERENCES contents(content_hash),
    model_name    TEXT NOT NULL,
    text          TEXT NOT NULL,
    input_tokens  INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    created_at    TEXT NOT NULL,
    PRIMARY KEY (content_hash, model_name)
);

CREATE INDEX condensations_model ON condensations (model_name);
