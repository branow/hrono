# Glossary

The words hrono uses, and the ones it deliberately does not. Settled from
`how-hrono-works.md` and the summarization experiments; this file is the copy a
clone can actually read.

Several of these were renamed during development and the old names are still
findable in early design notes. Where that happened the superseded word is
listed, so a search for it lands here rather than on a wrong assumption.

## The shape of what hrono builds

**source** — a place hrono reads: a git repository first, later a Confluence or
Notion space. Registering one pulls nothing; `sync` does.

**section** — the organizing unit. Around 10 KB of one file, filled greedily to
a per-category budget (code 10 KB, docs 10 KB, data 2 KB). A section is what
gets clustered, and what an agent reads when it explores.
*Superseded name: **chunk**. Used throughout `design-sketch-v1.md`; do not
reintroduce it.*

**passage** — around 800 B, the unit **recall** injects into a prompt. A section
reassembles byte-identically from its passages. Passages exist for retrieval;
sections exist for structure. They are not interchangeable.

**condensation** — what the first LLM pass writes about one section: its
essential information, identifiers copied verbatim, plus `GOTCHA:` lines for
anything non-obvious that could hurt a newcomer. Cached by the section's content
hash, so an unchanged file is never condensed twice. This is the **map** half of
map-reduce.

**topic** — a group of related sections, or of other topics, plus a brief. The
node of the tree. Bottom-level topics hold sections; topics above hold topics.
*Internal name: **node**, which is what the database calls it and what a URL
carries. A user-facing surface says topic.*

**brief** — an LLM-written summary of what a topic is, written from its
sections' **condensations**, not from their raw text. This is the **reduce**
half. It states what the group is as a whole, surfaces the groupings actually
present rather than an imposed structure, and ends with a `Caution:` section
aggregating the gotchas. Reference lists are appended mechanically by code and
are never written by the model.

**tree** — topics all the way up to a single root, over a named set of sources.
One database can hold several.

## What happens to it

**sync** — bring a tree up to date after its sources changed. The incremental
verb: it touches only what moved.

**maintain** — build a tree that does not exist yet, end to end. The cold verb,
and the expensive one. It refuses a tree nobody registered (`default`
always exists).

**recall** — answer a question by injecting the passages that answer it, with
provenance. Strict on purpose: when nothing clears the confidence floor it says
so and hands over to explore rather than inject something plausible.

**explore** — the other door: an agent walks the tree itself, reading briefs to
decide where to go.

**job** / **run** — background work. One instruction, which may fan out into
pieces.

## Health and judgement

**stale** — a brief that no longer matches what its topic holds, because the
members changed, or the prompt did, or the model did.

**pin** — a hand edit the pipeline must not undo. Pinning is what makes a
correction survive the next run.

**parked** / **incubator** — a section that is ingested and embedded but in no
topic yet, because the placement rule declined it. It is on the map's waiting
list, not lost.

**misfit** — a section whose own topic's centre is not the nearest one. The
health signal repair and settle act on.

**forced** — a section placed by a rule rather than by a measurement, so it
carries no similarity score.

## Words we do not use

**cluster** — the algorithm's verb. The thing it produces is a **topic**.

**chunk** — superseded by **section**.

**node** — the database's and the URL's word for a topic. On screen it is always a topic.

**paragraph** — not a unit in hrono. Splitting is by structure and byte budget,
never by paragraph.
