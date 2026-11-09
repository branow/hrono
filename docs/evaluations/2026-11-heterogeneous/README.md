# Heterogeneous sources: webERP code + GitHub threads (E2)

Does one hrono tree integrate different source types into one hierarchy, and
do the non-code sources add knowledge an agent cannot get from the code?
Measured on the two webERP trees that already existed (2026-11-weberp), so
no tree was built or synced for this. Protocol: `protocol.md`.

## Setup

- Tree A, code only: webERP at `4cb937f79`, 2,008 code sections, 132 leaf
  topics, 5 areas.
- Tree B: A plus the `webERP-threads` source, 858 issues, pull requests and
  discussions up to 2026-02-27 (955 sections), added to A by one sync
  (2026-11-06, job_f46aa101).
- Both: condense and judge haiku, brief and brief-upper sonnet, insights
  opus, all through claude-code; embedding granite-97m; lookups on.
- The clustering vector is `0.6·text + 0.4·folder`, and a section's folders
  are the prefixes of `source/folders/file` (docs/clustering.md).

## RQ1 Integration: no

`integration.py` on a copy of tree B; output `data/integration.json`.

| | B | random assignment, same leaf sizes (1,000 permutations) |
|---|---|---|
| leaves | 202 | |
| leaves mixing code and threads | **2** | 197.6 (min 191) |
| code-only leaves | 132 | |
| thread-only leaves | 68 | |
| mean leaf purity | 0.999 | 0.692 |

By area (sections, code / thread): installer, seed data and project
history 351 / 769; database installation and upgrade 157 / 171; finance
and ledger 200 / 13; report writer 433 / 2; sales, purchasing, stock and
master data 867 / 0.

Threads against the files they are about (a PR's changed files from the
GitHub API, `data/pr-files.tsv`; for issues and discussions, repository
file names in the text):

| | linked to ≥ 1 file | same leaf as a linked file | same area | same area, random files of the same count |
|---|---|---|---|---|
| pull requests | 350 of 415 | **0** | 210 | 189.1 |
| issues and discussions | 258 of 443 | **1** | 121 | 100.7 |

H1 does not hold. The tree keeps threads and code apart: 68 leaves hold only
threads, and a thread almost never shares a leaf with the code it changed or
names. At area level the match is only slightly above chance. Most threads
sit in one area ("installer, seed data and project history"), whatever
part of the system they discuss.

Why: the folder part of the vector. Every thread path starts
`webERP-threads/…` and every code path `webERP/…`, so a thread shares no
folder prefix with any code file and the full 0.4 folder weight with every
other thread. A thread about the sales order page therefore scores higher
against an unrelated thread than against `SelectOrderItems.php`. This is a
finding about the method: the folder signal that groups code well works
against integration across sources.

## RQ3 Placement on sync

From the recorded sync that added the threads
(`../2026-11-weberp/syncs/threads-4cb937f-job.txt`):

1. `update` forced 500 thread sections into existing (code) topics.
2. `monitor` then measured misfit 0.234 against a baseline of 0.061.
3. `repair` split 33 topics, migrated 219 sections and freed 125. A second
   repair dissolved 2, split 12 and reparented 21.
4. `adopt` (two passes, 1.5 h) formed the new leaves, 132 → 202.

So the first placement did put threads next to code; the misfit monitor
read that as damage and the repair moved them out into topics of their own.
The integration that update attempted was undone by the tree's own health
check, for the same reason as RQ1.

## RQ4 Cost per source type

API-equivalent, hrono's price table (`hrono usage --by run`):

| | sections | cost | per section |
|---|---|---|---|
| code, cold build (2026-11-04) | 2,008 | $60.28 | $0.030 |
| threads, added by sync (2026-11-06) | 955 | $80.55 | $0.084 |

The threads cost 2.8 times as much per section as the code. They were not
dearer to condense (132 condense calls); the briefs were written twice
(384 brief calls), first for the topics the threads were forced into and
again after the repair, plus 1.5 h of adoption.

## RQ2 Added knowledge: some, not significant

`qa.py`; questions `data/questions.json` (24, written by an agent from the
raw code and threads, never the trees: 12 answerable only from a thread, 12
from the code, 3-4 reference facts each); answers `data/answers.json`;
judge `data/grades.json`. For each question Sonnet answered from the 10
recall hits of tree A, from those of tree B, and with no context; a blind
Opus judge marked each fact covered, the three answers shuffled and
unlabelled.

| | facts covered, A | B | no context | B − A, mean per question (95% bootstrap CI) |
|---|---|---|---|---|
| thread questions (12, 40 facts) | 2 (5.6%) | **7 (18.1%)** | 2 (4.9%) | +0.125 (−0.062, +0.347) |
| code questions (12, 48 facts) | 15 (31.2%) | **19 (39.6%)** | 10 (20.8%) | +0.083 (−0.021, +0.208) |

Questions with at least one fact covered: thread A 2, B 4, none 2; code A
8, B 10, none 6.

- H2 points the right way but does not hold at this size: B covers more
  thread facts than A, and the interval includes zero. B is no worse on
  code questions (also slightly better, also not significant).
- Recall found the source thread in B's 10 hits for 9 of the 12 thread
  questions. Recall then returns a passage of about 600 characters around
  the best match, and the fact is often in another part of the thread. In
  T06 the hit is a comment recalling the decision ("when Ricard moved us to
  using some generated fields we realised that meant we were restricting to
  a minimum DB version") but not the comment that states 5.7.5 and the
  lead's policy, so the answer says it does not know. The single-shot,
  hits-only design undercounts what an agent that opens the thread would
  get.
- Threads did not crowd out code on code questions: they took 0 to 5 of B's
  10 hits (median 1).
- The no-context answers cover almost nothing on thread questions (2 of
  40), so those questions test the knowledge base, not model memory.

Cost of RQ2: answers $1.84, judge $0.78 (claude-code, API-equivalent).

## What this means

- The tree does not integrate heterogeneous sources. It files them side by
  side, by source type, and its own monitor and repair actively undo
  attempts to mix them. The cause is a design choice (the folder signal is
  keyed on the source name), so the fix would be in the method, for
  example folder similarity computed on the path inside the source, or
  threads given the paths of the files they touch. Untested here.
- The threads do carry knowledge the code does not, and recall finds the
  right thread, but the facts reach a single-shot answer only partly.
  Exploratory, n = 12 per half.
