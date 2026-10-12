# Architecture

hrono turns heterogeneous sources into a tree of topics that an AI agent can
recall from or explore, and it absorbs source changes incrementally instead of
rebuilding: settled knowledge does not move.

Pipeline: **sources → sections and passages → embeddings → topics → briefs →
tree**, served as **recall** (passages injected for a question) and **export**
(a folder of markdown an agent walks).

## Process model

One binary, `hrono` (`src/hrono/cli.py`). `hrono serve` (`src/hrono/server/`,
FastAPI) is the only process that touches the database: it owns the SQLite
file (single writer), all compute and all LLM calls. Every other subcommand is
a thin HTTP client (`src/hrono/client/http.py`), and so is the `/ui`
dashboard (`src/hrono/server/ui/`, server-rendered Jinja). Many people share
one server and one knowledge base. See [api.md](api.md).

- **Storage**: SQLite + `sqlite-vec` in one file (`src/hrono/db/`), with a
  forward-only migration runner (`db/migrations/`). At the target scale
  (~1M sections) every candidate database handles the load, so the choice is
  the one with no moving parts, and an update (section row, vector, parent
  pointer) stays one ACID transaction instead of a cross-store consistency
  problem. Default path `.hrono/hrono.db` (`--db` or `HRONO_DB`); source
  clones live beside it (`src/hrono/paths.py`).
- **Jobs**: config is data you PUT; work is a job you POST. A background
  worker thread (`src/hrono/jobs/worker.py`) runs one job at a time from the
  op registry (`jobs/ops.py`). A job whose heartbeat stops is re-queued, which
  is safe because the expensive stages are content-hash cached.
- **Registry** (`src/hrono/registry/`): five collections, `sources`,
  `connections`, `models`, `prompts` and `trees`, on one generic CRUD engine.
  A write is validated (reachability, auth, prompt placeholders) and a dry run
  reports its impact on each tree (`registry/impact.py`).
- **Secrets** (`src/hrono/crypto/`): Fernet under a master key from
  `--key-file` or `HRONO_MASTER_KEY`; only the key's fingerprint is stored.
  User tokens are stored as hashes (`src/hrono/auth/`). Roles: reader, writer,
  admin.
- **LLM providers** (`src/hrono/llm/`): `anthropic`, `openai` and compatible,
  and `claude-code` (the `claude` CLI, billed to a Claude subscription). Each
  role (`condense`, `brief`, `brief-upper`, `judge`) resolves to one model;
  first-run defaults are in `src/hrono/onboarding/defaults.py` (cheap model
  for condense and judge, stronger for briefs). Every call is a row in the
  usage ledger (`llm/ledger.py`), rolled up by `src/hrono/usage/`.

## Sources

`src/hrono/ingest/`. A source is a place knowledge already lives:

| Type | Reader |
|---|---|
| `git` | clone or fetch one repo (`git_syncer.py`) |
| `github-user`, `bitbucket-workspace` | discover an account's repos, then clone each (`discovery.py`) |
| `confluence`, `notion` | pull pages over the API and materialize them in the cache (`pages.py`) |

Every piece read carries a **version**: the commit hash, or the page's own
version. It is opaque and compared only for equality. The address scheme is
the resource's content model, never the access method: the same repo fetched
over SSH or HTTPS has one `git://host/org/repo` identity, otherwise one
section would get two identities and dedup would break.

**Filtering** (`ingest/filter.py`) applies, in order: the source's `only`
whitelist, its `exclude`, the baked ignore groups (`DEFAULT_IGNORE` in
`ingest/split/constants.py`: vendored trees, lockfiles, binary and media,
tabular data, generated code), then re-admission by `include` or
`include_generated`. Then a size cap (2 MB) and a null-byte sniff of the
first 8 KB. Symlinks and non-regular files are skipped.

## Sections and passages

`src/hrono/ingest/split/`. Files are never cut into arbitrary blocks.

1. **Structure tree.** tree-sitter parses the file with a grammar chosen by
   extension (`grammar.py`). Where structure runs out (a leaf span, or a
   file with no grammar), a delimiter cascade grows the tree synthetically:
   blank line → line → sentence → comma → word (`cascade.py`).
2. **Packer** (`pack.py`). One greedy packer groups consecutive siblings
   under a byte budget, descends into a node too big on its own, byte-chops a
   span with no delimiters (at a whitespace edge within 10% of the budget) and
   merges crumbs under 64 bytes into a neighbour. A group is flushed by the
   budget and nothing else.

The packer runs twice over the same tree:

- A **section** is the organizing unit: what is clustered and what an
  exploring agent reads. Budget by category (`constants.py`): code and docs
  10 KB, data 2 KB, each the log-scale knee of file-size distributions over
  four large repos.
- A **passage** is the quoting unit: what recall injects. Budget 800 bytes
  (~200 tokens), packed inside each section, so every section reassembles
  byte-identically from its passages.

A section that is mostly encoded data (runs of 400+ non-whitespace bytes over
half its length: base64 assets, minified bundles) is dropped
(`split/encoded.py`); condensing one wastes a call or exhausts it.

**Identity** (`ingest/identity.py`). Every section and passage has three:

- **Address**, where it came from: `<source_type>://<instance>/<path>@<version>`,
  rendered from four stored parts. Fragment-free: position is data, not
  identity.
- **Content hash**, what it is: SHA-256 of the raw bytes. Identical bytes are
  stored, embedded and condensed once, the way git splits refs from blobs.
- **Structure path**, where it sits in its file: segments `{type, name?, idx}`
  from the root to each packed node, rendered as `sp:/ContactService/.class_body/getByUser`.

A recalled passage's header is its address followed by its `sp:` paths.

## Topics and briefs

**Embedding** (`src/hrono/embed/`) runs in-process with
sentence-transformers. Vectors are keyed `(content hash, model)`, so re-runs
embed only new bytes and a model change re-embeds automatically. The default model is
`ibm-granite/granite-embedding-97m-multilingual-r2` (384 dims, reads up to 8k
tokens). A section's clustering vector blends what it is for with where it
lives: `[√0.6·text ; √0.4·folders]` (`cluster/blend.py`), where text is the
embedding of its condensation and folders weigh its leading path prefixes by
1/depth, so a dot product is `0.6·text_sim + 0.4·folder_sim`. Recall blends
content with the embedded path string instead (α = 0.5).

**Clustering** (`src/hrono/cluster/`): UMAP → HDBSCAN (leaf) → attach every
noise section to its nearest core member, so every section is in exactly one
topic. Leaf selection gives the small topics a summarization tree wants.
Upper levels cluster the briefs of the level below with the same pipeline,
scaled to the point count, until one root remains. Rules and constants:
[clustering.md](clustering.md).

**Briefing** (`src/hrono/summarize/`): each section is condensed once
(cheap model, cached by content hash), each leaf topic is briefed from its
condensations, and each upper topic from its children's briefs. References
are rendered by code, never by the LLM. Recipe: [summarization.md](summarization.md).

There is no per-section importance score. Importance is a relation between a
section and a question, not a property of the section, so a static score
chases the wrong thing. Redundancy is handled by structure instead: density
clustering collapses near-duplicates into one topic, condensation length
follows content density, and a brief compresses near-identical members into
a pattern plus variations.

**Manual edits** (`src/hrono/edits.py`, `src/hrono/pins.py`): an operator can
rewrite a brief, move a section or re-parent a topic. Every edit pins what it
changed, and the pipeline treats a pin as a hard constraint, so a manual fix
is never silently reverted by the next update.

## Recall

`src/hrono/recall/`. `POST /trees/{name}/recall` and `hrono recall` run over
the union of the tree's source passages and its brief passages. Briefs are
markdown, so they go through the same splitter into the same store under
`source_type='node'` (`recall/brief_passages.py`): architectural questions
surface briefs, detail questions surface sources.

In one sentence: if at least 90% of the question's content words occur in the
tree, return the 5 passages (up to 10) closest to it by cosine, one per file;
otherwise send the agent to the map.

- **Gate** (`gate.py`): a question's content words are its tokens of three
  letters or more that are not function words, matched by stem (less a plural
  or tense ending, at most 5 letters). When fewer than 90% of them
  occur in the tree's FTS index, the tree does not cover the question and
  recall returns no hits. Vocabulary separates on- from off-topic questions;
  similarity does not (every question has a nearest passage).
- **Ranking** (`similarity.py`): plain cosine of the question's embedding
  against each passage's content embedding, sources and briefs in one list.
- **Window** (`window.py`): the best passages in order, the first of each
  document (a file or a brief), up to the requested limit (cap 10). Never
  padded.

An empty result returns one line, *no confident matches - explore the map*:
misses fail safe to exploring, never to silence. The recipe replaced a
path-blended, z-scored one with fixed floors, which were calibrated on MiniLM
and cut most answers once the tree was embedded with granite
(`evaluations/2026-10-recall-queries/`).

## Explore: the export

`src/hrono/export/`. An agent explores a rendered copy of the tree, not the
stored one: plain markdown files it walks with the tools it already has
(`hrono tree export`, or a zip from `GET /trees/{name}/export.zip`).

The stored tree keeps whatever depth the data produced. The export collapses
it to a hop limit (`levels`, default 4: the hops from `root.md` down to the
sections a leaf names), always keeping the root and the leaf level
(`export/collapse.py`). The fixed cost of a hop dwarfs the cost of showing
more siblings ([research/hop-cost.md](research/hop-cost.md)), so wide and
shallow beats narrow and deep. Among the selections that fit, the one whose
widest page is smallest wins; a page budget of 40 entries keeps an index page
the size of one section.

The export is knowledge, not information: it holds briefs only and copies no
source. The reading agent already has the repositories, so a page points into
them. Each page is the stored brief (Caution section included) plus a listing
rendered by code (`export/render.py`), so navigation never depends on an LLM
writing a link correctly. An index page lists its children, each with a
one-sentence summary and, below the root, a `Sources:` line naming up to three
repo-relative files beneath it and how many more there are, as many as keep
the page within one section's size. A leaf ends with `## Sources`: each of its
files once, with the source name and the 7-character version. Export output is
deterministic.

## Lifecycle

Updates never re-run the build pipeline. Full rules:
[clustering.md](clustering.md) and [summarization.md](summarization.md#propagation).

- **`maintain`** (`tree/maintain.py`) builds a tree: sync → split → embed →
  condense → cluster → brief → build to root.
- **`sync-tree`** (`tree/sync_chain.py`) refreshes one: update → propagate →
  brief stale leaves → brief stale upper levels → monitor → repair → adopt new
  leaves. The order is load-bearing, so it is one op.
- **`update`** (`tree/update.py`) syncs, diffs files by content hash, re-splits
  only changed files, embeds and condenses only new bytes, and places changed
  sections against the pre-batch centroids. Untouched sections never move.
  Sections too novel for any topic are parked for the rest of the run; at its
  end they form new topics if there are enough of them, and the rest join
  their nearest topic, flagged `forced` for the monitor to re-check.
- **`propagate`** asks a judge whether a leaf's new content changes what its
  stored brief says; `minor` or `major` marks ancestor briefs stale and adds
  drift.
- **`monitor`** and **`repair`** measure misfits and split, migrate or
  dissolve one topic at a time.
- **`settle`** (`tree/settle.py`) is a warm full rebuild that applies only the
  membership diff. `sync-tree` reports when one is due; it runs only when an
  operator enqueues it (`POST /jobs` with `op: settle`).
- **The change journal** (`db/journal.py`) records every row a run inserts,
  updates or deletes in the tables that make up a tree, with the row as it
  was before, through triggers generated from the schema on every open. It is
  the run's history, what the run page shows it touched, and the way back:
  reverting a run (`POST /jobs/{id}/revert`) applies its entries in reverse.
  Run records, usage, users, configuration and the content-addressed caches
  are not journaled, so a revert keeps what was spent and syncing again
  reuses what was computed.

Invariants:

1. An update never moves a section whose content did not change.
2. Every placement outside build and settle is deterministic given the stored
   state.
3. Every section is in exactly one topic once a run ends.
4. Every membership change marks the affected brief stale; briefs regenerate
   from staleness only.
5. Embeddings and condensations are content-addressed; nothing is computed
   twice for the same bytes.
6. A pinned entity is never changed by the pipeline.
