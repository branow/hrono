# Summarization

How hrono writes briefs and decides when a change climbs the tree. Code:
`src/hrono/summarize/`; the default prompts are seeded from
`src/hrono/registry/collections/prompts.py` and editable per role (`condense`,
`brief`, `brief-upper`, `judge`).

## The recipe

Two layers, gotcha-aware, content-addressed.

1. **Condense, per section** (`summarize/condense.py`, cheap model). The
   condensation is only the input of its topic's brief: it is never shown to
   an agent, in recall or in the export. Each opens with one sentence on what
   the section is for, in the system's own terms (or that it is a test,
   config, migration or document, and what it serves). Then, for code, one
   line for each of: what arrives and its shape (IN), each entry point's
   checks in the order they run (ENTRY), every branch with its exact
   condition and every member of a list it tests (RULE), loops that poll or
   retry (LOOP), what is committed before a call that can fail (ORDER), each
   error handler (ON ERROR), each call to another service, queue, table or
   file with its path or configuration key (CALLS OUT), the states it sets
   (STATES), and what it plainly lacks (ABSENT). Documents and configuration
   keep every decision, value, step and reference. No word target.
   Identifiers and values are copied verbatim; secrets become `<secret>`.
   Results are cached by content hash, so an unchanged section is never
   condensed twice. Up to 8 sections share one call (`summarize/packed.py`),
   because a `claude-code` call carries a large fixed overhead; a section
   whose packed result is missing is retried alone.
2. **Brief, per leaf topic** (`summarize/brief.py`, stronger model). Over the
   condensations, everything a reader needs to answer exact questions about
   the topic, because nothing below the brief is shown: what it does and
   whom it hands work to; its contract with message and record shapes; each
   entry point's checks in order; every decision with its condition, lists
   verbatim; what is committed before a step that can fail and each error
   handler; its connections to other parts; hazards; the sources to open
   first. It says what the code does, never what a name suggests: behaviour
   that lives in another topic is marked "(behaviour not in this topic)". No
   word target. It writes about the topic, never about its input ("this
   group").
3. **Brief, per upper topic** (`summarize/brief_upper.py`, stronger model).
   Over the child briefs, with no condense stage: what the area does, then
   its end-to-end flows as numbered steps naming the part, the function, the
   state at each step and what a failed step leaves behind and what repairs
   it, one line per part not in a flow, and the hazards from how the parts
   interact. 400 to 900 words: the children's briefs are below it in the
   map, so a step names the part and what passes on, never its own checks
   or lists (without a range the bcreg root ran to 13,600 words). The model
   is never told it is in a tree, only whether the parts below are topics
   (level 1: the flows above) or areas of topics (level 2 and the root).
   Above level 1 the brief instead says, for every area, what it is for and
   which areas it hands work to or takes it from, then the flows that cross
   areas, then a **Conventions** part (each rule most areas follow with its
   condition, and each area doing a sibling's job differently), then the
   hazards. Without that, a root copied its first child (xgboost node 162).
   The default is replaced in an existing registry only where the row is
   still an earlier shipped version; an edited prompt is left as written
   (`Descriptor.superseded`). When the leaves below were written with
   lookups, the input ends with `=== Outside this area ===`: each topic
   elsewhere that a leaf here took a statement from, or that took one from
   a leaf here (`brief_uses`), with its opening line and what passed
   (`briefs.outside`). A step names such a part and says it sits elsewhere:
   without it the bcreg filing area wrote "no part retries" a lost filer
   message that the future-effective job, in another area, sends again.
   Its outside topics come with their hazards too: shown business-pay's
   opening line alone, the payments area wrote it had no duplicate guard.
   The section is part of the upper's member signature, so a changed
   relation or outside brief makes the area brief stale.

Why no word targets (docs/evaluations/2026-10-defines-uses/, round 8): with
the 60-120 word condensation and the 250-500 word brief, the leaf briefs
stated 56 of 104 answer claims the cited sources state 75 of; the brief
prompt told the writer the condensations "stay available" when nothing
below a brief is shown, and to leave out lists and keep three hazards.

**Lookups (a tree setting, off by default).** With "Look into other topics"
on, a leaf brief's writer may read the rest of the tree before it writes
(`summarize/lookup.py`). What it sees is what exists at that moment of a
build - condense has run over every section, no brief is written yet - laid
out as files: `source/<source>/<path>` (the text) and
`condensed/<source>/<path>.md` (its condensations), behind read-only `Grep`,
`Glob` and `Read` answered from the database, at most 15 calls. Every provider
runs the same tool loop (`llm/tools.py`). The writer lists each connection
its topic shows, finds the other side, and ends with `## Used`: the files a
statement came from. Those, less the topic's own members and at most 12, are
stored in `brief_uses` with each file's content signature; the `Used` and
`Lookups` sections are cut from the stored text, and any `source/` or
`condensed/` path that slipped into the text is rewritten to the repository
path an agent can open. These calls run with thinking on (budget 4,000):
without it the writer made 2-5 shallow lookups, with it 8-11. A brief that
comes back with no lookup at all is asked once more to look first (half the
leaf briefs of round 10 skipped them). A `Used` line may name a file by its
repository path or by the tools' path. They are the brief's
dependencies across branches: `propagate` judges a leaf whose used file
changed against that change, and a minor or major verdict marks the leaf and
its ancestors stale; a `none` verdict records the file's new signature, so it
is not judged again. Measured on the bcreg slice (2026-10-defines-uses, round
9): the writer's declarations held - no statement about another part came
from an undeclared file - and a brief that had described an endpoint from its
name stated the query it really runs.

**References are mechanical.** Member lists and links are rendered by code
from topic metadata, never written by the LLM: no tokens, no hallucinated
links. Briefs never contain routing ("for X see child Y").

**Provenance is data.** Each brief stores its model, prompt name and template
hash, token usage and the member signature it was written against
(`summarize/briefs.py`). A brief regenerates only when it is missing, its
members changed, or its prompt or model changed. A pinned brief is never
rewritten.

**Deterministic gates** run on every brief, with no LLM:

- *Faithfulness* (`summarize/faithfulness.py`): identifier-shaped tokens in
  the brief must appear in its source. Slash-joined prose (`CI/CD`, `and/or`)
  is not an identifier.
- *Shape* (`summarize/shape.py`): rejects a reply that is empty, that asks or
  addresses the caller, or that talks about the conversation instead of the
  material.
- *Copy* (`shape.copies`, upper briefs with two or more children): when more
  than **30%** of the brief's 6-word runs occur in one child's brief, the
  call is repeated once; if it still copies, the brief is stored flagged
  `copies-a-child`. It shows on Health and in `unusable-briefs` like the
  other flags, and a sync leaves it until the topic's members, prompt or
  model change. Level-1 briefs share under 10% with any one
  child.

## Why this shape

From six rounds and ~90 recorded runs over six sample clusters (coherent
business logic, near-duplicate translations, build configs, 28 HTML
templates, a tight group of DTOs, a low-coherence grab-bag). Prototype code:
[`research/prototype/summarize_experiments.py`](research/prototype/summarize_experiments.py).

- **Genericity.** The adaptive prompt found layers in code, languages in
  translations and build systems in configs without naming any of them. A
  prompt that listed code layers broke non-code clusters.
- **Incrementality.** Condensations keyed by hash are computed once ever.
- **Cost.** At the time: cheap-model condense ≈ $0.015 per section, once;
  brief ≈ $0.03–0.15 per topic over already-shrunk input. Briefing raw input
  with the stronger model cost $0.14–0.42.
- **Gotchas surface better in two layers.** Per-section attention found more
  real hazards (9 vs 5 on one cluster) than one pass over the raw cluster,
  and the brief curates the over-collection. Examples caught: a
  non-transactional batch insert, a silent no-op delete, an empty keyword
  becoming a match-all regex.
- **Composition upward works.** Briefing six briefs produced a good parent
  with per-child discriminative lines.
- **Faithfulness is checkable mechanically.** A token-cap on condensation
  made the model invent a value ("512 chars") that the brief then repeated;
  removing the cap removed that class of fabrication.

The 2026-10 prompts replace the adaptive ones after measurement on a large
unknown corpus (`evaluations/2026-10-condense-prompts/`,
`evaluations/2026-10-brief-prompts/`): scored against the verified facts of
an agent evaluation, the adaptive brief was a file catalog, opened by
describing its input in 71% of leaves, and its upper briefs ran longer than
their children. The leaf prompt keeps more of the facts in two thirds of the
words; the upper prompt keeps about 1.6 times as many at the same length.

## Rejected (do not retry blindly)

- Size budgets in prompts: a hard one is ignored (~2x overruns), and a
  range ("aim for 60 to 120 words") holds roughly but costs the facts that
  hard questions need (round 8 of 2026-10-defines-uses). The prompts now
  have none.
- Hard token caps on condensation: they starve dense sections and cause
  fabrication.
- LLM-written reference lists.
- Code-specific vocabulary in any prompt.
- Sibling-aware "not here, see X" briefs: a circular dependency between
  siblings that only exists at regeneration time.
- "Answers questions like:" sections: noise.
- Refine and outline pipelines: 2× cost, no visible win over one adaptive
  call.

## Insights

Optional and off by default (`insights` on the tree, role `insights` on a
model). A strong model reviews a big area of the tree and its findings are
written into the area's brief, so an agent reading the brief finds the rules no
single section states, the siblings that differ and the wrong statements of the
cheaper brief corrected, with their evidence.

**Which topics.** A topic is reviewed when the characters of brief below it
that no pass has covered reach the tree's `insights_threshold` (default
500 000). The root is reviewed when it never was, or when something under it
is unreviewed. A reviewed topic whose brief is written again (a pass on one of
its parts briefs it again from the extended brief) is reviewed again, so its
own findings are not lost; the dry run counts that pass too. A second `settle`
with nothing changed runs no pass. The count
is derived from stored briefs and the `insights_passes` rows: a brief is
covered when it was written no later than a pass on its topic or on one
between it and the topic, so a pass takes its subtree out of the count above
and a brief rewritten afterwards counts again (`summarize/insights.py`). The
dry run states the passes and the cost from the measured $2.43 a review plus
$0.39 to extend the brief.

**A pass** (`summarize/review.py`) is two calls on the model with the role
`insights`, with no fallback to another text model: with none, no pass runs
and the job's result and the dry run say so. The review gets the area's brief
and a one-line index of its topics in the prompt (prompt role
`insights-review`, the measured recipe in `dev/research/insights-recipe.md`),
and read-only lookups over the area and nothing else: the briefs of the
topics under it (`brief/...`), their condensations and their source, with a cap
of 60 calls. It answers with at most 15 findings: statement, angle, why it
matters, evidence (file, lines, version), where the briefs state it or should,
confidence, and the hypotheses it checked and dropped. They are stored
(`insights_findings`, one `insights_passes` row per pass). The extend call
(prompt role `insights-extend`, no tools) rewrites the brief in place with the
findings put where their reader needs them. The cheaper brief stays as the
previous version (`brief_versions`, reason `insights`, the pass that replaced
it); the one the latest run of passes extended is never pushed out of the
kept versions. The extended brief keeps the cheaper brief's provenance, so a
later `brief-upper` leaves it alone until the topic's parts change.

A review that does not finish (the cap, an answer that is not findings) stores
nothing and the job's result lists why under `failed`; the topic is due again.
A provider error fails the job, naming the topic (`review of topic <id>`) in
the stage `review` of a settle, as in a sync;
the topic's page then shows the failed run, as it does for a review that
did not finish. A pinned brief is never
overwritten: its findings are stored and the pass is marked skipped. The
parent of a reviewed topic is clustered (on a first build) or briefed again (on
`settle`) from the extended brief.

**Where it runs.** `settle` runs the passes that are due even when nothing
drifted (no churn, no misfit): it reads the tree's saved settings, runs the
passes `insights.passes_for` names bottom-up with the root last, and briefs
again only the parents of the topics it extended, never a re-cluster. This is
the "Review now" action on the tree's settings line and `POST /jobs
{"op":"settle"}`; its result is `settled: false` with `insights` counts. With
insights off, no model with the role, or nothing due, an untripped `settle`
is `settled: false` and calls no model. A tripped (or forced) `settle` reviews
inside its rebuild, as below. Each finding's evidence items carry `version`:
the synced version of the file's sections when the review read them (the
reviewer's own is dropped; a file outside the area has none), and the topic
page links that version; findings stored before this show today's link and
"version not recorded".

In `build-tree`, right after the briefs of a level are
written and before the level above is clustered, and after the root is
collected; so `maintain` and `settle` run it.

`sync-tree` runs it too, inside its upper-level briefing (`brief-upper`, and
again in `adopt`): after each level's briefs, before the level above is
written. A reviewed topic whose brief the sync rewrote with the cheaper model
gets a full new pass in that sync, so its parent is written from the extended
brief; stored findings are never re-applied to the new brief. A topic whose
count first reaches the threshold on a sync gets its first pass, and a topic
below the threshold gets none: the root has no rule of its own on a sync, it is
reviewed when its count reaches the threshold or its brief was rewritten. A
sync that leaves every count under the threshold and rewrites no reviewed
brief calls no model. A pinned topic's brief is left alone and the new
findings are stored, not applied. Each pass adds a version to the topic's
history (the kept five, besides the cheaper brief the latest run of passes
replaced, so a run of passes never pushes out the cheaper brief a reader
compares against; an earlier run's cheaper brief ages out like any version).
The job result counts `reviews`, `extends` and `findings` (`insights` for a
sync).

## Propagation

`summarize/propagate.py`, run by `sync-tree` before any re-brief. Whether a
change climbs is decided by a **relevance judge**, never by a similarity
metric or by comparing regenerated texts: regeneration rewords everything, so
two briefs of identical input already look different
([`update-threshold.ipynb`](research/prototype/update-threshold.ipynb), six
rounds). Generated text is only ever compared against deterministic inputs.

For each leaf whose member set changed, the judge gets the leaf's current
condensations and its **stored** brief and answers `none`, `minor` or
`major`: does anything the brief states become wrong, incomplete or worth
updating? Three votes, median verdict; a reply whose first word is not a
verdict is re-asked once, then abstains (a guessed `none` would silently
suppress a real climb).

- `none`: nothing is marked; the leaf is recorded as judged at that member set.
- `minor` / `major`: every ancestor up to `D_MAX` (5) levels is marked stale,
  and the tree's drift grows by 1 / 2. Drift feeds the settle trigger
  ([clustering.md](clustering.md#settle)).

Propagate must run before the leaf is re-briefed: re-briefing first rewrites
the stored brief with the new member signature, so nothing is judged and no
ancestor is ever marked. Every verdict is a row in `update_log`.
