---
id: 196
title: CI — run the gate on every push and pull request
priority: high
size: small
depends_on: []
spec_refs: []
---

## Context
1404 tests, and nothing runs them except a person remembering to. The repo has
a GitHub remote (`branow/hrono`), so the gate that `CONTRIBUTING.md` already
defines just needs somewhere to run.

## Description
One workflow, one job, the gate in the order `CONTRIBUTING.md` states it:
`ruff format`, then `ruff check`, then `pytest`.

Four decisions worth writing down:

- **`--check`, never `--fix`.** Locally the formatter is authoritative and
  rewrites; in CI it reports. A CI that fixes formatting is a CI that hides
  whether the author ran the gate, and pushes a commit nobody wrote.
- **`uv sync --locked`**, so a `uv.lock` that has drifted from
  `pyproject.toml` fails the build. A lockfile nobody verifies is a lockfile
  that stops meaning anything — and this repo just moved numpy between
  dependency groups (#194), which is exactly the edit that desyncs one.
- **No `embed` extra, and the skips are REPORTED.** The two real-weights tests
  (`HRONO_TEST_REAL_MODEL`) need model downloads; CI does not pull torch for
  them. But `-rs` prints why every skip happened, because a suite that quietly
  shrinks from 1404 to 40 looks exactly as green as one that does not (#170's
  concern, one level up).
- **`.gitignore` is deny-by-default** (`*` plus a whitelist), so the workflow
  file needs an explicit un-ignore or git will never see it. #171 hit this same
  wall with `CONTRIBUTING.md`.

## Acceptance criteria
- [x] Runs on push to `main` and on pull requests.
- [x] Fails on unformatted code, on a lint error, and on a failing test —
      each verified by deliberately breaking it, not assumed.
- [x] Fails on a lockfile that does not match `pyproject.toml`.
- [x] Skipped tests are visible in the log with their reason.
- [x] The workflow file is actually tracked by git.
- [x] Python 3.13, matching `.python-version`.

## Review log
- 2026-09-28 po: authored. The user asked for "simple CI to check tests, etc,
  usual" — so the usual, with the four decisions above stated rather than
  absorbed from a template.
- 2026-09-28 dev: `.github/workflows/gate.yml`, one job, plus the `.gitignore`
  un-ignore it needed to exist at all, and a CI section in the README.
  - **Each step verified by BREAKING it, not assumed** — the acceptance
    criterion said so and it is the only way to know a gate bites:
    unformatted code -> format step fails; a stray `import os` -> lint fails;
    a planted `assert 1 == 2` -> test step fails; an extra dependency added to
    `pyproject.toml` without re-locking -> `uv sync --locked` fails. All four
    restored afterwards, and `uv sync --locked` green again.
  - Ran the whole workflow's command sequence locally, in order, in the
    environment `--locked` produces: **1403 passed, 3 skipped in 106s**. The
    three skips are named in the log by `-rs`: two want
    `HRONO_TEST_REAL_MODEL`, one wants the `embed` extra. CI deliberately does
    not install that extra — it would pull torch for two tests whose weights it
    does not have.
  - Note for anyone reading a CI log against a local run: locally the count is
    1404/2 because a dev machine with `--all-extras` has the in-process embed
    backend. `--locked` drops it, which is the difference.
  - `concurrency` cancels a superseded run: a second push makes the first run's
    answer stale, and a queue of stale answers is how a CI becomes background
    noise.
  - NOT pushed. The branch is 53 commits ahead of `origin/main` and that is the
    user's call to make, not a side effect of adding a workflow file.
- 2026-09-28 qa: verified. The claim "this CI would have caught it" is only
  worth anything if someone made it fail on purpose first; all four failure
  modes were induced and observed.
