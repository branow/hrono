---
id: 084
title: committed regression test — one changed file re-briefs only its path (partial call count)
priority: medium
size: small
depends_on: [068, 065]
spec_refs: [build-order.md#M7, how-hrono-works.md]
---

## Context
Spun off from #068 (stable node ids) PO review (qa note). #068 delivers the
differentiator — a second `maintain` over an unchanged corpus makes ZERO LLM
calls, and a single changed file re-briefs only the changed leaf + its ancestor
path (qa drove a 9-file corpus: 2 calls vs 13 for a full build). The zero-call
case AND the changed-content->new-id mechanism are committed unit tests, but the
end-to-end "edit ONE file in a multi-file corpus and assert the PARTIAL call
count" is currently proven only by qa's manual drive, not a committed test. This
is hrono's core promise, so it deserves a committed regression guard.

## Description
Add one end-to-end test (fake embedder + fake LLM with a call counter, as the
maintain tests already do):
- Build a multi-file corpus (enough sections to form >1 leaf node).
- First `maintain` -> record the LLM call count (full build).
- Edit exactly ONE file -> `maintain` again -> assert the second call count is
  STRICTLY BETWEEN 0 and the full-build count (only the changed leaf's brief + its
  affected ancestor briefs), and that unchanged nodes kept their ids.
- Assert unchanged sibling briefs are byte-identical to the first build (not
  regenerated).

## Acceptance criteria
- [ ] A committed test edits one file in a multi-node corpus and asserts a partial
      (>0 and < full) re-brief call count, with unchanged node ids/briefs preserved.
- [ ] It fails if a regression makes a single-file change re-brief the whole tree
      (or nothing).
- [ ] `ruff format`, `ruff check --fix`, `pytest` all clean.

## Out of scope
- New incremental behavior — #068 already ships it; this only pins it with a
  committed regression test.

## Review log
- 2026-08-25 PO: spun off from #068 review. The zero-call + new-id mechanisms are
  committed-tested; this adds the missing committed guard on the partial-path
  re-brief (the differentiator). Medium: the behavior works and is manually
  proven; this hardens it. Natural to land with T34.2+ which drives the same path.

## PO triage 2026-09-21 — promoted to `todo`, priority confirmed `medium`

"One changed file re-briefs only its own topic" is the incremental promise
stated as a test. We now have #137's chain to drive it through end to end, which
is what this ticket was waiting for without knowing it.

## Review log (dev)
- 2026-09-21 dev: implemented and committed. Both criteria. Tests only.

  One end-to-end test over the 9-file corpus: full `maintain`, edit exactly one
  file, `maintain` again, and assert the work is strictly partial in three
  independent ways — the call count is between 0 and the full build, the changed
  path WAS re-briefed, and every topic that survived kept its id and its
  byte-identical text.

  **The call count alone cannot carry this**, which the mutations showed. With
  `_is_fresh` forced True nothing regenerates at all — and `partial.calls` is
  still nonzero, because `condense` pays for the new section whether or not any
  brief follows. So "some calls happened" is not evidence the promise held; the
  comparison of stored brief TEXT is. I had dropped that assertion while
  restructuring and the mutation caught it.

  **Comparing only the nodes present in BOTH builds** is deliberate: the changed
  leaf legitimately gets a new id (new content, new signature, #068), so a
  naive `first - regenerated` lookup raised `KeyError` on a node that was
  correctly retired. The surviving set is what the promise is actually about.

  The fake LLM numbers its replies, so a regenerated brief is distinguishable
  from an untouched one — the same lesson as #137: a constant fake makes
  regeneration invisible.

  Mutations: ignoring freshness (every brief regenerates, i.e. a full rebuild)
  fails 2; forcing everything fresh (nothing regenerates) fails 1.

  Gate clean: `ruff format`, `ruff check --fix`, `pytest` **898 passed**.
- 2026-09-21 qa: **PASS — to po-review.** Both criteria met, and the ticket
  caught its own weak spot before I did.

  The criterion asks it to fail if a one-file change re-briefs everything OR
  nothing, and both directions are pinned: ignoring freshness fails 2, forcing
  everything fresh fails 1. **The second only works because the assertion is on
  stored brief TEXT, not on the call count** — `condense` pays for the new
  section whether or not any brief follows, so a nonzero count is not evidence
  the promise held. Dev found that by mutating, having dropped the assertion
  while restructuring.

  Comparing only nodes present in BOTH builds is correct, not a convenience:
  the changed leaf legitimately gets a new id under #068, so a naive difference
  raises `KeyError` on a node that was properly retired.

  This is hrono's core promise with a committed guard on it at last.

## Review log (PO)
- 2026-09-21 PO: **PASSES — closed to done.** Both criteria met.

  **hrono's core promise finally has a committed guard.** "A source change
  touches only the affected nodes, never a full regeneration" is the first thing
  `CLAUDE.md` says about this project and the reason it exists; until today it
  was proven by one manual drive in August. Now a single edit in a nine-file
  corpus asserts partial work three independent ways, and both failure
  directions — rebuild everything, rebuild nothing — fail a test.

  **The call count is not the assertion, and that is the insight to keep.**
  `condense` pays for a new section whether or not any brief follows, so a
  nonzero count proves nothing about re-briefing. The comparison of stored brief
  TEXT is what carries it. Dev found that by mutating after restructuring had
  quietly dropped the assertion — the #128 discipline catching a regression in
  the very test being written.

  No new work spun off.
