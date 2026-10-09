---
id: 099
title: The batch counter bumps per changed source, not per `update` run
priority: high
size: small
depends_on: []
spec_refs: [build-order.md#T33, build-order.md#T13]
found_by: e2e manual QA 2026-09-03 — .e2e/FINDINGS.md F26; re-scoped by PO after #104
---

## Context

**Re-scoped by PO on 2026-09-14, after closing #104.** This ticket was filed as
two problems. One of them is gone, and the other was never about empty files at
all — so the title and scope now match what is actually left.

What was fixed by #104 (commit 306f0e2): the filter skips zero-byte files
outright. `src/itsdangerous/py.typed` — the file that motivated F26 — is no
longer ingestable in ANY configuration, including the maximum escape hatch
(`replace_defaults: true` + `include: ["**"]`), because the gate is a size
check, not a pattern. Verified on the real file.

What turned out not to exist: the original Decision called for a "seen,
produced no sections" marker, on the reasoning that whitespace-only and
comment-only files would have the same phantom-`new` symptom as `py.typed`.
**They do not — there is no such file.** qa probed this and the PO re-probed it
independently over **252 combinations** (18 degenerate inputs x 14 extensions):
whitespace-only, comment-only (`#`, `//`, `/* */`, `<!-- -->`), a lone newline,
CRLF-only, a single space, a single character, punctuation-only, a bare BOM,
BOM+newline, a form feed, NBSP and a zero-width space, across `.py .md .txt .go
.js .ts .rst .json .yaml .toml .html .css .sh` and extensionless. Every
non-empty input yields at least one section. `split()` returns `()` for
genuinely empty bytes and nothing else, and #104's gate now stops those before
the splitter sees them.

So the marker mechanism would guard a state that cannot occur. **Do not build
it.** If a future splitter change makes a non-empty file yield zero sections,
that is a splitter bug to fix there, not a marker to carry in the diff.

## Description

What remains is the "related observation" in the original filing, which is a
real defect with a real consequence and is not about empty files:

`_next_batch` is called inside `_update_source` — once per source that reports
changes — while `tree_batch`'s schema comment says "Each `update` run over a
tree bumps this". An `update` over three sources with changes bumps the counter
three times.

This matters more now than when it was filed. `tree_batch.batch` drives
incubator ageing (`current_batch - batch > MAX_AGE`), and **#095 wired ageing to
force-assign on every update**. An inflated counter therefore ages parked chunks
toward forced assignment several times faster than the design intends — and a
force-assigned member is currently never revisited (#113), so a premature
force-assignment permanently pollutes a topic's brief. A counting bug at one end
becomes irreversible map damage at the other.

Work: move `_next_batch` out of `_update_source` so it is called once per
`update` run, matching the schema comment, and settle the contract in the
docstring so it cannot drift back.

## Acceptance criteria
- [ ] `update` over an unchanged corpus changes nothing at all, batch counter
      included.
- [ ] An `update` run over N sources with changes bumps `tree_batch.batch`
      exactly once, and a regression test drives more than one changed source.
- [ ] The batch counter's contract (per run, not per source) is stated where it
      is read as well as where it is written.
- [ ] `ruff format`, `ruff check --fix`, `pytest` clean.

## Out of scope
- The zero-byte filter gate — delivered by #104.
- A "seen, produced no sections" marker — no reachable state, see Context.

## Review log
- 2026-09-14 PO: re-scoped after closing #104. Half of this ticket is delivered
  and half is unreachable; what is left is the batch-counter contract, which is
  smaller than the original framing but not less important — #095 and #113 have
  since made an inflated counter cause permanent brief pollution rather than
  just noise. Priority stays `high`, size stays `small`, title and criteria
  rewritten to match. **Recommended to land before the end-to-end re-run**: the
  re-run exercises `update` repeatedly over three sources, and an over-counting
  batch would distort exactly the incubator ageing behaviour the run is meant
  to observe.
- 2026-09-15 dev: started; moved to in-progress.
- 2026-09-15 dev: implemented and committed as `733549c`. Scope taken exactly as
  the PO re-scoped it: the batch-counter contract only. **No "seen, produced no
  sections" marker was built** — per the Context it would guard an unreachable
  state.

  **The change.** `_next_batch` moves out of `_update_source` and the run's
  number is threaded as a plain fold instead of a module- or object-level
  counter: `update` holds `batch: int | None = None` and passes it to each
  source; `_update_source` returns it unchanged when the source has no changes,
  allocates it with `_next_batch` when it is None and there ARE changes, and
  returns it so every later source in the same run reuses the same number. So
  the allocation is LAZY — which is what keeps acceptance criterion 1 true: a
  run over an unchanged corpus never reaches `_next_batch` and the counter does
  not move. No mutable carrier, no global; the data flow is visible in the
  signature (`batch: int | None` in, `int | None` out).

  **The contract is stated at both ends** (criterion 3): `tree/update.py`'s
  module docstring gains a "ONE BATCH NUMBER PER RUN, not per source" paragraph
  naming why it matters (ageing measures against this clock, and #113 makes a
  premature force permanent), and `cluster/incubator.py` — where the number is
  READ — now says a batch is one `update` RUN above `MAX_AGE`, together with
  how that interacts with #095's park semantics (`ON CONFLICT DO NOTHING` keeps
  the first park's batch; a join unparks), so the clock only runs while a chunk
  is genuinely homeless. Migration 0018's comment already said "Each `update`
  run over a tree bumps this" — the code now matches it rather than the comment
  being aspirational.

  **Tests (4 new, 692 total)**, in `tests/tree/test_update.py`:
  - `test_n_update_runs_advance_the_batch_counter_by_exactly_n` — four runs,
    each with one change, asserting the counter after EVERY run (N runs, N
    bumps).
  - `test_a_run_over_two_changed_sources_bumps_the_counter_once` — a second git
    source registered, both sources edited, ONE run: counter advances by
    exactly 1, and both sources' `f1.txt` really did land (asserted via
    `DISTINCT source`), so the single bump is not a run that skipped work.
  - `test_a_run_with_no_changes_leaves_the_counter_alone` — criterion 1.
  - `test_ageing_measures_runs_not_changed_sources` — the MAX_AGE boundary with
    two changed sources per run: after exactly `MAX_AGE` runs the chunk is
    still pending (`current - parked_at == MAX_AGE`, which is NOT `> MAX_AGE`),
    and one run later it is force-assigned. Pool invariant asserted every run.
  Regression-grade: restoring the per-source bump fails
  `..._bumps_the_counter_once` and `test_ageing_measures_runs_not_changed_
  sources` (the other two pass either way — with one changed source per run the
  two behaviours coincide, which is exactly why this hid for so long).

  **The ageing boundary, measured rather than argued.** A throwaway probe (run,
  read, deleted — not committed) drove the real `update` op over two sources
  until the parked chunk was forced:
  ```
  new code:  parked_at=1  forced after 6 runs  final batch=7   (7-1=6 > MAX_AGE=5)
  old code:  parked_at=1  forced after 3 runs  final batch=8   (3 runs, 8 batches)
  ```
  Exactly twice as fast on the old code with two sources — and it would be
  three times with three sources, which is the shape of the upcoming re-run.
  The new numbers land on the right side of MAX_AGE: not forced at the
  boundary, forced one run past it.

  Consistent with #095's migration 0022 as instructed: the pool is keyed
  `(tree, section_id)` and `park` keeps the ORIGINAL batch, so this change only
  affects what "one batch" means, never which row a park lands on; the
  `parked_at` this ticket's tests read back is the first park's number.

  Not touched: #114, #113, #102, #103, #105, #118, #119. `.e2e/` untouched
  (read-only; database mtime still 2026-09-03 20:54:49).
  Gate clean: `ruff format` (225 files unchanged), `ruff check --fix` (all
  checks passed), `pytest` **692 passed**. Handing off to verifying.
- 2026-09-15 qa: **PASS — to po-review.** No defects. The fold is correct in
  every ordering I could construct, the ageing boundary is exactly where the
  ticket says, and the PO's re-scope was honoured.

  **1. The fold — eight orderings driven through the real `update` op.** Three
  registered git sources, every subset of them changed, one run each:

  ```
  changed=()                      1 -> 1      changed=('repo','bbb')      1 -> 2
  changed=('repo',)               1 -> 2      changed=('bbb','ccc')       1 -> 2
  changed=('bbb',)                1 -> 2      changed=('repo','ccc')      1 -> 2
  changed=('ccc',)                1 -> 2      changed=('repo','bbb','ccc') 1 -> 2
  ```

  At most one bump, zero when nothing changed — independent of WHICH source
  changed or its position in the iteration (sources run `ORDER BY name`, so
  these cover first-changed/rest-not, first-not/later-changed, and all three).
  The same probe on `de5ef38` gives `+2` for two changed sources and **`+3`**
  for three, which is the defect.

  Two failure orderings the ticket does not mention, both correct:
  - a source whose sync raises BEFORE anything allocated -> counter untouched
    (the allocation sits inside the same `write()` transaction as diff and
    reconcile, so it rolls back);
  - a source whose sync raises AFTER an earlier source allocated -> exactly
    ONE bump for the whole failed run, not one per source reached.
  Worth recording for the re-run's log rather than fixing: a RETRY of a failed
  update job is a fresh run and may allocate another batch. That is defensible
  (a retry really is another run) and bounded, but a run-log reading batch
  numbers as "logical runs" should know it.

  I also drove the case you asked about — a non-empty `diff` whose reconcile
  yields nothing: it consumes the run's batch, which is right, because a run
  did happen and a source really did change.

  **2. The measurement, reproduced independently — and it scales to the
  re-run's three-source shape.** Alien chunk parked at batch 1, three sources
  changed every run:

  ```
  run 1: batch=2   pending=[('alien/zz.txt', 1)]
  ...
  run 5: batch=6   pending=[('alien/zz.txt', 1)]   <- current-parked == MAX_AGE, NOT forced
  run 6: batch=7   pending=[]                      <- forced, one run past the boundary
  ```

  The boundary is exactly `current - parked_at > MAX_AGE`: not forced at 5,
  forced at 6. It takes **6 runs whatever the source count**, which is the
  point. The same probe on `de5ef38` with three sources parks at batch 3 and
  forces by **run 2** (batch 9) — three times too fast, worse than the
  two-source figure of 3-vs-6 dev reported, and that is the shape the re-run
  would have had.

  **3. 095's pool semantics are unchanged and still hold under the new clock.**
  This commit touches `incubator.py` only in comments — `park`'s
  `ON CONFLICT(tree, section_id) DO NOTHING` (`incubator.py:68`) and
  `placement.py:173`'s unpark-on-join are both untouched. Observably: across
  all five ageing runs the parked row stayed `('alien/zz.txt', 1)` while the
  counter advanced 2..6, i.e. a re-park kept the ORIGINAL wait against a clock
  that now means runs. `assert_pool_invariant` was asserted after every one of
  those runs and held.

  **4. Two of the four new tests do pass under both — and both still earn their
  place.** Confirmed by running the new `test_update.py` against `de5ef38`:
  `test_a_run_over_two_changed_sources_bumps_the_counter_once` and
  `test_ageing_measures_runs_not_changed_sources` FAIL on the old code;
  `test_n_update_runs_advance_the_batch_counter_by_exactly_n` and
  `test_a_run_with_no_changes_leaves_the_counter_alone` pass on both, because
  with one source per run the two semantics coincide — which is exactly why
  this hid. I judged them by mutation rather than by opinion:
  - allocating EAGERLY at the top of `update()` (the obvious, tempting wrong
    fix — one line, and it looks like "one batch per run") is caught ONLY by
    `test_a_run_with_no_changes_leaves_the_counter_alone`. That test guards the
    laziness the whole design rests on; it is the opposite of padding.
  - `_next_batch` no longer incrementing is caught by
    `test_n_update_runs_advance_the_batch_counter_by_exactly_n` (plus four
    others). It states the ticket's headline contract directly.
  Reverting to per-source allocation fails both discriminating tests plus five
  of my probes. All four tests catch at least one realistic regression.

  **The PO's re-scope was honoured.** No "seen, produced no sections" marker was
  built: no migration in the diff, and no marker mechanism anywhere in `src/`.
  The commit is the batch-counter half only, which is what the re-scope asked
  for.

  **5. No regression across the 092-099 wave.** Full gate green, plus the groups
  most at risk re-run explicitly at HEAD: `test_incubator`, `test_placement`,
  `test_settle`, `test_update`, `tests/export`, `test_split_op`, `test_sync`,
  `tests/admin` — **98 passed**. 104's filter re-measured on the real corpus at
  HEAD (read-only) is unchanged: **69 files / 76 sections** across the three
  repos, identical to what I measured verifying 104. 098's anchor spot-checked:
  same absolute cache root from two cwds, no stray `.hrono`.

  Commit `733549c` is a clean Conventional Commit, atomic, 3 files, no stray
  changes; `.gitignore` is still the pre-existing uncommitted line. `.e2e/`
  read-only throughout — database mtime still 2026-09-03 20:54:49. Worktrees
  removed, tree clean.

  Gate re-run by me on `733549c`: `ruff format --check` 225 files unchanged,
  `ruff check` clean, `pytest` **692 passed** in 40.7s. All acceptance criteria
  hold.

  **Fitness for the e2e re-run (asked for explicitly).** I consider the
  corpus-facing pipeline sound enough to trust a live run's STRUCTURAL findings.
  Every measurement hazard the September run hit is closed and independently
  verified by me: F25 two divergent caches (098), F19/F20 export writing zero
  files and briefs colliding (096), F4/F5 the filter (104), F26 phantom batches
  (099 + 104's zero-byte gate), F29 stranded chunks (095). A number the re-run
  reads — a batch, a section count, an export file list, a pending pool — can
  now be believed.

  I would NOT trust it for brief/recall QUALITY findings, and the run should
  pre-record these as EXPECTED rather than discoveries, or they will be
  re-reported as new: **#114** (a drain-emitted leaf is briefed and written to
  the export but unreachable from `root.md` — expect orphan directories if any
  drain emits a core); **#113** (the `forced` flag has no reader, so a
  force-assigned low-similarity chunk is never re-checked and will pollute its
  node's brief); **#100** (a pure rename still ejects a file from its cluster —
  open, corpus-facing, and the September run hit it); **#097** (passages pack to
  ~100B not 800B, which shapes every recall result); **#102/#103/#105** (recall
  quality, brief output guard, judge verdict parsing); **#118** (a
  `package-lock.json` in any re-run repo will still be ingested); **#116** (an
  export polled while a build is running answers 500 — transient, not a
  defect); and **#106** (there is no `/trees/{name}/update` endpoint — I got a
  clean 404 driving it — so whatever drives the update path must account for
  that).
- 2026-09-15 PO: **ACCEPTED -> done.** Commit 733549c implements the re-scope
  exactly: the counter half, no marker mechanism. Verified independently.

  **Gate re-run by me:** `ruff format --check .` 225 files already formatted;
  `ruff check .` all checks passed; `uv run pytest` **692 passed** in 41.3s.

  **Diff read.** A plain fold — `batch: int | None` threaded through the source
  loop, each source returning it unchanged or allocating it once — is the right
  shape: no new state, no per-run object, nothing to keep in sync. Two details
  make it correct rather than merely tidy. **Lazy** allocation is what keeps
  "an unchanged run never bumps" true (eager allocation at the top of `update`
  is the tempting wrong fix that still reads like "one batch per run"). And the
  allocation sits INSIDE the diff/reconcile write transaction, so a sync that
  raises before it rolls the allocation back. Stating the contract at BOTH ends
  — `tree/update.py` where it is written and `cluster/incubator.py` where it is
  READ — is the thing that stops this drifting back; a clock is only meaningful
  if the reader agrees what a tick is.

  **I drove both properties myself, with THREE sources — the re-run's actual
  shape**, not the two the tests use. All eight subsets of three sources
  changing, through the real `update` op:

  ```
    changed-mask | n changed | batch delta      OLD (de5ef38), same probe
        000      |     0     |    0                      0
        001      |     1     |    1                      1
        011      |     2     |    1                      2
        111      |     3     |    1                      3
  ```

  Exactly one bump whenever anything changed, zero when nothing did,
  independent of how many sources changed. I re-ran the identical probe in a
  worktree at `de5ef38` and the old counter advanced once per changed source —
  **3x too fast at three sources**. That is the number that matters: it means a
  parked chunk would have been force-assigned after 2 runs instead of 6.

  **The ageing boundary, driven at three sources:** parked at batch 1, each run
  advancing by exactly 1 even with all three sources changing; the chunk
  survives at age 5 (`== MAX_AGE`) and is forced at age 6. The pool invariant
  (#095) held on every run, and the parked row kept its ORIGINAL batch
  throughout — `park`'s `ON CONFLICT DO NOTHING` means the clock measures time
  since first parking, not since last touch, which is what makes `MAX_AGE`
  mean what it says.

  This was the last thing I wanted before the re-run, and it is the right call
  that it was: with three sources the old clock ran triple speed, so every
  incubator observation the run makes would have been measuring the counter
  rather than the corpus — and via #113 (forced members are never revisited) a
  premature forcing is permanent, so the damage would have outlived the run.

  All four acceptance criteria hold.

  **Rulings:**
  1. **qa's fitness statement is CONFIRMED and its list is right — I am adding
     six items.** The scoping is correct: trustworthy for STRUCTURAL findings
     (every September measurement hazard is closed — #092/#093 server, #094
     clustering, #095 incubator wiring, #096 export, #098 cwd divergence, #099
     the clock), not for brief or recall QUALITY, because the defects that
     determine quality are precisely the ones still open. I would sharpen one
     thing: quality numbers taken during this run are not worthless, they are a
     **baseline** — record them for comparison after #097/#102/#103/#105 land,
     but do not read them as findings.
     qa's list (#114, #113, #100, #097, #102, #103, #105, #118, #116, #106) is
     accurate and I confirm it. Additions, all corpus- or operator-facing and
     open:
     - **#101** — placement writes no coords, so warm init can never fire. A
       `settle` in the run will reconcile COLD: expect more label churn between
       runs than "warm start reproduces the layout, ~0 delta" promises. Easy to
       mis-report as cluster instability.
     - **#110** — a re-run of `propagate` is not idempotent: expect doubled
       judge cost and doubled drift if it runs twice. Cost-facing as well as
       data-facing.
     - **#111** — `/health` reports the supervisor thread, not the reclaimer. If
       the run watches health (September's F23/F24 were exactly "health said ok
       while the worker was dead"), it can still read "alive" misleadingly.
     - **#054** — there is no sections->tree mapping, so ONE build clusters all
       three repos into a single tree. That was true in September too, so
       comparisons hold, but expect a map that mixes three unrelated projects;
       it is a known design gap, not a clustering failure.
     - **#102's root.md symptom, named explicitly** so it is not re-filed
       separately: the rendered `root.md` shows its child list TWICE — once as
       `Children:\n- node 1...` (raw ids, baked into the upper brief by
       `brief_upper.py:101`) and once as render's proper titled links. I saw
       this myself at #094's close. It is inside #102's scope.
     - **The chalk `source/vendor/**` decision (OPEN, human PO).** Not a ticket
       and not a defect: if it is left as-is, the run's chalk topic will NOT
       contain the two vendored dependencies that September's node-2 brief
       explicitly described, so a side-by-side brief comparison will look like a
       quality regression when it is a deliberate scope change. **Decide it
       before the run**, either way — it is one line of source config.
     One configuration constraint rather than an expected finding: **#067** is
     deferred on the "resolve the sole text model" default, so the run must
     register exactly ONE text model or condense/brief resolution breaks.
     Not expected and deliberately NOT on the list: #112 (76 sections is well
     above the 12-section floor), #115 (unreachable at one server/one worker),
     #119 (test-only routes), #076 (no `node-` prefixed source).
  2. **The retry caveat is CONFIRMED as defensible and bounded — no code change,
     but it must be pre-recorded.** A retried `update` IS another pass over the
     tree, so allocating another batch is the honest reading of "one batch per
     run"; making it idempotent would mean persisting an allocation per job id,
     which is real machinery for semantics that are already defensible. It is
     bounded: one extra tick per retry against a tolerance of `MAX_AGE` = 5.
     But qa is right that it interacts with #093, which made reclaim-and-retry
     NORMAL rather than exceptional, so it is no longer a theoretical path.
     Two consequences, both recorded rather than built:
     - **Into the re-run baseline**: if the batch counter ends higher than the
       number of successful update runs, retries are the explanation, not a
       regression of this ticket. Check `jobs` for retried runs before filing
       anything.
     - **Into #110**, which already owns re-run/retry idempotency: it should
       state the batch clock's retry semantics in the same pass, since a reader
       of "one batch per run" will otherwise be surprised by a retry making two.
     I am not filing a card for the behaviour itself. If the re-run shows
     retries materially inflating the clock — five or more in a run, or a chunk
     forced early because of them — that measurement is the trigger to file one.
