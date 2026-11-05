# Protocol: webERP pilot, code-only vs hrono

Written 2026-11-05 before any task run. Changes after a run starts are
recorded under "Deviations" at the end, with the date and the reason.

## Question

Does an hrono map of a messy, little-known codebase help a coding agent
implement real changes whose rules are spread across files? Pilot: one try
per arm per task, to check the setup and the cost before a full run.

## Corpus

webERP, github.com/timschofield/webERP (selection and familiarity in
README.md and probes/). The tree `weberp` is built at 842d073 (see
README.md: models, prompts, filter, cost). Familiarity probe (probes/): a
tool-less Sonnet scored 0 right, 1 partial, 2 wrong on 3 questions about
where webERP's rules live.

## Tasks

Each task is a real change that was later merged, given to the agent as a
problem statement written from the original issue, discussion or PR
description, with the solution removed. Statements: tasks/<id>/task.md.
Reference diffs (excluding locale/, css/, doc/): tasks/<id>/reference.diff.

| id | origin | base (workspace and tree) | reference |
|---|---|---|---|
| t1-bank-revalue | PR #845, merged 2026-02-19 | 842d073742e0 | 842d073..2d8fa77 |
| t2-unrealized-account | discussion #842, PR #848, merged 2026-02-19 | 2d8fa778b57d | 2d8fa77..882b00c |
| t3-item-notes | issue #592, commits cc85fec49 + 73c1963cb, 2026-02-27 | 4cb937f79e8b | 4cb937f79..73c1963cb |

The tree is brought to each task's base with hrono's incremental sync
before that task's hrono runs; each sync's calls and cost are recorded.
The pin of the source mirror moves to the base; nothing after the base is
visible to either arm.

Note on t1: the merged reference never calls the revaluation from the
login rate update (tasks/t1-bank-revalue/checklist.md); t1 is graded
against the task, not the reference.

## Arms

Identical except for the map:

- Agent: Claude Code 2.1.287, headless (`claude -p`), `--model sonnet`
  (reported model id recorded per run), `--max-turns 200`, `--safe-mode`
  (no CLAUDE.md, plugins, hooks or MCP), `--permission-mode acceptEdits`,
  allowed tools Read, Grep, Glob, Edit, Write, TodoWrite; disallowed Bash,
  WebFetch, WebSearch, Task, NotebookEdit. Timeout 4 h.
- Workspace: webERP at the base as plain files (no git history) plus
  task/task.md, committed once as a baseline; the agent's work is the diff
  against it.
- Prompt: task.md, then "The webERP repository is in the current
  directory; the task is task/task.md. There is nothing to run against:
  deliver the change as files."
- hrono arm only: the tree exported with `hrono tree export` at the base,
  added read-only with `--add-dir`, and the hrono plugin's session note and
  skill appended to the prompt (text generated from
  plugins/hrono at hrono's commit of the run; saved per run as
  `<run>.prompt.md`).

Harness: harness/implement.py (adapted from the PDP harness; same
flags). Per run it saves the prompt, argv, the full stream-json transcript,
stderr, the diff and a summary (turns, seconds, cost, model ids, exit).

## Grading

Blind review per task. One reviewer (Claude Opus through claude-code,
fresh session, no tools beyond reading the given files) gets the task
statement, the checklist, the reference diff with its known gaps, and the
two runs' diffs labelled A and B in an order fixed by a coin flip recorded
in a key file the reviewer never sees. It scores each run:

- checklist: each item met (1) / partly (0.5) / missed (0);
- correctness 0-5: would the change work as the task asks, in webERP;
- conventions 0-5: follows how webERP does the same thing elsewhere
  (upgrade scripts, helpers, page structure, security tokens, strings);
- regressions: anything it breaks, listed;
- a short justification per score.

The reviewer prompt is saved verbatim (grading/prompt.md) with every raw
reviewer output. Scores are reported per task and arm; with one try per arm
the pilot reports them as observations, not a significance test.

## Recorded per run

Task, arm, try, base, start time (UTC), seconds, turns, cost (claude-code
reported, API-equivalent), model ids, exit code, diff stat, files touched;
for the hrono arm also which map pages were read (from the transcript).

## Deviations

- 2026-11-05: t3's original choice was PR #878; its base is 555 app files
  from the tree pin, so it was replaced (before any run) by commit
  cc85fec49 + 73c1963cb (issue #592), base 31 files from the pin.
- 2026-11-05: the tree sync to t2's base was stopped in its brief stage
  (51 leaf briefs to rewrite, ~$16-19, beyond the pilot budget); on the user's
  go it was resumed from the stopped state (db/snap-2d8fa77-midsync.db) and
  completed; t3's sync ran in full. Both syncs are recorded in the README
  log and syncs/.
- 2026-11-05: in every task both arms ran in parallel (same start
  second, separate workspaces); the protocol did not fix the order.

## Amendment 1 (2026-11-05, before any of its runs)

Retrospective of the pilot (README "Retrospective"): the map held the
facts the hrono arm got wrong (t3: topic 50 states POST data is already
escaped by session.php; t2: topic 123 covers BankReconciliation.php), but
the arm read 1-4 pages and the plugin's note and skill only covered
answering questions. hrono f8004fd adds a "When the task is a change" section
to the skill and one sentence to the session note: before the first edit,
read the leaf brief of every file to be edited and of the shared files it
includes. No tree, prompt or task changed.

Rerun of t2 and t3 on the existing trees (db/snap-2d8fa77.db,
db/snap-4cb937f.db; exports unchanged), no sync:
- hrono arm: tries 2, 3, 4 with hrono f8004fd (the pilot's try 1 used the old
  note and is reported separately, not pooled).
- code arm: tries 2, 3 (identical setup; try 1 is pooled, giving 3).
- Grading: three blind pair reviews per task, hrono try k+1 vs code try k
  (k = 1, 2, 3), each with its own coin flip, same reviewer prompt.
- Reported: per-arm mean and every individual score; with n = 3 per arm
  still an observation, not a significance test.
