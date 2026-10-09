# Research: Knowledge Bases for AI Agents over Fragmented Enterprise Systems

Research run: 6 search angles, 27 sources fetched, 125 claims extracted, 25 adversarially verified (18 confirmed / 7 refuted), 110 subagent calls.

Scope: does prior art already solve hrono's three directions — (1) index/pointer files, (2) hierarchical abstraction trees, (3) incremental/self-updating knowledge bases — for agents working over large, messy, legacy, distributed enterprise systems?

---

## 1. Index / Pointer Files

Lightweight maps that point an agent at where information lives, without restructuring the underlying data.

### [Aider — repomap](https://aider.chat/2023/10/22/repomap.html)
Aider parses every source file with tree-sitter into an AST, extracts symbol definitions/references, builds a graph where files are nodes and symbol references are edges, and ranks files/symbols with PageRank so the most "important" (widely-referenced) code surfaces first. The map is then rendered as a compact, token-budgeted text summary injected into the LLM's context instead of raw file contents.

**Insight:** This is a working, shipped version of hrono's "pointer file" idea, scoped to code — but note it's still a *flat, single-level* ranked index, not a hierarchy. It solves "what to point at" via graph centrality (PageRank), which is a concrete, reusable technique hrono could borrow for ranking which parts of a fragmented enterprise system deserve a pointer entry at all.

### [Sourcegraph — how Cody understands your codebase](https://sourcegraph.com/blog/how-cody-understands-your-codebase)
Cody moved away from embeddings-based semantic retrieval and back to Sourcegraph's native code search, using an adapted BM25 ranking function combined with other signals (recency, file type, symbol structure) to select relevant snippets, rather than a static precomputed index of "where things are."

**Insight:** A direct counter-signal to "build a bigger index": Sourcegraph found that call-time hybrid search (lexical + signals) beat a purely precomputed embedding index for their use case. Worth weighing against hrono's tree/index approach — a pointer index doesn't have to be static; it can be a live-queried ranking function instead.

### [Sourcegraph — remote repository context](https://sourcegraph.com/blog/how-cody-provides-remote-repository-context)
Sourcegraph reports customers running Cody across 300,000+ repositories and 90GB+ monorepos without issue, using the same search-based context retrieval rather than exhaustive indexing of every repo.

**Insight:** Evidence that index/pointer-style approaches do scale to true enterprise-magnitude fragmentation (thousands of repos) — validates that hrono's direction 1 is viable at scale, not just toy-repo scale, provided the index is search/rank-based rather than requiring full precomputation of every relationship.

### [Cursor — secure codebase indexing](https://cursor.com/blog/secure-codebase-indexing) / [How Cursor actually indexes your codebase](https://towardsdatascience.com/how-cursor-actually-indexes-your-codebase/)
Cursor builds a Merkle tree of file hashes over the codebase; small edits change only the hash of the edited file plus its parent directories up the tree, so a periodic sync (~every 5 minutes) can diff local vs. server hash trees and re-embed only the mismatched files, rather than re-indexing everything.

**Insight:** This is really an *incremental-update* mechanism riding on top of an index (see Section 3), but it's relevant here too: the index itself (embeddings per file/chunk) is flat, and the Merkle tree exists purely to detect what changed — it is not itself a hierarchy of abstraction/summaries.

**Where index/pointer approaches fall short (per hrono's own framing, and corroborated here):** every source above still resolves down to raw file/chunk content at read time — none of them let an agent stop at a "good enough" abstraction level short of raw data, which is exactly the gap hrono's direction 2 is meant to close.

---

## 2. Hierarchical Abstraction Trees

Building multi-level summary trees so an agent can stop as high in the hierarchy as the query allows.

### [RAPTOR (Sarthi et al., ICLR 2024)](https://arxiv.org/html/2401.18059v1)
Recursively embeds, clusters (Gaussian Mixture Models), and LLM-summarizes chunks of raw text bottom-up, building a tree with several levels of abstraction. Verified: summaries compress child content by 72% on average (summary ≈131 tokens vs. ≈86-token average child length per node, aggregated across children). This is the closest academic blueprint to hrono's stated direction 2.

**Insight — and an important caveat:** Two related claims did **not** survive adversarial verification. First, RAPTOR's own paper claims a "collapsed tree" strategy (flattening all levels and retrieving by similarity across the whole tree at once) "consistently" beats layer-by-layer root-to-leaf traversal — verifiers found this overstated relative to the actual experiment (tested on only 20 stories from one dataset, not "consistently" across the board). Second, the claim that retrieval naturally and reliably pulls a large share of results from non-leaf (summary) nodes was only weakly supported (18.5%–57%, highly variable by dataset/retriever). **Net effect: RAPTOR does not actually give strong validated evidence that "stop before the leaf" retrieval works well** — hrono's assumption that an agent can often stop at a summary node is a hypothesis to test, not something RAPTOR already proved.

### [Microsoft GraphRAG — new tool for complex data discovery](https://www.microsoft.com/en-us/research/blog/graphrag-new-tool-for-complex-data-discovery-now-on-github/)
Uses an LLM to extract entities/relationships from private documents into a knowledge graph, then partitions the graph into nested hierarchical communities (Leiden algorithm) and pre-generates an LLM "community report" summary at every level of the hierarchy — each level a different granularity of abstraction over the same underlying data.

**Insight:** This is essentially RAPTOR's idea generalized from plain text to an entity-relationship graph, and it is Microsoft's flagship, most battle-tested implementation of hrono's direction 2. One motivating claim behind GraphRAG — that flat vector-similarity RAG specifically fails on "global sensemaking" questions — was **refuted on adversarial re-check** as an overreach of the cited evidence; treat that motivation as contested marketing framing, not an established fact.

### [Microsoft GraphRAG — dynamic community selection](https://www.microsoft.com/en-us/research/blog/graphrag-improving-global-search-via-dynamic-community-selection/)
Microsoft's own measurement: the original static global-search method processed ~1,500 community reports at one fixed hierarchy level per query, when only ~470 were actually relevant. Their fix starts at the tree root, uses an LLM to score each report's relevance, prunes irrelevant branches, and only descends into relevant sub-communities — cutting cost by 77%.

**Insight — the single most directly transferable finding in this research:** this is essentially a validated, production implementation of hrono's exact stated goal ("agent starts from the root node and moves in the direction he wants, doesn't always need to reach the leaf"). The transferable pattern is: *LLM-scored relevance at each node, prune-then-descend, root-first* — not a fixed depth or fixed traversal order.

### [RAG vs. GraphRAG: A Systematic Evaluation (arXiv 2502.11371)](https://arxiv.org/html/2502.11371v3)
Finds GraphRAG's advantage is task-dependent, not universal: graph/hierarchy-based methods win on multi-hop, reasoning-intensive questions, while flat RAG wins on single-hop, detail-oriented queries. Specifically, GraphRAG's global search (retrieving only high-level community summaries) underperformed flat RAG on detail-centric QA in one benchmark (30.89% vs. 55.28%), because fine-grained evidence gets lost in summarization. Also: overall effectiveness is bottlenecked by extraction quality — in one benchmark only 65.8% of gold-answer entities were even present in the constructed graph, and using a stronger extraction model to fix that raises cost.

**Insight — a real design constraint for hrono:** a pure top-down hierarchy-only design will systematically fail on "give me the exact value/detail" enterprise queries. hrono's tree likely needs an explicit bypass/escape hatch to raw data for detail-lookup tasks, not just root-to-leaf descent, and leaf-level summarization quality over messy legacy source data will hard-cap what the higher levels can ever represent.

### [GraphRAG-Bench (arXiv 2506.02404)](https://arxiv.org/pdf/2506.02404)
Argues existing GraphRAG evaluation leans on generic QA datasets that don't actually test whether the hierarchy improves reasoning (rather than just retrieval), and introduces a harder benchmark (1,018 multi-hop, domain-specific questions across 16 CS disciplines) designed so simple passage retrieval can't answer them.

**Insight:** Methodological warning, not a design pattern — if/when hrono evaluates its own tree, generic Q&A-style tests may not reveal whether the abstraction levels are actually helping vs. just retrieving.

---

## 3. Incremental / Self-Updating Knowledge Bases

This is the **weakest** direction in terms of validated prior art — several plausible-looking claims here were specifically refuted under adversarial review.

### [EChecker (arXiv 2404.13295, ISSTA 2024)](https://arxiv.org/pdf/2404.13295)
Detects build-dependency errors incrementally: infers only the dependencies changed by a new commit (from C/C++ preprocessor directives and Makefile diffs) instead of doing a full clean rebuild, reporting ~85x efficiency gain over full-rebuild-based detection.

**Insight:** The one clean, verified example of true incremental/delta knowledge maintenance in this research — but it's domain-narrow (C/C++ build-dependency graphs specifically). The transferable pattern is "diff the source → infer only the affected dependency subset → update only that subset," not the specific mechanism. Generalizing this to broad enterprise knowledge/summary trees is untested territory.

### [Cursor — Merkle-tree change detection](https://cursor.com/blog/secure-codebase-indexing)
Confirmed mechanism: file-hash Merkle tree, small edits change only the edited file's hash and its ancestor directory hashes, periodic sync diffs client vs. server tree to find and re-embed only mismatched files.

**Insight:** A solid, verified pattern for cheap change-detection at the *file* granularity — but it only tells you *which flat file changed*, not which higher-level summary/community/tree-node needs to be regenerated as a result. hrono's harder problem — propagating a leaf change up through multiple abstraction levels without redoing the whole tree — is not addressed by this mechanism.

### [lwn.net — Merkle trees for build systems](https://lwn.net/Articles/821367/)
General technique: a build system can detect whether *any* part of a large dependency tree changed by comparing one root Merkle hash, avoiding per-file timestamp/content checks, and can walk down to isolate exactly which subtree changed.

**Insight:** Confirms the "change detection" half of the problem (cheaply knowing something changed and roughly where) is well-solved and reusable. What it does *not* solve is the "regeneration" half — knowing a leaf changed doesn't tell you how to cheaply regenerate just the affected LLM-generated summary nodes above it.

### [CocoIndex — real-time data substrate for AI agents](https://medium.com/@cocoindex.io/building-a-real-time-data-substrate-for-ai-agents-the-architecture-behind-cocoindex-729981f0f3a4)
Reports concrete numbers for incremental vs. full reindexing: full reindex of a corpus ≈22 minutes, $8.50, 50,000 vector writes, vs. an incremental update for 10 changed files ≈45 seconds, $0.07, 400 vector writes.

**Insight:** Good evidence of *how large* the win from incremental updating can be (roughly 500-1000x cheaper for a small change) — a strong motivating data point to cite when justifying hrono's incremental-update direction as worth the engineering investment, even though CocoIndex's incrementality is at the flat vector-index layer, not the summary-hierarchy layer.

### [DoltHub — building a vector index with Prolly Trees](https://www.dolthub.com/blog/2024-10-08-how-to-build-a-vector-index-with-prolly-trees/)
Prolly trees are history-independent: identical data always produces the same tree structure regardless of insertion order (unlike ordinary B-trees), which makes them efficient to diff and merge — a property directly useful for versioned/incrementally-updated tree structures.

**Insight:** A genuinely relevant data-structure candidate for hrono's abstraction tree if it needs to support cheap structural diffing (e.g., "what changed between this version of the tree and the last one") — worth evaluating as the underlying storage structure for the hierarchy itself, not just for flat vector indexes.

### Claims that looked like direct prior art but were refuted
- **"A coding-agent context engine already does Merkle-tree-based incremental reindexing, touching only changed portions"** (from [arXiv 2606.22417](https://arxiv.org/pdf/2606.22417), "Code Isn't Memory") — refuted 1-2 on adversarial review.
- **"A structural codebase index causally improves task-localization/resolution in a controlled ablation"** (same paper) — also refuted 1-2.
- **"Palantir's Ontology uses Change Data Capture / streaming pipelines to avoid full regeneration"** — refuted 1-2 (Palantir's fragmentation-unification claim survived; its incremental-sync claim did not).

**Why this matters:** these refutations are informative in themselves. They suggest that genuine, benchmark-validated incremental/self-updating of *LLM-generated abstraction* (as opposed to flat vector indexes or narrow build graphs) is **not yet an established, proven industry practice** — this is the direction where hrono has the most room to do something genuinely new rather than re-implement solved prior art.

---

## 4. Cross-Cutting: Agentic Memory & Enterprise Fragmentation

Sources that combine index + hierarchy, or address the "large legacy enterprise system" framing directly.

### [Confucius Code Agent (arXiv 2512.10398)](https://arxiv.org/pdf/2512.10398)
Implements an explicit context-management layer for coding agents: a tree-structured, file-system-based hierarchical working memory (internal nodes = semantic groupings like packages/modules/subsystems, leaf nodes = Markdown documents with metadata and configurable visibility scopes) plus adaptive context compression — replacing flat chat history / naive truncation. A companion long-term memory system stores cross-session knowledge not as raw logs but as a hierarchical tree of typed Markdown notes (programmatically searchable/readable/writable/editable/importable). Measured ablation benefit: iteration turns 64→61, token cost 104k→93k, Resolve@1 53%→54.4%.

**Insight — the single closest existing implementation of hrono's combined idea (index + hierarchy, filesystem-native, typed nodes).** It's a working, benchmarked system that validates the whole approach end-to-end, with one caveat: it operates over a single repo's working session, not a large distributed multi-system legacy enterprise estate — the jump to "many legacy subsystems" scale is still unproven.

### [ByteRover — Context Tree (arXiv 2604.01599)](https://arxiv.org/abs/2604.01599)
Organizes agent memory as a 4-level hierarchical "Context Tree" (Domain → Topic → Subtopic → Entry); each node tracks explicit relationships (`@relation` cross-references), source/provenance metadata, and lifecycle metadata (importance score, maturity tier, recency decay). Stored entirely as human-readable markdown files on the local filesystem, deliberately avoiding vector DBs, graph DBs, or embedding services.

**Insight:** Direct validation that a lightweight, filesystem-only, no-vector-DB, no-graph-DB hierarchy is a *deliberate, defensible* architecture choice others have converged on independently — not just a stopgap for lack of infrastructure. Confidence downgraded to medium here because ByteRover is a commercial product and the source has a plausible conflict of interest.

### [MemGPT](https://research.memgpt.ai/)
Implements "virtual context management": pages data between the LLM's bounded context window ("main context") and external storage ("external context"), analogous to OS virtual memory paging between RAM and disk. Distinctively, it teaches the LLM *itself*, via tool/function calls, to actively decide what stays in-context vs. gets pushed out — not a fixed external retrieval pipeline making that decision for it.

**Insight:** A useful reframe for hrono's index/pointer direction: instead of a static pointer file the agent passively reads, give the agent tool-calls to actively manage and update its own working view of the index/tree, treating index navigation as an active skill rather than a one-shot lookup.

### [Letta — memory blocks](https://www.letta.com/blog/memory-blocks/)
Memory "blocks" are individually stored in a database with unique IDs and dynamically compiled into the LLM's context window at request time, rather than being baked into a static prompt.

**Insight:** Reinforces the same idea as MemGPT — treat context construction as a dynamic assembly step at request time, not a fixed document the agent reads start-to-finish.

### [Palantir Foundry — the Ontology system](https://www.palantir.com/docs/foundry/architecture-center/ontology-system)
Explicitly positioned to solve enterprise data fragmentation by unifying disparate legacy/duplicated systems (ERP, CRM, industrial DBs, document stores, sensors) into one coherent object/property/link model, without necessarily duplicating/migrating the underlying data. Partially corroborated independently, including by a skeptical third-party reviewer (Lokad) citing a real case connecting seven ERP systems.

**Insight:** Real proof that the fragmentation problem hrono describes is solvable at true enterprise scale — but via heavy, vendor-operated integration infrastructure (a semantic layer product with a large engineering/ops footprint), not a lightweight agent-context layer. Useful as an existence proof of feasibility, not as an architecture to copy. (Its claimed use of Change Data Capture for incremental sync did **not** survive adversarial verification — don't cite Palantir as proof of incremental self-updating.)

### [Glean — enterprise knowledge graph](https://www.glean.com/blog/knowledge-graph-agentic-engine)
Builds an enterprise knowledge graph with access controls that mirror source-system permissions (an employee can only see in the graph what they could already see in the source system), rather than a bolted-on separate permission layer.

**Insight:** A design constraint hrono should plan for early if it will ever touch real enterprise legacy data: permission-awareness needs to be inherited from source systems into the index/tree, not retrofitted later.

### [Foundation Capital / diginomica — "context graphs"](https://diginomica.com/context-graphs-unlock-new-seam-enterprise-knowledge-ai-agents)
Introduces "context graphs" as a framework/terminology for capturing enterprise decision-making knowledge (decision traces, not just facts) specifically for AI agents.

**Insight:** Naming/framing more than a technical contribution, but useful vocabulary — hrono's knowledge base may need to capture *why* decisions were made across legacy systems, not just *what* the current state is, if it's meant to help an agent reason about a messy system's history.

### [Sigmoid — modernizing legacy architectures with GenAI-powered knowledge graphs](https://sigmoidanalytics.medium.com/modernizing-legacy-architectures-using-genai-powered-knowledge-graphs-73d96169f6d7)
Describes a concrete 3-step pipeline for legacy-code knowledge graphs: (1) parse source into an AST via language-specific parsers, (2) LLM-generate semantic summaries per component, (3) store both structural and semantic metadata as graph nodes/edges with typed relationships (`calls`, `inherits`, `depends_on`, `defined_in`).

**Insight:** A practical, near-identical blueprint to what hrono is describing for its abstraction tree, specifically framed around *legacy* modernization rather than a clean modern repo — worth reading in full as the closest "how do I actually build this" writeup found in this research.

---

## 5. Limitations & Cost — What Prior Art Warns You About

### [GraphRAG cost cliff (Medium)](https://medium.com/graph-praxis/the-graphrag-cost-cliff-how-33-000-became-33-in-eighteen-months-be1b0fbe37e4)
Indexing a 5GB legal dataset with Microsoft GraphRAG cost $33,000 in early 2024, falling to roughly $33 by mid-2025 — attributed to LLM cost/efficiency improvements from Microsoft Research, not architecture changes.

### ["You probably don't need GraphRAG" (Medium)](https://medium.com/@amrwrites/you-probably-dont-need-graphrag-0bc9cf671db1) / [GitHub issue #385](https://github.com/microsoft/graphrag/issues/385)
Processing a 32,000-word book cost ~$7; users on GitHub reported $5 to run the basic single-file example and $35 to index just 10 documents, prompting many to switch to local/cheaper models.

**Insight (applies across both hierarchy and indexing directions):** building an LLM-summarized hierarchy over real data is not free, and costs can be non-obvious/surprising at first. This is a strong argument *for* hrono's incremental-update direction specifically — if building the tree once is expensive, avoiding full regeneration on every change isn't just an efficiency nicety, it's the difference between a usable system and an unaffordable one at enterprise scale.

### [arXiv 2606.06003 — LLM graph reasoning tool-access](https://arxiv.org/pdf/2606.06003)
A claim that the main obstacle to effective LLM graph reasoning is missing traversal *tools* rather than model intelligence was **refuted (0-3)** on adversarial review — treat this as an open, unresolved question rather than a settled explanation for why graph-based reasoning sometimes underperforms.

---

## Synthesis

**Already solved / strong prior art exists for:**
- Hierarchical abstraction trees over a single corpus or repo (RAPTOR, GraphRAG) — including root-first, prune-as-you-descend traversal (GraphRAG dynamic community selection) that is nearly a direct implementation of hrono's "start at root, go as deep as needed" goal.
- Lightweight, filesystem-native index+hierarchy specifically for coding agents (Confucius Code Agent, ByteRover) — both deliberately avoid vector/graph-DB infrastructure, validating a low-infrastructure approach.
- Change *detection* at the flat-file/dependency level (Merkle trees, EChecker) is a mature, reusable technique.
- Enterprise-scale fragmentation is solvable in principle (Palantir), just not via a lightweight approach.

**Still open / weakly validated — where hrono can differentiate rather than reinvent:**
- **True incremental regeneration of an LLM-generated abstraction hierarchy** (as opposed to a flat vector index or a narrow build-dependency graph) is essentially unproven in the literature found here. No source shows "leaf changed → regenerate only its parent summary, leave siblings/higher levels untouched" as a working, benchmarked system. This is hrono's biggest potential original contribution.
- Whether an agent can *reliably* stop at a summary node instead of descending to raw leaves is less proven than it first appears — RAPTOR's own evidence for this was largely refuted on close inspection, and GraphRAG-family research shows summary-level retrieval measurably loses on detail-oriented/single-hop queries. hrono's tree likely needs an explicit "drop to raw data" escape hatch, not a pure top-down design.
- Nothing in this research directly addresses hrono's specific scenario — many *distributed*, *legacy*, *duplicated* enterprise subsystems simultaneously — as opposed to one repo or one curated document corpus. Every hierarchy example here (RAPTOR, GraphRAG, Confucius) is single-corpus/single-repo scoped; scaling the same idea across many heterogeneous legacy systems at once is untested territory.
- The specific combination hrono proposes — index/pointer files *and* a separate hierarchical abstraction tree, used together — has no single documented example combining both explicitly as two coordinated layers; it's closest to Confucius Code Agent's design but not identical.

**Bottom line:** direction 2 (hierarchical abstraction trees) is the most externally validated and least risky to build — go read GraphRAG's dynamic community selection and Confucius Code Agent in full before designing hrono's traversal logic. Direction 1 (index/pointer files) is well-trodden and mostly a matter of picking known techniques (tree-sitter/AST parsing + PageRank-style ranking, or hybrid lexical+signal search) rather than inventing new ones. Direction 3 (incremental/self-updating) is the genuinely open problem — worth treating as hrono's core differentiator and the place to invest the most original design thinking, since even the tools that plausibly claimed to solve it (coding-agent "context engines," Palantir CDC sync) didn't hold up under scrutiny.
