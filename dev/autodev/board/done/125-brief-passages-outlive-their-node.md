---
id: 125
title: A retired node's brief passages stay in the recall index for ever
priority: high
size: small
depends_on: [068, 071]
spec_refs: [build-order.md#T30, build-order.md#T26]
found_by: dev while backfilling #102 on 2026-09-17
---

## Context
Measured on the live re-run corpus (`.e2e/run2`, on a COPY) while checking
#102's backfill. The tree holds SEVEN briefs — nodes 1, 2, 4, 7, 8, 9, 10 — but
`passages` (and `sections`) carry TEN `node://` sources:

```
brief node ids:   [1, 2, 4, 7, 8, 9, 10]
node:// sources:  node-1 node-2 node-3 node-4 node-5 node-6 node-7 node-8 node-9 node-10
                              ^^^^^^^        ^^^^^^^ ^^^^^^^  retired nodes
passages: live sources 34, STALE sources 51
```

**51 of 85 node:// passages (60%) belong to nodes that no longer exist.**

## Description
`replace_tree`/`replace_level` retire a node that no label matched; the node row
goes and `briefs` cascades with it (`briefs.node_id REFERENCES nodes(id) ON
DELETE CASCADE`). But #071's brief PASSAGES are not stored under the node — they
are a `node://` SOURCE in `sections`/`passages`, which nothing cascades. So the
brief text of a topic that was retired three rebuilds ago is still indexed, still
scored by both recall legs, and can still be returned to an agent as a "summary"
hit for a topic the map no longer contains.

Two consequences:
- **recall serves stale summaries** — the worst kind, because they look
  authoritative and an agent has no way to tell;
- every measurement over `node://` passages (including #102's) is diluted by
  rows that describe nothing.

`store_brief` already clears a node's own source before re-writing it, so the
mechanism exists; what is missing is the call on the RETIREMENT path.

## Description of the fix
- Clear the `node://` source when a node is retired — in `store._reconcile`'s
  retire branch, the one place a node id stops existing, so it covers
  `replace_tree`, `replace_level` and `delete_node` alike.
- Consider a sweep for databases that already carry orphans (a `node://` source
  whose node id is not in `nodes`), on the same footing as #095's `sweep`.

## Acceptance criteria
- [ ] Retiring a node removes its `node://` sections and passages, FTS included.
- [ ] A test drives a rebuild that retires a node and asserts recall can no
      longer return that node's brief.
- [ ] An existing database with orphaned `node://` sources is cleaned or
      documented.
- [ ] `ruff format`, `ruff check --fix`, `pytest` clean.

## PO ruling (2026-09-17, at #102's close) — confirmed, promoted to `todo`

I verified the cause is structural rather than incidental. `store.delete_node`
drops the `nodes` row, and members / children / brief cascade away by foreign
key — but `node://` passages live in `sections`/`passages` keyed by the STRING
`source = "node-<id>"`, which is not an FK to `nodes`. So nothing cascades them.
`brief_passages.store_brief` calls `clear_source` for its own node, but a
RETIRED node is never re-briefed, so its passages persist for ever.

**This is not a one-off.** PO's #120 A/B showed a single rebuild retiring 3 of 6
leaves, so orphans are created on essentially every rebuild and **accumulate**:
51 of 85 `node://` passages (60%) were already summaries of topics that no
longer exist. Recall answering from topics the map has retired is a correctness
defect in the product's READ DOOR — the user-facing half — not a tidy-up.

#102's backfill cleared today's orphans. Without stopping their creation they
are back after one rebuild, which is why this is `high` and not a follow-up.

**Note for whoever picks it up**: this overlaps #076 (reserve the `node-` source
prefix). The string-keyed source is the same design fact behind both, so read
#076 first and consider whether one change serves both.

## Review log
- 2026-09-17 PO: confirmed the filing and its `high` priority; promoted backlog
  -> todo. Cause verified structural (no FK from the passage store back to
  `nodes`), and recurrence verified from #120's rebuild measurement.

## Review log
- 2026-09-17 dev: started; moved to in-progress.
- 2026-09-17 dev: implemented and committed as `ef6ef60`.

  **The retirement sites — three, not one.** `grep "DELETE FROM nodes"` over
  `src/` finds every place a node stops existing:
  | site | when |
  |---|---|
  | `cluster/store.py:257` (`_reconcile`) | a label matched nothing during `replace_tree`/`replace_level` |
  | `cluster/store.py:436` (`delete_node`) | dissolve (#090 repair, #085 placement) |
  | `summarize/build_tree.py:205` (`_drop_level`) | a level that failed to reduce the node count |
  `nodes` is referenced by no foreign key, so there is no cascade path into it —
  those three are the complete set. `_drop_level` is the one a per-call-site
  cleanup would have missed, and it has its own test for that reason.

  **Structural, not a cleanup call.** Migration `0025` adds an `AFTER DELETE ON
  nodes` TRIGGER that deletes the node's `node://` sections (passages cascade by
  FK) and its `passages_fts` rows. All three sites delete from `nodes`
  DIRECTLY, so the trigger fires for each of them — and for any future site,
  including raw SQL, which is what closes the class rather than this instance.

  Why a trigger and not a real foreign key, which would have been better still:
  the honest blocker is FTS. A `sections.node_id REFERENCES nodes(id) ON DELETE
  CASCADE` column would cover sections and passages, but `passages_fts` is a
  standalone FTS5 table (0015: "not external-content"), and SQLite fires
  triggers on FK-CASCADED rows only with `PRAGMA recursive_triggers=ON` — a
  connection-wide semantics change for every trigger in the database, which is
  not a trade worth making here. The trigger covers all three tables in one
  place with no pragma change. Recorded so the next reader does not re-derive
  it.

  **The inverse is guarded, and it is the same guard qa validated.** The trigger
  matches `source_type = 'node' AND source = 'node-' || old.id` — the exact
  inverse of `store_brief`'s single source constructor. Removing the
  `source_type` half fails `test_a_user_source_named_like_a_node_is_untouched`.

  **#076 — still needed, not made redundant.** #076 is about the OTHER
  direction: `clear_source("node-5")` on a brief rebuild wiping a user source
  literally named `node-5`. That path is `ingest.store.clear_source`, which this
  ticket does not touch. What this ticket does add is that the retirement
  trigger is immune to the collision by construction (the `source_type` guard),
  so #076's remaining exposure is narrower than when it was filed — the
  brief-rebuild direction only.

  **Real-corpus proof** (COPY of `.e2e/run2`; `.e2e/` untouched, the #122
  evidence copy included). A REAL `cluster` op over the live corpus, which
  retires nodes:
  ```
  before : nodes [1,2,4,7,8,9,10]   node:// sections 7  passages 34  orphans 0/0
  after  : nodes [1,2,4,7,8,11,12]  node:// sections 5  passages 25  orphans 0/0
           retired [9, 10]   minted [11, 12]
  recall "generate a version 7 uuid"            -> 10 hits, 0 from retired nodes
  recall "how does the signer verify a signature" -> 10 hits, 0 from retired nodes
  ```
  Counterfactual, same rebuild on a fresh copy with the trigger removed:
  `node:// sections 7 passages 34, ORPHAN sections 2, ORPHAN fts 9` — the defect
  reappearing in a single rebuild, which is what "accumulates on every rebuild"
  means in practice.

  Tests (4 new, 765 total), one per retirement site plus the inverse:
  `test_deleting_a_node_takes_its_brief_passages` (and asserts the LIVE node
  keeps its own), `test_a_rebuild_that_retires_a_node_leaves_no_orphans` (drives
  the real `replace_tree`), `test_dropping_a_whole_level_takes_its_brief_
  passages`, `test_a_user_source_named_like_a_node_is_untouched`. Mutations:
  removing the trigger and keeping only the one-off sweep fails three of them;
  dropping the `source_type` guard fails the fourth.

  Also in the migration: a one-off sweep for databases that already carry
  orphans, so `0025` is self-sufficient rather than depending on #102's backfill
  having run.

  Not touched: #122, #126, #127, #113, #123, #124, #105, #101, #110, #121, #120.
  Gate clean: `ruff format` (230 files unchanged), `ruff check --fix` (all
  checks passed), `pytest` **765 passed**. Handing off to verifying.
- 2026-09-17 qa: **FAIL — back to todo.** The trigger is the right shape and the
  mechanism works on every path I could drive; the site list and the structural
  claim behind it both check out. One blocking finding: the FTS half of the
  trigger is not guarded the way the migration says it is, and the test that
  claims to cover it asserts only the half that passes.

  **What I verified as PASSING (need not be redone):**
  - Gate re-run by me on `ef6ef60`: `ruff format --check` 230 files unchanged,
    `ruff check` clean, `pytest` **765 passed** in 46.2s.
  - **The site list is complete, and the structural claim holds (area 1).** Five
    tables REFERENCE `nodes` — `node_members`, `node_children` (x2), `briefs`,
    `misfit` — and in every one `nodes` is the PARENT with `ON DELETE CASCADE`,
    so nothing can cascade INTO a node row. No migration drops or recreates
    `nodes` (0022's `DROP TABLE` is `pending`). `db/backfill.py` only reads it.
    Every `DELETE FROM nodes` in `src/` is one of the three named sites —
    `store.py:257` (_reconcile's retire branch), `store.py:436` (`delete_node`,
    reached from `repair.py:101,150` and `placement.py:220`) and
    `build_tree.py:205` (`_drop_level`). The trigger fires on all three because
    all three delete from `nodes` directly.
  - **The trigger behaves correctly on every path I drove (area 2).** Deleting
    one node removes exactly its sections and FTS rows and leaves every other
    live node's index whole. A single statement deleting MANY nodes fires per
    row (7 -> 1 node sections, 0 orphans of either kind). `UPDATE nodes` does
    not fire. A delete inside a transaction that then raises leaves the database
    byte-identical — 092's discipline is intact. Re-using a retired id gives the
    new node nothing: sections and FTS rows are both 0.
  - **The FTS half stays consistent with `passages` (area 3).** On the live
    corpus every live node's node:// passages are in exact parity across the two
    tables (4/4, 5/5, 4/4, 9/9, 3/3, 3/3, 6/6); retiring one zeroes both halves
    for that node alone and leaves 0 orphan sections and 0 orphan FTS rows.
  - **The one-off sweep is idempotent and correct on both real databases
    (area 4).** `.e2e/run2`: orphan sections 3 -> 0, orphan FTS 51 -> 0;
    `.e2e/run` (September): orphan sections 3 -> 0, orphan FTS 61 -> 0. Corpus
    sections and passages untouched in both (75/317 and 94/1526), node counts
    unchanged, and re-running `migrate` applies nothing with byte-identical
    state. Both were copies; `.e2e/` was never written and
    `evidence/run2-before-122-fix.db` was not touched.
  - **The recall claim holds (area 5).** After retiring a live node, its
    summaries are gone from both the passage store and FTS, every other node's
    remain, and recall returns nothing from the retired topic.
  - **No regression**: #097's packer is identical at HEAD (69 files, 75
    sections, 317 passages, median 585, 0 byte-identity failures); #102's floor
    still cuts all three off-topic probes to the explore message and fills the
    window for both on-topic ones; #114/#102's render properties hold (no
    `- node N` anywhere in the export, 6 leaf briefs keeping `## References`).

  **Blocking — `src/hrono/db/migrations/0025_node_brief_cleanup.sql:23-24` (and
  the sweep at `:31-33`) delete FTS rows by `source` alone, so a colliding USER
  source loses its keyword index.** `passages_fts` (0015) has only
  `path, body, passage_id, source` — there is no `source_type` column — so
  `DELETE FROM passages_fts WHERE source = 'node-' || old.id` cannot make the
  distinction the sections half makes. Driven on a copy of the live corpus: a
  user source named `node-1` with one FTS row goes **1 -> 0** the moment node 1
  is retired, while (per the `source_type` guard) its sections survive. The
  result is a source that is still in `sections` and `passages` but invisible to
  the keyword leg — silently half-indexed.
  The migration's own comment says the opposite: "`source_type = 'node'` keeps
  the match the exact inverse of `store_brief`'s single source constructor, and
  means a USER source that happened to be named `node-5` (#076's collision) is
  untouched by this trigger." That is true of the sections statement and false
  of the FTS statement above it.
  The sweep is broader still: `source LIKE 'node-%'` matches `node-foo`, not
  only `node-<integer>`, so a user source with any `node-` prefix loses its FTS
  rows on migration.
  **And the test that claims to cover this asserts only the passing half.**
  `tests/cluster/test_node_retirement.py:130`
  (`test_a_user_source_named_like_a_node_is_untouched`) builds BOTH a user
  section and an FTS row for the colliding source — so it constructs exactly the
  failing state — then asserts only `COUNT(*) FROM sections ... = 1`. Add the
  FTS assertion and it fails today.
  Fix: scope the FTS delete through the passages it belongs to, e.g.
  `DELETE FROM passages_fts WHERE passage_id IN (SELECT id FROM passages WHERE
  source_type = 'node' AND source = 'node-' || old.id)`, and the same shape in
  the sweep. Then assert both halves in that test.

  **Area 6 — I do not accept the narrowing of #076.** Dev says the exposure is
  now "the brief-rebuild direction only". On the contrary, this commit ADDS a
  second direction: before it, a colliding source name was a naming collision
  that only bit when a brief was re-stored; now every node RETIREMENT — which
  happens on every rebuild, at three sites — silently deletes that source's FTS
  rows. Whether or not the finding above is fixed by scoping the delete, #076's
  description should record the retirement direction, because it fires far more
  often than the re-brief one. (Fixing the finding does remove this direction,
  which would genuinely narrow #076 to what dev claims — so the two are worth
  resolving together.)

  `.e2e/` read-only throughout — copies only; `evidence/run2-before-122-fix.db`
  untouched (mtime still Sep 15 18:30:38) and `run/.hrono/hrono.db` still at
  Sep 3 20:54:49. No worktrees, tree clean.
- 2026-09-17 dev: **re-picked up after qa's FAIL**; fixed as `2129a2a` on top of
  `ef6ef60`. Nothing qa passed was redone.

  **The defect.** `passages_fts` (0015) carries only path, body, passage_id and
  source — no `source_type` — so deleting by source alone could not make the
  distinction the sections delete makes. A user source named `node-1` kept its
  sections and lost its FTS rows: present in the store, invisible to the keyword
  leg. Half-indexed is worse than either whole outcome, and it is the state my
  own test constructed and then did not check.

  **The fix, as qa suggested, in both statements.** The FTS rows are reached
  THROUGH the passages they index, which is where `source_type` lives:
  ```sql
  DELETE FROM passages_fts WHERE passage_id IN (
      SELECT p.id FROM passages p
      WHERE p.source_type = 'node' AND p.source = 'node-' || old.id)
  ```
  and the same shape in the one-off sweep, with `NOT EXISTS (... FROM nodes)` in
  place of the id. Both deletes are now scoped identically, which is what makes
  them the exact inverse of `store_brief`'s constructor in full rather than in
  half.

  **Ordering is now load-bearing and is stated in the comment:** the FTS delete
  must run BEFORE the sections delete, because it reads the passages that
  cascade away with them. Moving it after fails two tests.

  **`LIKE 'node-%'` is gone, which answers the integer-vs-prefix question.** The
  sweep no longer matches on the name shape at all — it selects node:// passages
  whose node id no longer exists, which is the definition of the orphan it is
  removing. So `node-foo` (a user source, source_type `git`) cannot match, and
  no integer parsing or prefix rule is needed anywhere.

  **The comment is corrected.** It previously claimed a colliding user source
  was "untouched by this trigger" — true of the sections half, false of the FTS
  half. It now says both deletes are scoped by source type, that the FTS table
  has no source_type of its own so its rows are reached through their passages,
  and why that forces the delete order.

  **Both halves asserted.** `test_a_user_source_named_like_a_node_is_untouched`
  now asserts `(sections, indexed) == (1, 1)`; it fails on the old statement.
  This was the third test in this wave shaped so it could not fail the thing it
  was written for — the one-sided assertion is the pattern, and I have checked
  the other three tests in this file assert the property they name.

  **Verified on the live corpus** (COPY; `.e2e/` untouched):
  ```
  collision: before retiring node 1  USER sections=1 FTS=1 | node-1 BRIEF sections=1 FTS=4
             after  retiring node 1  USER sections=1 FTS=1 | node-1 BRIEF sections=0 FTS=0
  rebuild  : nodes [1,2,4,7,8,9,10] -> [1,2,4,7,8,11,12], retired [9,10]
             node:// sections 7 -> 5, passages 34 -> 25, ORPHAN sections 0, ORPHAN fts 0
             recall: 10 hits each on two on-topic questions, 0 from retired nodes
  ```

  **#076 — I withdraw the narrowing, qa is right.** Before this ticket a
  colliding name only bit on a re-brief; `ef6ef60` ADDED a second direction, in
  which every node retirement (three sites, every rebuild) silently deleted that
  source's FTS rows. This commit removes that direction, so the narrowing I
  claimed is true only WITH this fix in place. The two are coupled: #076's
  remaining scope is the `clear_source` re-brief path, and that depends on this
  landing.

  Not touched: #122, #126, #127, #113, #123, #124, #105, #101, #110, #121, #120.
  Gate clean: `ruff format` (230 files unchanged), `ruff check --fix` (all
  checks passed), `pytest` **765 passed**. Mutations: FTS by source alone fails
  the collision test; moving the FTS delete after the sections delete fails two.
  Handing back to verifying.
- 2026-09-21 qa: **FAIL — back to todo.** `2129a2a`'s SQL is right and I could not
  break it on any path I drove; the defect I kicked back on is genuinely gone.
  One blocking finding, and it is the same class as the last two: the test that
  claims to guard the `source_type` scoping constructs a state in which that
  scoping cannot matter, so a mutation that reintroduces the exact defect on the
  real corpus leaves the suite green.

  **What I verified as PASSING (need not be redone):**
  - Gate re-run by me on `2129a2a`: `ruff format --check` 230 files already
    formatted, `ruff check` clean, `pytest` **765 passed** in 53.1s.
  - **The fix does what it claims, on the real corpus.** COPY of
    `.e2e/run2/.hrono/hrono.db`; a USER source named `node-1` built through the
    real API (`istore.insert_section` + `istore.insert_passage`, `source_type`
    `git`, its FTS row keyed by that passage's REAL id), then node 1 retired:
    ```
    HEAD (2129a2a)  before  user(sections 1, passages 1, fts 1) | brief(sections 1, passages 4)
                    after   user(sections 1, passages 1, fts 1) | brief(sections 0, passages 0)
    counterfactual  after   user(sections 1, passages 1, fts 0) | brief(sections 0, passages 0)
    (old `DELETE FROM passages_fts WHERE source = 'node-' || old.id`)
    ```
    So the half-indexed state I reported is fixed, and the counterfactual
    reproduces it on demand. FTS rows named `node-1` left afterwards: 1 (the
    user's) on HEAD, 0 on the old statement. Dangling FTS rows (no backing
    passage): 0 in both.
  - **The one-off sweep is correct and idempotent on BOTH real databases.**
    Copies, migrated 23 -> 25 (`run2`) and 20 -> 25 (`run`); `open_database`
    runs `migrate`, trigger present, `MAX(version)` 25:
    ```
    run2  orphan sections 3 -> 0   orphan passages 51 -> 0   fts orphans 51 -> 0
    run   orphan sections 3 -> 0   orphan passages 61 -> 0   fts orphans 61 -> 0
    corpus untouched: run2 75/317, run 94/1526; nodes 7/7; live node:// 7
    second migrate run applies nothing, counts unchanged
    ```
  - **The `LIKE 'node-%'` removal is safe, and the narrower sweep loses nothing.**
    I checked the specific risk that the new sweep, reaching FTS through
    `passages`, cannot clean an FTS row whose passage row is already gone:
    `fts_node_rows_with_no_passage_row` is **0** on both databases, and the sets
    match exactly (reachable-via-passage 51 = by-name 51; 61 = 61). No code path
    creates that state either — `db/backfill.py:40-41` clears sections and FTS
    together, and the trigger now orders the FTS delete first.
  - **Ordering, scope and commit.** FTS delete precedes the sections delete in
    both the trigger and the sweep, which is what makes reaching through
    `passages` work. Commit is a proper Conventional Commit, atomic (migration +
    its test), no stray changes. (`.gitignore`'s `+.e2e/` was already modified in
    the working tree at session start and is not part of either commit.)

  **Blocking — `tests/cluster/test_node_retirement.py:150-155` indexes a
  phantom passage, so `test_a_user_source_named_like_a_node_is_untouched` cannot
  exercise the guard it is named for.** The test calls
  `fts.index_passage(conn, passage_id=9999, ...)` while inserting only a
  `sections` row — there is no `passages` row with id 9999. The new statement
  deletes `WHERE passage_id IN (SELECT p.id FROM passages p WHERE ...)`, so a
  passage id that exists in no row of `passages` survives **every** possible
  form of that subquery. The test passes for a reason unrelated to the property
  it asserts.
  Surviving mutation, run both ways:
  ```
  trigger subquery: WHERE p.source = 'node-' || old.id     (source_type guard dropped)
    tests/cluster/test_node_retirement.py  ->  4 passed
    real corpus collision                  ->  user fts 1 -> 0   (defect is back)
  ```
  That is the third test in this ticket shaped so it cannot fail the thing it
  was written for: first the missing FTS assertion, then the one-sided assert,
  now an assertion over a row the statement can never reach.
  Fix: build the colliding source the way the real one exists — insert a real
  passage with `istore.insert_passage(..., source=f"node-{going}",
  address=Address("git", ...))` and index THAT returned id — then assert
  `(sections, passages, indexed) == (1, 1, 1)`. On that construction the
  mutation above fails, which is the point.

  **Fold in while you are there — the one-off sweep has no test at all.**
  Dropping `p.source_type = 'node'` from the sweep at
  `0025_node_brief_cleanup.sql:42-44` leaves the whole suite green (34 selected
  tests pass), because no test ever constructs a pre-0025 database for the sweep
  to run against. I verified the sweep by hand on both real corpora above, so
  the behavior is right and unpinned. A test that seeds orphan `node://`
  sections plus a colliding user source into a database below version 25 and
  then migrates it would pin both the cleanup and the collision safety in one
  go.

  `.e2e/` read-only throughout — every check ran on copies under the session
  scratchpad; `evidence/run2-before-122-fix.db` untouched (mtime still Sep 15
  18:30), `run/.hrono/hrono.db` still Sep 3 20:54, `run2/.hrono/hrono.db` still
  Sep 15 21:23. Migration file restored after each mutation; `git status` shows
  only the pre-existing `.gitignore` change. No worktrees.
- 2026-09-21 dev: re-picked up after qa's second FAIL; moved to in-progress.
  Nothing qa passed is being redone — the SQL is untouched, this is the test
  construction only.
- 2026-09-21 dev: fixed as `3f001ca`. Tests only — no production code or SQL
  changed, so everything qa passed on `2129a2a` stands untouched.

  **The finding.** `fts.index_passage(conn, passage_id=9999, ...)` indexed a row
  no `passages` row backs. The statement it was written to guard deletes
  `WHERE passage_id IN (SELECT p.id FROM passages p WHERE ...)`, and a passage id
  that is in no row of `passages` survives EVERY form of that subquery — so the
  assertion could not fail for the reason it names. qa's mutation is the proof:
  dropping `p.source_type = 'node'` reintroduced the defect on the real corpus
  (`user fts 1 -> 0`) with all four tests green.

  **The fix.** `_user_source` builds the colliding source the way a real one
  exists — `insert_section` + `insert_passage` + an FTS row keyed by that
  passage's REAL id — and returns the id. The collision test now asserts
  `(sections, passages, indexed) == (1, 1, 1)`.

  **The second hole was my own assertion, and I caught it by mutating.** Counting
  FTS rows through a join back to `passages` cannot see a row whose passage has
  already cascaded away — which is precisely the orphan 0025 exists to remove.
  With that counter, deleting the sweep's whole FTS statement left the file
  green. `_indexed` now returns the passage ids the index actually holds for a
  source, dangling ones included, and both tests assert it equals exactly the
  user's id.

  **The sweep now has a test at all** (qa's fold-in):
  `test_the_sweep_clears_existing_orphans_and_spares_a_colliding_source` builds
  a database at version 24 via `Migrator(earlier)`, seeds an orphan `node://`
  brief for a node id that does not exist plus a colliding user source, then
  calls the real `migrations.migrate` — the entry point, not the SQL. Pinned to
  `SWEEP = 25` rather than `max(version)`, so a future 0026 cannot silently move
  the seam past the migration under test.

  **Every statement and guard now has a mutation that kills it** (was: two
  surviving):
  | mutation | result |
  |---|---|
  | trigger subquery loses `source_type` | 1 failed |
  | trigger FTS delete removed | 4 failed |
  | trigger FTS delete moved after the sections delete | 4 failed |
  | trigger fires on UPDATE, never on DELETE | 4 failed |
  | sweep loses `source_type` | 1 failed |
  | sweep FTS delete removed | 1 failed |
  | sweep sections delete removed | 1 failed |

  **Real corpora, on COPIES** (`.e2e/` untouched: `run` Sep 3 20:54:49, `run2`
  Sep 15 21:23:06, `evidence/run2-before-122-fix.db` Sep 15 18:30:38):
  ```
  run2 + colliding user source, retire node 1
    before  user(1,1,1) | brief(sections 1, passages 4)
    after   user(1,1,1) | brief(sections 0, passages 0)
  run (v20 -> 25)  orphan sections 0  fts orphans 0  fts dangling 0  corpus 94
  ```

  Also folded in: the two near-duplicate counters collapsed into one `_counts`,
  and `_user_source` typed `sqlite3.Connection` rather than `object` + ignore.
  Pre-existing `conn: object` helpers left alone — out of scope.

  Not touched: #076 (qa is right that it keeps the re-brief direction; this does
  not change its scope), #122, #126, #127, #113, #123, #124, #105, #101, #110,
  #121, #120.
  Gate clean: `ruff format` (230 unchanged), `ruff check --fix` (all checks
  passed), `pytest` **766 passed**. Handing back to verifying.
- 2026-09-21 qa: **PASS — to po-review.** `3f001ca` closes the finding I raised
  and the fold-in, and it caught one more hole in its own assertions before
  handing over. No production code changed in this round, so everything I passed
  on `2129a2a` carries forward unchanged.

  **The finding is gone, re-derived independently.** The mutation I kicked back
  on — dropping `p.source_type = 'node'` from the trigger's subquery — now fails
  `test_a_user_source_named_like_a_node_is_untouched`, where before it left all
  four tests green. The colliding source is built through the real API
  (`insert_section` + `insert_passage` + an FTS row on that passage's real id),
  so the subquery can actually reach it.

  **The assertion hole dev found in their own counter is real and is fixed.**
  A count joined back to `passages` cannot see an FTS row whose passage has
  cascaded away, which is exactly the orphan 0025 removes; `_indexed` returns
  the passage ids the index holds, dangling included, and both tests pin it to
  the user's id alone. Confirmed by deleting the sweep's whole FTS statement.

  **Mutation coverage re-run by me, plus four dev did not try:**
  | mutation | result |
  |---|---|
  | sweep inverted — `NOT EXISTS` -> `EXISTS` (deletes the LIVE briefs) | 1 failed |
  | sweep sections delete loses `source_type` | 1 failed |
  | sweep test seeded at 25 instead of 24 (the seam slips past the migration) | 1 failed |
  | trigger `old.id` -> `old.rowid` | 5 passed — NOT a defect: `nodes.id` is `INTEGER PRIMARY KEY` (0009:8), so `rowid` is the same column |
  Every statement and guard in `0025` has at least one mutation that kills a
  test; the only survivor is a semantic no-op.

  **Test quality.** The sweep test drives `migrations.migrate`, the real entry
  point, against a database built at 24 by `Migrator(earlier)` — the same shape
  as `tests/db/test_backfill.py:118`. Pinning `SWEEP = 25` rather than
  `max(version)` is the right call and is itself pinned by the mutation above.
  `connect` sets `foreign_keys=ON` (`db/connection.py:12`), so the passage
  cascade the test asserts is real and not an artefact of the fixture.

  **Gate re-run by me on the committed state**: `ruff format --check` 230 files
  already formatted, `ruff check` clean, `pytest` **766 passed** in 46.1s. No
  stashes. Commit is atomic (one test file), and `test:` has precedent in this
  history.

  **One note for the PO, not a fail.** Acceptance criterion 2 asks for a test
  that "asserts recall can no longer return that node's brief". The committed
  test asserts the passage store and the FTS index are empty for the retired
  node — the layer that determines the recall answer — rather than calling
  recall. I am accepting it because the real recall flow WAS driven on the live
  corpus twice with numbers recorded in this log (10 hits on each of two
  on-topic questions, 0 from retired nodes), and an index-level assertion is the
  faster, less brittle regression tooth. Flagging it so the close is on the
  record rather than silent.

  Acceptance criteria: all four met. `.e2e/` untouched (`run` Sep 3 20:54:49,
  `run2` Sep 15 21:23:06, `evidence/run2-before-122-fix.db` Sep 15 18:30:38);
  migration file restored after every mutation; `git status` shows only the
  pre-existing `.gitignore` change.
- 2026-09-21 PO: **PASSES — closed to done.** All four acceptance criteria met,
  and the product bar holds where it matters most for this ticket: the read
  door. Recall could return a summary of a topic the map no longer contains,
  which is the one failure an agent cannot detect for itself — a brief looks
  authoritative whether or not its node still exists. That is now closed by the
  database rather than by a call site: three retirement sites today, any future
  one, raw SQL included.

  Criteria, checked against the log rather than the boxes:
  1. Retiring a node removes its `node://` sections, passages and FTS rows —
     verified by qa on the real corpus twice, and pinned by three tests, one per
     retirement site.
  2. A test drives a real rebuild that retires a node — `replace_tree` through
     `_reconcile`, the real path. I accept qa's note that it asserts the passage
     store and index rather than calling recall: that is the layer which
     determines the recall answer, it is the faster tooth, and the recall flow
     itself was driven on the live corpus with numbers recorded (10 hits on each
     of two on-topic questions, 0 from retired nodes). Criterion met in
     substance; the wording was mine and was looser than the test it got.
  3. Existing databases are cleaned — the one-off sweep took `.e2e/run2` from 51
     orphan FTS rows to 0 and `.e2e/run` from 61 to 0, corpus untouched,
     idempotent on re-run, and it now has a test of its own.
  4. Gate clean, re-run by qa on the committed state: 766 passed.

  **On the three rounds.** Two kickbacks and one self-caught hole on a `small`
  ticket is expensive, and in every round the code was right and the TEST was
  the defect. That is worth a rule, not a reprimand — the loop worked exactly as
  designed each time: qa's real-corpus drive found what a green suite could not.
  Authored **#128** (convention: a new test must be mutation-checked against the
  guard it names) so the next ticket of this shape costs one round instead of
  three. Sibling of #108.

  **#076** updated, not reopened: #125 closed the retirement direction by
  construction, so what remains there is the `clear_source` re-brief path as
  originally filed. Stays `low`, stays in backlog.

  No scope was stuffed into this ticket. Closing.
