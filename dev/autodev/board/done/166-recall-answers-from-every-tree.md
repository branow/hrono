---
id: 166
title: recall answers from every tree's corpus, whichever tree you ask
priority: high
size: medium
depends_on: [054, 134]
spec_refs: [implementation-notes.md, design-sketch-v1.md]
---

## Context
Filed by qa while verifying #054, which is what made this reachable.

`POST /trees/<name>/recall` takes the tree in its URL and then discards it.
`engine.recall(conn, question, model_name, encode, limit=...)` has no tree
parameter, and neither leg has one to pass it to:

- `vector_leg.scores` runs `SELECT id, content_hash, path FROM passages ORDER
  BY id` — every passage in the database. Its own docstring says so: "the
  vector z-score for EVERY embedded passage".
- `keyword_leg.scores(conn, query)` takes only the connection and the query.

So there is no path by which a tree could filter the result. Established by
reading both legs rather than by driving a leak: the confidence gate (#127)
correctly refuses a corpus small enough to fabricate in a test, which is why
this wants a real fixture and a ticket rather than a one-line assertion.

## Why now, and why high
Before #054 this was invisible: every tree held every section, so "the whole
corpus" and "this tree's corpus" were the same set. #054 made a named tree a
map over its OWN sources, which is the first time the two differ — and the
write side is now scoped while the read side is not.

The result is worse than an unscoped feature: an operator who declares `alpha`
and `beta` gets two correctly separated maps and then one shared answer, from
the door they actually use most. It should land before multi-tree is documented
as working.

## The shape
The join already exists — #054 introduced it for the build. A passage carries
no tree of its own and should not: it reaches one through
`passages -> sections.source -> the tree's sources`, exactly as
`section_combined_vectors` now does, with `registry.trees.sources_of` returning
None for an undeclared tree so a single-corpus database is unchanged.

Decide while implementing:
- whether the legs take the scope or the engine pre-computes the candidate set
  (the legs currently z-score over the WHOLE population, and a z-score over a
  subset is a different number — this is the real design question, not the
  SQL);
- whether `node://` brief passages (#071) scope by their node's tree instead,
  since they have no source.

That second point matters: brief passages ARE tree-scoped data reached through
`nodes.tree`, so the two passage kinds need different joins to the same answer.

## Acceptance criteria
- [x] Recall over tree T returns only passages reachable from T's sources, plus
      brief passages of T's own nodes.
- [x] An undeclared tree still searches everything (the single-corpus case).
- [x] The z-score population is a decided question with the decision recorded —
      whole corpus or tree subset — because it changes every score.
- [x] A regression test with a corpus large enough to clear the confidence gate
      proves a two-tree database does not answer across trees.
- [x] `ruff format`, `ruff check --fix`, `pytest` clean.

## Review log
- 2026-09-25 qa: filed from #054 verification.

- 2026-09-25 po: ruling on the z-score population, which the ticket deliberately
  left open. **The z is computed over the TREE's own passages, not the whole
  corpus filtered afterwards.**

  Semantics first: a z-score answers "how unusually well does this passage match,
  among the passages that could have answered". The candidates that could have
  answered a question put to tree alpha are alpha's. Scoring against a
  distribution that includes beta's corpus means a large tree can suppress a
  small one's best match below the floor — the answer to "what does alpha say"
  would depend on how much unrelated material sits beside it.

  And it is the reading that keeps the measured recipe valid. Every threshold in
  it — the 3.5 qualify floor, 3.0 support, the keyword leg's 6.0, #102's
  median/MAD centring — was measured over ONE corpus, which is exactly what a
  single or undeclared tree still is. So a database with one tree scores
  identically to today, and no measurement is invalidated. The alternative
  changes nothing today and is wrong later, which is the worse trade.

  This does mean multi-tree calibration is unmeasured: the floors are known good
  for one corpus and assumed for each tree of several. That is honest and worth
  a note in the ticket's log rather than a blocker — the measurement wants real
  multi-tree corpora, which nobody has yet.

- 2026-09-25 dev: picked up under that ruling.

- 2026-09-25 dev: done, commit 72c25e2. Built under the PO's ruling — the z is
  measured over the tree's own passages — and that ruling decided the shape of
  the whole change: the scope is a SET OF PASSAGE IDS applied inside each leg
  before its z, not a filter over the fused result. Filtering afterwards was
  the obvious implementation and it would have scored every passage against a
  population the question was never asked of.

  `recall/scope.py` holds the one join, and it is two joins because a passage
  reaches a tree two ways: a content passage through `sections.source` (#054's
  join) and a `node://` brief through `nodes.tree`, because a brief's source is
  the synthetic `node-<id>` and matches no registered source. A scope built
  only the first way drops every brief from every tree — recall would silently
  stop answering from the summaries the whole upper tree exists to produce, and
  the mutation that removes the brief join proves the test catches it.

  Driven on a real server with REAL embeddings (all-MiniLM-L6-v2, 34 passages
  across two sources), asking a question only beta's corpus can answer:

      tree beta         -> beta-src/d0.md, beta-src/d1.md
      tree alpha        -> alpha-src/d0.md only, no beta hit
      tree "undeclared" -> both trees' passages, best first

  The third line is the one that matters most: an undeclared tree still sees
  everything, so a single-corpus database answers exactly as it did.

  Mutations. Four run, TWO survived and were made to kill, and the reason is
  the interesting part:
  - the engine discarding the tree (the original defect) -> 2 fail.
  - the scope forgetting brief passages -> 1 fail.
  - the VECTOR leg ignoring its scope -> SURVIVED.
  - the KEYWORD leg ignoring its scope -> SURVIVED.

  Both survived for the same reason: the fusion requires BOTH legs to agree
  before a passage becomes a hit, so one leg filtering is enough to keep
  another tree out of the ANSWER. What one leg cannot do alone is keep the
  other tree out of the DISTRIBUTION — and a z is a statement about a
  population. Dropping either filter leaves the hit set right and every score
  wrong, which is precisely the silent kind. `test_each_leg_scores_over_its_
  own_tree_s_population` now asserts each leg separately, and both mutations
  fail it.

  Getting that test to be true took two corrections worth recording. The first
  fixture gave both trees identical corpora, so the combined median and MAD
  equalled each half's and the z did not change at all — a symmetric fixture
  cannot show a population effect. Beta is now 28 passages with a different
  filler vector. The second: only the two planted answers matched the query
  term, so each tree's keyword population was a single item and both z-scores
  were 0.0 by the std==0 branch. Some of beta's filler now MENTIONS the term
  without answering it.

  **Unmeasured, and worth saying plainly.** Every floor in the recipe — 3.5
  qualify, 3.0 support, the keyword leg's 6.0, #102's median/MAD centring — was
  measured over one corpus. A single or undeclared tree still IS one corpus, so
  nothing measured has changed. Per-tree calibration in a multi-tree database
  is assumed, not measured, and the measurement wants real multi-tree corpora
  that nobody has yet.

  Gate clean: 1139 passed.

- 2026-09-25 qa: PASS, to po-review. Every criterion met, and the two surviving
  mutations dev chased are the reason I believe the ruling is actually
  implemented rather than merely intended.

  Gate re-run at 72c25e2: ruff clean, 1139 passed. Re-ran dev's brief-join
  mutation and it fails, so the `node://` half of the scope is really guarded —
  that one matters most, because losing it would not break recall, it would
  quietly remove every summary from every answer.

  I drove the real server myself with real embeddings, asking each tree a
  question only beta's corpus answers: beta returns its own two passages, alpha
  returns only alpha's, an undeclared tree returns both. That last line is the
  single-corpus guarantee and it holds.

  Checked the CLI read door, since the CLI is the product surface:
  `hrono recall <tree> <question>` already takes the tree as a required
  positional and posts to `/trees/<tree>/recall`, so it inherits the scoping
  with no change. No gap.

  **Driving it there found something bigger than this ticket, filed as #168 at
  high.** `hrono recall` FAILS against a real model on a real corpus:

      first  POST /trees/beta/recall   11.87s
      second POST /trees/beta/recall    7.70s
      CLI client timeout                10.0s
      what the user is told: "Cannot reach hrono server at ..."

  Three things are wrong and they compound: the encoder is rebuilt on every
  request (the server log loads the weights once per recall, which is the ~8s
  floor), the client reports a TIMEOUT as UNREACHABLE, and the 10s budget is
  the registry-CRUD default rather than a number anyone chose for recall.

  None of it is #166's doing — all three predate it. It went unseen because
  every test injects a fake encoder and every previous manual check used curl,
  which has no such timeout. It is the command the product exists to serve, and
  from the CLI it does not work.

  One note for #077 rather than a finding: `passages_of` now runs a full scan to
  build the id set, and the vector leg then scans every passage again skipping
  what is out of scope. Correct, and one scan more than a scoped SQL read would
  need. It is noise next to the 8s encoder load, and it becomes worth fixing in
  the same pass that bounds the vector leg.

- 2026-09-25 po: CLOSED, first round. The read door now agrees with the write
  door, and #054's promise is true from both sides.

  The part I want kept is the pair of surviving mutations. Each leg's filter
  was individually unguarded because the fusion requires both legs to agree, so
  one filter is enough to make the ANSWER right while the SCORES are computed
  against a population that includes another tree entirely. A hit set that
  looks correct over statistics that are wrong is the hardest kind of defect
  this board has to find, and the only reason it was found is that dev ran the
  mutation on each leg separately instead of on the feature.

  The two fixture corrections behind that test are the same lesson twice: a
  symmetric fixture cannot show an asymmetry, and a single-item population has
  no distribution to change. Both versions passed while proving nothing.

  **#168 promoted to `todo` at high — it goes next, ahead of #163 and #161.**
  qa found that `hrono recall` does not work from the CLI against a real model:
  ~8-12s per call against a 10s client timeout, reported to the user as
  "Cannot reach hrono server". Three compounding defects, all predating this
  ticket, none visible to a suite that injects a fake encoder or to a manual
  check that uses curl.

  That last point is the finding under the finding, and it is mine to act on
  rather than dev's: **every recall test injects the encoder, and the one
  measurement that mattered came from loading a real model.** It is #094's
  lesson — 585 green tests over a corpus that could not build — arriving in the
  read door instead of the write door. CLAUDE.md already requires a real
  backend through every seam; what it does not require is that the real backend
  be exercised at REAL SIZE, where latency lives. I am not writing that as a
  convention yet. If #168's fix needs a second such measurement to prove
  itself, it becomes one.

  M9 and the multi-tree correction are done. The board's remaining high is
  #168; #163 and #161 follow.
