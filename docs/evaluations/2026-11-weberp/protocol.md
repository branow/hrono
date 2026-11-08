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

## Amendment 4 (2026-11-06, written after its runs): gate first, threads map, plugin changes

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

## Amendment 5 (2026-11-06, before any of its runs): a task built on rules away from the change

The claim under test is narrowed to the mechanism seen on the PDP contest task: the
map helps when the rules a change must follow sit away from the code it
starts from, under names a code search from the request does not reach.
Across t2, t3, t6, t7 and t8 code-only runs repeatedly missed rules of
this kind, and the existing tree states them (customer tables moved by
Z_ChangeCustomerCode and the customer delete rules: topic 105; POST input
already escaped by session.php: topic 50; no hardcoded tokens: topic 174;
UIGeneralFunctions: topics 50, 123, 225).

t9-credit-reviews (tasks/t9-credit-reviews/) is made up to need these
rules: a business request (brd.md) naming no file, table or rule; a
checklist (checklist.md, not given to the agent) of 10 request items and
7 away-from-the-change items, each with where the code holds it and which
existing map page states it. The task was chosen for this property;
results are reported as evidence for the mechanism, not as an average
over webERP tasks. No tree build or sync: base 4cb937f79e8b, threads
export `4cb937f...-threads`, harness v2 with THREADS, plugin with the brief
gate (8874d26 or later, commit recorded per run).

Order as amendment 4: one code-only gate try; if it misses about half of
items 11-17, one hrono try, then 3 tries per arm graded by blind pair
review (grading/prompt.md, checklist items 1-17), every score reported.

## Amendment 6 (2026-11-06, before any of its runs): a large task, 40 rules away from the change

t9 had 7 such rules and code-only found 5 by grepping one neighbour
table; one try per arm cannot separate the arms on 2 items. Like PDP
contest (31 files, ~120 turns, dozens of rules), t10-credit-control is a large
feature (credit reviews, holds on every invoicing route, three-level
reminder letters, interest and fee charges, bad-debt write-off, access,
install and upgrade, manual) described in a business request (brd.md) that
names no file, table or rule.

Its checklist has 15 request items (A) and 40 rules away from the change
(B). The B rules were collected before any run by four reading agents, one
per map area, from the existing map's briefs, each checked against the base
code (lists with map page and file:line in grading/t10-credit-control/
rules/). Rules the map states wrongly, and two where map pages contradict
each other, are left out. The task is built for this property; results are
evidence for the mechanism, not an average over webERP tasks.

Runs as amendment 5 (gate, then hrono, then 3 per arm), harness v2 with
THREADS, threads export, plugin with the brief gate; the hrono arm with
READ_MAP=1. Primary score: B met (/40), graded blind.

## Amendment 7 (2026-11-06, before any of its runs): t10 at a fixed turn budget

The t10 code-only gate met 35.5 of 40 B rules, but in 287 turns and $10:
with no budget it reads its way to the rules. Real agents run with a
budget, and on the PDP contest task and t9 the map arm used fewer turns. The
question becomes: at the same budget, how many B rules does each arm meet?

Both arms: t10 unchanged, `--max-turns 100` (TURNS=100), and both prompts
say "You have a budget of 100 turns for the whole task; plan your reading
so that the change is complete and NOTES.md written within it."
(BUDGET_NOTE=1). hrono arm with READ_MAP=1 and the threads export as in
amendment 6. One try per arm first, both in parallel; graded by the same
reading-agent audit as the gate (checklist A and B), then, if the arms
differ by more than a few B items, 3 tries per arm graded blind. A run cut
by the budget is graded on what it delivered.

## Amendment 8 (2026-11-06, before any of its runs): t10 with Haiku

Sonnet reads its way to most rules (gate 35.5/40). The map should matter
more for a model that cannot hold the code it reads. Both arms MODEL=haiku
(reported model id recorded), TURNS=200, no budget note; otherwise as
amendment 7 (hrono READ_MAP=1, threads export). One try per arm in
parallel, blind graded as amendment 7; 3 per arm if they differ clearly.

## Amendment 9 (2026-11-06, before its run): rules list in the hrono prompt

On t10 the hrono arm read the pages stating B15, B21 and B32 and still
missed them. READ_MAP=2 adds to the hrono prompt: write the rules the
briefs state for the change in NOTES.md under "Rules from the map", each
with its brief, follow them, and check the change against the list before
finishing. First run: Haiku, hrono only, compared with the amendment 8
code-only Haiku try; blind graded the same way.

## Amendment 10 (2026-11-08, before any of its runs): t11, a business-only BRD and a middle dose of the map

Per docs/evaluations/PRINCIPLES.md. t10's BRD was written by the person
holding the checklist and leaked the hidden rules. t11-credit-control is the
same feature with a new BRD written by an agent that saw no code, no
checklist and no earlier BRD, only a business brief (channels, people,
goals). Its checklist: the BRD's 43 requirements (A) and t10's 40 mined
rules unchanged (B; primary score).

The hrono arm reads a middle dose of the map: READ_MAP=3 replaces "read
every brief" with "root.md, the areas the request touches, then the leaf
briefs of the parts you change and of the other places the same data
reaches; nothing unrelated". Sonnet, TURNS=200, no budget note, THREADS,
threads export, plugin with the brief gate. Order as amendment 4: one
code-only gate try; if it misses about half of B, one hrono try; then 3
per arm, graded blind.

## Amendment 11 (2026-11-08, before any of its runs): ownership, not execution; whole-change review

t11 told the agent to "implement the change requested in brd.md" and both
arms cut half the feature. Per PRINCIPLES.md, t12-credit-control is t11
with the same BRD and checklist and a task statement that gives ownership:
the agent owns the feature, works out what it needs in webERP and what
else must change with it, decides the open questions, and builds all of
it. Same arms as amendment 10 (Sonnet, TURNS=200, THREADS, threads export,
hrono READ_MAP=3), both in parallel, one try each first.

Grading: the checklist (A /43, B /40) by a reading agent per run as
before, and a blind pairwise review (labels by coin flip) of the change as
a whole: completeness, fit with the system and its conventions, code
structure, regressions, what a maintainer would fix, which to merge and
why, findings beyond the checklist. Both reported in full.

## Amendment 12 (2026-11-08, before any of its runs): plan from the map; no recalled passages

The t12 hrono transcript (README, "t12: how the hrono agent used the map")
shows the map was read as a toll, not as a plan: 7 pages before the first
write, 18 more just before editing a file (9 after a gate refusal), after the design
was fixed. New files, where most of the feature lives, have no brief, so
the flows they copy (GL posting, allocations, customer login) were never
read, and the agent read as much source as code-only. Recall matched the
task statement, not the BRD, and attached 3 source snippets.

The hrono arm now runs with READ_MAP=4: read root.md, then only the
briefs of the parts the feature touches, including the existing flows its
new code does the same work as; take what a module does or how a flow works
from the brief instead of opening that code; open source only for the files
it changes, and only the parts it changes. RECALL=0 turns off recalled
passages (plugin setting `recall: false`). The brief gate is removed from
the plugin (it was an experiment of 2026-11-06 that forced reading after
the design was fixed); the session note, skill and read hook stay.
Everything else as amendment 11: t12-credit-control, Sonnet, TURNS=200,
THREADS, threads export, graded blind against code-only try 1 with the
checklist and the whole-change review. One hrono try first.

## Amendment 13 (2026-11-08, before any of its runs): Grep the map; customer-login error fixed by hand

In t12 hrono tries 1 and 2 the agent ran 135 Grep/Glob calls and none on
the map: Grep searches the working directory, the map is in another
folder, and nothing said to search it. The READ_MAP=4 prompt gains one
universal sentence: "The map is plain markdown files: Grep its folder to
find the briefs that cover a subject or a name, the same way you search
the code."

The sales-order-entry brief (37) listed `CustomerLogin` as a session
value; in the code it is the variable `$CustomerLogin` that
`includes/session.php` sets. hrono followed the brief twice and wrote a
dead `$_SESSION['CustomerLogin']` check. At the user's request this
summarization error was fixed by hand in a copy of the export
(EXPORT=4cb937f79e8b57063bd47132413abdac8abbcbdc-threads-fixed): brief 37
no longer lists it as a session value, brief 50 says both login flags are
plain variables, and the bare `CustomerLogin==1` / `SupplierLogin==1`
tests in 9 briefs are written `$CustomerLogin == 1`. The exact changes are
in grading/map-fix-customerlogin.diff. No other brief was changed. This is
a hand correction of a map fault, reported as such; the product fix
(faithfulness of session-value lists) is separate.

Run: hrono, READ_MAP=4, RECALL=0, the fixed export, otherwise as
amendment 12; graded blind against code-only try 1 the same way.
