-- Each tree's health report, worked out when the tree changes and read by the
-- Health and home pages, which never compute it themselves.
CREATE TABLE tree_health (
    tree TEXT PRIMARY KEY,
    checked_at TEXT NOT NULL,
    report TEXT NOT NULL
);
