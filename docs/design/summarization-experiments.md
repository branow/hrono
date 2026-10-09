# Summarization experiments — history and conclusions

How we arrived at the node-summarization recipe (2026-07-12). Prototype code in `prototype/summarize_experiments.py` (all prompts ever tried live in its `PROMPTS` dict with per-round comments; the active matrix selects what runs). Every run's full request/response/cost is browsable in `(prototype data, not kept) app/.hrono/summarization-experiments/report.html` (regenerate: `uv run python build_report.py`, no args; it also auto-regenerates after every experiment run).

## The chosen recipe (current favorite)

**Two-layer, gotcha-aware, content-addressed:**

1. **Map (per file, Haiku):** condense each chunk to its essential information — length follows content density (boilerplate collapses to one line, dense logic keeps what it needs), identifiers/values copied VERBATIM (never inferred), plus `GOTCHA:` lines for anything non-obvious a newcomer could be hurt by. Results cached by chunk **content hash** — an unchanged file is never re-condensed, which makes cluster rebuilds incremental (only new/changed files pay map cost; same pattern as the embeddings table).
2. **Reduce (per cluster, Haiku; Sonnet for messy clusters):** the "adaptive" prompt over the condensations — state what the group is as a whole, find the natural groupings actually present (never force a structure; must work for code/config/translations/prose alike), concrete names, compress near-identical chunks into pattern+variations — ending with a **Caution section** aggregating the map-stage gotchas (omitted when there's nothing to warn about).
3. **References are mechanical:** chunk URIs appended by code from cluster metadata, never LLM-written (no tokens, no hallucination). Not embedded in the summary text during experiments.

Why this shape won:
- **Genericity:** the adaptive prompt found layers in code, languages in translations, build systems in configs — without naming any of them (a prompt that listed code layers was tried and rejected).
- **Incrementality:** per-file condensations keyed by hash = compute once ever; rebuild cost is one cheap reduce.
- **Cost:** Haiku map ≈ $0.015/file (once), Haiku reduce ≈ $0.03–0.09/cluster, Sonnet reduce ≈ $0.05–0.15 (its premium applies to already-shrunk input). Sonnet-on-raw was $0.14–0.42.
- **Gotcha surfacing (two-layer beats single-pass):** per-file map attention found MORE real hazards (9 vs 5 on the test cluster) than one pass over the raw cluster; the reduce curates the noisy over-collection. Verified catches on webphone Contact code: non-transactional batch insert, silent no-op delete, case-sensitivity asymmetry in search, empty keyword → match-all `.*` regex, find/count pagination race.
- **Composition upward works:** summarizing the six node summaries produced a good parent node (~$0.10) with per-child discriminative lines — the tree's core assumption, validated ("cluster-100" in the report).
- **Faithfulness is checkable mechanically:** `prototype/check_faithfulness.py` extracts identifier-like tokens from every generated text and verifies each literally exists in the source (case-insensitive, labels count, slash-compounds split). Caught a real fabrication class early; after the map-prompt fix the corpus's only distortion was one word ("OneDevOps" for "OneDev").

## Experiment history (6 rounds, ~90 recorded runs over 6 sample clusters + 1 synthetic)

Sample clusters (extracted in `(prototype data, not kept) app/.hrono/summarization-samples/`): 14 = coherent business logic (Contact vertical slice), 0 = near-duplicate translations, 36 = build configs, 4 = 28 HTML templates, 19 = tiny/tight (5 SIP DTOs), 35 = low-coherence grab-bag. Backend: Claude Agent SDK (`claude_agent_sdk.query`, subscription auth, tools/settings disabled, fresh temp cwd).

- **Round 1 — literature baselines (Sonnet, cluster 14).** RAPTOR-minimal vs GraphRAG-structured (title/overview/per-chunk references) vs two-stage map-reduce, at 500/1500-token budgets. Learned: structured gives the routing shape; two-stage 4x cheaper; token budgets in prompts are ignored (~2x overruns); manual review preferred the *organically discovered* structure of the naive-1500 output over the imposed template.
- **Round 2 — "freeform layered" (Sonnet/Haiku × raw/condensed, cluster 14).** Encoded the preferred shape. Learned: Haiku holds up on raw input; **first real fabrication found** — the 120-token-capped condensation invented "photo max 512 chars", and the reduce model propagated it (it never sees the source). Prompt REJECTED for hardcoding code-specific layers (controller/DTO/mapper) — clusters can hold anything.
- **Round 3 — content-agnostic prompts (plain/adaptive/routing × Haiku/Sonnet, clusters 14/0/36).** **adaptive** wins on genericity; routing is compact but lossy (possibly right for higher tree levels); plain is a decent baseline. Also: references became mechanical; all prompts/responses recorded for the report from here on.
- **Round 4 — multi-step & structured (all 6 clusters).** refine (draft→check-against-source), outline (inventory→write), json (machine-usable record), and the condensed pipeline rerun after fixing the map prompt (**no token cap — length follows density; identifiers verbatim**). Learned: fabrication class eliminated (verified); refine/outline double cost without visible wins over single-call adaptive; skip-if-exists added so reruns only fill gaps.
- **Round 5 — routing-oriented ideas (agent-explored, clusters 14/35 + synthetic).** Three prototyped: **level2** (summarize the summaries) — WORKS, kept for parent nodes; **contrast** (sibling-aware, "Not here: X is in cluster-36") — quality was good but REJECTED: circular dependency between sibling summaries, only exists at regeneration time; **questions** (question-first framing) — boosted Haiku's identifier precision but the "Answers questions like:" section was disliked; REJECTED as a section (the precision trick may be worth folding into prompts later). Not pursued: self-consistency (cost multiplier for variance reduction we don't need), importance-weighted condensation (no strong per-chunk signal available), extractive-then-abstractive (overlaps outline+verbatim condensation).
- **Round 6 — gotchas (cluster 14, Haiku).** Motivation: legacy systems hide illogical, bug-prone decisions; the summary must move them UP the abstraction so an agent is warned without reading source. Tested dedicated-pass vs integrated Caution section on raw input (both caught all 3 known quirks; integrated version was all-signal and free), then **through the two-layer pipeline** (map prompt collects `GOTCHA:` lines per file, reduce aggregates) — which beat single-pass recall. Adopted into the recipe.

## Rejected, with reasons (don't retry blindly)

- Prompt-level size budgets (ignored; and size doesn't matter much — nodes just need to stay smaller than raw content).
- LLM-written reference lists (mechanical from metadata instead).
- Code-specific vocabulary in any prompt (breaks non-code clusters).
- Hard token caps in the map stage (starves dense files, *causes* fabrication).
- Contrast/sibling-aware summaries (circular dependency across siblings).
- "Answers questions like:" sections (disliked; adds noise).
- refine/outline pipelines (2x cost, no visible quality win over single-call adaptive).

## Open items

- **The real eval** — candidates are now too close for eyeballing: fixed per-cluster question sets (stratified detail vs conceptual), routing accuracy (selector over all node summaries picks the right cluster), G-Eval-style judge with rank-correlation calibration against manual ranking, faithfulness gate. Designed but not built.
- Model routing by cluster coherence (stored in `clusters.json`): Haiku reduce for tight clusters, Sonnet for messy ones — cheap heuristic, untested.
- json output shape for direct `nodes`-table insertion (worked; revisit when building the tree).
- Level-2+ prompts probably want the compact "routing" flavor rather than full adaptive — untested.
- Faithfulness checker has residual false-positive noise on prose slash-compounds; tighten only if it starts being used as a gate.
