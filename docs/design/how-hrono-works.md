# How hrono works

hrono is a self-maintaining abstraction layer over messy enterprise knowledge. It turns heterogeneous sources into a map of topics that an AI agent can recall from or explore, and it absorbs changes incrementally instead of being rebuilt — settled knowledge doesn't move.

This document describes the solution, precisely enough to replicate it.

## From sources to sections and passages

### Sources

A **source** is a place where knowledge already lives, declared in `sources.toml` as a URL plus an auth method (`none`, `ssh`, or `env:VAR` for a token in an environment variable). The only source type today is a git repository; the rest of the system never cares where text came from, only that it arrived with an address and a version.

Reading a git source means cloning it (or pulling, if already cloned) into a local cache at `.hrono/cache/git/<host>/<org>/<repo>/`. The **version** of everything read from that checkout is the commit hash — an opaque string compared only for equality, so future source types can put anything version-shaped there (a Confluence page revision, a Contentful entry version).

### Filtering

A filter decides which files are candidates at all, applying three rules in order:

1. **A glob-pattern exclude list** (Python `Path.full_match` semantics: `*` within a path segment, `**` across segments), covering vendored and generated directories (`.git`, `node_modules`, `dist`, `build`, `target`, `vendor`, `__pycache__`, `.venv`, `.tox`, `coverage`, `.next`, `.cache`), machine-generated lockfiles (`package-lock.json`, `yarn.lock`, `pnpm-lock.yaml`, `uv.lock`, `poetry.lock`, `Cargo.lock`, `Gemfile.lock`, `composer.lock`), binary/media/archive/compiled extensions, and office documents (`.pdf`, `.docx`, …) that need a dedicated extractor rather than raw text splitting.
2. **A size cap**: files over 2 MB are dropped — at that size they're generated bundles or data dumps, not knowledge.
3. **A null-byte sniff** for files no pattern covered: read the first few KB, drop the file if a `0x00` byte appears (the same binary-detection heuristic git uses).

### Structure-aware splitting

Files are never cut into arbitrary blocks. Splitting is two phases — build a structure tree, then pack it.

**Phase 1 — the structure tree.** Each file is parsed with tree-sitter, using a grammar chosen by extension: python, java, kotlin, javascript (`.js`/`.jsx`), typescript, tsx, go, ruby, rust, c (`.c`/`.h`), cpp, csharp, php, bash, sql, groovy (`.gradle`/`.groovy`), markdown (`.md`/`.mdx`), html, json, yaml (`.yaml`/`.yml`), toml, xml. The parse yields the file's real structure — functions, classes, headings, config blocks — as a tree of byte spans.

Where structure runs out, the tree keeps growing **synthetically**: any span the parser gave no children (or a whole file with no grammar) is subdivided by a delimiter cascade, applied in order inside spans still bigger than the passage budget: blank line (`"\n\n"`) → line (`"\n"`) → sentence (`". "`) → comma (`","`) → word (`" "`). A level that produces fewer than two pieces is skipped in favor of the next. The delimiters only grow the tree — all size decisions live in the packer, so parsed and synthetic structure are handled by one mechanism.

**Phase 2 — the packer.** One greedy packer walks the tree and groups consecutive sibling nodes into spans under a byte budget:

- Consecutive siblings accumulate into the current span while the next sibling still fits the budget.
- A node bigger than the budget on its own is descended into (its children become the siblings to pack).
- A span with no delimiters at all (one giant unbroken token) is byte-chopped at the budget, each piece marked as a raw part (`part k of n`).
- Spans smaller than 64 bytes merge into the preceding span (a tiny first span merges forward), so no meaningless fragment stands alone.

The packer runs **twice over the same tree**, producing the two units:

- A **section** — the organizing unit: what gets clustered into topics and what an exploring agent reads. Filled greedily to a per-category budget: an extension → category table assigns every file to `code`, `docs`, or `data`, with budgets 10 KB / 10 KB / 2 KB respectively (each the log-scale Kneedle knee of file-size distributions measured over four large repos).
- A **passage** — the quoting unit: what recall injects into an agent's context. Budget 800 bytes (≈ 200 tokens), packed *inside* each section's node group. A sibling group is flushed by the **budget and nothing else**, so a passage is filled to roughly the ≈ 200-token unit the budget describes. Where a span has no structure left to pack, the byte-chop cuts at the nearest whitespace edge (within 10% of the budget) so a part never ends mid-token.

  > **Corrected 2026-09-15 (PO, at #097's close).** This bullet previously read "a sibling group is flushed once it reaches 100 bytes, so a decent structural unit (a method, a config block) stands alone instead of being glued to unrelated neighbors". That rule is not in the settled recipe: `prototype/structure-split.ipynb:pack_node` flushes only on `nxt_start - group_start > budget`, and the sole small-span rule there is `merge_tiny`'s 64-byte `MIN_PARA` crumb merge (which production keeps). The prose was implemented literally as a `MIN_GROUP = 100` flush and capped passages at about an eighth of their budget: measured on three real repositories, 786 passages with a **152-byte median and 68% under 200 bytes**, so a recall hit was a truncated sentence rather than a quotable unit. Removing the flush alone moved the same corpus to a **585-byte median, 15% under 200 bytes, zero over budget**, with section packing and byte-identical reassembly unchanged. Do not reinstate a group-size flush from this paragraph's old wording.

Because the passage pack runs inside each section's node group, passage boundaries nest inside section boundaries by construction: every section is a sequence of whole passages and reassembles from them byte-identically — one ground truth, two zoom levels.

### Identity: address, hash, structure path

Every section and passage carries three identities, each answering a different question.

**The address** says *where it came from* — a URI assembled from four stored parts (source type, instance, file path, version):

```
<source_type>://<instance>/<path>@<version>
git://github.com/acme/webphone/src/ContactService.java@1a2b3c4d…
```

Addresses are **fragment-free**: a piece's position (byte range, ordering) is data attached to it, not part of its identity. The four parts are the stored source of truth; the URI is rendered from them, so the two can't drift.

**The content hash** says *what it is*: the SHA-256 of the piece's raw bytes, taken from the original file's byte range. Pieces with identical bytes share a hash regardless of how many addresses point at them — bodies are stored once, embedded once. Address and hash split the same way git splits refs from blobs: provenance is the key you navigate by, content is the key you deduplicate by.

**The structure path** says *where it sits inside its file*: the full chain of structure nodes from the file root to every node packed into the piece (usually one; several when small siblings share a passage). A segment is `{type, name?, idx}` — the tree-sitter node type, a best-effort display name (a declaration's `name` field, a JSON key, a markdown heading, an XML tag), and an index disambiguating same-type-same-name siblings, taken from the node's true sibling list in the AST. Synthetic segments are typed `~<level>` (e.g. `~line`); byte-chop pieces end in a `raw` segment with `part`/`of`. Structure paths are unique per file by construction.

For humans and prompts, a structure path renders as a compact `sp:` URI — percent-encoded names, `.type` for unnamed segments, `[i]` only when the index is above zero:

```
sp:/ContactService/.class_body/getByUser
```

The one-line header above every recalled passage is simply its address followed by its `sp:` paths.

## From sections to topics: building the map

The map is a tree of **topics**. A topic is a group of related sections plus a **brief** — an LLM-written summary of what the group is. Bottom-level topics hold sections; topics above hold other topics, up to a single root whose brief is the overview of everything hrono knows.

### Embedding

Every unique content hash is embedded exactly once: vectors are keyed `(hash, model)`, so re-runs only embed new hashes, duplicates are free, and a model swap is a config edit followed by automatic re-embedding. Embedding runs locally via `sentence-transformers` with `Qwen/Qwen3-Embedding-0.6B` (multilingual + code, 32k-token input, 1024 dims) — enterprise content shouldn't leave the machine, and local embedding is cheap.

A section's clustering vector blends *what it says* with *where it lives*: the file path is embedded with the same model and concatenated with the content vector as

```
[ √(1−α) · content_vec ; √α · path_vec ],  α = 0.5
```

so the dot product of two combined vectors is exactly `(1−α)·content_similarity + α·path_similarity` — path-aware similarity that works unchanged with standard UMAP/ANN tooling.

### Forming topics

Sections become topics through a fixed three-step pipeline:

1. **UMAP** on the combined vectors, to 25 dimensions, `metric="cosine"`, fixed seed — the nonlinear reduction creates the density contrast clustering needs (raw high-dimensional vectors suffer distance concentration).
2. **HDBSCAN** on the reduced vectors: `min_cluster_size=5`, `metric="euclidean"`, `cluster_selection_method="leaf"` — leaf selection yields many small clusters, the "small parents" shape a summarization tree needs.
3. **Attachment.** HDBSCAN leaves the most distinctive sections unclustered ("noise"). Every such section attaches to the topic of its most-similar clustered section, by dot product in the **original combined space** — deterministic and independent of the reducer. Each member keeps an `assigned` flag (density core vs attachment) and its attachment similarity.

The result is full coverage — every section belongs to exactly one topic — in small, coherent, summarizable groups.

### Briefing

A topic's brief is produced in two stages:

- **Condense — one pass per section (Haiku).** Each section is condensed to its essential information: length follows content density (boilerplate collapses to a line; dense logic keeps what it needs), identifiers and values copied verbatim, never inferred, plus `GOTCHA:` lines for anything non-obvious that could hurt a newcomer. Condensations are cached by the section's content hash — an unchanged section is never condensed twice, so rebuilding a topic costs one brief-writing call.
- **Brief — one pass per topic (Sonnet).** The prompt writes what the group *is* from the condensations: it finds the natural groupings actually present (never imposes a structure — it must work for code, configs, translations, and prose alike), names concrete things, compresses near-identical sections into pattern-plus-variations, and ends with a **Caution** section aggregating the condensation-stage gotchas (omitted when there's nothing to warn about).

**References are mechanical**: member lists and links are rendered by code from topic metadata, never written by the LLM — no tokens spent, no hallucinated links.

Provenance is data: every brief is stored with its model, cost, and the exact prompt that produced it. A brief is reused across rebuilds while its topic's member set is unchanged (keyed by a member-set signature); changing a prompt automatically invalidates every brief the old prompt wrote.

### Levels above: topics of topics

Upper levels reuse the same machinery on smaller inputs. The briefs of a level are embedded (content only — topics have no file path to blend) and clustered with the same UMAP → HDBSCAN → attachment pipeline, with dimensions and `min_cluster_size` scaled to the point count (e.g. UMAP-10, `min_cluster_size=3` at tens of topics). This repeats level by level until one root remains.

Upper-level briefs use a **pure-abstraction** prompt (Sonnet): the model is never told it's inside a tree — no node/child/subtree vocabulary, children rendered as plain titled texts — and must synthesize *across* them: the emergent rules and shared conventions that only exist when the children are seen together, with structure drawn from the material's own concepts and a ~500-word target. Briefs never contain routing ("for X see child Y") — references stay mechanical; the LLM only abstracts. The root brief uses the same prompt over the top level.

## Access: recall and explore

There are two doors into what hrono knows. **Recall** is the automatic one: a question comes in, hrono injects the passages that answer it, with provenance. **Explore** is the deliberate one: the agent walks the map itself. Recall is tuned strict on purpose — injection costs tokens on every request — and when it finds nothing confident it says so and hands over to explore: misses fail safe to traversal, never to silence.

### Recall

Recall runs two retrieval legs over the passage index and fuses them:

1. **The vector leg** ranks passages by the same path-blended similarity used for clustering: `(1−α)·sim(question, content) + α·sim(question, path)`, α = 0.5 — the path term catches what bodies don't say (a translation file's language, a license file's nature). Scores are converted to z-scores against the query's own full score distribution, and a passage qualifies at **z ≥ 3.5**.
2. **The keyword leg** ranks passages by BM25 over an FTS5 full-text index of path + body (query terms OR-ed), z-scored over its matched set. A keyword hit **never qualifies alone** — its background distribution is stopword matches, so meaningless text can score high; it qualifies only at **z ≥ 6.0 with vector support z ≥ 3.0**.

The qualified sets are unioned and ranked by **weighted reciprocal rank fusion, 70/30 vector/keyword** (score = Σ weight/(60 + rank)), capped at **10** passages. There is no gap-based cutoff — the z-floors alone decide. An empty union injects nothing and returns one line: *no confident matches — explore the map.*

Each injected hit is its one-line header — address plus `sp:` structure paths — followed by the full passage body. Structure paths are deliberately neither embedded nor FTS-indexed: the names they contain already appear in bodies; the rest is noise.

**Briefs are recallable too.** Every brief is markdown, so it goes through the same splitter into the same passage store under `source_type='node'`, addressed as

```
node://hrono/nodes/<id>/<title-slug>@<member-signature>
```

with the topic's title slug in the path (so the path-blend has semantics to match) and the member-set signature as the opaque version. Brief passages are embedded and FTS-indexed identically, and recall runs over the union of source and brief passages: architectural questions surface brief passages (which state cross-cutting facts no single section contains), detail questions surface source passages, and each hit is tagged as summary or source.

### Explore

The map an agent explores is not the stored tree — it's an **export** of it. The stored map keeps whatever depth the data naturally produced (many levels of small topics — the shape briefing wants), and lives in the database. From it, hrono renders a separate agent-facing tree into the **file system**: plain files an agent walks with the tools it already has — list a directory, read a brief, descend — no query API in the loop.

The exported tree is deliberately **flatter** than the stored one: the fixed cost of a traversal hop dwarfs the cost of showing more siblings, so wide and shallow beats narrow and deep. The export collapses stored levels into at most **3–4 agent-facing levels** even at million-section scale, with branching **narrow at the root and wide at the leaves** (a wrong turn at the root wastes the whole traversal; a wrong pick among many leaves costs almost nothing) — e.g. a 20/100/500 three-level shape.

Descending it, the root brief orients, each level's briefs say what lives below, and the Caution sections warn about hazards before any source is opened. At the bottom the agent reads whole sections — reassembled byte-identically from passages — with full provenance to reach the original file when even that isn't enough. Child listings are mechanical, rendered from the stored tree at export time, so navigation never depends on an LLM having written a link correctly.

How recall is served to agents (client/server split, protocol) is deliberately not fixed yet; explore needs no serving layer at all — it's files.

## Lifecycle: absorbing change

Updates never re-run the build pipeline. A change batch touches only what changed; everything else is guaranteed to stay put. The rules below govern the stored map; the agent-facing export re-renders from it.

### Detecting change

Syncing a source produces a new version; the changed files re-split, and each file's new `(structure path, content hash)` pairs are diffed against the stored ones. An unchanged hash triggers nothing, deterministically — change detection is mechanical, and noise is impossible on this path. Everything downstream is phrased as a diff: a modified section is old→new, a new file is empty→content, a removal is content→empty.

### Absorbing

Each changed section is handled by one rule set:

- **Deleted** → removed from its topic; the topic's brief is marked stale. A topic dropping below 2 members dissolves; its remaining member re-enters placement.
- **New or changed** → embed, then take the best blended similarity against all clustered sections: **≥ TAU (0.70)** → join that topic, mark its brief stale; **< TAU** → into the incubator.
- **Moved or renamed (same hash, new path)** → handled in place, never as delete-plus-add: the content vector is reused, the path vector recomputed, and the new combined vector re-checked against the section's current topic — still ≥ TAU → stays (metadata-only update); < TAU → a real reorganization signal, re-placed via the rule above.

Every placement is a dot product against stored state — deterministic, no clustering algorithm in the loop.

### The incubator

Sections too novel to join any topic (< TAU) wait in the **incubator** — parked, queryable as pending, in no topic yet. When the incubator reaches `min_cluster_size` (5), a **scoped mini-pipeline** runs over the pool alone: the same UMAP → HDBSCAN(leaf) → attachment recipe, on just those sections, touching nothing outside the set. Only its density-core clusters are emitted as new topics — stragglers are never married to each other. Residual pool noise is then force-assigned to the most similar existing topic, ignoring TAU: TAU is the "clearly needs no new topic" bar, not an admission gate, and a section outside the map is unfindable — worse than one alien member in a brief. Force-placed sections carry a `forced` flag plus their placement similarity, and the misfit monitor re-checks them preferentially — so a pioneer (the first section of a genuinely new topic, placed wrong) migrates automatically once its real siblings arrive. A section pending longer than N batches while the pool stays too small is force-assigned the same way — nothing waits forever.

### Propagation: how far a change climbs

Whether a change climbs the map is decided by a **relevance judge**, never by a similarity metric and never by comparing regenerated texts — regeneration rewords everything, so generated artifacts are only ever compared against deterministic inputs.

The judge is one universal question, asked per hop: *here is the current stored brief of this area; here is the change beneath it (a unified diff of raw source — a new file is pure additions, a removal pure deletions); does anything the brief states become wrong, incomplete, or worth updating?* The answer is `none` / `minor` / `major`. Both inputs are deterministic artifacts — the stored brief and the exact diff — so no source change means no judge call, and noise is structurally zero.

Mechanics:

- Judging is **batched per topic**: all of a topic's diffs go into one call (Haiku), so coordinated changes are seen together. Each verdict is best-of-3 majority; ties resolve to the higher severity.
- **`none`** → nothing regenerates; the existing condensation is aliased to the new content hash.
- **`minor`** → the topic's brief regenerates (changed sections re-condense; unchanged condensations come from cache) and the parent's `drift` increases by 1.
- **`major`** → the brief regenerates and the climb continues: the same diff is judged against the parent's stored brief, and so on toward the root. A change climbs exactly as far as it stays relevant to what's stated, and dies at the hop where abstraction absorbs it.
- **`drift`** accumulates skipped minors per parent; at **D_MAX (5)** the parent regenerates anyway and drift resets — many small changes add up to a refresh.
- Membership changes (a section joining or leaving a topic) bypass all of this: the member-set signature invalidates the brief unconditionally.
- Every verdict and skip/propagate decision is a row in an update log, so staleness is always inspectable.

### Monitoring: misfit

After every batch, hrono measures how well sections still sit where they are. All vectors are unit-length; a topic's centroid is the renormalized mean of its members. A section is a **misfit** iff its similarity to some other topic's centroid exceeds the similarity to its own. The misfit rate — misfits over total, tracked globally and per topic — is deterministic, cheap (plain dot products), and continuous. Its baseline is nonzero by nature (clusters aren't spheres; edge members lean), so thresholds are relative to the measured post-build baseline, never absolute. At scale, it's computed incrementally: only members of touched topics plus a random sample per batch.

### Repairs

Triggered by the monitor or by caps, each touching one topic only:

- **Migrate**: a section the monitor flags as a misfit moves to the topic whose centroid it is now closest to; both briefs are marked stale. This is the only misfit repair — there is no whole-topic re-clustering below a global settle.
- **Split**: a topic over **MAX_CAP (30 members)** — the edge of one faithful brief, derived from the summarization input budget — runs the scoped mini-pipeline over its members and becomes 2+ topics.
- **Dissolve**: below 2 members → members re-enter placement.

Only the affected briefs regenerate.

### Settling

Incremental life degrades the map's structure in ways no single-section repair can fix, so the map periodically **settles**: a full warm rebuild — UMAP re-fit with `init` = the stored coordinates, so the new layout extends the old instead of reshuffling it — followed by a **diff against current memberships**; only topics whose membership actually changed get re-briefed.

The trigger is an **accumulated churn counter**: every migration, every forced placement, and every dissolve since the last settle adds 1. When the counter reaches **~10% of all sections**, the map settles and the counter resets. The counter, not the misfit rate, is the primary trigger because migrations mask degradation — each one restores a healthy-looking misfit rate while the structure keeps decaying underneath; the counter remembers every repair the incremental path had to make. The threshold has a principled reading: a warm rebuild itself reshuffles ~10–15% of memberships, so hrono settles once it has already paid a rebuild's worth of churn in small pieces.

A backstop remains on the instantaneous signal: global misfit rate ≥ ~2× the post-build baseline forces a settle regardless of the counter (the case where repairs can't keep up). Settling is maintenance, not an update path; the normal life of the map is absorb → incubate → repair.

### Invariants

1. An update never moves a section whose content didn't change.
2. Every placement outside build/settle is deterministic given the stored state.
3. Every section is in exactly one topic, or explicitly in the incubator.
4. Every membership change marks the affected brief stale; briefs regenerate from stale flags only, never wholesale.
5. Embeddings and condensations are content-addressed; nothing is ever computed twice for the same bytes.
