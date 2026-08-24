-- The member-set signature a brief was written against (T23.2): a stable hash
-- of the node's ordered member ids at generation time. A brief is stale when
-- this differs from the node's current members, or when its stored prompt hash /
-- model provenance (#059) differs from the resolved brief prompt/model — the
-- two incremental-update invalidation keys. Nullable so briefs written before
-- this column compute as stale and regenerate once.

ALTER TABLE briefs ADD COLUMN member_signature TEXT;
