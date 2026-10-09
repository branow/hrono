# hrono design — file index

The design record: the research, the experiments and the settled decisions
hrono was built from, kept with the code (moved here from a private research
workspace on 2026-10-09). Quick map of what lives where. One line per file: what it is and when to open it.
`context.md` carries the deep per-file context; this is just navigation.

## Root — docs & research notes

| File | What it is |
|---|---|
| `context.md` | The living project summary: problem, approach, current status, next steps. **Start here.** |
| `design-sketch-v1.md` | Source of truth for architecture decisions — chunking, URI scheme, clustering, branching factor, update mechanism. |
| `clustering-lifecycle.md` | Source of truth for stored-cluster operating rules: BUILD / UPDATE / MONITOR / LOCAL REPAIRS / RECONCILE, parameters, invariants. |
| `TODO.md` | Deliberately deferred work: source discovery, non-git source types, importance modeling, per-language chunk sizing. |
| `research-knowledge-bases-for-agents.md` | Prior-art survey (RAPTOR, GraphRAG, incremental indexing, agentic memory). Why the hierarchical-tree direction is valid. |
| `research-cluster-summarization.md` | Verbatim summarization prompts from RAPTOR/GraphRAG/LlamaIndex and what they imply for hrono's node-summary prompt. |
| `llm-summarization-research.md` | Raw research notes behind the summarization work (long-form; distilled into the two files above/below). |
| `summarization-experiments.md` | The 6-round experiment history and the **chosen** node-summarization recipe (two-layer gotcha-aware map-reduce), plus rejected approaches. |
| `importance-discussion.md` | Discussion notes on chunk "importance" — conclusion (importance is chunk↔question, not a static score) distilled into `TODO.md`. |
| `hop-cost-experiment-results.md` | Measured real LLM-hop cost (`claude -p`) that informed branching-factor decisions. |

## prototype/ — research prototype (throwaway quality)

The notebooks keep their executed outputs, which are the evidence the
decisions cite. The prototype's `pyproject.toml` and its generated data
(`.hrono/`, cloned repos, caches) were not carried over, so the notebooks are a
record to read, not something to re-run as is.

### Configs
| File | What it is |
|---|---|
| `hrono.toml` | Resource config: which sources to ingest (git only for now: url + auth). |
| `filter.toml` | Which files are chunkable: glob excludes, size cap, null-byte sniff. |
| `chunking.toml` | Extension → category (code/docs/data), chunk sizes, separator hierarchies. Sizes empirically derived in `repo-analysis.ipynb`. |
| `embedding.toml` | Embedding model config (Qwen3-Embedding-0.6B, local) + batch-size OOM notes. |
| `paragraphing.toml` | RETIRED — config of the rejected recursive-delimiter paragraph splitting (see paragraph-split.ipynb); kept as history. |
| `structuring.toml` | Config of the settled structure-aware splitter (budgets, min sizes, delimiter cascade). Read by `structuring.py`. |

### Notebooks
| File | What it is |
|---|---|
| `research.ipynb` | The main pipeline notebook, steps 1–23: clone → filter → chunk → index → embed → clustering research → update-mechanism proofs. Where all clustering findings in `context.md` come from. |
| `repo-analysis.ipynb` | Empirical derivation of `chunk_size_kb` (Kneedle knee over 4 big OSS repos) and the kill-`chunk_overlap` analysis. |
| `model-comparison.ipynb` | Executed report: Qwen3-0.6B vs Granite R2 (311M/97M) — timing table, clustering comparison, and the experiment-model decision (97M for experiments, Qwen3 for final runs). |
| `paragraph-split.ipynb` | Paragraph-splitting first look: existing recursive splitter at paragraph scale over sampled chunks. Eyeball verdict: REJECTED — cuts through functions/JSON/prose; superseded by structure-split.ipynb. |
| `structure-split.ipynb` | Structure-aware (cAST-style) paragraph splitting prototype: tree-sitter structure trees + whole-node greedy packer over sample files, full paragraphs for eyeball review, corpus-wide parse timing. Approach ACCEPTED; settled recipe extracted to `structuring.py`. |
| `storage-v2.ipynb` | The v2 storage layer built and demonstrated on real data: `paragraphs` (ground truth) / `chunks` (derived runs) / `contents` (content-addressed bodies) in `.hrono/hrono-v2.db`, with RAG-hit rendering, byte-identical chunk reassembly, and dedup queries. |
| `rag-retrieval.ipynb` | The retrieval experiment series ending in the FROZEN recipe (α=0.5 blend + BM25, strict z-floors, RRF 70/30, empty→traverse): baseline failures, hybrid, α sweep, adaptive-k, and the 13-prompt calibration with no-answer controls. Verdict + residuals in its Observations cell. |
| `tree-level1.ipynb` | First real tree layer on v2: frozen clustering recipe over v2 chunks → `nodes`/`edges` tables (summaries survive rebuilds via member-set signature), then the chosen map-reduce summarization for a 5-node probe, DB-persisted (`condensations` table = map results, content-addressed; `prompts` table = provenance). |
| `tree-build.ipynb` | The complete tree: 41 level-1 summaries (`l1-pure` gotcha-aware map-reduce, haiku), 6 level-2 parents + root (`v7b` pure-abstraction prompt, sonnet), mechanical faithfulness gate, visual export `.hrono/tree.html`. Prompt changes auto-invalidate stale summaries. |
| `summarize-level2-experiments.ipynb` | The 7-round prompt search for level-2+ summarization on real parents: routing-style rejected, pure-abstraction/free-form/intent-only adopted (`v7b-sized`, sonnet). All outputs in `level2_experiments` with prompt provenance. |
| `update-threshold.ipynb` | Update-propagation calibration: three similarity metrics failed structurally (noise ≥ signal at every level) → adopted "hash detects, judge decides": Haiku judges the raw-source diff (none/minor/major), `nodes.drift` + `update_log` mechanics. Verdict in Observations. |
| `edit-stability.ipynb` | Modified-chunk stability test: UPDATE-rule replay of real webphone edit batches (HEAD~3/10/15) against the stored 41-cluster tree, with leave-one-out control and end-to-end validation of the amended rule. Verdict: edits never fall below TAU; the old nearest-member join rule was the churn source; the adopted sticky pre-batch-centroid re-check + nearest-centroid placement keeps 100% in place. Rule lives in `clustering-lifecycle.md` UPDATE. |
| `rag-summaries.ipynb` | The collapsed tree joins retrieval: node summaries split by the same structure-aware splitter into the same `paragraphs`/`contents` tables (`node://hrono/nodes/<id>/<slug>@<sig>`), embedded + FTS-indexed, frozen recipe over the union; architectural vs detail vs control prompts. |

### Scripts
| File | What it is |
|---|---|
| `build_clusters.py` | The settled clustering recipe as a runnable script (combined vectors α=0.5 → UMAP-25 → HDBSCAN leaf → noise assignment). Writes `.hrono/clusters.json`. |
| `structuring.py` | The settled structure-aware splitter as a module: tree-sitter structure trees, delimiter deepening, whole-node packer at two budgets (`split_file_hier`), `struct_paths` extraction, `sp:` URI rendering (`sp_render`). Configured by `structuring.toml`; used by `storage-v2.ipynb`. |
| `summarize_experiments.py` | Runs summarization prompt experiments (approach × size budget) over sample clusters via the Claude Agent SDK; records everything to `.hrono/summarization-experiments/`. |
| `check_faithfulness.py` | Mechanical (no-LLM) fabrication check: every identifier-like token in a summary must literally appear in its source. |
| `build_report.py` | Renders all recorded summarization experiments into one self-contained `.hrono/summarization-experiments/report.html`. |
| `test_embedding_models.py` | Embeds candidate models into the `(hash, model)` table and runs the frozen recipe from `build_clusters.py` on them; writes `clusters-<model>.json`. |
| `benchmark_embedding_models.py` | Timed full re-encode of the corpus per candidate model; appends machine + per-model numbers to `.hrono/embedding-benchmark.json`. |
| `main.py` | Placeholder entry point. |

## Where to look when…

- …deciding **architecture**: `design-sketch-v1.md`, then `context.md` for what's already settled.
- …touching **cluster update logic**: `clustering-lifecycle.md` (rules) + `research.ipynb` steps 20–23 (proof).
- …writing the **node summarizer**: `summarization-experiments.md` (chosen recipe) + `summarize_experiments.py` (working prompts/code).
- …changing **chunking numbers**: `repo-analysis.ipynb` conclusion cell first — they're measured, not guessed.
- …wondering **why not X**: rejected alternatives live in `context.md` (storage), `summarization-experiments.md` (prompts), `research.ipynb` (reducers/clusterers).
