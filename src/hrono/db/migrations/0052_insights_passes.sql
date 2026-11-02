-- One row per insights pass: a strong model reviewed a topic's subtree and
-- its brief was extended with what it found (`summarize/insights.py`). The
-- count of unreviewed brief characters under a topic is derived from these
-- rows and the briefs' write times, never stored, so it cannot drift on a
-- hand edit, a revert or an undo. A pass row is written AFTER the extended
-- brief, so the brief it left is not counted as unreviewed.
CREATE TABLE insights_passes (
    id         INTEGER PRIMARY KEY,
    node_id    INTEGER NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    passed_at  TEXT NOT NULL,
    model_name TEXT NOT NULL,
    version    TEXT NOT NULL  -- the node's member signature the pass covered
);

CREATE INDEX insights_passes_node ON insights_passes (node_id, passed_at);
