# hrono: project profile

Read by every autodev agent. Keep it short and true.

## Product and users
- A hierarchical, incrementally updated knowledge base for AI agents: it
  splits sources (git, GitHub, Bitbucket, Confluence, Notion) into sections,
  clusters them into a tree of topics with LLM-written briefs, and serves
  recall and explore to agents. A source change rewrites only what moved.
- One binary: `hrono serve` owns SQLite, compute and LLM calls; the CLI and
  the dashboard at `/ui` are its HTTP clients.
- Users (REQUIREMENTS.md): **admin** sets hrono up, pays for model calls,
  manages access; **curator** keeps the tree correct; **reader** browses,
  searches and asks, changing nothing; **agent** reads recall, explore and
  the export.
- Decisions: `docs/architecture.md`, `docs/api.md`, `docs/clustering.md`,
  `docs/summarization.md`, `docs/dashboard.md`; words: `GLOSSARY.md`; open
  work: `REQUIREMENTS.md`; real runs: `docs/evaluations/`.

## References
- Abstraction tree: RAPTOR (recursive cluster-and-summarize); take the
  recipe, not its structure (`docs/research/`).
- Graph retrieval baseline: LightRAG; the SWE-QA comparison is in
  `docs/evaluations/`.

## Gate
- Format and lint: `uv run ruff format . && uv run ruff check --fix .`
- Affected tests: `uv run pytest <test files>` (or `tests/<area>`)
- Fast suite (dev, once per epic before hand-off; merge after a clean
  rebase): `uv run pytest -n auto -m "not slow"`, budget 90 seconds
  (measured 54 s, 2070 tests, 2026-11-02).
- Full suite (qa, once per epic; merge only after a resolved conflict):
  `uv run pytest -n auto`, through the plugin's `heavy` lock.
- Browser drivers: Playwright against the production app on a real port,
  in `tests/server/test_ui_browser.py` (`tests/server/live.py`); the module
  is marked `slow` automatically by `tests/conftest.py`.
- Test markers: `slow` = real Chromium or the real UMAP/HDBSCAN recipe;
  skipped by the fast suite, run by the full suite and CI.
  `HRONO_TEST_REAL_MODEL=<id>` enables the real-embedding-model tests.

## Run the real app
Copy the built bench tree (flask, about 62 MB) into the worktree, never
serve the original:

    mkdir -p .hrono && cp ~/hrono-bench/db/hrono.db .hrono/hrono.db
    uv run hrono serve --key-file ~/hrono-bench/hrono.key --db .hrono/hrono.db --port <free port>

Sign in at `http://127.0.0.1:<port>/ui` with the admin token in
`~/hrono-bench/token`. Do not sync or rebuild the copy unless the epic
needs it: a build bills model calls (claude-code subscription).

## Needs
- uv and Python 3.13; `git`.
- Chromium for Playwright (`uv run playwright install chromium`).
- Network for Hugging Face weights on a first embed; the `claude` CLI,
  signed in, for any real `claude-code` model call. No Docker.

## Worktree setup
`uv sync -q --extra embed --extra cluster --extra claude-code`

## Conventions
`CONTRIBUTING.md` (design, jobs, code, tests, parallel-suite rules) and
`AGENTS.md`. Dashboard copy uses only `GLOSSARY.md` words. Ruff's formatter
is authoritative; line length 80.

## Commits
Conventional prefix (`feat(area):`, `fix(area):`, `dev: E0NN, ...` for board
changes), imperative and short. One commit per ticket, straight to `main`;
history stays linear.
