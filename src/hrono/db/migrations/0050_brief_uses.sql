-- The files a leaf brief looked up in other topics and took a statement from
-- (`summarize/lookup.py`). Such a file is a dependency the tree's shape does
-- not hold, so `propagate` follows these rows: when a used file's content no
-- longer matches `signature`, the brief is judged against the change. Only
-- files the writer declared it used are kept, never the topic's own members.
CREATE TABLE brief_uses (
    node_id   INTEGER NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    file      TEXT NOT NULL,  -- "<source>/<path>"
    signature TEXT NOT NULL,  -- the file's section content hashes, signed
    statement TEXT NOT NULL,  -- what the brief took from it
    PRIMARY KEY (node_id, file)
);

CREATE INDEX brief_uses_file ON brief_uses (file);
