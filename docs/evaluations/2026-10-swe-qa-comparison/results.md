# Results: hrono vs. other LLM knowledge bases on SWE-QA

Run 2026-10-10, hrono at `120d85f`. Protocol in [README.md](README.md); the
full generated tables are in `data/results.md` and
`data/results-streamlink.md`. Judge scores are 0–100 (SWE-QA's five 1–20
dimensions, Claude Sonnet as judge).

## Summary

1. **As a single-shot retriever, hrono is level with standard vector RAG and
   with RAPTOR, and it does that on about half the context.** Over all 144
   questions, hrono 67.5, dense 67.5, RAPTOR 67.2, BM25 65.7. None of the
   paired differences against hrono is significant (Holm p ≥ 0.26). hrono
   handed the answerer 4,170 characters on average, against the 8,000-character
   cap the others filled.
2. **Where retrieval matters, every retriever helps and hrono is in the top
   group.** Flask and requests are memorized: the model with no retrieval at
   all (70.1 overall; 76.6 and 78.9 on those two) beats every RAG system
   there, because 8 KB of excerpts crowd out what it already knows. On
   streamlink, the less-known repository, retrieval wins: RAPTOR 63.0,
   hrono 61.8, dense 60.4, BM25 56.6, closed-book 54.7. hrono beats
   closed-book by +7.1 points (95% CI +1.6 to +13.0) and BM25 by +5.2
   (+0.8 to +9.8). After Holm correction both are borderline (p = 0.064).
   hrono's differences from dense (+1.5) and RAPTOR (−1.2) are well inside
   noise.
3. **A tool-using agent beats every single-shot system by a wide margin, and
   hrono does not raise it further.** On the 48-question subset, the Claude
   Code agent with only the checkout scores 78.0, against 67.5–72.2 for every
   single-shot system (+5.7 to +10.4, all p < 0.001). Adding hrono's tree and
   recall changes nothing measurable: 77.4 when the agent may use them, and
   78.0 when it is told to start from them. Cost per question is also flat,
   or higher with hrono ($0.035 / $0.037 / $0.047).
4. **When the agent is free to choose, it ignores hrono.** In 48 runs the
   agent with hrono available called `hrono recall` once and never opened the
   exported tree; it greps instead. Told to start from hrono, it did: recall
   in all 48 runs and the tree in 40. It still scored the same, and it took
   longer. These questions are answered in 3–4 turns, so grep finds the code
   faster than a summary tree can route to it.
5. **The indexing cost ordering is clear: BM25 and dense are free, hrono and
   RAPTOR are moderate, LightRAG is not affordable.** hrono's three cold builds
   took 294 LLM calls and 0.83M output tokens (about 25 minutes of wall
   time). RAPTOR took about 1,300 summary calls and 0.57M output tokens.
   LightRAG was stopped after 85 extraction calls had produced 0.92M output
   tokens for 18 of flask's ~200 documents. That projects to about 10M output
   tokens for flask alone, more than ten times hrono's whole three-repository
   build, so it has no score.

## Single-shot, all 144 questions

| System | Score [95% CI] | Correctness | Completeness | File recall | Context chars |
|---|---|---|---|---|---|
| closed-book | **70.1** [67.4, 72.6] | 13.1 | 12.5 | – | 0 |
| hrono | **67.5** [65.0, 69.9] | 12.8 | 11.7 | 0.59 | 4,170 |
| dense | **67.5** [64.9, 70.0] | 12.8 | 11.8 | 0.75 | 7,975 |
| raptor | **67.2** [64.6, 69.5] | 12.6 | 11.7 | 0.70 | 7,983 |
| bm25 | **65.7** [62.8, 68.4] | 12.3 | 11.3 | 0.69 | 7,981 |

File recall is the fraction of the files cited by the reference answer that
appear in the context. It is measured on the 88 questions whose reference
cites a path; SWE-QA's streamlink references cite almost none. hrono's lower
recall is the cost of returning fewer passages; its score shows it chose them
well.

Paired against hrono (positive = hrono better): closed-book −2.6 [−5.1,
+0.1], Holm p 0.002; BM25 +1.9 [−0.2, +4.0], p 0.26; dense 0.0 [−2.1, +2.2],
p 1; RAPTOR +0.4 [−1.7, +2.5], p 1.

## By repository

| System | flask | requests | streamlink |
|---|---|---|---|
| closed-book | 76.6 | 78.9 | 54.7 |
| bm25 | 67.3 | 73.0 | 56.6 |
| dense | 68.7 | 73.5 | 60.4 |
| raptor | 65.9 | 72.5 | **63.0** |
| hrono | 67.7 | 73.1 | 61.8 |
| agent-repo (n=16 each) | 81.2 | 81.8 | 70.8 |
| agent-hrono (n=16 each) | 79.6 | 79.7 | 72.9 |
| agent-hrono-first (n=16 each) | 79.1 | 81.0 | 73.9 |

On streamlink both hrono arms are 2–3 points above the bare agent, but on 16
questions that is well inside noise.

## Agents (48 questions: every third per repository)

| Arm | Score [95% CI] | vs agent-repo | Turns | Wall s | $ / question |
|---|---|---|---|---|---|
| agent-repo | **78.0** [74.3, 81.1] | – | 3.9 | 11 | 0.035 |
| agent-hrono | **77.4** [74.3, 80.0] | −0.6, p 0.18 | 3.7 | 11 | 0.037 |
| agent-hrono-first | **78.0** [74.7, 80.6] | 0.0, p 0.19 | 3.6 | 15 | 0.047 |

## What this means for hrono

- **Recall's quality is competitive; its quantity is conservative.** It
  returned no passages at all on 21 of 144 questions (15%): 7 flask,
  8 requests, 6 streamlink. SWE-QA paraphrases away identifiers ("the
  framework's JSON serialization provider" for `DefaultJSONProvider`), and
  recall's corroboration rule (`vector_leg.qualify`) is designed to abstain
  when the question's words are not in the corpus. The cost here was small:
  questions where hrono returned nothing still scored 67.4, because the
  answerer fell back on memory. On an unknown private corpus, though, an
  abstention leaves the agent with nothing. A paraphrase or HyDE-style query
  rewrite before the vector leg is the obvious lever to test.
- **Briefs do surface in recall, but rarely.** 106 of 781 hits (14%) were
  brief passages; the rest were source. RAPTOR's collapsed tree ranks
  summaries alongside leaves the same way and edged hrono on the unknown
  repository (63.0 vs 61.8, not significant), so how much brief text recall
  admits is a knob worth an experiment.
- **The tree's value is not shown by this benchmark.** These are pinpoint
  questions that grep answers in a few turns. The tree should matter for
  questions with no greppable anchor (architecture, "where would I add X",
  cross-repository flows) and on corpora too large to grep. That claim stays
  open until it is measured; stage 4 of the BC Registries evaluation is the
  place to do it.
- **Bug found: hrono's `claude-code` provider leaves the CLI's tools
  enabled.** `--allowed-tools ""` only denies permission; the model still
  sees every tool. It tries to use them (`stop_reason: tool_use`), burns
  turns, and carries about 14–40k extra cached prompt tokens per call. The
  harness hit this on its first run, and it is the likely root of the
  `error_max_turns` failures in the BC Registries condense attempts.
  `--tools ""` removes the tools (1 turn, 0 cache tokens, verified). It is a
  one-line fix in `src/hrono/llm/claude_code.py`, not applied in this run, so
  the hrono numbers above were built with the bug in place.

## Threats to validity

- **Memorization.** Flask and requests are in every model's training data;
  only streamlink gives a clean read on retrieval, and it has 48 questions.
- **One judge, one sample.** The judge is Claude Sonnet, the same family as
  the answerer, with no second judge and one answer per question. It is the
  same for every system, so the comparisons hold, but absolute scores are not
  comparable with the SWE-QA paper's GPT-5-judged numbers.
- **Three of fifteen repositories, a 48-question agent subset.** Differences
  under about 3 points are not resolvable at this size.
- **Agent tool asymmetry.** agent-hrono's Bash permission was scoped to
  `hrono recall`, but Claude Code also auto-allows read-only shell commands
  (`sed`, `head`, `grep`), which agent-repo did not get. That favors the hrono
  arms slightly, and they still did not improve.
- **Index-time model calls ran before the `--tools` fix in the harness.**
  RAPTOR's flask and requests summaries and LightRAG's first calls were made
  with tools visible (they succeeded; only the token overhead differs). Every
  answer and judgment was made after the fix: the earlier answers were
  discarded and regenerated.
- **Usage limit.** The subscription's 5-hour window ran out partway through.
  The harness waited it out, retrying every 5 minutes, and no result was lost
  or partial (0 errors in every answer and judge pass).
- **LightRAG is unscored.** The reason is cost, not quality. Its index never
  finished.
