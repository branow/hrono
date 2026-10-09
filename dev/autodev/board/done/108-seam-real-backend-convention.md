---
id: 108
title: Convention — a ticket that introduces a seam must also test the real backend
priority: medium
size: small
depends_on: []
spec_refs: [build-order.md#T19]
found_by: e2e manual QA 2026-09-03 — .e2e/FINDINGS.md F18; re-scoped by PO after #094
---

## Context
585 tests passed while a three-repo corpus could not build to root (#094).
Every affected path was covered only through an injected seam:
`test_build_tree` passed `build=`, `test_levels` likewise, `incubator.drain`
took a `core_labeler` override, and the one real-recipe harness
(`tests/cluster/harness.py:planted_groups`) defaulted to 76 vectors —
comfortably above the size at which the real recipe broke. The seams were all
correct; what was missing was any test that let the REAL backend speak.

**Re-scoped by PO on 2026-09-14, after closing #094.** The original acceptance
criteria of this ticket — real `build_clusters`/`core_labels` at N = 4, 10, 26,
27, and a real-backend `build-tree` over a corpus small enough to stop the
recursion — were fully delivered by #094 itself
(`tests/cluster/test_build.py:127,139`, `tests/summarize/test_build_tree.py:274`).
Re-writing them would be duplicate work. What remains unwritten, and what
actually prevents the next bug of this class, is the standing rule. That rule is
now the whole of this ticket.

## Description
Write the rule into the places dev and qa actually read, so it binds every
future ticket rather than living in one closed ticket's Decision block:

> A ticket that introduces or extends a test seam (`build=`, `client=`,
> `core_labeler=`, `reduce=`, `encoder_for=`, or any other injected backend)
> must also carry at least one test that exercises the REAL backend through
> that path, even if only at a trivial size. Seam-injected tests prove the
> wiring; they cannot prove the backend's contract.

Three destinations, one line to three files:
- `CLAUDE.md`, under Conventions — the shared brief both roles load.
- `.autodev/loop/prompts/dev.md` — as something dev must produce.
- `.autodev/loop/prompts/qa.md` — as something qa must check before passing a
  ticket to `po-review/`.

No production code changes. No new tests — #094 already carries the regression
teeth this rule would have demanded.

## Acceptance criteria
- [ ] The rule is stated in `CLAUDE.md` Conventions, in `dev.md` as an
      obligation when writing tests, and in `qa.md` as a verification step.
- [ ] The wording names the concrete seams in use today so it is checkable, not
      aspirational.
- [ ] `ruff format`, `ruff check --fix`, `pytest` clean (nothing should change).

## Out of scope
- Re-testing the clustering recipe at small N — delivered by #094.
- Auditing every existing seam in the codebase for a missing real-backend test.
  The rule binds new work; a retro-audit, if ever wanted, is its own ticket.

## Review log
- 2026-09-14 PO: re-scoped from "add test teeth" to "write the convention", and
  unblocked (`depends_on` cleared — #094 is done and carried the teeth). qa
  raised this during #094's review: 094's real-backend tests cover nearly all of
  this ticket's original acceptance criteria. I am not closing it as covered,
  because the rule itself is the part that stops the next 094, and it is still
  unwritten. Title and criteria rewritten to match.

## Review log (dev)
- 2026-09-21 dev: started; moved to in-progress (batch with #111's re-fix, #126,
  #120).
- 2026-09-21 dev: implemented. **No commit, and that is correct** — all three
  destinations are gitignored by the repo's own design (`CLAUDE.md` is
  `.gitignore:2`, `.autodev/` is `.gitignore:25`), the same situation #128 hit
  and verified this week.

  The rule is in the three places both roles read, naming the concrete seams in
  use today (`build=`, `client=`, `core_labeler=`, `reduce=`, `encoder_for=`) so
  it is checkable rather than aspirational, as criterion 2 asks:
  - `CLAUDE.md` Conventions, directly under the regression-grade bullet;
  - `dev.md` step 4, as an obligation when deciding what would convince you;
  - `qa.md` checklist item 3, as something to check before passing a ticket on.

  Each states the evidence in one clause — 585 tests green while no corpus could
  build to root — so the "why" travels with the rule.

  **It sits beside #128's mutation rule on purpose.** They are the same failure
  from two directions: #128 catches a test that cannot fail, #108 catches a
  suite that can only fail about the wiring. In `dev.md` they are consecutive
  paragraphs in step 4; in `qa.md` consecutive clauses of item 3. A reader meets
  both at the moment they are deciding what to write.

  No production code changed and no tests added, per Out of scope — #094 already
  carries the teeth this rule would have demanded, and the retro-audit of
  existing seams is explicitly not this ticket.

  Gate clean: `ruff format`, `ruff check --fix`, `pytest` **825 passed**
  (unchanged, as expected).
- 2026-09-21 qa: **PASS — to po-review.** All three criteria met.

  **Verified:** the rule is in `CLAUDE.md` Conventions, `dev.md` step 4 and
  `qa.md` item 3; it names the five concrete seams in use today, which is
  criterion 2 and the difference between a checkable rule and a slogan; and each
  statement carries the evidence in one clause (585 green tests over a corpus
  that could not build to root).

  **No commit, correctly** — same as #128, and I re-checked rather than assumed:
  `CLAUDE.md` is `.gitignore:2` and `.autodev/` is `.gitignore:25`. Nothing
  else changed and the suite is unmoved at 825.

  **Placing it beside #128's mutation rule is the right editorial call.** They
  are the same failure from two directions — a test that cannot fail, and a
  suite that can only fail about the wiring — and a reader meets both at the
  moment they are deciding what to write. I would have flagged it if they had
  landed in different sections.

  One note, not a fail: this rule and #128's now both live in `dev.md` step 4,
  which is getting long. If a third joins them, that step wants sub-headings
  rather than a fourth consecutive paragraph.

## Review log (PO)
- 2026-09-21 PO: **PASSES — closed to done.** All three criteria met.

  Naming the five concrete seams is what makes this a rule rather than a
  sentiment, and it is the criterion I was most worried would be softened. A
  reviewer can now ask a checkable question: this ticket added `build=`, where
  is the test that runs the real thing through it?

  **Placing it beside #128's mutation rule is better than either alone.** They
  are the same failure from two directions — a test that cannot fail, and a
  suite that can only fail about the wiring — and #094 is the proof that the
  second is not hypothetical: 585 green tests over a corpus that could not build
  to root. Both now sit in the step where a dev decides what would convince
  them.

  No commit, correctly, and qa verified the claim rather than accepting it.

  Taking qa's editorial note as a standing instruction rather than a ticket: if
  a third rule joins these two in `dev.md` step 4, that step gets sub-headings
  instead of a fourth consecutive paragraph. Not worth a card; worth remembering.

  This also closes the last of the three convention tickets (#108, #128) that
  came out of the review rounds this month. The board's process debt is paid.
