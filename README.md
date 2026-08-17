# hrono

A hierarchical, incrementally-updated knowledge base for AI agents.

hrono ingests heterogeneous sources, splits and embeds them, and clusters
them into a tree of abstractions (raw sections to briefs to root) that it
serves to agents for retrieval. Its differentiator is incremental update:
a source change touches only the affected nodes, never a full rebuild.

The project ships as one binary, `hrono`. `hrono serve` is a long-running
HTTP server that owns the SQLite database, all compute, and all LLM calls;
every other subcommand is a thin HTTP client of that server.

## In-process embedding

Embedding sources locally (for clustering and recall) uses the heavyweight
`sentence-transformers` backend, which is an opt-in extra so the default
install stays lean:

    uv pip install "hrono[embed]"

Without it the default install has no `torch`, and the `embed` operation fails
with a clear "in-process embedding backend is not installed" message.

## Status

Early development. See the build order for milestone progress.
