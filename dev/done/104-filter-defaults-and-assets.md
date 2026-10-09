---
id: 104
title: Filter — user excludes replace the defaults, and binary-ish text assets are ingested
priority: high
size: small
depends_on: []
spec_refs: [build-order.md#T13, build-order.md#T7.1]
found_by: e2e manual QA 2026-09-03 — .e2e/FINDINGS.md F4, F5
---

## Context
`ingest/filter.py:_excludes` returns the caller's list when present, else
`_DEFAULT_EXCLUDE = ("**/node_modules/**", "**/*.lock")`. The only binary gate
is a null-byte sniff.

## Description
**F4 — excludes replace instead of extend.** A source that excludes one
directory silently loses `node_modules` and lockfile protection; on a JS repo
that is thousands of vendored files, embedded and condensed at LLM cost. The
e2e run had to repeat both default patterns by hand in all three sources.

**F5 — SVGs are treated as prose.** PNGs are correctly skipped (null bytes) but
SVGs sail through (`.e2e/artifacts/ingest-coverage.md`):

```
media/logo.svg                       -> 8 sections   (chalk)
docs/_static/itsdangerous-name.svg   -> 2 sections
docs/_static/itsdangerous-logo.svg   -> 1 section
docs/_static/itsdangerous-icon.svg   -> 1 section
```

12 of 92 sections (13% of the corpus and 13% of the condense LLM spend) were
path data. They then clustered together into node 1, whose brief was the
garbage in 103 — so the map's first topic was noise generated from noise.

Work:
- User `exclude` patterns extend the defaults (with an explicit replace opt-out
  if that is ever wanted).
- `split/constants.py` already has an extension -> category table; add an
  `ignore` category (svg, eps, ico, .map, .min.js, .min.css, fonts, ...).
- Skip zero-byte files here as well (see 099).

## Decision (2026-09-12, dev — technical call, no PO input needed)

Technical half, decided: a supplied `filter.exclude` EXTENDS the baked defaults;
replacing them requires an explicit `filter.replace_defaults: true`.

## Decided 2026-09-14 (PO)

Ignore by default, opt-in to include:
- **assets / non-prose**: `.svg .eps .ico .map .min.js .min.css` + font files
  (`.woff .woff2 .ttf .otf .eot`)
- **tabular data**: `.csv` (and `.tsv` — same shape, same near-zero value per
  token to an agent reading a map)
- **generated code**: `*_pb2.py`, `*_pb2_grpc.py`, `*.pb.go`, `*.g.dart`,
  `*.generated.*`, OpenAPI/Swagger-generated clients
- **vendored trees**: `vendor/`, `third_party/`, `node_modules/` (already there)

Rationale: the cost of ingesting these is per-section and immediate (embed +
one condense LLM call each), the benefit is occasional. In the QA run SVGs alone
were 12 of 92 sections — 13% of the corpus and 13% of the condense spend — and
they formed a junk topic occupying a seventh of the map.

Keep the list as DATA next to the existing extension -> category table, and add
an opt-in (`filter.include_generated: true` or an explicit `include` pattern) so
a caller who genuinely wants a generated client can ask for it.

Bad-brief handling (the other half of question B) is dev's call, recorded in
103: retry once, then store with a flag for triage rather than dropping the node.

## Acceptance criteria
- [ ] A source with a custom `exclude` still skips `node_modules` and lockfiles.
- [ ] No SVG / minified / font asset produces a section on the e2e corpus.
- [ ] `ruff format`, `ruff check --fix`, `pytest` clean.

## Review log
- 2026-09-14 dev: started; moved to in-progress.
- 2026-09-14 dev: implemented and committed as `306f0e2`, following the PO's
  "Decided 2026-09-14" block as written.

  **The data.** `ingest/split/constants.py` gains `DEFAULT_IGNORE`, a glob table
  beside the extension -> category table, grouped by WHY, plus
  `OPTIONAL_IGNORE = "generated"`. The old `_DEFAULT_EXCLUDE` is folded in so
  there is ONE list, not two:
  - `vendored`: `**/node_modules/**`, `**/vendor/**`, `**/third_party/**`
  - `locks`: `**/*.lock`
  - `assets`: `.svg .eps .ico .map .min.js .min.css .woff .woff2 .ttf .otf .eot`
  - `tabular`: `.csv .tsv`
  - `generated`: `*_pb2.py`, `*_pb2_grpc.py`, `*.pb.go`, `*.g.dart`,
    `*.generated.*`, `**/generated/**`, `**/.openapi-generator/**`,
    `**/.swagger-codegen/**`
  For "OpenAPI/Swagger-generated clients" I took only the two UNAMBIGUOUS marker
  directories those generators write, not a guess at client file names: a wrong
  pattern there drops real source, which is the one outcome worse than the junk
  being removed.

  **The rules** (`ingest/filter.py`, rewritten around a small frozen `_Rules`):
  1. the caller's `exclude` always applies and always wins;
  2. the baked groups EXTEND it (F4: they used to be REPLACED by it);
  3. `include: [patterns]` re-admits a file the baked groups caught — it does
     NOT override the caller's own `exclude`, so user intent stays the top
     layer;
  4. `include_generated: true` drops the `generated` group only;
  5. `replace_defaults: true` drops all baked groups — the full escape hatch.
  `registry/sources.py:GitFilter` gains `include`, `replace_defaults` and
  `include_generated`, so all three are validated at the API boundary.
  The size/symlink/binary gates are not patterns and are never dropped.

  **The 099 split, so nothing is double-implemented or dropped.** 099's own
  Decision names three changes; I did exactly the first here, because 104's
  decision block told me to: **the filter skips zero-byte files** (`size == 0`,
  next to the size cap). Left for **099**: (a) the "seen, produced no sections"
  marker for files that are non-empty but the splitter yields nothing for
  (whitespace-only, comment-only) — the zero-byte gate does NOT cover those and
  they have the identical phantom-`new` symptom; (b) moving `_next_batch` out of
  `_update_source` so it is called once per `update` run. 099's acceptance
  criterion ("update over an unchanged corpus changes nothing, batch counter
  included") is NOT met by this commit alone.

  **Real ingest delta over the three e2e repos** (`.e2e/repos/*`, read-only;
  old filter reconstructed exactly, both run with the source configs the QA run
  actually used, sections counted with the REAL splitter):

  | source       | files before -> after | sections before -> after |
  |--------------|-----------------------|--------------------------|
  | itsdangerous | 36 -> 32              | 41 -> 37                 |
  | chalk        | 22 -> 15              | 30 -> 16                 |
  | uuid         | 22 -> 22              | 23 -> 23                 |
  | **total**    | **80 -> 69**          | **94 -> 76 (-18, 19%)**  |

  Every dropped file, with the sections it used to cost:
  ```
  -1  docs/_static/itsdangerous-icon.svg      -8  media/logo.svg
  -1  docs/_static/itsdangerous-logo.svg      -1  source/vendor/ansi-styles/index.d.ts
  -2  docs/_static/itsdangerous-name.svg      -1  source/vendor/ansi-styles/index.js
  -0  src/itsdangerous/py.typed  (zero-byte)  -1  source/vendor/supports-color/browser.d.ts
                                              -1  source/vendor/supports-color/browser.js
                                              -1  source/vendor/supports-color/index.d.ts
                                              -1  source/vendor/supports-color/index.js
  ```
  All four SVGs are gone and they are exactly F5's **12 sections** (8+2+1+1).
  `uuid` is untouched — 22 files, 23 sections, byte for byte. No `.csv`/`.tsv`
  exists in these three repos, so that class is proven by unit test only.
  Surviving extensions per source, i.e. nothing genuine was lost:
  itsdangerous `.py .md .rst .toml .txt .json .yaml .sh .bat` + extensionless,
  chalk `.js .ts .md .json` + extensionless, uuid `.go .md .mod` +
  extensionless.

  **One judgement call the PO should see before the e2e re-run.** 6 of the 7
  chalk files dropped are `source/vendor/ansi-styles` and
  `source/vendor/supports-color` — genuine third-party JS that chalk vendors in,
  and the e2e run's node-2 brief explicitly described them as part of chalk's
  topic. They match the PO's `vendored` group exactly (`**/vendor/**`), so this
  is the decision working as written, not a leak; but it IS real content leaving
  the corpus, unlike the SVGs. Verified on the real repo that the opt-in brings
  them back precisely: `"include": ["**/source/vendor/**"]` re-admits those 6
  files and changes nothing else. If the PO wants them in the re-run, that one
  line on the chalk source is the fix — no code change.

  **Opt-in proven on real data, not just unit-tested** (the PO's point 1):
  `include` re-admits exactly what was asked for and nothing else;
  `include_generated` is a no-op on these repos (they contain no generated
  code) and re-admits `api_pb2.py` + `client.generated.ts` while leaving
  assets and vendored trees ignored in the unit fixture; `replace_defaults`
  re-admits all 7 chalk files.

  Tests (7 new + 1 renamed, 671 total), each verified regression-grade by
  mutating the source and watching the matching test go red:
  `_rules` reverted to replace-not-extend -> `test_custom_exclude_extends_the_
  defaults` fails (F4's regression test; the old test of the same shape was
  named `..._overrides_default` and PASSED under both semantics, which is why it
  never caught this); the `assets` group deleted -> 4 tests fail; the `include`
  override removed -> `test_an_include_pattern_re_admits_one_ignored_file`
  fails; the `size == 0` gate removed -> `test_a_zero_byte_file_is_never_
  ingestable` fails. Also covered: `include_generated` scoping,
  `replace_defaults`, exclude-beats-include, and case-insensitive extensions
  (`LOGO.SVG`).

  Gate clean: `ruff format` (222 files unchanged), `ruff check --fix` (all
  checks passed), `pytest` **671 passed**. Handing off to verifying.
- 2026-09-14 qa: **PASS — to po-review.** All three acceptance criteria hold.
  I reproduced the real-corpus delta independently and it matches dev's table
  exactly; the precedence rules hold in every combination I could construct;
  and every regression-grade claim checks out. Nothing blocking.

  **1. Regression risk — no genuine source or doc was lost.** I reconstructed
  the delta myself rather than reading dev's: the OLD filter from a worktree at
  `3f0df9a` (`PYTHONPATH` asserted inside it) against the NEW one, both over
  `.e2e/repos/{itsdangerous,chalk,uuid}` READ-ONLY, with the exact filter
  configs the QA run used (read out of the stored registry, not the RUN-LOG's
  elided copy), and sections counted with the real `split.pack.split`:

  | source       | files        | sections     |
  |--------------|--------------|--------------|
  | itsdangerous | 36 -> 32     | 41 -> 37     |
  | chalk        | 22 -> 15     | 30 -> 16     |
  | uuid         | 22 -> 22     | 23 -> 23     |
  | **total**    | **80 -> 69** | **94 -> 76** |

  Dev's numbers are exact. All 11 dropped files and their section costs match
  the Review log line for line. The four SVGs are 8+2+1+1 = **12 sections**,
  exactly F5's count; `src/itsdangerous/py.typed` is the 0-byte file; `uuid` is
  untouched. Surviving extension sets match what dev reported
  (itsdangerous `.py .md .rst .toml .txt .json .yaml .sh .bat` + extensionless,
  chalk `.js .ts .md .json` + extensionless, uuid `.go .md .mod` +
  extensionless). I then hunted the other way — every dropped path whose
  extension is source-or-doc — and the ONLY hits are the six chalk
  `source/vendor/**` files. No `.py`, `.md`, `.go`, `.rst` or first-party `.js`
  stopped being ingested anywhere.

  **2. Precedence — holds in every combination, and the hard gates are not
  droppable.** Built a synthetic tree and drove the full matrix:
  - baked groups still apply alongside a caller `exclude` (F4 closed);
  - `include: ["**/src/secret.py"]` does NOT re-admit a caller-excluded file;
  - `include: ["**/*.svg"]` DOES re-admit a baked-ignored file;
  - `include_generated: true` re-admits `api_pb2.py`,
    `gen/client.generated.ts`, `generated/out.py` and NOTHING else — assets and
    vendored trees stay ignored;
  - `replace_defaults: true` re-admits all seven baked-group files while the
    caller's own `exclude` still wins;
  - and under the maximum escape hatch
    (`replace_defaults: true` + `include: ["**"]`) the four non-pattern gates
    still hold: a 3 MB file, a file with a null byte, a zero-byte file and a
    symlink are excluded in every one of the nine configurations I ran.

  **3. Pattern soundness — no false positives I could find.** `**/vendor/**`,
  `**/third_party/**` and `**/generated/**` match a whole path SEGMENT only, so
  `src/vendored_helpers.py`, `src/vendor.py`, `third_party_utils/x.py` and
  `src/generated_code.py` all survive. `**/*.map` does not touch `roadmap.md`
  or `sitemap`. `**/*.min.js` does not touch `a.js`. All the globs match at the
  repo ROOT as well as nested (`**` matches zero segments), so `logo.svg` and
  `node_modules/` at the top level are caught. Taking only the two generator
  marker directories for OpenAPI/Swagger rather than guessing client filenames
  is the right call and I could not construct a legitimate file it catches.
  The one pattern that does catch something arguably legitimate is
  `**/*.generated.*` on a hand-written `report.generated.md` — which is the
  PO's decision working as written, not a leak.

  **4. The old test really was non-discriminating.** `3f0df9a`'s
  `test_custom_exclude_overrides_default` created only `a.py` and `b.py` — no
  `node_modules`, no lockfile anywhere in the tree — so its `== ("a.py",)`
  passes identically under replace and under extend semantics. That is exactly
  why F4 survived. The replacement builds the tree first and asserts
  `node_modules/dep/index.js` and `poetry.lock` stay out.

  **Mutation-verified myself**, in a worktree at `306f0e2`, five mutations,
  each caught by exactly the expected test and nothing else:
  - baked groups replaced-not-extended by a caller exclude ->
    `test_custom_exclude_extends_the_defaults`;
  - the `assets` group emptied -> 4 tests
    (`..._ignored_by_default`, `..._re_admits_one_ignored_file`,
    `..._generated_group_only`, `..._case_insensitively`);
  - `include` no longer re-admits -> `test_an_include_pattern_re_admits_one_
    ignored_file`;
  - the `size == 0` gate removed -> `test_a_zero_byte_file_is_never_ingestable`;
  - and one of my own, inverting the precedence so `include` beats the caller's
    `exclude` -> `test_a_users_exclude_beats_their_include`.

  **5. The 099 split is coherent — with one correction 099 needs.** 104 did
  exactly the first of 099's three changes, which 104's own decision block told
  it to do, and dev stated the boundary rather than leaving it implicit. But I
  probed 099's stated residual and it appears to be **empty**: `split()` returns
  `()` only for genuinely empty bytes, and I could not construct a non-empty
  input that yields zero sections — whitespace-only, comment-only, a single
  newline, a single space, across `.py .md .txt .go .js .rst .json .yaml` and
  extensionless all produce 1 section. Since 104's zero-byte gate now stops the
  only zero-section case before the splitter sees it, 099's half (a) — the
  "seen, produced no sections" marker — has no reachable state to guard, and
  099's motivating repro (`py.typed`) is already fixed here. **099 should be
  re-scoped before it is picked up**: confirm (a) is genuinely unreachable
  rather than building a marker mechanism for it, leaving `_next_batch`
  once-per-run as the real remaining work. Nothing fell BETWEEN the two
  tickets; the risk is the opposite, 099 being built twice as large as it is.

  **The chalk vendor question, as a factual matter — dev's account is exact.**
  The six files are `source/vendor/{ansi-styles,supports-color}/**`, genuine
  third-party JS chalk vendors in, 6 sections total. The real corpus confirms
  the rest: node 2's stored brief opens "a technical audit of **chalk 6.0.0**
  ... deconstructed into its benchmarks, public API, implementation internals,
  and **two vendored dependencies** (`ansi-styles` and `supports-color`)" and
  carries a whole "**Vendor: ansi-styles**" section; all six files are in node
  2's membership. And the opt-in lands precisely: on the real repo,
  `"include": ["**/source/vendor/**"]` adds exactly those six paths and removes
  nothing, while `replace_defaults` adds those six plus `media/logo.svg`. So
  this is real content leaving the corpus, it is the PO's `vendored` group
  working as written, and the fix if the PO wants them back is one line of
  source config with no code change. Purely the PO's call; I am not blocking on
  it.

  **Notes, none blocking:**
  - **Case semantics are asymmetric and undocumented.** `_Rules.skips`
    (`src/hrono/ingest/filter.py`) matches the baked `ignore` list against a
    LOWERCASED path — deliberately, so `LOGO.SVG` cannot sneak past the asset
    rule, and there is a test for it — but matches the caller's `exclude` and
    `include` against the path as-is. So `include: ["**/*.svg"]` re-admits
    `logo.svg` and silently NOT `LOGO2.SVG` (I drove both). I read this as
    defensible and consistent — our safety net is case-insensitive, the
    caller's own globs are literal, like every other glob tool — but the module
    docstring says nothing about case, and the asymmetry is exactly the sort of
    thing that reads as a bug later. Worth one sentence in the docstring.
  - **Lockfile names.** `**/*.lock` catches `uv.lock`/`yarn.lock`/
    `Gemfile.lock` but not `package-lock.json` or `pnpm-lock.yaml` — the
    default npm and pnpm lockfiles, and the biggest files in most JS repos. Not
    a regression (the pattern is unchanged from before #104) and none of the
    three e2e repos has one, so the real-corpus delta could not surface it.
    Filed as backlog **#118** rather than blocking.
  - `registry/sources.py:GitFilter` validates all three new fields at the API
    boundary, so a typo is a 422 rather than a silently-ignored knob. Good.
  - Commit `306f0e2` is a clean Conventional Commit, atomic, 4 files, no stray
    changes; the `.gitignore` line is still the pre-existing uncommitted one.
    `.e2e/` untouched throughout — repos read-only and still clean, database
    worked on as a copy in scratch.

  Gate re-run by me on `306f0e2`: `ruff format --check` 222 files unchanged,
  `ruff check` clean, `pytest` **671 passed** in 37.3s. Worktrees removed, tree
  clean. Handing to the PO — with the chalk-vendor decision and the 099
  re-scope as the two things worth their attention.
- 2026-09-14 PO: **ACCEPTED -> done.** Commit 306f0e2 implements the
  2026-09-14 decision block as written. Verified independently.

  **Gate re-run by me:** `ruff format --check .` 222 files already formatted;
  `ruff check .` all checks passed; `uv run pytest` **671 passed** in 37.6s.

  **Diff read.** The shape is right: the ignore list is DATA grouped by WHY,
  sitting beside the extension table it belongs with, and `_Rules.skips` is a
  three-line predicate that makes the precedence readable at a glance — the
  caller's `exclude` returns early and unconditionally, the baked groups apply
  only when `include` does not re-admit. Folding the old `_DEFAULT_EXCLUDE` into
  the one table rather than keeping two lists is the right instinct. Taking only
  the two unambiguous generator marker directories for OpenAPI/Swagger, rather
  than guessing client filenames, is the correct conservatism: dropping real
  source is worse than keeping junk.

  **Precedence driven by me** over a synthetic tree, all nine behaviours
  confirmed: a caller `exclude` no longer replaces the baked groups (F4 closed —
  `node_modules` and lockfiles stay out alongside it); `include: ["**/*.svg"]`
  re-admits a baked-ignored file; a user's `exclude` beats their own `include`;
  `include_generated` re-admits `api_pb2.py` while assets and vendored trees
  stay ignored; `replace_defaults` re-admits everything. Segment matching holds
  — `src/vendored_helpers.py`, `src/vendor.py`, `third_party_utils/x.py`,
  `roadmap.md` and `src/generated_code.py` all survive, which is where a naive
  substring list would have done real damage.

  **Real delta re-measured by me** on `.e2e/repos/*`, read-only (`.e2e/`
  untouched). My absolute counts differ from dev's and qa's because I used a
  generic config rather than the run's exact per-source excludes — but the
  DELTA, which is what matters, matches exactly: the four SVGs cost
  **8+1+1+2 = 12 sections**, precisely F5's figure; the six chalk
  `source/vendor/**` files cost 6; `uuid` loses nothing. No `.py`, `.md`,
  `.go`, `.rst` or first-party `.js` is dropped anywhere.
  The zero-byte gate confirmed on the real file: `src/itsdangerous/py.typed`
  (0 bytes) is no longer ingestable, **and stays out even under the maximum
  escape hatch** (`replace_defaults: true` + `include: ["**"]`) — no zero-byte
  file is ingestable in any configuration, because the gate is not a pattern.
  That is the correct layering.

  All three acceptance criteria hold.

  **Rulings:**
  1. **#099 CONFIRMED EMPTY on its first half, and re-scoped.** I did not take
     this on qa's word — I probed `split()` over **252 combinations** (18
     degenerate inputs x 14 extensions), going well past qa's set:
     whitespace-only, comment-only (`#`, `//`, `/* */`, `<!-- -->`), a lone
     newline, CRLF-only, a single space, a single char, punctuation-only, a
     bare BOM, BOM+newline, form feed, NBSP and a zero-width space, across
     `.py .md .txt .go .js .ts .rst .json .yaml .toml .html .css .sh` and
     extensionless. **Every non-empty input yields at least one section.** The
     ONLY zero-section input is genuinely empty bytes — and 104's zero-byte gate
     now removes that before the splitter is reached, at every configuration.
     So 099's "seen, produced no sections" marker has no reachable state to
     guard, and 099's motivating repro (`py.typed`) is fixed HERE. I have
     re-scoped 099 to the `_next_batch` half and recorded the evidence in it.
     Good catch by qa — this is the rarer and more valuable kind of finding, a
     ticket that would have been built at several times its real size.
  2. **#118 CONFIRMED, `low`, and it does NOT need to land before the e2e
     re-run.** I reproduced the gap directly: `poetry.lock` and `yarn.lock` are
     ignored by default, `package-lock.json` and `pnpm-lock.yaml` are NOT. Real
     and worth fixing — these are usually the largest files in a JS repo, so the
     cost is concentrated. But it is not a regression (the pattern predates
     104), and I checked the three e2e repos myself: the only lockfile present
     is `itsdangerous/uv.lock`, which `**/*.lock` already catches. So the
     re-run cannot surface it and gains nothing from waiting.
  3. **Case semantics: DOCUMENT, do not unify.** I drove the asymmetry —
     `include: ["**/*.svg"]` re-admits `logo.svg` and not `LOGO2.SVG`. It is
     principled and I want it kept: the baked list is a SAFETY NET, so it must
     be case-insensitive or `LOGO.SVG` reopens F5; the caller's own globs are
     their instructions, and every ordinary glob tool treats those literally.
     Unifying breaks something either way — making user globs case-insensitive
     silently widens their `exclude` beyond what they wrote, and making the
     baked list case-sensitive puts the F5 hole back. What is wrong is only that
     nothing says so. One sentence in the `filter.py` docstring; folded into
     **#118**, which already touches this list's coverage, rather than spawning
     a card for a sentence.
  4. **The chalk `source/vendor/**` question is NOT mine and I have not decided
     it.** Recorded as an open human-PO decision below, with the facts.

  **OPEN — for the human PO, before the e2e re-run.** Six of the eleven dropped
  files are chalk's `source/vendor/{ansi-styles,supports-color}/**`: genuine
  third-party JS that chalk vendors in, 6 sections. Unlike the SVGs this is real
  content leaving the corpus. The facts, confirmed by qa against the stored
  corpus: node 2's brief explicitly names "two vendored dependencies
  (`ansi-styles` and `supports-color`)" and carries a whole "Vendor:
  ansi-styles" section, and all six files are in node 2's membership — so the
  previous map treated them as part of chalk's topic. They match the `vendored`
  group exactly, so this is the decision working as written, not a leak. If they
  should come back, `"include": ["**/source/vendor/**"]` on the chalk source
  adds exactly those six and nothing else: one line of source config, no code
  change, reversible, and it affects only what the re-run ingests. Left open
  deliberately — this is a judgement about what a knowledge map should contain,
  not a defect.
