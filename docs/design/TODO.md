# hrono — TODO

Deliberately deferred work: things we know we'll need but are skipping for now to keep the research prototype moving.

## Source scope: discovery, not just enumeration
Right now `hrono.toml` requires listing every git repo by URL individually (see `prototype/hrono.toml`). Need a higher-level source that points at a whole account/org and discovers repos via API instead:
- **workspace/org as a source** — e.g. a Bitbucket workspace or GitHub org — hrono lists all repos in it itself rather than the user enumerating them one by one.
- Same idea applies to a GitHub account/org generally: point at the account, discover repos through the GitHub API, build the tree from whatever comes back.
- Open question: how new/removed repos in a workspace get picked up on subsequent runs (full re-discovery each time vs. some cached repo list).

## Other source types (beyond git)
Design already anticipates Contentful and Confluence (see `context.md`, `design-sketch-v1.md` — URI scheme has examples for both). Priority order:
1. **Confluence** — most important, unstructured docs.
2. **Contentful** — most important, structured CMS content.
3. **LaunchDarkly** — simplest of the three (flags + configs), lower priority.

Each needs its own resource-config shape in `hrono.toml` (auth, instance/space identifiers) and its own chunk-boundary rules in `chunking.toml`/`filter.toml`, same pattern as git today.

**Invariant to preserve when adding any source type or fetch mechanism** (see `design-sketch-v1.md`'s URI section and `chunk_uri` in `research.ipynb`): the URI scheme is the resource's content model, never the access/transport mechanism. If a git-hosted repo ever gets a second fetch path (e.g. reading a single file over a web API instead of full-cloning), that path must still emit `git://host/org/repo/...`, not `web://...` — otherwise the same chunk gets two identities depending on how it happened to be fetched, silently breaking dedup and the parent-pointer update mechanism.

## Importance modeling (research question, parked)
Not all chunks deserve equal summary detail: 100 near-identical test fixtures can share one thin parent, while 3 dense business-logic files may deserve detail-preserving treatment. Density clustering (HDBSCAN) already compresses *redundancy* correctly — near-duplicates collapse into one cluster naturally (first empirical check: webphone's `uk/es/en/translation.json` chunks should land in one tight cluster). What it can't see is *importance*, and the key finding from discussion: importance is not a property of a chunk but a relation chunk↔question — a static global score chases something that doesn't exist in isolation; retrieval-time relevance (the agent carries the question while traversing) does most of the job build-time "importance" was imagined for. If a proxy is ever needed, computable ingredients to mix: reference centrality (PageRank à la aider — flawed alone: a `toUpperCase` util is high-centrality, low-importance), dependency blast radius, git churn, uniqueness (embedding distance from corpus), and LLM-as-judge at summarization time ("what here would be costly to misunderstand?"). Only application: per-cluster summary detail budget (internally diverse cluster → longer summary), never tree shape.

## Chunking: per-language sizing and function-level containment
`prototype/repo-analysis.ipynb` derived `chunk_size_kb` per category (10/10/2 for code/docs/data) empirically via a log-scale Kneedle knee on file-size distributions across 4 large open-source repos. `chunk_overlap` was investigated and removed entirely (see the notebook's conclusion) — the splitter never truncates a piece, so a static copied-bytes overlap had no real job; the one edge case that needed fixing (raw-char fallback for an unsplittable oversized token) was a reassembly-correctness bug in `merge_pieces`, not a config number, and is now fixed.

Still open from the same notebook:
- **Per-language chunk_size** — real spread within `code` (p70 ranged 1404B TypeScript to 5914B Python), but we kept one global number per category for simplicity. If retrieval quality issues show up later, revisit whether `chunking.toml` needs a per-language override on top of the category default.
- File-level size is a proxy — the real self-containment question is per-function/section boundaries (AST/tree-sitter), not whole-file size. Worth doing once there's a way to actually measure retrieval quality against it.
- `filter.toml`'s `[default]` category fallback (no extension → `docs`) can miscategorize non-prose files (found via `moby/daemon/testdata/stat`, a test fixture, landing in `docs`) — low priority, but worth a `testdata/`-style exclude pattern or a saner default if it recurs.

## CLI polish: ASCII-art startup banner
When `hrono serve` starts it currently prints plain text. Nice-to-have: render the `hrono` name as an ASCII-art banner on startup so the terminal output looks polished. Purely cosmetic, no functional impact. Keep it optional/suppressible (e.g. a `--no-banner` flag or quiet mode) so it never gets in the way of scripting or log parsing.
