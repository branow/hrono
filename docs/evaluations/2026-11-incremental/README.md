# Incremental update on streamlink (E1)

Is hrono's incremental update (`hrono tree sync`) efficient and faithful?
One cold build, 18 syncs over real history, then two cold builds of the
final commit. Protocol: `protocol.md` (and its amendment 1). All costs are
API-equivalent from hrono's own ledger and price table (the calls ran
through claude-code on the subscription).

## Setup

- streamlink, whole repository. c₀ `28ecdc743` (2026-06-24): 620 files,
  893 sections. Final commit `1bd90e9a2` (2026-09-18): 913 sections.
- Steps `steps-plan.tsv`: 18 consecutive ranges, 1 to 47 commits, 1 to 73
  files changed.
- Models as webERP: condense and judge haiku, brief and brief-upper sonnet,
  granite-97m embedding. Lookups off, insights off (`data/tree.json`).
- hrono `89ab623`. Workspace `~/hrono-incremental` (not in git). Raw job
  reports `data/jobs/`, timings `data/steps.log`, per-step measures
  `steps.csv` (`measure.py`), agreement `data/fidelity.json`
  (`fidelity.py`).

## The cold builds

| | sections | leaves / areas | calls | cost | wall time |
|---|---|---|---|---|---|
| c₀ (`job_ee9fd384`) | 893 | 57 / 6 | 572 | $12.16 | 1 h 40 min |
| final commit, cold1 | 913 | 57 / 5 | 586 | $12.59 | 1 h 2 min |
| final commit, cold2 | 913 | 58 / 5 | 589 | $12.23 | 1 h 0 min |

The two final-commit builds ran in parallel with syncs 3-18 (amendment 1).

## Per step

Sections changed = (added + deleted) / 2; a section edited in place is
deleted and re-added under a new id.

| step | files | sections changed | leaves with changed members | briefs rewritten, leaf + upper | judge verdicts | cost | share of build | wall time |
|---|---|---|---|---|---|---|---|---|
| 1 | 1 | 1 | 1 | 2 + 2 | minor 1 | $0.70 | 5.8% | 4 min |
| 2 | 4 | 10 | 4 | 5 + 3 | major 3, minor 1 | $1.28 | 10.5% | 6 |
| 3 | 1 | 0 | 0 | 1 + 0 | | $0.13 | 1.1% | 2 |
| 4 | 5 | 16 | 4 | 5 + 3 | major 3, minor 1 | $1.19 | 9.8% | 11 |
| 5 | 1 | 0 | 0 | 1 + 0 | | $0.13 | 1.1% | 4 |
| 6 | 73 | 155 | 32 | 33 + 7 | major 23, minor 8, none 1 | $6.25 | 51.4% | 22 |
| 7 | 6 | 14 | 6 | 6 + 2 | major 1, none 4 | $1.01 | 8.3% | 6 |
| 8 | 3 | 8.5 | 1 | 2 + 2 | major 1 | $0.62 | 5.1% | 4 |
| 9 | 30 | 80.5 | 16 | 17 + 6 | major 11, minor 5 | $3.67 | 30.2% | 21 |
| 10 | 2 | 4 | 1 | 2 + 2 | major 1 | $0.71 | 5.8% | 4 |
| 11 | 1 | 1 | 1 | 2 + 2 | minor 1 | $0.67 | 5.5% | 4 |
| 12 | 8 | 15 | 8 | 8 + 5 | major 2, minor 3, none 2 | $2.09 | 17.2% | 7 |
| 13 | 2 | 3.5 | 3 | 4 + 3 | major 3 | $1.22 | 10.0% | 6 |
| 14 | 20 | 26.5 | 15 | 14 + 6 | major 10, minor 3, none 1 | $3.40 | 28.0% | 11 |
| 15 | 3 | 9.5 | 3 | 5 + 2 | major 1, minor 1, none 1 | $1.13 | 9.3% | 5 |
| 16 | 61 | 163 | 35 | 37 + 6 | major 23, minor 11, none 1 | $6.88 | 56.6% | 25 |
| 17 | 1 | 0 | 0 | 1 + 0 | | $0.13 | 1.1% | 2 |
| 18 | 7 | 33.5 | 5 | 6 + 3 | major 4, minor 1 | $1.59 | 13.1% | 7 |
| **all** | | | | | | **$32.79** | 270% | 2 h 38 min |

No sync forced or parked a section, and none failed a call. Misfit rose
from 0.029 to 0.036 (peak 0.040 in step 16). The only repairs were two
splits each in steps 15 and 16. `settle_due` turned true at step 6 and
stayed true: step 6 alone changed 155 sections, past the 50 drift points
of `CHURN_THRESHOLD` (misfit never reached 2× its baseline). As the
protocol says, no settle was run, so steps 7-18 and the fidelity result
are for a tree that hrono itself would have settled after step 6.

## RQ1 Cost

- **H1a (linear): holds.** Least squares over the 18 steps:
  cost = $0.69 + $0.038 × sections changed (R² 0.92), and
  cost = $0.42 + $0.187 × leaves with changed members (R² 0.99). Cost
  follows the number of topics touched more closely than the number of
  sections, because the unit of work is a brief.
- **H1b (a change of ≤ 2% of the sections costs well under 10% of a
  build): does not hold.** Of the 13 steps at or under 2%, the 10 that
  changed any section cost 5.1% to 17.2% of the build (median 8.8%), and 3
  were at or above 10%. A one-section change costs 5-6% of the build
  (steps 1, 8, 11: 5 brief calls, 2 brief-upper, 3 judge): the changed
  leaf takes 4 brief calls, the stuck brief below one more, and the change
  climbs to two upper briefs even on a "minor" verdict.
- **H1c (cumulative syncs below rebuilding at each step): holds, but
  narrowly read.** 18 syncs cost $32.79 against 18 × ~$12.3 = $221 for a
  rebuild at each step (15%). But they cost 2.7 cold builds in total; the
  running sum passed one build after step 8 (eight syncs, 6 weeks of
  history). Two kinds of step dominate: wide mechanical changes (step 6,
  a linter upgrade, and step 16, a type-checker upgrade, touched 17-18% of
  the sections and cost 51% and 57% of a build) and the fixed floor of a
  small change.
- **Fixed cost of a sync with nothing to do: $0.13**, from one brief that
  can never be written cleanly (below).
- Wall time: 2 to 25 minutes a sync, against 1-1 h 40 min for a build.

## RQ2 Locality

- **H2a (no unchanged section changes topic outside repair): holds.** 0
  in all 18 steps. 30 unchanged sections moved in steps 15 and 16, both by
  a reported repair (2 splits each).
- **H2b (no topic with changed members left un-briefed and un-judged):
  holds in 15 steps, fails in 3.** In steps 7, 12 and 14, the leaf holding
  `src/streamlink_cli/main.py` got 4 sections with new content (different
  hashes), yet its brief was not rewritten, no judge verdict was logged
  for it, and its `member_signature` stayed the same. The topic's brief
  therefore describes the file as it was before those edits. Cause not
  investigated in this run.
- **Amplification:** 1.1 leaf briefs and 1.5 briefs in all (leaf + upper)
  rewritten per leaf whose members changed, over all steps. With lookups
  off, a change stays local; compare webERP with lookups on, where 5 files
  rewrote 65 briefs ($35.35, 59% of its build) because briefs that had
  looked up a changed shared file were all judged material.
- **A brief rewritten every sync.** Leaf 13's brief is flagged by the copy
  gate ("talks-to-the-caller"), so the health check counts it as unusable
  (`stale 1` after the build and after every sync). Each sync rewrites it,
  and the new text is flagged again: one brief call ($0.13) on every sync,
  forever, including the three syncs that changed nothing.

## RQ3 Fidelity

Section → leaf agreement over the 913 sections all three trees share:

| | ARI | AMI |
|---|---|---|
| cold1 vs cold2 (noise floor) | 0.581 | 0.765 |
| incremental vs cold1 | 0.539 | 0.728 |
| incremental vs cold2 | 0.546 | 0.728 |
| c₀ vs incremental (604 sections unchanged since c₀) | 0.970 | 0.991 |

- **H3 holds.** After 18 syncs the incremental tree agrees with a cold
  build 0.035-0.042 ARI (0.037 AMI) less than two cold builds agree with
  each other.
- The noise floor itself is low: two cold builds of the same commit, with
  the clustering seed fixed (UMAP random_state 42), put the same sections
  in the same topic only to ARI 0.58. The condensations alone, rewritten
  by the LLM on each build, move that much. A cold rebuild is therefore
  not a stable reference; the incremental tree is closer to its own
  history (ARI 0.97 on unchanged sections) than any rebuild is to another.

## RQ4 Brief quality

| | briefs | faithfulness gate: unfaithful claims | copy-gate flags |
|---|---|---|---|
| incremental, after 18 syncs | 66 | 24 (36%) | 1 |
| cold1 | 63 | 32 (51%) | 0 |
| cold2 | 64 | 29 (45%) | 0 |
| c₀ build | 64 | 29 (45%) | 1 |

The incrementally maintained briefs are no worse than fresh ones on
hrono's own deterministic gates (fewer flagged as unfaithful). The share
of briefs with at least one unfaithful claim is high in every tree; that
is the gate's sensitivity, not something the update causes.

## What this means

- Incremental update is local and faithful: no unchanged section moved
  except by a reported repair, and after 18 syncs the tree is as close to
  a cold build as two cold builds are to each other.
- It is cheap relative to a rebuild for any single change (5-15% for most
  steps, 2-25 minutes) but not "near free": a one-section change costs
  5-6% of a build, and a wide mechanical change (a linter or type-checker
  upgrade touching a sixth of the code) costs half of one. Over 18 steps
  the syncs cost 2.7 builds.
- Three defects to fix: a changed topic that escaped both re-brief and
  judge (3 steps, the same leaf), a copy-gate-flagged brief retried on
  every sync, and the floor cost of a minor change climbing two levels.
