---
id: 063
title: mechanical faithfulness gate on generated briefs (T23.1)
priority: medium
size: medium
depends_on: [059]
spec_refs: [build-order.md#T23.1, summarization-experiments.md]
---

## Context
T23.1. LLM summaries can fabricate — the experiments caught a real class (a
capped condensation invented "photo max 512 chars", propagated by the reduce
stage). The defense that worked is MECHANICAL, not another LLM: extract
identifier-like tokens from every generated text and verify each literally exists
in the source (`app/check_faithfulness.py` in the prototype — case-insensitive,
labels count, slash-compounds split). After the map-prompt fix the corpus's only
residual distortion was one word. This ticket makes that check a gate on brief
output so a future prompt/model regression that starts fabricating fails a test /
is flagged, not silently served.

## Description
A pure, deterministic faithfulness checker + its wiring:
- `faithfulness(generated_text, source_text) -> report`: extract identifier-like
  tokens from the generated brief (case-insensitive; labels count; split slash-
  compounds, per the prototype), and check each appears literally in the source
  (a section's condensation input for a level-1 brief; child briefs for an upper
  brief). Report the unfaithful tokens.
- Bake the prototype's tokenization rules; port `check_faithfulness.py` clean (do
  not re-derive). Residual prose slash-compound false positives are known — keep
  the check as-is; tighten only if it becomes noisy in use.
- Wiring: run the gate after a brief is generated (#059/#061). OPEN QUESTION for
  dev — is an unfaithful brief a hard failure (fail the leaf, do not store) or a
  stored-but-flagged warning surfaced in health? Recommended default: FLAG (store
  the brief, record the unfaithful tokens as a warning readable in tree health),
  not a hard fail — a single fabricated token should not block a whole build.
  Confirm before wiring.

## Acceptance criteria
- [ ] A pure `faithfulness` function extracts identifier tokens and verifies each
      exists in source, per the prototype's rules; returns the offending tokens.
- [ ] Known-good fixture: a faithful brief passes; a brief with a planted
      fabricated identifier is caught.
- [ ] The gate runs on generated briefs; the fail-vs-flag policy is implemented
      per the resolved open question and covered by a test.
- [ ] Deterministic, no LLM, no network. `ruff format`, `ruff check --fix`,
      `pytest` clean; committed.

## Out of scope
- Any judge-model / LLM-based faithfulness scoring (this is the mechanical gate).
- Member-set / prompt-hash staleness (T23.2 / #064).
- The full eval harness (G-Eval / routing accuracy) — an open research item, not
  this ticket.

## Review log
- 2026-08-23 PO: authored as T23.1. Port the prototype's mechanical identifier-
  in-source check clean as a gate on brief output; flagged fail-vs-flag as the
  one policy decision with a "flag, don't hard-fail" default.
- 2026-08-24 dev: DONE, committed ca04938, handoff to qa. Ported the prototype's
  mechanical checker clean as `summarize/faithfulness.py`:
  `faithfulness(generated, source) -> tuple[str,...]` extracts identifier tokens
  (camelCase / PascalCase / dotted-path / snake_case / 3+ digit numbers) and
  returns those with no literal (case-insensitive) support in source; slash
  compounds count as supported when every part is. Pure, deterministic, no LLM.
  RESOLVED the open question with the recommended FLAG policy (not hard-fail): the
  gate runs on each generated brief's LLM output (before mechanical refs are
  appended, so refs never trip it) in both #059 brief and #061 brief-upper; the
  verdict is stored as `briefs.unfaithful` (migration 0014, JSON array, default
  '[]') and surfaced via `briefs.unfaithful_count` for tree health. A fabricated
  token flags the brief but never blocks the build.
  Verified: ruff clean; pytest 450 passed / 1 skip (+9: faithful passes,
  fabricated identifier caught, slash-compound rule, case-insensitivity, prose
  not flagged, 3+ digit rule, sorted/deterministic; gate flags-but-stores + a
  faithful brief records []). Committed fast after gate given the concurrent
  git-reset hazard.
- 2026-08-24 qa: PASS (commit ca04938) -> po-review. This time dev committed with
  a CLEAN tree and the earlier WIP ruff E501 (faithfulness.py:18) was fixed before
  commit — I confirmed ruff "All checks passed" with the tree clean right as 063
  landed. Verified every dimension:
  - Drove the gate end-to-end through the REAL brief op: an LLM output fabricating
    `ghostMethod` and `4096` (neither in the condensation source) -> both flagged
    in `briefs.unfaithful`, the brief STILL stored (FLAG policy, not hard-fail),
    `unfaithful_count` = 1 for tree health, and the mechanical URI refs were NOT
    flagged (the gate runs on the LLM text BEFORE refs are appended — correct).
  - Pure checker is a clean port of the prototype's rules: extracts camelCase /
    PascalCase / dotted-path / snake_case / 3+-digit tokens, verifies each has
    literal case-insensitive support in source, slash-compound supported iff every
    part is. 7 unit tests + 2 gate-wiring tests (flags-but-stores, faithful->[]).
  - Source = the reduce INPUT (condensations for #059, child briefs for #061),
    exactly as the ticket specifies; wired into both brief ops identically.
  - Migration 0014 `unfaithful TEXT NOT NULL DEFAULT '[]'` is backward-compatible
    (pre-gate briefs read faithful). Deterministic, no LLM, no network.
  - ruff clean; full suite 450 passed / 1 skip. Commit is atomic + Conventional.
  Observations for PO (non-blocking, NOT defects): (1) the gate checks the reduce
  stage (brief vs condensations); MAP-stage fabrication (condensation vs the
  original section) is not gated — per spec (the experiments' map-prompt fix
  handled that), out of scope, but worth remembering if a condense regression ever
  fabricates. (2) The PascalCase rule doesn't tokenize all-caps acronyms, so a
  fabricated all-caps token wouldn't be caught — matches the prototype's settled
  rules and the ticket's "keep as-is, tighten only if noisy". (Note: dev started
  #062 recursion-controller WIP [new build_tree.py + app.py registration] during
  my review; it is additive and appeared after 063 was gated on a clean tree, so
  it did not affect this result. Pre-existing `.gitignore` edit still uncommitted.)
- 2026-08-24 PO review: PASS -> done. Gated #063's commit (ca04938) in an
  isolated worktree (tree carried additive #062 WIP): ruff "All checks passed",
  38 summarize tests pass — the earlier WIP E501 (faithfulness.py:18) is fixed in
  the commit. Read faithfulness.py: a clean port of the prototype's rules — one
  regex extracts camelCase / PascalCase(2+ humps) / dotted-path / snake_case /
  3+-digit tokens, each verified for literal case-insensitive support in source,
  slash-compound supported iff every part is; pure, deterministic, no LLM. FLAG
  policy implemented as I recommended (my ticket's open question): a fabrication
  is stored in `briefs.unfaithful` (migration 0014, default '[]') and surfaced via
  `unfaithful_count` for health, NEVER blocks the build; the gate runs on the LLM
  text before mechanical refs are appended, so refs never trip it. Wired into both
  #059 brief and #061 brief-upper over their reduce INPUT. All acceptance criteria
  met. Accepted qa's two non-blocking notes as spec-consistent, out-of-scope
  limitations (map-stage fabrication not gated — the map-prompt fix handles it;
  all-caps acronyms not tokenized — matches the prototype's settled rules and the
  ticket's "tighten only if noisy") — no spinoff. Closed. **M4 T23 (freshness)
  complete** (063 gate + 064 invalidation); only #062 + #065 remain in M4.
