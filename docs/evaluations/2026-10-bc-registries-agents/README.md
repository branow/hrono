# Evaluation: agents with and without hrono on BC Registries (October 2026)

The SWE-QA comparison (`../2026-10-swe-qa-comparison/`) used small, famous
repositories and pinpoint questions. Models already know those repositories,
and grep finds the answers, so neither a RAG index nor a knowledge tree had
room to help. This evaluation fixes both problems:

- **The corpus is large and unknown.** BC Registries is four `bcgov`
  repositories, about 5,200 files in the checkout, with 10–21 GitHub stars
  each. The test runs at the snapshot hrono's tree `bcreg` was built from,
  2024-09-27 (see `../2026-10-bc-registries/`).
- **The questions need knowledge spread over many files.** There are two
  sets: real change requests, and architecture questions. Neither was
  written from hrono's output.

This folder holds:

- `README.md` (this file): the design.
- `results.md`: the findings.
- `harness/`: every script the run used.
- `data/`: the questions, every agent transcript summary, the scores and the
  call ledger.

## The questions

### Set 1: change localization (`data/locate.json`, 40 items)

This set is judge-free, and its answer key comes from history rather than
from an LLM.

1. `mine.py` lists the commits on each repository's main branch from
   2024-09-28 to 2025-04-30, that is, after the snapshot. It keeps those that
   modify 3–15 non-test source files that already existed at the snapshot,
   in at least 2 directories. That gave 153 commits.
2. `describe.py` passes each commit's diff, without tests, to Opus. Opus
   decides whether the commit is one coherent change, and keeps 143 of the
   153. For each kept commit, Opus writes the change request a developer
   would have been given, with no file, path, identifier or ticket names in
   it.
3. A seeded, stratified sample of commits that modify at least 4 files gave
   40 items: lear 14, sbc-auth 11, sbc-pay 11, business-filings-ui 4. Each
   item modifies 6.3 files on average.
4. The agent receives the change request and replies with up to 12 existing
   files it would modify. Its list is scored against the files the commit
   really modified, using recall, precision and F1.

### Set 2: architecture (`data/arch.json`, 36 questions)

1. `gen_questions.py` runs six Opus agents, one per area: lear filings, lear
   async/jobs, auth, pay, UI, and cross-repository. Each one explores the
   checkout with Read, Grep and Glob, never hrono. Each writes 6 questions
   of three kinds:
   - flow (14 questions): how something works end to end;
   - concept (12 questions): how a rule is modeled and enforced;
   - change (10 questions): where a change goes and what it affects.
   Every question needs at least 4 files to answer. Each answer is 4–8 key
   facts, and each fact cites the files that prove it.
2. `verify.py` runs a fresh Opus agent that checks every fact against the
   code. Of the 238 facts, 221 were marked correct and 17 partly correct; the
   partly correct ones were replaced by the verifier's corrected wording. No
   fact was wrong, so all 36 questions were kept.
3. `score.py` uses Opus as the judge, blind to the arm. For each reference
   fact, the judge gives 1 if the answer states it, 0.5 if it states it
   partly, and 0 if it is missing or contradicted. It also counts the
   answer's errors, meaning claims that contradict a fact. The question's
   score is its fact coverage, the mean of those per-fact scores.

## Arms

All arms use Claude Code with Sonnet, run headless with `--safe-mode`. They
share the same system prompt, the same task text and a 50-turn limit. They
run in a copy of the four repositories at the snapshot commits, extracted
with `git archive` and therefore without git history, so an agent cannot
read the answer from later commits.

| Arm | Code | hrono | Tools |
|---|---|---|---|
| repo | yes | – | Read, Grep, Glob, read-only shell |
| hrono | yes | export of `bcreg` plus `hrono recall bcreg`; must start from them | the same, plus the recall command |
| tree (diagnostic, set 2 only) | no | the export and recall only | Read, Grep, Glob, the recall command |
| none (floor, set 2 only) | no | – | none, a single completion |

The `tree` arm measures what the knowledge base itself knows. The `none` arm
checks how much a model can answer from training and general guessing.

A first run of set 1 was discarded. In that run, the hrono arm had the
shell but the repo arm did not, and the hrono arm grepped through the shell
without ever calling recall. Both arms now have the read-only shell, and the
hrono arm is told it must start from recall and the briefs.

## Statistics

Each mean is reported with a 10,000-resample bootstrap CI. The arms are
compared in pairs on the same questions, using a paired bootstrap CI and a
Wilcoxon signed-rank test. Every LLM call is logged with its tokens and its
API-equivalent cost (`data/runs/calls.jsonl`); the run's total was 67.5M
tokens and $60.

## Rerun

The workspace was `~/hrono-deep`, alongside the stage 1 workspace
`~/hrono-eval`, whose server must be running with tree `bcreg`.

```sh
python3 mine.py && python3 describe.py && python3 sample.py   # set 1
python3 gen_questions.py && python3 verify.py lear-filings lear-async auth pay ui cross
python3 run_arms.py locate repo hrono
python3 run_arms.py arch repo hrono tree && python3 closed_book.py
python3 score.py locate repo hrono && python3 score.py arch repo hrono tree none
uv run --project ~/hrono-bench/harness python analyze.py
```
