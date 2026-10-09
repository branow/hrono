# Importance Metrics for Hierarchical Knowledge Base Construction

## Goal

The objective is **not** to compute a single "importance score."

Instead, compute multiple **cheap, objective signals** from the raw data before any expensive LLM summarization. These signals become evidence that later helps decide:

- which clusters deserve more attention,
- which LLM/model to use,
- how much context to provide,
- how detailed the summary should be.

The final importance should emerge from the combination of these signals rather than from any single metric.

---

# 1. Novelty

### Definition

How different is a chunk from the rest of the knowledge base?

### Possible computation

- Compute embeddings.
- Find the *k* nearest neighbors.
- Average similarity to neighbors.

High similarity → low novelty.

Low similarity → high novelty.

### Discussion

Novelty is easy to compute and provides an objective signal.

However, novelty alone does **not** imply importance.

A very unique implementation detail may be irrelevant, while a common authentication pattern may be extremely important.

Still, novelty is useful as one piece of evidence.

---

# 2. Structural Importance (Centrality + Dependency)

### Definition

How structurally connected is a chunk to the rest of the knowledge base?

Initially we discussed centrality and dependency separately, but concluded that for this architecture they describe almost the same phenomenon.

### Possible computation

Construct an approximate graph before the first LLM pass.

Possible graph:

- nodes = chunks
- edges = embedding similarity (k-NN graph)

Then compute graph metrics such as:

- Degree
- PageRank
- Betweenness

These metrics are only approximations of structural importance.

### Discussion

This is **not** the final knowledge graph.

It is simply an approximation built from embeddings to estimate how connected a chunk is.

The graph is cheap to compute and gives useful structural signals.

---

# 3. Recurrence

### Definition

How many independent contexts express approximately the same idea?

Unlike novelty, recurrence is not about frequency inside one repository.

It measures whether similar information appears across independent sources.

### Possible computation

For each chunk:

- find similar chunks
- count distinct repositories
- count distinct source systems
- count distinct directory regions
- measure path diversity

### Discussion

This became one of the strongest candidate metrics.

Example:

A concept appearing in

- code,
- documentation,
- CMS,
- another repository

is likely more fundamental than a concept appearing only inside one folder.

Recurrence should be treated as a **chunk property**, not only a cluster property.

---

# 4. Temporal Profile (formerly Persistence)

### Original research idea

Persistence:
"Information that remains true for a long time is more important."

### Discussion

We found that persistence alone is misleading.

Examples:

- Stable for years → foundational architecture.
- Stable for years → abandoned dead code.

Both produce the same persistence score.

Instead, we proposed a richer concept:

## Temporal Profile

Possible signals:

- file age
- change frequency
- number of commits
- number of authors
- periods of activity/inactivity

Possible interpretations:

- Stable since creation → foundational.
- Active for years → evolving core subsystem.
- Active then frozen → mature subsystem.
- Frozen and isolated → possibly abandoned.

Temporal information should not directly determine importance.

Instead, it contributes evidence that is interpreted together with other metrics.

---

# 5. Actionability

### Original definition

"Does this information influence future decisions?"

### Discussion

We could not find an objective algorithmic approximation before LLM processing.

It appears to require semantic understanding.

It is probably better treated as a **second-stage metric** after summaries already exist.

Current status:

Not recommended for the first preprocessing layer.

---

# 6. Compression Gain

### Original definition

How much information can be replaced by one summary?

### Discussion

Initially this sounded promising.

However, for this pipeline compression is already handled by clustering.

Example:

100 similar files

↓

1 cluster

↓

1 summary

Therefore compression gain does not produce any additional decision.

It does not influence:

- model selection
- prompt size
- summary length

Current conclusion:

Not useful as an independent preprocessing metric.

---

# 7. Dependency

Originally considered separately from centrality.

After discussion we concluded that, for this architecture, dependency is essentially another expression of structural importance.

Rather than keeping two highly correlated metrics, merge them into:

- Structural Importance

---

# Final Proposed Toolbox

## Strong candidate metrics

- Novelty
- Structural Importance (graph metrics)
- Recurrence
- Temporal Profile

These are all algorithmically computable before any LLM call.

---

## Later-stage metrics

- Actionability

Requires semantic understanding.

Better computed after the first summarization layer.

---

## Dropped / merged metrics

Compression Gain

- already achieved through clustering

Dependency

- merged into Structural Importance

---

# Overall Philosophy

The biggest insight from the discussion:

**Do not try to compute "importance."**

Instead, compute multiple objective signals that each describe one aspect of a chunk.

For example:

- Novelty
- Structural importance
- Recurrence
- Temporal profile

Each signal is weak by itself.

Together they provide a much more convincing estimate of which clusters deserve more expensive LLM processing and richer summaries.

---

# Web Research: What the Literature Says (2026-07-11)

Deep-research pass over academic and practitioner work. Confidence labels: **confirmed** = survived 3-vote adversarial verification; others are quote-backed extractions from primary papers (verification cut short by session limit).

## Headline

The literature converges on the same conclusion as this document: there is no universal importance function, but there is a universal **shape** for one — a parameterized combination of a few domain-agnostic signals, where the parameters (weights, rubric, background corpus) are the user-configurable part.

## Signal: Graph centrality — confirmed, strongest cross-domain evidence

Validates our **Structural Importance** metric.

- TextRank (Mihalcea & Tarau, EMNLP 2004, https://aclanthology.org/W04-3252/) and LexRank (Erkan & Radev, JAIR 2004, https://arxiv.org/abs/1109.2128): a chunk is important if many important chunks relate to it.
- Formula: `S(Vi) = (1-d) + d * Σ_j [w_ji / Σ_k w_jk] * S(Vj)`, damping d = 0.85, converges in 20-30 iterations at threshold 0.0001.
- Confirmed claim: domain- and language-agnostic because fully unsupervised — no annotated corpora, no domain features.
- Parameterized by design: the application chooses what a node is (word, sentence, chunk, entity) and what an edge means (cosine similarity, co-occurrence, shared entities). Our k-NN embedding graph is exactly this pattern.
- Caveat from knowledge-graph research (GENI, KDD 2019, https://arxiv.org/abs/1905.08865; MultiImport, https://arxiv.org/abs/2006.12001): pure PageRank/degree underperforms on heterogeneous graphs because it ignores node/edge types; the fix is learning importance from whatever behavioral signal the deployer supplies (pageviews, votes) — configurable, not hardcoded.

## Signal: Information-theoretic surprise relative to a configurable background

Validates our **Novelty** metric and gives it a theoretical upgrade.

- Peyrard, "A Simple Theoretical Model of Importance for Summarization" (ACL 2019, https://aclanthology.org/P19-1101/): importance is only definable **relative to background knowledge K**. Decomposes into Redundancy, Relevance, Informativeness; unified as `P_{D/K}(ω) ∝ d_ω^α / k_ω^β` — frequent in the source, rare in the background — with tunable α/β and K as a free parameter.
- Setting K to a user profile, a query, or previously-seen documents makes the same formula personalized, query-focused, or update-oriented. This is the cleanest academic answer to per-user importance configuration.
- Simpler instances: SumBasic (average word frequency scoring), KLSum (minimize KL(source || selection)) — Haghighi & Vanderwende 2009, https://aclanthology.org/N09-1041.pdf. Same paper: spread across multiple documents beats repetition within one document — direct support for our **Recurrence** metric.
- Warning (Louis & Nenkova 2009, https://aclanthology.org/D09-1032/): JS-divergence correlates 0.88 with human judgments at the system level but is unreliable per individual chunk — distributional signals work on average, not per-item. Do not use as the sole per-chunk score.

## Signal: LLM-as-judge with an anchored rubric

Matches our **Actionability** conclusion: semantic importance needs an LLM, second stage.

- Generative Agents (Park et al. 2023): rate each memory 1-10 with anchored examples ("1 = mundane, ate lunch; 10 = major life event"); retrieval score = `α_rec * recency + α_imp * importance + α_rel * relevance`.
- Domain-agnostic because criteria live in the prompt — the rubric prompt is the natural user-config surface. Mem0 works the same way: no numeric formula, an LLM extraction prompt decides salience.
- Documented weakness: the fixed α weights are suboptimal across tasks.

## Signal: Learned multi-factor value function

- arXiv 2606.12945: `V(m) = Σ_i w_i * f_i(m)` over seven psychology-grounded factors (emotional intensity, goal relevance, self/user relevance, task utility, reliability, usage history, ...), weights fitted per workload from a downstream objective.
- Results: learned weights retain 0.77 of gold evidence vs 0.66 uniform weights vs 0.52 best single factor vs 0.37 recency-only. A neural net over the same factors does no better than the linear model.
- Methodological point: evaluate importance **blind** to the future query, otherwise plain embedding similarity trivially wins (~0.98) and no multi-factor advantage is measurable.

## Contrarian result to respect

- Kedzie et al. (EMNLP 2018, https://arxiv.org/pdf/1810.12343) and follow-ups: learned importance models transfer poorly across domains (news models fail on Reddit; ~50% is state of the art for domain-independent accuracy); in news, models mostly learn position bias.
- Implication: do not train a single supervised importance model. Keep the hardcoded part limited to unsupervised signals (centrality, informativeness); expose the rest (rubric, weights, background corpus K) as configuration.

## Mapping to our toolbox

| Our metric | Literature backing |
|---|---|
| Novelty | Peyrard informativeness vs background K; SumBasic/KLSum |
| Structural Importance | TextRank/LexRank centrality (confirmed) |
| Recurrence | Cross-document spread > within-doc frequency (Haghighi & Vanderwende) |
| Temporal Profile | Recency term in Generative Agents; weakest single factor (0.37) in the learned-value study |
| Actionability (2nd stage) | LLM rubric scoring (Generative Agents, Mem0) |
| Combination philosophy | Linear `Σ w_i f_i` with configurable weights beats any single signal and beats uniform weights |

## Suggested scoring shape

`importance(chunk) = w1 * centrality + w2 * informativeness_vs_K + w3 * llm_rubric_score + w4 * recurrence + w5 * temporal`

with `{w_i, rubric prompt, background corpus K}` as per-user configuration, defaulting to uniform weights and a generic rubric.
