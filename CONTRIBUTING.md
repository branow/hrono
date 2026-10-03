# Contributing to hrono

How this codebase is built. Every rule below was learned from a defect that
cost at least one round, and each keeps the ticket number that taught it —
those citations are the evidence. A rule whose reason is lost gets deleted by
the next person who finds it inconvenient.

The day-to-day working state (current ticket, local paths, the throwaway
prototype) lives in `CLAUDE.md`, which is deliberately not committed. This file
is the part that outlives one machine.

## Design decisions, settled

- API: field keys `snake_case`, enum/type values `kebab-case`. Config is data you PUT; work is a job you POST — writing config never triggers work.
- URIs are fragment-free resource addresses, canonical `<source-type>://<instance>/<path>@<version>` — no `#chunk-n`: named fragments were considered and rejected (`rad/hrono/context.md`), because `@version` already changes every URI on any edit. Position is data, not identity: it lives in a piece's `ordinal` and `sp_paths`. `hash` (raw byte range, SHA-256) is the dedup/embed-once key (#144).
- Two leaf granularities: **sections** (~10 KB, cluster/traversal unit) and **passages** (~800 B, recall injection unit); a section reassembles byte-identically from its passages.
- A registry field declares its own label and help ON the pydantic field — `title`, a one-line `description`, `examples` where a value has a shape worth showing, and `json_schema_extra={"group": ...}` for its form section. The settings form reads them from there, so the API's validation and the page cannot drift, and `tests/registry/test_field_docs.py` fails on a field without them (#210).
- Every word a person reads on the dashboard is one the glossary uses: `tests/server/test_ui_vocabulary.py` reads every route and fails on any word listed under "Words we do not use" in `GLOSSARY.md`, so adding a word there bans it. A number the Guide quotes comes from the constant behind it, and `tests/server/test_ui_guide.py` moves each constant to see the page follow (#216).
- Operating constants are **baked from the experiments, not config**: TAU 0.70, MAX_CAP 30, D_MAX 5, min_cluster_size 5, alpha 0.5, UMAP 25-dim, misfit thresholds. See `clustering-lifecycle.md`.

## Code quality

- Code quality (global rules): composition over inheritance; early returns, never-nest; no mutation (prefer tuples/frozen); dependency injection over monkeypatching; every parameter typed; no god objects/file sprawl; standard libs over hand-rolled. Simplicity first — minimum code that solves the ticket, nothing speculative.
- No new inline comments unless asked. No emojis anywhere. Roles (`reader`/`writer`/`admin`) enforced server-side from day one even while minimal.

## Testing

- Tests must fail if the feature breaks (regression-grade), not exist to pad coverage.
- A ticket that introduces or extends a test SEAM (`build=`, `client=`, `core_labeler=`, `reduce=`, `encoder_for=`, or any other injected backend) must also carry at least one test that exercises the REAL backend through that path, even at a trivial size. A seam proves the wiring; it cannot prove the backend's contract — 585 tests passed while no corpus could build to root (#094, #108).
- Where a backend's COST or its STATISTICS are part of its contract — model loading, clustering thresholds, recall's confidence gate — that real-backend test must run at a size where the cost or statistic is REAL, and the number must be recorded in the ticket. "Even at a trivial size" closes the wiring gap and not this one: `hrono recall` did not work at all against a real model while 1147 tests were green, because ~8s per request exists only at real size through a real client (#166, #168). Guard such a test with an env var naming the backend so it skips on a lean or offline install and runs where the weights are — `HRONO_TEST_REAL_MODEL=<id>` drives `tests/embed/test_runner.py` and `tests/server/test_warm_encoder.py`.
- A test written to guard a specific condition must be **mutation-checked**: break that condition in the code, confirm the test fails, restore it, and state the mutation and its result at handoff. A mutation that leaves the test green means the test is not yet a tooth — usually because it asserts one half of the state it constructed, or measures through a path the mutated code no longer populates (#125, #128).
- A test that CONSTRUCTS the state it asserts on proves the READER and says nothing about the WRITER. At least one test per feature must arrive at that state the way production does — through the endpoint, the op, the CLI — or the thing that builds it can be dead while every test stays green. Four tickets have paid for this: 585 tests over a corpus that could not build (#094), an orphan sweep whose only caller could have been `range(1)` forever because the collector was tested directly (#163), and `jobs.scope.fan_out`, called from tests only, so an aggregation shipped over a structure no request could produce (#172, #175).
- A SURVIVING mutation is a finding, not a formality: it says the guard sits somewhere other than where the test looks. Four shapes have appeared — a fixture too SYMMETRIC to show the asymmetry it claims, a population of ONE with no distribution to change, a unit test proving a FUNCTION while nothing proves its caller, and a property held by something else entirely (a daemon thread, a transaction) so deleting the code under test changes nothing (#162, #166, #163, #168). Work out which before changing anything.

- A dashboard property that lives in LAID-OUT PIXELS — horizontal overflow, a hint covering the figure it explains, a bar that wraps — is tested in a real browser (`tests/server/test_ui_browser.py`, Playwright over the production app on a real port, `tests/server/live.py`). A TestClient reads HTML and cannot see a 4px scrollbar; every page shipped with one until a browser measured it (#215). The test skips locally when no Chromium is installed (`uv run playwright install chromium`) and fails in CI, where a skip would hide the regression.

## Form, applied as files are touched

Two standing rules rather than tickets, because each is a per-file habit and a
big-bang sweep of either would be a large diff nobody can review for the one
thing it claims to change.

- **Order a module top-down**: the high-level entry points first, the helpers
  they call below them. Python resolves names at call time, so a helper defined
  lower is callable from a function defined higher; helpers at the top are a
  define-before-use habit from other languages, and they make a reader meet a
  module's plumbing before its subject (#049).
- **Collapse same-shape tests with `@pytest.mark.parametrize`**, giving each row
  a stable `id` so a failure names the case. pytest already rewrites `assert`
  and prints a full diff of both operands, so no matcher library earns its
  dependency; add an explicit `assert cond, "message"` only where the rewritten
  output is genuinely opaque, such as raw bytes or a large blob (#044).

## Jobs and the dependency graph

- **The graph lives in the DATA, not in job edges** (#051). What makes a re-run
  incremental is not knowing which job ran before, it is knowing whether a
  piece of CONTENT still matches what produced it: `briefs._is_fresh` compares
  the member signature, prompt hash and model fingerprint (#064, #191);
  `member_signature` signs over content hashes so a re-split does not
  invalidate a brief (#068); `propagate` climbs from a changed leaf and marks
  exactly the ancestors whose descriptions no longer hold (#087). A job DAG
  would be a second representation of the same dependency, and the two would
  eventually disagree with the data right and the graph confidently wrong.
- **A stage order is CODE, in one composing op** — `tree/sync_chain.py`, not a
  wiring diagram an operator can get wrong. #122 was a chain that skipped a
  stage: sections arrived unsummarised, `brief` dropped them, and the briefs
  cited sources they had never read, with no error anywhere.
- **Load under the lock, RELEASE, compute, re-acquire, persist** (#035, #040),
  and reconcile at persist against the same signatures rather than writing
  blindly. A job that holds the lock through slow work makes worker count
  worthless; a job that persists without re-checking overwrites whatever moved
  underneath it.

## The test harness

- A fixture that writes through the ADOPTED connection while a `TestClient` is
  running must stop the worker first
  (`client.app.state.worker.stop()` then `join`). The worker polls that same
  sqlite connection from its own thread, and two threads interleaving
  transactions on one connection fails intermittently in whichever test happens
  to be writing when a poll lands — it passed a whole file eight times in a row
  and failed twice in the full suite (#194). The same shape as #168's warm-up
  reading the database on a daemon thread.

## The gate

Before finishing any code change, in order: `uv run ruff format .`, then
`uv run ruff check --fix .`, then `uv run pytest -n auto`. Ruff's formatter is
authoritative — do not hand-format or fight its output. All three must be clean
before the work is done.

The suite runs in parallel, so a test may not share a port, a file or global
state with another. Bind port 0, write under `tmp_path`, and serve a stub API
with `tests.stub_server.serving` (its poll interval is short; the default
makes every teardown wait half a second). A module that runs the real UMAP ->
HDBSCAN recipe goes in `_UMAP_MODULES` in `tests/conftest.py`, so its one-time
nine-second import and compile is paid by two workers and not eight.

A module whose tests all start from the same built tree builds it once, as a
module fixture, and restores a copy per test (`tests/world.py`) instead of
rebuilding: see `tests/tree/test_update.py`. A wait that proves something takes
time (a heartbeat outliving a stale window) is scaled down, not slept at its
production length, and a poll interval is a module constant the test patches.
