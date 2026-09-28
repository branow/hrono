# hrono

A hierarchical, incrementally-updated knowledge base for AI agents.

hrono ingests heterogeneous sources, splits and embeds them, and clusters
them into a tree of abstractions (raw sections to briefs to root) that it
serves to agents for retrieval. Its differentiator is incremental update:
a source change touches only the affected nodes, never a full rebuild.

The project ships as one binary, `hrono`. `hrono serve` is a long-running
HTTP server that owns the SQLite database, all compute, and all LLM calls;
every other subcommand is a thin HTTP client of that server.

## Getting started

```
hrono admin new-key --out hrono.key     # the key every secret is encrypted under
hrono serve --key-file hrono.key        # prints a bootstrap admin token, once
hrono profile add local --server http://127.0.0.1:8080 --token <token>
```

Back the key up. Lose it and every stored secret is unreadable — hrono will
start, and nothing it has encrypted will open.

Then register a source and a model (`hrono sources set`, `hrono models set` —
each takes a JSON config on stdin or `-f`), and build the tree with
`hrono tree maintain default`.

## The dashboard

`hrono serve` also serves a web dashboard at `/ui`, from the same process and
the same API. Sign in with the same token the CLI uses; it is held in an
HttpOnly SameSite=Strict cookie and resolved by the same role check every API
route uses, so a reader sees read-only views and the controls a role cannot use
are absent as well as refused.

It is server-rendered Jinja with no build step and no JavaScript to vendor: the
map, the runs view, triage, the activity log and the config tables are plain
HTML, and every view is a URL you can paste to someone else. Manual tree
surgery — rename, brief, notes, reparent, merge, dissolve, split, move a chunk
— is there for admins.

## In-process embedding

Embedding sources locally (for clustering and recall) uses the heavyweight
`sentence-transformers` backend, which is an opt-in extra so the default
install stays lean:

    uv pip install "hrono[embed]"

Without it the default install has no `torch`, and the `embed` operation fails
with a clear "in-process embedding backend is not installed" message.

## Status

Early development, and everything in the build order is implemented: ingest,
clustering, briefs, recall, export, the incremental update lifecycle, manual
edits, the dashboard, and hardening (master-key rotation, shared-resource
dry-run). It has not been run against a large corpus in anger; recall costs
about 0.011 ms per passage per query, so a corpus of a few hundred thousand
passages is the first size where that is worth re-measuring.

## CI

Every push to `main` and every pull request runs the same gate
`CONTRIBUTING.md` defines — `ruff format`, `ruff check`, `pytest` — on Python
3.13 against the locked environment. It reports rather than rewrites: CI never
fixes formatting, because a green build has to mean the author ran the gate.

## Contributing

How this codebase is built — its settled design decisions, code-quality
rules, and testing rules, each with the ticket that taught it — is in
[CONTRIBUTING.md](CONTRIBUTING.md). Read it before writing code.
