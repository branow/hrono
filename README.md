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

A `set` is validated before it is stored: a connection against its provider, a
local embedding model by loading its weights (about 14 s the first time for
MiniLM), a text model on a `claude-code` connection by asking the `claude`
CLI one trivial question (a few seconds, and one call's overhead). It waits up
to 120 s for that. If it still times out, the write may have landed anyway. The
message names the command that shows whether it did (`hrono models get
<name>`), so run that before you retry.

### Choose the backend before the first build

A model points at a connection, and the connection's provider decides what a
build costs:

- `claude-code` needs no API key and bills through your existing Claude
  subscription. Use it to try hrono out, and for the incremental syncs after a
  first build, where a handful of changed sections costs a handful of calls.
- `anthropic` (an API key) is what a **first full build over a large corpus**
  should use. The CLI pays a fixed overhead per call — 18871 cached input
  tokens, about $0.038, 4–30 s — that no prompt can remove. Measured: the
  `condense` pass over 421 sections took about 70 minutes and about $16 through
  `claude-code`. The same work through `anthropic` pays for the content rather
  than the harness.

Both can be registered at once; the connection is named per model, so the
`condense` model can use `anthropic` for the build while everything else stays
on `claude-code`.

### Scope a source to part of a repository

`filter.only` is a whitelist of globs applied before anything else, so a
monorepo can be ingested one package at a time:

```json
{"filter": {"only": ["src/hrono/crypto/**", "src/hrono/auth/**"]}}
```

Without it every file of the clone is a candidate. `filter.exclude` removes
paths, `filter.include` re-admits files the baked ignore list caught — neither
is a whitelist.

### How many calls at once

`hrono serve` runs one op's LLM calls in a bounded pool, 4 at a time by
default. Set `HRONO_LLM_CONCURRENCY` in the server's environment to raise it
(an API key with headroom) or lower it to 1 (a rate limit, or a small box).
Writes stay serial whatever it is set to.

## The dashboard

`hrono serve` also serves a web dashboard at `/ui`, from the same process and
the same API. Sign in with the same token the CLI uses; it is held in an
HttpOnly SameSite=Strict cookie and resolved by the same role check every API
route uses, so a reader sees read-only views and the controls a role cannot use
are absent as well as refused.

It is server-rendered Jinja with no build step and no JavaScript to vendor: the
map, the runs view, the health checks, the activity log and the config tables
are plain HTML, and every view is a URL you can paste to someone else. Home
answers four questions: whether the tree is up to date (each git source of the
tree says when it was last read, at which commit, and whether its remote has
moved on since — asked of the remote with `git ls-remote`, at most once a
minute), whether anything is running (live, from the same event stream as the
Runs page, on an empty tree too), what the last run did (the two sit side by
side), and, below them, whether anything needs a person. Every empty state offers its
next step as a button, and every action returns to the page it came from saying
what it did. Manual tree
surgery — rename, brief, notes, reparent, merge, dissolve, split, move a chunk
— is there for admins.

Settings shows one collection at a time — trees, sources, connections, models,
prompts — as a table, with each field of a form labelled and explained. It says
at the top whether the registry is complete enough to build (a role with no
model, a model whose connection is gone), and a delete or a reset shows what it
would leave stale before you confirm it. The values the server's environment
sets — version, database path, `HRONO_LLM_CONCURRENCY` — are shown read-only.

Access is the admin-only page for who may sign in: list the people with their
roles, add one (the new token is shown once, in the answer to the form, and is
stored only as a hash), change a role, reissue a token or delete a person, each
of the last two after a confirmation naming them. The last admin can be neither
deleted nor demoted, here or through the API. The master key can be rotated from
the same page, which says how many secrets it re-encrypted and that the server
must then be restarted on the new key.

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

## The export an agent reads

`hrono tree export` writes the tree as a folder of markdown. A topic's
directory is named by its subject, not by the clause a brief opens with, and
the facts a brief states (constants, environment variables, sizes) carry a `[§]`
link to the section pages they were found in, added when the folder is written;
the stored brief is never altered. A page that has children shows only its
opening and its `## Children` list, because every turn of a session carries the
pages it has read; the detail is one hop down.

## Evaluating the export

Whether an agent finds things in an export faster than in the raw repository
is measured, not assumed: `.e2e/eval/` runs headless Claude Code over exports
at several hop limits and over the raw checkout, asks the same questions with
known answers, and reports reads, tokens, time and correctness side by side.
It costs money, so it is run by hand; [its README](.e2e/eval/README.md) says
how.

## CI

Every push to `main` and every pull request runs the same gate
`CONTRIBUTING.md` defines — `ruff format`, `ruff check`, `pytest` — on Python
3.13 against the locked environment. It reports rather than rewrites: CI never
fixes formatting, because a green build has to mean the author ran the gate.

## The words hrono uses

A topic is a group of sections; a section is ~10 KB of one file; a brief is a
topic's summary, written from the sections' condensations rather than their raw
text. The full list, including the names that were superseded during
development, is in [GLOSSARY.md](GLOSSARY.md) — and the dashboard carries the
same thing at `/ui/guide`, with this install's own numbers in it.

## Contributing

How this codebase is built — its settled design decisions, code-quality
rules, and testing rules, each with the ticket that taught it — is in
[CONTRIBUTING.md](CONTRIBUTING.md). Read it before writing code.
