-- What an insights pass found, and how a pass shows in a brief's history.
--
-- A pass stores each finding it made (`insights_findings`): the statement, the
-- evidence it read (file, lines, version), its confidence, where the brief
-- states it or should, and the hypotheses it checked and dropped (kept on the
-- pass). `skipped` is empty when the brief was extended; otherwise it says why
-- not ('pinned': the brief is a person's and is never overwritten, 'no
-- findings', or why the extend call gave no brief), and the findings stay.
ALTER TABLE insights_passes ADD COLUMN skipped TEXT NOT NULL DEFAULT '';
ALTER TABLE insights_passes ADD COLUMN dropped TEXT NOT NULL DEFAULT '[]';
ALTER TABLE insights_passes ADD COLUMN looked TEXT NOT NULL DEFAULT '';

CREATE TABLE insights_findings (
    id         INTEGER PRIMARY KEY,
    pass_id    INTEGER NOT NULL REFERENCES insights_passes(id)
               ON DELETE CASCADE,
    position   INTEGER NOT NULL,
    statement  TEXT NOT NULL,
    angle      TEXT NOT NULL DEFAULT '',
    why        TEXT NOT NULL DEFAULT '',
    evidence   TEXT NOT NULL DEFAULT '[]',  -- JSON: [{file, lines, version}]
    placement  TEXT NOT NULL DEFAULT '',
    confidence TEXT NOT NULL DEFAULT ''
);
CREATE INDEX insights_findings_pass ON insights_findings (pass_id, position);

-- A brief an insights pass replaced is kept like any other replaced brief,
-- with the reason 'insights' and the pass that replaced it (its model and
-- time are on the pass row). SQLite cannot widen a CHECK, so the table is
-- rebuilt.
CREATE TABLE brief_versions_new (
    id          INTEGER PRIMARY KEY,
    node_id     INTEGER NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    text        TEXT NOT NULL,
    model_name  TEXT NOT NULL,
    written_at  TEXT NOT NULL,
    replaced_at TEXT NOT NULL,
    reason      TEXT NOT NULL
                CHECK (reason IN ('regen', 'rewrite', 'insights')),
    prompt_name TEXT NOT NULL DEFAULT '',
    prompt_hash TEXT NOT NULL DEFAULT '',
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    member_signature TEXT NOT NULL DEFAULT '',
    members     TEXT NOT NULL DEFAULT '[]',
    source_model TEXT NOT NULL DEFAULT '',
    model_fingerprint TEXT,
    unfaithful  TEXT NOT NULL DEFAULT '[]',
    flagged     TEXT NOT NULL DEFAULT '',
    pass_id     INTEGER REFERENCES insights_passes(id) ON DELETE SET NULL
);
INSERT INTO brief_versions_new (
    id, node_id, text, model_name, written_at, replaced_at, reason,
    prompt_name, prompt_hash, input_tokens, output_tokens, member_signature,
    members, source_model, model_fingerprint, unfaithful, flagged
) SELECT
    id, node_id, text, model_name, written_at, replaced_at, reason,
    prompt_name, prompt_hash, input_tokens, output_tokens, member_signature,
    members, source_model, model_fingerprint, unfaithful, flagged
FROM brief_versions;
DROP TABLE brief_versions;
ALTER TABLE brief_versions_new RENAME TO brief_versions;
CREATE INDEX brief_versions_node ON brief_versions(node_id, id);
