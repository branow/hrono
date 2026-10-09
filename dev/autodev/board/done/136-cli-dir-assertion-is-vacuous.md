---
id: 136
title: The CLI working-directory test asserts something true of any answer
priority: low
size: small
depends_on: [107]
spec_refs: [build-order.md#T44.2]
found_by: qa while verifying #107 on 2026-09-21
---

## Context
`tests/llm/test_providers.py:61` asserts

```python
context.cli_dir().parent == context.cache_root.parent.parent / "cache"
```

which holds whatever `cli_dir()` returns under `<db>/cache`. Demonstrated:

```
cache_root        /tmp/x/cache/sources
cli_dir (as is)   /tmp/x/cache/cli      -> assertion True
cli_dir (mutated) /tmp/x/cache/sources  -> assertion True
```

So mutating `cli_dir()` to return the clone cache itself leaves the whole suite
green. The line above it (`client._workdir == context.cli_dir()`) is tautology —
both sides call the same method.

## Why this is not blocking #107
The acceptance criterion ("the CLI always runs from an hrono-owned working
directory, never the server's cwd; a test asserts the argv and cwd") IS covered,
by the real-subprocess test: the stub binary reports its own `pwd` and the test
asserts it equals the directory hrono chose. That test fails if the cwd is
dropped. What is unpinned is only WHICH hrono-owned directory, which is a design
choice rather than a criterion, and the practical harm of the mutated answer is
small — Claude Code reads `CLAUDE.md` from cwd and ancestors, not descendants,
so sitting in the clone root would not pick up a cloned repo's memory.

## Description
Replace both assertions with the property that is actually wanted: the CLI
directory is hrono-owned, is NOT the clone cache, and no synced source can ever
be an ancestor of it. State it once, so a future change to the layout has to
answer for itself.

## Acceptance criteria
- [ ] `cli_dir()` returning the clone cache fails a test.
- [ ] The assertion names the property (separate from the clones) rather than
      re-deriving the path.
- [ ] `ruff format`, `ruff check --fix`, `pytest` clean.

## Review log
- 2026-09-21 qa: filed while verifying #107. Not blocking — the criterion is
  carried by the real-subprocess test; this is a vacuous assertion beside it.

## Review log (dev)
- 2026-09-22 dev: implemented and committed. All three criteria. Tests only.

  The two assertions are replaced by the property that was actually wanted: the
  CLI directory is not the clone root, not inside it, not an ancestor of it, and
  still under hrono's own data root. Stated once, so a future change to the
  layout has to answer for itself.

  The ancestor clause is the one the ticket did not ask for and I added: the CLI
  reads `CLAUDE.md` from its cwd AND its ancestors, so a directory that
  CONTAINS the clones is as wrong as one inside them — it would sit above every
  cloned repo's memory. Both mutations now fail: `cli_dir` returning the clone
  root, and `cli_dir` nested inside it.

  Gate clean: **957 passed**.

## Review log (qa)
- 2026-09-22 qa: **PASS — to po-review.** All three criteria met.

  The property replaces the tautology, and the ancestor clause dev added beyond
  the ticket is the one I would have missed: the CLI reads `CLAUDE.md` from its
  cwd AND its ancestors, so a directory CONTAINING the clones is as wrong as one
  inside them. Three mutations fail — the clone root, inside it, and one of mine
  putting it outside hrono's data root entirely.

## Review log (PO)
- 2026-09-22 PO: **PASSES — closed to done.** Filed by qa against work done the
  same day, fixed a day later, and the fix is broader than the filing: the
  ancestor clause closes a case neither of us had named.
