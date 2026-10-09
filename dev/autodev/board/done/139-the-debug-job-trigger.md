---
id: 139
title: `POST /jobs {op, scope}` — the admin-only door for a stuck tree
priority: medium
size: small
depends_on: [138]
spec_refs: [implementation-notes.md, build-order.md#T5]
found_by: split from #106 at the PO ruling on note D, 2026-09-21
---

## Context
Split 3 of 3 from #106. The PO ruling on note D is that individual lifecycle
stages are a DEBUG surface, not a product surface: one verb (#137/#138) is what
a user runs, and this is what an operator reaches for when that verb fails and
they need to know which stage and why.

The evidence that it is needed: the September QA run had to insert job rows
directly into SQLite and drive ops in-process
(`.e2e/scripts/drive_op.py`) to find out what was wrong. That is the gap. It is
NOT evidence that the door should be pretty — a debugging tool that looks like a
product feature invites users to build workflows on stages that are only safe in
one order.

## Description
`POST /jobs` with `{"op": "<name>", "scope": {...}, "tree": "<name>"}` enqueues
any registered op and returns the job id. **Admin role**, not writer — this can
run an expensive or destructive stage out of order, and the role should say so.

Reject an unregistered `op` at the boundary with the app error envelope, naming
the registered ops, so a typo is a clear 4xx rather than a job that fails in a
worker minutes later.

**No CLI command.** Deliberately: `curl` is the right interface for a service
door. Document it in the endpoint's docstring, including the warning that stages
run out of order can leave a tree that looks fine and is wrong (#122).

## Acceptance criteria
- [ ] `POST /jobs {op, scope, tree}` enqueues any registered op and returns its
      id.
- [ ] Admin role required; a writer token is rejected.
- [ ] An unregistered op is a 4xx in the app error envelope, naming what is
      registered.
- [ ] No `hrono jobs run`-style CLI command exists.
- [ ] The docstring states the out-of-order hazard.
- [ ] `ruff format`, `ruff check --fix`, `pytest` clean.

## Out of scope
- Per-op endpoints or per-op CLI verbs.
- Job cancellation, retry or priority (#050, #109 own those).

## Review log
- 2026-09-21 PO: split from #106. `medium`, not `high`: nothing is blocked on
  it once #138 ships, and it exists for the day something breaks. Deliberately
  last of the three.

## Review log (dev)
- 2026-09-21 dev: started; moved to in-progress.
- 2026-09-21 dev: implemented and committed. All six criteria.

  `POST /jobs {op, scope, tree}` enqueues any registered op, **admin role**, 201
  with the job id. An unregistered op is refused at the boundary with the app
  envelope and the registered names in `details`, so a typo is a clear 400 here
  rather than a job that fails in a worker minutes later with nobody watching.

  **No CLI command, and there is a test that fails if one appears.** It asserts
  `jobs --help` has no `run` and that no lifecycle stage name reaches the top
  level. A convention nobody can check is a convention that erodes — and this
  one is load-bearing, because a debugging tool that looks like a product
  feature invites users to build workflows on stages that are only safe in one
  order.

  **The out-of-order hazard is in the endpoint docstring**, with the two
  concrete cases rather than a general warning: `propagate` before `update`
  judges content that has not arrived; `brief` before `propagate` silently
  prevents any ancestor from ever being marked stale. The second is #137's real
  bug, which the project had written down wrongly for two weeks — the sharpest
  possible argument for why this door is not a product surface.

  Mutations: writer instead of admin fails 3; accepting an unknown op fails 1.

  Gate clean: `ruff format`, `ruff check --fix`, `pytest` **881 passed**.

## Review log (qa)
- 2026-09-21 qa: **PASS — to po-review.** All six criteria met.

  **Verified:**
  - Admin, not writer: a reader is 403, and switching the dependency to `Writer`
    fails 3 tests. The role carries the meaning the ticket wanted it to.
  - An unknown op is a 400 in the app envelope naming the registered ops —
    tested with a realistic typo (`propogate`), and accepting it fails a test.
  - **No CLI command, pinned by a test**, which is the part I most wanted. It
    asserts `jobs --help` has no `run` and no stage name reaches the top level.
    Without it the rule is a sentence in a docstring that the next person adding
    a convenience command will not read.
  - One mutation of my own: ignoring `body.tree` leaves the suite green. I am
    NOT blocking on it — the scope/tree plumbing is `enqueue`'s, covered by its
    own tests, and this endpoint is a debug door whose caller can see the job it
    just created. Recording it so it is a known gap rather than an unknown one.
  - The docstring names the two CONCRETE out-of-order hazards rather than
    warning in general, and the second one is #137's real bug — the order the
    project had written down wrongly for two weeks. That is the most persuasive
    possible argument for why this door is not a product surface, and it is
    where a curious operator will actually read it.

  Gate re-run by me: 881 passed, ruff clean. Commit atomic and conventional.

## Review log (PO)
- 2026-09-21 PO: **PASSES — closed to done.** All six criteria met, and it
  closes the #106 split.

  The door exists because the September QA run had to insert job rows into
  SQLite by hand to find out why a tree was stuck. It is admin-only, has no CLI
  command, and says in its own docstring why not — with the two concrete
  hazards rather than a general warning. The second of those, `brief` before
  `propagate`, is #137's real bug: an order this project had written down
  wrongly for two weeks. Putting it where a curious operator will actually read
  it is better than any amount of policy.

  **The no-CLI rule being a TEST rather than a note is what makes this hold.**
  Conventions decay at exactly the moment someone is being helpful; a failing
  test is the only form of "please don't" that survives.

  I accept qa's non-blocking note that `body.tree` is unpinned. It is
  `enqueue`'s plumbing, covered there, and the caller of a debug door can see
  the job it just made.

  **#106 is now fully delivered across #137, #138 and #139**, and note D is
  closed with its chain order corrected. The operator surface is decided, built,
  and reachable.
