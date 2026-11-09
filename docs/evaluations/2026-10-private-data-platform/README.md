# A private data platform: where hrono helped (anonymized)

An evaluation on a proprietary codebase, reported without anything that
identifies the organization, its products, vendors, people or data. The
code, tasks, trees, transcripts and reviews stay with the organization and
are not reproducible from this page; only the design, the numbers and the
reasons are given here. It is the one setting so far where hrono gave an
agent a clear, repeated advantage, and the comparison with the settings
where it did not is the point of reporting it.

## The codebase

The data side of a mid-size online retailer that sells through a network
of independent sales representatives: six repositories maintained by a
small team over many years.

| part | files | sections (hrono's cut) |
|---|---|---|
| relational database: tables, stored procedures, deployment and manual scripts | 2,341 | 8,210 |
| reporting: report definitions, dashboards, report SQL | 1,136 | 4,999 |
| checkout and enrollment engine | 138 | 1,410 |
| data-lake ETL jobs | 494 | 634 |
| two schema-migration repositories | 49 | 71 |
| **all** | **4,158** | **15,324** |

What makes it hard for an agent:

- **No single convention.** The same kind of feature has been written many
  times by different people in different years. There are 52 stored
  procedures for the yearly sales contests alone, and they do the same
  things (count enrollments, net returns, check a member's status in a
  period, lock a run) in visibly different ways. The current pattern is
  the newest one, introduced by one recent contest; older ones are still
  in the tree and look equally authoritative.
- **Duplication instead of reuse.** Logic is copied from one procedure to
  the next and then drifts. A rule handled correctly in one place (for
  example, removing a refunded order's enrollment) is missing or done
  differently in a dozen others.
- **Rules live in sibling code, not near the change.** What a new contest
  must do is visible only by reading earlier contests and the shared
  procedures they call, far from any file a grep for the new feature's
  words would find.
- **Size.** About 15,000 sections; an agent's context holds a few dozen
  files.

## The tree

One tree over all six repositories, built in three batches with hrono's
default prompts: condense and judge on Haiku, briefs on Sonnet, the
granite-97m embedding, cross-topic lookups on. 440 leaf topics, 24 areas,
3 upper levels, one root. About $218 API-equivalent (condense $26.53,
briefs $163.16, upper briefs $25.46, judge $2.33), run on a subscription.
Files holding personal data and bulk data loads were excluded before
building.

## Tasks

Two real changes the team had already shipped, given as of the date
before the work started (each repository pinned there, so the answer is
not in the tree):

- **Contest (the main task).** A new yearly sales contest from the
  business requirements document of that date and the agreed API
  contract: stage tables, builder procedures, a final builder, an
  orchestrator and the read procedures the front end calls. The real
  change was 31 files, about 4,500 lines.
- **ETL.** Re-partition a large order-line table in the data lake by month
  of the order date and make the downstream job read only changed rows.
  The real change was 8 files in one repository.

## Arms and grading

- Both arms: Sonnet, 200 turns at most, Read/Grep/Glob/Edit/Write, the
  same prompt and workspace; three tries each.
- hrono arm: also the exported tree (Markdown), with the hrono plugin's
  session note and skill text pasted into the prompt (the runs used
  `--safe-mode`, so hooks were off).
- Each diff was reviewed blind by Opus (arm labels hidden behind a coin
  flip) against a rubric built from the real change and from the bugs the
  team later found and fixed in its own implementation. For the contest:
  architecture, time zones, orchestrator safety, returns, market filter,
  history (every check as of the period, not today), plus 11 real bugs as
  traps (a repeated bug counts against the run).

## Results

### Contest: hrono better in every pair

| | try 1 | try 2 | try 3 | mean |
|---|---|---|---|---|
| code only, /40 | 19 | 19 | 22 | 20.0 |
| hrono, /40 | **25** | **24** | **23** | **24.0** |
| code only, traps avoided /11 | 5 | 4 | 5 | 4.7 |
| hrono, traps avoided /11 | 5 | 8 | 4 | 5.7 |
| code only, orchestrator safety | 2 | 1 | 1 | |
| hrono, orchestrator safety | 4 | 3 | 4 | |
| code only, history | 1 | 1 | 2 | |
| hrono, history | 3 | 2 | 2 | |
| turns (mean) | | | | code 123, hrono 99 |
| cost per run (mean) | | | | code $5.09, hrono $4.38 |

Every hrono run scored above every code-only run. With three tries a side
that ordering has probability 1/20 under no difference (one-sided exact
permutation test, p = 0.05): significant at the minimum, a small sample.
The hrono arm was also cheaper and used fewer turns.

The hrono agents read the root, the contest area and then one or two
contest leaves (6, 8 and 10 map pages), and took from them the newest
contest's structure and its orchestrator pattern: an application lock
against concurrent runs, one transaction, and a failed run leaving the
previous results in place. The code-only agents found a contest by grep,
often an older one, and copied its weaker orchestrator and its live
status checks.

### What hrono did not fix

Both arms repeated the same hard bugs, and the reasons are informative:

- **Time zones.** The source system stores one time zone and the business
  runs on another; periods start at 23:00 in the stored zone. That rule
  was written nowhere in the code at the pin date, and the newest
  contest's own helper compared plain dates, so every agent copied the
  bug. A map derived from the code cannot hold a rule the code does not
  hold.
- **History.** 52 contest procedures check a member's *current* status;
  the as-of-period rule existed only in people's heads at that date.
- **Refunds.** Netting enrollments against refunded orders was done in
  older contests only. One leaf brief stated it eight times; the contest
  area brief the agents read did not mention it, and no run opened that
  leaf. The rule was in the map, one level further down than the agents
  went.
- Two remaining bugs were readings of the business document, out of reach
  of any map.

### ETL: no gain

| | try 1 | try 2 | try 3 | mean |
|---|---|---|---|---|
| code only, /25 | 14 | 14 | 14 | 14.0 |
| hrono, /25 | 13 | 12 | 14 | 13.0 |

Every run keyed the incremental read on the wrong timestamp (a copy of
the ingestion tool's sync column, not the column the lake sets when it
processes a row). Only one run, an hrono one, chose the requested month
partition from the right source table. The ETL repository is small (634
sections), consistent and self-contained: one folder of jobs built on a
shared base class, so grep and a few reads give an agent everything it
needs, and the map adds nothing.

### Extra notes from a stronger model: no gain

Opus "insight" notes added to the contest area (three passes), as
separate pages or merged into the area brief: 22.7 and 22.7 /40 against
24.0 without them; traps 5.3 and 5.7 against 5.7.

## Why it worked here and not elsewhere

Across the evaluations in this folder, hrono helped when three things
were true at once, and not when any was missing:

1. **The knowledge the change needs sits in code the agent would not
   open.** Here the right contest pattern and its safety rules were in
   sibling procedures among 52 near-duplicates, in a 15,000-section
   estate. In the ETL task everything needed was in one small, uniform
   folder that grep finds.
2. **The codebase has no single convention, so "copy the nearest
   example" picks the wrong one.** Grep finds *a* contest; the map's area
   brief says which contest is current and what the others do
   differently. On cleaner codebases (the ETL repository here; webERP,
   2026-11-weberp) the nearest example is usually the right one and the
   map's summary adds little over reading it.
3. **The rule is actually in the code.** hrono compresses what the code
   says. Where the rule was in nobody's code at the time (time zones,
   as-of history), the map could not supply it, and the hrono arm made
   the same mistake as code only.

Compared with webERP (2026-11-weberp): 2,000 sections of PHP pages with
inline SQL. hrono runs found more of the hidden rules (about 2 of 40
more), but a blind reviewer preferred the code-only change on 3 of 4
pairs, because the faults that decided the review were in shared plumbing
(mail, installer) the agent edited without reading the code, and the
codebase was small enough for code-only to read that plumbing itself.

## Limits

- One organization, one main task, three tries per arm, one blind reviewer
  per diff; the result is significant only at p = 0.05.
- Not reproducible outside the organization. The rubric was written by the
  team member who knew the real bugs, before the runs.
- The hrono arm ran with the plugin's text pasted into the prompt and
  hooks off (`--safe-mode`), not with the live plugin.
- The comparison across codebases is between different tasks, not a
  controlled variable.
