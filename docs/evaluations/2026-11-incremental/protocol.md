# Protocol: incremental update on streamlink (E1)

Written 2026-11-09, after the cold build at c₀ was started and before any
sync. Amendments are dated and added at the end, never edited in place
(docs/evaluations/PRINCIPLES.md).

## Questions and hypotheses

- **RQ1 Cost.** How does sync cost depend on the size of the change, and how
  does it compare with a cold build?
  - H1a: sync cost grows roughly linearly with the number of changed
    sections.
  - H1b: a change touching ≤ 2% of the sections costs well under 10% of the
    cold build.
  - H1c: the cumulative cost of the 18 syncs stays below the cost of a cold
    rebuild at each step.
- **RQ2 Locality.** Does a sync respect its own invariants?
  - H2a: no unchanged section changes topic during a sync, outside the
    repairs (split, migrate, dissolve) the sync reports, which are counted
    separately.
  - H2b: every topic whose members changed is re-briefed or judged; none is
    left stale.
  - The amplification factor (briefs rewritten / leaf topics whose members
    changed) is reported.
- **RQ3 Fidelity.** After 18 syncs, how far is the incrementally maintained
  tree from a cold build of the same commit?
  - H3: the agreement (ARI and AMI of section → leaf) between the
    incremental tree and a cold build is not meaningfully lower than the
    agreement between two cold builds (the noise floor).
  - Misfit and `settle_due` are recorded at every step.
- **RQ4 Brief quality (secondary).** The faithfulness gate pass rate and the
  copy-gate flags of the final incremental tree against the cold build.

## Corpus

streamlink (github.com/streamlink/streamlink), mirrored 2026-11-09. A
public Python project with a linear (rebased) history of small commits,
893 sections at c₀ by hrono's cut, inside the 500-2,500 range, and cheap
enough to build three times. Whole repository, no filter (as the
2026-10 SWE-QA run).

- c₀ = `28ecdc7433d27f096e49c054eeef37ea32db3f4a` (2026-06-24), the
  parent of the first commit of July 2026.
- Steps: `steps-plan.tsv`, 18 consecutive ranges after c₀ ending at
  `1bd90e9a2f` (2026-09-18), chosen by a target number of changed files
  (1 to 73) so that small, medium and large diffs alternate. Step 6 is a
  linter upgrade that rewrites 73 files lightly; step 16 is 47 commits,
  61 files. Frozen before the first sync.

## Configuration

- Workspace `~/hrono-incremental` (server on 8793, not in git). hrono at the
  commit of the cold build start (recorded in the README).
- Models as the webERP tree: condense and judge haiku, brief and
  brief-upper sonnet, all through claude-code (billed to the subscription;
  costs below are API-equivalent from `hrono usage`); embedding
  ibm-granite/granite-embedding-97m-multilingual-r2. Default prompts.
- Tree `streamlink`: lookups off, insights off, so the core mechanism is
  measured. The lookups-on case is covered by the two webERP syncs already
  recorded (2026-11-weberp: 5 files $35.35, 27 files $28.48, against a
  $60.28 build).

## Procedure

1. Cold build at c₀ (`hrono tree maintain`).
2. For each step: move the pin (`pin.git` master) to the step's commit, run
   `hrono tree sync`, wait for it, keep the job report, and copy the
   database (`db/step-NN.db`). Settle is not run; `settle_due` is recorded.
3. At the last step, a cold build of the same commit in a fresh workspace
   with no cache, twice, for the incremental-vs-cold and cold-vs-cold
   agreement.
4. `measure.py` reads consecutive database copies and the job reports and
   writes `steps.csv`.

## Measurements per step

Diff size (files; sections added, changed, deleted); LLM calls, tokens and
API-equivalent cost by role; wall time; sections placed, parked in the
incubator, new topics; repairs; leaves judged and the verdicts; briefs
rewritten (leaf, upper); unchanged sections that moved topic; topics with
changed members left un-briefed and un-judged; misfit; `settle_due`.

## Amendment 1 (2026-11-09, before any fidelity result): cold builds in parallel

To save time, the two cold builds at step 18's commit (`1bd90e9a2`) were
started while syncs 3-18 were still running, each in a fresh workspace
with its own database and no cache (`~/hrono-incremental/cold1`, `cold2`,
servers on 8794 and 8795). They share the subscription with the syncs, so
wall times overlap; cost and call counts are per job and unaffected. The
clustering seed is fixed in code, so the two cold builds differ only by
the LLM's condensations and briefs; that is the noise floor measured.
`fidelity.py` compares the section -> leaf assignments (sections matched by
path, byte offset and content hash) with ARI and AMI.
