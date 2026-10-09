---
id: 110
title: propagate is not idempotent on a re-run — double judge cost, double drift
priority: high
size: small
depends_on: [087, 093]
spec_refs: [build-order.md#T36, build-order.md#T39]
found_by: qa verification of 093 (2026-09-14); promoted by PO review of 093
---

## Context
#093 makes the worker reclaim a job left `running` by a dead worker and re-run
it. Its decision block accepted that "because every expensive stage is
content-hash cached" — true for `condense` and `embed`, and `brief` gap-fills,
but **not** for `propagate`, which is the op F24 actually stranded. PO ruled at
093's close that this does not block 093 (the counterfactual — a silently dead
queue — is far worse, and the damage is cost and audit fidelity, not data
integrity) but that it must be fixed, since 093 turns reclaim-and-re-run from a
never-event into a normal one.

The sharp case is the failed-`_finish` path 093 now recovers: `propagate`
commits **all** its writes in one transaction at the end, so a status write
that fails after that transaction leaves a job whose work is already done. The
re-run duplicates it rather than completing it.

## Description
`src/hrono/summarize/propagate.py:75-88` (`_changed_leaves`) selects leaves
purely by `briefs.member_signature(conn, node_id) != brief["member_signature"]`,
and `_record` (`propagate.py:124-132`) never clears that condition — it marks
ancestors stale, logs, and bumps drift, but leaves the leaf's stored
`member_signature` alone. So a reclaimed re-run of the same `propagate` job:

- re-selects exactly the same leaves;
- re-issues `BEST_OF` = 3 judge completions per leaf (real money; the e2e run
  measured 8-32 s per call);
- writes a second `update_log` row per topic, so the audit trail double-counts
  (no reader today — this is debt the M10 dashboard would inherit);
- `_bump_drift` (`propagate.py:163-167`) is additive
  (`ON CONFLICT ... SET drift = drift + ?`), so drift inflates toward
  `tree/settle.py:38` `CHURN_THRESHOLD = 50` and can pull forward a warm
  reconcile the tree did not earn.

Make a re-run of `propagate` a no-op for leaves already judged: record what was
judged (the judged member signature, or the batch) so `_changed_leaves` skips
them, and make the drift bump idempotent per (tree, node, batch) rather than
blindly additive.

## Open question — flag, do not guess
Recording the judged signature onto the leaf's brief is the obvious fix, but
`briefs.member_signature` is also what #064 uses to decide whether a brief may
be skipped on a re-brief, and `_record` deliberately calls `briefs.mark_stale`
on ancestors *without* touching members (#087). Confirm that marking a leaf
judged cannot suppress a genuine later re-brief; if it can, carry the judged
marker in a separate column or in `update_log` instead of mutating
`briefs.member_signature`. State which you chose and why in the Review log.

## Acceptance criteria
- [ ] Running the same `propagate` job twice over an unchanged tree issues one
      set of judge completions, not two (test asserts the call count on a stub
      `Completion`).
- [ ] The second run writes no additional `update_log` row per topic.
- [ ] The second run leaves `tree_batch.drift` unchanged — one increment per
      judged topic, not two.
- [ ] A leaf whose membership genuinely changes *after* a propagate run is
      still selected and judged on the next run (the fix must not suppress real
      work).
- [ ] A regression test fails if any of the above regresses.
- [ ] `ruff format`, `ruff check --fix`, `pytest` clean.

## Out of scope
- Worker/reclaim machinery — #093 is closed and correct; do not touch
  `jobs/worker.py` or `jobs/store.py`.
- `/health` reading liveness from the heartbeat column — that is #111.
- Idempotency audits of `condense`, `embed`, `brief`, `monitor`: all three were
  checked during 093's review and are safe to re-run as they stand.

## Review log
- 2026-09-14 qa: filed from 093 verification; not blocking 093 (pre-existing
  #087 debt that 093's reclaim exposes).
- 2026-09-14 PO: triaged at 093's close. Confirmed the defect by reading
  `propagate.py` and traced the blast radius: `update_log` has no readers yet,
  and an early `settle` is a near-no-op that resets the counter — so this is a
  cost and audit-fidelity bug, not an integrity one. `priority: high` and
  `depends_on: [087, 093]` confirmed as filed. Rewritten to Definition of
  Ready, the `/health` item split out to #111, and promoted to `todo/`.

## Added by PO (2026-09-15, at #099's close)

**Also state the batch clock's retry semantics, here.** #099 settled that
`tree_batch.batch` is "one `update` RUN over the tree", allocated lazily by the
first source with changes. A RETRIED update job is a fresh run and allocates
another batch. That is defensible — a retry genuinely is another pass, and
making it idempotent would mean persisting an allocation per job id, real
machinery for semantics that already read correctly — and it is bounded at one
extra tick per retry against a `MAX_AGE` tolerance of 5.

But #093 made reclaim-and-retry NORMAL rather than exceptional, so a reader of
"one batch per run" will meet a retry that makes two. This ticket already owns
re-run/retry idempotency, so it is the right place to say so: one sentence in
`tree/update.py` next to the contract, naming the retry case explicitly.

No behaviour change is being asked for. If the end-to-end re-run shows retries
materially inflating the clock (five or more in one run, or a chunk forced early
because of them), that measurement is the trigger to file a real ticket for
idempotent allocation — not before.

## Acceptance criteria (added)
- [ ] `tree/update.py`'s batch-contract docstring states that a retried run
      allocates a new batch, and why that is intended.

## Review log
- 2026-09-15 PO: folded in the retry-semantics note at #099's close. Same class
  of concern (re-run/retry idempotency), same pass, no separate card.

## Review log (dev)
- 2026-09-21 dev: started; moved to in-progress (batch with #105, #113, #101,
  #112).
- 2026-09-21 dev: implemented and committed as `24653d0`, on top of #105's
  `e9194f0` (same file; #105 landed first).

  **The open question, answered: a SEPARATE column.** Migration `0026` adds
  `briefs.judged_signature`. Writing the marker into `member_signature` — the
  obvious fix the ticket names — would make `_is_fresh` see the brief as fresh
  and #064 would skip a genuine re-brief. That is not a theoretical risk: I
  mutated `mark_judged` to write `member_signature` and the whole suite stayed
  green except one incidental test, so I added
  `test_judging_a_leaf_does_not_suppress_its_re_brief`, which asserts
  `briefs.stale_or_missing` still returns the leaf after judgement. The two
  clocks are now independent by construction and pinned by a test.

  **The skip.** `_changed_leaves` carries the current signature on `_Topic` and
  skips a leaf whose `judged_signature` already equals it. `_record` writes the
  marker for every REACHED verdict — `none` included, since a skip is a
  judgement — via `briefs.mark_judged`.

  **An abstention deliberately writes no marker.** #105 made a whole-panel
  abstention possible; that topic was not judged, so a re-run must try it again
  rather than inherit "already handled" from a panel that answered nothing.
  Tested.

  **A re-brief clears the marker for free.** `briefs.upsert` is
  `INSERT OR REPLACE` and does not list the column, so a regenerated brief resets
  it to NULL — a new brief has not been judged. Tested rather than assumed.
  (`briefs.get` had to project the new column; it selects explicitly, not `*`.)

  **Drift needed no second mechanism.** The ticket suggests making the bump
  idempotent per (tree, node, batch). `_bump_drift` is reachable only through
  `_changed_leaves`'s selection, so the skip already makes it fire once per
  judged topic; a per-(tree, node, batch) ledger would be machinery guarding a
  path that can no longer be taken twice. The criterion is asserted directly
  (drift 2 after two runs, not 4).

  **Batch retry semantics** (PO's fold-in): stated in `tree/update.py`'s batch
  contract, next to the lazy-allocation paragraph — a retried run is a fresh run
  and allocates another batch, with the reasoning and the bound (one extra tick
  against a MAX_AGE of 5). No behaviour change, as asked.

  Not touched: `jobs/worker.py`, `jobs/store.py` (#093 closed), `/health`
  (#111).

  Tests (5 new, 776 total): the reclaimed re-run (calls, audit rows and drift
  all unchanged on the second pass), a real membership change still judged, the
  re-brief clearing the marker, an abstention re-judged next run, and the
  re-brief-suppression guard. Mutations: removing the skip fails 1, marking an
  abstention fails 1, freezing the marker value fails 1, writing
  `member_signature` instead fails 2.

  Gate clean: `ruff format`, `ruff check --fix`, `pytest` **776 passed**.
- 2026-09-21 qa: **PASS — to po-review.** Every acceptance criterion holds,
  including the added one, and the flagged open question was answered the right
  way for the right reason.

  **The open question is answered correctly, and the answer is pinned.** A
  separate `judged_signature` column, not `member_signature`. I re-ran dev's
  own mutation: writing the marker into `member_signature` leaves the whole
  suite green apart from the tests dev added for exactly this, and
  `test_judging_a_leaf_does_not_suppress_its_re_brief` asserts the property
  through `briefs.stale_or_missing` — the real #064 reader — rather than
  through a proxy. That is the right place to assert it.

  **Verified independently:**
  - The read/write window: `_changed_leaves` reads outside the write lock and
    `_record` writes inside it. If a leaf's membership changes in between, the
    marker is written against the OLD signature, so the next run re-judges it.
    That is the safe direction (re-judging costs money, skipping costs
    correctness), and it is the direction the code takes.
  - An abstention writing no marker is right and tested: a panel that answered
    nothing has not judged the topic, and inheriting "already handled" from it
    would be the silent suppression #105 exists to prevent.
  - The re-brief reset is a property of `INSERT OR REPLACE` not listing the
    column — fragile-looking, but tested directly rather than assumed, which is
    what makes it safe to rely on.
  - Drift: I accept dev's argument that no second mechanism is needed.
    `_bump_drift` is reachable only through `_changed_leaves`' selection, and
    the criterion (drift 2 after two runs, not 4) is asserted directly. A
    per-(tree, node, batch) ledger would guard a path that can no longer be
    taken twice.
  - `briefs.get` projects explicitly, so the new column had to be added there —
    dev found that through a failing test rather than shipping a silent
    `judged_signature is None` forever. Worth noting as the reason the column
    reads correctly.
  - The `tree/update.py` retry-semantics paragraph says what the PO asked for
    and changes no behaviour.
  - Mutations re-run by me: removing the skip fails 1, marking an abstention
    fails 1, freezing the marker value fails 1, `member_signature` fails 2.

  Migration `0026` is additive (`ALTER TABLE ... ADD COLUMN`, nullable, no
  default backfill needed) and its comment states the reasoning rather than
  restating the SQL. No `jobs/` files touched, as the ticket required.

  Gate re-run by me: 789 passed, ruff clean. Commit atomic and conventional.

## Review log (PO)
- 2026-09-21 PO: **PASSES — closed to done.** Every criterion met, including the
  retry-semantics note I folded in at #099's close.

  The open question I flagged was the point of this ticket and it was answered
  the way I hoped: a separate column, because the obvious fix would have made a
  judged leaf look freshly-briefed to #064 and suppressed a real regeneration.
  What makes me comfortable closing it is that the answer is a TEST against the
  real reader (`briefs.stale_or_missing`), not an argument — dev mutated their
  own fix to prove the shortcut was wrong before rejecting it.

  The abstention carrying no marker is the correct seam with #105: a panel that
  answered nothing has not judged anything, so a re-run must pay for it again.
  Paying twice for a real failure is the right direction; skipping it silently
  is not.

  I accept the reasoning on drift. `_bump_drift` is reachable only through the
  selection the skip now guards, so a per-(tree, node, batch) ledger would be
  machinery defending a path that can no longer be taken. The criterion is
  asserted where it is observable (drift 2 after two runs, not 4), which is what
  I actually care about.

  No new work spun off. The audit-trail concern this ticket raised in passing
  ("`update_log` has no readers today — this is debt the M10 dashboard would
  inherit") is now a card of its own, **#132**, raised at #105's close.
