---
id: 098
title: Data locations must hang off the database, not the process cwd
priority: high
size: medium
depends_on: []
spec_refs: [build-order.md#T12, implementation-notes.md]
found_by: e2e manual QA 2026-09-03 — .e2e/FINDINGS.md F25, F6, F32
---

## Context
`ingest/sync.py:24` and `ingest/split_op.py:36` hardcode
`_CACHE_ROOT = Path(".hrono/cache/sources")`, and `db/database.py`
`DEFAULT_PATH = Path(".hrono/hrono.db")` — all relative to the current working
directory. `serve` and `reset` have no override flag.

## Description
**F25 — one database, several divergent caches.** The e2e server ran with cwd
`.e2e/run`, an in-process op driver with cwd `.e2e`. Two full clone sets
appeared for the same database, three commits apart:

```
  run/.hrono/cache/sources/itsdangerous -> 84a036f   license.rst present
      .hrono/cache/sources/itsdangerous -> 506eb72   license.rst absent
  run/.hrono/cache/sources/chalk        -> 661317e   utilities.js present
      .hrono/cache/sources/chalk        -> bce99a4   utilities.js absent
```

Diffing the database against the stale cache invented four changes, including a
**reversed rename** (`moved source/utilities.js (was source/util-helpers.js)`)
and a `new docs/license.rst` for a file deleted two commits earlier. So starting
`hrono serve` from a different directory silently re-clones every source and can
undo the last update's classifications.

**F6** — no `--db` flag anywhere, so the database location is "whatever cwd the
operator was in".
**F32** — `hrono reset` deletes the three database files and leaves
`.hrono/cache/` (10 MB of clones) behind, despite its help text claiming it
destroys ingested content; a "fresh start" then diffs against orphaned clones.

Work:
- Resolve the cache root from the database's own directory (or an explicit data
  root), never cwd; thread it through `sync`, `split`, `diff`, `update`.
- Add `--db PATH` (and/or `HRONO_DB`) to `serve` and `reset`.
- `reset` removes the cache too, or says plainly that it keeps it.

## Decision (2026-09-12, dev — technical call, no PO input needed)

The database path is the anchor: the cache root becomes
`<db_parent>/cache/sources`, resolved once at startup and threaded through
`sync`, `split`, `diff`, `update` as an explicit argument — no module-level
cwd-relative constant. `serve` and `reset` take `--db PATH` (env `HRONO_DB`).
`reset` removes the cache alongside the database, matching its own help text.

## Acceptance criteria
- [ ] Two processes with different cwds but the same `--db` use the same cache.
- [ ] `serve --db` and `reset --db` work and are documented in `--help`.
- [ ] `reset` leaves no orphaned ingest state (or documents what it keeps).
- [ ] `ruff format`, `ruff check --fix`, `pytest` clean.

## Review log
- 2026-09-15 dev: started; moved to in-progress.
- 2026-09-15 dev: implemented and committed as `f8acde7`, per the Decision
  block. No module-level cwd-relative path is left in `src/`
  (`grep -rn "CACHE_ROOT\|\.hrono/cache" src/` matches only `paths.py`).

  **How the path is threaded** (an argument all the way down, not a new global):
  ```
  serve --db PATH / $HRONO_DB / default
        -> paths.database_path()      resolved ONCE, absolute
        -> lock.exclusive(db_path)    lock sidecar sits with the database
        -> create_app(db_path=...)
             -> paths.cache_root(db_path)  = <db parent>/cache/sources
             -> Worker(..., cache_root=...)
                  -> JobContext(database, cipher, cache_root)
                       -> sync / split / update: context.cache_for(name)
  ```
  New `src/hrono/paths.py` owns the two derivations and nothing else.
  `JobContext.cache_root` is `Path | None`; `cache_for` RAISES `Internal` when
  it is None rather than falling back to a guessed location, so no code path can
  quietly resolve a cache against the working directory again. (None stays legal
  only for contexts whose ops never touch the cache — brief, condense, embed,
  cluster — which is most of the 110 test constructions.)

  **`--db` and the lock agree** (the ticket's point 2): `serve` locks
  `exclusive(db_path)`, so the sidecar is `<db>.lock` beside the chosen file —
  verified on disk below. `reset` now removes it too, plus the cache: `sidecars`
  gained `.lock` and `targets` gained `<db parent>/cache`, so "leaves no
  orphaned ingest state" is true rather than aspirational (F32). The wipe still
  refuses any path that is not `.hrono/hrono.db`, so the recursive delete is
  bounded by that guard.
  `--db` (env `HRONO_DB`) is on `serve`, `reset` AND `admin reset-token` — a
  recovery command that depends on the operator's directory has the same hazard.

  **Two-cwd proof, driven for real** (scratch only; `.e2e/` untouched). One
  database at `data/.hrono/hrono.db`, four empty working directories:
  ```
  serve from a/  --db data/.hrono/hrono.db  -> health 200
      on disk:   data/.hrono/hrono.db  +  data/.hrono/hrono.db.lock
      (nothing under a/)                      <- lock follows --db
  POST /sources repo=file://.../remote        <- 201, through the API
  [server stopped]
  drive sync+split from b/   cache root -> data/.hrono/cache/sources   2 sections
  drive sync     from c/     cache root -> data/.hrono/cache/sources
  drive diff     from c/     changes ()                                <- F25 gone
  serve from d/  --db (same) -> health 200, GET /sources returns the repo
                                registered by the server in a/
  every cache tree on disk:  data/.hrono/cache/sources   (exactly one)
  ls -a a/ b/ c/ d/       :  all four EMPTY — no .hrono anywhere
  clone commit unchanged across all of it
  reset --force --db (run from a/) removed:
      data/.hrono/hrono.db, data/.hrono/hrono.db.lock, data/.hrono/cache (136K)
  ```
  Under the old code b/ and c/ would each have grown their own
  `.hrono/cache/sources`, which is exactly how the September run got two clone
  sets three commits apart and a reversed rename.

  Tests (13 new, 684 total): `tests/test_paths.py` pins the resolution order
  (`--db` > `$HRONO_DB` > default), that the result is absolute, and that a
  later `chdir` cannot move it or its cache; `test_split_op.py::test_two_
  working_directories_share_one_cache` syncs from one cwd and splits from
  another and asserts exactly ONE clone tree exists and neither cwd grew a
  `.hrono`; `..._no_phantom_change` re-syncs from a third cwd and asserts
  `diff` returns `()`; `test_cli.py` covers `serve --db`, `$HRONO_DB`, `--db`
  in both `--help` texts, and `reset --db` wiping the named database + cache
  from an unrelated cwd; `test_reset.py` covers the cache and `.lock` removal.
  The ingest tests now build their context with `tests/context.py::job_context`
  (the anchor the worker uses) and the `monkeypatch.chdir` they needed for the
  cache is GONE from `test_sync.py` and `test_split_op.py` — they pass with no
  cwd manipulation at all, which is the property itself.

  Not touched, as instructed: #099 (batch counter), #114, #113, #102, #103,
  #105, #118. `.e2e/` was read only.
  Gate clean: `ruff format` (225 files unchanged), `ruff check --fix` (all
  checks passed), `pytest` **684 passed**. Handing off to verifying.
- 2026-09-15 qa: **FAIL — back to todo.** The de-cwd-ing itself is correct and
  complete, and I reproduced the two-cwd proof independently: the property this
  ticket exists to establish holds. One blocking finding, in the new recursive
  delete, found exactly where this ticket's risk is concentrated.

  **What I verified as PASSING (need not be redone):**
  - Gate re-run by me on `f8acde7`: `ruff format --check` 225 files unchanged,
    `ruff check` clean, `pytest` **684 passed** in 37.5s.
  - **The de-cwd-ing is complete.** `grep -rn "CACHE_ROOT\|\.hrono/cache" src/`
    now matches NOTHING (not "only paths.py" — `paths.py` builds the path from
    components, so the literal is gone entirely; the property is stronger than
    claimed). Hunting wider, the only cwd-relative constructs left in `src/`
    are `db/database.py:23 DEFAULT_PATH`, which exists to be resolved by
    `paths.database_path`, and `profile/store.py:75 Path.home()`, which is not
    cwd. No `Path.cwd()`, no `os.getcwd`, no other relative literal.
  - **The two-cwd proof, driven for real and not trusted.** One database at
    `data/.hrono/hrono.db`, four empty working directories, a real git remote:
    `serve` from `a/` with `--db` put the lock sidecar at
    `data/.hrono/hrono.db.lock` (beside the database, NOT in cwd) and left `a/`
    completely empty; a source registered through the API and a maintain job
    produced `data/.hrono/cache/sources`; a SECOND `serve` from `d/` against the
    same `--db` saw the same sources and grew no second cache; and two
    in-process drivers from `b/` and `c/` both resolved
    `cache_for("repo")` to the same absolute path, re-synced, and
    `diff` returned `()` from both — no phantom changes. Final state: exactly
    ONE cache tree on disk, all four cwds empty, clone commit unchanged
    throughout. F25's mechanism is closed.
  - **`JobContext.cache_root`'s None branch is unreachable in production.**
    There is exactly one `JobContext` construction in `src/`
    (`jobs/worker.py:177`), fed from `Worker(cache_root=...)`, fed from
    `server/app.py:131 cache_root(db_path)`, fed from the single production
    `create_app` call (`cli.py:136`) with `database_path(db)`, which always
    returns a Path. So the `Internal` cannot be raised by any user action — it
    is a genuine programming-error guard, correctly placed.
  - **Upgrade compatibility: no re-clone, and that is design rather than luck.**
    I drove it: from a pre-upgrade install whose cwd holds
    `.hrono/hrono.db` and `.hrono/cache/sources`, the new derivation resolves
    to the SAME cache directory and the existing clones are still readable.
    That is exact, because the old constant was `.hrono/cache/sources` relative
    to cwd and the old default database was `.hrono/hrono.db` relative to the
    same cwd — so `<db parent>/cache/sources` is the identity on the old
    default layout. The `.e2e` database at `.e2e/run/.hrono/hrono.db` is a
    no-op for that same reason, and the stale second cache at
    `.e2e/.hrono/cache` simply stops being read, which is the intended repair.
    Only an F25-shaped install (two caches already) orphans one, and the
    orphaned one is the bug.
  - **The tests really did stop manipulating cwd, without weakening.**
    `test_sync.py` had two `monkeypatch.chdir` calls at `306f0e2` and now has
    ZERO; its assertions are preserved and only the expected cache location
    moved to the anchored path. `test_split_op.py` still has four, but all four
    are inside the two NEW tests where changing directory IS the thing under
    test. `tests/context.py::job_context` builds the context the way the worker
    does, so the tests exercise the production anchor.
  - **Mutation-verified by me** in a worktree at `f8acde7` (`PYTHONPATH`
    asserted inside it): `cache_for` reverted to a cwd-relative constant -> 5
    tests fail including `test_two_working_directories_share_one_cache`;
    `database_path` no longer resolving to absolute -> both `tests/test_paths.py`
    cases fail; `.lock` dropped from `sidecars` ->
    `test_reset_removes_the_cache_and_the_lock` fails; the cache dropped from
    `targets` -> 3 tests fail including `test_reset_db_flag_wipes_the_named_
    database`.
  - **The recursive delete is genuinely bounded** — I attacked it hard and it
    held everywhere except the case below. The guard refuses every path whose
    last two components are not `.hrono/hrono.db` (9 name/parent combinations
    tried, only the real one wipes). Unrelated user data in the SAME `.hrono`
    directory survives (it removes five named paths, never the `.hrono` tree):
    `config.toml` and `notes/x.md` were untouched. Siblings outside `.hrono`
    survive. A symlink INSIDE the cache pointing at an outside directory is
    unlinked, not followed — the target and its payload survived. A symlinked
    `.hrono` DIRECTORY is refused, because `database_path` resolves first and
    the resolved parent is no longer `.hrono` — resolution makes the guard
    stricter, not weaker. A relative `--db` is resolved to absolute before the
    guard sees it.

  **Blocking defect — `src/hrono/admin/reset.py:57-63`: if the cache is a
  symlink, `reset` destroys the database, deletes nothing else, prints nothing,
  and exits on an unhandled `OSError`.**
  `shutil.rmtree` refuses a top-level symlink by design
  ("Cannot call rmtree on a symbolic link"). `targets` returns
  `(db, -wal, -shm, .lock, cache)` and the loop deletes in that order, so by
  the time the cache raises, the database and all three sidecars are already
  gone. `cli.reset` (`cli.py:104-107`) catches only `AppError`, so nothing
  handles it. Driven through the real CLI:

  ```
  $ hrono reset --force --db <...>/.hrono/hrono.db     # .hrono/cache -> elsewhere
  exit: 1   exception: OSError   output: ''
  db gone: True                      <- destroyed
  cache still fully intact: ['sources', 'repo', 'f.txt']
  ```

  The operator ends up with no database, an orphaned cache, and a stack trace
  instead of the "Removed:" report — which is precisely the F32 state this
  ticket exists to remove, now with data loss on top. This is NEW in this
  commit: before it, `reset` never touched the cache and never called `rmtree`.

  A symlinked cache is not exotic — moving a clone cache that grows to
  gigabytes onto a bigger volume is an ordinary ops move, and the ticket's own
  evidence is that the cache reaches 10 MB on three small repos.

  The same shape applies to ANY `OSError` in that loop (a read-only file in the
  cache, permission denied, a file held open): partial destruction, no report,
  no clean message. Two things to fix, both small:
  1. decide the symlink policy explicitly — either refuse with a clear message
     (`NotHronoDatabase`-style, so `cli_message` prints it), or `unlink()` the
     link itself rather than `rmtree` it, which is what "remove the cache
     beside the database" means when the cache is a link;
  2. make a failure in the loop an `AppError` (or catch `OSError` and re-raise
     as one) so `cli.reset` prints a clean message, and report what WAS removed
     before exiting — an operator whose database has just been deleted must not
     be told about it by a traceback.
  Please add a regression test for a symlinked cache directory asserting the
  command exits cleanly, says what happened, and leaves the symlink target
  intact.

  **Non-blocking notes:**
  - `src/hrono/server/app.py:92` — `create_app` defaults `db_path` to the
    RELATIVE `DEFAULT_PATH`, so `create_app(connection=...)` without a
    `db_path` (the injected-connection form) builds a Worker with a
    cwd-relative `cache_root(.hrono/hrono.db)`. No production caller does this —
    `cli.py:136` is the only one and it passes the resolved path, so the
    acceptance criterion holds — but it is the one remaining route by which a
    cwd-relative cache can reach a worker, and the design you state ("None
    rather than a guessed location") would be better served by passing
    `cache_root=None` when a connection is injected without a database path.
  - The Review-log grep claim says the pattern "matches only `paths.py`"; it
    now matches nothing at all. The property is stronger than claimed, so this
    is only an imprecision worth correcting for the record.
  - `--db` is on `serve`, `reset` and `admin reset-token`, all three documented
    in `--help`; putting it on the recovery command too is the right instinct.

  Commit `f8acde7` is a clean Conventional Commit, atomic, 22 files, no stray
  changes; the `.gitignore` line is still the pre-existing uncommitted one.
  `.e2e/` untouched — read only, database mtime still Sep 3 20:54:49. Worktree
  removed, servers stopped, tree clean.
- 2026-09-15 dev: **re-picked up after qa's FAIL**; fixed as `de5ef38` on top of
  `f8acde7`. Nothing qa passed was reverted.

  **Blocking defect — the recursive delete met a symlinked cache.** `targets`
  removes in order (db, -wal, -shm, .lock, cache), `shutil.rmtree` refuses a
  top-level symlink by design, and `cli.reset` caught only `AppError`: the
  database and all three sidecars were already gone when the `OSError` escaped,
  so the operator got exit 1, empty stdout, no database and an intact cache —
  F32's state, reintroduced by the fix for F32. Two changes, both in
  `admin/reset.py`:

  1. **Symlink policy: REFUSE, before anything is deleted** (`LinkedCache`,
     `code: linked-cache`, raised by `_refuse_linked_cache` as the first thing
     `wipe` does after the path guard). Why refuse rather than `unlink()` the
     link: the recursive delete is only safe because the path guard bounds it
     inside a `.hrono` directory, and a link points outside that bound — hrono
     cannot know what else lives at the other end. Unlinking would leave the
     clones on disk while the command claims to destroy ingested content, which
     is precisely the false claim F32 is about; refusing tells the truth and is
     reversible. The message names the link, the directory it escapes, what to
     do ("remove or re-point the link, then reset again") and that **nothing
     was removed**; `details` carry the link and its target. Documented in the
     module docstring as the behaviour, not an accident.
  2. **Any `OSError` in the loop becomes an `AppError` that still reports.**
     `ResetIncomplete` (`code: reset-incomplete`) carries
     `details["removed"]` (what actually went) and `details["failed"]`; `wipe`
     now accumulates `removed` as it goes instead of returning the plan. The
     CLI prints that list through the SAME `_report_removed` helper the success
     path uses, then the error, then exits 1 — so a half-done destructive
     command still hands over the list recovery is planned from. Covers
     permissions, a busy file and a full disk, not just symlinks.
     `_remove` also no longer sends a symlink-to-a-directory to `rmtree`
     (`path.is_dir() and not path.is_symlink()`), so any link that reaches it
     is unlinked rather than followed.

  **app.py:92 — taken, as qa suggested.** `create_app(connection=...)` now
  passes `cache_root=None` (`cache_root(db_path) if owned else None`): an
  injected connection says nothing about where its file is, so there is no
  anchor, and an ingest op raises `Internal` instead of resolving a
  cwd-relative cache. That closes the last route by which a cwd-relative cache
  could reach a worker. The docstring says so.

  Tests (4 new, 688 total), each verified regression-grade by restoring the old
  `wipe` body and watching them fail:
  `test_a_symlinked_cache_is_refused_before_anything_is_deleted` (raises
  `LinkedCache`; database still there, clones still there),
  `test_the_cli_refuses_a_symlinked_cache_without_a_traceback` (exit 1, no
  traceback, "symlink" in the output, nothing destroyed),
  `test_a_wipe_that_stops_part_way_still_reports_what_it_removed` (a
  `PermissionError` on the `.lock` -> `ResetIncomplete` whose
  `details["removed"] == [db]`), and
  `test_the_cli_prints_the_removals_of_a_partial_wipe` ("Removed:" + the
  database + "Permission denied", no traceback).

  **Real CLI verification** (scratch; `.e2e/` read-only, its database mtime is
  still `2026-09-03 20:54:49`): `.hrono/cache` symlinked to another directory ->
  `hrono reset --force --db ...` prints the refusal, exit 1, `hrono.db` still
  present, `volume/cache/sources/repo/f.txt` still readable. Replacing the link
  with a real directory and re-running -> "Removed:" lists the database and the
  cache, exit 0, only the empty `.hrono` directory left.

  **Suite timing, checked rather than assumed** (the 600 s timeout reported
  against this tree): no hang. Timed full runs on this exact tree gave
  **688 passed in 36.59s** and 37.33s, exit 0, with no stray `hrono serve` or
  `pytest` processes, no leftover `*.db.lock`, and nothing listening on the
  verification ports. Nothing in this round can block: the new CLI tests use
  Typer's in-process `CliRunner` (no subprocess), always pass `--force` (no
  confirm prompt waiting on stdin), and `reset` never takes the database
  flock. The coordinator has since confirmed the timeout was a collision with
  my own concurrent gate run.

  **Correction to my previous entry**: I wrote that
  `grep -rn "CACHE_ROOT\|\.hrono/cache" src/` matches "only `paths.py`". It
  matches NOTHING — `paths.py` builds the path from parts and never spells the
  literal. qa's stronger statement is the accurate one.

  Not touched: #099 (batch counter), #114, #113, #102, #103, #105, #118.
  Gate clean: `ruff format` (225 files unchanged), `ruff check --fix` (all
  checks passed), `pytest` **688 passed**. Handing back to verifying.
- 2026-09-15 qa: **PASS — to po-review.** The blocking finding is fixed, and
  fixed the right way: the refusal happens before anything is touched, not
  after. I re-drove my original repro and everything survives. Two unpinned
  behaviours reported below, neither blocking.

  **1. Ordering — proven, not merely raised.** My exact original repro
  (`.hrono/cache` a symlink to another directory), through the real CLI:

  ```
  $ hrono reset --force --db <...>/.hrono/hrono.db
  exit 1, no traceback
  "refusing to reset: the cache <...>/.hrono/cache is a symlink, so what it
   would delete is not bounded by <...>/.hrono. Remove or re-point the link,
   then reset again. Nothing was removed."
  hrono.db True | hrono.db-wal True | hrono.db-shm True | hrono.db.lock True
  cache link still present: True | link target intact: [sources, repo, f.txt]
  ```

  Every one of the five paths that used to be destroyed is untouched, and the
  message is accurate — "Nothing was removed" is literally true. At `f8acde7`
  this same command left the database and all three sidecars gone and printed
  nothing at all.

  **2. Evasion — the guard holds on every variant I could build.** Refused, with
  the database and all sidecars intact in each case: a RELATIVE symlink; a
  BROKEN/dangling link (`is_symlink()` is true even though `exists()` is false,
  so it cannot slip through `targets`' existence filter); and a link pointing at
  a directory INSIDE the same `.hrono` (conservative, and right — the guard is
  about boundedness, not about where the link happens to land). A hardlinked
  database file behaves as hardlinks inherently do: the alias survives, which is
  not an escape.

  **TOCTOU is structurally safe, not merely unlikely.** I drove `_remove`
  against a symlink-to-directory: it unlinks the link and leaves the target and
  its payload intact (`reset.py:99`, `path.is_dir() and not path.is_symlink()`).
  So even a swap between the check and the loop cannot delete anything outside
  the bound — the worst case is an unlinked link, and `shutil.rmtree` would
  refuse it anyway and now surface as `ResetIncomplete` WITH the report.

  One boundary worth recording rather than fixing: the check is on the cache
  directory itself, so a symlink one level deeper (`cache/sources`, or
  `cache/sources/<name>`) is not refused — `rmtree` unlinks it without following
  it, so nothing outside is deleted, but the clones at the other end survive
  while the command reports plain success. I do NOT think this should be
  "fixed": a deep scan would have to refuse a cache containing ANY symlink, and
  cloned repositories legitimately contain symlinks, so it would make `reset`
  refuse on ordinary corpora — a far worse outcome than an orphan in a
  contrived layout. The shallow boundary is the right trade; it is just worth a
  sentence in the module docstring saying the guard covers the cache root, not
  the tree beneath it.

  **3. `ResetIncomplete`'s report — exactly what the finding asked for.** Driven
  with a genuine mid-loop `OSError` (`chmod 0o500` on `cache/sources`, so the
  children cannot be unlinked), through the real CLI:

  ```
  Removed:
    .../.hrono/hrono.db
    .../.hrono/hrono.db-wal
    .../.hrono/hrono.db-shm
    .../.hrono/hrono.db.lock
  reset stopped at .../.hrono/cache: Permission denied
  exit 1, no traceback
  ```

  Through the library: `code=reset-incomplete`, `status=500`,
  `details['removed']` = the four that actually went, `details['failed']` =
  `cache`. I checked the report against the disk: removed ∪ still-present is
  exactly the full candidate set, so the list is accurate rather than the plan.
  That was the specific harm — a destroyed database with no report — and it is
  closed.

  **4. `app.py:141` (`cache_root(db_path) if owned else None`) — correct, and
  it is a programming-error guard a user cannot trigger into a 500.** I built an
  app from an injected connection, registered a real git source and forced a
  `sync` job onto its worker from a cwd where a stray cache would be visible:
  the JOB fails with `no cache root: this job context cannot run ingest ops`,
  the server stays up (`/health` 200), and **no cwd-relative `.hrono/cache` is
  created**. So the `Internal` is absorbed by the worker's own failure handling
  (`worker.py:_execute`) into a readable failed job — never a 500 — and the last
  route by which a cwd-relative cache could reach a worker is gone. No injected-
  connection test broke; the suite is green at 688.

  **5. No regression on what I passed at `f8acde7`** (spot-checked, not redone):
  `grep -rn "CACHE_ROOT\|\.hrono/cache" src/` still matches nothing; the path
  guard after its refactor into `_refuse_foreign_path` still refuses 8 of 9
  name/parent combinations and wipes only `.hrono/hrono.db`; unrelated data
  beside the database (`config.toml`, `outside.txt`) still survives a wipe; and
  the cache root resolves to the same absolute path from two different working
  directories with no stray `.hrono` in either.

  **Mutation-verified by me** in a worktree at `de5ef38` (`PYTHONPATH` asserted
  inside it). Caught:
  - the symlink refusal moved AFTER the delete loop ->
    `test_a_symlinked_cache_is_refused_before_anything_is_deleted` and
    `test_the_cli_refuses_a_symlinked_cache_without_a_traceback` both fail, so
    the ordering — the whole fix — is pinned as ordering and not just as a
    raise;
  - `wipe` reporting the plan instead of what went ->
    `test_a_wipe_that_stops_part_way_still_reports_what_it_removed`;
  - the CLI dropping the partial report ->
    `test_the_cli_prints_the_removals_of_a_partial_wipe`.

  **Two behaviours this commit adds are NOT pinned — reverting either leaves the
  suite green at 688.** I verified both by driving them, so the properties are
  true today; the gap is regression cover:
  - `src/hrono/admin/reset.py:99` — dropping `and not path.is_symlink()` from
    `_remove` (so a symlink-to-directory is handed to `rmtree` again) changes
    nothing in the suite. It is unreachable in the normal flow because
    `_refuse_linked_cache` fires first, which is why nothing covers it; it is
    the defence that makes the TOCTOU case safe, so it is worth a direct unit
    test on `_remove` rather than through `wipe`.
  - `src/hrono/server/app.py:141` — reverting to an unconditional
    `cache_root(db_path)` also leaves the suite green. This one is observable
    (I drove it above: failed job + no stray cache), it is the fix I asked for
    last round, and it protects exactly the property this ticket exists to
    establish, so it should not be the one thing here with no test. A short
    test in `tests/server/` asserting an injected-connection app fails an
    ingest job with that message and creates no `.hrono` in the cwd would pin
    it.
  Neither blocks: my blocking finding and all three behaviours it demanded are
  fixed and pinned, and the e2e re-run's precondition is demonstrably correct.
  Please fold both into the next touch of these files.

  Dev's correction about the grep claim is right and matches what I measured.

  Commit `de5ef38` is a clean Conventional Commit, atomic, 4 files, no stray
  changes; the `.gitignore` line is still the pre-existing uncommitted one.
  `.e2e/` untouched — read only, database mtime still Sep 3 20:54:49. Worktree
  removed, tree clean.

  Gate re-run by me on `de5ef38`: `ruff format --check` 225 files unchanged,
  `ruff check` clean, `pytest` **688 passed** in 36.78s (38.2s wall, no stray
  processes) — the hang scare does not reproduce here either. All four
  acceptance criteria hold. Handing to the PO.
- 2026-09-15 PO: **ACCEPTED -> done.** Two commits (f8acde7 de-cwd-ing +
  de5ef38 the destructive-command fix). Verified independently, including
  driving the destructive command myself — this ticket both introduced and
  fixed data loss, so I did not take the fix on report.

  **Gate re-run by me:** `ruff format --check .` 225 files already formatted;
  `ruff check .` all checks passed; `uv run pytest` **688 passed** in 37.3s.

  **F25 is closed, measured.** Same `--db` from three different working
  directories resolves to ONE cache root
  (`<db parent>/cache/sources`); resolution order is `--db` > `$HRONO_DB` >
  default; the result is absolute; and resolving from a cwd creates no stray
  `.hrono` there. `grep -rn "CACHE_ROOT\|\.hrono/cache" src/` matches **nothing**
  — the literal is gone, not merely centralised — and there is no `Path.cwd()`
  or `os.getcwd` anywhere in `src/`. Anchoring on the database and threading an
  argument (rather than swapping one global for another) is the right shape, and
  `JobContext.cache_root: Path | None` raising instead of guessing is what makes
  the property hold structurally rather than by convention.

  **I drove the destructive command on the exact layout that lost data in round
  one.** A real-looking install with `.hrono/cache` symlinked to an outside
  volume:
  - `hrono reset --force --db ...` -> **exit 1, no traceback**, one clear
    message naming the link, the bound it escapes, what to do, and "Nothing was
    removed."
  - **"Nothing was removed" is literally true**, which I checked byte by byte:
    `hrono.db`, `-wal`, `-shm`, `.lock` all still present with their ORIGINAL
    CONTENT, the link still present, and the outside payload intact. At
    `f8acde7` this same command destroyed the database and all three sidecars,
    printed nothing, and exited on an unhandled `OSError`.
  - Replacing the link with a real directory and re-running -> **exit 0**,
    "Removed:" listing all five paths, only the empty `.hrono` left, and the
    outside volume untouched.

  **The fix is the right one, and the reasoning matters more than the code.**
  Refusing beats `unlink()`: the recursive delete is only safe because the path
  guard bounds it inside `.hrono`, and a link points outside that bound.
  Unlinking would leave the clones on disk while the command claims to destroy
  ingested content — which is exactly the false claim F32 is about. Refusing is
  honest, reversible, and tells the operator what to do. Ordering it BEFORE any
  deletion, rather than handling the error after, is what turns a partial
  destruction into a no-op. `ResetIncomplete` carrying `removed`/`failed`
  through the same report helper as the success path is the right instinct too:
  an operator whose database has just been deleted must not learn about it from
  a traceback.

  All four acceptance criteria hold. The qa bounce was the most valuable one of
  this wave: it found data loss in the fix for a data-loss ticket, in a layout
  (a cache moved onto a bigger volume) that is ordinary ops, not exotic.

  **Rulings:**
  1. **Both unpinned behaviours: deferral ACCEPTED, but filed as a ticket, not
     a note.** I confirmed qa's report rather than trusting it — reverting BOTH
     lines in an isolated worktree (`PYTHONPATH` asserted inside it) leaves the
     suite green at **688 passed**. So both are genuinely uncovered.
     I am not blocking, for a reason I want on the record: neither is an
     acceptance criterion, and neither is reachable in production.
     `reset.py:99` sits behind `_refuse_linked_cache`, which IS pinned as
     ordering; `app.py:141` guards the injected-connection form of
     `create_app`, and `cli.py:136` is the only production caller and always
     passes a resolved path. Both were driven and shown correct. Holding the
     e2e re-run — the thing that finds real defects, as this entire 092-118 wave
     demonstrates — for two tests on unreachable routes is disproportionate.
     But "fold it into the next touch" is not a commitment, it is a hope, and
     that is how a review-requested fix rots. So it is **#119**, `medium`,
     small, with both tests plus the docstring sentence from ruling 2, and it
     states that the next change to either file must carry it.
     I single out `app.py:141` in that ticket: it is the fix qa asked for last
     round, it protects the ticket's central property, and a fix delivered on
     review with no regression cover is precisely the thing that silently
     reverts.
  2. **Shallow symlink boundary: trade CONFIRMED, docstring sentence is
     enough.** I drove it — a link at `cache/sources` (one level below the
     guard) is unlinked without being followed: **the outside payload survives
     intact**, only the report is incomplete (plain success while orphaned
     clones remain at the other end). So this is a reporting gap, not a safety
     gap, in a layout nobody has.
     qa's argument against deepening is correct and I am making it policy:
     cloned repositories legitimately contain symlinks, so a deep scan would
     have to refuse a cache containing ANY link — making `reset` refuse on
     ordinary corpora. **A destructive command that refuses on a normal install
     is a far worse product outcome than an orphan in a contrived one.** Guard
     the bound, not the tree. One sentence in the module docstring recording
     that the guard covers the cache root and not what is beneath it; folded
     into #119 rather than given a card of its own.
  3. **#099 is now the last thing I want before the e2e re-run** — see the note
     below.

  **Re-run readiness.** With #098 closed, the measurement hazard I flagged is
  gone: the run can be driven from any directory as long as every process
  passes the same `--db`, and the old two-cache divergence cannot recur. One
  ticket and one decision remain:
  - **#099** (high, small) — `_next_batch` bumps per changed source instead of
    per run. The re-run exercises `update` repeatedly over three sources, so an
    over-counting batch distorts exactly the incubator ageing the run is meant
    to observe, and via #113 (forced members are never revisited) that damage is
    permanent rather than cosmetic. Cheap; land it first.
  - **The chalk `source/vendor/**` decision** (open with the human PO from
    #104's close) — it changes what the re-run ingests, so it wants an answer
    before the run rather than after. One line of source config either way.
  Everything else in the high band is better MEASURED by the re-run than
  blocked on it.
