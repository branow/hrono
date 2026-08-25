-- The pending pool / incubator (#086, T35). A chunk that fits no existing
-- cluster (< TAU on the #085 placement rule) parks here BY CONTENT HASH until
-- enough siblings arrive to form a real cluster, rather than being force-married
-- to strangers. `batch` is the update-batch counter at park time, for aging
-- (force-assign after too many batches). Invariant: every chunk is in exactly
-- one cluster OR pending here, never both, never neither.
CREATE TABLE pending (
    tree         TEXT NOT NULL,
    content_hash TEXT NOT NULL REFERENCES contents(content_hash),
    path         TEXT NOT NULL,
    batch        INTEGER NOT NULL,
    created_at   TEXT NOT NULL,
    PRIMARY KEY (tree, content_hash)
);

-- A member force-assigned to a cluster ignoring TAU (residual after a drain, or
-- an aged-out pending chunk): flagged so the misfit monitor (T37) re-checks it
-- preferentially and a mis-placed pioneer migrates once its real siblings form.
ALTER TABLE node_members ADD COLUMN forced INTEGER NOT NULL DEFAULT 0;
