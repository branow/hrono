# Protocol: heterogeneous sources on webERP (E2)

Written 2026-11-09, before the knowledge check (RQ2) ran. The integration
analysis (RQ1) reads trees that already existed. Amendments are dated and
added at the end.

## Trees (reused, not rebuilt)

From 2026-11-weberp, both at webERP commit `4cb937f79`, same models,
embedder and settings (lookups on, insights on):

- A, code only: `~/hrono-weberp/db/snap-4cb937f.db`, 2,008 code sections.
- B, code + GitHub threads: `~/hrono-weberp/db/snap-4cb937f-threads.db`,
  A plus the `webERP-threads` source (858 threads up to 2026-02-27, 955
  sections), added by a sync.

Both are served read-only from copies in `~/hrono-e2/db/` (A on 8801, B on
8802).

## Questions and hypotheses

- **RQ1 Integration.** H1: a substantial share of leaf topics mixes code
  and threads, and a thread lands in the same leaf or area as the files it
  is about. Measured by `integration.py`: mixed leaves and per-leaf purity
  against 1,000 random permutations of the source types over the same leaf
  sizes; for each thread, its linked files (a PR's changed files from the
  GitHub API, `data/pr-files.tsv`; for issues and discussions, repository
  file names in the text) and whether any of them shares the thread's leaf
  or area, against random file sets of the same size.
- **RQ2 Added knowledge.** H2: on questions answerable only from the
  threads, answers from tree B's recall cover more reference facts than
  answers from tree A's; on code questions B is no worse.
  - `data/questions.json`: 24 questions written by an agent from the raw
    code and threads only (never the trees): 12 thread, 12 code, 3-4
    reference facts each. Frozen before any answer.
  - `qa.py`: for each question, 10 recall hits from A and from B; Sonnet
    answers from the hits alone; Sonnet also answers with no context (the
    memory check). A blind Opus judge marks each fact covered or not, the
    three answers shuffled and unlabelled. Fact recall per half, B - A
    with a paired bootstrap 95% CI. With 12 per half, exploratory.
- **RQ3 Placement on sync.** Read from the threads sync already recorded
  (2026-11-weberp, job_f46aa101): where the threads went, the repairs it
  caused, and its cost.
- **RQ4 Cost per source type.** From the recorded build and sync.
