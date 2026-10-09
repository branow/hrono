-- The incremental update-batch counter. Each `update` run over a
-- tree bumps this monotonically; the number stamps chunks parked in the
-- incubator so aging can force-assign a chunk that has waited too many
-- batches. One row per tree.
CREATE TABLE tree_batch (
    tree  TEXT PRIMARY KEY,
    batch INTEGER NOT NULL
);
