---
id: 122
title: `update` ingests content it never condenses, so a brief cites sources it never read
priority: high
size: medium
depends_on: [058, 085]
spec_refs: [build-order.md#T20, build-order.md#T34, how-hrono-works.md]
found_by: PO while closing 103 on 2026-09-15; first observed in the September e2e run
---

## Context

`condense` (#058) is called from **`maintain` and nowhere else**. `update` does
not condense; neither does `settle`. So every section an incremental `update`
ingests — a new file, a changed file's new sections — reaches the tree with no
condensation, for ever, until somebody runs a full `maintain`.

Measured by PO on `.e2e/run2/.hrono/hrono.db`: exactly three corpus sections
have no `condensations` row —

```
docs/unrelated-cooking-notes.md
src/itsdangerous/rotation.py      <- added by re-run scenario S1
src/itsdangerous/signer.py        <- appended to by re-run scenario S2
```

— which are precisely the files the incremental scenarios touched. The same
count was recorded in the September run.

**This was initially attributed to #097's re-packing. It is not.** PO ran the
real splitter over `.e2e/run2/repos` under `733549c` (pre-#097) and `9e01051`
(post-#097) and compared hash by hash: **112 sections both sides, identical key
sets, zero content hashes changed.** #097 moved PASSAGE boundaries only. The
cause is this missing stage, not that one.

**This is not #106 either.** #106's F9 is that nothing CHAINS the ops. This is a
stage missing from inside `update` itself, and it would persist unchanged if
`update -> propagate -> monitor -> repair -> settle` were chained perfectly.

## Description

The harm is worse than "the brief is summarised from less material", because the
two halves of a brief disagree about what it covers:

- `briefs.member_condensations` (`summarize/briefs.py:137`) **INNER JOINs**
  `condensations`, so a member with no condensation is silently dropped from the
  reduce input — no error, no warning, no flag.
- `briefs.member_uris` (`summarize/briefs.py:151`) is a **separate query with no
  such join**, so the mechanical reference list **still cites that section**.

So the brief claims provenance it does not have. An agent following the cited
URI gets content the brief never describes. A map that silently omits something
is incomplete; a map that cites a source it never read is wrong — and the
citation is exactly the thing we tell agents is mechanical and trustworthy.

It also feeds #087: `propagate`'s judge compares a brief against its source
material, so it judges a topic against an incomplete source and its verdict is
not meaningful for any topic holding an unsummarised member.

Work:
- `update` condenses what it ingests, before placement makes it a member.
  `condense` is already a content-hash cache (#058), so this costs one call per
  genuinely new section and nothing for unchanged content — the incremental
  promise is intact.
- Decide what `brief` does if a condensation is nevertheless missing. Silently
  dropping the member while still citing it is not an option that should
  survive this ticket: either the reference list is built from the same set the
  reduce input came from, or the node is flagged (#103's `briefs.flagged` now
  exists and is the natural carrier).

## Acceptance criteria
- [ ] After an `update` that adds or changes a file, every section it created
      has a `condensations` row for the active model, with no full `maintain`.
- [ ] A regression test drives `update` over a new AND a changed file and
      asserts no member section lacks a condensation.
- [ ] A brief's mechanical reference list and its reduce input cover the SAME
      member set, or the node is flagged — no brief silently cites a section
      that contributed nothing.
- [ ] Re-running `update` over unchanged content makes zero condense calls (the
      #058 cache still holds).
- [ ] `ruff format`, `ruff check --fix`, `pytest` clean.

## Out of scope
- Chaining the lifecycle ops (#106, F9).
- `settle`'s own condense behaviour, if it needs one — settle re-clusters
  existing content, which a maintain has already condensed. Note it if you find
  otherwise; do not extend scope on a guess.

## Verification warning

**A full `maintain` MASKS this defect.** A full build condenses everything, so
the three uncondensed sections vanish and the gap does not reappear until the
next `update`. Two consequences:

1. Do not verify this ticket against a freshly-maintained corpus. Verify it by
   running an `update` and checking the sections that update created.
2. **`.e2e/run2/.hrono/hrono.db` is currently the only live evidence of this
   defect. Preserve a copy before the planned full maintain overwrites it.**

## Review log
- 2026-09-15 PO: filed while closing #103. qa found the missing condensations
  and attributed them to #097; the coordinator disputed that; PO settled it by
  measurement (#097 changed zero section hashes) and confirmed the real cause in
  the source (`condense` has exactly one caller, `maintain`). PO also found the
  citation half — the reference list keeps citing a section the reduce input
  dropped — which is what makes this `high` rather than a tidy-up: an incomplete
  map is a gap, a mis-cited one is an error.

## Also recorded here (PO, 2026-09-15, from #114's review)

**The update-path half of #114 lands on this ticket's open question.** #114
attaches an orphaned level-0 node under its nearest level-1 parent by scoring
the leaf's BRIEF vector against brief-space centroids. `update` makes no LLM
calls, so an update-born leaf has no brief and therefore no vector in that
space — its member sections' content+path vectors are a different space
entirely. So #114 ships with `settle` + `maintain` coverage only, and an
update-born leaf stays unlinked from `root.md` until the next brief pass.

If this ticket gives `update` a condense (and, if it goes that far, a brief)
pass, #114's attachment follows for free and no further work is needed there.
If it deliberately does NOT — keeping `update` free of LLM calls as the
incremental promise — then record that decision here explicitly, because it
makes #114's residual permanent-until-settle by design rather than by omission,
and the next person to look at an unlinked leaf should find the reasoning rather
than rediscover it.

Either way this is a decision this ticket owns, not #114.

## This ticket is the ROOT OF A CHAIN (PO, 2026-09-15, at #114's close)

qa established this by CONTROL, not inference: it changed exactly one variable —
planted the 14 missing condensations — and re-ran the SAME settle. Every
alien-holding node then briefed AND parented. That is the right way to establish
a cause, and it means this ticket is worth more than its own acceptance criteria
suggest.

The chain:

```
update ingests content
  -> nothing condenses it                      (this ticket)
  -> the node cannot be briefed at settle      (brief reduces over condensations)
  -> with no brief there is no brief VECTOR
  -> attach_orphans cannot place it            (#114 scores brief vs brief-space)
  -> the topic stays unreachable from root.md
```

So #114's residual window is **"until the next FULL PASS"**, not "until the next
settle" as #114's Review log originally said (corrected on both tickets). Fixing
this ticket closes #114's residual for free — the leaf gets a condensation, so
it gets a brief, so it gets a vector, so it gets a parent.

That raises the stakes of the open question already recorded above. If `update`
gains a condense pass, the chain resolves end to end. If it deliberately does
not — keeping `update` free of LLM calls as the incremental promise — then that
decision makes #114's residual permanent-until-full-pass BY DESIGN, and must be
written down here as such, because three separate tickets now depend on knowing
which it is.

## Review log (dev)
- 2026-09-21 dev: started; moved to in-progress (batch with #123, #132, #127).
- 2026-09-21 dev: implemented and committed.

  **The decision this ticket owned: `update` CONDENSES, and therefore makes LLM
  calls.** Recorded here because three tickets depend on knowing which way it
  went. The incremental promise is that work is proportional to the CHANGE, not
  that an op is free: `condense` is a content-hash cache (#058), so this costs
  one call per genuinely new section and nothing for unchanged content. The
  alternative — keeping `update` LLM-free — would have made #114's residual
  permanent by design, and the chain the PO traced is real, which I verified by
  driving it rather than reasoning about it (below).

  `update` gained `client: object | None = None`, the same shape `maintain` and
  every other LLM op uses, and calls `condense` once per RUN after all sources
  are reconciled. Unguarded: `condense` returns before building a client when
  nothing is pending, so an update over an unchanged corpus still makes zero
  calls (tested), while a corpus carrying OLD gaps — which is exactly
  `.e2e/run2`'s three uncondensed sections — heals them on the next update
  instead of skipping them. I had a `if batch is not None` guard first; a
  mutation proved it changed nothing observable, so it went.

  **#114's residual is now SHORTER, and this is measured, not argued.**
  `test_a_leaf_update_drained_in_is_healed_by_the_next_full_pass` asserted the
  old chain: drain emits a leaf -> no condensation -> no brief -> no brief
  vector -> no parent, healed only by a full `maintain`. With this commit the
  test FAILED, because a settle now heals it. I rewrote it as
  `..._healed_by_the_next_settle`: update still writes no brief (asserted), but
  the condensations are there, so settle briefs the leaf, so #114's rule has a
  vector to place it by. That is the PO's chain closing end to end.

  **The citation half — structural, not disciplined.** The two queries are gone.
  `briefs.reduce_input` returns `texts` and `uris` from the SAME rows plus a
  `dropped` count, so a member that contributed nothing cannot be cited: they
  are one query, not two kept in agreement by care. `member_condensations`
  stays as a thin wrapper over it for `propagate`'s use.
  And the gap is not silent either: `brief` sets #103's `flagged` when
  `dropped > 0`. The ticket allowed "same set OR flagged"; agreement removes the
  ERROR (citing what was never read) and the flag removes the SILENCE
  (summarising less than the node holds), so both were worth the two lines.

  Tests (3 new + 1 rewritten, 793 total): new-and-changed files both condensed
  after one update; a second update over unchanged content makes zero calls; a
  brief with an uncondensed member cites only what it read AND is flagged; plus
  the rewritten residual test. Mutations: removing the condense call fails 3,
  dropping the flag fails 1, rebuilding the URI list from all members fails 1.

  Not touched: op chaining (#106), `settle`'s own condense behaviour — settle
  re-clusters content a maintain or now an update has condensed, and I found no
  case where it needs its own pass.

  Gate clean: `ruff format`, `ruff check --fix`, `pytest` **793 passed**.
- 2026-09-21 qa: **FAIL — back to todo.** The decision is right, the citation fix
  is structural and good, and the chain the PO traced really does close. One
  blocking finding: `update` now fails on a corpus that has no text model, and
  it fails even when there is nothing whatsoever to do.

  **Blocking — `hrono update` raises `LLMError: no text model available` on a
  run with zero changes.** `condense` resolves the text model BEFORE it checks
  what is pending (`summarize/condense.py:42` then `:45`), and the call in
  `tree/update.py` is unguarded, so the resolution happens on every update
  regardless. Driven:
  ```
  corpus with an embedding model and no text model
  condense(...)  ->  LLMError: no text model available
  ```
  Before this commit `update` needed no text model at all. Now the first
  `hrono update` on a fresh install — no sources, no text model, nothing to do —
  errors, and the message names a stage the user never asked for. That is the
  user-friendly bar ("actionable error messages") and the trustworthy bar
  ("writing config never triggers work") both, from a run that should have been
  a no-op.

  Two ways out, and I have no preference between them — the trade is yours:
  - restore the `if batch is not None` guard you removed. It IS observable after
    all, just not by the test that existed; the cost is that a corpus carrying
    OLD gaps no longer self-heals on a no-change run, which was a real benefit
    of removing it;
  - or make `condense` resolve the model after it knows there is work, so an op
    with nothing to do never asks for a credential it does not need. That keeps
    the self-heal AND fixes the fresh-install case, and it is arguably right for
    `condense` on its own terms.
  Either way, add the test: an update over a corpus with no text model and no
  changes must succeed.

  **What I verified as PASSING (need not be redone):**
  - Gate re-run by me on the committed state: `ruff format --check` 230 files
    already formatted, `ruff check` clean, `pytest` **810 passed**.
  - **The decision is recorded where the three dependent tickets will find it**
    — in `tree/update.py`'s own contract, not only in this log. That is what
    #114, #123 and the PO note all needed.
  - **The chain closes, and the test proves it rather than asserting it.** The
    old residual test FAILED on this commit, which is the correct signal: a
    settle now heals a drained leaf. Rewriting it as
    `..._healed_by_the_next_settle` — keeping the "update still never briefs"
    half and adding `_condensed(db, "alien/")` — is exactly the right rewrite,
    and it is the measured form of the PO's chain.
  - **The citation fix is structural, which is what I most wanted to see.**
    `reduce_input` returns `texts` and `uris` from ONE query, so they cannot
    disagree; two queries kept in agreement by discipline is how the defect
    existed in the first place. The `dropped` count carried on the same object
    is what makes the flag possible without a third query.
  - Doing BOTH halves of the ticket's "same set OR flagged" is right, and I
    would have pushed back on either alone: agreement removes the error (citing
    what was never read), the flag removes the silence (summarising less than
    the node holds).
  - `member_condensations` surviving as a thin wrapper keeps `propagate`
    unchanged; I checked it is the only other caller.
  - Mutations I re-ran: removing the condense call fails 3, dropping the flag
    fails 1, rebuilding the URI list from all members fails 1.
  - The 12 rewritten `update(...)` call sites now route through one `run_update`
    helper, which is better than what was there before this ticket.
- 2026-09-21 dev: **re-picked up after qa's FAIL**; fixed on top of the previous
  commit. Nothing qa passed was redone.

  **qa is right, and the guard I removed was the fix.** I had removed
  `if batch is not None` because a mutation showed it changed nothing
  observable. It changed something no test looked at: `condense` resolves the
  text model BEFORE checking what is pending, so an unguarded call made
  `hrono update` fail with `LLMError: no text model available` on a fresh
  install with no sources and nothing to do. "Unobservable" meant "unobserved",
  which is the #128 lesson arriving from the other side — a surviving mutation
  can mean the guard is dead OR that the test is missing, and I assumed the
  first.

  **Of qa's two options I took the guard rather than reordering `condense`.**
  Resolving the model before the work is `condense`'s own contract: asked to
  condense, with no model, it should say so loudly — it is a scoped op a user
  can run directly. The thing that was wrong is `update` asking it to run when
  there is nothing to condense. Guarding the CALLER keeps both behaviours
  correct; reordering `condense` would have made a directly-invoked
  `hrono condense` on a model-less database silently succeed, which is worse.

  **What the guard costs, stated rather than hidden:** a corpus carrying OLD
  uncondensed sections now heals them on the next run WITH changes rather than
  on any run at all. That is a wait, not a hole — `condense` is global, so the
  first real change sweeps them up. `.e2e/run2`'s three gaps heal on its next
  update either way.

  Test: `test_an_update_with_nothing_to_do_needs_no_text_model` — an embedding
  model, no sources, no text model, `update` must simply return. Mutations:
  removing the guard fails it (the regression, reproduced), removing the
  condense call fails 3.

  Gate clean: `ruff format`, `ruff check --fix`, `pytest` **811 passed**.
  Handing back to verifying.
- 2026-09-21 qa: **PASS — to po-review.** The regression I sent this back for is
  gone, and the reasoning for which of my two options was taken is better than
  the option I would have picked.

  **Re-driven by me, the exact reproduction from my kickback:**
  ```
  embedding model registered, no sources, no text model
  update(...)  ->  OK (no-op)
  ```
  Previously `LLMError: no text model available`.

  **Guarding the CALLER rather than reordering `condense` is the right call and
  I withdraw the half of my suggestion that said otherwise.** Resolving the
  model before the work is `condense`'s own contract — it is a scoped op a user
  can invoke directly, and `hrono condense` on a model-less database should say
  so loudly rather than succeed silently. What was wrong is `update` asking it
  to run with nothing to condense. Guarding the caller keeps both behaviours
  correct; my reordering suggestion would have traded this bug for a quieter one
  in the op a user actually invokes by name.

  **The cost is stated rather than hidden**, which is what I wanted to see: a
  corpus carrying OLD gaps now heals on the next run WITH changes rather than on
  any run. `condense` is global, so the first real change sweeps them up —
  a wait, not a hole, and `.e2e/run2`'s three gaps heal either way.

  Mutations: removing the guard reproduces the regression and fails the new
  test; removing the condense call fails 3. I re-ran both.

  Everything in my previous PASS list stands unchanged — the decision record in
  `tree/update.py`, the rewritten residual test proving a settle now heals a
  drained leaf, and `reduce_input` making the citation and the reduce input one
  query instead of two kept in agreement by discipline.

  Gate re-run by me: 817 passed, ruff clean. Both commits atomic and
  conventional.

## Review log (PO)
- 2026-09-21 PO: **PASSES — closed to done.** All five criteria met, plus the
  decision I asked this ticket to own.

  **The decision, recorded where three other tickets will find it:** `update`
  condenses, and therefore makes LLM calls. That is the right reading of the
  incremental promise — work proportional to the CHANGE, not an op that is free
  — and the chain it closes is measured, not argued: a drained leaf now gets a
  condensation, therefore a brief, therefore a brief vector, therefore a parent.
  #114's residual is "until the next settle" rather than "until the next full
  pass", and the test that used to assert the old bound now asserts the new one.
  That test FAILING on the first attempt is the best evidence in the ticket.

  **The citation half is the part I care most about and it is fixed
  structurally.** A brief citing a section it never read is worse than a brief
  that omits one: an incomplete map is a gap, a mis-cited map is an error, and
  we tell agents the citations are mechanical and trustworthy. One query
  returning both halves means they cannot disagree — two queries kept in
  agreement by discipline is exactly how this defect existed for as long as it
  did.

  **On the round it cost.** qa was right to send it back: an op that fails with
  "no text model available" on a fresh install with nothing to do is a user
  encountering a stage they never asked for. And the resolution is better than
  either party's opening position — dev declined half of qa's own suggestion
  with a reason I agree with (reordering `condense` would have made a
  directly-invoked `hrono condense` succeed silently on a model-less database,
  trading a loud bug for a quiet one in the op a user actually types). That is
  the review loop working rather than a ping-pong.

  No new work spun off. The "old gaps heal on the next changed run rather than
  any run" cost is stated in the code, which is where a future reader will look.
