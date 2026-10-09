---
id: 088
title: extend the prompt placeholder guard to `judge` ({source}/{summary}), now that its tokens are settled
priority: medium
size: small
depends_on: [066, 087]
spec_refs: [build-order.md#T36]
---

## Context
Spun off from #087 (propagate) PO review. #066 added a data-driven placeholder
guard (`_REQUIRED_PLACEHOLDERS`) requiring `{content}` on content-consuming
prompts, but DEFERRED `judge` "because its op isn't built and its tokens aren't
settled". #087 built propagate and settled them: the seeded `judge` prompt now
consumes `{source}` and `{summary}` (`template.replace`). So a user editing the
judge prompt to drop those tokens would SILENTLY degrade propagate — the replace
no-ops, the judge sees no source/summary, and it likely always returns "none",
quietly breaking upward staleness. The seeded default has both (works out of the
box), so it is not a live defect — but the guard now has a settled contract to
enforce.

## Description
- Add `judge: ("{source}", "{summary}")` to #066's `_REQUIRED_PLACEHOLDERS` so a
  judge template missing either token is rejected at write time (ValidationFailed
  -> 400), same as the condense/brief roles.
- Update the prompt-CRUD tests that use an ARBITRARY `judge` template (the ones
  #066 deliberately left unconstrained) to use a `{source}`/`{summary}` template,
  intent unchanged.
- Seeded judge default already has both -> still passes; reset-to-default valid.

## Acceptance criteria
- [ ] Writing a `judge` prompt without `{source}` or `{summary}` is rejected; the
      seeded default passes; reset-to-default restores a valid template.
- [ ] The required-placeholder table stays data-driven (no per-role branch).
- [ ] `ruff format`, `ruff check --fix`, `pytest` all clean; work committed.

## Out of scope
- Any change to propagate (#087) or the judge recipe.

## Review log
- 2026-08-25 PO: spun off from #087 review. #066 deferred judge because its tokens
  were unsettled; #087 settled them ({source}/{summary}), so close the same silent-
  no-op footgun for the judge role. Medium/small: seeded default works, this guards
  user edits.
- 2026-08-25 dev: implemented (commit d1b34b9). Added `"judge": ("{source}",
  "{summary}")` to #066's data-driven `_REQUIRED_PLACEHOLDERS` (no per-role branch;
  the existing `_validate` loop enforces it). Updated the prompt-CRUD tests that had
  used arbitrary judge templates (they predate the settled tokens): the parametrized
  role-registration test now uses a per-role token map; test_crud_round_trip and the
  two test_prompt_defaults cases use {source}/{summary} templates (intent unchanged).
  Added a parametrized rejection test — judge missing either token -> 400 — and the
  seeded-default-satisfies-validation test already covers reset-to-default. Gate
  clean: 568 passed / 1 skipped. Ready for qa.
- 2026-08-25 qa: PASS (commit d1b34b9) -> po-review. Tree CLEAN. Exactly the fix I
  recommended on #087: `judge: ("{source}", "{summary}")` added to the data-driven
  `_REQUIRED_PLACEHOLDERS` (no per-role branch), same ValidationFailed -> 400 path
  as condense/brief. The new parametrized `test_judge_template_missing_a_settled_
  token_is_rejected` proves BOTH tokens are required (missing {source}, missing
  {summary}, or neither -> 400) through the real registry write path; the seeded
  judge default (which has both) still validates; the per-role registration test
  and the two prompt-defaults cases were updated to valid {source}/{summary}
  templates (intent unchanged, a necessary fixture fix). ruff clean; registry
  suites 85 passed; full suite 568 passed / 1 skip; atomic Conventional Commit.
  Closes the judge silent-degradation footgun; the #058->#066->#087->#088 chain of
  the placeholder guard is now complete for every content-consuming role.
- 2026-08-25 PO review: PASS -> done. Gated #088's commit (d1b34b9) in an isolated worktree (tree carried untracked #089 monitor-migration WIP): ruff clean, 85 registry tests pass. Confirmed `judge: ("{source}", "{summary}")` is in the data-driven _REQUIRED_PLACEHOLDERS (no per-role branch; the existing _validate loop enforces it), the parametrized rejection test proves both tokens required through the real write path (missing either -> 400), the seeded judge default still validates, and the fixture tests that predated the settled tokens were updated to valid templates (intent unchanged). All acceptance criteria met. Closed. The placeholder-guard chain #058 -> #066 -> #087 -> #088 is complete for every content-consuming role (condense/brief/brief-upper/judge).
