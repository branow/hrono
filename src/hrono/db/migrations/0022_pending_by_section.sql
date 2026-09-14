-- Re-key the incubator pool from CONTENT HASH to SECTION (#095). Membership is
-- per section (`node_members.section_id`), so a hash-keyed pool is coarser than
-- the thing it is the complement of: two sections with identical bodies at
-- different paths share one content hash but get DIFFERENT combined vectors
-- (the #039 path blend, ALPHA 0.5), so one can clear TAU and join a cluster
-- while its twin parks. One row then cannot represent them -- it claims both
-- are homeless, is retired when either is homed (stranding the twin in no node
-- AND no pool), and force-assigns both when either ages out (putting the homed
-- twin in a second node). Keyed by section, the pool is exactly as granular as
-- membership and the invariant holds per chunk. `path` and `content_hash` are
-- read from `sections` instead of being copied, and a deleted section takes its
-- pool row with it.
CREATE TABLE pending_by_section (
    tree       TEXT NOT NULL,
    section_id INTEGER NOT NULL REFERENCES sections(id) ON DELETE CASCADE,
    batch      INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (tree, section_id)
);

-- Carry the existing pool across, dropping rows for sections a build has since
-- homed: those are the "clustered AND pending" half of the invariant, and the
-- hash key is why they survived.
INSERT INTO pending_by_section(tree, section_id, batch, created_at)
SELECT p.tree, s.id, p.batch, p.created_at
FROM pending p
JOIN sections s
  ON s.content_hash = p.content_hash AND s.path = p.path
WHERE NOT EXISTS (
    SELECT 1 FROM node_members m JOIN nodes n ON n.id = m.node_id
    WHERE m.section_id = s.id AND n.tree = p.tree AND n.level = 0
);

DROP TABLE pending;

ALTER TABLE pending_by_section RENAME TO pending;
