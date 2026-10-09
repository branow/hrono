# Research: cluster-summarization prompts in hierarchical retrieval systems

Research record from before hrono's recipe was settled. What hrono does now is in [../summarization.md](../summarization.md): it adopted mechanical references and routing-free briefs, and rejected prompt-level size budgets.

Deep-research pass (2026-07-12, capped run: 20 agents / ~385k tokens) on how existing systems prompt an LLM to summarize a cluster into a tree node, and how they evaluate the result. All quotes below were verified verbatim against the systems' main/master branches on the fetch date — pin to the quotes, not the URLs (these repos move fast; GraphRAG already restructured into a monorepo, so older paths 404).

**Coverage caveat:** the capped run answered question (1) — actual prompts of RAPTOR / GraphRAG / LlamaIndex — thoroughly, and did NOT get to (2) prompt-design papers, (3) evaluation protocols (SummaC, G-Eval, LLM-as-judge, retrieval-based evals), or (4) heterogeneous code+config+docs clusters. Those remain open (see "Open questions"). A follow-up pass scoped to evaluation only is the natural next research step if we want it.

## The headline: two prompt-design philosophies

**Minimal free-text (RAPTOR, LlamaIndex):** a one-sentence generic prompt, quality comes from tree structure + embeddings, not prompt engineering.

**Structured routing-oriented (GraphRAG community reports):** fixed JSON schema, entity-rich titles, prompt-level grounding rules. This is the closest thing to a reusable template for hrono's routing-node use case.

## RAPTOR (official repo, HEAD 7da1d48)

- Summarization prompt, verbatim: `"Write a summary of the following, including as many key details as possible: {context}:"` (system prompt: "You are a helpful assistant."). No structure, no keywords, no routing guidance — repo-wide grep found no other summarization prompt.
- Its only design lever is a **length budget**: `summarization_length` defaults to 100 tokens (`tree_builder.py:72-74`), passed as `max_tokens` to the summarize call (signature fallback 150). Cluster summaries are genuinely capped at ~100 tokens.
- Implication: RAPTOR's retrieval quality comes from the tree + embedding similarity over short generic summaries, not from prompt engineering. Sources: `raptor/SummarizationModels.py:34,64`, `raptor/tree_builder.py`, `raptor/cluster_tree_builder.py`.

## Microsoft GraphRAG community reports (main branch, 2026-07-12)

The most reusable template for a routing node. Both the default indexing prompt (`packages/graphrag/graphrag/prompts/index/community_report.py`) and the prompt-tune template (`.../prompt_tune/template/community_report_summarization.py`) carry the same design:

- **Fixed five-field JSON output**, enforced in the prompt: "The output should be a single JSON object that can be parsed by json.loads." Fields: `title`, `summary`, `rating`, `rating_explanation`, `findings[]` (each finding = `{summary, explanation}`).
- **Entity-rich titles**: "TITLE: community's name that represents its key entities - title should be short but specific. When possible, include representative named entities in the title." (Few-shot example: "Verdant Oasis Plaza and Unity March".) This is exactly the keyword/entity-inclusion pattern that makes a node label scannable for descent decisions.
- **Prompt-level grounding rules** ("# Grounding Rules" section): every claim must carry an inline citation `[Data: <dataset name> (record ids)]`, max 5 ids per reference plus `"+more"`; "Do not include information where the supporting evidence for it is not provided"; "Do not make anything up in your answer." Instruction-only faithfulness — no programmatic check — but the citation format makes post-hoc verification of summary-against-source feasible (relevant to our `assigned`-flag / diff-layer ideas: citations = child pointers inside the summary text).
- Note: GraphRAG's `{input_text}` is pre-structured entity/relationship tables, not raw chunk text — its prompt shape transfers, its input shape doesn't directly.

## LlamaIndex tree index (main branch, 2026-07-12)

- Node-summary prompt (`DEFAULT_SUMMARY_PROMPT_TMPL`) is minimal free text: "Write a summary of the following. Try to use only the information provided. Try to include as many key details as possible." No budget, no schema, no entities. Confirmed as the actual tree-index default (`indices/tree/base.py:81`).
- **The architecturally interesting part — decoupled routing**: descent intelligence lives in separate query-time `TREE_SELECT` prompts, not in the summaries. The selector shows child summaries as a numbered list and constrains output to `ANSWER: <number>` + justification ("Using only the choices above and not prior knowledge, return the choice that is most relevant to the question"). A `TREE_SELECT_MULTIPLE` variant returns ranked `ANSWER: <numbers>` capped by `branching_factor`, wired to `TreeSelectLeafRetriever.child_branch_factor` for multi-way descent.
- Takeaway for hrono: summaries only need to be **discriminative among siblings**; the constrained-output selector prompt does the routing work. Summary generation and descent decisions are separable design problems. (Caveat: this is LLM-guided retriever traversal, not an autonomous agent, but the mechanism transfers.)

## What this suggests for hrono

1. Start from the GraphRAG shape, simplified: JSON node = short entity/identifier-rich `title` + `summary` + optionally per-finding child citations (our chunk URIs). For code, "named entities" = symbol names, file names, config keys.
2. Impose a token budget like RAPTOR (their 100 is likely too tight for routing text; something in the 100-300 range).
3. Write the descent/query prompt as a separate artifact from day one (LlamaIndex TREE_SELECT pattern: numbered siblings, constrained answer format) — don't try to make the summary "do" routing.
4. Grounding rules + child citations give a cheap post-hoc faithfulness check even before any formal eval exists.

## Open questions (not covered by this pass)

- Evaluation of routing-oriented summaries: no verified findings on reference-free metrics, LLM-as-judge protocols, or downstream descent-accuracy evals. Most direct option for hrono — measure descent-decision accuracy against gold chunk locations — appears unstudied; likely we design our own (the earlier "routing test" idea: given a question answered in cluster X, does a selector over all node summaries pick X).
- Code-focused summarizers (aider repo-map, DeepWiki-style generators): do symbol/identifier-preservation instructions improve routing over code trees?
- Structured JSON + entity titles vs short free text: is one measurably better for LLM-driven descent, or does the constrained selector prompt do most of the work regardless?
- Heterogeneous clusters (code + config + docs in one cluster): unified prompt vs type-aware sectioning vs map-reduce per type; at what cluster size does map-reduce beat a single call?

## Refuted along the way

- "RAPTOR's entire prompt design is the bare system prompt 'You are a helpful assistant.'" — overreach; the real instruction is in the user message (see above).
