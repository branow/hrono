-- Upper-level topic membership: a level N+1 node's members are level-N NODES,
-- not sections, so they cannot live in node_members (whose section_id FKs
-- sections). node_children links a parent node to its child nodes, mirroring
-- node_members' attached/similarity flags. Leaf nodes (level 0) keep their
-- section membership in node_members; every level above uses this table.

CREATE TABLE node_children (
    parent_id             INTEGER NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    child_id              INTEGER NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    attached              INTEGER NOT NULL,
    assignment_similarity REAL,
    created_at            TEXT NOT NULL,
    PRIMARY KEY (parent_id, child_id)
);

CREATE INDEX node_children_child ON node_children (child_id);
