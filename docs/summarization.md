# Summarization

How hrono writes briefs and decides when a change climbs the tree. Code:
`src/hrono/summarize/`; the default prompts are seeded from
`src/hrono/registry/collections/prompts.py` and editable per role (`condense`,
`brief`, `brief-upper`, `judge`).

## The recipe

Two layers, gotcha-aware, content-addressed.

1. **Condense, per section** (`summarize/condense.py`, cheap model). Each
   section opens with one sentence on what it is for, in the system's own
   terms (or that it is a test, config, migration or document, and what it
   serves). Then what comes in and goes out, the main flow, and every
   decision with the function, constant, list or field that holds it.
   Mechanism comes after purpose; boilerplate collapses to a line. 60 to 120
   words, up to 250 for dense logic. Identifiers and values are copied
   verbatim, and `GOTCHA:` lines flag only what the code shows (a swallowed
   exception, a partial update), never a guess. Results are cached by
   content hash, so an unchanged section is never condensed twice. Up to 8
   sections share one call (`summarize/packed.py`), because a `claude-code`
   call carries a large fixed overhead; a section whose packed result is
   missing is retried alone.
2. **Brief, per leaf topic** (`summarize/brief.py`, stronger model). Over the
   condensations, what a reader needs to understand the part's role and find
   where to change it, in order: what it does and whom it hands work to; its
   contract (what comes in and goes out, with the message or record shapes);
   its decisions one line each with where they live, including every state
   change and every check that refuses a caller; at most three hazards that
   lose or corrupt work; two to four sources to open first. Setup,
   configuration, field lists, health checks and test plumbing are left to
   the condensations below. 250 to 500 words, up to 800 for several jobs.
   It writes about the part, never about its input ("this group").
3. **Brief, per upper topic** (`summarize/brief_upper.py`, stronger model).
   Over the child briefs, with no condense stage: what the area does, then
   its end-to-end flows as numbered steps naming the part, the function and
   the state at each step, one line per part not in a flow, and at most
   three hazards from how the parts interact. 300 to 600 words however many
   children there are. The model is never told it is in a tree.

**References are mechanical.** Member lists and links are rendered by code
from topic metadata, never written by the LLM: no tokens, no hallucinated
links. Briefs never contain routing ("for X see child Y").

**Provenance is data.** Each brief stores its model, prompt name and template
hash, token usage and the member signature it was written against
(`summarize/briefs.py`). A brief regenerates only when it is missing, its
members changed, or its prompt or model changed. A pinned brief is never
rewritten.

**Two deterministic gates** run on every brief, with no LLM:

- *Faithfulness* (`summarize/faithfulness.py`): identifier-shaped tokens in
  the brief must appear in its source. Slash-joined prose (`CI/CD`, `and/or`)
  is not an identifier.
- *Shape* (`summarize/shape.py`): rejects a reply that is empty, that asks or
  addresses the caller, or that talks about the conversation instead of the
  material.

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

- Hard size budgets in prompts: ignored (~2× overruns). A range with an
  escape for dense content ("aim for 60 to 120 words; dense logic may use
  up to 250") holds roughly, and a tight one costs facts.
- Hard token caps on condensation: they starve dense sections and cause
  fabrication.
- LLM-written reference lists.
- Code-specific vocabulary in any prompt.
- Sibling-aware "not here, see X" briefs: a circular dependency between
  siblings that only exists at regeneration time.
- "Answers questions like:" sections: noise.
- Refine and outline pipelines: 2× cost, no visible win over one adaptive
  call.

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
