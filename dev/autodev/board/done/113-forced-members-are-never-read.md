---
id: 113
title: Force-assigned members are flagged but nothing ever reads the flag
priority: high
size: small
depends_on: [086, 089, 090]
spec_refs: [build-order.md#T35.3, build-order.md#T37, build-order.md#T38]
found_by: qa verification of 095 on 2026-09-14
---

## Context
`0017_incubator.sql` adds `node_members.forced` with an explicit promise:

> A member force-assigned to a cluster ignoring TAU ... flagged so the misfit
> monitor (T37) re-checks it preferentially and a mis-placed pioneer migrates
> once its real siblings form.

Neither half is implemented.

```
$ grep -rn "forced" src/
```
returns only writers (`cluster/store.py:239,254,261`, `cluster/incubator.py`,
`cluster/placement.py`). No reader anywhere.

## Description
`monitor._misfits` decides misfit purely as `best_other > own`. A force-assigned
chunk is attached to its NEAREST centroid by construction, so `own` is the
maximum and it is never counted as a misfit. `monitor.sample` picks its bounded
per-batch re-check by deterministic round-robin over node ids, with no
preference for clusters holding forced members. `repair.migrate` then triggers
only on a cluster's stored misfit rate, so it never moves the chunk either.

Measured on the real e2e corpus while verifying #095: replaying F29's stranded
state force-assigns `docs/unrelated-cooking-notes.md` into node 8 at similarity
**0.281** — far below TAU 0.70 — with `forced = 1`. Per T35.3 the assignment
itself is correct by design (a chunk outside the tree is unfindable). What is
missing is the second half: nothing ever revisits it, so an unrelated cooking
note sits inside a source-code topic and pollutes that topic's brief for ever.

## Description of the fix
Give the flag a reader. Either:
- `monitor.sample` prefers clusters that hold `forced` members, and a forced
  member is re-checked against TAU (not just against `best_other`), so a
  pioneer below TAU stays visible as a misfit; or
- `repair` grows a rule for forced members specifically — once the pool has
  produced a real cluster that fits it better, migrate it there and clear the
  flag.

Whichever is chosen, `forced` must be cleared when a member is re-placed
normally, or the flag accumulates and stops meaning anything.

## Acceptance criteria
- [ ] A force-assigned member below TAU is observable as a misfit through the
      monitor's stored counts, not just in `node_members.forced`.
- [ ] Once a better-fitting cluster exists, repair moves the forced member and
      clears the flag; a test proves the 0.281-style pioneer leaves the topic it
      was force-married into.
- [ ] `ruff format`, `ruff check --fix`, `pytest` clean.

## Decision (2026-09-14, PO — at #095's close)

**Raised medium -> `high`, and promoted to `todo/`.** I reproduced the 0.281
placement myself while reviewing #095 (`docs/unrelated-cooking-notes.md`
force-assigned into node 8 at similarity 0.2805, `forced = 1`), so this is
measured rather than argued.

Three reasons it outranks its filed priority:
- It is an **unimplemented promise already shipped**, written into migration
  `0017_incubator.sql`, not new scope.
- **#095 industrialised the producer without the corrector.** `age` and `drain`
  now force-assign on every update, so the rate of sub-TAU marriages goes UP as
  a direct consequence of closing #095. The two halves were specified together
  (T35.3 + T37) and only one shipped; that coupling is what moves the priority.
- A forced member **permanently degrades a brief**, and briefs are what the
  whole tree is made of. Retrieval quality is the product, not a polish item.

**Relationship to #104 (my earlier call: ignore junk at ingest) — they are
complementary, and neither may be closed on the other's account.** Ingest
filtering is globs, size caps and a null-byte sniff: it cannot recognise that a
cooking note is off-topic for a source-code repository, which is exactly the
observed case. #104 reduces the junk that arrives; #113 is the ONLY mechanism
that can correct junk once it has been placed. There is currently no downstream
correction at all — that is the gap.

The choice between the two named fixes (monitor reads the flag vs repair grows
a forced rule) stays dev's technical call. Both acceptance criteria must hold
whichever is picked, including clearing `forced` on a normal re-placement so the
flag keeps meaning something.

## Review log
- 2026-09-14 PO: raised medium -> high and promoted backlog -> todo at the close
  of #095, which is what made the producer routine. Confirmed it is not covered
  by #104.
- 2026-09-21 dev: started; moved to in-progress (batch with #105, #110, #101,
  #112).
- 2026-09-21 dev: implemented and committed as `0a2d10c`.

  **Both named fixes, because neither alone closes the ticket.** The ticket
  offered monitor-reads-the-flag OR repair-grows-a-rule; working through the
  arithmetic, each is inert without the other:
  - monitor alone: a forced member becomes visible as a misfit, but one alien
    member in seven is a rate of 0.14, under `MISFIT_THRESHOLD` 0.25, so
    `repair` never calls `migrate` and the pioneer still never leaves;
  - repair alone: `migrate` would move it, but nothing ever selects its cluster
    once the batch that forced it stops being dirty.

  **Monitor (`cluster/monitor.py`).** `_misfits` now counts a member as a misfit
  when `best_other > own` OR it is `forced` and its own similarity is below TAU.
  This is the exception the original rule cannot express: a forced member was
  attached to its NEAREST centroid by construction, so `own` is the maximum and
  `best_other > own` is false however alien it is. `sample` grew a `prefer`
  argument — clusters holding a forced member jump the round-robin — and
  `monitor` passes `store.forced_holders`. Deterministic and bounded as before.

  **Repair (`cluster/repair.py`).** `_needs_migrate` triggers the migrate rule
  on the stored rate OR the presence of a forced member. `migrate`'s move
  condition needed no change: if a better cluster exists at all, `best > own`
  already holds. `store.add_member(..., forced=False)` on the move is what
  clears the flag, so "re-placed normally" and "flag cleared" are the same
  write. (`placement.assign_or_park` already re-places unforced, so the
  dissolve-survivor path was correct already.)

  **Store (`cluster/store.py`).** Two readers for a column that had only
  writers: `forced_members(node_id)` and `forced_holders(tree)`.

  **The measured case, reproduced as a test.** F29's
  `docs/unrelated-cooking-notes.md` at 0.281: six topic-0 members plus one
  forced alien. Rate 1/7 = 0.14, asserted BELOW the threshold in the test, so
  the old trigger provably could not fire; once its real siblings form a
  cluster, `repair` moves it there and the flag is gone.

  Tests (6 new, 782 total): forced-below-TAU is a misfit; the identical member
  unforced is NOT (the control that proves the flag is what is read, since the
  geometry alone says nothing); a forced member that actually fits is not a
  misfit (forcing is not guilt, and the rate must not inflate for ever); the
  sample preference; the pioneer leaving; and a pioneer with nowhere better
  staying put WITH its flag, so the next batch looks again.
  Mutations, all killed: dropping the forced rule, dropping its TAU check,
  dropping the sample preference, reverting the repair trigger to rate-only,
  and keeping `forced=True` on the move.

  Not touched: #104 (complementary, as the PO ruled), #124, #123.
  Gate clean: `ruff format`, `ruff check --fix`, `pytest` **782 passed**.
- 2026-09-21 qa: **PASS — to po-review.** Both acceptance criteria hold, and the
  decision to implement BOTH named fixes rather than either is correct — I
  checked the arithmetic dev gives and it is right: one alien member in seven is
  a rate of 0.14, so the monitor half alone leaves the pioneer married for ever,
  and the repair half alone is never reached once the batch stops being dirty.
  The ticket offered a choice between two halves of one mechanism.

  **Verified independently:**
  - The control test is the one that makes this ticket provable: the SAME member
    with the SAME vectors and the flag off is not a misfit. Without it, the new
    count could have been geometry rather than the flag, and the ticket's whole
    claim ("nothing reads the flag") would be untested.
  - Forcing is not treated as guilt: a member forced into a cluster it fits at
    or above TAU is not counted, so the rate does not inflate permanently. That
    is the right reading of 0017 and it is tested.
  - `migrate`'s move condition genuinely needed no change — if a better cluster
    exists, `best > own` already holds — and `add_member(..., forced=False)` is
    what clears the flag, so "re-placed normally" and "flag cleared" are one
    write rather than two that can disagree.
  - A pioneer with nowhere better keeps BOTH its place and its flag: the repair
    does not shuffle it into a worse home just because it is flagged.
  - Mutations re-run by me, all killed: dropping the forced rule, dropping its
    TAU check, dropping the sample preference, reverting to the rate-only
    trigger, and keeping `forced=True` on the move.
  - Import direction is clean: `monitor` -> `placement` for TAU, and `placement`
    does not import `monitor`, so no cycle.
  - Real corpus (`.e2e/run2`, on a COPY): 0 forced members today, so this path
    could not be exercised there — the evidence for it is the planted-geometry
    tests, which is the honest available proof. Noted rather than glossed.

  **Filed, not blocking: #129.** The preferred slice of `sample` is taken in
  sorted node-id order and is not rotated by the batch seed, so above
  `SAMPLE_SIZE` (32) forced holders the same 32 are re-checked for ever
  (verified: seeds 1, 2 and 99 give an identical pick; holders 33+ never
  sampled). It does not block this ticket — `repair._needs_migrate` iterates
  every cluster and reads the flag directly, so a starved holder's pioneer still
  migrates, and a newly forced member's cluster is dirty in its own batch — so
  it is a staleness bound on the COUNT, not a correctness hole.

  Gate re-run by me: 789 passed, ruff clean. Commit atomic and conventional.

## Review log (PO)
- 2026-09-21 PO: **PASSES — closed to done.** Both criteria met, and the call to
  implement both halves rather than pick one is right — I wrote that ticket
  offering a choice and the choice was wrong. The arithmetic settles it: one
  alien member in seven is a rate of 0.14 against a threshold of 0.25, so the
  monitor half alone leaves the pioneer exactly where it was, and the repair
  half alone is never reached once the batch stops being dirty. They were
  specified together in 0017 because they are one mechanism. Ticket authors
  should not offer an either/or that the numbers do not support; noted for my
  own future tickets.

  The control test is what makes me confident: the same member, same vectors,
  flag off, not a misfit. Without it the new count could have been geometry, and
  the whole claim of this ticket — that the flag had no reader — would have gone
  unproven. And "forcing is not guilt" (a forced member that actually fits is
  not counted) is the part I would have missed writing the ticket; a permanently
  inflated rate would have pulled settle forward on trees that had earned
  nothing.

  **This closes an unimplemented promise that shipped in a migration comment.**
  That is the category I care most about: 0017 told a reader that mis-placed
  pioneers migrate once their real siblings form, and until this commit that
  sentence was fiction. Retrieval quality is the product, and a cooking note
  sitting inside a source-code topic poisons that topic's brief for every query
  that reaches it.

  qa's **#129** (holders past `SAMPLE_SIZE` starve the sample rotation) stays
  `low` in backlog and I agree with the reasoning for not blocking: repair
  iterates every cluster and reads the flag directly, so the correction still
  reaches a starved holder — what starves is the count refresh. Revisit if a
  real corpus ever shows more than 32 clusters holding forced members.
