-- Every API recall leaves a row, so an admin can see whether agents use
-- the tree and what they ask. The panel's Ask page does not write here: it is
-- a curator, not an agent. `confident` is 0 when recall refused (no hit
-- cleared the floor); `top_score` is the best hit's score, NULL on a refusal.
-- The newest rows per tree are kept (hrono.recall.log.KEEP); nothing else in
-- the database is touched.
CREATE TABLE recall_log (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    tree      TEXT NOT NULL,
    user      TEXT NOT NULL,
    question  TEXT NOT NULL,
    hits      INTEGER NOT NULL,
    top_score REAL,
    confident INTEGER NOT NULL CHECK (confident IN (0, 1)),
    asked_at  TEXT NOT NULL
);

CREATE INDEX recall_log_tree ON recall_log (tree, id);
