-- A retired node must not leave its brief behind.
--
-- `briefs`, `node_members` and `node_children` all FK the node and cascade with
-- it, but the brief PASSAGES are keyed by a STRING source, `node-<id>`, which
-- no foreign key can express — so without this every rebuild that retired a
-- node would leave its summary in the recall index for ever. On a ~120-section
-- test corpus that reached 51 of 85 node:// passages (60%): recall answered
-- with summaries of topics the map no longer contained, which is a correctness
-- defect in the read door.
--
-- A TRIGGER rather than a cleanup call at each retirement site: the three sites
-- today (`_reconcile`'s retire branch, `delete_node`, `build_tree._drop_level`)
-- all delete from `nodes` directly, so the database enforces this for them and
-- for any future one, including raw SQL. `passages` cascade from `sections` by
-- FK; `passages_fts` is a standalone FTS5 table with no content sync, so it is
-- deleted explicitly here.
--
-- Both deletes are scoped by SOURCE TYPE, which is what makes them the exact
-- inverse of `store_brief`'s single source constructor: a USER source that
-- happened to be named `node-5` (a name collision) is left alone in full. The
-- FTS table carries no `source_type` of its own, so its rows are reached
-- THROUGH the passages they index — which is also why the FTS delete must come
-- FIRST, while those passages still exist.

CREATE TRIGGER nodes_brief_cleanup AFTER DELETE ON nodes
BEGIN
    DELETE FROM passages_fts
    WHERE passage_id IN (
        SELECT p.id FROM passages p
        WHERE p.source_type = 'node' AND p.source = 'node-' || old.id
    );

    DELETE FROM sections
    WHERE source_type = 'node' AND source = 'node-' || old.id;
END;

-- One-off: orphans already accumulated in a database built before the trigger.
-- Scoped the same way, so this needs no `LIKE 'node-%'` — which would also have
-- matched a user source called `node-foo`. A node:// passage whose node id is
-- gone is the whole definition of an orphan here.
DELETE FROM passages_fts
WHERE passage_id IN (
    SELECT p.id FROM passages p
    WHERE p.source_type = 'node'
      AND NOT EXISTS (SELECT 1 FROM nodes n WHERE 'node-' || n.id = p.source)
);

DELETE FROM sections
WHERE source_type = 'node'
  AND NOT EXISTS (SELECT 1 FROM nodes n WHERE 'node-' || n.id = sections.source);
