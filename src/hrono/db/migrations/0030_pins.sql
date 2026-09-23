-- A hand-edit pins what it touched, and the pipeline treats a pin as a hard
-- constraint (#154, T45). Without this a manual fix is silently reverted on
-- the next update, which is worse than not offering the edit at all.
--
-- One TABLE rather than a flag per table: `kind` says what is held — a brief,
-- a section's membership, a node's parenting — so a new pinnable thing is a
-- new kind, not a migration. `target_id` is the node id for `brief` and
-- `parenting`, and the section id for `membership`.
--
-- `reason` records WHY, because a pin outlives the person who set it and a
-- frozen topic with no explanation is a mystery someone will eventually
-- resolve by deleting it.
CREATE TABLE pins (
    kind      TEXT NOT NULL,
    target_id INTEGER NOT NULL,
    reason    TEXT,
    pinned_at TEXT NOT NULL,
    PRIMARY KEY (kind, target_id)
);

CREATE INDEX pins_kind ON pins (kind);

-- A retired node takes its pins with it, exactly as it takes its brief: a pin
-- on an id the tree no longer holds would silently apply to whatever node is
-- created with that id next.
CREATE TRIGGER pins_follow_node
AFTER DELETE ON nodes
BEGIN
    DELETE FROM pins
    WHERE kind IN ('brief', 'parenting') AND target_id = OLD.id;
END;

CREATE TRIGGER pins_follow_section
AFTER DELETE ON sections
BEGIN
    DELETE FROM pins WHERE kind = 'membership' AND target_id = OLD.id;
END;
