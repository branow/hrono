# sync_source docstring says the setup path calls it

From po review E013 (qa r2 note). Since c325ad9 the setup wizard calls
`fetch_source`, not `sync_source`, but `src/hrono/ingest/sync.py`
`sync_source`'s docstring still says "the setup path fetches a source" through
it. Fix the docstring (or move that sentence to `fetch_source`).
