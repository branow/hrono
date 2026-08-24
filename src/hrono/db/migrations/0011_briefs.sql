-- One brief per node (the T21 reduce stage): the LLM-written summary of a
-- topic, plus the provenance freshness (#064) and the cost API read back — the
-- model that wrote it, the prompt by name and template hash, and token usage.
-- Member reference URIs are baked into `text` mechanically by the op, never by
-- the LLM. Keyed by node so a rebuilt node replaces its brief.

CREATE TABLE briefs (
    node_id       INTEGER PRIMARY KEY REFERENCES nodes(id) ON DELETE CASCADE,
    text          TEXT NOT NULL,
    model_name    TEXT NOT NULL,
    prompt_name   TEXT NOT NULL,
    prompt_hash   TEXT NOT NULL,
    input_tokens  INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    created_at    TEXT NOT NULL
);
