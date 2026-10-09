---
id: 128
title: Convention — a new test must be mutation-checked against the guard it names
priority: medium
size: small
depends_on: []
spec_refs: [build-order.md#T59]
found_by: PO at #125's close, 2026-09-21 — three consecutive kickbacks, one cause
---

## Context
Spun off from #125 PO review. #125 was kicked back twice and self-corrected once
more, and all three were the SAME defect in the TEST, never in the code:

| round | the test | why it could not fail |
|---|---|---|
| `ef6ef60` | `test_a_user_source_named_like_a_node_is_untouched` | built both halves of the failing state, asserted only the passing half |
| `2129a2a` | the same test, both halves asserted | indexed a phantom `passage_id`, which the statement under test can never reach |
| `3f001ca` (caught by dev, pre-handoff) | the new sweep test's own counter | counted FTS rows through a join to `passages`, so a row whose passage had cascaded away was invisible — the exact orphan being removed |

Each time the suite was green, the reviewer's eye found it, and the real corpus
proved the defect was live. Three rounds of a one-line ticket. The cost is not
the SQL, it is that a green suite carried no information about the guard the
test was named for.

This is the sibling of #108: that rule says a seam-injected test cannot prove
the backend's contract; this one says an assertion cannot prove a guard it
cannot reach. Both are "the test passed for a reason unrelated to the thing it
was written for."

## Description
Write the rule into the places dev and qa actually read, so it binds future
tickets rather than living in one closed ticket's Review log:

> A test written to guard a specific condition must be mutation-checked against
> it: break that condition in the code, confirm the test fails, restore it.
> State the mutation and its result in the handoff. If a mutation leaves the
> test green, the test is not yet a regression tooth — most often because it
> asserts one half of the state it constructed, or measures through a path the
> mutated code no longer populates.

Three destinations, one line to three files, the same set #108 uses:
- `CLAUDE.md`, under Conventions — the brief both roles load.
- `.autodev/loop/prompts/dev.md`, step 4 ("Decide how you will prove it works").
- `.autodev/loop/prompts/qa.md`, checklist item 3 (test adequacy) — qa re-runs
  at least one of the stated mutations rather than trusting the claim.

Keep it to a sentence or two per destination. This is a documentation ticket;
it changes no production code and adds no tests of its own.

## Acceptance criteria
- [ ] The rule appears in `CLAUDE.md` under Conventions, in the file's voice.
- [ ] `dev.md` step 4 requires stating the mutation and its result at handoff.
- [ ] `qa.md` checklist item 3 requires qa to re-run at least one stated mutation.
- [ ] Wording is consistent across the three, and cites #125 as the origin so
      the evidence is one grep away.
- [ ] `ruff format`, `ruff check --fix`, `pytest` clean (nothing should change).

## Out of scope
- Adopting a mutation-testing TOOL (mutmut / cosmic-ray). `CLAUDE.md` already
  names a > 90% kill-rate target; wiring a runner is its own ticket, and this
  rule must hold by hand in the meantime.
- Retrofitting the rule onto existing tests. It binds new and changed tests.

## Review log
- 2026-09-21 PO: authored at #125's close. Three kickbacks on one small ticket,
  one cause each time, and in every round the real corpus could show the defect
  while the suite could not. The rule is cheap; the rounds were not.

## Review log (dev)
- 2026-09-21 dev: started; moved to in-progress (batch with #122's re-fix, #111,
  #134).
- 2026-09-21 dev: implemented. **No commit exists, and that is correct, not an
  omission** — all three destinations are gitignored by the repo's own design:
  ```
  $ git check-ignore -v CLAUDE.md .autodev/loop/prompts/dev.md
  .gitignore:2    CLAUDE.md
  .gitignore:25   .autodev/
  ```
  `CLAUDE.md` says so in its own first line ("local-only working memory ... must
  never be committed"), and the board lives under `.autodev/`. #108, the
  precedent this ticket follows, has the same property. So the gate ran and is
  clean, but there is nothing to commit and I have not manufactured one.

  **The rule, in the three places both roles actually read:**
  - `CLAUDE.md` Conventions, one bullet under the existing regression-grade line,
    in the file's voice and citing #125 as the evidence.
  - `dev.md` step 4 ("Decide how you will prove it works") — state the mutation
    and its result at handoff.
  - `qa.md` checklist item 3 — re-run at least one of the dev's stated mutations
    AND try one they did not.

  **I added a clause the ticket did not ask for, and it earned its place this
  same batch.** A surviving mutation has two causes that are easy to confuse:
  the guard is dead code, or the test is missing. #122 removed a guard as
  "unobservable" on a surviving mutation; it was merely unobserved, and
  restoring it was the fix qa sent the ticket back for. Without that sentence
  the rule teaches the wrong lesson half the time — "delete what a mutation does
  not kill" — so it is in `dev.md` next to the rule itself.

  Wording is consistent across the three and each cites #125/#128, so the
  evidence is one grep away as the criteria asked.

  Not adopting a mutation-testing TOOL, per Out of scope: `CLAUDE.md` already
  names a >90% kill-rate target, and wiring mutmut or cosmic-ray is its own
  ticket. This rule has to hold by hand until then, and it did across #101,
  #105, #110, #111, #112, #113, #122, #123, #127 and #132 — every one of which
  had at least one mutation survive a first draft.

  Gate clean: `ruff format`, `ruff check --fix`, `pytest` **817 passed**
  (unchanged, as expected for a documentation ticket).

## Review log (qa)
- 2026-09-21 qa: **PASS — to po-review.** All five criteria met, and the rule
  earned its keep inside the same batch that wrote it — I failed #111 on a
  surviving mutation I tried only because this ticket told me to try one the dev
  had not.

  **Verified:**
  - The rule is in all three destinations, worded consistently, each citing
    #125/#128 so the evidence is one grep away: `CLAUDE.md` Conventions (under
    the existing regression-grade bullet), `dev.md` step 4, `qa.md` checklist
    item 3.
  - **No commit, correctly.** I checked rather than took it on trust:
    `git check-ignore -v` reports `.gitignore:2 CLAUDE.md` and
    `.gitignore:25 .autodev/`, and `git ls-files CLAUDE.md` is empty. All three
    destinations are local-only by the repo's own design, `CLAUDE.md` says so in
    its first line, and #108 has the same property. Manufacturing a commit here
    would have been the wrong instinct.
  - Nothing else changed: 817 passed, identical to before, which is what a
    documentation ticket should do.

  **The clause dev added beyond the ticket is the most valuable line in it.**
  "A surviving mutation has two causes: the guard is dead code, or the test is
  missing — decide which before you delete anything." Without it the rule
  teaches "delete what a mutation does not kill", and #122 is the proof of how
  that goes: a guard removed as unobservable that was merely unobserved, and
  restoring it was the fix. Both halves of the lesson are now in `dev.md` next
  to each other.

  One observation, not a fail: the rule is stated for tests that guard "a
  specific condition", which is the right scope — it would be absurd applied to
  every assertion in a fixture. Whoever applies it should read it that way.

## Review log (PO)
- 2026-09-21 PO: **PASSES — closed to done.** All five criteria met, and it paid
  for itself inside the batch that wrote it: qa failed #111 on a mutation tried
  only because this rule told them to try one the dev had not.

  I authored this after #125 took three rounds with the code right every time
  and the test unable to fail. It is now in the three places both roles read,
  worded the same in each, citing the evidence.

  **The clause dev added beyond my brief is better than my brief.** "A surviving
  mutation has two causes — the guard is dead code, or the test is missing —
  decide which before you delete anything." Without it the rule teaches half a
  lesson, and #122 in this same batch is the proof: a guard removed as
  unobservable that was merely unobserved, and restoring it was the fix. I would
  not have thought to write that sentence, and the ticket is stronger for it.

  **No commit, and that is correct.** All three destinations are gitignored by
  the repo's own design; qa checked with `git check-ignore` rather than taking
  it on trust, which is the right instinct for a claim of the form "there is
  nothing to show you".

  Accepting qa's scoping note: the rule is for tests that guard a specific
  condition, not for every assertion in a fixture. The wording already says so.

- 2026-09-23 po: a third instance, from #144: #126's reserve test hand-wrote
  `...#chunk-<n>` URIs into `passages`, a shape production never writes, so the
  window rule it named was being exercised against fabricated data. #125 and
  #128 were the same shape of error. The common factor is worth stating in one
  line, and it is now in dev.md and qa.md: A FIXTURE THAT WRITES ROWS
  PRODUCTION NEVER WRITES IS NOT A TEST OF PRODUCTION. Prefer the real insert
  helper; when a test must fabricate a row, say in a comment why the real path
  cannot reach that state.
