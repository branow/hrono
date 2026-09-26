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
- Operating constants are **baked from the experiments, not config**: TAU 0.70, MAX_CAP 30, D_MAX 5, min_cluster_size 5, alpha 0.5, UMAP 25-dim, misfit thresholds. See `clustering-lifecycle.md`.

## Code quality

- Code quality (global rules): composition over inheritance; early returns, never-nest; no mutation (prefer tuples/frozen); dependency injection over monkeypatching; every parameter typed; no god objects/file sprawl; standard libs over hand-rolled. Simplicity first — minimum code that solves the ticket, nothing speculative.
- No new inline comments unless asked. No emojis anywhere. Roles (`reader`/`writer`/`admin`) enforced server-side from day one even while minimal.

## Testing

- Tests must fail if the feature breaks (regression-grade), not exist to pad coverage.
- A ticket that introduces or extends a test SEAM (`build=`, `client=`, `core_labeler=`, `reduce=`, `encoder_for=`, or any other injected backend) must also carry at least one test that exercises the REAL backend through that path, even at a trivial size. A seam proves the wiring; it cannot prove the backend's contract — 585 tests passed while no corpus could build to root (#094, #108).
- Where a backend's COST or its STATISTICS are part of its contract — model loading, clustering thresholds, recall's confidence gate — that real-backend test must run at a size where the cost or statistic is REAL, and the number must be recorded in the ticket. "Even at a trivial size" closes the wiring gap and not this one: `hrono recall` did not work at all against a real model while 1147 tests were green, because ~8s per request exists only at real size through a real client (#166, #168). Guard such a test with an env var naming the backend so it skips on a lean or offline install and runs where the weights are — `HRONO_TEST_REAL_MODEL=<id>` drives `tests/embed/test_runner.py` and `tests/server/test_warm_encoder.py`.
- A test written to guard a specific condition must be **mutation-checked**: break that condition in the code, confirm the test fails, restore it, and state the mutation and its result at handoff. A mutation that leaves the test green means the test is not yet a tooth — usually because it asserts one half of the state it constructed, or measures through a path the mutated code no longer populates (#125, #128).
- A SURVIVING mutation is a finding, not a formality: it says the guard sits somewhere other than where the test looks. Four shapes have appeared — a fixture too SYMMETRIC to show the asymmetry it claims, a population of ONE with no distribution to change, a unit test proving a FUNCTION while nothing proves its caller, and a property held by something else entirely (a daemon thread, a transaction) so deleting the code under test changes nothing (#162, #166, #163, #168). Work out which before changing anything.

## The gate

Before finishing any code change, in order: `uv run ruff format .`, then
`uv run ruff check --fix .`, then `uv run pytest`. Ruff's formatter is
authoritative — do not hand-format or fight its output. All three must be clean
before the work is done.
