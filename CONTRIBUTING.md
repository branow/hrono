# Contributing to hrono

Thanks for your interest in hrono. This guide covers setup, the gate every
change passes, how to open a pull request, and the conventions the codebase
follows. Each convention states its reason: a rule whose reason is lost gets
deleted by the next person who finds it inconvenient.

Coding agents should also read [AGENTS.md](AGENTS.md).

## Getting started

You need Python 3.13+, [uv](https://docs.astral.sh/uv/) and `git`.

```sh
git clone https://github.com/<you>/hrono.git
cd hrono
uv sync --extra embed --extra cluster
uv run playwright install chromium
```

`uv sync` installs the `dev` group, which carries the test tools and the
clustering backend the tests exercise. The `embed` extra is needed to run a
real build locally; the suite itself runs without it. Playwright's Chromium
drives the layout tests; without it they skip locally and fail in CI.

## The gate

Before finishing any change, run, in order:

```sh
uv run ruff format .
uv run ruff check --fix .
uv run pytest -n auto
```

All three must be clean. Ruff's formatter is authoritative; do not hand-format
or fight its output. CI runs the same gate in check mode and never rewrites
code, so a green build means the author ran it.

## Pull requests

1. Fork the repository and create a branch from `main`.
2. Make one focused change, with the tests that prove it.
3. Run the gate.
4. Open a pull request against `main` describing what changed and why.

CI must pass before a pull request is merged. For anything larger than a fix,
open an issue first so the approach can be agreed before the work.

## Design decisions

- **API shape.** Field keys are `snake_case`; enum and type values are
  `kebab-case`. Config is data you PUT; work is a job you POST. Writing config
  never triggers work, so a config change is always cheap and reviewable.
- **URIs are resource addresses**, canonical
  `<source-type>://<instance>/<path>@<version>`, with no fragment. `@version`
  already changes every URI on any edit, so a fragment would add nothing.
  Position is data, not identity: it lives in a piece's `ordinal` and
  `sp_paths`. `hash` (SHA-256 of the raw byte range) is the dedup and
  embed-once key.
- **Two leaf granularities.** Sections (~10 KB) are the cluster and traversal
  unit; passages (~800 B) are the recall unit. A section reassembles
  byte-identically from its passages.
- **A registry field documents itself** on the pydantic field: `title`, a
  one-line `description`, `examples` where a value has a shape worth showing,
  and `json_schema_extra={"group": ...}` for its form section. The settings
  form reads them from there, so the API's validation and the page cannot
  drift. `tests/registry/test_field_docs.py` fails on a field without them.
- **The dashboard speaks the glossary.** `tests/server/test_ui_vocabulary.py`
  reads every route and fails on any word listed under "Words we do not use"
  in `GLOSSARY.md`, so adding a word there bans it. A number the Guide quotes
  comes from the constant behind it, and `tests/server/test_ui_guide.py` moves
  each constant to see the page follow.
- **Previews and estimates share code with what they preview.** The setup path
  keeps no progress record: a step is done when the registry says so, and
  every write is the registry engine's own `replace_item`. A source preview is
  `ingest.filter.survey`, the function ingest is built on, and an estimate
  counts sections with `split_op.sections_of`, the cut a split stores. A
  preview therefore cannot disagree with the ingest it previews.
- **Operating constants are baked from experiments, not config**: TAU 0.70,
  MAX_CAP 30, D_MAX 5, min_cluster_size 5, alpha 0.5, UMAP 25-dim, and the
  misfit thresholds. See [docs/clustering.md](docs/clustering.md).

## Jobs and dependencies

- **The dependency graph lives in the data, not in job edges.** A re-run is
  incremental because each piece of content records what produced it:
  `briefs._is_fresh` compares the member signature, prompt hash and model
  fingerprint; `member_signature` signs over content hashes, so a re-split
  does not invalidate a brief; `propagate` climbs from a changed leaf and marks
  exactly the ancestors whose briefs no longer hold. A job DAG would be a
  second representation of the same dependency, and the two would drift.
- **A stage order is code, in one composing op** (`tree/sync_chain.py`), not a
  wiring an operator can get wrong. A chain that skips a stage fails silently:
  sections arrive without condensations and briefs cite sources they never
  read.
- **Load under the lock, release it, compute, re-acquire, persist**, and
  reconcile at persist against the same signatures. A job that holds the lock
  through slow work makes the worker count worthless; one that persists
  without re-checking overwrites whatever changed underneath it.

## Code

- Prefer composition over inheritance, early returns over nesting, immutable
  values (tuples, frozen models) over mutation, and dependency injection over
  monkeypatching. Small, focused modules read better than god objects.
- Type every parameter.
- Prefer the standard library and established packages over hand-rolled code.
- Write the minimum code that solves the problem; nothing speculative.
- Comments explain why, not what, and only where the code cannot say it.
- No emojis anywhere.
- Roles (`reader`, `writer`, `admin`) are enforced server-side on every route.
- **Order a module top-down**: entry points first, the helpers they call
  below. Python resolves names at call time, so this works, and a reader meets
  a module's subject before its plumbing. Apply it to files as you touch them
  rather than in a sweep, so every diff stays reviewable.

## Tests

- **A test must fail when the feature breaks.** Tests exist to catch
  regressions, not to pad coverage.
- **Every injected seam needs a real-backend test.** A seam (`build=`,
  `client=`, `reduce=`, `encoder_for=` or any other injected backend) proves
  the wiring but not the backend's contract. At least one test drives the real
  backend through that path, even at a trivial size.
- **Where cost or statistics are the contract, test at real size.** Model
  loading, clustering thresholds and recall's confidence gate behave
  differently at toy size. Guard such tests with an environment variable
  naming the backend, so they skip on a lean or offline install:
  `HRONO_TEST_REAL_MODEL=<id>` drives `tests/embed/test_runner.py` and
  `tests/server/test_warm_encoder.py`.
- **Reach the state the way production does.** A test that constructs the
  state it asserts on proves the reader, not the writer. At least one test per
  feature arrives at that state through the endpoint, the op or the CLI;
  otherwise the code that builds it can be dead while every test stays green.
- **Mutation-check a guard.** Break the condition a test guards, confirm the
  test fails, restore it. If the test stays green, find out why before changing
  anything: usually the fixture is too symmetric to show the asymmetry, the
  population is one, only the function and not its caller is tested, or the
  property is held by something else (a thread, a transaction).
- **Test laid-out pixels in a real browser.** Horizontal overflow, a hint
  covering a figure, a wrapping bar: a `TestClient` reads HTML and cannot see
  them. `tests/server/test_ui_browser.py` runs Playwright against the
  production app on a real port (`tests/server/live.py`).
- **Collapse same-shape tests with `@pytest.mark.parametrize`**, giving each
  row a stable `id` so a failure names the case. pytest already rewrites
  `assert` and diffs both operands, so no matcher library earns its
  dependency.

### The suite runs in parallel

- A test may not share a port, a file or global state with another. Bind port
  0, write under `tmp_path`, and serve a stub API with
  `tests.stub_server.serving`.
- A module that runs the real UMAP and HDBSCAN recipe goes in `_UMAP_MODULES`
  in `tests/conftest.py`, so its one-time import and compile cost is paid by
  two workers rather than all of them.
- A module whose tests all start from the same built tree builds it once, as a
  module fixture, and restores a copy per test (`tests/world.py`); see
  `tests/tree/test_update.py`.
- A wait that proves something takes time is scaled down, not slept at
  production length; a poll interval is a module constant the test patches.
- A fixture that writes through the adopted database connection while a
  `TestClient` is running stops the worker first
  (`client.app.state.worker.stop()`, then `join`). The worker polls the same
  SQLite connection from its own thread, and two threads interleaving
  transactions on one connection fail intermittently.

## Reporting bugs and security issues

Open a GitHub issue for bugs and feature requests. Report security
vulnerabilities privately, as described in [SECURITY.md](SECURITY.md).

By contributing you agree that your contributions are licensed under the
[Apache License 2.0](LICENSE).
