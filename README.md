# hrono

A hierarchical, incrementally updated knowledge base for AI agents.

[![CI](https://github.com/branow/hrono/actions/workflows/ci.yml/badge.svg)](https://github.com/branow/hrono/actions/workflows/ci.yml)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![Python 3.13](https://img.shields.io/badge/python-3.13-blue.svg)](https://www.python.org/downloads/)

## What it is

hrono reads your sources (git repositories, a GitHub user or organization, a
Bitbucket workspace, Confluence, Notion), splits them into sections, embeds
them, and clusters them into a tree of topics. Each topic carries a brief: an
LLM-written summary of what it holds. Briefs of briefs climb to a single root.
An agent uses the tree two ways: **recall** hands it the passages that answer a
question, with provenance, and **explore** lets it walk the briefs from the
root down to the files it needs.

The differentiator is **incremental update**. When a source changes, hrono
re-reads only what moved, re-places only the affected sections and rewrites
only the briefs whose inputs changed. A one-file commit costs a handful of
model calls, not a rebuild.

hrono is one binary, `hrono`. `hrono serve` is a long-running HTTP server that
owns the SQLite database, all compute and all LLM calls. Every other
subcommand is a thin HTTP client of that server, and so is the web dashboard
at `/ui`.

## Quickstart

With hrono installed (below) and a repository of a few dozen files or more:

```sh
hrono admin new-key --out hrono.key     # the key every secret is encrypted under
hrono serve --key-file hrono.key        # prints a bootstrap admin token, once
```

In a second terminal:

```sh
hrono profile add local --server http://127.0.0.1:8080   # prompts for the token

hrono connections set claude -f - <<'EOF'
{"name": "claude", "provider": "claude-code", "auth": {"method": "none"}}
EOF

hrono models set emb -f - <<'EOF'
{"name": "emb", "kind": "embedding", "connection": null,
 "model": "sentence-transformers/all-MiniLM-L6-v2"}
EOF

hrono models set writer -f - <<'EOF'
{"name": "writer", "kind": "text", "connection": "claude", "model": "sonnet"}
EOF

hrono sources set repo -f - <<'EOF'
{"name": "repo", "type": "git",
 "url": "https://github.com/you/your-repo.git", "auth": {"method": "none"}}
EOF

hrono tree maintain default      # the cold, full build; prints a job id
hrono jobs watch <job-id>        # follows it until it ends
hrono recall default "how does the authentication flow work"
```

After the sources change, `hrono tree sync default` applies only the diff.
That is the everyday command.

Prefer the browser? Sign in to `http://127.0.0.1:8080/ui` with the bootstrap
token. Its Set up page walks a new install from a connection to a built tree.

Back up the key file. Without it every stored secret is unreadable: hrono
starts, and nothing it encrypted opens.

## Install

hrono is not yet published to PyPI; install it from source. You need Python
3.13+, [uv](https://docs.astral.sh/uv/) and `git`. The `claude` CLI, installed
and signed in, is needed only for the `claude-code` provider.

```sh
git clone https://github.com/branow/hrono.git
cd hrono
uv sync --extra embed --extra cluster
source .venv/bin/activate        # or prefix each command with `uv run`
```

The two extras are heavyweight (torch, umap-learn, hdbscan; several GB
together) and opt-in. Without `embed` the embed stage fails with "in-process
embedding backend is not installed"; without `cluster` the build stops at
clustering with the matching message.

The first build downloads the embedding model weights from Hugging Face, so it
needs network access. Clustering needs at least 12 sections; a toy source of
two small files stops with "too few sections".

## Concepts

- **source**: a place hrono reads. Registering one pulls nothing; a sync does.
- **section**: about 10 KB of one file; the unit hrono clusters and an agent
  reads when it explores.
- **passage**: about 800 B; the unit recall returns. A section reassembles
  byte-identically from its passages.
- **topic**: a group of sections, or of other topics, with a **brief** that
  summarizes it. Topics nest up to one root.
- **tree**: the topics over a named set of sources. One server can hold
  several; `default` always exists.
- **sync** brings a built tree up to date incrementally; **maintain** builds
  one from scratch.

The full vocabulary is in [GLOSSARY.md](GLOSSARY.md); the dashboard carries
the same at `/ui/guide`, with this install's numbers.

## The CLI

| Command | What it does |
| --- | --- |
| `hrono serve` | Run the server (`--host`, `--port`, `--key-file`, `--db`). |
| `hrono profile add\|list\|use\|current\|set-token\|rm` | Manage client profiles. |
| `hrono connections\|models\|prompts\|sources list\|get\|set\|rm` | Manage the registry; `set` reads JSON from `-f` or stdin. |
| `hrono tree config list\|get\|set\|rm` | Manage trees and the sources each maps. |
| `hrono tree maintain <tree>` | Build a tree from scratch. |
| `hrono tree sync <tree>` | Bring a built tree up to date incrementally. |
| `hrono tree export <tree> --out <dir>` | Write the tree as a folder of Markdown (`--levels` sets the hop limit, default 4). |
| `hrono tree pending <tree>` | List sections not yet placed in a topic. |
| `hrono jobs list\|get\|watch\|cancel` | Inspect and control background jobs. |
| `hrono recall [tree] "<question>"` | Return the passages that answer a question (`--limit`, `--json`). |
| `hrono usage` | Tokens, model time and cost by run, model, upstream model, user or day. |
| `hrono admin new-key\|reset-token` | Local recovery; acts on the database file, needs no token. |
| `hrono reset` | Wipe the local database after a confirmation. |

`hrono recall "question"` with no tree name uses the profile's
`--default-tree`, or `default`.

Exit codes: 0 ok, 1 failure, 2 usage, 3 server unreachable or timed out,
4 unauthorized or forbidden, 5 not found. `hrono jobs get` and `watch` exit 1
for a job that failed or was canceled.

### The export an agent reads

`hrono tree export` writes the tree as Markdown an agent can walk without a
server: `root.md`, one directory per topic named by its subject, and the
section files beneath. However deep the stored tree is, the export is at most
`--levels` hops from root to a section. Facts a brief states carry a `[§]` link
to the sections they came from. The dashboard's Export page has ready-to-paste
commands for wiring an agent to a tree.

## The dashboard

<!-- screenshot: docs/images/dashboard.png -->

`hrono serve` also serves a dashboard at `/ui`, from the same process and the
same API. Sign in with the token the CLI uses; a reader sees read-only views
and controls a role cannot use are absent as well as refused. It is
server-rendered HTML with no build step, every view is a shareable URL, and
everything is reachable from the keyboard.

Home shows whether the tree is up to date and what is running. Map, Outline,
Find and Ask are the ways into the knowledge. Runs, Health and Usage show what
the pipeline did, what needs a person, and what it cost. Set up, Settings and
Access cover installation, configuration and who may sign in.

The page-by-page guide is in [docs/dashboard.md](docs/dashboard.md).

## Configuration

### LLM providers

A model points at a connection, and the connection's provider decides what a
build costs. Supported providers: `claude-code`, `anthropic`, `openai` and
`openai-compatible` (Ollama, vLLM, LM Studio and similar servers).

- `claude-code` needs no API key and bills through your Claude subscription.
  Use it to try hrono and for incremental syncs, where a few changed sections
  cost a few calls. Each call carries a fixed overhead (about 19k cached input
  tokens and 4 to 30 s), so a first build over a large corpus is slow: the
  condense pass over 421 sections took about 70 minutes.
- `anthropic` bills per token to an API key and pays for the content rather
  than the harness. Use it for a first full build over a large corpus:

  ```json
  {"name": "api", "provider": "anthropic",
   "auth": {"method": "api-key", "key": "sk-ant-..."}}
  ```

Models can be assigned per role (`condense`, `brief`, `brief-upper`, `judge`),
so the condense model can use `anthropic` while everything else stays on
`claude-code`. A one-model install needs no roles.

Every `set` is validated before it is stored: a connection against its
provider, a local embedding model by loading its weights, a text model by one
trivial call. `hrono connections get <name>` shows a stored config with its
secrets masked.

### Sources

Source types: `git`, `github-user`, `bitbucket-workspace`, `confluence` and
`notion`. A git source can be scoped to part of a repository with
`filter.only`, a whitelist of globs applied before anything else:

```json
{"filter": {"only": ["src/payments/**", "src/auth/**"]}}
```

`filter.exclude` removes paths and `filter.include` re-admits files the
built-in ignore list caught; neither is a whitelist.

### Where data lives

The server's database is `.hrono/hrono.db`, **relative to the directory you
start it from**; `serve` prints the resolved path first. Pin it with `--db` or
`HRONO_DB`. The client profile lives under `~/.hrono`.

### Environment variables

| Variable | Meaning |
| --- | --- |
| `HRONO_DB` | Database path for `serve`, `reset` and `admin` when `--db` is not given. |
| `HRONO_HOME` | Where the client profile lives (default `~/.hrono`). |
| `HRONO_MASTER_KEY` | The master key, instead of `--key-file`. |
| `HRONO_TOKEN` | The token `profile add` and `profile set-token` read when `--token` is not given. |
| `HRONO_LLM_CONCURRENCY` | Concurrent LLM calls per operation (default 4). Writes stay serial. |

### Recovering access

The bootstrap token is shown once. To reissue it, on the machine that holds
the database file:

```sh
hrono admin reset-token admin        # prints a fresh token, once
hrono profile set-token local        # records it on the existing profile
```

A lost master key is not recoverable. `hrono reset` wipes the database and the
synced source caches after a confirmation, and refuses while a server holds
the file; the next `hrono serve` starts clean.

## Status

hrono is alpha software. Ingest, clustering, briefs, recall, export,
incremental sync, manual edits, the dashboard, usage accounting and master-key
rotation all work and are covered by tests. Interfaces may still change
between releases. Large corpora are the open frontier: recall costs about
0.011 ms per passage per query, so a few hundred thousand passages is the
first size worth re-measuring.

## Documentation

- [docs/README.md](docs/README.md): the documentation index.
- [docs/architecture.md](docs/architecture.md): how hrono works.
- [docs/api.md](docs/api.md): the REST API and CLI reference.
- [docs/dashboard.md](docs/dashboard.md): the dashboard, page by page.
- [docs/evaluations/](docs/evaluations/): runs against real corpora, with
  logs, findings and metrics.

## Contributing

Contributions are welcome. Read [CONTRIBUTING.md](CONTRIBUTING.md) for setup,
the gate every change passes, and the engineering conventions. Coding agents
start at [AGENTS.md](AGENTS.md). Report security issues privately as described
in [SECURITY.md](SECURITY.md).

## License

[Apache-2.0](LICENSE). Copyright 2026 Orest Bodnar.
