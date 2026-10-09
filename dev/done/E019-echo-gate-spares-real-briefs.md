---
id: E019
title: the echo gate spares a real brief about the prompt's own vocabulary
priority: medium
depends_on: [E015]
requirements: [96]
---

## Goal
E015's echo gate can flag a real brief whose subject shares the prompt's words
(an INI parser, a tree-shaped codebase, hrono itself). A flagged brief is never
fresh, so it is rewritten at two calls on every maintain, forever.

## Tickets

### 1 words the material uses are not echo evidence
Change: `echoes()` counts only prompt words absent from the node's own material
(its children's text); words the prompt tells the model to write ("caution")
never count.
Done when:
- [ ] a brief on an INI parser and one on a node/parent/child tree pass; a pure
  prompt echo still fails; boundary tests, mutation-checked
Look at: src/hrono/summarize/shape.py `echoes`, brief.py, brief_upper.py

### 2 a flagged brief is not re-paid on every maintain
Change: as E015 T2 for condensations, a flagged brief is recorded and not
rewritten until its members, model or prompt change.
Done when:
- [ ] two maintains over an unchanged tree with one stubborn echo spend the
  rewrite calls once; the second reports zero
Look at: summarize/store.py, briefs.py; E015 T2

## Out of scope
- retuning the eight-word / 30% thresholds without a measured miss

## Log
- 2026-10-03 po: created from backlog echo-gate-domain-vocabulary (E015 qa round 2). Waits on E018 (brief.py prompts).
- 2026-10-03 po: started; E018 left summarize/ untouched (T1/T2 changed export/ only), overlap gone.
- 2026-10-03 dev: round 1 started
- 2026-10-03 dev: T1+T2 committed ba6a02a; verified by shape/unusable-brief tests plus 742 summarize/server/tree tests; mutations (material subtraction, quote strip, _rewritable) all killed.
- 2026-10-03 qa: round 1 FAIL at ba6a02a: drove two maintains (calls 2 then 0, T2 holds) and re-ran the quote-strip mutation (killed); the read-time material mutation survived, material() ignores the condense model (stubborn echo re-paid with a second model's condensations, reproduced), two stale docstrings, one commit for two tickets; see qa findings.
- 2026-10-03 dev: round 2 fixes committed (material from condense model's reduce input, stored-path test, docstrings), head 960d0f4; 744 summarize/server/tree tests pass; mutations (material -> empty, any-model join) killed. ba6a02a left as one commit: dev.md forbids rewriting commits qa has seen.
- 2026-10-03 qa: round 2 FAIL at 960d0f4: round-1 findings 1-3 fixed (second-model cache test kills the any-model join, stored-path test kills material->""); new: material() resolves the condense model with an empty scope, so a brief job run with scope {type: model} re-pays and lists honest briefs every pass (reproduced: 2 calls then 2, listed 2); upper-level material (child_briefs fallback) mutant survives all 744 tests; commit split withdrawn per dev.md; see qa findings.
- round 3: b074d45 findings A (briefs.source_model recorded at write, read by material) and B (upper stored-path test); mutations: source_model read off, child_briefs fallback dropped, both killed.
- 2026-10-03 qa: round 3 PASS at b074d45: round-2 findings A and B fixed; ruff clean, full suite 1925 passed; re-ran mutations (recorded source_model ignored, brief() not recording source_model, child_briefs fallback dropped), all killed by the new scoped-job and upper stored-path tests.
- 2026-10-03 po: accept at b074d45: T1 (material-word subtraction, quoted words excluded) and T2 (settled echo not re-paid; 2 calls then 0) met per qa rounds 1-3; source_model migration keeps read-time material honest under scoped jobs; API docstring updated, no user-facing copy affected.
- merged to main at a2b505d
