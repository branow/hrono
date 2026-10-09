---
id: 066
title: validate content-consuming prompts keep their `{content}` placeholder
priority: medium
size: small
depends_on: [020, 021, 058]
spec_refs: [build-order.md#T10.2, implementation-notes.md]
---

## Context
Spun off from #058 (condense) PO review (qa observation #2). The summarize ops
render a role prompt by `template.replace("{content}", body)` — a SILENT no-op if
the template has no `{content}` placeholder. The seeded defaults (#021) all
contain it, so #058 is safe today, but a user editing the `condense`/`brief`
prompt via the registry to drop `{content}` would condense/brief the INSTRUCTIONS
with no section body attached — a summary of nothing, with no error. #059 (brief)
and #061 (brief-upper) inherit the same footgun. The prompts registry already has
a validation-hook seam (#020/#021, `validate` on the descriptor) — the correct
home for this check.

## Description
Add a prompt-validation rule (in the prompts descriptor's `validate` hook) that
rejects a write whose template omits a required placeholder for its role:
- `condense`-role and `brief`-role templates MUST contain `{content}` (the map/
  reduce body is injected there).
- Whatever placeholder `brief-upper` uses for child briefs MUST be present in a
  `brief-upper`-role template. OPEN QUESTION for dev: confirm the exact
  placeholder token(s) the #059/#061 ops inject (`{content}` vs a child-briefs
  token) and drive the required-set from that — do not guess a token the op
  does not use.
- The rule is DATA-driven (a role -> required-placeholders table), not an
  if/elif ladder, consistent with the descriptor engine.
- A missing placeholder is a clean validation error (ValidationFailed -> 422),
  same path as the other registry validators; the seeded defaults still pass.

## Acceptance criteria
- [ ] Writing a `condense`/`brief` prompt without `{content}` is rejected with a
      clear validation error; the seeded defaults pass unchanged.
- [ ] The required-placeholder set is data-driven per role (no per-role
      branching), and matches the tokens the ops actually inject.
- [ ] `brief-upper`'s required placeholder is validated per the resolved open
      question.
- [ ] Reset-to-default (#021) still restores a valid template.
- [ ] `ruff format`, `ruff check --fix`, `pytest` all clean; work committed.

## Out of scope
- Any change to how the ops render prompts (they keep `template.replace`); this
  guards the stored template so the replace can never silently no-op.
- Full template linting (unknown placeholders, balanced braces) — only the
  required-placeholder-present rule.

## Review log
- 2026-08-24 PO: spun off from #058 PO review (qa obs #2). #058 met its criteria
  with the seeded default; this closes the silent-no-op footgun a user prompt
  edit would open, in the registry validation seam where it belongs, before/with
  the brief ops (#059/#061) that inherit it. Medium: real footgun, but seeded
  defaults are safe so not urgent.
- 2026-08-24 dev: DONE, committed e4b7873, handoff to qa. Implemented the
  prompts descriptor `_validate` hook (registry/prompts.py) as a data-driven
  `_REQUIRED_PLACEHOLDERS` table (role -> required tokens), no per-role branch:
    condense / brief / brief-upper -> ("{content}",)
  A write whose template omits a required token raises `ValidationFailed`
  (subclasses BadRequest -> 400) via the same engine path as the other registry
  validators. (Ticket said 422; the codebase's registry-validation convention is
  ValidationFailed=400 — followed that for consistency rather than hand-roll a
  different status.)
  RESOLVED the open question on tokens: all three reduce/map ops inject at
  `{content}` — condense (#058) and brief (#059) do `template.replace("{content}",
  ...)`, and the seeded brief-upper default also uses `{content}`; confirmed
  against the actual ops, not guessed. `judge` is intentionally OMITTED from the
  table — its op (#063) isn't built and its injection tokens aren't settled, and
  the ticket says not to guard a token no op uses.
  Seeded defaults all contain `{content}` so they pass unchanged; reset-to-default
  restores a valid template.
  Tests: rejection for each of condense/brief/brief-upper without `{content}`
  (400); judge accepted without it; every seeded default passes `PROMPTS.validate`;
  strengthened the existing reset-to-default test to assert the restored template
  is valid. Also updated the pre-existing prompt test helpers whose placeholder
  template ("{section}") is now invalid for content-consuming roles -> switched to
  a `{content}` template (their intent unchanged).
  Verified: ruff format/check clean; pytest 426 passed / 1 skip (+5 new). Left the
  pre-existing `.gitignore` edit out of the commit.
- 2026-08-24 qa: PASS -> po-review. Verified every dimension:
  - Rule is data-driven (`_REQUIRED_PLACEHOLDERS` role -> tokens table + a
    comprehension), no per-role branch, consistent with the descriptor engine.
    condense/brief/brief-upper -> `{content}`; judge omitted (its op #063 isn't
    built and its tokens aren't settled — correct not to guard a token no op uses).
  - Tokens match what the ops inject: confirmed condense (#058) and brief (#059)
    both do `template.replace("{content}", ...)`, and the seeded brief-upper
    default already contains `{content}`. Open question resolved correctly.
  - Status code: dev used `ValidationFailed` -> 400, and I confirmed the chain in
    the code (`ValidationFailed(BadRequest)`, `BadRequest.status_code = 400`,
    errors.py). The ticket's "422" conflates this with pydantic request validation
    (bad ROLE is 422); a descriptor validate-hook failure is 400. Right call for
    consistency with the git/anthropic/model validators.
  - Tests regression-grade: parametrized rejection (400) for condense/brief/
    brief-upper without `{content}`; judge accepted (201) without it; every seeded
    default passes `PROMPTS.validate`; reset-to-default strengthened to assert the
    restored template still contains `{content}`. Pre-existing helpers that used
    `{section}`/`OVERRIDE` (now invalid for content roles) updated to `{content}`
    with intent unchanged — a necessary, correct fixture fix, not scope creep.
  - Gate clean: ruff format/check clean; prompt suites 19 passed; full suite 426
    passed / 1 skip. Commit e4b7873 is atomic and a clean Conventional Commit.
  Note for #061: this now requires a `brief-upper` prompt to contain `{content}`,
  driven from the seeded default (the #061 op isn't built yet). When #061 lands,
  confirm its op injects at `{content}` (not a `{child_briefs}`-style token) and
  update `_REQUIRED_PLACEHOLDERS` + the seeded default together if it diverges.
  (Pre-existing unrelated `.gitignore` edit remains uncommitted, out of this
  ticket's commit.)
- 2026-08-24 PO review: PASS -> done. Tree is clean (commit e4b7873; the WIP that
  polluted #059's review is now properly committed). Read prompts.py: the rule is
  a data-driven `_REQUIRED_PLACEHOLDERS` table (condense/brief/brief-upper ->
  `{content}`, judge omitted) walked by one comprehension in `_validate` — no
  per-role branch, consistent with the descriptor engine. Ran prompt suites (19
  pass), ruff clean, full suite 426 passed / 1 skip. All acceptance criteria met.
  ACCEPTED the deviation from the ticket's "422": a descriptor validate-hook
  failure is `ValidationFailed` (BadRequest -> 400), matching the git/anthropic/
  model validators; my ticket's 422 conflated it with pydantic's bad-role case.
  dev/qa's 400 is the correct, consistent call — my ticket text was imprecise.
  Threaded qa's forward-note into #061 (brief-upper must inject at `{content}` or
  update the table + seeded default together). Closed. The silent-no-op footgun
  is shut across condense/brief/brief-upper.
