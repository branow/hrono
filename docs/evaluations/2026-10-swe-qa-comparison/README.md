# Evaluation: hrono against other LLM knowledge bases on SWE-QA (October 2026)

The first head-to-head comparison of hrono with other tools that build a
knowledge base over a corpus for an LLM to answer from. It uses a published
benchmark with reference answers, so the scores do not depend on questions
written for hrono. This folder keeps the protocol, the code that ran it, the
raw answers and judgments, and the results.

- `README.md` (this file): question, design, controls, and how to rerun.
- `results.md`: the tables produced by `harness/analyze.py`, and the reading.
- `harness/`: every script the run used.
- `data/`: raw answers, judgments, call ledger and build stats (JSONL).

## The question

Given the same repository, the same answering model and the same context
budget, does hrono's knowledge base let an LLM answer real repository
questions better than (a) no retrieval, (b) standard lexical and vector RAG,
(c) RAPTOR, the published method closest to hrono's design (recursive
clustering and summarization into a tree), and (d) LightRAG, a widely used
graph-based RAG? And does giving a coding agent hrono's tree and recall make
it answer better or more cheaply than the same agent with only the code?

## Benchmark

[SWE-QA](https://arxiv.org/abs/2509.14635) (Peng et al., ACL 2026 Findings;
data and scripts at `github.com/peng-weihan/SWE-QA-Bench`): 48 curated
question-answer pairs per repository, mined from real GitHub issues, with
reference answers that cite files, classes and lines. 90.9% of its questions
need more than one reasoning hop and 77.6% need more than one file.

Three of its fifteen repositories were used, at the commits the benchmark pins:

| Repository | Commit | Files ingested | Size ingested | Why |
|---|---|---|---|---|
| pallets/flask | `85c5d93` | 221 | 1.14 MB | Small, famous (a memorization check) |
| psf/requests | `46e939b` | 117 | 0.63 MB | Small, famous |
| streamlink/streamlink | `ab1f365` | 605 | 3.46 MB | SWE-QA v2: chosen to be less known, larger |

That is 144 questions. Three repositories, not fifteen, because each tool
must index each repository with LLM calls, all of which go through one Claude
subscription and a three-hour window.

## Systems

| System | What it is | Index-time LLM | Retrieval |
|---|---|---|---|
| closed-book | No retrieval: the model answers from memory | – | – |
| bm25 | Okapi BM25 over line-aligned chunks of at most 800 chars, identifiers split on snake/camel case | – | top chunks |
| dense | The same chunks embedded with all-MiniLM-L6-v2 | – | cosine top chunks |
| raptor | RAPTOR (Sarthi et al., ICLR 2024), official code `parthsarthi03/raptor@7da1d48`: UMAP + GMM soft clustering and recursive summaries over the same chunks | Sonnet (summaries) | collapsed tree: every node ranked by cosine |
| lightrag | LightRAG (`lightrag-hku` 1.5.7): entity/relation graph extraction, hybrid (local + global) retrieval. **Indexing stopped for cost; unscored** (see results) | Haiku (extraction, query keywords) | its own hybrid context |
| hrono | hrono at `120d85f`: a cold `hrono tree maintain` per repository, then `POST /trees/{repo}/recall` | Haiku (condense), Sonnet (briefs) | recall, at most 10 passages |
| agent-repo | Claude Code, Sonnet, headless, tools Read/Grep/Glob over the checkout | – | the agent searches |
| agent-hrono | The same agent plus the exported hrono tree (`hrono tree export`) and `hrono recall`, offered as optional | (hrono's build) | the agent searches and navigates |
| agent-hrono-first | As agent-hrono, but told it must run recall and read the tree before searching the code | (hrono's build) | the same |

The LLM choices mirror hrono's own configuration: the bulk, per-chunk work
(hrono's condense, LightRAG's extraction) runs on Haiku, and summaries meant
to be read (hrono's briefs, RAPTOR's summaries) on Sonnet.

## Controls

Everything that is not the system under test is held fixed:

- **Same files.** Every system indexes exactly the files hrono ingested
  (taken from hrono's `sections` table), so hrono's ignore rules apply to all.
- **Same embedding model.** all-MiniLM-L6-v2 for every dense component
  (hrono, dense, RAPTOR, LightRAG), on CPU.
- **Same chunk size.** 800-character line-aligned chunks for bm25, dense and
  RAPTOR's leaves, matching hrono's ~800 B passage target. RAPTOR's own
  sentence splitter splits on `.` and would shred code, so it was replaced;
  its clustering and summarization are unchanged. LightRAG keeps its own
  chunker (it is part of the method).
- **Same context cap.** At most 8,000 characters of retrieved context per
  question, ranked chunks taken in order. The cap was sized to hrono's recall
  (at most 10 passages of ~800 B). A system may return less; hrono often does.
- **Same answer step.** Claude Sonnet through the Claude CLI, in the same
  isolated mode hrono's `claude-code` provider uses (`--safe-mode`, replaced
  system prompt, no tools), with SWE-QA's own system prompt and one shared
  answer template ("at most 300 words").
- **Same judge, blind.** SWE-QA's own LLM-as-a-judge prompt, read verbatim
  from the benchmark's `llm-as-a-judge.py` at run time: correctness,
  completeness, relevance, clarity and reasoning, each 1–20, total 100.
  The judge sees only the question, the reference and the candidate, never the
  system. The benchmark used GPT-5 as judge; here it is Claude Sonnet, so
  absolute scores are not comparable with the paper's, only with each other.
- **Same agent setup.** Both agent arms use the same model, system prompt,
  40-turn limit, task text and tools; agent-hrono only adds a paragraph
  pointing at the tree and the recall command. Both run on the same fixed
  subset: every third question per repository (48).
- **Reproducible calls.** Every LLM call is cached on disk by its exact
  inputs, so a rerun reproduces it; every real call is logged with tokens,
  time and API-equivalent cost (`data/calls.jsonl`).

## Measures

- **Judge score** (0–100), mean with a 95% bootstrap CI.
- **Paired comparison** against hrono on the same questions: mean difference
  with a paired bootstrap CI, wins/ties/losses, two-sided Wilcoxon
  signed-rank p, Holm-corrected across comparisons.
- **File recall** (judge-free): of the repository paths a reference answer
  cites, the fraction that appear in the context the system handed the
  answerer.
- **Cost**: index-time LLM calls, tokens and model time; per-question agent
  turns, tokens, wall time and API-equivalent cost.

## Rerun

The harness expects the workspace layout it ran in (`~/hrono-bench`): the
SWE-QA-Bench clone, the three repositories at their pinned commits with bare
mirrors that hrono's git sources point at, a `raptor/` checkout, and a hrono
server on port 8788 with the three trees built.

```sh
cd harness && uv sync
uv run python build_raptor.py flask requests streamlink
uv run python lightrag_adapter.py build flask requests streamlink
uv run python run_eval.py answer hrono closed-book bm25 dense raptor lightrag
uv run python run_agents.py agent-repo agent-hrono agent-hrono-first
uv run python run_eval.py judge hrono closed-book bm25 dense raptor lightrag agent-repo agent-hrono agent-hrono-first
uv run python analyze.py > ../runs/results.md
```
