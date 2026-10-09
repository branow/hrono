# AGENTS.md: hrono

Instructions for any coding agent working in this repository. `CLAUDE.md` only
imports this file. Everything an agent needs is in the repository, so a fresh
clone on any machine has all of it.

## What hrono is

A hierarchical knowledge base for AI agents. It ingests heterogeneous sources
(git repositories, GitHub/Bitbucket accounts, Confluence, Notion). It splits
them, embeds them, and clusters them into a tree of abstractions (raw sections
-> briefs -> briefs of briefs -> root). It serves that tree to an agent and
answers retrieval queries. The differentiator is **incremental update**: a
source change touches only the affected nodes, never a full regeneration.

There is one binary, `hrono`, with subcommands. `hrono serve` is a
long-running HTTP server that owns the SQLite file (single writer), all
compute, and all LLM calls. Every other subcommand (`hrono recall`,
`hrono tree`, `hrono sources`, ...) is a thin HTTP client of that server, and
so is the web dashboard at `/ui`.

## Where things are

- `src/hrono/`: the package. `tests/`: the suite.
- `README.md`: install and use. `CONTRIBUTING.md`: the conventions (read it
  before writing code; it is not auto-loaded). `GLOSSARY.md`: the words the
  dashboard may use. `REQUIREMENTS.md`: the product requirements the dev loop
  works toward.
- `docs/design/`: the design record hrono was built from. Start with
  `INDEX.md`, then `context.md`. The settled decisions:
  - `implementation-notes.md`: the REST API and CLI.
  - `design-sketch-v1.md`: the architecture.
  - `clustering-lifecycle.md`: the cluster operating rules and baked
    constants.
  - `summarization-experiments.md`: the summarization recipe.
  - `build-order.md`: the original ticket plan (M0–M11, all done).
  - `prototype/`: the research notebooks with their outputs. Mine them for
    recipes, but do not port their structure.
- `docs/evaluations/`: every real run of hrono, with its log, findings and
  metrics. Add a folder per evaluation (`<YYYY-MM>-<corpus>/`) and keep it
  up to date as the run goes.
- `dev/`: the development process, as the epic board. Status is the folder a
  ticket file sits in: `backlog/` -> `todo/` -> `in-progress/` ->
  `verifying/` -> `po-review/` -> `done/`. Also here: `archive/`, `evidence/`
  per epic, and `board.md`, the PO's index.
- `.claude/autodev/` holds the PO, dev and qa role instructions.
  `.claude/workflows/autodev.js` is the workflow that runs the loop over the
  board.

## How we work

New work comes from the user, from `REQUIREMENTS.md` and from
`dev/backlog/`. Each change is implemented **and tested**
before the next starts. Commit straight to `main`.

**Before finishing any code change, run, in order:** `uv run ruff format .`,
then `uv run ruff check --fix .`, then `uv run pytest -n auto`. Ruff's
formatter is authoritative; do not hand-format or fight its output. All three
must be clean before the work is done.

When the change has its own skill, load it before writing code:
- `engineering:developer` for writing or structuring code.
- `engineering:qa` for tests.
- `engineering:security` for secrets, auth, input safety and dependencies.
- `engineering:release` for commits and CI.
- `coding-principles` for general code philosophy.

## Tech stack

- Python 3.13, managed by **uv**; package `src/hrono/`, console script `hrono`.
- Server: **FastAPI + uvicorn**, SQLite + **sqlite-vec** in one file, and a
  hand-rolled forward-only migration runner. A background worker runs jobs.
- CLI: **Typer** + **httpx**. Models and validation: **pydantic v2**.
- Secrets at rest: **cryptography** (Fernet), with the master key from
  `--key-file` or `HRONO_MASTER_KEY`.
- ML in-process (extras `embed` and `cluster`): **sentence-transformers**,
  **tree-sitter** + **tree-sitter-language-pack**, **umap-learn** +
  **hdbscan**.
- LLM providers: **anthropic**, **openai** (and compatible), and the
  **claude** CLI (`claude-code`, billed to a Claude subscription).
- Dashboard: server-rendered Jinja at `/ui`, no frontend build.
- Tests: **pytest** (+ xdist, Playwright for layout). Lint and format:
  **ruff**, line length 80.

## Local-only files

These stay out of git: `.venv/`, tool caches, `.playwright-mcp/`, the epic
worktrees under `.claude/worktrees/`, screenshots on the board
(`dev/**/*.png`), and `.claude/settings.local.json`. An evaluation's working
data (cloned repos, the server's database, its logs) lives outside the
repository; only what is recorded under `docs/evaluations/` is kept.
