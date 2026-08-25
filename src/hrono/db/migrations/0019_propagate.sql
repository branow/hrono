-- The propagate judge cascade (#087, T36). A changed leaf brief must mark its
-- ancestors stale even though #068's upper signature (child node ids) is
-- unchanged by a sticky-placed leaf. `briefs.stale` is that explicit mark: set
-- by propagate, checked by #064's freshness, cleared when the brief regenerates
-- (INSERT OR REPLACE resets it to the default). `tree_batch.drift` accumulates
-- the climb magnitude (minor/major) that feeds the settle trigger (T39).
ALTER TABLE briefs ADD COLUMN stale INTEGER NOT NULL DEFAULT 0;

ALTER TABLE tree_batch ADD COLUMN drift INTEGER NOT NULL DEFAULT 0;

-- The audit trail the dashboard reads: one row per judged topic recording its
-- verdict (none/minor/major) and whether the cascade propagated or stopped.
CREATE TABLE update_log (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    tree       TEXT NOT NULL,
    node_id    INTEGER NOT NULL,
    verdict    TEXT NOT NULL,
    action     TEXT NOT NULL,
    climbed_to INTEGER,
    created_at TEXT NOT NULL
);
