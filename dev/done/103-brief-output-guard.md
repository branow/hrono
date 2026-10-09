---
id: 103
title: Brief output guard — a conversational non-answer was stored as a topic's brief
priority: high
size: small
depends_on: []
spec_refs: [build-order.md#T21, build-order.md#T23.1]
found_by: e2e manual QA 2026-09-03 — .e2e/FINDINGS.md F21, F22
---

## Context
Node 1 of the e2e build clustered four SVG assets (see 104). Its stored brief,
served verbatim to any agent reading the map:

```
This appears to be a condensation format guide with SVG examples, not a request
for me to act on something. Are you shar[ing]...
```

## Description
**F21** — the model answered conversationally instead of summarising, and
nothing caught it: `briefs.unfaithful` is `[]` for that node, so the mechanical
faithfulness gate passed it. There is no shape check between the LLM and the
stored tree — no refusal/meta-response detection, no minimum-content check, no
retry.

**F22** — the faithfulness gate also false-positives on ordinary prose. Flagged
tokens after the build (`.e2e/artifacts/tree-01-after-build.md`):

| node | flagged |
| --- | --- |
| 4 | `CI/CD`, `tabs/spaces/line` |
| 5 | `Signer.rsplit`, `TimedSerializer.loads`, `e.g` |
| 6 | `binaries/packages`, `licensor/contributors` |
| 7 | `encoding/decoding` |

`Signer.rsplit` is a genuine catch (the brief attributes `str.rsplit` to the
Signer API). The rest are not identifiers — the gate treats any token containing
`/` or `.` as one — so five false positives against one true positive make the
signal unusable as a triage queue.

Work:
- Add a brief shape guard: detect a meta/refusal/question response and retry
  once, then flag the node rather than storing the text.
- Tighten the identifier heuristic (require an identifier-shaped token:
  `[A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_]`, exclude prose slashes and trailing-dot
  abbreviations, ignore a stopword list like `e.g`, `i.e`, `CI/CD`).

## Decision (2026-09-12, dev — technical call, no PO input needed)

Technical half, decided: tighten the faithfulness heuristic so it only considers
identifier-shaped tokens (`[A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*`, or
CamelCase/snake_case multi-part names), excludes prose slashes, and carries a
small stopword list (`e.g`, `i.e`, `CI/CD`, `and/or`). Target: `Signer.rsplit`
still flags, none of the seven prose tokens do.

## Decided 2026-09-14 (PO)

Retry the call once. If the second reply still fails the shape check, STORE it
but flag the node for triage — never drop the node. Losing a whole topic from
the map because one call misbehaved is worse than a flagged brief an operator
can see and regenerate.

## Acceptance criteria
- [ ] A brief that is a question/refusal is not stored silently; the node is
      flagged (or the call retried).
- [ ] On the e2e corpus the gate flags `Signer.rsplit` and none of the prose
      tokens above; a fixture test pins both directions.
- [ ] `ruff format`, `ruff check --fix`, `pytest` clean.

## Review log
- 2026-09-15 dev: started; moved to in-progress.
- 2026-09-15 dev: implemented and committed as `fd15c60`. Both decided halves,
  plus the export title leak the coordinator folded in.

  **1. The shape guard (`summarize/shape.py`).** It rejects exactly three
  shapes, each something a summary of code or docs does not do:
  - `asks-the-caller` — a sentence ending in "?" that contains you/your. This
    is what catches F21 ("...Are you sharing this as a reference pattern...").
  - `addresses-the-caller` — an assistant meta-opener in the FIRST sentence
    only (`I cannot`, `as an AI`, `I'd be happy to`, `I'm not sure`, `let me
    know if`, `could you clarify`). Restricted to the opening so a brief that
    quotes such a phrase mid-text is safe.
  - `empty` — under 40 characters, i.e. shorter than one sentence.
  Everything else passes. I deliberately do NOT reject: a generic `## Summary`
  heading, no heading, bullets-only, unusual length, or a question ABOUT the
  material ("what happens when a signature expires?") — all pinned as usable in
  `test_usable_briefs_are_left_alone`. The rule is conservative on purpose: a
  false positive costs a paid retry AND pollutes the triage queue the flag
  exists to serve, which is the same failure as no gate at all.

  **2. Retry then flag, never drop (`shape.answer`).** One retry, then store.
  Termination is structural rather than a budget: `answer` makes at most two
  calls — a model that always talks back is stored flagged after exactly two,
  proven by `test_a_model_that_always_talks_back_terminates_and_flags`. The
  stored row keeps the SECOND reply and the reason in the new `briefs.flagged`
  column (migration `0023`, default ''), so triage is
  `SELECT node_id, flagged FROM briefs WHERE flagged != ''`. Usage from both
  calls is SUMMED, because that is what the node cost and the cost API's job is
  cost. Wired into BOTH `brief` and `brief_upper` — a conversational reply at
  level 1 would be the map's root.

  **3. Faithfulness tightened (`summarize/faithfulness.py`).** Identifier
  tokens are now dotted names, camelCase, PascalCase, snake_case and 3+ digit
  numbers; SLASH compounds are not identifiers at all, and `e.g`/`i.e`/`a.k.a`
  are stopwords. A dotted compound counts as supported when the source contains
  it OR contains each of its parts — the same rule the old code already applied
  to slash compounds, moved to where it belongs.

  **Measured on the eight real tokens from F22** (fixture-pinned in
  `test_the_qa_false_positives_are_no_longer_flagged` and
  `test_the_one_genuine_qa_catch_still_flags`):
  `Signer.rsplit` FLAGS; `CI/CD`, `tabs/spaces/line`, `TimedSerializer.loads`,
  `e.g`, `binaries/packages`, `licensor/contributors`, `encoding/decoding` do
  NOT. That the two dotted ones separate is not luck: I checked the September
  corpus's condensations directly — "rsplit" appears in NO live section's
  condensation (only in a stale row for a content hash no section carries any
  more), while "timedserializer" and "loads" both appear. So the part-wise rule
  clears the real API and flags the invented call.

  **Measured on every stored brief in both e2e databases** (read-only; brief
  text with the mechanical reference footer stripped, which is what production
  checks):
  ```
  .e2e/run  (September):  8 flags -> 1   (only Node.js survives)
  .e2e/run2 (the re-run): 17 flags -> 8
  ```
  Everything cleared is prose or a real API: `CI/CD`, `tabs/spaces/line`,
  `Flask/Werkzeug`, `test/demo`, `prefix/postfix`, `JavaScript/Node`,
  `output/checking`, `v3/v5`, `Deno/xo`, `TypeScript/bundlers`,
  `generation/validation`, `Keys/secrets`, plus `BadSignature.payload`,
  `base64.hex`, `TimestampSigner.unsign`, `parse.go`. What remains is mostly
  camelCase API names the source never mentions (`indexOf`, `replaceAll`,
  `stringReplaceAll`, `SigningAlgorithm`, `mystring.signature`) — the gate
  doing its job. Two residual FPs are proper nouns (`JavaScript`, `Node.js`)
  from the pre-existing Pascal/dotted rules; I did not start a product-name
  dictionary for them, and they are 2 flags across 13 briefs rather than 17.

  **The export title leak — fixed in the RENDERER, not the shape check.**
  `.e2e/run2/exports/map/summary-2/brief.md` is a perfectly good brief that
  opens with `## Summary`; `render._heading` slugged that into the directory
  name. Making the shape check demand a title would retry and then flag a good
  brief — the exact false positive constraint 1 forbids, paid for twice. So
  `_heading` now skips a boilerplate heading (summary/overview/introduction/
  ...), strips markdown emphasis, keeps only the first sentence and trims to 80
  characters on a word boundary. On the live artifact the directory becomes
  `this-is-a-specification-document-for-the-itsdangerous-librar-<id>`, and as a
  bonus every root.md link title stops being a whole paragraph. It needs no
  regeneration: it fixes briefs already stored.

  **Test-fixture correction worth flagging for #102's calibration:** several
  suites faked an LLM reply of "a plain summary." (16 chars), which the floor
  correctly reads as no answer. I replaced those stand-ins with realistic
  one-sentence briefs rather than lowering the floor to fit them — what the
  fakes return is now closer to what the ops actually receive.

  Tests (24 new, 738 total), each verified regression-grade by mutating the
  source: removing the retry, removing the question rule, making slashes
  identifiers again, and removing the boilerplate skip each fail their tests.
  Migration `0023` applied to a COPY of the real re-run database: version 23,
  `flagged` column present and empty, `integrity_check ok`. `.e2e/` untouched
  (`run/.hrono/hrono.db` mtime still 2026-09-03 20:54:49).

  Not touched: #120 (next), #102, #105, #113, #114, #101, #110.
  Gate clean: `ruff format` (227 files unchanged), `ruff check --fix` (all
  checks passed), `pytest` **738 passed**. Handing off to verifying.
- 2026-09-15 qa: **PASS — to po-review.** All three acceptance criteria hold and
  I verified both halves against the real stored data rather than lookalikes.
  Two non-blocking findings, one filed as backlog #121.

  **1. False positives — 0 on every real brief, 4 constructible.** Ran the shape
  check over all 14 stored briefs in BOTH databases (copies; brief text with the
  `\n\nReferences:` footer stripped, which is what production checks):
  `.e2e/run` (September) **1 of 7 rejected**, and that one is F21 itself;
  `.e2e/run2` (re-run) **0 of 7**. So on real data the only rejection is the
  true positive.
  The constructed half is where it bites, and it is one class: the
  `asks-the-caller` rule fires on ANY sentence ending in "?" containing
  you/your, so it cannot tell interrogating the caller from QUOTING a question
  that is in the material. Four legitimate briefs are rejected — one opening by
  quoting a source question, one summarising a FAQ, one whose last entry quotes
  a user-voice question, one reporting a readme's rhetorical question. The two
  cases you named specifically (quoted question, FAQ) both fire; "You can
  configure..." does NOT (correctly — it is not a question). Cost per hit is a
  paid retry plus a triage row, and the brief is still stored, so it is spend
  and noise rather than a lost topic — which is why it does not block. The
  corpus that would expose it is docs/FAQ/Confluence, i.e. the next source type,
  so filed as backlog **#121** with the four texts and a cheap discriminator
  (F21's question is the LAST sentence; a quoted one usually is not).
  Everything the ticket promised to leave alone does pass: a generic
  `## Summary` heading, no heading, bullets-only, a question ABOUT the material
  with no "you", an assistant phrase in the SECOND sentence, and a brief exactly
  at the 40-char floor.

  **2. It catches F21's actual text.** Not a synthetic lookalike — the stored
  `briefs.text` for node 1 of `.e2e/run/.hrono/hrono.db` is rejected with reason
  `asks-the-caller`. That is the row the ticket was raised for.

  **3. Termination is structural, and the accounting is right.** Driven with a
  fake model: a model that ALWAYS talks back makes exactly 2 calls and the node
  is stored flagged; bad-then-good makes 2 calls, stores the GOOD reply and
  flags nothing; good-first makes 1. Usage is summed only when a retry happened
  (10+20 in, 1+2 out) and left alone otherwise, so the cost API sees what the
  node cost. The stored flag is the SECOND reply's reason, which is what an
  operator needs — it describes the text they will actually read.
  `SELECT node_id, flagged FROM briefs WHERE flagged != ''` is a usable triage
  queue.

  **4. The 8 remaining run2 flags, judged one by one.** I recomputed against
  each node's own source and cross-checked every token against the repo working
  trees:

  | token | node | verdict |
  |---|---|---|
  | `unix_timestamp` | 2 | **genuine** — appears in NO file in any of the three repos |
  | `mystring.signature` | 3 | **genuine** — `mystring` appears in no repo file; an invented example name |
  | `indexOf` | 4 | **genuine by the gate's contract** — a real chalk name, but absent from the condensations of every one of node 4's six members, so the brief asserted it from pre-training rather than from its input |
  | `replaceAll` | 4 | same |
  | `stringReplaceAll` | 4 | same |
  | `SigningAlgorithm` | 2 | **indeterminate** — a real `signer.py` class; see the note below |
  | `hmac.compare_digest` | 2 | **indeterminate** — same |
  | `JavaScript` | 5 | **residual false positive** — a language name in `chalk/readme.md` (a member) that the PascalCase rule reads as an identifier; dev conceded this one |

  So 5 genuine, 2 indeterminate, 1 residual FP — against 1 genuine / 7 prose
  before. That is good precision, not a gate still too loose, and the direction
  of the remaining error is the harmless one (a name the model supplied that its
  input did not contain).
  The indeterminate pair is worth knowing before the full maintain: **2 of node
  2's 11 members have no `condensations` row at all** (`src/itsdangerous/
  signer.py` and `rotation.py`), because condensations are keyed by content hash
  and #097's re-packing changed those hashes. Those two files hold exactly
  `SigningAlgorithm` and `compare_digest`, so they read as unsupported today
  while they were almost certainly supported when the brief was written. It is a
  consequence of 097 landing on an existing database, not a defect here, and the
  planned full maintain re-condenses everything and heals it — but #102 must not
  be calibrated before that maintain, which is already the agreed order.
  Acceptance criterion 2 verified directly: of the eight F22 tokens,
  `Signer.rsplit` is the ONLY flag — five of the prose tokens are no longer even
  extracted as identifiers, `TimedSerializer.loads` is extracted and cleared
  part-wise, `e.g` is a stopword.

  **5. The renderer change is safe and narrower than feared.** On the real
  database only **1 of 6** directories changes (`summary-2` ->
  `this-is-a-specification-document-for-the-itsdangerous-librar-2`); the other
  five are byte-identical to the previous renderer, and the file count is 80
  both ways. Collision is impossible by construction, not by luck: the name is
  `f"{slug}-{node_id}"` and node ids are primary keys, so two directories differ
  even if `_heading` returned the same string for every node — confirmed, 6
  unique directories with distinct suffixes. One thing worth a line in the
  release note rather than a ticket: `_materialize` never deletes, so exporting
  over a PREVIOUS export leaves the old `summary-2/` directory beside the new
  one. That is pre-existing behaviour for any brief change, the remedy is a
  fresh `-o` directory, and it will happen exactly once per renamed node.

  **6. Migration 0023 against a COPY of the real re-run database:** version 22
  -> 23, the only column added is `flagged`, every existing value is `''`, every
  brief's text is preserved byte-for-byte, `integrity_check ok`,
  `foreign_key_check` empty, the triage query runs, and re-running `migrate`
  applies nothing.

  **The test stand-in replacements are honest.** Only the faked reply TEXT
  changed, from a 16-character stub to a realistic one sentence; every `Usage`
  tuple is unchanged and not one assertion was touched, so the six suites assert
  exactly what they asserted before. The floor was not lowered to fit them
  (`MIN_CHARS` is still 40, the new stubs are ~57 chars) — the fakes were moved
  toward what the ops actually receive, which is the right direction.

  **Mutation-verified by me** in a worktree at `fd15c60` (`PYTHONPATH` asserted
  inside it): the retry removed -> 4 tests fail; the `asks-the-caller` rule
  removed -> 5; slashes made identifiers again -> 6 including every parametrised
  F22 prose token; the boilerplate skip removed -> 1; the flag not stored -> 1.

  **Non-blocking finding — `tests/export/test_render.py:298`,
  `test_a_boilerplate_heading_does_not_become_the_directory_name` does not test
  that.** It builds a tree with a SINGLE level-0 node, which is therefore the
  root, and the root has no directory at all — so its two assertions are
  `"root.md" in files` and `"Summary" in title`, neither of which touches a
  directory name (the second asserts the brief renders verbatim, a different and
  fine property). Removing the boilerplate skip leaves it green. The behaviour
  IS pinned, by `test_a_long_first_line_is_trimmed_to_a_usable_title:329`, which
  builds a non-root node opening `## Summary` and asserts
  `not [d for d in directories if d.startswith("summary-")]` — that is the test
  my mutation failed. So this is a mis-scoped and misleadingly named test rather
  than a coverage hole; please either point it at a non-root node or fold it
  into the test that already covers it.

  Commit `fd15c60` is a clean Conventional Commit, atomic, 17 files, no stray
  changes; `.gitignore` is still the pre-existing uncommitted line. #120, #102,
  #105, #113, #114, #101 and #110 left alone. `.e2e/` was read-only to me
  throughout — every check ran on copies in scratch; `run/.hrono/hrono.db` is
  still at 2026-09-03 20:54:49, and `run2`'s mtime moved only from the server
  shutdown you announced, not from anything I did.

  Gate re-run by me on `fd15c60`: `ruff format --check` 227 files unchanged,
  `ruff check` clean, `pytest` **738 passed** in 42.8s.
- 2026-09-15 PO: **ACCEPTED -> done.** Commit fd15c60. Verified independently.

  **Gate re-run by me:** `ruff format --check .` 225 files already formatted;
  `ruff check .` all checks passed; `uv run pytest` **738 passed** in 45.1s.

  **I ran the shape check over every real stored brief myself**, both databases:
  run1 rejects **1 of 7** — node 1, `asks-the-caller`, which is F21 verbatim —
  and run2 rejects **0 of 7**. **Zero false positives across all 14 real
  briefs.** Migration 0023 applied to a copy: schema 22 -> 23, `flagged` column
  present, all 7 briefs preserved, default `''`. Matches qa exactly.

  **The restraint is what makes this good.** Rejecting exactly three shapes and
  explicitly NOT rejecting a generic "## Summary" heading, bullets-only, unusual
  length, or a question ABOUT the material is the right call: a false positive
  costs a paid retry and then pollutes the very triage queue the flag exists to
  serve, so the guard has to be cheaper to be wrong about than the thing it
  catches. Restricting `addresses-the-caller` to the FIRST sentence, so a brief
  quoting such a phrase mid-text is safe, is the same instinct applied twice.
  Fixing the summary-2 export leak in the RENDERER rather than the shape check
  is also right, and dev's reasoning is the reasoning I would have given:
  summary-2 is a good brief, so demanding a title would retry it and then flag
  it — the exact false positive the ticket forbids, paid twice.

  All acceptance criteria hold.

  **1. THE CAUSAL CLAIM: qa is wrong, and you are right. I settled it with
  measurement.**
  qa attributed the 2 missing `condensations` rows to #097 re-packing changing
  those sections' content hashes. That is disproved directly:
  - **#097 changed ZERO section content hashes.** I ran the real splitter over
    `.e2e/run2/repos` under `733549c` (the commit before #097) and under
    `9e01051`, and compared hash by hash: **112 sections both sides, identical
    key sets, 0 hashes changed.** #097 moved PASSAGE boundaries; section
    boundaries and therefore section content hashes were untouched — which is
    exactly the invariant I verified at its close (sections 112 on both sides).
    So #097 cannot have orphaned a single condensation.
  - **The evidence positively fits your explanation.** Corpus-wide, exactly
    THREE sections lack a condensation:
    `docs/unrelated-cooking-notes.md`, `src/itsdangerous/rotation.py`,
    `src/itsdangerous/signer.py` — precisely the files your incremental
    scenarios touched, and the same count you recorded in September. (qa saw 2
    because it looked only at node 2's members; the third, cooking-notes, is the
    force-assigned chunk.)
  - **And the mechanism is confirmed in the source**: `condense` is called from
    `maintain` and nowhere else. `update` does not condense, `settle` does not
    condense. Any content an `update` ingests is never summarised.

  **I also found the harm is worse than "an incomplete source", and this is the
  part that sets the priority.** `briefs.member_condensations` INNER JOINs
  `condensations`, so an unsummarised member is silently dropped from the reduce
  input — no error, no warning, no flag. But `briefs.member_uris` is a SEPARATE
  query with no such join, so the brief's mechanical reference list **still
  cites the section whose content the model never saw.** The brief therefore
  claims provenance it does not have: an agent following that URI gets content
  the brief does not describe. That is a map lying about its own sources, not
  merely an abbreviated one.
  **This is NOT #106.** #106's F9 is that nothing CHAINS the ops; this is a
  stage missing from INSIDE `update`, and it would persist unchanged even if
  `update -> propagate -> monitor -> repair -> settle` were chained perfectly.
  Filed as **#122**, high.
  **And you are right that the maintain will mask it**: a full build condenses
  everything, so the three uncondensed sections disappear and the gap only
  returns after the next `update`. Two consequences recorded on #122 — it must
  not be verified against a freshly-maintained corpus, and **run2's database is
  currently the only live evidence, so preserve a copy before the maintain
  overwrites it.**

  **2. The mis-scoped test: re-point it, but not now — folded into #102.**
  qa is right on both halves: `tests/export/test_render.py:298` builds a single
  level-0 node which IS the root, and the root has no directory, so the
  boilerplate skip is not exercised and removing it leaves the test green; and
  the behaviour is genuinely pinned by
  `test_a_long_first_line_is_trimmed_to_a_usable_title:329`. So this is a
  naming/scoping defect, not a coverage hole — no silent regression is possible.
  I am not kicking #103 back for it: the ticket met its criteria and a test that
  is merely mis-aimed is not a reason to spend a dev+qa cycle. But I am not
  leaving it as a note either, because **a test whose name claims a property it
  does not test is worse than no test** — the next reader trusts the name and
  may delete the skip. It goes to **#102**, which already edits
  `export/render.py` (the `Children:` footer addendum) and will be in
  `tests/export/test_render.py` anyway. Same pass, no new card.

  **3. #121: confirmed at `medium`, and YES, specify the discriminator now.**
  Medium rather than low: zero false positives on 14 real briefs says the class
  is not currently biting, but a corpus containing an FAQ, a troubleshooting doc
  or a docstring that quotes a question at the reader is entirely ordinary, and
  the cost lands twice — a paid retry plus a polluted triage queue. Not low.
  Not high either: it is one narrow class, bounded, and the guard is otherwise
  measured clean.
  And yes, record qa's discriminator while the reasoning is fresh — a heuristic
  is cheap to write down now and expensive to rediscover. I have recorded it as
  the STARTING proposal with a validation requirement rather than as a settled
  decision, since it is a heuristic nobody has yet tested against a corpus: it
  must keep rejecting F21 and must stop rejecting all four of qa's constructed
  cases, and if it cannot do both, the ticket should say so and close rather
  than ship a worse guard than the conservative one it replaces.
