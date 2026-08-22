-- Bottom-level topics (nodes) built by the `cluster` op: groups of related
-- sections that the brief step (M4) summarises and the tree is built from. A
-- node belongs to a named tree (the topic hierarchy over a corpus) at a level
-- (0 = leaf, sections); upper levels (M4) reuse the same table. `label` is the
-- HDBSCAN cluster label within the build, kept for traceability.

CREATE TABLE nodes (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    tree       TEXT NOT NULL,
    level      INTEGER NOT NULL,
    label      INTEGER NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX nodes_tree ON nodes (tree, level);

-- Which sections belong to which node, one row per section. `attached` = the
-- section was HDBSCAN noise and was attached by proximity to its nearest
-- cluster in the ORIGINAL combined space (1) vs a density-core member (0);
-- `assignment_similarity` is that combined-space similarity, non-null only for
-- attached members.
CREATE TABLE node_members (
    node_id               INTEGER NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    section_id            INTEGER NOT NULL REFERENCES sections(id) ON DELETE CASCADE,
    attached              INTEGER NOT NULL,
    assignment_similarity REAL,
    created_at            TEXT NOT NULL,
    PRIMARY KEY (node_id, section_id)
);

CREATE INDEX node_members_section ON node_members (section_id);

-- The reduced UMAP coordinate per section for a tree (a float32 blob), kept for
-- warm-init on a later rebuild (#T39 incremental settle) and the dashboard
-- graph. One coordinate per (tree, section).
CREATE TABLE section_coords (
    tree       TEXT NOT NULL,
    section_id INTEGER NOT NULL REFERENCES sections(id) ON DELETE CASCADE,
    dims       INTEGER NOT NULL,
    coords     BLOB NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (tree, section_id)
);
