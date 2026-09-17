-- A retired node must not leave its brief behind (#125).
--
-- `briefs`, `node_members` and `node_children` all FK the node and cascade with
-- it, but #071's brief PASSAGES are keyed by a STRING source, `node-<id>`, which
-- no foreign key can express — so every rebuild that retired a node left its
-- summary in the recall index for ever. On the QA corpus that had reached 51 of
-- 85 node:// passages (60%): recall was answering with summaries of topics the
-- map no longer contained, which is a correctness defect in the read door.
--
-- A TRIGGER rather than a cleanup call at each retirement site: the three sites
-- today (`_reconcile`'s retire branch, `delete_node`, `build_tree._drop_level`)
-- all delete from `nodes` directly, so the database enforces this for them and
-- for any future one, including raw SQL. `passages` cascade from `sections` by
-- FK; `passages_fts` is a standalone FTS5 table with no content sync, so it is
-- deleted explicitly here.
--
-- `source_type = 'node'` keeps the match the exact inverse of `store_brief`'s
-- single source constructor, and means a USER source that happened to be named
-- `node-5` (#076's collision) is untouched by this trigger.

CREATE TRIGGER nodes_brief_cleanup AFTER DELETE ON nodes
BEGIN
    DELETE FROM passages_fts
    WHERE source = 'node-' || old.id;

    DELETE FROM sections
    WHERE source_type = 'node' AND source = 'node-' || old.id;
END;

-- One-off: orphans already accumulated in a database built before the trigger.
DELETE FROM passages_fts
WHERE source LIKE 'node-%'
  AND NOT EXISTS (SELECT 1 FROM nodes n WHERE 'node-' || n.id = source);

DELETE FROM sections
WHERE source_type = 'node'
  AND NOT EXISTS (SELECT 1 FROM nodes n WHERE 'node-' || n.id = sections.source);
