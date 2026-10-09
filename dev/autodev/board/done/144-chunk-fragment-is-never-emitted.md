---
id: 144
title: the URI's #chunk-n fragment is documented but never emitted
priority: low
size: small
depends_on: []
spec_refs: [design-sketch-v1.md, CLAUDE.md]
found_by: dev while writing #143's identity assertions
---

## Context
The settled URI scheme is
`<source-type>://<instance>/<path>#chunk-<n>@<version>`, and `recall/engine.py`
reads a document key as "the passage's URI without its `#chunk-n` fragment".
No code anywhere writes that fragment: `grep -rn "chunk-" src/hrono` returns
exactly one hit, and it is that comment. A passage's stored `uri` is its
section's — `git://ex/repo/a.py@v1` — with position carried in `sp_paths` and
the row's ordinals instead.

Found while asserting #143's identity rules over a non-filesystem source: the
assertion that a passage URI carries `#chunk-` failed, and the reason was not
the new reader.

## Description
Decide which is true and make the other match:
- the fragment is genuinely wanted (then passages must emit it, and the
  diversity key in `recall/engine.py` becomes a real strip rather than a no-op
  that happens to work because every passage of a section shares one URI), or
- position is fully carried by `sp_paths` + ordinals (then the scheme in the
  design sketch and CLAUDE.md is stale and should lose the fragment).

Note the second reading makes `recall`'s document key silently correct for the
wrong reason today: it groups by section because the URIs are already equal,
not because it stripped anything.

## Acceptance criteria
- [ ] One of the two readings is chosen and recorded.
- [ ] Code and docs agree; the recall document key means what it says.
- [ ] `ruff format`, `ruff check --fix`, `pytest` clean.

## Review log
- 2026-09-23 dev: filed from #143. Not blocking it — #143 asserts the identity
  rules as implemented and says so in the test.

- 2026-09-23 po: PROMOTED to todo, with the decision made so dev does not have
  to guess. The spec settles it: `context.md` records that "named fragments
  were considered and rejected since `@version` changes every URI on any edit
  anyway", and CLAUDE.md's own line says "position is data, not identity" —
  one sentence before printing a canonical form that contains a position. The
  code is right; the scheme as written down is stale. So: the URI stays
  fragment-free, and what must change is the wording in CLAUDE.md, the comment
  in `recall/engine.py`, and the `split("#")` that implements a strip nobody
  needs. Size small, priority low, but worth doing while the evidence is fresh:
  the next person to read that comment will otherwise implement the fragment.

- 2026-09-23 dev: the PO's reading is the one the code already follows, so the
  change is to the words and to the one line implementing a strip nobody needs.
  `recall/engine._documents` returns the stored URI; its docstring says why
  there is nothing to strip; CLAUDE.md's URI line now matches the spec's own
  record of the decision.

  The interesting part is what it uncovered. #126's end-to-end reserve test
  hand-wrote `...@v1#chunk-<n>` URIs straight into `passages` — a shape nothing
  in hrono emits — so every passage looked like its own document and the
  reserve was being exercised against fabricated data. Removing the strip made
  it fail, which is how it surfaced. Its fixture now stores passages through
  `insert_passage`, like production, and the test still kills the reserve
  mutation (reserve off -> 3 fail), so it has teeth AND realistic data now.

  Mutations run, all killed:
  - the key computed per passage -> 3 fail.
  - the key with the version stripped -> 2 fail.
  - the reserve disabled, against the REPAIRED #126 test -> 3 fail.

- 2026-09-23 qa: PASSED. Re-ran dev's per-passage-key mutation (3 fail) and
  added one dev did not: a `#chunk-0` fragment reappearing in `Address.uri` ->
  5 fail across recall and ingest, so the scheme itself is pinned and not just
  the key. Gate clean, 983 passing. Commit is atomic and subject-only; CLAUDE.md
  is correctly absent from it (gitignored, local-only by its own first line).

  The real value here is the repaired #126 test, which is the third time this
  board has caught a test that passed for a reason unrelated to its name
  (#125, #128, now this). Worth noting the pattern: all three were fixtures
  that wrote rows production never writes.

- 2026-09-23 po: CLOSED. Docs and code now agree, and the decision is recorded
  where the next reader will meet it rather than in a spec file outside the
  repo. I am taking the fixture pattern seriously — see the note added to #128.
