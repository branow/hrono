-- Full-text index over passage path + body for recall's keyword leg (T25.2),
-- ranked by BM25 (FTS5's default). Standalone, not external-content: a passage's
-- body lives in `contents` by hash, so the `split` op populates this from the
-- raw bytes and keeps it in sync (delete-by-source, then re-insert, on every
-- re-split). `passage_id` maps a hit back to its passage and `source` drives the
-- delete-by-source; both are UNINDEXED bookkeeping. The structure path (`sp:`)
-- is deliberately NOT indexed — only the address path and the body.

CREATE VIRTUAL TABLE passages_fts USING fts5(
    path,
    body,
    passage_id UNINDEXED,
    source UNINDEXED
);
