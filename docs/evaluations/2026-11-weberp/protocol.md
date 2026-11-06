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

## Amendment 2 (2026-11-05, before any of its runs)

Found after amendment 1: the harness (v1, copied from the PDP harness)
ran `--safe-mode`, which turns off every plugin and hook. The hrono arm got
the plugin's note and skill pasted into the prompt, and the plugin's recall
hook (UserPromptSubmit: `hrono recall <tree> <prompt>`, the top passages and
their pages attached to the prompt) never ran, in any webERP or PDP run.

Harness v2 (harness/implement.py) runs the real plugin: `--plugin-dir
plugins/hrono`, the plugin's settings in `~/hrono-weberp/home/agent.json`
per workspace, recall from the live tree (the run refuses to start unless
the mirror's pin is the task's base), the Skill tool allowed. Both arms drop
`--safe-mode` for `--setting-sources ""` and `--strict-mcp-config` (checked:
no user CLAUDE.md, settings, plugins or MCP load; Claude Code's built-in
plugins, skills and memory instructions do, in both arms). The prompt is
the same text as before, passed as an argument; the hrono arm's prompt no
longer carries the note and skill (the plugin supplies them). The recall
text is saved per run (<run>.recall.md), produced by the same hook code.

Runs: t3 at 4cb937f (the live tree's base), 3 tries per arm, both arms
new (v2), all six in parallel; three blind pair reviews (hrono k vs code
k, own coin flip each). t2 needs the tree restored to 2d8fa77 for recall
and follows only on the user's go.

## Amendment 3 (2026-11-06, before any of its runs)

The pilot tasks were small (3-10 files, ~50-300 lines, ~45 turns) and
greppable; hrono helped on PDP only on the large feature (contest: 31 files
+4,481, ~120 turns, with a 31 KB BRD), not on the smaller ETL task. t4 is
a large feature made up from webERP's next big change after the base:
the forecasting module (ef95df0b3, 34 files +8,989), described in a BRD
written from its manual without file, table or SQL names
(tasks/t4-forecasting/: task.md and brd.md go to the agent; checklist.md
and reference.diff do not). Base 4cb937f79e8b, the tree's current commit,
so no sync; the reference was written ~500 app files later and has known
gaps (checklist.md). The harness now copies every task file except
checklist.md and reference.diff into task/. Harness v2 (real plugin and
recall); the prompt is task.md as before. 3 tries per arm, all six in
parallel; three blind pair reviews (hrono k vs code k), same reviewer
prompt.

## Amendment 4 (2026-11-06): gate first, threads map, plugin changes

- **Order.** A task is first given to one code-only try. Only when that
  try fails on a large share of its checklist (aim: about half met) does
  one hrono try follow, and only then repeated tries. t5, t6 and t7 failed
  this gate (code-only met most items); t8 passed it (13 of 22 met).
- **Threads.** From t6 on both arms get the repository's issues, pull
  requests and discussions up to the base date as files (`github/`), and
  the hrono arm reads the threads map (export
  `4cb937f...-threads`, built on the db copy `db/hrono-threads.db`;
  `db/hrono.db` and the code-only export are unchanged). Harness option
  `EXPORT` selects the export.
- **Plugin changes between tries** (each try records the commit it ran on
  through its run date):
  - 71909d0: recall also reads the text files the prompt names (the BRD);
    the session note sends a change through root.md first.
  - 8874d26: reading a project file names its brief; an edit is refused
    until root.md and the edited file's briefs are read (setting `gate`,
    default on).
  t8 hrono try 1 ran on 71909d0, try 2 on 8874d26. The first t8 hrono try
  (before 71909d0, map never read) is kept in runs/void/ and not graded.
- **Stopped start.** The very first t8 hrono start returned no recall
  (the hook timed out on the server's first call after the sync); it was
  stopped within seconds of starting and its files deleted before the
  rerun that is in runs/void/.
- **Audits.** t7 and t8 tries are audited by one reading agent each
  (Opus 5.5, knows the arm, not blind), key claims checked by hand;
  reports verbatim in grading/gates/. Blind A/B review as in amendments
  1-3 is still the rule for a comparison of repeated tries.
