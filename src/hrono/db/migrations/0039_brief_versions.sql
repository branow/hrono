-- A brief overwritten, by a regeneration or by hand, is not lost.
--
-- `briefs` holds one row per topic, so every write replaces the text before it;
-- for a bad rewrite to be noticed and copied back, `briefs.upsert`
-- copies the text it replaces here, with who wrote that text (`model_name`,
-- 'hand-edited' for a person), when it was written, when it was replaced, and
-- why (`reason`: 'regen' or 'rewrite'). Only the newest few are kept per
-- topic; `briefs.KEEP_VERSIONS` is the constant.
CREATE TABLE brief_versions (
    id          INTEGER PRIMARY KEY,
    node_id     INTEGER NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    text        TEXT NOT NULL,
    model_name  TEXT NOT NULL,
    written_at  TEXT NOT NULL,
    replaced_at TEXT NOT NULL,
    reason      TEXT NOT NULL CHECK (reason IN ('regen', 'rewrite'))
);
CREATE INDEX brief_versions_node ON brief_versions(node_id, id);
