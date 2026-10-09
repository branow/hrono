-- Upper-level topic membership: a level N+1 node's members are level-N NODES,
-- not sections, so they cannot live in node_members (whose section_id FKs
-- sections). node_children links a parent node to its child nodes. Leaf nodes
-- (level 0) keep their section membership in node_members; every level above
-- uses this table.
--
-- `attached` carries node_members' meaning: 1 = attached by proximity to the
-- nearest parent, 0 = a density-core member of it. `assignment_similarity`
-- DIVERGES from node_members' convention: it is recorded on every row,
-- not only attached ones, because a confident attachment's score is the
-- diagnostic a misfit check one level up will read, and there is no
-- reader today for discarding it to protect.

CREATE TABLE node_children (
    parent_id             INTEGER NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    child_id              INTEGER NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    attached              INTEGER NOT NULL,
    assignment_similarity REAL,
    created_at            TEXT NOT NULL,
    PRIMARY KEY (parent_id, child_id)
);

CREATE INDEX node_children_child ON node_children (child_id);
