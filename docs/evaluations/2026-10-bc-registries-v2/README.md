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

## Why round 2 shows no clear gain: the 15 runs read one by one

Each question's runs were traced step by step, and every fact an arm missed
was looked up in the map and the code.

| question | code alone | what happened |
|---|---|---|
| `auth-0` invite flow | 1.00 | One well-named file (`invitation.py`); grep "invit" finds it. Code+map never opened the map, 5 turns instead of 21. The map holds the missed facts in front-end and helper leaves under other areas. |
| `pay-3` account lock | 0.83 | The question's words are the identifiers (`freeze`, `has_nsf_invoices`); three greps find every file. Code+map never opened the map; recall pulled it to Vue briefs. |
| `ui-0` dashboard load | 0.86 | Six obvious files from `main.ts`. The map saved 7 turns, added no facts; tree-only stopped after one leaf. |
| `lear-filings-1` payment to filer | 0.50 | Map arms +0.14 from one leaf (the legacy entity-pay worker grep never found). 5 turns lost to wrong leaf paths. The status listener and change-of-address rule are in legal-api leaves whose summaries do not mention them. |
| `cross-0` annual report | 0.62 | All arms 0.62. Missed facts are fine details; the pay leaf states some weakly and reports one rule as a "silent bug" (it saw a truncated chunk). |

Causes, across the five:

1. **The sample was easy.** Three of the five are answered at 0.83 to 1.00 by
   code alone, so nothing can be added. In the first run only 4 of the 36
   questions scored 0.85 or more with code alone; this sample drew 3 of
   them. The ten hardest for code alone (0.29 to 0.64) are where a map can
   show.
2. **The code+map agent skips the map.** It did not open it on `auth-0` and
   `pay-3`, though told to: grep is faster when the question names the
   code. An instruction is not enough.
3. **Navigation loses the agent.** Leaf pages sit under area folders but
   agents assumed flat paths (5 turns lost); area summaries are generic
   ("models and small helpers") and do not name the behaviour inside; one
   app or service is split across areas with no link (business-filings-ui
   in two areas, auth front and back end, pay-queue in two).
4. **Briefs drop what these questions turn on**: side effects and callers
   (who calls `ensure_no_payment_blockers`, the `NSF_LOCK_ACCOUNT` publish),
   route strings, enum and topic names, the branch that keeps a state; one
   misplaced detail (`fetchData` in "the dashboard component", it is
   `App.vue`) and one invented bug from a truncated chunk.
5. **Recall attaches noise for flow questions**: test files, notebooks and
   unrelated UI; it never surfaced the key leaves.

## Round 2b: the five hardest questions for code alone

The five questions code alone scored lowest on in the first run, same arms.

| arm | lear-filings-2 | pay-0 | auth-4 | pay-5 | ui-3 | mean | turns |
|---|---|---|---|---|---|---|---|
| code only, first run | 0.29 | 0.36 | 0.50 | 0.50 | 0.50 | 0.43 | 11 |
| code + old tree | 0.57 | 0.29 | 0.58 | 0.57 | 0.83 | 0.57 | 8 |
| old tree only | 0.21 | 0.29 | 0.58 | 0.43 | 0.58 | 0.42 | 5 |
| code only, round 2 | 0.64 | 0.50 | 0.50 | 0.64 | 0.83 | 0.62 | 12 |
| code + new tree | 0.64 | 0.50 | 0.58 | 0.57 | 0.75 | 0.61 | 10 |
| new tree only | 0.43 | 0.50 | 0.50 | 0.64 | 0.67 | 0.55 | 7 |

Read run by run:

- **They were not hard.** Four of the five first-run scores were noise: the
  same code-only setup gained 0.14 to 0.35 on a rerun by opening one more
  file. Grep finds every one of them (`tempRegNumber`, `get_owner_count`,
  `deletion_locked` are distinctive).
- **The rubric caps every arm.** Facts reward what the question does not
  ask: pay-api fee internals for an end-to-end question (`pay-0`, every arm
  0.50), side effects of a guard (`auth-4`, every arm 0 on two facts), the
  readers of a status (`lear-filings-2`, every arm 0). A hedge ("approved or
  created") earns full credit; a wrong claim every arm shares is not
  penalised.
- **The map's effect is speed, which the score does not count**: code+map
  matched code alone in 6 turns instead of 15 (`lear-filings-2`) and 12
  instead of 24 (`pay-0`).
- **How the map arms went wrong**: read only `root.md` and went back to grep
  (`lear-filings-2`); lost turns to leaf paths without their area folder
  (`pay-5`); answered from briefs without opening the code and stated a
  wrong status (`pay-5`); stopped where the map's coverage ended (`pay-0`).
- **What the map lacks here**: per-subclass overrides and literal statuses
  (`get_default_invoice_status`, APPROVED against CREATED), fee logic
  (`fee_schedule.py` appears only in a test brief), side effects of one
  method of a pair, client-to-endpoint mappings (`leaveOrg` → DELETE); the
  facts that are present sit in leaves behind area lines that do not name
  them, in a repository split across two areas, or only in test briefs.

## What the ten cases say

The benchmark, as it stands, cannot show the map's value: its questions are
answered by grep, one run per question moves a score by up to 0.35, and its
facts reward details the questions do not ask for. Where the map helps (the
legacy entity-pay worker, the partner-disbursement exclusion, half the
turns) it is either one fact or not scored.

The map itself has fixable faults, found again and again: leaf links an
agent mis-resolves, one service split over areas with no link, area and
root lines that name parts rather than behaviour, briefs that drop
identifiers, overrides and side effects, and recall that attaches tests and
templates. And the agent uses the map badly: it skips it, reads only the
root, or treats it as the answer instead of a pointer into the code.

## Round 3: plain questions, two arms, each run twice

The 10 analysed questions rewritten without the code's names, rubrics
trimmed to what each asks (`../2026-10-bc-registries-agents/data/arch3.json`,
22 of 85 facts dropped); code only against code + hrono (map + recall), a
12-turn budget for both, the map instruction "the map points you to the
right files: open them, verify, follow the flow past it", the export saying
which folder an area's leaves are in (`9822283`). Fact coverage per run:

| question | code a | code b | hrono a | hrono b | code | hrono | diff |
|---|---|---|---|---|---|---|---|
| lear-filings-1 | 0.70 | 0.80 | 0.80 | 0.80 | 0.75 | 0.80 | +0.05 |
| lear-filings-2 | 0.75 | 0.83 | 0.83 | 0.75 | 0.79 | 0.79 | 0.00 |
| auth-0 | 1.00 | 0.93 | 0.93 | 0.93 | 0.96 | 0.93 | -0.04 |
| auth-4 | 0.75 | 0.88 | 0.88 | 0.75 | 0.81 | 0.81 | 0.00 |
| pay-0 | 0.64 | 0.57 | 0.50 | 0.64 | 0.61 | 0.57 | -0.04 |
| pay-3 | 0.80 | 0.70 | 0.80 | 0.70 | 0.75 | 0.75 | 0.00 |
| pay-5 | 0.57 | 0.64 | 0.71 | 0.71 | 0.61 | 0.71 | +0.11 |
| ui-0 | 0.86 | 0.79 | 0.71 | 0.71 | 0.82 | 0.71 | -0.11 |
| ui-3 | 0.75 | 0.75 | 0.88 | 0.88 | 0.75 | 0.88 | +0.12 |
| cross-0 | 0.71 | 0.79 | 0.71 | 0.00 | 0.75 | 0.36 | -0.39 |
| mean | | | | | 0.76 | 0.73 | -0.03 |

Turns 10.3 (code) and 11.2 (hrono); cost $2.78 and $3.21 for 20 runs each;
2 contradicted facts each. hrono opened the map in 15 of 20 runs.

- The one large difference is a harness artefact: on `cross-0` run b the
  hrono agent spent 7 of its 12 turns reading the map (root, 3 areas, 3
  leaves), ran out of turns while verifying in the code and returned no
  answer. Scored at its run a, hrono's mean is 0.77 against 0.76.
- Otherwise the arms are level: the per-question differences (−0.11 to
  +0.12) are the size of the run-to-run spread inside one arm (up to 0.13).
- Plain wording did not defeat grep: code alone still covers 0.76. Sonnet
  finds the files from domain words ("filing", "invoice", "dashboard") as
  well as from identifiers.

On this benchmark, a Sonnet agent with the checkout gains nothing
measurable from hrono, in facts or in turns.

## Hard questions: what an engineer gets wrong

`../2026-10-bc-registries-agents/harness/gen_hard.py`: one Opus agent per
theme (inconsistency, authorization, impact, failure, legacy) wrote two
questions whose answer depends on code the question's words do not lead to;
an Opus verifier checked every fact; a code-only run calibrated them and the
five it did worst on were kept (`data/hard5.json`). Both arms 30 turns, run
twice; the hrono arm is told to grep the map like code.

| question | code a | code b | hrono a | hrono b |
|---|---|---|---|---|
| staff-only fee waiver: where enforced | 0.29 | 0.64 | 0.71 | 0.21 |
| can an unaffiliated user read a business's filings | 0.50 | 0.62 | 0.62 | 0.50 |
| a second filing type held for staff review | 0.50 | 0.57 | 0.50 | 0.57 |
| a payment-completed message that fails or repeats | 0.29 | 0.50 | 0.43 | 0.43 |
| the old and new payment listeners | 0.44 | 0.50 | 0.56 | 0.50 |
| mean | 0.49 | | 0.50 | |

Contradicted facts 13 (code) and 10 (hrono); turns 13.8 and 15.7. The
questions are hard (both arms miss half the facts), and the arms are level.
Calibration flattered the code arm's difficulty: its second run scored
higher on every question.

Read case by case, with every missed fact looked up in the map:

- **The agents barely read it.** In 6 of 10 hrono runs one grep, then code;
  on two questions no brief was opened. A grep for the question's words
  ("waive", "affiliat") reaches the code directly; the map does not use the
  words a hard question turns on ("missing check", "open route").
- **The hard part is not in the map.** It holds what each part does and
  where a rule lives. It does not hold what a hard question asks: a check
  that is missing or commented out, the condition a guard compares, what a
  security lookup is cached by, whose token goes on an outbound call, what
  is committed before a failure point, whether a failed publish is
  recorded or only logged, which worker has no review branch, two copies of
  an enum that drifted, and who produces what a listener consumes. Read
  perfectly, the map would have added about one fact on two questions and
  nothing on the authorization one.
- **Some briefs mislead.** A test-suite brief says an endpoint returns
  filings whose effective date is in the future; the code does the
  opposite. "Business GET checks view permission" is false; "`check_auth()`
  verifies account access" reads as a guarantee it is not. A brief that
  omits a guard led an agent to claim there is none.
- **One answer key is wrong**: the fee-waiver question's fact 6 (a non-staff
  caller does get a refusal, `PaymentLineItem.create`), so some
  "contradictions" there were correct answers.

The tree, as briefs of what each cluster of code does, cannot answer
the questions where agents make mistakes: those turn on absences,
conditions and links between services, and the brief recipe drops all three.
