# Rebuilt tree on BC Registries: agent test setup, reviewed before the run

The E050 rebuild (`~/hrono-eval/db/hrono-v2.db`, server on port 8789,
profile `v2`) is tested with the agents evaluation's harness
(`../2026-10-bc-registries-agents/`). Before the full run, this page shows
exactly what an agent is given, and the problems a 2-question pilot found.
Nothing here has been run on all 36 questions.

## The tree under test

- Built 2026-10-12 by one `maintain` (job `job_77ea57df…`), hrono at
  `90b26fe`: condense `purpose-decisions`, leaf brief `core-states`, upper
  brief `area-flows`, granite embeddings, clustering on condensation plus
  folders.
- 8,459 sections in 443 leaves, under 23 level-1 nodes, under 3 level-2
  nodes, under the root.
- Export: `h2 tree export bcreg --out ~/hrono-eval/export-bcreg-v2`, written
  from the rebuilt tree after the build. The default `--levels 4`, the same
  as the old run's `export-bcreg`: root → 3 → 23 → 443 brief pages, each
  leaf page linking its source sections. One page lists 82 entries, over the
  exporter's 40-entry budget.

## What an agent is given

All arms: Claude Code, Sonnet, headless, `--safe-mode`, 50 turns at most,
no Edit, Write, Web or Task tools. The code is the four repositories at the
snapshot commits, without git history (`~/hrono-deep/corpus`).

System prompt, every arm:

> You are a senior software engineer working in the BC Registries codebase
> (the British Columbia business registry). The current directory holds four
> repositories: lear/ (legal-api, colin-api, queue services, jobs), sbc-auth/
> (auth-api, auth-web), sbc-pay/ (pay-api, pay-queue, bcol-api, jobs) and
> business-filings-ui/ (Vue front end). You may only read; do not modify
> files.

Task, every arm:

> Question about this codebase:
> {question}
>
> Investigate with your tools as much as you need, then reply with only the
> final answer: precise, naming the concrete components (modules, classes,
> functions, queues, endpoints) and their file paths relative to the current
> directory, at most 400 words.

| arm | runs in | tools | added to the task |
|---|---|---|---|
| `repo` (old run, reused) | the code | Read, Grep, Glob, read-only shell | nothing |
| `hrono-v2` | the code, export added with `--add-dir` | the same, plus `h2 recall` | the paragraph below |
| `tree-v2` | the export, no code | Read, Grep, Glob, `h2 recall` | the tree-only paragraph below |

`hrono-v2` paragraph:

> A hierarchical knowledge base of this codebase is available, built by
> hrono:
> - {export}/root.md is the root of a tree of topic briefs (LLM-written
>   summaries of the code). Each brief links down to narrower briefs and, at
>   the bottom, to the source sections it summarizes.
> - `h2 recall bcreg "<question or keywords>"` prints the source passages
>   and summaries most relevant to a query. A source passage is labelled
>   git:///.../mirror/<repo>/<path>@<commit>; that file is at <repo>/<path>
>   in the current directory.
>
> Before searching the code you MUST start from this knowledge base: run
> recall at least once and read root.md and the briefs beneath it that cover
> the task, to learn which components are involved and where they live.
> Then verify in the code.

`tree-v2` paragraph:

> You do NOT have the source code. You have only hrono's knowledge base of
> it, in the current directory:
> - root.md is the root of a tree of topic briefs (LLM-written summaries of
>   the code). Each brief links down to narrower briefs and, at the bottom,
>   to the source sections it summarizes.
> - `h2 recall bcreg "<question or keywords>"` prints the source passages
>   and summaries most relevant to a query.
>
> Answer from these alone; navigate the tree and run recall as much as you
> need.

The answer is scored by Opus against the question's verified facts (1
stated, 0.5 partly, 0 missing), blind to the arm.

## Problems found

1. **Recall is gated for MiniLM, and now answers almost nothing to a
   question.** A passage qualifies at vector z ≥ 3.2 with keyword support,
   or z ≥ 4.5 without (`recall/vector_leg.py`), floors swept on MiniLM.
   Granite's similarities are flatter, so far fewer passages clear them:

   | query | old tree (MiniLM): z ≥ 3.2 / ≥ 4.5 | new tree (granite) |
   |---|---|---|
   | "payment confirmation paid invoice applies filing to business; future effective filing" | 426 / 3 | 18 / 0 |
   | "How does an account get locked after a bounced payment and how is it unlocked?" | 950 / 83 | 486 / 4 |
   | "entity filer worker" | 467 / 44 | 358 / 19 |

   The first query returns "No confident matches - explore the map." on the
   new tree. Short keyword queries still work.
2. **The code-plus-tree agent barely uses the tree.** In both pilot runs it
   ran recall once, printed the first 60 lines of `root.md`, and then only
   grepped and read code. It never opened a brief below the root. The
   instruction says to read "the briefs beneath it that cover the task", but
   nothing checks it, and grep is faster.
3. **The tree-only agent's system prompt is wrong.** It says "The current
   directory holds four repositories", but in that arm the current directory
   is the export.
4. **Nothing tells the agent what a brief holds.** The new briefs have a
   fixed order (contract, decisions, hazards, sources to open first) and the
   upper briefs list flows; the prompt describes them only as "LLM-written
   summaries". On `pay-3` the tree-only agent ran recall six times and never
   opened a brief.

## What each pilot agent did

### `hrono-v2` on `pay-3` (13 turns, coverage 0.67; code alone 1.00)

1. recall "account freeze lock NSF bounced debit overdue EFT statement block
   payments", and the first 60 lines of root.md
2. to 12. grep and read in `sbc-pay` and `sbc-auth`

### `hrono-v2` on `lear-filings-1` (11 turns, 0.57; code alone 0.57)

1. recall "payment confirmation filing processor applies filing to
   business; future effective filing", and the first 60 lines of root.md
2. to 10. `ls`, `cat`, `grep` and `sed` in `lear/queue_services`,
   `lear/jobs` and `legal-api`

### `tree-v2` on `lear-filings-1` (7 turns, 0.64; old tree alone 0.36)

1. recall (no confident matches)
2. grep root.md for payment, future, pay-queue, filer
3. the "pay and filing queue system" brief
4. the "entity filing" and "queue services" briefs below it
5. the business-pay, payment and entity-pay leaf briefs, and the
   future-effective brief
6. the entity-filer leaf brief

### `tree-v2` on `pay-3` (8 turns, 0.58; old tree alone 0.58)

1. to 7. recall, six times, with ever more specific identifiers
   (`NSF_SUSPENDED`, `publish_lock_account_event`, `has_overdue_invoices`,
   `unlock_frozen_accounts`); no brief opened

## Before the full run

- Recalibrate recall's floors for granite (or per model), on the same
  probes the MiniLM floors were swept on.
- Fix the tree-only system prompt.
- Decide how the code-plus-tree agent should be told to use the tree, and
  whether to describe the brief layout.

## Round 2: 5 questions, 2026-10-12

Run after the fixes above: system prompt with only the code's path, the
3-level export (`export-bcreg-v2-L3`), recall attached by hrono's Claude Code
plugin (hooks, no recall command), recall at `c0f637d` (cosine plus word
gate), instructions in the user prompt. Arms `code-r2`, `hrono-r2`,
`tree-r2` in `../2026-10-bc-registries-agents/harness/run_arms.py`. Fact
coverage, scored by Opus as in the first run; the first run's arms (`repo`,
`hrono`, `tree`: old tree, old recall, repository descriptions in the system
prompt) on the same questions for comparison.

| arm | lear-filings-1 | pay-3 | auth-0 | ui-0 | cross-0 | mean | errors | turns | cost |
|---|---|---|---|---|---|---|---|---|---|
| code only, first run | 0.57 | 1.00 | 0.86 | 0.86 | 0.56 | 0.77 | 0 | 12 | $0.75 |
| code + old tree | 0.50 | 0.67 | 1.00 | 0.57 | 0.50 | 0.65 | 1 | 8 | $0.64 |
| old tree only | 0.36 | 0.58 | 0.50 | 0.50 | 0.44 | 0.48 | 2 | 7 | $0.67 |
| code only, round 2 | 0.50 | 0.83 | 1.00 | 0.86 | 0.62 | 0.76 | 0 | 16 | $1.15 |
| code + new tree | 0.64 | 0.75 | 0.86 | 0.86 | 0.62 | 0.75 | 0 | 12 | $0.94 |
| new tree only | 0.64 | 0.58 | 0.71 | 0.57 | 0.62 | 0.63 | 1 | 10 | $0.84 |

- The tree alone went from 0.48 to 0.63. On the two flow questions
  (`lear-filings-1`, `cross-0`) it matches or beats the code.
- Code plus tree went from 0.12 below code alone to level with it (0.75
  against 0.76), in 12 turns instead of 16 and 18% cheaper.
- Recall was attached to every run. The code-plus-tree agent opened the map
  on 3 of 5 questions (none on `auth-0` and `pay-3`).
- Five questions: a difference under about 0.1 is noise.
