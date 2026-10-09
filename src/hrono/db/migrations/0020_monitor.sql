-- The misfit health signal that repair and settle read.
-- A chunk is a MISFIT when some other cluster's centroid is nearer than its own;
-- `misfit` stores the per-cluster count so a batch re-checks only its dirty
-- clusters (plus a bounded sample) and the global rate aggregates stored rows
-- without rescanning the corpus. `tree_batch.baseline` is the post-build global
-- rate the triggers compare against (a fresh tree's rate is nonzero by nature).
ALTER TABLE tree_batch ADD COLUMN baseline REAL;

CREATE TABLE misfit (
    tree       TEXT NOT NULL,
    node_id    INTEGER NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    misfits    INTEGER NOT NULL,
    members    INTEGER NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (tree, node_id)
);
