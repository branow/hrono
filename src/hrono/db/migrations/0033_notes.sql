-- Human notes, and the export shows them.
--
-- The spec is explicit about who a note is FOR: "a human 'deprecated, use X'
-- annotation flows into the rendered tree so the traversing agent sees it."
-- It is not a dashboard comment field — it is a sentence the agent reads
-- beside a model's summary, and the whole value is that it can tell them
-- apart.
--
-- Append-only, one row per note: an operator's later correction must not
-- silently erase the note the rest of the team has been reading. A note does
-- NOT pin — annotating a topic is not correcting the map, and freezing a tree
-- because someone left a comment would be a trap.
CREATE TABLE notes (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    kind       TEXT NOT NULL,          -- 'node' | 'section'
    target_id  INTEGER NOT NULL,
    text       TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX notes_target ON notes (kind, target_id);

-- A retired node takes its notes with it, exactly as it takes its brief and
-- its pins: a note on an id the tree no longer holds would reappear on
-- whatever is created with that id next.
CREATE TRIGGER notes_follow_node
AFTER DELETE ON nodes
BEGIN
    DELETE FROM notes WHERE kind = 'node' AND target_id = OLD.id;
END;

CREATE TRIGGER notes_follow_section
AFTER DELETE ON sections
BEGIN
    DELETE FROM notes WHERE kind = 'section' AND target_id = OLD.id;
END;
