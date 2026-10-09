---
id: 067
title: role->model mapping for text models (condense/brief/brief-upper/judge) + cross-model condensation read
priority: medium
size: medium
depends_on: [058, 059]
spec_refs: [implementation-notes.md, summarization-experiments.md, build-order.md#M4]
---

## Context
Spun off from #058/#059. The spec's per-tree config maps a ROLE to a model name
(`"models": {"condense": "cheap", "brief": "smart", "judge": "cheap"}`), but there
is no storage for it: `Model` (#018) has `kind` but no `role`, and both the
condense (#058) and brief (#059) ops resolve "the sole text model, or the one
named in scope" (`summarize/resolve.resolve_text_model`). That is the agreed YAGNI
default and is correct WHILE there is one text model — but it hides a real coupling
that becomes a bug the moment condense and brief use DIFFERENT models.

## The landmine to fix (qa observation on #059)
`brief` reads its member condensations keyed by the model name it itself resolves,
and records provenance under that name too (`briefs.member_condensations(conn,
node_id, model_name)` where `model_name` is the BRIEF model). Condensations are
stored by #058 under the CONDENSE model's name. Today those are the same sole
text model, so the join matches. With a distinct condense vs brief model, `brief`
would look up condensations under the brief model's name and find NONE — silently
briefing empty input. When role->model lands, brief MUST read condensations under
the CONDENSE model, not the brief model.

## Description (when pulled in)
- Give the summarisation roles a model mapping: a `role` on text models, or a
  per-tree/global `role -> model-name` config block (decide against the spec's
  tree config shape — do not invent a third mechanism).
- `resolve_text_model` gains a role argument: condense resolves the condense
  model, brief the brief model, brief-upper the brief-upper model, judge the
  judge model. Keep the sole-text-model fallback when no mapping is set.
- FIX THE COUPLING: `brief` reads condensations under the CONDENSE role's model
  name (the producer), independent of the brief model it calls. Same for any
  op that consumes another op's model-keyed cache.
- Model routing by cluster coherence (Haiku tight / Sonnet messy) stays a
  separate deferred open item — this ticket is role->model, not coherence
  routing.

## Trigger to pull into todo
When a second TEXT model is configured (a distinct condense vs brief/judge
model) — i.e. the first time the sole-text-model assumption stops holding. Until
then the #058/#059 default is correct.

## Acceptance criteria
- [ ] A role->model mapping exists (per the chosen mechanism); each summarisation
      op resolves ITS role's model, with the sole-text-model fallback preserved.
- [ ] `brief` reads condensations under the CONDENSE model's name regardless of
      the brief model — a distinct-model fixture proves briefs are built from the
      real condensations, not empty input.
- [ ] Existing single-text-model behavior is unchanged.
- [ ] `ruff format`, `ruff check --fix`, `pytest` all clean.

## Out of scope
- Coherence-based model routing (deferred open item).
- Changing the condensations/briefs cache shapes (they are already model-keyed).

## Review log
- 2026-08-24 PO: spun off from #059 PO review (qa model-coupling observation),
  folding in the #058 deferred role->model open question. Parked with a pull-in
  trigger (first second text model). The load-bearing requirement is the cross-
  model read: brief must consume condensations under the CONDENSE model, or a
  distinct condense/brief model silently briefs empty input.

## Review log (dev)
- 2026-09-22 dev: implemented and committed. **The landmine is the deliverable;
  the mapping is how it becomes reachable.**

  **Mechanism: an optional `role` on the text model** — not a third
  configuration system, as the ticket required. The registry already holds
  models with a `kind`; a `role` beside it expresses the spec's
  `condense -> cheap, brief -> smart` mapping with no new collection, no tree
  config block and no new file. `resolve_text_model(conn, scope, role)` applies
  three rules in order: a model NAMED in the scope wins, else the model whose
  role matches, else the sole text model. **The last is exact and unchanged** —
  a one-model install configures no roles and behaves as it always has, which a
  test pins for all four roles.

  Two models and no mapping is now an error that NAMES the role it wanted,
  rather than "name one in the scope" — the operator's next action is to give
  one a role, so the message says that.

  **The landmine, fixed in both places it lives.** A consumer reads a producer's
  cache under the PRODUCER's model name:
  - `brief` reduces condensations `condense` wrote;
  - `propagate` judges a leaf against those same condensations.
  Both used to key the lookup by their own resolved model. While one text model
  served every role the names matched and nothing showed; with a cheap condense
  model and a smart brief model, both would find NO condensations and carry on —
  briefing an empty reduce input and judging a blank page, with no error
  anywhere. `producer_model_name` is that lookup and it is why role resolution
  lives in `resolve` rather than in each op.

  **The propagate half needed a sharper assertion than I first wrote.** Leaf
  SELECTION does not depend on the model name — only the judged CONTENT does —
  so `judge.calls == BEST_OF` passes whether the source is real or empty. The
  test now asserts the condensation text appears in what the judge received.
  A call count that looks right while the content is blank is exactly the
  failure this ticket is about, and my first test reproduced it.

  Also removed: an early `if name is not None: return text[0]`. A mutation
  showed it unobservable, and it is provably redundant rather than untested — a
  named scope narrows the rows to one model, so everything below has a single
  candidate. The reason is in the docstring so it is not re-added.

  Tests (8 new, 924 total): the one-model default for all four roles, a role
  picking its model, a scoped name winning, two-models-no-mapping naming the
  role, two models claiming one role, the producer lookup, and both landmine
  halves driven end to end. Mutations, all killed: brief reading under its own
  model, propagate the same, the role branch removed, two-for-one-role accepted.

  Out of scope and untouched: model routing by cluster coherence, which the
  ticket defers.

  Gate clean: `ruff format`, `ruff check --fix`, `pytest` **924 passed**.
- 2026-09-22 qa: **FAIL — back to todo.** The landmine is properly fixed and the
  resolution rules are right. One mutation of mine survives, and it is the class
  of defect this project decided about three weeks ago.

  **Blocking — nothing rejects an invalid role.**
  ```
  mutation: role: SummarisationRole | None  ->  role: str | None
  result:   212 passed
  ```
  The `Literal` is the only thing stopping `{"role": "condence"}` from being
  written, and no test asserts it. A typo'd role is config that VALIDATES and
  then does nothing: the model is never selected for any stage, and on a
  two-model install the other stages start failing with "multiple text models"
  pointing at a mapping the operator believes they configured.

  That is precisely what #107 was closed for getting right — "a connection whose
  CLI is missing must be rejected at write time, never at condense time" — and
  the same bar applies to a mapping that cannot ever match. Validation you
  cannot delete without a test failing is not validation yet.

  Fix: a test that PUTs a model with a bogus role and asserts the write is
  refused, beside one that accepts each of the four valid roles. The registry
  test harness already does both shapes.

  **What I verified as PASSING (need not be redone):**
  - Gate: ruff clean, **924 passed**.
  - **The sole-model fallback is genuinely exact** — removing it fails 57 tests,
    which is the strongest possible evidence that a one-model install is
    unaffected. That was the thing most at risk in this change and it is nailed.
  - Mutations dev ran, re-run by me: brief reading under its own model fails 1,
    propagate the same fails 1, the role branch removed fails 5, two models for
    one role accepted fails 1.
  - **The propagate assertion is the detail that makes this ticket real.** Leaf
    selection does not depend on the model name, so a call-count assertion
    passes whether the judged source is real or blank. Catching that in their
    own first test, and asserting on the content the judge received instead, is
    the #128 discipline working.
  - Choosing an optional `role` on the model over a new config block is right:
    the ticket forbade inventing a third mechanism, and this invents none.
  - Removing the redundant early return rather than testing it is the correct
    disposal — dev showed it was provably unreachable-as-different, not merely
    unobserved, which is the distinction #128 asks for.
- 2026-09-22 dev: **re-picked up after qa's FAIL**; fixed. Tests only.

  qa is right and the comparison to #107 is the one that lands: a typo'd role is
  config that validates and then does nothing, which is the same shape as a
  connection whose CLI is missing being accepted at write time. The `Literal`
  was already doing the work; nothing would have noticed if it stopped.

  Two tests: a bogus role is refused by the model itself, and each of the four
  valid stage names is accepted. The second is parametrised over the stages that
  actually resolve a text model, so a fifth stage appearing fails it until the
  `Literal` grows — which is the failure I would want, rather than a silent
  role nothing matches.

  qa's mutation now fails. Gate clean: **929 passed**. Handing back to verifying.
- 2026-09-22 qa: **PASS — to po-review.** My mutation now fails, and the
  parametrised half is a better fix than I asked for: it fails when a fifth
  summarisation stage appears without a role, which turns a future silent
  mismatch into a build error.

  Everything in my previous PASS list stands, in particular that removing the
  sole-model fallback fails 57 tests — a one-model install is provably
  unaffected by this change, which was the thing most at risk.

  Gate re-run by me: **929 passed**, ruff clean.

## Review log (PO)
- 2026-09-22 PO: **PASSES — closed to done.** All criteria met.

  **The landmine is what this ticket was for, and it was three weeks from
  becoming real.** #107 shipped a second provider; the moment anyone configures
  a cheap `claude-code` condense model beside a paid brief model, both `brief`
  and `propagate` would have looked for condensations under their OWN model name
  and found none — briefing an empty input and judging a blank page, with no
  error anywhere and every call count looking correct. qa noticed this while
  reviewing #059 in August and wrote it down. That is the value of a review note
  that becomes a ticket rather than a comment.

  The mechanism is right: an optional `role` on the model, no new collection, no
  tree-config block, and a sole-model fallback so exact that deleting it fails
  57 tests. A one-model install configures nothing and notices nothing.

  **Two small judgements I want on the record.** Asserting on the CONTENT the
  judge received rather than the call count — because selection does not depend
  on the model name, so a count assertion passes over a blank page. And
  refusing an invalid role at write time, which qa caught and correctly measured
  against #107's bar: config that validates and then does nothing is the failure
  we decided about three weeks ago.

  No new work spun off. Model routing by cluster coherence stays deferred, as
  the ticket scoped.
