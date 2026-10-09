---
id: 118
title: The baked lock pattern misses package-lock.json and pnpm-lock.yaml
priority: low
size: small
depends_on: [104]
spec_refs: [build-order.md#T13]
found_by: qa while verifying 104 on 2026-09-14
---

## Context
`DEFAULT_IGNORE["locks"]` is a single glob, `**/*.lock`, carried over unchanged
from the pre-#104 `_DEFAULT_EXCLUDE`. It covers the lockfiles that happen to
use that extension and nothing else:

```
**/*.lock vs yarn.lock          -> True
**/*.lock vs uv.lock            -> True
**/*.lock vs Gemfile.lock       -> True
**/*.lock vs package-lock.json  -> False
**/*.lock vs pnpm-lock.yaml     -> False
```

`package-lock.json` is the default lockfile npm writes, so the single most
common lockfile in the JS ecosystem — the ecosystem #104's own evidence is
drawn from — is ingested as ordinary JSON. It is typically tens of thousands of
lines of resolved dependency metadata, i.e. exactly the per-section embed +
condense cost #104 exists to avoid, with no value to an agent reading the map.

## Description
Not a regression — the pattern is unchanged from before #104, and none of the
three e2e repos contains one (itsdangerous has `uv.lock`, which IS caught), so
#104's real-corpus delta could not surface it. #104's acceptance criterion says
"still skips node_modules and lockfiles", and that criterion is met for the
extend-vs-replace semantics it is about; this is a separate question of which
NAMES count as a lockfile, which the PO's decision block did not enumerate
beyond "already there".

## Description of the fix
Add the common non-`.lock` lockfile names to the `locks` group as data:
`package-lock.json`, `pnpm-lock.yaml`, `npm-shrinkwrap.json`, `bun.lockb`
(binary, so the null-byte sniff already catches it — include for clarity),
`composer.lock`/`Gemfile.lock`/`Cargo.lock`/`poetry.lock`/`uv.lock` (already
covered by `*.lock`). Keep them exact filenames, not prefixes, so a real file
called e.g. `package-lock.example.json` is not swept up.

## Acceptance criteria
- [ ] A repo containing `package-lock.json` and `pnpm-lock.yaml` ingests
      neither by default.
- [ ] `filter.replace_defaults` and an explicit `filter.include` still
      re-admit them, like every other baked group.
- [ ] A file whose name merely contains "lock" (`locking.py`,
      `package-lock.example.json`) is still ingested.
- [ ] `ruff format`, `ruff check --fix`, `pytest` clean.

## Added by PO (2026-09-14, at #104's close)

**Also document the case semantics, here.** `filter.py:_Rules.skips` matches the
baked ignore list against a LOWERCASED path (deliberate, and tested — otherwise
`LOGO.SVG` walks straight past the asset rule and F5 reopens), but matches the
caller's own `exclude` and `include` literally. Driven: `include: ["**/*.svg"]`
re-admits `logo.svg` and silently not `LOGO2.SVG`.

**Keep the behaviour; do not unify it.** The baked list is a safety net and must
be case-insensitive; the caller's globs are their instructions and every
ordinary glob tool treats those literally. Unifying breaks something in either
direction — case-insensitive user globs silently widen an `exclude` beyond what
was written, and a case-sensitive baked list puts the F5 hole back. What is
missing is only that nothing says so.

Folded in here rather than given its own card because this ticket already edits
the same list's coverage, and a card for one sentence costs more than the
sentence.

## Acceptance criteria (added)
- [ ] `filter.py`'s module docstring states that the baked ignore list matches
      case-insensitively while the caller's `exclude`/`include` are literal, and
      why.

## Review log
- 2026-09-14 PO: confirmed at `low`. I reproduced the gap directly —
  `poetry.lock` and `yarn.lock` are ignored by default, `package-lock.json` and
  `pnpm-lock.yaml` are not. Real and worth fixing (these are usually the largest
  files in a JS repo, so the cost is concentrated), but not a regression: the
  `**/*.lock` pattern predates #104.
  **Does NOT need to land before the end-to-end re-run.** I checked the three
  e2e repos myself: the only lockfile present is `itsdangerous/uv.lock`, which
  `**/*.lock` already catches. The re-run cannot surface this and gains nothing
  from waiting for it.

## Review log (dev)
- 2026-09-22 dev: implemented and committed. All five criteria (four original,
  one added by the PO).

  Four names added to the `locks` group as DATA — `package-lock.json`,
  `npm-shrinkwrap.json`, `pnpm-lock.yaml`, `bun.lockb` — with the reason for
  exact names rather than prefixes in a comment beside them: a real file called
  `package-lock.example.json` is documentation, and a prefix glob would eat it.
  Both directions are tested, and the prefix mutation fails.

  The PO's folded-in case note is in `filter.py`'s module docstring: the baked
  ignore list matches a LOWERCASED path while the caller's `exclude`/`include`
  match literally, and the asymmetry stays because unifying breaks something
  either way — a case-sensitive baked list reopens F5 (`LOGO.SVG` walking past
  the asset rule), and case-insensitive user globs silently widen an `exclude`
  beyond what was written.

  Tests drive the real `ingestable` over a JS-shaped tree rather than the
  internal rules object, so what is asserted is what a user's repo would
  actually produce. Mutations: reverting to the single glob fails 1, prefix
  matching fails 1.

  Gate clean: `ruff format`, `ruff check --fix`, `pytest` **936 passed**.

## Review log (qa)
- 2026-09-22 qa: **PASS — to po-review.** All five criteria met.

  Driven through the real `ingestable` over a JS-shaped tree, so what is
  asserted is what a user's repo produces. Mutations: the single glob fails 1,
  prefix matching fails 1. One of mine — renaming the group key — changes
  nothing, correctly: the filter iterates patterns, so the key is documentation.

  The case-semantics paragraph the PO folded in is stated where `filter.py`'s
  reader will meet it, with the reason for the asymmetry rather than just the
  fact. That asymmetry looks like a bug until you know F5.

## Review log (PO)
- 2026-09-22 PO: **PASSES — closed to done.** All five criteria met.

  `package-lock.json` is the single most common lockfile in the ecosystem #104's
  own evidence came from, and it was being ingested as ordinary JSON: tens of
  thousands of lines of resolved dependency metadata, embedded and condensed at
  full price, with nothing in it for an agent reading the map.

  Exact names rather than prefixes, with the reason beside them and a mutation
  proving it — `package-lock.example.json` is documentation and survives.

  The case-semantics paragraph is the part that will save someone an afternoon.
  The baked list matching case-insensitively while user globs match literally
  looks like an inconsistency until you know it is holding F5 shut.
