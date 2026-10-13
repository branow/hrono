# AGENTS.md: hrono

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
- `docs/README.md`: the documentation index. The settled decisions:
  - `docs/architecture.md`: how hrono works, end to end.
  - `docs/api.md`: the REST API and CLI.
  - `docs/clustering.md`: the cluster operating rules and baked constants.
  - `docs/summarization.md`: the summarization recipe.
  - `docs/dashboard.md`: the dashboard, page by page.
  - `docs/research/`: prior art, experiments and the research notebooks
    (`prototype/`). Mine them for recipes, but do not port their structure.
- `docs/evaluations/`: every real run of hrono, with its log, findings and
  metrics. Add a folder per evaluation (`<YYYY-MM>-<corpus>/`) and keep it
  up to date as the run goes.
- `dev/`: the development process, as the epic board. Status is the folder a
  ticket file sits in: `backlog/` -> `todo/` -> `in-progress/` ->
  `verifying/` -> `po-review/` -> `done/`. Also here: `archive/` and
  `board.md`, the board's index. `dev/evidence/` holds per-epic evidence and
  is local-only (git-ignored).
- `.claude/autodev/` holds the PO, dev and qa role instructions.
  `.claude/workflows/autodev.js` is the workflow that runs the loop over the
  board.

## How we work

New work comes from the user, from `REQUIREMENTS.md` and from
`dev/backlog/`. Each change is implemented **and tested**
before the next starts. Maintainers commit straight to `main`; outside
contributors open a pull request.

**Before finishing any code change, run, in order:** `uv run ruff format .`,
then `uv run ruff check --fix .`, then `uv run pytest -n auto`. Ruff's
formatter is authoritative; do not hand-format or fight its output. All three
must be clean before the work is done.

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
- LLM providers: `anthropic` (the **anthropic** SDK), `openai` and
  `openai-compatible` (over httpx), and `claude-code` (the **claude** CLI
  through **claude-agent-sdk**, extra `claude-code`, billed to a Claude
  subscription).
- Dashboard: server-rendered Jinja at `/ui`, no frontend build.
- Tests: **pytest** (+ xdist, Playwright for layout). Lint and format:
  **ruff**, line length 80.
