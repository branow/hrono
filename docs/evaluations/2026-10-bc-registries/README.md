# Evaluation: hrono on BC Registries (October 2026)

The first time hrono was run end to end on a real, large, multi-repository
corpus that no model knows from training. This folder keeps how it was run,
every attempt and failure, the fixes each failure produced, and the raw
metrics, so later work can compare against it.

- `README.md` (this file): the plan, the setup, and a step-by-step log.
- `findings.md`: every problem found, numbered, with its status.
- `data/<snapshot>/`: metrics exported from the eval database by
  `scripts/export_metrics.py`. Each snapshot directory is described below.
- `scripts/`: the scripts the eval ran (`pin.sh`, `replay.sh`, the `h`
  CLI wrapper, `export_metrics.py`).

## The plan

The evaluation has four stages, and each one ends with a review in the
dashboard before the next starts.

1. **Cold build at a past snapshot.** Pin each repository about two years
   back and build the tree from nothing.
2. **Incremental replay.** Move the repositories forward month by month and
   run `hrono tree sync` after each step. Record what each sync touched,
   compared with the size of the diff, plus time and cost. Then compare
   against a fresh cold build at the final snapshot.
3. **Question set.** About 30 questions at the final snapshot, tiered from
   simple lookups through cross-repository architecture questions to
   implementation tasks. Each has an expected answer grounded in files.
4. **Agents A/B.** Agent A gets only the clones. Agent B gets the clones plus
   the exported tree and `hrono recall`. Compare correctness, tokens, tool
   calls and time per tier. Wherever B is not better, find out why and fix
   hrono.

Status as of this commit: stage 1 done (cold build plus one incremental
sync). Stages 3 and 4 were run on the stage 1 tree as their own evaluation,
`../2026-10-bc-registries-agents/`. Stage 2 not started.

## Corpus

BC Registries, the Government of British Columbia's business registry
(`github.com/bcgov`). It was chosen because it is large, its repositories
interact, its history is long and active, and it is obscure: 10–21 stars per
repository, so a model cannot answer from memory.

| Repository | What it is | Pinned commit (last before 2024-10-01) |
|---|---|---|
| lear | legal-api (the registry), colin-api, queue services, jobs | `a30995be5` 2024-09-27 |
| sbc-auth | auth-api, auth-web (Vue), account/org/permission services | `e76103cf` 2024-09-25 |
| sbc-pay | pay-api, pay-queue, bcol-api, fees and invoices | `ac82a1c9` 2024-09-27 |
| business-filings-ui | Vue front end over legal-api | `6af0a43e` 2024-09-24 |

The repositories call each other over REST: legal-api is configured with
`AUTH_API_URL`, `PAY_API_URL` and `NAMEX_API_URL`, and the UI uses shared
component packages. Runners-up were NAV familie-ba-sak (Norwegian
identifiers, 44% bot commits on the frontend) and Helsinki Linked Events
(choppy history).

## Setup

All of it is outside the repository, in one workspace folder
(`~/hrono-eval` on the machine that ran it; about 1.8 GB after stage 1,
none of it committed), with `scripts/` copied to `bin/`:

| Path | Size | What it is |
|---|---|---|
| `upstream/<repo>` | 282 MB | Full clones of the four repositories from GitHub. |
| `mirror/<repo>.git` | <1 MB | Bare repositories the git sources point at (see below). |
| `db/hrono.db` | 432 MB | The live database: tree `bcreg` after sync 0. |
| `db/after-sync0.db` | 437 MB | A `.backup` of the state exported as `data/01-cold-build-and-sync0`. |
| `db/snapshot-build1.db` | 431 MB | A `.backup` after the cold build, before sync 0. |
| `db/cache/` | 246 MB | Source clones and the CLI work dir; rebuilt by a sync. |
| `hrono.key` | | The master key for all three databases. |
| `home/`, `token` | | CLI profile `eval` and its admin token, used through `scripts/h`. |
| `*.start`, `*.end`, `serve*.log` | | Timestamps and server logs of each run. |

- A git source fetches its remote's HEAD and has no ref option, so
  `scripts/pin.sh <date>` force-pushes the last first-parent commit before
  that date to each mirror's `main`. That is how history gets replayed.
- The sources point at `mirror/` by absolute path, so a copied database
  can be browsed and queried elsewhere but syncs only where the mirrors are.
- The snapshots are kept to rerun a stage from a known state; the next
  stages start from `db/hrono.db`.
- One server, `hrono serve --port 8787`, started with
  `HRONO_LLM_CONCURRENCY=8` (4 for the first 15 minutes) under `nohup`.

Registered configuration:

| Item | Value |
|---|---|
| connection `claude` | provider `claude-code` (the operator's Claude subscription) |
| model `emb` | `sentence-transformers/all-MiniLM-L6-v2`, in-process |
| model `condense` | `haiku` via `claude`, role `condense` |
| model `brief` | `sonnet` via `claude`, role `brief` |
| model `brief-upper` | `sonnet` via `claude`, role `brief-upper` |
| model `judge` | `haiku` via `claude`, role `judge` |
| sources | the four mirrors, `auth: {"method": "none"}`, no filter |
| tree `bcreg` | all four sources |

## Stage 1 log

Times are UTC. The job ids match `data/*/jobs.json` and
`data/*/calls_by_run.csv`.

### 0. Before the build: packing (commit `9e8318b`)

Condense made one `claude` call per section. Every call carries the CLI's
fixed harness (~19k cached tokens, several seconds), and the README's
measurement was 421 sections taking 70 minutes and $16. Condense now packs
up to 8 sections or 32 KB into one call. Each section is rendered through
the unchanged template and wrapped as a nonce-tagged task, and anything
missing or conversational in the answer falls back to a single call. On
real Haiku, one call answered 5 tasks in 6 s.

### 1. Attempt 1: `job_19f5efd9`, 09:21 to 09:56 2026-10-08, failed

- Ingest: 9,827 sections (8,505 distinct, 33.7 MB). lear 4,592,
  sbc-auth 2,535, sbc-pay 2,092, business-filings-ui 608. Splitting took
  about 2 minutes; embedding took about 8 minutes (2,016 in-process
  batches).
- Condense at width 4: ~5.2 sections per pack, 31.8 s per call (max 60 s),
  ~2,550 output tokens per pack. Projected: 4.5 hours.
- At about 09:36 the server was restarted with width 8. The job left
  running by the dead worker was requeued and resumed (recovery works), and
  the 94 condensations already stored were kept. The restart left an
  orphaned `claude -p` subprocess (finding E8).
- Failed with `error_max_turns` on a pack holding `vfs_fonts.js` (a
  vendored base64 font) and a large OpenAPI YAML. 1,484 condensed. A single
  failed call stopped the whole op.
- Fix `4d5e8b2`: the CLI raises `Unfinished` on max turns. A failed pack is
  answered one section at a time, and a section that is still unfinished
  alone is recorded as refused (`unfinished`).

### 2. Attempt 2: `job_67c3ea34`, 10:13 to 10:55, failed

- Condense at width 8: about 94 sections per minute.
- Failed on one `429` from the subscription at 4,534 condensed. The next
  call went through; the CLI client had no retry.
- Fix `5e5f211`: 429/503/529 are retried at 10, 30 and 90 s.
- The server was also killed at its 2-hour mark: it had been started inside
  the agent's background shell, which has a time limit. It runs under
  `nohup` from then on.

### 3. Attempt 3: `job_a161f199`, 12:15 to 12:44, failed

- Failed when one call timed out at 300 s on a pack holding
  `certificateSeal.html`, a 245 KB file that is one line of inline base64.
  5,482 condensed.
- An audit of all 9,827 sections found **758 sections (17% of the bytes)
  that were encoded data**: base64 images and fonts inlined in HTML report
  and email templates, `vfs_fonts.js`, `faker.js` and `cheerio.js` under
  `tests/performance/libs`, and gold-file JSON holding base64 PDFs.
- Fix `8f8d3aa`: the split drops any section where whitespace-free runs of
  400+ bytes cover more than half of it. The corpus went from 9,827 to
  9,069 sections.

### 4. Attempt 4: `job_39bf368f`, 12:49 to 14:36, failed

- Condense finished (8,281 condensed, 0 refused). Clustering made 489
  leaves. Briefs were written until brief 367 of 489.
- Failed on a `429` that outlasted the 130 s backoff. This was the
  subscription's usage limit, which the agent driving the eval also
  shares; the agent was paused by the same limit.
- Fix `a362385`: after the short backoff, a busy upstream is retried every
  5 minutes for up to 6 hours. The worker's heartbeat runs on its own
  thread, so a waiting job is not reclaimed. Between waits the client checks
  its job's row, so a run that is stopped stops waiting.

### 5. Attempt 5: `job_e90ed0a1`, 16:33 to 16:47 2026-10-09, succeeded

- Resumed after the usage window reset. The server was restarted onto
  `a362385` partway through; the job was requeued and finished.
- Result (`data/00-cold-build/`): 9,069 sections in 489 leaves, then 25,
  then 2, then the root. Leaf size: median 16, min 6, p90 35, max 89.
  **66 leaves were over the repair cap of 30.** 27% of members were
  noise-attached, and 202 of 489 leaves span more than one repository.
- Cost over all five attempts (`usage_by_run.txt`): 1,240 condense calls
  and 527 brief calls, **about $62 API-equivalent** on the
  subscription (an estimate, not money spent), and about 13.8 hours of
  model time. The wall clock across the attempts that did work was about
  3 h 45 min.

### 6. Incremental sync 0: `job_24ce131b`, 16:50 to 17:12, succeeded

- Inspecting the tree showed SchemaSpy documentation sites in sbc-auth and
  sbc-pay that vendor `bower/` copies of jquery, jquery-ui, codemirror and
  bootstrap: 626 sections, and the root brief opened by describing
  "third-party front-end stacks".
- Fix `a7f5771`: `bower/` and `bower_components/` are ignored by default.
- This was applied with `hrono tree sync`, the incremental path, rather
  than a rebuild. 610 sections left and 5 were parked. Stages: update 51 s,
  propagate 533 s (7 judged, 1 propagated), brief 24 s (7 briefs),
  brief-upper 86 s, monitor 101 s, **repair 21 s with 120 splits**,
  adopt 504 s.
- That repair is the cold build's debt, not the change: the cold build left
  66 leaves over the cap, and the first sync split them (135 brief and 31
  brief-upper calls, $11.39 of the sync's cost). Afterwards: 536 leaves,
  median 14, max 50, 18 still over 30.
- Result: `data/01-cold-build-and-sync0/`.

## Stage 1 review notes

- Recall (`data/01-cold-build-and-sync0/recall_samples.md`, five
  questions) finds the right code for most of them: `authorization.py` and
  `role_validator.py` for roles, `update_colin_filings.py` for the COLIN
  sync, `fee_schedule.py` and `payment_service.py` for fees. It also ranks
  email templates, a CI workflow and UI dialogs first for some questions.
- Topic titles are taken from each brief's first words. Many briefs open
  with "This is a set of condensed notes on…", so titles and node URIs read
  like `this-is-a-set-of-condensed-notes-on-the-pytest…` (E19).
- The root has two children whose briefs both describe "the BC Registries
  ecosystem", so the top split carries no meaning (E17).

## Reproducing

```
scripts/pin.sh 2024-10-01                  # mirrors to the snapshot
scripts/h tree maintain bcreg              # cold build
scripts/replay.sh 2024-11-01 2024-12-01    # stage 2: one sync per date
python scripts/export_metrics.py <workspace>/db/hrono.db bcreg data/<name>
```

The server needs `uv sync --extra embed --extra cluster` in the hrono
checkout, and the `claude` CLI signed in.
