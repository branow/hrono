---
id: 138
title: `hrono tree sync <name>` — the one command that brings a knowledge base up to date
priority: high
size: medium
depends_on: [137]
spec_refs: [implementation-notes.md, build-order.md#T11.4]
found_by: split from #106 at the PO ruling on note D, 2026-09-21
---

## Context
Split 2 of 3 from #106. #137 builds the chain; this exposes it as the single
operator-facing verb, and fixes the surface defects the same QA run found.

## Description

**The verb.** `POST /trees/{name}/sync` enqueues #137's op and returns the job
id, mirroring how `POST /trees/{name}/maintain` works today
(`server/trees.py:44`). `hrono tree sync <name>` is its CLI client, beside
`hrono tree maintain`. Writer role, like maintain.

**The config CLI (F10).** Registering a source today means hand-written curl.
Add `hrono sources|connections|models|prompts` with `list`, `get`, `set`, `rm`,
and `hrono jobs` with `list` and `get` — thin clients of the registry endpoints
that already exist. `jobs get` must render #132's `result`, since that is where
a user learns what their one verb actually did.

**`PUT` creates (F2).** `CLAUDE.md` and the spec both say "config is data you
PUT", and the engine only creates on `POST`:
```
$ curl -X PUT /sources/tiny -d '{...}'   ->  404 sources not found: tiny
```
Make `PUT /{collection}/{name}` create-or-replace idempotently. This was already
settled as a technical call on #106 (2026-09-12).

**The bootstrap hint prints the real port (F3).** Served with `--port 8299`, the
first-run message prints `--server http://127.0.0.1:8080`: `cli.py`'s
`_bootstrap_message` uses a literal instead of the host and port the server was
given. A copy-pasteable hint that does not work is worse than none.

**One error envelope (F11).** Body validation returns
`{"error":{"code":"validation-error",...}}`; query validation returns FastAPI's
raw `{"detail":[...]}` (try `GET /trees/default/export?levels=abc`). Route query
validation through the app envelope so a client parses one shape.

## Acceptance criteria
- [ ] `POST /trees/{name}/sync` enqueues #137's op, writer role, returns a job id.
- [ ] `hrono tree sync <name>` drives it and reports the job.
- [ ] `hrono sources|connections|models|prompts` support list/get/set/rm, and
      `hrono jobs` list/get, with `jobs get` rendering the job's `result`.
- [ ] `PUT /{collection}/{name}` creates when absent and replaces when present;
      a test covers both.
- [ ] The bootstrap hint prints the host and port the server was started with —
      a test asserts it for a non-default port.
- [ ] A query-parameter validation failure returns the app error envelope.
- [ ] No per-op CLI command is added (PO note D.2 — that is #139's debug door).
- [ ] `ruff format`, `ruff check --fix`, `pytest` clean.

## Out of scope
- The chain itself (#137) and the generic op trigger (#139).
- Any command that triggers a single lifecycle stage.

## Review log
- 2026-09-21 PO: split from #106. Carries #106's four already-settled technical
  fixes (F2, F3, F10, F11) because they are all the same surface and shipping
  them together is one coherent change rather than four scattered ones.

## Review log (dev)
- 2026-09-21 dev: started; moved to in-progress.
- 2026-09-21 dev: implemented and committed as `515bb82`. All eight criteria.

  **The verb.** `POST /trees/{name}/sync` (writer) enqueues #137's `sync-tree`
  op; `hrono tree sync <name>` is its client beside `hrono tree maintain`. The
  two stay separate commands on purpose and the docstrings say why — a cold
  build and an update have very different costs, and conflating them is how a
  user pays for a rebuild by accident.

  **The config CLI.** `hrono sources|connections|models|prompts` each get
  `list/get/set/rm`, built from ONE factory: a collection is only a name in the
  CLI, exactly as it is only a descriptor on the server, so a fifth collection
  is a line in a loop rather than a fifth command module. Plus `hrono jobs
  list|get`, where `get` renders #132's `result` — which is what makes one verb
  over six stages acceptable rather than a black box.
  `set` takes JSON from `-f` or stdin and PUTs it, so writing config is
  declarative.

  **No per-op CLI command**, per PO note D.2 — and there is a test that fails if
  one appears, asserting `propagate`, `repair`, `monitor`, `settle` and `update`
  are absent from `hrono tree --help`. A convention nobody can check is a
  convention that erodes.

  **The three surface defects, all driven against a REAL running server** on
  `--port 8299`, not only unit-tested:
  ```
  F3 hint      hrono profile add local --server http://127.0.0.1:8299 ...
  F2 PUT new   PUT /prompts/live -> 200, GET -> 200   (was 404)
  F11 envelope {"error":{"code":"validation-error","message":"invalid request",
                "details":{"errors":[{"loc":["query","levels"], ...}]}}}
  the verb     POST /trees/default/sync -> {"job_id":"job_5d81..."}
               GET /jobs/<id> -> op "sync-tree", status pending
  ```
  F11 needed a `RequestValidationError` handler: body validation already raised
  our `Invalid` from inside the registry engine, but a bad QUERY parameter
  escaped as FastAPI's raw `{"detail": [...]}`, so a client had to parse two
  shapes depending on which half of the request was wrong.

  **On PUT creating**: `POST` keeps its create-only meaning and still 409s on
  conflict, which a test pins. The two verbs now mean different things on
  purpose rather than by omission.

  Tests (19 new, 877 total) across two files. Mutations, all killed: sync
  enqueuing `maintain`, sync open to readers, the query handler removed, the
  hint hardcoded again, `set` POSTing instead of PUTting, `jobs get` hiding the
  result, and the name not defaulted from the path.

  **One self-inflicted scare worth recording:** my mutation harness backed files
  up by basename, and `registry/commands.py` and `jobs/commands.py` collide —
  the restore wrote one over the other and I had to rewrite the file. It was
  caught immediately by an ImportError, nothing was committed, but a harness
  that can silently destroy a source file is worth not repeating: back up by
  full path.

  Gate clean: `ruff format`, `ruff check --fix`, `pytest` **877 passed**.
- 2026-09-21 qa: **FAIL — back to todo.** The surface is right and the live
  evidence is real. Two mutations I tried survive, and the first one matters
  because this ticket changed which path is the PRIMARY write path.

  **Blocking — nothing pins that the validation hook runs on PUT.**
  ```
  mutation: delete `_run_hook(...)` from replace_item (engine.py:81)
  result:   881 passed
  ```
  The hook is what checks a connection's credential and a source's
  reachability — `_validate_anthropic` hits the list-models endpoint,
  `_validate_claude_code` (#107, closed yesterday) probes that the CLI runs,
  `git_validation` checks the repo. It runs on POST and is covered there.

  Before this ticket that was almost enough, because PUT could only replace an
  existing row. **Now PUT creates, and `hrono sources set` uses PUT** — so the
  path a user actually types to register a source is the one path whose
  validation nothing asserts. If that hook is ever dropped from `replace_item`,
  an unreachable source or an invalid connection is accepted silently and the
  user learns about it at sync time, hours later. That is the exact failure mode
  #107 was praised for closing, reopened through a different door.

  Fix: one test per direction — a PUT that CREATES with a config the hook
  rejects must fail, and a PUT that REPLACES with a rejected config must fail.
  The registry tests already have a descriptor with a hook to borrow.

  **Also unpinned, not blocking on its own — fold it in:** `hrono <collection>
  rm` prints "Reset" for a seeded default and "Deleted" otherwise, and
  collapsing that to always "Deleted" leaves the suite green. It is only
  output, but it is output that tells a user whether their config is gone or
  back to its default, which is a different thing to know.

  **What I verified as PASSING (need not be redone):**
  - Gate: 241 files formatted, ruff clean, **881 passed**.
  - **The live-server evidence is the right kind and I re-read it carefully.**
    All four surface defects were driven against a real `hrono serve --port
    8299`, not only through the test client: the hint printed `:8299`, a PUT to
    a name that did not exist returned 200 and was then readable, a bad query
    parameter came back in the app envelope, and the verb enqueued a `sync-tree`
    job that `GET /jobs/{id}` confirms. F3 in particular could not have been
    caught any other way — the bug was in a string only the real startup path
    prints.
  - Mutations dev ran, re-run by me, plus two of mine: PUT skipping VALIDATION
    (as opposed to the hook) does fail a test, so the body-shape half is
    covered.
  - **The no-per-op-command rule is pinned by a test**, asserting the five stage
    names are absent from `hrono tree --help`. A convention that cannot be
    checked erodes; this one can.
  - One factory for four collections is the right shape — a fifth collection is
    a line in a loop, matching how the server already treats them as one engine
    plus four descriptors.
  - `jobs get` rendering `result` is what makes one verb over six stages
    acceptable rather than a black box, and it is tested both ways (a run that
    reported, and one that did not).
  - Dev's note about the mutation harness clobbering a source file by basename
    collision: caught by an ImportError, nothing committed, tree clean. Worth
    the write-up.
- 2026-09-21 dev: **re-picked up after qa's FAIL**; fixed. Tests only — no
  production code changed, so everything qa passed stands.

  **qa's finding is the right one and the reasoning is what makes it
  blocking.** The validation hook was already running on PUT; what was missing
  is that nothing asserted it. That was nearly harmless while PUT could only
  replace — and this ticket is exactly what changed it, because PUT now CREATES
  and `hrono <collection> set` uses PUT. The path a user types to register a
  source was the one path whose validation was unpinned, and the hook is what
  checks a connection's credential (#107's CLI probe, the anthropic key probe)
  and a git source's reachability.

  Two tests, one per direction, on the engine's own hooked descriptor: a PUT
  that CREATES with a config the hook rejects must fail AND leave nothing
  behind (asserted with a follow-up GET returning 404), and a PUT that REPLACES
  with a rejected config must fail AND leave the old value intact. Deleting
  `_run_hook` from `replace_item` now fails both.

  Also folded in, as qa asked: `hrono <collection> rm` reporting "Reset" for a
  seeded default versus "Deleted" otherwise is pinned. It is only output, but it
  is the output that tells a user whether their config is gone or back to its
  default.

  While there I re-ran the PUT-creates mutation at full scope — `if False` in
  place of the create branch fails 2 in `tests/server`. My earlier narrow run
  missed it because the test lives in `test_operator_surface.py`; scoping a
  mutation run too tightly reports a survivor that is not one.

  Gate clean: `ruff format`, `ruff check --fix`, `pytest` **884 passed**.
  Handing back to verifying.
- 2026-09-21 qa: **PASS — to po-review.** Both findings closed.

  My mutation, re-run: deleting `_run_hook` from `replace_item` now fails 2.
  The construction is right in a way I did not specify — the create-direction
  test asserts a follow-up GET returns 404, so a rejected PUT is proven to have
  left NOTHING behind rather than merely returning an error; the replace
  direction asserts the old value survived. Those are the two ways a failed
  validation could still corrupt config, and both are covered.

  The `rm` wording is pinned both ways. And dev's note about scoping a mutation
  run too tightly is worth keeping: `if False` on the PUT create branch looked
  like a survivor only because the run excluded `tests/server`. A mutation
  report is only as good as its scope.

  Everything in my previous PASS list stands, including the live-server evidence
  for all four surface defects.

  Gate re-run by me: **884 passed**, ruff clean. Commit is test-only and atomic.

## Review log (PO)
- 2026-09-21 PO: **PASSES — closed to done.** All eight criteria met.

  **This is the ticket that makes hrono's differentiator reachable.** Every
  piece of incremental update has been implemented and tested for weeks, and
  until today a user who changed their code had exactly one supported option: a
  full rebuild. `hrono tree sync <name>` is the whole decision, delivered.

  The four surface defects shipping with it is the right grouping — they are one
  surface and a user meets them in one sitting. F3 in particular is the kind of
  defect that decides whether someone keeps going: the single copy-pasteable
  line in hrono's first run pointed at a port nothing was listening on.

  **Driving all four against a real `hrono serve` rather than only the test
  client is what I most want to see repeated.** F3 could not have been caught
  any other way — the bug was in a string only the real startup path prints.
  "It actually works, end to end" is the first line of the product bar and this
  is what honouring it looks like.

  **qa's kickback was correct and its reasoning is the part to keep.** The hook
  was running; nothing asserted it. That was nearly harmless while PUT could
  only replace — and this ticket is precisely what changed it. A change that
  makes an existing untested path load-bearing has effectively introduced the
  risk, even though it touched none of that code. Worth remembering when
  reviewing anything that reroutes a call path.

  No new work spun off. The stage names being absent from `hrono tree --help`
  is pinned by a test, which is how D.2 stays true after I stop watching.
