---
id: 044
title: test hygiene — lean on @pytest.mark.parametrize, no new test-framework dep
priority: low
size: medium
depends_on: []
spec_refs: []
---

## Context
Raised during review: should we adopt a test framework (testify-style) for
cleaner tests and better failure messages? Decision: NO new dependency. pytest
already rewrites `assert`, so a bare `assert a == b` prints a full introspected
diff of both operands on failure — the "clear message" concern from Go/Java is
already solved by the framework we are on. Matcher libs (assertpy, PyHamcrest)
are style, not capability, and cut against the project's minimal-deps lean.

The real, actionable win is table-driven tests via `@pytest.mark.parametrize`
(the idiomatic equivalent of Java parameterized / Go table tests — decorator
based, no reflection, one reported case per row). Already used in ~11 of ~47
test files; not applied consistently.

## Description
A hygiene sweep, done opportunistically per touched file (NOT a big-bang PR):
- Collapse groups of near-identical one-assert test functions into a single
  parametrized table (canonical example: `tests/crypto/test_tokens.py`).
- Give each parametrize row a stable `id` so failures name the case.
- Add an explicit `assert cond, "message"` ONLY where the rewritten pytest
  output is genuinely opaque (e.g. asserting on raw bytes / large blobs).
- Do NOT add any assertion/matcher library.

## Acceptance criteria
- [ ] Repetitive same-shape tests in touched files are parametrized with named
      ids; behavior and coverage unchanged (still regression-grade).
- [ ] No new test dependency added.
- [ ] `ruff format`, `ruff check --fix`, `pytest` all clean.

## Out of scope
- Any change to what is tested or the mutation-kill bar — this is form, not
  coverage.
- A single sweeping refactor of all 47 files at once; do it as files are touched.

## Review log
- 2026-08-22 stakeholder + PO: discussed; agreed pytest's assert rewriting
  already covers the failure-message need, so no framework dep. Captured the
  parametrize sweep as low-pri opportunistic hygiene.
- 2026-09-27 po: CLOSED as a CONVENTION rather than a ticket. Both halves of
  this ticket say the same thing — "opportunistic, per touched file, NOT a
  big-bang PR" — which is the definition of a standing rule, not of work with
  an end. It now lives in `CONTRIBUTING.md` under "Form, applied as files are
  touched" (#171 created that file for exactly this), where it applies to every
  ticket automatically instead of waiting in a backlog nobody can finish.
