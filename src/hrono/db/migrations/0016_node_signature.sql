-- Stable node identity across rebuilds (#068, M7 incremental placement). A
-- content-derived signature per node so a re-cluster over unchanged input REUSES
-- the node id — keeping its brief (no cascade-delete, no LLM regeneration) — and
-- only genuinely new/changed clusters mint fresh ids. Leaf nodes sign over their
-- members' CONTENT HASHES (stable across a re-split's new section ids); upper
-- nodes over their child node ids (stable once the level below is). Nullable so
-- rows written before this column simply never match and rebuild once.

ALTER TABLE nodes ADD COLUMN signature TEXT;
