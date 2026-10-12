# Recall queries: does cutting the prompt into pieces help?

Pilot, 2026-10-12, on the rebuilt `bcreg` tree (`~/hrono-eval/db/hrono-v2.db`,
granite). hrono's Claude Code plugin recalls on the whole prompt, and a prompt
is often a question plus instructions. This tries mechanical ways (no model
call) to turn a prompt into recall queries, each recalled with hrono's own
legs and floors, the hits merged round-robin, one per file.

5 architecture questions (`lear-filings-1`, `pay-3`, `auth-0`, `ui-0`,
`cross-0`), each in 4 shapes: the bare question; with the agents
evaluation's answer-format paragraph; with that and a map instruction; and
wrapped in a chatty message. A prompt is FOUND when a top-5 hit is a file
the question's verified facts cite, or a leaf brief over one. 5 off-topic
questions should return nothing.

| strategy | found | bare | task | task+map | chatty | files covered | off-topic leaks |
|---|---|---|---|---|---|---|---|
| `whole` (today) | 10/20 | 2/5 | 3/5 | 2/5 | 3/5 | 0.13 | 1/5 |
| `split-all`: every sentence a query | 7/20 | 2/5 | 2/5 | 1/5 | 2/5 | 0.08 | 1/5 |
| `split-filter`: instruction sentences dropped | 8/20 | 2/5 | 2/5 | 2/5 | 2/5 | 0.13 | 1/5 |
| `filter-join`: dropped, the rest one query | 8/20 | 2/5 | 2/5 | 2/5 | 2/5 | 0.13 | 1/5 |
| `filter-join+names`: plus identifiers as a query | 8/20 | 2/5 | 2/5 | 2/5 | 2/5 | 0.13 | 1/5 |
| `clauses`: sub-questions cut at "and how…" | 8/20 | 2/5 | 2/5 | 2/5 | 2/5 | 0.12 | 1/5 |

## Reading

- **Instructions do dilute the query**, and filtering them out restores it:
  the best vector z drops on every question when the format and map text is
  added (`lear-filings-1` 3.65 bare, 3.12 with the format, 3.04 with the
  map), and `filter-join` scores exactly what the bare question scores.
- **But the bare question itself is found 2 times in 5.** Shaping the query
  cannot fix that; the limit is past the query:
  - `pay-3` and `ui-0` are found: an answer file ranks 1st and 3rd.
  - `auth-0`: the first answer passage ranks 18th of 42 that qualify.
  - `cross-0`: nothing qualifies; the best z is 3.16, and answer files sit
    at rank 37.
  - `lear-filings-1`: the best z is 3.65, and the answer files are not near
    the top.
- **Splitting into sentences loses**: each piece carries less of the
  question than the whole, and round-robin gives weak pieces equal slots.
- **The vector z cannot tell on-topic from off-topic.** Off-topic questions
  reach a top z of 3.9 to 4.8, above several real questions (3.1 to 5.2).
  Only keyword corroboration separates them, and narrowly: the best
  corroborated z is at most 2.85 off-topic and at least 2.78 on-topic.
- `whole` scoring 10 against 8 is two prompts on 5 questions: noise.

## The new formula

`harness/diagnose.py` showed plain semantic search was not the problem:
with granite, plain cosine put an answer file in the top 5 for 3 of the 5
questions (MiniLM: 1). hrono's recipe lost them: its z-score floors (3.2
with keyword support, 4.5 without) were calibrated on MiniLM, whose top
passages score z 4 to 7, while granite's score 3 to 5; and its path-string
blend lifted files whose path matched the question over the answers
(`auth-0`: 4 answer files in plain cosine's top 10, none in hrono's).
`harness/formulas.py` compared replacements:

| formula | found (20 prompts) | files covered | off-topic leaks |
|---|---|---|---|
| hrono's recipe | 8 | 0.13 | 1/5 |
| cosine | 12 | 0.21 | 5/5 |
| cosine + word gate | 12 | 0.21 | 1/5 (0 at a higher bar) |
| cosine + BM25 (RRF) | 12 | 0.20 | 5/5 |

Adopted in `c0f637d`: if at least 90% of the question's content words occur
in the tree (matched by stem), return the passages closest by cosine, one
per file; otherwise send the agent to the map. On bcreg all 36 architecture
questions have 0.95 or more of their words in the tree; 9 of 10 off-topic
questions 0.80 or less.

Through `hrono recall` on the rebuilt tree every one of the 5 questions now
returns 5 passages, and "How do I knit a cable stitch?" returns the explore
message. Test files still take many of the top slots (4 of 5 for
`lear-filings-1`), because a test reads like a question about its code.

The harness scripts import recall's legs as they were before `c0f637d`
(`queries.py`, `diagnose.py`); run them at `4f1de53^`.

## Next

- In the plugin, drop instruction sentences before recalling: cheap, and it
  gives the bare question's quality back to a prompt with instructions.
- The real gap is ranking and gating for long, conceptual questions. That
  is recall's own design (floors, corroboration, what a brief passage
  competes against), not the query.

## Reproduce

```
cd harness
uv run python queries.py ~/hrono-eval/db/hrono-v2.db
```
